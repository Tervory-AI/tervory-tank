"""Offline routing, token replay, native receipts and Command/MCP parity."""
import ast
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

import httpx
from fastapi import FastAPI, HTTPException
import pytest
import pytest_asyncio

import command
import mcp_server
from agents.tisan import builder, savings
from test_command import command_pool as command_pool
from test_tisan_requests import runtime as runtime, brief, confirmed, journal_row, client as client

ROOT = Path(__file__).resolve().parents[1]
TENANT = UUID('11111111-1111-4111-8111-111111111111')
OTHER = UUID('22222222-2222-4222-8222-222222222222')
FIXTURES = json.loads((ROOT/'tests/fixtures/tisan_gate6_plans.json').read_text())


@pytest.mark.asyncio
async def test_recorded_plans_count_real_bpe_before_and_after():
    contract = builder.manifest()
    before = 0
    calls = []
    async def route(tenant, task, messages):
        assert task == 'tisan.plan'
        calls.append(copy.deepcopy(messages))
        return {'content': json.dumps(FIXTURES['cases'][0]['response'])}
    tank = SimpleNamespace(route=route)
    for case in FIXTURES['cases']:
        messages = [{'role': 'system', 'content': FIXTURES['baseline_prefix'] + json.dumps(contract)},
                    {'role': 'user', 'content': case['request']}]
        before += savings.tokens(messages) + savings.tokens(case['response'])
        assert await builder.make_plan({'request': case['request']}, case['tenant'], contract, tank) == case['response']
    after = sum(savings.tokens(messages) + savings.tokens(FIXTURES['cases'][0]['response']) for messages in calls)
    assert len(calls) == 2  # First tenant, then foreign tenant; JSON/repeat use code.
    assert (before, after) == (12434, 2714)
    print(f'GATE6_TOKENS before={before} after={after} encoding=cl100k reference input+output')


@pytest.mark.asyncio
async def test_cache_is_tenant_contract_bound_copied_expiring_and_bounded(monkeypatch):
    tank = SimpleNamespace(route=AsyncMock(return_value={'content': json.dumps(FIXTURES['cases'][0]['response'])}))
    contract = builder.manifest()
    first = await builder.make_plan({'request': 'one page'}, str(TENANT), contract, tank)
    first['pages'].clear()
    assert (await builder.make_plan({'request': 'one page'}, str(TENANT), contract, tank))['pages']
    assert tank.route.await_count == 1
    await builder.make_plan({'request': 'one page'}, str(OTHER), contract, tank)
    changed = copy.deepcopy(contract)
    changed['schema'] += '.revision'
    await builder.make_plan({'request': 'one page'}, str(TENANT), changed, tank)
    assert tank.route.await_count == 3
    for key, (_, value) in tank._tisan_plan_cache.items():
        tank._tisan_plan_cache[key] = (0, value)
    await builder.make_plan({'request': 'one page'}, str(TENANT), contract, tank)
    assert tank.route.await_count == 4
    for number in range(130):
        await builder.make_plan({'request': f'one page {number}'}, str(TENANT), contract, tank)
    assert len(tank._tisan_plan_cache) == 128


@pytest.mark.asyncio
async def test_code_parses_json_and_never_caches_errors_or_approval_requests():
    tank = SimpleNamespace(route=AsyncMock(side_effect=RuntimeError('approval required')))
    contract = builder.manifest()
    value = FIXTURES['cases'][0]['response']
    assert await builder.make_plan({'request': json.dumps(value)}, str(TENANT), contract, None) == value
    for invalid in ('{broken', '{"pages": []}'):
        with pytest.raises(ValueError):
            await builder.make_plan({'request': invalid}, str(TENANT), contract, tank)
    for _ in range(2):
        with pytest.raises(RuntimeError, match='approval required'):
            await builder.make_plan({'request': 'one page'}, str(TENANT), contract, tank)
    assert tank.route.await_count == 2
    assert not tank._tisan_plan_cache


