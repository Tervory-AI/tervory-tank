import ast
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException

from test_tiger import ROOT, TENANT_A, TENANT_B, NOW, _load, _watch
import test_tiger_competitors as database_fixtures
postgres = database_fixtures.postgres
database = database_fixtures.database
from tiger_sheet.patch_source import source
from batch import Checkpoint, completed, plan
from execution import once_check, job_pool
from watch import MemoryStore, PgStore


@pytest.mark.asyncio
async def test_every_agent_route_requires_its_existing_room_credential(monkeypatch):
    agent = _load('gate5_auth', ROOT/'agents/tiger/app.py')
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.setenv('RIG_TIGER_CHECK_KEY', 'placeholder-rig-key')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=agent.app), base_url='http://placeholder') as client:
        seen = set()
        routes = {name: set(operations) for name, operations in agent.app.openapi()['paths'].items()}
        for route in agent.app.routes:
            if hasattr(route, 'path'):
                routes.setdefault(route.path, set()).update(route.methods or [])
        for original, methods in routes.items():
            path = original.replace('{watch_id}', str(uuid4())).replace('{job_id}', str(uuid4()))
            path = path.replace('{category}', 'screenshots').replace('{name:path}', 'placeholder')
            for method in methods:
                response = await client.request(method, path)
                assert response.status_code == 401, (method, path, response.text)
                seen.add(original)
        assert {'/jobs', '/health', '/batch/check', '/batch/discover', '/watchlist', '/rig/check-now', '/gold/candidates'} <= seen
        for value in ('', 'wrong-placeholder', 'placeholder-room-key-extra'):
            assert (await client.get('/watchlist', headers={'X-Tank-Key': value})).status_code == 401


@pytest.mark.asyncio
async def test_authenticated_routes_preserve_identity_and_do_not_accept_conflicting_tenant(monkeypatch):
    agent = _load('gate5_scope', ROOT/'agents/tiger/app.py')
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    store = MemoryStore()
    foreign = await store.create_watch(_watch(TENANT_B))
    monkeypatch.setattr(agent, '_store', lambda: store)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=agent.app), base_url='http://placeholder',
                                headers={'X-Tank-Key': 'placeholder-room-key', 'X-Tenant-ID': TENANT_A}) as client:
        assert (await client.get('/watchlist', params={'tenant_id': TENANT_A})).json() == {'watches': []}
        assert (await client.get('/watchlist', params={'tenant_id': TENANT_B})).status_code == 403
        assert (await client.post('/batch/check', json={'tenant_id': TENANT_B})).status_code == 403
        assert (await client.delete('/watchlist/'+foreign['id'], params={'tenant_id': TENANT_A})).status_code == 404
        assert (await client.get('/watchlist', params={'tenant_id': 'not-a-uuid'})).status_code == 422
    assert (await store.list_watches(TENANT_B))[0]['id'] == foreign['id']


