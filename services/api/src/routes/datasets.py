"""Dataset routes - Metadata, schema, and preview."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import text
import structlog
from typing import List, Optional

from services.api.src.config import settings
from services.api.src.database import get_db_context

router = APIRouter()
logger = structlog.get_logger()


@router.get("/datasets/{dataset_id}")
async def get_dataset(
    dataset_id: str,
) -> dict:
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
    async with get_db_context() as conn:
        row = await conn.fetchrow(query, dataset_id)

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

    return dict(row)


@router.get("/datasets/{dataset_id}/schema")
async def get_dataset_schema(
    dataset_id: str,
) -> dict:
    """Get dataset schema (columns, types, statistics)."""
    async with get_db_context() as conn:
        # First verify dataset exists
        dataset_check = await conn.fetchrow(
            "SELECT id FROM datasets WHERE dataset_id = $1",
            dataset_id
        )
        if not dataset_check:
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
        columns_rows = await conn.fetch(query, dataset_id)
        columns = [dict(row) for row in columns_rows]

        # Get profile info
        profile_query = """
            SELECT row_count, byte_size, (to_jsonb(dp)->>'profiled_at')::timestamptz AS profiled_at, profile_version
            FROM dataset_profiles dp
            WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
        """
        profile = await conn.fetchrow(profile_query, dataset_id)

    return {
        "datasetId": dataset_id,
        "columns": columns,
        "rowCount": profile["row_count"] if profile else None,
        "byteSize": profile["byte_size"] if profile else None,
        "profiledAt": profile["profiled_at"].isoformat() if profile and profile["profiled_at"] else None,
        "profileVersion": profile["profile_version"] if profile else None,
    }


@router.get("/datasets/{dataset_id}/preview")
async def get_dataset_preview(
    dataset_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """Get a bounded preview of dataset rows."""
    async with get_db_context() as conn:
        # Verify dataset exists and get table name
        dataset_query = """
            SELECT id, format FROM datasets WHERE dataset_id = $1
        """
        dataset = await conn.fetchrow(dataset_query, dataset_id)

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
        columns_rows = await conn.fetch(columns_query, dataset_id)
        columns = [dict(row) for row in columns_rows]

        # Get total row count
        profile_query = """
            SELECT row_count FROM dataset_profiles
            WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
        """
        profile = await conn.fetchrow(profile_query, dataset_id)
        total_rows = profile["row_count"] if profile else 0

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