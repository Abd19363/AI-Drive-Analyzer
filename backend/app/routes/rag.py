import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List, Literal
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db import get_db
from app.models import GoogleAccount, ChatQuery, QueryTelemetry, User, ChatSession
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
    clean_response_text,
    is_constituency_data_query,
    filter_files_by_query_scope,
    _DOCUMENT_REQUEST_PATTERN,
    _DOCUMENT_SEARCH_PATTERN,
    _PERSONAL_CONTEXT_PATTERN,
    _BUSINESS_DATA_PATTERN,
    _EXPLICIT_GENERAL_PATTERN,
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
    session_id: Optional[str] = None
    allow_general_answer: bool = False
    matched_file_ids: Optional[List[str]] = None
    force_drive_search: bool = False
    intent: Optional[QueryIntent] = None


class CreateSessionRequest(BaseModel):
    user_id: str
    title: Optional[str] = "New Chat"
    messages: Optional[List[Dict[str, Any]]] = None


class UpdateSessionRequest(BaseModel):
    user_id: str
    title: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None


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


class DisplayedResponseTimingRequest(BaseModel):
    query_id: str
    elapsed_ms: float = Field(ge=0, le=86_400_000)
    status: Literal["success", "error", "cancelled"]


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

    if not selected_file_ids and not matched_file_ids:
        matched_file_ids = await _find_drive_name_matches(db, query, user_id)
        if matched_file_ids:
            logger.info(
                "[RAG] Drive catalog name match found %d file/folder candidate(s) "
                "before intent routing",
                len(matched_file_ids),
            )
            if intent in {
                "capabilities",
                "assistant_info",
                "direct_answer",
                "media",
            }:
                intent = classify_query_intent(query, has_selected_files=True)
                if intent in {
                    "capabilities",
                    "assistant_info",
                    "direct_answer",
                    "media",
                }:
                    intent = "fact"
            return intent, matched_file_ids

    if force_drive_search and intent in {
        "capabilities",
        "assistant_info",
        "direct_answer",
        "media",
    }:
        intent = "fact"

    if (
        not force_drive_search
        and not selected_file_ids
        and not matched_file_ids
        and is_constituency_data_query(query)
    ):
        return intent, []

    if not force_drive_search and not selected_file_ids and not matched_file_ids:
        if is_fast_general_knowledge_query(query):
            return "direct_answer", []

        if intent in {"capabilities", "assistant_info", "direct_answer", "media", "drive_inventory"}:
            return intent, []

    if not force_drive_search and not selected_file_ids and not matched_file_ids:
        has_doc_indicators = (
            bool(_DOCUMENT_REQUEST_PATTERN.search(query))
            or bool(_DOCUMENT_SEARCH_PATTERN.search(query))
            or bool(_PERSONAL_CONTEXT_PATTERN.search(query))
            or bool(_BUSINESS_DATA_PATTERN.search(query))
        )
        if not has_doc_indicators and await classify_general_vs_drive_query(query):
            return "direct_answer", []

    resolved_intent = classify_query_intent(
        query,
        has_selected_files=bool(
            selected_file_ids or matched_file_ids or force_drive_search
        ),
    )
    if force_drive_search and resolved_intent in {
        "capabilities",
        "assistant_info",
        "direct_answer",
        "media",
    }:
        resolved_intent = "fact"
    return resolved_intent, matched_file_ids