@pytest.mark.asyncio
async def test_invalid_model_repair_is_short_and_bounded():
    tank = SimpleNamespace(route=AsyncMock(return_value={'content': 'x' * 30000}))
    with pytest.raises(ValueError, match='invalid plan after retry'):
        await builder.make_plan({'request': 'one page'}, str(TENANT), builder.manifest(), tank)
    assert tank.route.await_count == 2
    repair = tank.route.call_args_list[1].args[2]
    assert len(repair[-2]['content']) <= 4096 and len(repair[-1]['content']) < 600


def test_all_owned_model_work_uses_tank_and_receipt_memories_are_not_embedded():
    calls = []
    for path in (ROOT/'agents/tisan').glob('*.py'):
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, 'module', '') or ''
                names = [module] + [item.name for item in getattr(node, 'names', [])]
                assert not any(name.split('.')[0] in {'openai', 'anthropic', 'ollama', 'litellm', 'google.generativeai'} for name in names)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'route':
                calls.append((path.name, ast.unparse(node.func.value)))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'remember':
                assert any(k.arg == 'index' and isinstance(k.value, ast.Constant) and k.value.value is False for k in node.keywords)
        assert not any(host in source for host in ('api.openai.com', 'api.anthropic.com', 'generativelanguage.googleapis.com'))
    assert calls == [('builder.py', 'tank')]


@pytest_asyncio.fixture
async def receipts_db(command_pool):
    async with command_pool.acquire() as conn:
        from chassis.db import ensure_schema
        await ensure_schema(conn, 'tisan')
        await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
        await conn.execute((ROOT/'agents/tisan/schema.sql').read_text())
        await conn.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES('sol','openai',0.000001,0.000003)")
    return command_pool


@pytest.mark.asyncio
async def test_every_job_kind_code_zero_failure_refusal_and_empty_tenant(receipts_db):
    for kind in ('ping', 'scaffold', 'figma', 'pipeline', 'build', 'archive'):
        for value in ({'ok': True}, {'ok': False, 'refused': True}, {'ok': False, 'missing_settings': ['FIGMA_TOKEN']}):
            ctx = SimpleNamespace(tenant_id=str(TENANT), job_id=str(uuid4()), input={'kind': kind})
            result = await savings.run(AsyncMock(return_value=value), ctx, receipts_db, kind)
            receipt = result['receipt']
            assert receipt['cost_usd'] == 0 and receipt['baseline_cost_usd'] > 0
            assert receipt['saved_usd'] == receipt['baseline_cost_usd']
            async with receipts_db.acquire() as conn:
                assert await conn.fetchval('SELECT count(*) FROM agent_tisan.run_receipts WHERE tenant_id=$1 AND id=$2', TENANT, UUID(receipt['ledger_id'])) == 1
    async with receipts_db.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_tisan.run_receipts WHERE tenant_id=$1', OTHER) == 0


