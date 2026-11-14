"""Numerical content detection for datasets."""

import io
import mimetypes
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import structlog

logger = structlog.get_logger()


@dataclass
class NumericalDetectionResult:
    """Result of numerical content detection."""

    has_numerical_data: bool
    numeric_columns: list[str]
    column_types: dict[str, str]
    row_count: int
    sample_size: int
    error: Optional[str] = None
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class NumericalDetector:
    """Detects numerical content in dataset files."""

    # Maximum rows to sample for detection
    MAX_SAMPLE_ROWS = 10000

    # Maximum bytes to read for detection
    MAX_SAMPLE_BYTES = 50 * 1024 * 1024  # 50 MB

    # Minimum fraction of non-null numeric values to consider a column numeric
    MIN_NUMERIC_FRACTION = 0.5

    # Supported file formats for detection
    SUPPORTED_FORMATS = {
        "csv", "tsv", "txt", "parquet", "json", "jsonl",
        "xlsx", "xls", "feather", "orc"
    }

    def __init__(
        self,
        max_sample_rows: int = MAX_SAMPLE_ROWS,
        max_sample_bytes: int = MAX_SAMPLE_BYTES,
        min_numeric_fraction: float = MIN_NUMERIC_FRACTION,
    ):
        self.max_sample_rows = max_sample_rows
        self.max_sample_bytes = max_sample_bytes
        self.min_numeric_fraction = min_numeric_fraction

    def _detect_format(self, content: bytes, filename: str) -> str:
        """Detect file format from content and filename."""
        # Try mimetype from filename
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            if "csv" in mime_type or "comma" in mime_type:
                return "csv"
            if "parquet" in mime_type:
                return "parquet"
            if "json" in mime_type:
                return "json"
            if "excel" in mime_type or "spreadsheet" in mime_type:
                return "xlsx"

        # Try to detect from content
        if content[:4] == b"PAR1":  # Parquet magic bytes
            return "parquet"
        if content[:4] in (b"\x1f\x8b", b"\x50\x4b"):  # gzip or zip
            # Could be compressed CSV/Parquet
            return "compressed"

        # Default to CSV for text-like content
        try:
            content.decode("utf-8")
            return "csv"
        except UnicodeDecodeError:
            return "unknown"

    def _read_sample(self, content: bytes, format_hint: str) -> pd.DataFrame:
        """Read a sample of the data based on format."""
        format_hint = format_hint.lower()

        if format_hint == "csv":
            return self._read_csv_sample(content)
        elif format_hint == "tsv":
            return self._read_csv_sample(content, sep="\t")
        elif format_hint == "parquet":
            return self._read_parquet_sample(content)
        elif format_hint == "json":
            return self._read_json_sample(content)
        elif format_hint == "jsonl":
            return self._read_jsonl_sample(content)
        elif format_hint in ("xlsx", "xls"):
            return self._read_excel_sample(content)
        else:
            # Try CSV as fallback
            try:
                return self._read_csv_sample(content)
            except Exception:
                raise ValueError(f"Unsupported format: {format_hint}")

    def _read_csv_sample(self, content: bytes, sep: str = ",") -> pd.DataFrame:
        """Read CSV sample with size limits."""
        # Use StringIO for text content
        text_content = content[:self.max_sample_bytes].decode("utf-8", errors="replace")
        return pd.read_csv(
            io.StringIO(text_content),
            sep=sep,
            nrows=self.max_sample_rows,
            low_memory=False,
            on_bad_lines="skip",
        )

    def _read_parquet_sample(self, content: bytes) -> pd.DataFrame:
        """Read Parquet sample."""
        import pyarrow.parquet as pq
        import pyarrow as pa

        buffer = io.BytesIO(content[:self.max_sample_bytes])
        table = pq.read_table(buffer)
        return table.to_pandas().head(self.max_sample_rows)

    def _read_json_sample(self, content: bytes) -> pd.DataFrame:
        """Read JSON sample."""
        text_content = content[:self.max_sample_bytes].decode("utf-8", errors="replace")
        return pd.read_json(io.StringIO(text_content), lines=False).head(self.max_sample_rows)

    def _read_jsonl_sample(self, content: bytes) -> pd.DataFrame:
        """Read JSON Lines sample."""
        text_content = content[:self.max_sample_bytes].decode("utf-8", errors="replace")
        return pd.read_json(io.StringIO(text_content), lines=True).head(self.max_sample_rows)

    def _read_excel_sample(self, content: bytes) -> pd.DataFrame:
        """Read Excel sample."""
        buffer = io.BytesIO(content[:self.max_sample_bytes])
        return pd.read_excel(buffer, nrows=self.max_sample_rows)

    def _analyze_columns(self, df: pd.DataFrame) -> tuple[dict[str, str], list[str]]:
        """Analyze DataFrame columns for numerical content."""
        column_types = {}
        numeric_columns = []

        for col in df.columns:
            series = df[col]

            # Skip if all null
            if series.isna().all():
                column_types[col] = "empty"
                continue

            total_count = series.notna().sum()
            if total_count == 0:
                column_types[col] = "empty"
                continue

            unique_vals = series.dropna().unique()

            # Check for boolean FIRST (before numeric)
            if len(unique_vals) <= 2:
                bool_vals = {"true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"}
                if all(str(v).lower() in bool_vals for v in unique_vals):
                    column_types[col] = "boolean"
                    continue

            # Try numeric conversion
            numeric_series = pd.to_numeric(series, errors="coerce")
            non_null_count = numeric_series.notna().sum()

            numeric_fraction = non_null_count / total_count

            if numeric_fraction >= self.min_numeric_fraction:
                # Check if it's actually numeric (not just a few numbers)
                if non_null_count >= 3:  # At least 3 numeric values
                    column_types[col] = "numeric"
                    numeric_columns.append(col)
                    continue

            # Check for datetime
            try:
                dt_series = pd.to_datetime(series, errors="coerce")
                dt_non_null = dt_series.notna().sum()
                if dt_non_null / total_count >= self.min_numeric_fraction:
                    column_types[col] = "datetime"
                    continue
            except Exception:
                pass

            # Check for categorical (low cardinality) - more lenient for small datasets
            if total_count > 0:
                unique_ratio = len(unique_vals) / total_count
                # For small datasets (< 100 rows), be more lenient
                threshold = 0.1 if total_count < 100 else 0.05
                # Also consider absolute unique count for very small datasets
                if (unique_ratio < threshold and len(unique_vals) < 50) or \
                   (total_count < 20 and len(unique_vals) <= 5):
                    column_types[col] = "categorical"
                    continue

            # Default to text
            column_types[col] = "text"

        return column_types, numeric_columns

    def detect_from_bytes(self, content: bytes, filename: str = "data.csv") -> NumericalDetectionResult:
        """Detect numerical content from raw bytes."""
        if not content:
            return NumericalDetectionResult(
                has_numerical_data=False,
                numeric_columns=[],
                column_types={},
                row_count=0,
                sample_size=0,
                error="Empty content"
            )

        if len(content) > self.max_sample_bytes:
            logger.warning(
                "content_truncated_for_detection",
                filename=filename,
                original_size=len(content),
                sample_size=self.max_sample_bytes
            )

        # Detect format
        format_hint = self._detect_format(content, filename)

        if format_hint == "unknown":
            return NumericalDetectionResult(
                has_numerical_data=False,
                numeric_columns=[],
                column_types={},
                row_count=0,
                sample_size=min(len(content), self.max_sample_bytes),
                error=f"Unsupported or unrecognized format: {filename}"
            )

        try:
            # Read sample
            df = self._read_sample(content, format_hint)

            if df.empty:
                return NumericalDetectionResult(
                    has_numerical_data=False,
                    numeric_columns=[],
                    column_types={},
                    row_count=0,
                    sample_size=min(len(content), self.max_sample_bytes),
                    warnings=["No data rows found in sample"]
                )

            # Analyze columns
            column_types, numeric_columns = self._analyze_columns(df)

            has_numerical = len(numeric_columns) > 0

            warnings = []
            if len(df) >= self.max_sample_rows:
                warnings.append(f"Sample limited to {self.max_sample_rows} rows")
            if len(content) > self.max_sample_bytes:
                warnings.append(f"File truncated to {self.max_sample_bytes} bytes for analysis")

            return NumericalDetectionResult(
                has_numerical_data=has_numerical,
                numeric_columns=numeric_columns,
                column_types=column_types,
                row_count=len(df),
                sample_size=min(len(content), self.max_sample_bytes),
                warnings=warnings
            )

        except Exception as e:
            logger.error("numerical_detection_failed", filename=filename, error=str(e))
            return NumericalDetectionResult(
                has_numerical_data=False,
                numeric_columns=[],
                column_types={},
                row_count=0,
                sample_size=min(len(content), self.max_sample_bytes),
                error=f"Detection failed: {str(e)}"
            )

    async def detect_from_url(
        self,
        url: str,
        allowed_domains: Optional[set[str]] = None,
        timeout: float = 30.0,
    ) -> NumericalDetectionResult:
        """Detect numerical content by downloading from URL."""
        import httpx

        if allowed_domains:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.netloc not in allowed_domains:
                return NumericalDetectionResult(
                    has_numerical_data=False,
                    numeric_columns=[],
                    column_types={},
                    row_count=0,
                    sample_size=0,
                    error=f"Domain not allowed: {parsed.netloc}"
                )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Stream download to limit memory
                async with client.stream("GET", url) as response:
                    response.raise_for_status()

                    content = b""
                    async for chunk in response.aiter_bytes():
                        content += chunk
                        if len(content) > self.max_sample_bytes:
                            break

                # Get filename from URL or Content-Disposition
                filename = url.split("/")[-1] or "data.csv"
                if "content-disposition" in response.headers:
                    import re
                    cd = response.headers["content-disposition"]
                    match = re.search(r'filename[*]?=([^;]+)', cd)
                    if match:
                        filename = match.group(1).strip('"')

                return self.detect_from_bytes(content, filename)

        except Exception as e:
            logger.error("url_numerical_detection_failed", url=url, error=str(e))
            return NumericalDetectionResult(
                has_numerical_data=False,
                numeric_columns=[],
                column_types={},
                row_count=0,
                sample_size=0,
                error=f"Download or detection failed: {str(e)}"
            )


# Convenience function
def detect_numerical_content(
    content: bytes,
    filename: str = "data.csv",
    max_sample_rows: int = 10000,
) -> NumericalDetectionResult:
    """Convenience function for numerical content detection."""
    detector = NumericalDetector(max_sample_rows=max_sample_rows)
    return detector.detect_from_bytes(content, filename)