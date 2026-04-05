-- Cloud PostgreSQL schema for repair guides (CarDiagn + charm.li) and RAG chunks.
-- Use with CARDIAGN_DB_URL (or REPAIR_GUIDES_DB_URL). Diago backend is the only consumer.

-- Unified repair/manual content (cardiagn and charm_li)
CREATE TABLE IF NOT EXISTS repair_guides (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL CHECK (source IN ('cardiagn', 'charm_li')),
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    vehicle_make TEXT,
    vehicle_model TEXT,
    year_min INTEGER,
    year_max INTEGER,
    category TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source, source_url)
);

CREATE INDEX IF NOT EXISTS idx_repair_guides_source ON repair_guides(source);
CREATE INDEX IF NOT EXISTS idx_repair_guides_make_model ON repair_guides(vehicle_make, vehicle_model);
CREATE INDEX IF NOT EXISTS idx_repair_guides_year ON repair_guides(year_min, year_max);
CREATE INDEX IF NOT EXISTS idx_repair_guides_category ON repair_guides(category);

-- Full-text search on title, summary, content
ALTER TABLE repair_guides ADD COLUMN IF NOT EXISTS search_vector tsvector;
-- Run after table is populated or on schedule:
-- UPDATE repair_guides SET search_vector = to_tsvector('english', coalesce(title,'') || ' ' || coalesce(summary,'') || ' ' || coalesce(content,''));

-- Optional: step-by-step procedures (for CarDiagn-style guides)
CREATE TABLE IF NOT EXISTS repair_steps (
    id SERIAL PRIMARY KEY,
    guide_id INTEGER NOT NULL REFERENCES repair_guides(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    title TEXT,
    body TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_repair_steps_guide ON repair_steps(guide_id);

-- RAG chunks for ASE-aligned diagnostic chat (in-process or pgvector)
CREATE TABLE IF NOT EXISTS rag_chunks (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'ase_curated',
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Optional: pgvector extension for embedding similarity search (uncomment if using Supabase/pgvector)
-- CREATE EXTENSION IF NOT EXISTS vector;
-- ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS embedding vector(384);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_source ON rag_chunks(source);
