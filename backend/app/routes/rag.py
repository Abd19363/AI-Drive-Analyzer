import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db import get_db
from app.models import User, GoogleAccount, ChatQuery
from app.services.drive_service import list_files
from app.services.gemini_service import GeminiServiceUnavailableError
from app.services.rag_workflow import create_rag_graph

router = APIRouter(prefix="/api/rag", tags=["rag"])

class QuestionRequest(BaseModel):
    user_id: str
    query: str
    selected_file_ids: Optional[List[str]] = None

# Instantiate the compiled LangGraph
rag_graph = create_rag_graph()

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

    # Validate user & drive connection
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.user_id == user_id))
    google_acc = acc_res.scalars().first()
    if not google_acc:
        raise HTTPException(status_code=400, detail="Google Drive is not connected.")

    # Retrieve current file catalog from Google Drive
    try:
        available_files = await asyncio.to_thread(list_files, google_acc, page_size=100)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to access Google Drive: {str(e)}")

    # Initialize Graph State
    initial_state = {
        "db": db,
        "user_id": user_id,
        "google_account": google_acc,
        "query": query,
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
    try:
        final_state = await rag_graph.ainvoke(initial_state)
    except GeminiServiceUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        import traceback
        print(f"[RAG ERROR] Workflow failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"RAG execution error: {str(e)}")

    return {
        "query": query,
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