@pytest.mark.asyncio
async def test_tank_relay_forwards_existing_room_key_and_never_logs_it(monkeypatch):
    parsed = ast.parse(source('tank/main.py'))
    function = next(node for node in parsed.body if isinstance(node, ast.AsyncFunctionDef) and node.name == '_tiger_call')
    calls = []
    async def answer(request):
        calls.append(request)
        assert request.headers['x-tank-key'] == 'placeholder-room-key'
        assert request.extensions['timeout']['read'] == 30
        return httpx.Response(200, json={'watches': []})
    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as http:
        namespace = {'os': os, 'httpx': httpx, 'HTTPException': HTTPException, 'Any': object,
                     '_http': http, 'TIGER_AGENT_URL': 'http://placeholder'}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'proposed relay', 'exec'), namespace)
        monkeypatch.delenv('TANK_KEY_TIGER', raising=False)
        with pytest.raises(HTTPException) as missing:
            await namespace['_tiger_call']('GET', '/watchlist', [], None)
        assert missing.value.status_code == 503 and 'TANK_KEY_TIGER' in missing.value.detail and calls == []
        monkeypatch.setenv('TANK_KEY_TIGER', 'placeholder-room-key')
        assert (await namespace['_tiger_call']('GET', '/watchlist', [('tenant_id', TENANT_A)], None)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize('fail_first', [False, True])
async def test_completed_price_job_is_atomic_and_reused_after_lost_completion(database, fail_first):
    ident = uuid4()
    await database.execute("INSERT INTO agent_tiger.jobs(id,tenant_id,kind,input,status) VALUES($1,$2,'check','{}','running')",
                           ident, UUID(TENANT_A))
    count = 0
    @once_check(lambda: database)
    async def work(ctx):
        nonlocal count
        count += 1
        observation = await PgStore(job_pool(database)).add_observation({
            'tenant_id': TENANT_A, 'url': _watch()['url'], 'ts': NOW, 'price': '12.00',
            'currency': 'USD', 'availability': 'InStock', 'method': 'jsonld', 'evidence': '{}'})
        if fail_first and count == 1:
            raise RuntimeError('placeholder worker failure')
        await asyncio.sleep(.01)
        return {'observation': observation}
    ctx = SimpleNamespace(tenant_id=TENANT_A, job_id=ident)
    if fail_first:
        with pytest.raises(RuntimeError): await work(ctx)
        assert await database.fetchval('SELECT count(*) FROM agent_tiger.observations') == 0
    first, second = await asyncio.gather(work(ctx), work(ctx))
    assert first == second == await work(ctx)
    assert count == (2 if fail_first else 1)
    assert await database.fetchval('SELECT count(*) FROM agent_tiger.observations') == 1
    stored = await database.fetchval('SELECT result FROM agent_tiger.jobs WHERE id=$1', ident)
    assert json.loads(stored) == first


@pytest.mark.asyncio
async def test_queued_job_polling_expires_without_resubmitting(monkeypatch):
    import batch
    monkeypatch.setattr(batch, 'JOB_WAIT_S', .02)
    ident = str(uuid4())
    job = {'id': ident, 'tenant_id': TENANT_A, 'status': 'running'}
    requests, progress = [], []
    async def answer(request):
        requests.append(request.method)
        return httpx.Response(200, json=job)
    async def immediate(_): await asyncio.sleep(0)
    async with httpx.AsyncClient(base_url='https://placeholder.invalid', transport=httpx.MockTransport(answer)) as client:
        with pytest.raises(TimeoutError):
            await completed(client, TENANT_A, job, ident, immediate, progress.append)
    assert requests and set(requests) == {'GET'} and set(progress) == {ident}


def test_checkpoint_refuses_symlinks_and_concurrent_writers(tmp_path):
    target = tmp_path/'outside'
    target.write_text('placeholder private content')
    link = tmp_path/'linked'
    link.symlink_to(target)
    args = (TENANT_A, str(uuid4()), plan([], TENANT_A))
    with pytest.raises(ValueError, match='symbolic'):
        Checkpoint(link, *args)
    assert target.read_text() == 'placeholder private content'
    path = tmp_path/'checkpoint'
    first = Checkpoint(path, *args)
    try:
        assert path.stat().st_mode & 0o777 == 0o600
        with pytest.raises(BlockingIOError): Checkpoint(path, *args)
    finally:
        first.close()
    Checkpoint(path, *args).close()


@pytest.mark.asyncio
async def test_browser_requires_auth_and_hides_exception_details(monkeypatch, tmp_path):
    browser = _load('gate5_browser', ROOT/'tiger/app.py')
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=browser.app), base_url='http://placeholder') as client:
        for path in ('/render', '/ocr', '/health', '/openapi.json'):
            assert (await client.post(path)).status_code == 401
    ctx = SimpleNamespace(new_page=AsyncMock(return_value=object()), close=AsyncMock())
    browser._browser = SimpleNamespace(new_context=AsyncMock(return_value=ctx))
    monkeypatch.setattr(browser, '_route', AsyncMock())
    monkeypatch.setattr(browser, '_fill', AsyncMock(side_effect=RuntimeError('placeholder-private-value')))
    result = await browser._render_ephemeral(browser.RenderReq(url='https://placeholder.example'), 0)
    assert 'placeholder-private-value' not in json.dumps(result)
    assert result['error'] == 'Tiger is not reachable right now.'
    path = tmp_path/'session.json'
    async def save(path):
        assert Path(path).stat().st_mode & 0o777 == 0o600
        Path(path).write_text('{"cookies": []}')
    await browser._save_session(SimpleNamespace(storage_state=save), path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.asyncio
async def test_authenticated_ocr_skill_preserves_existing_parser_without_exposing_key(monkeypatch):
    parsed = ast.parse(source('tank/main.py'))
    definition = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == 'TigerOcrHTTP')
    scope = {'os': os, 'asyncio': asyncio, 'HTTPException': HTTPException}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), 'proposed OCR boundary', 'exec'), scope)
    requests = []
    async def answer(request):
        requests.append(request)
        assert request.headers['x-tank-key'] == 'placeholder-room-key'
        assert request.extensions['timeout']['read'] == 30
        return httpx.Response(200, json={'text': '$12.50'})
    monkeypatch.setenv('TIGER_URL', 'http://placeholder')
    monkeypatch.setenv('TANK_KEY_TIGER', 'placeholder-room-key')
    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as http:
        boundary = scope['TigerOcrHTTP'](http)
        with pytest.raises(HTTPException):
            await boundary.post('https://foreign.invalid/ocr')
        skill = _load('gate5_ocr_skill', ROOT/'tank/skills/tiger.price_ocr/1.0.1/run.py')
        result = await skill.run({'url': 'https://store.example/item', 'png_base64': 'placeholder-image'},
                                SimpleNamespace(http=boundary, env={'TIGER_URL': 'http://placeholder'}))
        assert result['items'][0]['price'] == '12.50' and len(requests) == 1
        monkeypatch.delenv('TANK_KEY_TIGER')
        with pytest.raises(HTTPException) as failure:
            await boundary.post('http://placeholder/ocr')
        assert failure.value.status_code == 503 and len(requests) == 1
    import yaml
    deployment = yaml.safe_load(source('docker-compose.yml'))['services']['tiger']
    assert deployment['environment']['TANK_KEY'] == '${TANK_KEY_TIGER:-}'
    assert 'X-Tank-Key' in deployment['healthcheck']['test'][-1]


