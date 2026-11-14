# @enigma-sac/contracts

Shared contracts, TypeScript types, and JSON schemas for the **Semantic Data Discovery & Interactive Dashboards** project.

## Overview

This package defines the canonical data contracts used across all services:

- **Dataset** — Core dataset metadata with provenance and verification status
- **PSI Investigation** — NASA PSI investigation metadata
- **Search** — Request/response for semantic search across the 26 selected investigations
- **Schema** — Dataset schema with column types and statistics
- **Preview** — Bounded data samples
- **Summary** — Evidence-based LLM-generated summaries
- **Visualization** — Chart configuration and preview responses
- **API Errors** — Standardized error responses

## Installation

```bash
npm install @enigma-sac/contracts
```

## Usage

### TypeScript Types

```typescript
import type { Dataset, SearchRequest, SearchResponse, SummaryResponse } from '@enigma-sac/contracts';

// Use types in your service
const dataset: Dataset = {
  id: 'psi-20-bre-temp',
  psiId: 'PSI-20',
  name: 'BRE Temperature Data',
  // ...
};
```

### JSON Schema Validation

```typescript
import { validateSearchRequest, validateSearchResponse } from '@enigma-sac/contracts';

const request = { query: 'combustion temperature in microgravity' };
const { valid, errors } = validateSearchRequest(request);

if (!valid) {
  throw new Error(`Invalid request: ${errors}`);
}
```

### OpenAPI Specification

The OpenAPI 3.0 specification is available at `src/api/openapi.yaml` and can be used to generate clients, servers, and documentation.

## Schema Files

| Schema | Description |
|--------|-------------|
| `search.json` | Search request payload |
| `search-response.json` | Search response with all matching datasets |
| `dataset.json` | Complete dataset metadata |
| `dataset-schema.json` | Dataset schema (columns, types, statistics) |
| `dataset-preview.json` | Bounded dataset preview |
| `summary.json` | Summary generation request |
| `summary-response.json` | Evidence-based summary response |
| `chart-preview.json` | Chart generation request |
| `chart-preview-response.json` | Chart specification and data |
| `psi-investigation.json` | PSI investigation metadata |
| `api-error.json` | Standardized error response |
| `health.json` | Health check response |

## Key Contract Rules

### Search Response

- `total_matches` **must equal** `datasets.length`
- `source_collection` is fixed: `"NASA PSI — Combustion Science: 26 Selected Investigations"`
- `data_filter` is fixed: `"numeric_only"`
- `status` is either `"matches_found"` or `"no_matches"`

### Dataset URL Types

The `urlType` field distinguishes:
- `investigation_page` — PSI investigation landing page (not a direct download)
- `direct_download` — Direct link to downloadable data file
- `doi` — Digital Object Identifier link
- `unverified` — URL not yet verified

### Numerical Data Only

Only datasets with verified numerical content (`verificationStatus: "verified"` and non-empty `numericColumns`) are returned in search results.

## Development

```bash
# Install dependencies
npm install

# Build TypeScript declarations
npm run build

# Validate all schemas
npm run validate

# Run tests
npm test
```

## Adding New Schemas

1. Create JSON Schema in `src/schemas/`
2. Add TypeScript types in `src/types/index.ts`
3. Create validation function in `src/validation/`
4. Export from `src/index.ts`
5. Add tests in `tests/`
6. Run `npm run validate` and `npm test`

## Versioning

Contracts follow semantic versioning. Breaking changes to schemas require a major version bump.

## License

MIT