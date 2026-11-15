#!/usr/bin/env python3
"""
Ingest synthetic data into the database and generate embeddings.

This script:
1. Reads the synthetic CSV files
2. Creates dataset records in the database
3. Generates embeddings for each dataset using the embedding service
4. Stores embeddings in the vector index
"""

import asyncio
import hashlib
import json
import re
import uuid
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import structlog
from pgvector.asyncpg import register_vector

import asyncpg

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.search.src.embedding.http_client import embed_text
from services.search.src.config import settings
from services.catalog.src.models.catalog import (
    DataFormat,
    URLType,
    VerificationStatus,
    AccessPolicy,
    ColumnType,
)
from services.catalog.src.validation.numerical_detector import NumericalDetector

# Use settings from config (which loads from .env)
CATALOG_VERSION = settings.CATALOG_VERSION
EMBEDDING_MODEL = settings.EMBEDDING_MODEL
EMBEDDING_VERSION = settings.EMBEDDING_VERSION

logger = structlog.get_logger()

SYNTHETIC_DATA_DIR = Path(__file__).parent.parent / "data" / "synthetic"

# Dataset metadata matching the seed SQL
DATASET_METADATA = [
    {
        "dataset_id": "psi-20-bre-temperature-csv",
        "psi_id": "PSI-20",
        "name": "BRE Flame Temperature Measurements",
        "description": "Temperature measurements from Burning Rate Emulator (BRE) experiments on ISS. Includes time-series temperature data for various flow conditions and fuel types.",
        "filename": "psi-20-bre-temperature-csv.csv",
        "url_type": URLType.DIRECT_DOWNLOAD,
        "format": DataFormat.CSV,
        "source": "NASA Physical Sciences Informatics (Synthetic)",
        "license": "Public Domain",
        "access_policy": AccessPolicy.PUBLIC,
        "coverage_temporal": "2019-2021",
        "coverage_geographic": "ISS Microgravity",
        "tags": ["temperature", "time-series", "gaseous-fuels", "bre", "acme"],
    },
    {
        "dataset_id": "psi-21-cld-soot-csv",
        "psi_id": "PSI-21",
        "name": "CLD Flame Soot Volume Fraction Data",
        "description": "Soot volume fraction and temperature measurements from Coflow Laminar Diffusion Flame experiments. Includes radial profiles at multiple axial positions.",
        "filename": "psi-21-cld-soot-csv.csv",
        "url_type": URLType.DIRECT_DOWNLOAD,
        "format": DataFormat.CSV,
        "source": "NASA Physical Sciences Informatics (Synthetic)",
        "license": "Public Domain",
        "access_policy": AccessPolicy.PUBLIC,
        "coverage_temporal": "2019-2021",
        "coverage_geographic": "ISS Microgravity",
        "tags": ["soot", "diffusion-flames", "radial-profiles", "cld-flame", "acme"],
    },
    {
        "dataset_id": "psi-69-flex-droplet-extinction-csv",
        "psi_id": "PSI-69",
        "name": "FLEX Droplet Extinction Measurements",
        "description": "Droplet diameter and extinction data from Flame Extinguishment Experiment. Includes various fuel types, oxygen concentrations, and suppressant gases.",
        "filename": "psi-69-flex-droplet-extinction-csv.csv",
        "url_type": URLType.DIRECT_DOWNLOAD,
        "format": DataFormat.CSV,
        "source": "NASA Physical Sciences Informatics (Synthetic)",
        "license": "Public Domain",
        "access_policy": AccessPolicy.PUBLIC,
        "coverage_temporal": "2010-2017",
        "coverage_geographic": "ISS Microgravity",
        "tags": ["droplets", "extinction", "suppressants", "flex", "liquid-fuels"],
    },
    {
        "dataset_id": "psi-39-cfi-cool-flame-csv",
        "psi_id": "PSI-39",
        "name": "CFI Cool Flame Droplet Temperature Data",
        "description": "Temperature measurements showing cool flame behavior in liquid fuel droplets. Captures transition from hot flame to cool flame combustion.",
        "filename": "psi-39-cfi-cool-flame-csv.csv",
        "url_type": URLType.DIRECT_DOWNLOAD,
        "format": DataFormat.CSV,
        "source": "NASA Physical Sciences Informatics (Synthetic)",
        "license": "Public Domain",
        "access_policy": AccessPolicy.PUBLIC,
        "coverage_temporal": "2010-2017",
        "coverage_geographic": "ISS Microgravity",
        "tags": ["cool-flames", "droplets", "temperature", "low-temperature-chemistry", "cfi"],
    },
    {
        "dataset_id": "psi-107-spice-smoke-point-csv",
        "psi_id": "PSI-107",
        "name": "SPICE Smoke Point and Flame Length Data",
        "description": "Smoke point measurements for laminar jet diffusion flames. 526 flame conditions with burner diameter, coflow velocity, and smoke onset data.",
        "filename": "psi-107-spice-smoke-point-csv.csv",
        "url_type": URLType.DIRECT_DOWNLOAD,
        "format": DataFormat.CSV,
        "source": "NASA Physical Sciences Informatics (Synthetic)",
        "license": "Public Domain",
        "access_policy": AccessPolicy.PUBLIC,
        "coverage_temporal": "2015-2017",
        "coverage_geographic": "ISS Microgravity",
        "tags": ["smoke-point", "diffusion-flames", "coflow", "spice", "soot-onset"],
    },
    {
        "dataset_id": "psi-26-bass-solid-flame-spread-csv",
        "psi_id": "PSI-26",
        "name": "BASS Solid Fuel Flame Spread Rates",
        "description": "Flame spread rate measurements for various solid materials in microgravity. Includes PMMA, cotton, and other spacecraft materials.",
        "filename": "psi-26-bass-solid-flame-spread-csv.csv",
        "url_type": URLType.DIRECT_DOWNLOAD,
        "format": DataFormat.CSV,
        "source": "NASA Physical Sciences Informatics (Synthetic)",
        "license": "Public Domain",
        "access_policy": AccessPolicy.PUBLIC,
        "coverage_temporal": "2011-2017",
        "coverage_geographic": "ISS Microgravity",
        "tags": ["solid-fuels", "flame-spread", "bass", "material-flammability", "microgravity"],
    },
    {
        "dataset_id": "psi-102-same-smoke-aerosol-csv",
        "psi_id": "PSI-102",
        "name": "SAME Smoke Aerosol Size Distribution Data",
        "description": "Particle size distribution measurements from Smoke Aerosol Measurement Experiment. Includes count median diameter and geometric standard deviation.",
        "filename": "psi-102-same-smoke-aerosol-csv.csv",
        "url_type": URLType.DIRECT_DOWNLOAD,
        "format": DataFormat.CSV,
        "source": "NASA Physical Sciences Informatics (Synthetic)",
        "license": "Public Domain",
        "access_policy": AccessPolicy.PUBLIC,
        "coverage_temporal": "2011-2017",
        "coverage_geographic": "ISS Microgravity",
        "tags": ["smoke", "aerosols", "particle-size", "same", "detector-response"],
    },
    {
        "dataset_id": "psi-98-saffire-i-fabric-burn-csv",
        "psi_id": "PSI-98",
        "name": "SAFFIRE-I Large Fabric Burn Sensor Data",
        "description": "Temperature, pressure, oxygen, and CO2 sensor data from the SAFFIRE-I large fabric burn experiment on Cygnus spacecraft.",
        "filename": "psi-98-saffire-i-fabric-burn-csv.csv",
        "url_type": URLType.DIRECT_DOWNLOAD,
        "format": DataFormat.CSV,
        "source": "NASA Physical Sciences Informatics (Synthetic)",
        "license": "Public Domain",
        "access_policy": AccessPolicy.PUBLIC,
        "coverage_temporal": "2016",
        "coverage_geographic": "Cygnus Spacecraft Microgravity",
        "tags": ["saffire", "fabric-burn", "large-scale", "cygnus", "sensor-data", "fire-safety"],
    },
    {
        "dataset_id": "psi-159-cfig-gaseous-cool-flame-csv",
        "psi_id": "PSI-159",
        "name": "CFI-G Gaseous Cool Flame Temperature Data",
        "description": "Temperature and species concentration data from Cool Flames Investigation with Gases. Shows stable low-temperature oxidation regimes.",
        "filename": "psi-159-cfig-gaseous-cool-flame-csv.csv",
        "url_type": URLType.DIRECT_DOWNLOAD,
        "format": DataFormat.CSV,
        "source": "NASA Physical Sciences Informatics (Synthetic)",
        "license": "Public Domain",
        "access_policy": AccessPolicy.PUBLIC,
        "coverage_temporal": "2021-2022",
        "coverage_geographic": "ISS Microgravity",
        "tags": ["cool-flames", "gaseous-fuels", "low-temperature-oxidation", "cfig", "acme"],
    },
    {
        "dataset_id": "psi-106-slice-liftoff-csv",
        "psi_id": "PSI-106",
        "name": "SLICE Flame Liftoff and Structure Data",
        "description": "Flame liftoff height and structure measurements for gas jet diffusion flames in microgravity. Various burner diameters and flow rates.",
        "filename": "psi-106-slice-liftoff-csv.csv",
        "url_type": URLType.DIRECT_DOWNLOAD,
        "format": DataFormat.CSV,
        "source": "NASA Physical Sciences Informatics (Synthetic)",
        "license": "Public Domain",
        "access_policy": AccessPolicy.PUBLIC,
        "coverage_temporal": "2015-2017",
        "coverage_geographic": "ISS Microgravity",
        "tags": ["liftoff", "diffusion-flames", "gas-jet", "slice", "flame-structure"],
    },
]


