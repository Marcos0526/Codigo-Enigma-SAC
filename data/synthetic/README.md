# Synthetic Data for NASA PSI Combustion Science

This directory contains synthetic CSV datasets generated for testing and development of the Enigma SAC semantic search system.

## Datasets

| Dataset ID | PSI Investigation | Description | Rows | Columns |
|------------|-------------------|-------------|------|---------|
| psi-20-bre-temperature-csv | PSI-20 | BRE Flame Temperature Measurements | 5,000 | 7 |
| psi-21-cld-soot-csv | PSI-21 | CLD Flame Soot Volume Fraction Data | 3,000 | 5 |
| psi-69-flex-droplet-extinction-csv | PSI-69 | FLEX Droplet Extinction Measurements | 4,000 | 8 |
| psi-39-cfi-cool-flame-csv | PSI-39 | CFI Cool Flame Droplet Temperature Data | 3,500 | 6 |
| psi-107-spice-smoke-point-csv | PSI-107 | SPICE Smoke Point and Flame Length Data | 1,440 | 6 |
| psi-26-bass-solid-flame-spread-csv | PSI-26 | BASS Solid Fuel Flame Spread Rates | 2,500 | 7 |
| psi-102-same-smoke-aerosol-csv | PSI-102 | SAME Smoke Aerosol Size Distribution Data | 1,998 | 7 |
| psi-98-saffire-i-fabric-burn-csv | PSI-98 | SAFFIRE-I Large Fabric Burn Sensor Data | 5,000 | 8 |
| psi-159-cfig-gaseous-cool-flame-csv | PSI-159 | CFI-G Gaseous Cool Flame Temperature Data | 3,000 | 7 |
| psi-106-slice-liftoff-csv | PSI-106 | SLICE Flame Liftoff and Structure Data | 800 | 7 |

## Generation

The data is generated using `scripts/generate_synthetic_data.py` with realistic physics-based models:

- **BRE Temperature**: Time-series temperature with flow oscillations
- **CLD Soot**: Radial profiles with axial decay
- **FLEX Droplets**: d²-law combustion with suppressants
- **CFI Cool Flames**: Hot-to-cool flame transition dynamics
- **SPICE Smoke Point**: 526 flame conditions with burner/coflow variations
- **BASS Flame Spread**: Material-specific spread rate models
- **SAME Aerosols**: Log-normal particle size distributions
- **SAFFIRE Sensor Data**: Time-series from large fabric burn
- **CFI-G Gaseous Cool Flames**: Species concentrations with oscillations
- **SLICE Liftoff**: Gas jet diffusion flame liftoff correlations

## Ingestion

Run from the repository root. The loader reads `DATABASE_URL`, `EMBEDDING_API_URL`, and model metadata from `.env` (environment variables override them). Start PostgreSQL and the embedding service before loading:

```bash
python3 scripts/ingest_synthetic_data.py
```

The loader seeds the 26 investigation records and loads all ten synthetic datasets, column statistics, profiles, and embeddings in one transaction. Repeating the command updates existing datasets without duplicating them. It supports both the SQL initialization schema (`TEXT[]`) and the older ORM schema (`JSONB`). A failed load rolls back the whole transaction. These files are development data, not NASA experimental measurements.

## Testing Search

```bash
export DATABASE_URL=postgresql://enigma:enigma@localhost:5432/enigma_sac
export EMBEDDING_API_URL=http://localhost:8080/embed
python scripts/test_search.py
```

## Check Database State

```bash
export DATABASE_URL=postgresql://enigma:enigma@localhost:5432/enigma_sac
python scripts/check_database.py
```