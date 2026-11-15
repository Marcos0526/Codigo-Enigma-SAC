"""Verify provider request formats without calling paid external services."""

from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from services.search.src.embedding.http_client import embed_text


def config(provider='nvidia', key='test-key'):
    return SimpleNamespace(
        EMBEDDING_PROVIDER=provider,
        EMBEDDING_API_KEY=key,
        EMBEDDING_MODEL='nvidia/nemotron-3.5-embed-1b',
        EMBEDDING_DIMENSIONS=384,
        EMBEDDING_API_URL='http://localhost:8080/embed',
        NVIDIA_API_BASE_URL='https://integrate.api.nvidia.com/v1/',
    )


@pytest.mark.parametrize('input_type', ['query', 'passage'])
@pytest.mark.asyncio
async def test_nvidia_authenticated_asymmetric_request(input_type):
    import json

    def handler(request):
        assert str(request.url) == 'https://integrate.api.nvidia.com/v1/embeddings'
        assert request.headers['Authorization'] == 'Bearer test-key'
        payload = json.loads(request.content)
        assert payload['model'] == 'nvidia/nemotron-3.5-embed-1b'
        assert payload['input'] == ['combustion']
        assert payload['input_type'] == input_type
        assert payload['dimensions'] == 384
        return httpx.Response(200, json={'data': [{'embedding': [0.5] * 384}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch('services.search.src.embedding.http_client.httpx.AsyncClient', return_value=client):
        assert len(await embed_text('combustion', config(), input_type=input_type)) == 384


@pytest.mark.asyncio
async def test_missing_nvidia_key_fails_before_network_call():
    with pytest.raises(ValueError, match='EMBEDDING_API_KEY'):
        await embed_text('combustion', config(key=''), input_type='query')


@pytest.mark.asyncio
async def test_local_service_still_uses_texts_format():
    import json

    def handler(request):
        assert str(request.url) == 'http://localhost:8080/embed'
        assert json.loads(request.content) == {'texts': ['combustion']}
        assert 'Authorization' not in request.headers
        return httpx.Response(200, json={'embeddings': [[0.5] * 384]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch('services.search.src.embedding.http_client.httpx.AsyncClient', return_value=client):
        assert len(await embed_text('combustion', config('local', ''), input_type='query')) == 384


@pytest.mark.asyncio
async def test_incompatible_dimensions_are_rejected():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={'data': [{'embedding': [0.5] * 2048}]})
    )
    client = httpx.AsyncClient(transport=transport)
    with patch('services.search.src.embedding.http_client.httpx.AsyncClient', return_value=client):
        with pytest.raises(ValueError, match='dimensions'):
            await embed_text('combustion', config(), input_type='query')
