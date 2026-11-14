"""Tests for dataset profiling."""

import pytest
import pandas as pd
import numpy as np

from services.summarizer.src.profiling.dataset_profiler import (
    DatasetProfiler,
    ColumnProfile,
    ColumnType,
)


class TestDatasetProfiler:
    """Tests for dataset profiling."""

    @pytest.fixture
    def profiler(self):
        return DatasetProfiler(max_rows=1000)

    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame with mixed column types."""
        np.random.seed(42)
        return pd.DataFrame({
            "numeric_col": [1.0, 2.0, 3.0, 4.0, 5.0, np.nan],
            "int_col": [10, 20, 30, 40, 50, 60],
            "categorical_col": ["A", "B", "A", "C", "B", "A"],
            "datetime_col": pd.date_range("2024-01-01", periods=6, freq="D"),
            "text_col": ["short", "medium length", "a very long text string here", "x", "y", "z"],
            "boolean_col": [True, False, True, True, False, False],
            "all_null": [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
        })

    def test_detect_numeric_column(self, profiler, sample_df):
        """Test numeric column detection."""
        col_type = profiler._detect_column_type(sample_df["numeric_col"])
        assert col_type == ColumnType.NUMERIC

        col_type = profiler._detect_column_type(sample_df["int_col"])
        assert col_type == ColumnType.NUMERIC

    def test_detect_categorical_column(self, profiler, sample_df):
        """Test categorical column detection."""
        col_type = profiler._detect_column_type(sample_df["categorical_col"])
        assert col_type == ColumnType.CATEGORICAL

    def test_detect_datetime_column(self, profiler, sample_df):
        """Test datetime column detection."""
        col_type = profiler._detect_column_type(sample_df["datetime_col"])
        assert col_type == ColumnType.DATETIME

    def test_detect_text_column(self, profiler, sample_df):
        """Test text column detection."""
        col_type = profiler._detect_column_type(sample_df["text_col"])
        assert col_type == ColumnType.TEXT

    def test_detect_boolean_column(self, profiler, sample_df):
        """Test boolean column detection."""
        col_type = profiler._detect_column_type(sample_df["boolean_col"])
        assert col_type == ColumnType.BOOLEAN

    def test_detect_all_null_column(self, profiler, sample_df):
        """Test all-null column detection."""
        col_type = profiler._detect_column_type(sample_df["all_null"])
        assert col_type == ColumnType.UNKNOWN

    def test_profile_numeric_statistics(self, profiler, sample_df):
        """Test numeric statistics computation."""
        stats = profiler._profile_numeric(sample_df["numeric_col"])

        assert "min_val" in stats
        assert "max_val" in stats
        assert "mean" in stats
        assert "median" in stats
        assert "std" in stats
        assert "q1" in stats
        assert "q3" in stats
        assert "iqr" in stats
        assert "skewness" in stats
        assert "kurtosis" in stats

        assert stats["min_val"] == 1.0
        assert stats["max_val"] == 5.0
        assert stats["mean"] == 3.0  # (1+2+3+4+5)/5

    def test_profile_categorical_statistics(self, profiler, sample_df):
        """Test categorical statistics computation."""
        stats = profiler._profile_categorical(sample_df["categorical_col"])

        assert "top_values" in stats
        assert "entropy" in stats
        assert stats["top_values"]["A"] == 3
        assert stats["top_values"]["B"] == 2
        assert stats["top_values"]["C"] == 1
        assert stats["entropy"] > 0

    def test_profile_datetime_statistics(self, profiler, sample_df):
        """Test datetime statistics computation."""
        stats = profiler._profile_datetime(sample_df["datetime_col"])

        assert "min_date" in stats
        assert "max_date" in stats
        assert "date_range_days" in stats
        assert stats["date_range_days"] == 5.0

    def test_profile_text_statistics(self, profiler, sample_df):
        """Test text statistics computation."""
        stats = profiler._profile_text(sample_df["text_col"])

        assert "avg_length" in stats
        assert "min_length" in stats
        assert "max_length" in stats
        assert stats["min_length"] == 1  # "x"
        assert stats["max_length"] > 20  # "a very long text string here"

    def test_profile_boolean_statistics(self, profiler, sample_df):
        """Test boolean statistics computation."""
        stats = profiler._profile_boolean(sample_df["boolean_col"])

        assert "true_count" in stats
        assert "false_count" in stats
        assert stats["true_count"] == 3
        assert stats["false_count"] == 3

    def test_full_dataframe_profiling(self, profiler, sample_df):
        """Test full DataFrame profiling."""
        profile = profiler.profile_dataframe(sample_df, "test-dataset")

        assert profile.dataset_id == "test-dataset"
        assert profile.row_count == 6
        assert profile.column_count == 7
        assert len(profile.columns) == 7
        assert profile.profiling_duration_ms > 0
        assert profile.memory_used_mb >= 0

        # Check column profiles
        col_names = [c.name for c in profile.columns]
        assert "numeric_col" in col_names
        assert "categorical_col" in col_names
        assert "datetime_col" in col_names
        assert "text_col" in col_names
        assert "boolean_col" in col_names
        assert "all_null" in col_names

        # Check numeric column profile
        numeric_profile = next(c for c in profile.columns if c.name == "numeric_col")
        assert numeric_profile.dtype == ColumnType.NUMERIC
        assert numeric_profile.null_count == 1
        assert numeric_profile.null_fraction == 1/6
        assert numeric_profile.min_val == 1.0
        assert numeric_profile.max_val == 5.0

        # Check categorical column profile
        cat_profile = next(c for c in profile.columns if c.name == "categorical_col")
        assert cat_profile.dtype == ColumnType.CATEGORICAL
        assert cat_profile.top_values is not None
        assert cat_profile.entropy is not None

        # Check warnings
        assert any("all_null" in w for w in profile.warnings)

    def test_row_limit(self):
        """Test row limiting."""
        profiler = DatasetProfiler(max_rows=3)
        df = pd.DataFrame({"a": range(10)})
        profile = profiler.profile_dataframe(df, "test")
        assert profile.row_count == 3

    def test_column_type_enum_values(self):
        """Test ColumnType enum values."""
        assert ColumnType.NUMERIC.value == "numeric"
        assert ColumnType.CATEGORICAL.value == "categorical"
        assert ColumnType.DATETIME.value == "datetime"
        assert ColumnType.TEXT.value == "text"
        assert ColumnType.BOOLEAN.value == "boolean"
        assert ColumnType.UNKNOWN.value == "unknown"


class TestColumnProfile:
    """Tests for ColumnProfile dataclass."""

    def test_column_profile_creation(self):
        """Test ColumnProfile creation."""
        profile = ColumnProfile(
            name="test_col",
            dtype=ColumnType.NUMERIC,
            nullable=True,
            null_count=2,
            null_fraction=0.2,
            unique_count=8,
            min_val=0.0,
            max_val=100.0,
            mean=50.0,
        )

        assert profile.name == "test_col"
        assert profile.dtype == ColumnType.NUMERIC
        assert profile.min_val == 0.0
        assert profile.max_val == 100.0
        assert profile.mean == 50.0