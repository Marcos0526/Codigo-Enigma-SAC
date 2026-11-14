"""Vector search retrieval for datasets."""

import structlog
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

import asyncpg
from pgvector.asyncpg import register_vector

from services.search.src.config import settings
from services.search.src.embedding.service import get_embedding_service

logger = structlog.get_logger()


@dataclass
class SearchResult:
    """Search result with score and metadata."""
    dataset_id: str
    psi_id: str
    name: str
    description: Optional[str]
    url: str
    format: str
    numeric_columns: List[str]
    score: float
    investigation_title: Optional[str]
    verification_status: str


@dataclass
class SearchResults:
    """Complete search results with metadata."""
    query: str
    results: List[SearchResult]
    total_matches: int
    processing_time_ms: float
    embedding_model: str
    embedding_version: str
    catalog_version: str


class VectorSearchRetriever:
    """Retrieves datasets using vector similarity search."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.embedding_service = get_embedding_service()

    async def search(
        self,
        query: str,
        min_similarity: float = None,
        match_count: int = None,
        filter_psi_ids: Optional[List[str]] = None,
        filter_verification: Optional[List[str]] = None,
        filter_formats: Optional[List[str]] = None,
    ) -> SearchResults:
        """Perform vector similarity search."""
        import time
        start_time = time.time()

        min_similarity = min_similarity or settings.SEARCH_MIN_SCORE
        match_count = match_count or settings.SEARCH_MAX_RESULTS

        logger.info(
            "vector_search_started",
            query=query[:100],
            min_similarity=min_similarity,
            match_count=match_count,
        )

        # Generate query embedding
        query_embedding = await self.embedding_service.embed_single(query)

        # Build and execute search query
        results = await self._execute_search(
            query_embedding=query_embedding,
            min_similarity=min_similarity,
            match_count=match_count,
            filter_psi_ids=filter_psi_ids,
            filter_verification=filter_verification,
            filter_formats=filter_formats,
        )

        processing_time = (time.time() - start_time) * 1000

        search_results = SearchResults(
            query=query,
            results=results,
            total_matches=len(results),
            processing_time_ms=round(processing_time, 2),
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_version=settings.EMBEDDING_VERSION,
            catalog_version=settings.CATALOG_VERSION,
        )

        logger.info(
            "vector_search_completed",
            query=query[:100],
            total_matches=len(results),
            processing_time_ms=search_results.processing_time_ms,
        )

        return search_results

    async def _execute_search(
        self,
        query_embedding: List[float],
        min_similarity: float,
        match_count: int,
        filter_psi_ids: Optional[List[str]],
        filter_verification: Optional[List[str]],
        filter_formats: Optional[List[str]],
    ) -> List[SearchResult]:
        """Execute the vector search query."""
        # Convert embedding to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Build filter conditions
        params = [embedding_str, min_similarity, match_count]
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
            params.extend(filter_verification)
            param_idx += len(filter_verification)

        fmt_filter = ""
        if filter_formats:
            placeholders = ",".join([f"${i}" for i in range(param_idx, param_idx + len(filter_formats))])
            fmt_filter = f"AND d.format IN ({placeholders})"
            params.extend(filter_formats)

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
              {fmt_filter}
            ORDER BY de.embedding <=> $1::vector
            LIMIT $3
        """

        async with self.pool.acquire() as conn:
            await register_vector(conn)
            rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            results.append(SearchResult(
                dataset_id=row["dataset_id"],
                psi_id=row["psi_id"],
                name=row["name"],
                description=row["description"],
                url=row["url"],
                format=row["format"],
                numeric_columns=row["numeric_columns"],
                score=round(float(row["score"]), 4),
                investigation_title=row["investigation_title"],
                verification_status=row["verification_status"],
            ))

        return results

    async def get_similar_datasets(
        self,
        dataset_id: str,
        match_count: int = 10,
        min_similarity: float = 0.5,
    ) -> List[SearchResult]:
        """Find datasets similar to a given dataset."""
        # Get the dataset's embedding
        async with self.pool.acquire() as conn:
            await register_vector(conn)
            row = await conn.fetchrow(
                """
                SELECT de.embedding, d.psi_id
                FROM dataset_embeddings de
                JOIN datasets d ON d.id = de.dataset_id
                WHERE d.dataset_id = $1
                """,
                dataset_id
            )

        if not row:
            return []

        query_embedding = row["embedding"]
        psi_id = row["psi_id"]

        # Search excluding the source dataset
        results = await self._execute_search(
            query_embedding=query_embedding,
            min_similarity=min_similarity,
            match_count=match_count + 1,  # +1 to account for self
            filter_verification=["verified"],
        )

        # Filter out the source dataset
        return [r for r in results if r.dataset_id != dataset_id][:match_count]


