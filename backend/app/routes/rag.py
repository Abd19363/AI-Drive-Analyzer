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
)
from app.services.guardrail_service import is_query_about_media, MEDIA_QUERY_RESPONSE
from app.services.gemini_service import synthesize_answer

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
    allow_general_answer: bool = False


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
) -> Dict[str, Any]:
    return {
        "query": query,
        "intent": intent,
        "answer": answer,
        "analysis_required": analysis_required,
        "needs_general_confirmation": needs_general_confirmation,
        "auto_discovered": auto_discovered,
        "candidate_files": candidate_files or [],
        "safe_embedded_files": safe_embedded_files or [],
        "blocked_confidential_files": [],
        "retrieved_sources": retrieved_sources or [],
    }


async def _save_answer(
    db: AsyncSession,
    user_id: str,
    query: str,
    answer: str,
    identified_files: Optional[List[str]] = None,
) -> None:
    db.add(ChatQuery(
        user_id=user_id,
        query_text=query,
        identified_files=identified_files or [],
        skipped_files=[],
        answer_text=answer,
    ))
    await db.commit()


@router.post("/intent")
async def classify_question(
    payload: QueryIntentRequest,
    db: AsyncSession = Depends(get_db),
):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    matched_file_ids: List[str] = []
    selected_file_ids = payload.selected_file_ids or []
    if not payload.allow_general_answer:
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
    if payload.allow_general_answer:
        return {
            "intent": intent,
            "analysis_required": False,
            "matched_file_ids": [],
        }

    return {
        "intent": intent,
        "analysis_required": _requires_document_analysis(intent),
        "matched_file_ids": matched_file_ids,
    }


@router.post("/ask")
async def ask_question(payload: QuestionRequest, db: AsyncSession = Depends(get_db)):
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
    retrieval_file_ids = matched_file_ids or selected_file_ids
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
        await _save_answer(db, user_id, query, answer)
        return _answer_response(
            query, intent, answer, analysis_required=False
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
        await _save_answer(db, user_id, query, answer)
        return _answer_response(
            query, intent, answer, analysis_required=False
        )

    if intent == "direct_answer":
        try:
            answer = await answer_general_query(query)
        except GeminiServiceUnavailableError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        await _save_answer(db, user_id, query, answer)
        return _answer_response(
            query, intent, answer, analysis_required=False
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
        cached_names = list(dict.fromkeys(
            chunk.get("file_name")
            for chunk in cached_chunks
            if chunk.get("file_name")
        ))
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
        await _save_answer(db, user_id, query, answer, cached_names)
        return _answer_response(
            query,
            intent,
            answer,
            analysis_required=True,
            candidate_files=cached_names,
            safe_embedded_files=cached_names,
            retrieved_sources=[
                {
                    "file_name": chunk.get("file_name"),
                    "similarity": round(chunk.get("similarity", 0), 3),
                }
                for chunk in cached_chunks
            ],
            auto_discovered=not retrieval_file_ids,
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
        await _save_answer(db, user_id, query, answer)
        return _answer_response(
            query,
            intent,
            answer,
            analysis_required=False,
            needs_general_confirmation=True,
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

    if final_state.get("needs_general_confirmation"):
        return _answer_response(
            query,
            intent,
            final_state.get("answer", ""),
            analysis_required=False,
            needs_general_confirmation=True,
        )

    return {
        "query": query,
        "intent": intent,
        "answer": final_state.get("answer"),
        "analysis_required": True,
        "needs_general_confirmation": False,
        "auto_discovered": final_state.get("auto_discovered", False),
        "candidate_files": [f.get("name") for f in final_state.get("candidate_files", [])],
        "safe_embedded_files": [f.get("name") for f in final_state.get("safe_files", [])],
        "blocked_confidential_files": final_state.get("confidential_files", []),
        "retrieved_sources": [
            {"file_name": c.get("file_name"), "similarity": round(c.get("similarity", 0), 3)}
            for c in final_state.get("retrieved_chunks", [])
        ]
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
