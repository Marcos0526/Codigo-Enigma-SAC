"""Keep the full Markdown response intact for the research summary card."""

import asyncio
from unittest.mock import AsyncMock, patch

from services.api.src.routes import summarization
from services.api.src.routes.summarization import (
    generate_descriptive_summary,
    generate_llm_summary,
    parse_summary,
)


def test_summary_preserves_complete_markdown():
    markdown = (
        "# Research summary\n\n## Findings\n\n"
        + "- **Measured evidence:** the numerical range is cataloged.\n" * 20
        + "\n| Variable | Unit |\n| --- | --- |\n| Temperature | K |\n\n"
        + "## Limitations\n\nNo causal inference is established."
    )
    facts = {"name": "Temperature", "psi_id": "PSI-20", "dataset_id": "test", "numeric_columns": []}
    result = parse_summary(markdown, facts)
    assert len(markdown) > 500
    assert result["executiveSummary"] == markdown
    assert result["executiveSummary"].endswith("No causal inference is established.")


def test_fallback_summary_uses_markdown_headings():
    facts = {
        "name": "Temperature", "psi_id": "PSI-20", "dataset_id": "test",
        "format": "csv", "access_policy": "public", "verification_status": "verified",
    }
    result = generate_descriptive_summary(facts)
    assert result.startswith("# Temperature")
    assert "## Executive summary\n\n" in result
    assert "## Findings" in result
    assert "## Sources" in result


def test_fallback_summary_explains_experiment_and_variable_limits():
    facts = {
        "name": "19056A2 data", "psi_id": "PSI-20", "dataset_id": "test",
        "investigation_title": "ACME — Burning Rate Emulator (BRE)",
        "format": "csv", "access_policy": "local read-only",
        "verification_status": "verified", "numeric_columns": [],
        "experiment_context": {
            "research_area": "Combustion Science",
            "subresearch_area": "Flames of Gaseous Fuels",
            "scientific_focus": "Gaseous combustion; flame burning rates",
            "project_setting": "ISS microgravity experiment",
            "objectives": "Determine how ventilation and oxygen affect burning rates.",
            "approach": "Use an ACME modular burner in the ISS Combustion Integrated Rack.",
        },
        "dataset_context": {
            "source_file": "19056A2_data.csv",
            "row_count": 31316,
            "column_count": 36,
            "related_files": [{"name": "19056B1 data", "format": "csv"}],
        },
    }
    result = generate_descriptive_summary(facts)
    assert "## Experiment context" in result
    assert "Determine how ventilation and oxygen affect burning rates." in result
    assert "## What this dataset represents" in result
    assert "19056A2_data.csv" in result
    assert "## Variable interpretation" in result
    assert "No formal variable dictionary" in result


def test_groq_provider_uses_openai_compatible_summary():
    facts = {"name": "Temperature", "psi_id": "PSI-20", "dataset_id": "test"}
    with patch.object(summarization.settings, "LLM_PROVIDER", "groq"), patch.object(
        summarization.settings, "LLM_API_KEY", "test-key"
    ), patch.object(
        summarization,
        "generate_openai_summary",
        AsyncMock(return_value="Groq summary"),
    ) as generate:
        result = asyncio.run(generate_llm_summary(facts, {}))

    assert result == "Groq summary"
    generate.assert_awaited_once_with(facts, {})
