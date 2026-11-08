"""Additional rollout gaps: real Ask-mode journal and combined layer receipts."""
from datetime import timedelta
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import exact_cache
import paid_steps
import priority_queue as queue
from test_tank_tenant_boundaries import boundary as boundary_fixture
from test_tank_ladder import ladder as ladder_fixture, request
from test_tank_priority_offpeak import prepare
from test_engine_exact_cache import setup, run

boundary = boundary_fixture
ladder = ladder_fixture
REAL_ADMIT = paid_steps.admit


@pytest.mark.asyncio
async def test_c1_returned_receipt_preserves_other_layers(monkeypatch):
    monkeypatch.setenv('ENGINE_C1_ENABLED', '1')
    existing = {'C4': {'attempts': 2, 'hits': 1, 'saved_usd': 0.},
                'C5': {'attempts': 1, 'hits': 1, 'cached_tokens': 20}}
    answer = SimpleNamespace(engine={'cache_layers': existing}, cache_layer='C1',
        cache_backend='tank-sql', model='placeholder-model', tokens_in=20, tokens_out=10,
        content='placeholder answer', ledger_id='placeholder-ledger')
    answer.model_copy = lambda *, update: SimpleNamespace(**update)
    conn = SimpleNamespace(execute=AsyncMock())
    class Acquire:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *args):
            pass
    rt = SimpleNamespace(RouteResponse=SimpleNamespace, box_region=lambda: 'us-east',
        pool=lambda: SimpleNamespace(acquire=Acquire), _roster_models=AsyncMock(return_value=[]))
    req = SimpleNamespace(tenant_id='placeholder-tenant', task_type='placeholder-task',
        case_ref=None, messages=[])
    result = await exact_cache.record(rt, req, {'cache_scope': 'tenant', 'cache_ttl_s': 60}, answer)
    assert result.engine['cache_layers'] == {**existing, 'C1': {
        'attempts': 1, 'hits': 1, 'saved_usd': None, 'estimated': True}}
    assert answer.engine['cache_layers'] == existing


@pytest.mark.asyncio
async def test_policy_correction_and_rejection_invalidate_exact_answer(ladder, monkeypatch):
    monkeypatch.setenv('ENGINE_C1_ENABLED', '1')
    b = ladder
    req = await setup(b, monkeypatch)
    first = await run(b, req)
    assert (await run(b, req)).cache_layer == 'C1'
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET system_prompt='placeholder corrected instruction' WHERE tenant_id=$1 AND task_type=$2",
                           req.tenant_id, req.task_type)
    corrected = await run(b, req)
    assert corrected.cache_layer is None and len(b.sent) == 2
    assert (await run(b, req)).cache_layer == 'C1'
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.ledger SET feedback='rejected' WHERE tenant_id=$1 AND id=$2",
                           req.tenant_id, corrected.ledger_id)
    refreshed = await run(b, req)
    assert refreshed.cache_layer is None and len(b.sent) == 3
    assert b.sent[-1]['cache']['no-cache'] is True
    assert first.ledger_id != refreshed.ledger_id


@pytest.mark.asyncio
async def test_deferred_ask_keeps_grant_and_replays_once_before_deadline(ladder, monkeypatch):
    b = ladder
    monkeypatch.setenv('ENGINE_I8_ENABLED', '1')
    clock, _ = await prepare(b, monkeypatch)
    # Undo both protocol fixtures' Auto wrappers. Admission uses the real Ask
    # journal; only the provider gateway and the clock remain fixtures.
    monkeypatch.setattr(paid_steps, 'admit', REAL_ADMIT)
    req = request(b, b.tenants[0], text='placeholder approval-bound deferred work',
                  interactive=False, priority='offpeak')
    req.deadline = clock[0] + timedelta(hours=3)
    context = paid_steps.Run(req.tenant_id, uuid.uuid4(), paid_steps.fingerprint(req.model_dump()))
    with paid_steps.run_scope(context):
        with pytest.raises(paid_steps.ApprovalRequired) as stopped:
            await b.tank.run_route(req)
        assert not b.sent
        async with b.pool.acquire() as conn:
            assert await conn.fetchval('SELECT count(*) FROM tank.offpeak_jobs WHERE tenant_id=$1', req.tenant_id) == 0
            approval = await conn.fetchrow('SELECT * FROM tank.paid_step_approvals WHERE tenant_id=$1 AND id=$2',
                                          req.tenant_id, stopped.value.approval_id)
        assert approval['state'] == 'pending' and approval['authorization_mode'] == 'pending'
        await paid_steps.decide(req.tenant_id, approval['id'], user='placeholder-admin',
                                approve=True, reason='placeholder fixture approval')
        job = await b.tank.run_route(req)
    async with b.pool.acquire() as conn:
        snapshot = json.loads(await conn.fetchval('SELECT policy FROM tank.offpeak_jobs WHERE tenant_id=$1 AND id=$2', req.tenant_id, job.id))
    assert snapshot['paid_run']['tenant_id'] == str(req.tenant_id)
    assert snapshot['paid_run']['run_id'] == str(context.run_id)
    assert approval['request_hash'] == snapshot['paid_run']['request_hash']
    await queue.process_once(b.tank)
    assert not b.sent
    assert (await queue.status(b.tank, job.id, req.tenant_id))['status'] == 'queued'
    clock[0] += timedelta(hours=2)
    await queue.process_once(b.tank)
    await queue.process_once(b.tank)
    result = await queue.status(b.tank, job.id, req.tenant_id)
    assert result['status'] == 'completed' and len(b.sent) == 1
    assert result['result']['ledger_id'] == str(job.id) and clock[0] < req.deadline
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.paid_step_approvals WHERE tenant_id=$1', req.tenant_id) == 1
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND id=$2', req.tenant_id, job.id) == 1
        assert await conn.fetchval('SELECT state FROM tank.paid_step_approvals WHERE tenant_id=$1 AND id=$2', req.tenant_id, approval['id']) == 'approved'
