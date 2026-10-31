import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, text
from app.models import DriveFile, GuardrailLog, DocumentChunk, ChatQuery
from app.services.drive_service import download_file, get_folder_children
from app.services.guardrail_service import (
    run_guardrails,
    screen_metadata,
    is_media_file,
    is_query_about_media,
    MEDIA_QUERY_RESPONSE,
)
from app.services.extractor_service import chunk_text, extract_excel_sheet_text
from app.services.embedding_service import get_or_create_embeddings, embed_single_query
from app.services.gemini_service import analyze_query_for_drive_files, synthesize_answer
from app.services.query_adaptive_service import (
    adaptive_embed_for_query,
    adaptive_embed_pdf_for_query,  # kept for backward compat
    chunk_relevance_filter,
    expand_query_for_retrieval,
    needs_adaptive_embedding,
)
from app.services.query_intent_service import (
    QueryIntent,
    implicit_sheet_name_candidate,
    is_document_structure_query,
    match_files_by_title,
    requested_sheet_name,
)

logger = logging.getLogger(__name__)

class RAGState(TypedDict):
    db: AsyncSession
    user_id: str
    google_account: Any
    query: str
    query_embedding_cache: Dict[str, List[float]]
    intent: QueryIntent
    selected_file_ids: Optional[List[str]]
    available_files: List[Dict[str, Any]]
    candidate_files: List[Dict[str, Any]]
    safe_files: List[Dict[str, Any]]
    confidential_files: List[Dict[str, Any]]
    retrieved_chunks: List[Dict[str, Any]]
    answer: str
    auto_discovered: bool
    is_media_query: bool
    needs_general_confirmation: bool
    requested_sheet_name: Optional[str]
    sheet_scoped_safe_files: List[Dict[str, Any]]
    _live_tracker: Optional[Dict[str, Any]]

async def node_analyze_query(state: RAGState) -> Dict[str, Any]:
    """
    Step 1: Identifies candidate files.
    If the user selected specific files in the UI, uses those files directly.
    Otherwise uses AI auto-discovery to find relevant files across Drive.
    Also detects if the query is asking about images or video files.
    """
    query = state["query"]
    available_files = state["available_files"]
    selected_file_ids = state.get("selected_file_ids") or []

    auto_discovered = False
    query_is_media = is_query_about_media(query)

    if selected_file_ids:
        # User explicitly selected files — prioritize them directly
        selected_set = set(selected_file_ids)
        candidate_files = [f for f in available_files if f.get("id") in selected_set]
        logger.info(f"[RAG] Using user-selected {len(candidate_files)} file(s): {[f.get('name') for f in candidate_files]}")

        all_selected_are_media = (
            len(candidate_files) > 0 and all(is_media_file(f) for f in candidate_files)
        )
        if query_is_media or all_selected_are_media:
            return {
                "candidate_files": candidate_files,
                "auto_discovered": False,
                "is_media_query": True
            }

        # User selected mixed files; filter out media so only textual files are processed
        candidate_files = [f for f in candidate_files if not is_media_file(f)]
    else:
        # Auto-discovery: identify ONLY the relevant candidate file(s) for the query
        auto_discovered = True
        if query_is_media:
            return {
                "candidate_files": [],
                "auto_discovered": True,
                "is_media_query": True
            }

        # Fast title match check first (0ms LLM latency)
        title_matches = match_files_by_title(query, available_files, minimum_score=20)
        if title_matches:
            candidate_files = [f for f in title_matches if not is_media_file(f)]
            logger.info(f"[RAG] Fast title match found {len(candidate_files)} candidate(s) without LLM: {[f.get('name') for f in candidate_files]}")
        else:
            candidate_files = await analyze_query_for_drive_files(query, available_files)
            candidate_files = [f for f in candidate_files if not is_media_file(f)]
            logger.info(f"[RAG] Auto-discovery identified {len(candidate_files)} candidate file(s): {[f.get('name') for f in candidate_files]}")

    # Expand any candidate folders into their actual document files
    expanded = []
    for cfile in candidate_files:
        if cfile.get("mimeType") == "application/vnd.google-apps.folder":
            folder_id = cfile.get("id")
            children = []
            if folder_id:
                children = await asyncio.to_thread(
                    get_folder_children,
                    state["google_account"],
                    folder_id,
                )
                for child in children:
                    child["folder_name"] = cfile.get("name")
                children = [
                    child for child in children
                    if child.get("mimeType") != "application/vnd.google-apps.folder"
                    and not is_media_file(child)
                ]
            if children:
                # Rank children inside the folder by relevance to query
                ranked_children = match_files_by_title(query, children)
                if ranked_children:
                    expanded.extend(ranked_children[:2])
                else:
                    expanded.extend(children[:2])
            else:
                expanded.append(cfile)
        else:
            if not is_media_file(cfile):
                expanded.append(cfile)

    seen = set()
    unique_candidates = [f for f in expanded if f.get("id") not in seen and not seen.add(f.get("id"))]
    # Cap candidate files to at most 1 for auto-discovery to keep processing fast and only embed the queried file
    max_cands = 3 if selected_file_ids else 1
    return {"candidate_files": unique_candidates[:max_cands], "auto_discovered": auto_discovered, "is_media_query": False}

