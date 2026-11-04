"""Real SQL, founder cards and suspended continuations; no paid service calls."""
import asyncio
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import paid_steps as paid
from test_tank_tenant_boundaries import boundary  # noqa: F401

pytestmark = pytest.mark.paid_step_controls


async def waiting(b, *, after=None):
    async with asyncio.timeout(3):
        while True:
            rows = await paid.pending()
            found = [row for row in rows if row['id'] != after]
            if found:
                return found[-1]
            await asyncio.sleep(.01)


@pytest.mark.asyncio
async def test_each_step_asks_and_only_founder_can_approve_once(boundary, monkeypatch):  # noqa: F811
    b = boundary
    monkeypatch.setattr(paid, 'POLL_SECONDS', .01)
    spent = []
    async def run():
        for step in ('vendor.brave', 'hf.jobs.photogrammetry'):
            await paid.authorize(step, {'query':'private input'}, tenant=b.tenants[0])
            spent.append(step)
    work = asyncio.create_task(run())
    try:
        first = await waiting(b)
        assert spent == []
        assert await paid.mode('vendor.brave') == 'ask'
        route = '/v1/controls/paid-steps/approve'
        assert (await b.client.post(route, json={'approval_id':str(first['id'])})).status_code == 404
        founder = {'X-Tervory-Admin':'founder-fixture'}
        result = await b.client.post(route, headers=founder, json={'approval_id':str(first['id'])})
        assert result.status_code == 200, result.text
        assert (await b.client.post(route, headers=founder, json={'approval_id':str(first['id'])})).status_code == 409
        second = await waiting(b, after=first['id'])
        assert spent == ['vendor.brave']
        assert second['step_id'] == 'hf.jobs.photogrammetry'
        await b.client.post(route, headers=founder, json={'approval_id':str(second['id'])})
        await asyncio.wait_for(work, 3)
        assert spent == ['vendor.brave','hf.jobs.photogrammetry']
    finally:
        work.cancel()
        await asyncio.gather(work, return_exceptions=True)


@pytest.mark.asyncio
async def test_auto_is_individual_and_global_pause_overrides_it(boundary, monkeypatch):  # noqa: F811
    b = boundary
    monkeypatch.setattr(b.tank, '_roster_models', AsyncMock(return_value=[]))
    await paid.set_mode(paid.Setting(step_id='vendor.brave', mode='auto'), 'founder-fixture')
    assert await paid.mode('vendor.google_places') == 'ask'
    await paid.authorize('vendor.brave', {'input':'one'}, tenant=b.tenants[0])
    await b.pool.execute("INSERT INTO tank.controls(tenant_id,name,value,updated_by) VALUES($1,'paid_paused',true,'fixture')", paid.PLATFORM_TENANT)
    with pytest.raises(HTTPException, match='paid work is paused'):
        await paid.authorize('vendor.brave', {'input':'two'}, tenant=b.tenants[0])
    rows = await b.pool.fetch('SELECT * FROM tank.paid_step_log WHERE tenant_id=$1', paid.PLATFORM_TENANT)
    assert len(rows) == 1 and rows[0]['old_mode'] == 'ask' and rows[0]['new_mode'] == 'auto'


