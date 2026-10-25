from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db import get_db
from app.models import GuardrailLog, DriveFile

router = APIRouter(prefix="/api/guardrails", tags=["guardrails"])

@router.get("/logs")
async def get_guardrail_logs(user_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    """
    Retrieves the security guardrail audit logs for blocked files.
    """
    result = await db.execute(
        select(GuardrailLog)
        .join(DriveFile, GuardrailLog.file_id == DriveFile.id)
        .where(DriveFile.user_id == user_id)
        .order_by(GuardrailLog.created_at.desc())
        .options(selectinload(GuardrailLog.file))
    )
    logs = result.scalars().all()

    formatted_logs = [
        {
            "id": str(log.id),
            "file_name": log.file.name if log.file else "Unknown",
            "check_stage": log.check_stage,
            "detection_type": log.detection_type,
            "snippet_matched": log.snippet_matched,
            "confidence_score": log.confidence_score,
            "timestamp": log.created_at.isoformat() if log.created_at else None
        }
        for log in logs
    ]

    return {"logs": formatted_logs}
