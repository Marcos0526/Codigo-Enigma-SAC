"""Search regressions for API entry points and catalog column types."""

import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.api.main import app
from services.api.src.main import app as canonical_app
from services.api.src.database import get_db_session
from services.api.src.routes import search


def test_legacy_entry_point_uses_current_routes():
    assert app is canonical_app
    paths = {route.path for route in app.routes}
    assert '/api/v1/search' in paths
    assert '/api/v1/chat/completions' in paths


def test_search_http_response():
    async def database_session():
        yield None

    app.dependency_overrides[get_db_session] = database_session
    try:
        with patch.object(search, 'generate_embedding', AsyncMock(return_value=[1.0, 0.0, 0.0])), patch.object(
            search, 'vector_search', AsyncMock(return_value=[])
        ):
            client = TestClient(app)
            response = client.post('/api/v1/search', json={'query': 'temperature'})
            assert response.status_code == 200
            assert response.json()['status'] == 'no_matches'
            assert response.json()['datasets'] == []
            invalid = client.post('/api/v1/search', json={'query': ''})
            assert invalid.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db_session, None)


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
