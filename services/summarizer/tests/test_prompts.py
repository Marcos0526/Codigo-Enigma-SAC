"""Tests for summary prompts and parsing."""

import pytest
from services.summarizer.src.prompts.summary_prompts import (
    PromptContext,
    build_prompt,
    parse_summary_response,
    generate_descriptive_summary,
    format_column_profiles,
)
from services.summarizer.src.profiling.dataset_profiler import ColumnProfile, ColumnType


class TestPromptBuilding:
    """Tests for prompt building."""

    @pytest.fixture
    def sample_context(self):
        """Create a sample prompt context."""
        columns = [
            ColumnProfile(
                name="temperature_k",
                dtype=ColumnType.NUMERIC,
                nullable=False,
                null_count=0,
                null_fraction=0.0,
                unique_count=100,
                min_val=800.0,
                max_val=2200.0,
                mean=1540.0,
                median=1500.0,
                std=300.0,
                q1=1200.0,
                q3=1800.0,
            ),
            ColumnProfile(
                name="time_s",
                dtype=ColumnType.NUMERIC,
                nullable=False,
                null_count=0,
                null_fraction=0.0,
                unique_count=100,
                min_val=0.0,
                max_val=100.0,
                mean=50.0,
                median=50.0,
                std=30.0,
            ),
            ColumnProfile(
                name="experiment_id",
                dtype=ColumnType.CATEGORICAL,
                nullable=False,
                null_count=0,
                null_fraction=0.0,
                unique_count=5,
                top_values={"exp_1": 30, "exp_2": 25, "exp_3": 20, "exp_4": 15, "exp_5": 10},
                entropy=1.5,
            ),
        ]

        return PromptContext(
            dataset_id="psi-20-bre-temperature-csv",
            name="BRE Flame Temperature Measurements",
            description="Temperature measurements from Burning Rate Emulator experiments",
            psi_id="PSI-20",
            investigation_title="ACME — Burning Rate Emulator (BRE)",
            format="csv",
            url="https://psi.nasa.gov/physci/repo/data/investigations/PSI-20/data/bre_temperature.csv",
            url_type="direct_download",
            source="NASA Physical Sciences Informatics",
            license="Public Domain",
            access_policy="public",
            tags=["temperature", "time-series", "gaseous-fuels", "bre", "acme"],
            verification_status="verified",
            row_count=15420,
            columns=columns,
            profiling_version="1.0.0",
            catalog_version="1.0.0",
        )

    def test_format_column_profiles(self, sample_context):
        """Test column profile formatting."""
        formatted = format_column_profiles(sample_context.columns)

        assert "temperature_k (numeric)" in formatted
        assert "time_s (numeric)" in formatted
        assert "experiment_id (categorical)" in formatted
        # Check for range in scientific notation or plain
        assert "range=[800" in formatted or "range=[8.00e+02" in formatted
        assert "2200" in formatted or "2.2e+03" in formatted
        assert "mean=1.54e+03" in formatted or "mean=1540" in formatted
        assert "top_values" in formatted

    def test_build_prompt(self, sample_context):
        """Test prompt building."""
        system_prompt, user_prompt = build_prompt(sample_context)

        # Check system prompt
        assert "CRITICAL RULES" in system_prompt
        assert "NEVER invent statistics" in system_prompt
        assert "OUTPUT FORMAT" in system_prompt

        # Check user prompt
        assert "BRE Flame Temperature Measurements" in user_prompt
        assert "PSI-20" in user_prompt
        assert "ACME — Burning Rate Emulator (BRE)" in user_prompt
        assert "temperature_k (numeric)" in user_prompt
        # Check for range in scientific notation or plain
        assert "800" in user_prompt and "2200" in user_prompt


class TestDescriptiveSummary:
    """Tests for descriptive summary generation."""

    @pytest.fixture
    def sample_context(self):
        """Create a sample prompt context."""
        columns = [
            ColumnProfile(
                name="temperature_k",
                dtype=ColumnType.NUMERIC,
                nullable=False,
                null_count=0,
                null_fraction=0.0,
                unique_count=100,
                min_val=800.0,
                max_val=2200.0,
                mean=1540.0,
                median=1500.0,
                std=300.0,
            ),
            ColumnProfile(
                name="experiment_id",
                dtype=ColumnType.CATEGORICAL,
                nullable=False,
                null_count=0,
                null_fraction=0.0,
                unique_count=5,
                top_values={"exp_1": 30, "exp_2": 25, "exp_3": 20},
            ),
        ]

        return PromptContext(
            dataset_id="psi-20-bre-temperature-csv",
            name="BRE Flame Temperature Measurements",
            description="Temperature measurements from BRE experiments",
            psi_id="PSI-20",
            investigation_title="ACME — Burning Rate Emulator (BRE)",
            format="csv",
            url="https://example.com/data.csv",
            url_type="direct_download",
            source="NASA PSI",
            license="Public Domain",
            access_policy="public",
            tags=["temperature", "gaseous-fuels"],
            verification_status="verified",
            row_count=15420,
            columns=columns,
            profiling_version="1.0.0",
            catalog_version="1.0.0",
        )

    def test_generate_descriptive_summary(self, sample_context):
        """Test descriptive summary generation."""
        summary = generate_descriptive_summary(sample_context)

        assert "BRE Flame Temperature Measurements" in summary
        assert "PSI-20" in summary
        assert "ACME — Burning Rate Emulator (BRE)" in summary
        assert "15420" in summary
        assert "temperature_k" in summary
        assert "experiment_id" in summary
        # Check for range in either format
        assert "800" in summary and "2200" in summary
        assert "verified" in summary
        assert "SOURCES" in summary


