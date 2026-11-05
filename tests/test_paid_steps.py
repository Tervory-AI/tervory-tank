"""Paid-rung invariants against disposable local Postgres; no provider traffic."""
import asyncio
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg
import pytest
import pytest_asyncio
from fastapi import HTTPException

import controls
import paid_steps as p

A = uuid.UUID('00000000-0000-4000-8000-000000000999')
B = uuid.UUID('00000000-0000-4000-8000-000000000998')
ROOT = Path(__file__).resolve().parents[1]
PRODUCT_TASKS = {'base':'base.extract','tiger':'agent.tiger.think','market_lab':'market.research',
    'rig':'rig.ask','tisan':'tisan.plan','radix':'agent.radix.think','zenas':'zenas.apply',
    'trigger':'trigger.write','autumbra':'agent.ghost.think','model':'command.turn'}


def command_schema_fixture(schema):
    # Apply the actual command tables and their later native-identity migration.
    # These focused tests intentionally omit unrelated platform schemas.
    tables = schema[schema.index('CREATE TABLE IF NOT EXISTS tank.command_threads'):schema.index('CREATE TABLE IF NOT EXISTS tank.command_builds')]
    issuer_column = next(line for line in schema.splitlines()
                         if line.startswith('ALTER TABLE tank.command_threads ADD COLUMN IF NOT EXISTS trigger_signin_issuer '))
    return tables + '\n' + issuer_column


@pytest_asyncio.fixture
async def database(monkeypatch):
    url = os.environ.get('PAID_STEPS_TEST_DATABASE_URL') or os.environ.get('POOL_SCHEMA_DATABASE_URL')
    if not url:
        pytest.skip('Select a disposable local Postgres with PAID_STEPS_TEST_DATABASE_URL')
    if urlsplit(url).hostname not in {'127.0.0.1', 'localhost', '::1'}:
        pytest.fail('Paid-step tests require explicit loopback Postgres')
    monkeypatch.setenv('DATABASE_URL', url)
    monkeypatch.setenv('LITELLM_MASTER_KEY', 'placeholder-litellm-key')
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-workspace-key')
    monkeypatch.setenv('LITELLM_URL', 'http://placeholder-litellm')
    admin = await asyncpg.connect(url)
    name = 'placeholder_paid_' + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    placeholder_dsn = urlsplit(url)._replace(path='/'+name).geturl()
    pool = await asyncpg.create_pool(placeholder_dsn,min_size=1,max_size=5)
    schema = (ROOT / 'tank/schema.sql').read_text().split('-- Paid ladder steps:', 1)[1].split('-- END PAID LADDER STEPS',1)[0]
    async with pool.acquire() as conn:
        await conn.execute('CREATE SCHEMA tank; CREATE TABLE tank.ledger(id uuid,tenant_id uuid); ALTER TABLE tank.ledger ENABLE ROW LEVEL SECURITY')
        await conn.execute(schema[schema.index('CREATE TABLE'):])
    monkeypatch.setattr(p, 'db', lambda: pool)
    async def master(**kwargs):
        if master.paused:
            raise HTTPException(503, 'placeholder master pause')
    master.paused = False
    monkeypatch.setattr(controls, 'refuse_paid', master)
    try:
        yield pool, master
    finally:
        await pool.close()
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


def run(tenant=A):
    return p.Run(tenant, uuid.uuid4(), p.fingerprint({'input':'placeholder'}))


async def admission(owner, tenant=A):
    return await p.admit(f'{owner}.placeholder.paid', tenant_id=tenant, owner=owner,
                         kind='placeholder', source='placeholder fixture', task=f'{owner}.placeholder')


@pytest.mark.asyncio
@pytest.mark.parametrize('owner', p.PRODUCTS)
async def test_every_product_ask_auto_and_master(database, owner):
    pool, master = database
    context = run()
    called = []
    async def invoke():
        result = await admission(owner)
        called.append('placeholder provider call')
        return result
    with p.run_scope(context):
        with pytest.raises(p.ApprovalRequired) as stopped:
            await invoke()
        assert not called
        row = await p.decide(A, stopped.value.approval_id, user='placeholder-admin', approve=True, reason='placeholder approved')
        assert row['state'] == 'approved'
        assert (await invoke())['authorization_mode'] == 'approved'
        assert len(called) == 1
        master.paused = True
        with pytest.raises(HTTPException) as blocked:
            await invoke()
        assert blocked.value.status_code == 503
        assert len(called) == 1
    master.paused = False
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto','placeholder-admin')", A, f'{owner}.placeholder.paid')
    with p.run_scope(run()):
        assert (await invoke())['authorization_mode'] == 'automatic'
    with p.run_scope(run(B)):
        with pytest.raises(p.ApprovalRequired):
            await admission(owner, B)
    master.paused = True
    with p.run_scope(run()):
        with pytest.raises(HTTPException):
            await invoke()
    assert len(called) == 2


@pytest.mark.asyncio
async def test_free_work_needs_no_context_or_control(database):
    _, master = database
    master.paused = True
    assert await p.admit('placeholder', tenant_id=A, owner='base', kind='code', source='placeholder', task='base.placeholder', paid=False) is None


@pytest.mark.asyncio
async def test_tenant_denial_and_immutable_decision(database):
    with p.run_scope(run()):
        with pytest.raises(p.ApprovalRequired) as stopped:
            await admission('base')
        with pytest.raises(HTTPException) as foreign:
            await p.decide(B, stopped.value.approval_id, user='placeholder-admin-b', approve=True, reason='placeholder')
        assert foreign.value.status_code == 404
        row = await p.decide(A, stopped.value.approval_id, user='placeholder-admin', approve=False, reason='placeholder not needed')
        assert row['reason'] == 'placeholder not needed'
        assert row['decided_at'].tzinfo is not None
        with pytest.raises(HTTPException) as denied:
            await admission('base')
        assert denied.value.status_code == 403
        with pytest.raises(HTTPException) as changed:
            await p.decide(A, stopped.value.approval_id, user='placeholder-admin', approve=True, reason='placeholder')
        assert changed.value.status_code == 409


