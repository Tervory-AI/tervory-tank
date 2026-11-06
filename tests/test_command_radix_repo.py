"""Client repo scans: real Command confirmation, upload ownership and code receipts."""
import base64
import io
import importlib.util
import sys
from pathlib import Path
import json
import uuid
import zipfile
from unittest.mock import AsyncMock
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException

import command
from test_command import TENANT, OTHER, runtime as runtime, command_pool as command_pool, api as api
from test_radix_iac import fake_checkov as fake_checkov
from test_rx1_scans import Ctx, _dirty, _tar, FIXTURE
from scanlib import orchestrate

JOB = uuid.UUID('33333333-3333-4333-8333-333333333333')


@pytest_asyncio.fixture
async def repo_api(api, runtime, monkeypatch):
    client, pool = api
    monkeypatch.setenv('DATABASE_URL', 'postgresql://postgres@127.0.0.1:55435/placeholder_test')
    monkeypatch.setenv('LITELLM_MASTER_KEY', 'placeholder-unused')
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-unused')
    spec = importlib.util.spec_from_file_location('placeholder_r5_tank', Path('tank/main.py'))
    real_tank = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, real_tank)
    spec.loader.exec_module(real_tank)
    runtime.tank = real_tank
    runtime.pool = lambda: pool
    runtime.RouteRequest = real_tank.RouteRequest
    runtime._record_local = real_tank._record_local
    runtime.Message = real_tank.Message
    runtime.run_route = AsyncMock(side_effect=AssertionError('placeholder: no model call'))
    monkeypatch.setattr(real_tank, 'pool', lambda: pool)
    monkeypatch.setattr(real_tank, 'box_region', lambda: 'us-east')
    runtime.app = FastAPI()
    runtime.app.include_router(command.router)
    monkeypatch.setenv('TANK_KEY_RADIX', 'placeholder-room-auth')
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'radix','placeholder-founder')", TENANT)
    yield client, pool, runtime


async def upload(client, raw, *, headers=None, name='placeholder-repo.zip'):
    thread = (await client.post('/v1/command/threads', json={}, headers=headers)).json()['thread_id']
    response = await client.post(f'/v1/command/threads/{thread}/attachments', params={'name': name}, content=raw, headers=headers)
    assert response.status_code == 200, response.text
    return thread, response.json()['attachment_id']


async def propose(client, thread, tool, arguments):
    response = await client.post(f'/v1/command/threads/{thread}/actions', json={'tool': tool, 'arguments': arguments})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize('archive_kind', ['tar', 'zip'])
