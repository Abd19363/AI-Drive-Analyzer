import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Enable OAuth2 over HTTP for local development
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from app.config import settings
from app.routes import auth, drive, guardrails, rag

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Privacy-Guarded On-Demand RAG system for Google Drive",
    version="1.0.0"
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

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "embedding_model": settings.EMBEDDING_MODEL_NAME,
        "embedding_dimensions": settings.EMBEDDING_DIM
    }