async def node_guardrail_gate(state: RAGState) -> Dict[str, Any]:
    """
    Step 2: Downloads only candidate files and executes the 4-layer privacy guardrail.
    Files containing CNIC, salary slips, passports, or financial statements are blocked.
    """
    if state.get("is_media_query"):
        return {"safe_files": [], "confidential_files": []}

    db = state["db"]
    google_account = state["google_account"]
    user_id = state["user_id"]
    candidate_files = state["candidate_files"]

    safe_files = []
    confidential_files = []
    files_to_inspect = []
    chunk_delete_ids = set()

    candidate_ids = {
        cfile.get("id")
        for cfile in candidate_files
        if cfile.get("id")
    }
    existing_files = {}
    if candidate_ids:
        result = await db.execute(
            select(DriveFile).where(
                DriveFile.user_id == user_id,
                DriveFile.file_id.in_(candidate_ids),
            )
        )
        existing_files = {
            db_file.file_id: db_file
            for db_file in result.scalars().all()
        }

    for cfile in candidate_files:
        file_id = cfile.get("id")
        file_name = cfile.get("name")
        mime_type = cfile.get("mimeType", "")
        web_link = cfile.get("webViewLink", "")
        size = int(cfile.get("size", 0)) if cfile.get("size") else 0
        source_modified_time = cfile.get("modifiedTime")

        # ── Upfront metadata screening ──────────────────────────────────
        # Run screen_metadata BEFORE checking is_unchanged, so newly added
        # sensitive patterns (e.g. easypaisa, psid) catch files that were
        # previously marked PASSED under older guardrail rules.
        meta_flagged, meta_reason, meta_type = screen_metadata(file_name)
        if meta_flagged:
            db_file_meta = existing_files.get(file_id)
            if db_file_meta:
                db_file_meta.guardrail_status = "FLAGGED_CONFIDENTIAL"
                db_file_meta.confidentiality_reason = meta_reason
                # Delete any previously embedded chunks
                if db_file_meta.is_embedded:
                    chunk_delete_ids.add(db_file_meta.id)
                    db_file_meta.is_embedded = False
            confidential_files.append({
                "id": file_id,
                "name": file_name,
                "reason": meta_reason,
                "detection_type": meta_type
            })
            continue

        db_file = existing_files.get(file_id)
        if not db_file:
            db_file = DriveFile(
                user_id=user_id,
                file_id=file_id,
                name=file_name,
                mime_type=mime_type,
                size_bytes=size,
                web_view_link=web_link,
                guardrail_status="UNCHECKED",
                source_modified_time=None,
            )
            db.add(db_file)
            existing_files[file_id] = db_file
        else:
            db_file.name = file_name
            db_file.mime_type = mime_type
            db_file.size_bytes = size
            db_file.web_view_link = web_link

        is_unchanged = (
            source_modified_time is not None
            and db_file.source_modified_time == source_modified_time
        )

        # Reuse the previous scan and index only while Drive says the source is unchanged.
        if is_unchanged and db_file.guardrail_status == "FLAGGED_CONFIDENTIAL":
            confidential_files.append({
                "id": file_id,
                "name": file_name,
                "reason": db_file.confidentiality_reason or "Previously flagged as confidential"
            })
            continue

        if (
            is_unchanged
            and db_file.guardrail_status == "PASSED"
            and db_file.is_embedded
        ):
            safe_files.append({
                "db_id": db_file.id,
                "file_id": file_id,
                "name": file_name,
                "extracted_text": "",
                "is_embedded": True,
                "source_modified_time": db_file.source_modified_time,
            })
            continue

        if not is_unchanged or not db_file.is_embedded:
            if db_file.id:
                chunk_delete_ids.add(db_file.id)
            db_file.is_embedded = False
            db_file.guardrail_status = "UNCHECKED"
            db_file.confidentiality_reason = None

        files_to_inspect.append({
            "db_file": db_file,
            "file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "source_modified_time": source_modified_time,
        })

    await db.flush()
    if chunk_delete_ids:
        await db.execute(
            delete(DocumentChunk)
            .where(DocumentChunk.file_id.in_(chunk_delete_ids))
        )

    # Downloads and pure document inspection are independent across files.
    # Bound concurrency to limit Drive and Vision API pressure.
    semaphore = asyncio.Semaphore(3)

    async def inspect_file(file_info):
        async with semaphore:
            try:
                file_bytes = await asyncio.to_thread(
                    download_file,
                    google_account,
                    file_info["file_id"],
                    file_info["mime_type"],
                )
            except Exception as exc:
                return file_info, None, exc, None

            guard_result = await asyncio.to_thread(
                run_guardrails,
                file_info["file_name"],
                file_info["mime_type"],
                file_bytes,
            )
            return file_info, guard_result, None, file_bytes

    inspection_results = await asyncio.gather(
        *(inspect_file(file_info) for file_info in files_to_inspect)
    )

    for file_info, guard_result, download_error, file_bytes in inspection_results:
        file_id = file_info["file_id"]
        file_name = file_info["file_name"]
        db_file = file_info["db_file"]

        if download_error is not None:
            confidential_files.append({
                "id": file_id,
                "name": file_name,
                "reason": f"Unable to download for inspection: {download_error}"
            })
            continue

        db_file.source_modified_time = file_info["source_modified_time"]
        db_file.last_scanned_at = datetime.now(timezone.utc)

        if guard_result["is_confidential"]:
            db_file.guardrail_status = "FLAGGED_CONFIDENTIAL"
            db_file.confidentiality_reason = guard_result["reason"]
            db.add(GuardrailLog(
                file_id=db_file.id,
                check_stage=guard_result["stage"],
                detection_type=guard_result.get("detection_type"),
                snippet_matched=guard_result.get("snippet"),
                confidence_score=guard_result.get("confidence", 1.0)
            ))
            confidential_files.append({
                "id": file_id,
                "name": file_name,
                "reason": guard_result["reason"],
                "detection_type": guard_result.get("detection_type")
            })
        else:
            db_file.guardrail_status = "PASSED"
            db_file.confidentiality_reason = None
            safe_files.append({
                "db_id": db_file.id,
                "file_id": file_id,
                "name": file_name,
                "mime_type": file_info.get("mime_type", ""),
                "file_bytes": file_bytes,
                "extracted_text": guard_result.get("extracted_text", ""),
                "is_embedded": db_file.is_embedded,
                "source_modified_time": db_file.source_modified_time,
            })

    await db.commit()

    return {
        "safe_files": safe_files,
        "confidential_files": confidential_files
    }


