"""Data connectors for fetching dataset data."""

import io
import structlog
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional, Any

import httpx
import pandas as pd

from services.visualization.src.config import settings
from services.visualization.src.validation.column_validator import ColumnValidator, ColumnInfo, ColumnType, create_column_validator

logger = structlog.get_logger()


@dataclass
class ConnectorConfig:
    """Configuration for data connectors."""
    max_rows: int = settings.MAX_CHART_ROWS
    max_bytes: int = settings.MAX_DOWNLOAD_SIZE
    chunk_size: int = 8192
    timeout: float = settings.DOWNLOAD_TIMEOUT


@dataclass
class DataPreview:
    """Preview of dataset data."""
    columns: List[str]
    dtypes: Dict[str, str]
    rows: List[Dict[str, Any]]
    total_rows: int
    sample_rows: int
    column_info: Dict[str, ColumnInfo]


class BaseConnector(ABC):
    """Base class for data connectors."""

    def __init__(self, config: Optional[ConnectorConfig] = None):
        self.config = config or ConnectorConfig()
        self.column_validator = create_column_validator()
        self._data: Optional[pd.DataFrame] = None
        self._column_info: Dict[str, ColumnInfo] = {}

    @abstractmethod
    async def connect(self, url: str) -> bool:
        """Establish connection to data source."""
        pass

    @abstractmethod
    async def get_preview(self, limit: int = 100, offset: int = 0) -> DataPreview:
        """Get a preview of the data."""
        pass

    @abstractmethod
    async def get_data(
        self,
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> pd.DataFrame:
        """Get data with optional filtering and column selection."""
        pass

    @abstractmethod
    async def get_column_info(self) -> Dict[str, ColumnInfo]:
        """Get column type information."""
        pass

    @abstractmethod
    async def close(self):
        """Close connection."""
        pass

    def _analyze_columns(self, df: pd.DataFrame) -> Dict[str, ColumnInfo]:
        """Analyze DataFrame columns."""
        column_info = {}
        for col_name in df.columns:
            series = df[col_name]
            col_type = self.column_validator.infer_column_type(series)

            info = ColumnInfo(
                name=col_name,
                type=col_type,
                nullable=series.isna().any(),
                unique_count=int(series.nunique()) if col_type in (ColumnType.CATEGORICAL, ColumnType.TEXT, ColumnType.BOOLEAN) else None,
                statistics=self._compute_statistics(series, col_type) if col_type == ColumnType.NUMERIC else None,
            )
            column_info[col_name] = info
        return column_info

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
        allowed_domains: Optional[Set[str]] = None,
    ):
        super().__init__(config)
        self.url = url
        self.allowed_domains = allowed_domains or set(settings.allowed_domains_list)
        self._client: Optional[httpx.AsyncClient] = None
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
                    raise ValueError(f"File too large: {content_length} bytes (max {self.config.max_bytes})")

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

            # Analyze columns
            self._column_info = self._analyze_columns(self._data)

        except Exception as e:
            logger.error("content_parsing_failed", url=self.url, format=fmt, error=str(e))
            raise

    async def get_preview(self, limit: int = 100, offset: int = 0) -> DataPreview:
        """Get a preview of the data."""
        if self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")

        # Apply offset and limit
        preview_df = self._data.iloc[offset:offset + min(limit, self.config.max_rows)]

        return DataPreview(
            columns=list(self._data.columns),
            dtypes={col: str(dtype) for col, dtype in self._data.dtypes.items()},
            rows=preview_df.to_dict("records"),
            total_rows=len(self._data),
            sample_rows=len(preview_df),
            column_info=self._column_info,
        )

    async def get_data(
        self,
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> pd.DataFrame:
        """Get data with optional filtering and column selection."""
        if self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")

        data = self._data

        # Apply column selection
        if columns:
            valid_columns = [c for c in columns if c in data.columns]
            if valid_columns:
                data = data[valid_columns]

        # Apply filters (simple equality filters)
        if filters:
            for col, value in filters.items():
                if col in data.columns:
                    data = data[data[col] == value]

        # Apply offset and limit
        if offset:
            data = data.iloc[offset:]
        if limit:
            data = data.head(min(limit, self.config.max_rows))

        return data

    async def get_column_info(self) -> Dict[str, ColumnInfo]:
        """Get column type information."""
        if self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._column_info

    async def close(self):
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._data = None
        self._content = None


class ParquetConnector(HTTPConnector):
    """Specialized connector for Parquet files with column projection."""

    async def get_data(
        self,
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> pd.DataFrame:
        """Get data with optional column projection (more efficient for Parquet)."""
        if self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")

        # For Parquet, we could re-read with column projection
        # For now, use base implementation
        return await super().get_data(columns, filters, limit, offset)


def create_connector(
    url: str,
    format_hint: Optional[str] = None,
    config: Optional[ConnectorConfig] = None,
    allowed_domains: Optional[Set[str]] = None,
) -> BaseConnector:
    """Factory function to create appropriate connector."""
    if format_hint == "parquet" or url.lower().endswith(".parquet"):
        return ParquetConnector(url, config, allowed_domains)
    return HTTPConnector(url, config, allowed_domains)