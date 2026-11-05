"""Proposed server code executed in memory; actual HTTP and disposable SQL."""
import json
import sys
import types
import uuid
from unittest.mock import AsyncMock
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from test_command import runtime, TENANT, OTHER  # noqa: F401
import test_command
from opli_agent.proposal import proposed_files

@pytest.fixture
def proposed(monkeypatch, runtime):
    files = proposed_files()
    if 'tank/command_stream.py' in files:
        stream = types.ModuleType('command_stream'); stream.__file__ = 'proposal:command_stream.py'
        monkeypatch.setitem(sys.modules, 'command_stream', stream)
        exec(compile(files['tank/command_stream.py'], stream.__file__, 'exec'), stream.__dict__)
    sessions = types.ModuleType('code_sessions'); sessions.__file__ = 'proposal:code_sessions.py'
    monkeypatch.setitem(sys.modules, 'code_sessions', sessions)
    exec(compile(files['tank/code_sessions.py'], sessions.__file__, 'exec'), sessions.__dict__)
    module = types.ModuleType('command'); module.__file__ = 'proposal:command.py'
    monkeypatch.setitem(sys.modules, 'command', module)
    exec(compile(files['tank/command.py'], module.__file__, 'exec'), module.__dict__)
    if 'tank/plugins.py' in files:
        from pathlib import Path
        plugins = types.ModuleType('plugins'); plugins.__file__ = str(Path(test_command.command.__file__).resolve().with_name('plugins.py'))
        monkeypatch.setitem(sys.modules, 'plugins', plugins)
        exec(compile(files['tank/plugins.py'], plugins.__file__, 'exec'), plugins.__dict__)
    monkeypatch.setattr(test_command, 'command', module)
    runtime._storage_mask = lambda value: value
    runtime.list_models = AsyncMock(return_value=[{'name':'placeholder-allowed','input_usd_per_m':1,'output_usd_per_m':2,'upstream':'never expose'}, {'name':'placeholder-denied','input_usd_per_m':3}])
    runtime.model_call_refusal = lambda text, model, **kwargs: 'refused' if model == 'placeholder-denied' else None
    return module

@pytest_asyncio.fixture
async def gate_api(proposed, runtime, monkeypatch):
    generator = test_command.command_pool.__wrapped__()
    pool = await anext(generator)
    try:
        files = proposed_files()
        if 'tank/schema.sql' in files:
            schema = files['tank/schema.sql'].split('-- BEGIN opli\n')[1].split('-- END opli')[0]
            await pool.execute(schema)
            await pool.execute(schema)
        monkeypatch.setattr(proposed, 'db', lambda: pool)
        app = FastAPI(); app.include_router(proposed.router)
        headers = {'x-tank-key': runtime.TANK_API_KEY, 'x-tervory-tenant': str(TENANT), 'x-tervory-user':'founder'}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture',headers=headers) as client:
            yield client, pool
    finally:
        await generator.aclose()

async def answer(proposed, pool, monkeypatch, content):
    ledger = uuid.uuid4()
    await pool.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd) VALUES($1,$2,'orchestrator','command.code','placeholder-allowed',0.004)", ledger, TENANT)
    stub = AsyncMock(return_value=types.SimpleNamespace(ledger_id=ledger,content=json.dumps(content)))
    monkeypatch.setattr(proposed,'route_code',stub)
    return stub

