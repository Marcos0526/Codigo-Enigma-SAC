"""
Summarization routes - Evidence-based dataset summaries
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import httpx
import structlog
import time
from typing import List, Optional
from pydantic import BaseModel, Field

from services.api.config import settings
from services.api.database import get_db_session

router = APIRouter()
logger = structlog.get_logger()


class SummaryRequest(BaseModel):
    datasetId: str
    options: Optional[dict] = None


class Finding(BaseModel):
    description: str
    evidence: str
    source: str


class SummarySource(BaseModel):
    type: str
    reference: str


class SummaryResponse(BaseModel):
    datasetId: str
    title: str
    executiveSummary: str
    keyVariables: List[str]
    coverage: dict
    findings: List[Finding]
    limitations: List[str]
    warnings: List[str]
    sources: List[SummarySource]
    generatedAt: str
    catalogVersion: str
    profilingVersion: Optional[str] = None


@router.post("/datasets/{dataset_id}/summary", response_model=SummaryResponse)
async def generate_summary(
    dataset_id: str,
    request: SummaryRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SummaryResponse:
    """
    Generate an evidence-based summary of the dataset using only verifiable metadata
    and computed statistics. The LLM never receives raw data as instructions.
    """
    start_time = time.time()
    request_id = request.datasetId  # Using dataset_id as request tracking

    logger.info("summary_generation_started", dataset_id=dataset_id)

    # Verify dataset exists and get metadata
    dataset_query = """
        SELECT d.*, pi.title AS investigation_title
        FROM datasets d
        JOIN psi_investigations pi ON pi.psi_id = d.psi_id
        WHERE d.dataset_id = $1
    """
    dataset_result = await db.execute(text(dataset_query), [dataset_id])
    dataset = dataset_result.fetchone()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Dataset not found: {dataset_id}",
                }
            },
        )

    # Get schema and statistics
    schema_query = """
        SELECT column_name, column_type, unit, statistics
        FROM dataset_schemas
        WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
        ORDER BY ordinal_position
    """
    schema_result = await db.execute(text(schema_query), [dataset_id])
    columns = [dict(row._mapping) for row in schema_result.fetchall()]

    # Get profile
    profile_query = """
        SELECT row_count, profiled_at, profile_version
        FROM dataset_profiles
        WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
    """
    profile_result = await db.execute(text(profile_query), [dataset_id])
    profile = profile_result.fetchone()

    # Build verifiable facts for LLM
    facts = build_verifiable_facts(dataset, columns, profile)

    # Generate summary using LLM
    try:
        summary_text = await generate_llm_summary(facts, request.options or {})
    except Exception as e:
        logger.error("llm_summary_failed", dataset_id=dataset_id, error=str(e))
        # Fallback to descriptive summary
        summary_text = generate_descriptive_summary(facts)

    # Parse and structure the summary
    structured_summary = parse_summary(summary_text, facts)

    processing_time = round((time.time() - start_time) * 1000, 2)

    response = SummaryResponse(
        datasetId=dataset_id,
        title=structured_summary["title"],
        executiveSummary=structured_summary["executiveSummary"],
        keyVariables=structured_summary["keyVariables"],
        coverage=structured_summary["coverage"],
        findings=structured_summary["findings"],
        limitations=structured_summary["limitations"],
        warnings=structured_summary["warnings"],
        sources=structured_summary["sources"],
        generatedAt=time.time(),
        catalogVersion=settings.CATALOG_VERSION,
        profilingVersion=profile.profile_version if profile else None,
    )

    logger.info("summary_generation_completed", dataset_id=dataset_id, processing_time_ms=processing_time)

    return response


def build_verifiable_facts(dataset, columns, profile) -> dict:
    """Build structured verifiable facts from metadata and statistics."""
    numeric_columns = [c for c in columns if c["column_type"] == "numeric"]
    categorical_columns = [c for c in columns if c["column_type"] == "categorical"]

    facts = {
        "dataset_id": dataset.dataset_id,
        "name": dataset.name,
        "description": dataset.description,
        "psi_id": dataset.psi_id,
        "investigation_title": dataset.investigation_title,
        "format": dataset.format,
        "url": dataset.url,
        "url_type": dataset.url_type,
        "source": dataset.source,
        "license": dataset.license,
        "access_policy": dataset.access_policy,
        "tags": dataset.tags,
        "numeric_columns": [
            {
                "name": c["column_name"],
                "unit": c["unit"],
                "statistics": c["statistics"],
            }
            for c in numeric_columns
        ],
        "categorical_columns": [
            {"name": c["column_name"]}
            for c in categorical_columns
        ],
        "row_count": profile.row_count if profile else None,
        "profiled_at": profile.profiled_at.isoformat() if profile and profile.profiled_at else None,
        "verification_status": dataset.verification_status,
        "verified_at": dataset.verified_at.isoformat() if dataset.verified_at else None,
    }

    return facts


async def generate_llm_summary(facts: dict, options: dict) -> str:
    """Generate summary using LLM with verifiable facts only."""
    if settings.LLM_PROVIDER == "openai" and settings.LLM_API_KEY:
        return await generate_openai_summary(facts, options)
    elif settings.LLM_PROVIDER == "anthropic" and settings.LLM_API_KEY:
        return await generate_anthropic_summary(facts, options)
    else:
        # Local/fallback
        return generate_descriptive_summary(facts)


async def generate_openai_summary(facts: dict, options: dict) -> str:
    """Generate summary using OpenAI API."""
    import json

    max_length = options.get("maxLength", 1000)

    system_prompt = """You are a scientific data analyst. Generate a concise, evidence-based summary of a dataset using ONLY the provided verifiable facts. 

