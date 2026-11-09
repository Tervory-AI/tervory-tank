"""Drive the shipped room worker; configure policy at real fake-network edges."""
import asyncio
import json
import uuid


async def configure_ladder(conn, stack):
    from engine_models import OPEN
    from paid_steps import model_step, register
    # Local rungs are explicitly offline. Every configured open rung is on the
    # fake gateway roster; real ladder and paid admission remain in control.
    await conn.execute("UPDATE tank.policy SET cache_scope='none',shadow_rate=0,candidate_model=NULL WHERE task_type='tisan.plan'")
    for tenant in (stack.tenant, stack.other_tenant):
        for model in (*OPEN, 'luna'):
            await register(conn, model_step('tisan.plan', model, agent='tisan'), 'tisan', 'model',
                           'tank.policy', task='tisan.plan', model=model)
            await conn.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) "
                "VALUES($1,$2,'auto','placeholder-test-admin') ON CONFLICT DO NOTHING",
                uuid.UUID(tenant), model_step('tisan.plan', model, agent='tisan'))


async def finish_job(tisan, job_id, tenant):
    from chassis.app import _context
    from chassis.worker import claim_next, run_claimed
    from chassis.tenant_db import tenant_scope
    app = tisan.runtime.app.app
    # Competing callers really contend for the same SQL claim. One runs the
    # handler; the other reads its durable result, never a test-side planner.
    with tenant_scope(tenant):
        for _ in range(200):
            async with app.state.pool.acquire() as conn:
                job = await claim_next(conn, 'tisan')
                if job:
                    await run_claimed(conn, 'tisan', job, app.state.handlers,
                                      lambda row: _context(app, 'tisan', row))
                row = await conn.fetchrow('SELECT status,result,error FROM agent_tisan.jobs WHERE tenant_id=$1 AND id=$2',
                                          uuid.UUID(tenant), uuid.UUID(job_id))
            if row['status'] == 'done':
                result = row['result']
                return json.loads(result) if isinstance(result, str) else result
            if row['status'] == 'failed' or row['error']:
                raise RuntimeError('Actual Tisan worker failed: ' + str(row['error']) + ' ' + str(tisan.events))
            await asyncio.sleep(.01)
    raise AssertionError('Actual Tisan worker did not complete')


async def assert_checkpoint_replay(tisan):
    import main
    from tisan_fixture import USER_A
    run = str(uuid.uuid4())
    tisan.transport_outage = 'list'
    before = len(tisan.provider_calls)
    first = await tisan.plan('placeholder checkpoint replay', run_id=run)
    job = uuid.uuid5(uuid.UUID(tisan.stack.tenant), json.dumps([USER_A, run]))
    # A recovered worker replays the durable logical job after a lost completion
    # acknowledgement. Memory remains unavailable, forcing the real Tank call.
    with __import__('chassis.tenant_db', fromlist=['tenant_scope']).tenant_scope(tisan.stack.tenant):
        async with tisan.runtime.app.app.state.pool.acquire() as conn:
            await conn.execute("UPDATE agent_tisan.jobs SET status='queued',result=NULL,run_at=now() WHERE tenant_id=$1 AND id=$2",
                               uuid.UUID(tisan.stack.tenant), job)
    second = await tisan.plan('placeholder checkpoint replay', run_id=run)
    assert len(tisan.provider_calls) == before + 1
    assert first['brain_receipt']['ledger_ids'] == second['brain_receipt']['ledger_ids']
    async with main.pool().acquire() as conn:
        rows = await conn.fetch('SELECT state,run_id FROM tank.paid_step_calls WHERE tenant_id=$1', uuid.UUID(tisan.stack.tenant))
    assert rows and all(row['state'] == 'completed' for row in rows)


async def assert_unsigned_task(tisan):
    import httpx
    from tisan_fixture import KEY, USER_A, USER_B
    before, calls = await tisan.records(), len(tisan.provider_calls)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tisan.room), base_url='http://agent-tisan:8000') as raw:
        response = await raw.post('/plan/start', headers={'X-Tank-Key': KEY, 'X-Tervory-Admin': USER_A,
            'X-Tervory-User-Assertion': 'invalid'}, json={'tenant_id': tisan.stack.tenant,
            'run_id': str(uuid.uuid4()), 'brief': {**tisan.last_brief, 'user_id': USER_B}})
    assert response.status_code == 200, response.text
    result = await finish_job(tisan, response.json()['job_id'], tisan.stack.tenant)
    assert result['brain_receipt']['paid_calls'] == 1 and result['brain_receipt']['memory_id'] is None
    assert len(tisan.provider_calls) == calls + 1 and await tisan.records() == before
