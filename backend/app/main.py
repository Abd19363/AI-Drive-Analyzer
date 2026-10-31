import os
import warnings

# Suppress pypdf's fontTools notice — fonttools IS installed; this warning is informational noise.
warnings.filterwarnings(
    "ignore",
    message=".*fontTools.*required to fully parse the encoding of a CFF Type1 font.*",
    category=UserWarning,
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Enable OAuth2 over HTTP for local development
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

import asyncio
import logging
from contextlib import asynccontextmanager

from app.config import settings
from app.db import engine, Base, AsyncSessionLocal
from app.models import AdminUser
from app.routes import auth, drive, guardrails, rag, admin
from app.routes.admin import hash_password
from app.services.embedding_service import get_embedding_model
from sqlalchemy import select, text

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables (including admin_users and query_telemetry)
    try:
        logger.info("[Startup] Ensuring database tables exist...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Ensure PostgreSQL Trigger permanently protects Lead Admin from DELETE:
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION protect_lead_admin_from_delete()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF OLD.role = 'SUPER_ADMIN' THEN
                        RAISE EXCEPTION 'The Lead Admin (SUPER_ADMIN: %) is permanently protected from deletion. It can only be deleted by truncating the admin_users table in the database.', OLD.email;
                    END IF;
                    RETURN OLD;
                END;
                $$ LANGUAGE plpgsql;
            """))
            await conn.execute(text("""
                DROP TRIGGER IF EXISTS trg_protect_lead_admin_delete ON admin_users;
            """))
            await conn.execute(text("""
                CREATE TRIGGER trg_protect_lead_admin_delete
                BEFORE DELETE ON admin_users
                FOR EACH ROW
                EXECUTE FUNCTION protect_lead_admin_from_delete();
            """))
        logger.info("[Startup] Database tables and Lead Admin delete protection trigger verified.")
    except Exception as e:
        logger.warning("[Startup] Database table initialization warning: %s", e)

    # Pre-warm embedding model in background thread to prevent cold-start latency
    try:
        logger.info("[Startup] Pre-warming embedding model...")
        await asyncio.to_thread(get_embedding_model)
        logger.info("[Startup] Embedding model loaded and ready.")
    except Exception as e:
        logger.warning("[Startup] Embedding model pre-warming deferred: %s", e)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Privacy-Guarded On-Demand RAG system for Google Drive",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend interactions
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(auth.router)
app.include_router(drive.router)
app.include_router(guardrails.router)
app.include_router(rag.router)
app.include_router(admin.router)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "embedding_model": settings.EMBEDDING_MODEL_NAME,
        "embedding_dimensions": settings.EMBEDDING_DIM
    }
