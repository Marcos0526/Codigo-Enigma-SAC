"""Dataset profiling for statistical analysis."""

import io
import time
import structlog
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

import pandas as pd
import numpy as np
from scipy import stats

from services.summarizer.src.config import settings

logger = structlog.get_logger()


class ColumnType(str, Enum):
    """Column data types for profiling."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    DATETIME = "datetime"
    TEXT = "text"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


@dataclass
class ColumnProfile:
    """Profile for a single column."""
    name: str
    dtype: ColumnType
    nullable: bool
    null_count: int
    null_fraction: float
    unique_count: int
    sample_values: List[Any] = field(default_factory=list)

    # Numeric statistics
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    iqr: Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None

    # Categorical statistics
    top_values: Optional[Dict[Any, int]] = None
    entropy: Optional[float] = None

    # Datetime statistics
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    date_range_days: Optional[float] = None

    # Text statistics
    avg_length: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None


@dataclass
class DatasetProfile:
    """Complete dataset profile."""
    dataset_id: str
    row_count: int
    column_count: int
    byte_size: int
    columns: List[ColumnProfile]
    profiling_duration_ms: float
    memory_used_mb: float
    warnings: List[str] = field(default_factory=list)
    profiled_at: str = ""


class DatasetProfiler:
    """Profiles datasets to compute comprehensive statistics."""

    def __init__(
        self,
        max_rows: int = None,
        max_memory_mb: int = None,
        max_time_seconds: int = None,
        sample_size: int = None,
    ):
        self.max_rows = max_rows or settings.MAX_PROFILE_ROWS
        self.max_memory_mb = max_memory_mb or settings.MAX_PROFILE_MEMORY_MB
        self.max_time_seconds = max_time_seconds or settings.MAX_PROFILE_TIME_SECONDS
        self.sample_size = sample_size or settings.PROFILE_SAMPLE_SIZE

    def _detect_column_type(self, series: pd.Series) -> ColumnType:
        """Detect the semantic type of a column."""
        # Skip if all null
        if series.isna().all():
            return ColumnType.UNKNOWN

        non_null = series.dropna()
        total_count = len(non_null)

        if total_count == 0:
            return ColumnType.UNKNOWN

        # Check dtype kind FIRST for native types
        dtype_kind = non_null.dtype.kind
        if dtype_kind == 'M':  # datetime64
            return ColumnType.DATETIME
        if dtype_kind == 'b':  # boolean
            return ColumnType.BOOLEAN
        if dtype_kind in ('i', 'u', 'f'):  # integer, unsigned, float
            return ColumnType.NUMERIC

        # Check boolean FIRST (before numeric, since bool converts to 1/0)
        unique_vals = non_null.unique()
        if len(unique_vals) <= 2:
            bool_vals = {"true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"}
            if all(str(v).lower() in bool_vals for v in unique_vals):
                return ColumnType.BOOLEAN

        # Try numeric
        numeric = pd.to_numeric(non_null, errors="coerce")
        numeric_count = numeric.notna().sum()
        if numeric_count / total_count > 0.8:
            return ColumnType.NUMERIC

        # Try datetime (only for string-like data that looks like dates)
        # Check if the data looks like date strings first
        sample = non_null.head(10).astype(str)
        looks_like_dates = any(
            any(c in s for c in ['-', '/', ':', 'T']) 
            for s in sample
        )
        if looks_like_dates:
            try:
                dt = pd.to_datetime(non_null, errors="coerce")
                dt_count = dt.notna().sum()
                if dt_count / total_count > 0.8:
                    return ColumnType.DATETIME
            except Exception:
                pass

        # Check categorical (low cardinality) - consider both ratio and absolute count
        unique_ratio = len(unique_vals) / total_count
        # Categorical if: low ratio AND small absolute unique count (not just small ratio)
        # Also consider absolute unique count for small datasets
        is_categorical = False
        if unique_ratio < 0.2 and len(unique_vals) < 50:
            is_categorical = True
        # For small datasets with few unique values, also consider categorical
        elif len(unique_vals) <= 10 and total_count >= 5 and unique_ratio <= 0.5:
            is_categorical = True

        if is_categorical:
            return ColumnType.CATEGORICAL

        return ColumnType.TEXT

    def _profile_numeric(self, series: pd.Series) -> Dict[str, Any]:
        """Compute numeric statistics."""
        numeric = pd.to_numeric(series, errors="coerce")
        valid = numeric.dropna()

        if len(valid) == 0:
            return {}

        q1 = valid.quantile(0.25)
        q3 = valid.quantile(0.75)

        return {
            "min_val": float(valid.min()),
            "max_val": float(valid.max()),
            "mean": float(valid.mean()),
            "median": float(valid.median()),
            "std": float(valid.std()) if len(valid) > 1 else 0.0,
            "q1": float(q1),
            "q3": float(q3),
            "iqr": float(q3 - q1),
            "skewness": float(stats.skew(valid)) if len(valid) > 2 else 0.0,
            "kurtosis": float(stats.kurtosis(valid)) if len(valid) > 3 else 0.0,
        }

    def _profile_categorical(self, series: pd.Series) -> Dict[str, Any]:
        """Compute categorical statistics."""
        non_null = series.dropna()
        if len(non_null) == 0:
            return {}

        value_counts = non_null.value_counts()
        top_values = value_counts.head(10).to_dict()

        # Entropy
        probs = value_counts / len(non_null)
        entropy = -sum(p * np.log2(p) for p in probs if p > 0)

        return {
            "top_values": top_values,
            "entropy": float(entropy),
        }

    def _profile_datetime(self, series: pd.Series) -> Dict[str, Any]:
        """Compute datetime statistics."""
        try:
            dt = pd.to_datetime(series, errors="coerce")
            valid = dt.dropna()
            if len(valid) == 0:
                return {}

            return {
                "min_date": valid.min().isoformat(),
                "max_date": valid.max().isoformat(),
                "date_range_days": float((valid.max() - valid.min()).total_seconds() / 86400),
            }
        except Exception:
            return {}

    def _profile_text(self, series: pd.Series) -> Dict[str, Any]:
        """Compute text statistics."""
        non_null = series.dropna()
        if len(non_null) == 0:
            return {}

        lengths = non_null.astype(str).str.len()
        return {
            "avg_length": float(lengths.mean()),
            "min_length": int(lengths.min()),
            "max_length": int(lengths.max()),
        }

    def _profile_boolean(self, series: pd.Series) -> Dict[str, Any]:
        """Compute boolean statistics."""
        non_null = series.dropna()
        if len(non_null) == 0:
            return {}

        # Count true/false
        true_count = 0
        for v in non_null:
            if str(v).lower() in {"true", "yes", "1", "t", "y"}:
                true_count += 1

        return {
            "true_count": true_count,
            "false_count": len(non_null) - true_count,
        }

    def profile_dataframe(self, df: pd.DataFrame, dataset_id: str) -> DatasetProfile:
        """Profile a pandas DataFrame."""
        import psutil
        import os

        start_time = time.time()
        process = psutil.Process(os.getpid())
        start_memory = process.memory_info().rss / 1024 / 1024

        # Limit rows if needed
        if len(df) > self.max_rows:
            df = df.head(self.max_rows)

        # Limit memory
        current_memory = process.memory_info().rss / 1024 / 1024
        if current_memory - start_memory > self.max_memory_mb:
            logger.warning("memory_limit_exceeded", dataset_id=dataset_id)

        columns = []
        warnings = []

        for col_name in df.columns:
            series = df[col_name]
            col_type = self._detect_column_type(series)

            null_count = int(series.isna().sum())
            total_count = len(series)
            nullable = null_count > 0

            profile = ColumnProfile(
                name=col_name,
                dtype=col_type,
                nullable=nullable,
                null_count=null_count,
                null_fraction=null_count / total_count if total_count > 0 else 0.0,
                unique_count=int(series.nunique()),
                sample_values=series.dropna().head(5).tolist(),
            )

            # Type-specific profiling
            if col_type == ColumnType.NUMERIC:
                stats = self._profile_numeric(series)
                for k, v in stats.items():
                    setattr(profile, k, v)
            elif col_type == ColumnType.CATEGORICAL:
                stats = self._profile_categorical(series)
                for k, v in stats.items():
                    setattr(profile, k, v)
            elif col_type == ColumnType.DATETIME:
                stats = self._profile_datetime(series)
                for k, v in stats.items():
                    setattr(profile, k, v)
            elif col_type == ColumnType.TEXT:
                stats = self._profile_text(series)
                for k, v in stats.items():
                    setattr(profile, k, v)
            elif col_type == ColumnType.BOOLEAN:
                stats = self._profile_boolean(series)
                for k, v in stats.items():
                    setattr(profile, k, v)

            # Check for warnings
            if profile.null_fraction > 0.5:
                warnings.append(f"Column '{col_name}' has >50% null values")

            if col_type == ColumnType.CATEGORICAL and profile.unique_count > 1000:
                warnings.append(f"Column '{col_name}' has high cardinality ({profile.unique_count} unique values)")

            columns.append(profile)

        end_time = time.time()
        end_memory = process.memory_info().rss / 1024 / 1024

        return DatasetProfile(
            dataset_id=dataset_id,
            row_count=len(df),
            column_count=len(df.columns),
            byte_size=df.memory_usage(deep=True).sum(),
            columns=columns,
            profiling_duration_ms=round((end_time - start_time) * 1000, 2),
            memory_used_mb=round(end_memory - start_memory, 2),
            warnings=warnings,
            profiled_at=pd.Timestamp.now().isoformat(),
        )

    def profile_from_connector(
        self,
        connector,
        dataset_id: str,
        columns: Optional[List[str]] = None,
    ) -> DatasetProfile:
        """Profile dataset using a data connector."""
        # Get sample data from connector
        preview = connector.get_preview(limit=self.sample_size)

        # Create DataFrame
        df = pd.DataFrame(preview.rows, columns=preview.columns)

        # Filter columns if specified
        if columns:
            df = df[[c for c in columns if c in df.columns]]

        return self.profile_dataframe(df, dataset_id)


def create_profiler() -> DatasetProfiler:
    """Create a profiler with default settings."""
    return DatasetProfiler()