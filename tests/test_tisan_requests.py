"""T3 offline: real room journal, fake Hermes, and disposable PostgreSQL cards."""
import copy
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

import command
import tisan_requests as requests
from agents.tisan import promotion, publish
from chassis.memory import MemoryClient
from test_command import command_pool as command_pool
from trigger_commands import CONFIRMED

ROOT = Path(__file__).resolve().parents[1]
TENANT = uuid.UUID('11111111-1111-4111-8111-111111111111')
OTHER = uuid.UUID('22222222-2222-4222-8222-222222222222')
SHA = 'a' * 40


def brief():
    return {'name': 'placeholder site', 'slug': 'placeholder-site', 'locale': 'en',
            'brand': {}, 'request': 'placeholder client request'}


def builder():
    spec = importlib.util.spec_from_file_location('t3_placeholder_builder', ROOT / 'agents/tisan/builder.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['passed', 'failed', 'refused', 'exception'])
async def test_each_build_has_one_private_measured_record(monkeypatch, outcome):
    b = builder()
    source = {'slug': 'placeholder-site', 'ok': outcome == 'passed', 'build': 3,
              'checks': [{'name': 'placeholder check', 'ok': outcome == 'passed', 'detail': 'placeholder detail'}]}
    if outcome == 'passed':
        source['archive'] = '/data/builds/' + str(TENANT) + '/placeholder-site/3.tar.gz'
    if outcome == 'refused':
        source.update(refused=True, detail='placeholder refusal')
    execute = AsyncMock(side_effect=RuntimeError('placeholder private error')) if outcome == 'exception' else AsyncMock(return_value=copy.deepcopy(source))
    monkeypatch.setattr(b, 'execute', execute)
    import chassis.events
    monkeypatch.setattr(chassis.events, 'publish', AsyncMock())
    records = []
    record_id = str(uuid.uuid4())
    def hermes(request):
        assert request.url.host == 'placeholder-hermes'
        body = json.loads(request.content)
        records.append(body)
        return httpx.Response(201, json={'id': record_id})
    async with httpx.AsyncClient(transport=httpx.MockTransport(hermes)) as http:
        ctx = SimpleNamespace(input=brief(), tenant_id=str(TENANT), job_id=str(uuid.uuid4()), tank=None,
            memory=MemoryClient(base_url='http://placeholder-hermes', api_key='placeholder-room', agent='tisan', http=http))
        result = await b.handle(ctx)
    assert len(records) == 1 and records[0]['tenant_id'] == str(TENANT)
    assert records[0]['kind'] == 'build' and records[0]['confidence'] == 1.0
    claim = json.loads(records[0]['text'])
    assert claim['slug'] == 'placeholder-site' and claim['ok'] == (outcome == 'passed')
    assert claim['checks'] == ([] if outcome == 'exception' else source['checks'])
    assert records[0]['evidence'] == [ctx.job_id] + (['3.tar.gz'] if outcome == 'passed' else [])
    assert result['memory_id'] == record_id
    assert 'tier' not in records[0] and 'public' not in records[0]
    assert 'placeholder private error' not in records[0]['text']


@pytest.mark.asyncio
async def test_memory_failure_preserves_build_and_logs_class_only(monkeypatch, caplog):
    b = builder()
    source = {'ok': False, 'refused': True, 'checks': [], 'detail': 'placeholder refusal'}
    monkeypatch.setattr(b, 'execute', AsyncMock(return_value=source.copy()))
    ctx = SimpleNamespace(input=brief(), tenant_id=str(TENANT), job_id=str(uuid.uuid4()), tank=None,
        memory=SimpleNamespace(remember=AsyncMock(side_effect=RuntimeError('placeholder sensitive message'))))
    assert await b.handle(ctx) == source
    assert 'RuntimeError' in caplog.text and 'placeholder sensitive message' not in caplog.text


@pytest.fixture
def runtime(monkeypatch):
    runtime = SimpleNamespace(TANK_API_KEY='placeholder-workspace', box_region=lambda: 'us-east')
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'placeholder-founder')
    monkeypatch.setenv('TANK_KEY_TISAN', 'placeholder-room')
    monkeypatch.setitem(sys.modules, 'main', runtime)
    return runtime