@pytest.mark.asyncio
async def test_model_spend_cache_receipts_retries_scope_and_no_double_billing(receipts_db):
    route_id = uuid4()
    async with receipts_db.acquire() as conn:
        await conn.execute("INSERT INTO tank.ledger(id,tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out) VALUES($1,$2,'us-east','tisan','tisan.plan',1,'sol',0.0001,30,10)", route_id, TENANT)
    tank = SimpleNamespace(route=AsyncMock(return_value={'content': json.dumps(FIXTURES['cases'][0]['response']), 'ledger_id': str(route_id)}))
    ctx = SimpleNamespace(tenant_id=str(TENANT), job_id=str(uuid4()), input={'request': 'one page'})
    async def plan(owned):
        return await builder.make_plan(owned.input, owned.tenant_id, builder.manifest(), tank)
    first = await savings.run(plan, ctx, receipts_db, 'build')
    assert first['receipt']['cost_usd'] == 0.0001
    assert first['receipt']['tokens_in'] == 30 and first['receipt']['tokens_out'] == 10
    second = await savings.run(plan, ctx, receipts_db, 'build')  # Durable same-job reconciliation.
    assert second['ledger_id'] == first['ledger_id'] and second['receipt']['cost_usd'] == 0.0001
    ctx.job_id = str(uuid4())
    cached = await savings.run(plan, ctx, receipts_db, 'build')
    assert cached['receipt']['cost_usd'] == 0 and cached['receipt']['tokens_in'] == 0
    assert cached['receipt']['baseline_cost_usd'] > 0
    assert tank.route.await_count == 1
    async with receipts_db.acquire() as conn:
        assert float(await conn.fetchval('SELECT sum(cost_usd) FROM tank.ledger WHERE tenant_id=$1', TENANT)) == 0.0001
        with pytest.raises(ValueError, match='outside tenant'):
            await savings.complete(conn, OTHER, uuid4(), 'build', {}, {}, ids=[route_id])
        records = [dict(await conn.fetchrow('SELECT * FROM tank.ledger WHERE tenant_id=$1 AND id=$2', TENANT, UUID(first['ledger_id'])))]
        measured = await savings.overlay(conn, TENANT, records)
        assert measured[0]['cost_usd'] == 0.0001
        assert measured[0]['baseline_cost_usd'] > 0
        assert (await savings.overlay(conn, OTHER, records))[0]['cost_usd'] == 0
        with pytest.raises(ValueError, match='input changed'):
            await savings.complete(conn, TENANT, UUID(ctx.job_id), 'build', {'changed': True}, {})


@pytest.mark.asyncio
async def test_unknown_provider_spend_is_pending_and_exception_is_private(receipts_db):
    ctx = SimpleNamespace(tenant_id=str(TENANT), job_id=str(uuid4()), input={})
    async def failed(owned):
        savings.routing()
        raise TimeoutError('private provider text')
    with pytest.raises(TimeoutError):
        await savings.run(failed, ctx, receipts_db, 'build')
    async with receipts_db.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM agent_tisan.run_receipts WHERE tenant_id=$1', TENANT)
        assert row['cost_usd'] is None and row['uncertain']
        assert 'private provider text' not in str(dict(row))
        await conn.execute('DELETE FROM tank.proof_prices')
        receipt = await savings.complete(conn, TENANT, uuid4(), 'figma', {}, {})
        assert receipt['cost_usd'] == 0 and receipt['baseline_cost_usd'] is None
        assert receipt['saved_usd'] is None


