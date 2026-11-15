## Nemotron 3.5 embedding configuration

Edit the root `.env` (keep the real key out of Git):

```dotenv
EMBEDDING_PROVIDER=nvidia
EMBEDDING_API_KEY=your_nvidia_key
EMBEDDING_MODEL=nvidia/nemotron-3.5-embed-1b
NVIDIA_API_BASE_URL=https://integrate.api.nvidia.com/v1
EMBEDDING_DIMENSIONS=384
```

The API and synthetic loader call `/v1/embeddings` with Bearer authentication.
Queries use `input_type=query`; indexed dataset descriptions use `input_type=passage`.
384 output dimensions keep the current `vector(384)` index compatible. The model
supports reduced dimensions from 128 through its native 2048 dimensions.

After saving the configuration, regenerate **all** catalog embeddings before restarting the API:

```bash
python3 scripts/ingest_synthetic_data.py
python3 -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Do not compare Nemotron query vectors with the existing MiniLM document vectors,
even when both contain 384 values. Ingestion is transactional: an API failure
leaves the previous index intact. The current sample catalog contains ten datasets;
if you add other datasets, re-index those with the same model too.

Reference: https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-embed-1b-infer

---

# NVIDIA Embedding API Setup

This guide shows how to configure the Enigma SAC system to use NVIDIA's embedding API.

## Quick Start

### 1. Get your NVIDIA API Key
1. Go to [NVIDIA Build](https://build.nvidia.com/)
2. Sign in or create an account
3. Navigate to the embedding models (e.g., `nvidia/nv-embedqa-e5-v5`)
4. Generate an API key

### 2. Configure Environment Variables

Copy the example file and add your API key:

```bash
cp .env.example .env
```

Edit `.env` and set:

```env
# Use NVIDIA as embedding provider
EMBEDDING_PROVIDER=nvidia

# Your NVIDIA API key (required)
EMBEDDING_API_KEY=nvapi_xxxxxxxxxxxxxxxxxxxxxxxx

# Model to use (default: nvidia/nv-embedqa-e5-v5)
EMBEDDING_MODEL=nvidia/nv-embedqa-e5-v5

# Embedding dimensions (default: 1024 for nv-embedqa-e5-v5)
EMBEDDING_DIMENSIONS=1024

# NVIDIA API base URL (usually don't need to change)
NVIDIA_API_BASE_URL=https://integrate.api.nvidia.com/v1
```

### 3. Start Services

```bash
# Start database and services
docker-compose -f infra/docker-compose.yml up -d

# Or run locally with Python
export $(cat .env | xargs)  # Load env vars
python -m services.api.src.main
```

### 4. Test the Integration

```bash
# Test embedding generation
python scripts/test_nvidia_embedding.py

# Test full search pipeline
python scripts/test_search.py
```

## Supported NVIDIA Models

| Model | Dimensions | Description |
|-------|------------|-------------|
| `nvidia/nv-embedqa-e5-v5` | 1024 | General purpose QA embedding (recommended) |
| `nvidia/nv-embedqa-mistral-7b-v2` | 4096 | Larger model, higher quality |
| `nvidia/nv-embed-v1` | 1024 | General embedding model |

## Configuration Details

### Search Service Config (`services/search/src/config.py`)
- `EMBEDDING_PROVIDER`: Set to `"nvidia"`
- `EMBEDDING_API_KEY`: Your NVIDIA API key
- `EMBEDDING_MODEL`: Model identifier (e.g., `nvidia/nv-embedqa-e5-v5`)
- `EMBEDDING_DIMENSIONS`: Output dimensions (1024 for most NVIDIA models)
- `NVIDIA_API_BASE_URL`: Base URL for NVIDIA API

### API Service Config (`services/api/src/config.py`)
Same variables as above, loaded from `.env` file.

### Docker Compose (`infra/docker-compose.yml`)
Environment variables passed to API container:
- `EMBEDDING_PROVIDER`
- `EMBEDDING_API_KEY`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIMENSIONS`
- `NVIDIA_API_BASE_URL`

## Switching Between Providers

You can easily switch providers by changing `EMBEDDING_PROVIDER`:

```env
# Local (sentence-transformers)
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384

# OpenAI
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-xxxxx
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# NVIDIA
EMBEDDING_PROVIDER=nvidia
EMBEDDING_API_KEY=nvapi_xxxxx
EMBEDDING_MODEL=nvidia/nv-embedqa-e5-v5
EMBEDDING_DIMENSIONS=1024

# Remote (custom HTTP endpoint)
EMBEDDING_PROVIDER=remote
EMBEDDING_API_URL=http://your-embedding-service:8080/embed
```

## Verification

After setup, verify everything works:

```bash
# Check database has embeddings
python scripts/check_database.py

# Test search with your queries
python scripts/test_search.py
```

Expected output:
```
✅ Health check passed!
✅ Embeddings generated successfully!
   Model: nvidia/nv-embedqa-e5-v5
   Dimensions: 1024
   Token count: 45
   Number of embeddings: 3
```

## Troubleshooting

### "Invalid API Key"
- Verify your API key is correct
- Check the key has embedding permissions
- Ensure no extra spaces in `.env`

### "Model not found"
- Check model name spelling: `nvidia/nv-embedqa-e5-v5`
- Some models may require specific access

### "Dimensions mismatch"
- Ensure `EMBEDDING_DIMENSIONS` matches the model output
- `nv-embedqa-e5-v5` = 1024 dimensions
- Update database vector column if changing dimensions

### Connection timeout
- Check network access to `integrate.api.nvidia.com`
- Increase `EMBEDDING_TIMEOUT` if needed

## Re-embedding Existing Data

If you switch providers or models, you'll need to regenerate embeddings:

```bash
# Re-ingest synthetic data with new embeddings
python scripts/ingest_synthetic_data.py

# Or use the catalog CLI
cd services/catalog && python -m src.cli ingest_datasets
```