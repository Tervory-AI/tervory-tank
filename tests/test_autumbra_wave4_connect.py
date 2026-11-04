"""Provider connect, post-write HTTPS health and real-adapter receipt contracts."""
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import autumbra_connect as connect
import command
import httpx
import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from test_autumbra_cloudflare_hand import TENANT


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['good', 'inactive', 'multi_zone', 'wrong_zone', 'transport'])
async def test_connect_checks_active_single_zone_without_writes(mode):
    calls = []
    def provider(request):
        calls.append(request)
        assert request.method == 'GET' and request.url.host == 'api.cloudflare.com'
        assert request.headers['Authorization'] == 'Bearer placeholder-token'
        if mode == 'transport':
            raise httpx.ConnectError('private provider detail', request=request)
        result = {'status': 'disabled' if mode == 'inactive' else 'active'}
        if request.url.path.endswith('/zones'):
            result = [{'id': 'a' * 32, 'name': 'wrong.example' if mode == 'wrong_zone' else 'tervory.com'}]
            if mode == 'multi_zone':
                result.append({'id': 'b' * 32, 'name': 'other.example'})
        return httpx.Response(200, json={'success': True, 'result': result})
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
        if mode == 'good':
            await connect.verify_cloudflare(client, 'placeholder-token', 'tervory.com', 'a' * 32)
            assert len(calls) == 2
        else:
            with pytest.raises(HTTPException) as caught:
                await connect.verify_cloudflare(client, 'placeholder-token', 'tervory.com', 'a' * 32)
            assert caught.value.status_code == 422
            assert 'private provider detail' not in caught.value.detail


@pytest.mark.asyncio
async def test_connect_saves_named_token_only_to_own_vault(monkeypatch):
    tenant = uuid.UUID(TENANT)
    authorized = AsyncMock(return_value=(tenant, 'ghost', 'placeholder-owner'))
    actor = SimpleNamespace(tenant_id=tenant, founder=False, tenant_admin=True)
    monkeypatch.setattr(command, 'identity', AsyncMock(side_effect=lambda request: actor))
    verified = AsyncMock()
    monkeypatch.setattr(connect, 'verify_cloudflare', verified)
    sealed = []
    def seal(value, aad):
        sealed.append((value, aad))
        return b'placeholder-ciphertext'
    monkeypatch.setattr(connect, 'seal', seal)
    saved = AsyncMock()
    async def body(request):
        return await request.json()
    app, router = FastAPI(), APIRouter()
    connect.register(router, SimpleNamespace(_http=object()), authorized, body, saved, JSONResponse)
    app.include_router(router)
    data = {'tenant_id': TENANT, 'name': 'CLOUDFLARE_EDGE', 'token': 'placeholder-token',
            'zone_name': 'tervory.com', 'zone_id': 'a' * 32, 'permissions': connect.PERMISSIONS,
            'specific_zone_only': True}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank') as client:
        response = await client.post('/ghost.vault/autumbra/connect/cloudflare', json=data)
        assert response.status_code == 200 and response.json()['name'] == data['name']
        assert 'placeholder-token' not in response.text
        args = saved.call_args.args
        assert args[:4] == (tenant, 'ghost.vault', 'secrets', data['name'])
        assert args[-1] == b'placeholder-ciphertext'
        assert sealed == [({'value': 'placeholder-token'}, f'plugins:v1:{tenant}:ghost.vault:secret:CLOUDFLARE_EDGE')]
        assert 'placeholder-token' not in json.dumps(args[4])
        actor.tenant_admin = False
        assert (await client.post('/ghost.vault/autumbra/connect/cloudflare', json=data)).status_code == 403
        actor.tenant_admin = True
        actor.tenant_id = uuid.UUID('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')
        assert (await client.post('/ghost.vault/autumbra/connect/cloudflare', json=data)).status_code == 403
        assert saved.await_count == 1
        assert authorized.await_count == 3




@pytest.mark.asyncio
async def test_real_vault_authorization_does_not_require_nonexistent_ghost_grant(monkeypatch):
    from vault_routes import build_router
    tenant = uuid.UUID(TENANT)
    actor = SimpleNamespace(tenant_id=tenant, founder=False, tenant_admin=True)
    monkeypatch.setattr(command, 'identity', AsyncMock(side_effect=lambda request: actor))
    tank = SimpleNamespace(TANK_API_KEY='placeholder-workspace-key', box_region=lambda: 'us-east', _http=object())
    # No DB save or provider call should run in these negative cases.
    monkeypatch.setattr(connect, 'verify_cloudflare', AsyncMock(side_effect=HTTPException(422, 'provider checked')))
    app = FastAPI()
    app.include_router(build_router(tank))
    headers = {'x-tank-key': 'placeholder-workspace-key', 'x-tervory-tenant': TENANT,
               'x-tervory-user': 'placeholder-user', 'x-tervory-squad': 'ghost'}
    data = {'tenant_id': TENANT, 'name': 'CLOUDFLARE_EDGE', 'token': 'placeholder-token',
            'zone_name': 'tervory.com', 'zone_id': 'a' * 32, 'permissions': connect.PERMISSIONS,
            'specific_zone_only': True}
    path = '/v1/vaults/ghost.vault/autumbra/connect/cloudflare'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank') as client:
        response = await client.post(path, json=data, headers=headers)
        assert response.status_code == 422 and response.json()['detail'] == 'provider checked'
        assert (await client.post(path, json=data)).status_code == 401
        actor.tenant_admin = False
        assert (await client.post(path, json=data, headers=headers)).status_code == 403
        actor.tenant_admin = True
        assert (await client.post(path, json=data, headers={**headers, 'x-tervory-tenant': str(uuid.uuid4())})).status_code == 403
        assert (await client.post(path, json=data, headers={**headers, 'x-tervory-home-region': 'za'})).status_code == 403


@pytest.mark.asyncio
async def test_google_connect_installs_only_nonsecret_stable_binding(monkeypatch):
    import ghost_routes
    tenant = uuid.UUID(TENANT)
    monkeypatch.setattr(command, 'identity', AsyncMock(return_value=SimpleNamespace(tenant_id=tenant, founder=False, tenant_admin=True)))
    monkeypatch.setattr(connect, 'seal', lambda value, aad: b'placeholder-sealed')
    corridor = AsyncMock(return_value=httpx.Response(200, json={'status': 'awaiting_verified_push'}))
    monkeypatch.setattr(ghost_routes, 'call_room', corridor)
    saved = AsyncMock()
    async def body(request):
        return await request.json()
    router, app = APIRouter(), FastAPI()
    connect.register(router, SimpleNamespace(_http=None), AsyncMock(return_value=(tenant, 'ghost', 'owner')), body, saved, JSONResponse)
    app.include_router(router)
    data = {'tenant_id': TENANT, 'audience': 'https://example.test/push',
            'service_account': 'push@project.iam.gserviceaccount.com',
            'subscription': 'projects/project/subscriptions/alerts', 'customer_id': 'C123'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank') as client:
        path = '/ghost.vault/autumbra/connect/google_workspace'
        first = await client.post(path, json=data)
        second = await client.post(path, json=data)
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert first.json()['status'] == 'awaiting_verified_push'
        sent = corridor.call_args.kwargs['body']
        assert set(sent) == {*data, 'connection_id'}
        assert sent['tenant_id'] == TENANT
        assert sent['connection_id'] == first.json()['connection_id']
        assert saved.call_args.args[:3] == (tenant, 'ghost.vault', 'secrets')
