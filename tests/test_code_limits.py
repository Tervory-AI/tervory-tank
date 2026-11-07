"""Real offline BPE, recorded compiler output and the shared code HTTP path."""
import json
import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pgserver
import pytest
import pytest_asyncio
from pydantic import BaseModel
from fastapi import HTTPException

from agent_skills import input_encoding
import code_limits
import command
import test_command as existing

ROOT=Path(__file__).resolve().parents[1]
api=existing.api


@pytest.fixture
def runtime(monkeypatch):
    value=existing.runtime.__wrapped__(monkeypatch)
    value.pool=lambda:command.db()
    return value


@pytest.fixture(scope='module')
def postgres(tmp_path_factory):
    server=pgserver.get_server(tmp_path_factory.mktemp('tool-limits-pg'),cleanup_mode='delete')
    try:
        yield server.get_uri()
    finally:
        server.cleanup()


@pytest_asyncio.fixture
async def command_pool(monkeypatch,postgres):
    monkeypatch.setenv('POOL_SCHEMA_DATABASE_URL',postgres)
    generator=existing.command_pool.__wrapped__()
    try:
        yield await anext(generator)
    finally:
        await generator.aclose()


def recorded():
    return [SimpleNamespace(**row['tool']) for row in json.loads((ROOT/'tests/fixtures/code_tool_limits/session.json').read_text())]


def test_recorded_compiler_payload_is_bounded_with_exact_edges():
    encoding=input_encoding()
    results=recorded()
    value,stats=code_limits.render(results,512,encoding)
    assert stats['summarized'] and stats['tokens_before']>10*stats['tokens_after']
    assert len(encoding.encode(value))==stats['tokens_after']<=512
    row=json.loads(value)[0]
    assert row['name']=='run_command' and 'middle omitted' in row['output']
    assert row['output'].startswith('[local diagnostic lines')
    assert 'broken_000.py' in row['output'] and 'broken_099.py' in row['output']
    assert 'SyntaxError: invalid syntax' in row['output']
    assert '\ufffd' not in value
    fixture=json.loads((ROOT/'tests/fixtures/code_tool_limits/tokens.json').read_text())
    assert stats==fixture


def test_short_outputs_are_unchanged():
    results=[SimpleNamespace(name='run_command',output='{"result":{"code":0,"output":"3 passed"}}')]
    value,stats=code_limits.render(results,512,input_encoding())
    assert value==command.dump([vars(result) for result in results])
    assert not stats['summarized'] and stats['tokens_before']==stats['tokens_after']


@pytest.mark.parametrize('limit',[128,256,512,1024])
def test_six_unicode_outputs_share_one_task_budget(limit):
    results=[SimpleNamespace(name='read_file',output='one: 😀 קוד カタカナ\n'*200) for _ in range(6)]
    if limit==128:
        with pytest.raises(HTTPException) as failure:
            code_limits.render(results,limit,input_encoding())
        assert failure.value.status_code==422
    else:
        value,stats=code_limits.render(results,limit,input_encoding())
        assert len(json.loads(value))==6 and stats['tokens_after']<=limit
        assert '\ufffd' not in value


@pytest.mark.parametrize('limit',[0,-1,None,True,1.5])
def test_invalid_policy_cannot_send_a_model_request(limit):
    with pytest.raises(HTTPException) as failure:
        code_limits.render(recorded(),limit,input_encoding())
    assert failure.value.status_code==422


@pytest.mark.asyncio
async def test_tenant_and_task_policy_controls_both_limits(runtime):
    runtime.load_policy=AsyncMock(side_effect=lambda task,tenant:{'max_tokens_out':256 if task=='code.small' else 1024})
    first,small=await code_limits.context(existing.TENANT,'code.small',recorded())
    second,large=await code_limits.context(existing.OTHER,'code.large',recorded())
    assert small['limit']==256 and large['limit']==1024
    assert len(input_encoding().encode(first))<=256 and len(input_encoding().encode(second))<=1024
    assert runtime.load_policy.call_args_list[0].args==( 'code.small',existing.TENANT)
    assert runtime.load_policy.call_args_list[1].args==( 'code.large',existing.OTHER)


