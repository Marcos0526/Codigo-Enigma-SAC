"""Cross-encoder reranking for search results."""

import structlog
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from services.search.src.retrieval.vector_search import SearchResult
from services.search.src.config import settings

logger = structlog.get_logger()


@dataclass
class RerankedResult:
    """Reranked search result."""
    result: SearchResult
    rerank_score: float
    original_score: float


class CrossEncoderReranker:
    """Reranks search results using a cross-encoder model."""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.SEARCH_RERANK_MODEL
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            from sentence_transformers import CrossEncoder
            logger.info("loading_cross_encoder_model", model=self.model_name)
            self._model = CrossEncoder(self.model_name, device="cpu")

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = None,
    ) -> List[RerankedResult]:
        """Rerank results using cross-encoder."""
        if not results:
            return []

        self._load_model()
        top_k = top_k or settings.SEARCH_RERANK_TOP_K

        # Prepare query-result pairs
        pairs = []
        for result in results:
            # Create text representation of result
            result_text = self._result_to_text(result)
            pairs.append([query, result_text])

        # Get cross-encoder scores
        scores = self._model.predict(pairs, show_progress_bar=False)

        # Create reranked results
        reranked = []
        for result, score in zip(results, scores):
            reranked.append(RerankedResult(
                result=result,
                rerank_score=float(score),
                original_score=result.score,
            ))

        # Sort by rerank score
        reranked.sort(key=lambda x: x.rerank_score, reverse=True)

        # Limit to top_k
        return reranked[:top_k]

    def _result_to_text(self, result: SearchResult) -> str:
        """Convert result to text for cross-encoder."""
        parts = [
            result.name,
            result.description or "",
            f"PSI: {result.psi_id}",
            f"Investigation: {result.investigation_title or ''}",
            f"Format: {result.format}",
            f"Columns: {', '.join(result.numeric_columns[:10])}",
        ]
        return " | ".join(filter(None, parts))


class SimpleReranker:
    """Simple heuristic reranker (no ML model required)."""

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = None,
    ) -> List[RerankedResult]:
        """Rerank using heuristic scoring."""
        if not results:
            return []

        top_k = top_k or settings.SEARCH_RERANK_TOP_K
        query_lower = query.lower()
        query_words = set(query_lower.split())

        reranked = []
        for result in results:
            # Calculate heuristic boost
            boost = 0.0

            # Boost for query words in name
            name_words = set(result.name.lower().split())
            name_overlap = len(query_words & name_words) / max(len(query_words), 1)
            boost += name_overlap * 0.3

            # Boost for query words in description
            if result.description:
                desc_words = set(result.description.lower().split())
                desc_overlap = len(query_words & desc_words) / max(len(query_words), 1)
                boost += desc_overlap * 0.2

            # Boost for query words in investigation title
            if result.investigation_title:
                inv_words = set(result.investigation_title.lower().split())
                inv_overlap = len(query_words & inv_words) / max(len(query_words), 1)
                boost += inv_overlap * 0.1

            # Boost for numeric column relevance
            column_overlap = 0
            for col in result.numeric_columns:
                col_words = set(col.lower().replace("_", " ").split())
                if query_words & col_words:
                    column_overlap += 1
            if result.numeric_columns:
                boost += (column_overlap / len(result.numeric_columns)) * 0.2

            # Boost for verified datasets
            if result.verification_status == "verified":
                boost += 0.1

            rerank_score = result.score + boost

            reranked.append(RerankedResult(
                result=result,
                rerank_score=rerank_score,
                original_score=result.score,
            ))

        # Sort by rerank score
        reranked.sort(key=lambda x: x.rerank_score, reverse=True)

        return reranked[:top_k]


def get_reranker() -> "CrossEncoderReranker | SimpleReranker":
    """Get appropriate reranker based on configuration."""
    if settings.SEARCH_RERANK_ENABLED:
        try:
            return CrossEncoderReranker()
        except Exception as e:
            logger.warning("cross_encoder_reranker_unavailable", error=str(e))
            return SimpleReranker()
    return SimpleReranker()