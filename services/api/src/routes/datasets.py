"""Dataset routes - Metadata, schema, and preview."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog
from typing import List, Optional

from services.api.src.config import settings
from services.api.src.database import get_db_session

router = APIRouter()
logger = structlog.get_logger()


@router.get("/datasets/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get complete dataset metadata."""
    query = """
        SELECT
            d.*,
            pi.title AS investigation_title,
            pi.description AS investigation_description
        FROM datasets d
        JOIN psi_investigations pi ON pi.psi_id = d.psi_id
        WHERE d.dataset_id = $1
    """
    result = await db.execute(text(query), [dataset_id])
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Dataset not found: {dataset_id}",
                }
            },
        )

    return dict(row._mapping)


@router.get("/datasets/{dataset_id}/schema")
async def get_dataset_schema(
    dataset_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get dataset schema (columns, types, statistics)."""
    # First verify dataset exists
    dataset_check = await db.execute(
        text("SELECT id FROM datasets WHERE dataset_id = $1"),
        [dataset_id]
    )
    if not dataset_check.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Dataset not found: {dataset_id}",
                }
            },
        )

    # Get schema
    query = """
        SELECT
            column_name,
            column_type,
            description,
            unit,
            nullable,
            sample_values,
            statistics,
            ordinal_position
        FROM dataset_schemas
        WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
        ORDER BY ordinal_position
    """
    result = await db.execute(text(query), [dataset_id])
    columns = [dict(row._mapping) for row in result.fetchall()]

    # Get profile info
    profile_query = """
        SELECT row_count, byte_size, profiled_at, profile_version
        FROM dataset_profiles
        WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
    """
    profile_result = await db.execute(text(profile_query), [dataset_id])
    profile = profile_result.fetchone()

    return {
        "datasetId": dataset_id,
        "columns": columns,
        "rowCount": profile.row_count if profile else None,
        "byteSize": profile.byte_size if profile else None,
        "profiledAt": profile.profiled_at.isoformat() if profile and profile.profiled_at else None,
        "profileVersion": profile.profile_version if profile else None,
    }


@router.get("/datasets/{dataset_id}/preview")
async def get_dataset_preview(
    dataset_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    """Get a bounded preview of dataset rows."""
    # Verify dataset exists and get table name
    dataset_query = """
        SELECT id, format FROM datasets WHERE dataset_id = $1
    """
    dataset_result = await db.execute(text(dataset_query), [dataset_id])
    dataset = dataset_result.fetchone()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Dataset not found: {dataset_id}",
                }
            },
        )

    # Get column info
    columns_query = """
        SELECT column_name, column_type, description, unit, nullable
        FROM dataset_schemas
        WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
        ORDER BY ordinal_position
    """
    columns_result = await db.execute(text(columns_query), [dataset_id])
    columns = [dict(row._mapping) for row in columns_result.fetchall()]

    # Get total row count
    profile_query = """
        SELECT row_count FROM dataset_profiles
        WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
    """
    profile_result = await db.execute(text(profile_query), [dataset_id])
    profile = profile_result.fetchone()
    total_rows = profile.row_count if profile else 0

    return {
        "datasetId": dataset_id,
        "columns": columns,
        "rows": [],  # Would be populated from actual data connector
        "totalRows": total_rows,
        "returnedRows": 0,
        "offset": offset,
        "limit": limit,
        "warnings": ["Preview not available - data connector not configured for this dataset"],
    }