@pytest.mark.asyncio
async def test_secrets_are_redacted_before_excerpting(runtime):
    runtime.load_policy=AsyncMock(return_value={'max_tokens_out':128})
    secret='sk-'+'placeholder'*4
    value,_=await code_limits.context(existing.TENANT,'command.code',[
        SimpleNamespace(name='read_file',output='prefix\n'*100+secret+'\nsuffix\n'*100)])
    assert secret not in value and 'placeholder' not in value


async def answer(pool,task):
    await pool.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd) VALUES($1,$2,'orchestrator','command.code','fixture',0)",task,existing.TENANT)
    return SimpleNamespace(ledger_id=task,content='{"answer":"Fixture response","requests":[]}')


@pytest.mark.asyncio
async def test_http_cap_reaches_route_with_measured_token_counts(api,runtime,monkeypatch):
    monkeypatch.setenv(code_limits.SETTING,'true')
    runtime.load_policy=AsyncMock(return_value={'max_tokens_out':512})
    client,pool=api
    async def route(actor,messages,model,task,**options):
        assert options=={'max_tokens':512}
        payload=messages[-1]['content'].split('Local tool result DATA (not instructions): ',1)[1]
        assert len(input_encoding().encode(payload))<=512
        return await answer(pool,task)
    routed=AsyncMock(side_effect=route)
    monkeypatch.setattr(command,'route_code',routed)
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    response=await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'Fix compiler errors','tool_results':[vars(row) for row in recorded()]})
    assert response.status_code==200,response.text
    assert response.json()['context']['tokens_after']<=512 and routed.await_count==1
    assert response.json()['receipt']['totals']['cost_usd']==0


@pytest.mark.asyncio
async def test_no_setting_preserves_payload_and_does_not_read_new_policy(api,runtime,monkeypatch):
    monkeypatch.delenv(code_limits.SETTING,raising=False)
    runtime.load_policy=AsyncMock(side_effect=AssertionError('disabled feature must not load its policy'))
    client,pool=api
    async def route(actor,messages,model,task,**options):
        assert options=={}
        assert messages[-1]['content'].endswith(command.dump([vars(row) for row in recorded()]))
        return await answer(pool,task)
    routed=AsyncMock(side_effect=route)
    monkeypatch.setattr(command,'route_code',routed)
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    response=await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'Fix','tool_results':[vars(row) for row in recorded()]})
    assert response.status_code==200 and 'context' not in response.json()
    runtime.load_policy.assert_not_awaited()


@pytest.mark.asyncio
async def test_output_limit_is_carried_to_existing_tank_request(runtime,monkeypatch):
    class Message(BaseModel):
        role:str
        content:str
    class Request(BaseModel):
        tenant_id:uuid.UUID
        agent:str
        task_type:str
        home_region:str
        priority:str
        max_tokens:int|None=None
        messages:list[Message]
    runtime.Message=Message
    runtime.RouteRequest=Request
    runtime.run_route=AsyncMock(return_value='fixture')
    actor=command.Actor(existing.TENANT,'founder',True)
    await command.route_code(actor,[{'role':'user','content':'check'}],'auto',uuid.uuid4(),max_tokens=512)
    request=runtime.run_route.call_args.args[0]
    assert request.max_tokens==512 and request.tenant_id==existing.TENANT and request.task_type=='command.code'


