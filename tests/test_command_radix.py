"""Founder passive tools use Confirm and the existing tenant-bound corridor."""
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import command
import radix_passive_routes as corridor
from test_command import TENANT, OTHER, runtime, command_pool, api

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agents/radix'))
from passive_store import artifact_id, target_url

CASES = [
    ('radix.domain.prove', {'domain': 'owned.example'}),
    ('radix.passive.scan', {'url': 'https://owned.example/', 'commit': 'a' * 40}),
    ('radix.findings', {'scan_id': '11111111-1111-4111-8111-111111111111'}),
]


@pytest.mark.parametrize('tool,args', CASES)
def test_founder_only_and_bound_arguments(runtime, tool, args):
    for founder, user in [(False, 'client'), (True, 'founder')]:
        actor = command.Actor(TENANT, user, founder, frozenset({'radix'}))
        action = command.PlannedAction(tool=tool, arguments=args)
        if not founder:
            with pytest.raises(HTTPException) as error:
                command.adapter_request(action, actor)
            assert error.value.status_code == 403
            assert tool not in command.allowed_tools(actor)
            continue
        method, path, params, body = command.adapter_request(action, actor)
        assert (body or params)['tenant_id'] == str(TENANT)
        if tool == 'radix.passive.scan':
            assert body == {'tenant_id': str(TENANT), 'target': args['url'], 'artifact': 'commit:' + args['commit']}
        for injected in ('tenant_id', 'user_id', 'region', 'artifact'):
            with pytest.raises(HTTPException):
                command.validate_action(command.PlannedAction(tool=tool, arguments={**args, injected: str(OTHER)}), actor)


@pytest.mark.parametrize('tool,args', CASES)
@pytest.mark.asyncio
async def test_confirm_dispatch_and_tenant_binding(api, runtime, monkeypatch, tool, args):
    client, pool = api
    runtime.app = FastAPI()
    runtime.pool = lambda: pool
    calls = []

    async def room(request):
        payload = json.loads(request.content) if request.method == 'POST' else dict(request.url.params)
        assert payload['tenant_id'] == request.headers['x-tervory-tenant'] == str(TENANT)
        calls.append((request.url.path, payload))
        if request.url.path.endswith('/domains'):
            return httpx.Response(201, json={'tenant_id': str(TENANT), 'domain': 'owned.example',
                'name': '_tervory-verify.owned.example', 'value': 'public-txt-proof', 'expires_at': '2030-01-01T00:00:00+00:00'})
        if request.url.path.endswith('/findings'):
            return httpx.Response(200, json={'findings': []})
        return httpx.Response(200, json={'scan_id': CASES[2][1]['scan_id'], 'findings': []})

    monkeypatch.setenv('TANK_KEY_RADIX', 'offline-radix-test')
    async with httpx.AsyncClient(transport=httpx.MockTransport(room)) as room_http:
        runtime._http = room_http
        runtime.app.include_router(corridor.build_router(runtime))
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'radix','founder')", TENANT)
        thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
        proposed = await client.post(f'/v1/command/threads/{thread}/actions', json={'tool': tool, 'arguments': args})
        assert proposed.status_code == 200, proposed.text
        card = proposed.json()
        assert card['status'] == 'pending' and calls == []
        path = f"/v1/command/cards/{card['card_id']}"
        assert (await client.post(path, json={'action': 'confirm'}, headers={'x-tervory-tenant': str(OTHER)})).status_code == 404
        assert (await client.post(path, json={'action': 'confirm'}, headers={'x-tervory-user': 'client'})).status_code == 404
        confirmed = await client.post(path, json={'action': 'confirm'})
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()['status'] == 'confirmed', confirmed.text
        assert len(calls) == 1
        await client.post(path, json={'action': 'confirm'})
        assert len(calls) == 1
        result = confirmed.json()['result']
        if tool == 'radix.domain.prove':
            assert set(result) == {'name', 'value', 'expires_at'}
        elif tool == 'radix.passive.scan':
            assert result == {'scan_id': CASES[2][1]['scan_id']}
        else:
            assert result == {'findings': []}


