"""Search service main module."""

import structlog
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

import asyncpg

from services.search.src.config import settings
from services.search.src.embedding.service import get_embedding_service, initialize_embedding_service
from services.search.src.retrieval.vector_search import (
    VectorSearchRetriever,
    HybridRetriever,
    SearchResult,
    SearchResults,
)
from services.search.src.classification.query_classifier import (
    QueryClassifier,
    ClassificationResult,
    CombustionSubtopic,
)
from services.search.src.reranking.cross_encoder import get_reranker, RerankedResult

logger = structlog.get_logger()


@dataclass
class SearchResponse:
    """Complete search response matching the API contract."""
    query: str
    status: str  # "matches_found" | "no_matches"
    source_collection: str
    data_filter: str
    total_matches: int
    datasets: List[Dict[str, Any]]
    search_metadata: Dict[str, Any]


class SearchService:
    """Main search service orchestrating all search components."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.vector_retriever = VectorSearchRetriever(pool)
        self.hybrid_retriever = HybridRetriever(pool)
        self.classifier = QueryClassifier()
        self.reranker = get_reranker()

    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> SearchResponse:
        """
        Main search entry point.
        
        Performs:
        1. Query classification
        2. Vector/hybrid retrieval
        3. Reranking (if enabled)
        4. Filter application
        5. Response formatting
        """
        start_time = time.time()

        filters = filters or {}
        options = options or {}

        logger.info("search_started", query=query[:100])

        # Step 1: Classify query
        classification = self.classifier.classify(query)
        logger.info(
            "query_classified",
            subtopic=classification.subtopic.value,
            confidence=classification.confidence,
        )

        # Step 2: Apply classification-based filters if not explicitly provided
        search_filters = self._merge_filters(classification.suggested_filters, filters)

        # Step 3: Choose retrieval strategy
        use_hybrid = options.get("hybrid", True)
        use_rerank = options.get("rerank", settings.SEARCH_RERANK_ENABLED)

        min_score = options.get("minScore", settings.SEARCH_MIN_SCORE)
        max_results = options.get("maxResults", settings.SEARCH_MAX_RESULTS)

        # Step 4: Retrieve
        if use_hybrid:
            retrieval_results = await self.hybrid_retriever.search(
                query=query,
                min_similarity=min_score,
                match_count=max_results * 2,  # Fetch extra for reranking
                filter_psi_ids=search_filters.get("psi_ids"),
                filter_verification=search_filters.get("verification_status"),
                filter_formats=search_filters.get("formats"),
            )
            results = retrieval_results.results
        else:
            retrieval_results = await self.vector_retriever.search(
                query=query,
                min_similarity=min_score,
                match_count=max_results * 2,
                filter_psi_ids=search_filters.get("psi_ids"),
                filter_verification=search_filters.get("verification_status"),
                filter_formats=search_filters.get("formats"),
            )
            results = retrieval_results.results

        # Step 5: Rerank if enabled
        if use_rerank and results:
            reranked = self.reranker.rerank(query, results, top_k=max_results)
            results = [r.result for r in reranked]
        else:
            results = results[:max_results]

        # Step 6: Format response
        response = self._format_response(
            query=query,
            results=results,
            classification=classification,
            retrieval_time=retrieval_results.processing_time_ms if 'retrieval_results' in locals() else 0,
            total_time=(time.time() - start_time) * 1000,
        )

        logger.info(
            "search_completed",
            query=query[:100],
            total_matches=response.total_matches,
            processing_time_ms=response.search_metadata["processingTimeMs"],
        )

        return response

    def _merge_filters(
        self,
        suggested: Dict[str, List[str]],
        explicit: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        """Merge suggested and explicit filters. Explicit filters take precedence."""
        merged = {}

        # Explicit filters override suggested
        for key, value in suggested.items():
            if key not in explicit:
                merged[key] = value

        # Add explicit filters
        for key, value in explicit.items():
            if isinstance(value, list):
                merged[key] = value
            else:
                merged[key] = [value]

        return merged

    def _format_response(
        self,
        query: str,
        results: List[SearchResult],
        classification: ClassificationResult,
        retrieval_time: float,
        total_time: float,
    ) -> SearchResponse:
        """Format results into API response."""
        datasets = []
        for result in results:
            datasets.append({
                "id": result.dataset_id,
                "psiId": result.psi_id,
                "name": result.name,
                "description": result.description or "",
                "url": result.url,
                "format": result.format,
                "numericColumns": result.numeric_columns,
                "score": result.score,
                "investigationTitle": result.investigation_title,
                "verificationStatus": result.verification_status,
            })

        status = "matches_found" if datasets else "no_matches"

        return SearchResponse(
            query=query,
            status=status,
            source_collection=settings.SOURCE_COLLECTION,
            data_filter=settings.DATA_FILTER,
            total_matches=len(datasets),
            datasets=datasets,
            search_metadata={
                "catalogVersion": settings.CATALOG_VERSION,
                "embeddingModel": settings.EMBEDDING_MODEL,
                "embeddingVersion": settings.EMBEDDING_VERSION,
                "retrievedAt": time.time(),
                "processingTimeMs": round(total_time, 2),
                "retrievalTimeMs": round(retrieval_time, 2),
                "classification": {
                    "subtopic": classification.subtopic.value,
                    "confidence": classification.confidence,
                    "isCombustionRelated": classification.is_combustion_related,
                },
            },
        )

    async def get_similar_datasets(
        self,
        dataset_id: str,
        match_count: int = 10,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Find datasets similar to a given dataset."""
        results = await self.vector_retriever.get_similar_datasets(
            dataset_id=dataset_id,
            match_count=match_count,
            min_similarity=min_similarity,
        )

        return [{
            "id": r.dataset_id,
            "psiId": r.psi_id,
            "name": r.name,
            "description": r.description or "",
            "url": r.url,
            "format": r.format,
            "numericColumns": r.numeric_columns,
            "score": r.score,
            "investigationTitle": r.investigation_title,
            "verificationStatus": r.verification_status,
        } for r in results]

    async def health_check(self) -> Dict[str, Any]:
        """Check search service health."""
        embedding_healthy = await get_embedding_service().health_check()

        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_healthy = True
        except Exception:
            db_healthy = False

        return {
            "status": "healthy" if (embedding_healthy and db_healthy) else "degraded",
            "embedding_service": "healthy" if embedding_healthy else "unhealthy",
            "database": "healthy" if db_healthy else "unhealthy",
            "reranker": type(self.reranker).__name__,
        }


# Global service instance
_search_service: Optional["SearchService"] = None


def get_search_service() -> "SearchService":
    """Get global search service instance."""
    global _search_service
    if _search_service is None:
        raise RuntimeError("Search service not initialized")
    return _search_service


async def initialize_search_service(pool: asyncpg.Pool) -> "SearchService":
    """Initialize global search service."""
    global _search_service

    # Initialize embedding service first
    await initialize_embedding_service()

    _search_service = SearchService(pool)
    logger.info("search_service_initialized")
    return _search_service


async def close_search_service():
    """Close global search service."""
    global _search_service
    _search_service = None