# Search Service

Semantic search service for NASA PSI Combustion Science datasets. Provides vector similarity search, hybrid search, query classification, and reranking capabilities.

## Features

- **Vector Search**: Semantic search using pgvector and sentence-transformers embeddings
- **Hybrid Search**: Combines vector similarity with PostgreSQL full-text search
- **Query Classification**: Classifies queries into combustion science subtopics
- **Reranking**: Cross-encoder reranking for improved relevance
- **Filtering**: Filter by PSI investigation, format, verification status
- **Combustion Domain**: Specialized for 26 NASA PSI Combustion Science investigations

## Architecture

```
services/search/
├── src/
│   ├── embedding/          # Embedding providers (local, remote, OpenAI)
│   ├── retrieval/          # Vector & hybrid search retrievers
│   ├── classification/     # Query classification for combustion domain
│   ├── reranking/          # Cross-encoder and heuristic rerankers
│   ├── search_service.py   # Main orchestration service
│   ├── config.py           # Configuration management
│   └── cli.py              # Command-line interface
├── tests/                  # Unit tests
└── pyproject.toml          # Dependencies
```

## Installation

```bash
cd services/search
pip install -e ".[dev]"
```

## Configuration

Environment variables:
- `DATABASE_URL` - PostgreSQL connection string
- `EMBEDDING_PROVIDER` - local, remote, or openai
- `EMBEDDING_MODEL` - Sentence transformer model name
- `SEARCH_MIN_SCORE` - Minimum similarity threshold
- `SEARCH_MAX_RESULTS` - Maximum results per query
- `SEARCH_RERANK_ENABLED` - Enable cross-encoder reranking

## Usage

### Search
```bash
search search "combustion temperature in microgravity" \
  --min-score 0.3 \
  --max-results 50 \
  --hybrid \
  --rerank
```

### Find Similar Datasets
```bash
search similar psi-20-bre-temperature-csv --count 10
```

### Classify Query
```bash
search classify "flame propagation in microgravity"
```

### Evaluation Queries
```bash
search evaluation-queries
```

### Health Check
```bash
search health
```

## Search Flow

1. **Query Classification**: Classify query into combustion subtopic (temperature, microgravity, propagation, extinction, soot, aerosols, fire safety, cool flames, solid/gaseous/liquid fuels)
2. **Filter Generation**: Auto-suggest PSI IDs, tags, formats based on classification
3. **Retrieval**: Vector search (or hybrid with keyword search)
4. **Reranking**: Cross-encoder or heuristic reranking
5. **Response**: Formatted results with scores, metadata, and search info

## Combustion Subtopics

| Subtopic | Description | Example PSI Investigations |
|----------|-------------|---------------------------|
| `combustion_temperature` | Temperature measurements, pyrometry | PSI-20, PSI-21, PSI-69 |
| `flame_microgravity` | Microgravity flame behavior | PSI-20, PSI-21, PSI-22, PSI-23, PSI-159 |
| `flame_propagation` | Flame spread, burning rate | PSI-25, PSI-62, PSI-98, PSI-99 |
| `extinction` | Extinction limits, suppressants | PSI-69, PSI-142, PSI-10 |
| `soot` | Soot formation, volume fraction | PSI-21, PSI-10, PSI-22, PSI-60, PSI-107 |
| `aerosols_smoke` | Smoke particles, aerosols | PSI-47, PSI-101, PSI-102, PSI-115 |
| `fire_safety` | Spacecraft fire safety | PSI-98, PSI-99, PSI-100, PSI-26, PSI-25 |
| `cool_flames` | Low-temperature cool flames | PSI-39, PSI-159, PSI-142, PSI-117 |
| `solid_fuels` | Solid material combustion | PSI-26, PSI-25, PSI-62 |
| `gaseous_fuels` | Gaseous diffusion/premixed flames | PSI-20, PSI-21, PSI-10, PSI-22 |
| `liquid_fuels` | Droplet/spray combustion | PSI-39, PSI-69 |

## API Contract

The service implements the search contract from `@enigma-sac/contracts`:

```json
{
  "query": "string",
  "status": "matches_found | no_matches",
  "source_collection": "NASA PSI — Combustion Science: 26 Selected Investigations",
  "data_filter": "numeric_only",
  "total_matches": 0,
  "datasets": [...],
  "search_metadata": {...}
}
```

## Testing

```bash
cd services/search
pytest tests/ -v
```

## Security

- All database queries use parameterized statements
- Embedding service called via HTTP with timeouts
- No user input directly in SQL queries
- Domain allowlisting for external API calls