async def test_confirmed_archive_all_scanners_redacted_and_zero_receipts(repo_api, monkeypatch, fake_checkov, archive_kind):
    client, pool, runtime = repo_api
    files = {**_dirty(), 'open.tf': 'locals { placeholder = true }'}
    if archive_kind == 'tar':
        raw = _tar(files)
    else:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            for path, text in files.items():
                archive.writestr(path, text)
        raw = buffer.getvalue()
    thread, attachment = await upload(client, raw)
    calls, jobs = [], {}

    def room(request):
        calls.append(request)
        assert request.headers['x-tank-key'] == 'placeholder-room-auth'
        if request.method == 'POST':
            data = json.loads(request.content)
            assert data['tenant_id'] == data['input']['tenant_id'] == str(TENANT)
            assert data['kind'] == 'scan' and data['input']['ref'] == 'placeholder-repo.zip'
            assert base64.b64decode(data['input']['source'][4:]) == raw
            ctx = Ctx(data['input']['source'], data['input']['ref'], str(TENANT))
            ctx.job_id = str(JOB)
            result = orchestrate.build_result(ctx)
            jobs[str(JOB)] = {'id': str(JOB), 'tenant_id': str(TENANT), 'kind': 'scan', 'status': 'done', 'result': result}
            return httpx.Response(201, json={'id': str(JOB), 'tenant_id': str(TENANT), 'kind': 'scan', 'status': 'queued'})
        assert request.url.params['tenant_id'] == str(TENANT)
        return httpx.Response(200, json=jobs[str(JOB)])

    async with httpx.AsyncClient(transport=httpx.MockTransport(room)) as http:
        runtime._http = http
        # A direct route or dispatch has no durable confirmation authority.
        direct = await client.post('/v1/command/radix/repo/scan', json={'attachment_id': attachment})
        assert direct.status_code == 409 and not calls
        action = command.PlannedAction(tool='radix.repo.scan', arguments={'attachment_id': attachment})
        status, _ = await command.dispatch_action(action, command.Actor(TENANT, 'founder', True))
        assert status == 409 and not calls
        card = await propose(client, thread, action.tool, action.arguments)
        assert card['status'] == 'pending' and not calls
        path = f"/v1/command/cards/{card['card_id']}"
        result = (await client.post(path, json={'action': 'confirm'})).json()
        assert result['status'] == 'confirmed', result
        assert result['result']['scan_id'] == str(JOB) and result['result']['status'] == 'pending'
        await client.post(path, json={'action': 'confirm'})
        assert len(calls) == 1
        read = await propose(client, thread, 'radix.repo.findings', {'scan_id': str(JOB)})
        result = (await client.post(f"/v1/command/cards/{read['card_id']}", json={'action': 'confirm'})).json()
        assert result['status'] == 'confirmed', result
        data = result['result']
        assert {r['tool'] for r in data['findings']} == {'scan.secrets', 'scan.dependencies', 'scan.static', 'scan.iac'}
        assert next(r for r in data['findings'] if r['tool'] == 'scan.iac')['severity'] == 'unknown'
        assert FIXTURE not in json.dumps(data)
        assert data['critical'] > 0 and data['summary']
        rows = await pool.fetch("SELECT task_type,agent,model,cost_usd,tokens_in,tokens_out FROM tank.ledger WHERE tenant_id=$1", TENANT)
        assert {r['task_type'] for r in rows} == {'radix.repo.scan', 'radix.repo.findings'}
        assert all(r['agent'] == 'radix' and r['model'] == 'code' and r['cost_usd'] == 0
                   and r['tokens_in'] == r['tokens_out'] == 0 for r in rows)
        snapshot = (await client.get(f'/v1/command/threads/{thread}')).json()
        assert len(snapshot['receipts']) == 2 and snapshot['thread']['spent_usd'] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('ownership,archive_kind', [
    ('same', 'invalid'), ('other-user', 'tar'), ('other-user', 'zip'),
    ('other-tenant', 'tar'), ('other-tenant', 'zip'),
])
async def test_invalid_archive_and_foreign_upload_never_reach_room(repo_api, monkeypatch, ownership, archive_kind):
    client, pool, runtime = repo_api
    headers = {'x-tervory-user': 'placeholder-other'} if ownership == 'other-user' else (
        {'x-tervory-tenant': str(OTHER)} if ownership == 'other-tenant' else None)
    raw = b'placeholder: not an archive'
    if archive_kind == 'tar':
        raw = _tar({'placeholder.txt': 'placeholder'})
    elif archive_kind == 'zip':
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('placeholder.txt', 'placeholder')
        raw = buffer.getvalue()
    _, attachment = await upload(client, raw, headers=headers)
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    room = AsyncMock(side_effect=AssertionError('placeholder: must not reach room'))
    monkeypatch.setattr('ghost_routes.call_room', room)
    dispatched = []
    dispatch = command.dispatch_action
    async def observe(action, actor):
        status, data = await dispatch(action, actor)
        dispatched.append((status, data))
        return status, data
    monkeypatch.setattr(command, 'dispatch_action', observe)
    card = await propose(client, thread, 'radix.repo.scan', {'attachment_id': attachment})
    result = (await client.post(f"/v1/command/cards/{card['card_id']}", json={'action': 'confirm'})).json()
    assert result['status'] == 'failed'
    room.assert_not_awaited()
    assert len(dispatched) == 1
    count = await pool.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1", TENANT)
    if ownership == 'same':
        assert dispatched[0][0] == 422
        assert dispatched[0][1]['detail'] == 'Hand over a tar or zip archive.'
        assert count == 1
    else:
        assert dispatched[0] == (404, {'detail': 'Attachment not found'})
        assert count == 0
        snapshot = (await client.get(f'/v1/command/threads/{thread}')).json()
        assert snapshot['receipts'] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('mismatch', ['envelope', 'result', 'missing', 'wrong-id', 'wrong-kind'])
