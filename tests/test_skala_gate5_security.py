import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest
import skala
import skala_jobs
import gold
from test_skala_approval_safety import database as _database, package
from test_skala_finish_jobs import room_runtime

database = _database


@pytest.mark.asyncio
async def test_skill_timeout_cancels_work_without_replay(monkeypatch):
    started, stopped = [], []
    async def slow(payload, ctx):
        started.append(1)
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append(1)
    monkeypatch.setattr(skala, '_import_run', lambda pkg: slow)
    monkeypatch.setattr(skala, 'SKILL_TIMEOUT_SECONDS', .02)
    with pytest.raises(RuntimeError, match='did not finish in time'):
        await skala.run_skill(SimpleNamespace(ref='base.offline@1.0.0'), {}, None)
    assert started == stopped == [1]


@pytest.mark.parametrize('location', ['run.py', 'helper.py', 'evals', 'skill.yaml'])
def test_package_symlinks_cannot_read_or_execute_outside_content(tmp_path, location):
    pkg = package(tmp_path)
    outside = tmp_path / 'outside'
    outside.write_text('offline-private-placeholder')
    target = pkg.path / location
    target.unlink(missing_ok=True)
    target.symlink_to(outside)
    for operation in (lambda: skala.source_files(pkg), lambda: skala.package_hash(pkg), lambda: skala._import_run(pkg)):
        with pytest.raises(ValueError, match='symbolic links'):
            operation()


def test_invalid_package_does_not_log_parser_values(tmp_path, caplog):
    path = tmp_path / 'base.offline/1.0.0'
    path.mkdir(parents=True)
    (path / 'skill.yaml').write_text('offline-private-placeholder: [ invalid')
    assert skala.load_packages(tmp_path) == {}
    assert 'offline-private-placeholder' not in caplog.text
    assert 'invalid package skipped' in caplog.text


@pytest.mark.asyncio
async def test_provider_exception_is_not_stored_in_eval_result(tmp_path, monkeypatch):
    pkg = package(tmp_path)
    async def failed(*args):
        raise ValueError('offline-private-placeholder')
    monkeypatch.setattr(skala, 'run_skill', failed)
    result = await skala.run_evals(pkg, lambda: SimpleNamespace(cost_usd=0, calls=0))
    assert result['passed'] == 0
    assert 'offline-private-placeholder' not in json.dumps(result)
    assert 'could not complete' in result['details'][0]['why']


@pytest.mark.asyncio
async def test_evaluation_overlap_and_retry_return_one_durable_result(database, monkeypatch):
    import main
    from tenant_db import TenantPool
    monkeypatch.setattr(main, '_pool', TenantPool(database))
    monkeypatch.setattr(main, '_admin_pool', None)
    started, release = asyncio.Event(), asyncio.Event()
    calls = []
    @skala_jobs.single_evaluation
    async def evaluate(skill_id, version, body=None):
        calls.append((skill_id, version))
        started.set()
        await release.wait()
        return {'score': 1, 'receipt': 'offline-placeholder'}
    token = skala_jobs.request_key.set('offline-request-one')
    try:
        first = asyncio.create_task(evaluate('base.offline', '1.0.0', SimpleNamespace(by='founder')))
        await started.wait()
        # Another session must see the reservation before work finishes. A
        # scoped transaction here also deadlocks concurrent startup indexes.
        assert await database.fetchval("SELECT count(*) FROM tank.policy_log WHERE task_type='skala.evaluation' AND action='pending'") == 1
        async with database.acquire() as conn:
            await asyncio.wait_for(conn.execute("CREATE INDEX CONCURRENTLY eval_pending_probe ON tank.policy_log(action)"), 10)
        with pytest.raises(HTTPException) as duplicate:
            await evaluate('base.offline', '1.0.0', SimpleNamespace(by='founder'))
        assert duplicate.value.status_code == 409
        release.set()
        result = await first
        assert await evaluate('base.offline', '1.0.0', SimpleNamespace(by='founder')) == result
        assert len(calls) == 1
        assert await database.fetchval("SELECT count(*) FROM tank.policy_log WHERE task_type='skala.evaluation' AND action='complete'") == 1
        with pytest.raises(HTTPException):
            await evaluate('base.other', '1.0.0', SimpleNamespace(by='founder'))
    finally:
        release.set()
        skala_jobs.request_key.reset(token)


