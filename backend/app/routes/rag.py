import asyncio
import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db import get_db
from app.models import GoogleAccount, ChatQuery, QueryTelemetry, User
from app.services.drive_service import get_cached_file_catalog, list_files_cached
from app.services.gemini_service import (
    GeminiServiceUnavailableError,
    answer_general_query,
    classify_general_vs_drive_query,
    synthesize_answer,
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
    is_fast_general_knowledge_query,
    is_drive_inventory_query,
    extract_drive_inventory_target,
    _DOCUMENT_REQUEST_PATTERN,
    _DOCUMENT_SEARCH_PATTERN,
    _PERSONAL_CONTEXT_PATTERN,
    _BUSINESS_DATA_PATTERN,
)
from app.services.guardrail_service import is_query_about_media, MEDIA_QUERY_RESPONSE
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
    force_drive_search: bool = False
    intent: Optional[QueryIntent] = None


class QueryIntentRequest(BaseModel):
    user_id: str
    query: str
    selected_file_ids: Optional[List[str]] = None
    matched_file_ids: Optional[List[str]] = None
    allow_general_answer: bool = False
    force_drive_search: bool = False


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
    return intent not in {"capabilities", "assistant_info", "direct_answer", "media", "drive_inventory"}


async def _resolve_query_route(
    db: AsyncSession,
    query: str,
    user_id: str,
    selected_file_ids: List[str],
    matched_file_ids: List[str],
    force_drive_search: bool,
) -> tuple[QueryIntent, List[str]]:
    intent = _classify_request_intent(
        query,
        selected_file_ids,
        matched_file_ids,
    )

    if not force_drive_search and not selected_file_ids and not matched_file_ids:
        if is_fast_general_knowledge_query(query):
            return "direct_answer", []

        if intent in {"capabilities", "assistant_info", "direct_answer", "media", "drive_inventory"}:
            return intent, []

    google_account = None
    available_files = None
    title_matches = []
    if not selected_file_ids and not matched_file_ids:
        account_result = await db.execute(
            select(GoogleAccount).where(GoogleAccount.user_id == user_id)
        )
        google_account = account_result.scalars().first()
        if google_account:
            available_files = get_cached_file_catalog(
                google_account,
                page_size=100,
                expand_folders=False,
            )
            if not available_files:
                try:
                    available_files = await asyncio.to_thread(
                        list_files_cached,
                        google_account,
                        page_size=100,
                        expand_folders=False,
                    )
                except Exception as exc:
                    logger.warning("[RAG] Drive file catalog load warning: %s", exc)
                    available_files = []

            if available_files:
                strong_title_matches = match_files_by_title(
                    query,
                    available_files,
                    minimum_score=20,
                )
                if strong_title_matches:
                    strong_ids = [
                        file_info["id"]
                        for file_info in strong_title_matches
                        if file_info.get("id")
                    ]
                    logger.info(
                        "[RAG] Strong filename match routed query directly to %d file(s), skipping general-vs-Drive classification.",
                        len(strong_ids),
                    )
                    return (
                        _classify_request_intent(query, selected_file_ids, strong_ids),
                        strong_ids,
                    )
                title_matches = match_files_by_title(query, available_files)

    if not force_drive_search and not selected_file_ids and not matched_file_ids:
        has_doc_indicators = (
            bool(_DOCUMENT_REQUEST_PATTERN.search(query))
            or bool(_DOCUMENT_SEARCH_PATTERN.search(query))
            or bool(_PERSONAL_CONTEXT_PATTERN.search(query))
            or bool(_BUSINESS_DATA_PATTERN.search(query))
        )
        if not has_doc_indicators and await classify_general_vs_drive_query(query, available_files):
            return "direct_answer", []

    if not selected_file_ids and not matched_file_ids:
        matched_file_ids = [
            file_info["id"]
            for file_info in title_matches
            if file_info.get("id")
        ]

    return (
        _classify_request_intent(query, selected_file_ids, matched_file_ids),
        matched_file_ids,
    )


