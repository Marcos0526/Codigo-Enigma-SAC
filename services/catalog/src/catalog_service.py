"""Catalog service main module."""

import asyncio
import structlog
from contextlib import asynccontextmanager
from typing import Optional, List

import asyncpg
from pgvector.asyncpg import register_vector

from services.catalog.src.models.catalog import (
    Base,
    PSIInvestigation,
    Dataset,
    DatasetSchema,
    DatasetProfile,
    DatasetEmbedding,
    VerificationStatus,
    DataFormat,
    URLType,
    ColumnType,
    AccessPolicy,
)
from services.catalog.src.ingestion.psi_ingester import PSIIngester, run_psi_ingestion
from services.catalog.src.ingestion.dataset_ingester import DatasetIngester, run_dataset_ingestion
from services.catalog.src.validation.url_validator import URLValidator, validate_dataset_url
from services.catalog.src.validation.numerical_detector import NumericalDetector, detect_numerical_content
from services.catalog.src.validation.deduplication import (
    DatasetDeduplicator,
    generate_stable_dataset_id,
)
from services.catalog.src.connectors.data_connector import (
    BaseConnector,
    HTTPConnector,
    ParquetConnector,
    create_connector,
    ConnectorConfig,
    DataPreview,
)

logger = structlog.get_logger()


