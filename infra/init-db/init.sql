-- ============================================================================
-- Enigma SAC - Database Initialization Script for Render
-- This script is run during database creation
-- ============================================================================

-- Enable required extensions (pgvector must be available on the PostgreSQL instance)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create custom types
CREATE TYPE IF NOT EXISTS verification_status AS ENUM ('verified', 'pending', 'failed', 'unknown');
CREATE TYPE IF NOT EXISTS access_policy AS ENUM ('public', 'restricted', 'authenticated', 'unknown');
CREATE TYPE IF NOT EXISTS url_type AS ENUM ('investigation_page', 'direct_download', 'doi', 'unverified');
CREATE TYPE IF NOT EXISTS data_format AS ENUM ('csv', 'parquet', 'json', 'xlsx', 'api', 'sql', 'unknown');
CREATE TYPE IF NOT EXISTS column_type AS ENUM ('numeric', 'categorical', 'datetime', 'text', 'boolean', 'unknown');
CREATE TYPE IF NOT EXISTS search_status AS ENUM ('matches_found', 'no_matches');

-- Create tables (schema)
-- This will be populated by the application's init_db migrations

-- Verify extension installation
\echo 'pgvector extension status:'
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Note: Data will be seeded by the application after deployment
-- Run the catalog ingestion job to populate the database