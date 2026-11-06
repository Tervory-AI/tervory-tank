"""Offline launch journeys, database ownership and hostile-boundary proofs."""
import asyncio
import ast
import json
import subprocess
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from test_b3_base_room import ROOT, _load, _scripted, BASE_CORE
import test_base_finish_training as database_fixtures
postgres = database_fixtures.postgres
database = database_fixtures.database
import room
from network import BoundedHTTP, admitted


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.delenv('BASE_BRAIN_URL', raising=False)
    module = _load('base_gate5_app_' + uuid4().hex, ROOT / 'agents/base/app.py')
    monkeypatch.setattr(module, 'ensure_worker', AsyncMock())
    return module


@pytest.mark.asyncio
async def test_every_non_health_route_rejects_anonymous_and_workspace_keys_before_work(base):
    # Includes generic chassis storage/tasks, brain and documentation routes.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app), base_url='http://local') as client:
        for route in base.app.routes:
            if getattr(route, 'path', None) == '/health':
                continue
            for method in getattr(route, 'methods', set()) - {'HEAD', 'OPTIONS'}:
                for headers in ({}, {'X-Tank-Key': 'placeholder-workspace-key'}):
                    response = await client.request(method, route.path, headers=headers, json={})
                    assert response.status_code == 401, (method, route.path)
    base.ensure_worker.assert_not_awaited()


@pytest.mark.asyncio
async def test_full_room_journey_day_zero_submit_result_receipt_and_tenant_isolation(base, database, monkeypatch):
    async with database.acquire() as conn:
        await conn.execute('CREATE SCHEMA agent_base')
        await room.ensure_tables(conn, recover=False)
    base.app.state.pool = database
    class Skills:
        async def pin(self, *args): return {key: '2.0.0' for key in BASE_CORE}, {'base.normalize': 'base.normalize@2.0.0'}
        def bind(self, *args):
            async def run(key, payload): return {**_scripted(key, payload), '_cost_usd': 0}
            return run
    skills = Skills()
    monkeypatch.setattr(base, '_skills', lambda: skills)
    monkeypatch.setattr(room, 'publish', AsyncMock())
    tenant, other, request = uuid4(), uuid4(), uuid4()
    body = {'tenant_id': str(tenant), 'request_id': str(request), 'batch': 'First list',
            'records': [{'name': 'Recorded Business', 'city': 'Washington', 'state': 'DC'}]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app), base_url='http://local',
                                headers={'X-Tank-Key': 'placeholder-room-key'}) as client:
        assert (await client.get('/v1/base/batches', params={'tenant_id': str(tenant)})).json() == []
        first = await client.post('/v1/base/run', json=body)
        assert first.status_code == 202, first.text
        retry = await client.post('/v1/base/run', json=body)
        assert retry.json() == first.json()
        changed = await client.post('/v1/base/run', json={**body, 'records': [{'name': 'Changed input'}]})
        assert changed.status_code == 409
        async with database.acquire() as conn:
            assert await conn.fetchval('SELECT count(*) FROM agent_base.tasks') == 1
            task = await conn.fetchrow('SELECT id,input FROM agent_base.tasks WHERE tenant_id=$1', tenant)
        await room._run_batch(database, task['id'], json.loads(task['input']), skills.bind())
        records = (await client.get('/v1/base/records', params={'tenant_id': str(tenant)})).json()
        assert len(records) == 1 and records[0]['status'] == 'done'
        assert records[0]['profile'] and records[0]['passes']
        assert (await client.get('/v1/base/records', params={'tenant_id': str(other), 'task_id': str(task['id'])})).json() == []
        assert (await client.get('/v1/base/batches', params={'tenant_id': str(other)})).json() == []
        assert (await client.post('/v1/base/retry', json={'tenant_id': str(other), 'batch': 'First list'})).json() == {'requeued': 0}
        own = (await client.get('/v1/base/batches', params={'tenant_id': str(tenant)})).json()
        assert own[0]['total'] == own[0]['done'] == 1
        async with database.acquire() as conn:
            cfg = json.loads(await conn.fetchval('SELECT input FROM agent_base.tasks WHERE tenant_id=$1 AND id=$2', tenant, task['id']))
            assert cfg['model_spend'] == 0 and cfg['submission_response']['task']['id'] == str(task['id'])
        # A reload/lost acknowledgement after completion still returns the same receipt.
        assert (await client.post('/v1/base/run', json=body)).json() == first.json()


