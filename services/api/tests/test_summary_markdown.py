"""Keep the full Markdown response intact for the research summary card."""

from services.api.src.routes.summarization import generate_descriptive_summary, parse_summary


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