def generate_stable_dataset_id(psi_id: str, filename: str, url: str) -> str:
    """Generate a stable dataset ID from metadata."""
    content = f"{psi_id}|{filename}|{url}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def infer_column_type(series: pd.Series) -> ColumnType:
    """Infer column type from pandas series."""
    total_count = series.notna().sum()
    if total_count == 0:
        return ColumnType.TEXT

    unique = series.dropna().unique()

    # Try numeric
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() / total_count > 0.8:
        return ColumnType.NUMERIC

    # Try datetime
    try:
        dt = pd.to_datetime(series, errors="coerce")
        if dt.notna().sum() / total_count > 0.8:
            return ColumnType.DATETIME
    except Exception:
        pass

    # Check boolean
    if len(unique) <= 2:
        bool_vals = {"true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"}
        if all(str(v).lower() in bool_vals for v in unique):
            return ColumnType.BOOLEAN

    # Check categorical
    unique_ratio = len(unique) / total_count
    threshold = 0.1 if total_count < 100 else 0.05
    if (unique_ratio < threshold and len(unique) < 50) or \
       (total_count < 20 and len(unique) <= 5):
        return ColumnType.CATEGORICAL

    return ColumnType.TEXT


def compute_column_statistics(series: pd.Series, col_type: ColumnType) -> Optional[dict]:
    """Compute statistics for a column."""
    if col_type != ColumnType.NUMERIC:
        return None

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() == 0:
        return None

    return {
        "count": int(numeric.notna().sum()),
        "null_count": int(numeric.isna().sum()),
        "min": float(numeric.min()),
        "max": float(numeric.max()),
        "mean": float(numeric.mean()),
        "median": float(numeric.median()),
        "std": float(numeric.std()),
        "q1": float(numeric.quantile(0.25)),
        "q2": float(numeric.quantile(0.5)),
        "q3": float(numeric.quantile(0.75)),
    }


