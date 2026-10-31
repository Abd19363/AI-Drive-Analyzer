import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db import get_db
from app.models import User, GoogleAccount, DriveFile
from app.services.drive_service import list_files_cached, clear_file_catalog_cache, get_folder_children
from app.services.guardrail_service import screen_metadata

router = APIRouter(prefix="/api/drive", tags=["drive"])

@router.get("/files")
async def get_user_drive_files(
    user_id: str = Query(...),
    refresh: bool = Query(False),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches the user's Google Drive files and merges with guardrail/embedding status from DB.
    """
    # Fetch google credentials
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.user_id == user_id))
    google_acc = acc_res.scalars().first()
    if not google_acc:
        return {"files": [], "error": "NOT_CONNECTED", "message": "Google Drive is not connected."}

    # Fetch files from Drive (supports cache and forced refresh)
    try:
        drive_items = await asyncio.to_thread(
            list_files_cached, google_acc, page_size=100, force_refresh=refresh
        )
    except Exception as e:
        err_str = str(e)
        print(f"[DRIVE API ERROR] {err_str}")
        if "insufficient" in err_str.lower() or "permission" in err_str.lower() or "403" in err_str:
            return {
                "files": [],
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": "Google Drive permission was not granted. Please reconnect and make sure to check the box: 'See and download all your Google Drive files'."
            }
        elif "disabled" in err_str.lower() or "not been used" in err_str.lower():
            return {
                "files": [],
                "error": "API_NOT_ENABLED",
                "message": "Google Drive API is not enabled in Google Cloud Console."
            }
        return {"files": [], "error": "API_ERROR", "message": f"Google Drive API error: {err_str}"}

    # Fetch cached DB records for these files
    file_ids = [f.get("id") for f in drive_items]
    db_res = await db.execute(
        select(DriveFile).where(DriveFile.user_id == user_id, DriveFile.file_id.in_(file_ids))
    )
    db_files_map = {df.file_id: df for df in db_res.scalars().all()}

    # Merge status
    enriched_files = []
    for f in drive_items:
        fid = f.get("id")
        fname = f.get("name", "")
        cached = db_files_map.get(fid)

        # Run upfront metadata screening so newly-added sensitive patterns
        # (e.g. easypaisa, psid, receipt) are reflected in the UI immediately
        meta_flagged, meta_reason, meta_type = screen_metadata(fname)
        guardrail_status = cached.guardrail_status if cached else "UNCHECKED"
        confidentiality_reason = cached.confidentiality_reason if cached else None

        if meta_flagged and guardrail_status != "FLAGGED_CONFIDENTIAL":
            guardrail_status = "FLAGGED_CONFIDENTIAL"
            confidentiality_reason = meta_reason

        enriched_files.append({
            "id": fid,
            "name": fname,
            "mime_type": f.get("mimeType"),
            "size": f.get("size"),
            "web_view_link": f.get("webViewLink"),
            "modified_time": f.get("modifiedTime"),
            "guardrail_status": guardrail_status,
            "confidentiality_reason": confidentiality_reason,
            "is_embedded": cached.is_embedded if cached else False,
            "last_scanned_at": cached.last_scanned_at if cached else None,
            "parent_id": f.get("parent_id"),
            "folder_name": f.get("folder_name"),
            "is_folder": f.get("mimeType") == "application/vnd.google-apps.folder" or f.get("is_folder") is True,
        })

    return {"files": enriched_files}


@router.get("/folder-children")
async def get_folder_children_route(
    user_id: str = Query(...),
    folder_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches direct children (files and sub-folders) for a given folder on demand.
    """
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.user_id == user_id))
    google_acc = acc_res.scalars().first()
    if not google_acc:
        return {"files": [], "error": "NOT_CONNECTED"}

    try:
        children = await asyncio.to_thread(get_folder_children, google_acc, folder_id)
        file_ids = [c.get("id") for c in children]
        db_res = await db.execute(
            select(DriveFile).where(DriveFile.user_id == user_id, DriveFile.file_id.in_(file_ids))
        )
        db_files_map = {df.file_id: df for df in db_res.scalars().all()}

        enriched = []
        for c in children:
            fid = c.get("id")
            fname = c.get("name", "")
            cached = db_files_map.get(fid)
            meta_flagged, meta_reason, _ = screen_metadata(fname)
            guardrail_status = cached.guardrail_status if cached else "UNCHECKED"
            confidentiality_reason = cached.confidentiality_reason if cached else None

            if meta_flagged and guardrail_status != "FLAGGED_CONFIDENTIAL":
                guardrail_status = "FLAGGED_CONFIDENTIAL"
                confidentiality_reason = meta_reason

            enriched.append({
                "id": fid,
                "name": fname,
                "mime_type": c.get("mimeType"),
                "size": c.get("size"),
                "web_view_link": c.get("webViewLink"),
                "modified_time": c.get("modifiedTime"),
                "guardrail_status": guardrail_status,
                "confidentiality_reason": confidentiality_reason,
                "is_embedded": cached.is_embedded if cached else False,
                "last_scanned_at": cached.last_scanned_at if cached else None,
                "parent_id": folder_id,
                "is_folder": c.get("mimeType") == "application/vnd.google-apps.folder" or c.get("is_folder") is True,
            })

        return {"files": enriched}
    except Exception as e:
        return {"files": [], "error": str(e)}
