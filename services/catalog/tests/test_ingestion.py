"""Tests for catalog ingestion."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio

from services.catalog.src.ingestion.psi_ingester import PSIIngester, IngestionResult
from services.catalog.src.ingestion.dataset_ingester import DatasetIngester, DatasetIngestionResult
from services.catalog.src.models.catalog import (
    PSIInvestigation,
    VerificationStatus,
    DataFormat,
    URLType as ModelURLType,
)
from services.catalog.src.validation.url_validator import URLValidationResult


class TestPSIIngester:
    """Tests for PSI investigation ingester."""

    @pytest.fixture
    def mock_pool(self):
        """Create a mock database pool."""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        return pool

    @pytest.fixture
    def ingester(self, mock_pool):
        """Create ingester with mock pool."""
        return PSIIngester(mock_pool)

    @pytest.mark.asyncio
    async def test_filter_selected_investigations(self, ingester):
        """Test filtering to 26 selected investigations."""
        index_rows = [
            {"psi_id": "PSI-20", "title": "Test 20"},
            {"psi_id": "PSI-999", "title": "Not Selected"},
            {"psi_id": "PSI-21", "title": "Test 21"},
        ]

        filtered = ingester.filter_selected_investigations(index_rows)

        assert len(filtered) == 2
        assert all(r["psi_id"] in {"PSI-20", "PSI-21"} for r in filtered)

    @pytest.mark.asyncio
    async def test_parse_investigation_page_with_doi(self, ingester):
        """Test parsing investigation page with DOI."""
        from bs4 import BeautifulSoup

        html = """
        <html>
            <h1>PSI-20: ACME — Burning Rate Emulator (BRE)</h1>
            <p>DOI: 10.60555/vb93-3y72</p>
            <h2>Objectives</h2>
            <p>Determine burning rates in low-gravity.</p>
            <h2>Approach</h2>
            <p>Use ACME modular burner.</p>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        metadata = ingester.parse_investigation_page("PSI-20", soup)

        assert metadata["psi_id"] == "PSI-20"
        assert "Burning Rate Emulator" in metadata["title"]
        assert metadata["doi"] == "10.60555/vb93-3y72"
        assert metadata["doi_url"] == "https://doi.org/10.60555/vb93-3y72"
        assert "burning rates" in metadata["objectives"].lower()
        assert metadata["metadata_status"] == VerificationStatus.VERIFIED.value

    @pytest.mark.asyncio
    async def test_parse_investigation_page_pending(self, ingester):
        """Test parsing investigation page with minimal content (pending)."""
        from bs4 import BeautifulSoup

        html = """
        <html>
            <h1>PSI-68</h1>
            <p>No detailed content available.</p>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        metadata = ingester.parse_investigation_page("PSI-68", soup)

        assert metadata["psi_id"] == "PSI-68"
        assert metadata["metadata_status"] == VerificationStatus.PENDING.value
        assert "pending-verification" in metadata["tags"]


class TestDatasetIngester:
    """Tests for dataset ingester."""

    @pytest.fixture
    def mock_pool(self):
        """Create a mock database pool."""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        return pool

    @pytest.fixture
    def ingester(self, mock_pool):
        """Create dataset ingester with mock pool."""
        return DatasetIngester(mock_pool)

    @pytest.mark.asyncio
    async def test_detect_format_from_url(self, ingester):
        """Test format detection from URL."""
        assert ingester._detect_format_from_url("https://example.com/data.csv") == DataFormat.CSV
        assert ingester._detect_format_from_url("https://example.com/data.parquet") == DataFormat.PARQUET
        assert ingester._detect_format_from_url("https://example.com/data.json") == DataFormat.JSON
        assert ingester._detect_format_from_url("https://example.com/data.xlsx") == DataFormat.XLSX
        assert ingester._detect_format_from_url("https://example.com/data") == DataFormat.UNKNOWN

    def test_classify_url_type(self, ingester):
        """Test URL type classification."""
        # DOI
        assert ingester._classify_url_type("https://doi.org/10.1234/test") == ModelURLType.DOI

        # Investigation page
        assert ingester._classify_url_type(
            "https://psi.nasa.gov/physci/repo/data/investigations/PSI-20"
        ) == ModelURLType.INVESTIGATION_PAGE

        # Direct download by extension
        assert ingester._classify_url_type("https://example.com/data.csv") == ModelURLType.DIRECT_DOWNLOAD
        assert ingester._classify_url_type("https://example.com/data.parquet") == ModelURLType.DIRECT_DOWNLOAD

        # Direct download by content type
        assert ingester._classify_url_type(
            "https://example.com/data", "text/csv"
        ) == ModelURLType.DIRECT_DOWNLOAD

        # Unverified
        assert ingester._classify_url_type("https://example.com/page") == ModelURLType.UNVERIFIED

    def test_infer_column_type(self, ingester):
        """Test column type inference."""
        import pandas as pd

        # Numeric
        numeric_series = pd.Series([1, 2, 3, 4, 5])
        assert ingester._infer_column_type(numeric_series) == "numeric"

        # Float
        float_series = pd.Series([1.1, 2.2, 3.3])
        assert ingester._infer_column_type(float_series) == "numeric"

        # Boolean - string values
        bool_series = pd.Series(["true", "false", "true"])
        assert ingester._infer_column_type(bool_series) == "boolean"

        # String boolean variations
        str_bool = pd.Series(["yes", "no", "yes"])
        assert ingester._infer_column_type(str_bool) == "boolean"

        # Categorical (low cardinality)
        cat_series = pd.Series(["A", "B", "A", "B", "A"])
        assert ingester._infer_column_type(cat_series) == "categorical"

        # Text (high cardinality)
        text_series = pd.Series([f"item_{i}" for i in range(100)])
        assert ingester._infer_column_type(text_series) == "text"

    def test_compute_column_statistics(self, ingester):
        """Test column statistics computation."""
        import pandas as pd

        numeric_series = pd.Series([10, 20, 30, 40, 50])
        stats = ingester._compute_column_statistics(numeric_series, "numeric")

        assert stats is not None
        assert stats["count"] == 5
        assert stats["min"] == 10
        assert stats["max"] == 50
        assert stats["mean"] == 30
        assert stats["median"] == 30

        # Non-numeric should return None
        text_series = pd.Series(["a", "b", "c"])
        stats = ingester._compute_column_statistics(text_series, "text")
        assert stats is None


class TestCatalogModels:
    """Tests for catalog data models."""

    def test_psi_investigation_model(self):
        """Test PSI investigation model validation."""
        inv = PSIInvestigation(
            psi_id="PSI-20",
            title="Test Investigation",
            description="Test description",
            research_area="Combustion Science",
            psi_record_url="https://psi.nasa.gov/physci/repo/data/investigations/PSI-20",
            metadata_status=VerificationStatus.VERIFIED,
            tags=["test"],
        )

        assert inv.psi_id == "PSI-20"
        assert inv.metadata_status == VerificationStatus.VERIFIED

    def test_dataset_model(self):
        """Test dataset model validation."""
        from services.catalog.src.models.catalog import Dataset

        dataset = Dataset(
            dataset_id="psi-20-test-abc12345",
            psi_id="PSI-20",
            name="Test Dataset",
            description="Test description",
            url="https://example.com/data.csv",
            url_type=ModelURLType.DIRECT_DOWNLOAD,
            format=DataFormat.CSV,
            numeric_columns=["temperature", "pressure"],
            source="NASA PSI",
            access_policy="public",
            catalog_version="1.0.0",
            verification_status=VerificationStatus.VERIFIED,
            tags=["test"],
            provenance_investigation_url="https://psi.nasa.gov/physci/repo/data/investigations/PSI-20",
            provenance_dataset_url="https://example.com/data.csv",
        )

        assert dataset.dataset_id == "psi-20-test-abc12345"
        assert dataset.format == DataFormat.CSV
        assert dataset.url_type == ModelURLType.DIRECT_DOWNLOAD
        assert len(dataset.numeric_columns) == 2

    def test_verification_status_enum(self):
        """Test verification status enum values."""
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.PENDING.value == "pending"
        assert VerificationStatus.FAILED.value == "failed"
        assert VerificationStatus.UNKNOWN.value == "unknown"

    def test_data_format_enum(self):
        """Test data format enum values."""
        assert DataFormat.CSV.value == "csv"
        assert DataFormat.PARQUET.value == "parquet"
        assert DataFormat.JSON.value == "json"
        assert DataFormat.UNKNOWN.value == "unknown"

    def test_url_type_enum(self):
        """Test URL type enum values."""
        assert ModelURLType.INVESTIGATION_PAGE.value == "investigation_page"
        assert ModelURLType.DIRECT_DOWNLOAD.value == "direct_download"
        assert ModelURLType.DOI.value == "doi"
        assert ModelURLType.UNVERIFIED.value == "unverified"