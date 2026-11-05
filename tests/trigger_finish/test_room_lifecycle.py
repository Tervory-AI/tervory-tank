from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
import pytest

from trigger import app as room


@pytest.mark.asyncio
async def test_failed_schema_initialisation_closes_database(monkeypatch):
    pool = SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError('placeholder schema failure')),
                           close=AsyncMock())
    monkeypatch.setenv('DATABASE_URL', 'postgresql://placeholder/placeholder')
    monkeypatch.setattr(room.asyncpg, 'create_pool', AsyncMock(return_value=pool))
    http = Mock()
    monkeypatch.setattr(room.httpx, 'AsyncClient', http)
    app = FastAPI()
    with pytest.raises(RuntimeError, match='placeholder schema failure'):
        async with room.lifespan(app):
            pytest.fail('A failed schema must not start the application')
    pool.close.assert_awaited_once()
    assert app.state.pool is None
    http.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('fail', [False, True])
async def test_shutdown_closes_http_then_database_even_on_failure(monkeypatch, fail):
    closed = []
    async def close_pool():
        closed.append('database')
    async def close_http():
        closed.append('http')
    pool = SimpleNamespace(execute=AsyncMock(), close=close_pool)
    http = SimpleNamespace(aclose=close_http)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://placeholder/placeholder')
    monkeypatch.setattr(room.asyncpg, 'create_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr(room.httpx, 'AsyncClient', Mock(return_value=http))
    app = FastAPI()
    try:
        async with room.lifespan(app):
            assert app.state.pool is pool
            if fail:
                raise RuntimeError('placeholder shutdown')
    except RuntimeError:
        assert fail
    assert app.state.pool is None
    assert closed == ['http', 'database']
