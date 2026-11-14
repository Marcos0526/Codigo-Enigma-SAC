"""Embedding service for generating vector embeddings."""

import hashlib
import structlog
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

import httpx
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential

from services.search.src.config import settings

logger = structlog.get_logger()


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    embeddings: List[List[float]]
    model: str
    version: str
    dimensions: int
    token_count: int = 0


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings for a list of texts."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is healthy."""
        pass


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embedding provider using sentence-transformers."""

    def __init__(
        self,
        model_name: str = None,
        device: str = None,
        batch_size: int = None,
        max_length: int = None,
    ):
        self.model_name = model_name or settings.LOCAL_EMBEDDING_MODEL
        self.device = device or settings.LOCAL_EMBEDDING_DEVICE
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self.max_length = max_length or settings.EMBEDDING_MAX_LENGTH
        self._model = None
        self._model_version = "1.0.0"

    def _load_model(self):
        """Lazy load the sentence transformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("loading_embedding_model", model=self.model_name, device=self.device)
            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._model.max_seq_length = self.max_length

    async def embed(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings using local model."""
        self._load_model()

        # Process in batches
        all_embeddings = []
        total_tokens = 0

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            # Run in thread pool to avoid blocking
            import asyncio
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self._model.encode(batch, convert_to_numpy=True, normalize_embeddings=True)
            )
            all_embeddings.extend(embeddings.tolist())
            total_tokens += sum(len(t.split()) for t in batch)

        return EmbeddingResult(
            embeddings=all_embeddings,
            model=self.model_name,
            version=self._model_version,
            dimensions=len(all_embeddings[0]) if all_embeddings else 0,
            token_count=total_tokens,
        )

    async def health_check(self) -> bool:
        """Check if local model is loaded and working."""
        try:
            self._load_model()
            test_embedding = self._model.encode(["test"], convert_to_numpy=True)
            return test_embedding.shape[1] == settings.EMBEDDING_DIMENSIONS
        except Exception as e:
            logger.error("local_embedding_health_check_failed", error=str(e))
            return False


class RemoteEmbeddingProvider(EmbeddingProvider):
    """Remote embedding provider (HTTP API)."""

    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        model: str = None,
        version: str = None,
        dimensions: int = None,
    ):
        self.api_url = api_url or settings.EMBEDDING_API_URL
        self.api_key = api_key or settings.EMBEDDING_API_KEY
        self.model = model or settings.EMBEDDING_MODEL
        self.version = version or settings.EMBEDDING_VERSION
        self.dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.EMBEDDING_TIMEOUT),
                headers=headers,
            )
        return self._client

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def embed(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings via remote API."""
        client = self._get_client()

        response = await client.post(
            self.api_url,
            json={"texts": texts},
        )
        response.raise_for_status()
        data = response.json()

        embeddings = data.get("embeddings", [])
        if not embeddings:
            raise ValueError("No embeddings returned from API")

        return EmbeddingResult(
            embeddings=embeddings,
            model=self.model,
            version=self.version,
            dimensions=self.dimensions,
            token_count=data.get("token_count", 0),
        )

    async def health_check(self) -> bool:
        """Check if remote API is healthy."""
        try:
            client = self._get_client()
            # Try a simple embedding
            response = await client.post(
                self.api_url,
                json={"texts": ["health check"]},
            )
            return response.status_code == 200
        except Exception as e:
            logger.error("remote_embedding_health_check_failed", error=str(e))
            return False

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimensions: int = 1536):
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.EMBEDDING_TIMEOUT),
                headers={"Authorization": f"Bearer {self.api_key}"},
                base_url="https://api.openai.com/v1",
            )
        return self._client

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def embed(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings via OpenAI API."""
        client = self._get_client()

        response = await client.post(
            "/embeddings",
            json={
                "input": texts,
                "model": self.model,
                "dimensions": self.dimensions if "text-embedding-3" in self.model else None,
            },
        )
        response.raise_for_status()
        data = response.json()

        embeddings = [item["embedding"] for item in data["data"]]

        return EmbeddingResult(
            embeddings=embeddings,
            model=self.model,
            version="1.0.0",
            dimensions=self.dimensions,
            token_count=data.get("usage", {}).get("total_tokens", 0),
        )

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            result = await self.embed(["health check"])
            return len(result.embeddings) > 0
        except Exception as e:
            logger.error("openai_embedding_health_check_failed", error=str(e))
            return False


class NVIDIAEmbeddingProvider(EmbeddingProvider):
    """NVIDIA embedding provider (OpenAI-compatible API)."""

    def __init__(
        self,
        api_key: str,
        model: str = "nvidia/nv-embedqa-e5-v5",
        dimensions: int = 1024,
        base_url: str = None,
    ):
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.base_url = base_url or settings.NVIDIA_API_BASE_URL
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.EMBEDDING_TIMEOUT),
                headers={"Authorization": f"Bearer {self.api_key}"},
                base_url=self.base_url,
            )
        return self._client

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def embed(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings via NVIDIA API (OpenAI-compatible)."""
        client = self._get_client()

        response = await client.post(
            "/embeddings",
            json={
                "input": texts,
                "model": self.model,
                "dimensions": self.dimensions,
            },
        )
        response.raise_for_status()
        data = response.json()

        embeddings = [item["embedding"] for item in data["data"]]

        return EmbeddingResult(
            embeddings=embeddings,
            model=self.model,
            version="1.0.0",
            dimensions=self.dimensions,
            token_count=data.get("usage", {}).get("total_tokens", 0),
        )

    async def health_check(self) -> bool:
        """Check if NVIDIA API is accessible."""
        try:
            result = await self.embed(["health check"])
            return len(result.embeddings) > 0
        except Exception as e:
            logger.error("nvidia_embedding_health_check_failed", error=str(e))
            return False

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class EmbeddingService:
    """Main embedding service with provider management and caching."""

    def __init__(self):
        self.provider: Optional[EmbeddingProvider] = None
        self._cache: Dict[str, List[float]] = {}
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the configured embedding provider."""
        provider_type = settings.EMBEDDING_PROVIDER.lower()

        if provider_type == "local":
            self.provider = LocalEmbeddingProvider()
        elif provider_type == "remote":
            self.provider = RemoteEmbeddingProvider()
        elif provider_type == "openai":
            if not settings.EMBEDDING_API_KEY:
                raise ValueError("OpenAI API key required for OpenAI provider")
            self.provider = OpenAIEmbeddingProvider(
                api_key=settings.EMBEDDING_API_KEY,
                model=settings.EMBEDDING_MODEL,
                dimensions=settings.EMBEDDING_DIMENSIONS,
            )
        elif provider_type == "nvidia":
            if not settings.EMBEDDING_API_KEY:
                raise ValueError("NVIDIA API key required for NVIDIA provider")
            self.provider = NVIDIAEmbeddingProvider(
                api_key=settings.EMBEDDING_API_KEY,
                model=settings.EMBEDDING_MODEL,
                dimensions=settings.EMBEDDING_DIMENSIONS,
                base_url=settings.NVIDIA_API_BASE_URL,
            )
        else:
            raise ValueError(f"Unknown embedding provider: {provider_type}")

        logger.info("embedding_provider_initialized", provider=provider_type, model=settings.EMBEDDING_MODEL)

    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    async def embed(self, texts: List[str], use_cache: bool = True) -> EmbeddingResult:
        """Generate embeddings with optional caching."""
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                model=settings.EMBEDDING_MODEL,
                version=settings.EMBEDDING_VERSION,
                dimensions=settings.EMBEDDING_DIMENSIONS,
            )

        # Check cache
        if use_cache and settings.CACHE_EMBEDDINGS:
            cached_results = []
            uncached_texts = []
            uncached_indices = []

            for i, text in enumerate(texts):
                key = self._cache_key(text)
                if key in self._cache:
                    cached_results.append((i, self._cache[key]))
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)

            if not uncached_texts:
                # All cached
                embeddings = [None] * len(texts)
                for idx, emb in cached_results:
                    embeddings[idx] = emb
                return EmbeddingResult(
                    embeddings=embeddings,
                    model=settings.EMBEDDING_MODEL,
                    version=settings.EMBEDDING_VERSION,
                    dimensions=settings.EMBEDDING_DIMENSIONS,
                )

            # Generate embeddings for uncached texts
            result = await self.provider.embed(uncached_texts)

            # Update cache
            for text, embedding in zip(uncached_texts, result.embeddings):
                key = self._cache_key(text)
                self._cache[key] = embedding

            # Merge cached and new results
            final_embeddings = [None] * len(texts)
            for idx, emb in cached_results:
                final_embeddings[idx] = emb
            for idx, emb in zip(uncached_indices, result.embeddings):
                final_embeddings[idx] = emb

            return EmbeddingResult(
                embeddings=final_embeddings,
                model=result.model,
                version=result.version,
                dimensions=result.dimensions,
                token_count=result.token_count,
            )
        else:
            return await self.provider.embed(texts)

    async def embed_single(self, text: str, use_cache: bool = True) -> List[float]:
        """Generate embedding for a single text."""
        result = await self.embed([text], use_cache=use_cache)
        return result.embeddings[0] if result.embeddings else []

    async def health_check(self) -> bool:
        """Check embedding service health."""
        if self.provider:
            return await self.provider.health_check()
        return False

    def clear_cache(self):
        """Clear embedding cache."""
        self._cache.clear()
        logger.info("embedding_cache_cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": "unlimited",
        }


# Global service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def initialize_embedding_service() -> EmbeddingService:
    """Initialize and verify embedding service."""
    service = get_embedding_service()
    healthy = await service.health_check()
    if not healthy:
        logger.warning("embedding_service_health_check_failed")
    return service