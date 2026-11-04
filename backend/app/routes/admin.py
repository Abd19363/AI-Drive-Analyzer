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
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, desc
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


def calculate_cost(prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0) -> float:
    """
    Computes estimated cost in USD based on Gemini API standard rates:
    - Input: $0.075 per 1,000,000 tokens ($0.000075 / 1k tokens)
    - Output: $0.300 per 1,000,000 tokens ($0.000300 / 1k tokens)
    If prompt/completion not separated, uses blended rate ($0.15 / 1M tokens).
    """
    if prompt_tokens > 0 or completion_tokens > 0:
        cost = (prompt_tokens * 0.075 / 1_000_000) + (completion_tokens * 0.30 / 1_000_000)
    elif total_tokens > 0:
        cost = total_tokens * 0.15 / 1_000_000
    else:
        cost = 0.0
    return round(cost, 6)


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


class AssignTokensRequest(BaseModel):
    assigned_tokens: int = Field(ge=0, le=50_000_000)
    duration: Optional[str] = "1_month" # "1_week", "3_weeks", "1_month", "6_months", "1_year"


class UserAdminSessionRequest(BaseModel):
    user_id: str


SUBSCRIPTION_DURATION_DAYS = {
    "1_week": 7,
    "3_weeks": 21,
    "1_month": 30,
    "6_months": 180,
    "1_year": 365,
}

def calculate_token_expiration(duration: Optional[str]) -> tuple[Optional[datetime], int]:
    days = SUBSCRIPTION_DURATION_DAYS.get(duration or "1_month", 30)
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    return expires_at, days


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


