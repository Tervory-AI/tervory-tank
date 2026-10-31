"""Batch by default for background work: priority=batch + interactive=false queues.

Real Tank/SQL where a database is configured; LiteLLM and provider batches are
stubbed. The client and Zenas tests need neither a database nor a network.
"""
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

import priority_queue as queue
from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_tank_ladder import ladder, policy, request  # noqa: F401
from test_tank_batch_providers import setup as batch_setup


async def _jobs(b, tenant):
    async with b.pool.acquire() as conn:
        return await conn.fetchval('SELECT count(*) FROM tank.offpeak_jobs WHERE tenant_id=$1', tenant)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
async def test_background_route_uses_provider_batch_and_labels_batch(ladder, monkeypatch, provider):  # noqa: F811
    b = ladder
    stub, body = await batch_setup(b, monkeypatch, provider, count=1)
    monkeypatch.setenv('TANK_BATCH_MIN', '50')
    req = body.requests[0].model_copy(update={'priority': 'batch', 'interactive': False})
    job = await b.tank.route(req, caller=None)
    assert isinstance(job, queue.QueuedResponse) and job.priority == 'batch'
    await asyncio.gather(*list(b.tank._background))
    await b.tank.process_batches_once()
    assert len(stub.submissions()) == 1 and not b.sent
    stub.finished = True
    await b.tank.process_batches_once()
    await queue.process_once(b.tank)
    status = await queue.status(b.tank, job.id, req.tenant_id)
    assert status['status'] == 'completed' and status['priority'] == 'batch'
    assert status['result']['content']
    async with b.pool.acquire() as conn:
        receipt = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2', job.id, req.tenant_id)
        assert receipt['batch'] and receipt['priority'] == 'batch' and receipt['outcome'] == 'delivered'
        # Same prices as the offpeak batch test: half the 0.0007 baseline.
        assert float(receipt['cost_usd']) == pytest.approx(0.00035)
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1', req.tenant_id) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('update', [
    {'priority': 'batch'},                                   # interactive defaults to true
    {'priority': 'batch', 'interactive': True},
    {'priority': 'urgent', 'interactive': False},            # the opt-out for an urgent run
    {'priority': 'standard', 'interactive': False},
])
async def test_interactive_or_opt_out_is_answered_now(ladder, monkeypatch, update):  # noqa: F811
    b = ladder
    stub, body = await batch_setup(b, monkeypatch, 'openai', count=1)
    req = body.requests[0].model_copy(update={'interactive': True, **update})
    result = await b.tank.route(req, caller=None)
    assert isinstance(result, b.tank.RouteResponse) and result.content
    assert len(b.sent) == 1 and not stub.calls
    assert await _jobs(b, req.tenant_id) == 0


@pytest.mark.asyncio
async def test_internal_run_route_is_unchanged_without_opt_in(ladder, monkeypatch):  # noqa: F811
    # Tasks, skills and the public batch endpoint call run_route directly; only
    # the public /v1/route entry may turn priority=batch into a queued job.
    b = ladder
    stub, body = await batch_setup(b, monkeypatch, 'openai', count=1)
    req = body.requests[0].model_copy(update={'priority': 'batch', 'interactive': False})
    result = await b.tank.run_route(req)
    assert isinstance(result, b.tank.RouteResponse) and len(b.sent) == 1
    assert await _jobs(b, req.tenant_id) == 0


@pytest.mark.asyncio
async def test_public_batch_with_batch_priority_is_still_one_provider_batch(ladder, monkeypatch):  # noqa: F811
    b = ladder
    stub, body = await batch_setup(b, monkeypatch, 'openai', count=2)
    for item in body.requests:
        item.priority = 'batch'
    queued = await b.tank.route_batch(body, caller=None)
    assert queued['status'] == 'queued' and len(queued['results']) == 2
    assert await _jobs(b, b.tenants[0]) == 0 and not b.sent


@pytest.mark.asyncio
async def test_seat_without_provider_batch_waits_then_runs_with_its_own_price(ladder, monkeypatch):  # noqa: F811
    from test_tank_priority_offpeak import prepare
    b = ladder
    await prepare(b, monkeypatch, window=False)
    job = await b.tank.route(request(b, b.tenants[0], text='Offline input', priority='batch', interactive=False), caller=None)
    assert job.status == 'queued' and job.priority == 'batch'
    await asyncio.gather(*list(b.tank._background))
    assert len(b.sent) == 1
    status = await queue.status(b.tank, job.id, b.tenants[0])
    assert status['status'] == 'completed' and status['priority'] == 'batch'
    async with b.pool.acquire() as conn:
        receipt = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2', job.id, b.tenants[0])
        assert receipt['priority'] == 'batch' and receipt['cost_status'] == 'set'
        assert float(receipt['cost_usd']) == pytest.approx(0.001)


