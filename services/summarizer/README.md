# Summarizer Service

Evidence-based dataset summarization for NASA PSI Combustion Science datasets. Generates summaries using only verifiable metadata and computed statistics - never invents facts.

## Features

- **Dataset Profiling**: Computes comprehensive statistics (numeric, categorical, datetime, text, boolean)
- **LLM-based Summarization**: Uses OpenAI, Anthropic, or Ollama with strict evidence-based prompts
- **Descriptive Fallback**: Template-based summaries when LLM unavailable or statistics insufficient
- **Evidence-based**: Every claim traced to source (metadata or computed_statistics)
- **Audit Trail**: Logs generation with catalog version, profiling version, tokens used
- **Security**: SSRF protection, domain allowlisting, no arbitrary data download

## Architecture

```
services/summarizer/
├── src/
│   ├── profiling/          # Dataset profiling & statistics
│   ├── llm/                # LLM clients (OpenAI, Anthropic, Ollama)
│   ├── prompts/            # Prompt templates & parsing
│   ├── summarizer_service.py  # Main orchestration
│   ├── config.py           # Configuration
│   └── cli.py              # Command-line interface
├── tests/                  # Unit tests
├── pyproject.toml          # Dependencies
└── README.md
```

## Installation

```bash
cd services/summarizer
pip install -e ".[dev]"
```

## Configuration

Environment variables:
- `DATABASE_URL` - PostgreSQL connection string
- `LLM_PROVIDER` - openai, anthropic, ollama, local
- `LLM_API_KEY` - API key for OpenAI/Anthropic
- `LLM_MODEL` - Model name (gpt-4-turbo-preview, claude-3-opus, etc.)
- `LLM_API_URL` - For Ollama/local (default: http://localhost:11434)
- `MAX_PROFILE_ROWS` - Max rows to profile (default: 100000)
- `MAX_PROFILE_MEMORY_MB` - Memory limit (default: 512)
- `SUMMARY_MAX_LENGTH` - Max summary length (default: 1000)

## Usage

### Generate Summary
```bash
summarizer summarize psi-20-bre-temperature-csv \
  --include-stats \
  --max-length 1000 \
  --output json
```

### Profile Dataset
```bash
summarizer profile psi-20-bre-temperature-csv --sample-size 10000
```

### Test Prompt
```bash
summarizer test-prompt
```

### Health Check
```bash
summarizer health
```

### Initialize LLM
```bash
summarizer init-llm
```

## Summary Output Format

```json
{
  "datasetId": "psi-20-bre-temperature-csv",
  "title": "BRE Flame Temperature Measurements Summary",
  "executiveSummary": "This dataset contains temperature measurements...",
  "keyVariables": ["temperature_k", "time_s", "experiment_id"],
  "coverage": {
    "temporal": "2019-2021",
    "geographic": "ISS Microgravity",
    "rowCount": 15420
  },
  "findings": [
    {
      "description": "Temperature ranges from 800K to 2200K",
      "evidence": "min=800, max=2200, mean=1540",
      "source": "computed_statistics"
    }
  ],
  "limitations": ["Limited to gaseous fuel experiments"],
  "warnings": ["Verification status: verified"],
  "sources": [
    {"type": "metadata", "reference": "PSI-20 investigation record"},
    {"type": "statistics", "reference": "column statistics for temperature_k"}
  ],
  "generatedAt": "2024-01-15T10:30:00Z",
  "catalogVersion": "1.0.0",
  "profilingVersion": "1.0.0",
  "generationTimeMs": 1250.5,
  "tokensUsed": 1234
}
```

## Prompt Design

### System Prompt
Enforces critical rules:
1. Never invent statistics or findings
2. Distinguish metadata vs computed statistics
3. Every claim must have source reference
4. List limitations and warnings

### User Prompt Template
Provides verifiable facts:
- Dataset metadata (name, description, PSI ID, format, URL)
- Column profiles with statistics
- Row count, tags, verification status

### Output Parsing
Structured parsing of LLM response into:
- Title, executive summary, key variables
- Coverage (temporal, geographic, row count)
- Findings (description, evidence, source)
- Limitations, warnings, sources

## Profiling Statistics

| Column Type | Statistics Computed |
|-------------|---------------------|
| Numeric | min, max, mean, median, std, q1, q3, IQR, skewness, kurtosis |
| Categorical | top values, entropy |
| Datetime | min date, max date, range (days) |
| Text | avg/min/max length |
| Boolean | true/false counts |

## Security

- **SSRF Protection**: Domain allowlisting, no private IPs
- **No Arbitrary Download**: Only cataloged datasets
- **Input Validation**: All LLM inputs sanitized
- **Audit Logging**: Every generation logged with version info

## Testing

```bash
cd services/summarizer
pytest tests/ -v
```

## API Contract

Implements the summarization contract from `@enigma-sac/contracts`:

- `POST /api/v1/datasets/{id}/summary` - Generate summary
- Request: `{datasetId, options: {includeStatistics, maxLength}}`
- Response: SummaryResponse with findings, sources, metadata