def _handle_drive_inventory_query(
    query: str,
    available_files: List[Dict[str, Any]],
) -> tuple[str, List[str]]:
    """Answers file existence and drive inventory queries directly from Drive catalog."""
    target, is_vague = extract_drive_inventory_target(query)

    if is_vague:
        answer = (
            "Please specify the file name, document title, or topic you would like me to check "
            "in your Google Drive (for example: *'Is my resume in my drive?'* or *'Check whether "
            "Form-33 is in my drive'*)."
        )
        return answer, []

    if target == "LIST_ALL":
        textual_files = [
            f for f in available_files
            if f.get("mimeType") != "application/vnd.google-apps.folder"
        ]
        if not textual_files:
            return "There are currently no document files found in your connected Google Drive.", []

        file_lines = []
        for f in textual_files[:15]:
            name = f.get("name", "Untitled")
            file_lines.append(f"- 📄 **{name}**")

        remaining = len(textual_files) - 15
        more_note = f"\n\n*...and {remaining} more file(s).*" if remaining > 0 else ""
        answer = (
            f"Here are the document(s) currently available in your Google Drive ({len(textual_files)} total):\n\n"
            + "\n".join(file_lines)
            + more_note
            + "\n\nYou can ask questions about the contents of any of these files or select them on the left."
        )
        return answer, [f.get("name") for f in textual_files[:5]]

    # Specific target search across available_files
    matched = match_files_by_title(target, available_files, minimum_score=15)
    if not matched:
        import re
        q_words = [w.lower() for w in re.split(r"[^a-zA-Z0-9]+", target) if len(w) >= 2]
        fallback_matched = []
        for f in available_files:
            fname = (f.get("name") or "").lower()
            if any(w in fname for w in q_words):
                fallback_matched.append(f)
        matched = fallback_matched[:3]

    if matched:
        cand_names = [f.get("name") for f in matched if f.get("name")]
        file_bullets = []
        for f in matched:
            name = f.get("name", "Untitled")
            mod = f.get("modifiedTime", "")
            date_str = f" (modified {mod[:10]})" if mod else ""
            file_bullets.append(f"- 📄 **{name}**{date_str}")

        answer = (
            f"Yes, I found matching file(s) in your Google Drive:\n\n"
            + "\n".join(file_bullets)
            + f"\n\nWould you like me to answer questions or analyze information from {'this document' if len(matched) == 1 else 'these documents'}?"
        )
        return answer, cand_names
    else:
        sample_files = [f.get("name") for f in available_files[:5] if f.get("name")]
        sample_text = (
            "\n\nSome of the files in your Drive include:\n"
            + "\n".join(f"- 📄 {name}" for name in sample_files)
            if sample_files else ""
        )
        answer = (
            f"I checked your Google Drive files, but found no document matching **\"{target}\"**."
            + sample_text
            + "\n\nPlease check the spelling or select a file from your Drive list on the left."
        )
        return answer, []


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


