"""Chart generation engine using Altair."""

import json
import structlog
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union

import altair as alt
import pandas as pd

from services.visualization.src.config import settings
from services.visualization.src.validation.column_validator import (
    ChartCompatibility,
    ChartType,
    ColumnType,
    ColumnInfo,
    ColumnValidator,
)

logger = structlog.get_logger()

# Configure Altair
alt.data_transformers.disable_max_rows()


@dataclass
class ChartSpec:
    """Chart specification."""
    chart_type: ChartType
    spec: Dict[str, Any]  # Vega-Lite spec
    data: List[Dict[str, Any]]
    columns: Dict[str, ColumnInfo]
    warnings: List[str]
    metadata: Dict[str, Any]


class ChartEngine:
    """Generates Altair charts from data."""

    def __init__(self):
        self.column_validator = ColumnValidator()

    def create_chart(
        self,
        data: pd.DataFrame,
        chart_type: str,
        x_column: str,
        y_column: Optional[str] = None,
        group_by_column: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> ChartSpec:
        """
        Create a chart from DataFrame data.
        
        Args:
            data: DataFrame with data
            chart_type: Type of chart (bar, line, scatter, histogram)
            x_column: Column name for x-axis
            y_column: Column name for y-axis (required for bar, line, scatter)
            group_by_column: Column name for grouping/color
            options: Chart options (title, labels, aggregation, etc.)
            
        Returns:
            ChartSpec with Vega-Lite specification and data
        """
        options = options or {}
        chart_type_enum = ChartType(chart_type.lower())

        # Validate data
        if data.empty:
            return ChartSpec(
                chart_type=chart_type_enum,
                spec={},
                data=[],
                columns={},
                warnings=["No data available for chart"],
                metadata={"rowCount": 0, "filteredRowCount": 0},
            )

        # Validate columns exist
        for col in [x_column, y_column, group_by_column]:
            if col and col not in data.columns:
                return ChartSpec(
                    chart_type=chart_type_enum,
                    spec={},
                    data=[],
                    columns={},
                    warnings=[f"Column '{col}' not found in data"],
                    metadata={"rowCount": len(data), "filteredRowCount": 0},
                )

        # Get column info
        column_info = self._get_column_info(data, x_column, y_column, group_by_column)

        # Validate compatibility
        compat = self.column_validator.validate_chart_compatibility(
            chart_type, x_column, y_column, group_by_column, column_info
        )

        if not compat.compatible and chart_type_enum != ChartType.HISTOGRAM:
            return ChartSpec(
                chart_type=chart_type_enum,
                spec={},
                data=[],
                columns=column_info,
                warnings=compat.warnings,
                metadata={
                    "rowCount": len(data),
                    "filteredRowCount": 0,
                },
            )

        # Prepare data (apply sampling if needed)
        chart_data, sampled = self._prepare_data(data, chart_type_enum, options)

        # Generate chart specification
        spec = self._generate_spec(
            chart_type_enum,
            chart_data,
            x_column,
            y_column,
            group_by_column,
            column_info,
            options,
        )

        # Prepare output data
        output_data = chart_data.to_dict("records")

        metadata = {
            "rowCount": len(data),
            "filteredRowCount": len(chart_data),
            "sampled": sampled,
            "processingTimeMs": 0,  # Will be set by caller
        }

        return ChartSpec(
            chart_type=chart_type_enum,
            spec=spec,
            data=output_data,
            columns=column_info,
            warnings=compat.warnings,
            metadata=metadata,
        )

    def _get_column_info(
        self,
        data: pd.DataFrame,
        x_column: str,
        y_column: Optional[str],
        group_by_column: Optional[str],
    ) -> Dict[str, ColumnInfo]:
        """Get column info for relevant columns."""
        relevant = [c for c in [x_column, y_column, group_by_column] if c and c in data.columns]
        return self.column_validator.analyze_columns(data[relevant])

    def _prepare_data(
        self,
        data: pd.DataFrame,
        chart_type: ChartType,
        options: Dict[str, Any],
    ) -> tuple[pd.DataFrame, bool]:
        """Prepare data for charting (sampling, sorting, etc.)."""
        sampled = False
        chart_data = data.copy()

        # Sort for line charts
        if chart_type == ChartType.LINE and "x" in chart_data.columns:
            # We don't know x_column here, so skip auto-sort
            pass

        # Apply row limit
        limit = options.get("limit", settings.MAX_CHART_ROWS)
        if len(chart_data) > limit:
            if options.get("sampleMethod") == "random":
                chart_data = chart_data.sample(n=limit, random_state=42)
            elif options.get("sampleMethod") == "systematic":
                step = len(chart_data) // limit
                chart_data = chart_data.iloc[::step].head(limit)
            else:
                chart_data = chart_data.head(limit)
            sampled = True

        return chart_data, sampled

    def _generate_spec(
        self,
        chart_type: ChartType,
        data: pd.DataFrame,
        x_column: str,
        y_column: Optional[str],
        group_by_column: Optional[str],
        column_info: Dict[str, ColumnInfo],
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate Vega-Lite specification."""

        # Base chart configuration
        base_config = {
            "width": options.get("width", settings.DEFAULT_CHART_WIDTH),
            "height": options.get("height", settings.DEFAULT_CHART_HEIGHT),
        }

        if options.get("title"):
            base_config["title"] = options["title"]

        # Create encodings
        encodings = {}

        # X encoding
        x_col_info = column_info.get(x_column)
        x_encoding = self._create_encoding(
            field=x_column,
            col_type=x_col_info.type if x_col_info else ColumnType.UNKNOWN,
            role="x",
            unit=x_col_info.unit if x_col_info else None,
            label=options.get("xLabel", x_column),
        )
        encodings["x"] = x_encoding

        # Y encoding
        if chart_type != ChartType.HISTOGRAM and y_column:
            y_col_info = column_info.get(y_column)
            y_encoding = self._create_encoding(
                field=y_column,
                col_type=y_col_info.type if y_col_info else ColumnType.UNKNOWN,
                role="y",
                unit=y_col_info.unit if y_col_info else None,
                label=options.get("yLabel", y_column),
                aggregate=options.get("aggregation") if options.get("aggregation") != "none" else None,
            )
            encodings["y"] = y_encoding
        elif chart_type == ChartType.HISTOGRAM:
            # Histogram uses count on y
            encodings["y"] = {"aggregate": "count", "type": "quantitative", "title": "Count"}

        # Color/group by encoding
        if group_by_column and group_by_column in column_info:
            group_col_info = column_info[group_by_column]
            encodings["color"] = self._create_encoding(
                field=group_by_column,
                col_type=group_col_info.type,
                role="color",
                label=group_by_column,
            )

        # Create chart spec based on type
        spec = self._create_chart_spec(chart_type, encodings, base_config, options)

        return spec

    def _create_encoding(
        self,
        field: str,
        col_type: ColumnType,
        role: str,
        unit: Optional[str] = None,
        label: Optional[str] = None,
        aggregate: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create Vega-Lite encoding for a field."""
        # Map column type to Vega-Lite type
        type_map = {
            ColumnType.NUMERIC: "quantitative",
            ColumnType.DATETIME: "temporal",
            ColumnType.CATEGORICAL: "nominal",
            ColumnType.TEXT: "nominal",
            ColumnType.BOOLEAN: "nominal",
            ColumnType.UNKNOWN: "quantitative",
        }

        vega_type = type_map.get(col_type, "quantitative")

        encoding = {
            "field": field,
            "type": vega_type,
            "title": label or field,
        }

        if unit:
            encoding["title"] += f" ({unit})"

        if aggregate:
            encoding["aggregate"] = aggregate

        # Special handling for histograms
        if role == "x" and col_type == ColumnType.NUMERIC:
            # Allow binning for numeric x in histograms
            pass

        return encoding

    def _create_chart_spec(
        self,
        chart_type: ChartType,
        encodings: Dict[str, Any],
        base_config: Dict[str, Any],
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create the final Vega-Lite chart specification."""

        if chart_type == ChartType.BAR:
            mark = "bar"
        elif chart_type == ChartType.LINE:
            mark = "line"
        elif chart_type == ChartType.SCATTER:
            mark = "point"
        elif chart_type == ChartType.HISTOGRAM:
            mark = "bar"
            # Add binning for histogram x-axis
            if "x" in encodings:
                encodings["x"]["bin"] = True
        else:
            mark = "point"

        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "mark": mark,
            "encoding": encodings,
            **base_config,
        }

        # Add config for better defaults
        spec["config"] = {
            "view": {"stroke": "transparent"},
            "axis": {"grid": True, "gridOpacity": 0.3},
            "legend": {"orient": "right"},
        }

        return spec

    def to_vega_lite(self, chart_spec: ChartSpec) -> Dict[str, Any]:
        """Convert ChartSpec to Vega-Lite format for rendering."""
        return {
            "spec": chart_spec.spec,
            "data": {"values": chart_spec.data},
        }


def create_chart_engine() -> ChartEngine:
    """Create a chart engine instance."""
    return ChartEngine()