async def get_embedding(text: str, embedding_api_url: str) -> list[float]:
    """Index documents as passages; searches use query embeddings."""
    return await embed_text(text, settings, input_type="passage", api_url=embedding_api_url)


async def ingest_dataset(
    conn: asyncpg.Connection,
    metadata: dict,
    embedding_api_url: str,
) -> bool:
    """Ingest a single dataset."""
    dataset_id = metadata["dataset_id"]
    filename = metadata["filename"]
    filepath = SYNTHETIC_DATA_DIR / filename
    
    if not filepath.exists():
        logger.error("file_not_found", dataset_id=dataset_id, filepath=str(filepath))
        return False

    # Read CSV
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        logger.error("csv_read_failed", dataset_id=dataset_id, error=str(e))
        return False

    # Detect numerical content
    detector = NumericalDetector()
    try:
        detection = detector.detect_from_bytes(filepath.read_bytes(), filename)
    except Exception as e:
        logger.error("numerical_detection_failed", dataset_id=dataset_id, error=str(e))
        return False

    if not detection.has_numerical_data:
        logger.warning("no_numerical_data", dataset_id=dataset_id)
        return False

    # Generate embedding for the dataset description
    embedding_text = f"{metadata['name']}. {metadata['description']}. Columns: {', '.join(df.columns)}"
    try:
        embedding = await get_embedding(embedding_text, embedding_api_url)
    except Exception as e:
        logger.error("embedding_generation_failed", dataset_id=dataset_id, error=str(e))
        return False

    # Build file URL (local path)
    file_url = f"file://{filepath.absolute()}"

    # Support both the SQL initialization schema and the older ORM schema.
    column_types = {
        row["column_name"]: row["data_type"]
        for row in await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'datasets'"
        )
    }
    existing_id = await conn.fetchval(
        "SELECT id FROM datasets WHERE dataset_id = $1", dataset_id
    )
    record_id = existing_id or uuid.uuid4()
    if column_types["id"] != "uuid":
        record_id = str(record_id)

    values = {
        "id": record_id,
        "dataset_id": dataset_id,
        "psi_id": metadata["psi_id"],
        "name": metadata["name"],
        "description": metadata["description"],
        "url": file_url,
        "url_type": metadata["url_type"].value,
        "format": metadata["format"].value,
        "numeric_columns": detection.numeric_columns,
        "source": metadata["source"],
        "license": metadata["license"],
        "access_policy": metadata["access_policy"].value,
        "coverage_temporal": metadata["coverage_temporal"],
        "coverage_geographic": metadata["coverage_geographic"],
        "catalog_version": CATALOG_VERSION,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_version": EMBEDDING_VERSION,
        "verification_status": VerificationStatus.VERIFIED.value,
        "tags": metadata["tags"],
        "provenance_investigation_url": f"https://psi.nasa.gov/physci/repo/data/investigations/{metadata['psi_id']}",
        "provenance_dataset_url": file_url,
    }
    for column in ("numeric_columns", "tags"):
        if column_types[column] in ("json", "jsonb"):
            values[column] = json.dumps(values[column])
    columns = list(values)
    placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
    updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in columns if column != "id")
    dataset_row = await conn.fetchrow(
        f"INSERT INTO datasets ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT (id) DO UPDATE SET {updates}, updated_at = NOW() RETURNING id",
        *values.values(),
    )

    dataset_db_id = dataset_row["id"]
    logger.info("dataset_inserted", dataset_id=dataset_id, db_id=dataset_db_id)

    # Insert schema
    for i, col in enumerate(df.columns):
        col_type = infer_column_type(df[col])
        statistics = compute_column_statistics(df[col], col_type)
        
        sample_values = None
        if col_type != ColumnType.TEXT:
            sample_vals = df[col].dropna().head(5).tolist()
            if sample_vals:
                # Convert to JSON string for PostgreSQL JSONB column
                sample_values = json.dumps(sample_vals)

        try:
            await conn.execute(
                """
                INSERT INTO dataset_schemas (
                    dataset_id, column_name, column_type, description, unit,
                    nullable, sample_values, statistics, ordinal_position, profile_version
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (dataset_id, column_name) DO UPDATE SET
                    column_type = EXCLUDED.column_type,
                    description = EXCLUDED.description,
                    unit = EXCLUDED.unit,
                    nullable = EXCLUDED.nullable,
                    sample_values = EXCLUDED.sample_values,
                    statistics = EXCLUDED.statistics,
                    ordinal_position = EXCLUDED.ordinal_position,
                    profile_version = EXCLUDED.profile_version
                """,
                dataset_db_id,
                col,
                col_type.value,
                None,  # description
                None,  # unit
                bool(df[col].isna().any()),
                sample_values,
                json.dumps(statistics) if statistics else None,
                i,
                "1.0.0",
            )
        except Exception as e:
            logger.error("schema_insert_failed", dataset_id=dataset_id, column=col, error=str(e))
            raise

    warnings_type = await conn.fetchval(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = 'dataset_profiles' "
        "AND column_name = 'warnings'"
    )
    profile_warnings = detection.warnings
    if warnings_type in ("text", "json", "jsonb"):
        profile_warnings = json.dumps(profile_warnings)

    # Insert profile
    try:
        await conn.execute(
            """
            INSERT INTO dataset_profiles (
                dataset_id, row_count, byte_size, column_count,
                profile_version, profiling_duration_ms, warnings
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (dataset_id) DO UPDATE SET
                row_count = EXCLUDED.row_count,
                byte_size = EXCLUDED.byte_size,
                column_count = EXCLUDED.column_count,
                profile_version = EXCLUDED.profile_version,
                profiling_duration_ms = EXCLUDED.profiling_duration_ms,
                warnings = EXCLUDED.warnings
            """,
            dataset_db_id,
            len(df),
            filepath.stat().st_size,
            len(df.columns),
            "1.0.0",
            None,
            profile_warnings,
        )
    except Exception as e:
        logger.error("profile_insert_failed", dataset_id=dataset_id, error=str(e))
        raise

    # Insert embedding
    try:
        # pgvector expects a list/array, not a string - pass the list directly
        await conn.execute(
            """
            INSERT INTO dataset_embeddings (dataset_id, embedding, model, version, content_hash)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (dataset_id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                model = EXCLUDED.model,
                version = EXCLUDED.version,
                content_hash = EXCLUDED.content_hash
            """,
            dataset_db_id,
            embedding,  # Pass list directly, asyncpg will handle vector conversion
            EMBEDDING_MODEL,
            EMBEDDING_VERSION,
            hashlib.sha256(embedding_text.encode()).hexdigest()[:64],
        )
    except Exception as e:
        logger.error("embedding_insert_failed", dataset_id=dataset_id, error=str(e))
        return False

    logger.info("dataset_fully_ingested", dataset_id=dataset_id, db_id=dataset_db_id)
    return True


