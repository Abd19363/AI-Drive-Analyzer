import logging
import time
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, func

from app.db import get_db
from app.config import settings
from app.models import User, GoogleAccount, QueryAnswerCache, AdminUser
from app.services.auth_service import generate_authorization_url, handle_oauth_callback
from app.services.email_service import send_password_reset_email
from app.routes.admin import hash_password, verify_password, generate_verification_code

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def create_user_token(user_id: str, email: str, expires_in_hours: int = 72) -> str:
    payload = {
        "user_id": str(user_id),
        "email": email,
        "exp": int(time.time()) + (expires_in_hours * 3600),
    }
    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(json_bytes).decode("utf-8").rstrip("=")
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{sig}"


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────
class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserForgotPasswordRequest(BaseModel):
    email: str


class UserResetPasswordRequest(BaseModel):
    email: str
    verification_code: str
    new_password: str


# ─────────────────────────────────────────────────────────────
# User Authentication & Password Reset Endpoints
# ─────────────────────────────────────────────────────────────
@router.post("/register")
async def user_register(payload: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user for the User Portal."""
    email = payload.email.strip().lower()
    password = payload.password.strip()
    full_name = payload.full_name.strip() if payload.full_name else email.split("@")[0]

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is required.",
        )

    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long.",
        )

    user_res = await db.execute(select(User).where(func.lower(User.email) == email))
    user = user_res.scalars().first()

    if user:
        if user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please sign in or reset your password.",
            )
        # Existing OAuth user setting a password for the first time
        user.password_hash = hash_password(password)
        if full_name:
            user.full_name = full_name
        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
    else:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.user_id == user.id))
    google_acc = acc_res.scalars().first()

    token = create_user_token(str(user.id), user.email)
    return {
        "success": True,
        "token": token,
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "is_drive_connected": google_acc is not None,
        "google_email": google_acc.email if google_acc else None,
    }


@router.post("/login")
async def user_login(payload: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Sign in to the User Portal with email and password."""
    email = payload.email.strip().lower()
    password = payload.password.strip()

    user_res = await db.execute(select(User).where(func.lower(User.email) == email))
    user = user_res.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No account found with this email. Please click 'Create Account' to register.",
        )

    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No password has been set for this account yet. Please use 'Forgot Password' to set one.",
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please verify your password or use 'Forgot password?'.",
        )

    acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.user_id == user.id))
    google_acc = acc_res.scalars().first()

    token = create_user_token(str(user.id), user.email)
    return {
        "success": True,
        "token": token,
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name or user.email.split("@")[0],
        "is_drive_connected": google_acc is not None,
        "google_email": google_acc.email if google_acc else None,
    }


@router.post("/forgot-password")
async def user_forgot_password(payload: UserForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Send a 6-digit password reset verification code to the user's email."""
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is required.",
        )

    user_res = await db.execute(select(User).where(func.lower(User.email) == email))
    user = user_res.scalars().first()

    if not user:
        return {
            "success": True,
            "message": "If an account exists with this email, a 6-digit verification code has been sent.",
        }

    code = generate_verification_code()
    user.reset_code = code
    user.reset_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db.commit()

    try:
        await send_password_reset_email(
            to_email=user.email,
            verification_code=code,
            recipient_name=user.full_name or "User",
        )
    except Exception as e:
        logger.warning("[USER AUTH] Failed to send password reset email: %s", e)

    return {
        "success": True,
        "message": "A 6-digit verification code has been sent to your registered email.",
    }


@router.post("/reset-password")
async def user_reset_password(payload: UserResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Verify code and update the user's password."""
    email = payload.email.strip().lower()
    code = payload.verification_code.strip()
    new_password = payload.new_password.strip()

    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters long.",
        )

    user_res = await db.execute(select(User).where(func.lower(User.email) == email))
    user = user_res.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or verification code.",
        )

    if not user.reset_code or user.reset_code.strip() != code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please check your email and try again.",
        )

    now = datetime.now(timezone.utc)
    expires = user.reset_code_expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if not expires or now > expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code has expired (valid for 15 minutes). Please request a new one.",
        )

    user.password_hash = hash_password(new_password)
    user.reset_code = None
    user.reset_code_expires_at = None
    user.updated_at = datetime.now(timezone.utc)

    # Synchronize with User Admin account if one exists
    admin_res = await db.execute(
        select(AdminUser).where(
            (AdminUser.linked_user_id == user.id) | (func.lower(AdminUser.email) == email)
        )
    )
    admin_match = admin_res.scalars().first()
    if admin_match and admin_match.role == "SECONDARY_ADMIN":
        admin_match.password_hash = user.password_hash
        admin_match.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "success": True,
        "message": "Password updated successfully! You can now sign in with your new password.",
    }


# ─────────────────────────────────────────────────────────────
# Google OAuth Endpoints
# ─────────────────────────────────────────────────────────────
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