@pytest.mark.asyncio
async def test_two_worker_processes_cannot_recover_or_run_the_same_queue(database, monkeypatch):
    entered = asyncio.Event()
    finished = []
    async def owned(*args):
        entered.set()
        try: await asyncio.Event().wait()
        finally: finished.append(True)
    monkeypatch.setattr(room, '_owned_loop', owned)
    first = asyncio.create_task(room.base_loop(database, object()))
    await asyncio.wait_for(entered.wait(), 3)
    await asyncio.wait_for(room.base_loop(database, object()), 3)
    assert finished == []
    first.cancel()
    await asyncio.gather(first, return_exceptions=True)
    assert finished == [True]
    # Cancellation releases ownership, so a replacement can resume checkpoints.
    entered.clear()
    replacement = asyncio.create_task(room.base_loop(database, object()))
    await asyncio.wait_for(entered.wait(), 3)
    replacement.cancel()
    await asyncio.gather(replacement, return_exceptions=True)
    assert len(finished) == 2


@pytest.mark.asyncio
async def test_submission_contention_returns_a_bounded_conflict_without_queueing(base, database, monkeypatch):
    async with database.acquire() as conn:
        await conn.execute('CREATE SCHEMA agent_base')
        await room.ensure_tables(conn, recover=False)
    tenant, request = uuid4(), uuid4()
    from uuid import uuid5
    base.app.state.pool = database
    monkeypatch.setattr(base, '_skills', lambda: SimpleNamespace(pin=AsyncMock(return_value=({}, {})), bind=lambda *a: None))
    body = base.BaseRun(tenant_id=tenant, request_id=request, batch='A', records=[{'name': 'A'}])
    async with database.acquire() as conn, conn.transaction():
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))', str(uuid5(tenant, str(request))))
        with pytest.raises(Exception) as error:
            await asyncio.wait_for(base.base_run(body), 1)
        assert error.value.status_code == 409
        assert await conn.fetchval('SELECT count(*) FROM agent_base.tasks') == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['retry', 'rerun'])
async def test_retry_and_rerun_roll_back_on_database_failure_and_can_be_retried(base,database,action):
    tenant=uuid4()
    status='failed' if action=='retry' else 'done'
    async with database.acquire() as conn:
        await conn.execute('CREATE SCHEMA agent_base')
        await room.ensure_tables(conn,recover=False)
        task=await room.insert_batch(conn,tenant,None,'Recorded',[{'name':'Recorded'}],'',False,None,1,None)
        await conn.execute('UPDATE agent_base.tasks SET status=$2 WHERE id=$1',task['id'],status)
        await conn.execute('UPDATE agent_base.records SET status=$2,passes=$3::jsonb WHERE task_id=$1',task['id'],status,
                           json.dumps({'5':{'skipped':'recorded model failure'}}))
    broken=True
    class Connection:
        def __init__(self,conn):self.conn=conn
        def __getattr__(self,name):return getattr(self.conn,name)
        async def execute(self,query,*args):
            if broken and query==room.SQL_REQUEUE_TASKS:
                raise RuntimeError('placeholder-private-database-input')
            return await self.conn.execute(query,*args)
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            async with database.acquire() as conn:yield Connection(conn)
    base.app.state.pool=Pool()
    body={'tenant_id':str(tenant),'batch':'Recorded',**({'flag':'model_skipped'} if action=='rerun' else {})}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app),base_url='http://local',
                                headers={'X-Tank-Key':'placeholder-room-key'}) as client:
        failed=await client.post('/v1/base/'+action,json=body)
        assert failed.status_code==503 and 'placeholder-private' not in failed.text
        async with database.acquire() as conn:
            assert await conn.fetchval('SELECT status FROM agent_base.records WHERE task_id=$1',task['id'])==status
            assert await conn.fetchval('SELECT status FROM agent_base.tasks WHERE id=$1',task['id'])==status
        broken=False
        assert (await client.post('/v1/base/'+action,json=body)).json()=={'requeued':1}
        assert (await client.post('/v1/base/'+action,json=body)).json()=={'requeued':0}
        async with database.acquire() as conn:
            assert await conn.fetchval('SELECT status FROM agent_base.tasks WHERE id=$1',task['id'])=='queued'
            assert await conn.fetchval('SELECT count(*) FROM agent_base.records')==1