class CatalogService:
    """Main catalog service for managing NASA PSI datasets."""

    def __init__(
        self,
        database_url: str,
        allowed_domains: Optional[set[str]] = None,
        pool_size: int = 10,
    ):
        self.database_url = database_url
        self.allowed_domains = allowed_domains or {
            "psi.nasa.gov",
            "raw.githubusercontent.com",
            "data.nasa.gov",
            "doi.org",
            "github.com",
            "githubusercontent.com",
        }
        self.pool_size = pool_size
        self._pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize database connection pool."""
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=self.pool_size,
            init=self._init_connection,
        )
        logger.info("catalog_service_initialized", pool_size=self.pool_size)

    async def _init_connection(self, conn: asyncpg.Connection):
        """Initialize connection with pgvector support."""
        await register_vector(conn)

    async def close(self):
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("catalog_service_closed")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a database connection."""
        async with self._pool.acquire() as conn:
            yield conn

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool."""
        if not self._pool:
            raise RuntimeError("Catalog service not initialized")
        return self._pool

    # =========================================================================
    # Investigation Methods
    # =========================================================================

    async def get_investigation(self, psi_id: str) -> Optional[PSIInvestigation]:
        """Get investigation by PSI ID."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM psi_investigations WHERE psi_id = $1",
                psi_id
            )
            return PSIInvestigation(**dict(row)) if row else None

    async def list_investigations(
        self,
        status: Optional[VerificationStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PSIInvestigation]:
        """List investigations with optional filtering."""
        async with self.acquire() as conn:
            query = "SELECT * FROM psi_investigations"
            params = []

            if status:
                query += " WHERE metadata_status = $1"
                params.append(status.value)

            query += " ORDER BY psi_id LIMIT $" + str(len(params) + 1) + " OFFSET $" + str(len(params) + 2)
            params.extend([limit, offset])

            rows = await conn.fetch(query, *params)
            return [PSIInvestigation(**dict(row)) for row in rows]

    async def count_investigations(self, status: Optional[VerificationStatus] = None) -> int:
        """Count investigations."""
        async with self.acquire() as conn:
            if status:
                return await conn.fetchval(
                    "SELECT COUNT(*) FROM psi_investigations WHERE metadata_status = $1",
                    status.value
                )
            return await conn.fetchval("SELECT COUNT(*) FROM psi_investigations")

    # =========================================================================
    # Dataset Methods
    # =========================================================================

    async def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get dataset by stable ID."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM datasets WHERE dataset_id = $1",
                dataset_id
            )
            return Dataset(**dict(row)) if row else None

    async def get_dataset_by_db_id(self, db_id: str) -> Optional[Dataset]:
        """Get dataset by database UUID."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM datasets WHERE id = $1",
                db_id
            )
            return Dataset(**dict(row)) if row else None

    async def list_datasets(
        self,
        psi_id: Optional[str] = None,
        verification_status: Optional[VerificationStatus] = None,
        format: Optional[DataFormat] = None,
        has_numeric: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dataset]:
        """List datasets with filtering."""
        async with self.acquire() as conn:
            query = "SELECT * FROM datasets WHERE 1=1"
            params = []
            param_idx = 1

            if psi_id:
                query += f" AND psi_id = ${param_idx}"
                params.append(psi_id)
                param_idx += 1

            if verification_status:
                query += f" AND verification_status = ${param_idx}"
                params.append(verification_status.value)
                param_idx += 1

            if format:
                query += f" AND format = ${param_idx}"
                params.append(format.value)
                param_idx += 1

            if has_numeric:
                query += " AND numeric_columns IS NOT NULL AND array_length(numeric_columns, 1) > 0"

            query += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
            params.extend([limit, offset])

            rows = await conn.fetch(query, *params)
            return [Dataset(**dict(row)) for row in rows]

    async def count_datasets(
        self,
        psi_id: Optional[str] = None,
        verification_status: Optional[VerificationStatus] = None,
    ) -> int:
        """Count datasets."""
        async with self.acquire() as conn:
            query = "SELECT COUNT(*) FROM datasets WHERE 1=1"
            params = []
            param_idx = 1

            if psi_id:
                query += f" AND psi_id = ${param_idx}"
                params.append(psi_id)
                param_idx += 1

            if verification_status:
                query += f" AND verification_status = ${param_idx}"
                params.append(verification_status.value)
                param_idx += 1

            return await conn.fetchval(query, *params)

    async def get_dataset_schema(self, dataset_id: str) -> List[DatasetSchema]:
        """Get dataset schema."""
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM dataset_schemas
                WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
                ORDER BY ordinal_position
                """,
                dataset_id
            )
            return [DatasetSchema(**dict(row)) for row in rows]

    async def get_dataset_profile(self, dataset_id: str) -> Optional[DatasetProfile]:
        """Get dataset profile."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM dataset_profiles
                WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
                """,
                dataset_id
            )
            return DatasetProfile(**dict(row)) if row else None

    # =========================================================================
    # Search Methods
    # =========================================================================

    async def search_datasets(
        self,
        query_embedding: List[float],
        min_similarity: float = 0.3,
        match_count: int = 50,
        filter_psi_ids: Optional[List[str]] = None,
        filter_verification: Optional[List[VerificationStatus]] = None,
    ) -> List[dict]:
        """Search datasets by vector similarity."""
        async with self.acquire() as conn:
            # Build filter conditions
            params = [query_embedding, min_similarity, match_count]
            param_idx = 4

            psi_filter = ""
            if filter_psi_ids:
                placeholders = ",".join([f"${i}" for i in range(param_idx, param_idx + len(filter_psi_ids))])
                psi_filter = f"AND d.psi_id IN ({placeholders})"
                params.extend(filter_psi_ids)
                param_idx += len(filter_psi_ids)

            ver_filter = ""
            if filter_verification:
                placeholders = ",".join([f"${i}" for i in range(param_idx, param_idx + len(filter_verification))])
                ver_filter = f"AND d.verification_status IN ({placeholders})"
                params.extend([v.value for v in filter_verification])

            query = f"""
                SELECT
                    d.dataset_id,
                    d.psi_id,
                    d.name,
                    d.description,
                    d.url,
                    d.format,
                    d.numeric_columns,
                    1 - (de.embedding <=> $1::vector) AS score,
                    pi.title AS investigation_title,
                    d.verification_status
                FROM datasets d
                JOIN dataset_embeddings de ON de.dataset_id = d.id
                JOIN psi_investigations pi ON pi.psi_id = d.psi_id
                WHERE 1 - (de.embedding <=> $1::vector) >= $2
                  AND d.verification_status = 'verified'
                  AND d.numeric_columns IS NOT NULL
                  AND array_length(d.numeric_columns, 1) > 0
                  {psi_filter}
                  {ver_filter}
                ORDER BY de.embedding <=> $1::vector
                LIMIT $3
            """

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    # =========================================================================
    # Ingestion Methods
    # =========================================================================

    async def ingest_psi_investigations(self) -> List:
        """Ingest all 26 selected PSI investigations."""
        return await run_psi_ingestion(self._pool, self.allowed_domains)

    async def ingest_datasets(self, psi_ids: Optional[List[str]] = None) -> dict:
        """Ingest datasets for investigations."""
        return await run_dataset_ingestion(self._pool, psi_ids, self.allowed_domains)

    # =========================================================================
    # Validation Methods
    # =========================================================================

    async def validate_url(self, url: str) -> dict:
        """Validate a dataset URL."""
        async with URLValidator(allowed_domains=self.allowed_domains) as validator:
            result = await validator.validate_url(url)
            return {
                "is_valid": result.is_valid,
                "url_type": result.url_type,
                "content_type": result.content_type,
                "content_length": result.content_length,
                "error": result.error,
                "final_url": result.final_url,
            }

    async def detect_numerical_content(self, content: bytes, filename: str = "data.csv") -> dict:
        """Detect numerical content in dataset."""
        result = detect_numerical_content(content, filename)
        return {
            "has_numerical_data": result.has_numerical_data,
            "numeric_columns": result.numeric_columns,
            "column_types": result.column_types,
            "row_count": result.row_count,
            "sample_size": result.sample_size,
            "error": result.error,
            "warnings": result.warnings,
        }

    async def check_duplicate(self, dataset_metadata: dict, content: Optional[bytes] = None) -> dict:
        """Check for duplicate dataset."""
        deduplicator = DatasetDeduplicator(self._pool)
        result = await deduplicator.check_all(dataset_metadata, content)
        return {
            "is_duplicate": result.is_duplicate,
            "existing_dataset_id": result.existing_dataset_id,
            "match_type": result.match_type,
            "similarity_score": result.similarity_score,
            "details": result.details,
        }

    # =========================================================================
    # Connector Methods
    # =========================================================================

    def create_connector(
        self,
        url: str,
        format_hint: Optional[str] = None,
        config: Optional[ConnectorConfig] = None,
    ) -> BaseConnector:
        """Create a data connector for a URL."""
        return create_connector(url, format_hint, config, self.allowed_domains)

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict:
        """Check service health."""
        try:
            async with self.acquire() as conn:
                await conn.fetchval("SELECT 1")

            # Check pgvector
            async with self.acquire() as conn:
                await conn.fetchval("SELECT 1 FROM psi_investigations LIMIT 1")

            return {
                "status": "healthy",
                "database": "connected",
                "pool_size": self.pool_size,
            }
        except Exception as e:
            logger.error("health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
            }


# Global service instance
_catalog_service: Optional[CatalogService] = None


async def get_catalog_service() -> CatalogService:
    """Get global catalog service instance."""
    global _catalog_service
    if _catalog_service is None:
        raise RuntimeError("Catalog service not initialized")
    return _catalog_service


async def initialize_catalog_service(
    database_url: str,
    allowed_domains: Optional[set[str]] = None,
    pool_size: int = 10,
) -> CatalogService:
    """Initialize global catalog service."""
    global _catalog_service
    _catalog_service = CatalogService(database_url, allowed_domains, pool_size)
    await _catalog_service.initialize()
    return _catalog_service


async def close_catalog_service():
    """Close global catalog service."""
    global _catalog_service
    if _catalog_service:
        await _catalog_service.close()
        _catalog_service = None