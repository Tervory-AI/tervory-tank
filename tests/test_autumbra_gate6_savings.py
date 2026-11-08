import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from agents.ghost import dogfood_hf, savings
from agents.ghost.app import Tank
from agents.ghost.threat_queue import ThreatPayloadQueue

ROOT = Path(__file__).resolve().parents[1]
A, B = '10000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000002'


def test_recorded_prompt_token_budget_and_cached_code_answer():
    from agent_skills import input_tokens
    rows = dogfood_hf.load_synthetic_fixtures()
    old = ('You are Autumbra Watch (propose-only). Summarize these SYNTHETIC SIEM '
           'fixture lines for dogfood. Do not invent client data. Reply with a short '
           'JSON object: {"summary": str, "suspect_site": str|null}.\n\nFIXTURES:\n'
           + '\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n')
    def tokens(prompt):
        return input_tokens({'messages': [{'role': 'system', 'content': 'Autumbra Watch dogfood. Synthetic fixtures only.'},
                                          {'role': 'user', 'content': prompt}]})
    assert (tokens(old), tokens(dogfood_hf.build_watch_prompt(rows))) == (446, 205)
    dogfood_hf._summary.cache_clear()
    first = dogfood_hf.dogfood_watch_triage()
    second = dogfood_hf.dogfood_watch_triage()
    assert first['summary_local'] == second['summary_local'] == {'events': {'http_upload': 1, 'auth_fail': 1, 'waf_match': 1},
                                                               'sites': ['coolify.tervory.com', 'panel.tervory.com']}
    assert dogfood_hf._summary.cache_info().hits == 1
    assert first['cost_usd'] == second['cost_usd'] == 0


@pytest.mark.asyncio
async def test_dogfood_replaces_model_with_cached_code_and_tank_receipt(monkeypatch):
    monkeypatch.setenv('AUTUMBRA_HF_LIVE', '1')
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    calls = []
    async def call(self, method, path, body):
        calls.append((method, path, body))
        return {'ledger_id': body['receipt_id'], 'tenant_id': body['tenant_id'],
                'receipt_id': body['receipt_id'], 'cost_usd': 0, 'would_have_cost_usd': .001}
    monkeypatch.setattr(Tank, 'call', call)
    prompt=dogfood_hf.build_watch_prompt(dogfood_hf.load_synthetic_fixtures())
    dogfood_hf._summary.cache_clear()
    results=[await dogfood_hf.call_tank_inference(prompt) for _ in range(2)]
    assert results[0]['content']==results[1]['content']
    assert results[0]['ledger_id']!=results[1]['ledger_id']  # One receipt for each run.
    assert dogfood_hf._summary.cache_info().hits==1
    for result in results:
        assert result['tokens_in']==result['tokens_out']==result['cost_usd']==0
        assert result['rung']==3 and result['model']=='code'
    for method,path,body in calls:
        assert (method,path)==('POST','/v1/ghost/autumbra/savings')
        assert body['tenant_id']==dogfood_hf.PLATFORM_TENANT
        assert not {'model','api_key','provider','messages'} & body.keys()
    async def invalid(*args): return {'ledger_id': 'not-a-receipt'}
    monkeypatch.setattr(Tank, 'call', invalid)
    with pytest.raises(dogfood_hf.HfDogfoodError, match='with a receipt'):
        await dogfood_hf.call_tank_inference(prompt)


@pytest.mark.asyncio
async def test_offline_receipt_price_is_tenant_scoped_cached_and_never_replays_action(tmp_path):
    q = ThreatPayloadQueue(tmp_path)
    q.write_receipt({'id': 'one', 'tenant_id': A, 'outcome': 'blocked', 'applied': True, 'secret': 'private'})
    local = q.list_receipts()[0]
    assert local['cost_usd'] == 0 and local['would_have_cost_usd'] is None
    tank = SimpleNamespace(call=AsyncMock(return_value={'tenant_id': A, 'receipt_id': 'one', 'would_have_cost_usd': .001,
                                                       'baseline_status': 'priced'}))
    priced = await savings.price_receipt(tank, local, A)
    assert priced['would_have_cost_usd'] == .001 and priced['cost_usd'] == 0
    assert 'private' not in json.dumps(tank.call.call_args.args)
    await savings.price_receipt(tank, priced, A)
    tank.call.assert_awaited_once()
    with pytest.raises(ValueError, match='another tenant'):
        await savings.price_receipt(tank, priced, B)
    for price in [-1, float('nan'), True, '0.5']:
        tank.call.return_value = {'tenant_id': A, 'receipt_id': 'two', 'would_have_cost_usd': price}
        receipt = await savings.price_receipt(tank, {'id': 'two', 'tenant_id': A}, A)
        assert receipt['would_have_cost_usd'] is None and receipt['baseline_status'] == 'unavailable'
    tank.call.side_effect = RuntimeError('private upstream')
    receipt = await savings.price_receipt(tank, {'id': 'two', 'tenant_id': A}, A)
    assert receipt['cost_usd'] == 0 and receipt['baseline_status'] == 'unavailable'
    assert 'private' not in json.dumps(receipt)