@pytest.mark.asyncio
async def test_roster_filters_customer_and_pin_rechecks_before_write(gate_api, proposed, runtime, monkeypatch):
    client,pool = gate_api
    founder=await client.get('/v1/command/code-models'); assert founder.status_code==200
    assert {r['name'] for r in founder.json()}=={'placeholder-allowed','placeholder-denied'}
    member={'x-tervory-user':'member'}
    roster=await client.get('/v1/command/code-models',headers=member)
    assert [r['name'] for r in roster.json()]==['placeholder-allowed']; assert 'upstream' not in roster.text
    thread=(await client.post('/v1/command/threads',headers=member,json={})).json()['thread_id']
    route=await answer(proposed,pool,monkeypatch,{'answer':'done','requests':[]})
    denied=await client.post(f'/v1/command/threads/{thread}/code-turn',headers=member,json={'text':'hello','model':'placeholder-denied'})
    assert denied.status_code==403 and 'placeholder-denied' not in denied.text; route.assert_not_called()
    assert await pool.fetchval('SELECT count(*) FROM tank.tasks')==0
    accepted=await client.post(f'/v1/command/threads/{thread}/code-turn',headers=member,json={'text':'hello','model':'placeholder-allowed'})
    assert accepted.status_code==200,accepted.text
    assert route.call_args.args[2]=='placeholder-allowed'
    assert accepted.json()['turn']=={'model':'placeholder-allowed','cost_usd':0.004}
    runtime.model_call_refusal=lambda *args,**kwargs:'revoked'
    denied=await client.post(f'/v1/command/threads/{thread}/code-turn',headers=member,json={'text':'again','model':'placeholder-allowed'})
    assert denied.status_code==403; assert route.await_count==1

@pytest.mark.asyncio
async def test_sessions_redact_persist_and_enforce_owner_tenant_issuer(gate_api, proposed, monkeypatch):
    client,pool=gate_api
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    secret='ghp_'+'placeholder'*3
    await answer(proposed,pool,monkeypatch,{'answer':'done\n'+secret,'requests':[]})
    result=await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'task\n'+secret,'history':[{'kind':'project','content':'private project notes'}],'tool_results':[{'name':'read_file','output':'private source canary'}]})
    assert result.status_code==200,result.text
    saved=await client.get('/v1/command/code-sessions/'+thread); assert saved.status_code==200
    assert [i['kind'] for i in saved.json()['history']]==['user','assistant']; assert '[redacted]' in saved.text
    state=await pool.fetchval('SELECT state::text FROM tank.command_threads WHERE thread_id=$1',uuid.UUID(thread))
    assert secret not in state and 'private source canary' not in state and 'private project notes' not in state
    assert saved.json()['cost_usd']==0.004
    assert [r['thread_id'] for r in (await client.get('/v1/command/code-sessions')).json()]==[thread]
    for headers in [{'x-tervory-user':'other'},{'x-tervory-tenant':str(OTHER)}]:
        assert (await client.get('/v1/command/code-sessions/'+thread,headers=headers)).status_code==404
        assert (await client.get('/v1/command/code-sessions',headers=headers)).json()==[]
    await pool.execute("UPDATE tank.command_threads SET trigger_signin_issuer='https://placeholder.invalid' WHERE thread_id=$1",uuid.UUID(thread))
    assert (await client.get('/v1/command/code-sessions/'+thread)).status_code==404
    assert (await client.get('/v1/command/code-sessions')).json()==[]

@pytest.mark.asyncio
async def test_plan_rejects_mutations_and_mode_switch_in_continuation(gate_api, proposed, monkeypatch):
    client,pool=gate_api
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    route=await answer(proposed,pool,monkeypatch,{'answer':'proposal','requests':[{'name':'run_command','arguments':{'command':'echo forbidden'}}]})
    request_id=str(uuid.uuid4())
    data={'text':'plan','mode':'plan','prompt_id':request_id}
    bad=await client.post(f'/v1/command/threads/{thread}/code-turn',json=data)
    assert bad.status_code==422; assert json.loads(await pool.fetchval('SELECT state::text FROM tank.command_threads WHERE thread_id=$1',uuid.UUID(thread)))['cards']=={}
    assert 'Read only' in route.call_args.args[1][0]['content']
    mismatch=await client.post(f'/v1/command/threads/{thread}/code-turn',json={**data,'continuation':True,'mode':'auto-edit'})
    assert mismatch.status_code==409; assert route.await_count==1
    await answer(proposed,pool,monkeypatch,{'answer':'A proposed plan','requests':[]})
    good=await client.post(f'/v1/command/threads/{thread}/code-turn',json={**data,'prompt_id':str(uuid.uuid4())})
    assert good.status_code==200,good.text
    assert good.json()['requests']==[]

