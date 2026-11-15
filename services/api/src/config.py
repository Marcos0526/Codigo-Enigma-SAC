"""API service configuration."""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Application
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "info"

    # Database
    DATABASE_URL: str = "postgresql://enigma:enigma@localhost:5432/enigma_sac"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_SSL: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Embedding Service
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_API_URL: str = "http://localhost:8080/embed"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_VERSION: str = "1.0.0"
    EMBEDDING_DIMENSIONS: int = 384
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_MAX_LENGTH: int = 512

    # NVIDIA API (when using EMBEDDING_PROVIDER=nvidia)
    NVIDIA_API_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_INPUT_TYPE: str = "query"

    # LLM Service
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: str = ""
    LLM_API_URL: str = ""
    LLM_MODEL: str = "gpt-4-turbo-preview"
    LLM_MAX_TOKENS: int = 2000
    LLM_TEMPERATURE: float = 0.1

    # Data Connectors
    ALLOWED_DATA_DOMAINS: str = "psi.nasa.gov,raw.githubusercontent.com,data.nasa.gov"
    MAX_DOWNLOAD_SIZE: int = 104857600
    DOWNLOAD_TIMEOUT: int = 30

    # Search
    SEARCH_MIN_SCORE: float = 0.3
    SEARCH_MAX_RESULTS: int = 100
    SEARCH_RERANK_ENABLED: bool = False
    SEARCH_RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Profiling & Visualization Limits
    MAX_PROFILE_ROWS: int = 100000
    MAX_PROFILE_MEMORY_MB: int = 512
    MAX_PROFILE_TIME_SECONDS: int = 60
    MAX_CHART_ROWS: int = 10000
    MAX_CHART_MEMORY_MB: int = 256
    MAX_CHART_TIME_SECONDS: int = 30

    # Security
    SSRF_PROTECTION_ENABLED: bool = True
    ALLOWED_IP_RANGES: str = ""
    RATE_LIMIT_RPM: int = 60

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Catalog
    CATALOG_VERSION: str = "1.0.0"
    CATALOG_SOURCE_URL: str = "https://psi.nasa.gov/physci/repo/search?q=combustion&data_source=psi&data_type=investigation"
    CATALOG_PSI_INDEX_CSV: str = "https://raw.githubusercontent.com/Krypton-N/NASA-SPACE-APPS/main/data/psi/psi_index.csv"

    # Service URLs (for service-to-service communication)
    CATALOG_SERVICE_URL: str = "http://localhost:8001"
    SEARCH_SERVICE_URL: str = "http://localhost:8002"
    SUMMARIZER_SERVICE_URL: str = "http://localhost:8003"
    VISUALIZATION_SERVICE_URL: str = "http://localhost:8004"

    # Source collection constant
    SOURCE_COLLECTION: str = "NASA PSI — Combustion Science: 26 Selected Investigations"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"

    @property
    def allowed_domains_list(self) -> List[str]:
        return [d.strip() for d in self.ALLOWED_DATA_DOMAINS.split(",") if d.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_ip_ranges_list(self) -> List[str]:
        return [r.strip() for r in self.ALLOWED_IP_RANGES.split(",") if r.strip()]

    @property
    def embedding_dimensions(self) -> int:
        """Alias for VECTOR_DIMENSIONS for backward compatibility."""
        return self.VECTOR_DIMENSIONS


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()