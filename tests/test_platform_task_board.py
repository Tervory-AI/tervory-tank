import uuid
from unittest.mock import AsyncMock

import priority_queue
import pytest
from test_tank_tenant_boundaries import boundary  # noqa: F401


async def seed(b, tenant, *, outcome='delivered', reference=None):
    ledger, task = reference or uuid.uuid4(), uuid.uuid4()
    async with b.pool.acquire() as conn:
        if reference is None:
            await conn.execute("""INSERT INTO tank.ledger(id,tenant_id,agent,task_type,rung,model,outcome)
                VALUES($1,$2,'tier0','fixture.board',1,'offline-model',$3)""", ledger, tenant, outcome)
            await conn.execute("""INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content)
                VALUES($1,$2,'fixture.board','[]','Offline answer')""", ledger, tenant)
        await conn.execute("""INSERT INTO tank.tasks(id,tenant_id,title,input,status,ledger_id,result)
            VALUES($1,$2,'Offline task','[]','done',$3,'Offline answer')""", task, tenant, ledger)
    return task, ledger


@pytest.mark.asyncio
async def test_receipt_states_wrong_note_and_tenant_boundary(boundary):  # noqa: F811
    b = boundary
    own, other = b.tenants
    task, ledger = await seed(b, own)
    foreign_task, foreign_ledger = await seed(b, other)
    unverified, _ = await seed(b, own, outcome='unverified')
    broken, _ = await seed(b, own, reference=foreign_ledger)
    headers = {'X-Tervory-User':'client-a', 'X-Tervory-Tenant':str(own)}
    rows = (await b.client.get('/v1/task-board', headers=headers)).json()
    assert {r['id'] for r in rows} == {str(task), str(unverified), str(broken)}
    assert all(r['status'] == r['board_state'] for r in rows)
    states = {r['id']:r['board_state'] for r in rows}
    assert states[str(task)] == 'delivered' and states[str(unverified)] == states[str(broken)] == 'unverified'
    assert next(r for r in rows if r['id'] == str(broken))['model'] is None
    path = '/v1/tasks/'+str(task)+'/feedback'
    for note in ('', '  ', 'x'*1001):
        assert (await b.client.post(path, headers=headers, json={'feedback':'wrong','note':note})).status_code == 422
    assert (await b.client.post('/v1/tasks/'+str(foreign_task)+'/feedback', headers=headers,
        json={'feedback':'wrong','note':'Must not write another tenant.'})).status_code == 404
    result = await b.client.post(path, headers=headers,
        json={'feedback':'wrong','note':'  The total is incorrect.  ','tenant_id':str(other),'by':'forged'})
    assert result.status_code == 200 and result.json()['board_state'] == 'unverified'
    async with b.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT feedback,feedback_note,feedback_by,outcome FROM tank.ledger WHERE id=$1 AND tenant_id=$2', ledger, own)
        assert dict(row) == {'feedback':'rejected','feedback_note':'The total is incorrect.','feedback_by':'client-a','outcome':'delivered'}
        assert await conn.fetchval('SELECT verdict FROM tank.evals WHERE ledger_id=$1 AND tenant_id=$2', ledger, own) == 'rejected'
        assert await conn.fetchval('SELECT feedback FROM tank.ledger WHERE id=$1 AND tenant_id=$2', foreign_ledger, other) is None
    assert (await b.client.post('/v1/tasks/'+str(unverified)+'/feedback', headers=headers, json={'feedback':'accepted'})).status_code == 404
    assert (await b.client.post('/v1/tasks/'+str(unverified)+'/feedback', headers=headers, json={'feedback':'wrong','note':'Incorrect total.'})).status_code == 200


@pytest.mark.asyncio
async def test_feedback_rollback_is_atomic(boundary, monkeypatch):  # noqa: F811
    import training
    b = boundary
    _, ledger = await seed(b, b.tenants[0])
    monkeypatch.setattr(training, 'collect_ledger', AsyncMock(side_effect=RuntimeError('offline failure')))
    with pytest.raises(RuntimeError):
        await b.tank.ledger_feedback(ledger, b.tank.Feedback(tenant_id=b.tenants[0], feedback='wrong', note='Incorrect total.'))
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT feedback FROM tank.ledger WHERE id=$1 AND tenant_id=$2', ledger, b.tenants[0]) is None
        assert await conn.fetchval('SELECT count(*) FROM tank.evals WHERE ledger_id=$1 AND tenant_id=$2', ledger, b.tenants[0]) == 0


@pytest.mark.asyncio
async def test_deferred_task_waits_for_durable_completion(boundary, monkeypatch):  # noqa: F811
    b = boundary
    task, job = await seed(b, b.tenants[0], outcome='queued')
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.offpeak_jobs(id,tenant_id,region,request,policy,task_id)
            VALUES($1,$2,'us-east','{}','{}',$3)""", job, b.tenants[0], task)
        await conn.execute("UPDATE tank.tasks SET status='queued',ledger_id=NULL,result=NULL WHERE id=$1 AND tenant_id=$2", task, b.tenants[0])
    monkeypatch.setattr(b.tank, 'run_route', AsyncMock(return_value=priority_queue.QueuedResponse(id=job, ledger_id=job)))
    req = b.tank.RouteRequest(tenant_id=b.tenants[0], messages=[b.tank.Message(role='user',content='Offline input')])
    await b.tank._run_task(task, req)
    row = await b.tank.get_task(task, b.tenants[0])
    assert row['status'] == 'queued' and row['finished_at'] is None and row['ledger_id'] == job
    async with b.pool.acquire() as conn:
        await priority_queue._finish(b.tank, conn, {'id':job,'tenant_id':b.tenants[0]}, error='dispatch_failed', uncertain=True)
    row = await b.tank.get_task(task, b.tenants[0])
    assert row['status'] == 'failed' and row['board_state'] == 'unverified' and row['finished_at'] is not None


def test_workspace_feedback_uses_server_identity_and_home():
    import subprocess
    from pathlib import Path
    result = subprocess.run(['node','tests/platform/feedback.cjs'], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout+result.stderr
