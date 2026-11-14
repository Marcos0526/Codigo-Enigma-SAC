"""Tests for catalog validation utilities."""

import pytest
import pandas as pd
import io

from services.catalog.src.validation.url_validator import (
    URLValidator,
    URLValidationResult,
)
from services.catalog.src.validation.numerical_detector import (
    NumericalDetector,
    NumericalDetectionResult,
)
from services.catalog.src.validation.deduplication import (
    generate_stable_dataset_id,
    normalize_dataset_name,
)
from services.catalog.src.models.catalog import URLType


class TestURLValidator:
    """Tests for URL validation."""

    def test_classify_doi_url(self):
        """Test DOI URL classification."""
        validator = URLValidator()
        assert validator._classify_url_type("https://doi.org/10.1234/test") == URLType.DOI.value
        assert validator._classify_url_type("http://dx.doi.org/10.1234/test") == URLType.DOI.value

    def test_classify_psi_investigation_page(self):
        """Test PSI investigation page classification."""
        validator = URLValidator()
        url = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-20"
        assert validator._classify_url_type(url) == URLType.INVESTIGATION_PAGE.value

        url_with_slash = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-20/"
        assert validator._classify_url_type(url_with_slash) == URLType.INVESTIGATION_PAGE.value

    def test_classify_direct_download_by_extension(self):
        """Test direct download classification by file extension."""
        validator = URLValidator()
        extensions = [".csv", ".parquet", ".json", ".xlsx", ".tsv", ".txt", ".zip"]
        for ext in extensions:
            url = f"https://example.com/data{ext}"
            assert validator._classify_url_type(url) == URLType.DIRECT_DOWNLOAD.value, f"Failed for {ext}"

    def test_classify_direct_download_by_content_type(self):
        """Test direct download classification by content type."""
        validator = URLValidator()
        url = "https://example.com/data"

        data_content_types = [
            "text/csv",
            "application/csv",
            "application/vnd.ms-excel",
            "application/parquet",
            "application/json",
            "application/octet-stream",
            "application/zip",
            "application/gzip",
        ]

        for ct in data_content_types:
            assert validator._classify_url_type(url, ct) == URLType.DIRECT_DOWNLOAD.value, f"Failed for {ct}"

    def test_classify_unverified(self):
        """Test unverified classification for unknown URLs."""
        validator = URLValidator()
        assert validator._classify_url_type("https://example.com/unknown") == URLType.UNVERIFIED.value

    @pytest.mark.asyncio
    async def test_validate_allowed_domain(self):
        """Test validation of allowed domains."""
        validator = URLValidator(allowed_domains={"example.com"})
        # This would need a real HTTP server to test fully
        # Just testing the domain check logic
        assert validator._is_allowed_domain("https://example.com/data.csv") is True
        assert validator._is_allowed_domain("https://sub.example.com/data.csv") is True
        assert validator._is_allowed_domain("https://notallowed.com/data.csv") is False