@pytest.fixture
def catalog():
    import command_tools.autumbra as module
    return module


def test_window_mobile_and_mcp_share_catalog_validation_and_scope(catalog):
    import command, mcp_server
    owner = command.Actor(UUID(A), 'owner', False, tenant_admin=True)
    member = command.Actor(UUID(A), 'member', False)
    founder = command.Actor(UUID(A), 'founder', True)
    names = {tool['name']: tool for tool in mcp_server.tools(owner)['tools']}
    assert set(catalog.TENANT_ADMIN_TOOLS) <= names.keys()
    for action in catalog.CLIENT_ACTIONS:
        assert 'autumbra.' + action not in command.allowed_tools(member)
    for action in catalog.WATCH_ACTIONS:
        assert 'autumbra.' + action not in names
        assert 'autumbra.' + action in command.allowed_tools(founder)
    for name in ('autumbra.receipts', 'autumbra.settings'):
        assert names[name]['annotations']['readOnlyHint']
        value = command.validate_action(command.PlannedAction(tool=name, arguments={}), owner)
        assert command.adapter_request(value, owner)[2:] == ({}, None)
        with pytest.raises((ValueError, HTTPException)):
            command.validate_action(command.PlannedAction(tool=name, arguments={'tenant_id': B}), owner)
    assert 'autumbra.shield.undo' in command.CONFIRMED
    assert 'autumbra.settings.set' in command.CONFIRMED


@pytest.mark.asyncio
async def test_explicit_tool_plan_uses_code_and_leaves_receipt(catalog, monkeypatch):
    import command, trigger_routes
    actor = command.Actor(UUID(A), 'owner', False, tenant_admin=True)
    monkeypatch.setattr(trigger_routes, 'code_receipt', AsyncMock(return_value=UUID(B)))
    result = await catalog.code_plan(actor, [{'role':'user', 'content':'autumbra.receipts'}], None)
    assert json.loads(result.content)['actions'] == [{'tool':'autumbra.receipts', 'arguments':{}}]
    assert result.ledger_id == UUID(B)
    assert await catalog.code_plan(actor, [{'role':'user', 'content':'unrelated'}], None) is None
    with pytest.raises((ValueError, HTTPException)):
        await catalog.code_plan(actor, [{'role':'user', 'content':'autumbra.receipts {"tenant_id":"'+B+'"}'}], None)


def test_receipt_view_real_cost_unknown_cost_and_empty_shape():
    subprocess.run(['node', 'tests/autumbra_gate6_savings.cjs'], cwd=ROOT, check=True, timeout=60)


from test_train1 import database

__all__ = ["database"]  # pytest fixture re-export


