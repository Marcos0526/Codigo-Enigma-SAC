"""Dataset ingestion from investigation pages and known data sources."""

import hashlib
import mimetypes
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd
import structlog
from bs4 import BeautifulSoup

from services.catalog.src.models.catalog import (
    Dataset,
    DatasetSchema,
    DatasetProfile,
    DataFormat,
    URLType,
    VerificationStatus,
    AccessPolicy,
    ColumnType,
    CATALOG_VERSION,
    EMBEDDING_MODEL,
    EMBEDDING_VERSION,
)
from services.catalog.src.validation.url_validator import URLValidator, URLValidationResult
from services.catalog.src.validation.numerical_detector import NumericalDetector, NumericalDetectionResult
from services.catalog.src.validation.deduplication import (
    DatasetDeduplicator,
    DuplicateCheckResult,
    generate_stable_dataset_id,
)

logger = structlog.get_logger()


@dataclass
class DatasetIngestionResult:
    """Result of dataset ingestion."""

    success: bool
    dataset: Optional[Dataset] = None
    schema: list[DatasetSchema] = None
    profile: Optional[DatasetProfile] = None
    error: Optional[str] = None
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.schema is None:
            self.schema = []


class DatasetIngester:
    """Ingests datasets from investigation pages and data URLs."""

    def __init__(
        self,
        db_pool,
        allowed_domains: Optional[set[str]] = None,
        timeout: float = 60.0,
        max_download_size: int = 100 * 1024 * 1024,  # 100 MB
    ):
        self.db_pool = db_pool
        self.allowed_domains = allowed_domains or {
            "psi.nasa.gov",
            "raw.githubusercontent.com",
            "data.nasa.gov",
            "doi.org",
            "github.com",
            "githubusercontent.com",
        }
        self.timeout = timeout
        self.max_download_size = max_download_size
        self._client: Optional[httpx.AsyncClient] = None
        self.deduplicator = DatasetDeduplicator(db_pool)
        self.numerical_detector = NumericalDetector()

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
        return self._client

    def _detect_format_from_url(self, url: str, content_type: Optional[str] = None) -> DataFormat:
        """Detect data format from URL and content type."""
        parsed = urlparse(url)
        path = parsed.path.lower()

        # Check file extension
        if path.endswith(".csv"):
            return DataFormat.CSV
        elif path.endswith(".parquet"):
            return DataFormat.PARQUET
        elif path.endswith(".json") or path.endswith(".jsonl"):
            return DataFormat.JSON
        elif path.endswith(".xlsx") or path.endswith(".xls"):
            return DataFormat.XLSX

        # Check content type
        if content_type:
            if "csv" in content_type:
                return DataFormat.CSV
            elif "parquet" in content_type:
                return DataFormat.PARQUET
            elif "json" in content_type:
                return DataFormat.JSON
            elif "excel" in content_type or "spreadsheet" in content_type:
                return DataFormat.XLSX

        return DataFormat.UNKNOWN

    def _classify_url_type(self, url: str, content_type: Optional[str] = None) -> URLType:
        """Classify URL type."""
        parsed = urlparse(url)
        path = parsed.path.lower()

        # DOI
        if "doi.org" in parsed.netloc:
            return URLType.DOI

        # PSI investigation page pattern
        if re.match(r".*/physci/repo/data/investigations/PSI-\d+/?$", url):
            return URLType.INVESTIGATION_PAGE

        # Direct download extensions
        for ext in [".csv", ".parquet", ".json", ".jsonl", ".xlsx", ".xls", ".tsv", ".txt", ".zip"]:
            if path.endswith(ext):
                return URLType.DIRECT_DOWNLOAD

        # Check content type
        if content_type:
            data_types = ["csv", "parquet", "json", "excel", "octet-stream", "zip"]
            if any(dt in content_type.lower() for dt in data_types):
                return URLType.DIRECT_DOWNLOAD

        return URLType.UNVERIFIED

    async def discover_dataset_urls(self, investigation_page_url: str) -> list[str]:
        """Discover dataset URLs from an investigation page."""
        try:
            client = self._get_client()
            response = await client.get(investigation_page_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            urls = set()

            # Find all links
            for link in soup.find_all("a", href=True):
                href = link["href"]
                full_url = urljoin(investigation_page_url, href)

                # Filter for likely data files
                parsed = urlparse(full_url)
                path = parsed.path.lower()

                # Check for data file extensions
                data_extensions = [
                    ".csv", ".parquet", ".json", ".jsonl", ".xlsx", ".xls",
                    ".tsv", ".txt", ".dat", ".nc", ".hdf5", ".h5", ".fits",
                    ".zip", ".gz", ".tar", ".tgz"
                ]

                if any(path.endswith(ext) for ext in data_extensions):
                    urls.add(full_url)

                # Check for "data" or "download" in link text or URL
                link_text = link.get_text(strip=True).lower()
                if any(keyword in link_text for keyword in ["data", "download", "dataset", "file"]):
                    if any(path.endswith(ext) for ext in data_extensions):
                        urls.add(full_url)

            logger.info("discovered_dataset_urls", investigation_url=investigation_page_url, count=len(urls))
            return list(urls)

        except Exception as e:
            logger.error("discover_dataset_urls_failed", url=investigation_page_url, error=str(e))
            return []

    async def download_and_analyze(self, url: str) -> tuple[Optional[bytes], URLValidationResult]:
        """Download dataset content and validate URL."""
        # First validate URL
        async with URLValidator(allowed_domains=self.allowed_domains) as validator:
            validation = await validator.validate_url(url)

        if not validation.is_valid:
            return None, validation

        # Download content (limited)
        try:
            client = self._get_client()
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                content = b""
                async for chunk in response.aiter_bytes():
                    content += chunk
                    if len(content) > self.max_download_size:
                        logger.warning("download_truncated", url=url, size=len(content))
                        break

                # Update validation with final content type
                content_type = response.headers.get("content-type")
                validation.content_type = content_type

                return content, validation

        except Exception as e:
            logger.error("download_failed", url=url, error=str(e))
            validation.is_valid = False
            validation.error = f"Download failed: {str(e)}"
            return None, validation

    def _infer_column_type(self, series: pd.Series) -> ColumnType:
        """Infer column type from pandas series."""
        total_count = series.notna().sum()
        if total_count == 0:
            return ColumnType.TEXT

        unique = series.dropna().unique()

        # Try numeric
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() / total_count > 0.8:
            return ColumnType.NUMERIC

        # Try datetime
        try:
            dt = pd.to_datetime(series, errors="coerce")
            if dt.notna().sum() / total_count > 0.8:
                return ColumnType.DATETIME
        except Exception:
            pass

        # Check boolean
        if len(unique) <= 2:
            bool_vals = {"true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"}
            if all(str(v).lower() in bool_vals for v in unique):
                return ColumnType.BOOLEAN

        # Check categorical (low cardinality) - more lenient for small datasets
        unique_ratio = len(unique) / total_count
        threshold = 0.1 if total_count < 100 else 0.05
        # Also consider absolute unique count for very small datasets
        if (unique_ratio < threshold and len(unique) < 50) or \
           (total_count < 20 and len(unique) <= 5):
            return ColumnType.CATEGORICAL

        return ColumnType.TEXT

    def _compute_column_statistics(self, series: pd.Series, col_type: ColumnType) -> Optional[dict]:
        """Compute statistics for a column."""
        if col_type != ColumnType.NUMERIC:
            return None

        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() == 0:
            return None

        return {
            "count": int(numeric.notna().sum()),
            "null_count": int(numeric.isna().sum()),
            "min": float(numeric.min()),
            "max": float(numeric.max()),
            "mean": float(numeric.mean()),
            "median": float(numeric.median()),
            "std": float(numeric.std()),
            "q1": float(numeric.quantile(0.25)),
            "q2": float(numeric.quantile(0.5)),
            "q3": float(numeric.quantile(0.75)),
        }

    async def ingest_from_url(
        self,
        url: str,
        investigation_psi_id: str,
        investigation_title: str,
    ) -> DatasetIngestionResult:
        """Ingest a single dataset from a URL."""
        logger.info("ingesting_dataset_from_url", url=url, psi_id=investigation_psi_id)

        # Download and validate
        content, validation = await self.download_and_analyze(url)
        if not validation.is_valid or content is None:
            return DatasetIngestionResult(
                success=False,
                error=f"URL validation/download failed: {validation.error}"
            )

        # Detect numerical content
        filename = urlparse(url).path.split("/")[-1] or "data.csv"
        detection = self.numerical_detector.detect_from_bytes(content, filename)

        if not detection.has_numerical_data:
            logger.info("no_numerical_data", url=url)
            return DatasetIngestionResult(
                success=False,
                error="No numerical data detected in dataset",
                warnings=detection.warnings
            )

        # Check for duplicates
        dataset_metadata = {
            "name": f"{investigation_psi_id} - {filename}",
            "psi_id": investigation_psi_id,
            "url": url,
            "numeric_columns": detection.numeric_columns,
            "provenance_dataset_url": url,
        }

        duplicate_check = await self.deduplicator.check_all(dataset_metadata, content)
        if duplicate_check.is_duplicate:
            logger.info("duplicate_dataset_skipped", existing_id=duplicate_check.existing_dataset_id)
            return DatasetIngestionResult(
                success=False,
                error=f"Duplicate dataset found: {duplicate_check.existing_dataset_id}",
                warnings=[f"Duplicate of {duplicate_check.existing_dataset_id} ({duplicate_check.match_type})"]
            )

        # Determine format and URL type
        data_format = self._detect_format_from_url(url, validation.content_type)
        url_type = self._classify_url_type(url, validation.content_type)

        # Generate stable dataset ID
        dataset_id = generate_stable_dataset_id(
            investigation_psi_id,
            filename,
            url
        )

        # Parse DataFrame for schema extraction
        try:
            df = self.numerical_detector._read_sample(content, data_format.value.lower())
        except Exception as e:
            logger.error("schema_extraction_failed", url=url, error=str(e))
            return DatasetIngestionResult(
                success=False,
                error=f"Failed to parse dataset for schema: {str(e)}"
            )

        # Build schema
        schema = []
        for i, col in enumerate(df.columns):
            col_type = self._infer_column_type(df[col])
            statistics = self._compute_column_statistics(df[col], col_type)

            schema.append(DatasetSchema(
                dataset_id=None,  # Will be set after dataset insert
                column_name=col,
                column_type=col_type,
                description=None,
                unit=None,
                nullable=df[col].isna().any(),
                sample_values=df[col].dropna().head(5).tolist() if col_type != ColumnType.TEXT else None,
                statistics=statistics,
                ordinal_position=i,
                profile_version="1.0.0",
            ))

        # Create dataset model
        dataset = Dataset(
            dataset_id=dataset_id,
            psi_id=investigation_psi_id,
            name=f"{investigation_psi_id} - {filename}",
            description=f"Dataset from {investigation_title} ({investigation_psi_id}): {filename}",
            url=url,
            url_type=url_type,
            format=data_format,
            numeric_columns=detection.numeric_columns,
            source="NASA PSI",
            license="Public Domain",
            access_policy=AccessPolicy.PUBLIC,
            coverage_temporal=None,
            coverage_geographic="ISS Microgravity",
            catalog_version=CATALOG_VERSION,
            embedding_model=EMBEDDING_MODEL,
            embedding_version=EMBEDDING_VERSION,
            verification_status=VerificationStatus.VERIFIED if detection.has_numerical_data else VerificationStatus.PENDING,
            verified_at=None,
            tags=["nasa-psi", "combustion-science", investigation_psi_id.lower()],
            provenance_investigation_url=f"https://psi.nasa.gov/physci/repo/data/investigations/{investigation_psi_id}",
            provenance_dataset_url=url,
        )

        # Create profile
        profile = DatasetProfile(
            dataset_id=None,  # Will be set after dataset insert
            row_count=len(df),
            byte_size=len(content),
            column_count=len(df.columns),
            profile_version="1.0.0",
            profiling_duration_ms=None,
            warnings=detection.warnings,
        )

        # Store in database
        try:
            async with self.db_pool.acquire() as conn:
                # Insert dataset
                dataset_row = await conn.fetchrow(
                    """
                    INSERT INTO datasets (
                        dataset_id, psi_id, name, description, url, url_type, format,
                        numeric_columns, source, license, access_policy,
                        coverage_temporal, coverage_geographic, catalog_version,
                        embedding_model, embedding_version, verification_status,
                        verified_at, tags, provenance_investigation_url,
                        provenance_dataset_url
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                    ON CONFLICT (dataset_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        url = EXCLUDED.url,
                        url_type = EXCLUDED.url_type,
                        format = EXCLUDED.format,
                        numeric_columns = EXCLUDED.numeric_columns,
                        verification_status = EXCLUDED.verification_status,
                        verified_at = EXCLUDED.verified_at,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    dataset.dataset_id,
                    dataset.psi_id,
                    dataset.name,
                    dataset.description,
                    dataset.url,
                    dataset.url_type.value,
                    dataset.format.value,
                    dataset.numeric_columns,
                    dataset.source,
                    dataset.license,
                    dataset.access_policy.value,
                    dataset.coverage_temporal,
                    dataset.coverage_geographic,
                    dataset.catalog_version,
                    dataset.embedding_model,
                    dataset.embedding_version,
                    dataset.verification_status.value,
                    dataset.verified_at,
                    dataset.tags,
                    dataset.provenance_investigation_url,
                    dataset.provenance_dataset_url,
                )

                dataset_db_id = dataset_row["id"]

                # Insert schema
                for col_schema in schema:
                    await conn.execute(
                        """
                        INSERT INTO dataset_schemas (
                            dataset_id, column_name, column_type, description, unit,
                            nullable, sample_values, statistics, ordinal_position, profile_version
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (dataset_id, column_name) DO UPDATE SET
                            column_type = EXCLUDED.column_type,
                            description = EXCLUDED.description,
                            unit = EXCLUDED.unit,
                            nullable = EXCLUDED.nullable,
                            sample_values = EXCLUDED.sample_values,
                            statistics = EXCLUDED.statistics,
                            ordinal_position = EXCLUDED.ordinal_position,
                            profile_version = EXCLUDED.profile_version
                        """,
                        dataset_db_id,
                        col_schema.column_name,
                        col_schema.column_type.value,
                        col_schema.description,
                        col_schema.unit,
                        col_schema.nullable,
                        col_schema.sample_values,
                        col_schema.statistics,
                        col_schema.ordinal_position,
                        col_schema.profile_version,
                    )

                # Insert profile
                await conn.execute(
                    """
                    INSERT INTO dataset_profiles (
                        dataset_id, row_count, byte_size, column_count,
                        profile_version, profiling_duration_ms, warnings
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (dataset_id) DO UPDATE SET
                        row_count = EXCLUDED.row_count,
                        byte_size = EXCLUDED.byte_size,
                        column_count = EXCLUDED.column_count,
                        profile_version = EXCLUDED.profile_version,
                        profiling_duration_ms = EXCLUDED.profiling_duration_ms,
                        warnings = EXCLUDED.warnings
                    """,
                    dataset_db_id,
                    profile.row_count,
                    profile.byte_size,
                    profile.column_count,
                    profile.profile_version,
                    profile.profiling_duration_ms,
                    profile.warnings,
                )

        except Exception as e:
            logger.error("dataset_db_insert_failed", dataset_id=dataset_id, error=str(e))
            return DatasetIngestionResult(
                success=False,
                error=f"Database insert failed: {str(e)}"
            )

        return DatasetIngestionResult(
            success=True,
            dataset=dataset,
            schema=schema,
            profile=profile,
            warnings=detection.warnings
        )

    async def ingest_investigation_datasets(self, psi_id: str) -> list[DatasetIngestionResult]:
        """Ingest all datasets for a given investigation."""
        # Get investigation title
        async with self.db_pool.acquire() as conn:
            inv = await conn.fetchrow(
                "SELECT title, psi_record_url FROM psi_investigations WHERE psi_id = $1",
                psi_id
            )

        if not inv:
            logger.warning("investigation_not_found", psi_id=psi_id)
            return []

        investigation_title = inv["title"]
        investigation_url = inv["psi_record_url"]

        # Discover dataset URLs
        dataset_urls = await self.discover_dataset_urls(investigation_url)

        # Also check for known data URLs pattern
        known_patterns = [
            f"https://psi.nasa.gov/physci/repo/data/investigations/{psi_id}/data/",
            f"https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/{psi_id.lower()}/",
        ]

        for pattern in known_patterns:
            try:
                client = self._get_client()
                resp = await client.get(pattern)
                if resp.status_code == 200:
                    # Try to parse directory listing or find data files
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for link in soup.find_all("a", href=True):
                        full_url = urljoin(pattern, link["href"])
                        if full_url not in dataset_urls:
                            dataset_urls.append(full_url)
            except Exception:
                pass

        # Ingest each discovered URL
        results = []
        for url in dataset_urls:
            result = await self.ingest_from_url(url, psi_id, investigation_title)
            results.append(result)
            if result.success:
                logger.info("dataset_ingested", dataset_id=result.dataset.dataset_id, url=url)
            else:
                logger.warning("dataset_ingestion_failed", url=url, error=result.error)

        return results


async def run_dataset_ingestion(
    db_pool,
    psi_ids: Optional[list[str]] = None,
    allowed_domains: Optional[set[str]] = None,
) -> dict[str, list[DatasetIngestionResult]]:
    """Convenience function to run dataset ingestion for investigations."""
    async with DatasetIngester(db_pool, allowed_domains) as ingester:
        if psi_ids is None:
            # Get all verified investigations
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT psi_id FROM psi_investigations WHERE metadata_status = 'verified'"
                )
                psi_ids = [row["psi_id"] for row in rows]

        results = {}
        for psi_id in psi_ids:
            results[psi_id] = await ingester.ingest_investigation_datasets(psi_id)

        return results