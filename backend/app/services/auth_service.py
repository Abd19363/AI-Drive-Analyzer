import os
import datetime
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import google.oauth2.credentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.config import settings
from app.models import User, GoogleAccount

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

def get_google_flow(state: str = None):
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=settings.GOOGLE_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
        autogenerate_code_verifier=False,
        state=state
    )
    return flow

def generate_authorization_url(state: str = None):
    flow = get_google_flow(state=state)
    auth_url, flow_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent select_account",
        state=state
    )
    return auth_url, flow_state

async def handle_oauth_callback(code: str, db: AsyncSession, state: str = None):
    flow = get_google_flow(state=state)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Get user profile information from Google
    user_info_service = build("oauth2", "v2", credentials=credentials)
    user_info = user_info_service.userinfo().get().execute()

    email = user_info.get("email")
    google_id = user_info.get("id")

    if not email:
        raise ValueError("Could not retrieve email from Google Account.")

    # Link to authenticated user if state is a user_id
    target_user = None
    if state:
        try:
            import uuid as uuid_pkg
            uid = uuid_pkg.UUID(state)
            state_user_res = await db.execute(select(User).where(User.id == uid))
            target_user = state_user_res.scalars().first()
        except Exception:
            pass

    if not target_user:
        # Find or create User by email
        result = await db.execute(select(User).where(User.email == email))
        target_user = result.scalars().first()

    if not target_user:
        target_user = User(email=email)
        db.add(target_user)
        await db.flush()

    user = target_user

    # Find or update GoogleAccount
    acc_result = await db.execute(
        select(GoogleAccount).where(GoogleAccount.user_id == user.id, GoogleAccount.google_user_id == google_id)
    )
    google_acc = acc_result.scalars().first()

    expires_at = None
    if credentials.expiry:
        expires_at = credentials.expiry

    if not google_acc:
        google_acc = GoogleAccount(
            user_id=user.id,
            google_user_id=google_id,
            email=email,
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri or "https://oauth2.googleapis.com/token",
            scopes=credentials.scopes or settings.GOOGLE_SCOPES,
            expires_at=expires_at
        )
        db.add(google_acc)
    else:
        google_acc.access_token = credentials.token
        if credentials.refresh_token:
            google_acc.refresh_token = credentials.refresh_token
        google_acc.expires_at = expires_at

    await db.commit()
    await db.refresh(user)
    return user
