import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import AdminUser, QueryTelemetry, ChatQuery, User, GoogleAccount
from app.services.email_service import (
    notify_super_admin_of_registration,
    notify_applicant_of_status,
    send_password_reset_email,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─────────────────────────────────────────────────────────────
# Password Hashing & Token Helpers
# ─────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_admin_token(admin_id: str, email: str, role: str, expires_in_hours: int = 24) -> str:
    payload = {
        "admin_id": str(admin_id),
        "email": email,
        "role": role,
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


def decode_admin_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None

        # Add padding back if necessary
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


async def get_current_admin(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required. Please provide a valid Bearer token.",
        )
    token = authorization[7:].strip()
    payload = decode_admin_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin session token.",
        )

    admin_res = await db.execute(
        select(AdminUser).where(AdminUser.id == uuid.UUID(payload["admin_id"]))
    )
    admin = admin_res.scalars().first()
    if not admin or admin.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is not active or approved.",
        )
    return admin


def generate_verification_code() -> str:
    """Generate a secure 6-digit numeric verification code."""
    return f"{secrets.randbelow(900000) + 100000}"


# ─────────────────────────────────────────────────────────────
# Request / Response Schemas
# ─────────────────────────────────────────────────────────────
class AdminLoginRequest(BaseModel):
    email: str
    password: str
    role_type: Optional[str] = "ANY"  # "LEAD_ADMIN" | "USER_ADMIN" | "ANY"


class AdminRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    request_note: Optional[str] = None
    role_type: Optional[str] = "USER_ADMIN"  # "LEAD_ADMIN" | "USER_ADMIN"


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    verification_code: str
    new_password: str


class AdminApprovalActionRequest(BaseModel):
    admin_id: str
    action: str  # "APPROVE" or "REJECT"


# ─────────────────────────────────────────────────────────────
# Endpoints: Setup Status, Auth & Password Reset
# ─────────────────────────────────────────────────────────────
@router.get("/setup-status")
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    """Check if the initial Lead Admin has been registered."""
    super_admin_res = await db.execute(
        select(AdminUser).where(AdminUser.role == "SUPER_ADMIN", AdminUser.status == "APPROVED")
    )
    super_admin = super_admin_res.scalars().first()
    has_super = super_admin is not None
    email_hint = None
    if has_super and super_admin.email:
        parts = super_admin.email.split("@")
        masked_user = parts[0][:2] + "***" if len(parts[0]) > 2 else "***"
        domain = parts[1] if len(parts) > 1 else ""
        email_hint = f"{masked_user}@{domain}"

    return {
        "has_super_admin": has_super,
        "super_admin_email_hint": email_hint,
    }


