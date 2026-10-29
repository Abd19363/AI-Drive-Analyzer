import asyncio
import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db import get_db
from app.models import GoogleAccount, ChatQuery
from app.services.drive_service import list_files_cached
from app.services.gemini_service import (
    GeminiServiceUnavailableError,
    answer_general_query,
)
from app.services.rag_workflow import (
    create_rag_graph,
    search_cached_user_documents,
)
from app.services.query_intent_service import (
    QueryIntent,
    classify_query_intent,
    match_files_by_title,
    requested_sheet_name,
)
from app.services.guardrail_service import is_query_about_media, MEDIA_QUERY_RESPONSE
from app.services.gemini_service import synthesize_answer
from app.services.query_cache_service import (
    QueryCacheUnavailableError,
    cache_lock_key,
    cached_answer_response,
    coalesce_query,
    lookup_cached_answer,
    store_cached_answer,
    store_user_decision,
)

router = APIRouter(prefix="/api/rag", tags=["rag"])
logger = logging.getLogger(__name__)

class QuestionRequest(BaseModel):
    user_id: str
    query: str
    selected_file_ids: Optional[List[str]] = None
    query_id: Optional[str] = None
    allow_general_answer: bool = False
    matched_file_ids: Optional[List[str]] = None


class QueryIntentRequest(BaseModel):
    user_id: str
    query: str
    selected_file_ids: Optional[List[str]] = None
    matched_file_ids: Optional[List[str]] = None
    allow_general_answer: bool = False


class QueryDecisionRequest(BaseModel):
    user_id: str
    query: str
    intent: str
    selected_file_ids: Optional[List[str]] = None
    decision: str


class CancelQueryRequest(BaseModel):
    user_id: str
    query_id: str

# Instantiate the compiled LangGraph
rag_graph = create_rag_graph()
_active_queries: dict[str, tuple[str, asyncio.Task]] = {}


def _classify_request_intent(
    query: str,
    selected_file_ids: List[str],
    matched_file_ids: Optional[List[str]] = None,
) -> QueryIntent:
    intent = classify_query_intent(
        query,
        has_selected_files=bool(selected_file_ids or matched_file_ids),
    )
    if intent in {"capabilities", "assistant_info"}:
        return intent
    if is_query_about_media(query):
        return "media"
    return intent


def _requires_document_analysis(intent: QueryIntent) -> bool:
    return intent not in {"capabilities", "assistant_info", "direct_answer", "media"}


def _answer_response(
    query: str,
    intent: QueryIntent,
    answer: str,
    *,
    analysis_required: bool,
    needs_general_confirmation: bool = False,
    candidate_files: Optional[List[str]] = None,
    safe_embedded_files: Optional[List[str]] = None,
    retrieved_sources: Optional[List[Dict[str, Any]]] = None,
    auto_discovered: bool = False,
    answer_source: str = "google_drive",
    cached: bool = False,
    matched_file_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "query": query,
        "intent": intent,
        "answer": answer,
        "answer_source": answer_source,
        "cached": cached,
        "analysis_required": analysis_required,
        "needs_general_confirmation": needs_general_confirmation,
        "auto_discovered": auto_discovered,
        "candidate_files": candidate_files or [],
        "safe_embedded_files": safe_embedded_files or [],
        "matched_file_ids": matched_file_ids or [],
        "blocked_confidential_files": [],
        "retrieved_sources": retrieved_sources or [],
    }


async def _save_answer(
    db: AsyncSession,
    user_id: str,
    query: str,
    answer: str,
    intent: str,
    answer_kind: str,
    selected_file_ids: Optional[List[str]] = None,
    identified_files: Optional[List[str]] = None,
    source_file_ids: Optional[List[str]] = None,
    source_file_names: Optional[List[str]] = None,
    document_versions: Optional[Dict[str, Optional[str]]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> None:
    db.add(ChatQuery(
        user_id=user_id,
        query_text=query,
        identified_files=identified_files or [],
        skipped_files=[],
        answer_text=answer,
    ))
    await db.commit()
    await store_cached_answer(
        db,
        user_id,
        query,
        intent,
        answer,
        answer_kind,
        selected_file_ids=selected_file_ids,
        source_file_ids=source_file_ids,
        source_file_names=source_file_names,
        document_versions=document_versions,
        sources=sources,
    )


async def _lookup_answer_cache(
    db: AsyncSession,
    user_id: str,
    query: str,
    intent: str,
    selected_file_ids: Optional[List[str]],
    *,
    allow_general_answer: bool = False,
) -> Optional[Dict[str, Any]]:
    try:
        entry = await lookup_cached_answer(
            db,
            user_id,
            query,
            intent,
            selected_file_ids,
            allow_general_answer=allow_general_answer,
        )
    except QueryCacheUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "The answer cache is unavailable. Apply the latest backend "
                "schema before retrying."
            ),
        ) from exc
    if not entry:
        return None
    logger.info("[RAG] Answer cache hit: kind=%s intent=%s", entry.answer_kind, intent)
    db.add(ChatQuery(
        user_id=user_id,
        query_text=query,
        identified_files=entry.source_file_names or [],
        skipped_files=[],
        answer_text=entry.answer_text,
    ))
    await db.commit()
    return cached_answer_response(query, intent, entry)