async def seed_investigations(conn):
    """Load the repository's investigation metadata for either catalog schema."""
    seed_sql = (Path(__file__).parent.parent / "infra/init-db/02-seed-psi-investigations.sql").read_text()
    full_schema = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = 'psi_investigations' "
        "AND column_name = 'research_area')"
    )
    if full_schema:
        await conn.execute(seed_sql)
        return
    # The legacy table stores only identifiers, titles, descriptions and sector.
    pattern = r"\(\s*'(PSI-\d+)',\s*'((?:[^']|'')*)',\s*'((?:[^']|'')*)'"
    investigations = re.findall(pattern, seed_sql)
    if len(investigations) != 26:
        raise ValueError("Expected 26 investigations in the repository seed")
    for psi_id, title, description in investigations:
        await conn.execute(
            "INSERT INTO psi_investigations (psi_id, title, description, sector) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT (psi_id) DO NOTHING",
            psi_id, title.replace("''", "'"), description.replace("''", "'"), "Combustion Science",
        )


async def main():
    """Load all test datasets atomically; fail instead of leaving partial data."""
    database_url = settings.DATABASE_URL
    embedding_api_url = settings.EMBEDDING_API_URL
    logger.info("starting_synthetic_data_ingestion", embedding_model=EMBEDDING_MODEL)
    conn = await asyncpg.connect(database_url)
    try:
        await register_vector(conn)
        async with conn.transaction():
            await seed_investigations(conn)
            for metadata in DATASET_METADATA:
                if not await ingest_dataset(conn, metadata, embedding_api_url):
                    raise RuntimeError(f"Ingestion failed: {metadata['dataset_id']}")
        logger.info("ingestion_complete", successful=len(DATASET_METADATA), total=len(DATASET_METADATA))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
