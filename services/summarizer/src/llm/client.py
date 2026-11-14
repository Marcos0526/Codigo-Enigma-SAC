"""LLM client for generating summaries."""

import structlog
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from services.summarizer.src.config import settings

logger = structlog.get_logger()


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    tokens_used: int
    model: str
    provider: str


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """Generate completion."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if client is healthy."""
        pass


class OpenAIClient(LLMClient):
    """OpenAI API client."""

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
        timeout: float = None,
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        self.temperature = temperature or settings.LLM_TEMPERATURE
        self.timeout = timeout or settings.LLM_TIMEOUT
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={"Authorization": f"Bearer {self.api_key}"},
                base_url="https://api.openai.com/v1",
            )
        return self._client

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """Generate completion using OpenAI API."""
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            model=self.model,
            provider="openai",
        )

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            result = await self.generate("test", "You are a helpful assistant.")
            return len(result.content) > 0
        except Exception as e:
            logger.error("openai_health_check_failed", error=str(e))
            return False

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class AnthropicClient(LLMClient):
    """Anthropic API client."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-3-opus-20240229",
        max_tokens: int = None,
        temperature: float = None,
        timeout: float = None,
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model
        self.max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        self.temperature = temperature or settings.LLM_TEMPERATURE
        self.timeout = timeout or settings.LLM_TIMEOUT
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                base_url="https://api.anthropic.com/v1",
            )
        return self._client

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """Generate completion using Anthropic API."""
        client = self._get_client()

        response = await client.post(
            "/messages",
            json={
                "model": self.model,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["content"][0]["text"],
            tokens_used=data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0),
            model=self.model,
            provider="anthropic",
        )

    async def health_check(self) -> bool:
        """Check if Anthropic API is accessible."""
        try:
            result = await self.generate("test", "You are a helpful assistant.")
            return len(result.content) > 0
        except Exception as e:
            logger.error("anthropic_health_check_failed", error=str(e))
            return False


class OllamaClient(LLMClient):
    """Ollama local LLM client."""

    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
        timeout: float = None,
    ):
        self.base_url = base_url or settings.LLM_API_URL or "http://localhost:11434"
        self.model = model or settings.LLM_MODEL
        self.max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        self.temperature = temperature or settings.LLM_TEMPERATURE
        self.timeout = timeout or settings.LLM_TIMEOUT
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                base_url=self.base_url,
            )
        return self._client

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """Generate completion using Ollama API."""
        client = self._get_client()

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        response = await client.post(
            "/api/generate",
            json={
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                },
            },
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data.get("response", ""),
            tokens_used=0,  # Ollama doesn't return token count
            model=self.model,
            provider="ollama",
        )

    async def health_check(self) -> bool:
        """Check if Ollama is accessible."""
        try:
            result = await self.generate("test", "You are a helpful assistant.")
            return len(result.content) > 0
        except Exception as e:
            logger.error("ollama_health_check_failed", error=str(e))
            return False


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.responses = responses or {}
        self.call_count = 0

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """Return mock response."""
        self.call_count += 1

        # Check for specific prompt patterns
        for pattern, response in self.responses.items():
            if pattern in prompt:
                return LLMResponse(
                    content=response,
                    tokens_used=100,
                    model="mock",
                    provider="mock",
                )

        # Default response
        return LLMResponse(
            content="Mock summary generated for dataset.",
            tokens_used=100,
            model="mock",
            provider="mock",
        )

    async def health_check(self) -> bool:
        return True


def get_llm_client() -> LLMClient:
    """Get configured LLM client."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        if not settings.LLM_API_KEY:
            raise ValueError("OpenAI API key required but not configured")
        return OpenAIClient()
    elif provider == "anthropic":
        if not settings.LLM_API_KEY:
            raise ValueError("Anthropic API key required but not configured")
        return AnthropicClient()
    elif provider == "ollama":
        return OllamaClient()
    elif provider == "local":
        # Use Ollama as local
        return OllamaClient()
    else:
        # Default to mock for testing
        logger.warning("unknown_llm_provider_using_mock", provider=provider)
        return MockLLMClient()


async def initialize_llm_client() -> LLMClient:
    """Initialize and verify LLM client."""
    client = get_llm_client()
    healthy = await client.health_check()
    if not healthy:
        logger.warning("llm_client_health_check_failed")
    return client