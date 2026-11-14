"""Prompt templates for dataset summarization."""

import json
from typing import Dict, List, Any
from dataclasses import dataclass

from services.summarizer.src.profiling.dataset_profiler import ColumnProfile, DatasetProfile


@dataclass
class PromptContext:
    """Context for prompt generation."""
    dataset_id: str
    name: str
    description: str
    psi_id: str
    investigation_title: str
    format: str
    url: str
    url_type: str
    source: str
    license: str
    access_policy: str
    tags: List[str]
    verification_status: str
    row_count: int
    columns: List[ColumnProfile]
    profiling_version: str
    catalog_version: str


# System prompt - defines the role and constraints
SYSTEM_PROMPT = """You are a scientific data analyst specializing in combustion science datasets from NASA PSI (Physical Sciences Informatics).

CRITICAL RULES - YOU MUST FOLLOW THESE EXACTLY:
1. NEVER invent statistics, numbers, findings, or claims not explicitly provided in the verifiable facts
2. NEVER make interpretations or conclusions beyond what the data directly supports
3. ALWAYS distinguish between METADATA (descriptions, tags) and COMPUTED STATISTICS (actual data analysis)
4. If statistics are not available for a column, STATE THIS EXPLICITLY - do not guess
5. Every claim must have a SOURCE REFERENCE: either "metadata" or "computed_statistics"
6. List LIMITATIONS and WARNINGS about unavailable information
7. Be concise and scientific in tone

OUTPUT FORMAT - Structure your response as:
TITLE: [Dataset title]
EXECUTIVE_SUMMARY: [2-3 sentence summary]
KEY_VARIABLES: [Comma-separated list of key variables]
COVERAGE: [Temporal, geographic, row count]
FINDINGS: [Each finding as: DESCRIPTION | EVIDENCE | SOURCE]
LIMITATIONS: [List of limitations]
WARNINGS: [List of warnings]
SOURCES: [List of sources with type and reference]"""

# User prompt template - filled with verifiable facts
USER_PROMPT_TEMPLATE = """VERIFIED FACTS FOR DATASET: {dataset_id}

METADATA:
- Name: {name}
- Description: {description}
- PSI Investigation: {psi_id} ({investigation_title})
- Format: {format}
- URL: {url} (Type: {url_type})
- Source: {source}
- License: {license}
- Access Policy: {access_policy}
- Tags: {tags}
- Verification Status: {verification_status}
- Row Count: {row_count}
- Catalog Version: {catalog_version}
- Profiling Version: {profiling_version}

COLUMN PROFILES:
{column_profiles}

Generate an evidence-based summary following the required format. Use ONLY the facts above. Do not infer or add information not present in these facts."""


def _format_number(val: float) -> str:
    """Format number without scientific notation."""
    if val is None:
        return "N/A"
    # Use fixed-point notation, avoid scientific notation
    if abs(val) >= 1e6 or (abs(val) < 1e-3 and val != 0):
        return f"{val:.3g}"
    # For reasonable ranges, use fixed point with up to 3 decimal places
    if val == int(val):
        return str(int(val))
    return f"{val:.3f}".rstrip('0').rstrip('.')


def format_column_profiles(columns: List[ColumnProfile]) -> str:
    """Format column profiles for prompt."""
    lines = []
    for col in columns:
        line = f"- {col.name} ({col.dtype.value}): "
        details = []

        details.append(f"nullable={col.nullable}, null_fraction={col.null_fraction:.2f}")
        details.append(f"unique={col.unique_count}")

        if col.dtype.value == "numeric":
            if col.min_val is not None:
                details.append(f"range=[{_format_number(col.min_val)}, {_format_number(col.max_val)}]")
            if col.mean is not None:
                details.append(f"mean={_format_number(col.mean)}")
            if col.median is not None:
                details.append(f"median={_format_number(col.median)}")
            if col.std is not None:
                details.append(f"std={_format_number(col.std)}")

        elif col.dtype.value == "categorical":
            if col.top_values:
                top = list(col.top_values.keys())[:5]
                details.append(f"top_values={top}")
            if col.entropy is not None:
                details.append(f"entropy={col.entropy:.3f}")

        elif col.dtype.value == "datetime":
            if col.min_date and col.max_date:
                details.append(f"range=[{col.min_date}, {col.max_date}]")
            if col.date_range_days is not None:
                details.append(f"span={col.date_range_days:.1f} days")

        elif col.dtype.value == "text":
            if col.avg_length is not None:
                details.append(f"avg_len={col.avg_length:.1f}")

        line += ", ".join(details)
        lines.append(line)

    return "\n".join(lines)


