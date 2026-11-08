"""Stage 2 item 9: the third identical error never reaches a model."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pgserver
import pytest
import pytest_asyncio

import code_gate
import command
import test_command as existing

api = existing.api


@pytest.fixture
def runtime(monkeypatch):
    value = existing.runtime.__wrapped__(monkeypatch)
    value.pool = lambda: command.db()
    return value


def failure(text='fixture.py:7: expected 2, got 1', *, name='run_command', code=1):
    return SimpleNamespace(name=name, output=json.dumps({'arguments': {'command': 'pytest'},
        'result': {'ran': True, 'code': code, 'timed_out': False, 'output': text}}))


@pytest.fixture(autouse=True)
def opt_in(monkeypatch):
    monkeypatch.setenv(code_gate.SETTING, 'true')


@pytest.fixture(scope='module')
def local_postgres(tmp_path_factory):
    server = pgserver.get_server(tmp_path_factory.mktemp('code-gate-pg'), cleanup_mode='delete')
    try:
        yield server.get_uri()
    finally:
        server.cleanup()


@pytest_asyncio.fixture
async def command_pool(monkeypatch, local_postgres):
    monkeypatch.setenv('POOL_SCHEMA_DATABASE_URL', local_postgres)
    generator = existing.command_pool.__wrapped__()
    try:
        yield await anext(generator)
    finally:
        await generator.aclose()


def test_third_occurrence_stops_and_latches():
    state = {}
    for _ in range(2):
        assert code_gate.advance(state, 'task', [failure()]) is None
    stopped = code_gate.advance(state, 'task', [failure()])
    assert stopped['reason'] == 'repeated_error' and stopped['occurrences'] == 3
    assert code_gate.advance(state, 'task', []) == stopped
    assert code_gate.advance(state, 'task', [failure(code=0)]) == stopped
    assert code_gate.advance(state, 'new-user-task', [failure()]) is None
    assert 'expected 2' not in json.dumps(state)


@pytest.mark.parametrize('setting', [None, '', 'false', '1', 'TRUE', 'not-a-setting'])
def test_no_new_setting_is_exactly_a_noop(monkeypatch, setting):
    if setting is None:
        monkeypatch.delenv(code_gate.SETTING, raising=False)
    else:
        monkeypatch.setenv(code_gate.SETTING, setting)
    state = {'unrelated': {'state': [1,2,3]}}
    before = json.dumps(state)
    for _ in range(5):
        assert code_gate.advance(state, 'task', [failure()]) is None
    assert json.dumps(state) == before


def test_one_batch_with_three_occurrences_stops():
    stopped = code_gate.advance({}, 'task', [failure(),failure(),failure()])
    assert stopped['reason'] == 'repeated_error' and stopped['occurrences'] == 3


def test_read_data_success_and_declined_commands_are_not_failures():
    state = {}
    for _ in range(4):
        results = [failure(name='read_file'), failure(code=0),
                   SimpleNamespace(name='run_command',output=json.dumps({'result':{'ran':False}}))]
        assert code_gate.advance(state,'task',results) is None
    assert state['code_gate']['errors'] == {}


def test_distinct_errors_and_read_batches_do_not_reset_counts():
    state = {}
    for text in ['first error','other error','first error','third error']:
        assert code_gate.advance(state,'task',[failure(text)]) is None
    assert code_gate.advance(state,'task',[failure(name='read_file')]) is None
    assert code_gate.advance(state,'task',[failure('first error')])['reason'] == 'repeated_error'


def test_cosmetic_ansi_and_line_endings_do_not_hide_the_same_error():
    state = {}
    for text in ['error\nline\n','\x1b[31merror\x1b[0m\r\nline\r\n']:
        assert code_gate.advance(state,'task',[failure(text)]) is None
    assert code_gate.advance(state,'task',[failure('error\nline')])['occurrences'] == 3


@pytest.mark.parametrize('value',['{','[]','{}','{"result":null}','['*2000+']'*2000])
def test_malformed_command_result_stops_without_guessing(value):
    result = SimpleNamespace(name='run_command',output=value)
    assert code_gate.advance({},'task',[result])['reason'] == 'invalid_command_result'


def test_error_state_has_a_fixed_bound():
    state = {}
    for number in range(code_gate.MAX_ERRORS):
        assert code_gate.advance(state,'task',[failure(str(number))]) is None
    assert code_gate.advance(state,'task',[failure('one more')])['reason'] == 'error_limit'
    assert len(state['code_gate']['errors']) == code_gate.MAX_ERRORS


async def fake_model(pool, task):
    await pool.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd) "
        "VALUES($1,$2,'orchestrator','command.code','fixture',0.001)", task, existing.TENANT)
    return SimpleNamespace(ledger_id=task,content='{"answer":"Fixture repair","requests":[]}')


@pytest.mark.asyncio
async def test_real_http_third_error_stops_before_paid_call_and_persists(api, monkeypatch):
    client,pool = api
    async def model(actor,messages,name,task):
        return await fake_model(pool,task)
    route = AsyncMock(side_effect=model)
    monkeypatch.setattr(command,'route_code',route)
    thread = (await client.post('/v1/command/threads',json={})).json()['thread_id']
    prompt = str(uuid.uuid4())
    body = {'text':'Fix the failing test','prompt_id':prompt,'tool_results':[]}
    assert (await client.post(f'/v1/command/threads/{thread}/code-turn',json=body)).status_code == 200
    assert route.await_count == 1
    body.update(continuation=True,tool_results=[vars(failure())])
    for _ in range(2):
        reply = await client.post(f'/v1/command/threads/{thread}/code-turn',json=body)
        assert reply.status_code == 200 and 'gate' not in reply.json()
    stopped = await client.post(f'/v1/command/threads/{thread}/code-turn',json=body)
    assert stopped.status_code == 200, stopped.text
    result = stopped.json()
    assert result['gate']['reason'] == 'repeated_error' and result['requests'] == []
    assert result['turn']['cost_usd'] == result['receipt']['totals']['cost_usd'] == 0
    assert len(result['receipt']['rows']) == 1 and route.await_count == 3
    again = await client.post(f'/v1/command/threads/{thread}/code-turn',json={**body,'tool_results':[]})
    assert again.json()['gate'] == result['gate'] and route.await_count == 3
    state = json.loads(await pool.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1',uuid.UUID(thread)))
    assert state['active_turn'] is None and 'fixture.py' not in json.dumps(state)
    assert state['code_gate']['stopped'] == result['gate']
    for headers in [{'x-tervory-user':'other-user'},{'x-tervory-tenant':str(existing.OTHER)}]:
        foreign = await client.post(f'/v1/command/threads/{thread}/code-turn',json=body,headers=headers)
        assert foreign.status_code == 404
    fresh = await client.post(f'/v1/command/threads/{thread}/code-turn',json={**body,'prompt_id':str(uuid.uuid4()),'continuation':False,'tool_results':[]})
    assert fresh.status_code == 200 and 'gate' not in fresh.json() and route.await_count == 4


@pytest.mark.asyncio
async def test_request_replay_cannot_count_the_same_failure_twice(api,monkeypatch):
    client,pool = api
    async def model(actor,messages,name,task):
        return await fake_model(pool,task)
    route = AsyncMock(side_effect=model)
    monkeypatch.setattr(command,'route_code',route)
    thread = (await client.post('/v1/command/threads',json={})).json()['thread_id']
    prompt = str(uuid.uuid4())
    await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'Fix','prompt_id':prompt})
    body = {'text':'Fix','prompt_id':prompt,'request_id':str(uuid.uuid4()),'continuation':True,'tool_results':[vars(failure())]}
    assert (await client.post(f'/v1/command/threads/{thread}/code-turn',json=body)).status_code == 200
    assert (await client.post(f'/v1/command/threads/{thread}/code-turn',json=body)).status_code == 409
    state = json.loads(await pool.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1',uuid.UUID(thread)))
    assert list(state['code_gate']['errors'].values()) == [1] and route.await_count == 2


@pytest.mark.asyncio
async def test_unchanged_http_path_with_no_setting(api,monkeypatch):
    monkeypatch.delenv(code_gate.SETTING,raising=False)
    client,pool = api
    async def model(actor,messages,name,task):
        return await fake_model(pool,task)
    route = AsyncMock(side_effect=model)
    monkeypatch.setattr(command,'route_code',route)
    thread = (await client.post('/v1/command/threads',json={})).json()['thread_id']
    prompt = str(uuid.uuid4())
    for number in range(5):
        reply = await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'Fix','prompt_id':prompt,
            'continuation':number>0,'tool_results':[vars(failure())]})
        assert reply.status_code == 200 and 'gate' not in reply.json()
    assert route.await_count == 5
    state = json.loads(await pool.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1',uuid.UUID(thread)))
    assert 'code_gate' not in state
