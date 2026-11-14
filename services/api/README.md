# API Service

HTTP API gateway for the Semantic Data Discovery & Interactive Dashboards system. Orchestrates the catalog, search, summarizer, and visualization services.

## Features

- **RESTful API** with OpenAPI 3.0 specification
- **Semantic Search** across 26 NASA PSI Combustion Science investigations
- **Dataset Management** - metadata, schema, preview
- **Evidence-based Summarization** via LLM with strict fact-checking
- **Interactive Visualization** - chart generation with Vega-Lite specs
- **Structured Logging** with request tracing
- **Rate Limiting** and SSRF protection
- **Health Checks** for Kubernetes readiness/liveness probes

## Architecture

```
services/api/
├── src/
│   ├── routes/           # API route handlers
│   ├── middleware/       # Request ID, logging, rate limiting
│   ├── database.py       # Async database connections
│   ├── config.py         # Configuration management
│   └── main.py           # FastAPI app + CLI
├── tests/                # Unit tests
├── pyproject.toml        # Dependencies
└── README.md
```

## API Endpoints

### Search
```
POST /api/v1/search
```
Semantic search across 26 NASA PSI investigations.

**Request:**
```json
{
  "query": "combustion temperature in microgravity",
  "filters": {
    "psiIds": ["PSI-20", "PSI-21"],
    "hasNumericData": true
  },
  "options": {
    "maxResults": 50,
    "minScore": 0.3
  }
}
```

**Response:**
```json
{
  "query": "combustion temperature in microgravity",
  "status": "matches_found",
  "source_collection": "NASA PSI — Combustion Science: 26 Selected Investigations",
  "data_filter": "numeric_only",
  "total_matches": 2,
  "datasets": [...],
  "searchMetadata": {...}
}
```

### Datasets
```
GET /api/v1/datasets/{id}           # Dataset metadata
GET /api/v1/datasets/{id}/schema    # Column schema with statistics
GET /api/v1/datasets/{id}/preview   # Data preview (100 rows)
```

### Summarization
```
POST /api/v1/datasets/{id}/summary
```
Evidence-based summary generation.

**Request:**
```json
{
  "datasetId": "psi-20-bre-temperature-csv",
  "options": {
    "includeStatistics": true,
    "maxLength": 1000
  }
}
```

### Visualization
```
POST /api/v1/charts/preview
```
Generate chart specification and data.

**Request:**
```json
{
  "datasetId": "psi-20-bre-temperature-csv",
  "chartType": "bar",
  "xAxis": "category",
  "yAxis": "temperature",
  "groupBy": "experiment",
  "options": {
    "title": "Temperature by Category",
    "width": 800,
    "height": 400
  }
}
```

### Health
```
GET /api/v1/health          # Full health check
GET /api/v1/health/ready    # Kubernetes readiness probe
GET /api/v1/health/live     # Kubernetes liveness probe
```

## Installation

```bash
cd services/api
pip install -e ".[dev]"
```

## Configuration

Environment variables (see `.env.example`):
- `DATABASE_URL` - PostgreSQL connection string
- `EMBEDDING_API_URL` - Embedding service URL
- `LLM_PROVIDER` - openai, anthropic, ollama, local
- `LLM_API_KEY` - API key for LLM provider
- `RATE_LIMIT_RPM` - Requests per minute (default: 60)
- `CORS_ORIGINS` - Allowed origins

## Running

```bash
# Development
api run --database-url postgresql://user:pass@localhost:5432/enigma_sac --reload

# Production
api run --database-url postgresql://user:pass@localhost:5432/enigma_sac

# Initialize database
api init-db --database-url postgresql://user:pass@localhost:5432/enigma_sac
```

## Testing

```bash
cd services/api
pytest tests/ -v
```

## Security

- **SSRF Protection**: Domain allowlisting, private IP blocking
- **Rate Limiting**: In-memory sliding window (configurable)
- **Input Validation**: Pydantic models for all endpoints
- **Structured Logging**: JSON logs with request IDs
- **CORS**: Configurable allowed origins

## Service Integration

The API orchestrates these internal services:
- **Catalog Service** - Dataset metadata and schema
- **Search Service** - Vector similarity search via pgvector
- **Summarizer Service** - LLM-based summarization
- **Visualization Service** - Chart generation

Each service can be deployed independently and communicates via HTTP.