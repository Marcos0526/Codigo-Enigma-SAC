"""Column type validation and chart compatibility checking."""

import structlog
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Any

import pandas as pd

from services.visualization.src.config import settings

logger = structlog.get_logger()


class ColumnType(str, Enum):
    """Column data types for visualization."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    DATETIME = "datetime"
    TEXT = "text"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


class ChartType(str, Enum):
    """Supported chart types."""
    BAR = "bar"
    LINE = "line"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"


@dataclass
class ColumnInfo:
    """Information about a dataset column."""
    name: str
    type: ColumnType
    description: Optional[str] = None
    unit: Optional[str] = None
    nullable: bool = True
    unique_count: Optional[int] = None
    statistics: Optional[Dict[str, Any]] = None


@dataclass
class ChartCompatibility:
    """Chart compatibility result."""
    compatible: bool
    chart_type: ChartType
    warnings: List[str]
    required_columns: Dict[str, ColumnType]  # role -> required type
    provided_columns: Dict[str, ColumnInfo]  # role -> provided column


# Chart type compatibility rules
CHART_COMPATIBILITY = {
    ChartType.BAR: {
        "required": {
            "x": {ColumnType.CATEGORICAL, ColumnType.DATETIME, ColumnType.TEXT, ColumnType.BOOLEAN},
            "y": {ColumnType.NUMERIC},
        },
        "optional": {
            "groupBy": {ColumnType.CATEGORICAL, ColumnType.TEXT, ColumnType.BOOLEAN},
        },
        "description": "Bar chart: categorical/datetime x-axis, numeric y-axis",
    },
    ChartType.LINE: {
        "required": {
            "x": {ColumnType.DATETIME, ColumnType.NUMERIC, ColumnType.CATEGORICAL},
            "y": {ColumnType.NUMERIC},
        },
        "optional": {
            "groupBy": {ColumnType.CATEGORICAL, ColumnType.TEXT, ColumnType.BOOLEAN},
        },
        "description": "Line chart: datetime/numeric x-axis, numeric y-axis",
    },
    ChartType.SCATTER: {
        "required": {
            "x": {ColumnType.NUMERIC, ColumnType.DATETIME},
            "y": {ColumnType.NUMERIC},
        },
        "optional": {
            "groupBy": {ColumnType.CATEGORICAL, ColumnType.TEXT, ColumnType.BOOLEAN},
        },
        "description": "Scatter plot: numeric x and y axes",
    },
    ChartType.HISTOGRAM: {
        "required": {
            "x": {ColumnType.NUMERIC, ColumnType.DATETIME},
        },
        "optional": {
            "groupBy": {ColumnType.CATEGORICAL, ColumnType.TEXT, ColumnType.BOOLEAN},
        },
        "description": "Histogram: numeric/datetime single column",
    },
}


class ColumnValidator:
    """Validates column types and chart compatibility."""

    def __init__(self):
        self.chart_types = settings.supported_chart_types_list

    def infer_column_type(self, series) -> ColumnType:
        """Infer column type from pandas Series."""

        # Handle null series
        if series.isna().all():
            return ColumnType.UNKNOWN

        non_null = series.dropna()
        if len(non_null) == 0:
            return ColumnType.UNKNOWN

        # Check dtype kind
        dtype_kind = non_null.dtype.kind
        if dtype_kind == 'M':  # datetime64
            return ColumnType.DATETIME
        if dtype_kind == 'b':  # boolean
            return ColumnType.BOOLEAN
        if dtype_kind in ('i', 'u', 'f'):  # integer, unsigned, float
            return ColumnType.NUMERIC

        # Check boolean values (string)
        unique_vals = non_null.unique()
        if len(unique_vals) <= 2:
            bool_vals = {"true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"}
            if all(str(v).lower() in bool_vals for v in unique_vals):
                return ColumnType.BOOLEAN

        # Try numeric conversion
        numeric = pd.to_numeric(non_null, errors="coerce")
        if numeric.notna().sum() / len(non_null) > 0.8:
            return ColumnType.NUMERIC

        # Try datetime
        sample = non_null.head(10).astype(str)
        looks_like_dates = any(
            any(c in s for c in ['-', '/', ':', 'T'])
            for s in sample
        )
        if looks_like_dates:
            try:
                dt = pd.to_datetime(non_null, errors="coerce")
                if dt.notna().sum() / len(non_null) > 0.8:
                    return ColumnType.DATETIME
            except Exception:
                pass

        # Categorical (low cardinality)
        unique_ratio = len(unique_vals) / len(non_null)
        if unique_ratio < 0.2 and len(unique_vals) < 50:
            return ColumnType.CATEGORICAL
        # For small datasets, also check if most values are unique (text-like)
        if len(non_null) < 20 and len(unique_vals) <= 10:
            # Categorical if unique_ratio is reasonably low (many repeated values)
            # or if absolute unique count is small
            if unique_ratio < 0.7 or len(unique_vals) <= 5:
                return ColumnType.CATEGORICAL

        return ColumnType.TEXT

    def validate_column_exists(self, columns: Dict[str, ColumnInfo], column_name: str) -> Optional[ColumnInfo]:
        """Check if column exists in dataset."""
        return columns.get(column_name)

    def validate_chart_compatibility(
        self,
        chart_type: str,
        x_column: Optional[str],
        y_column: Optional[str],
        group_by_column: Optional[str],
        available_columns: Dict[str, ColumnInfo],
    ) -> ChartCompatibility:
        """Validate if columns are compatible with chart type."""
        chart_type_enum = ChartType(chart_type.lower())
        rules = CHART_COMPATIBILITY.get(chart_type_enum)

        if not rules:
            return ChartCompatibility(
                compatible=False,
                chart_type=chart_type_enum,
                warnings=[f"Unsupported chart type: {chart_type}"],
                required_columns={},
                provided_columns={},
            )

        warnings = []
        provided = {}
        required_roles = {}

        # Check required columns
        for role, allowed_types in rules["required"].items():
            column_name = {"x": x_column, "y": y_column}.get(role)
            required_roles[role] = allowed_types

            if not column_name:
                warnings.append(f"Required {role}-axis column not specified for {chart_type} chart")
                continue

            column = self.validate_column_exists(available_columns, column_name)
            if not column:
                warnings.append(f"Column '{column_name}' not found in dataset")
                continue

            provided[role] = column

            if column.type not in allowed_types:
                warnings.append(
                    f"{role}-axis column '{column_name}' has type '{column.type.value}', "
                    f"but {chart_type} chart requires one of: {', '.join(t.value for t in allowed_types)}"
                )

        # Check optional columns
        for role, allowed_types in rules.get("optional", {}).items():
            column_name = {"groupBy": group_by_column}.get(role)
            if column_name:
                column = self.validate_column_exists(available_columns, column_name)
                if column:
                    provided[role] = column
                    if column.type not in allowed_types:
                        warnings.append(
                            f"Group-by column '{column_name}' has type '{column.type.value}', "
                            f"recommended types: {', '.join(t.value for t in allowed_types)}"
                        )

        # Additional validations
        self._validate_additional_rules(chart_type_enum, x_column, y_column, group_by_column, available_columns, warnings)

        compatible = len(warnings) == 0

        return ChartCompatibility(
            compatible=compatible,
            chart_type=chart_type_enum,
            warnings=warnings,
            required_columns=required_roles,
            provided_columns=provided,
        )

    def _validate_additional_rules(
        self,
        chart_type: ChartType,
        x_column: Optional[str],
        y_column: Optional[str],
        group_by_column: Optional[str],
        available_columns: Dict[str, ColumnInfo],
        warnings: List[str],
    ):
        """Additional chart-specific validations."""
        # Check for high cardinality categorical columns
        for role, col_name in [("x", x_column), ("groupBy", group_by_column)]:
            if col_name and col_name in available_columns:
                col = available_columns[col_name]
                if col.type in (ColumnType.CATEGORICAL, ColumnType.TEXT) and col.unique_count:
                    if col.unique_count > 50:
                        warnings.append(
                            f"{role}-axis column '{col_name}' has high cardinality ({col.unique_count} unique values). "
                            f"Consider aggregation or filtering."
                        )

        # Check for same column used multiple times
        used_columns = [c for c in [x_column, y_column, group_by_column] if c]
        if len(used_columns) != len(set(used_columns)):
            warnings.append("Same column used for multiple roles (x, y, groupBy)")

        # Chart-specific checks
        if chart_type == ChartType.HISTOGRAM and y_column:
            warnings.append("Histogram charts ignore y-axis (count is computed automatically)")

        if chart_type == ChartType.LINE and x_column and x_column in available_columns:
            x_col = available_columns[x_column]
            if x_col.type not in (ColumnType.DATETIME, ColumnType.NUMERIC):
                warnings.append(
                    f"Line charts work best with datetime or numeric x-axis. "
                    f"Current x-axis type: {x_col.type.value}"
                )

    def get_suggested_charts(self, columns: Dict[str, ColumnInfo]) -> List[Dict[str, Any]]:
        """Get suggested chart types based on available columns."""
        suggestions = []

        numeric_cols = [name for name, col in columns.items() if col.type == ColumnType.NUMERIC]
        categorical_cols = [name for name, col in columns.items() if col.type in (ColumnType.CATEGORICAL, ColumnType.TEXT, ColumnType.BOOLEAN)]
        datetime_cols = [name for name, col in columns.items() if col.type == ColumnType.DATETIME]

        # Scatter: needs 2+ numeric
        if len(numeric_cols) >= 2:
            suggestions.append({
                "chart_type": "scatter",
                "description": "Scatter plot for numeric relationships",
                "suggested_x": numeric_cols[0],
                "suggested_y": numeric_cols[1],
            })

        # Line: datetime + numeric
        if datetime_cols and numeric_cols:
            suggestions.append({
                "chart_type": "line",
                "description": "Time series line chart",
                "suggested_x": datetime_cols[0],
                "suggested_y": numeric_cols[0],
            })

        # Bar: categorical + numeric
        if categorical_cols and numeric_cols:
            suggestions.append({
                "chart_type": "bar",
                "description": "Bar chart for categorical vs numeric",
                "suggested_x": categorical_cols[0],
                "suggested_y": numeric_cols[0],
            })

        # Histogram: single numeric
        if numeric_cols:
            suggestions.append({
                "chart_type": "histogram",
                "description": "Histogram for numeric distribution",
                "suggested_x": numeric_cols[0],
            })

        return suggestions

    def _compute_statistics(self, series: pd.Series, col_type: ColumnType) -> Optional[Dict[str, Any]]:
        """Compute basic statistics for a numeric series."""
        if col_type != ColumnType.NUMERIC:
            return None

        numeric = pd.to_numeric(series, errors="coerce")
        valid = numeric.dropna()

        if len(valid) == 0:
            return None

        return {
            "count": int(valid.count()),
            "min": float(valid.min()),
            "max": float(valid.max()),
            "mean": float(valid.mean()),
            "median": float(valid.median()),
            "std": float(valid.std()) if len(valid) > 1 else 0.0,
            "q1": float(valid.quantile(0.25)),
            "q3": float(valid.quantile(0.75)),
        }

    def analyze_columns(self, df: pd.DataFrame) -> Dict[str, ColumnInfo]:
        """Analyze DataFrame columns and return column info."""
        column_info = {}
        for col_name in df.columns:
            series = df[col_name]
            col_type = self.infer_column_type(series)

            info = ColumnInfo(
                name=col_name,
                type=col_type,
                nullable=series.isna().any(),
                unique_count=int(series.nunique()) if col_type in (ColumnType.CATEGORICAL, ColumnType.TEXT, ColumnType.BOOLEAN) else None,
                statistics=self._compute_statistics(series, col_type) if col_type == ColumnType.NUMERIC else None,
            )
            column_info[col_name] = info
        return column_info


def create_column_validator() -> ColumnValidator:
    """Create a column validator with default settings."""
    return ColumnValidator()