def build_prompt(context: PromptContext) -> tuple[str, str]:
    """Build system and user prompts for summarization."""
    column_profiles = format_column_profiles(context.columns)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        dataset_id=context.dataset_id,
        name=context.name,
        description=context.description,
        psi_id=context.psi_id,
        investigation_title=context.investigation_title,
        format=context.format,
        url=context.url,
        url_type=context.url_type,
        source=context.source,
        license=context.license,
        access_policy=context.access_policy,
        tags=", ".join(context.tags),
        verification_status=context.verification_status,
        row_count=context.row_count,
        catalog_version=context.catalog_version,
        profiling_version=context.profiling_version,
        column_profiles=column_profiles,
    )

    return SYSTEM_PROMPT, user_prompt


def parse_summary_response(response: str, context: PromptContext) -> Dict[str, Any]:
    """Parse LLM response into structured summary."""
    lines = response.strip().split("\n")

    result = {
        "title": "",
        "executiveSummary": "",
        "keyVariables": [],
        "coverage": {},
        "findings": [],
        "limitations": [],
        "warnings": [],
        "sources": [],
    }

    current_section = None
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect section headers
        if line.startswith("TITLE:"):
            current_section = "title"
            result["title"] = line[6:].strip()
        elif line.startswith("EXECUTIVE_SUMMARY:"):
            current_section = "executiveSummary"
            result["executiveSummary"] = line[18:].strip()
        elif line.startswith("KEY_VARIABLES:"):
            current_section = "keyVariables"
            vars_str = line[14:].strip()
            result["keyVariables"] = [v.strip() for v in vars_str.split(",") if v.strip()]
        elif line.startswith("COVERAGE:"):
            current_section = "coverage"
            result["coverage"]["description"] = line[9:].strip()
        elif line.startswith("FINDINGS:"):
            current_section = "findings"
            # Parse finding if on same line
            finding_text = line[9:].strip()
            if finding_text:
                result["findings"].append(parse_finding(finding_text))
        elif line.startswith("LIMITATIONS:"):
            current_section = "limitations"
            lim = line[12:].strip()
            if lim:
                result["limitations"].append(lim)
        elif line.startswith("WARNINGS:"):
            current_section = "warnings"
            warn = line[9:].strip()
            if warn:
                result["warnings"].append(warn)
        elif line.startswith("SOURCES:"):
            current_section = "sources"
            src = line[8:].strip()
            if src:
                result["sources"].append(parse_source(src))
        elif current_section == "findings" and line:
            result["findings"].append(parse_finding(line))
        elif current_section == "limitations" and line:
            result["limitations"].append(line)
        elif current_section == "warnings" and line:
            result["warnings"].append(line)
        elif current_section == "sources" and line:
            result["sources"].append(parse_source(line))
        elif current_section == "executiveSummary":
            result["executiveSummary"] += " " + line
        elif current_section == "coverage":
            if "description" not in result["coverage"]:
                result["coverage"]["description"] = line
            else:
                result["coverage"]["description"] += " " + line

    # Add standard sources
    result["sources"].extend([
        {"type": "metadata", "reference": f"{context.psi_id} investigation record"},
        {"type": "metadata", "reference": f"dataset catalog entry {context.dataset_id}"},
    ])

    # Add statistics sources for numeric columns
    for col in context.columns:
        if col.dtype.value == "numeric" and col.mean is not None:
            result["sources"].append({
                "type": "statistics",
                "reference": f"column statistics for {col.name}"
            })

    return result