@pytest.fixture
def tank_patch(tmp_path, monkeypatch):
    for name in ('command.py', 'tisan_requests.py', 'tisan_pipeline.py'):
        path = tmp_path/'tank'/name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes((ROOT/'vendor/tervory-tank/tank'/name).read_bytes())
    subprocess.run(['git', 'apply', '--exclude=tests/registry_frozen.golden', '--check', str(ROOT/'tank-patches/gate6.patch')], cwd=tmp_path, check=True)
    subprocess.run(['git', 'apply', '--exclude=tests/registry_frozen.golden', str(ROOT/'tank-patches/gate6.patch')], cwd=tmp_path, check=True)
    # Execute the actual changed functions with the existing native runtime.
    tree = ast.parse((tmp_path/'tank/command.py').read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name in {'record_receipts', 'get_thread', 'task_receipts'}]
    for node in nodes:
        node.decorator_list = []
    namespace = dict(command.__dict__)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'gate6_command_patch', 'exec'), namespace)
    for name in ('record_receipts', 'get_thread', 'task_receipts'):
        monkeypatch.setattr(command, name, namespace[name])
    spec = importlib.util.spec_from_file_location('gate6_tisan_requests', tmp_path/'tank/tisan_requests.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    import tisan_requests
    monkeypatch.setattr(tisan_requests, 'build_router', module.build_router)
    monkeypatch.setattr(tisan_requests, 'build_result', module.build_result)
    return namespace, module


def test_mcp_exposes_same_main_actions_and_auth_as_window_mobile(runtime):
    for founder, admin in ((True, False), (False, True), (False, False)):
        actor = command.Actor(TENANT, 'placeholder-founder' if founder else 'placeholder-user', founder,
            frozenset({'tisan'}), tenant_admin=admin)
        tools = {t['name']: t for t in mcp_server.tools(actor)['tools']}
        for name in ('tisan.request', 'tisan.preview', 'tisan.feedback', 'tisan.handover'):
            assert (name in tools) == (founder or admin)
        assert ('tisan.build' in tools) == founder
        if admin:
            assert tools['tisan.preview']['annotations']['readOnlyHint'] is True
            assert tools['tisan.request']['annotations']['readOnlyHint'] is False
            with pytest.raises(HTTPException):
                command.validate_action(command.PlannedAction(tool='tisan.request', arguments={**brief(), 'tenant_id': str(OTHER)}), actor)


@pytest.mark.asyncio
async def test_native_command_and_mcp_use_saved_costs_day_zero_and_foreign_denial(tank_patch, client, receipts_db, runtime):
    http, pool, journal, room = client
    runtime.app = FastAPI()
    runtime.app.include_router(command.router)
    runtime.app.include_router(tank_patch[1].build_router())
    # All these fixtures share the same disposable native Command pool.
    assert pool is receipts_db
    created = await http.post('/v1/command/threads', json={})
    thread = created.json()['thread_id']
    actor = command.Actor(TENANT, 'placeholder-admin', False, frozenset({'tisan'}), tenant_admin=True)
    empty = await command.get_thread(UUID(thread), actor)
    assert empty['receipts'] == []
    proposed = await http.post(f'/v1/command/threads/{thread}/actions', json={'tool': 'tisan.request', 'arguments': brief()})
    card = proposed.json()['card_id']
    response = await http.post('/v1/command/cards/' + card, json={'action': 'confirm'})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['result']['receipt']['cost_usd'] == 0
    evidence = await command.get_thread(UUID(thread), actor)
    receipt = next(r for r in evidence['receipts'] if r['step_id'] == card)
    assert receipt['cost_usd'] == 0 and receipt['baseline_cost_usd'] > 0
    assert 'model' not in receipt and 'baseline_model' not in receipt
    foreign = command.Actor(OTHER, actor.user_id, False, frozenset({'tisan'}), tenant_admin=True)
    with pytest.raises(HTTPException) as error:
        await command.get_thread(UUID(thread), foreign)
    assert error.value.status_code == 404
    journal_row(journal, 1)
    preview = await mcp_server.call_tool({'name': 'tisan.preview', 'arguments': {'slug': brief()['slug']}}, actor, {'thread_id': UUID(thread)})
    preview_data = json.loads(preview['content'][0]['text'])
    assert preview_data['result']['build'] == 1
    assert preview_data['receipts'][0]['cost_usd'] == 0
    assert preview_data['receipts'][0]['baseline_cost_usd'] > 0
    # MCP calls the same native validation/proposal/Confirm corridor, with the
    # same receipts. Mutations remain pending until the existing Confirm UI.
    reply = await mcp_server.call_tool({'name': 'tisan.feedback', 'arguments': {'slug': brief()['slug'], 'text': 'recorded correction'}}, actor, {'thread_id': UUID(thread)})
    payload = json.loads(reply['content'][0]['text'])
    assert payload['status'] == 'pending'
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.tisan_request_events WHERE tenant_id=$1', TENANT) == 1
    feedback = await confirmed(http, 'tisan.feedback', {'slug': brief()['slug'], 'text': 'recorded correction'})
    assert feedback.json()['receipt']['cost_usd'] == 0
    assert feedback.json()['receipt']['baseline_cost_usd'] > 0
    journal_row(journal, 2, sha='b' * 40)
    handover = await confirmed(http, 'tisan.handover', {'slug': brief()['slug']})
    assert handover.json()['status'] == 'accepted'
    assert handover.json()['receipt']['cost_usd'] == 0
    assert handover.json()['receipt']['baseline_cost_usd'] > 0


@pytest.mark.asyncio
async def test_model_repair_receipt_keeps_both_charges(receipts_db):
    ids = [uuid4(), uuid4()]
    async with receipts_db.acquire() as conn:
        for identifier in ids:
            await conn.execute("INSERT INTO tank.ledger(id,tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out) VALUES($1,$2,'us-east','tisan','tisan.plan',1,'sol',0.0001,30,10)", identifier, TENANT)
    tank = SimpleNamespace(route=AsyncMock(side_effect=[
        {'content': '{}', 'ledger_id': str(ids[0])},
        {'content': json.dumps(FIXTURES['cases'][0]['response']), 'ledger_id': str(ids[1])}]))
    ctx = SimpleNamespace(tenant_id=str(TENANT), job_id=str(uuid4()), input={'request': 'one page'})
    async def execute(owned):
        return await builder.make_plan(owned.input, owned.tenant_id, builder.manifest(), tank)
    result = await savings.run(execute, ctx, receipts_db, 'build')
    assert result['receipt']['cost_usd'] == 0.0002
    assert result['receipt']['tokens_in'] == 60 and result['receipt']['tokens_out'] == 20


@pytest.mark.asyncio
async def test_confirmed_request_and_pipeline_share_operation_without_receipt_collision(receipts_db):
    operation = uuid4()
    async with receipts_db.acquire() as conn:
        request = await savings.complete(conn, TENANT, operation, 'request', brief(), {'status': 'requested'})
        pipeline = await savings.complete(conn, TENANT, operation, 'pipeline', {'brief': brief()}, {'status': 'done'})
        assert request['ledger_id'] != pipeline['ledger_id']
        assert UUID(pipeline['ledger_id']) == savings.run_id(TENANT, operation, 'pipeline')
        assert await conn.fetchval('SELECT count(*) FROM agent_tisan.run_receipts WHERE tenant_id=$1', TENANT) == 2


@pytest.mark.asyncio
async def test_receipt_rls_rejects_cross_tenant_rows(receipts_db):
    async with receipts_db.acquire() as conn:
        for tenant in (TENANT, OTHER):
            await savings.complete(conn, tenant, uuid4(), 'figma', {}, {})
        role = 'gate6_' + uuid4().hex
        await conn.execute(f'CREATE ROLE "{role}" NOLOGIN')
        try:
            await conn.execute(f'GRANT USAGE ON SCHEMA agent_tisan TO "{role}"')
            await conn.execute(f'GRANT SELECT ON agent_tisan.run_receipts TO "{role}"')
            for tenant in (TENANT, OTHER):
                async with conn.transaction():
                    await conn.execute(f'SET LOCAL ROLE "{role}"')
                    await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(tenant))
                    rows = await conn.fetch('SELECT DISTINCT tenant_id FROM agent_tisan.run_receipts')
                    assert [dict(row) for row in rows] == [{'tenant_id': tenant}]
        finally:
            await conn.execute(f'DROP OWNED BY "{role}"')
            await conn.execute(f'DROP ROLE "{role}"')