@router.post("/login")
async def admin_login(payload: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Sign in to an Admin role (separately handled for Lead Admin vs User Admin):
    - Lead Admin: Authenticates against primary Lead Admin credentials in admin_users.
    - User Admin: Authenticates with User Portal credentials. Requires prior one-time approval by Lead Admin.
    """
    email = payload.email.strip().lower()
    password = payload.password.strip()
    role_type = (payload.role_type or "ANY").upper()

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required.",
        )

    # ── CASE 1: LEAD ADMIN LOGIN ──
    if role_type == "LEAD_ADMIN":
        admin_res = await db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email))
        admin = admin_res.scalars().first()

        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Lead Admin email or password.",
            )

        if admin.role != "SUPER_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account is registered as a User Admin. Please use the User Admin tab to sign in.",
            )

        if not verify_password(password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Lead Admin email or password.",
            )

        admin.last_login_at = datetime.utcnow()
        await db.commit()

        token = create_admin_token(str(admin.id), admin.email, admin.role)
        return {
            "token": token,
            "role": "SUPER_ADMIN",
            "email": admin.email,
            "full_name": admin.full_name,
        }

    # ── CASE 2: USER ADMIN LOGIN (uses same credentials as User Portal) ──
    elif role_type == "USER_ADMIN":
        # Look up User Portal account
        user_res = await db.execute(select(User).where(func.lower(User.email) == email))
        user = user_res.scalars().first()

        # Look up AdminUser record
        admin_res = await db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email))
        admin = admin_res.scalars().first()

        if admin and admin.role == "SUPER_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account is registered as the Lead Admin. Please use the Lead Admin tab to sign in.",
            )

        if not user and not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No account found with this email. Please register on the User Portal or request User Admin access.",
            )

        # Check credentials against User Portal password or Admin password
        user_pw_valid = user and user.password_hash and verify_password(password, user.password_hash)
        admin_pw_valid = admin and admin.password_hash and verify_password(password, admin.password_hash)

        if not user_pw_valid and not admin_pw_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password. Please use your User Portal account password or use 'Forgot password?'.",
            )

        # Check if user has requested User Admin access
        if not admin or admin.role != "SECONDARY_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have not requested User Admin access yet. Please click 'Request User Admin Access' and provide your reason for approval.",
            )

        # Check approval status
        if admin.status == "PENDING":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your User Admin access request is currently PENDING approval by the Lead Admin. You will be able to log in once approved.",
            )
        if admin.status == "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your User Admin access request was not approved by the Lead Admin.",
            )

        # Approved User Admin: sync linked user and password hash if needed
        if user:
            if not admin.linked_user_id:
                admin.linked_user_id = user.id
            if user_pw_valid and admin.password_hash != user.password_hash:
                admin.password_hash = user.password_hash
            elif admin_pw_valid and user.password_hash != admin.password_hash:
                user.password_hash = admin.password_hash

        admin.last_login_at = datetime.utcnow()
        await db.commit()

        token = create_admin_token(str(admin.id), admin.email, admin.role)
        return {
            "token": token,
            "role": "SECONDARY_ADMIN",
            "email": admin.email,
            "full_name": admin.full_name,
        }

    # ── CASE 3: ANY (Automatic detection) ──
    else:
        admin_res = await db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email))
        admin = admin_res.scalars().first()

        user_res = await db.execute(select(User).where(func.lower(User.email) == email))
        user = user_res.scalars().first()

        pw_ok = False
        if admin and verify_password(password, admin.password_hash):
            pw_ok = True
        elif user and user.password_hash and verify_password(password, user.password_hash):
            pw_ok = True
            if admin:
                admin.password_hash = user.password_hash

        if not admin or not pw_ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if admin.status == "PENDING":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your admin access request is currently PENDING approval by the Lead Admin.",
            )
        if admin.status == "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your admin access request was not approved by the Lead Admin.",
            )

        admin.last_login_at = datetime.utcnow()
        await db.commit()

        token = create_admin_token(str(admin.id), admin.email, admin.role)
        return {
            "token": token,
            "role": admin.role,
            "email": admin.email,
            "full_name": admin.full_name,
        }


@router.post("/register")
async def admin_register(payload: AdminRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register an Admin account (separately handled for Lead Admin vs User Admin):
    - Lead Admin: Initial system setup only. Instant APPROVED status.
    - User Admin: Uses User Portal credentials. Requires reason and Lead Admin approval for first login.
    """
    email = payload.email.strip().lower()
    full_name = payload.full_name.strip()
    password = payload.password.strip()
    role_type = (payload.role_type or "USER_ADMIN").upper()

    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long.",
        )

    # Check if a Lead Admin currently exists
    super_admin_res = await db.execute(
        select(AdminUser).where(AdminUser.role == "SUPER_ADMIN", AdminUser.status == "APPROVED")
    )
    existing_super_admin = super_admin_res.scalars().first()

    # ── REGISTER AS LEAD ADMIN ──
    if role_type == "LEAD_ADMIN":
        if existing_super_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A Lead Admin has already been registered for this system. Only one Lead Admin is permitted.",
            )

        user_res = await db.execute(select(User).where(func.lower(User.email) == email))
        user = user_res.scalars().first()
        linked_user_id = user.id if user else None

        new_admin = AdminUser(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role="SUPER_ADMIN",
            status="APPROVED",
            request_note="Primary Lead Admin (Initial Setup)",
            approved_by="System (Initial Lead Admin Setup)",
            approved_at=datetime.utcnow(),
            linked_user_id=linked_user_id,
        )
        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)

        return {
            "status": "APPROVED",
            "role": "SUPER_ADMIN",
            "message": "Lead Admin account successfully registered and activated! You can now sign in.",
        }

    # ── REGISTER AS USER ADMIN ──
    else:
        if not existing_super_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Initial setup required: The Lead Admin must be registered before User Admins can request access.",
            )

        reason = (payload.request_note or "").strip()
        if len(reason) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a valid reason for requesting User Admin access.",
            )

        # Check existing admin account
        existing_res = await db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email))
        existing = existing_res.scalars().first()

        if existing:
            if existing.role == "SUPER_ADMIN":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This email belongs to the Lead Admin. Please sign in via the Lead Admin tab.",
                )
            if existing.status == "PENDING":
                return {
                    "status": "PENDING",
                    "role": "SECONDARY_ADMIN",
                    "message": "Your User Admin request is already submitted and pending approval by the Lead Admin.",
                }
            if existing.status == "APPROVED":
                return {
                    "status": "APPROVED",
                    "role": "SECONDARY_ADMIN",
                    "message": "Your User Admin account is already approved! Please sign in using your User Portal credentials.",
                }
            if existing.status == "REJECTED":
                # Re-submit request with updated reason
                existing.status = "PENDING"
                existing.request_note = reason
                existing.password_hash = hash_password(password)
                existing.updated_at = datetime.utcnow()
                await db.commit()

                try:
                    await notify_super_admin_of_registration(
                        applicant_name=full_name,
                        applicant_email=email,
                        super_admin_email=existing_super_admin.email,
                        request_note=reason,
                    )
                except Exception as e:
                    logger.warning("[ADMIN] Failed to trigger notification email: %s", e)

                return {
                    "status": "PENDING",
                    "role": "SECONDARY_ADMIN",
                    "message": "Your updated User Admin request has been submitted to the Lead Admin for approval.",
                }

        # Link or create corresponding User Portal account
        user_res = await db.execute(select(User).where(func.lower(User.email) == email))
        user = user_res.scalars().first()
        if not user:
            user = User(
                email=email,
                password_hash=hash_password(password),
                full_name=full_name,
            )
            db.add(user)
            await db.flush()
        elif not user.password_hash:
            user.password_hash = hash_password(password)
        else:
            # User exists in User Portal: verify their existing User Portal password
            if not verify_password(password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="The password entered does not match your existing User Portal password. User Admin uses the same credentials as your User Portal account.",
                )

        new_admin = AdminUser(
            email=email,
            password_hash=user.password_hash,
            full_name=full_name,
            role="SECONDARY_ADMIN",
            status="PENDING",
            request_note=reason,
            linked_user_id=user.id,
        )
        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)

        try:
            await notify_super_admin_of_registration(
                applicant_name=full_name,
                applicant_email=email,
                super_admin_email=existing_super_admin.email,
                request_note=reason,
            )
        except Exception as e:
            logger.warning("[ADMIN] Failed to trigger notification email: %s", e)

        return {
            "status": "PENDING",
            "role": "SECONDARY_ADMIN",
            "message": (
                "User Admin request submitted successfully! A notification email has been dispatched "
                "to the Lead Admin for approval. Once approved, you can log in using your User Portal credentials."
            ),
        }