async def node_index_safe_files(state: RAGState) -> Dict[str, Any]:
    """
    Step 3: Create embeddings in batches for verified safe files and store
    their chunks in PostgreSQL pgvector.
    """
    if state.get("is_media_query"):
        return {}

    db = state["db"]
    user_id = state["user_id"]
    safe_files = state["safe_files"]
    chunks_to_store = []
    indexed_file_ids = set()

    for sfile in safe_files:
        if sfile.get("is_embedded"):
            continue

        text_content = sfile.get("extracted_text", "")
        if not text_content.strip():
            # If safe document has sparse/scanned text (e.g. Form-33), run bounded OCR on demand for this single safe file
            try:
                from app.services.extractor_service import extract_content
                file_bytes = sfile.get("file_bytes")
                if not file_bytes:
                    google_account = state.get("google_account")
                    if google_account:
                        file_bytes = await asyncio.to_thread(
                            download_file,
                            google_account,
                            sfile["file_id"],
                            sfile.get("mime_type", ""),
                        )
                if file_bytes:
                    text_content = await asyncio.to_thread(
                        extract_content,
                        file_bytes,
                        sfile.get("mime_type", ""),
                        sfile["name"],
                        run_ocr_if_sparse=True,
                    )
                    sfile["extracted_text"] = text_content
            except Exception as e:
                logger.warning(f"On-demand OCR failed for {sfile.get('name')}: {e}")

        if not text_content.strip():
            continue

        chunks = chunk_text(text_content, chunk_size=1200, chunk_overlap=150)
        if not chunks:
            continue

        # Cap on-demand chunk indexing to at most 35 chunks per file to guarantee <= 1s embedding time
        capped_chunks = chunks[:35]
        indexed_file_ids.add(sfile["db_id"])
        chunks_to_store.extend(
            (sfile, idx, chunk_str)
            for idx, chunk_str in enumerate(capped_chunks)
        )

    if not chunks_to_store:
        return {}

    embeddings = await get_or_create_embeddings(
        [chunk for _, _, chunk in chunks_to_store],
        db,
    )

    for (sfile, idx, chunk_str), emb in zip(chunks_to_store, embeddings):
        clean_chunk = chunk_str.replace("\x00", "")
        db.add(DocumentChunk(
            file_id=sfile["db_id"],
            user_id=user_id,
            chunk_index=idx,
            chunk_text=clean_chunk,
            embedding=emb,
            token_count=len(clean_chunk.split()),
            metadata_={"file_name": sfile["name"], "file_id": sfile["file_id"]}
        ))

    result = await db.execute(
        select(DriveFile).where(DriveFile.id.in_(indexed_file_ids))
    )
    for db_file in result.scalars().all():
        db_file.is_embedded = True

    await db.commit()
    return {}

