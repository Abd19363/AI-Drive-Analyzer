import asyncio
import hashlib
import logging
import re
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DriveFile, QueryAnswerCache
from app.services.query_intent_service import (
    implicit_sheet_name_candidate,
    requested_sheet_name,
)

logger = logging.getLogger(__name__)
_query_locks: Dict[str, tuple[asyncio.Lock, int]] = {}
_query_locks_guard = threading.Lock()


class QueryCacheUnavailableError(RuntimeError):
    """Raised when the persistent answer cache cannot be accessed."""


def normalize_query(query: str) -> str:
    """Normalize only case, whitespace, and common sentence punctuation."""
    normalized = " ".join(query.casefold().split())
    return re.sub(r"[?!.;,]+$", "", normalized).strip()


def query_hash(query: str) -> str:
    normalized = normalize_query(query)
    sheet_name = requested_sheet_name(query) or implicit_sheet_name_candidate(query)
    if sheet_name:
        normalized = f"sheet:{normalize_query(sheet_name)}\n{normalized}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def scope_hash(selected_file_ids: Optional[List[str]] = None) -> str:
    ids = sorted(set(selected_file_ids or []))
    value = "\n".join(ids)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def cache_lock_key(
    user_id: str,
    query: str,
    intent: str,
    selected_file_ids: Optional[List[str]] = None,
) -> str:
    context = "|".join((
        str(user_id),
        query_hash(query),
        intent,
        scope_hash(selected_file_ids),
    ))
    return hashlib.sha256(context.encode("utf-8")).hexdigest()


@asynccontextmanager
async def coalesce_query(key: str) -> AsyncGenerator[None, None]:
    """Coalesce identical cache misses within this backend process."""
    with _query_locks_guard:
        lock, users = _query_locks.get(key, (asyncio.Lock(), 0))
        _query_locks[key] = (lock, users + 1)

    acquired = False
    try:
        await lock.acquire()
        acquired = True
        yield
    finally:
        if acquired:
            lock.release()
        with _query_locks_guard:
            current_lock, users = _query_locks[key]
            if users <= 1:
                _query_locks.pop(key, None)
            else:
                _query_locks[key] = (current_lock, users - 1)


def _cache_kinds(intent: str, allow_general_answer: bool) -> List[str]:
    if intent in {"capabilities", "assistant_info", "media"}:
        return ["assistant"]
    if allow_general_answer or intent == "direct_answer":
        return ["general"]
    return ["document", "insufficient"]


async def _document_versions_are_current(
    db: AsyncSession,
    user_id: str,
    entry: QueryAnswerCache,
) -> bool:
    file_ids = entry.source_file_ids or []
    if entry.answer_kind == "document" and not file_ids:
        return False
    if not file_ids:
        return entry.answer_kind == "insufficient"

    try:
        result = await db.execute(
            select(
                DriveFile.file_id,
                DriveFile.source_modified_time,
                DriveFile.guardrail_status,
                DriveFile.is_embedded,
            ).where(
                DriveFile.user_id == user_id,
                DriveFile.file_id.in_(file_ids),
            )
        )
    except Exception as exc:
        logger.exception("Failed to validate document versions for answer cache.")
        raise QueryCacheUnavailableError(
            "The answer cache could not validate its source documents."
        ) from exc
    current_versions = {
        row[0]: (row[1], row[2], row[3])
        for row in result.all()
    }
    if len(current_versions) != len(set(file_ids)):
        return False

    cached_versions = entry.document_versions or {}
    for file_id in file_ids:
        current = current_versions.get(file_id)
        if not current or current[0] != cached_versions.get(file_id):
            return False
        if current[1] != "PASSED":
            return False
        if entry.answer_kind == "document" and not current[2]:
            return False
    return True


async def lookup_cached_answer(
    db: AsyncSession,
    user_id: str,
    query: str,
    intent: str,
    selected_file_ids: Optional[List[str]] = None,
    *,
    allow_general_answer: bool = False,
) -> Optional[QueryAnswerCache]:
    """Return a complete, safe exact-normalized-query cache entry, if valid."""
    now = datetime.now(timezone.utc)
    try:
        result = await db.execute(
            select(QueryAnswerCache)
            .where(
                QueryAnswerCache.user_id == user_id,
                QueryAnswerCache.query_hash == query_hash(query),
                QueryAnswerCache.intent == intent,
                QueryAnswerCache.scope_hash == scope_hash(selected_file_ids),
                QueryAnswerCache.answer_kind.in_(
                    _cache_kinds(intent, allow_general_answer)
                ),
                QueryAnswerCache.is_complete.is_(True),
                QueryAnswerCache.is_safe.is_(True),
                QueryAnswerCache.expires_at > now,
            )
            .order_by(QueryAnswerCache.created_at.desc())
        )
    except Exception as exc:
        logger.exception("Failed to query persistent answer cache.")
        raise QueryCacheUnavailableError(
            "The answer cache could not be queried."
        ) from exc

    allowed_kinds = _cache_kinds(intent, allow_general_answer)
    for entry in result.scalars().all():
        if entry.answer_kind not in allowed_kinds:
            continue
        if entry.expires_at <= now or not entry.is_complete or not entry.is_safe:
            continue
        if entry.answer_kind in {"document", "insufficient"}:
            if not await _document_versions_are_current(db, user_id, entry):
                logger.info(
                    "[RAG] Ignoring stale %s answer cache for user %s",
                    entry.answer_kind,
                    user_id,
                )
                try:
                    await db.execute(
                        delete(QueryAnswerCache).where(
                            QueryAnswerCache.id == entry.id
                        )
                    )
                    await db.commit()
                except Exception as exc:
                    logger.exception("Failed to invalidate a stale answer cache entry.")
                    raise QueryCacheUnavailableError(
                        "The answer cache could not invalidate a stale entry."
                    ) from exc
                continue
        return entry
    return None