async def test_findings_refuse_foreign_or_mismatched_job(repo_api, monkeypatch, mismatch):
    client, _, runtime = repo_api
    data = {'id': str(JOB), 'tenant_id': str(TENANT), 'kind': 'scan', 'status': 'done',
            'result': {'scan_id': str(JOB), 'tenant_id': str(TENANT), 'findings': [{'fix': 'placeholder-private'}]}}
    if mismatch == 'envelope': data['tenant_id'] = str(OTHER)
    if mismatch == 'result': data['result']['tenant_id'] = str(OTHER)
    if mismatch == 'wrong-id': data['id'] = str(uuid.uuid4())
    if mismatch == 'wrong-kind': data['kind'] = 'ping'
    if mismatch == 'missing': data.pop('tenant_id')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data))) as http:
        runtime._http = http
        response = await client.get('/v1/command/radix/repo/findings', params={'scan_id': str(JOB)})
    assert response.status_code == 404
    assert 'placeholder-private' not in response.text
    assert response.json()['cost_usd'] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('status,expected', [('queued','pending'), ('running','running'), ('failed','failed')])
async def test_pending_failed_results_do_not_fabricate_findings(repo_api, status, expected):
    client, _, runtime = repo_api
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={
        'id': str(JOB), 'tenant_id': str(TENANT), 'kind': 'scan', 'status': status,
        'result': None, 'error': 'placeholder-private exception'}))) as http:
        runtime._http = http
        response = await client.get('/v1/command/radix/repo/findings', params={'scan_id': str(JOB)})
    data = response.json()
    assert data['status'] == expected and 'findings' not in data
    assert 'placeholder-private' not in response.text


@pytest.mark.asyncio
async def test_explicit_scan_turn_binds_upload_without_model_or_execution(repo_api):
    client, pool, runtime = repo_api
    thread, attachment = await upload(client, _tar({'placeholder.txt': 'placeholder'}))
    response = await client.post(f'/v1/command/threads/{thread}/turn', json={
        'text': 'radix.repo.scan', 'attachments': [{'attachment_id': attachment}]})
    assert response.status_code == 200
    runtime.run_route.assert_not_awaited()
    snapshot = (await client.get(f'/v1/command/threads/{thread}')).json()
    assert snapshot['cards'][0]['tool'] == 'radix.repo.scan'
    assert snapshot['cards'][0]['status'] == 'pending'
    assert snapshot['cards'][0]['arguments'] == {'attachment_id': attachment}
    rows = await pool.fetch("SELECT model,cost_usd FROM tank.ledger WHERE tenant_id=$1", TENANT)
    assert len(rows) == 1 and rows[0]['model'] == 'code' and rows[0]['cost_usd'] == 0


def test_client_catalogue_and_no_injected_authority(runtime):
    actor = command.Actor(TENANT, 'placeholder-client', False, frozenset({'radix'}))
    assert {'radix.repo.scan', 'radix.repo.findings'} <= set(command.allowed_tools(actor))
    for tool, args in [('radix.repo.scan', {'attachment_id': str(JOB)}), ('radix.repo.findings', {'scan_id': str(JOB)})]:
        assert command.ADAPTERS[tool].paid is False
        for key in ('tenant_id', 'user_id', 'confirmed', 'source'):
            with pytest.raises(HTTPException):
                command.validate_action(command.PlannedAction(tool=tool, arguments={**args, key: 'placeholder'}), actor)