def test_admin_catalogue_and_build_validation(runtime):
    for founder, admin in [(True, False), (False, True), (False, False)]:
        actor = command.Actor(TENANT, 'placeholder-founder' if founder else 'placeholder-user', founder,
                              frozenset({'tisan'}), tenant_admin=admin)
        available = command.allowed_tools(actor)
        assert all((tool in available) == (founder or admin) for tool in requests.TOOLS)
        assert ('tisan.build' in available) == founder
    for field, value in [('slug', '../placeholder'), ('name', ''), ('locale', 'placeholder-invalid')]:
        data = {**brief(), field: value}
        with pytest.raises(ValidationError):
            command.TisanRequestArgs.model_validate(data)
        with pytest.raises(ValidationError):
            command.TisanBuildArgs.model_validate(data)
    for field in ('tenant_id', 'plan', 'copy', 'media'):
        with pytest.raises(ValidationError):
            command.TisanRequestArgs.model_validate({**brief(), field: {}})
    with pytest.raises(ValidationError):
        requests.FeedbackArgs(request_id=uuid.uuid4(), text='p' * 4001)


def journal_row(journal, number, *, tenant=TENANT, state='succeeded', sha=SHA, action='publish'):
    site = 'placeholder-site'
    try:
        journal.site(str(tenant), site)
    except promotion.Refused:
        journal.register(str(tenant), site, {'staging': 'placeholder-stage-' + str(tenant),
            'production': 'placeholder-prod-' + str(tenant), 'url': 'https://placeholder-stage.test/'})
    op = str(uuid.uuid4())
    journal.reserve(str(tenant), site, op, action, 'placeholder-founder', f'build:{number}')
    journal.update(str(tenant), site, op, state,
        {'expected': f'build:{number}', 'commit': sha, 'url': 'https://placeholder-stage.test/'}, terminal=True)


@pytest_asyncio.fixture
async def client(runtime, command_pool, tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('TANK_KEY', 'placeholder-room')
    monkeypatch.setattr(command, 'db', lambda: command_pool)
    runtime.pool = lambda: command_pool
    room = FastAPI()
    publish.mount(room, promotion)
    journal = promotion.Journal(tmp_path / 'promotion.sqlite3')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room), base_url='http://placeholder-room') as corridor:
        runtime._http = corridor
        app = FastAPI()
        app.include_router(command.router)
        app.include_router(requests.build_router())
        headers = {'X-Tank-Key': 'placeholder-workspace', 'X-Tervory-Tenant': str(TENANT),
                   'X-Tervory-User': 'placeholder-admin', 'X-Tervory-Role': 'org:admin'}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-tank', headers=headers) as http:
            yield http, command_pool, journal, room


async def confirmed(client, tool, body, *, tenant=TENANT, operation=None):
    operation = operation or uuid.uuid4()
    marker = CONFIRMED.set((tenant, 'placeholder-admin', operation, tool, body))
    try:
        return await client.post('/v1/command/tisan/' + tool.split('.')[1], json=body)
    finally:
        CONFIRMED.reset(marker)