async def _record_telemetry(
    db: AsyncSession,
    user_id: str,
    latency_ms: float,
    cache_hit: bool,
    api_called: bool,
    intent: str = "general",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    query_id: Optional[str] = None,
) -> None:
    try:
        user_res = await db.execute(select(User.email).where(User.id == user_id))
        user_email = user_res.scalar() or "User"
        total_tokens = prompt_tokens + completion_tokens
        telemetry = QueryTelemetry(
            query_id=query_id,
            user_id=user_id,
            user_email=user_email,
            latency_ms=max(latency_ms, 1.0),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cache_hit=cache_hit,
            api_called=api_called,
            intent=intent,
        )
        db.add(telemetry)
        await db.commit()
    except Exception as e:
        logger.warning("[TELEMETRY] Failed to record query telemetry: %s", e)


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
    primary_responding_file = (
        (source_file_names[0] if source_file_names else None)
        or (identified_files[0] if identified_files else None)
    )
    db.add(ChatQuery(
        user_id=user_id,
        query_text=query,
        identified_files=identified_files or [],
        skipped_files=[],
        source_file_names=source_file_names or [],
        responding_file_name=primary_responding_file,
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
    primary_file = entry.source_file_names[0] if entry.source_file_names else None
    db.add(ChatQuery(
        user_id=user_id,
        query_text=query,
        identified_files=entry.source_file_names or [],
        skipped_files=[],
        source_file_names=entry.source_file_names or [],
        responding_file_name=primary_file,
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

        sim_val = round(float(chunk.get("similarity", 0)), 3)
        if sim_val < 0.15:
            continue
        key = (file_name, sim_val)
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

    intent, matched_file_ids = await _resolve_query_route(
        db,
        query,
        payload.user_id,
        selected_file_ids,
        matched_file_ids,
        payload.force_drive_search,
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
        "[RAG] Intent routing after cache miss took %.3fs (intent=%s, analysis_required=%s)",
        time.perf_counter() - cache_started_at,
        intent,
        _requires_document_analysis(intent),
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

    started_at = time.perf_counter()
    selected_file_ids = payload.selected_file_ids or []
    matched_file_ids = payload.matched_file_ids or []
    if payload.intent is None:
        initial_intent = _classify_request_intent(
            query,
            selected_file_ids,
            matched_file_ids,
        )
        cached_response = await _lookup_answer_cache(
            db,
            payload.user_id,
            query,
            initial_intent,
            selected_file_ids,
            allow_general_answer=payload.allow_general_answer,
        )
        if cached_response:
            return cached_response

        if payload.allow_general_answer:
            intent = initial_intent
        else:
            intent, matched_file_ids = await _resolve_query_route(
                db,
                query,
                payload.user_id,
                selected_file_ids,
                matched_file_ids,
                payload.force_drive_search,
            )
            payload.matched_file_ids = matched_file_ids
            if intent != initial_intent:
                cached_response = await _lookup_answer_cache(
                    db,
                    payload.user_id,
                    query,
                    intent,
                    selected_file_ids,
                    allow_general_answer=payload.allow_general_answer,
                )
                if cached_response:
                    return cached_response
    else:
        intent = payload.intent
        cached_response = await _lookup_answer_cache(
            db,
            payload.user_id,
            query,
            intent,
            selected_file_ids,
            allow_general_answer=payload.allow_general_answer,
        )
        if cached_response:
            latency_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "[RAG] /ask cache hit returned in %.3fs",
                time.perf_counter() - started_at,
            )
            await _record_telemetry(
                db, payload.user_id, latency_ms, cache_hit=True, api_called=False,
                intent=intent, query_id=payload.query_id
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
            latency_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "[RAG] Coalesced request returned cached answer in %.3fs",
                time.perf_counter() - started_at,
            )
            await _record_telemetry(
                db, payload.user_id, latency_ms, cache_hit=True, api_called=False,
                intent=intent, query_id=payload.query_id
            )
            return cached_response

        logger.info("[RAG] /ask cache miss after %.3fs", time.perf_counter() - started_at)
        try:
            response = await _ask_question_uncached(payload, db, intent=intent)
            latency_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "[RAG] Cache miss request completed in %.3fs",
                time.perf_counter() - started_at,
            )
            ans_text = response.get("answer") or ""
            prompt_toks = len(query.split()) * 4 + 350
            comp_toks = len(ans_text.split()) * 4
            await _record_telemetry(
                db, payload.user_id, latency_ms, cache_hit=False, api_called=True,
                intent=intent, prompt_tokens=prompt_toks, completion_tokens=comp_toks,
                query_id=payload.query_id
            )
            return response
        except asyncio.CancelledError as exc:
            await db.rollback()
            logger.info("[RAG] Query %s was cancelled by the user.", payload.query_id)
            raise HTTPException(status_code=499, detail="Query cancelled.") from exc
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
    intent: Optional[QueryIntent] = None,
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
    if intent is None:
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

    if intent == "drive_inventory":
        acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.user_id == user_id))
        google_acc = acc_res.scalars().first()
        if not google_acc:
            answer = "Google Drive isn't connected to check for files. Please connect your Google Drive first."
            await _save_answer(db, user_id, query, answer, intent, "assistant", selected_file_ids=selected_file_ids)
            return _answer_response(query, intent, answer, analysis_required=False, answer_source="assistant")

        available_files = get_cached_file_catalog(google_acc, page_size=100, expand_folders=False)
        if not available_files:
            try:
                available_files = await asyncio.to_thread(
                    list_files_cached, google_acc, page_size=100, expand_folders=False
                )
            except Exception as exc:
                logger.warning("[RAG] Drive file catalog load warning: %s", exc)
                available_files = []

        answer, candidate_names = _handle_drive_inventory_query(query, available_files or [])
        await _save_answer(
            db, user_id, query, answer, intent, "inventory",
            selected_file_ids=selected_file_ids,
            identified_files=candidate_names,
            source_file_names=candidate_names,
        )
        return _answer_response(
            query,
            intent,
            answer,
            analysis_required=False,
            candidate_files=candidate_names,
            answer_source="google_drive",
            auto_discovered=bool(candidate_names),
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

    query_embedding_cache: Dict[str, List[float]] = {}
    try:
        cached_chunks = await search_cached_user_documents(
            db,
            user_id,
            query,
            retrieval_file_ids,
            query_embedding_cache=query_embedding_cache,
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
        is_out_of_scope = (
            "do not contain information regarding" in answer
            or "does not contain information regarding" in answer
            or "doesn't contain information regarding" in answer
        )
        if is_out_of_scope:
            if not retrieval_file_ids:
                fallback_answer = (
                    "The information you're asking about isn't in your Google Drive documents. "
                    "Would you like me to answer using general knowledge instead?"
                )
                await _save_answer(
                    db=db,
                    user_id=user_id,
                    query=query,
                    answer=fallback_answer,
                    intent=str(intent),
                    answer_kind="insufficient",
                    selected_file_ids=selected_file_ids,
                    identified_files=[],
                    source_file_ids=[],
                    source_file_names=[],
                    document_versions={},
                    sources=[],
                )
                return _answer_response(
                    query,
                    intent,
                    fallback_answer,
                    analysis_required=False,
                    needs_general_confirmation=True,
                    answer_source="insufficient_drive_evidence",
                    matched_file_ids=[],
                    candidate_files=[],
                    safe_embedded_files=[],
                    retrieved_sources=[],
                    auto_discovered=True,
                )
            else:
                selected_str = ", ".join(cached_names) if cached_names else "selected document(s)"
                fallback_answer = (
                    f"The selected document(s) ({selected_str}) do not contain information regarding '{query}'. "
                    f"Would you like me to answer using general knowledge instead?"
                )
                await _save_answer(
                    db=db,
                    user_id=user_id,
                    query=query,
                    answer=fallback_answer,
                    intent=str(intent),
                    answer_kind="insufficient",
                    selected_file_ids=selected_file_ids,
                    identified_files=cached_names,
                    source_file_ids=source_file_ids,
                    source_file_names=source_names or cached_names,
                    document_versions=versions,
                    sources=[],
                )
                return _answer_response(
                    query,
                    intent,
                    fallback_answer,
                    analysis_required=False,
                    needs_general_confirmation=True,
                    answer_source="insufficient_drive_evidence",
                    matched_file_ids=matched_file_ids,
                    candidate_files=cached_names,
                    safe_embedded_files=cached_names,
                    retrieved_sources=[],
                    auto_discovered=False,
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
        available_files = await asyncio.to_thread(
            list_files_cached,
            google_acc,
            page_size=100,
            expand_folders=False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to access Google Drive: {str(e)}")
    logger.info(
        "[RAG] Drive catalog loaded in %.3fs (%d files)",
        time.perf_counter() - catalog_started_at,
        len(available_files),
    )

    # Initialize Graph State
    live_tracker = {}
    initial_state = {
        "db": db,
        "user_id": user_id,
        "google_account": google_acc,
        "query": query,
        "query_embedding_cache": query_embedding_cache,
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
        "_live_tracker": live_tracker,
    }

    # Execute LangGraph RAG Workflow (guaranteed <= 28s execution ceiling)
    workflow_started_at = time.perf_counter()
    try:
        final_state = await asyncio.wait_for(
            rag_graph.ainvoke(initial_state),
            timeout=28.0,
        )
    except asyncio.TimeoutError:
        logger.warning("[RAG] Workflow reached 28s limit; producing grounded answer from available progress")
        curr_chunks = live_tracker.get("retrieved_chunks", [])
        safe_files = live_tracker.get("safe_files", [])
        cands = live_tracker.get("candidate_files", [])
        cand_names = [f.get("name") for f in safe_files if f.get("name")] or [f.get("name") for f in cands if f.get("name")]

        if curr_chunks:
            try:
                timeout_ans = await synthesize_answer(
                    query, curr_chunks, [], selected_file_names=cand_names, auto_discovered=len(retrieval_file_ids) == 0
                )
            except Exception:
                timeout_ans = f"Based on your document ({', '.join(cand_names) if cand_names else 'Drive file'}), here is what was found regarding '{query}'."
        elif safe_files and safe_files[0].get("extracted_text"):
            first_text = safe_files[0].get("extracted_text")[:6000]
            quick_chunk = [{"chunk_text": first_text, "file_name": cand_names[0] if cand_names else "Document", "similarity": 1.0}]
            try:
                timeout_ans = await synthesize_answer(
                    query, quick_chunk, [], selected_file_names=cand_names, auto_discovered=len(retrieval_file_ids) == 0
                )
            except Exception:
                timeout_ans = f"Searched {cand_names[0] if cand_names else 'your document'} for '{query}'."
        else:
            try:
                timeout_ans = await answer_general_query(query)
            except Exception:
                timeout_ans = f"I searched your connected Google Drive files for '{query}'. Please see the matched file(s) for details."

        final_state = {
            "answer": timeout_ans,
            "retrieved_chunks": curr_chunks,
            "safe_files": safe_files,
            "candidate_files": cands,
            "confidential_files": live_tracker.get("confidential_files", []),
            "needs_general_confirmation": False,
            "auto_discovered": len(retrieval_file_ids) == 0,
        }
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
        is_auto = not retrieval_file_ids
        display_candidates = [] if is_auto else source_names
        display_sources = [] if is_auto else sources
        await store_cached_answer(
            db,
            user_id,
            query,
            intent,
            final_state.get("answer", ""),
            "insufficient",
            selected_file_ids=selected_file_ids,
            source_file_ids=source_file_ids,
            source_file_names=display_candidates,
            document_versions=versions,
            sources=display_sources,
        )
        return _answer_response(
            query,
            intent,
            final_state.get("answer", ""),
            analysis_required=False,
            needs_general_confirmation=True,
            candidate_files=display_candidates,
            safe_embedded_files=display_candidates,
            retrieved_sources=display_sources,
            answer_source="insufficient_drive_evidence",
            matched_file_ids=matched_file_ids,
            auto_discovered=is_auto,
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