async def _get_query_embedding(
    query: str,
    query_embedding_cache: Optional[Dict[str, List[float]]] = None,
) -> List[float]:
    if query_embedding_cache is not None and query in query_embedding_cache:
        return query_embedding_cache[query]

    embedding = await asyncio.to_thread(embed_single_query, query)
    if query_embedding_cache is not None:
        query_embedding_cache[query] = embedding
    return embedding


async def _run_vector_search(
    db: AsyncSession,
    query: str,
    safe_db_ids: list,
    limit: int = 25,
    query_embedding_cache: Optional[Dict[str, List[float]]] = None,
) -> list:
    """Execute pgvector cosine similarity search and return ranked chunks."""
    query_vector = await _get_query_embedding(query, query_embedding_cache)
    query_vector_str = "[" + ",".join(map(str, query_vector)) + "]"
    sql = text("""
        SELECT dc.chunk_text, df.name as file_name,
               1 - (dc.embedding <=> :qvec) as similarity,
               df.file_id, df.source_modified_time
        FROM document_chunks dc
        JOIN drive_files df ON dc.file_id = df.id
        WHERE dc.file_id = ANY(:file_ids)
        ORDER BY dc.embedding <=> :qvec
        LIMIT :lim;
    """)
    result = await db.execute(sql, {"qvec": query_vector_str, "file_ids": safe_db_ids, "lim": limit})
    return [
        {
            "chunk_text": row[0],
            "file_name": row[1],
            "similarity": float(row[2]),
            "file_id": row[3],
            "source_modified_time": row[4],
        }
        for row in result
    ]