@pytest.mark.asyncio
async def test_browser_missing_key_and_session_save_failure_are_explicit(monkeypatch, tmp_path, caplog):
    browser = _load('gate5_browser_save', ROOT/'tiger/app.py')
    monkeypatch.setattr(browser, 'DATA_DIR', str(tmp_path))
    monkeypatch.delenv('TANK_KEY', raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=browser.app), base_url='http://placeholder') as client:
        response = await client.get('/health')
        assert response.status_code == 503 and response.json()['settings'] == ['TANK_KEY']
    page = SimpleNamespace(close=AsyncMock())
    context = SimpleNamespace(new_page=AsyncMock(return_value=page), close=AsyncMock())
    live = browser._Live(context)
    path = tmp_path/'session.json'
    monkeypatch.setattr(browser, '_session_live', AsyncMock(return_value=(live, path)))
    monkeypatch.setattr(browser, '_route', AsyncMock())
    async def fill(page, req, out): out['ok'] = True
    monkeypatch.setattr(browser, '_fill', fill)
    monkeypatch.setattr(browser, '_save_session', AsyncMock(side_effect=OSError('placeholder-private-value')))
    result = await browser._render_session(browser.RenderReq(url='https://store.example', session='same', tenant=TENANT_A, agent='tiger'), 0)
    assert not result['ok'] and result['error'] == 'That could not be saved. Try again.'
    await browser._save_and_close(('tiger', TENANT_A, 'same'), live)
    assert 'placeholder-private-value' not in caplog.text and 'session save failed' in caplog.text
    page.close.assert_awaited_once()
    context.close.assert_awaited_once()


def test_browser_session_cannot_follow_another_tenants_directory(tmp_path):
    browser = _load('gate5_browser_path', ROOT/'tiger/app.py')
    first = browser.session_file(tmp_path, 'tiger', TENANT_A, 'same')
    second = browser.session_file(tmp_path, 'tiger', TENANT_B, 'same')
    second.parent.mkdir(parents=True)
    first.parent.symlink_to(second.parent, target_is_directory=True)
    with pytest.raises(browser.SessionKeyError):
        browser.session_file(tmp_path, 'tiger', TENANT_A, 'same')


def test_bad_checkpoint_releases_lock_without_changing_input(tmp_path):
    import sqlite3
    path = tmp_path/'bad.sqlite'
    path.write_text('placeholder invalid database')
    for _ in range(2):
        with pytest.raises(sqlite3.DatabaseError):
            Checkpoint(path, TENANT_A, str(uuid4()), [])
    assert path.read_text() == 'placeholder invalid database'