@pytest.mark.asyncio
async def test_agent_key_polls_only_its_own_job(ladder, monkeypatch):  # noqa: F811
    from test_tank_priority_offpeak import prepare
    b = ladder
    await prepare(b, monkeypatch, window=True)  # stays queued: the window is shut
    monkeypatch.setenv('TANK_KEY_ZENAS', 'zenas-fixture-key')
    monkeypatch.setenv('TANK_KEY_RIG', 'rig-fixture-key')
    req = request(b, b.tenants[0], text='Offline input', priority='batch', interactive=False)
    sent = await b.client.post('/v1/route', json=req.model_dump(mode='json'), headers={'X-Tank-Key': 'zenas-fixture-key'})
    assert sent.status_code == 200 and sent.json()['status'] == 'queued' and sent.json()['priority'] == 'batch'
    job_id = sent.json()['id']
    await asyncio.gather(*list(b.tank._background))
    path, params = '/v1/route/jobs/' + job_id, {'tenant_id': str(b.tenants[0])}
    own = await b.client.get(path, params=params, headers={'X-Tank-Key': 'zenas-fixture-key'})
    assert own.status_code == 200 and own.json()['status'] == 'queued' and 'caller' not in own.json()
    assert (await b.client.get(path, params=params, headers={'X-Tank-Key': 'rig-fixture-key'})).status_code == 404
    assert (await b.client.get(path, params=params)).status_code == 200          # the Workspace key
    other = {'tenant_id': str(b.tenants[1])}
    assert (await b.client.get(path, params=other, headers={'X-Tank-Key': 'zenas-fixture-key'})).status_code == 404
    # Still nothing else under /v1/route/ for an agent key.
    assert (await b.client.get('/v1/route/jobs/' + job_id + '/x', params=params,
                               headers={'X-Tank-Key': 'zenas-fixture-key'})).status_code in {403, 404}


# ---------- chassis client: no database, no network ----------

def _client(handler):
    from chassis import tank as chassis_tank
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return chassis_tank, chassis_tank.TankClient('http://tank', 'fixture-key', 'zenas', http)


@pytest.mark.asyncio
async def test_client_default_body_is_unchanged():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={'content': 'now', 'ledger_id': str(uuid.uuid4())})

    _, client = _client(handler)
    assert (await client.route('t', 'zenas.scope', [{'role': 'user', 'content': 'q'}]))['content'] == 'now'
    assert set(bodies[0]) == {'tenant_id', 'agent', 'task_type', 'messages'}


@pytest.mark.asyncio
async def test_client_background_queues_then_waits_for_the_answer(monkeypatch):
    seen, polls = [], []
    job = str(uuid.uuid4())

    def handler(request):
        if request.method == 'POST':
            seen.append(json.loads(request.content))
            return httpx.Response(200, json={'id': job, 'ledger_id': job, 'status': 'queued', 'priority': 'batch'})
        polls.append(request)
        assert request.url.path == '/v1/route/jobs/' + job and request.url.params['tenant_id'] == 't'
        assert request.headers['X-Tank-Key'] == 'fixture-key'
        if len(polls) < 3:
            return httpx.Response(200, json={'id': job, 'status': 'batch'})
        return httpx.Response(200, json={'id': job, 'status': 'completed', 'result': {'content': 'later', 'model': 'm'}})

    chassis_tank, client = _client(handler)
    sleeps = []
    monkeypatch.setattr(chassis_tank.asyncio, 'sleep', AsyncMock(side_effect=lambda s: sleeps.append(s)))
    answer = await client.route('t', 'zenas.case_facts', [{'role': 'user', 'content': 'q'}], background=True)
    assert answer == {'content': 'later', 'model': 'm'}
    assert seen[0]['priority'] == 'batch' and seen[0]['interactive'] is False
    assert len(polls) == 3 and sleeps == [5.0, 7.5]


