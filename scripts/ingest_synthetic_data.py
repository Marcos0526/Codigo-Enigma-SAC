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
import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import structlog
from pgvector.asyncpg import register_vector

import asyncpg

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    """Get embedding from the embedding service."""
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            embedding_api_url,
            json={"texts": [text]},
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]


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

    # Insert dataset
    try:
        dataset_row = await conn.fetchrow(
            """
            INSERT INTO datasets (
                dataset_id, psi_id, name, description, url, url_type, format,
                numeric_columns, source, license, access_policy,
                coverage_temporal, coverage_geographic, catalog_version,
                embedding_model, embedding_version, verification_status,
                verified_at, tags, provenance_investigation_url,
                provenance_dataset_url
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
            ON CONFLICT (dataset_id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                url = EXCLUDED.url,
                url_type = EXCLUDED.url_type,
                format = EXCLUDED.format,
                numeric_columns = EXCLUDED.numeric_columns,
                verification_status = EXCLUDED.verification_status,
                verified_at = EXCLUDED.verified_at,
                updated_at = NOW()
            RETURNING id
            """,
            dataset_id,
            metadata["psi_id"],
            metadata["name"],
            metadata["description"],
            file_url,
            metadata["url_type"].value,
            metadata["format"].value,
            detection.numeric_columns,
            metadata["source"],
            metadata["license"],
            metadata["access_policy"].value,
            metadata["coverage_temporal"],
            metadata["coverage_geographic"],
            CATALOG_VERSION,
            EMBEDDING_MODEL,
            EMBEDDING_VERSION,
            VerificationStatus.VERIFIED.value,
            None,  # verified_at
            metadata["tags"],
            f"https://psi.nasa.gov/physci/repo/data/investigations/{metadata['psi_id']}",
            file_url,
        )
    except Exception as e:
        logger.error("dataset_insert_failed", dataset_id=dataset_id, error=str(e))
        return False

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
            detection.warnings,
        )
    except Exception as e:
        logger.error("profile_insert_failed", dataset_id=dataset_id, error=str(e))

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


async def main():
    """Main ingestion function."""
    # Get database URL from environment or use default
    database_url = os.getenv("DATABASE_URL", "postgresql://enigma:enigma@localhost:5432/enigma_sac")
    embedding_api_url = os.getenv("EMBEDDING_API_URL", "http://localhost:8080/embed")

    logger.info("starting_synthetic_data_ingestion", 
                database_url=database_url,
                embedding_api_url=embedding_api_url)

    # Connect to database
    conn = await asyncpg.connect(database_url)
    await register_vector(conn)

    try:
        success_count = 0
        for metadata in DATASET_METADATA:
            success = await ingest_dataset(conn, metadata, embedding_api_url)
            if success:
                success_count += 1

        logger.info("ingestion_complete", successful=success_count, total=len(DATASET_METADATA))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())