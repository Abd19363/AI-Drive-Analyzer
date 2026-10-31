import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, BigInteger, Float,
    TIMESTAMP, ForeignKey, ARRAY, UniqueConstraint
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
    password_hash = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    reset_code = Column(String(20), nullable=True)
    reset_code_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
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
    identified_files = Column(JSONB, default=list) # files analyzed
    skipped_files = Column(JSONB, default=list)
    source_file_names = Column(JSONB, default=list) # files referenced
    responding_file_name = Column(String(500), nullable=True) # file name from which system responds
    answer_text = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="queries")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="SECONDARY_ADMIN") # "SUPER_ADMIN" (Developer) or "SECONDARY_ADMIN"
    status = Column(String(50), default="PENDING") # "PENDING", "APPROVED", "REJECTED"
    request_note = Column(Text, nullable=True)
    linked_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    reset_code = Column(String(20), nullable=True)
    reset_code_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)


from sqlalchemy import event

@event.listens_for(AdminUser, "before_delete")
def protect_lead_admin_from_orm_delete(mapper, connection, target):
    """
    Ensures that the Lead Admin (SUPER_ADMIN) cannot be deleted via ORM or SQL DELETE.
    The Lead Admin can only be deleted by truncating the admin_users table in the database.
    """
    if target.role == "SUPER_ADMIN":
        raise ValueError(
            "The Lead Admin (SUPER_ADMIN) is permanently protected and cannot be deleted via DELETE. "
            "It can only be removed by truncating the admin_users table in the database."
        )


class QueryTelemetry(Base):
    __tablename__ = "query_telemetry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(String(100), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_email = Column(String(255), nullable=True, index=True)
    latency_ms = Column(Float, nullable=False, default=0.0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cache_hit = Column(Boolean, default=False)
    api_called = Column(Boolean, default=False)
    intent = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, index=True)


class QueryAnswerCache(Base):
    __tablename__ = "query_answer_cache"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "query_hash",
            "intent",
            "scope_hash",
            "answer_kind",
            name="uq_query_answer_cache_context",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query_hash = Column(String(64), nullable=False, index=True)
    intent = Column(String(40), nullable=False)
    scope_hash = Column(String(64), nullable=False)
    answer_kind = Column(String(30), nullable=False)
    answer_text = Column(Text, nullable=False)
    source_file_ids = Column(JSONB, nullable=False, default=list)
    source_file_names = Column(JSONB, nullable=False, default=list)
    document_versions = Column(JSONB, nullable=False, default=dict)
    sources = Column(JSONB, nullable=False, default=list)
    is_complete = Column(Boolean, nullable=False, default=False)
    is_safe = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