CRITICAL RULES:
1. NEVER invent statistics, numbers, or findings not explicitly provided in the facts
2. NEVER make claims beyond what the data supports
3. Clearly distinguish between metadata (descriptions, tags) and computed statistics
4. If statistics are not available, state this explicitly
5. Include source references for every claim
6. List limitations and warnings about unavailable information

Format your response as structured text with clear sections."""

    user_prompt = f"""Dataset Facts (VERIFIED - DO NOT INVENT ADDITIONAL INFORMATION):

{json.dumps(facts, indent=2, default=str)}

Generate a summary with:
1. Title
2. Executive Summary (2-3 sentences)
3. Key Variables
4. Coverage (temporal, geographic, row count)
5. Findings (each with description, evidence, source)
6. Limitations
7. Warnings
8. Sources"""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": settings.LLM_MAX_TOKENS,
                "temperature": settings.LLM_TEMPERATURE,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def generate_anthropic_summary(facts: dict, options: dict) -> str:
    """Generate summary using Anthropic API."""
    import json

    max_length = options.get("maxLength", 1000)

    system_prompt = """You are a scientific data analyst. Generate a concise, evidence-based summary of a dataset using ONLY the provided verifiable facts. 

CRITICAL RULES:
1. NEVER invent statistics, numbers, or findings not explicitly provided in the facts
2. NEVER make claims beyond what the data supports
3. Clearly distinguish between metadata (descriptions, tags) and computed statistics
4. If statistics are not available, state this explicitly
5. Include source references for every claim
6. List limitations and warnings about unavailable information"""

    user_prompt = f"""Dataset Facts (VERIFIED - DO NOT INVENT ADDITIONAL INFORMATION):

{json.dumps(facts, indent=2, default=str)}