@pytest.mark.asyncio
async def test_concurrent_ask_is_one_approval_and_request_is_bound(database):
    pool, _ = database
    context = run()
    async def attempt():
        with p.run_scope(context):
            try:
                await admission('base')
            except p.ApprovalRequired as exc:
                return exc.approval_id
    ids = await asyncio.gather(*(attempt() for _ in range(4)))
    assert len(set(ids)) == 1
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.paid_step_approvals WHERE tenant_id=$1', A) == 1
    with p.run_scope(p.Run(A, context.run_id, p.fingerprint('placeholder different input'))):
        with pytest.raises(HTTPException) as changed:
            await admission('base')
        assert changed.value.status_code == 409


@pytest.mark.asyncio
async def test_checkpoint_replays_results_and_refuses_uncertain_calls(database):
    context = run()
    calls = []
    async def provider():
        calls.append('placeholder')
        return {'content':'placeholder answer', 'ledger_id':'placeholder-receipt'}
    with p.run_scope(context):
        key = p.fingerprint('placeholder call')
        assert await p.checkpoint(key, provider) == await p.checkpoint(key, provider)
        assert len(calls) == 1
        async def crash():
            calls.append('placeholder uncertain')
            raise RuntimeError('placeholder lost response')
        key = p.fingerprint('placeholder uncertain')
        with pytest.raises(RuntimeError):
            await p.checkpoint(key, crash)
        with pytest.raises(HTTPException) as uncertain:
            await p.checkpoint(key, provider)
        assert uncertain.value.status_code == 409
        assert len(calls) == 2


@pytest.mark.asyncio
async def test_checkpoint_wait_is_committed_and_resumes_without_repaying(database):
    context = run()
    called = []
    with p.run_scope(context):
        async def first():
            called.append('placeholder earlier paid response')
            return {'answer':'placeholder cached response'}
        await p.checkpoint(p.fingerprint('placeholder earlier'), first)
        async def next_step():
            await admission('base')
            called.append('placeholder next paid response')
            return {'answer':'placeholder next'}
        key = p.fingerprint('placeholder next')
        with pytest.raises(p.ApprovalRequired) as stopped:
            await p.checkpoint(key, next_step)
        await p.decide(A, stopped.value.approval_id, user='placeholder-admin', approve=True, reason='placeholder approved')
        await p.checkpoint(p.fingerprint('placeholder earlier'), first)
        await p.checkpoint(key, next_step)
        assert called == ['placeholder earlier paid response','placeholder next paid response']


def test_model_seats_and_tasks_have_independent_switches():
    assert len({p.model_step(task, model) for task in ('base.extract','base.verify')
                for model in ('placeholder-cheap','placeholder-frontier')}) == 4
    assert p.product('agent.tisan.think') == 'tisan'
    assert p.product('ghost.explain') == 'autumbra'
    assert p.product('market.research') == 'market_lab'


@pytest.mark.asyncio
async def test_approval_pause_is_not_swallowed_by_skill_fallback(database):
    import httpx
    from fastapi import FastAPI
    app = FastAPI()
    app.add_middleware(p.ApprovalMiddleware)
    context = run()
    calls = []
    @app.post('/placeholder')
    async def skill():
        with p.run_scope(context):
            try:
                await admission('base')
                calls.append('placeholder paid dispatch')
            except Exception:
                calls.append('placeholder swallowed pause')
        return {'done': True}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        response = await client.post('/placeholder')
        assert response.status_code == 409
        assert response.json()['detail']['code'] == 'paid_step_approval_required'
        assert not calls
        await p.decide(A, uuid.UUID(response.json()['detail']['approval_id']), user='placeholder-admin', approve=True, reason='placeholder approved')
        assert (await client.post('/placeholder')).json() == {'done': True}
        assert calls == ['placeholder paid dispatch']


@pytest.mark.asyncio
async def test_chats_existing_confirm_card_approves_and_denies(database, monkeypatch):
    import command
    import httpx
    from fastapi import FastAPI
    pool, _ = database
    monkeypatch.setattr(command, 'db', lambda: pool)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'placeholder-admin')
    actor = command.Actor(A, 'placeholder-admin', True, tenant_admin=True)
    thread = uuid.uuid4()
    schema = (ROOT / 'tank/schema.sql').read_text()
    schema = command_schema_fixture(schema)
    async with pool.acquire() as conn:
        await conn.execute(schema)
    app = FastAPI()
    app.include_router(command.router)
    app.dependency_overrides[command.identity] = lambda: actor
    with p.run_scope(run()):
        with pytest.raises(p.ApprovalRequired) as stopped:
            await admission('base')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        response = await client.post('/v1/command/threads', json={'title':'placeholder paid work'})
        thread = response.json()['thread_id']
        response = await client.get(f'/v1/command/threads/{thread}')
        card = response.json()['cards'][0]
        assert card['card_id'] == str(stopped.value.approval_id)
        assert card['status'] == 'pending'
        assert card['kind'] == 'paid_run'
        assert card['tool'] == 'paid_steps.approve'
        assert (await client.post(f"/v1/command/cards/{card['card_id']}", json={'action':'confirm','reason':'placeholder approved'})).json()['status'] == 'confirmed'
    with p.run_scope(run()):
        with pytest.raises(p.ApprovalRequired) as stopped:
            await admission('base')
    await p.sync_cards(uuid.UUID(thread), actor)
    result = await p.resolve_card(uuid.UUID(thread), stopped.value.approval_id,
                                 command.CardAction(action='cancel',reason='placeholder budget reserved'), actor)
    assert result['status'] == 'cancelled'
    assert result['result']['reason'] == 'placeholder budget reserved'
    # A non-admin in the same tenant cannot use this card as authority.
    actor = command.Actor(A, 'placeholder-admin', False, tenant_admin=False)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', '')
    async with pool.acquire() as conn:
        await conn.execute('CREATE TABLE tank.tenant_squad(tenant_id uuid,agent text)')
    with pytest.raises(HTTPException) as denied:
        await p.resolve_card(uuid.UUID(thread), stopped.value.approval_id,
                             command.CardAction(action='confirm',reason='placeholder'), actor)
    assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_rls_refuses_cross_tenant_reads_and_writes(database):
    pool, _ = database
    with p.run_scope(run()):
        with pytest.raises(p.ApprovalRequired):
            await admission('base')
    role = 'placeholder_paid_' + uuid.uuid4().hex
    async with pool.acquire() as conn:
        await conn.execute(f'CREATE ROLE "{role}" NOLOGIN')
        try:
            await conn.execute(f'GRANT USAGE ON SCHEMA tank TO "{role}"')
            await conn.execute(f'GRANT SELECT,INSERT,UPDATE ON tank.paid_step_approvals TO "{role}"')
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE "{role}"')
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(B))
                assert await conn.fetchval('SELECT count(*) FROM tank.paid_step_approvals') == 0
                assert await conn.execute("UPDATE tank.paid_step_approvals SET state='approved' WHERE tenant_id=$1", A) == 'UPDATE 0'
        finally:
            await conn.execute(f'DROP OWNED BY "{role}"')
            await conn.execute(f'DROP ROLE "{role}"')


