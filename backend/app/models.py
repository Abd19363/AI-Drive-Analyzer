import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, BigInteger, Float,
    TIMESTAMP, ForeignKey, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from app.db import Base
from app.config import settings

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    google_accounts = relationship("GoogleAccount", back_populates="user", cascade="all, delete-orphan")
    drive_files = relationship("DriveFile", back_populates="user", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="user", cascade="all, delete-orphan")
    queries = relationship("ChatQuery", back_populates="user", cascade="all, delete-orphan")


class GoogleAccount(Base):
    __tablename__ = "google_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    google_user_id = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_uri = Column(String(255), default="https://oauth2.googleapis.com/token")
    scopes = Column(ARRAY(String), default=[])
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="google_accounts")


class DriveFile(Base):
    __tablename__ = "drive_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(String(255), nullable=False, index=True) # Google Drive File ID
    name = Column(String(500), nullable=False)
    mime_type = Column(String(255), nullable=False)
    size_bytes = Column(BigInteger, nullable=True)
    web_view_link = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True)
    etag = Column(String(255), nullable=True)
    guardrail_status = Column(String(50), default="UNCHECKED") # 'UNCHECKED', 'PASSED', 'FLAGGED_CONFIDENTIAL'
    confidentiality_reason = Column(Text, nullable=True)
    is_embedded = Column(Boolean, default=False)
    last_scanned_at = Column(TIMESTAMP(timezone=True), nullable=True)
    source_modified_time = Column(String(64), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="drive_files")
    guardrail_logs = relationship("GuardrailLog", back_populates="file", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="file", cascade="all, delete-orphan")


class GuardrailLog(Base):
    __tablename__ = "guardrail_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("drive_files.id", ondelete="CASCADE"), nullable=False, index=True)
    check_stage = Column(String(100), nullable=False) # 'METADATA_SCREENING', 'OCR_ANALYSIS', 'REGEX_VALIDATOR', 'AI_CLASSIFIER'
    detection_type = Column(String(100), nullable=True) # 'CNIC', 'SALARY_SLIP', 'PASSPORT', 'FINANCIAL_STATEMENT', 'SENSITIVE_KEYWORD'
    snippet_matched = Column(Text, nullable=True)
    confidence_score = Column(Float, default=1.0)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    file = relationship("DriveFile", back_populates="guardrail_logs")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("drive_files.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True) # 384 dimensions for all-MiniLM-L6-v2
    token_count = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    file = relationship("DriveFile", back_populates="chunks")
    user = relationship("User", back_populates="chunks")


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    model_name = Column(String(100), default="all-MiniLM-L6-v2")
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class ChatQuery(Base):
    __tablename__ = "chat_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    identified_files = Column(JSONB, default=list)
    skipped_files = Column(JSONB, default=list)
    answer_text = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="queries")
