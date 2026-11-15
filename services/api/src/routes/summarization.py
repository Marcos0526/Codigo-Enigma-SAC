"""Summarization routes - Evidence-based dataset summaries."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
import httpx
import structlog
import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from services.api.src.config import settings
from services.api.src.database import get_db_context

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
) -> SummaryResponse:
    """
    Generate an evidence-based summary of the dataset using only verifiable metadata
    and computed statistics. The LLM never receives raw data as instructions.
    """
    start_time = time.time()

    logger.info("summary_generation_started", dataset_id=dataset_id)

    async with get_db_context() as conn:
        # Verify dataset exists and get metadata
        dataset_query = """
            SELECT d.*, pi.title AS investigation_title
            FROM datasets d
            JOIN psi_investigations pi ON pi.psi_id = d.psi_id
            WHERE d.dataset_id = $1
        """
        dataset = await conn.fetchrow(dataset_query, dataset_id)

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
        schema_rows = await conn.fetch(schema_query, dataset_id)
        columns = [dict(row) for row in schema_rows]

        # Get profile
        profile_query = """
            SELECT row_count, (to_jsonb(dp)->>'profiled_at')::timestamptz AS profiled_at, profile_version
            FROM dataset_profiles dp
            WHERE dataset_id = (SELECT id FROM datasets WHERE dataset_id = $1)
        """
        profile = await conn.fetchrow(profile_query, dataset_id)

        # Build verifiable facts for LLM
        facts = build_verifiable_facts(dict(dataset), columns, dict(profile) if profile else None)

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
        generatedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        catalogVersion=settings.CATALOG_VERSION,
        profilingVersion=profile.get("profile_version") if profile else None,
    )

    logger.info("summary_generation_completed", dataset_id=dataset_id, processing_time_ms=processing_time)

    return response


import json

def build_verifiable_facts(dataset, columns, profile) -> dict:
    """Build structured verifiable facts from metadata and statistics."""
    numeric_columns = [c for c in columns if c["column_type"] == "numeric"]
    categorical_columns = [c for c in columns if c["column_type"] == "categorical"]

    def parse_stats(stats_raw):
        if not stats_raw:
            return None
        if isinstance(stats_raw, str):
            try:
                return json.loads(stats_raw)
            except json.JSONDecodeError:
                return None
        elif isinstance(stats_raw, dict):
            return stats_raw
        return None

    facts = {
        "dataset_id": dataset["dataset_id"],
        "name": dataset["name"],
        "description": dataset["description"],
        "psi_id": dataset["psi_id"],
        "investigation_title": dataset.get("investigation_title", ""),
        "format": dataset["format"],
        "url": dataset["url"],
        "url_type": dataset["url_type"],
        "source": dataset["source"],
        "license": dataset["license"],
        "access_policy": dataset["access_policy"],
        "tags": dataset["tags"],
        "numeric_columns": [
            {
                "name": c["column_name"],
                "unit": c["unit"],
                "statistics": parse_stats(c["statistics"]),
            }
            for c in numeric_columns
        ],
        "categorical_columns": [
            {"name": c["column_name"]}
            for c in categorical_columns
        ],
        "row_count": profile.get("row_count") if profile else None,
        "profiled_at": profile.get("profiled_at").isoformat() if profile and profile.get("profiled_at") else None,
        "verification_status": dataset["verification_status"],
        "verified_at": dataset["verified_at"].isoformat() if dataset.get("verified_at") else None,
    }

    return facts


async def generate_llm_summary(facts: dict, options: dict) -> str:
    """Generate summary using LLM with verifiable facts only."""
    if settings.LLM_PROVIDER in {"openai", "groq"} and settings.LLM_API_KEY:
        return await generate_openai_summary(facts, options)
    elif settings.LLM_PROVIDER == "anthropic" and settings.LLM_API_KEY:
        return await generate_anthropic_summary(facts, options)
    elif settings.LLM_PROVIDER == "nvidia" and settings.LLM_API_KEY:
        try:
            return await generate_nvidia_summary(facts, options)
        except Exception as e:
            logger.warning("nvidia_llm_failed_fallback", error=str(e))
            return generate_descriptive_summary(facts)
    else:
        # Local/fallback
        return generate_descriptive_summary(facts)


async def generate_openai_summary(facts: dict, options: dict) -> str:
    """Generate summary using OpenAI-compatible API (OpenAI, Groq, Together, etc.)."""
    import json

    max_length = options.get("maxLength", 1000)

    system_prompt = """You are a scientific data analyst. Generate a concise, evidence-based summary of a dataset using ONLY the provided verifiable facts and local context.