@pytest.mark.asyncio
async def test_base_skill_waits_then_resumes_through_existing_client(database, monkeypatch):
    import importlib.util
    from types import SimpleNamespace

    import httpx
    from fastapi import FastAPI, Request

    import paid_http
    import vendor_meter
    monkeypatch.syspath_prepend(str(ROOT / "agents/base"))
    from agents.base.room import SkillClient
    from chassis import paid_steps as room_approval
    pool, _ = database
    monkeypatch.setattr(room_approval, 'POLL_SECONDS', 0.01)
    monkeypatch.setenv('TANK_KEY_BASE', 'placeholder-room-key')
    spec = importlib.util.spec_from_file_location('placeholder_find_site', ROOT / 'tank/skills/base.find_site/1.7.1/run.py')
    skill = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(skill)
    dispatched = []
    async def provider(request):
        assert request.url.host == 'api.search.brave.com'
        dispatched.append('placeholder brave request')
        return httpx.Response(200, json={'web': {'results': [{'url':'https://placeholder.example/'}]}})
    async def reserve(request):
        receipt = uuid.uuid4()
        async with pool.acquire() as conn:
            await conn.execute('INSERT INTO tank.ledger(id,tenant_id) VALUES($1,$2)', receipt, A)
        request.extensions['vendor_receipt'] = (receipt, A, 'brave.search')
    monkeypatch.setattr(vendor_meter, 'request_hook', reserve)
    app = FastAPI()
    app.add_middleware(p.ApprovalMiddleware)
    run_id = uuid.uuid4()
    context = p.Run(A, run_id, p.fingerprint({'record':'placeholder'}))
    async with paid_http.Client(transport=httpx.MockTransport(provider),
                                event_hooks={'request':[controls.paid_host_hook]}) as vendor:
        @app.post('/v1/skala/base.find_site/run')
        async def execute(request: Request):
            body = await request.json()
            assert body['tenant_id'] == str(A)
            assert request.headers['x-tank-key'] == 'placeholder-room-key'
            assert body.get('paid_run_id', str(run_id)) == str(run_id)
            token = vendor_meter.current.set(vendor_meter.Run(A,'us-east','base','base.find_site@1.7.1',None,None))
            try:
                with p.run_scope(context):
                    urls = await skill._brave(SimpleNamespace(http=vendor,env={'BRAVE_API_KEY':'placeholder-brave-key'}), 'placeholder business')
                return {'urls':urls}
            finally:
                vendor_meter.current.reset(token)
        @app.get('/v1/paid-steps/approvals/{approval_id}')
        async def status(approval_id: uuid.UUID):
            async with pool.acquire() as conn:
                state = await conn.fetchval('SELECT state FROM tank.paid_step_approvals WHERE tenant_id=$1 AND id=$2',A,approval_id)
            return {'state':state}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://placeholder-tank') as client:
            skills = SkillClient(client,'http://placeholder-tank','placeholder-room-key')
            call = skills.bind({'base.find_site':'1.7.1'},False,str(A))
            task = asyncio.create_task(call('base.find_site',{'name':'placeholder business'}))
            try:
                pending = None
                for _ in range(100):
                    async with pool.acquire() as conn:
                        pending = await conn.fetchrow("SELECT * FROM tank.paid_step_approvals WHERE tenant_id=$1 AND state='pending'", A)
                    if pending:
                        break
                    await asyncio.sleep(0.01)
                assert pending is not None and not dispatched
                assert not task.done(), 'Base must be waiting, not failed'
                await p.decide(A,pending['id'],user='placeholder-admin',approve=True,reason='placeholder approve this step')
                result = await asyncio.wait_for(task,timeout=20)
                assert result['urls'] == ['https://placeholder.example/']
                assert dispatched == ['placeholder brave request']
                # Reusing the run replays the response without another reservation or request.
                assert await call('base.find_site',{'name':'placeholder business'}) == result
                assert len(dispatched) == 1
                async with pool.acquire() as conn:
                    receipt = await conn.fetchrow('SELECT paid_step_id,paid_step_mode FROM tank.ledger WHERE tenant_id=$1', A)
                assert dict(receipt) == {'paid_step_id':'base.find_site.brave','paid_step_mode':'approved'}
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task,return_exceptions=True)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def routing_pool():
    url = os.environ.get('PAID_STEPS_TEST_DATABASE_URL') or os.environ.get('POOL_SCHEMA_DATABASE_URL')
    if not url:
        pytest.skip('Select disposable local Postgres')
    assert urlsplit(url).hostname in {'localhost','127.0.0.1','::1'}
    admin = await asyncpg.connect(url)
    name = 'placeholder_paid_router_' + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    pool = await asyncpg.create_pool(urlsplit(url)._replace(path='/'+name).geturl(),min_size=1,max_size=5)
    try:
        async with pool.acquire() as conn:
            await conn.execute((ROOT / 'tank/schema.sql').read_text())
        yield pool
    finally:
        await pool.close()
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


