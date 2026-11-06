"""Interactive failures settle safely, keep tenant scope, and permit explicit retry."""
import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
import httpx
import pytest

from test_radix_passive import database as database, A, B
from test_radix_business_routes import Store, ROUTES, ENGINE, fixture, OTHER
import passive_routes
import egress


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['timeout', 'invalid-json', 'wrong-shape'])
async def test_watch_outage_never_enrolls_then_explicit_retry_succeeds(database, monkeypatch, failure):
    app = FastAPI(); app.state.pool = database.pool; passive_routes.attach(app)
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    await database.issue(A, 'owned.example')
    calls = []
    async def peer(request):
        calls.append(request)
        assert request.extensions['timeout']['read'] == 15
        if len(calls) == 1:
            if failure == 'timeout': raise httpx.ReadTimeout('placeholder-private-key', request=request)
            return httpx.Response(200, content=b'not-json' if failure == 'invalid-json' else b'[]')
        return httpx.Response(200, json={'ready': True})
    original = httpx.AsyncClient
    monkeypatch.setattr(passive_routes.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(peer), **kwargs))
    headers = {'X-Tank-Key': 'placeholder-room-key', 'X-Tervory-Tenant': str(A)}
    async with original(transport=httpx.ASGITransport(app), base_url='http://placeholder-room', headers=headers) as client:
        body = {'tenant_id': str(A), 'domain': 'owned.example', 'interval': 'daily', 'run_now': False}
        response = await client.post('/passive/watch', json=body)
        assert response.status_code == 503 and 'placeholder-private-key' not in response.text
        assert await database.watches(A) == [] and len(calls) == 1
        assert (await client.post('/passive/watch', json=body)).status_code == 200
        assert len(await database.watches(A)) == 1 and len(calls) == 2
        assert (await client.get('/passive/watches', params={'tenant_id': str(B)})).status_code == 403
        assert (await client.post('/passive/watch', json={**body, 'tenant_id': str(B)})).status_code == 403
        assert len(calls) == 2


@pytest.mark.asyncio
async def test_withdrawal_is_durable_even_when_gateway_fails_and_retry_is_safe(database, monkeypatch):
    app = FastAPI(); app.state.pool = database.pool; passive_routes.attach(app)
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    await database.issue(A, 'owned.example')
    await database.consent(A, 'owned.example', 'placeholder-user', 'placeholder written consent')
    calls = []
    async def peer(request):
        calls.append(request)
        if len(calls) == 1: raise httpx.ConnectTimeout('placeholder-private-key', request=request)
        return httpx.Response(200, json={'revoked': True})
    original = httpx.AsyncClient
    monkeypatch.setattr(passive_routes.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(peer), **kwargs))
    headers = {'X-Tank-Key': 'placeholder-room-key', 'X-Tervory-Tenant': str(A),
               'X-Tervory-Active-Authorized': 'true', 'X-Tervory-User': 'placeholder-user'}
    async with original(transport=httpx.ASGITransport(app), base_url='http://placeholder-room', headers=headers) as client:
        body = {'tenant_id': str(A), 'domain': 'owned.example'}
        response = await client.post('/passive/consent-withdraw', json=body)
        assert response.status_code == 503 and 'placeholder-private-key' not in response.text
        assert await database.consent_id(A, 'owned.example') is None and len(calls) == 1
        assert (await client.post('/passive/consent-withdraw', json=body)).status_code == 200
        assert await database.consent_id(A, 'owned.example') is None and len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('skill', sorted(ROUTES.SKILLS))
async def test_business_deadline_then_retry_persists_only_owned_result(monkeypatch, skill):
    app = FastAPI(); app.state.pool = Store()
    app.state.tank = SimpleNamespace(run_skill=AsyncMock(side_effect=TimeoutError('placeholder-private-key')))
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key'); monkeypatch.setenv('TANK_REGION', 'us-east')
    ROUTES.attach(app); body = fixture()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://placeholder-room',
                                 headers={'X-Tank-Key': 'placeholder-room-key'}) as client:
        response = await client.post('/verify/'+skill, json=body)
        assert response.status_code == 502 and 'placeholder-private-key' not in response.text
        assert app.state.pool.rows == {} and app.state.tank.run_skill.await_count == 1
        app.state.tank.run_skill.side_effect = lambda tenant, name, payload: ENGINE.analyse(skill, payload, tenant)
        response = await client.post('/verify/'+skill, json=body)
        assert response.status_code == 201, response.text
        result = response.json(); target = '/verify/runs/'+result['id']
        assert (await client.get(target, params={'tenant_id': body['tenant_id']})).json() == result
        assert (await client.get(target, params={'tenant_id': OTHER})).status_code == 404
        assert app.state.tank.run_skill.await_count == 2


def test_dns_deadline_refuses_without_dial_or_unbounded_retry(monkeypatch):
    release = threading.Event(); done = threading.Event(); calls = []; finished = []
    slots = egress.BOUNDS['max_concurrent']
    def stuck(*args, **kwargs):
        calls.append(args)
        try: release.wait(1); return []
        finally:
            finished.append(True)
            if len(finished) == slots: done.set()
    monkeypatch.setattr(egress.socket, 'getaddrinfo', stuck)
    monkeypatch.setattr(egress, 'DNS_SECONDS', 0.01)
    try:
        for attempt in range(slots + 1):
            with pytest.raises(egress.ProxyError, match='dns failed'):
                egress.system_resolve(egress.APPROVED_HOST)
            assert len(calls) == min(attempt + 1, slots)
    finally:
        release.set(); assert done.wait(1)


@pytest.mark.asyncio
async def test_stalled_business_call_is_cancelled_before_any_storage(monkeypatch):
    app = FastAPI(); app.state.pool = Store(); cancelled = []
    async def stalled(*args):
        try: await asyncio.Event().wait()
        finally: cancelled.append(True)
    app.state.tank = SimpleNamespace(run_skill=AsyncMock(side_effect=stalled))
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key'); monkeypatch.setenv('TANK_REGION', 'us-east')
    timeout = asyncio.timeout
    monkeypatch.setattr(ROUTES.asyncio, 'timeout', lambda seconds: timeout(0.01))
    ROUTES.attach(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://placeholder-room') as client:
        response = await client.post('/verify/business_risk', json=fixture(), headers={'X-Tank-Key': 'placeholder-room-key'})
    assert response.status_code == 502 and cancelled == [True]
    assert not app.state.pool.rows and app.state.tank.run_skill.await_count == 1
