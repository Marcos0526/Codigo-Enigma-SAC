"""Tests for the shared OpenAI-compatible LLM retry logic."""

import time

import httpx

from services.api.src.routes.llm_client import MAX_RETRY_WAIT_SECONDS, retry_wait_seconds


def _response(headers=None, json_body=None):
    return httpx.Response(
        429,
        headers=headers or {},
        json=json_body,
        request=httpx.Request("POST", "https://example.test/chat/completions"),
    )


def test_retry_wait_uses_retry_after_header():
    assert retry_wait_seconds(_response(headers={"retry-after": "7"})) == 7.0


def test_retry_wait_uses_groq_retry_at_ms():
    retry_at_ms = (time.time() + 30) * 1000
    wait = retry_wait_seconds(
        _response(json_body={"error": {"retryAtMs": retry_at_ms}})
    )
    assert 29 <= wait <= 30


def test_retry_wait_is_bounded_and_has_default():
    far_future = (time.time() + 120) * 1000
    assert retry_wait_seconds(_response(json_body={"retryAtMs": far_future})) == MAX_RETRY_WAIT_SECONDS
    assert retry_wait_seconds(_response()) == 2.0