@pytest_asyncio.fixture(loop_scope="module")
async def router_database(routing_pool, monkeypatch):
    monkeypatch.setenv('DATABASE_URL','postgresql://localhost/placeholder-unused')
    monkeypatch.setenv('LITELLM_MASTER_KEY','placeholder-litellm-key')
    monkeypatch.setenv('LITELLM_URL','http://placeholder-litellm')
    monkeypatch.setenv('TANK_API_KEY','placeholder-workspace-key')
    monkeypatch.setattr(p,'db',lambda:routing_pool)
    async def master(**kwargs):
        if master.paused:
            raise HTTPException(503,'placeholder master stop')
    master.paused = False
    monkeypatch.setattr(controls,'refuse_paid',master)
    return routing_pool, master


async def exercise_model_router(router_database, monkeypatch, owner, *, fail_primary=False, via_http=False):
    from unittest.mock import AsyncMock

    import httpx
    import main as tank
    client_class = httpx.AsyncClient
    pool, master = router_database
    tenant = uuid.uuid5(A, owner + str(fail_primary))
    monkeypatch.setenv('TANK_REGION','us-east')
    monkeypatch.delenv('TANK_PROVIDER_ALLOW',raising=False)
    monkeypatch.setattr(tank,'pool',lambda:pool)
    monkeypatch.setattr(tank,'_redis',None)
    policy = dict(model='placeholder-model',rung=1,priority='standard',system_prompt=None,
                  max_tokens_out=32,cache_scope='none',candidate_model=None,shadow_rate=0,
                  semantic_cache=False,fallbacks=[])
    if fail_primary:
        policy['fallbacks'] = ['placeholder-fallback']
    monkeypatch.setattr(tank,'load_policy',AsyncMock(return_value=policy))
    roster = [{'model_name':'placeholder-model','model_info':{'input_cost_per_token':0.000001,'output_cost_per_token':0.000002}}]
    roster.append({'model_name':'placeholder-fallback','model_info':{'input_cost_per_token':0.000001,'output_cost_per_token':0.000002}})
    monkeypatch.setattr(tank,'_roster_models',AsyncMock(return_value=roster))
    monkeypatch.setattr(tank,'_check_route_task',AsyncMock())
    calls = []
    class Gateway:
        def __init__(self,**kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self,*args):
            pass
        async def post(self,url,**kwargs):
            assert url == tank.LITELLM_URL + '/v1/chat/completions'
            assert kwargs['json']['disable_fallbacks'] is True
            calls.append(kwargs['json'])
            if fail_primary and kwargs['json']['model'] == 'placeholder-model':
                return httpx.Response(500,json={'error':'placeholder unavailable'})
            return httpx.Response(200,json={'choices':[{'message':{'content':'placeholder answer'},'finish_reason':'stop'}],
                                 'usage':{'prompt_tokens':5,'completion_tokens':5}},
                                 headers={'x-litellm-response-cost':'0.01','x-litellm-model-group':kwargs['json']['model']})
    monkeypatch.setattr(tank.httpx,'AsyncClient',Gateway)
    task_type = PRODUCT_TASKS[owner]
    req = tank.RouteRequest(tenant_id=tenant,agent=owner,task_type=task_type,home_region='us-east',
                            messages=[tank.Message(role='user',content='placeholder request')])
    async def invoke():
        if not via_http:
            return await tank.run_route(req)
        from fastapi import FastAPI
        app = FastAPI()
        app.add_middleware(p.ApprovalMiddleware)
        app.post('/v1/route')(tank.route)
        app.dependency_overrides[tank.require_key] = lambda: None
        async with client_class(transport=httpx.ASGITransport(app),base_url='http://placeholder-tank') as client:
            response = await client.post('/v1/route',json=req.model_dump(mode='json'))
        if response.status_code == 409:
            detail = response.json()['detail']
            assert detail['code'] == 'paid_step_approval_required'
            pause = p.ApprovalRequired(uuid.UUID(detail['approval_id']),detail['step_id'])
            pause.detail = detail
            raise pause
        if response.status_code != 200:
            raise HTTPException(response.status_code,response.json())
        return tank.RouteResponse.model_validate(response.json())
    with pytest.raises(p.ApprovalRequired) as stopped:
        await invoke()
    assert not calls
    req.paid_run_id = uuid.UUID(stopped.value.detail['run_id'])
    if via_http:
        import command
        from fastapi import FastAPI
        monkeypatch.setattr(command,'db',lambda:pool)
        app = FastAPI()
        app.include_router(command.router)
        actor = command.Actor(tenant,'placeholder-admin',False,tenant_admin=True)
        app.dependency_overrides[command.identity] = lambda: actor
        async with client_class(transport=httpx.ASGITransport(app),base_url='http://placeholder-tank') as client:
            opened = await client.post('/v1/command/threads',json={'title':'placeholder paid request'})
            assert opened.status_code == 200
            thread_id = opened.json()['thread_id']
            snapshot = await client.get('/v1/command/threads/'+thread_id)
            card = snapshot.json()['cards'][0]
            assert card['card_id'] == str(stopped.value.approval_id)
            assert card['kind'] == 'paid_run' and card['status'] == 'pending'
            assert task_type in card['summary'] and 'placeholder-model' in card['summary']
            confirmed = await client.post('/v1/command/cards/'+card['card_id'],json={'action':'confirm','reason':'placeholder approved'})
            assert confirmed.status_code == 200 and confirmed.json()['status'] == 'confirmed'
    else:
        await p.decide(tenant,stopped.value.approval_id,user='placeholder-admin',approve=True,reason='placeholder approved')
    if fail_primary:
        with pytest.raises(p.ApprovalRequired) as fallback:
            await invoke()
        assert len(calls) == 1
        assert fallback.value.step_id != stopped.value.step_id
        await p.decide(tenant,fallback.value.approval_id,user='placeholder-admin',approve=True,reason='placeholder fallback approved')
        first = await invoke()
        assert first.content == 'placeholder answer' and len(calls) == 2
        assert (await invoke()).ledger_id == first.ledger_id
        assert len(calls) == 2
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND outcome='failed' AND paid_step_mode='approved'",tenant) == 1
        return
    first = await invoke()
    assert first.content == 'placeholder answer' and len(calls) == 1
    assert (await invoke()).ledger_id == first.ledger_id
    assert len(calls) == 1
    async with pool.acquire() as conn:
        receipt = await conn.fetchrow('SELECT paid_step_id,paid_step_mode FROM tank.ledger WHERE tenant_id=$1 AND id=$2',tenant,first.ledger_id)
        assert receipt['paid_step_mode'] == 'approved'
        await conn.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto','placeholder-admin')",tenant,receipt['paid_step_id'])
    req.paid_run_id = uuid.uuid4()
    automatic = await invoke()
    assert automatic.rung == 1
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT paid_step_mode FROM tank.ledger WHERE tenant_id=$1 AND id=$2',tenant,automatic.ledger_id) == 'automatic'
    assert len(calls) == 2
    req.paid_run_id = uuid.uuid4()
    master.paused = True
    with pytest.raises(HTTPException) as paused:
        await invoke()
    assert paused.value.status_code == 503 and len(calls) == 2
    master.paused = False
    # The master stop refused before dispatch, so unpausing is not an uncertain retry.
    assert (await invoke()).content == 'placeholder answer'
    assert len(calls) == 3