def cached_answer_response(
    query: str,
    intent: str,
    entry: QueryAnswerCache,
) -> Dict[str, Any]:
    answer_source = {
        "general": "general_knowledge",
        "document": "google_drive",
        "insufficient": "insufficient_drive_evidence",
        "assistant": "assistant",
    }.get(entry.answer_kind, "unknown")
    return {
        "query": query,
        "intent": intent,
        "answer": entry.answer_text,
        "answer_source": answer_source,
        "cached": True,
        "analysis_required": False,
        "needs_general_confirmation": entry.answer_kind == "insufficient",
        "auto_discovered": entry.scope_hash == scope_hash(),
        "candidate_files": entry.source_file_names or [],
        "safe_embedded_files": entry.source_file_names or [],
        "matched_file_ids": entry.source_file_ids or [],
        "blocked_confidential_files": [],
        "retrieved_sources": entry.sources or [],
    }


async def store_cached_answer(
    db: AsyncSession,
    user_id: str,
    query: str,
    intent: str,
    answer: str,
    answer_kind: str,
    *,
    selected_file_ids: Optional[List[str]] = None,
    source_file_ids: Optional[List[str]] = None,
    source_file_names: Optional[List[str]] = None,
    document_versions: Optional[Dict[str, Optional[str]]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    is_complete: bool = True,
    is_safe: bool = True,
) -> bool:
    """Persist only complete answer results, without caching document text."""
    if answer_kind not in {
        "assistant", "general", "document", "insufficient", "decision"
    }:
        raise ValueError(f"Unsupported answer cache kind: {answer_kind}")
    if not is_complete or not is_safe or not answer.strip():
        return False

    if answer_kind == "document" and not source_file_ids:
        logger.info("Skipping grounded-answer cache without document provenance.")
        return False

    ttl_seconds = {
        "general": settings.GENERAL_ANSWER_CACHE_TTL_SECONDS,
        "assistant": settings.QUERY_ANSWER_CACHE_TTL_SECONDS,
        "document": settings.QUERY_ANSWER_CACHE_TTL_SECONDS,
        "insufficient": settings.INSUFFICIENT_ANSWER_CACHE_TTL_SECONDS,
        "decision": settings.QUERY_DECISION_CACHE_TTL_SECONDS,
    }[answer_kind]
    if ttl_seconds <= 0:
        return False

    now = datetime.now(timezone.utc)
    values = {
        "user_id": user_id,
        "query_hash": query_hash(query),
        "intent": intent,
        "scope_hash": scope_hash(selected_file_ids),
        "answer_kind": answer_kind,
        "answer_text": answer,
        "source_file_ids": list(dict.fromkeys(source_file_ids or [])),
        "source_file_names": list(dict.fromkeys(source_file_names or [])),
        "document_versions": document_versions or {},
        "sources": sources or [],
        "is_complete": is_complete,
        "is_safe": is_safe,
        "created_at": now,
        "expires_at": now + timedelta(seconds=ttl_seconds),
    }
    statement = insert(QueryAnswerCache).values(**values)
    statement = statement.on_conflict_do_update(
        constraint="uq_query_answer_cache_context",
        set_={
            key: value
            for key, value in values.items()
            if key not in {"user_id", "query_hash", "intent", "scope_hash", "answer_kind"}
        },
    )
    try:
        await db.execute(statement)
        await db.execute(
            delete(QueryAnswerCache).where(QueryAnswerCache.expires_at <= now)
        )
        await db.commit()
    except Exception as exc:
        logger.exception("Failed to persist query answer cache entry.")
        raise QueryCacheUnavailableError(
            "The answer cache could not be updated."
        ) from exc
    return True


async def store_user_decision(
    db: AsyncSession,
    user_id: str,
    query: str,
    intent: str,
    decision: str,
    selected_file_ids: Optional[List[str]] = None,
) -> None:
    if decision not in {"accepted", "declined"}:
        raise ValueError("Decision must be 'accepted' or 'declined'.")
    await store_cached_answer(
        db,
        user_id,
        query,
        intent,
        decision,
        "decision",
        selected_file_ids=selected_file_ids,
    )