@pytest.mark.asyncio
@pytest.mark.parametrize('broken', ['missing-findings', 'non-list-findings', 'bad-json'])
async def test_malformed_room_result_is_not_a_clean_scan(repo_api, broken):
    client, _, runtime = repo_api
    data = {'id': str(JOB), 'tenant_id': str(TENANT), 'kind': 'scan', 'status': 'done',
            'result': {'scan_id': str(JOB), 'tenant_id': str(TENANT)}}
    if broken == 'non-list-findings':
        data['result']['findings'] = 'placeholder-private'
    response = httpx.Response(200, text='placeholder-private') if broken == 'bad-json' else httpx.Response(200, json=data)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response)) as http:
        runtime._http = http
        result = await client.get('/v1/command/radix/repo/findings', params={'scan_id': str(JOB)})
    assert result.status_code == 503
    assert result.json()['cost_usd'] == 0 and result.json()['ledger_id']
    assert 'findings' not in result.json() and 'placeholder-private' not in result.text


@pytest.mark.asyncio
async def test_tank_room_eval_uses_radix_key_and_existing_executor(repo_api, monkeypatch):
    _, _, runtime = repo_api
    requests = []
    def room(request):
        requests.append(request)
        assert str(request.url) == 'http://agent-radix:8000/evals/run'
        assert request.headers['X-Tank-Key'] == 'placeholder-room-auth'
        assert json.loads(request.content) == {'skill_id': 'scan.iac', 'version': '1.0.0',
            'tenant_id': str(TENANT), 'input': {'files': []}}
        return httpx.Response(200, json={'status': 'not run', 'refused': True})
    async with httpx.AsyncClient(transport=httpx.MockTransport(room)) as http:
        monkeypatch.setattr(runtime.tank, '_http', http)
        pkg = SimpleNamespace(id='scan.iac',version='1.0.0')
        ctx = SimpleNamespace(tenant_id=TENANT)
        result = await runtime.tank.run_room_eval(pkg, {'files': []}, ctx)
        assert result == {'status': 'not run', 'refused': True}
        monkeypatch.delenv('TANK_KEY_RADIX')
        with pytest.raises(RuntimeError, match='Missing setting: TANK_KEY_RADIX'):
            await runtime.tank.run_room_eval(pkg, {'files': []}, ctx)
        assert len(requests) == 1


@pytest.mark.asyncio
async def test_real_room_job_query_is_tenant_scoped(repo_api):
    from chassis.app import create_app
    from chassis.db import ensure_schema
    client, pool, runtime = repo_api
    async with pool.acquire() as conn:
        await ensure_schema(conn, 'radix')
    room = create_app(agent='radix', handlers={})
    room.state.pool = pool
    async with httpx.AsyncClient(transport=httpx.ASGITransport(room), base_url='http://agent-radix:8000') as http:
        runtime._http = http
        queued = await http.post('/jobs', json={'tenant_id': str(TENANT), 'kind': 'scan', 'input': {}})
        assert queued.status_code == 201
        scan_id = queued.json()['id']
        saved = {'scan_id': scan_id, 'tenant_id': str(TENANT), 'findings': [],
                 'summary': 'placeholder-private-summary', 'critical': 0}
        async with pool.acquire() as conn:
            await conn.execute("UPDATE agent_radix.jobs SET status='done',result=$3::jsonb WHERE id=$1 AND tenant_id=$2",
                               uuid.UUID(scan_id), TENANT, json.dumps(saved))
        own = await client.get('/v1/command/radix/repo/findings', params={'scan_id': scan_id})
        assert own.status_code == 200 and own.json()['status'] == 'complete'
        assert own.json()['findings'] == []
        foreign = await client.get('/v1/command/radix/repo/findings', params={'scan_id': scan_id},
                                   headers={'x-tervory-tenant': str(OTHER)})
        assert foreign.status_code == 404 and 'placeholder-private-summary' not in foreign.text
