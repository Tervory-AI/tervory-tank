"""I8 automatic scheduling: actual router/SQL, fake providers and a frozen clock."""
from contextvars import ContextVar
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

import exact_cache
import priority_queue as queue
import product_identity
from test_tank_tenant_boundaries import boundary as boundary_fixture
from test_tank_ladder import ladder as ladder_fixture, request
from test_tank_priority_offpeak import prepare
from test_tank_batch_providers import setup as batch_setup

boundary = boundary_fixture
ladder = ladder_fixture


async def eligible(b, value=True):
    async with b.pool.acquire() as conn:
        await conn.execute('UPDATE tank.policy SET batch_eligible=$2 WHERE tenant_id=$1', b.tenants[0], value)


@pytest.mark.asyncio
async def test_automatic_job_waits_for_cheaper_window_and_preserves_user(ladder, monkeypatch):
    b = ladder
    clock, _ = await prepare(b, monkeypatch)
    await eligible(b)
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET cache_scope='tenant' WHERE tenant_id=$1", b.tenants[0])
    actor = product_identity.User(str(b.tenants[0]), 'placeholder-user-a', 'member')
    monkeypatch.setattr(product_identity, 'current', ContextVar('placeholder-scheduled-user', default=actor))
    req = request(b, b.tenants[0], text='placeholder scheduled request', interactive=False, priority='standard')
    req.deadline = clock[0] + timedelta(hours=3)
    selected = await b.tank.load_policy(req.task_type, req.tenant_id)
    messages = [m.model_dump() for m in req.messages]
    if selected['system_prompt']:
        messages.insert(0, {'role': 'system', 'content': selected['system_prompt']})
    identity = b.tank._cache_identity(req, selected, messages,
        min(req.max_tokens or selected['max_tokens_out'], selected['max_tokens_out']), None)
    namespace = exact_cache.request_options(req, selected, identity, selected['model'])['cache']['namespace']
    job = await b.tank.run_route(req)
    assert isinstance(job, queue.QueuedResponse) and not b.sent
    view = await queue.status(b.tank, job.id, req.tenant_id)
    assert view['schedule']['dispatch_at'] == (clock[0] + timedelta(hours=2)).isoformat()
    # A worker may inherit another job's context; the saved actor must win.
    foreign = product_identity.User(str(b.tenants[1]), 'placeholder-user-b', 'member')
    product_identity.current.set(foreign)
    await queue.process_once(b.tank)
    assert not b.sent
    clock[0] += timedelta(hours=2)
    await queue.process_once(b.tank)
    result = (await queue.status(b.tank, job.id, req.tenant_id))['result']
    assert result['ledger_id'] == str(job.id) and result['cost_usd'] == pytest.approx(.00004206)
    assert b.sent[0]['cache']['namespace'] == namespace
    assert product_identity.current.get() == foreign
    await queue.process_once(b.tank)
    assert len(b.sent) == 1
    with pytest.raises(b.tank.HTTPException) as denied:
        await queue.status(b.tank, job.id, b.tenants[1])
    assert denied.value.status_code == 404
    product_identity.current.set(actor)
    repeated = await b.tank.run_route(req)
    assert repeated.cost_usd == 0 and repeated.cache_layer == 'C1'
    assert len(b.sent) == 1  # Free answers return before automatic deferral.


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['urgent', 'interactive', 'ineligible', 'deadline', 'no_discount'])
async def test_automatic_waiting_never_delays_ineligible_or_unrewarded_work(ladder, monkeypatch, case):
    b = ladder
    clock, _ = await prepare(b, monkeypatch, window=case != 'no_discount')
    await eligible(b, case != 'ineligible')
    req = request(b, b.tenants[0], text='placeholder immediate request',
        interactive=case == 'interactive', priority='urgent' if case == 'urgent' else 'standard')
    req.deadline = clock[0] + timedelta(hours=1 if case == 'deadline' else 3)
    result = await b.tank.run_route(req)
    assert isinstance(result, b.tank.RouteResponse) and len(b.sent) == 1
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.offpeak_jobs WHERE tenant_id=$1', req.tenant_id) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('entry', ['run_route', 'route'])
async def test_automatic_provider_batch_uses_bounded_default_deadline(ladder, monkeypatch, entry):
    b = ladder
    stub, body = await batch_setup(b, monkeypatch, 'openai', count=1)
    req = body.requests[0].model_copy(update={'priority': 'standard'})
    req.messages[-1].content = 'placeholder batch request 0'
    at = queue.now()
    monkeypatch.setattr(queue, 'now', lambda: at)
    kick = Mock()
    monkeypatch.setattr(queue, 'kick', kick)
    job = await getattr(b.tank, entry)(req, caller=None)
    assert kick.call_count == int(entry == 'route')
    view = await queue.status(b.tank, job.id, req.tenant_id)
    assert view['schedule']['mode'] == 'batch'
    assert view['schedule']['deadline'] == (at + timedelta(hours=24, seconds=120)).isoformat()
    await queue.process_once(b.tank)
    await b.tank.process_batches_once()
    assert len(stub.submissions()) == 1 and not b.sent
    stub.finished = True
    await b.tank.process_batches_once()
    await queue.process_once(b.tank)
    result = (await queue.status(b.tank, job.id, req.tenant_id))['result']
    assert float(result['cost_usd']) == pytest.approx(.00035)
    assert result['discount_usd'] == pytest.approx(.00035)
    assert result['engine']['cache_layers']['C5']['attempts'] == 0


@pytest.mark.asyncio
async def test_free_rungs_and_moa_never_enter_automatic_waiting(ladder, monkeypatch):
    b = ladder
    req = request(b, b.tenants[0], text='placeholder free request', interactive=False)
    price = AsyncMock(side_effect=AssertionError('free and MoA do not need price-window discovery'))
    monkeypatch.setattr(b.tank, '_batch_price', price)
    for settings in ({'model': 'local'}, {'model': 'local-large'}, {'model': 'placeholder', '_engine': {'free': True}},
                     {'model': 'placeholder', 'moa_enabled': True}):
        policy = {'priority': 'standard', 'batch_eligible': True, **settings}
        assert await queue.automatic_request(b.tank, req, policy, [], {}) is req
    for suffix in ('#engine-eval', '#engine-shadow', '#engine-judge', '#moa.check'):
        evaluation = req.model_copy(update={'task_type': req.task_type + suffix})
        policy = {'model': 'placeholder', 'priority': 'standard', 'batch_eligible': True}
        assert await queue.automatic_request(b.tank, evaluation, policy, [], {}) is evaluation
    price.assert_not_awaited()


def test_job_actor_clears_unsigned_context_and_rejects_other_tenant(monkeypatch):
    actor = product_identity.User('placeholder-tenant-a', 'placeholder-user-a', 'member')
    monkeypatch.setattr(product_identity, 'current', ContextVar('placeholder-actor', default=actor))
    with queue.job_actor({}, 'placeholder-tenant-b'):
        assert product_identity.current.get() is None
    assert product_identity.current.get() == actor
    with pytest.raises(HTTPException, match='Deferred actor'):
        with queue.job_actor({'actor': vars(actor)}, 'placeholder-tenant-b'):
            pytest.fail('foreign actor entered')
