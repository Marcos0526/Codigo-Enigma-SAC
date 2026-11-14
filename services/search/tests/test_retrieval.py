"""Tests for vector search retrieval."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, AsyncMock

from services.search.src.retrieval.vector_search import (
    VectorSearchRetriever,
    HybridRetriever,
    SearchResult,
    SearchResults,
)
from services.search.src.reranking.cross_encoder import (
    CrossEncoderReranker,
    SimpleReranker,
    RerankedResult,
)
from services.search.src.config import settings


def make_async_context_manager(mock_conn):
    """Create a mock async context manager for pool.acquire()."""
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.return_value = mock_conn
    mock_acquire.__aexit__.return_value = AsyncMock(return_value=None)
    return mock_acquire


class TestVectorSearchRetriever:
    """Tests for vector search retriever."""

    @pytest.fixture
    def mock_pool(self):
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire = MagicMock(return_value=make_async_context_manager(conn))
        return pool

    @pytest.fixture
    def mock_embedding_service(self):
        service = AsyncMock()
        service.embed_single = AsyncMock(return_value=[0.1] * 384)
        return service

    @pytest.fixture
    def retriever(self, mock_pool, mock_embedding_service):
        with patch("services.search.src.retrieval.vector_search.get_embedding_service", return_value=mock_embedding_service):
            return VectorSearchRetriever(mock_pool)

    @pytest.mark.asyncio
    async def test_search_builds_correct_query(self, retriever, mock_pool):
        """Test that search builds correct SQL query."""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []
        mock_pool.acquire.return_value = make_async_context_manager(mock_conn)

        await retriever.search(
            query="test query",
            min_similarity=0.3,
            match_count=10,
        )

        # Verify fetch was called
        mock_conn.fetch.assert_called_once()
        call_args = mock_conn.fetch.call_args
        query_sql = call_args[0][0]

        # Check key parts of query
        assert "dataset_embeddings" in query_sql
        assert "psi_investigations" in query_sql
        assert "<=>" in query_sql  # pgvector distance operator
        assert "verification_status = 'verified'" in query_sql
        assert "numeric_columns IS NOT NULL" in query_sql

    @pytest.mark.asyncio
    async def test_search_with_psi_filter(self, retriever, mock_pool):
        """Test search with PSI ID filter."""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []
        mock_pool.acquire.return_value = make_async_context_manager(mock_conn)

        await retriever.search(
            query="test",
            filter_psi_ids=["PSI-20", "PSI-21"],
        )

        call_args = mock_conn.fetch.call_args
        params = call_args[0][1:]
        query_sql = call_args[0][0]

        assert "PSI-20" in params
        assert "PSI-21" in params
        assert "d.psi_id IN" in query_sql

    @pytest.mark.asyncio
    async def test_search_returns_formatted_results(self, retriever, mock_pool):
        """Test search returns properly formatted results."""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "dataset_id": "test-001",
                "psi_id": "PSI-20",
                "name": "Test Dataset",
                "description": "Test description",
                "url": "https://example.com/data.csv",
                "format": "csv",
                "numeric_columns": ["temp", "pressure"],
                "score": 0.95,
                "investigation_title": "Test Investigation",
                "verification_status": "verified",
            }
        ]
        mock_pool.acquire.return_value = make_async_context_manager(mock_conn)

        results = await retriever.search(query="test")

        assert len(results.results) == 1
        result = results.results[0]
        assert isinstance(result, SearchResult)
        assert result.dataset_id == "test-001"
        assert result.score == 0.95
        assert result.numeric_columns == ["temp", "pressure"]


class TestHybridRetriever:
    """Tests for hybrid retriever."""

    @pytest.fixture
    def mock_pool(self):
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire = MagicMock(return_value=make_async_context_manager(conn))
        return pool

    @pytest.fixture
    def hybrid_retriever(self, mock_pool):
        with patch("services.search.src.retrieval.vector_search.get_embedding_service"):
            return HybridRetriever(mock_pool)

    @pytest.mark.asyncio
    async def test_keyword_search_query(self, hybrid_retriever, mock_pool):
        """Test keyword search builds tsquery correctly."""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []
        mock_pool.acquire.return_value = make_async_context_manager(mock_conn)

        await hybrid_retriever._keyword_search(
            query="combustion temperature",
            match_count=10,
            filter_psi_ids=None,
            filter_verification=None,
            filter_formats=None,
        )

        call_args = mock_conn.fetch.call_args
        params = call_args[0][1:]
        query_sql = call_args[0][0]

        # Check tsquery is built
        assert "to_tsquery" in query_sql
        assert "combustion" in params[0] or "temperature" in params[0]
        assert "@@" in query_sql  # tsvector match operator

    def test_combine_results(self, hybrid_retriever):
        """Test result combination with weighted scores."""
        vector_results = [
            SearchResult(
                dataset_id="ds1", psi_id="PSI-20", name="Dataset 1",
                description="", url="", format="csv", numeric_columns=[],
                score=0.9, investigation_title="", verification_status="verified",
            ),
            SearchResult(
                dataset_id="ds2", psi_id="PSI-21", name="Dataset 2",
                description="", url="", format="csv", numeric_columns=[],
                score=0.7, investigation_title="", verification_status="verified",
            ),
        ]

        keyword_results = [
            SearchResult(
                dataset_id="ds1", psi_id="PSI-20", name="Dataset 1",
                description="", url="", format="csv", numeric_columns=[],
                score=0.8, investigation_title="", verification_status="verified",
            ),
            SearchResult(
                dataset_id="ds3", psi_id="PSI-22", name="Dataset 3",
                description="", url="", format="csv", numeric_columns=[],
                score=0.6, investigation_title="", verification_status="verified",
            ),
        ]

        combined = hybrid_retriever._combine_results(
            vector_results, keyword_results,
            vector_weight=0.7, keyword_weight=0.3,
        )

        # Should have 3 unique results
        assert len(combined) == 3

        # ds1 should be first (highest combined score)
        assert combined[0].dataset_id == "ds1"
        assert combined[0].score > 0.85  # 0.7*0.9 + 0.3*0.8 = 0.87 (normalized)


class TestRerankers:
    """Tests for reranking."""

    @pytest.fixture
    def sample_results(self):
        return [
            SearchResult(
                dataset_id="ds1", psi_id="PSI-20", name="Temperature Data",
                description="Flame temperature measurements", url="", format="csv",
                numeric_columns=["temp", "time"], score=0.8,
                investigation_title="ACME BRE", verification_status="verified",
            ),
            SearchResult(
                dataset_id="ds2", psi_id="PSI-21", name="Soot Measurements",
                description="Soot volume fraction in diffusion flames", url="", format="csv",
                numeric_columns=["soot", "radius"], score=0.7,
                investigation_title="ACME CLD", verification_status="verified",
            ),
            SearchResult(
                dataset_id="ds3", psi_id="PSI-69", name="Droplet Extinction",
                description="Droplet extinction in microgravity", url="", format="csv",
                numeric_columns=["diameter", "time"], score=0.6,
                investigation_title="FLEX", verification_status="verified",
            ),
        ]

    def test_simple_reranker_boosts_relevant(self, sample_results):
        """Test simple reranker boosts results matching query."""
        reranker = SimpleReranker()
        query = "temperature flame"

        reranked = reranker.rerank(query, sample_results, top_k=3)

        assert len(reranked) == 3
        # Temperature Data should be boosted
        assert reranked[0].result.dataset_id == "ds1"
        assert reranked[0].rerank_score > reranked[0].original_score

    def test_simple_reranker_verified_boost(self, sample_results):
        """Test verified datasets get small boost."""
        reranker = SimpleReranker()

        # Add unverified result
        unverified = SearchResult(
            dataset_id="ds4", psi_id="PSI-99", name="Unverified Data",
            description="", url="", format="csv", numeric_columns=["x"],
            score=0.9, investigation_title="", verification_status="pending",
        )
        results = sample_results + [unverified]

        reranked = reranker.rerank("test", results, top_k=4)

        # Verified results should generally rank higher despite lower original score
        verified_ids = [r.result.dataset_id for r in reranked if r.result.verification_status == "verified"]
        assert "ds1" in verified_ids or "ds2" in verified_ids

    def test_reranker_respects_top_k(self, sample_results):
        """Test reranker respects top_k limit."""
        reranker = SimpleReranker()
        reranked = reranker.rerank("test", sample_results, top_k=2)
        assert len(reranked) == 2

    def test_empty_results(self):
        """Test reranker handles empty results."""
        reranker = SimpleReranker()
        reranked = reranker.rerank("test", [])
        assert reranked == []


class TestSearchResults:
    """Tests for SearchResults dataclass."""

    def test_search_results_creation(self):
        """Test SearchResults creation."""
        results = SearchResults(
            query="test query",
            results=[],
            total_matches=0,
            processing_time_ms=100.0,
            embedding_model="test-model",
            embedding_version="1.0",
            catalog_version="1.0",
        )

        assert results.query == "test query"
        assert results.total_matches == 0
        assert results.processing_time_ms == 100.0

    def test_reranked_result(self):
        """Test RerankedResult dataclass."""
        base = SearchResult(
            dataset_id="ds1", psi_id="PSI-20", name="Test",
            description="", url="", format="csv", numeric_columns=[],
            score=0.8, investigation_title="", verification_status="verified",
        )

        reranked = RerankedResult(
            result=base,
            rerank_score=0.9,
            original_score=0.8,
        )

        assert reranked.rerank_score == 0.9
        assert reranked.original_score == 0.8
        assert reranked.result.dataset_id == "ds1"