"""Tests for chart engine."""

import pytest
import pandas as pd
import numpy as np

from services.visualization.src.charts.chart_engine import ChartEngine, ChartSpec, ChartType
from services.visualization.src.validation.column_validator import ColumnType, ColumnInfo


class TestChartEngine:
    """Tests for chart engine."""

    @pytest.fixture
    def engine(self):
        return ChartEngine()

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        np.random.seed(42)
        return pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=100, freq="h"),
            "temperature": np.random.normal(1500, 200, 100),
            "pressure": np.random.normal(101.3, 5, 100),
            "experiment": np.random.choice(["exp_1", "exp_2", "exp_3"], 100),
            "category": np.random.choice(["A", "B", "C"], 100),
        })

    def test_create_bar_chart(self, engine, sample_data):
        """Test bar chart creation."""
        spec = engine.create_chart(
            data=sample_data,
            chart_type="bar",
            x_column="category",
            y_column="temperature",
            options={"title": "Temperature by Category"},
        )

        assert isinstance(spec, ChartSpec)
        assert spec.chart_type == ChartType.BAR
        assert "mark" in spec.spec
        assert spec.spec["mark"] == "bar"
        assert spec.spec["encoding"]["x"]["field"] == "category"
        assert spec.spec["encoding"]["y"]["field"] == "temperature"
        assert len(spec.data) > 0

    def test_create_line_chart(self, engine, sample_data):
        """Test line chart creation."""
        spec = engine.create_chart(
            data=sample_data,
            chart_type="line",
            x_column="time",
            y_column="temperature",
            options={"title": "Temperature Over Time"},
        )

        assert spec.chart_type == ChartType.LINE
        assert spec.spec["mark"] == "line"
        assert spec.spec["encoding"]["x"]["field"] == "time"
        assert spec.spec["encoding"]["y"]["field"] == "temperature"

    def test_create_scatter_chart(self, engine, sample_data):
        """Test scatter chart creation."""
        spec = engine.create_chart(
            data=sample_data,
            chart_type="scatter",
            x_column="pressure",
            y_column="temperature",
            group_by_column="experiment",
            options={"title": "Temperature vs Pressure"},
        )

        assert spec.chart_type == ChartType.SCATTER
        assert spec.spec["mark"] == "point"
        assert spec.spec["encoding"]["x"]["field"] == "pressure"
        assert spec.spec["encoding"]["y"]["field"] == "temperature"
        assert "color" in spec.spec["encoding"]
        assert spec.spec["encoding"]["color"]["field"] == "experiment"

    def test_create_histogram_chart(self, engine, sample_data):
        """Test histogram creation."""
        spec = engine.create_chart(
            data=sample_data,
            chart_type="histogram",
            x_column="temperature",
            options={"title": "Temperature Distribution"},
        )

        assert spec.chart_type == ChartType.HISTOGRAM
        assert spec.spec["mark"] == "bar"
        assert "bin" in spec.spec["encoding"]["x"]
        assert spec.spec["encoding"]["x"]["bin"] is True
        assert spec.spec["encoding"]["y"]["aggregate"] == "count"

    def test_empty_data(self, engine):
        """Test chart creation with empty data."""
        empty_df = pd.DataFrame()
        spec = engine.create_chart(
            data=empty_df,
            chart_type="bar",
            x_column="x",
            y_column="y",
        )

        assert spec.chart_type == ChartType.BAR
        assert spec.spec == {}
        assert spec.data == []
        assert "No data available" in spec.warnings[0]

    def test_missing_column(self, engine, sample_data):
        """Test chart creation with missing column."""
        spec = engine.create_chart(
            data=sample_data,
            chart_type="bar",
            x_column="missing_column",
            y_column="temperature",
        )

        assert spec.spec == {}
        assert spec.data == []
        assert any("not found" in w.lower() for w in spec.warnings)

    def test_chart_spec_contains_data(self, engine, sample_data):
        """Test that chart spec includes data."""
        spec = engine.create_chart(
            data=sample_data.head(10),
            chart_type="bar",
            x_column="category",
            y_column="temperature",
        )

        assert len(spec.data) == 10
        assert all("category" in row and "temperature" in row for row in spec.data)

    def test_chart_options(self, engine, sample_data):
        """Test chart options are applied."""
        spec = engine.create_chart(
            data=sample_data,
            chart_type="bar",
            x_column="category",
            y_column="temperature",
            options={
                "title": "Test Title",
                "xLabel": "Category",
                "yLabel": "Temp (K)",
                "width": 600,
                "height": 300,
            },
        )

        assert spec.spec.get("title") == "Test Title"
        assert spec.spec["width"] == 600
        assert spec.spec["height"] == 300
        assert spec.spec["encoding"]["x"]["title"] == "Category"
        assert spec.spec["encoding"]["y"]["title"] == "Temp (K)"

    def test_aggregation_option(self, engine, sample_data):
        """Test aggregation option for line/bar charts."""
        spec = engine.create_chart(
            data=sample_data,
            chart_type="line",
            x_column="time",
            y_column="temperature",
            options={"aggregation": "mean"},
        )

        # Line chart with aggregation should have aggregate in y encoding
        assert spec.spec["encoding"]["y"].get("aggregate") == "mean"

    def test_histogram_ignores_y_axis(self, engine, sample_data):
        """Test that histogram ignores y-axis."""
        spec = engine.create_chart(
            data=sample_data,
            chart_type="histogram",
            x_column="temperature",
            y_column="pressure",  # Should be ignored
        )

        assert spec.chart_type == ChartType.HISTOGRAM
        assert spec.spec["encoding"]["y"]["aggregate"] == "count"

    def test_to_vega_lite(self, engine, sample_data):
        """Test conversion to Vega-Lite format."""
        spec = engine.create_chart(
            data=sample_data.head(5),
            chart_type="bar",
            x_column="category",
            y_column="temperature",
        )

        vega_lite = engine.to_vega_lite(spec)

        assert "spec" in vega_lite
        assert "data" in vega_lite
        assert vega_lite["data"]["values"] == spec.data


class TestChartSpec:
    """Tests for ChartSpec dataclass."""

    def test_chart_spec_creation(self):
        """Test ChartSpec creation."""
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            spec={"mark": "bar", "encoding": {}},
            data=[{"x": 1, "y": 2}],
            columns={},
            warnings=[],
            metadata={"rowCount": 100, "filteredRowCount": 10},
        )

        assert spec.chart_type == ChartType.BAR
        assert len(spec.data) == 1
        assert spec.metadata["rowCount"] == 100