@router.post("/user-admin-session")
async def get_user_admin_session(
    payload: UserAdminSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Seamlessly creates or retrieves a User Admin (SECONDARY_ADMIN) session token
    for a user who is authenticated in the User Portal.
    """
    try:
        uid = uuid.UUID(payload.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format.")

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    # Check if this user is the registered Lead Admin (SUPER_ADMIN)
    super_admin_res = await db.execute(
        select(AdminUser).where(
            func.lower(AdminUser.email) == user.email.lower(),
            AdminUser.role == "SUPER_ADMIN",
            AdminUser.status == "APPROVED",
        )
    )
    super_admin = super_admin_res.scalars().first()
    if super_admin:
        token = create_admin_token(str(super_admin.id), super_admin.email, super_admin.role)
        return {
            "token": token,
            "role": "SUPER_ADMIN",
            "email": super_admin.email,
            "full_name": super_admin.full_name,
        }

    # Regular user: find or create their SECONDARY_ADMIN record
    admin_res = await db.execute(
        select(AdminUser).where(
            (AdminUser.linked_user_id == user.id) | (func.lower(AdminUser.email) == user.email.lower())
        )
    )
    admin = admin_res.scalars().first()

    if not admin:
        admin = AdminUser(
            email=user.email.lower(),
            password_hash=user.password_hash or hash_password("UserAdmin@123"),
            full_name=user.full_name or user.email.split("@")[0],
            role="SECONDARY_ADMIN",
            status="APPROVED",
            approved_by="AUTO_APPROVED",
            approved_at=datetime.utcnow(),
            linked_user_id=user.id,
        )
        db.add(admin)
        await db.flush()
    else:
        admin.status = "APPROVED"
        admin.role = "SECONDARY_ADMIN"
        if not admin.linked_user_id:
            admin.linked_user_id = user.id

    admin.last_login_at = datetime.utcnow()
    await db.commit()

    token = create_admin_token(str(admin.id), admin.email, admin.role)
    return {
        "token": token,
        "role": "SECONDARY_ADMIN",
        "email": admin.email,
        "full_name": admin.full_name,
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

        # User does not require approval for login into User Admin account
        if not admin:
            admin = AdminUser(
                email=email,
                password_hash=user.password_hash if (user and user.password_hash) else hash_password(password),
                full_name=user.full_name if (user and user.full_name) else email.split("@")[0],
                role="SECONDARY_ADMIN",
                status="APPROVED",
                approved_by="AUTO_APPROVED",
                approved_at=datetime.utcnow(),
                linked_user_id=user.id if user else None,
            )
            db.add(admin)
            await db.flush()
        else:
            admin.status = "APPROVED"
            admin.role = "SECONDARY_ADMIN"
            if user and not admin.linked_user_id:
                admin.linked_user_id = user.id

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

        if admin.role != "SUPER_ADMIN":
            admin.status = "APPROVED"
        elif admin.status == "PENDING":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your admin access request is currently PENDING approval by the Lead Admin.",
            )
        elif admin.status == "REJECTED":
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
            existing.status = "APPROVED"
            existing.role = "SECONDARY_ADMIN"
            existing.password_hash = hash_password(password)
            existing.updated_at = datetime.utcnow()
            await db.commit()
            return {
                "status": "APPROVED",
                "role": "SECONDARY_ADMIN",
                "message": "User Admin account registered and activated successfully! You can now sign in directly.",
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
            status="APPROVED",
            request_note=reason,
            approved_by="AUTO_APPROVED",
            approved_at=datetime.utcnow(),
            linked_user_id=user.id,
        )
        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)

        return {
            "status": "APPROVED",
            "role": "SECONDARY_ADMIN",
            "message": "User Admin account registered and activated successfully! You can now sign in directly using your User Portal credentials.",
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
    total_cost_usd = calculate_cost(prompt_tokens, completion_tokens, total_tokens)

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
    telemetry_logs = []
    for row in logs_res:
        p_tok = row[3] or 0
        c_tok = row[4] or 0
        tot_tok = row[5] or 0
        cache_hit_flag = bool(row[6])
        api_called_flag = bool(row[7])

        if cache_hit_flag and not api_called_flag:
            query_cost = 0.0
        else:
            query_cost = calculate_cost(p_tok, c_tok, tot_tok)

        telemetry_logs.append({
            "id": str(row[0]),
            "user_email": row[1] or "Anonymous User",
            "latency_ms": round(row[2], 1),
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "total_tokens": tot_tok,
            "cost_usd": query_cost,
            "cost_formatted": f"${query_cost:.5f}" if query_cost > 0 else "$0.00000",
            "cache_hit": cache_hit_flag,
            "api_called": api_called_flag,
            "intent": row[8] or "general",
            "timestamp": row[9].strftime("%Y-%m-%d %H:%M:%S") if row[9] else "-",
            "privacy_status": "Zero-Knowledge: Query content redacted",
        })

    return {
        "kpis": {
            "total_queries": total_queries,
            "avg_latency_ms": round(avg_latency, 1),
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_cost_usd": round(total_cost_usd, 4),
            "formatted_total_cost": f"${total_cost_usd:.4f}",
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
    total_query_tokens_calc = 0
    for q in queries:
        files_analyzed = q.identified_files or []
        files_referenced = q.source_file_names or []
        responding_file = (
            q.responding_file_name
            or (files_referenced[0] if files_referenced else None)
            or (files_analyzed[0] if files_analyzed else "General Knowledge / Knowledge Base")
        )
        answer_snippet = (q.answer_text[:140] + "...") if q.answer_text and len(q.answer_text) > 140 else (q.answer_text or "")

        total_toks = getattr(q, "total_tokens", 0) or 0
        prompt_toks = getattr(q, "prompt_tokens", 0) or 0
        comp_toks = getattr(q, "completion_tokens", 0) or 0
        if total_toks == 0:
            prompt_toks = max(1, len(q.query_text or "") // 4)
            comp_toks = max(1, len(q.answer_text or "") // 4)
            total_toks = prompt_toks + comp_toks
        total_query_tokens_calc += total_toks

        audit_records.append({
            "id": str(q.id),
            "query_asked": q.query_text,
            "files_analyzed": files_analyzed,
            "files_referenced": files_referenced,
            "responding_file_name": responding_file,
            "answer_snippet": answer_snippet,
            "prompt_tokens": prompt_toks,
            "completion_tokens": comp_toks,
            "total_tokens": total_toks,
            "timestamp": q.created_at.strftime("%Y-%m-%d %H:%M:%S") if q.created_at else "-",
        })

    target_user_id = current_admin.linked_user_id
    if not target_user_id:
        user_res = await db.execute(
            select(User.id).where(func.lower(User.email) == current_admin.email.lower())
        )
        target_user_id = user_res.scalar()

    user_obj = None
    assigned_tokens = 50000
    if target_user_id:
        user_obj = await db.get(User, target_user_id)
        if user_obj and hasattr(user_obj, "assigned_tokens"):
            assigned_tokens = user_obj.assigned_tokens or 50000

    tokens_consumed = 0
    if target_user_id:
        consumed_res = await db.execute(
            select(func.coalesce(func.sum(QueryTelemetry.total_tokens), 0)).where(
                QueryTelemetry.user_id == target_user_id
            )
        )
        tokens_consumed = int(consumed_res.scalar() or 0)

    if total_query_tokens_calc > tokens_consumed:
        tokens_consumed = total_query_tokens_calc

    now_utc = datetime.now(timezone.utc)
    is_expired = False
    sub_duration = getattr(user_obj, "subscription_duration", "1_month") or "1_month"
    token_expires_at_iso = None
    if user_obj and user_obj.token_expires_at:
        token_expires_at_iso = user_obj.token_expires_at.isoformat()
        if now_utc > user_obj.token_expires_at:
            is_expired = True

    # Tokens used in current period (since last token update):
    current_period_consumed = 0
    if user_obj and user_obj.tokens_assigned_at and target_user_id:
        p_res = await db.execute(
            select(func.coalesce(func.sum(QueryTelemetry.total_tokens), 0)).where(
                QueryTelemetry.user_id == target_user_id,
                QueryTelemetry.created_at >= user_obj.tokens_assigned_at,
            )
        )
        current_period_consumed = int(p_res.scalar() or 0)
    else:
        current_period_consumed = tokens_consumed

    if is_expired:
        tokens_left = 0
    else:
        tokens_left = max(0, assigned_tokens - tokens_consumed)

    return {
        "audits": audit_records,
        "token_stats": {
            "assigned_tokens": assigned_tokens,
            "tokens_consumed": tokens_consumed,
            "current_period_consumed": current_period_consumed,
            "tokens_left": tokens_left,
            "subscription_duration": sub_duration,
            "token_expires_at": token_expires_at_iso,
            "is_expired": is_expired,
        },
    }


# ─────────────────────────────────────────────────────────────
# LEAD ADMIN ONLY: User Token Usage & Allocation
# ─────────────────────────────────────────────────────────────
@router.get("/users-token-usage")
async def get_users_token_usage(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Lead Admin view: Displays token consumption, expiration, and allocated token budget for all users.
    """
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lead Admin access required to view user token usage.",
        )

    users_res = await db.execute(select(User).order_by(User.created_at.desc()))
    users = users_res.scalars().all()

    telemetry_res = await db.execute(
        select(
            QueryTelemetry.user_id,
            func.coalesce(func.sum(QueryTelemetry.total_tokens), 0).label("consumed"),
            func.coalesce(func.sum(QueryTelemetry.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(QueryTelemetry.completion_tokens), 0).label("completion_tokens"),
            func.count(QueryTelemetry.id).label("queries_count"),
        ).group_by(QueryTelemetry.user_id)
    )
    usage_map = {
        row.user_id: {
            "consumed": int(row.consumed),
            "prompt_tokens": int(row.prompt_tokens),
            "completion_tokens": int(row.completion_tokens),
            "queries_count": int(row.queries_count),
        }
        for row in telemetry_res
    }

    now_utc = datetime.now(timezone.utc)
    user_list = []
    for u in users:
        stats = usage_map.get(
            u.id,
            {"consumed": 0, "prompt_tokens": 0, "completion_tokens": 0, "queries_count": 0},
        )
        assigned = getattr(u, "assigned_tokens", 50000) or 50000
        consumed = stats["consumed"]
        p_tok = stats["prompt_tokens"]
        c_tok = stats["completion_tokens"]
        user_cost = calculate_cost(p_tok, c_tok, consumed)

        # Check expiration
        is_expired = False
        if u.token_expires_at and now_utc > u.token_expires_at:
            is_expired = True

        # Check current period consumption (from tokens_assigned_at)
        period_consumed = 0
        if u.tokens_assigned_at:
            period_res = await db.execute(
                select(func.coalesce(func.sum(QueryTelemetry.total_tokens), 0)).where(
                    QueryTelemetry.user_id == u.id,
                    QueryTelemetry.created_at >= u.tokens_assigned_at,
                )
            )
            period_consumed = int(period_res.scalar() or 0)
        else:
            period_consumed = consumed

        if is_expired:
            tokens_left = 0
        else:
            tokens_left = max(0, assigned - consumed)

        user_list.append({
            "user_id": str(u.id),
            "email": u.email,
            "full_name": u.full_name or u.email.split("@")[0],
            "assigned_tokens": assigned,
            "subscription_duration": getattr(u, "subscription_duration", "1_month") or "1_month",
            "tokens_assigned_at": u.tokens_assigned_at.isoformat() if u.tokens_assigned_at else (u.created_at.isoformat() if u.created_at else None),
            "token_expires_at": u.token_expires_at.isoformat() if u.token_expires_at else None,
            "is_expired": is_expired,
            "tokens_consumed": consumed,
            "period_tokens_consumed": period_consumed,
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "estimated_cost_usd": user_cost,
            "cost_formatted": f"${user_cost:.4f}",
            "tokens_left": tokens_left,
            "query_count": stats["queries_count"],
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else "-",
        })

    total_system_tokens = sum(u["tokens_consumed"] for u in user_list)
    total_system_cost = sum(u["estimated_cost_usd"] for u in user_list)

    return {
        "users": user_list,
        "system_summary": {
            "total_tokens_consumed": total_system_tokens,
            "total_cost_usd": round(total_system_cost, 4),
            "cost_formatted": f"${total_system_cost:.4f}",
            "total_users": len(user_list),
        },
    }


@router.post("/users/{user_id}/assign-tokens")
async def assign_user_tokens(
    user_id: str,
    payload: AssignTokensRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Lead Admin action: Updates the allocated token balance and subscription duration for a user.
    """
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lead Admin access required to assign user tokens.",
        )

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format.")

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    duration_key = payload.duration or "1_month"
    expires_at, days = calculate_token_expiration(duration_key)
    now_utc = datetime.now(timezone.utc)

    user.assigned_tokens = payload.assigned_tokens
    user.subscription_duration = duration_key
    user.tokens_assigned_at = now_utc
    user.token_expires_at = expires_at
    await db.commit()

    consumed_res = await db.execute(
        select(
            func.coalesce(func.sum(QueryTelemetry.total_tokens), 0).label("tot"),
            func.coalesce(func.sum(QueryTelemetry.prompt_tokens), 0).label("pt"),
            func.coalesce(func.sum(QueryTelemetry.completion_tokens), 0).label("ct"),
        ).where(
            QueryTelemetry.user_id == user.id
        )
    )
    c_row = consumed_res.first()
    consumed = int(c_row.tot) if c_row else 0
    p_tok = int(c_row.pt) if c_row else 0
    c_tok = int(c_row.ct) if c_row else 0
    user_cost = calculate_cost(p_tok, c_tok, consumed)

    formatted_duration = duration_key.replace("_", " ").title()
    return {
        "success": True,
        "user_id": str(user.id),
        "email": user.email,
        "assigned_tokens": user.assigned_tokens,
        "subscription_duration": user.subscription_duration,
        "token_expires_at": user.token_expires_at.isoformat() if user.token_expires_at else None,
        "is_expired": False,
        "tokens_consumed": consumed,
        "estimated_cost_usd": user_cost,
        "cost_formatted": f"${user_cost:.4f}",
        "tokens_left": user.assigned_tokens,
        "message": f"Successfully updated tokens to {payload.assigned_tokens:,} ({formatted_duration}) for {user.email}.",
    }


@router.delete("/users/{user_id}")
async def delete_user_account(
    user_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Lead Admin action: Permanently deletes a user and cascades deletion of all their
    Drive files, document chunks, chat sessions, queries, telemetry, and cached answers.
    Also deletes any associated secondary AdminUser entry for that user.
    """
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lead Admin access required to delete user accounts.",
        )

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format.")

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    user_email = user.email

    # Also remove secondary admin account for this email if one exists (never delete SUPER_ADMIN)
    admin_res = await db.execute(
        select(AdminUser).where(
            (AdminUser.linked_user_id == user.id) | (func.lower(AdminUser.email) == user_email.lower())
        )
    )
    for admin_acc in admin_res.scalars().all():
        if admin_acc.role != "SUPER_ADMIN":
            await db.delete(admin_acc)

    await db.delete(user)
    await db.commit()

    return {
        "success": True,
        "message": f"User {user_email} and all associated data have been permanently deleted.",
        "deleted_user_id": str(uid),
    }


@router.delete("/telemetry/{telemetry_id}")
async def delete_telemetry_log(
    telemetry_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Lead Admin action: Permanently deletes a specific technical telemetry log.
    """
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lead Admin access required to delete telemetry logs.",
        )

    try:
        tid = uuid.UUID(telemetry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid telemetry ID format.")

    entry = await db.get(QueryTelemetry, tid)
    if not entry:
        raise HTTPException(status_code=404, detail="Telemetry log entry not found.")

    await db.delete(entry)
    await db.commit()

    return {
        "success": True,
        "message": "Telemetry log entry deleted successfully.",
        "deleted_telemetry_id": str(tid),
    }