class TestSummaryParsing:
    """Tests for summary response parsing."""

    def test_parse_summary_response(self):
        """Test parsing LLM response."""
        response = """TITLE: Test Dataset Summary
EXECUTIVE_SUMMARY: This is a test summary of the dataset.
KEY_VARIABLES: temperature, pressure, time
COVERAGE: Temporal: 2020-2021, Rows: 1000
FINDINGS:
- Temperature varies | min=300, max=2000, mean=1200 | computed_statistics
- Pressure ranges from 100 to 500 kPa | min=100, max=500 | computed_statistics
LIMITATIONS:
- Limited to specific conditions
- No data for extreme temperatures
WARNINGS:
- Statistics from sampled data
SOURCES:
- metadata: PSI-20 investigation record
- computed_statistics: column statistics for temperature"""

        from services.summarizer.src.profiling.dataset_profiler import ColumnProfile, ColumnType

        columns = [
            ColumnProfile(name="temperature", dtype=ColumnType.NUMERIC, nullable=False, null_count=0, null_fraction=0.0, unique_count=10, min_val=300, max_val=2000, mean=1200),
        ]

        context = PromptContext(
            dataset_id="test-001",
            name="Test Dataset",
            description="Test",
            psi_id="PSI-20",
            investigation_title="Test Investigation",
            format="csv",
            url="https://example.com/data.csv",
            url_type="direct_download",
            source="NASA",
            license="Public Domain",
            access_policy="public",
            tags=["test"],
            verification_status="verified",
            row_count=1000,
            columns=columns,
            profiling_version="1.0",
            catalog_version="1.0",
        )

        parsed = parse_summary_response(response, context)

        assert parsed["title"] == "Test Dataset Summary"
        assert parsed["executiveSummary"] == "This is a test summary of the dataset."
        assert parsed["keyVariables"] == ["temperature", "pressure", "time"]
        assert parsed["coverage"]["description"] == "Temporal: 2020-2021, Rows: 1000"
        assert len(parsed["findings"]) == 2
        # Findings include the leading dash
        assert parsed["findings"][0]["description"] == "- Temperature varies"
        assert parsed["findings"][0]["source"] == "computed_statistics"
        assert len(parsed["limitations"]) == 2
        assert len(parsed["warnings"]) == 1
        assert len(parsed["sources"]) >= 2

    def test_parse_finding_with_pipes(self):
        """Test parsing finding with pipe separators."""
        from services.summarizer.src.prompts.summary_prompts import parse_finding

        finding = parse_finding("Temperature varies | min=300, max=2000 | computed_statistics")
        assert finding["description"] == "Temperature varies"
        assert finding["evidence"] == "min=300, max=2000"
        assert finding["source"] == "computed_statistics"

    def test_parse_finding_without_pipes(self):
        """Test parsing finding without pipe separators."""
        from services.summarizer.src.prompts.summary_prompts import parse_finding

        finding = parse_finding("Simple finding without pipes")
        assert finding["description"] == "Simple finding without pipes"
        # When no pipes, evidence defaults to description, source to metadata
        assert finding["evidence"] == "From metadata"
        assert finding["source"] == "metadata"

    def test_parse_source(self):
        """Test parsing source."""
        from services.summarizer.src.prompts.summary_prompts import parse_source

        source = parse_source("metadata: PSI-20 investigation record")
        assert source["type"] == "metadata"
        assert source["reference"] == "PSI-20 investigation record"

        source = parse_source("computed_statistics: column statistics for temperature")
        assert source["type"] == "computed_statistics"
        assert source["reference"] == "column statistics for temperature"

    def test_parse_malformed_response(self):
        """Test parsing malformed response."""
        response = """TITLE: Test
EXECUTIVE_SUMMARY: Summary here
KEY_VARIABLES: a, b, c
COVERAGE: Some coverage
FINDINGS:
- Finding 1
LIMITATIONS:
- Limitation 1
WARNINGS:
- Warning 1
SOURCES:
- metadata: source 1"""

        from services.summarizer.src.profiling.dataset_profiler import ColumnProfile, ColumnType

        columns = [
            ColumnProfile(name="col1", dtype=ColumnType.NUMERIC, nullable=False, null_count=0, null_fraction=0.0, unique_count=10),
        ]

        context = PromptContext(
            dataset_id="test-001",
            name="Test Dataset",
            description="Test",
            psi_id="PSI-20",
            investigation_title="Test",
            format="csv",
            url="https://example.com/data.csv",
            url_type="direct_download",
            source="NASA",
            license="Public Domain",
            access_policy="public",
            tags=["test"],
            verification_status="verified",
            row_count=1000,
            columns=columns,
            profiling_version="1.0",
            catalog_version="1.0",
        )

        parsed = parse_summary_response(response, context)

        assert parsed["title"] == "Test"
        assert "Finding 1" in str(parsed["findings"])
        # Limitations include the leading dash
        assert "- Limitation 1" in parsed["limitations"]
        # Warnings include the leading dash
        assert "- Warning 1" in parsed["warnings"]