@pytest.mark.asyncio
async def test_wait_detaches_http_and_resumes_exact_coroutine(boundary, monkeypatch):  # noqa: F811
    b = boundary
    monkeypatch.setattr(paid, 'POLL_SECONDS', .01)
    app = FastAPI()
    app.add_middleware(paid.PaidRunMiddleware)
    calls = []
    @app.post('/v1/route')
    async def route():
        calls.append('free')
        await paid.authorize('vendor.brave', {'body':'bound input'}, tenant=b.tenants[0])
        calls.append('paid')
        return {'answer':'complete'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        result = await client.post('/v1/route')
    assert result.status_code == 202 and calls == ['free']
    info = result.json()
    approval = await waiting(b)
    await paid.decide(approval['id'], 'founder-fixture')
    async with asyncio.timeout(3):
        while True:
            status = await b.client.get(info['status_path'], params={'tenant_id':str(b.tenants[0])})
            assert status.status_code == 200, status.text
            if status.json()['status'] == 'completed':
                break
            await asyncio.sleep(.01)
    assert calls == ['free','paid']
    assert status.json()['result'] == {'answer':'complete'}
    assert (await b.client.get(info['status_path'], params={'tenant_id':str(b.tenants[1])})).status_code == 404


@pytest.mark.asyncio
async def test_changed_inputs_or_cancel_never_dispatch(boundary, monkeypatch):  # noqa: F811
    b = boundary
    monkeypatch.setattr(paid, 'POLL_SECONDS', .01)
    payload = {'input':'first'}
    work = asyncio.create_task(paid.authorize('vendor.brave', payload, tenant=b.tenants[0]))
    await waiting(b)
    payload['input'] = 'changed'
    with pytest.raises(HTTPException, match='inputs changed'):
        await work
    assert await b.pool.fetchval('SELECT count(*) FROM tank.paid_step_approvals WHERE tenant_id=$1 AND status=\'claimed\'', b.tenants[0]) == 0


def test_founder_tools_do_not_exist_for_clients():
    import command
    actor = command.Actor(uuid.uuid4(), 'client', False)
    assert not any(name.startswith('platform.paid') for name in command.allowed_tools(actor))


@pytest.mark.asyncio
async def test_chats_waits_for_founder_card_and_resumes_saved_turn(boundary, monkeypatch):  # noqa: F811
    import command
    from types import SimpleNamespace
    from trigger_routes import code_receipt
    b = boundary
    monkeypatch.setattr(paid, 'POLL_SECONDS', .01)
    called = []
    async def answer(actor, messages, **kwargs):
        await paid.authorize('vendor.brave', {'query':'bound'}, tenant=actor.tenant_id)
        called.append('paid')
        ledger = await code_receipt(actor.tenant_id, 'fixture', task_id=kwargs['task_id'])
        return SimpleNamespace(ledger_id=ledger, content='The saved answer.')
    monkeypatch.setattr(command, 'route_turn', answer)
    headers = {'X-Tervory-User':'founder-fixture','X-Tervory-Tenant':str(b.tenants[0])}
    thread = (await b.client.post('/v1/command/threads', headers=headers, json={})).json()['thread_id']
    result = await b.client.post(f'/v1/command/threads/{thread}/turn', headers=headers, json={'text':'Do the work'})
    assert result.status_code == 200, result.text
    assert called == []
    saved = (await b.client.get(f'/v1/command/threads/{thread}', headers=headers)).json()
    card = saved['cards'][0] if isinstance(saved['cards'], list) else next(iter(saved['cards'].values()))
    assert card['tool'] == 'platform.paid_step.approve'
    result = await b.client.post('/v1/command/cards/'+card['card_id'], headers=headers, json={'action':'confirm'})
    assert result.status_code == 200, result.text
    async with asyncio.timeout(3):
        while not called:
            await asyncio.sleep(.01)
    async with asyncio.timeout(3):
        while True:
            saved = (await b.client.get(f'/v1/command/threads/{thread}', headers=headers)).json()
            if any(m['role'] == 'assistant' for m in saved['messages']):
                break
            await asyncio.sleep(.01)
    assert called == ['paid']
    assert saved['messages'][-1]['content'] == 'The saved answer.'


@pytest.mark.asyncio
async def test_queued_ask_releases_pool_and_cannot_be_dispatched_twice(boundary, monkeypatch):  # noqa: F811
    import asyncpg
    import os
    import priority_queue
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace
    b = boundary
    name = await b.pool.fetchval('SELECT current_database()')
    single = await asyncpg.create_pool(os.environ['POOL_SCHEMA_DATABASE_URL'], database=name, min_size=1, max_size=1)
    monkeypatch.setattr(b.tank, '_pool', single)
    monkeypatch.setattr(paid, 'POLL_SECONDS', .01)
    monkeypatch.setattr(b.tank, '_roster_models', AsyncMock(return_value=[{'model_name':'luna','model_info':{}}]))
    monkeypatch.setattr(b.tank, '_batch_price', AsyncMock(return_value={'discount':1,'provider':'unsupported','native':'luna'}))
    monkeypatch.setattr(b.tank, '_call_upper', lambda *args:.01)
    req = b.tank.RouteRequest(tenant_id=b.tenants[0], task_type='base.normalize', priority='offpeak',
        deadline_at=datetime.now(UTC)+timedelta(minutes=5), messages=[{'role':'user','content':'queued input'}])
    policy = await b.tank.load_policy(req.task_type, req.tenant_id)
    item = b.tank._DeferredRoute(req, policy, [{'role':'user','content':'queued input'}], 100, {}, [], None)
    queued = await priority_queue.enqueue(b.tank, item)
    calls = []
    async def execute(*args, **kwargs):
        await paid.authorize(paid.model_step('luna'), {'input':'queued input'}, tenant=req.tenant_id)
        calls.append('sent')
        return SimpleNamespace(model_dump=lambda **kwargs:{'content':'done','ledger_id':str(queued.id)})
    monkeypatch.setattr(b.tank, 'run_route', execute)
    try:
        await asyncio.wait_for(priority_queue.process_once(b.tank, job_id=queued.id, tenant_id=req.tenant_id), 3)
        approval = await waiting(b)
        assert await asyncio.wait_for(single.fetchval('SELECT 1'), 1) == 1
        await priority_queue.process_once(b.tank, job_id=queued.id, tenant_id=req.tenant_id)
        assert calls == []
        await paid.decide(approval['id'], 'founder-fixture')
        async with asyncio.timeout(3):
            while (await priority_queue.status(b.tank, queued.id, req.tenant_id))['status'] != 'completed':
                await asyncio.sleep(.01)
        assert calls == ['sent']
    finally:
        for task in list(paid.LIVE):
            if not task.done():
                task.cancel()
        await asyncio.gather(*list(paid.LIVE), return_exceptions=True)
        await single.close()


@pytest.mark.asyncio
async def test_pause_changed_while_waiting_blocks_approved_dispatch(boundary, monkeypatch):  # noqa: F811
    b = boundary
    monkeypatch.setattr(paid, 'POLL_SECONDS', .01)
    sent = []
    async def operation():
        await paid.authorize('vendor.brave', {'input':'bound'}, tenant=b.tenants[0])
        sent.append(True)
    work = asyncio.create_task(operation())
    try:
        approval = await waiting(b)
        await paid.decide(approval['id'], 'founder-fixture')
        await b.pool.execute("INSERT INTO tank.controls(tenant_id,name,value,updated_by) VALUES($1,'paid_paused',true,'fixture')", paid.PLATFORM_TENANT)
        with pytest.raises(HTTPException, match='paid work is paused'):
            await asyncio.wait_for(work, 3)
        assert sent == []
    finally:
        work.cancel()
        await asyncio.gather(work, return_exceptions=True)


@pytest.mark.asyncio
async def test_hf_job_claim_waits_without_a_charged_receipt(boundary, monkeypatch):  # noqa: F811
    b = boundary
    monkeypatch.setenv('TANK_KEY_RIG', 'rig-offline-key')
    monkeypatch.setattr(paid, 'POLL_SECONDS', .01)
    tenant, job = b.tenants[0], uuid.uuid4()
    await b.pool.execute('''INSERT INTO tank.rig_forge_limits
        (tenant_id,method,enabled,image,flavor,hour_usd,billing_quantum_seconds,max_seconds,max_job_usd,total_budget_usd)
        VALUES($1,'trellis2',true,$2,'a10g-small',1,60,600,1,1)''', tenant,
        'ghcr.io/tervory-ai/rig-forge-trellis2@sha256:'+'a'*64)
    body = {'tenant_id':str(tenant),'job_id':str(job),'home_region':'us-east'}
    headers = {'X-Tank-Key':'rig-offline-key'}
    response = await b.client.post('/v1/agents/rig/forge/reserve', headers=headers,
        json={**body,'method':'trellis2','timeout_seconds':600,'cost_cap_usd':'1'})
    assert response.status_code == 200, response.text
    response = await b.client.post('/v1/agents/rig/forge/claim', headers=headers, json=body)
    assert response.status_code == 202, response.text
    try:
        approval = await waiting(b)
        assert approval['step_id'] == 'hf.jobs.trellis2'
        assert await b.pool.fetchval('SELECT state FROM tank.rig_forge_jobs WHERE tenant_id=$1 AND id=$2', tenant, job) == 'reserved'
        assert await b.pool.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND task_id=$2', tenant, job) == 0
        await paid.decide(approval['id'], 'founder-fixture')
        async with asyncio.timeout(3):
            while await b.pool.fetchval('SELECT state FROM tank.rig_forge_jobs WHERE tenant_id=$1 AND id=$2', tenant, job) != 'claimed':
                await asyncio.sleep(.01)
        assert await b.pool.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND task_id=$2', tenant, job) == 1
        assert (await b.client.post('/v1/agents/rig/forge/claim', headers=headers, json=body)).status_code == 409
    finally:
        for task in list(paid.LIVE):
            if not task.done():
                task.cancel()
        await asyncio.gather(*list(paid.LIVE), return_exceptions=True)


@pytest.mark.asyncio
async def test_model_rungs_are_independent_and_cancel_or_expiry_never_spends(boundary, monkeypatch):  # noqa: F811
    b = boundary
    from datetime import UTC, datetime, timedelta
    monkeypatch.setattr(paid, 'POLL_SECONDS', .01)
    for expired in (False, True):
        async def operation():
            if expired:
                paid.current().deadline = datetime.now(UTC)-timedelta(seconds=1)
            await paid.authorize(paid.model_step('luna',2), {'input':'bound'}, tenant=b.tenants[0])
            pytest.fail('Cancelled or expired step dispatched')
        work = asyncio.create_task(operation())
        if expired:
            with pytest.raises(HTTPException, match='expired'):
                await asyncio.wait_for(work, 3)
        else:
            approval = await waiting(b)
            assert approval['step_id'] == 'model.rung2.luna'
            await paid.decide(approval['id'], 'founder-fixture', approve=False)
            with pytest.raises(HTTPException, match='no longer available'):
                await asyncio.wait_for(work, 3)
    assert await paid.mode(paid.model_step('luna',1)) == 'ask'
    assert await paid.mode(paid.model_step('luna',2)) == 'ask'


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
async def test_room_protocol_waits_then_returns_original_completion(boundary, monkeypatch, stream):  # noqa: F811
    import agent_skills
    b = boundary
    monkeypatch.setenv('TANK_KEY_BASE', 'base-offline-key')
    monkeypatch.setattr(paid, 'POLL_SECONDS', .01)
    calls = []
    async def completion(*args, **kwargs):
        await paid.authorize(paid.model_step('luna'), {'input':'bound'}, tenant=b.tenants[0])
        calls.append('sent')
        return {'id':'saved','created':1,'model':'luna','usage':{},'receipt':{},
                'choices':[{'index':0,'message':{'role':'assistant','content':'done'},'finish_reason':'stop'}]}
    monkeypatch.setattr(agent_skills, 'complete', completion)
    work = asyncio.create_task(b.client.post('/v1/agents/base/chat/completions',
        headers={'X-Tank-Key':'base-offline-key','X-Tenant-ID':str(b.tenants[0])},
        json={'stream':stream,'messages':[{'role':'user','content':'bound'}]}))
    try:
        row = await waiting(b)
        assert not calls and not work.done()
        await paid.decide(row['id'], 'founder-fixture')
        response = await asyncio.wait_for(work, 3)
        assert response.status_code == 200 and calls == ['sent']
        if stream:
            assert 'waiting for founder approval' in response.text and 'data: [DONE]' in response.text
        else:
            assert response.json()['choices'][0]['message']['content'] == 'done'
    finally:
        work.cancel()
        await asyncio.gather(work, return_exceptions=True)


@pytest.mark.asyncio
async def test_settings_available_through_code_only_founder_chat(boundary, monkeypatch):  # noqa: F811
    import command
    b = boundary
    monkeypatch.setattr(b.tank, '_roster_models', AsyncMock(return_value=[{'model_name':'luna'}]))
    actor = command.Actor(b.tenants[0], 'founder-fixture', True)
    plan = await paid.code_plan(actor, [{'role':'user','content':'/paid-step model.rung2.luna auto'}], uuid.uuid4())
    import json
    action = json.loads(plan.content)['actions'][0]
    assert action['tool'] == 'platform.paid_step.set'
    assert action['arguments'] == {'step_id':'model.rung2.luna','mode':'auto'}
    method, path, params, body = command.adapter_request(command.PlannedAction(**action), actor)
    assert method == 'PUT' and params == {} and body == action['arguments']
    result = await b.client.put(path, headers={'X-Tervory-Admin':'founder-fixture'}, json=body)
    assert result.status_code == 200, result.text
    assert await paid.mode('model.rung2.luna') == 'auto'
    assert await paid.mode('model.rung1.luna') == 'ask'


@pytest.mark.asyncio
async def test_schema_reapply_enables_paid_table_rls_and_lease_boolean(boundary):  # noqa: F811
    from pathlib import Path
    b = boundary
    schema = (Path(__file__).resolve().parents[1]/'tank/schema.sql').read_text()
    await b.pool.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
    await b.pool.execute(schema)
    tables = await b.pool.fetch("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace='tank'::regnamespace AND relname IN ('paid_step_settings','paid_step_log','paid_step_workers','paid_runs','paid_step_approvals')")
    assert len(tables) == 5 and all(row['relrowsecurity'] and row['relforcerowsecurity'] for row in tables)
    await paid.heartbeat()
    assert await b.pool.fetchval('SELECT tank.paid_worker_alive($1)', paid.SERVER)
    assert not await b.pool.fetchval('SELECT tank.paid_worker_alive($1)', uuid.uuid4())