@pytest.mark.asyncio
async def test_client_background_on_an_old_tank_returns_the_direct_answer():
    def handler(request):
        return httpx.Response(200, json={'content': 'direct', 'ledger_id': str(uuid.uuid4())})

    _, client = _client(handler)
    assert (await client.route('t', 'x', [{'role': 'user', 'content': 'q'}], background=True))['content'] == 'direct'


@pytest.mark.asyncio
@pytest.mark.parametrize('final', [{'status': 'failed', 'error': 'batch_failed'}, {'status': 'uncertain'},
                                   {'status': 'completed', 'result': None}])
async def test_client_background_failures_raise(monkeypatch, final):
    job = str(uuid.uuid4())

    def handler(request):
        if request.method == 'POST':
            return httpx.Response(200, json={'id': job, 'status': 'queued'})
        return httpx.Response(200, json={'id': job, **final})

    chassis_tank, client = _client(handler)
    monkeypatch.setattr(chassis_tank.asyncio, 'sleep', AsyncMock())
    with pytest.raises(RuntimeError):
        await client.route('t', 'x', [{'role': 'user', 'content': 'q'}], background=True)


@pytest.mark.asyncio
async def test_client_background_stops_waiting_at_the_limit(monkeypatch):
    job = str(uuid.uuid4())

    def handler(request):
        if request.method == 'POST':
            return httpx.Response(200, json={'id': job, 'status': 'queued'})
        return httpx.Response(200, json={'id': job, 'status': 'queued'})

    chassis_tank, client = _client(handler)
    monkeypatch.setenv('TANK_BACKGROUND_WAIT_S', '20')
    clock = [0.0]

    async def sleep(seconds):
        clock[0] += seconds

    monkeypatch.setattr(chassis_tank.asyncio, 'sleep', sleep)
    monkeypatch.setattr(chassis_tank.time, 'monotonic', lambda: clock[0])
    with pytest.raises(RuntimeError, match='stopped waiting'):
        await client.route('t', 'x', [{'role': 'user', 'content': 'q'}], background=True)
    assert clock[0] <= 20


# ---------- Zenas nightly conversion: no database, no network ----------

@pytest.mark.asyncio
async def test_ask_all_keeps_order_and_limit():
    from agents.zenas.core import convert
    running, peak = [0], [0]

    class Model:
        parallel = 3

        async def complete(self, messages, *, task_type, provider):
            running[0] += 1
            peak[0] = max(peak[0], running[0])
            await asyncio.sleep(0)
            running[0] -= 1
            text = messages[0]['content']
            if text == 'boom':
                raise RuntimeError('model down')
            return {'content': text.upper(), 'finish_reason': 'stop'}

    answers = await convert._ask_all(Model(), ['a', 'boom', 'c', 'd', 'e'])
    assert [a['content'] if isinstance(a, dict) else 'ERR' for a in answers] == ['A', 'ERR', 'C', 'D', 'E']
    assert peak[0] == 3
    peak[0] = 0
    plain = Model()
    plain.parallel = None
    await convert._ask_all(plain, ['a', 'b', 'c'])
    assert peak[0] == 1


@pytest.mark.parametrize('raw,value', [('', 50), ('8', 8), ('0', 50), ('x', 50), ('-3', 50)])
def test_convert_parallel(monkeypatch, raw, value):
    from agents.zenas.core import convert
    monkeypatch.setenv('ZENAS_CONVERT_PARALLEL', raw)
    assert convert.convert_parallel() == value


@pytest.mark.asyncio
async def test_night_model_sends_case_facts_in_background_only(monkeypatch):
    from agents.zenas.core import convert
    import chassis.tank as chassis_tank
    calls = []

    class Fake:
        def __init__(self, *args):
            pass

        async def route(self, tenant, task_type, messages, *, background=False):
            calls.append((task_type, background))
            return {'content': 'ok'}

    monkeypatch.setattr(chassis_tank, 'TankClient', Fake)
    monkeypatch.setenv('TANK_KEY', 'fixture-key')
    monkeypatch.setenv('TANK_URL', 'http://tank')
    model, http = convert._night_model()
    try:
        assert model.parallel == 50
        await model.complete([{'role': 'user', 'content': 'q'}], task_type='zenas.case_facts', provider='luna')
        await model.complete([{'role': 'user', 'content': 'q'}], task_type='zenas.rule_card', provider='luna')
    finally:
        await http.aclose()
    assert calls == [('zenas.case_facts', True), ('zenas.rule_card', False)]
