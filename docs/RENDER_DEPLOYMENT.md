# Render Deployment Guide for Enigma SAC

This guide explains how to deploy the Enigma SAC application to Render.

## Prerequisites

1. A Render account (free tier works for development)
2. A PostgreSQL-compatible LLM API key (OpenAI, NVIDIA, etc.)
3. This repository with the `render.yaml` file

## Quick Start

### Option 1: Using the Blueprint (Recommended)

1. Push the `render.yaml` file to your repository root
2. Go to Render Dashboard → New → Blueprint
3. Connect your repository
4. Render will automatically create all services defined in `render.yaml`

### Option 2: Manual Setup

Create the following services manually:

#### 1. PostgreSQL Database
- Type: PostgreSQL
- Name: `enigma-sac-db`
- PostgreSQL Version: 16
- Plan: 1c-2g or higher for production
- Connection Pool: pgbouncer

#### 2. Redis Cache
- Type: Key Value (Redis)
- Name: `enigma-sac-redis`
- Plan: free or higher

#### 3. API Service
- Type: Web Service
- Name: `enigma-sac-api`
- Runtime: Python
- Build Command: See `render.yaml`
- Start Command: `python -m uvicorn services.api.main:app --host 0.0.0.0 --port 8000`
- Port: 8000
- Plan: Starter (free) or higher

#### 4. Web Frontend
- Type: Web Service
- Name: `enigma-sac-web`
- Runtime: Node
- Build Command: `npm run build --workspace=apps/web`
- Start Command: `npm run start --workspace=apps/web`
- Port: 3000

#### 5. Cron Job: Catalog Ingestion
- Type: Cron Job
- Name: `enigma-sac-catalog-ingest`
- Runtime: Python
- Schedule: `0 * * * *` (hourly)
- Timeout: 600 seconds (10 minutes)

## Required Environment Variables

### API Service (`enigma-sac-api`)

| Variable | Value | Notes |
|----------|-------|-------|
| `APP_ENV` | `production` | - |
| `APP_PORT` | `8000` | - |
| `DATABASE_URL` | Auto-populated by Render | From `enigma-sac-db` |
| `REDIS_URL` | Auto-populated by Render | From `enigma-sac-redis` |
| `EMBEDDING_PROVIDER` | `local` | Can also be `nvidia`, `openai`, etc. |
| `LLM_API_KEY` | Your API key | **Required** - set via Render secrets |
| `LLM_MODEL` | `gpt-4-turbo-preview` | - |
| `CORS_ORIGINS` | Your URLs | Auto-updates with RENDER_EXTERNAL_URL |

### Web Service (`enigma-sac-web`)

| Variable | Value | Notes |
|----------|-------|-------|
| `NODE_ENV` | `production` | - |
| `PORT` | `3000` | - |
| `API_BACKEND_URL` | `http://enigma-sac-api:8000` | - |

### Catalog Ingestion Cron Job

| Variable | Value | Notes |
|----------|-------|-------|
| `APP_ENV` | `production` | - |
| `DATABASE_URL` | Auto-populated | From `enigma-sac-db` |
| `REDIS_URL` | Auto-populated | From `enigma-sac-redis` |
| `LLM_API_KEY` | Your API key | **Required** |
| `LLM_MODEL` | Your model | - |

## Database Setup

### Enable pgvector Extension

The `preDeployCommand` in the API service automatically runs:
```bash
bash infra/init-db/init_render.sh
```

This enables the required PostgreSQL extensions:
- `uuid-ossp` - UUID generation
- `pgvector` - Vector similarity search
- `pg_trgm` - Trigram indexing

### Database Schema

The schema is created automatically by the application on startup. No manual intervention required.

## First Deployment

1. Deploy all services
2. Wait for API health check to pass
3. Run the catalog ingestion job to seed data:
   ```bash
   curl -X POST https://enigma-sac-api.onrender.com/api/v1/datasets/ingest
   ```
   Or use the cron job `enigma-sac-catalog-ingest`

4. Trigger initial data ingestion via the API or wait for the hourly cron job

## Post-Deployment Tasks

### Update CORS Settings
The `CORS_ORIGINS` variable is auto-populated with `${RENDER_EXTERNAL_URL}`. Verify it's correct in the Render dashboard.

### Seed Initial Data
Run the catalog ingestion to populate your database:
```bash
render cron run enigma-sac-catalog-ingest --now
```

### Monitor Services
- API Health: `https://your-api-url.onrender.com/health`
- Web UI: `https://your-web-url.onrender.com`

## Costs

### Free Tier Limits
- API: 750 hours/month (1 instance, 512MB RAM)
- Web: 750 hours/month (1 instance, 512MB RAM)
- PostgreSQL: 256MB, 1 GB disk
- Redis: 256MB

### Paid Plans (for production)
- API/Web: Starts at $7/month (1C-2GB)
- PostgreSQL: $25+/month (2C-8GB recommended)
- Redis: $7+/month

## Troubleshooting

### Database Connection Issues
1. Check `DATABASE_URL` is correctly linked to `enigma-sac-db`
2. Verify pgvector extension is enabled
3. Check logs for connection errors

### API Returns 500 Errors
1. Check logs for missing environment variables
2. Verify `LLM_API_KEY` is set correctly
3. Ensure `DATABASE_URL` points to a healthy database

### Web Frontend Not Loading
1. Check `API_BACKEND_URL` is accessible
2. Verify CORS settings allow your domain
3. Check build logs for errors

## Scaling

### For Higher Traffic
- Upgrade API plan to 2C-4G or higher
- Enable autoscaling in service settings
- Upgrade PostgreSQL to Standard-2X plan

### For Database Growth
- Upgrade PostgreSQL plan
- Increase disk size in database settings
- Enable storage autoscaling

## Environment Variables Reference

### All Available Variables

See `services/api/src/config.py` for the complete configuration schema.

Key configuration groups:

1. **Application Settings**
   - `APP_ENV`, `APP_PORT`, `LOG_LEVEL`

2. **Database & Redis**
   - `DATABASE_URL`, `REDIS_URL`

3. **Embedding**
   - `EMBEDDING_PROVIDER` (local/nvidia/openai)
   - `EMBEDDING_MODEL`, `EMBEDDING_API_URL`

4. **LLM**
   - `LLM_PROVIDER` (openai/nvidia/anthropic/local)
   - `LLM_MODEL`, `LLM_API_KEY`

5. **Data Connectors**
   - `ALLOWED_DATA_DOMAINS`
   - `MAX_DOWNLOAD_SIZE`, `DOWNLOAD_TIMEOUT`

6. **Search**
   - `SEARCH_MIN_SCORE`, `SEARCH_MAX_RESULTS`

7. **Security**
   - `SSRF_PROTECTION_ENABLED`
   - `RATE_LIMIT_RPM`
   - `CORS_ORIGINS`