async def _find_drive_name_matches(
    db: AsyncSession,
    query: str,
    user_id: str,
) -> List[str]:
    account_result = await db.execute(
        select(GoogleAccount).where(GoogleAccount.user_id == user_id)
    )
    google_account = account_result.scalars().first()
    if not google_account:
        return []

    available_files = get_cached_file_catalog(
        google_account,
        page_size=100,
        expand_folders=True,
    )
    if available_files is None:
        try:
            available_files = await asyncio.to_thread(
                list_files_cached,
                google_account,
                page_size=100,
                expand_folders=True,
            )
        except Exception as exc:
            logger.exception(
                "[RAG] Could not check Drive names before intent routing."
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not check Google Drive file and folder names before "
                    "answering. Please retry after reconnecting Drive."
                ),
            ) from exc

    matches = match_files_by_title(query, available_files or [], minimum_score=15)
    matches = filter_files_by_query_scope(query, matches)
    if not matches:
        return []

    from app.services.guardrail_service import is_media_file

    catalog_by_parent: Dict[str, List[Dict[str, Any]]] = {}
    for f in (available_files or []):
        pid = f.get("parent_id")
        if pid:
            catalog_by_parent.setdefault(pid, []).append(f)

    prioritized_ids: List[str] = []
    seen_ids = set()

    for item in matches:
        is_folder = (
            item.get("mimeType") == "application/vnd.google-apps.folder"
            or item.get("is_folder", False)
        )
        if is_folder:
            f_id = item.get("id")
            if not f_id:
                continue
            pending = [f_id]
            visited = set()
            while pending:
                curr = pending.pop()
                if curr in visited:
                    continue
                visited.add(curr)
                for child in catalog_by_parent.get(curr, []):
                    child_is_fld = (
                        child.get("mimeType") == "application/vnd.google-apps.folder"
                        or child.get("is_folder", False)
                    )
                    child_id = child.get("id")
                    if child_is_fld:
                        if child_id:
                            pending.append(child_id)
                    elif not is_media_file(child):
                        if child_id and child_id not in seen_ids:
                            seen_ids.add(child_id)
                            prioritized_ids.append(str(child_id))
        else:
            fid = item.get("id")
            if fid and fid not in seen_ids and not is_media_file(item):
                seen_ids.add(fid)
                prioritized_ids.append(str(fid))

    return prioritized_ids


def _handle_drive_inventory_query(
    query: str,
    available_files: List[Dict[str, Any]],
) -> tuple[str, List[str]]:
    """Answers file existence and drive inventory queries directly from Drive catalog without special characters."""
    target, is_vague = extract_drive_inventory_target(query)

    if is_vague:
        answer = (
            "Please specify the file name, document title, or topic you would like me to check in your Google Drive "
            "(for example: Is my resume in my drive? or Check whether Form-33 is in my drive)."
        )
        return clean_response_text(answer), []

    if target == "LIST_ALL":
        textual_files = [
            f for f in available_files
            if f.get("mimeType") != "application/vnd.google-apps.folder"
        ]
        if not textual_files:
            return "There are currently no document files found in your connected Google Drive.", []

        file_lines = []
        for idx, f in enumerate(textual_files[:15], 1):
            name = f.get("name", "Untitled")
            file_lines.append(f"{idx}. {name}")

        remaining = len(textual_files) - 15
        more_note = f"\n\nAnd {remaining} more file(s)." if remaining > 0 else ""
        answer = (
            f"Here are the document(s) currently available in your Google Drive ({len(textual_files)} total):\n\n"
            + "\n".join(file_lines)
            + more_note
            + "\n\nYou can ask questions about the contents of any of these files or select them on the left."
        )
        return clean_response_text(answer), [f.get("name") for f in textual_files[:5]]

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
        for idx, f in enumerate(matched, 1):
            name = f.get("name", "Untitled")
            mod = f.get("modifiedTime", "")
            date_str = f" - Last modified: {mod[:10]}" if mod else ""
            file_bullets.append(f"{idx}. {name}{date_str}")

        count_phrase = "this document" if len(matched) == 1 else "these documents"
        answer = (
            "Yes, I found matching file(s) in your Google Drive:\n\n"
            + "\n".join(file_bullets)
            + f"\n\nWould you like me to answer questions or analyze information from {count_phrase}?"
        )
        return clean_response_text(answer), cand_names
    else:
        sample_files = [f.get("name") for f in available_files[:5] if f.get("name")]
        sample_text = (
            "\n\nSome of the files in your Drive include:\n"
            + "\n".join(f"{idx}. {name}" for idx, name in enumerate(sample_files, 1))
            if sample_files else ""
        )
        answer = (
            f"I checked your Google Drive files, but found no document matching '{target}'."
            + sample_text
            + "\n\nPlease check the spelling or select a file from your Drive list on the left."
        )
        return clean_response_text(answer), []


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
        "answer": clean_response_text(answer),
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
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
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
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens or (prompt_tokens + completion_tokens),
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
            file_info.get("extraction_version", 0),
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
            document_versions[file_id] = (
                f"{version}|extract:{file_info.get('extraction_version', 0)}"
            )
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
            document_versions[file_id] = (
                f"{source_version}|extract:{chunk.get('extraction_version', 0)}"
            )
            if file_name:
                source_names.append(file_name)
        elif file_name in versions_by_name:
            (
                matched_id,
                matched_version,
                matched_extraction_version,
            ) = versions_by_name[file_name]
            if matched_version:
                source_ids.append(matched_id)
                document_versions[matched_id] = (
                    f"{matched_version}|extract:{matched_extraction_version}"
                )
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
    started_at = time.perf_counter()
    try:
        return await _ask_question_impl(payload, db)
    finally:
        logger.info(
            "[RAG] Query response completed in %.3fs (query_id=%s)",
            time.perf_counter() - started_at,
            payload.query_id or "n/a",
        )


