"""Exercise room identity, gate transport and Tank's actual proxy function offline."""
import ast
import os
import types
from pathlib import Path

import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response

from agents.tisan import promotion, promotion_api
from test_promotion import FakeCoolify, NEW, OLD, TARGET, TENANT, OTHER


@pytest.mark.asyncio
async def test_room_identity_gate_binding_and_status(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('TANK_KEY', 'room-test-only')
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder')
    monkeypatch.setenv('TANK_REGION', 'za')
    monkeypatch.setenv('TISAN_COOLIFY_URL', 'https://coolify.test')
    monkeypatch.setenv('TISAN_COOLIFY_TOKEN', 'test-only')
    fake = FakeCoolify()
    gate_calls = []
    gate_available = True
    from datetime import datetime, timezone
    async def transport(request):
        nonlocal gate_available
        if request.url.host == 'coolify.test':
            return await httpx.ASGITransport(app=fake.api).handle_async_request(request)
        import json
        data = json.loads(request.content)
        gate_calls.append((request.url.path, data, dict(request.headers)))
        assert request.headers['x-tervory-region'] == 'za'
        assert request.headers['x-tervory-tenant'] == TENANT
        assert request.headers['x-tervory-squad'] == 'tisan'
        assert request.headers['x-tank-key'] == 'room-test-only'
        if not gate_available:
            return httpx.Response(404, json={'detail': 'missing gate'})
        return httpx.Response(200, json={**data, 'allowed': True, 'scan_id': 'server-owned',
            'completed_at': datetime.now(timezone.utc).isoformat(), 'status': 'complete', 'high': 0, 'critical': 0})
    def client(**kwargs):
        assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        return httpx.AsyncClient(transport=httpx.MockTransport(transport), **kwargs)
    monkeypatch.setattr(promotion_api, 'httpx', types.SimpleNamespace(AsyncClient=client, HTTPError=httpx.HTTPError))
    async def checked(url):
        assert url == TARGET
        return {'passed': True, 'artifact': 'local-proof'}
    monkeypatch.setattr(promotion_api, 'live_check', checked)
    app = FastAPI()
    promotion_api.mount(app, promotion)
    headers = {'x-tank-key': 'room-test-only', 'x-tervory-admin': 'founder'}
    binding = {'tenant_id': TENANT, 'site': 'site', 'staging': 'stage', 'production': 'prod', 'url': TARGET}
    operation = {'tenant_id': TENANT, 'site': 'site', 'operation_id': '11111111-1111-1111-1111-111111111111', 'commit': NEW}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://room') as browser:
        assert (await browser.post('/promotion/sites', json=binding)).status_code == 404
        assert (await browser.post('/promotion/sites', headers={**headers, 'x-tervory-admin': 'member'}, json=binding)).status_code == 404
        assert not (tmp_path / 'promotion.sqlite3').exists()
        assert (await browser.post('/promotion/sites', headers=headers, json=binding)).status_code == 200
        assert (await browser.post('/promotion/promote', headers=headers, json={**operation, 'tenant_id': OTHER})).status_code == 503
        gate_available = False
        result = await browser.post('/promotion/promote', headers=headers, json=operation)
        assert result.json()['result'] == 'refused' and not fake.writes
        gate_available = True
        operation['operation_id'] = '22222222-2222-2222-2222-222222222222'
        result = await browser.post('/promotion/promote', headers=headers, json=operation)
        assert result.json()['result'] == 'pending'
        result = await browser.post('/promotion/status', headers=headers, json=operation)
        assert result.json()['result'] == 'succeeded'
        paths = [call[0] for call in gate_calls]
        assert paths == ['/v1/radix/passive/scans', '/v1/radix/passive/scans', '/v1/radix/passive/gate']
        assert gate_calls[-1][1] == {'tenant_id': TENANT, 'target': TARGET, 'artifact': 'commit:' + NEW}
        history = await browser.get('/promotion/history', headers=headers, params={'tenant_id': OTHER, 'site': 'site'})
        assert history.json() == []
        assert not any(key in result.text for key in ['test-only', 'Authorization', 'logs'])


@pytest.mark.asyncio
async def test_actual_tank_proxy_auth_allowlist_scope_and_size(monkeypatch):
    source = (Path(__file__).resolve().parents[2] / 'tank/main.py').read_text()
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'tisan_promotion_proxy')
    async def require_admin(x_tank_key: str = __import__('fastapi').Header(default=''),
                            x_tervory_admin: str = __import__('fastapi').Header(default='')):
        if x_tank_key != 'workspace-test-only' or x_tervory_admin != 'founder':
            raise HTTPException(404)
    import sys
    monkeypatch.setitem(sys.modules, 'admin', types.SimpleNamespace(require_admin=require_admin))
    calls = []
    async def upstream(request):
        calls.append(request)
        return httpx.Response(200, json={'result': 'pending'})
    monkeypatch.setenv('TANK_KEY_TISAN', 'room-test-only')
    app = FastAPI()
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as corridor:
        namespace = dict(app=app, Depends=Depends, Request=Request, Response=Response,
            HTTPException=HTTPException, os=os, httpx=httpx, _http=corridor)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'tank/main.py', 'exec'), namespace)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank') as browser:
            headers = {'x-tank-key': 'workspace-test-only', 'x-tervory-admin': 'founder'}
            assert (await browser.post('/v1/tisan/promotion/promote', json={})).status_code == 404
            assert (await browser.post('/v1/tisan/promotion/destroy', headers=headers, json={})).status_code == 404
            assert (await browser.post('/v1/tisan/promotion/promote', headers=headers, content=b'x'*8193)).status_code == 413
            assert not calls
            body = {'tenant_id': TENANT, 'site': 'site', 'commit': OLD}
            assert (await browser.post('/v1/tisan/promotion/promote', headers=headers, json=body)).status_code == 200
            assert len(calls) == 1
            assert str(calls[0].url) == 'http://agent-tisan:8000/promotion/promote'
            assert calls[0].headers['x-tank-key'] == 'room-test-only'
            assert calls[0].headers['x-tervory-admin'] == 'founder'
