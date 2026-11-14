"""
Visualization routes - Chart generation and preview
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog
import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from services.api.config import settings
from services.api.database import get_db_session

router = APIRouter()
logger = structlog.get_logger()


class ChartPreviewRequest(BaseModel):
    datasetId: str
    chartType: str = Field(..., pattern="^(bar|line|scatter|histogram)$")
    xAxis: str
    yAxis: Optional[str] = None
    groupBy: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


class ChartPreviewResponse(BaseModel):
    datasetId: str
    chartType: str
    spec: Dict[str, Any]
    data: List[Dict[str, Any]]
    columns: Dict[str, Any]
    warnings: List[str]
    metadata: Dict[str, Any]


@router.post("/charts/preview", response_model=ChartPreviewResponse)
async def generate_chart_preview(
    request: ChartPreviewRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ChartPreviewResponse:
    """
    Generate an interactive chart specification and data for the selected dataset.
    Validates column compatibility with the requested chart type.
    """
    start_time = time.time()

    logger.info(
        "chart_generation_started",
        dataset_id=request.datasetId,
        chart_type=request.chartType,
    )

    # Verify dataset exists
    dataset_query = """
        SELECT id FROM datasets WHERE dataset_id = $1
    """
    dataset_result = await db.execute(text(dataset_query), [request.datasetId])
    dataset = dataset_result.fetchone()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Dataset not found: {request.datasetId}",
                }
            },
        )

    # Get column information
    columns_query = """
        SELECT column_name, column_type, description, unit, nullable
        FROM dataset_schemas
        WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
        ORDER BY ordinal_position
    """
    columns_result = await db.execute(text(columns_query), [request.datasetId])
    columns = [dict(row._mapping) for row in columns_result.fetchall()]

    column_map = {c["column_name"]: c for c in columns}

    # Validate columns exist
    x_col = column_map.get(request.xAxis)
    if not x_col:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"X-axis column not found: {request.xAxis}",
                }
            },
        )

    y_col = None
    if request.yAxis:
        y_col = column_map.get(request.yAxis)
        if not y_col:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"Y-axis column not found: {request.yAxis}",
                    }
                },
            )

    group_col = None
    if request.groupBy:
        group_col = column_map.get(request.groupBy)
        if not group_col:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"Group-by column not found: {request.groupBy}",
                    }
                },
            )

    # Validate chart type compatibility
    warnings = validate_chart_compatibility(request.chartType, x_col, y_col, group_col)

    # Get profile for metadata
    profile_query = """
        SELECT row_count FROM dataset_profiles
        WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
    """
    profile_result = await db.execute(text(profile_query), [request.datasetId])
    profile = profile_result.fetchone()
    row_count = profile.row_count if profile else 0

    # Generate chart spec and sample data
    spec = generate_chart_spec(request, x_col, y_col, group_col)
    sample_data = generate_sample_data(request, x_col, y_col, group_col, columns)

    processing_time = round((time.time() - start_time) * 1000, 2)

    response = ChartPreviewResponse(
        datasetId=request.datasetId,
        chartType=request.chartType,
        spec=spec,
        data=sample_data,
        columns={
            "x": x_col,
            "y": y_col,
            "groupBy": group_col,
        },
        warnings=warnings,
        metadata={
            "rowCount": row_count,
            "filteredRowCount": len(sample_data),
            "processingTimeMs": processing_time,
            "memoryUsedBytes": len(str(sample_data)).encode().__len__(),
        },
    )

    logger.info(
        "chart_generation_completed",
        dataset_id=request.datasetId,
        chart_type=request.chartType,
        processing_time_ms=processing_time,
    )

    return response


def validate_chart_compatibility(
    chart_type: str,
    x_col: dict,
    y_col: Optional[dict],
    group_col: Optional[dict],
) -> List[str]:
    """Validate column compatibility with chart type."""
    warnings = []

    # Check x-axis
    if chart_type == "histogram":
        if x_col["column_type"] not in ("numeric", "datetime"):
            warnings.append(f"Histogram works best with numeric/datetime columns; x-axis is {x_col['column_type']}")
    else:
        # bar, line, scatter
        if x_col["column_type"] not in ("numeric", "datetime", "categorical"):
            warnings.append(f"X-axis type {x_col['column_type']} may not render well")

    # Check y-axis (required for bar, line, scatter)
    if chart_type in ("bar", "line", "scatter"):
        if not y_col:
            warnings.append(f"{chart_type} chart requires a Y-axis column")
        elif y_col["column_type"] != "numeric":
            warnings.append(f"Y-axis should be numeric for {chart_type} chart; got {y_col['column_type']}")

    # Check group-by
    if group_col and group_col["column_type"] not in ("categorical", "text"):
        warnings.append(f"Group-by column should be categorical; got {group_col['column_type']}")

    # Check for missing values
    for col, name in [(x_col, "X-axis"), (y_col, "Y-axis"), (group_col, "Group-by")]:
        if col and col.get("nullable"):
            warnings.append(f"{name} column '{col['column_name']}' contains missing values")

    return warnings


def generate_chart_spec(
    request: ChartPreviewRequest,
    x_col: dict,
    y_col: Optional[dict],
    group_col: Optional[dict],
) -> Dict[str, Any]:
    """Generate Vega-Lite chart specification."""
    options = request.options or {}
    chart_type = request.chartType

    # Base encoding
    x_encoding = {
        "field": x_col["column_name"],
        "type": map_column_type(x_col["column_type"]),
        "title": options.get("xLabel", x_col["column_name"]),
    }
    if x_col.get("unit"):
        x_encoding["title"] += f" ({x_col['unit']})"

    encoding = {"x": x_encoding}

    if chart_type == "histogram":
        encoding["x"]["bin"] = True
        encoding["y"] = {"aggregate": "count", "type": "quantitative", "title": "Count"}
        mark = "bar"
    else:
        if y_col:
            y_encoding = {
                "field": y_col["column_name"],
                "type": map_column_type(y_col["column_type"]),
                "title": options.get("yLabel", y_col["column_name"]),
            }
            if y_col.get("unit"):
                y_encoding["title"] += f" ({y_col['unit']})"

            # Apply aggregation if specified
            aggregation = options.get("aggregation", "none")
            if aggregation != "none":
                y_encoding["aggregate"] = aggregation

            encoding["y"] = y_encoding

        if group_col:
            encoding["color"] = {
                "field": group_col["column_name"],
                "type": "nominal",
                "title": group_col["column_name"],
            }

        # Mark type
        mark_map = {"bar": "bar", "line": "line", "scatter": "point"}
        mark = mark_map.get(chart_type, "point")

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "mark": mark,
        "encoding": encoding,
    }

    if options.get("title"):
        spec["title"] = options["title"]

    if options.get("width"):
        spec["width"] = options["width"]
    if options.get("height"):
        spec["height"] = options["height"]

    return spec


def map_column_type(col_type: str) -> str:
    """Map internal column type to Vega-Lite type."""
    mapping = {
        "numeric": "quantitative",
        "datetime": "temporal",
        "categorical": "nominal",
        "text": "nominal",
        "boolean": "nominal",
        "unknown": "quantitative",
    }
    return mapping.get(col_type, "quantitative")


def generate_sample_data(
    request: ChartPreviewRequest,
    x_col: dict,
    y_col: Optional[dict],
    group_col: Optional[dict],
    all_columns: List[dict],
) -> List[Dict[str, Any]]:
    """Generate sample data for chart preview.
    
    In production, this would query the actual data source.
    For now, return mock data based on column statistics.
    """
    options = request.options or {}
    limit = options.get("limit", 50)

    # Get statistics for numeric columns to generate realistic samples
    x_stats = x_col.get("statistics") if x_col else None
    y_stats = y_col.get("statistics") if y_col else None

    sample_data = []

    for i in range(min(limit, 20)):  # Limit to 20 sample points for preview
        row = {}

        # Generate x value
        if x_stats and x_col["column_type"] == "numeric":
            import random
            row[x_col["column_name"]] = round(
                random.uniform(x_stats.get("min", 0), x_stats.get("max", 100)), 2
            )
        elif x_col["column_type"] == "categorical":
            row[x_col["column_name"]] = f"Category_{i % 5}"
        elif x_col["column_type"] == "datetime":
            row[x_col["column_name"]] = f"2024-01-{(i % 28) + 1:02d}"
        else:
            row[x_col["column_name"]] = i

        # Generate y value
        if y_col and y_stats and y_col["column_type"] == "numeric":
            import random
            row[y_col["column_name"]] = round(
                random.uniform(y_stats.get("min", 0), y_stats.get("max", 100)), 2
            )
        elif y_col:
            row[y_col["column_name"]] = i * 10

        # Generate group-by value
        if group_col:
            if group_col["column_type"] == "categorical":
                row[group_col["column_name"]] = f"Group_{i % 3}"
            else:
                row[group_col["column_name"]] = i

        sample_data.append(row)

    return sample_data