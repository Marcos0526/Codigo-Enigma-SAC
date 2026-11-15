"""Shared OpenAI-compatible LLM HTTP client with provider rate-limit retries."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict

import httpx
import structlog

from services.api.src.config import settings

logger = structlog.get_logger()

MAX_RETRIES = 3
MAX_RETRY_WAIT_SECONDS = 45.0


def _header_retry_seconds(response: httpx.Response) -> float | None:
    retry_after = response.headers.get("retry-after")
    if retry_after is None:
        return None
    try:
        return max(float(retry_after), 0.0)
    except ValueError:
        return None


def _body_retry_seconds(response: httpx.Response) -> float | None:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        return None

    candidates = [
        payload.get("retryAtMs"),
        payload.get("error", {}).get("retryAtMs")
        if isinstance(payload.get("error"), dict)
        else None,
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            remaining_ms = float(candidate) - time.time() * 1000
            return max(remaining_ms / 1000, 0.0)
        except (TypeError, ValueError):
            continue
    return None


def retry_wait_seconds(response: httpx.Response) -> float:
    """Return a bounded wait time from Retry-After or Groq's retryAtMs."""
    delay = _header_retry_seconds(response)
    if delay is None:
        delay = _body_retry_seconds(response)
    if delay is None:
        delay = 2.0
    return min(max(delay, 0.5), MAX_RETRY_WAIT_SECONDS)


async def post_chat_completion(payload: Dict[str, Any]) -> httpx.Response:
    """POST /chat/completions and retry transient 429 responses.

    Groq's free tier enforces per-minute token limits and rejects a request if
    the tokens already used plus the reserved max_tokens exceed the limit. The
    provider returns a precise retry time, so waiting once is usually enough.
    """
    base_url = settings.LLM_API_URL or "https://api.openai.com/v1"
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 429:
                response.raise_for_status()
                return response

            wait_seconds = retry_wait_seconds(response)
            logger.warning(
                "llm_rate_limited",
                attempt=attempt,
                max_attempts=MAX_RETRIES,
                wait_seconds=round(wait_seconds, 2),
                provider_response=response.text[:600],
            )
            if attempt == MAX_RETRIES:
                response.raise_for_status()
                return response
            await asyncio.sleep(wait_seconds)

    raise RuntimeError("LLM request exhausted retries without a response")