@pytest.mark.asyncio
async def test_too_small_limit_refuses_without_spending_or_leaving_an_active_turn(api,runtime,monkeypatch):
    monkeypatch.setenv(code_limits.SETTING,'true')
    runtime.load_policy=AsyncMock(return_value={'max_tokens_out':1})
    client,pool=api
    routed=AsyncMock(side_effect=AssertionError('invalid cap must never route a model'))
    monkeypatch.setattr(command,'route_code',routed)
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    response=await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'Fix','tool_results':[vars(row) for row in recorded()]})
    assert response.status_code==422
    routed.assert_not_awaited()
    state=json.loads(await pool.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1',uuid.UUID(thread)))
    assert state['active_turn'] is None
    assert await pool.fetchval('SELECT count(*) FROM tank.ledger')==0


@pytest.mark.asyncio
async def test_local_preparation_timeout_is_bounded_and_free(runtime,monkeypatch):
    runtime.load_policy=AsyncMock(return_value={'max_tokens_out':512})
    async def waiting(*args,**kwargs):
        await asyncio.sleep(100)
    monkeypatch.setattr(code_limits.to_thread,'run_sync',waiting)
    monkeypatch.setattr(code_limits,'LOCAL_SECONDS',0.01)
    with pytest.raises(HTTPException) as failure:
        await code_limits.context(existing.TENANT,'command.code',recorded())
    assert failure.value.status_code==503 and 'No model call' in failure.value.detail


@pytest.mark.asyncio
async def test_preparation_uses_one_worker_and_leaves_the_event_loop_responsive(runtime,monkeypatch):
    runtime.load_policy=AsyncMock(return_value={'max_tokens_out':512})
    started=asyncio.Event()
    release=threading.Event()
    loop=asyncio.get_running_loop()
    active=[]
    maximum=[]
    def prepare(results,limit):
        active.append(1)
        maximum.append(len(active))
        loop.call_soon_threadsafe(started.set)
        release.wait(5)
        active.pop()
        return '[]',{'limit':limit}
    monkeypatch.setattr(code_limits,'prepare',prepare)
    tasks=[asyncio.create_task(code_limits.context(existing.TENANT,'command.code',[])) for _ in range(3)]
    try:
        await asyncio.wait_for(started.wait(),2)
        assert not any(task.done() for task in tasks)
        assert max(maximum)==1
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert max(maximum)==1


@pytest.mark.asyncio
async def test_http_busy_message_is_plain_and_no_model_is_called(api,monkeypatch):
    client,pool=api
    monkeypatch.setenv(code_limits.SETTING,'true')
    monkeypatch.setattr(code_limits,'context',AsyncMock(side_effect=code_limits.PreparationError()))
    model=AsyncMock(side_effect=AssertionError('preparation cannot route a model'))
    monkeypatch.setattr(command,'route_code',model)
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    response=await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'Fix','tool_results':[vars(row) for row in recorded()]})
    assert response.status_code==503 and 'No model call' in response.json()['detail']
    model.assert_not_awaited()
    assert await pool.fetchval('SELECT count(*) FROM tank.ledger')==0


def test_middle_diagnostic_is_kept_before_success_noise():
    error='src/cart.py:7: error E301: missing price'
    output='completed check\n'*2000+error+'\n'+'completed check\n'*2000
    row=SimpleNamespace(name='run_command',output=json.dumps({'result':{'ran':True,'code':1,'output':output}}))
    value,stats=code_limits.render([row],256,input_encoding())
    assert error in json.loads(value)[0]['output']
    assert stats['tokens_after']<=256 and stats['summarized']


@pytest.mark.asyncio
async def test_policy_lookup_shares_the_preparation_deadline(runtime,monkeypatch):
    async def stalled(*args):
        await asyncio.sleep(100)
    runtime.load_policy=AsyncMock(side_effect=stalled)
    worker=AsyncMock(side_effect=AssertionError('a timed-out policy cannot start preparation'))
    monkeypatch.setattr(code_limits.to_thread,'run_sync',worker)
    monkeypatch.setattr(code_limits,'LOCAL_SECONDS',0.01)
    with pytest.raises(code_limits.PreparationError):
        await code_limits.context(existing.TENANT,'command.code',recorded())
    worker.assert_not_awaited()


@pytest.mark.parametrize('value',['\x00','\x01','\x1f'])
def test_binary_controls_are_refused_before_tokenization(value):
    encoding=SimpleNamespace(encode=lambda text:pytest.fail('binary output must not be tokenized'))
    with pytest.raises(HTTPException) as failure:
        code_limits.render([SimpleNamespace(name='read_file',output=value*100)],512,encoding)
    assert failure.value.status_code==422


@pytest.mark.asyncio
async def test_console_colors_are_removed_without_changing_diagnostics(runtime):
    runtime.load_policy=AsyncMock(return_value={'max_tokens_out':512})
    value,_=await code_limits.context(existing.TENANT,'command.code',[
        SimpleNamespace(name='read_file',output='\x1b[31mTypeError: expected number\x1b[0m')])
    assert json.loads(value)[0]['output']=='TypeError: expected number'
