-- Migrate cases table from integer PK to UUID
-- Run: docker exec -i postgres psql -U postgres -d litigation < migrate_cases_uuid.sql

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DROP TABLE IF EXISTS cases CASCADE;

CREATE TABLE cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id),
    case_name VARCHAR NOT NULL,
    claim_type VARCHAR DEFAULT '',
    current_stage VARCHAR DEFAULT 'draft',
    plaintiff_name VARCHAR DEFAULT '',
    plaintiff_counsel VARCHAR DEFAULT '',
    defense_name VARCHAR DEFAULT '',
    defense_counsel VARCHAR DEFAULT '',
    state VARCHAR DEFAULT '',
    court VARCHAR DEFAULT '',
    county VARCHAR DEFAULT '',
    trial_date VARCHAR DEFAULT '',
    summary VARCHAR DEFAULT '',
    analysis VARCHAR DEFAULT 'Not started',
    document_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_cases_user_id ON cases(user_id);
CREATE INDEX idx_cases_case_name ON cases(case_name);