@pytest.mark.asyncio
async def test_real_postgres_prices_code_without_inventing_billed_tokens_and_reuses_receipt(database, monkeypatch):
    pool, core = database
    import autumbra_savings as module
    async with pool.acquire() as conn:
        # Use an explicit test-only reporting policy; production invents no baseline.
        await conn.execute("""INSERT INTO tank.policy(task_type,rung,model,priority,cache_scope)
            VALUES('ghost.savings',1,'sol','standard','none') ON CONFLICT DO NOTHING""")
        await conn.execute("""INSERT INTO tank.proof_prices(model,family,input_usd,output_usd,active)
            VALUES('sol','openai',0.000001,0.000002,true) ON CONFLICT(model) DO UPDATE
            SET family='openai',input_usd=0.000001,output_usd=0.000002,active=true""")
    body = module.SavingsRequest(tenant_id=A, receipt_id='recorded-one', reference={'action':'block_ip','outcome':'applied'})
    first = await module.quote(core, body)
    second = await module.quote(core, body)
    assert first == second and first['cost_usd'] == 0 and first['would_have_cost_usd'] > 0
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM tank.ledger WHERE tenant_id=$1', UUID(A))
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1', UUID(A)) == 1
        assert row['tokens_in'] == row['tokens_out'] == row['cost_usd'] == 0
        expected = first['reference_tokens_in'] * .000001 + first['reference_tokens_out'] * .000002
        assert float(row['baseline_cost_usd']) == pytest.approx(expected, abs=.000001)
        assert first['would_have_cost_usd'] == float(row['baseline_cost_usd'])
    # Same identifier in another tenant creates a distinct receipt; an explicit
    # attempt to reuse the first tenant's ledger UUID is denied and rolled back.
    other = await module.quote(core, body.model_copy(update={'tenant_id': UUID(B)}))
    assert other['ledger_id'] != first['ledger_id']
    with pytest.raises(HTTPException) as error:
        await module.quote(core, module.SavingsRequest(tenant_id=B, receipt_id=first['ledger_id'], reference=body.reference))
    assert error.value.status_code == 409
    with pytest.raises(HTTPException):
        await module.quote(core, body.model_copy(update={'reference': {'outcome': 'different'}}))
    with pytest.raises(HTTPException):
        await module.quote(core, body.model_copy(update={'reference': {'raw_log': 'private'}}))
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.proof_prices SET active=false WHERE model='sol'")
    missing = await module.quote(core, body.model_copy(update={'receipt_id':'unpriced'}))
    assert missing['would_have_cost_usd'] is None and missing['baseline_status'] == 'unpriced'


