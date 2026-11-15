"""Search regressions for API entry points and catalog column types."""

import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from services.api.main import app
from services.api.src.main import app as canonical_app
from services.api.src.database import get_db_session
from services.api.src.routes import local_data, search


def test_legacy_entry_point_uses_current_routes():
    assert app is canonical_app
    paths = {route.path for route in app.routes}
    assert '/api/v1/search' in paths
    assert '/api/v1/chat/completions' in paths


def test_search_http_response():
    rag = Mock()
    rag.search.return_value = ([], [])
    with patch.object(local_data, 'get_rag', return_value=rag):
        client = TestClient(app)
        response = client.post('/api/v1/search', json={'query': 'temperature'})
        assert response.status_code == 200
        assert response.json()['status'] == 'no_matches'
        assert response.json()['datasets'] == []
        assert response.json()['searchMetadata']['source'] == 'data/psi_databases'
        invalid = client.post('/api/v1/search', json={'query': ''})
        assert invalid.status_code == 422


def test_chat_uses_local_rag_without_llm_key():
    rag = Mock()
    rag.retrieve.return_value = [{
        'content': 'PSI-20 BRE temperature metadata',
        'metadata': {'source': 'PSI-20/19056A2_data.csv'},
        'score': 0.8,
    }]
    with patch.object(local_data, 'get_rag', return_value=rag), patch.object(
        local_data.settings, 'LLM_API_KEY', ''
    ):
        response = TestClient(app).post('/api/v1/chat/completions', json={
            'messages': [{'role': 'user', 'content': 'What temperature data is available?'}]
        })
    assert response.status_code == 200
    content = response.json()['choices'][0]['message']['content']
    assert 'local NASA PSI RAG' in content
    assert 'PSI-20/19056A2_data.csv' in content
    rag.retrieve.assert_called_once()


def test_chat_with_llm_grounds_the_prompt_and_appends_sources():
    from services.api.src.routes.chat import (
        ChatChoice,
        ChatCompletionResponse,
        ChatMessage,
    )

    rag = Mock()
    rag.retrieve.return_value = [{
        'content': 'PSI-20 BRE temperature metadata',
        'metadata': {'source': 'PSI-20/19056A2_data.csv'},
        'score': 0.8,
    }]
    expected = ChatCompletionResponse(
        id='llm-1',
        created=1,
        model='test-model',
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(role='assistant', content='Grounded answer [1]'),
                finish_reason='stop',
            )
        ],
        usage={'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
    )
    captured = {}

    async def fake_completion(request):
        captured['request'] = request
        return expected

    with patch.object(local_data, 'get_rag', return_value=rag), patch.object(
        local_data.settings, 'LLM_API_KEY', 'test-key'
    ), patch.object(
        local_data, 'legacy_chat_completions', side_effect=fake_completion
    ):
        response = TestClient(app).post('/api/v1/chat/completions', json={
            'messages': [
                {'role': 'system', 'content': 'Selected dataset: 19056A2 data'},
                {'role': 'user', 'content': 'What temperature data is available?'},
            ]
        })

    assert response.status_code == 200
    content = response.json()['choices'][0]['message']['content']
    assert content.startswith('Grounded answer [1]')
    assert 'Local NASA PSI sources:' in content
    assert 'PSI-20/19056A2_data.csv' in content

    messages = captured['request'].messages
    assert messages[0].role == 'system'
    assert 'RETRIEVED LOCAL NASA PSI CONTEXT' in messages[0].content
    assert 'PSI-20/19056A2_data.csv' in messages[0].content
    assert 'cosine 0.800' in messages[0].content
    assert 'Selected dataset: 19056A2 data' in messages[0].content
    assert [message.role for message in messages[1:]] == ['user']