@pytest.mark.asyncio
async def test_full_request_preview_revision_signoff_and_tenant_isolation(client):
    http, pool, journal, room = client
    assert (await http.post('/v1/command/tisan/request', json=brief())).status_code == 409
    created = await confirmed(http, 'tisan.request', brief())
    assert created.status_code == 200, created.text
    data = created.json()
    request_id = data['request_id']
    assert data['status'] == 'requested' and data['input'] == brief() and data['cost_usd'] == 0
    body = {'request_id': request_id}
    empty = await http.get('/v1/command/tisan/preview', params=body)
    assert empty.json()['status'] == 'unavailable' and 'url' not in empty.json()
    journal_row(journal, 1)
    journal_row(journal, 9, state='failed')
    journal_row(journal, 8, state='pending')
    journal_row(journal, 99, tenant=OTHER)
    preview = await http.get('/v1/command/tisan/preview', params=body)
    assert preview.json()['build'] == 1 and preview.json()['commit'] == SHA
    feedback = {**body, 'text': 'placeholder change request'}
    assert (await http.post('/v1/command/tisan/feedback', json=feedback)).status_code == 409
    assert (await http.post('/v1/command/tisan/handover', json=body)).status_code == 409
    first = await confirmed(http, 'tisan.feedback', feedback)
    assert first.status_code == 200 and first.json()['status'] == 'changes_requested'
    async with pool.acquire() as conn:
        count = await conn.fetchval('SELECT count(*) FROM tank.tisan_request_events WHERE tenant_id=$1 AND request_id=$2', TENANT, uuid.UUID(request_id))
    assert count == 2
    assert (await confirmed(http, 'tisan.handover', body)).status_code == 409
    assert (await confirmed(http, 'tisan.feedback', feedback)).status_code == 409
    journal_row(journal, 2, sha='b' * 40)
    newer = (await http.get('/v1/command/tisan/preview', params=body)).json()
    assert newer['build'] == 2 and newer['commit'] == 'b' * 40
    accepted = await confirmed(http, 'tisan.handover', body)
    assert accepted.status_code == 200 and accepted.json()['status'] == 'accepted'
    assert accepted.json()['commit'] == 'b' * 40
    assert (await confirmed(http, 'tisan.feedback', feedback)).status_code == 409
    async with pool.acquire() as conn:
        events = await conn.fetch('SELECT kind,build,"commit",text FROM tank.tisan_request_events WHERE tenant_id=$1 AND request_id=$2 ORDER BY created_at', TENANT, uuid.UUID(request_id))
        assert [e['kind'] for e in events] == ['requested', 'changes_requested', 'accepted']
        assert events[1]['text'] == feedback['text'] and events[1]['build'] == 1 and events[2]['build'] == 2
        receipt = await conn.fetchrow('SELECT cost_usd,model,agent FROM tank.ledger WHERE tenant_id=$1 AND id=$2', TENANT, uuid.UUID(accepted.json()['ledger_id']))
        assert receipt['cost_usd'] == 0 and receipt['model'] == 'code' and receipt['agent'] == 'tisan'
    foreign = await http.get('/v1/command/tisan/preview', params=body, headers={'X-Tervory-Tenant': str(OTHER)})
    assert foreign.status_code == 404
    assert (await http.get('/v1/command/tisan/preview', params=body, headers={'X-Tervory-Role': ''})).status_code == 403
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room), base_url='http://placeholder-room') as direct:
        assert (await direct.get('/publish/latest', params={'tenant_id': str(TENANT), 'slug': 'placeholder-site'})).status_code == 404


@pytest.mark.asyncio
async def test_confirmed_card_dispatch_and_deterministic_plan(client, monkeypatch):
    http, pool, _, _ = client
    actor = command.Actor(TENANT, 'placeholder-admin', False, tenant_admin=True)
    action = command.validate_action(command.PlannedAction(tool='tisan.request', arguments=brief()), actor)
    # Proposal alone only creates the existing pending card and writes no request.
    monkeypatch.setattr(command, 'event', AsyncMock())
    monkeypatch.setattr(command, 'step', AsyncMock())
    state = {'cards': {}}
    card = await command.propose_action(None, {}, state, action, actor)
    assert card['status'] == 'pending'
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.tisan_requests WHERE tenant_id=$1', TENANT) == 0
    method, path, params, body = command.adapter_request(action, actor)
    assert method == 'POST' and path == '/v1/command/tisan/request' and params == {} and body == brief()
    planned = await requests.code_plan(actor, [{'role': 'user', 'content': 'tisan.request ' + json.dumps(brief())}], uuid.uuid4())
    assert json.loads(planned.content)['actions'] == [action.model_dump(mode='json')]
    # The same payload needs an executing owned card before dispatch_confirmed.
    from trigger_commands import dispatch_confirmed
    with pytest.raises(HTTPException):
        await dispatch_confirmed(action, actor, uuid.uuid4(), uuid.uuid4())


