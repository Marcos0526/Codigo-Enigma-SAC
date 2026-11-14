"""Summarizer service configuration."""

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

    # LLM Service
    LLM_PROVIDER: str = "openai"  # openai, anthropic, local, ollama
    LLM_API_KEY: str = ""
    LLM_API_URL: str = ""  # For local/ollama
    LLM_MODEL: str = "gpt-4-turbo-preview"
    LLM_MAX_TOKENS: int = 2000
    LLM_TEMPERATURE: float = 0.1
    LLM_TIMEOUT: float = 60.0

    # Profiling
    MAX_PROFILE_ROWS: int = 100000
    MAX_PROFILE_MEMORY_MB: int = 512
    MAX_PROFILE_TIME_SECONDS: int = 60
    PROFILE_SAMPLE_SIZE: int = 10000

    # Summary Generation
    SUMMARY_MAX_LENGTH: int = 1000
    SUMMARY_INCLUDE_STATISTICS: bool = True
    SUMMARY_TEMPLATE_VERSION: str = "1.0"

    # Security
    SSRF_PROTECTION_ENABLED: bool = True
    ALLOWED_DATA_DOMAINS: str = "psi.nasa.gov,raw.githubusercontent.com,data.nasa.gov"

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()