def test_chat_falls_back_to_retrieval_when_llm_fails():
    rag = Mock()
    rag.retrieve.return_value = [{
        'content': 'PSI-21 soot metadata',
        'metadata': {'source': 'PSI-21/17319A3_data.csv'},
        'score': 0.7,
    }]
    with patch.object(local_data, 'get_rag', return_value=rag), patch.object(
        local_data.settings, 'LLM_API_KEY', 'test-key'
    ), patch.object(
        local_data, 'legacy_chat_completions', AsyncMock(side_effect=RuntimeError('boom'))
    ):
        response = TestClient(app).post('/api/v1/chat/completions', json={
            'messages': [{'role': 'user', 'content': 'What soot data is available?'}]
        })

    assert response.status_code == 200
    content = response.json()['choices'][0]['message']['content']
    assert 'LLM could not be reached' in content
    assert 'PSI-21/17319A3_data.csv' in content


@pytest.mark.parametrize('origin', ['http://localhost:3000', 'http://127.0.0.1:3000'])
def test_browser_search_preflight(origin):
    response = TestClient(app).options(
        '/api/v1/search',
        headers={
            'Origin': origin,
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type',
        },
    )
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == origin


@pytest.mark.parametrize('column_type', ['TEXT[]', 'JSONB'])
@pytest.mark.asyncio
async def test_search_with_catalog_column_types(column_type):
    """Exercise actual pgvector SQL without changing persistent catalog data."""
    database_url = os.getenv('TEST_DATABASE_URL')
    if not database_url:
        pytest.skip('Set TEST_DATABASE_URL to run PostgreSQL regression tests')

    import asyncpg

    conn = await asyncpg.connect(database_url)
    transaction = conn.transaction()
    await transaction.start()
    try:
        await conn.execute(f'''
            CREATE TEMP TABLE datasets (
                id TEXT, dataset_id TEXT, psi_id TEXT, name TEXT,
                description TEXT, url TEXT, format TEXT,
                numeric_columns {column_type}, verification_status TEXT
            ) ON COMMIT DROP
        ''')
        await conn.execute('''
            CREATE TEMP TABLE dataset_embeddings (
                dataset_id TEXT, embedding vector(3)
            ) ON COMMIT DROP
        ''')
        await conn.execute('''
            CREATE TEMP TABLE psi_investigations (
                psi_id TEXT, title TEXT
            ) ON COMMIT DROP
        ''')
        columns = "'{temperature}'::text[]" if column_type == 'TEXT[]' else "'[\"temperature\"]'::jsonb"
        empty = "'{}'::text[]" if column_type == 'TEXT[]' else "'[]'::jsonb"
        await conn.execute(f'''
            INSERT INTO datasets VALUES
                ('1', 'test-temperature', 'PSI-20', 'Temperature', NULL,
                 'https://example.org/data.csv', 'csv', {columns}, 'verified'),
                ('2', 'test-empty', 'PSI-20', 'Empty', NULL,
                 'https://example.org/empty.csv', 'csv', {empty}, 'verified'),
                ('3', 'test-unverified', 'PSI-20', 'Unverified', NULL,
                 'https://example.org/unverified.csv', 'csv', {columns}, 'unknown');
            INSERT INTO psi_investigations VALUES ('PSI-20', 'Combustion');
            INSERT INTO dataset_embeddings VALUES
                ('1', '[1,0,0]'), ('2', '[1,0,0]'), ('3', '[1,0,0]')
        ''')

        @asynccontextmanager
        async def database_context():
            yield conn

        with patch('services.api.src.database.get_db_context', database_context), patch.object(
            search, 'generate_embedding', AsyncMock(return_value=[1.0, 0.0, 0.0])
        ):
            result = await search.search_datasets(
                search.SearchRequest(query='temperature', filters={'psiIds': ['PSI-20']}),
                db=None,
            )
            assert result.total_matches == 1
            assert result.datasets[0].id == 'test-temperature'
            assert result.datasets[0].numericColumns == ['temperature']
            assert result.datasets[0].description == ''
            assert result.datasets[0].score == 1.0

            no_matches = await search.search_datasets(
                search.SearchRequest(query='temperature', filters={'psiIds': ['PSI-99']}),
                db=None,
            )
            assert no_matches.status == 'no_matches'
            assert no_matches.total_matches == 0
            assert no_matches.datasets == []
    finally:
        await transaction.rollback()
        await conn.close()