@pytest.mark.asyncio
async def test_active_session_cannot_restart_a_turn_or_duplicate_a_prompt(gate_api, proposed, monkeypatch):
    client,pool=gate_api
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']; prompt=str(uuid.uuid4())
    await answer(proposed,pool,monkeypatch,{'answer':'read','requests':[{'name':'read_file','arguments':{'path':'file.txt'}}]})
    first=await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'inspect','prompt_id':prompt})
    assert first.status_code==200,first.text
    await answer(proposed,pool,monkeypatch,{'answer':'done','requests':[]})
    second=await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'inspect','prompt_id':prompt,'continuation':True})
    assert second.status_code==200,second.text
    saved=(await client.get('/v1/command/code-sessions/'+thread)).json()
    assert len([x for x in saved['history'] if x['kind']=='user'])==1
    await pool.execute("UPDATE tank.command_threads SET state=jsonb_set(state,'{active_turn}',to_jsonb('placeholder-active'::text)) WHERE thread_id=$1",uuid.UUID(thread))
    assert (await client.get('/v1/command/code-sessions/'+thread)).json()['active'] is True
    assert (await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'restart'})).status_code==409

@pytest.mark.asyncio
async def test_mcp_admin_policy_is_tenant_scoped_and_member_cannot_change_it(gate_api):
    client, pool = gate_api
    body = {'server_id': 'http:https://placeholder.invalid', 'blocked': True}
    member = {'x-tervory-user': 'member'}
    assert (await client.put('/v1/command/code-mcp-policy', headers=member, json=body)).status_code == 403
    admin = {**member, 'x-tervory-role': 'org:admin'}
    assert (await client.put('/v1/command/code-mcp-policy', headers=admin, json=body)).status_code == 200
    assert (await client.get('/v1/command/code-mcp-policy', headers=member)).json() == {'blocked': [body['server_id']]}
    assert (await client.get('/v1/command/code-mcp-policy', headers={'x-tervory-tenant': str(OTHER)})).json() == {'blocked': []}
    assert (await client.put('/v1/command/code-mcp-policy', headers=admin, json={**body, 'blocked':False})).status_code == 200
    assert (await client.get('/v1/command/code-mcp-policy')).json() == {'blocked': []}
    assert (await client.put('/v1/command/code-mcp-policy', json={**body, 'server_id':'http:https://user:secret@placeholder.invalid'})).status_code == 422


@pytest.mark.asyncio
async def test_code_attachments_keep_existing_storage_redaction_and_ownership(gate_api, proposed, monkeypatch):
    import base64
    client, pool = gate_api
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    uploaded = await client.post('/v1/command/code-attachments', json={'thread_id':thread,'name':'image.png','base64':base64.b64encode(b'\x89PNG\r\n\x1a\nplaceholder').decode()})
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()['model_readable'] is False
    identifier = uploaded.json()['attachment_id']
    route = await answer(proposed,pool,monkeypatch,{'answer':'done','requests':[]})
    secret = 'ghp_' + 'placeholder'*3
    request = {'text':'inspect','attachments':[{'attachment_id':identifier},{'name':'words.txt','text':'hello\n'+secret}]}
    response = await client.post(f'/v1/command/threads/{thread}/code-turn',json=request)
    assert response.status_code == 200, response.text
    context = json.dumps(route.call_args.args[1]); assert secret not in context and '[redacted]' in context and 'model_readable' in context
    other = (await client.post('/v1/command/threads',json={},headers={'x-tervory-user':'other'})).json()['thread_id']
    assert (await client.post(f'/v1/command/threads/{other}/code-turn',headers={'x-tervory-user':'other'},json=request)).status_code == 404
    saved = await pool.fetchval('SELECT state::text FROM tank.command_threads WHERE thread_id=$1',uuid.UUID(thread))
    assert secret not in saved and 'hello' not in saved


