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
from app.services.drive_service import download_file
from app.services.guardrail_service import (
    run_guardrails,
    screen_metadata,
    is_media_file,
    is_query_about_media,
    MEDIA_QUERY_RESPONSE,
)
from app.services.extractor_service import chunk_text
from app.services.embedding_service import get_or_create_embeddings, embed_single_query
from app.services.gemini_service import analyze_query_for_drive_files, synthesize_answer
from app.services.query_adaptive_service import (
    adaptive_embed_for_query,
    adaptive_embed_pdf_for_query,  # kept for backward compat
    chunk_relevance_filter,
    expand_query_for_retrieval,
    needs_adaptive_embedding,
)
from app.services.query_intent_service import QueryIntent

logger = logging.getLogger(__name__)

class RAGState(TypedDict):
    db: AsyncSession
    user_id: str
    google_account: Any
    query: str
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
        # Auto-discovery: AI analysis over Drive catalog
        auto_discovered = True
        if query_is_media:
            return {
                "candidate_files": [],
                "auto_discovered": True,
                "is_media_query": True
            }

        candidate_files = await analyze_query_for_drive_files(query, available_files)
        # Exclude media files from auto-discovery candidates
        candidate_files = [f for f in candidate_files if not is_media_file(f)]
        logger.info(f"[RAG] Auto-discovery identified {len(candidate_files)} candidate file(s): {[f.get('name') for f in candidate_files]}")

    # Expand any candidate folders into their actual document files
    expanded = []
    for cfile in candidate_files:
        if cfile.get("mimeType") == "application/vnd.google-apps.folder":
            fname = cfile.get("name")
            children = [
                f for f in available_files
                if f.get("folder_name") == fname
                and f.get("mimeType") != "application/vnd.google-apps.folder"
                and not is_media_file(f)
            ]
            if children:
                expanded.extend(children[:10])
            else:
                expanded.append(cfile)
        else:
            if not is_media_file(cfile):
                expanded.append(cfile)

    seen = set()
    unique_candidates = [f for f in expanded if f.get("id") not in seen and not seen.add(f.get("id"))]
    return {"candidate_files": unique_candidates, "auto_discovered": auto_discovered, "is_media_query": False}

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
            # Update DB record if it exists
            res_meta = await db.execute(
                select(DriveFile).where(DriveFile.user_id == user_id, DriveFile.file_id == file_id)
            )
            db_file_meta = res_meta.scalars().first()
            if db_file_meta:
                db_file_meta.guardrail_status = "FLAGGED_CONFIDENTIAL"
                db_file_meta.confidentiality_reason = meta_reason
                # Delete any previously embedded chunks
                if db_file_meta.is_embedded:
                    await db.execute(delete(DocumentChunk).where(DocumentChunk.file_id == db_file_meta.id))
                    db_file_meta.is_embedded = False
            confidential_files.append({
                "id": file_id,
                "name": file_name,
                "reason": meta_reason,
                "detection_type": meta_type
            })
            continue

        # Check or create DriveFile entry in DB
        res = await db.execute(
            select(DriveFile).where(DriveFile.user_id == user_id, DriveFile.file_id == file_id)
        )
        db_file = res.scalars().first()
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
            await db.flush()
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
                "is_embedded": True
            })
            continue

        if not is_unchanged or not db_file.is_embedded:
            await db.execute(delete(DocumentChunk).where(DocumentChunk.file_id == db_file.id))
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
                return file_info, None, exc

            guard_result = await asyncio.to_thread(
                run_guardrails,
                file_info["file_name"],
                file_info["mime_type"],
                file_bytes,
            )
            return file_info, guard_result, None

    inspection_results = await asyncio.gather(
        *(inspect_file(file_info) for file_info in files_to_inspect)
    )

    for file_info, guard_result, download_error in inspection_results:
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
                "extracted_text": guard_result.get("extracted_text", ""),
                "is_embedded": db_file.is_embedded
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
            continue

        chunks = chunk_text(text_content, chunk_size=1200, chunk_overlap=150)
        if not chunks:
            continue

        indexed_file_ids.add(sfile["db_id"])
        chunks_to_store.extend(
            (sfile, idx, chunk_str)
            for idx, chunk_str in enumerate(chunks)
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

async def _run_vector_search(db: AsyncSession, query: str, safe_db_ids: list, limit: int = 25) -> list:
    """Execute pgvector cosine similarity search and return ranked chunks."""
    query_vector = await asyncio.to_thread(embed_single_query, query)
    query_vector_str = "[" + ",".join(map(str, query_vector)) + "]"
    sql = text("""
        SELECT dc.chunk_text, df.name as file_name, 1 - (dc.embedding <=> :qvec) as similarity
        FROM document_chunks dc
        JOIN drive_files df ON dc.file_id = df.id
        WHERE dc.file_id = ANY(:file_ids)
        ORDER BY dc.embedding <=> :qvec
        LIMIT :lim;
    """)
    result = await db.execute(sql, {"qvec": query_vector_str, "file_ids": safe_db_ids, "lim": limit})
    return [
        {"chunk_text": row[0], "file_name": row[1], "similarity": float(row[2])}
        for row in result
    ]


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

    safe_db_ids = [s["db_id"] for s in safe_files]
    retrieval_query = expand_query_for_retrieval(query)

    # ── ⓪ Full-document shortcut for small/medium files ──────────────────
    # If the total text of all selected files is small enough, skip vector
    # search entirely and pass the full document text to the LLM.
    FULL_DOC_CHAR_LIMIT = 12000
    full_doc_texts = await _get_full_document_texts(db, safe_db_ids)
    total_chars = sum(len(t) for t in full_doc_texts.values())

    if total_chars > 0 and total_chars <= FULL_DOC_CHAR_LIMIT:
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

    # ── ① Initial vector search ──────────────────────────────────────────
    retrieved = await _run_vector_search(db, retrieval_query, safe_db_ids)

    # ── ② Post-retrieval keyword filter (universal, any file type) ───────
    retrieved = chunk_relevance_filter(retrieved, retrieval_query)
    logger.info(
        f"[RAG] After keyword filter: {len(retrieved)} chunks, "
        f"top sim={max((c['similarity'] for c in retrieved), default=0):.3f}"
    )

    # ── ③ Adaptive extraction if still insufficient ──────────────────────
    if needs_adaptive_embedding(retrieved, retrieval_query):
        logger.info(
            "[RAG] Results insufficient — triggering universal adaptive extraction."
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
        retrieved = await _run_vector_search(db, retrieval_query, safe_db_ids)
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
    auto_discovered = state.get("auto_discovered", False)
    available_files = state.get("available_files", [])

    selected_names = [f.get("name") for f in candidate_files if f.get("name")] or [s.get("name") for s in safe_files if s.get("name")]
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
            return await node(state)
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
