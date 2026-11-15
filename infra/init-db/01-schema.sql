-- ============================================================================
-- Enigma SAC - Database Schema
-- Semantic Data Discovery & Interactive Dashboards
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- Custom Types
-- ============================================================================

CREATE TYPE verification_status AS ENUM ('verified', 'pending', 'failed', 'unknown');
CREATE TYPE access_policy AS ENUM ('public', 'restricted', 'authenticated', 'unknown');
CREATE TYPE url_type AS ENUM ('investigation_page', 'direct_download', 'doi', 'unverified');
CREATE TYPE data_format AS ENUM ('csv', 'parquet', 'json', 'xlsx', 'api', 'sql', 'unknown');
CREATE TYPE column_type AS ENUM ('numeric', 'categorical', 'datetime', 'text', 'boolean', 'unknown');
CREATE TYPE search_status AS ENUM ('matches_found', 'no_matches');

-- ============================================================================
-- PSI Investigations Table
-- ============================================================================

CREATE TABLE psi_investigations (
    psi_id VARCHAR(20) PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    research_area VARCHAR(100) NOT NULL DEFAULT 'Combustion Science',
    sub_research_area VARCHAR(100),
    scientific_focus TEXT,
    project_setting TEXT,
    record_type VARCHAR(50) NOT NULL DEFAULT 'Investigation',
    doi VARCHAR(100),
    doi_url TEXT,
    psi_record_url TEXT NOT NULL,
    objectives TEXT,
    approach TEXT,
    sources TEXT[],
    metadata_status verification_status NOT NULL DEFAULT 'unknown',
    verified_at TIMESTAMPTZ,
    tags TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_psi_investigations_tags ON psi_investigations USING GIN (tags);
CREATE INDEX idx_psi_investigations_sub_area ON psi_investigations (sub_research_area);
CREATE INDEX idx_psi_investigations_status ON psi_investigations (metadata_status);

-- ============================================================================
-- Datasets Table
-- ============================================================================

CREATE TABLE datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id VARCHAR(100) NOT NULL UNIQUE,
    psi_id VARCHAR(20) NOT NULL REFERENCES psi_investigations(psi_id),
    name TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    url_type url_type NOT NULL DEFAULT 'unverified',
    format data_format NOT NULL DEFAULT 'unknown',
    numeric_columns TEXT[] NOT NULL DEFAULT '{}',
    source TEXT,
    license TEXT,
    access_policy access_policy NOT NULL DEFAULT 'unknown',
    coverage_temporal TEXT,
    coverage_geographic TEXT,
    catalog_version VARCHAR(20) NOT NULL,
    embedding_model VARCHAR(100),
    embedding_version VARCHAR(20),
    verification_status verification_status NOT NULL DEFAULT 'unknown',
    verified_at TIMESTAMPTZ,
    tags TEXT[],
    provenance_investigation_url TEXT NOT NULL,
    provenance_dataset_url TEXT NOT NULL,
    provenance_retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_datasets_psi_id ON datasets (psi_id);
CREATE INDEX idx_datasets_verification ON datasets (verification_status);
CREATE INDEX idx_datasets_format ON datasets (format);
CREATE INDEX idx_datasets_tags ON datasets USING GIN (tags);
CREATE INDEX idx_datasets_numeric_columns ON datasets USING GIN (numeric_columns);
CREATE INDEX idx_datasets_catalog_version ON datasets (catalog_version);

-- ============================================================================
-- Dataset Embeddings (for vector search)
-- ============================================================================

CREATE TABLE dataset_embeddings (
    dataset_id UUID PRIMARY KEY REFERENCES datasets(id) ON DELETE CASCADE,
    embedding VECTOR(384) NOT NULL,
    model VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Vector similarity index (using HNSW for better performance)
CREATE INDEX idx_dataset_embeddings_vector ON dataset_embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- Dataset Schemas (Column metadata)
-- ============================================================================

CREATE TABLE dataset_schemas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    column_type column_type NOT NULL DEFAULT 'unknown',
    description TEXT,
    unit VARCHAR(100),
    nullable BOOLEAN NOT NULL DEFAULT TRUE,
    sample_values JSONB,
    statistics JSONB,
    ordinal_position INTEGER NOT NULL,
    profiled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    profile_version VARCHAR(20) NOT NULL,
    UNIQUE (dataset_id, column_name)
);

CREATE INDEX idx_dataset_schemas_dataset ON dataset_schemas (dataset_id);
CREATE INDEX idx_dataset_schemas_type ON dataset_schemas (column_type);

-- ============================================================================
-- Dataset Profiling Metadata
-- ============================================================================

CREATE TABLE dataset_profiles (
    dataset_id UUID PRIMARY KEY REFERENCES datasets(id) ON DELETE CASCADE,
    row_count BIGINT,
    byte_size BIGINT,
    column_count INTEGER,
    profiled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    profile_version VARCHAR(20) NOT NULL,
    profiling_duration_ms INTEGER,
    warnings TEXT[]
);

-- ============================================================================
-- Search Query Log (for evaluation and analytics)
-- ============================================================================

CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    query_embedding VECTOR(384),
    filters JSONB,
    status search_status NOT NULL,
    total_matches INTEGER NOT NULL DEFAULT 0,
    processing_time_ms INTEGER,
    embedding_model VARCHAR(100),
    embedding_version VARCHAR(20),
    catalog_version VARCHAR(20),
    user_agent TEXT,
    ip_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_search_queries_created ON search_queries (created_at DESC);
CREATE INDEX idx_search_queries_status ON search_queries (status);

-- ============================================================================
-- Search Results (for evaluation)
-- ============================================================================

CREATE TABLE search_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    search_query_id UUID NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    score DOUBLE PRECISION NOT NULL,
    rank INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_search_results_query ON search_results (search_query_id);
CREATE INDEX idx_search_results_dataset ON search_results (dataset_id);

-- ============================================================================
-- Summary Generations (for audit trail)
-- ============================================================================

CREATE TABLE summary_generations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    request_options JSONB,
    summary JSONB NOT NULL,
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    tokens_used INTEGER,
    generation_time_ms INTEGER,
    catalog_version VARCHAR(20),
    profiling_version VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_summary_generations_dataset ON summary_generations (dataset_id);

-- ============================================================================
-- Chart Generations (for audit trail)
-- ============================================================================

CREATE TABLE chart_generations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    request JSONB NOT NULL,
    response_metadata JSONB NOT NULL,
    processing_time_ms INTEGER,
    memory_used_bytes BIGINT,
    row_count INTEGER,
    filtered_row_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chart_generations_dataset ON chart_generations (dataset_id);

-- ============================================================================
-- Updated At Trigger
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_psi_investigations_updated_at
    BEFORE UPDATE ON psi_investigations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_datasets_updated_at
    BEFORE UPDATE ON datasets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to find similar datasets by embedding
CREATE OR REPLACE FUNCTION find_similar_datasets(
    query_embedding VECTOR(384),
    match_count INT DEFAULT 50,
    min_similarity FLOAT DEFAULT 0.3,
    filter_psi_ids VARCHAR[] DEFAULT NULL,
    filter_verification verification_status[] DEFAULT NULL
)
RETURNS TABLE (
    dataset_id UUID,
    dataset_stable_id VARCHAR(100),
    psi_id VARCHAR(20),
    name TEXT,
    description TEXT,
    url TEXT,
    format data_format,
    numeric_columns TEXT[],
    score DOUBLE PRECISION,
    investigation_title TEXT,
    verification_status verification_status
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.dataset_id,
        d.psi_id,
        d.name,
        d.description,
        d.url,
        d.format,
        d.numeric_columns,
        1 - (de.embedding <=> query_embedding) AS score,
        pi.title AS investigation_title,
        d.verification_status
    FROM datasets d
    JOIN dataset_embeddings de ON de.dataset_id = d.id
    JOIN psi_investigations pi ON pi.psi_id = d.psi_id
    WHERE 1 - (de.embedding <=> query_embedding) >= min_similarity
      AND d.verification_status = 'verified'
      AND d.numeric_columns IS NOT NULL
      AND array_length(d.numeric_columns, 1) > 0
      AND (filter_psi_ids IS NULL OR d.psi_id = ANY(filter_psi_ids))
      AND (filter_verification IS NULL OR d.verification_status = ANY(filter_verification))
    ORDER BY de.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- Row Level Security (Optional - enable for production)
-- ============================================================================

-- ALTER TABLE datasets ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY datasets_read_policy ON datasets FOR SELECT USING (access_policy = 'public');