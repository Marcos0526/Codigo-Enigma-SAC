"""Visualization service main module."""

import structlog
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

import asyncpg
import pandas as pd

from services.visualization.src.config import settings
from services.visualization.src.connectors.data_connector import (
    create_connector,
    DataPreview,
)
from services.visualization.src.charts.chart_engine import (
    ChartEngine,
    ChartSpec,
    ChartType,
)
from services.visualization.src.validation.column_validator import (
    ColumnValidator,
    ColumnInfo,
    ChartCompatibility,
    ChartType as ValidatorChartType,
    create_column_validator,
)

logger = structlog.get_logger()


@dataclass
class ChartPreviewRequest:
    """Request for chart preview."""
    dataset_id: str
    chart_type: str
    x_axis: str
    y_axis: Optional[str] = None
    group_by: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


@dataclass
class ChartPreviewResponse:
    """Chart preview response."""
    dataset_id: str
    chart_type: str
    spec: Dict[str, Any]
    data: List[Dict[str, Any]]
    columns: Dict[str, Any]
    warnings: List[str]
    metadata: Dict[str, Any]


class VisualizationService:
    """Main visualization service orchestrating data fetching and chart generation."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.chart_engine = ChartEngine()
        self.column_validator = create_column_validator()

    async def generate_chart_preview(
        self,
        request: ChartPreviewRequest,
    ) -> ChartPreviewResponse:
        """
        Generate chart preview for a dataset.
        
        Flow:
        1. Get dataset metadata and URL
        2. Connect to data source
        3. Fetch data with filters/limits
        4. Validate chart compatibility
        5. Generate chart spec
        6. Return spec + data
        """
        start_time = time.time()

        logger.info(
            "chart_generation_started",
            dataset_id=request.dataset_id,
            chart_type=request.chart_type,
        )

        # Step 1: Get dataset metadata
        dataset = await self._get_dataset(request.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {request.dataset_id}")

        # Step 2: Connect to data source
        connector = create_connector(
            url=dataset["url"],
            format_hint=dataset["format"] if dataset["format"] != "unknown" else None,
        )

        try:
            await connector.connect()

            # Step 3: Get column info
            column_info = await connector.get_column_info()

            # Step 4: Validate chart compatibility
            compat = self.column_validator.validate_chart_compatibility(
                chart_type=request.chart_type,
                x_column=request.x_axis,
                y_column=request.y_axis,
                group_by_column=request.group_by,
                available_columns=column_info,
            )

            if not compat.compatible and request.chart_type.lower() != "histogram":
                return ChartPreviewResponse(
                    dataset_id=request.dataset_id,
                    chart_type=request.chart_type,
                    spec={},
                    data=[],
                    columns={},
                    warnings=compat.warnings,
                    metadata={
                        "rowCount": 0,
                        "filteredRowCount": 0,
                        "processingTimeMs": round((time.time() - start_time) * 1000, 2),
                        "memoryUsedBytes": 0,
                    },
                )

            # Step 5: Fetch data with filters and limits
            options = request.options or {}
            limit = options.get("limit", settings.MAX_CHART_ROWS)
            offset = options.get("offset", 0)

            data = await connector.get_data(
                columns=[request.x_axis] + ([request.y_axis] if request.y_axis else []) + ([request.group_by] if request.group_by else []),
                filters=request.filters,
                limit=limit,
                offset=offset,
            )

            if data.empty:
                return ChartPreviewResponse(
                    dataset_id=request.dataset_id,
                    chart_type=request.chart_type,
                    spec={},
                    data=[],
                    columns={},
                    warnings=["No data returned after applying filters"],
                    metadata={
                        "rowCount": 0,
                        "filteredRowCount": 0,
                        "processingTimeMs": round((time.time() - start_time) * 1000, 2),
                        "memoryUsedBytes": 0,
                    },
                )

            # Step 6: Generate chart
            chart_spec = self.chart_engine.create_chart(
                data=data,
                chart_type=request.chart_type,
                x_column=request.x_axis,
                y_column=request.y_axis,
                group_by_column=request.group_by,
                options=request.options,
            )

            processing_time = round((time.time() - start_time) * 1000, 2)

            # Step 7: Format response
            column_output = {}
            for role, col_info in chart_spec.columns.items():
                column_output[role] = {
                    "name": col_info.name,
                    "type": col_info.type.value,
                    "description": col_info.description,
                    "unit": col_info.unit,
                    "nullable": col_info.nullable,
                }

            response = ChartPreviewResponse(
                dataset_id=request.dataset_id,
                chart_type=request.chart_type,
                spec=chart_spec.spec,
                data=chart_spec.data,
                columns=column_output,
                warnings=chart_spec.warnings,
                metadata={
                    "rowCount": chart_spec.metadata.get("rowCount", 0),
                    "filteredRowCount": chart_spec.metadata.get("filteredRowCount", 0),
                    "processingTimeMs": processing_time,
                    "memoryUsedBytes": len(str(chart_spec.data).encode()),
                },
            )

            logger.info(
                "chart_generation_completed",
                dataset_id=request.dataset_id,
                chart_type=request.chart_type,
                processing_time_ms=processing_time,
            )

            return response

        finally:
            await connector.close()

    async def get_dataset_preview(
        self,
        dataset_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> DataPreview:
        """Get a preview of dataset data."""
        dataset = await self._get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")

        connector = create_connector(
            url=dataset["url"],
            format_hint=dataset["format"] if dataset["format"] != "unknown" else None,
        )

        try:
            await connector.connect()
            preview = await connector.get_preview(limit=limit, offset=offset)
            return preview
        finally:
            await connector.close()

    async def get_column_info(self, dataset_id: str) -> Dict[str, Any]:
        """Get column type information for a dataset."""
        dataset = await self._get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")

        connector = create_connector(
            url=dataset["url"],
            format_hint=dataset["format"] if dataset["format"] != "unknown" else None,
        )

        try:
            await connector.connect()
            column_info = await connector.get_column_info()
            return {
                name: {
                    "name": info.name,
                    "type": info.type.value,
                    "description": info.description,
                    "unit": info.unit,
                    "nullable": info.nullable,
                    "unique_count": info.unique_count,
                    "statistics": info.statistics,
                }
                for name, info in column_info.items()
            }
        finally:
            await connector.close()

    async def validate_chart_compatibility(
        self,
        dataset_id: str,
        chart_type: str,
        x_axis: str,
        y_axis: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> ChartCompatibility:
        """Validate if a chart configuration is compatible with the dataset."""
        dataset = await self._get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")

        connector = create_connector(
            url=dataset["url"],
            format_hint=dataset["format"] if dataset["format"] != "unknown" else None,
        )

        try:
            await connector.connect()
            column_info = await connector.get_column_info()
            return self.column_validator.validate_chart_compatibility(
                chart_type=chart_type,
                x_column=x_axis,
                y_column=y_axis,
                group_by_column=group_by,
                available_columns=column_info,
            )
        finally:
            await connector.close()

    async def get_suggested_charts(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Get suggested chart types for a dataset."""
        dataset = await self._get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")

        connector = create_connector(
            url=dataset["url"],
            format_hint=dataset["format"] if dataset["format"] != "unknown" else None,
        )

        try:
            await connector.connect()
            column_info = await connector.get_column_info()
            return self.column_validator.get_suggested_charts(column_info)
        finally:
            await connector.close()

    async def _get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get dataset metadata from catalog."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT d.*, pi.title as investigation_title
                FROM datasets d
                JOIN psi_investigations pi ON pi.psi_id = d.psi_id
                WHERE d.dataset_id = $1
                """,
                dataset_id
            )
            return dict(row) if row else None

    async def health_check(self) -> Dict[str, Any]:
        """Check visualization service health."""
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_healthy = True
        except Exception:
            db_healthy = False

        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "database": "healthy" if db_healthy else "unhealthy",
            "chart_engine": "ready",
            "supported_chart_types": settings.supported_chart_types_list,
        }


# Global service instance
_visualization_service: Optional["VisualizationService"] = None


def get_visualization_service() -> "VisualizationService":
    """Get global visualization service instance."""
    global _visualization_service
    if _visualization_service is None:
        raise RuntimeError("Visualization service not initialized")
    return _visualization_service


async def initialize_visualization_service(pool: asyncpg.Pool) -> "VisualizationService":
    """Initialize global visualization service."""
    global _visualization_service
    _visualization_service = VisualizationService(pool)
    logger.info("visualization_service_initialized")
    return _visualization_service


async def close_visualization_service():
    """Close global visualization service."""
    global _visualization_service
    _visualization_service = None