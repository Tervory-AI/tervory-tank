"""No-progress proofs use synthetic checkpoints and no model/provider calls."""
import json
import uuid
from unittest.mock import AsyncMock
import command
import test_code_gate as gate_tests

api = gate_tests.api
runtime = gate_tests.runtime
command_pool = gate_tests.command_pool
local_postgres = gate_tests.local_postgres
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import code_gate
import code_progress


def progress(number, tests=1, stage=0):
    return code_progress.Progress(tree=f'{number:064x}', tests_passed=tests, build_stage=stage)


def tool(text):
    return SimpleNamespace(name='read_file',output=json.dumps({'arguments':{'path':'private.py'},'result':{'text':text}}))


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setenv(code_gate.SETTING,'true')
    monkeypatch.setenv(code_progress.SETTING,'true')


def test_two_rounds_without_progress_stop_before_the_next_call():
    state = {}
    assert code_gate.advance(state,'task',[],progress(1)) is None
    assert code_gate.advance(state,'task',[tool('first change')],progress(2),True) is None
    stop = code_gate.advance(state,'task',[tool('second change')],progress(3),True)
    assert stop['reason'] == 'no_progress'
    assert code_gate.advance(state,'task',[],progress(4,tests=100),True) == stop
    assert 'private.py' not in json.dumps(state)


def test_gains_in_tests_or_build_reset_the_two_round_counter():
    state = {}
    assert code_gate.advance(state,'task',[],progress(1)) is None
    for number,tests,stage in [(2,1,0),(3,2,0),(4,2,0),(5,2,1),(6,2,1),(7,3,1)]:
        assert code_gate.advance(state,'task',[tool(str(number))],progress(number,tests,stage),True) is None


def test_identical_tool_rounds_stop_even_with_reported_progress():
    state = {}
    assert code_gate.advance(state,'task',[],progress(1)) is None
    assert code_gate.advance(state,'task',[tool('same')],progress(2,2),True) is None
    assert code_gate.advance(state,'task',[tool('same')],progress(3,3),True)['reason'] == 'repeated_tool_round'


def test_undone_then_redone_changes_stop_even_with_reported_progress():
    state = {}
    for index,tree in enumerate([1,2,1]):
        assert code_gate.advance(state,'task',[],progress(tree,index),index>0) is None
    assert code_gate.advance(state,'task',[],progress(2,3),True)['reason'] == 'oscillating_changes'


def test_continuation_requires_check_evidence():
    state = {}
    assert code_gate.advance(state,'task',[]) is None
    assert code_gate.advance(state,'task',[],None,True)['reason'] == 'local_checks_required'


def test_a_new_task_is_independent():
    state = {}
    for index in range(3):
        code_gate.advance(state,'task',[],progress(index),index>0)
    assert code_gate.advance(state,'new task',[],progress(1)) is None
    assert state['code_gate']['progress']['stalled'] == 0


@pytest.mark.parametrize('value',[None,'','false','TRUE','1','not-a-setting'])
def test_no_progress_setting_is_a_noop(monkeypatch,value):
    if value is None:
        monkeypatch.delenv(code_progress.SETTING,raising=False)
    else:
        monkeypatch.setenv(code_progress.SETTING,value)
    state = {}
    for index in range(6):
        assert code_gate.advance(state,'task',[],progress(1),index>0) is None
    assert 'progress' not in state['code_gate']


def test_master_gate_off_does_not_mutate_state(monkeypatch):
    monkeypatch.delenv(code_gate.SETTING,raising=False)
    state = {}
    assert code_gate.advance(state,'task',[],progress(1),True) is None
    assert state == {}


@pytest.mark.parametrize('changes',[{'tree':'../secret'},{'tests_passed':-1},{'tests_passed':True},
    {'build_stage':-1},{'build_stage':10001},{'tenant_id':'other'}])
def test_evidence_is_strict_and_bounded(changes):
    with pytest.raises(ValidationError):
        code_progress.Progress.model_validate({**progress(1).model_dump(),**changes})


@pytest.mark.asyncio
async def test_http_no_progress_stops_at_two_rounds_without_another_model_call(api,monkeypatch):
    client,pool = api
    async def model(actor,messages,name,task):
        return await gate_tests.fake_model(pool,task)
    route=AsyncMock(side_effect=model)
    monkeypatch.setattr(command,'route_code',route)
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    prompt=str(uuid.uuid4())
    for number in range(3):
        body={'text':'Fix the build','prompt_id':prompt,'continuation':number>0,
              'progress':progress(number).model_dump(),'tool_results':[vars(tool(str(number)))]}
        response=await client.post(f'/v1/command/threads/{thread}/code-turn',json=body)
        assert response.status_code == 200,response.text
        if number<2:
            assert 'gate' not in response.json()
        else:
            assert response.json()['gate']['reason']=='no_progress'
            assert response.json()['receipt']['totals']['cost_usd']==0
    assert route.await_count==2
    body['progress']=progress(4,tests=999).model_dump()
    retry=await client.post(f'/v1/command/threads/{thread}/code-turn',json=body)
    assert retry.json()['gate']['reason']=='no_progress' and route.await_count==2


@pytest.mark.asyncio
async def test_http_missing_checks_and_invalid_progress_never_reach_a_model(api,monkeypatch):
    client,_=api
    route=AsyncMock()
    monkeypatch.setattr(command,'route_code',route)
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    bad=await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'Fix',
        'progress':{**progress(1).model_dump(),'tests_passed':True}})
    assert bad.status_code==422 and route.await_count==0


@pytest.mark.asyncio
@pytest.mark.parametrize('evidence',[None,progress(1).model_dump()])
async def test_disabled_host_keeps_the_old_rejection_for_new_fields(api,monkeypatch,evidence):
    monkeypatch.delenv(code_gate.SETTING,raising=False)
    monkeypatch.delenv(code_progress.SETTING,raising=False)
    client,pool=api
    model=AsyncMock(side_effect=AssertionError('disabled metadata must not start paid work'))
    monkeypatch.setattr(command,'route_code',model)
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    response=await client.post(f'/v1/command/threads/{thread}/code-turn',json={'text':'Fix','progress':evidence})
    assert response.status_code==422
    model.assert_not_awaited()
    assert await pool.fetchval('SELECT count(*) FROM tank.tasks')==0
