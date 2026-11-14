"""Tests for column validator and chart compatibility."""

import pytest
import pandas as pd
import numpy as np

from services.visualization.src.validation.column_validator import (
    ColumnValidator,
    ChartType,
    ColumnType,
    ColumnInfo,
    ChartCompatibility,
    create_column_validator,
)


class TestColumnValidator:
    """Tests for column validator."""

    @pytest.fixture
    def validator(self):
        return ColumnValidator()

    def test_infer_numeric_column(self, validator):
        """Test numeric column type inference."""
        series = pd.Series([1, 2, 3, 4, 5])
        assert validator.infer_column_type(series) == ColumnType.NUMERIC

        # Float series
        series = pd.Series([1.1, 2.2, 3.3])
        assert validator.infer_column_type(series) == ColumnType.NUMERIC

    def test_infer_categorical_column(self, validator):
        """Test categorical column type inference."""
        series = pd.Series(["A", "B", "A", "C", "B", "A"])
        assert validator.infer_column_type(series) == ColumnType.CATEGORICAL

    def test_infer_datetime_column(self, validator):
        """Test datetime column type inference."""
        series = pd.date_range("2024-01-01", periods=6, freq="D")
        assert validator.infer_column_type(series) == ColumnType.DATETIME

    def test_infer_text_column(self, validator):
        """Test text column type inference."""
        series = pd.Series(["short", "medium length", "a very long text string here", "x", "y", "z"])
        assert validator.infer_column_type(series) == ColumnType.TEXT

    def test_infer_boolean_column(self, validator):
        """Test boolean column type inference."""
        series = pd.Series([True, False, True, True, False, False])
        assert validator.infer_column_type(series) == ColumnType.BOOLEAN

        # String boolean
        series = pd.Series(["true", "false", "true"])
        assert validator.infer_column_type(series) == ColumnType.BOOLEAN

    def test_infer_boolean_from_0_1(self, validator):
        """Test boolean inference from 0/1."""
        series = pd.Series([1, 0, 1, 0, 1])
        # 0/1 integers are numeric, not boolean
        assert validator.infer_column_type(series) == ColumnType.NUMERIC

    def test_validate_chart_compatibility_bar(self, validator):
        """Test bar chart compatibility validation."""
        columns = {
            "category": ColumnInfo(name="category", type=ColumnType.CATEGORICAL, nullable=False),
            "value": ColumnInfo(name="value", type=ColumnType.NUMERIC, nullable=False),
        }

        compat = validator.validate_chart_compatibility(
            chart_type="bar",
            x_column="category",
            y_column="value",
            group_by_column=None,
            available_columns=columns,
        )

        assert compat.compatible is True
        assert compat.chart_type == ChartType.BAR

    def test_validate_chart_compatibility_bar_wrong_types(self, validator):
        """Test bar chart with wrong column types."""
        columns = {
            "category": ColumnInfo(name="category", type=ColumnType.NUMERIC, nullable=False),
            "value": ColumnInfo(name="value", type=ColumnType.CATEGORICAL, nullable=False),
        }

        compat = validator.validate_chart_compatibility(
            chart_type="bar",
            x_column="category",
            y_column="value",
            group_by_column=None,
            available_columns=columns,
        )

        assert compat.compatible is False
        assert any("type" in w.lower() for w in compat.warnings)

    def test_validate_chart_compatibility_line(self, validator):
        """Test line chart compatibility validation."""
        columns = {
            "time": ColumnInfo(name="time", type=ColumnType.DATETIME, nullable=False),
            "temperature": ColumnInfo(name="temperature", type=ColumnType.NUMERIC, nullable=False),
        }

        compat = validator.validate_chart_compatibility(
            chart_type="line",
            x_column="time",
            y_column="temperature",
            group_by_column=None,
            available_columns=columns,
        )

        assert compat.compatible is True
        assert compat.chart_type == ChartType.LINE

    def test_validate_chart_compatibility_scatter(self, validator):
        """Test scatter chart compatibility validation."""
        columns = {
            "x": ColumnInfo(name="x", type=ColumnType.NUMERIC, nullable=False),
            "y": ColumnInfo(name="y", type=ColumnType.NUMERIC, nullable=False),
        }

        compat = validator.validate_chart_compatibility(
            chart_type="scatter",
            x_column="x",
            y_column="y",
            group_by_column=None,
            available_columns=columns,
        )

        assert compat.compatible is True
        assert compat.chart_type == ChartType.SCATTER

    def test_validate_chart_compatibility_histogram(self, validator):
        """Test histogram compatibility validation."""
        columns = {
            "values": ColumnInfo(name="values", type=ColumnType.NUMERIC, nullable=False),
        }

        compat = validator.validate_chart_compatibility(
            chart_type="histogram",
            x_column="values",
            y_column=None,
            group_by_column=None,
            available_columns=columns,
        )

        assert compat.compatible is True
        assert compat.chart_type == ChartType.HISTOGRAM

    def test_validate_chart_compatibility_missing_column(self, validator):
        """Test validation with missing column."""
        columns = {
            "category": ColumnInfo(name="category", type=ColumnType.CATEGORICAL, nullable=False),
        }

        compat = validator.validate_chart_compatibility(
            chart_type="bar",
            x_column="category",
            y_column="missing",
            group_by_column=None,
            available_columns=columns,
        )

        assert compat.compatible is False
        assert any("not found" in w.lower() for w in compat.warnings)

    def test_validate_chart_compatibility_same_column_multiple_roles(self, validator):
        """Test validation when same column used for multiple roles."""
        columns = {
            "value": ColumnInfo(name="value", type=ColumnType.NUMERIC, nullable=False),
        }

        compat = validator.validate_chart_compatibility(
            chart_type="scatter",
            x_column="value",
            y_column="value",
            group_by_column=None,
            available_columns=columns,
        )

        assert any("multiple roles" in w.lower() for w in compat.warnings)

    def test_get_suggested_charts(self, validator):
        """Test suggested charts for column types."""
        columns = {
            "time": ColumnInfo(name="time", type=ColumnType.DATETIME, nullable=False),
            "temp": ColumnInfo(name="temp", type=ColumnType.NUMERIC, nullable=False),
            "category": ColumnInfo(name="category", type=ColumnType.CATEGORICAL, nullable=False),
            "value": ColumnInfo(name="value", type=ColumnType.NUMERIC, nullable=False),
        }

        suggestions = validator.get_suggested_charts(columns)

        # Should suggest scatter (2+ numeric), line (datetime + numeric), bar (categorical + numeric), histogram (numeric)
        chart_types = [s["chart_type"] for s in suggestions]
        assert "scatter" in chart_types
        assert "line" in chart_types
        assert "bar" in chart_types
        assert "histogram" in chart_types


