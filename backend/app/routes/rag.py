import asyncio
import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db import get_db
from app.models import User, GoogleAccount, ChatQuery
from app.services.drive_service import list_files_cached
from app.services.gemini_service import GeminiServiceUnavailableError
from app.services.rag_workflow import create_rag_graph
from app.services.query_intent_service import classify_query_intent

router = APIRouter(prefix="/api/rag", tags=["rag"])
logger = logging.getLogger(__name__)

class QuestionRequest(BaseModel):
    user_id: str
    query: str
    selected_file_ids: Optional[List[str]] = None
    query_id: Optional[str] = None


class CancelQueryRequest(BaseModel):
    user_id: str
    query_id: str

# Instantiate the compiled LangGraph
rag_graph = create_rag_graph()
_active_queries: dict[str, tuple[str, asyncio.Task]] = {}

@router.post("/ask")
async def ask_question(payload: QuestionRequest, db: AsyncSession = Depends(get_db)):
    """
    On-Demand RAG Query Endpoint:
    1. Does NOT embed all files upfront.
    2. Takes user query and selected file(s) (or automatically discovers if none selected).
    3. Runs candidate files through 4-layer privacy guardrail (OCR, Regex, Metadata).
    4. Confidentials are blocked and excluded from embeddings.
    5. Safe candidates are chunked & embedded with all-MiniLM-L6-v2 (384-dim).
    6. Vector search + Gemini response with citations and out-of-scope detection.
    """
    user_id = payload.user_id
    query = payload.query.strip()
    selected_file_ids = payload.selected_file_ids or []

    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    intent = classify_query_intent(query)
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
    else:
        answer = None

    if answer is not None:
        db.add(ChatQuery(
            user_id=user_id,
            query_text=query,
            identified_files=[],
            skipped_files=[],
            answer_text=answer,
        ))
        await db.commit()
        return {
            "query": query,
            "intent": intent,
            "answer": answer,
            "auto_discovered": False,
            "candidate_files": [],
            "safe_embedded_files": [],
            "blocked_confidential_files": [],
            "retrieved_sources": [],
        }

    # Validate user & drive connection
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.user_id == user_id))
    google_acc = acc_res.scalars().first()
    if not google_acc:
        raise HTTPException(status_code=400, detail="Google Drive is not connected.")

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
        "selected_file_ids": selected_file_ids,
        "available_files": available_files,
        "candidate_files": [],
        "safe_files": [],
        "confidential_files": [],
        "retrieved_chunks": [],
        "answer": "",
        "auto_discovered": len(selected_file_ids) == 0,
        "is_media_query": False,
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

    return {
        "query": query,
        "intent": intent,
        "answer": final_state.get("answer"),
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