@pytest.mark.parametrize('concurrency', [0, -1, 13, 1000000])
def test_input_validation_bounds_parallelism_before_any_external_work(base, concurrency):
    with pytest.raises(ValidationError):
        base.BaseRun(tenant_id=uuid4(), batch='A', records=[{}], concurrency=concurrency)


@pytest.mark.asyncio
@pytest.mark.parametrize('method,attempts', [('get', 2), ('post', 1), ('delete', 1)])
async def test_stalled_external_calls_have_wall_deadlines_and_safe_retry_limits(method, attempts):
    calls = []
    async def hang(*args, **kwargs):
        calls.append(True)
        await asyncio.Event().wait()
    client = BoundedHTTP(SimpleNamespace(**{method: hang}))
    with pytest.raises(httpx.TimeoutException, match='Base could not complete this request'):
        await asyncio.wait_for(getattr(client, method)('http://fake', timeout=.01), .2)
    assert len(calls) == attempts


@pytest.mark.asyncio
async def test_generic_http_request_keeps_its_contract_and_its_retry_budget():
    calls=[]
    async def respond(request):
        calls.append(request)
        return httpx.Response(503 if len(calls)==1 else 200,json={})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as raw:
        client=BoundedHTTP(BoundedHTTP(raw))
        assert (await client.request('GET','http://fake/memories',json=None)).status_code==200
        assert len(calls)==2
        assert (await client.request('POST','http://fake/memories',json={'text':'Recorded'})).status_code==200
        assert len(calls)==3 and json.loads(calls[-1].content)=={'text':'Recorded'}


def test_generated_state_labels_remain_valid_retry_and_rerun_inputs(base):
    label='A'*120+' · DC'
    assert base.BaseRetry(tenant_id=uuid4(),batch=label).batch==label
    assert base.BaseRerun(tenant_id=uuid4(),batch=label).batch==label


@pytest.mark.asyncio
async def test_read_retry_recovers_but_paid_approval_has_one_total_deadline():
    calls = []
    async def read(*args, **kwargs):
        calls.append(True)
        return httpx.Response(503 if len(calls) == 1 else 200, json={'ok': True})
    assert (await BoundedHTTP(SimpleNamespace(get=read)).get('http://fake')).json() == {'ok': True}
    assert len(calls) == 2
    with pytest.raises(httpx.TimeoutException):
        await admitted(asyncio.Event().wait(), .01)


@pytest.mark.asyncio
async def test_repeated_paid_approval_cannot_replay_a_write_forever():
    tenant=str(uuid4())
    posts=[]
    async def post(*args, **kwargs):
        posts.append(kwargs['json'])
        return httpx.Response(409,json={'detail':{'code':'paid_step_approval_required',
            'tenant_id':tenant,'approval_id':'placeholder-approval','run_id':'placeholder-run'}})
    async def get(*args, **kwargs): return httpx.Response(200,json={'state':'approved'},request=httpx.Request('GET','http://fake'))
    client=room.SkillClient(SimpleNamespace(post=post,get=get),'http://fake','placeholder-room-key')
    call=client.bind({'base.extract':'2.0.0'},False,tenant)
    with pytest.raises(httpx.TimeoutException):
        await asyncio.wait_for(call('base.extract',{'text':'Recorded text'}),.2)
    assert len(posts)==2
    assert posts[1]['paid_run_id']=='placeholder-run'