@router.post("/forgot-password")
async def admin_forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Request a password reset verification code sent to the admin's registered email.
    Supports both Lead Admin (Super Admin) and User Admins.
    """
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is required.",
        )

    admin_res = await db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email))
    admin = admin_res.scalars().first()

    if not admin:
        # Generic security response
        return {
            "success": True,
            "message": "If this email is registered, a 6-digit verification code has been sent.",
        }

    if admin.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is currently not active or approved.",
        )

    # Generate 6-digit verification code
    code = generate_verification_code()
    admin.reset_code = code
    admin.reset_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db.commit()

    # Send verification email
    try:
        await send_password_reset_email(
            to_email=admin.email,
            verification_code=code,
            recipient_name=admin.full_name,
        )
    except Exception as e:
        logger.warning("[ADMIN] Error sending password reset email: %s", e)

    return {
        "success": True,
        "message": "A 6-digit verification code has been sent to your registered email.",
    }


@router.post("/reset-password")
async def admin_reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Verify the 6-digit code and update the admin's password.
    Supports both Lead Admin (Super Admin) and User Admins.
    """
    email = payload.email.strip().lower()
    code = payload.verification_code.strip()
    new_password = payload.new_password.strip()

    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters long.",
        )

    admin_res = await db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email))
    admin = admin_res.scalars().first()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or verification code.",
        )

    if not admin.reset_code or admin.reset_code.strip() != code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please check your email and try again.",
        )

    now = datetime.now(timezone.utc)
    expires = admin.reset_code_expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if not expires or now > expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code has expired (valid for 15 minutes). Please request a new one.",
        )

    # Update password and clear reset code
    admin.password_hash = hash_password(new_password)
    admin.reset_code = None
    admin.reset_code_expires_at = None
    admin.updated_at = datetime.now(timezone.utc)

    # If linked to a User account (or User Admin role), synchronize User Portal password
    if admin.linked_user_id:
        user_res = await db.execute(select(User).where(User.id == admin.linked_user_id))
        linked_u = user_res.scalars().first()
        if linked_u:
            linked_u.password_hash = admin.password_hash
            linked_u.updated_at = datetime.now(timezone.utc)
    else:
        user_res = await db.execute(select(User).where(func.lower(User.email) == email))
        linked_u = user_res.scalars().first()
        if linked_u:
            linked_u.password_hash = admin.password_hash
            linked_u.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "success": True,
        "message": "Password successfully updated! You can now log in with your new password.",
    }