Generate a summary with:
1. Title
2. Executive Summary (2-3 sentences)
3. Key Variables
4. Coverage (temporal, geographic, row count)
5. Findings (each with description, evidence, source)
6. Limitations
7. Warnings
8. Sources"""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.LLM_API_KEY,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-3-opus-20240229",
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": settings.LLM_MAX_TOKENS,
                "temperature": settings.LLM_TEMPERATURE,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]


def generate_descriptive_summary(facts: dict) -> str:
    """Generate a descriptive summary without LLM (fallback)."""
    numeric_cols = facts.get("numeric_columns", [])
    cat_cols = facts.get("categorical_columns", [])
    row_count = facts.get("row_count")

    lines = [
        f"Title: {facts['name']} - Descriptive Summary",
        "",
        f"Executive Summary: This dataset ({facts['name']}) from investigation {facts['psi_id']} "
        f"({facts.get('investigation_title', 'Unknown')}) contains {len(numeric_cols)} numerical columns "
        f"and {len(cat_cols)} categorical columns. "
        f"{'It has ' + str(row_count) + ' rows.' if row_count else 'Row count is not available.'} "
        f"Data format: {facts['format']}. Access: {facts['access_policy']}.",
        "",
        "Key Variables: " + ", ".join([c["name"] for c in numeric_cols + cat_cols]) or "None",
        "",
        f"Coverage: Temporal: {facts.get('tags', ['Unknown'])[0] if facts.get('tags') else 'Unknown'}, "
        f"Rows: {row_count if row_count else 'Unknown'}",
        "",
        "Findings:",
    ]

    for col in numeric_cols:
        stats = col.get("statistics")
        if stats:
            lines.append(
                f"  - {col['name']}: range [{stats.get('min', 'N/A')}, {stats.get('max', 'N/A')}] "
                f"(mean: {stats.get('mean', 'N/A')}, source: computed_statistics)"
            )
        else:
            lines.append(f"  - {col['name']}: numerical column (no statistics available, source: metadata)")

    lines.extend([
        "",
        "Limitations:",
        "  - Summary generated from metadata only; no LLM enhancement available",
        "  - Statistics may not be available for all columns",
        "  - Data not directly inspected; based on cataloged metadata",
        "",
        "Warnings:",
        "  - This is a descriptive summary, not an analytical summary",
        "  - Verification status: " + facts.get("verification_status", "unknown"),
        "",
        "Sources:",
        f"  - metadata: {facts['psi_id']} investigation record",
        f"  - metadata: dataset catalog entry {facts['dataset_id']}",
    ])

    if numeric_cols:
        lines.append("  - computed_statistics: column statistics for numeric columns")

    return "\n".join(lines)


def parse_summary(summary_text: str, facts: dict) -> dict:
    """Parse LLM-generated summary into structured format."""
    # Simple parsing - in production, use structured output from LLM
    lines = summary_text.strip().split("\n")

    return {
        "title": facts["name"] + " - Summary",
        "executiveSummary": summary_text[:500] + "..." if len(summary_text) > 500 else summary_text,
        "keyVariables": [c["name"] for c in facts.get("numeric_columns", []) + facts.get("categorical_columns", [])],
        "coverage": {
            "temporal": facts.get("tags", ["Unknown"])[0] if facts.get("tags") else "Unknown",
            "rowCount": facts.get("row_count"),
        },
        "findings": [
            {
                "description": f"Column {c['name']} has range [{c['statistics'].get('min')}, {c['statistics'].get('max')}]",
                "evidence": f"min={c['statistics'].get('min')}, max={c['statistics'].get('max')}, mean={c['statistics'].get('mean')}",
                "source": "computed_statistics",
            }
            for c in facts.get("numeric_columns", []) if c.get("statistics")
        ],
        "limitations": [
            "Summary based on cataloged metadata and available statistics",
            "Not all columns may have computed statistics",
        ],
        "warnings": [
            "Verification status: " + facts.get("verification_status", "unknown"),
        ],
        "sources": [
            {"type": "metadata", "reference": f"{facts['psi_id']} investigation record"},
            {"type": "metadata", "reference": f"dataset catalog entry {facts['dataset_id']}"},
        ] + [
            {"type": "statistics", "reference": f"column statistics for {c['name']}"}
            for c in facts.get("numeric_columns", []) if c.get("statistics")
        ],
    }