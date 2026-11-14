"""Search service configuration."""

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

    # Embedding Service
    EMBEDDING_PROVIDER: str = "local"  # local, openai, cohere, huggingface
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_API_URL: str = "http://localhost:8080/embed"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_VERSION: str = "1.0.0"
    EMBEDDING_DIMENSIONS: int = 384
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_MAX_LENGTH: int = 512

    # Local embedding model (for local provider)
    LOCAL_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    LOCAL_EMBEDDING_DEVICE: str = "cpu"  # cpu, cuda, mps

    # Search Configuration
    SEARCH_MIN_SCORE: float = 0.3
    SEARCH_MAX_RESULTS: int = 100
    SEARCH_DEFAULT_RESULTS: int = 50
    SEARCH_RERANK_ENABLED: bool = False
    SEARCH_RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    SEARCH_RERANK_TOP_K: int = 50

    # Query Classification
    CLASSIFICATION_ENABLED: bool = True
    CLASSIFICATION_MODEL: str = "distilbert-base-uncased"
    CLASSIFICATION_LABELS: List[str] = Field(default_factory=lambda: [
        "combustion_temperature",
        "flame_microgravity",
        "flame_propagation",
        "extinction",
        "soot",
        "aerosols_smoke",
        "fire_safety",
        "cool_flames",
        "solid_fuels",
        "gaseous_fuels",
        "liquid_fuels",
        "general_combustion",
    ])

    # Catalog
    CATALOG_VERSION: str = "1.0.0"
    SOURCE_COLLECTION: str = "NASA PSI — Combustion Science: 26 Selected Investigations"
    DATA_FILTER: str = "numeric_only"

    # Performance
    EMBEDDING_TIMEOUT: float = 30.0
    SEARCH_TIMEOUT: float = 10.0
    RERANK_TIMEOUT: float = 15.0

    # Caching
    CACHE_EMBEDDINGS: bool = True
    CACHE_TTL_SECONDS: int = 3600

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()