@router.post("/ask/displayed")
async def log_ask_response_displayed(payload: DisplayedResponseTimingRequest):
    logger.info(
        "[RAG] End-to-end query time (submit-to-UI response): %.3fs "
        "(status=%s, query_id=%s)",
        payload.elapsed_ms / 1000,
        payload.status,
        payload.query_id,
    )
    return {"logged": True}


async def _ask_question_impl(
    payload: QuestionRequest,
    db: AsyncSession = Depends(get_db),
):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # Check token expiration & quota balance for user
    if payload.user_id:
        try:
            user_uid = uuid.UUID(payload.user_id)
            user_record = await db.get(User, user_uid)
            if user_record:
                now_utc = datetime.now(timezone.utc)
                if user_record.token_expires_at and now_utc > user_record.token_expires_at:
                    raise HTTPException(
                        status_code=403,
                        detail="Your token subscription has expired. Please contact the administrator to renew or update your token subscription.",
                    )
                # Check remaining tokens against total consumption
                tokens_stmt = select(
                    func.coalesce(func.sum(QueryTelemetry.total_tokens), 0)
                ).where(
                    QueryTelemetry.user_id == user_record.id,
                )
                t_res = await db.execute(tokens_stmt)
                tokens_used_total = int(t_res.scalar() or 0)
                if user_record.assigned_tokens > 0 and tokens_used_total >= user_record.assigned_tokens:
                    raise HTTPException(
                        status_code=403,
                        detail="Your token quota has been exhausted. Please contact the administrator to allocate more tokens.",
                    )
        except ValueError:
            pass

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
            latency_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "[RAG] /ask early cache hit returned in %.3fs",
                time.perf_counter() - started_at,
            )
            await _record_telemetry(
                db, payload.user_id, latency_ms, cache_hit=True, api_called=False,
                intent=initial_intent, prompt_tokens=0, completion_tokens=0,
                query_id=payload.query_id
            )
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
                    latency_ms = (time.perf_counter() - started_at) * 1000
                    logger.info(
                        "[RAG] /ask route cache hit returned in %.3fs",
                        time.perf_counter() - started_at,
                    )
                    await _record_telemetry(
                        db, payload.user_id, latency_ms, cache_hit=True, api_called=False,
                        intent=intent, prompt_tokens=0, completion_tokens=0,
                        query_id=payload.query_id
                    )
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
        if (
            not payload.allow_general_answer
            and not selected_file_ids
            and not matched_file_ids
        ):
            matched_file_ids = await _find_drive_name_matches(
                db,
                query,
                payload.user_id,
            )
            if matched_file_ids:
                payload.matched_file_ids = matched_file_ids
                if intent in {
                    "capabilities",
                    "assistant_info",
                    "direct_answer",
                    "media",
                }:
                    intent = "fact"
        if payload.force_drive_search and intent in {
            "capabilities",
            "assistant_info",
            "direct_answer",
            "media",
        }:
            intent = "fact"

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

        available_files = get_cached_file_catalog(google_acc, page_size=100, expand_folders=True)
        if not available_files:
            try:
                available_files = await asyncio.to_thread(
                    list_files_cached, google_acc, page_size=100, expand_folders=True
                )
            except Exception as exc:
                logger.exception("[RAG] Failed to load the Drive inventory catalog.")
                raise HTTPException(
                    status_code=503,
                    detail="Could not load Google Drive files. Please retry.",
                ) from exc

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
        import re
        is_greeting = bool(
            re.match(
                r"^\s*(?:hi|hello|hey|howdy|greetings|good\s+(?:morning|afternoon|evening|day)|how\s+are\s+you|who\s+are\s+you|tell\s+me\s+a\s+joke)\b[?.!]*\s*$",
                query,
                re.I,
            )
        )
        is_explicit_general = bool(_EXPLICIT_GENERAL_PATTERN.search(query))
        if is_greeting or is_explicit_general or payload.allow_general_answer:
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
    cached_chunks = []
    try:
        cached_chunks = await search_cached_user_documents(
            db,
            user_id,
            query,
            selected_file_ids=retrieval_file_ids if retrieval_file_ids else None,
            query_embedding_cache=query_embedding_cache,
        )
    except Exception as exc:
        logger.exception("Failed to search the indexed document cache.")
        cached_chunks = []

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
        ans_lower = answer.lower()
        is_out_of_scope = (
            "do not contain information regarding" in ans_lower
            or "does not contain information regarding" in ans_lower
            or "doesn't contain information regarding" in ans_lower
            or "not shown in the supplied text" in ans_lower
            or "not found in the supplied text" in ans_lower
            or "could not be read from the selected document" in ans_lower
        )
        if not is_out_of_scope:
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
        elif selected_file_ids:
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
                sources=sources,
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
        elif not retrieval_file_ids:
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
            expand_folders=True,
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
        if matched_file_ids and not selected_file_ids:
            logger.info(
                "[RAG] Name-matched file(s) did not answer the query; "
                "trying semantic search across indexed Drive documents."
            )
            try:
                fallback_chunks = await search_cached_user_documents(
                    db,
                    user_id,
                    query,
                    query_embedding_cache=query_embedding_cache,
                )
            except Exception as exc:
                logger.exception(
                    "[RAG] Semantic fallback search failed after a Drive-name match."
                )
                raise HTTPException(
                    status_code=500,
                    detail="Failed to search the indexed documents for a semantic fallback.",
                ) from exc

            if fallback_chunks:
                fallback_names = list(dict.fromkeys(
                    chunk["file_name"]
                    for chunk in fallback_chunks
                    if chunk.get("file_name")
                ))
                try:
                    fallback_answer = await synthesize_answer(
                        query,
                        fallback_chunks,
                        [],
                        selected_file_names=fallback_names,
                        auto_discovered=True,
                        available_file_names=fallback_names,
                        intent=intent,
                    )
                except GeminiServiceUnavailableError as exc:
                    raise HTTPException(
                        status_code=503,
                        detail=str(exc),
                    ) from exc
                fb_lower = fallback_answer.lower()
                fallback_out_of_scope = (
                    "do not contain information regarding" in fb_lower
                    or "does not contain information regarding" in fb_lower
                    or "doesn't contain information regarding" in fb_lower
                    or "not shown in the supplied text" in fb_lower
                    or "not found in the supplied text" in fb_lower
                    or "could not be read from the selected document" in fb_lower
                )
                if not fallback_out_of_scope:
                    (
                        fallback_source_ids,
                        fallback_source_names,
                        fallback_versions,
                        fallback_sources,
                    ) = _cache_document_evidence([], fallback_chunks)
                    await _save_answer(
                        db=db,
                        user_id=user_id,
                        query=query,
                        answer=fallback_answer,
                        intent=str(intent),
                        answer_kind="document",
                        selected_file_ids=selected_file_ids,
                        identified_files=fallback_names,
                        source_file_ids=fallback_source_ids,
                        source_file_names=fallback_source_names or fallback_names,
                        document_versions=fallback_versions,
                        sources=fallback_sources,
                    )
                    return _answer_response(
                        query,
                        intent,
                        fallback_answer,
                        analysis_required=True,
                        candidate_files=fallback_names,
                        safe_embedded_files=fallback_names,
                        retrieved_sources=fallback_sources,
                        auto_discovered=True,
                        answer_source="google_drive",
                        matched_file_ids=matched_file_ids,
                    )

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
    candidate_names = (
        [file_info.get("name") for file_info in safe_files]
        if sheet_scope
        else [f.get("name") for f in final_state.get("candidate_files", [])]
    )
    all_source_names = list(dict.fromkeys(source_names + [n for n in candidate_names if n]))
    await _save_answer(
        db=db,
        user_id=user_id,
        query=query,
        answer=answer,
        intent=str(intent),
        answer_kind="document",
        selected_file_ids=selected_file_ids,
        identified_files=all_source_names,
        source_file_ids=source_file_ids,
        source_file_names=all_source_names,
        document_versions=versions,
        sources=sources,
    )

    return {
        "query": query,
        "intent": intent,
        "answer": clean_response_text(answer),
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



@router.get("/sessions")
async def list_chat_sessions(user_id: str, db: AsyncSession = Depends(get_db)):
    """List all active (non-deleted) chat sessions for a user."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.is_deleted.is_(False))
        .order_by(ChatSession.updated_at.desc())
    )
    res = await db.execute(stmt)
    sessions = res.scalars().all()
    return {
        "sessions": [
            {
                "id": str(s.id),
                "title": s.title,
                "message_count": len(s.messages or []),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]
    }


@router.post("/sessions")
async def create_chat_session(payload: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    """Create a new chat session for a user."""
    default_welcome = [
        {
            "id": "welcome-1",
            "sender": "ai",
            "text": "Hello! I'm your AI Drive Assistant. You can select specific documents from your Google Drive catalog on the left, or simply ask a question and I'll automatically find the relevant files for you. Your documents are protected by built-in privacy and security checks.",
            "time": "Just now",
            "showSecurityNotice": True,
            "citations": [],
            "blockedFiles": [],
        }
    ]
    msgs = payload.messages if payload.messages is not None else default_welcome
    session = ChatSession(
        user_id=payload.user_id,
        title=payload.title or "New Chat",
        messages=msgs,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {
        "id": str(session.id),
        "title": session.title,
        "messages": session.messages or [],
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


@router.get("/sessions/{session_id}")
async def get_chat_session(
    session_id: str,
    user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get a chat session and its full message history."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.is_deleted.is_(False),
    )
    if user_id:
        stmt = stmt.where(ChatSession.user_id == user_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return {
        "id": str(session.id),
        "title": session.title,
        "messages": session.messages or [],
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


@router.put("/sessions/{session_id}")
async def update_chat_session(session_id: str, payload: UpdateSessionRequest, db: AsyncSession = Depends(get_db)):
    """Update title and/or messages of a chat session."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == payload.user_id,
        ChatSession.is_deleted.is_(False),
    )
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")

    if payload.title is not None:
        session.title = payload.title.strip()[:255] or session.title
    if payload.messages is not None:
        session.messages = payload.messages
    session.updated_at = datetime.utcnow()
    await db.commit()
    return {
        "id": str(session.id),
        "title": session.title,
        "message_count": len(session.messages or []),
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Mark a chat session as deleted."""
    stmt = select(ChatSession).where(ChatSession.id == session_id)
    if user_id:
        stmt = stmt.where(ChatSession.user_id == user_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")

    session.is_deleted = True
    session.updated_at = datetime.utcnow()
    await db.commit()
    return {"deleted": True, "id": str(session.id)}


@router.post("/sessions/{session_id}/clear")
async def clear_chat_session(
    session_id: str,
    user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Clear all messages in the chat session, resetting to the initial state."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.is_deleted.is_(False),
    )
    if user_id:
        stmt = stmt.where(ChatSession.user_id == user_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")

    default_welcome = [
        {
            "id": "welcome-1",
            "sender": "ai",
            "text": "Hello! I'm your AI Drive Assistant. You can select specific documents from your Google Drive catalog on the left, or simply ask a question and I'll automatically find the relevant files for you. Your documents are protected by built-in privacy and security checks.",
            "time": "Just now",
            "showSecurityNotice": True,
            "citations": [],
            "blockedFiles": [],
        }
    ]
    session.messages = default_welcome
    session.updated_at = datetime.utcnow()
    await db.commit()
    return {"cleared": True, "id": str(session.id), "messages": session.messages}
