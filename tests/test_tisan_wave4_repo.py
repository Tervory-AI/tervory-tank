"""Offline R5 orchestration: actual Tank corridor, archive binding and deployment gates."""
import base64
import hashlib
import json
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

import ghost_routes
import tisan_pipeline
from agents.tisan import publish, repo_scan
from test_tisan_publish import TENANT, build


@pytest.fixture
def corridor(monkeypatch):
    monkeypatch.setenv('TANK_KEY_TISAN', 'placeholder-room')
    monkeypatch.setenv('TANK_KEY', 'placeholder-room')
    monkeypatch.setenv('TANK_URL', 'http://placeholder-tank')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(box_region=lambda: 'us-east'))
    state = {'critical': 0, 'complete': True, 'wrong_tenant': False, 'wrong_ref': False, 'calls': [], 'jobs': {}}

    async def room(method, room, path, *, body=None, params=None):
        assert room == 'radix'
        state['calls'].append((method, path))
        if method == 'POST':
            raw = base64.b64decode(body['input']['source'][4:], validate=True)
            assert body['input']['tenant_id'] == body['tenant_id']
            assert body['input']['ref'] == 'sha256:' + hashlib.sha256(raw).hexdigest()
            ident = str(uuid4())
            state['jobs'][ident] = body
            return httpx.Response(201, json={'id': ident, 'tenant_id': body['tenant_id'], 'kind': 'scan'})
        ident = path.rsplit('/', 1)[-1]
        original = state['jobs'][ident]
        tenant = original['tenant_id']
        assert params == {'tenant_id': tenant}
        if state['wrong_tenant']:
            tenant = str(uuid4())
        result = {'tenant_id': tenant, 'scan_id': ident, 'critical': state['critical'],
            'scan_complete': state['complete'], 'tools': sorted(repo_scan.TOOLS), 'leaked': False,
            'ref': 'placeholder-wrong' if state['wrong_ref'] else original['input']['ref'], 'findings': []}
        return httpx.Response(200, json={'id': ident, 'tenant_id': tenant, 'kind': 'scan', 'status': 'done', 'result': result})

    monkeypatch.setattr(ghost_routes, 'call_room', room)
    app = FastAPI()
    app.include_router(tisan_pipeline.build_router(), prefix='/v1/command/tisan')
    return app, state


@pytest.mark.asyncio
@pytest.mark.parametrize('critical', [0, 1])
async def test_build_records_real_r5_corridor_receipt_and_critical_blocks(tmp_path, corridor, critical):
    app, state = corridor
    state['critical'] = critical
    build(tmp_path)
    manifest = json.loads((tmp_path / 'builds' / TENANT / 'site/1.json').read_text())
    manifest['checks'] = [manifest['checks'][0]]  # A new archive has not been scanned yet.
    manifest['archive'] = str(tmp_path / 'builds' / TENANT / 'site/1.tar.gz')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-tank') as client:
        measured = await repo_scan.attach(manifest, TENANT, http=client)
    assert measured['ok'] is (critical == 0)
    check = measured['checks'][-1]
    assert check['name'] == 'radix.repo' and check['critical'] == critical
    assert check['tenant_id'] == TENANT and UUID(check['scan_id'])
    assert json.loads((tmp_path / 'builds' / TENANT / 'site/1.json').read_text())['checks'][-1] == check
    assert state['calls'][0] == ('POST', '/jobs') and state['calls'][1][0] == 'GET'
    if critical:
        with pytest.raises(ValueError):
            publish.stored_build(tmp_path, TENANT, 'site', 1)
    else:
        assert publish.stored_build(tmp_path, TENANT, 'site', 1)['manifest']['checks'][-1] == check
        archive = tmp_path / 'builds' / TENANT / 'site/1.tar.gz'
        archive.write_bytes(archive.read_bytes() + b'placeholder-tamper')
        with pytest.raises(ValueError, match='repo scan required'):
            publish.stored_build(tmp_path, TENANT, 'site', 1)


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['complete', 'wrong_tenant', 'wrong_ref'])
async def test_incomplete_foreign_or_wrong_artifact_scan_fails_closed(tmp_path, corridor, change):
    app, state = corridor
    state[change] = False if change == 'complete' else True
    build(tmp_path)
    archive = tmp_path / 'builds' / TENANT / 'site/1.tar.gz'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-tank') as client:
        check = await repo_scan.check(archive, TENANT, http=client)
    assert check['ok'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('header,value', [('x-tank-key', 'placeholder-other'), ('x-tervory-tenant', str(uuid4())),
                                         ('x-tervory-region', 'za')])
async def test_corridor_requires_room_tenant_and_region(corridor, header, value):
    app, state = corridor
    raw = b'\x1f\x8bplaceholder'
    headers = {**{k.lower(): v for k, v in repo_scan.headers(TENANT).items()}, header: value}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-tank') as client:
        response = await client.post('/v1/command/tisan/pipeline/repo-scan', headers=headers,
            json={'tenant_id': TENANT, 'source': base64.b64encode(raw).decode(), 'sha256': hashlib.sha256(raw).hexdigest()})
    assert response.status_code == 403 and not state['calls']


def test_legacy_build_without_repo_receipt_cannot_publish(tmp_path):
    build(tmp_path)
    path = tmp_path / 'builds' / TENANT / 'site/1.json'
    data = json.loads(path.read_text())
    data['checks'] = [data['checks'][0]]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='repo scan required'):
        publish.stored_build(tmp_path, TENANT, 'site', 1)