@pytest.mark.parametrize('commit', [None, '', 'a' * 39, 'g' * 40, 'commit:' + 'a' * 40])
@pytest.mark.asyncio
async def test_missing_invalid_commit_uses_existing_artifact_validator(runtime, monkeypatch, commit):
    actor = command.Actor(TENANT, 'founder', True)
    args = {'url': 'https://owned.example/'}
    if commit is not None:
        args['commit'] = commit
    action = command.PlannedAction(tool='radix.passive.scan', arguments=args)
    method, path, params, body = command.adapter_request(action, actor)
    with pytest.raises(ValueError, match='^invalid artifact$'):
        artifact_id(body['artifact'])


@pytest.mark.parametrize('url', ['http://owned.example/', 'https://owned.example/path', 'https://owned.example:443/', 'https://owned.example/?x=1'])
def test_passive_url_uses_existing_origin_validator(runtime, url):
    actor = command.Actor(TENANT, 'founder', True)
    _, _, _, body = command.adapter_request(command.PlannedAction(tool='radix.passive.scan', arguments={'url': url, 'commit': 'a' * 40}), actor)
    with pytest.raises(ValueError, match='invalid target'):
        target_url(body['target'])


@pytest.mark.parametrize('detail,status,expected', [
    ('domain proof required', 403, 'domain proof required'),
    ([{'loc': ['body', 'artifact'], 'msg': 'Value error, invalid artifact'}], 422, 'invalid artifact'),
])
@pytest.mark.asyncio
async def test_corridor_preserves_only_required_refusals(runtime, monkeypatch, detail, status, expected):
    @asynccontextmanager
    async def acquire():
        async def fetchval(*args):
            return 1
        yield SimpleNamespace(fetchval=fetchval)
    runtime.pool = lambda: SimpleNamespace(acquire=acquire)
    monkeypatch.setenv('TANK_KEY_RADIX', 'offline-radix-test')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, json={'detail': detail}))) as room_http:
        runtime._http = room_http
        app = FastAPI(); app.include_router(corridor.build_router(runtime))
        headers = {'x-tank-key': runtime.TANK_API_KEY, 'x-tervory-tenant': str(TENANT), 'x-tervory-user': 'founder', 'x-tervory-squad': 'radix', 'x-tervory-region': 'us-east'}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
            response = await client.post('/v1/radix/passive/scans', json={'tenant_id': str(TENANT), 'target': 'https://owned.example/', 'artifact': 'commit:'}, headers=headers)
        assert response.status_code == status and response.json() == {'detail': expected}


@pytest.mark.parametrize('args,expected', [
    ({'url': 'https://owned.example/'}, 'invalid artifact'),
    ({'url': 'https://owned.example/', 'commit': 'a' * 39}, 'invalid artifact'),
    ({'url': 'https://owned.example/', 'commit': 'g' * 40}, 'invalid artifact'),
    ({'url': 'https://owned.example/', 'commit': 'a' * 40}, 'domain proof required'),
])
@pytest.mark.asyncio
async def test_dispatch_refusals_through_real_room_validation(runtime, monkeypatch, args, expected):
    import passive_routes
    @asynccontextmanager
    async def acquire():
        async def fetchval(*args): return 1
        yield SimpleNamespace(fetchval=fetchval)
    runtime.pool = lambda: SimpleNamespace(acquire=acquire)
    calls = []
    class Unproved:
        def __init__(self, pool): pass
        async def create(self, tenant, target, artifact):
            assert tenant == TENANT
            artifact_id(artifact); target_url(target)
            calls.append((tenant, target, artifact))
            raise PermissionError('domain proof required')
    monkeypatch.setattr(passive_routes, 'Store', Unproved)
    room_app = FastAPI()
    room_app.state.pool = object()
    room_app.dependency_overrides[passive_routes.require_tank] = lambda: None
    passive_routes.attach(room_app)
    monkeypatch.setenv('TANK_KEY_RADIX', 'offline-radix-test')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(room_app)) as room_http:
        runtime._http = room_http
        runtime.app = FastAPI(); runtime.app.include_router(corridor.build_router(runtime))
        status, result = await command.dispatch_action(command.PlannedAction(tool='radix.passive.scan', arguments=args), command.Actor(TENANT, 'founder', True))
    assert status == (403 if expected == 'domain proof required' else 422)
    assert result == {'detail': expected}
    assert len(calls) == (1 if expected == 'domain proof required' else 0)
