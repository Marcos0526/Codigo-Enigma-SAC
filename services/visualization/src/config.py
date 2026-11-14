"""Visualization service configuration."""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Application
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "info"

    # Database
    DATABASE_URL: str = "postgresql://enigma:enigma@localhost:5432/enigma_sac"
    DATABASE_POOL_SIZE: int = 10

    # Data Connectors
    ALLOWED_DATA_DOMAINS: str = "psi.nasa.gov,raw.githubusercontent.com,data.nasa.gov"
    MAX_DOWNLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB
    DOWNLOAD_TIMEOUT: float = 30.0

    # Chart Limits
    MAX_CHART_ROWS: int = 10000
    MAX_CHART_MEMORY_MB: int = 256
    MAX_CHART_TIME_SECONDS: int = 30
    MAX_PREVIEW_ROWS: int = 1000
    DEFAULT_CHART_WIDTH: int = 800
    DEFAULT_CHART_HEIGHT: int = 400

    # Chart Types Supported
    SUPPORTED_CHART_TYPES: str = "bar,line,scatter,histogram"

    # Sampling
    SAMPLE_METHOD: str = "systematic"  # systematic, random, head
    DEFAULT_SAMPLE_SIZE: int = 5000

    # Security
    SSRF_PROTECTION_ENABLED: bool = True

    # Catalog
    CATALOG_VERSION: str = "1.0.0"
    SOURCE_COLLECTION: str = "NASA PSI — Combustion Science: 26 Selected Investigations"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @property
    def allowed_domains_list(self) -> List[str]:
        return [d.strip() for d in self.ALLOWED_DATA_DOMAINS.split(",") if d.strip()]

    @property
    def supported_chart_types_list(self) -> List[str]:
        return [c.strip() for c in self.SUPPORTED_CHART_TYPES.split(",") if c.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()