@pytest.mark.asyncio
@pytest.mark.parametrize('action,args,method,path', [
    ('settings', {}, 'GET', '/ghost/autumbra/settings'),
    ('hands', {}, 'GET', '/ghost/autumbra/hands'),
    ('hands.set', {'hand':'cloudflare','connected':True}, 'POST', '/ghost/autumbra/hands'),
    ('settings.set', {'shield_mode':'Never'}, 'POST', '/ghost/autumbra/settings'),
    ('receipts', {}, 'GET', '/ghost/autumbra/receipts/weekly/'+A),
    ('shield.approve', {'site':'shop.example','prior_receipt_id':'receipt'}, 'POST', '/ghost/autumbra/queue/approve'),
    ('shield.undo', {'site':'shop.example','prior_receipt_id':'receipt'}, 'POST', '/ghost/autumbra/queue/undo'),
    ('look', {'target':'workspace'}, 'POST', '/look'),
    ('incidents', {}, 'GET', '/incidents'),
    ('resolve', {'incident':B,'cause':'application_bug','fix':'reviewed_pr_deployed'}, 'POST', '/incidents/'+B+'/resolve'),
    ('shields', {}, 'GET', '/ghost/shields'),
    ('shields.raise', {'shield':B}, 'POST', '/ghost/shields/'+B+'/raise'),
    ('shields.undo', {'shield':B}, 'POST', '/ghost/shields/'+B+'/undo'),
])
async def test_tools_execute_same_room_routes_with_auth_confirm_and_receipts(catalog, monkeypatch, action, args, method, path):
    import command, ghost_routes, trigger_routes, trigger_commands
    import autumbra_savings as savings_module
    module = ghost_routes
    owner = command.Actor(UUID(A), 'owner', action in catalog.WATCH_ACTIONS, tenant_admin=True)
    async def identity(request):
        if request.headers.get('x-tank-key') != 'placeholder-key' or request.headers.get('x-tervory-user') != 'owner':
            raise HTTPException(401)
        return owner
    monkeypatch.setattr(command, 'identity', identity)
    monkeypatch.setattr(trigger_routes, 'code_receipt', AsyncMock(return_value=UUID(B)))
    confirmations = []
    monkeypatch.setattr(trigger_commands, 'confirmation', lambda actor, tool, values: confirmations.append((actor,tool,dict(values))))
    async def room(m, r, p, **kwargs):
        assert r == 'ghost'
        if action == 'settings.set' and m == 'GET':
            assert kwargs['params'] == {'tenant_id':A}
            return httpx.Response(200,json={'settings':{'tenant_id':A,'watched_hosts':['shop.example']}})
        assert (m,p) == (method,path)
        if action in ('settings','settings.set','shield.approve','shield.undo','hands','hands.set'):
            scoped = kwargs['params'] if method == 'GET' else kwargs['body']
            assert scoped['tenant_id'] == A
            if action == 'settings.set': assert scoped['watched_hosts'] == ['shop.example']
        return httpx.Response(200,json={'outcome':'recorded','tenant_id':A})
    monkeypatch.setattr(module, "call_room", AsyncMock(side_effect=room))
    monkeypatch.setattr(module, "runtime", lambda: None)
    monkeypatch.setattr(savings_module,'quote',AsyncMock(return_value={'cost_usd':0,'would_have_cost_usd':.001,'tenant_id':A}))
    app = FastAPI(); app.include_router(module.router)
    adapter = command.ADAPTERS['autumbra.'+action]
    headers={'x-tank-key':'placeholder-key','x-tervory-user':'owner'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://offline') as client:
        route='/v1/ghost/autumbra/tools/'+action
        assert (await client.request(adapter.method,route)).status_code == 401
        response=await client.request(adapter.method,route,headers=headers,**({'params':args} if adapter.method=='GET' else {'json':args}))
        assert response.status_code == 200, response.text
        assert response.json()['ledger_id'] == B and response.json()['would_have_cost_usd'] == .001
        before=module.call_room.await_count
        injected={**args,'tenant_id':B}
        response=await client.request(adapter.method,route,headers=headers,**({'params':injected} if adapter.method=='GET' else {'json':injected}))
        assert response.status_code == 422 and module.call_room.await_count == before
    assert bool(confirmations) == ('autumbra.'+action in catalog.CONFIRMED)


@pytest.mark.asyncio
async def test_scheduled_savings_refresh_persists_once_excludes_fixtures_and_does_not_call_enforce(monkeypatch,tmp_path):
    from agents.ghost import app as watch
    from agents.ghost.store import Store
    from agents.ghost.client_settings import ClientAutumbraSettings, save_settings
    monkeypatch.setenv('THREAT_PAYLOAD_QUEUE_ROOT',str(tmp_path/'queues'))
    monkeypatch.setenv('TANK_KEY','placeholder-key')
    monkeypatch.delenv('TENANT_ID',raising=False)
    store=Store(tmp_path/'watch.sqlite')
    save_settings(store,ClientAutumbraSettings(tenant_id=A))
    queue=watch.watch_threat_queue(A)
    queue.write_receipt({'id':'real','tenant_id':A,'outcome':'blocked'})
    queue.write_receipt({'id':'fake','tenant_id':A,'fixture':True})
    queue.write_receipt({'id':'wrong','tenant_id':B,'outcome':'blocked'})
    calls=[]
    def reply(request):
        assert request.url.path=='/v1/ghost/autumbra/savings'
        calls.append(json.loads(request.content))
        return httpx.Response(200,json={'tenant_id':A,'receipt_id':'real','would_have_cost_usd':.001,'baseline_status':'priced'})
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
            app=SimpleNamespace(state=SimpleNamespace(store=store,http=client))
            assert await watch.refresh_receipt_savings(app)=={'priced':1,'unavailable':0}
            assert await watch.refresh_receipt_savings(app)=={'priced':0,'unavailable':0}
        assert len(calls)==1 and calls[0]['tenant_id']==A
        assert next(row for row in queue.list_receipts() if row['id']=='real')['would_have_cost_usd']==.001
    finally:
        store.close()


def test_owned_model_entrypoints_have_no_direct_provider_client():
    import ast
    forbidden={'openai','anthropic','litellm','huggingface_hub','google.generativeai','google.genai'}
    for path in (ROOT/'agents/ghost').rglob('*.py'):
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                assert not {name.name for name in node.names} & forbidden, path
            elif isinstance(node,ast.ImportFrom):
                assert node.module not in forbidden, path


@pytest.mark.asyncio
async def test_pricing_corridor_requires_watch_key_before_recording(monkeypatch):
    import ghost_routes
    import autumbra_savings as savings_module
    module = ghost_routes
    async def require_key(request, key):
        if key=='placeholder-watch': return 'ghost'
        if key=='placeholder-other': return 'base'
        raise HTTPException(401)
    core=SimpleNamespace(require_key=require_key)
    monkeypatch.setattr(ghost_routes,'runtime',lambda:core)
    app=FastAPI();app.include_router(module.router)
    monkeypatch.setattr(savings_module,'quote',AsyncMock(return_value={'cost_usd':0,'would_have_cost_usd':None}))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://offline') as client:
        body={'tenant_id':A,'receipt_id':'receipt','reference':{'outcome':'blocked'}}
        for key,status in [('',401),('placeholder-other',403),('placeholder-watch',200)]:
            response=await client.post('/v1/ghost/autumbra/savings',headers={'X-Tank-Key':key},json=body)
            assert response.status_code==status
    savings_module.quote.assert_awaited_once()


def test_code_run_receipts_are_durable_and_never_cross_tenants(tmp_path):
    from agents.ghost.store import Store
    path=tmp_path/'watch.sqlite'
    store=Store(path)
    first=store.record_run(A,'inventory','checked')
    store.record_run(B,'monitor','unavailable')
    assert first['cost_usd']==0 and first['would_have_cost_usd'] is None
    with pytest.raises(ValueError): store.save_run(B,first)
    store.close()
    store=Store(path)
    try:
        assert store.run_receipts(A)==[first]
        assert store.run_receipts(B)[0]['kind']=='monitor'
        assert store.run_receipts(dogfood_hf.PLATFORM_TENANT)==[]
    finally: store.close()


@pytest.mark.asyncio
async def test_code_job_receipt_view_has_costs_without_an_undo_block_action(monkeypatch,tmp_path):
    from agents.ghost import app as watch
    from agents.ghost.store import Store
    monkeypatch.setenv('TANK_KEY','placeholder-key')
    monkeypatch.setenv('AUTUMBRA_UNDO_TOKEN_SECRET','placeholder-signing-key')
    monkeypatch.setenv('THREAT_PAYLOAD_QUEUE_ROOT',str(tmp_path/'queues'))
    store=Store(tmp_path/'watch.sqlite')
    receipt=store.record_run(A,'settings_change','saved')
    receipt['would_have_cost_usd']=.001
    watch.watch_threat_queue(A).write_receipt(receipt)
    app=watch.create_app();app.state.store=store
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://offline') as client:
            response=await client.get('/ghost/autumbra/receipts/weekly/'+A,headers={'X-Tank-Key':'placeholder-key'})
        assert response.status_code==200
        row=response.json()['receipts'][0]
        assert row['cost_usd']==0 and row['would_have_cost_usd']==.001
        assert row['url']==''
    finally:store.close()


@pytest.mark.asyncio
async def test_legacy_diagnostic_keeps_current_tank_route(monkeypatch):
    from agents.ghost.app import Tank
    monkeypatch.setenv('AUTUMBRA_HF_LIVE','1')
    monkeypatch.setenv('TANK_KEY','placeholder-room-key')
    calls=[]
    ledger='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
    async def call(self,method,path,body):
        calls.append((method,path,body))
        return {'ledger_id':ledger,'content':'Fixture summary','cost_usd':0}
    monkeypatch.setattr(Tank,'call',call)
    result=await dogfood_hf.call_tank_inference('Synthetic events only')
    assert result['ledger_id']==ledger
    assert len(calls)==1 and calls[0][:2]==('POST','/v1/route')
    assert calls[0][2]['task_type']=='reason.brief' and calls[0][2]['agent']=='ghost'
    assert 'model' not in calls[0][2]
    monkeypatch.delenv('AUTUMBRA_HF_LIVE')
    with pytest.raises(dogfood_hf.HfDogfoodError,match='STOPPED'):
        await dogfood_hf.call_tank_inference('Synthetic events only')
    assert len(calls)==1


@pytest.mark.asyncio
async def test_malformed_code_fixture_never_falls_back_to_model(monkeypatch):
    from agents.ghost.app import Tank
    monkeypatch.setenv('AUTUMBRA_HF_LIVE','1')
    monkeypatch.setenv('TANK_KEY','placeholder-room-key')
    call=AsyncMock(side_effect=AssertionError('Malformed fixtures must never dispatch'))
    monkeypatch.setattr(Tank,'call',call)
    for raw in ('not-json', '{}', '[1]'):
        with pytest.raises(dogfood_hf.HfDogfoodError,match='with a receipt'):
            await dogfood_hf.call_tank_inference(dogfood_hf.PROMPT_PREFIX+raw)
    call.assert_not_awaited()