@pytest.mark.asyncio
async def test_long_build_receipt_reaches_existing_founder_card_once(tank_patch, client, receipts_db, runtime):
    http, pool, _, _ = client
    actor = command.Actor(TENANT, 'placeholder-founder', True)
    headers = {'X-Tervory-User': actor.user_id}
    thread = (await http.post('/v1/command/threads', json={}, headers=headers)).json()['thread_id']
    proposed = await http.post(f'/v1/command/threads/{thread}/actions', headers=headers,
        json={'tool': 'tisan.build', 'arguments': brief()})
    assert proposed.status_code == 200, proposed.text
    card_id = proposed.json()['card_id']
    job = uuid4()
    async with pool.acquire() as conn:
        receipt = await savings.complete(conn, TENANT, job, 'build', {'name': 'Recorded build'}, {'ok': True})
        row = await conn.fetchrow('SELECT state FROM tank.command_threads WHERE tenant_id=$1 AND thread_id=$2', TENANT, UUID(thread))
        state = command.unpack(row['state'])
        state['cards'][card_id].update(status='confirmed', result={'kind': 'build', 'status': 'queued', 'job_id': str(job)})
        await conn.execute('UPDATE tank.command_threads SET state=$3::jsonb WHERE tenant_id=$1 AND thread_id=$2', TENANT, UUID(thread), json.dumps(state))
    def respond(request):
        assert request.url.params['tenant_id'] == str(TENANT)
        assert request.headers['X-Tervory-Tenant'] == str(TENANT)
        return httpx.Response(200, json={'id': str(job), 'tenant_id': str(TENANT), 'kind': 'build', 'status': 'done',
            'result': {'ok': True, 'build': 1, 'ledger_id': receipt['ledger_id'], 'receipt': receipt}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as corridor:
        runtime._http = corridor
        first = await command.get_thread(UUID(thread), actor)
        second = await command.get_thread(UUID(thread), actor)
    assert first['cards'][0]['result']['build'] == 1
    assert first['cards'][0]['receipt_status'] == 'recorded'
    assert len(first['receipts']) == len(second['receipts']) == 1
    assert first['receipts'][0]['cost_usd'] == 0 and first['receipts'][0]['baseline_cost_usd'] > 0
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.command_receipt_links WHERE tenant_id=$1 AND ledger_id=$2', TENANT, UUID(receipt['ledger_id'])) == 1


@pytest.mark.asyncio
async def test_worker_does_nothing_until_receipt_migration_is_ready(command_pool):
    handler = AsyncMock()
    ctx = SimpleNamespace(tenant_id=str(TENANT), job_id=str(uuid4()), input={})
    with pytest.raises(RuntimeError, match='receipt store unavailable'):
        await savings.run(handler, ctx, command_pool, 'build')
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_room_without_tank_database_access_records_through_authenticated_corridor(tank_patch, receipts_db, runtime, monkeypatch):
    source = Path(tank_patch[1].__file__).with_name('tisan_pipeline.py')
    spec = importlib.util.spec_from_file_location('gate6_receipt_corridor', source)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    app = FastAPI()
    app.include_router(module.build_router(), prefix='/v1/command/tisan')
    runtime.pool = lambda: receipts_db
    headers = {'X-Tank-Key': 'placeholder-room', 'X-Tervory-Tenant': str(TENANT), 'X-Tervory-Region': 'us-east'}
    monkeypatch.setenv('TANK_KEY', 'placeholder-room')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-tank') as corridor:
        # The production room gets only its own schema, not price/ledger grants.
        role = 'gate6_room_' + uuid4().hex
        async with receipts_db.acquire() as conn:
            await conn.execute(f'CREATE ROLE "{role}" NOLOGIN')
            await conn.execute(f'GRANT USAGE ON SCHEMA agent_tisan TO "{role}"')
            await conn.execute(f'GRANT SELECT,INSERT,UPDATE ON agent_tisan.run_receipts TO "{role}"')
            try:
                operation = uuid4()
                async with conn.transaction():
                    await conn.execute(f'SET LOCAL ROLE "{role}"')
                    await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(TENANT))
                    assert not await conn.fetchval("SELECT has_schema_privilege(current_user,'tank','USAGE')")
                    monkeypatch.delenv('TANK_URL', raising=False)
                    pending = await savings.remote(conn, TENANT, operation, 'build', {'request': 'recorded'}, {'ok': True})
                    assert pending['cost_usd'] == 0 and pending['baseline_cost_usd'] is None
                # Local pending evidence commits before Tank reconciles it.
                # A fake transport is the only outbound route; real HTTP is off.
                original = httpx.AsyncClient
                class Proxy:
                    async def __aenter__(self): return corridor
                    async def __aexit__(self, *args): return False
                monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: Proxy())
                monkeypatch.setenv('TANK_URL', 'http://placeholder-tank')
                async with conn.transaction():
                    await conn.execute(f'SET LOCAL ROLE "{role}"')
                    await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(TENANT))
                    result = await savings.remote(conn, TENANT, operation, 'build', {'request': 'recorded'}, {'ok': True})
                    assert result['ledger_id'] == pending['ledger_id']
                    assert result['cost_usd'] == 0 and result['baseline_cost_usd'] > 0
                from agents.tisan import upstream
                real_post = upstream.post
                sent = []
                async def lost_ack(*args, **kwargs):
                    sent.append(kwargs['json']['operation_id'])
                    await real_post(*args, **kwargs)
                    raise httpx.ReadError('recorded lost acknowledgement')
                monkeypatch.setattr(upstream, 'post', lost_ack)
                async with conn.transaction():
                    await conn.execute(f'SET LOCAL ROLE "{role}"')
                    await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(TENANT))
                    recovered = await savings.remote(conn, TENANT, uuid4(), 'build', {}, {'ok': True})
                    assert recovered['cost_usd'] == 0 and recovered['baseline_cost_usd'] > 0
                assert len(sent) == 1
                monkeypatch.setattr(upstream, 'post', real_post)
                monkeypatch.setattr(httpx, 'AsyncClient', original)
                body = {'tenant_id': str(TENANT), 'operation_id': str(uuid4()), 'kind': 'build',
                    'measurement': {'input_hash': 'a' * 64, 'tokens_in': 20, 'tokens_out': 10}, 'route_ids': []}
                for override in ({'X-Tank-Key': 'placeholder-wrong'}, {'X-Tervory-Tenant': str(OTHER)}, {'X-Tervory-Region': 'za'}):
                    assert (await corridor.post('/v1/command/tisan/pipeline/receipts', headers={**headers, **override}, json=body)).status_code == 403
                foreign = uuid4()
                await conn.execute("INSERT INTO tank.ledger(id,tenant_id,region,agent,task_type,rung,model,cost_usd) VALUES($1,$2,'us-east','tisan','tisan.plan',1,'sol',0.01)", foreign, OTHER)
                denied = await corridor.post('/v1/command/tisan/pipeline/receipts', headers=headers, json={**body, 'route_ids': [str(foreign)]})
                assert denied.status_code == 409
                invalid = await corridor.post('/v1/command/tisan/pipeline/receipts', headers=headers, json={**body, 'measurement': {**body['measurement'], 'tokens_in': -1}})
                assert invalid.status_code == 422
            finally:
                await conn.execute(f'DROP OWNED BY "{role}"')
                await conn.execute(f'DROP ROLE "{role}"')