class HybridRetriever:
    """Combines vector search with keyword/BM25 search."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.vector_retriever = VectorSearchRetriever(pool)

    async def search(
        self,
        query: str,
        min_similarity: float = None,
        match_count: int = None,
        filter_psi_ids: Optional[List[str]] = None,
        filter_verification: Optional[List[str]] = None,
        filter_formats: Optional[List[str]] = None,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> SearchResults:
        """Perform hybrid search combining vector and keyword search."""
        import time
        start_time = time.time()

        min_similarity = min_similarity or settings.SEARCH_MIN_SCORE
        match_count = match_count or settings.SEARCH_MAX_RESULTS

        # Get vector results (fetch more for reranking)
        vector_results = await self.vector_retriever.search(
            query=query,
            min_similarity=min_similarity,
            match_count=match_count * 2,
            filter_psi_ids=filter_psi_ids,
            filter_verification=filter_verification,
            filter_formats=filter_formats,
        )

        # Get keyword results
        keyword_results = await self._keyword_search(
            query=query,
            match_count=match_count * 2,
            filter_psi_ids=filter_psi_ids,
            filter_verification=filter_verification,
            filter_formats=filter_formats,
        )

        # Combine and rerank
        combined = self._combine_results(
            vector_results.results,
            keyword_results,
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
        )

        # Limit to requested count
        final_results = combined[:match_count]

        processing_time = (time.time() - start_time) * 1000

        return SearchResults(
            query=query,
            results=final_results,
            total_matches=len(final_results),
            processing_time_ms=round(processing_time, 2),
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_version=settings.EMBEDDING_VERSION,
            catalog_version=settings.CATALOG_VERSION,
        )

    async def _keyword_search(
        self,
        query: str,
        match_count: int,
        filter_psi_ids: Optional[List[str]],
        filter_verification: Optional[List[str]],
        filter_formats: Optional[List[str]],
    ) -> List[SearchResult]:
        """Perform keyword search using PostgreSQL full-text search."""
        # Build tsquery from query
        tsquery = " | ".join(query.split())

        params = [tsquery, match_count]
        param_idx = 3

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
            params.extend(filter_verification)
            param_idx += len(filter_verification)

        fmt_filter = ""
        if filter_formats:
            placeholders = ",".join([f"${i}" for i in range(param_idx, param_idx + len(filter_formats))])
            fmt_filter = f"AND d.format IN ({placeholders})"
            params.extend(filter_formats)

        query = f"""
            SELECT
                d.dataset_id,
                d.psi_id,
                d.name,
                d.description,
                d.url,
                d.format,
                d.numeric_columns,
                ts_rank_cd(
                    to_tsvector('english', d.name || ' ' || COALESCE(d.description, '')),
                    to_tsquery('english', $1)
                ) AS score,
                pi.title AS investigation_title,
                d.verification_status
            FROM datasets d
            JOIN psi_investigations pi ON pi.psi_id = d.psi_id
            WHERE to_tsvector('english', d.name || ' ' || COALESCE(d.description, '')) @@ to_tsquery('english', $1)
              AND d.verification_status = 'verified'
              AND d.numeric_columns IS NOT NULL
              AND array_length(d.numeric_columns, 1) > 0
              {psi_filter}
              {ver_filter}
              {fmt_filter}
            ORDER BY score DESC
            LIMIT $2
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            results.append(SearchResult(
                dataset_id=row["dataset_id"],
                psi_id=row["psi_id"],
                name=row["name"],
                description=row["description"],
                url=row["url"],
                format=row["format"],
                numeric_columns=row["numeric_columns"],
                score=round(float(row["score"]), 4),
                investigation_title=row["investigation_title"],
                verification_status=row["verification_status"],
            ))

        return results

    def _combine_results(
        self,
        vector_results: List[SearchResult],
        keyword_results: List[SearchResult],
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> List[SearchResult]:
        """Combine vector and keyword results with weighted scores."""
        # Create score maps
        vector_scores = {r.dataset_id: r.score for r in vector_results}
        keyword_scores = {r.dataset_id: r.score for r in keyword_results}

        # Normalize scores
        max_vector = max(vector_scores.values()) if vector_scores else 1.0
        max_keyword = max(keyword_scores.values()) if keyword_scores else 1.0

        if max_vector > 0:
            vector_scores = {k: v / max_vector for k, v in vector_scores.items()}
        if max_keyword > 0:
            keyword_scores = {k: v / max_keyword for k, v in keyword_scores.items()}

        # Combine all unique dataset IDs
        all_ids = set(vector_scores.keys()) | set(keyword_scores.keys())

        # Calculate combined scores
        combined = []
        for dataset_id in all_ids:
            v_score = vector_scores.get(dataset_id, 0.0)
            k_score = keyword_scores.get(dataset_id, 0.0)
            combined_score = vector_weight * v_score + keyword_weight * k_score

            # Get result object (prefer vector result for metadata)
            result_obj = next((r for r in vector_results if r.dataset_id == dataset_id), None)
            if not result_obj:
                result_obj = next((r for r in keyword_results if r.dataset_id == dataset_id), None)

            if result_obj:
                # Create new result with combined score
                combined.append(SearchResult(
                    dataset_id=result_obj.dataset_id,
                    psi_id=result_obj.psi_id,
                    name=result_obj.name,
                    description=result_obj.description,
                    url=result_obj.url,
                    format=result_obj.format,
                    numeric_columns=result_obj.numeric_columns,
                    score=round(combined_score, 4),
                    investigation_title=result_obj.investigation_title,
                    verification_status=result_obj.verification_status,
                ))

        # Sort by combined score
        combined.sort(key=lambda x: x.score, reverse=True)
        return combined