@pytest.mark.asyncio
async def test_error_bodies_and_model_failures_never_expose_provider_secrets(caplog, monkeypatch):
    from pipeline import ModelAccountBlocked
    client = room.SkillClient(None, 'http://fake', 'placeholder-room-key')
    with pytest.raises(room.SkillError) as failure:
        await client._read(httpx.Response(500, json={'detail': 'placeholder-private-input'}))
    monkeypatch.setitem(room._model_pause, 'until', 0)
    room.pause_models('placeholder-private-input')
    assert 'placeholder-private-input' not in str(failure.value) + caplog.text + room._model_pause['reason']
    assert 'placeholder-private-input' not in ModelAccountBlocked('placeholder-private-input').reason
    monkeypatch.setitem(room._model_pause, 'until', 0)


@pytest.mark.asyncio
async def test_provider_account_errors_still_pause_models_without_disclosing_the_body():
    from pipeline import is_account_error
    client = room.SkillClient(None, 'http://fake', 'placeholder-room-key')
    with pytest.raises(room.SkillError) as failure:
        await client._read(httpx.Response(500, json={'detail': 'billing unavailable: placeholder-private-input'}))
    assert is_account_error(failure.value)
    assert 'placeholder-private-input' not in str(failure.value)


@pytest.mark.asyncio
async def test_dripping_stream_has_a_total_deadline_and_closes_without_replay():
    opened, closed = [], []
    class Response:
        async def aiter_bytes(self):
            while True:
                yield b'x'
                await asyncio.sleep(.003)
    @asynccontextmanager
    async def stream(*args, **kwargs):
        opened.append(True)
        try: yield Response()
        finally: closed.append(True)
    with pytest.raises(httpx.TimeoutException):
        async with BoundedHTTP(SimpleNamespace(stream=stream)).stream('GET', 'http://fake', timeout=.01) as response:
            async for _ in response.aiter_bytes(): pass
    assert opened == closed == [True]


@pytest.mark.asyncio
async def test_worker_recovery_never_requeues_a_separately_owned_training_job(database):
    tenant = uuid4()
    async with database.acquire() as conn:
        await conn.execute('CREATE SCHEMA agent_base')
        await room.ensure_tables(conn, recover=False)
        ids=[]
        for kind in ('base.enrich','base.training'):
            task=await room.insert_batch(conn,tenant,None,kind,[{'name':'Recorded'}],'',False,None,1,None)
            ids.append(task['id'])
            await conn.execute("UPDATE agent_base.tasks SET task_type=$2,status='running' WHERE id=$1", task['id'],kind)
            await conn.execute("UPDATE agent_base.records SET status='running' WHERE task_id=$1", task['id'])
        await room.ensure_tables(conn)
        assert await conn.fetchval('SELECT status FROM agent_base.records WHERE task_id=$1',ids[0]) == 'queued'
        assert await conn.fetchval('SELECT status FROM agent_base.records WHERE task_id=$1',ids[1]) == 'running'


@pytest.mark.asyncio
async def test_unavailable_external_call_returns_a_plain_client_error_and_safe_log(base,monkeypatch,caplog):
    async def failure(*args): raise httpx.ConnectError('placeholder-private-input')
    monkeypatch.setattr(base,'_skills',lambda: SimpleNamespace(engines=failure))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app),base_url='http://local',
                                headers={'X-Tank-Key':'placeholder-room-key'}) as client:
        response=await client.get('/v1/base/engines')
    assert response.status_code == 503
    assert response.json()['detail'] == 'Base is unavailable. Your existing work has not changed.'
    assert 'placeholder-private-input' not in response.text + caplog.text


@pytest.mark.asyncio
async def test_stalled_route_has_an_outer_deadline_and_a_plain_error(base,monkeypatch):
    async def hang():await asyncio.Event().wait()
    monkeypatch.setattr(base,'REQUEST_TIMEOUT',.01)
    monkeypatch.setattr(base,'_skills',lambda:SimpleNamespace(engines=hang))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app),base_url='http://local',
                                headers={'X-Tank-Key':'placeholder-room-key'}) as client:
        response=await asyncio.wait_for(client.get('/v1/base/engines'),.3)
    assert response.status_code==503
    assert response.json()['detail']=='Base is unavailable. Your existing work has not changed.'


