from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from app.db import get_db
from app.config import settings
from app.models import User, GoogleAccount, QueryAnswerCache
from app.services.auth_service import generate_authorization_url, handle_oauth_callback

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.get("/google/url")
def get_google_auth_url(redirect_state: str = Query(None)):
    """
    Generates Google OAuth URL for user consent.
    """
    try:
        url, state = generate_authorization_url(redirect_state)
        return {"authorization_url": url, "state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/google/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Exchanges code for access & refresh tokens, upserts user in DB, and redirects to frontend.
    """
    try:
        user = await handle_oauth_callback(code, db, state=state)
        print(f"[AUTH SUCCESS] User connected: {user.email} (id: {user.id})")
        # Redirect to frontend dashboard with user_id
        redirect_target = f"{settings.FRONTEND_URL}?user_id={user.id}&connected=true"
        return RedirectResponse(url=redirect_target)
    except Exception as e:
        import traceback
        print(f"[AUTH ERROR] OAuth callback failed: {e}")
        traceback.print_exc()
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?error={str(e)}")

@router.get("/me")
async def get_user_status(user_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    """
    Checks user and Google Drive connection status.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.user_id == user.id))
    google_acc = acc_res.scalars().first()

    return {
        "user_id": str(user.id),
        "email": user.email,
        "is_drive_connected": google_acc is not None,
        "google_email": google_acc.email if google_acc else None
    }

@router.delete("/disconnect")
async def disconnect_google_drive(user_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    """
    Revokes Google Drive access by removing the stored OAuth credentials.
    The user account itself is preserved so they can reconnect later.
    """
    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.user_id == user_id))
    google_acc = acc_res.scalars().first()

    if not google_acc:
        raise HTTPException(status_code=404, detail="No connected Google Drive account found.")

    await db.execute(
        delete(QueryAnswerCache).where(QueryAnswerCache.user_id == user_id)
    )
    await db.delete(google_acc)
    await db.commit()

    print(f"[AUTH] Google Drive disconnected for user_id={user_id}")
    return {"success": True, "message": "Google Drive disconnected successfully."}