CRITICAL RULES:
1. NEVER invent statistics, numbers, units, instruments, or findings not explicitly provided in the facts or context
2. NEVER make claims beyond what the evidence supports
3. Clearly distinguish investigation metadata, computed statistics, and interpretations inferred from column names
4. If a variable meaning or unit is not explicit, label the interpretation as "Inferred" and say that no formal data dictionary is available
5. If statistics are not available, state this explicitly
6. Include source references for every factual claim
7. List limitations and warnings about unavailable information

Format your response as structured Markdown."""

    user_prompt = f"""Dataset Facts and Local Context (VERIFIED - DO NOT INVENT ADDITIONAL INFORMATION):

{json.dumps(facts, separators=(",", ":"), default=str)}

Write the complete response in English Markdown. Use headings, paragraphs, bullet lists, and tables where appropriate. Do not wrap the response in a code fence.

Generate a summary with:
1. Title
2. Experiment context: what experiment or investigation produced this dataset, where it ran, its objective, and its approach
3. What this dataset represents: the source file, its likely observation unit, and what the rows/measurements mean; explicitly state uncertainty when the observation unit is not documented
4. Executive Summary (2-3 sentences)
5. Key variables and interpretation: use a table with Variable, Likely role, and Meaning/evidence. Select at most 10 scientifically relevant variables. Classify roles as experimental condition, response/measurement, time/index, or engineering/housekeeping when the evidence supports it. Mark inferred meanings as "Inferred"
6. Coverage (research area, project setting, row count, column count)
7. Findings (at most 6 concise bullets, each with description, evidence, source)
8. Limitations (explicitly mention missing variable dictionary or units when applicable)
9. Warnings
10. Sources"""

    # Use custom API URL if provided (for Groq, Together, etc.), otherwise default to OpenAI
    # Ensure the URL ends with /chat/completions
    base_url = settings.LLM_API_URL or "https://api.openai.com/v1"
    api_url = base_url.rstrip("/") + "/chat/completions"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            api_url,
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

Write the complete response in English Markdown. Use headings, paragraphs, bullet lists, and tables where appropriate. Do not wrap the response in a code fence.

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


async def generate_nvidia_summary(facts: dict, options: dict) -> str:
    """Generate summary using NVIDIA API (OpenAI-compatible)."""
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

Write the complete response in English Markdown. Use headings, paragraphs, bullet lists, and tables where appropriate. Do not wrap the response in a code fence.

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
            f"{settings.NVIDIA_API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.NVIDIA_LLM_MODEL,
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
        lines.append("  - computed_statistics: column statistics for " + ", ".join(c["name"] for c in numeric_cols))

    return "\n".join(lines)


def parse_summary(summary_text: str, facts: dict) -> dict:
    """Parse LLM-generated summary into structured format."""
    lines = summary_text.strip().split("\n")

    return {
        "title": facts["name"] + " - Summary",
        "executiveSummary": summary_text.strip(),
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


import json

def generate_descriptive_summary(facts: dict) -> str:
    """Generate a descriptive summary without LLM (fallback)."""
    numeric_cols = facts.get("numeric_columns", [])
    cat_cols = facts.get("categorical_columns", [])
    row_count = facts.get("row_count")

    lines = [
        f"# {facts['name']} — Descriptive Summary",
        "",
        f"## Executive summary\n\nThis dataset ({facts['name']}) from investigation {facts['psi_id']} "
        f"({facts.get('investigation_title', 'Unknown')}) contains {len(numeric_cols)} numerical columns "
        f"and {len(cat_cols)} categorical columns across {row_count or 'unknown'} rows. "
        f"Data format: {facts['format']}. Access: {facts['access_policy']}. Verification status: {facts['verification_status']}.",
    ]

    experiment = facts.get("experiment_context") or {}
    if experiment:
        lines.extend(
            [
                "",
                "## Experiment context",
                f"- Investigation: {facts['psi_id']} — {facts.get('investigation_title', 'Unknown')}",
                f"- Research area: {experiment.get('research_area', 'Unknown')}"
                + (
                    f" / {experiment['subresearch_area']}"
                    if experiment.get("subresearch_area")
                    else ""
                ),
                f"- Scientific focus: {experiment.get('scientific_focus', 'Unknown')}",
                f"- Setting: {experiment.get('project_setting', 'Unknown')}",
                f"- Objective: {experiment.get('objectives', 'Unknown')}",
                f"- Approach: {experiment.get('approach', 'Unknown')}",
            ]
        )

    dataset_context = facts.get("dataset_context") or {}
    if dataset_context:
        related = ", ".join(
            f"{item.get('name')} ({item.get('format', '').upper()})"
            for item in dataset_context.get("related_files", [])
        )
        lines.extend(
            [
                "",
                "## What this dataset represents",
                f"- Source file: {dataset_context.get('source_file', facts['dataset_id'])}",
                f"- Rows: {dataset_context.get('row_count', row_count or 'unknown')}",
                f"- Columns: {dataset_context.get('column_count', len(numeric_cols) + len(cat_cols))}",
                f"- Related files in this investigation: {related or 'Unknown'}",
                "- Observation unit: not documented in the local metadata; interpretations must be verified against the source documentation.",
            ]
        )

    lines.extend(
        [
            "",
            "## Key variables\n\n"
            + (", ".join([c["name"] for c in numeric_cols + cat_cols]) or "None"),
            "",
            "## Variable interpretation",
            "- No formal variable dictionary or unit metadata is available in the local files.",
            "- Meanings can only be inferred from column names, sample values, statistics, and the investigation context; verify inferred meanings with the NASA PSI source documentation.",
            "",
            f"## Coverage\n\nResearch area: {facts.get('tags', ['Unknown'])[0] if facts.get('tags') else 'Unknown'}, "
            f"Rows: {row_count if row_count else 'Unknown'}",
            "",
            "## Findings",
        ]
    )

    for col in numeric_cols:
        stats_raw = col.get("statistics")
        stats = {}
        if stats_raw:
            if isinstance(stats_raw, str):
                try:
                    stats = json.loads(stats_raw)
                except json.JSONDecodeError:
                    stats = {}
            elif isinstance(stats_raw, dict):
                stats = stats_raw
        
        if stats:
            lines.append(
                f"  - {col['name']}: range [{stats.get('min', 'N/A')}, {stats.get('max', 'N/A')}] "
                f"(mean: {stats.get('mean', 'N/A')}, source: computed_statistics)"
            )
        else:
            lines.append(f"  - {col['name']}: numerical column (no statistics available, source: metadata)")

    for col in cat_cols:
        lines.append(f"  - {col['name']}: categorical column (source: metadata)")

    lines.extend([
        "",
        "## Limitations",
        "  - Summary generated from metadata only; no LLM enhancement available",
        "  - Statistics may not be available for all columns",
        "  - Data not directly inspected; based on cataloged metadata",
        "",
        "## Data notes",
        "  - This is a descriptive summary, not an analytical summary",
        "  - Verification status: " + facts.get("verification_status", "unknown"),
        "",
        "## Sources",
        f"  - metadata: {facts['psi_id']} investigation record",
        f"  - metadata: dataset catalog entry {facts['dataset_id']}",
    ])

    if numeric_cols:
        lines.append("  - computed_statistics: column statistics for " + ", ".join(c["name"] for c in numeric_cols))

    return "\n".join(lines)