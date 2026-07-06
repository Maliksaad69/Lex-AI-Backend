-- Create documents table
-- Run: docker exec -i postgres psql -U postgres -d litigation < migrate_documents.sql

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id),
    case_id UUID NOT NULL REFERENCES cases(id),
    filename VARCHAR NOT NULL,
    file_type VARCHAR DEFAULT '',
    file_size INTEGER DEFAULT 0,
    file_path VARCHAR DEFAULT '',
    page_count INTEGER DEFAULT 0,
    text_preview VARCHAR DEFAULT '',
    chunks_count INTEGER DEFAULT 0,
    qdrant_document_id VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_case_id ON documents(case_id);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);
CREATE INDEX IF NOT EXISTS idx_documents_qdrant_id ON documents(qdrant_document_id);