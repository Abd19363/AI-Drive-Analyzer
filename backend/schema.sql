-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Google OAuth Accounts Table
CREATE TABLE IF NOT EXISTS google_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    google_user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_uri VARCHAR(255) DEFAULT 'https://oauth2.googleapis.com/token',
    scopes TEXT[] DEFAULT '{}',
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_google UNIQUE(user_id, google_user_id)
);

-- Google Drive File Metadata, Content Hash, and Guardrail Status Table
CREATE TABLE IF NOT EXISTS drive_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_id VARCHAR(255) NOT NULL, -- Google Drive File ID
    name VARCHAR(500) NOT NULL,
    mime_type VARCHAR(255) NOT NULL,
    size_bytes BIGINT,
    web_view_link TEXT,
    content_hash VARCHAR(64), -- SHA-256 for embedding caching
    etag VARCHAR(255),        -- Google Drive ETag for sync detection
    guardrail_status VARCHAR(50) DEFAULT 'UNCHECKED', -- 'UNCHECKED', 'PASSED', 'FLAGGED_CONFIDENTIAL'
    confidentiality_reason TEXT,
    is_embedded BOOLEAN DEFAULT FALSE,
    last_scanned_at TIMESTAMP WITH TIME ZONE,
    source_modified_time VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_file UNIQUE(user_id, file_id)
);

ALTER TABLE drive_files
    ADD COLUMN IF NOT EXISTS source_modified_time VARCHAR(64);

-- Guardrail Audit Logs (records reasons for blocking confidential files)
CREATE TABLE IF NOT EXISTS guardrail_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES drive_files(id) ON DELETE CASCADE,
    check_stage VARCHAR(100) NOT NULL, -- 'METADATA_SCREENING', 'OCR_ANALYSIS', 'REGEX_VALIDATOR', 'AI_CLASSIFIER'
    detection_type VARCHAR(100),       -- 'CNIC', 'SALARY_SLIP', 'PASSPORT', 'FINANCIAL_STATEMENT', 'SENSITIVE_KEYWORD'
    snippet_matched TEXT,
    confidence_score FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Document Chunks with 384-dimensional vectors for all-MiniLM-L6-v2
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES drive_files(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(384), -- Exact match for all-MiniLM-L6-v2 (384 dimensions)
    token_count INT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Embedding Cache Table (caching hash -> chunk embeddings to prevent redundant LLM/model calls)
CREATE TABLE IF NOT EXISTS embedding_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    model_name VARCHAR(100) DEFAULT 'all-MiniLM-L6-v2',
    embedding vector(384) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast cosine similarity search on document_chunks
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx 
ON document_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Index for fast lookup on embedding_cache
CREATE INDEX IF NOT EXISTS embedding_cache_hash_idx 
ON embedding_cache(content_hash);

-- Chat Queries & Q&A Audit Table
CREATE TABLE IF NOT EXISTS chat_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    identified_files JSONB DEFAULT '[]'::jsonb,
    skipped_files JSONB DEFAULT '[]'::jsonb,
    answer_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User-scoped answer cache; full document text is never stored here.
CREATE TABLE IF NOT EXISTS query_answer_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query_hash VARCHAR(64) NOT NULL,
    intent VARCHAR(40) NOT NULL,
    scope_hash VARCHAR(64) NOT NULL,
    answer_kind VARCHAR(30) NOT NULL,
    answer_text TEXT NOT NULL,
    source_file_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_file_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    document_versions JSONB NOT NULL DEFAULT '{}'::jsonb,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    is_safe BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_query_answer_cache_context
        UNIQUE (user_id, query_hash, intent, scope_hash, answer_kind)
);

CREATE INDEX IF NOT EXISTS query_answer_cache_lookup_idx
    ON query_answer_cache(user_id, query_hash, scope_hash, expires_at);
