"""API routes backed by local NASA PSI files and the FAISS RAG pipeline."""

from __future__ import annotations

import asyncio
import time
from functools import lru_cache
from typing import Dict

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from services.api.src.config import settings
from services.api.src.routes.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    chat_completions as legacy_chat_completions,
    list_models as legacy_list_models,
)
from services.api.src.routes.search import (
    SOURCE_COLLECTION,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from services.api.src.routes.summarization import (
    SummaryRequest,
    SummaryResponse,
    build_verifiable_facts,
    generate_llm_summary,
    parse_summary,
)
from services.api.src.routes.visualization import (
    ChartPreviewRequest,
    ChartPreviewResponse,
    generate_chart_spec,
    validate_chart_compatibility,
)
from services.search.src.rag.local_catalog import LocalPSICatalog
from services.search.src.rag.psi_data_rag import PSIDataRAG

router = APIRouter()
logger = structlog.get_logger()


@lru_cache(maxsize=1)
def get_catalog() -> LocalPSICatalog:
    return LocalPSICatalog(settings.PSI_DATA_DIR)


@lru_cache(maxsize=1)
def get_rag() -> PSIDataRAG:
    return PSIDataRAG(
        catalog=get_catalog(),
        cache_dir=settings.NASA_RAG_CACHE,
        embedding_model=settings.NASA_RAG_EMBEDDING_MODEL,
    )


def _not_found(dataset_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": {
                "code": "NOT_FOUND",
                "message": f"Local NASA PSI dataset not found: {dataset_id}",
            }
        },
    )


@router.post("/search", response_model=SearchResponse)
async def search_local_datasets(request: SearchRequest) -> SearchResponse:
    started = time.time()
    options = request.options or {}
    filters = request.filters or {}
    max_results = max(1, min(int(options.get("maxResults", 100)), 100))
    min_score = float(options.get("minScore", settings.SEARCH_MIN_SCORE))
    try:
        datasets, retrieved = await asyncio.to_thread(
            get_rag().search,
            request.query,
            max_results,
            min_score,
            filters.get("psiIds"),
        )
    except (ImportError, ModuleNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "RAG_DEPENDENCIES_MISSING",
                    "message": f"RAG dependencies are not installed: {exc}",
                }
            },
        ) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "RAG_UNAVAILABLE", "message": str(exc)}},
        ) from exc

    return SearchResponse(
        query=request.query,
        status="matches_found" if datasets else "no_matches",
        source_collection=SOURCE_COLLECTION,
        data_filter="local_nasa_psi_numeric_only",
        total_matches=len(datasets),
        datasets=[SearchResult(**dataset) for dataset in datasets],
        searchMetadata={
            "source": "data/psi_databases",
            "catalogVersion": settings.CATALOG_VERSION,
            "embeddingModel": settings.NASA_RAG_EMBEDDING_MODEL,
            "retrievedChunks": len(retrieved),
            "processingTimeMs": round((time.time() - started) * 1000, 2),
        },
    )