class TestChartCompatibility:
    """Tests for ChartCompatibility dataclass."""

    def test_chart_compatibility_creation(self):
        """Test ChartCompatibility creation."""
        compat = ChartCompatibility(
            compatible=True,
            chart_type=ChartType.BAR,
            warnings=[],
            required_columns={"x": {ColumnType.CATEGORICAL}, "y": {ColumnType.NUMERIC}},
            provided_columns={
                "x": ColumnInfo(name="cat", type=ColumnType.CATEGORICAL),
                "y": ColumnInfo(name="val", type=ColumnType.NUMERIC),
            },
        )

        assert compat.compatible is True
        assert compat.chart_type == ChartType.BAR


class TestColumnInfo:
    """Tests for ColumnInfo dataclass."""

    def test_column_info_creation(self):
        """Test ColumnInfo creation."""
        info = ColumnInfo(
            name="temperature",
            type=ColumnType.NUMERIC,
            description="Temperature in Kelvin",
            unit="K",
            nullable=False,
            unique_count=100,
            statistics={"min": 300, "max": 2000, "mean": 1500},
        )

        assert info.name == "temperature"
        assert info.type == ColumnType.NUMERIC
        assert info.unit == "K"
        assert info.nullable is False
        assert info.unique_count == 100
        assert info.statistics["mean"] == 1500