@pytest.mark.asyncio
@pytest.mark.parametrize('complete', [False, True])
async def test_deadline_closes_a_stalled_stream_and_never_sends_a_second_final_body(base,monkeypatch,complete):
    monkeypatch.setattr(base,'REQUEST_TIMEOUT',.01)
    messages=[]
    async def stalled(scope,receive,send):
        await send({'type':'http.response.start','status':200,'headers':[]})
        if complete:await send({'type':'http.response.body','body':b'{}'})
        await asyncio.Event().wait()
    async def send(message):messages.append(message)
    await asyncio.wait_for(base.RequestDeadline(stalled)({'type':'http'},AsyncMock(),send),.2)
    assert len(messages)==2
    assert messages[-1]['type']=='http.response.body'
    assert not messages[-1].get('more_body',False)
    assert messages[-1]['body']==(b'{}' if complete else b'')


@pytest.mark.asyncio
async def test_trusted_tank_proxy_uses_only_the_room_key_and_refuses_a_missing_binding(monkeypatch):
    import os
    from fastapi import HTTPException
    from starlette.requests import Request
    from starlette.responses import Response
    source=subprocess.check_output(['node','-e',"process.stdout.write(require('./tests/base_gate5_sources.cjs').read('tank/main.py'))"],cwd=ROOT,text=True)
    function=next(node for node in ast.parse(source).body if isinstance(node,ast.AsyncFunctionDef) and node.name=='base_proxy')
    function.decorator_list=[]
    transport=SimpleNamespace(request=AsyncMock(return_value=httpx.Response(202,json={'task':'recorded'})))
    namespace={'os':os,'HTTPException':HTTPException,'Request':Request,'Response':Response,'httpx':httpx,
               '_BASE_ROUTES':{'run'},'_http':transport,'BASE_AGENT_URL':'http://fake-room'}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),'proposed-base-proxy','exec'),namespace)
    request=Request({'type':'http','method':'POST','path':'/v1/base/run','query_string':b'',
                     'headers':[(b'x-tank-key',b'placeholder-workspace-key'),(b'content-type',b'application/json')]},
                    receive=AsyncMock(return_value={'type':'http.request','body':b'{}','more_body':False}))
    monkeypatch.delenv('TANK_KEY_BASE',raising=False)
    with pytest.raises(HTTPException) as missing:
        await namespace['base_proxy']('run',request)
    assert missing.value.status_code==503 and missing.value.detail=='Missing setting: TANK_KEY_BASE'
    transport.request.assert_not_awaited()
    monkeypatch.setenv('TANK_KEY_BASE','placeholder-room-key')
    assert (await namespace['base_proxy']('run',request)).status_code==202
    headers=transport.request.await_args.kwargs['headers']
    assert headers=={'X-Tank-Key':'placeholder-room-key','content-type':'application/json'}


@pytest.mark.asyncio
async def test_public_file_dns_has_a_total_deadline(monkeypatch):
    from engines.ffl import reference_source
    async def stuck(*args): await asyncio.Event().wait()
    monkeypatch.setattr(reference_source,'public_destination',stuck)
    monkeypatch.setattr(reference_source,'DNS_TIMEOUT',.01)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(reference_source.destination('https://recorded.example/file.csv'),.2)


def test_shared_patch_stack_is_integrated_without_modifying_sources():
    import hashlib
    files = set()
    for patch in (ROOT/"tank-patches/base").glob("gate[45].patch"):
        files.update(line[6:] for line in patch.read_text().splitlines() if line.startswith("+++ b/"))
    before = {file: hashlib.sha256((ROOT/file).read_bytes()).hexdigest() for file in files}
    assert files and all((ROOT/file).is_file() for file in files)
    result = subprocess.run(['node', '-e', "const {root,sources}=require('./tests/base_gate5_sources.cjs');const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');for(const [file,source] of sources)assert.equal(source,fs.readFileSync(path.join(root,file),'utf8'));"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {file: hashlib.sha256((ROOT/file).read_bytes()).hexdigest() for file in files} == before


def test_offline_browser_journeys_and_shared_security_patch():
    result = subprocess.run(['node', 'tests/base_gate5_journeys.cjs'], cwd=ROOT, capture_output=True, text=True, timeout=110)
    assert result.returncode == 0, result.stdout + result.stderr
