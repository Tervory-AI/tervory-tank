"""Finite network work, transport identity, input scope and log redaction."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from agents.tisan import builder, upstream, promotion


@pytest.mark.asyncio
@pytest.mark.parametrize('first', ['timeout', 429, 502, 503, 504])
async def test_safe_reads_retry_once_and_keep_timeouts_and_redirects_explicit(first):
    calls = []
    async def respond(request):
        calls.append(request)
        assert request.extensions['timeout']['read'] == 0.5
        if len(calls) == 1:
            if first == 'timeout':
                raise httpx.ReadTimeout('placeholder private provider text')
            return httpx.Response(first, json={'detail': 'placeholder private provider text'})
        return httpx.Response(200, json={'ok': True})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await upstream.get(client, 'https://placeholder-provider.invalid/data', timeout=0.5)
    assert result.json() == {'ok': True} and len(calls) == upstream.READ_ATTEMPTS == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
async def test_uncertain_writes_are_not_retried_and_do_not_expose_provider_text(method, caplog):
    calls = []
    def respond(request):
        calls.append(request)
        raise httpx.ReadTimeout('placeholder private provider text')
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(upstream.Unavailable, match='^External service unavailable$'):
            await upstream.request(client, method, 'https://placeholder-provider.invalid/write')
    assert len(calls) == upstream.WRITE_ATTEMPTS == 1
    assert 'placeholder private provider text' not in caplog.text


@pytest.mark.asyncio
async def test_slow_stream_has_a_whole_request_deadline_and_finite_attempts():
    calls = []
    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                await asyncio.sleep(0.01)
                yield b' '
    def respond(request):
        calls.append(request)
        return httpx.Response(200, stream=Slow())
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(upstream.Unavailable):
            await asyncio.wait_for(upstream.get(client, 'https://placeholder-provider.invalid/data', timeout=0.04), 1)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_redirects_are_never_followed_and_unavailable_reads_end_after_two_attempts():
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(302, headers={'location': 'https://placeholder-foreign.invalid/'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond), follow_redirects=True) as client:
        assert (await upstream.get(client, 'https://placeholder-provider.invalid/data')).status_code == 302
    assert len(calls) == 1
    calls.clear()
    def unavailable(request):
        calls.append(request)
        raise httpx.ConnectError('placeholder private failure')
    async with httpx.AsyncClient(transport=httpx.MockTransport(unavailable)) as client:
        with pytest.raises(upstream.Unavailable, match='^External service unavailable$'):
            await upstream.get(client, 'https://placeholder-provider.invalid/data')
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_coolify_writes_keep_the_existing_unknown_outcome_without_retry():
    calls = []
    def respond(request):
        calls.append(request)
        raise httpx.ReadTimeout('placeholder private upstream error')
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        api = promotion.Coolify(client, 'https://placeholder-coolify.invalid', 'placeholder')
        with pytest.raises(promotion.CoolifyUnknown, match='^Coolify mutation outcome unknown$'):
            await api.call('POST', '/deploy', mutation=True, json={'uuid': 'placeholder-stage'})
    assert len(calls) == 1


@pytest.mark.parametrize('path,method', [('/jobs','POST'), ('/jobs/'+str(uuid4()),'GET'),
    ('/evals/run','POST'), ('/gold/pages','GET'), ('/gold/approve','POST'), ('/gold/candidates','GET'),
    ('/pipeline/start','POST'), ('/quotes','POST'), ('/publish/build','POST'), ('/promotion/promote','POST'),
    ('/storage/usage','GET'), ('/openapi.json','GET')])
def test_actual_room_private_routes_require_a_transport_key_before_work(monkeypatch, caplog, path, method):
    from agents.tisan import app as room
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    client = TestClient(room.app)
    try:
        for headers in ({}, {'X-Tank-Key':'placeholder-wrong', 'X-Tervory-Admin':'placeholder-founder'},
                        [('X-Tank-Key','placeholder-room-key'),('X-Tank-Key','placeholder-wrong')]):
            result = client.request(method, path, headers=headers, json={})
            assert result.status_code == 401
            assert result.json() == {'detail': 'room key required'}
    finally:
        client.close()
    assert 'placeholder-room-key' not in caplog.text and 'placeholder-wrong' not in caplog.text


@pytest.mark.parametrize('mode', ['body', 'query', 'duplicate-query', 'duplicate-header', 'invalid'])
def test_forwarded_tenant_claim_cannot_be_replaced_by_route_input(monkeypatch, mode):
    from agents.tisan import app as room
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    owner, foreign = str(uuid4()), str(uuid4())
    headers = [('X-Tank-Key','placeholder-room-key'), ('X-Tervory-Tenant',owner)]
    params = []
    payload = {'tenant_id': owner, 'kind':'ping', 'input':{}}
    if mode == 'body': payload['tenant_id'] = foreign
    elif mode == 'query': params = [('tenant_id',foreign)]
    elif mode == 'duplicate-query': params = [('tenant_id',owner),('tenant_id',foreign)]
    elif mode == 'duplicate-header': headers.append(('X-Tervory-Tenant',foreign))
    else: headers[1] = ('X-Tervory-Tenant','placeholder-invalid')
    result = TestClient(room.app).post('/jobs', headers=headers, params=params, json=payload)
    assert result.status_code == (422 if mode == 'invalid' else 404)
    assert result.json()['detail'] in {'not found', 'A workspace is required.'}


@pytest.mark.asyncio
async def test_plan_error_and_memory_error_never_copy_provider_details_into_receipts(monkeypatch, caplog):
    tank = SimpleNamespace(route=AsyncMock(return_value={'content': 'placeholder private upstream invalid json'}))
    with pytest.raises(ValueError) as failure:
        await builder.make_plan({'request':'placeholder brief'}, str(uuid4()), {}, tank)
    assert str(failure.value) == 'invalid plan after retry' and tank.route.await_count == 2
    monkeypatch.setattr(builder, 'execute', AsyncMock(return_value={'ok': False, 'checks': []}))
    context = SimpleNamespace(input={},tenant_id=str(uuid4()),job_id=str(uuid4()),tank=None,
        memory=SimpleNamespace(remember=AsyncMock(return_value={'id':'placeholder private invalid identifier'})))
    result = await builder.handle(context)
    assert 'memory_id' not in result
    assert 'placeholder private' not in json.dumps(result) + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize('seen', [-1, True, 'placeholder private provider text'])
async def test_heartbeat_does_not_present_unvalidated_provider_data_as_a_count(seen, caplog):
    from agents.tisan import app as room
    context = SimpleNamespace(agent='tisan',tenant_id=str(uuid4()),input={'heartbeat':True},
        memory=SimpleNamespace(remember=AsyncMock(return_value={'seen':seen})))
    result = await room.ping(context)
    assert result['memory'] == 'unreachable' and 'heartbeats_seen' not in result
    assert 'placeholder private provider text' not in caplog.text