def _cache_document_evidence(
    safe_files: List[Dict[str, Any]],
    retrieved_chunks: List[Dict[str, Any]],
) -> tuple[List[str], List[str], Dict[str, Optional[str]], List[Dict[str, Any]]]:
    versions_by_name = {
        file_info.get("name"): (
            str(file_info.get("file_id")),
            file_info.get("source_modified_time"),
        )
        for file_info in safe_files
        if file_info.get("file_id")
    }
    source_ids: List[str] = []
    document_versions: Dict[str, Optional[str]] = {}
    source_names: List[str] = []

    for file_info in safe_files:
        file_id = file_info.get("file_id")
        version = file_info.get("source_modified_time")
        if file_id and version:
            file_id = str(file_id)
            source_ids.append(file_id)
            document_versions[file_id] = str(version)
            if file_info.get("name"):
                source_names.append(file_info["name"])

    sources = []
    seen_sources = set()
    for chunk in retrieved_chunks:
        file_id = chunk.get("file_id")
        file_name = chunk.get("file_name")
        source_version = chunk.get("source_modified_time")
        if file_id and source_version:
            file_id = str(file_id)
            source_ids.append(file_id)
            document_versions[file_id] = str(source_version)
            if file_name:
                source_names.append(file_name)
        elif file_name in versions_by_name:
            matched_id, matched_version = versions_by_name[file_name]
            if matched_version:
                source_ids.append(matched_id)
                document_versions[matched_id] = str(matched_version)
                source_names.append(file_name)

        key = (file_name, round(float(chunk.get("similarity", 0)), 3))
        if file_name and key not in seen_sources:
            seen_sources.add(key)
            sources.append({
                "file_name": file_name,
                "similarity": key[1],
            })

    return (
        list(dict.fromkeys(source_ids)),
        list(dict.fromkeys(source_names)),
        document_versions,
        sources,
    )


@router.post("/intent")
async def classify_question(
    payload: QueryIntentRequest,
    db: AsyncSession = Depends(get_db),
):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    selected_file_ids = payload.selected_file_ids or []
    matched_file_ids = payload.matched_file_ids or []
    initial_intent = _classify_request_intent(
        query,
        selected_file_ids,
        matched_file_ids,
    )

    cache_started_at = time.perf_counter()
    cached_response = await _lookup_answer_cache(
        db,
        payload.user_id,
        query,
        initial_intent,
        selected_file_ids,
        allow_general_answer=payload.allow_general_answer,
    )
    if cached_response:
        logger.info(
            "[RAG] Answer cache hit returned in %.3fs",
            time.perf_counter() - cache_started_at,
        )
        return {
            "intent": initial_intent,
            "analysis_required": False,
            "matched_file_ids": matched_file_ids,
            "cached_response": cached_response,
        }
    logger.info(
        "[RAG] Answer cache miss checked in %.3fs",
        time.perf_counter() - cache_started_at,
    )

    if payload.allow_general_answer:
        return {
            "intent": initial_intent,
            "analysis_required": False,
            "matched_file_ids": matched_file_ids,
        }

    if not matched_file_ids and not selected_file_ids:
        account_result = await db.execute(
            select(GoogleAccount).where(GoogleAccount.user_id == payload.user_id)
        )
        google_account = account_result.scalars().first()
        if google_account:
            try:
                available_files = await asyncio.to_thread(
                    list_files_cached, google_account, page_size=100
                )
            except Exception as exc:
                logger.exception("Failed to load Drive file names for query routing.")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to check Drive file names for this question.",
                ) from exc
            matched_files = match_files_by_title(query, available_files)
            matched_file_ids = [
                file_info["id"]
                for file_info in matched_files
                if file_info.get("id")
            ]

    intent = _classify_request_intent(
        query,
        selected_file_ids,
        matched_file_ids,
    )
    if intent != initial_intent:
        cached_response = await _lookup_answer_cache(
            db,
            payload.user_id,
            query,
            intent,
            selected_file_ids,
        )
        if cached_response:
            logger.info(
                "[RAG] Answer cache hit after file-title routing in %.3fs",
                time.perf_counter() - cache_started_at,
            )
            return {
                "intent": intent,
                "analysis_required": False,
                "matched_file_ids": matched_file_ids,
                "cached_response": cached_response,
            }

    logger.info(
        "[RAG] Intent routing after cache miss took %.3fs",
        time.perf_counter() - cache_started_at,
    )
    if payload.allow_general_answer:
        return {
            "intent": intent,
            "analysis_required": False,
            "matched_file_ids": matched_file_ids,
        }

    return {
        "intent": intent,
        "analysis_required": _requires_document_analysis(intent),
        "matched_file_ids": matched_file_ids,
    }