@router.get("/datasets/{dataset_id}")
async def get_local_dataset(dataset_id: str) -> dict:
    try:
        return get_catalog().public_dataset(dataset_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise _not_found(dataset_id) from exc


@router.get("/datasets/{dataset_id}/schema")
async def get_local_dataset_schema(dataset_id: str) -> dict:
    try:
        return get_catalog().get_schema(dataset_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise _not_found(dataset_id) from exc


@router.get("/datasets/{dataset_id}/preview")
async def get_local_dataset_preview(
    dataset_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    try:
        return get_catalog().get_preview(dataset_id, limit=limit, offset=offset)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise _not_found(dataset_id) from exc


@router.post("/charts/preview", response_model=ChartPreviewResponse)
async def generate_local_chart_preview(request: ChartPreviewRequest) -> ChartPreviewResponse:
    started = time.time()
    try:
        schema = get_catalog().get_schema(request.datasetId)
        columns = schema["columns"]
        column_map = {column["column_name"]: column for column in columns}
        x_col = column_map.get(request.xAxis)
        y_col = column_map.get(request.yAxis) if request.yAxis else None
        group_col = column_map.get(request.groupBy) if request.groupBy else None
        if not x_col or (request.yAxis and not y_col) or (request.groupBy and not group_col):
            raise ValueError("A requested chart column does not exist in the local dataset")
        options = request.options or {}
        limit = max(1, min(int(options.get("limit", 500)), 10000))
        rows = get_catalog().get_chart_rows(
            request.datasetId,
            request.xAxis,
            request.yAxis,
            request.groupBy,
            limit,
        )
    except FileNotFoundError as exc:
        raise _not_found(request.datasetId) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
        ) from exc

    warnings = validate_chart_compatibility(request.chartType, x_col, y_col, group_col)
    return ChartPreviewResponse(
        datasetId=request.datasetId,
        chartType=request.chartType,
        spec=generate_chart_spec(request.chartType, x_col, y_col, group_col, options),
        data=rows,
        columns={"x": x_col, "y": y_col, "groupBy": group_col},
        warnings=warnings,
        metadata={
            "source": "data/psi_databases",
            "rowCount": schema["rowCount"],
            "filteredRowCount": len(rows),
            "processingTimeMs": round((time.time() - started) * 1000, 2),
            "memoryUsedBytes": len(str(rows).encode()),
        },
    )


@router.post("/datasets/{dataset_id}/summary", response_model=SummaryResponse)
async def generate_local_summary(dataset_id: str, request: SummaryRequest) -> SummaryResponse:
    started = time.time()
    try:
        dataset = get_catalog().public_dataset(dataset_id)
        schema = get_catalog().get_schema(dataset_id)
        investigation = get_catalog().get_investigation(dataset["psiId"])
        source_file = get_catalog().get_dataset(dataset_id)["_path"].name
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise _not_found(dataset_id) from exc

    profile = {
        "row_count": schema["rowCount"],
        "profiled_at": None,
        "profile_version": schema["profileVersion"],
    }
    facts = build_verifiable_facts(dataset, schema["columns"], profile)
    facts["experiment_context"] = {
        "research_area": investigation.get("research_area"),
        "subresearch_area": investigation.get("subresearch_area"),
        "scientific_focus": investigation.get("scientific_focus"),
        "project_setting": investigation.get("project_setting"),
        "objectives": investigation.get("objectives"),
        "approach": investigation.get("approach"),
        "doi": investigation.get("doi"),
    }
    facts["dataset_context"] = {
        "source_file": source_file,
        "file_format": dataset.get("format"),
        "row_count": schema["rowCount"],
        "column_count": len(schema["columns"]),
        "related_files": [
            {"name": item["name"], "format": item["format"]}
            for item in get_catalog().list_datasets()
            if item["psi_id"] == dataset["psiId"]
        ],
        "available_evidence": [
            "NASA PSI investigation metadata",
            "local file schema and inferred column types",
            "sampled column statistics",
            "local FAISS RAG excerpts",
        ],
    }

    # Ground the summary in the same local RAG index used by the assistant. The
    # excerpts contain the investigation record and this file's schema, but not a
    # formal variable dictionary, so the prompt must mark interpretations.
    retrieval_query = " ".join(
        part
        for part in (
            dataset["psiId"],
            investigation.get("title", ""),
            dataset.get("name", ""),
            source_file,
            investigation.get("objectives", ""),
            investigation.get("approach", ""),
        )
        if part
    )
    try:
        retrieved = await asyncio.to_thread(
            get_rag().retrieve, retrieval_query, settings.NASA_RAG_TOP_K
        )
        facts["local_rag_context"] = [
            {
                "source": match["metadata"].get("source", "NASA PSI metadata"),
                "cosine": round(float(match["score"]), 3),
                "excerpt": match["content"][:800],
            }
            for match in retrieved
            if match["metadata"].get("psi_id") == dataset["psiId"]
        ][:2]
    except (ImportError, ModuleNotFoundError, OSError, ValueError) as exc:
        logger.warning("summary_rag_unavailable", dataset_id=dataset_id, error=str(exc))
        facts["local_rag_context"] = []

    try:
        summary_text = await generate_llm_summary(facts, request.options or {})
    except Exception as exc:
        response_body = ""
        response = getattr(exc, "response", None)
        if response is not None:
            response_body = getattr(response, "text", "")[:600]
        logger.warning(
            "local_llm_summary_failed_falling_back",
            dataset_id=dataset_id,
            error=str(exc),
            provider_response=response_body,
        )
        from services.api.src.routes.summarization import generate_descriptive_summary

        summary_text = generate_descriptive_summary(facts)
    structured = parse_summary(summary_text, facts)
    # The legacy summary labels the first tag as temporal coverage; the local
    # catalog tags are research areas, so report them without mislabelling.
    structured["coverage"] = {
        "researchArea": dataset.get("tags", [None])[0],
        "rowCount": schema["rowCount"],
        "columnCount": len(schema["columns"]),
    }
    structured["sources"].append(
        {"type": "local_file", "reference": get_catalog().get_dataset(dataset_id)["_path"].name}
    )
    return SummaryResponse(
        datasetId=dataset_id,
        **structured,
        generatedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        catalogVersion=settings.CATALOG_VERSION,
        profilingVersion=schema["profileVersion"],
    )


def _format_sources(retrieved: list[dict]) -> str:
    sources = []
    for index, match in enumerate(retrieved[: settings.NASA_RAG_TOP_K], start=1):
        metadata = match["metadata"]
        label = metadata.get("source", "NASA PSI metadata")
        sources.append(f"[{index}] {label} (cosine {match['score']:.3f})")
    return "\n".join(sources)


def _retrieval_only_response(retrieved: list[dict], note: str) -> ChatCompletionResponse:
    """Return cited retrievals when no LLM is configured or reachable."""
    excerpts = "\n\n".join(
        f"[{index}] {match['metadata'].get('source', 'NASA PSI metadata')}\n"
        f"{match['content'][:700]}"
        for index, match in enumerate(retrieved[:3], start=1)
    )
    content = f"{note}\n\n{excerpts or 'No relevant local NASA PSI metadata was found.'}"
    return ChatCompletionResponse(
        id=f"local-rag-{int(time.time() * 1000)}",
        created=int(time.time()),
        model="local-nasa-psi-rag",
        choices=[
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )


def _rag_system_message(retrieved: list[dict], request: ChatCompletionRequest) -> ChatMessage:
    context_parts = []
    for index, match in enumerate(retrieved, start=1):
        metadata = match["metadata"]
        context_parts.append(
            f"[{index}] {metadata.get('source', 'NASA PSI metadata')} "
            f"(cosine {match['score']:.3f})\n{match['content'][:1500]}"
        )
    existing_constraints = "\n".join(
        message.content for message in request.messages if message.role == "system"
    ).strip()
    if len(existing_constraints) > 6000:
        existing_constraints = (
            existing_constraints[:6000] + "\n[selected dataset context truncated]"
        )
    return ChatMessage(
        role="system",
        content=(
            "You are the NASA PSI Combustion Science RAG assistant. Answer in the user's "
            "language. Use ONLY the selected-dataset context and the retrieved local "
            "context below for factual claims, investigation IDs, dataset/file names, "
            "column names, statistics and numbers. When the question is about the "
            "currently selected dataset, prefer the SELECTED DATASET context and cite it "
            "as [S]. Cite retrieved-context facts with the matching bracket number, for "
            "example [1]. If neither context answers the question, say what is missing "
            "instead of guessing. Never invent measurements, units, rows or file "
            "contents. Clearly separate investigation metadata from computed column "
            "statistics. If sources disagree, state the disagreement and cite both.\n\n"
            + (
                f"SELECTED DATASET / APPLICATION CONTEXT (authoritative for the current "
                f"selection; cite as [S]):\n{existing_constraints}\n\n"
                if existing_constraints
                else ""
            )
            + f"RETRIEVED LOCAL NASA PSI CONTEXT (top {len(retrieved)} by cosine similarity):\n"
            + "\n\n".join(context_parts)
        ),
    )


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def local_rag_chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    question = next(
        (message.content for message in reversed(request.messages) if message.role == "user"),
        "",
    ).strip()
    if not question:
        raise HTTPException(status_code=400, detail="A user message is required")
    system_context = "\n".join(
        message.content for message in request.messages if message.role == "system"
    ).strip()
    # Include the selected-dataset context in the retrieval query so questions
    # such as "what columns does the selected dataset have?" do not retrieve
    # unrelated PSI files.
    retrieval_query = f"{system_context[:1500]}\n{question}".strip() if system_context else question
    try:
        retrieved = await asyncio.to_thread(
            get_rag().retrieve, retrieval_query, settings.NASA_RAG_TOP_K
        )
    except (ImportError, ModuleNotFoundError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "RAG_UNAVAILABLE", "message": str(exc)}},
        ) from exc

    if not settings.LLM_API_KEY:
        # Retrieval remains useful without an external LLM key; never fabricate generation.
        return _retrieval_only_response(
            retrieved,
            "Retrieval result from the local NASA PSI RAG (no LLM API key configured):",
        )

    rag_system = _rag_system_message(retrieved, request)
    conversation = [message for message in request.messages if message.role != "system"]
    # Providers such as Groq enforce output-token-per-minute limits. Cap the
    # request to the configured maximum so a frontend default does not force a
    # fallback to retrieval-only mode.
    max_tokens = min(
        request.max_tokens or settings.LLM_MAX_TOKENS,
        settings.LLM_MAX_TOKENS,
    )
    enriched = request.model_copy(
        update={"messages": [rag_system, *conversation], "max_tokens": max_tokens}
    )
    try:
        response = await legacy_chat_completions(enriched)
    except Exception as exc:
        logger.warning("rag_llm_failed_falling_back_to_retrieval", error=str(exc))
        return _retrieval_only_response(
            retrieved,
            "The configured LLM could not be reached. This is the cited retrieval result "
            "from the local NASA PSI RAG:",
        )

    sources = _format_sources(retrieved)
    if sources and response.choices:
        response.choices[0].message.content += f"\n\nLocal NASA PSI sources:\n{sources}"
    return response


@router.get("/chat/models")
async def local_rag_models() -> Dict:
    if settings.LLM_API_KEY:
        return await legacy_list_models()
    return {
        "models": ["local-nasa-psi-rag"],
        "retrieval_model": settings.NASA_RAG_EMBEDDING_MODEL,
        "data_source": "data/psi_databases",
    }
