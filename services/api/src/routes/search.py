"""Search routes - Semantic search for NASA PSI datasets."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import httpx
import structlog
import time
from typing import List, Optional
from pydantic import BaseModel, Field

from services.api.src.config import settings
from services.api.src.database import get_db_session

router = APIRouter()
logger = structlog.get_logger()


# Request/Response models (matching contracts)
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    filters: Optional[dict] = None
    options: Optional[dict] = None


class SearchResult(BaseModel):
    id: str
    psiId: str
    name: str
    description: str
    url: str
    format: str
    numericColumns: List[str]
    score: float
    investigationTitle: Optional[str] = None
    verificationStatus: str


class SearchResponse(BaseModel):
    query: str
    status: str
    source_collection: str
    data_filter: str
    total_matches: int
    datasets: List[SearchResult]
    searchMetadata: dict


SOURCE_COLLECTION = "NASA PSI — Combustion Science: 26 Selected Investigations"


@router.post("/search", response_model=SearchResponse)
async def search_datasets(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SearchResponse:
    """
    Perform semantic search across the 26 selected NASA PSI Combustion Science investigations.
    Returns all matching datasets with verified numerical content, ranked by relevance.
    """
    start_time = time.time()

    logger.info(
        "search_started",
        query=request.query[:100],
    )

    try:
        # Step 1: Generate query embedding
        query_embedding = await generate_embedding(request.query)

        # Step 2: Search vector index
        filters = request.filters or {}
        options = request.options or {}

        min_score = options.get("minScore", settings.SEARCH_MIN_SCORE)
        max_results = options.get("maxResults", settings.SEARCH_MAX_RESULTS)

        psi_ids = filters.get("psiIds")
        verification_status = filters.get("verificationStatus", ["verified"])

        # Execute vector search
        results = await vector_search(
            db=db,
            query_embedding=query_embedding,
            min_similarity=min_score,
            match_count=max_results,
            filter_psi_ids=psi_ids,
            filter_verification=verification_status,
        )

        # Step 3: Format response
        datasets = []
        for row in results:
            datasets.append(SearchResult(
                id=row["dataset_id"],
                psiId=row["psi_id"],
                name=row["name"],
                description=row["description"] or "",
                url=row["url"],
                format=row["format"],
                numericColumns=row["numeric_columns"],
                score=round(row["score"], 4),
                investigationTitle=row.get("investigation_title"),
                verificationStatus=row["verification_status"],
            ))

        status_value = "matches_found" if datasets else "no_matches"
        processing_time = round((time.time() - start_time) * 1000, 2)

        response = SearchResponse(
            query=request.query,
            status=status_value,
            source_collection=SOURCE_COLLECTION,
            data_filter="numeric_only",
            total_matches=len(datasets),
            datasets=datasets,
            searchMetadata={
                "catalogVersion": settings.CATALOG_VERSION,
                "embeddingModel": settings.EMBEDDING_MODEL,
                "embeddingVersion": settings.EMBEDDING_VERSION,
                "retrievedAt": time.time(),
                "processingTimeMs": processing_time,
            },
        )

        logger.info(
            "search_completed",
            query=request.query[:100],
            total_matches=len(datasets),
            processing_time_ms=processing_time,
        )

        return response

    except Exception as e:
        logger.error(
            "search_failed",
            query=request.query[:100],
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "SEARCH_ERROR",
                    "message": "Search service temporarily unavailable",
                }
            },
        )


async def generate_embedding(text: str) -> List[float]:
    """Generate embedding for query text."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            settings.EMBEDDING_API_URL,
            json={"texts": [text]},
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]


async def vector_search(
    db: AsyncSession,
    query_embedding: List[float],
    min_similarity: float,
    match_count: int,
    filter_psi_ids: Optional[List[str]],
    filter_verification: Optional[List[str]],
) -> List:
    """Execute vector similarity search using pgvector."""
    # Build filter conditions
    param_idx = 4
    psi_filter = ""
    if filter_psi_ids:
        psi_placeholders = ",".join([f"${i}" for i in range(param_idx, param_idx + len(filter_psi_ids))])
        psi_filter = f"AND d.psi_id IN ({psi_placeholders})"
        param_idx += len(filter_psi_ids)

    ver_filter = ""
    if filter_verification:
        ver_placeholders = ",".join([f"${i}" for i in range(param_idx, param_idx + len(filter_verification))])
        ver_filter = f"AND d.verification_status IN ({ver_placeholders})"
        param_idx += len(filter_verification)

    query = f"""
        SELECT
            d.dataset_id,
            d.psi_id,
            d.name,
            d.description,
            d.url,
            d.format,
            d.numeric_columns,
            1 - (de.embedding <=> $1) AS score,
            pi.title AS investigation_title,
            d.verification_status
        FROM datasets d
        JOIN dataset_embeddings de ON de.dataset_id = d.id
        JOIN psi_investigations pi ON pi.psi_id = d.psi_id
        WHERE 1 - (de.embedding <=> $1) >= $2
          AND d.verification_status = 'verified'
          AND d.numeric_columns IS NOT NULL
          AND array_length(d.numeric_columns, 1) > 0
          {psi_filter}
          {ver_filter}
        ORDER BY de.embedding <=> $1
        LIMIT $3
    """

    # Use raw connection for pgvector compatibility
    from services.api.src.database import get_db_context
    async with get_db_context() as conn:
        # pgvector expects vector as string format '[1,2,3]'
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        params = [embedding_str, min_similarity, match_count]
        if filter_psi_ids:
            params.extend(filter_psi_ids)
        if filter_verification:
            params.extend(filter_verification)
        
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]