@router.post("/ask")
async def ask_question(payload: QuestionRequest, db: AsyncSession = Depends(get_db)):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    selected_file_ids = payload.selected_file_ids or []
    matched_file_ids = payload.matched_file_ids or []
    intent = _classify_request_intent(
        query,
        selected_file_ids,
        matched_file_ids,
    )
    started_at = time.perf_counter()
    cached_response = await _lookup_answer_cache(
        db,
        payload.user_id,
        query,
        intent,
        selected_file_ids,
        allow_general_answer=payload.allow_general_answer,
    )
    if cached_response:
        logger.info(
            "[RAG] /ask cache hit returned in %.3fs",
            time.perf_counter() - started_at,
        )
        return cached_response

    lock_key = cache_lock_key(
        payload.user_id,
        query,
        intent,
        selected_file_ids,
    )
    async with coalesce_query(lock_key):
        cached_response = await _lookup_answer_cache(
            db,
            payload.user_id,
            query,
            intent,
            selected_file_ids,
            allow_general_answer=payload.allow_general_answer,
        )
        if cached_response:
            logger.info(
                "[RAG] Coalesced request returned cached answer in %.3fs",
                time.perf_counter() - started_at,
            )
            return cached_response

        logger.info("[RAG] /ask cache miss after %.3fs", time.perf_counter() - started_at)
        try:
            response = await _ask_question_uncached(payload, db)
            logger.info(
                "[RAG] Cache miss request completed in %.3fs",
                time.perf_counter() - started_at,
            )
            return response
        except QueryCacheUnavailableError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The answer cache is unavailable. Apply the latest backend "
                    "schema before retrying."
                ),
            ) from exc