@router.get("/me")
async def get_admin_profile(current_admin: AdminUser = Depends(get_current_admin)):
    return {
        "id": str(current_admin.id),
        "email": current_admin.email,
        "full_name": current_admin.full_name,
        "role": current_admin.role,
        "status": current_admin.status,
    }


# ─────────────────────────────────────────────────────────────
# LEAD ADMIN (SUPER ADMIN) ONLY: Technical Telemetry & Approvals
# ─────────────────────────────────────────────────────────────
@router.get("/metrics")
async def get_technical_metrics(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns technical telemetry: latency, token usage, cache hit/miss, API called,
    and logged-in user email list.
    STRICT PRIVACY: Does NOT include query text or answer content of any user.
    """
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to Lead Admin.",
        )

    # Aggregate telemetry statistics
    total_queries_res = await db.execute(select(func.count(QueryTelemetry.id)))
    total_queries = total_queries_res.scalar() or 0

    avg_latency_res = await db.execute(select(func.avg(QueryTelemetry.latency_ms)))
    avg_latency = float(avg_latency_res.scalar() or 0.0)

    total_tokens_res = await db.execute(
        select(
            func.sum(QueryTelemetry.total_tokens),
            func.sum(QueryTelemetry.prompt_tokens),
            func.sum(QueryTelemetry.completion_tokens),
        )
    )
    tok_row = total_tokens_res.first()
    total_tokens = tok_row[0] or 0
    prompt_tokens = tok_row[1] or 0
    completion_tokens = tok_row[2] or 0

    cache_hit_res = await db.execute(
        select(func.count(QueryTelemetry.id)).where(QueryTelemetry.cache_hit.is_(True))
    )
    cache_hits = cache_hit_res.scalar() or 0

    api_called_res = await db.execute(
        select(func.count(QueryTelemetry.id)).where(QueryTelemetry.api_called.is_(True))
    )
    api_calls = api_called_res.scalar() or 0

    cache_misses = max(total_queries - cache_hits, 0)
    cache_hit_ratio = round((cache_hits / total_queries * 100), 1) if total_queries > 0 else 0.0

    # Logged-in user accounts list with activity summary
    users_stmt = (
        select(
            User.email,
            User.created_at,
            func.count(QueryTelemetry.id).label("query_count"),
            func.max(QueryTelemetry.created_at).label("last_activity"),
        )
        .outerjoin(QueryTelemetry, User.id == QueryTelemetry.user_id)
        .group_by(User.id, User.email, User.created_at)
        .order_by(desc("last_activity"))
    )
    users_res = await db.execute(users_stmt)
    logged_in_users = [
        {
            "email": row[0],
            "first_joined": row[1].strftime("%Y-%m-%d %H:%M") if row[1] else "-",
            "queries_executed": row[2],
            "last_active": row[3].strftime("%Y-%m-%d %H:%M:%S") if row[3] else "Never",
        }
        for row in users_res
    ]

    # Recent technical logs (strictly metadata: NO query text or answers)
    logs_stmt = (
        select(
            QueryTelemetry.id,
            QueryTelemetry.user_email,
            QueryTelemetry.latency_ms,
            QueryTelemetry.prompt_tokens,
            QueryTelemetry.completion_tokens,
            QueryTelemetry.total_tokens,
            QueryTelemetry.cache_hit,
            QueryTelemetry.api_called,
            QueryTelemetry.intent,
            QueryTelemetry.created_at,
        )
        .order_by(QueryTelemetry.created_at.desc())
        .limit(50)
    )
    logs_res = await db.execute(logs_stmt)
    telemetry_logs = [
        {
            "id": str(row[0]),
            "user_email": row[1] or "Anonymous User",
            "latency_ms": round(row[2], 1),
            "prompt_tokens": row[3],
            "completion_tokens": row[4],
            "total_tokens": row[5],
            "cache_hit": row[6],
            "api_called": row[7],
            "intent": row[8] or "general",
            "timestamp": row[9].strftime("%Y-%m-%d %H:%M:%S") if row[9] else "-",
            "privacy_status": "Zero-Knowledge: Query content redacted",
        }
        for row in logs_res
    ]

    return {
        "kpis": {
            "total_queries": total_queries,
            "avg_latency_ms": round(avg_latency, 1),
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_ratio": cache_hit_ratio,
            "api_calls": api_calls,
            "cache_served": cache_hits,
        },
        "logged_in_users": logged_in_users,
        "telemetry_logs": telemetry_logs,
    }


@router.get("/pending-requests")
async def get_pending_admin_requests(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to Super Admin.",
        )

    res = await db.execute(
        select(AdminUser)
        .where(AdminUser.role == "SECONDARY_ADMIN")
        .order_by(AdminUser.created_at.desc())
    )
    requests = res.scalars().all()
    return {
        "requests": [
            {
                "id": str(req.id),
                "email": req.email,
                "full_name": req.full_name,
                "status": req.status,
                "request_note": req.request_note,
                "created_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req.created_at else "-",
                "approved_by": req.approved_by,
                "approved_at": req.approved_at.strftime("%Y-%m-%d %H:%M:%S") if req.approved_at else None,
            }
            for req in requests
        ]
    }


@router.post("/handle-request")
async def handle_admin_request(
    payload: AdminApprovalActionRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to Super Admin.",
        )

    action = payload.action.upper()
    if action not in ("APPROVE", "REJECT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be APPROVE or REJECT.",
        )

    target_res = await db.execute(
        select(AdminUser).where(AdminUser.id == uuid.UUID(payload.admin_id))
    )
    target = target_res.scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="Admin request not found.")

    if target.role == "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The Lead Admin (Super Admin) account cannot be modified or rejected. It can only be deleted by truncating the admin_users table in the database.",
        )

    new_status = "APPROVED" if action == "APPROVE" else "REJECTED"
    target.status = new_status
    target.approved_by = current_admin.email
    target.approved_at = datetime.utcnow()
    await db.commit()

    # Notify applicant via email
    try:
        await notify_applicant_of_status(
            applicant_name=target.full_name,
            applicant_email=target.email,
            status=new_status,
        )
    except Exception as e:
        logger.warning("[ADMIN] Failed to dispatch status notification email: %s", e)

    return {
        "success": True,
        "status": new_status,
        "message": f"User Admin request for {target.email} has been {new_status.lower()}.",
    }


# ─────────────────────────────────────────────────────────────
# USER ADMIN ONLY: User Activity & Document Audits
# ─────────────────────────────────────────────────────────────
@router.get("/user-audit")
async def get_user_activity_audit(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    For User Admins (approved users):
    Shows ONLY queries asked, files referenced, files analyzed, and file name from which system responds.
    Strictly isolated per user — cannot view other users' private queries or Lead Admin technical telemetry.
    """
    # Scope to their linked user account or matching email
    user_id_clause = None
    if current_admin.linked_user_id:
        user_id_clause = ChatQuery.user_id == current_admin.linked_user_id
    else:
        # Match by email in User table
        user_res = await db.execute(
            select(User.id).where(func.lower(User.email) == current_admin.email.lower())
        )
        matched_uid = user_res.scalar()
        if matched_uid:
            user_id_clause = ChatQuery.user_id == matched_uid

    # If no linked account yet, return empty list gracefully
    if user_id_clause is None:
        return {
            "audits": [],
            "message": "No query history found for your account yet. Queries you ask will appear here.",
        }

    stmt = (
        select(ChatQuery)
        .where(user_id_clause)
        .order_by(ChatQuery.created_at.desc())
        .limit(100)
    )
    res = await db.execute(stmt)
    queries = res.scalars().all()

    audit_records = []
    for q in queries:
        files_analyzed = q.identified_files or []
        files_referenced = q.source_file_names or []
        responding_file = (
            q.responding_file_name
            or (files_referenced[0] if files_referenced else None)
            or (files_analyzed[0] if files_analyzed else "General Knowledge / Knowledge Base")
        )
        answer_snippet = (q.answer_text[:140] + "...") if q.answer_text and len(q.answer_text) > 140 else (q.answer_text or "")

        audit_records.append({
            "id": str(q.id),
            "query_asked": q.query_text,
            "files_analyzed": files_analyzed,
            "files_referenced": files_referenced,
            "responding_file_name": responding_file,
            "answer_snippet": answer_snippet,
            "timestamp": q.created_at.strftime("%Y-%m-%d %H:%M:%S") if q.created_at else "-",
        })

    return {"audits": audit_records}