@pytest.mark.asyncio
async def test_local_mcp_proposals_validate_catalogue_and_plan_blocks_execution(gate_api, proposed, monkeypatch):
    client,pool = gate_api
    thread = (await client.post('/v1/command/threads',json={})).json()['thread_id']
    request = {'name':'local_mcp','arguments':{'server':'fixture','tool':'echo','arguments':{'text':'hello'}}}
    await answer(proposed,pool,monkeypatch,{'answer':'','requests':[request]})
    body = {'text':'inspect','local_mcp':[{'server':'fixture','name':'echo','description':'echo','inputSchema':{'type':'object','required':['text'],'properties':{'text':{'type':'string'}}}}]}
    result=await client.post(f'/v1/command/threads/{thread}/code-turn',json=body)
    assert result.status_code == 200, result.text
    assert result.json()['requests'] == [request] and result.json()['cards'] == []
    await answer(proposed,pool,monkeypatch,{'answer':'','requests':[request]})
    result=await client.post(f'/v1/command/threads/{thread}/code-turn',json={**body,'mode':'plan'})
    assert result.status_code == 422
    await answer(proposed,pool,monkeypatch,{'answer':'','requests':[request]})
    result=await client.post(f'/v1/command/threads/{thread}/code-turn',json={**body,'local_mcp':[]})
    assert result.status_code == 422


@pytest.mark.asyncio
async def test_tank_web_catalogue_keeps_only_authorized_read_search_and_fetch(proposed):
    from plugins import code_actor
    conn=types.SimpleNamespace(fetch=AsyncMock(return_value=[]))
    actor=proposed.Actor(TENANT,'member',False,mcp_tools={
        'mcp.placeholder.web_search':{'name':'web_search','access':'read','vault':'base.vault','connection_id':'placeholder'},
        'mcp.placeholder.web_fetch':{'name':'web_fetch','access':'read','vault':'base.vault','connection_id':'placeholder'},
        'mcp.placeholder.write':{'name':'web_fetch','access':'write','vault':'base.vault','connection_id':'placeholder'},
    })
    result=await code_actor(actor,conn)
    assert set(result.mcp_tools) == {'mcp.placeholder.web_search','mcp.placeholder.web_fetch'}


@pytest.mark.asyncio
async def test_code_stream_emits_redacted_preview_then_validated_result_and_receipt(gate_api, proposed, monkeypatch):
    import code_sessions
    client,pool = gate_api
    thread = (await client.post('/v1/command/threads',json={})).json()['thread_id']
    route = await answer(proposed,pool,monkeypatch,{'answer':'done','requests':[]})
    result = route.return_value
    secret = 'ghp_'+'placeholder'*3
    async def stream(*args):
        sink = code_sessions.TOKEN_SINK.get(); assert sink is not None
        await sink('{"answer":"Hello ')
        await sink(secret+' ","requests":[]}')
        return result
    route.side_effect=stream
    response=await client.post(f'/v1/command/threads/{thread}/code-stream',json={'text':'inspect'})
    assert response.status_code == 200, response.text
    assert response.headers['content-type'].startswith('text/event-stream')
    assert response.text.index('code_preview') < response.text.index('code_result')
    assert secret not in response.text and '[redacted]' in response.text
    result_frame = next(frame for frame in response.text.split('\n\n') if frame.startswith('event: code_result\n'))
    result = json.loads(result_frame.split('data: ', 1)[1])
    assert result['turn']['cost_usd'] == 0.004
    assert result['receipt']['rows'][0]['cost_usd'] == 0.004
    assert await pool.fetchval("SELECT count(*) FROM tank.command_events WHERE kind='code_preview'") == 0
    assert code_sessions.TOKEN_SINK.get() is None


