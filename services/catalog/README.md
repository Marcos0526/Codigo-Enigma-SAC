# Catalog Service

Catalog service for NASA PSI Combustion Science datasets. Handles ingestion, validation, and management of the 26 selected investigations and their associated numerical datasets.

## Features

- **PSI Investigation Ingestion**: Fetches and parses the 26 selected NASA PSI Combustion Science investigations from the official PSI index
- **Dataset Discovery**: Discovers and ingests numerical datasets from investigation pages
- **URL Validation**: Validates and classifies URLs (investigation_page, direct_download, doi, unverified)
- **Numerical Content Detection**: Automatically detects numerical columns in CSV, Parquet, JSON, Excel files
- **Deduplication**: Prevents duplicate datasets using URL, content hash, and metadata similarity
- **Provenance Tracking**: Maintains full provenance from investigation to dataset
- **Vector Search**: Supports semantic search via pgvector embeddings

## Architecture

```
services/catalog/
├── src/
│   ├── models/          # SQLAlchemy + Pydantic models
│   ├── ingestion/       # PSI & dataset ingestion pipelines
│   ├── validation/      # URL, numerical, deduplication validators
│   ├── connectors/      # Data connectors (HTTP, Parquet, etc.)
│   ├── catalog_service.py  # Main service class
│   └── cli.py           # Command-line interface
├── tests/               # Unit and integration tests
└── pyproject.toml       # Dependencies and config
```

## Installation

```bash
cd services/catalog
pip install -e ".[dev]"
```

## Configuration

Environment variables:
- `DATABASE_URL` - PostgreSQL connection string (required)
- `ALLOWED_DOMAINS` - Comma-separated list of allowed domains for data access

## Usage

### Initialize Database
```bash
catalog init-db --database-url postgresql://user:pass@localhost/db
```

### Ingest PSI Investigations
```bash
catalog ingest-psi --database-url postgresql://user:pass@localhost/db
```

### Ingest Datasets
```bash
# All investigations
catalog ingest-datasets --database-url postgresql://user:pass@localhost/db

# Specific investigations
catalog ingest-datasets --psi-ids PSI-20,PSI-21 --database-url postgresql://user:pass@localhost/db
```

### Validate URL
```bash
catalog validate-url https://psi.nasa.gov/physci/repo/data/investigations/PSI-20/data/file.csv
```

### List Investigations
```bash
catalog list-investigations
```

### List Datasets
```bash
catalog list-datasets PSI-20
```

### Health Check
```bash
catalog health
```

## Data Models

### PSI Investigation
- `psi_id`: PSI-XX identifier
- `title`: Investigation title
- `description`: Description
- `research_area`: Research area (Combustion Science)
- `sub_research_area`: Sub-area from PSI index
- `scientific_focus`: Specific scientific focus
- `project_setting`: ISS microgravity, Ground Investigation, etc.
- `doi`: Digital Object Identifier
- `metadata_status`: verified/pending/failed/unknown
- `tags`: Topic tags

### Dataset
- `dataset_id`: Stable unique identifier
- `psi_id`: Parent investigation
- `name`: Dataset name
- `description`: Description
- `url`: Data URL
- `url_type`: investigation_page/direct_download/doi/unverified
- `format`: csv/parquet/json/xlsx/etc.
- `numeric_columns`: List of numerical column names
- `verification_status`: verified/pending/failed/unknown
- `provenance`: Investigation URL, dataset URL, retrieval timestamp

## Validation Rules

### URL Validation
- Domain must be in allowlist (psi.nasa.gov, raw.githubusercontent.com, etc.)
- SSRF protection blocks private/local IPs
- Classifies URL type automatically

### Numerical Content Detection
- Samples up to 10,000 rows / 50 MB
- Requires ≥50% non-null numeric values
- Detects numeric, datetime, boolean, categorical, text types
- Computes statistics for numeric columns

### Deduplication
1. Exact URL match (highest priority)
2. Content hash match (SHA-256)
3. Metadata similarity (Jaccard on numeric columns, threshold 0.9)

## Database Schema

PostgreSQL with pgvector extension:
- `psi_investigations`: Investigation metadata
- `datasets`: Dataset catalog entries
- `dataset_schemas`: Column-level schema
- `dataset_profiles`: Profiling metadata
- `dataset_embeddings`: Vector embeddings for search
- `search_queries` / `search_results`: Query logging for evaluation

## Testing

```bash
cd services/catalog
pytest tests/ -v
```

## Security

- All external URLs validated against allowlist
- SSRF protection via domain and IP validation
- Content size limits enforced
- No arbitrary SQL execution
- Read-only database connections where possible