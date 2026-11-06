from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID
import asyncio

import httpx
import pytest
from pydantic import ValidationError
from trigger import app as room
from trigger.voice import Voice, VoiceStore


@pytest.mark.asyncio
@pytest.mark.parametrize('route', ['/check', '/write', '/voice/show', '/skala/languagetool'])
@pytest.mark.parametrize('key', ['', 'placeholder-wrong'])
async def test_every_room_route_rejects_unauthenticated_before_io(monkeypatch, route, key):
    monkeypatch.setenv('TANK_KEY', 'placeholder-correct')
    monkeypatch.setattr(room.app.state, 'missing_settings', [], raising=False)
    pool = SimpleNamespace(fetchval=AsyncMock(), fetch=AsyncMock())
    monkeypatch.setattr(room.app.state, 'pool', pool, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app), base_url='http://room') as client:
        result = await client.post(route, headers={'x-tank-key': key}, json={'tenant_id': str(UUID(int=11)), 'text': 'Owned text'})
    assert result.status_code == 401
    pool.fetchval.assert_not_awaited()
    pool.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_tenant_and_extra_fields_refused_before_storage(monkeypatch):
    monkeypatch.setenv('TANK_KEY', 'placeholder-correct')
    monkeypatch.setattr(room.app.state, 'missing_settings', [], raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app), base_url='http://room') as client:
        result = await client.post('/write', headers={'x-tank-key':'placeholder-correct'},
            json={'tenant_id': 'invalid', 'text': 'Owned text', 'path':'../../outside'})
    assert result.status_code == 422


@pytest.mark.asyncio
async def test_voice_queries_are_bound_to_requested_tenant():
    pool = SimpleNamespace(fetchval=AsyncMock(return_value=None))
    store = VoiceStore(pool)
    for tenant in [UUID(int=11), UUID(int=12)]:
        assert await store.get(tenant) is None
        sql, bound = pool.fetchval.await_args.args
        assert 'WHERE tenant_id=$1' in sql and bound == tenant


@pytest.mark.parametrize('path', ['../../outside','/etc/passwd','govuk/../../outside'])
def test_stylebook_paths_cannot_escape_bundled_sources(path):
    with pytest.raises(ValidationError):
        Voice(status='live', revision=1, stylebook=path)


@pytest.mark.asyncio
async def test_unused_internal_documentation_routes_are_closed():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app), base_url='http://room') as client:
        for path in ('/docs', '/redoc', '/openapi.json'):
            assert (await client.get(path)).status_code == 404


@pytest.mark.asyncio
async def test_whole_room_deadline_includes_stalled_database(monkeypatch):
    async def stalled(*args):
        await asyncio.Event().wait()
    monkeypatch.setattr(room, 'REQUEST_TIMEOUT_SECONDS', .01)
    monkeypatch.setattr(room.app.state, 'missing_settings', [], raising=False)
    monkeypatch.setattr(room.app.state, 'pool', SimpleNamespace(fetchval=stalled), raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app), base_url='http://room') as client:
        response = await client.get('/health')
    assert response.status_code == 503
    assert 'outcome is unknown' in response.json()['detail']


@pytest.mark.asyncio
async def test_unexpected_error_is_plain_and_private_payload_not_logged(monkeypatch, caplog):
    monkeypatch.setattr(room.app.state, 'missing_settings', [], raising=False)
    monkeypatch.setattr(room.app.state, 'pool', SimpleNamespace(fetchval=AsyncMock(side_effect=RuntimeError('placeholder private credential'))), raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app), base_url='http://room') as client:
        response = await client.get('/health')
    assert response.status_code == 503
    assert 'Please try again' in response.text
    assert 'placeholder private credential' not in response.text + caplog.text


@pytest.mark.asyncio
async def test_response_completion_is_bounded_without_second_headers(monkeypatch):
    monkeypatch.setattr(room, 'REQUEST_TIMEOUT_SECONDS', .01)
    async def stream(scope, receive, send):
        await send({'type':'http.response.start', 'status':200, 'headers':[]})
        await asyncio.Event().wait()
    sent=[]
    async def send(message):
        sent.append(message)
    await room.RequestBoundary(stream)({'type':'http'}, None, send)
    assert [m['type'] for m in sent] == ['http.response.start', 'http.response.body']
    assert sent[-1]['more_body'] is False


@pytest.mark.asyncio
async def test_failure_after_completed_response_never_sends_twice(caplog):
    async def complete(scope, receive, send):
        await send({'type':'http.response.start', 'status':200, 'headers':[]})
        await send({'type':'http.response.body', 'body':b'{}'})
        raise RuntimeError('placeholder private credential')
    sent=[]
    async def send(message):
        sent.append(message)
    await room.RequestBoundary(complete)({'type':'http'}, None, send)
    assert len(sent)==2
    assert 'placeholder private credential' not in caplog.text
