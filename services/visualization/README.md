# Visualization Service

Interactive chart generation for NASA PSI Combustion Science datasets. Generates Vega-Lite specifications and data for bar, line, scatter, and histogram charts.

## Features

- **Chart Types**: Bar, Line, Scatter, Histogram
- **Data Connectors**: HTTP/HTTPS (CSV, Parquet, JSON, Excel) with domain allowlisting
- **Column Type Validation**: Automatic type inference and chart compatibility checking
- **Vega-Lite Output**: Standard visualization grammar for rendering
- **Sampling & Limits**: Row limits, memory limits, time limits for performance
- **Security**: SSRF protection, domain allowlisting, no arbitrary data download

## Architecture

```
services/visualization/
├── src/
│   ├── charts/           # Chart engine (Altair/Vega-Lite)
│   ├── connectors/       # Data connectors (HTTP, Parquet)
│   ├── validation/       # Column type validation & chart compatibility
│   ├── visualization_service.py  # Main orchestration
│   ├── config.py         # Configuration
│   └── cli.py            # Command-line interface
├── tests/                # Unit tests
├── pyproject.toml        # Dependencies
└── README.md
```

## Installation

```bash
cd services/visualization
pip install -e ".[dev]"
```

## Configuration

Environment variables:
- `DATABASE_URL` - PostgreSQL connection string
- `ALLOWED_DATA_DOMAINS` - Comma-separated allowed domains (default: psi.nasa.gov, raw.githubusercontent.com, data.nasa.gov)
- `MAX_CHART_ROWS` - Max rows for chart data (default: 10000)
- `MAX_CHART_MEMORY_MB` - Memory limit (default: 256)
- `MAX_CHART_TIME_SECONDS` - Time limit (default: 30)

## Usage

### Generate Chart
```bash
visualization chart psi-20-bre-temperature-csv bar \
  --x-axis category \
  --y-axis temperature \
  --group-by experiment \
  --limit 1000 \
  --title "Temperature by Category" \
  --output json
```

### Preview Dataset
```bash
visualization preview psi-20-bre-temperature-csv --limit 100
```

### Get Column Info
```bash
visualization columns psi-20-bre-temperature-csv
```

### Validate Chart Compatibility
```bash
visualization validate psi-20-bre-temperature-csv scatter \
  --x-axis pressure \
  --y-axis temperature
```

### Get Suggested Charts
```bash
visualization suggest psi-20-bre-temperature-csv
```

### Test Connector
```bash
visualization test-connector https://example.com/data.csv --limit 100
```

### Health Check
```bash
visualization health
```

## Chart Compatibility Rules

| Chart Type | X-Axis | Y-Axis | Group By |
|------------|--------|--------|----------|
| Bar | Categorical, Datetime, Text, Boolean | Numeric | Categorical, Text, Boolean |
| Line | Datetime, Numeric, Categorical | Numeric | Categorical, Text, Boolean |
| Scatter | Numeric, Datetime | Numeric | Categorical, Text, Boolean |
| Histogram | Numeric, Datetime | (ignored - count) | Categorical, Text, Boolean |

## API Contract

Implements the visualization contract from `@enigma-sac/contracts`:

- `POST /api/v1/charts/preview` - Generate chart preview
- Request: `ChartPreviewRequest` with datasetId, chartType, xAxis, yAxis, groupBy, filters, options
- Response: `ChartPreviewResponse` with spec, data, columns, warnings, metadata

## Output Format

```json
{
  "datasetId": "psi-20-bre-temperature-csv",
  "chartType": "bar",
  "spec": {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "mark": "bar",
    "encoding": {
      "x": {"field": "category", "type": "nominal", "title": "Category"},
      "y": {"field": "temperature", "type": "quantitative", "title": "Temperature (K)"},
      "color": {"field": "experiment", "type": "nominal", "title": "Experiment"}
    },
    "width": 800,
    "height": 400
  },
  "data": [
    {"category": "A", "temperature": 1500, "experiment": "exp_1"},
    ...
  ],
  "columns": {
    "x": {"name": "category", "type": "categorical", ...},
    "y": {"name": "temperature", "type": "numeric", "unit": "K", ...},
    "groupBy": {"name": "experiment", "type": "categorical", ...}
  },
  "warnings": [],
  "metadata": {
    "rowCount": 15420,
    "filteredRowCount": 1000,
    "processingTimeMs": 45.2,
    "memoryUsedBytes": 2048576
  }
}
```

## Testing

```bash
cd services/visualization
pytest tests/ -v
```

## Security

- **SSRF Protection**: Domain allowlisting, no private IPs
- **No Arbitrary Download**: Only cataloged datasets
- **Input Validation**: All chart parameters validated
- **Resource Limits**: Row, memory, and time limits enforced