def parse_finding(text: str) -> Dict[str, str]:
    """Parse a finding line into structured format."""
    # Expected format: DESCRIPTION | EVIDENCE | SOURCE
    parts = [p.strip() for p in text.split("|")]
    if len(parts) >= 3:
        return {
            "description": parts[0],
            "evidence": parts[1],
            "source": parts[2],
        }
    elif len(parts) == 2:
        return {
            "description": parts[0],
            "evidence": parts[1],
            "source": "metadata",
        }
    else:
        return {
            "description": text,
            "evidence": "From metadata",
            "source": "metadata",
        }


def parse_source(text: str) -> Dict[str, str]:
    """Parse a source line into structured format."""
    # Expected format: TYPE: REFERENCE
    parts = [p.strip() for p in text.split(":", 1)]
    if len(parts) == 2:
        return {"type": parts[0].lower(), "reference": parts[1]}
    return {"type": "metadata", "reference": text}


# Descriptive summary template (when no LLM available or statistics unavailable)
DESCRIPTIVE_SUMMARY_TEMPLATE = """TITLE: {name} - Descriptive Summary

EXECUTIVE_SUMMARY: This dataset ({name}) from investigation {psi_id} ({investigation_title}) contains {num_numeric} numerical columns and {num_categorical} categorical columns across {row_count} rows. Data format: {format}. Access: {access_policy}. Verification status: {verification_status}.

KEY_VARIABLES: {key_variables}

COVERAGE: {coverage_desc}

FINDINGS:
{findings}

LIMITATIONS:
- Summary generated from metadata only; no LLM enhancement available
- Statistics may not be available for all columns
- Data not directly inspected; based on cataloged metadata

WARNINGS:
- Verification status: {verification_status}
- This is a descriptive summary, not an analytical summary
- Numerical content detection based on sampling

SOURCES:
- metadata: {psi_id} investigation record
- metadata: dataset catalog entry {dataset_id}
{sources_statistics}"""


def generate_descriptive_summary(context: PromptContext) -> str:
    """Generate a descriptive summary without LLM."""
    numeric_cols = [c for c in context.columns if c.dtype.value == "numeric"]
    categorical_cols = [c for c in context.columns if c.dtype.value == "categorical"]

    findings_lines = []
    for col in numeric_cols:
        if col.min_val is not None:
            findings_lines.append(
                f"- {col.name}: range [{_format_number(col.min_val)}, {_format_number(col.max_val)}] "
                f"(mean: {_format_number(col.mean)}, source: computed_statistics)"
            )
        else:
            findings_lines.append(f"- {col.name}: numerical column (no statistics available, source: metadata)")

    for col in categorical_cols:
        if col.top_values:
            top = list(col.top_values.keys())[:3]
            findings_lines.append(f"- {col.name}: categorical with values {top} (source: metadata)")

    sources_stats = ""
    if numeric_cols:
        sources_stats = "\n- computed_statistics: column statistics for " + ", ".join(c.name for c in numeric_cols)

    return DESCRIPTIVE_SUMMARY_TEMPLATE.format(
        name=context.name,
        psi_id=context.psi_id,
        investigation_title=context.investigation_title,
        num_numeric=len(numeric_cols),
        num_categorical=len(categorical_cols),
        row_count=context.row_count or "unknown",
        format=context.format,
        access_policy=context.access_policy,
        verification_status=context.verification_status,
        key_variables=", ".join([c.name for c in context.columns]),
        coverage_desc=f"Temporal: {context.tags[0] if context.tags else 'Unknown'}, Rows: {context.row_count or 'Unknown'}",
        findings="\n".join(findings_lines) if findings_lines else "- No statistical findings available",
        dataset_id=context.dataset_id,
        sources_statistics=sources_stats,
    )