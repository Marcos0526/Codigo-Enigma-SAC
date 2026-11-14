"""Summarizer service main module."""

import structlog
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

import asyncpg

from services.summarizer.src.config import settings
from services.summarizer.src.profiling.dataset_profiler import (
    DatasetProfiler,
    DatasetProfile,
    ColumnProfile,
)
from services.summarizer.src.llm.client import get_llm_client, LLMClient
from services.summarizer.src.prompts.summary_prompts import (
    PromptContext,
    build_prompt,
    parse_summary_response,
    generate_descriptive_summary,
)

logger = structlog.get_logger()


@dataclass
class SummaryRequest:
    """Request for summary generation."""
    dataset_id: str
    include_statistics: bool = True
    max_length: int = 1000


@dataclass
class SummaryResponse:
    """Summary generation response."""
    dataset_id: str
    title: str
    executive_summary: str
    key_variables: List[str]
    coverage: Dict[str, Any]
    findings: List[Dict[str, str]]
    limitations: List[str]
    warnings: List[str]
    sources: List[Dict[str, str]]
    generated_at: str
    catalog_version: str
    profiling_version: str
    generation_time_ms: float
    tokens_used: int = 0


class SummarizerService:
    """Main summarizer service orchestrating profiling and LLM generation."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.profiler = DatasetProfiler()
        self.llm_client: Optional[LLMClient] = None

    async def initialize(self):
        """Initialize LLM client."""
        self.llm_client = get_llm_client()
        logger.info("summarizer_service_initialized", provider=settings.LLM_PROVIDER)

    async def generate_summary(self, request: SummaryRequest) -> SummaryResponse:
        """Generate evidence-based summary for a dataset."""
        start_time = time.time()

        logger.info("summary_generation_started", dataset_id=request.dataset_id)

        # Step 1: Get dataset metadata from catalog
        dataset_metadata = await self._get_dataset_metadata(request.dataset_id)
        if not dataset_metadata:
            raise ValueError(f"Dataset not found: {request.dataset_id}")

        # Step 2: Get column profiles (schema + statistics)
        column_profiles = await self._get_column_profiles(request.dataset_id)

        # Step 3: Get dataset profile (row count, etc.)
        profile = await self._get_dataset_profile(request.dataset_id)

        # Step 4: Build prompt context
        context = self._build_context(
            dataset_metadata=dataset_metadata,
            column_profiles=column_profiles,
            profile=profile,
        )

        # Step 5: Generate summary
        if request.include_statistics and profile and profile.columns:
            summary = await self._generate_llm_summary(context, request.max_length)
        else:
            summary = self._generate_descriptive_summary(context)

        # Step 6: Format response
        generation_time = round((time.time() - start_time) * 1000, 2)

        response = SummaryResponse(
            dataset_id=request.dataset_id,
            title=summary.get("title", context.name),
            executive_summary=summary.get("executiveSummary", ""),
            key_variables=summary.get("keyVariables", []),
            coverage=summary.get("coverage", {}),
            findings=summary.get("findings", []),
            limitations=summary.get("limitations", []),
            warnings=summary.get("warnings", []),
            sources=summary.get("sources", []),
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            catalog_version=settings.CATALOG_VERSION,
            profiling_version=profile.profiling_version if profile else "unknown",
            generation_time_ms=generation_time,
        )

        # Step 7: Log generation for audit trail
        await self._log_generation(request.dataset_id, response)

        logger.info(
            "summary_generation_completed",
            dataset_id=request.dataset_id,
            generation_time_ms=generation_time,
        )

        return response

    async def _get_dataset_metadata(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get dataset metadata from catalog."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT d.*, pi.title as investigation_title
                FROM datasets d
                JOIN psi_investigations pi ON pi.psi_id = d.psi_id
                WHERE d.dataset_id = $1
                """,
                dataset_id
            )
            return dict(row) if row else None

    async def _get_column_profiles(self, dataset_id: str) -> List[ColumnProfile]:
        """Get column profiles from catalog."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM dataset_schemas
                WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
                ORDER BY ordinal_position
                """,
                dataset_id
            )

        profiles = []
        for row in rows:
            stats = row["statistics"] if row["statistics"] else {}
            profiles.append(ColumnProfile(
                name=row["column_name"],
                dtype=row["column_type"],
                nullable=row["nullable"],
                null_count=stats.get("null_count", 0),
                null_fraction=stats.get("null_count", 0) / max(stats.get("count", 1), 1),
                unique_count=stats.get("unique_count", 0),
                sample_values=row["sample_values"] or [],
                min_val=stats.get("min"),
                max_val=stats.get("max"),
                mean=stats.get("mean"),
                median=stats.get("median"),
                std=stats.get("std"),
                q1=stats.get("q1"),
                q3=stats.get("q3"),
                top_values=stats.get("top_values"),
                entropy=stats.get("entropy"),
            ))
        return profiles

    async def _get_dataset_profile(self, dataset_id: str) -> Optional[DatasetProfile]:
        """Get dataset profile from catalog."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM dataset_profiles
                WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
                """,
                dataset_id
            )
            if row:
                return DatasetProfile(
                    dataset_id=dataset_id,
                    row_count=row["row_count"],
                    column_count=row["column_count"],
                    byte_size=row["byte_size"],
                    columns=[],  # Filled separately
                    profiling_duration_ms=row["profiling_duration_ms"],
                    memory_used_mb=0,
                    warnings=row["warnings"] or [],
                    profiled_at=row["profiled_at"].isoformat() if row["profiled_at"] else "",
                )
        return None

    def _build_context(
        self,
        dataset_metadata: Dict[str, Any],
        column_profiles: List[ColumnProfile],
        profile: Optional[DatasetProfile],
    ) -> PromptContext:
        """Build prompt context from metadata and profiles."""
        return PromptContext(
            dataset_id=dataset_metadata["dataset_id"],
            name=dataset_metadata["name"],
            description=dataset_metadata["description"] or "",
            psi_id=dataset_metadata["psi_id"],
            investigation_title=dataset_metadata.get("investigation_title", ""),
            format=dataset_metadata["format"],
            url=dataset_metadata["url"],
            url_type=dataset_metadata["url_type"],
            source=dataset_metadata["source"] or "NASA PSI",
            license=dataset_metadata["license"] or "Public Domain",
            access_policy=dataset_metadata["access_policy"],
            tags=dataset_metadata["tags"] or [],
            verification_status=dataset_metadata["verification_status"],
            row_count=profile.row_count if profile else dataset_metadata.get("row_count", 0),
            columns=column_profiles,
            profiling_version=profile.profiling_version if profile else "1.0",
            catalog_version=settings.CATALOG_VERSION,
        )

    async def _generate_llm_summary(self, context: PromptContext, max_length: int) -> Dict[str, Any]:
        """Generate summary using LLM."""
        system_prompt, user_prompt = build_prompt(context)

        try:
            response = await self.llm_client.generate(user_prompt, system_prompt)
            parsed = parse_summary_response(response.content, context)
            return parsed
        except Exception as e:
            logger.error("llm_generation_failed", dataset_id=context.dataset_id, error=str(e))
            # Fallback to descriptive summary
            return parse_summary_response(
                generate_descriptive_summary(context),
                context
            )

    def _generate_descriptive_summary(self, context: PromptContext) -> Dict[str, Any]:
        """Generate descriptive summary without LLM."""
        desc = generate_descriptive_summary(context)
        return parse_summary_response(desc, context)

    async def _log_generation(self, dataset_id: str, response: SummaryResponse):
        """Log summary generation for audit trail."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO summary_generations (
                        dataset_id, request_options, summary, llm_provider,
                        llm_model, tokens_used, generation_time_ms,
                        catalog_version, profiling_version
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    dataset_id,
                    {"include_statistics": True, "max_length": 1000},
                    {
                        "title": response.title,
                        "executiveSummary": response.executive_summary,
                        "keyVariables": response.key_variables,
                        "coverage": response.coverage,
                        "findings": response.findings,
                        "limitations": response.limitations,
                        "warnings": response.warnings,
                        "sources": response.sources,
                    },
                    settings.LLM_PROVIDER,
                    settings.LLM_MODEL,
                    response.tokens_used,
                    response.generation_time_ms,
                    response.catalog_version,
                    response.profiling_version,
                )
        except Exception as e:
            logger.warning("summary_logging_failed", dataset_id=dataset_id, error=str(e))

    async def health_check(self) -> Dict[str, Any]:
        """Check summarizer service health."""
        llm_healthy = False
        if self.llm_client:
            llm_healthy = await self.llm_client.health_check()

        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_healthy = True
        except Exception:
            db_healthy = False

        return {
            "status": "healthy" if (llm_healthy and db_healthy) else "degraded",
            "llm_client": "healthy" if llm_healthy else "unhealthy",
            "database": "healthy" if db_healthy else "unhealthy",
            "llm_provider": settings.LLM_PROVIDER,
            "llm_model": settings.LLM_MODEL,
        }


# Global service instance
_summarizer_service: Optional[SummarizerService] = None


def get_summarizer_service() -> SummarizerService:
    """Get global summarizer service instance."""
    global _summarizer_service
    if _summarizer_service is None:
        raise RuntimeError("Summarizer service not initialized")
    return _summarizer_service


async def initialize_summarizer_service(pool: asyncpg.Pool) -> SummarizerService:
    """Initialize global summarizer service."""
    global _summarizer_service
    _summarizer_service = SummarizerService(pool)
    await _summarizer_service.initialize()
    logger.info("summarizer_service_initialized")
    return _summarizer_service


async def close_summarizer_service():
    """Close global summarizer service."""
    global _summarizer_service
    if _summarizer_service and _summarizer_service.llm_client:
        await _summarizer_service.llm_client.close()
    _summarizer_service = None