@pytest.mark.asyncio
@pytest.mark.parametrize('model_started', [False, True])
async def test_tank_timeout_leaves_pending_local_evidence_without_masking_completed_code(receipts_db, monkeypatch, model_started):
    real_timeout = asyncio.timeout
    monkeypatch.setattr(asyncio, 'timeout', lambda seconds: real_timeout(seconds / 100))
    monkeypatch.setenv('TANK_URL', 'http://placeholder-tank')
    monkeypatch.setenv('TANK_KEY', 'placeholder-room')
    sent = []
    async def slow_post(*args, **kwargs):
        sent.append(kwargs)
        await asyncio.sleep(1)
        raise AssertionError('the bounded call must time out first')
    class Client:
        async def __aenter__(self): return SimpleNamespace(post=slow_post)
        async def __aexit__(self, *args): return False
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: Client())
    async def finished(ctx):
        if model_started:
            savings.routing()
        return {'ok': True}
    ctx = SimpleNamespace(tenant_id=str(TENANT), job_id=str(uuid4()), input={})
    result = await savings.run(finished, ctx, receipts_db, 'build', recorder=savings.remote)
    assert result['ok'] is True
    assert result['receipt']['cost_usd'] == (None if model_started else 0)
    assert result['receipt']['baseline_cost_usd'] is None
    assert len(sent) == 1
