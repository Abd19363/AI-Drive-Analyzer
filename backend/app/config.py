import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Drive Analyzer"
    ENVIRONMENT: str = "development"
    
    # Database
    # Note: user database is db_ai_drive
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/db_ai_drive"
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/db_ai_drive"
    
    # AI & Embeddings
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    DRIVE_FILE_CATALOG_CACHE_TTL_SECONDS: int = 60
    QUERY_ANSWER_CACHE_TTL_SECONDS: int = 60
    GENERAL_ANSWER_CACHE_TTL_SECONDS: int = 86400
    INSUFFICIENT_ANSWER_CACHE_TTL_SECONDS: int = 30
    QUERY_DECISION_CACHE_TTL_SECONDS: int = 3600
    
    # Google OAuth 2.0 Credentials (for Google Drive access)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"
    
    # Security & Tokens
    SECRET_KEY: str = "supersecret-jwt-session-key-change-in-production-123456"
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Google Drive Scopes requested
    GOOGLE_SCOPES: List[str] = [
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/drive.readonly",
        "openid"
    ]
    
    # Optional OCR binary path for Windows
    TESSERACT_CMD: str = "tesseract"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
