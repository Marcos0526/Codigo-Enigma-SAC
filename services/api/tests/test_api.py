"""Tests for API routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from services.api.src.main import app
from services.api.src.config import settings


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Enigma SAC API"
        assert "version" in data
        assert "docs" in data
        assert "health" in data


class TestConfig:
    """Tests for configuration."""

    def test_settings_load(self):
        """Test settings load correctly."""
        assert settings.APP_VERSION == "1.0.0"
        assert settings.SOURCE_COLLECTION == "NASA PSI — Combustion Science: 26 Selected Investigations"
        assert settings.CATALOG_VERSION == "1.0.0"
        assert settings.VECTOR_DIMENSIONS == 384
        assert settings.embedding_dimensions == 384  # alias property

    def test_allowed_domains_parsed(self):
        """Test allowed domains are parsed correctly."""
        domains = settings.allowed_domains_list
        assert "psi.nasa.gov" in domains
        assert "raw.githubusercontent.com" in domains
        assert "data.nasa.gov" in domains

    def test_cors_origins_parsed(self):
        """Test CORS origins are parsed correctly."""
        origins = settings.cors_origins_list
        assert "http://localhost:3000" in origins
        assert "http://localhost:8000" in origins


class TestSearchEndpoint:
    """Tests for search endpoint."""

    def test_search_validation(self, client):
        """Test search request validation."""
        # Empty query should fail
        response = client.post("/api/v1/search", json={"query": ""})
        assert response.status_code == 422

        # Missing query should fail
        response = client.post("/api/v1/search", json={})
        assert response.status_code == 422

    def test_search_minimal_request(self, client):
        """Test minimal valid search request structure."""
        # Just test validation passes - will fail at DB layer
        response = client.post("/api/v1/search", json={"query": "combustion temperature"})
        # Should not be 422 (validation error) - validation passes
        assert response.status_code != 422