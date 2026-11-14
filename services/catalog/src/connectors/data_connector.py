"""Data connectors for accessing dataset files."""

import io
import structlog
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, AsyncIterator

import pandas as pd
import httpx

logger = structlog.get_logger()


@dataclass
class ConnectorConfig:
    """Configuration for data connectors."""

    max_rows: int = 100000
    max_bytes: int = 500 * 1024 * 1024  # 500 MB
    chunk_size: int = 8192
    timeout: float = 60.0


@dataclass
class DataPreview:
    """Preview of dataset data."""

    columns: list[str]
    dtypes: dict[str, str]
    rows: list[dict]
    total_rows: int
    sample_rows: int


class BaseConnector(ABC):
    """Base class for data connectors."""

    def __init__(self, config: Optional[ConnectorConfig] = None):
        self.config = config or ConnectorConfig()

    @abstractmethod
    async def connect(self, url: str) -> bool:
        """Establish connection to data source."""
        pass

    @abstractmethod
    async def get_preview(self, limit: int = 100, offset: int = 0) -> DataPreview:
        """Get a preview of the data."""
        pass

    @abstractmethod
    async def get_schema(self) -> dict:
        """Get schema information."""
        pass

    @abstractmethod
    async def query(self, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
        """Execute a query (for SQL sources)."""
        pass

    @abstractmethod
    async def iter_chunks(self, chunk_size: Optional[int] = None) -> AsyncIterator[pd.DataFrame]:
        """Iterate over data in chunks."""
        pass

    @abstractmethod
    async def close(self):
        """Close connection."""
        pass


class HTTPConnector(BaseConnector):
    """Connector for HTTP/HTTPS data sources (CSV, Parquet, JSON, etc.)."""

    SUPPORTED_FORMATS = {
        "csv", "tsv", "parquet", "json", "jsonl",
        "xlsx", "xls", "feather", "orc"
    }

    def __init__(
        self,
        url: str,
        config: Optional[ConnectorConfig] = None,
        allowed_domains: Optional[set[str]] = None,
    ):
        super().__init__(config)
        self.url = url
        self.allowed_domains = allowed_domains or {
            "psi.nasa.gov",
            "raw.githubusercontent.com",
            "data.nasa.gov",
            "doi.org",
            "github.com",
            "githubusercontent.com",
        }
        self._client: Optional[httpx.AsyncClient] = None
        self._data: Optional[pd.DataFrame] = None
        self._format: Optional[str] = None
        self._content: Optional[bytes] = None

    def _validate_domain(self) -> bool:
        """Validate that URL domain is allowed."""
        from urllib.parse import urlparse
        parsed = urlparse(self.url)
        domain = parsed.netloc.lower()
        for allowed in self.allowed_domains:
            if domain == allowed or domain.endswith("." + allowed):
                return True
        return False

    def _detect_format(self, content_type: Optional[str] = None) -> str:
        """Detect file format from URL and content type."""
        from urllib.parse import urlparse
        import mimetypes

        parsed = urlparse(self.url)
        path = parsed.path.lower()

        # Check extension
        for fmt in self.SUPPORTED_FORMATS:
            if path.endswith(f".{fmt}"):
                return fmt

        # Check content type
        if content_type:
            if "csv" in content_type or "comma" in content_type:
                return "csv"
            if "parquet" in content_type:
                return "parquet"
            if "json" in content_type:
                return "json"
            if "excel" in content_type or "spreadsheet" in content_type:
                return "xlsx"

        return "unknown"

    async def connect(self, url: Optional[str] = None) -> bool:
        """Download and parse the data file."""
        if url:
            self.url = url

        # Validate domain
        if not self._validate_domain():
            logger.error("domain_not_allowed", url=self.url)
            raise ValueError(f"Domain not allowed: {self.url}")

        # Download
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.config.timeout))

        try:
            async with self._client.stream("GET", self.url) as response:
                response.raise_for_status()

                # Check content length
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self.config.max_bytes:
                    raise ValueError(f"File too large: {content_length} bytes")

                # Download content
                content = b""
                async for chunk in response.aiter_bytes(self.config.chunk_size):
                    content += chunk
                    if len(content) > self.config.max_bytes:
                        logger.warning("content_truncated", url=self.url)
                        break

                self._content = content
                content_type = response.headers.get("content-type")
                self._format = self._detect_format(content_type)

                # Parse based on format
                await self._parse_content()

                return True

        except Exception as e:
            logger.error("http_connector_connect_failed", url=self.url, error=str(e))
            raise

    async def _parse_content(self):
        """Parse downloaded content into DataFrame."""
        if not self._content or not self._format:
            return

        fmt = self._format.lower()

        try:
            if fmt == "csv":
                self._data = pd.read_csv(
                    io.BytesIO(self._content),
                    nrows=self.config.max_rows,
                    low_memory=False,
                )
            elif fmt == "tsv":
                self._data = pd.read_csv(
                    io.BytesIO(self._content),
                    sep="\t",
                    nrows=self.config.max_rows,
                    low_memory=False,
                )
            elif fmt == "parquet":
                import pyarrow.parquet as pq
                table = pq.read_table(io.BytesIO(self._content))
                self._data = table.to_pandas().head(self.config.max_rows)
            elif fmt == "json":
                self._data = pd.read_json(io.BytesIO(self._content)).head(self.config.max_rows)
            elif fmt == "jsonl":
                self._data = pd.read_json(io.BytesIO(self._content), lines=True).head(self.config.max_rows)
            elif fmt in ("xlsx", "xls"):
                self._data = pd.read_excel(io.BytesIO(self._content)).head(self.config.max_rows)
            else:
                raise ValueError(f"Unsupported format: {fmt}")

        except Exception as e:
            logger.error("content_parsing_failed", url=self.url, format=fmt, error=str(e))
            raise

    async def get_preview(self, limit: int = 100, offset: int = 0) -> DataPreview:
        """Get a preview of the data."""
        if self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")

        # Apply offset and limit
        preview_df = self._data.iloc[offset:offset + limit]

        return DataPreview(
            columns=list(self._data.columns),
            dtypes={col: str(dtype) for col, dtype in self._data.dtypes.items()},
            rows=preview_df.to_dict("records"),
            total_rows=len(self._data),
            sample_rows=len(preview_df),
        )

    async def get_schema(self) -> dict:
        """Get schema information."""
        if self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")

        columns = {}
        for col in self._data.columns:
            series = self._data[col]
            dtype = str(series.dtype)

            # Determine semantic type
            if dtype in ("int64", "float64", "int32", "float32"):
                semantic_type = "numeric"
            elif dtype == "bool":
                semantic_type = "boolean"
            elif "datetime" in dtype:
                semantic_type = "datetime"
            elif dtype == "object":
                # Check if categorical
                unique_ratio = series.nunique() / len(series) if len(series) > 0 else 0
                semantic_type = "categorical" if unique_ratio < 0.05 else "text"
            else:
                semantic_type = "unknown"

            columns[col] = {
                "dtype": dtype,
                "semantic_type": semantic_type,
                "nullable": series.isna().any(),
                "unique_count": int(series.nunique()),
                "null_count": int(series.isna().sum()),
            }

            # Add statistics for numeric columns
            if semantic_type == "numeric":
                numeric = pd.to_numeric(series, errors="coerce")
                if numeric.notna().sum() > 0:
                    columns[col]["statistics"] = {
                        "min": float(numeric.min()),
                        "max": float(numeric.max()),
                        "mean": float(numeric.mean()),
                        "median": float(numeric.median()),
                        "std": float(numeric.std()),
                    }

        return {
            "format": self._format,
            "columns": columns,
            "row_count": len(self._data),
            "byte_size": len(self._content) if self._content else 0,
        }

    async def query(self, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
        """Execute query using pandasql (limited support)."""
        if self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")

        # Use pandas query/eval for simple filtering
        try:
            # This is a simplified implementation
            # For full SQL support, would need pandasql or duckdb
            return self._data.query(sql) if "SELECT" not in sql.upper() else self._data
        except Exception:
            return self._data

    async def iter_chunks(self, chunk_size: Optional[int] = None) -> AsyncIterator[pd.DataFrame]:
        """Iterate over data in chunks."""
        if self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")

        size = chunk_size or self.config.max_rows
        for i in range(0, len(self._data), size):
            yield self._data.iloc[i:i + size]

    async def close(self):
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._data = None
        self._content = None


class ParquetConnector(HTTPConnector):
    """Specialized connector for Parquet files with column projection."""

    async def get_preview(self, limit: int = 100, offset: int = 0, columns: Optional[list[str]] = None) -> DataPreview:
        """Get preview with optional column projection."""
        if self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")

        # If columns specified, we'd need to re-read from parquet with projection
        # For now, just filter the loaded DataFrame
        data = self._data[columns] if columns else self._data
        preview_df = data.iloc[offset:offset + limit]

        return DataPreview(
            columns=list(data.columns),
            dtypes={col: str(dtype) for col, dtype in data.dtypes.items()},
            rows=preview_df.to_dict("records"),
            total_rows=len(data),
            sample_rows=len(preview_df),
        )

    async def iter_chunks(self, chunk_size: Optional[int] = None, columns: Optional[list[str]] = None) -> AsyncIterator[pd.DataFrame]:
        """Iterate with optional column projection."""
        if self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")

        data = self._data[columns] if columns else self._data
        size = chunk_size or self.config.max_rows

        for i in range(0, len(data), size):
            yield data.iloc[i:i + size]


def create_connector(
    url: str,
    format_hint: Optional[str] = None,
    config: Optional[ConnectorConfig] = None,
    allowed_domains: Optional[set[str]] = None,
) -> BaseConnector:
    """Factory function to create appropriate connector."""
    if format_hint == "parquet" or url.lower().endswith(".parquet"):
        return ParquetConnector(url, config, allowed_domains)
    return HTTPConnector(url, config, allowed_domains)