def test_schema_stays_before_generated_memory_and_startup_applies_it():
    schema = (ROOT / 'tank/schema.sql').read_text()
    assert schema.index('CREATE TABLE IF NOT EXISTS tank.tisan_requests') < schema.index('-- BEGIN GENERATED AGENT MEMORY')
    assert schema.rstrip().endswith('-- END GENERATED AGENT MEMORY')
    assert "oid='tank.command_threads'::regclass AND relrowsecurity" in schema
    for table in ('tisan_requests', 'tisan_request_events'):
        assert f'ALTER TABLE tank.{table} FORCE ROW LEVEL SECURITY' in schema
        assert f'CREATE POLICY tenant_boundary ON tank.{table} AS RESTRICTIVE' in schema
    assert 'await conn.execute(ddl)' in (ROOT / 'tank/main.py').read_text()


@pytest.mark.asyncio
async def test_real_confirm_card_dispatches_request_once(client, runtime):
    http, pool, _, _ = client
    app = FastAPI()
    app.include_router(command.router)
    app.include_router(requests.build_router())
    runtime.app = app
    # dispatch_action uses Tank's real ASGI app, never a network fallback.
    thread = (await http.post('/v1/command/threads', json={'title': 'placeholder request'})).json()['thread_id']
    proposed = await http.post(f'/v1/command/threads/{thread}/actions', json={'tool': 'tisan.request', 'arguments': brief()})
    assert proposed.status_code == 200, proposed.text
    card = proposed.json()
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.tisan_requests WHERE tenant_id=$1', TENANT) == 0
    result = await http.post('/v1/command/cards/' + card['card_id'], json={'action': 'confirm'})
    assert result.status_code == 200, result.text
    assert result.json()['status'] == 'confirmed', result.text
    assert result.json()['result']['status'] == 'requested'
    repeat = await http.post('/v1/command/cards/' + card['card_id'], json={'action': 'confirm'})
    assert repeat.status_code == 200
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.tisan_requests WHERE tenant_id=$1', TENANT) == 1
        assert await conn.fetchval('SELECT count(*) FROM tank.tisan_request_events WHERE tenant_id=$1', TENANT) == 1


@pytest.mark.asyncio
async def test_rls_joins_enforced_rollout_and_prevents_cross_tenant_rows(command_pool):
    async with command_pool.acquire() as conn:
        before = await conn.fetch('SELECT relname,relrowsecurity FROM pg_class WHERE oid IN (\'tank.tisan_requests\'::regclass,\'tank.tisan_request_events\'::regclass)')
        assert all(not r['relrowsecurity'] for r in before)
        await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
        schema = (ROOT / 'tank/schema.sql').read_text()
        await conn.execute(schema)
        await conn.execute(schema)
        rows = await conn.fetch('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid IN (\'tank.tisan_requests\'::regclass,\'tank.tisan_request_events\'::regclass)')
        assert all(r['relrowsecurity'] and r['relforcerowsecurity'] for r in rows)
        await conn.execute("DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='placeholder_tisan_t3_reader') THEN CREATE ROLE placeholder_tisan_t3_reader NOSUPERUSER NOBYPASSRLS; END IF; END $$")
        await conn.execute('GRANT USAGE ON SCHEMA tank TO placeholder_tisan_t3_reader')
        await conn.execute('GRANT SELECT,INSERT ON tank.tisan_requests,tank.tisan_request_events TO placeholder_tisan_t3_reader')
        first, second = uuid.uuid4(), uuid.uuid4()
        await conn.execute("INSERT INTO tank.tisan_requests(tenant_id,request_id,actor,data,state) VALUES($1,$2,'placeholder-user','{}','requested'),($3,$4,'placeholder-other','{}','requested')", TENANT, first, OTHER, second)
        async with conn.transaction():
            await conn.execute('SET LOCAL ROLE placeholder_tisan_t3_reader')
            await conn.fetchval("SELECT set_config('app.tenant_id',$1,true)", str(TENANT))
            visible = await conn.fetch('SELECT tenant_id,request_id FROM tank.tisan_requests')
            assert [(row['tenant_id'], row['request_id']) for row in visible] == [(TENANT, first)]
            with pytest.raises(__import__('asyncpg').InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute("INSERT INTO tank.tisan_request_events(tenant_id,event_id,request_id,kind,actor) VALUES($1,$2,$3,'requested','placeholder-user')", OTHER, uuid.uuid4(), second)