async def _run_filename_and_title_search(
    db: AsyncSession,
    query: str,
    safe_db_ids: list,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Concurrently match explicit file names, keywords, or folder mentions in the query."""
    from app.services.query_adaptive_service import _extract_query_tokens
    tokens = [t.lower() for t in _extract_query_tokens(query) if len(t) >= 3]
    if not tokens or not safe_db_ids:
        return []

    res = await db.execute(
        select(DriveFile.id, DriveFile.name).where(DriveFile.id.in_(safe_db_ids))
    )
    matching_file_ids = []
    for db_id, fname in res.all():
        fname_lower = (fname or "").lower()
        if any(t in fname_lower for t in tokens):
            matching_file_ids.append(db_id)

    if not matching_file_ids:
        return []

    sql = text("""
        SELECT dc.chunk_text, df.name as file_name,
               0.90 as similarity,
               df.file_id, df.source_modified_time
        FROM document_chunks dc
        JOIN drive_files df ON dc.file_id = df.id
        WHERE dc.file_id = ANY(:matched_ids)
        ORDER BY dc.chunk_index
        LIMIT :lim;
    """)
    chunk_res = await db.execute(sql, {"matched_ids": matching_file_ids, "lim": limit})
    return [
        {
            "chunk_text": row[0],
            "file_name": row[1],
            "similarity": float(row[2]),
            "file_id": row[3],
            "source_modified_time": row[4],
            "filename_matched": True,
        }
        for row in chunk_res
    ]


async def search_cached_user_documents(
    db: AsyncSession,
    user_id: str,
    query: str,
    selected_file_ids: Optional[List[str]] = None,
    query_embedding_cache: Optional[Dict[str, List[float]]] = None,
) -> List[Dict[str, Any]]:
    """Search previously indexed, guardrail-approved chunks before accessing Drive."""
    statement = select(DriveFile.id).where(
        DriveFile.user_id == user_id,
        DriveFile.guardrail_status == "PASSED",
        DriveFile.is_embedded.is_(True),
    )
    if selected_file_ids:
        statement = statement.where(DriveFile.file_id.in_(selected_file_ids))

    result = await db.execute(statement)
    safe_db_ids = list(result.scalars().all())
    if not safe_db_ids:
        return []

    if selected_file_ids and is_document_structure_query(query):
        statement = (
            select(
                DocumentChunk.chunk_text,
                DriveFile.name,
                DriveFile.file_id,
                DriveFile.source_modified_time,
            )
            .join(DriveFile, DocumentChunk.file_id == DriveFile.id)
            .where(
                DriveFile.id.in_(safe_db_ids),
                DriveFile.user_id == user_id,
                DriveFile.guardrail_status == "PASSED",
                DriveFile.is_embedded.is_(True),
            )
            .order_by(DriveFile.name, DocumentChunk.chunk_index)
        )
        chunks_result = await db.execute(statement)
        return [
            {
                "chunk_text": row[0],
                "file_name": row[1],
                "similarity": 1.0,
                "file_id": row[2],
                "source_modified_time": row[3],
            }
            for row in chunks_result
        ]

    retrieval_query = expand_query_for_retrieval(query)
    # Concurrent Hybrid Search: semantic vector search + explicit filename/keyword search
    vector_task = _run_vector_search(
        db,
        retrieval_query,
        safe_db_ids,
        limit=25,
        query_embedding_cache=query_embedding_cache,
    )
    filename_task = _run_filename_and_title_search(db, query, safe_db_ids, limit=10)
    vector_chunks, filename_chunks = await asyncio.gather(vector_task, filename_task)

    seen_chunk_texts = set()
    combined_raw_chunks = []
    for ch in filename_chunks + vector_chunks:
        ctext = ch.get("chunk_text", "").strip()
        if ctext and ctext not in seen_chunk_texts:
            seen_chunk_texts.add(ctext)
            combined_raw_chunks.append(ch)

    retrieved = chunk_relevance_filter(combined_raw_chunks, retrieval_query)
    meaningful = [
        c for c in retrieved
        if c.get("similarity", 0) >= 0.22
        or (c.get("similarity", 0) >= 0.15 and c.get("keyword_score", 0) >= 2)
        or c.get("filename_matched")
    ]
    if meaningful:
        return meaningful[:12]
    return []


async def _get_full_document_texts(db: AsyncSession, safe_db_ids: list) -> Dict[str, str]:
    """Retrieve all chunk texts per file for full-document fallback."""
    sql = text("""
        SELECT df.name as file_name, dc.chunk_text, dc.chunk_index
        FROM document_chunks dc
        JOIN drive_files df ON dc.file_id = df.id
        WHERE dc.file_id = ANY(:file_ids)
        ORDER BY df.name, dc.chunk_index;
    """)
    result = await db.execute(sql, {"file_ids": safe_db_ids})
    file_texts: Dict[str, List[str]] = {}
    for row in result:
        fname = row[0]
        if fname not in file_texts:
            file_texts[fname] = []
        file_texts[fname].append(row[1])
    return {fname: "\n\n".join(chunks) for fname, chunks in file_texts.items()}


async def node_vector_search(state: RAGState) -> Dict[str, Any]:
    """
    Step 4: Vector retrieval + universal relevance validation.

    Flow:
    ⓪ Full-document shortcut: if total indexed content per file is ≤6000 chars,
       pass entire document text as a single chunk — avoids retrieval misses.
    ① Run cosine similarity search against indexed chunks.
    ② Apply keyword relevance filter — drops chunks that don't actually
       mention the queried entity (e.g. wrong constituency). Works for
       ALL file types (PDF, DOCX, CSV, Excel, TXT, etc.).
    ③ If results are still insufficient, trigger query-adaptive extraction:
       - Downloads the source document from Google Drive.
       - Extracts ONLY sections matching the user's query.
       - Uses Gemini Vision OCR for scanned PDF pages.
       - Chunks and embeds only those targeted sections.
       - Re-runs vector search + keyword filter.
    """
    db = state["db"]
    query = state["query"]
    user_id = state["user_id"]
    google_account = state["google_account"]
    safe_files = state["safe_files"]

    if state.get("is_media_query") or not safe_files:
        return {"retrieved_chunks": []}

    requested_sheet = requested_sheet_name(query)
    sheet_candidate = requested_sheet
    if not sheet_candidate and state.get("selected_file_ids"):
        sheet_candidate = implicit_sheet_name_candidate(query)
    if sheet_candidate:
        sheet_safe_files = []
        searched_sheet_files = []
        sheet_chunk_metadata = []
        sheet_db_ids = [safe_file["db_id"] for safe_file in safe_files]
        db_result = await db.execute(
            select(DriveFile).where(DriveFile.id.in_(sheet_db_ids))
        )
        sheet_files_by_id = {
            db_file.id: db_file for db_file in db_result.scalars().all()
        }
        sheet_files = []
        for safe_file in safe_files:
            file_name = safe_file.get("name", "")
            db_file = sheet_files_by_id.get(safe_file["db_id"])
            mime_type = (
                db_file.mime_type if db_file else safe_file.get("mime_type", "")
            )
            if file_name.lower().endswith(".xlsx") or "spreadsheetml" in mime_type:
                sheet_files.append((safe_file, mime_type))
                searched_sheet_files.append(file_name)

        sheet_semaphore = asyncio.Semaphore(2)

        async def extract_requested_sheet(safe_file, mime_type):
            async with sheet_semaphore:
                # Reuse in-memory downloaded file bytes whenever available
                file_bytes = safe_file.get("file_bytes")
                if not file_bytes:
                    file_bytes = await asyncio.to_thread(
                        download_file,
                        google_account,
                        safe_file["file_id"],
                        mime_type,
                    )
                sheet_text = await asyncio.to_thread(
                    extract_excel_sheet_text,
                    file_bytes,
                    sheet_candidate,
                )
                return safe_file, sheet_text

        sheet_results = await asyncio.gather(
            *(
                extract_requested_sheet(safe_file, mime_type)
                for safe_file, mime_type in sheet_files
            ),
            return_exceptions=True,
        )
        for result in sheet_results:
            if isinstance(result, BaseException):
                raise result

        for safe_file, sheet_text in sheet_results:
            if not sheet_text:
                continue
            file_name = safe_file.get("name", "")
            sheet_safe_files.append(safe_file)
            for chunk_text_value in chunk_text(
                sheet_text,
                chunk_size=1200,
                chunk_overlap=150,
            ):
                sheet_chunk_metadata.append({
                    "chunk_text": chunk_text_value,
                    "file_name": file_name,
                    "file_id": safe_file["file_id"],
                    "source_modified_time": safe_file.get(
                        "source_modified_time"
                    ),
                    "sheet_name": sheet_candidate,
                })

        retrieved_chunks = []
        if sheet_chunk_metadata:
            sheet_embeddings = await get_or_create_embeddings(
                [item["chunk_text"] for item in sheet_chunk_metadata],
                db,
            )
            query_embedding = await _get_query_embedding(
                expand_query_for_retrieval(query),
                state.get("query_embedding_cache"),
            )
            semantic_chunks = []
            for item, embedding in zip(sheet_chunk_metadata, sheet_embeddings):
                semantic_chunks.append({
                    **item,
                    "similarity": sum(
                        float(query_value) * float(chunk_value)
                        for query_value, chunk_value in zip(
                            query_embedding,
                            embedding,
                        )
                    ),
                })
            retrieved_chunks = chunk_relevance_filter(
                semantic_chunks,
                query,
            )
            if not is_document_structure_query(query):
                retrieved_chunks = retrieved_chunks[:12]

        if requested_sheet or retrieved_chunks:
            return {
                "retrieved_chunks": retrieved_chunks,
                "requested_sheet_name": sheet_candidate,
                "sheet_scoped_safe_files": sheet_safe_files,
                "sheet_search_file_names": searched_sheet_files,
            }

    if not safe_files:
        return {"retrieved_chunks": []}

    safe_db_ids = [s["db_id"] for s in safe_files]
    retrieval_query = expand_query_for_retrieval(query)

    # ── ⓪ Full-document shortcut for small/medium files ──────────────────
    # If the total text of all selected files is small enough, skip vector
    # search entirely and pass the full document text to the LLM.
    FULL_DOC_CHAR_LIMIT = 12000
    full_doc_texts = await _get_full_document_texts(db, safe_db_ids)
    total_chars = sum(len(t) for t in full_doc_texts.values())

    if total_chars > 0 and (
        total_chars <= FULL_DOC_CHAR_LIMIT
        or is_document_structure_query(query)
    ):
        logger.info(
            f"[RAG] Full-document shortcut: {len(full_doc_texts)} file(s), "
            f"{total_chars} total chars — sending complete text to LLM."
        )
        full_doc_chunks = [
            {
                "chunk_text": doc_text,
                "file_name": fname,
                "similarity": 1.0,
                "keyword_score": 99,
                "combined_score": 1.0,
            }
            for fname, doc_text in full_doc_texts.items()
        ]
        return {"retrieved_chunks": full_doc_chunks}

    # ── ① Initial concurrent hybrid search (vector + filename/title match) ──
    query_embedding_cache = state.get("query_embedding_cache")
    vector_task = _run_vector_search(
        db,
        retrieval_query,
        safe_db_ids,
        limit=25,
        query_embedding_cache=query_embedding_cache,
    )
    filename_task = _run_filename_and_title_search(db, query, safe_db_ids, limit=10)
    vector_chunks, filename_chunks = await asyncio.gather(vector_task, filename_task)

    seen_texts = set()
    combined_raw = []
    for ch in filename_chunks + vector_chunks:
        ctext = ch.get("chunk_text", "").strip()
        if ctext and ctext not in seen_texts:
            seen_texts.add(ctext)
            combined_raw.append(ch)

    retrieved = chunk_relevance_filter(combined_raw, retrieval_query)
    logger.info(
        f"[RAG] After keyword filter: {len(retrieved)} chunks, "
        f"top sim={max((c['similarity'] for c in retrieved), default=0):.3f}"
    )

    # ── ③ Adaptive extraction if still insufficient ──────────────────────
    # Only run heavy adaptive sectioning if the user explicitly selected files and evidence is weak.
    top_sim = max((c.get("similarity", 0) for c in retrieved), default=0)
    top_kw = max((c.get("keyword_score", 0) for c in retrieved), default=0)
    has_strong_evidence = top_sim >= 0.28 or top_kw >= 2 or any(c.get("filename_matched") for c in retrieved)

    if not state.get("auto_discovered") and not has_strong_evidence and needs_adaptive_embedding(retrieved, retrieval_query):
        logger.info(
            "[RAG] Results insufficient for selected file(s) — triggering adaptive extraction."
        )
        for sfile in safe_files:
            file_id = sfile.get("file_id")
            db_id = sfile.get("db_id")
            name = sfile.get("name", "")

            try:
                res = await db.execute(select(DriveFile).where(DriveFile.id == db_id))
                db_file = res.scalars().first()
                mime = db_file.mime_type if db_file else "application/octet-stream"

                logger.info(f"[RAG] Adaptive extraction: {name} (mime={mime})")
                # Reuse in-memory bytes if available to eliminate redundant Drive network downloads
                file_bytes = sfile.get("file_bytes")
                if not file_bytes:
                    file_bytes = await asyncio.to_thread(
                        download_file, google_account, file_id, mime
                    )

                new_chunks = await adaptive_embed_for_query(
                    file_bytes=file_bytes,
                    file_name=name,
                    mime_type=mime,
                    query=retrieval_query,
                    db_file_id=db_id,
                    user_id=user_id,
                    db=db,
                )
                logger.info(
                    f"[RAG] Adaptive extraction added {len(new_chunks)} chunks for {name}."
                )
            except Exception as exc:
                logger.warning(f"[RAG] Adaptive extraction failed for {name}: {exc}")

        # Re-run search + filter with fresh embeddings
        retrieved = await _run_vector_search(
            db,
            retrieval_query,
            safe_db_ids,
            query_embedding_cache=query_embedding_cache,
        )
        retrieved = chunk_relevance_filter(retrieved, retrieval_query)
        logger.info(
            f"[RAG] Post-adaptive: {len(retrieved)} chunks, "
            f"top sim={max((c['similarity'] for c in retrieved), default=0):.3f}, "
            f"top kw_score={max((c.get('keyword_score',0) for c in retrieved), default=0)}"
        )

    return {"retrieved_chunks": retrieved}

async def node_synthesize(state: RAGState) -> Dict[str, Any]:
    """
    Step 5: Generate answer using Gemini LLM with citations and audit logging.
    """
    db = state["db"]
    user_id = state["user_id"]
    query = state["query"]
    retrieved_chunks = state.get("retrieved_chunks", [])
    confidential_files = state.get("confidential_files", [])
    candidate_files = state.get("candidate_files", [])
    safe_files = state.get("safe_files", [])
    requested_sheet = (
        state.get("requested_sheet_name") or requested_sheet_name(query)
    )
    sheet_scoped_safe_files = state.get("sheet_scoped_safe_files", [])
    auto_discovered = state.get("auto_discovered", False)
    available_files = state.get("available_files", [])

    source_files = sheet_scoped_safe_files if requested_sheet else safe_files
    selected_names = (
        [f.get("name") for f in source_files if f.get("name")]
        if requested_sheet
        else [f.get("name") for f in candidate_files if f.get("name")]
        or [s.get("name") for s in safe_files if s.get("name")]
    )
    all_file_names = [f.get("name") for f in available_files if f.get("name")]

    if state.get("is_media_query"):
        chat_log = ChatQuery(
            user_id=user_id,
            query_text=query,
            identified_files=selected_names,
            skipped_files=[],
            answer_text=MEDIA_QUERY_RESPONSE
        )
        db.add(chat_log)
        await db.commit()
        return {"answer": MEDIA_QUERY_RESPONSE}

    if requested_sheet and not retrieved_chunks:
        searched_file_names = state.get("sheet_search_file_names", [])
        searched_names = (
            ", ".join(searched_file_names)
            or ", ".join(selected_names)
            or "the searched files"
        )
        answer = (
            f"I couldn't find a worksheet named “{requested_sheet}” in "
            f"{searched_names}. I did not use information from other sheets or files."
        )
        db.add(ChatQuery(
            user_id=user_id,
            query_text=query,
            identified_files=selected_names,
            skipped_files=[],
            answer_text=answer,
        ))
        await db.commit()
        return {"answer": answer}

    if not retrieved_chunks and not confidential_files:
        answer = (
            "The information you're asking about isn't in your Google Drive. "
            "Would you like me to answer using general knowledge instead?"
        )
        db.add(ChatQuery(
            user_id=user_id,
            query_text=query,
            identified_files=[],
            skipped_files=[],
            answer_text=answer,
        ))
        await db.commit()
        return {"answer": answer, "needs_general_confirmation": True}

    if state.get("intent") == "document_search" and not retrieved_chunks:
        searched_names = [
            file_info.get("name")
            for file_info in safe_files
            if file_info.get("name")
        ]
        if searched_names:
            answer = (
                "I searched the available content in "
                f"{', '.join(searched_names)} but did not find text identifying "
                "an agreement or contract. This only covers the documents that "
                "were searchable for this request."
            )
        elif confidential_files:
            answer = (
                "I could not verify whether an agreement was present because the "
                "likely document(s) were withheld by the privacy checks."
            )
        else:
            answer = (
                "I could not identify searchable documents likely to contain an "
                "agreement, so I cannot confirm whether one exists in your Drive. "
                "Try selecting the relevant files or asking with a document name."
            )

        db.add(ChatQuery(
            user_id=user_id,
            query_text=query,
            identified_files=selected_names,
            skipped_files=confidential_files,
            answer_text=answer,
        ))
        await db.commit()
        return {"answer": answer}

    answer = await synthesize_answer(
        query,
        retrieved_chunks,
        confidential_files,
        selected_file_names=selected_names,
        auto_discovered=auto_discovered,
        available_file_names=all_file_names,
        intent=state.get("intent", "general"),
    )

    is_out_of_scope = (
        "do not contain information regarding" in answer
        or "does not contain information regarding" in answer
        or "doesn't contain information regarding" in answer
    )
    if is_out_of_scope:
        if auto_discovered:
            answer = (
                "The information you're asking about isn't in your Google Drive documents. "
                "Would you like me to answer using general knowledge instead?"
            )
            selected_names = []
        else:
            selected_str = ", ".join(selected_names) if selected_names else "selected document(s)"
            answer = (
                f"The selected document(s) ({selected_str}) do not contain information regarding '{query}'. "
                f"Would you like me to answer using general knowledge instead?"
            )
        chat_log = ChatQuery(
            user_id=user_id,
            query_text=query,
            identified_files=selected_names,
            skipped_files=confidential_files,
            answer_text=answer,
        )
        db.add(chat_log)
        await db.commit()
        return {
            "answer": answer,
            "needs_general_confirmation": True,
            "candidate_files": selected_names,
            "safe_files": [] if auto_discovered else safe_files,
            "retrieved_chunks": [],
        }

    # Save to chat_queries table
    chat_log = ChatQuery(
        user_id=user_id,
        query_text=query,
        identified_files=selected_names,
        skipped_files=confidential_files,
        answer_text=answer
    )
    db.add(chat_log)
    await db.commit()

    return {"answer": answer}


def _timed_node(
    name: str,
    node: Callable[[RAGState], Awaitable[Dict[str, Any]]],
) -> Callable[[RAGState], Awaitable[Dict[str, Any]]]:
    async def run(state):
        started_at = time.perf_counter()
        try:
            res = await node(state)
            if isinstance(res, dict) and "_live_tracker" in state and isinstance(state["_live_tracker"], dict):
                state["_live_tracker"].update(res)
            return res
        finally:
            logger.info(
                "[RAG] Stage %s finished in %.3fs",
                name,
                time.perf_counter() - started_at,
            )

    return run


def create_rag_graph():
    """
    Constructs the LangGraph state machine workflow.
    """
    workflow = StateGraph(RAGState)

    workflow.add_node("analyze_query", _timed_node("analyze_query", node_analyze_query))
    workflow.add_node("guardrail_gate", _timed_node("guardrail_gate", node_guardrail_gate))
    workflow.add_node("index_safe_files", _timed_node("index_safe_files", node_index_safe_files))
    workflow.add_node("vector_search", _timed_node("vector_search", node_vector_search))
    workflow.add_node("synthesize", _timed_node("synthesize", node_synthesize))

    workflow.set_entry_point("analyze_query")
    workflow.add_edge("analyze_query", "guardrail_gate")
    workflow.add_edge("guardrail_gate", "index_safe_files")
    workflow.add_edge("index_safe_files", "vector_search")
    workflow.add_edge("vector_search", "synthesize")
    workflow.add_edge("synthesize", END)

    return workflow.compile()