async def _ask_question_uncached(
    payload: QuestionRequest,
    db: AsyncSession,
):
    """
    Search approved indexed content first, then inspect Drive candidates. Only
    after both searches fail does the user get an option for a general answer.
    """
    user_id = payload.user_id
    query = payload.query.strip()
    selected_file_ids = payload.selected_file_ids or []

    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    matched_file_ids = payload.matched_file_ids or []
    retrieval_file_ids = selected_file_ids or matched_file_ids
    intent = _classify_request_intent(
        query,
        selected_file_ids,
        matched_file_ids,
    )
    if payload.allow_general_answer and intent not in {
        "capabilities", "assistant_info", "media"
    }:
        try:
            answer = await answer_general_query(query)
        except GeminiServiceUnavailableError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        await _save_answer(
            db, user_id, query, answer, intent, "general",
            selected_file_ids=selected_file_ids,
        )
        await store_user_decision(
            db, user_id, query, intent, "accepted", selected_file_ids
        )
        return _answer_response(
            query,
            intent,
            answer,
            analysis_required=False,
            answer_source="general_knowledge",
            matched_file_ids=matched_file_ids,
        )

    if intent == "capabilities":
        answer = (
            "I can retrieve and answer questions from textual documents including "
            "PDF, DOCX, CSV, XLSX, TXT, JSON, and Markdown files. Google Docs, "
            "Sheets, and Slides are supported through export. Image and video "
            "content is not supported for question answering. You can ask about "
            "information in your connected Drive files, or select files to limit "
            "the search."
        )
    elif intent == "assistant_info":
        answer = (
            "I answer questions using the text of your Drive documents, not just "
            "their filenames. When you select files, I limit the search to those "
            "files; otherwise, I identify likely candidates from your Drive catalog. "
            "For eligible files, I check for sensitive content, extract and index "
            "safe text, then retrieve the document sections most relevant to your "
            "question using semantic similarity and keyword relevance. I generate "
            "an answer from those retrieved sections and provide source references. "
            "If a file is new or has changed, it may need to be downloaded, screened, "
            "extracted, and indexed before it can be searched. I do not analyze "
            "unrelated files to answer general questions about how this process works."
        )
    elif intent == "media":
        answer = MEDIA_QUERY_RESPONSE
    else:
        answer = None

    if answer is not None:
        await _save_answer(
            db, user_id, query, answer, intent, "assistant",
            selected_file_ids=selected_file_ids,
        )
        return _answer_response(
            query,
            intent,
            answer,
            analysis_required=False,
            answer_source="assistant",
        )

    if intent == "direct_answer":
        try:
            answer = await answer_general_query(query)
        except GeminiServiceUnavailableError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        await _save_answer(
            db, user_id, query, answer, intent, "general",
            selected_file_ids=selected_file_ids,
        )
        return _answer_response(
            query,
            intent,
            answer,
            analysis_required=False,
            answer_source="general_knowledge",
        )

    try:
        cached_chunks = await search_cached_user_documents(
            db, user_id, query, retrieval_file_ids
        )
    except Exception as exc:
        logger.exception("Failed to search the indexed document cache.")
        raise HTTPException(
            status_code=500, detail="Failed to search the document cache."
        ) from exc

    if cached_chunks:
        cached_file_names: List[str] = []
        for chunk in cached_chunks:
            file_name = chunk.get("file_name")
            if isinstance(file_name, str) and file_name:
                cached_file_names.append(file_name)
        cached_names: List[str] = list(dict.fromkeys(cached_file_names))
        try:
            answer = await synthesize_answer(
                query,
                cached_chunks,
                [],
                selected_file_names=cached_names,
                auto_discovered=not retrieval_file_ids,
                available_file_names=cached_names,
                intent=intent,
            )
        except GeminiServiceUnavailableError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        source_file_ids, source_names, versions, sources = _cache_document_evidence(
            [],
            cached_chunks,
        )
        await _save_answer(
            db=db,
            user_id=user_id,
            query=query,
            answer=answer,
            intent=str(intent),
            answer_kind="document",
            selected_file_ids=selected_file_ids,
            identified_files=cached_names,
            source_file_ids=source_file_ids,
            source_file_names=source_names or cached_names,
            document_versions=versions,
            sources=sources,
        )
        return _answer_response(
            query,
            intent,
            answer,
            analysis_required=True,
            candidate_files=cached_names,
            safe_embedded_files=cached_names,
            retrieved_sources=sources,
            auto_discovered=not retrieval_file_ids,
            answer_source="google_drive",
            matched_file_ids=matched_file_ids,
        )

    # Validate user & drive connection
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.user_id == user_id))
    google_acc = acc_res.scalars().first()
    if not google_acc:
        answer = (
            "I couldn't find this information in your indexed documents, and "
            "Google Drive isn't connected to check for a matching file. "
            "Would you like me to answer using general knowledge instead?"
        )
        await _save_answer(
            db, user_id, query, answer, intent, "insufficient",
            selected_file_ids=selected_file_ids,
        )
        return _answer_response(
            query,
            intent,
            answer,
            analysis_required=False,
            needs_general_confirmation=True,
            answer_source="insufficient_drive_evidence",
            matched_file_ids=matched_file_ids,
        )

    current_task = asyncio.current_task()
    if payload.query_id and current_task:
        active = _active_queries.get(payload.query_id)
        if active and not active[1].done():
            raise HTTPException(status_code=409, detail="Query ID is already active.")
        _active_queries[payload.query_id] = (user_id, current_task)

        def clear_completed_query(completed_task):
            registered = _active_queries.get(payload.query_id)
            if registered and registered[1] is completed_task:
                _active_queries.pop(payload.query_id, None)

        current_task.add_done_callback(clear_completed_query)

    # Retrieve current file catalog from Google Drive
    catalog_started_at = time.perf_counter()
    try:
        available_files = await asyncio.to_thread(list_files_cached, google_acc, page_size=100)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to access Google Drive: {str(e)}")
    logger.info(
        "[RAG] Drive catalog loaded in %.3fs (%d files)",
        time.perf_counter() - catalog_started_at,
        len(available_files),
    )

    # Initialize Graph State
    initial_state = {
        "db": db,
        "user_id": user_id,
        "google_account": google_acc,
        "query": query,
        "intent": intent,
        "selected_file_ids": retrieval_file_ids,
        "available_files": available_files,
        "candidate_files": [],
        "safe_files": [],
        "confidential_files": [],
        "retrieved_chunks": [],
        "answer": "",
        "auto_discovered": len(retrieval_file_ids) == 0,
        "is_media_query": False,
        "needs_general_confirmation": False,
        "requested_sheet_name": None,
        "sheet_scoped_safe_files": [],
        "sheet_search_file_names": [],
    }

    # Execute LangGraph RAG Workflow
    workflow_started_at = time.perf_counter()
    try:
        final_state = await rag_graph.ainvoke(initial_state)
    except GeminiServiceUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        import traceback
        print(f"[RAG ERROR] Workflow failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"RAG execution error: {str(e)}")
    finally:
        logger.info(
            "[RAG] Full workflow finished in %.3fs",
            time.perf_counter() - workflow_started_at,
        )

    sheet_scope = (
        final_state.get("requested_sheet_name") or requested_sheet_name(query)
    )
    safe_files = final_state.get("safe_files", [])
    if sheet_scope:
        safe_files = final_state.get("sheet_scoped_safe_files", [])

    if final_state.get("needs_general_confirmation"):
        retrieved_chunks = final_state.get("retrieved_chunks", [])
        source_file_ids, source_names, versions, sources = _cache_document_evidence(
            safe_files,
            retrieved_chunks,
        )
        await store_cached_answer(
            db,
            user_id,
            query,
            intent,
            final_state.get("answer", ""),
            "insufficient",
            selected_file_ids=selected_file_ids,
            source_file_ids=source_file_ids,
            source_file_names=source_names,
            document_versions=versions,
            sources=sources,
        )
        return _answer_response(
            query,
            intent,
            final_state.get("answer", ""),
            analysis_required=False,
            needs_general_confirmation=True,
            candidate_files=source_names,
            safe_embedded_files=source_names,
            retrieved_sources=sources,
            answer_source="insufficient_drive_evidence",
            matched_file_ids=matched_file_ids,
        )

    retrieved_chunks = final_state.get("retrieved_chunks", [])
    source_file_ids, source_names, versions, sources = _cache_document_evidence(
        safe_files,
        retrieved_chunks,
    )
    answer = final_state.get("answer") or ""
    await store_cached_answer(
        db,
        user_id,
        query,
        intent,
        answer,
        "document",
        selected_file_ids=selected_file_ids,
        source_file_ids=source_file_ids,
        source_file_names=source_names,
        document_versions=versions,
        sources=sources,
    )

    return {
        "query": query,
        "intent": intent,
        "answer": answer,
        "answer_source": "google_drive",
        "cached": False,
        "analysis_required": True,
        "needs_general_confirmation": False,
        "auto_discovered": final_state.get("auto_discovered", False),
        "candidate_files": (
            [file_info.get("name") for file_info in safe_files]
            if sheet_scope
            else [f.get("name") for f in final_state.get("candidate_files", [])]
        ),
        "safe_embedded_files": [f.get("name") for f in safe_files],
        "matched_file_ids": matched_file_ids,
        "blocked_confidential_files": final_state.get("confidential_files", []),
        "retrieved_sources": sources,
    }


@router.post("/cancel")
async def cancel_question(payload: CancelQueryRequest):
    active = _active_queries.get(payload.query_id)
    if not active or active[1].done():
        return {"query_id": payload.query_id, "cancelled": False, "detail": "Query is not running."}
    if active[0] != payload.user_id:
        raise HTTPException(status_code=404, detail="Active query not found.")

    active[1].cancel()
    return {"query_id": payload.query_id, "cancelled": True}


@router.post("/fallback-decision")
async def record_fallback_decision(
    payload: QueryDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if payload.decision not in {"accepted", "declined"}:
        raise HTTPException(status_code=400, detail="Decision must be accepted or declined.")

    try:
        await store_user_decision(
            db,
            payload.user_id,
            query,
            payload.intent,
            payload.decision,
            payload.selected_file_ids,
        )
    except QueryCacheUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="The answer cache is unavailable. Apply the latest backend schema.",
        ) from exc

    return {"recorded": True}


@router.get("/history")
async def get_query_history(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieves previous questions and answers.
    """
    res = await db.execute(
        select(ChatQuery)
        .where(ChatQuery.user_id == user_id)
        .order_by(ChatQuery.created_at.desc())
        .limit(20)
    )
    records = res.scalars().all()
    return {
        "history": [
            {
                "id": str(r.id),
                "query": r.query_text,
                "answer": r.answer_text,
                "identified_files": r.identified_files,
                "skipped_files": r.skipped_files,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in records
        ]
    }