@pytest.mark.asyncio
async def test_code_stream_router_reuses_existing_callback_and_failures_are_not_retried(gate_api, proposed, runtime, monkeypatch):
    import code_sessions
    runtime.Message=lambda **kw:kw
    runtime.RouteRequest=lambda **kw:types.SimpleNamespace(**kw)
    runtime.run_route=AsyncMock(return_value='placeholder')
    async def sink(value): pass
    marker=code_sessions.TOKEN_SINK.set(sink)
    try:
        await proposed.route_code(proposed.Actor(TENANT,'founder',True),[{'role':'user','content':'hi'}],'auto',uuid.uuid4())
        assert runtime.run_route.call_args.kwargs['_on_token'] is sink
        assert runtime.run_route.call_args.args[0].task_type == 'command.code'
    finally: code_sessions.TOKEN_SINK.reset(marker)
    client,pool=gate_api
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    route=AsyncMock(side_effect=RuntimeError('placeholder private failure'))
    monkeypatch.setattr(proposed,'route_code',route)
    response=await client.post(f'/v1/command/threads/{thread}/code-stream',json={'text':'inspect'})
    assert 'event: error' in response.text and 'placeholder private failure' not in response.text
    assert route.await_count == 1
    state=json.loads(await pool.fetchval('SELECT state::text FROM tank.command_threads WHERE thread_id=$1',uuid.UUID(thread)))
    assert state['active_turn'] is None and list(state['steps'].values())[0]['status'] == 'failed'


@pytest.mark.asyncio
async def test_code_savings_use_frozen_code_policy_prices_without_another_model_call(gate_api, proposed, monkeypatch):
    client,pool=gate_api
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    route=await answer(proposed,pool,monkeypatch,{'answer':'done','requests':[]})
    await pool.execute('UPDATE tank.ledger SET tokens_in=10,tokens_out=5 WHERE id=$1',route.return_value.ledger_id)
    price=AsyncMock(return_value={'model':'placeholder-auto','input_usd':'0.001','output_usd':'0.002','priced_at':None})
    monkeypatch.setattr(proposed,'auto_price_snapshot',price)
    response=await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'inspect','model':'placeholder-allowed'})
    assert response.status_code == 200,response.text
    assert price.call_args.args[2]=='command.code'
    assert response.json()['receipt']['rows'][0]['auto_cost_usd']==0.02
    session=(await client.get('/v1/command/code-sessions/'+thread)).json()
    assert session['savings_usd']==pytest.approx(0.016)
    assert route.await_count == 1


@pytest.mark.asyncio
async def test_existing_source_privacy_assertions_with_proposed_server(gate_api, proposed, monkeypatch):
    # Execute the original regression, including all assertions, with this
    # proposal's HTTP/SQL fixture. The Tank checkout stays untouched.
    import ast
    source = ast.parse(proposed_files()['tests/test_command_code.py'])
    case = next(node for node in source.body if isinstance(node, ast.AsyncFunctionDef)
                and node.name == 'test_code_returns_requests_and_stores_only_tool_metadata')
    namespace = {**globals(), 'command': proposed, 'SimpleNamespace': types.SimpleNamespace}
    exec(compile(ast.Module(body=[case], type_ignores=[]), 'proposal:source_privacy_regression', 'exec'), namespace)
    await namespace[case.name](gate_api, monkeypatch)


def test_public_corridor_forwards_only_authorized_opli_routes():
    import subprocess
    result = subprocess.run(['node', 'tests/opli_agent/corridor.cjs'], input=proposed_files()['workspace/lib/tank.ts'], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'OPLI corridor checks passed' in result.stdout


def test_release_host_aliases_are_public_and_confined_to_release_assets():
    import subprocess
    files=proposed_files()
    result=subprocess.run(['node','tests/opli_agent/release-paths.cjs'],input=json.dumps({key:value for key,value in files.items() if key.startswith('workspace/')}),text=True,capture_output=True,check=False)
    assert result.returncode == 0,result.stdout+result.stderr
    assert 'OPLI release aliases passed' in result.stdout