class TestNumericalDetector:
    """Tests for numerical content detection."""

    def test_detect_csv_with_numeric_columns(self):
        """Test detection of numeric columns in CSV."""
        detector = NumericalDetector()
        csv_content = b"time,temperature,pressure\n0,300,101.3\n1,350,102.1\n2,400,103.5\n"
        result = detector.detect_from_bytes(csv_content, "test.csv")

        assert result.has_numerical_data is True
        assert "temperature" in result.numeric_columns
        assert "pressure" in result.numeric_columns
        assert "time" in result.numeric_columns
        assert result.column_types["temperature"] == "numeric"
        assert result.column_types["pressure"] == "numeric"

    def test_detect_csv_with_mixed_columns(self):
        """Test detection with mixed column types."""
        detector = NumericalDetector()
        csv_content = b"id,name,temperature,category\n1,sample1,300,A\n2,sample2,350,B\n3,sample3,400,A\n"
        result = detector.detect_from_bytes(csv_content, "test.csv")

        assert result.has_numerical_data is True
        assert "temperature" in result.numeric_columns
        assert "id" in result.numeric_columns  # id is numeric
        # For small datasets, name with few unique values is categorical
        assert result.column_types["category"] == "categorical"

    def test_detect_csv_no_numeric(self):
        """Test detection with no numeric columns."""
        detector = NumericalDetector()
        csv_content = b"name,category,description\nsample1,A,desc1\nsample2,B,desc2\n"
        result = detector.detect_from_bytes(csv_content, "test.csv")

        assert result.has_numerical_data is False
        assert len(result.numeric_columns) == 0

    def test_detect_datetime_column(self):
        """Test datetime column detection."""
        detector = NumericalDetector()
        csv_content = b"timestamp,value\n2024-01-01,10\n2024-01-02,20\n2024-01-03,30\n"
        result = detector.detect_from_bytes(csv_content, "test.csv")

        assert "timestamp" in result.column_types
        assert result.column_types["timestamp"] == "datetime"

    def test_detect_boolean_column(self):
        """Test boolean column detection."""
        detector = NumericalDetector()
        csv_content = b"flag,value\ntrue,10\nfalse,20\ntrue,30\n"
        result = detector.detect_from_bytes(csv_content, "test.csv")

        assert result.column_types["flag"] == "boolean"

    def test_empty_content(self):
        """Test detection with empty content."""
        detector = NumericalDetector()
        result = detector.detect_from_bytes(b"", "test.csv")

        assert result.has_numerical_data is False
        assert result.error == "Empty content"

    def test_min_numeric_fraction(self):
        """Test minimum numeric fraction threshold."""
        detector = NumericalDetector(min_numeric_fraction=0.9)
        # Only 2 out of 3 values are numeric (66%)
        csv_content = b"value\n10\n20\nnot_a_number\n"
        result = detector.detect_from_bytes(csv_content, "test.csv")

        # Should not be classified as numeric due to threshold
        assert "value" not in result.numeric_columns or result.column_types["value"] != "numeric"


class TestDeduplication:
    """Tests for deduplication utilities."""

    def test_generate_stable_dataset_id(self):
        """Test stable dataset ID generation."""
        id1 = generate_stable_dataset_id("PSI-20", "temperature.csv", "https://example.com/data.csv")
        id2 = generate_stable_dataset_id("PSI-20", "temperature.csv", "https://example.com/data.csv")
        id3 = generate_stable_dataset_id("PSI-21", "temperature.csv", "https://example.com/data.csv")

        assert id1 == id2  # Same inputs produce same ID
        assert id1 != id3  # Different PSI ID produces different ID
        assert id1.startswith("psi-20-temperature-")

    def test_normalize_dataset_name(self):
        """Test dataset name normalization."""
        assert normalize_dataset_name("Temperature Data") == "temperature-data"
        assert normalize_dataset_name("Flame_Temperature_Measurements") == "flame-temperature-measurements"
        assert normalize_dataset_name("  Spaces  and  Symbols!@#  ") == "spaces-and-symbols"
        assert normalize_dataset_name("MULTIPLE---HYPHENS") == "multiple-hyphens"

    def test_generate_stable_id_with_special_chars(self):
        """Test stable ID generation with special characters in name."""
        id1 = generate_stable_dataset_id("PSI-20", "temp@#$%data.csv", "https://example.com/data.csv")
        # Special chars removed, extension stripped
        assert id1.startswith("psi-20-tempdata-")


class TestIntegration:
    """Integration tests for validation pipeline."""

    def test_full_detection_pipeline(self):
        """Test complete detection pipeline."""
        # Create a realistic dataset
        df = pd.DataFrame({
            "time_s": [0, 1, 2, 3, 4],
            "temperature_k": [300, 350, 400, 450, 500],
            "pressure_kpa": [101.3, 102.1, 103.5, 104.2, 105.0],
            "experiment_id": ["exp1", "exp1", "exp2", "exp2", "exp3"],
            "fuel_type": ["methane", "methane", "propane", "propane", "hydrogen"],
        })

        # Convert to CSV bytes
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue().encode()

        # Detect
        detector = NumericalDetector()
        result = detector.detect_from_bytes(csv_content, "combustion_data.csv")

        assert result.has_numerical_data is True
        assert set(result.numeric_columns) == {"time_s", "temperature_k", "pressure_kpa"}
        assert result.column_types["experiment_id"] == "categorical"
        assert result.column_types["fuel_type"] == "categorical"