@pytest.mark.asyncio
async def test_interrupted_evaluation_is_not_replayed(database, monkeypatch):
    import main
    from tenant_db import TenantPool
    monkeypatch.setattr(main, '_pool', TenantPool(database))
    monkeypatch.setattr(main, '_admin_pool', None)
    calls = []
    @skala_jobs.single_evaluation
    async def evaluate(skill, version, body=None):
        calls.append(1)
        raise RuntimeError('offline failure')
    token = skala_jobs.request_key.set('offline-interrupted')
    try:
        with pytest.raises(RuntimeError):
            await evaluate('base.offline','1.0.0')
        with pytest.raises(HTTPException) as refused:
            await evaluate('base.offline','1.0.0')
        assert refused.value.status_code == 409
        assert calls == [1]
    finally:
        skala_jobs.request_key.reset(token)


@pytest.mark.asyncio
async def test_gold_wrong_tenant_and_concurrent_checks_cannot_duplicate_training(database, monkeypatch):
    room_runtime(database, monkeypatch, lambda request: (_ for _ in ()).throw(AssertionError('No external call')))
    owner, other = uuid4(), uuid4()
    value = {'record': 'offline-public-source'}
    while gold.is_holdout(owner, 'base.offline', value):
        value = {'record': str(uuid4())}
    ident = await gold.add_candidate(database, tenant=owner, agent='base', skill='base.offline',
        value=value, expected={'ok': True}, source='offline', ref='one')
    with pytest.raises(HTTPException) as denied:
        await gold.check(ident, gold.Verdict(action='right'), gold.Reviewer('other', other, True))
    assert denied.value.status_code == 404
    assert await gold.next_example('base','base.offline',actor=gold.Reviewer('other',other,True)) is None
    actor=gold.Reviewer('founder',owner,True)
    results=await asyncio.gather(*(gold.check(ident,gold.Verdict(action='right'),actor) for _ in range(2)), return_exceptions=True)
    assert sum(isinstance(r,HTTPException) and r.status_code==409 for r in results)==1
    assert sum(isinstance(r,dict) and r.get('ok') for r in results)==1
    assert await database.fetchval('SELECT count(*) FROM tank.training_pairs WHERE tenant_id=$1',owner)==1
    assert await database.fetchval('SELECT count(*) FROM tank.training_pairs WHERE tenant_id=$1',other)==0


@pytest.mark.asyncio
async def test_every_skala_http_route_rejects_anonymous_and_room_keys(monkeypatch):
    import httpx
    import main
    monkeypatch.setattr(main, 'DATABASE_URL', 'postgresql://offline-placeholder')
    monkeypatch.setattr(main, 'TANK_API_KEY', 'workspace-placeholder')
    monkeypatch.setattr(main, 'LITELLM_MASTER_KEY', 'model-placeholder')
    monkeypatch.setattr(main, '_agent_keys_synced', True)
    monkeypatch.setenv('TANK_KEY_TRIGGER', 'room-placeholder')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://local') as client:
        def walk(routes):
            for route in routes:
                if hasattr(route, 'original_router'):
                    yield from walk(route.original_router.routes)
                elif hasattr(route, 'path'):
                    yield route
        routes=[route for route in walk(main.app.routes) if route.path.startswith(('/v1/skala','/v1/gold'))]
        assert len(routes)>=12
        for route in routes:
            path=route.path
            for name in ('skill_id','skill'):
                path=path.replace('{'+name+'}', 'base.offline')
            path=path.replace('{version}', '1.0.0').replace('{example_id}',str(uuid4()))
            for method in route.methods & {'GET','POST'}:
                response=await client.request(method,path,json={} if method=='POST' else None)
                assert response.status_code in {401,404}, (method,path,response.status_code)
                if '/run' not in path:
                    response=await client.request(method,path,json={} if method=='POST' else None,headers={'x-tank-key':'room-placeholder'})
                    assert response.status_code in {401,403,404}, (method,path,response.status_code)


@pytest.mark.asyncio
@pytest.mark.parametrize('cancelled',[False,True])
async def test_training_provider_deadline_and_cancellation_reap_the_process(monkeypatch,cancelled):
    import training
    entered=asyncio.Event()
    class Process:
        killed=False
        calls=0
        async def communicate(self):
            self.calls+=1
            if self.killed:return b'',b''
            entered.set()
            await asyncio.Event().wait()
        def kill(self):self.killed=True
    process=Process()
    starts=[]
    async def start(*args,**kwargs):
        starts.append(args)
        assert kwargs['stderr']==asyncio.subprocess.DEVNULL
        return process
    monkeypatch.setattr(training.asyncio,'create_subprocess_exec',start)
    monkeypatch.setattr(training,'TRAINING_COMMAND_TIMEOUT_SECONDS',.02)
    task=asyncio.create_task(training._training_subprocess('--dry-run'))
    await entered.wait()
    if cancelled:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    else:
        result=await task
        assert result['status']=='Training operation failed; check configuration, budget and provenance.'
    assert len(starts)==1 and process.killed and process.calls==2