@pytest.mark.parametrize('decision', ['approved', 'denied', 'foreign'])
def test_hermes_waits_only_for_its_tenant_and_never_writes_approval(monkeypatch, decision):
    import importlib.util
    import httpx
    spec = importlib.util.spec_from_file_location('placeholder_paid_sdk', ROOT / 'agents/_brain/paid_approval.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    approval_id = '00000000-0000-4000-8000-000000000997'
    def provider(request):
        calls.append((request.method, request.url.path))
        if request.method == 'GET':
            assert request.headers['X-Tank-Key'] == 'placeholder-room-key'
            return httpx.Response(200, json={'state': decision})
        if len(calls) == 1:
            return httpx.Response(409,json={'detail':{'code':'paid_step_approval_required',
                'approval_id':approval_id,'run_id':'00000000-0000-4000-8000-000000000996','tenant_id':str(B if decision == 'foreign' else A)}})
        return httpx.Response(200,json={'choices':[{'message':{'content':'placeholder answer'}}]})
    original = module.install('https://tank.example', 'placeholder-room-key', str(A), wait=lambda _:None)
    try:
        with httpx.Client(transport=httpx.MockTransport(provider)) as client:
            if decision == 'approved':
                assert client.post('https://tank.example/chat/completions',json={}).status_code == 200
                assert calls == [('POST','/chat/completions'),('GET','/v1/paid-steps/approvals/'+approval_id),('POST','/chat/completions')]
            else:
                with pytest.raises(RuntimeError):
                    client.post('https://tank.example/chat/completions',json={})
                assert len(calls) == (1 if decision == 'foreign' else 2)
    finally:
        httpx.Client.send = original


@pytest.mark.asyncio(loop_scope='module')
async def test_settings_require_admin_and_do_not_change_another_tenant(router_database, monkeypatch):
    database=router_database
    import httpx
    from fastapi import FastAPI
    import command
    actor = command.Actor(A,'placeholder-admin',False,tenant_admin=True)
    app = FastAPI()
    app.include_router(p.build_router())
    app.dependency_overrides[command.identity] = lambda: actor
    step = p.model_step('base.placeholder','placeholder-model')
    async with database[0].acquire() as conn:
        await p.register(conn,step,'base','model','placeholder fixture')
        await conn.execute("INSERT INTO tank.policy(tenant_id,task_type,model) VALUES($1,'base.placeholder','placeholder-model')",A)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://placeholder') as client:
        result = await client.put('/v1/command/paid-steps/'+step,json={'mode':'auto'})
        assert result.status_code == 200 and result.json()['mode'] == 'auto'
        actor = command.Actor(B,'placeholder-member',False,tenant_admin=False)
        assert (await client.put('/v1/command/paid-steps/'+step,json={'mode':'auto'})).status_code == 403
        assert (await client.get('/v1/command/paid-steps/approvals/pending')).status_code == 403
    async with database[0].acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.paid_step_settings WHERE tenant_id=$1',B) == 0


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.parametrize('owner', p.PRODUCTS)
async def test_real_model_router_per_product_ask_auto_master(router_database, monkeypatch, owner):
    await exercise_model_router(router_database,monkeypatch,owner)


@pytest.mark.asyncio(loop_scope='module')
async def test_configured_fallback_requires_its_own_approval_without_repaying_primary(router_database,monkeypatch):
    await exercise_model_router(router_database,monkeypatch,'base',fail_primary=True)


@pytest.mark.asyncio
async def test_continuation_resumes_once_and_failure_is_inspectable(database, monkeypatch):
    from unittest.mock import AsyncMock
    pool, _ = database
    with p.run_scope(run()):
        with pytest.raises(p.ApprovalRequired) as stopped:
            await admission('base')
    await p.save_background(stopped.value, {'kind':'tank.task','task_id':str(uuid.uuid4()),
        'request':{'tenant_id':str(A),'messages':[{'role':'user','content':'placeholder request'}]}})
    await p.decide(A,stopped.value.approval_id,user='placeholder-admin',approve=True,reason='placeholder approved')
    work = AsyncMock(side_effect=RuntimeError('placeholder unavailable'))
    monkeypatch.setattr(__import__('main'),'_run_task',work)
    with pytest.raises(RuntimeError):
        await p.resume(A,stopped.value.approval_id)
    await p.resume(A,stopped.value.approval_id)
    work.assert_awaited_once()
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT resume_status FROM tank.paid_step_approvals WHERE tenant_id=$1 AND id=$2',A,stopped.value.approval_id) == 'failed'


@pytest.mark.asyncio(loop_scope='module')
async def test_registry_lists_configured_seats_defaults_and_tenant_boundaries(router_database,monkeypatch):
    import httpx
    from fastapi import FastAPI
    import command
    pool, _ = router_database
    owner = uuid.uuid5(A,'placeholder-registry-owner')
    other = uuid.uuid5(B,'placeholder-registry-owner')
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.policy(tenant_id,task_type,rung,model) VALUES($1,'base.placeholder_private',1,'placeholder-private-model')",other)
        await conn.execute("INSERT INTO tank.policy(tenant_id,task_type,rung,model,fallbacks) VALUES($1,'tisan.placeholder_registry',1,'placeholder-primary',ARRAY['placeholder-fallback'])",owner)
    actor = command.Actor(owner,'placeholder-admin',False,tenant_admin=True)
    app = FastAPI()
    app.include_router(p.build_router())
    app.dependency_overrides[command.identity] = lambda: actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://placeholder') as client:
        result = await client.get('/v1/command/paid-steps')
        assert result.status_code == 200
        entries = {item['step_id']:item for item in result.json()['steps']}
        primary = p.model_step('tisan.placeholder_registry','placeholder-primary')
        assert entries[primary]['mode'] == 'ask'
        assert entries[primary]['task_type'] == 'tisan.placeholder_registry'
        assert entries[primary]['model'] == 'placeholder-primary'
        assert p.model_step('tisan.placeholder_registry','placeholder-fallback') in entries
        assert p.model_step('base.placeholder_private','placeholder-private-model') not in entries
        assert (await client.put('/v1/command/paid-steps/'+primary,json={'mode':'auto'})).status_code == 200
        assert (await client.put('/v1/command/paid-steps/'+primary,json={'mode':'invalid'})).status_code == 422
        actor = command.Actor(other,'placeholder-admin',False,tenant_admin=True)
        assert primary not in {item['step_id'] for item in (await client.get('/v1/command/paid-steps')).json()['steps']}
        assert (await client.put('/v1/command/paid-steps/'+primary,json={'mode':'auto'})).status_code==404


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.parametrize('host,suffix',[('api.search.brave.com','brave'),('maps.googleapis.com','places')])
async def test_each_vendor_http_boundary_asks_auto_runs_and_master_stops(router_database,monkeypatch,host,suffix):
    import httpx
    import main
    import paid_http
    import vendor_meter
    pool, master = router_database
    tenant = uuid.uuid5(A,'placeholder-vendor-'+suffix)
    monkeypatch.setattr(main,'pool',lambda:pool)
    calls=[]
    url = 'https://'+host+('/maps/api/place/textsearch/json' if suffix == 'places' else '/res/v1/web/search')
    async def provider(request):
        assert request.url.host == host
        calls.append(request.url.host)
        return httpx.Response(200,json={'status':'OK','placeholder':True})
    token = vendor_meter.current.set(vendor_meter.Run(tenant,'us-east','base','base.find_site@1.7.1',None,None))
    try:
        async with paid_http.Client(transport=httpx.MockTransport(provider),event_hooks={
                'request':[controls.paid_host_hook],'response':[vendor_meter.response_hook]}) as client:
            context = p.Run(tenant,uuid.uuid4(),p.fingerprint('placeholder-vendor-request'))
            with p.run_scope(context):
                with pytest.raises(p.ApprovalRequired) as stopped:
                    await client.get(url)
                assert not calls
                assert stopped.value.step_id == 'base.find_site.'+suffix
                await p.decide(tenant,stopped.value.approval_id,user='placeholder-admin',approve=True,reason='placeholder approved')
                assert (await client.get(url)).status_code == 200
                assert (await client.get(url)).status_code == 200
                assert len(calls) == 1
            async with pool.acquire() as conn:
                assert await conn.fetchval('SELECT paid_step_mode FROM tank.ledger WHERE tenant_id=$1',tenant) == 'approved'
                await conn.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto','placeholder-admin')",tenant,stopped.value.step_id)
            with p.run_scope(p.Run(tenant,uuid.uuid4(),context.request_hash)):
                assert (await client.get(url)).status_code == 200
            assert len(calls) == 2
            master.paused=True
            with p.run_scope(p.Run(tenant,uuid.uuid4(),context.request_hash)):
                with pytest.raises(HTTPException) as refused:
                    await client.get(url)
                assert refused.value.status_code == 503 and len(calls) == 2
    finally:
        vendor_meter.current.reset(token)


def test_free_model_requires_zero_tokens_and_no_paid_tools():
    assert p.free_model({'input_cost_per_token':0,'output_cost_per_token':0})
    assert not p.free_model({})
    assert not p.free_model({'input_cost_per_token':0,'output_cost_per_token':0,'search_fee_per_request':0.01})
    assert not p.free_model({'input_cost_per_token':0,'output_cost_per_token':0,'research_only':True})


@pytest.mark.asyncio
async def test_member_request_approval_reaches_admin_without_exposing_private_turn(database,monkeypatch):
    import command
    import httpx
    from fastapi import FastAPI
    pool, _ = database
    monkeypatch.setattr(command,'db',lambda:pool)
    schema = (ROOT/'tank/schema.sql').read_text()
    async with pool.acquire() as conn:
        await conn.execute(command_schema_fixture(schema))
        await conn.execute('CREATE TABLE tank.tenant_squad(tenant_id uuid,agent text)')
    actor = command.Actor(A,'placeholder-member',False,tenant_admin=False)
    app = FastAPI()
    app.include_router(command.router)
    app.dependency_overrides[command.identity] = lambda: actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://placeholder') as client:
        private = (await client.post('/v1/command/threads',json={'title':'placeholder private member turn'})).json()['thread_id']
        with p.run_scope(p.Run(A,uuid.uuid4(),p.fingerprint('placeholder private request'),actor.user_id,uuid.UUID(private))):
            with pytest.raises(p.ApprovalRequired) as stopped:
                await admission('base')
        actor = command.Actor(A,'placeholder-admin',False,tenant_admin=True)
        assert (await client.get('/v1/command/threads/'+private)).status_code == 404
        admin_thread = (await client.post('/v1/command/threads',json={'title':'placeholder administrator'})).json()['thread_id']
        response = await client.get('/v1/command/threads/'+admin_thread)
        card = response.json()['cards'][0]
        assert card['card_id'] == str(stopped.value.approval_id)
        assert 'placeholder private request' not in response.text
        confirmed = await client.post('/v1/command/cards/'+card['card_id'],json={'action':'confirm','reason':'placeholder approved'})
        assert confirmed.status_code == 200
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT thread_id,delivery_thread_id,state FROM tank.paid_step_approvals WHERE tenant_id=$1 AND id=$2',A,stopped.value.approval_id)
        assert row['thread_id'] == uuid.UUID(private)
        assert row['delivery_thread_id'] == uuid.UUID(admin_thread)
        assert row['state'] == 'approved'


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.parametrize('approve',[True,False])
async def test_background_task_pauses_and_resumes_or_records_denial(router_database,monkeypatch,approve):
    import main
    pool, _ = router_database
    monkeypatch.setattr(main,'pool',lambda:pool)
    tenant = uuid.uuid5(A,'placeholder-task-'+str(approve))
    task_id = uuid.uuid4()
    request = main.RouteRequest(tenant_id=tenant,agent='base',task_type='base.extract',
        messages=[main.Message(role='user',content='placeholder task input')])
    async with pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.tasks(id,tenant_id,created_by,agent,task_type,title,input)
            VALUES($1,$2,'placeholder-user','base','base.extract','placeholder task','[]')""",task_id,tenant)
    calls=[]
    async def route(req,task_id=None):
        context = p.Run(tenant,task_id,p.fingerprint(req.model_dump(exclude={'paid_run_id'})))
        with p.run_scope(context):
            approval = await p.admit('base.placeholder.task',tenant_id=tenant,owner='base',kind='model',
                source='placeholder task fixture',task='base.extract')
            calls.append('placeholder paid dispatch')
            ledger = uuid.uuid4()
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,rung) VALUES($1,$2,'base','base.extract','placeholder-model',1)",ledger,tenant)
            await p.attach_receipt(ledger,approval)
            return main.RouteResponse(ledger_id=ledger,model='placeholder-model',rung=1,
                content='placeholder task answer',tokens_in=1,tokens_out=1,cost_usd=0.01,latency_ms=1)
    monkeypatch.setattr(main,'run_route',route)
    await main._run_task(task_id,request)
    assert not calls
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT status FROM tank.tasks WHERE tenant_id=$1 AND id=$2',tenant,task_id) == 'queued'
        pending = await conn.fetchval('SELECT id FROM tank.paid_step_approvals WHERE tenant_id=$1 AND run_id=$2',tenant,task_id)
    await p.decide(tenant,pending,user='placeholder-admin',approve=approve,reason='placeholder task decision')
    if approve:
        await p.resume(tenant,pending)
        assert calls == ['placeholder paid dispatch']
    else:
        assert not calls
    async with pool.acquire() as conn:
        task = await conn.fetchrow('SELECT status,result,error FROM tank.tasks WHERE tenant_id=$1 AND id=$2',tenant,task_id)
        assert task['status'] == ('done' if approve else 'failed')
        assert task['result'] == ('placeholder task answer' if approve else None)
        if not approve:
            assert task['error'] == 'Paid step denied by tenant administrator'


@pytest.mark.asyncio
@pytest.mark.parametrize('approve',[True,False],ids=['approve','deny'])
async def test_direct_research_card_waits_and_resumes_once(database,monkeypatch,approve):
    import command
    import httpx
    from fastapi import FastAPI
    from unittest.mock import AsyncMock
    pool,_ = database
    monkeypatch.setattr(command,'db',lambda:pool)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS','placeholder-admin')
    actor = command.Actor(A,'placeholder-admin',True,tenant_admin=True)
    monkeypatch.setattr(command,'authorized_actor',AsyncMock(return_value=actor))
    monkeypatch.setattr(command,'refresh_action_receipts',AsyncMock())
    schema = (ROOT/'tank/schema.sql').read_text()
    async with pool.acquire() as conn:
        await conn.execute(command_schema_fixture(schema))
    app = FastAPI()
    app.include_router(command.router)
    app.dependency_overrides[command.identity] = lambda:actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://placeholder') as client:
        tid = uuid.UUID((await client.post('/v1/command/threads',json={'title':'placeholder research'})).json()['thread_id'])
        action = command.PlannedAction(tool='market_lab.research',arguments={'question':'placeholder research question'})
        async with command.editing(tid,actor) as (conn,row,state):
            card = await command.propose_action(conn,row,state,action,actor)
        card_id = card['card_id']
        calls = []
        async def dispatch(action,owner,*,paid_run_id):
            with p.run_scope(p.Run(owner.tenant_id,paid_run_id,p.fingerprint(action.model_dump()))):
                try:
                    await admission('market_lab')
                except p.ApprovalRequired as pause:
                    return 409,{'detail':pause.detail}
                calls.append('placeholder paid research')
                return 200,{'answer':'placeholder answer'}
        monkeypatch.setattr(command,'dispatch_action',dispatch)
        first = await command.execute_card(tid,actor,card_id,action)
        assert first['status'] == 'pending'
        assert not calls
        approval_id = uuid.UUID(first['paid_approval_id'])
        # Reconfirming the original action cannot dispatch around its approval.
        assert (await command.card_action(uuid.UUID(card_id),command.CardAction(action='confirm'),actor))['status'] == 'pending'
        decision = await p.decide(A,approval_id,user=actor.user_id,approve=approve,reason='placeholder decision')
        if approve:
            await p.resume(A,approval_id)
            await p.resume(A,approval_id)
            assert calls == ['placeholder paid research']
        else:
            assert decision['reason'] == 'placeholder decision'
            await p.sync_cards(tid,actor)
            assert not calls
        async with pool.acquire() as conn:
            row = await command.owned(conn,tid,actor)
        assert command.unpack(row['state'])['cards'][card_id]['status'] == ('confirmed' if approve else 'cancelled')


@pytest.mark.asyncio
async def test_bootstrap_tenant_role_can_backfill_registry_but_not_rewrite_audit(database):
    pool,_ = database
    role='placeholder_paid_role_'+uuid.uuid4().hex
    async with pool.acquire() as conn:
        await conn.execute(f'CREATE ROLE "{role}" NOLOGIN')
        try:
            await conn.execute(f'GRANT USAGE ON SCHEMA tank TO "{role}"')
            await p.bootstrap_access(conn,role)
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE "{role}"')
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)",str(A))
                await p.register(conn,'base.placeholder.role','base','model','placeholder',task='base.placeholder')
                await p.register(conn,'base.placeholder.role','base','model','placeholder',task='base.placeholder',model='placeholder-model')
                assert await conn.fetchval("SELECT model FROM tank.paid_steps WHERE step_id=$1",'base.placeholder.role')=='placeholder-model'
                assert not await conn.fetchval("SELECT has_table_privilege(current_user,'tank.paid_step_settings_log','UPDATE')")
        finally:
            await conn.execute(f'DROP OWNED BY "{role}"')
            await conn.execute(f'DROP ROLE "{role}"')


@pytest.mark.asyncio(loop_scope='module')
async def test_sdk_request_without_task_uses_opaque_resume_and_keeps_new_calls_distinct(router_database,monkeypatch):
    import agent_skills
    import httpx
    import main
    from fastapi import FastAPI
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    pool,_=router_database
    monkeypatch.setenv('TANK_KEY_BASE','placeholder-base-key')
    policy={'model':'placeholder-sdk-model','rung':1,'priority':'standard','max_tokens_out':256}
    rt=SimpleNamespace(pool=lambda:pool,load_policy=AsyncMock(return_value=policy),
        _roster_models=AsyncMock(return_value=[{'model_name':'placeholder-sdk-model','model_info':{
            'input_cost_per_token':0.001,'output_cost_per_token':0.001}}]),
        box_region=lambda:'us-east',model_call_refusal=lambda *a,**kw:None,
        graduate=main.graduate,LITELLM_URL='http://placeholder-sdk',LITELLM_MASTER_KEY='placeholder-sdk-key')
    original=httpx.AsyncClient
    calls=[]
    def gateway(request):
        value=__import__('json').loads(request.content)
        assert 'paid_run_id' not in value
        calls.append(value)
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'placeholder answer'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':1,'completion_tokens':1}},headers={'x-litellm-response-cost':'0.002'})
    monkeypatch.setattr(agent_skills.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(gateway)))
    app=FastAPI()
    app.add_middleware(p.ApprovalMiddleware)
    app.include_router(agent_skills.build_router(rt))
    headers={'X-Tank-Key':'placeholder-base-key','X-Tenant-ID':str(A),'X-Home-Region':'us-east'}
    body={'messages':[{'role':'user','content':'placeholder SDK request'}]}
    async with original(transport=httpx.ASGITransport(app),base_url='http://placeholder') as client:
        path='/v1/agents/base/chat/completions'
        waiting=await client.post(path,headers=headers,json=body)
        assert waiting.status_code==409 and not calls
        detail=waiting.json()['detail']
        await p.decide(A,uuid.UUID(detail['approval_id']),user='placeholder-admin',approve=True,reason='placeholder approved')
        resumed={**body,'paid_run_id':detail['run_id']}
        first=await client.post(path,headers=headers,json=resumed)
        assert first.status_code==200,first.text
        assert (await client.post(path,headers=headers,json=resumed)).json()==first.json()
        assert len(calls)==1
        distinct=await client.post(path,headers=headers,json=body)
        assert distinct.status_code==409 and distinct.json()['detail']['run_id']!=detail['run_id']
        assert (await client.post(path,headers=headers,json={**body,'paid_run_id':'placeholder-invalid'})).status_code==422


@pytest.mark.asyncio
async def test_resolved_card_history_does_not_hide_new_pending_approvals(database,monkeypatch):
    import command
    import httpx
    from fastapi import FastAPI
    pool,_=database
    monkeypatch.setattr(command,'db',lambda:pool)
    actor=command.Actor(A,'placeholder-admin',False,tenant_admin=True)
    schema=(ROOT/'tank/schema.sql').read_text()
    async with pool.acquire() as conn:
        await conn.execute(command_schema_fixture(schema))
        await p.register(conn,'base.placeholder.paid','base','model','placeholder')
    app=FastAPI()
    app.include_router(command.router)
    app.dependency_overrides[command.identity]=lambda:actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://placeholder') as client:
        tid=uuid.UUID((await client.post('/v1/command/threads',json={'title':'placeholder history'})).json()['thread_id'])
    async with command.editing(tid,actor) as (conn,row,state):
        for _ in range(105):
            key=uuid.uuid4()
            await conn.execute("""INSERT INTO tank.paid_step_approvals
                (id,tenant_id,run_id,step_id,request_hash,state,authorization_mode,delivery_thread_id)
                VALUES($1,$2,$3,'base.placeholder.paid',$4,'approved','automatic',$5)""",key,A,uuid.uuid4(),p.fingerprint({'placeholder':True}),tid)
            state['cards'][str(key)]={'card_id':str(key),'kind':'paid_run','tool':'paid_steps.approve','status':'confirmed','summary':'placeholder history'}
    with p.run_scope(run()):
        with pytest.raises(p.ApprovalRequired) as stopped:
            await admission('base')
    await p.sync_cards(tid,actor)
    async with pool.acquire() as conn:
        row=await command.owned(conn,tid,actor)
    assert command.unpack(row['state'])['cards'][str(stopped.value.approval_id)]['status']=='pending'


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [b'', b'not JSON', b'[]', b'{"detail":"ordinary conflict"}'])
async def test_room_preserves_non_approval_conflicts_without_polling(body):
    import httpx
    from chassis import paid_steps as room_approval
    calls = []
    def conflict(request):
        calls.append(request)
        assert request.method == 'POST'
        return httpx.Response(409, content=body)
    async with httpx.AsyncClient(transport=httpx.MockTransport(conflict)) as client:
        response = await room_approval.post(client, 'http://placeholder-tank', '/v1/route',
            {'tenant_id': str(A)}, {'x-tank-key': 'placeholder-room-key'})
    assert response.status_code == 409 and response.content == body
    assert len(calls) == 1
