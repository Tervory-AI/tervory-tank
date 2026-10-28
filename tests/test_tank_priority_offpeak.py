"""Offline priority routing: real Tank/SQL, frozen clock, stubbed LiteLLM only."""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import yaml

import priority_queue as queue
from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_tank_ladder import ladder, policy, request  # noqa: F401
from test_tank_batch_providers import setup as batch_setup

UTC = timezone.utc
SETTINGS = {'timezone': 'UTC', 'charge_multiplier': 0.5, 'cache_read_input_cost_per_token': 0.000000006,
            'windows': [{'days': [0, 1, 2, 3, 4], 'start': '00:00', 'end': '01:00'},
                        {'days': [0, 1, 2, 3, 4], 'start': '04:00', 'end': '06:00'},
                        {'days': [0, 1, 2, 3, 4], 'start': '10:00', 'end': '24:00'},
                        {'days': [5, 6], 'start': '00:00', 'end': '24:00'}]}


@pytest.mark.parametrize('stamp,opened', [
    ('2026-10-28T00:59:59', True), ('2026-10-28T01:00:00', False),
    ('2026-10-28T03:59:59', False), ('2026-10-28T04:00:00', True),
    ('2026-10-28T05:59:59', True), ('2026-10-28T06:00:00', False),
    ('2026-10-28T09:59:59', False), ('2026-10-28T10:00:00', True),
    ('2026-10-31T02:00:00', True), ('2026-11-01T07:00:00', True),
])
def test_window_boundaries(stamp, opened):
    assert queue.window_open(SETTINGS, datetime.fromisoformat(stamp).replace(tzinfo=UTC)) is opened


def test_config_roster_and_invalid_windows():
    data = yaml.safe_load((Path(__file__).parents[1] / 'litellm/config.yaml').read_text())
    models = {r['model_name']: r for r in data['model_list']}
    assert models['deepseek-flash']['model_info']['offpeak'] == SETTINGS
    assert models['deepseek-pro']['model_info']['offpeak']['charge_multiplier'] == 0.5
    assert queue.window_open(None, datetime(2026, 10, 28, 2, tzinfo=UTC))
    with pytest.raises(ValueError):
        queue.window_open({**SETTINGS, 'windows': [{'days': [2], 'start': '23:00', 'end': '01:00'}]},
                          datetime(2026, 10, 28, 2, tzinfo=UTC))


async def prepare(b, monkeypatch, *, window=True, cap=1):
    info = {'input_cost_per_token': 0.0000003, 'output_cost_per_token': 0.0000012}
    if window:
        info['offpeak'] = SETTINGS
    roster = [{'model_name': 'deepseek-flash', 'litellm_params': {'model': 'deepseek/deepseek-flash'}, 'model_info': info}]
    monkeypatch.setattr(b.tank, '_roster_models', AsyncMock(return_value=roster))
    monkeypatch.setattr(b.tank.semantic_cache, 'lookup', AsyncMock(return_value=None))
    monkeypatch.setattr(b.tank.semantic_cache, 'schedule', Mock())
    await policy(b, b.tenants[0], model='deepseek-flash', rung=1, max_cost_usd=cap)
    clock = [datetime(2026, 10, 28, 2, tzinfo=UTC)]
    monkeypatch.setattr(queue, 'now', lambda: clock[0])

    class Gateway:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            b.sent.append(kwargs['json'])
            return httpx.Response(200, headers={'content-type': 'application/json', 'x-litellm-response-cost': '0.001'},
                json={'choices': [{'message': {'content': json.dumps({'text': 'Offline answer', 'actions': []})}}],
                      'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'prompt_cache_hit_tokens': 20}},
                request=httpx.Request('POST', url))

    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', Gateway)
    return clock, info


@pytest.mark.asyncio
async def test_urgent_skips_all_shadows_and_cache(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    await prepare(b, monkeypatch)
    for name in ('_cache_read', '_shadow'):
        monkeypatch.setattr(b.tank, name, AsyncMock(side_effect=AssertionError('urgent shadow/cache')))
    monkeypatch.setattr(b.tank.semantic_cache, 'lookup', AsyncMock(side_effect=AssertionError('urgent encoder')))
    monkeypatch.setattr(b.tank.semantic_cache, 'schedule', Mock(side_effect=AssertionError('urgent shadow')))
    monkeypatch.setattr(b.tank.routellm_shadow, 'configuration', Mock(side_effect=AssertionError('urgent router')))
    result = await b.tank.run_route(request(b, b.tenants[0], text='Offline input', priority='urgent'))
    assert result.content and len(b.sent) == 1
    async with b.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2', result.ledger_id, b.tenants[0])
        assert row['priority'] == 'urgent' and row['sent_at'] is not None
        assert await conn.fetchval('SELECT count(*) FROM tank.offpeak_jobs WHERE tenant_id=$1', b.tenants[0]) == 0


@pytest.mark.asyncio
async def test_standard_keeps_today_path(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    await prepare(b, monkeypatch)
    result = await b.tank.run_route(request(b, b.tenants[0], text='Offline input', priority='standard'))
    assert result.cost_usd == 0.001 and len(b.sent) == 1
    b.tank.semantic_cache.lookup.assert_awaited_once()
    b.tank.semantic_cache.schedule.assert_called_once()


@pytest.mark.asyncio
async def test_hold_then_send_same_receipt_and_actual_discount(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    clock, info = await prepare(b, monkeypatch)
    job = await b.tank.run_route(request(b, b.tenants[0], text='Offline input', priority='offpeak'))
    await queue.process_once(b.tank)
    assert not b.sent and (await queue.status(b.tank, job.id, b.tenants[0]))['status'] == 'queued'
    async with b.pool.acquire() as conn:
        receipt = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2', job.id, b.tenants[0])
        assert receipt['outcome'] == 'queued' and receipt['sent_at'] is None and receipt['cost_status'] == 'not_set'
    clock[0] = datetime(2026, 10, 28, 4, tzinfo=UTC)
    await asyncio.gather(queue.process_once(b.tank), queue.process_once(b.tank))
    await queue.process_once(b.tank)
    result = await queue.status(b.tank, job.id, b.tenants[0])
    assert result['status'] == 'completed' and len(b.sent) == 1
    async with b.pool.acquire() as conn:
        receipt = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2', job.id, b.tenants[0])
        assert receipt['outcome'] == 'delivered' and receipt['priority'] == 'offpeak'
        assert receipt['sent_at'] == clock[0] and receipt['cost_status'] == 'set'
        assert float(receipt['cost_usd']) == pytest.approx((80 * info['input_cost_per_token'] + 20 * SETTINGS['cache_read_input_cost_per_token'] + 50 * info['output_cost_per_token']) * 0.5, abs=1e-8)
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1', b.tenants[0]) == 1
    with pytest.raises(b.tank.HTTPException) as error:
        await queue.status(b.tank, job.id, b.tenants[1])
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_no_window_runs_at_once_via_route(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    await prepare(b, monkeypatch, window=False)
    job = await b.tank.route(request(b, b.tenants[0], text='Offline input', priority='offpeak'), caller=None)
    assert job.status == 'queued'
    await asyncio.gather(*list(b.tank._background))
    assert len(b.sent) == 1
    result = await queue.status(b.tank, job.id, b.tenants[0])
    assert result['result']['cost_usd'] == 0.001


@pytest.mark.asyncio
async def test_cap_refuses_before_queue(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    await prepare(b, monkeypatch, cap=0.00000001)
    with pytest.raises(b.tank.HTTPException) as error:
        await b.tank.run_route(request(b, b.tenants[0], text='Offline input', priority='offpeak'))
    assert error.value.status_code == 409 and not b.sent
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.offpeak_jobs WHERE tenant_id=$1', b.tenants[0]) == 0


@pytest.mark.asyncio
async def test_interrupted_dispatch_never_repeated(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    await prepare(b, monkeypatch)
    job = await b.tank.run_route(request(b, b.tenants[0], text='Offline input', priority='offpeak'))
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.offpeak_jobs SET status='dispatching' WHERE id=$1 AND tenant_id=$2", job.id, b.tenants[0])
    await queue.process_once(b.tank)
    assert (await queue.status(b.tank, job.id, b.tenants[0]))['status'] == 'uncertain' and not b.sent


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', ['openai', 'vertex_ai', 'anthropic'])
@pytest.mark.parametrize('failed', [False, True])
async def test_offpeak_uses_existing_batch_and_fallback(ladder, monkeypatch, provider, failed):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    stub, body = await batch_setup(b, monkeypatch, provider, count=1)
    monkeypatch.setenv('TANK_BATCH_MIN', '50')
    req = body.requests[0].model_copy(update={'priority': 'offpeak', 'interactive': True})
    job = await b.tank.run_route(req)
    await queue.process_once(b.tank)
    await b.tank.process_batches_once()
    assert len(stub.submissions()) == 1 and not b.sent
    if failed:
        stub.failures[0] = 'missing'
    stub.finished = True
    await b.tank.process_batches_once()
    await queue.process_once(b.tank)
    result = await queue.status(b.tank, job.id, req.tenant_id)
    assert result['status'] == 'completed'
    assert len(b.sent) == int(failed)
    async with b.pool.acquire() as conn:
        receipt = await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2', job.id, req.tenant_id)
        assert receipt['batch'] and receipt['priority'] == 'offpeak'
        assert receipt['outcome'] == 'delivered' and receipt['sent_at'] is not None
        assert float(receipt['cost_usd']) == pytest.approx(0.001 if failed else 0.00035)
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1', req.tenant_id) == 1


def test_missing_usage_does_not_invent_price():
    info = {'offpeak': SETTINGS, 'input_cost_per_token': 0.0000003, 'output_cost_per_token': 0.0000012}
    assert queue.usage_cost(info, {}, datetime(2026, 10, 28, 4, tzinfo=UTC)) is None
    assert queue.usage_cost(info, {'prompt_tokens': 10, 'completion_tokens': 10}, datetime(2026, 10, 28, 4, tzinfo=UTC)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('early_close', [False, True])
async def test_command_deferral_survives_browser_close_and_replays_once(ladder, monkeypatch, early_close):  # noqa: F811 (pytest fixture parameter)
    import command
    import trigger_routes
    b = ladder
    clock, _ = await prepare(b, monkeypatch)
    monkeypatch.setattr(trigger_routes, 'code_plan', AsyncMock(return_value=None))
    actor = command.Actor(b.tenants[0], 'founder-fixture', True)
    async with b.pool.acquire() as conn:
        await conn.execute("""UPDATE tank.policy SET model='deepseek-flash',rung=1,max_cost_usd=1,
            system_prompt=NULL,cache_scope='none' WHERE task_type='command.turn' AND tenant_id IS NULL""")
    thread = await command.create_thread(command.NewThread(title='Offline priority proof'), actor)
    thread_id = uuid.UUID(thread['thread_id'])
    gate = asyncio.Event()
    route_turn = command.route_turn

    async def gated(*args, **kwargs):
        if early_close:
            await gate.wait()
        return await route_turn(*args, **kwargs)

    monkeypatch.setattr(command, 'route_turn', gated)
    stream = await command.turn(thread_id, command.Turn(text='Offline input', priority='offpeak'), actor)
    if early_close:
        await anext(stream.body_iterator)
        await stream.body_iterator.aclose()
        gate.set()
        await asyncio.gather(*list(command._background))
    else:
        events = [part async for part in stream.body_iterator]
        assert any('job_id' in part for part in events)
    await asyncio.gather(*list(b.tank._background))
    assert not b.sent
    async with b.pool.acquire() as conn:
        job = await conn.fetchrow('SELECT * FROM tank.offpeak_jobs WHERE tenant_id=$1', actor.tenant_id)
        state = json.loads(await conn.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1 AND tenant_id=$2', thread_id, actor.tenant_id))
        assert state['active_turn'] is None and state['steps'][str(job['task_id'])]['status'] == 'planned'
    # Browser/SSE is gone. The durable worker uses the saved thread and task.
    clock[0] = datetime(2026, 10, 28, 4, tzinfo=UTC)
    await queue.process_once(b.tank)
    await queue.notify_commands(b.tank)
    await queue.notify_commands(b.tank)
    async with b.pool.acquire() as conn:
        state = json.loads(await conn.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1 AND tenant_id=$2', thread_id, actor.tenant_id))
        assert [m['content'] for m in state['messages'] if m['role'] == 'assistant'] == ['Offline answer']
        assert state['steps'][str(job['task_id'])]['status'] == 'done'
        assert len(state['receipts']) == 1 and state['receipts'][0]['ledger_id'] == str(job['id'])
        assert await conn.fetchval('SELECT status FROM tank.tasks WHERE id=$1 AND tenant_id=$2', job['task_id'], actor.tenant_id) == 'done'
    assert len(b.sent) == 1


@pytest.mark.asyncio
async def test_changed_policy_cancels_queued_work(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    clock, _ = await prepare(b, monkeypatch)
    job = await b.tank.run_route(request(b, b.tenants[0], text='Offline input', priority='offpeak'))
    async with b.pool.acquire() as conn:
        await conn.execute('UPDATE tank.policy SET updated_at=now() WHERE tenant_id=$1', b.tenants[0])
    clock[0] = datetime(2026, 10, 28, 4, tzinfo=UTC)
    await queue.process_once(b.tank)
    assert (await queue.status(b.tank, job.id, b.tenants[0]))['error'] == 'policy_changed' and not b.sent


@pytest.mark.asyncio
async def test_transport_failure_keeps_one_unknown_receipt(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    clock, _ = await prepare(b, monkeypatch)
    job = await b.tank.run_route(request(b, b.tenants[0], text='Offline input', priority='offpeak'))
    monkeypatch.setattr(b.tank.httpx.AsyncClient, 'post', AsyncMock(side_effect=httpx.ReadTimeout('offline failure')))
    clock[0] = datetime(2026, 10, 28, 4, tzinfo=UTC)
    await queue.process_once(b.tank)
    await queue.process_once(b.tank)
    b.tank.httpx.AsyncClient.post.assert_awaited_once()
    async with b.pool.acquire() as conn:
        rows = await conn.fetch('SELECT * FROM tank.ledger WHERE tenant_id=$1', b.tenants[0])
        assert len(rows) == 1 and rows[0]['id'] == job.id
        assert rows[0]['cost_status'] == 'not_set' and rows[0]['sent_at'] == clock[0]


@pytest.mark.asyncio
async def test_roster_preserves_window_metadata_without_credentials(ladder):  # noqa: F811 (pytest fixture parameter)
    row = ladder.tank._roster_row({'model_name': 'deepseek-flash', 'litellm_params': {'model': 'deepseek/deepseek-flash'},
                                  'model_info': {'offpeak': SETTINGS}})
    assert row['model_info']['offpeak'] == SETTINGS


@pytest.mark.asyncio
async def test_window_closing_during_preflight_requeues_without_sending(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    clock, _ = await prepare(b, monkeypatch)
    job = await b.tank.run_route(request(b, b.tenants[0], text='Offline input', priority='offpeak'))
    clock[0] = datetime(2026, 10, 28, 4, tzinfo=UTC)
    price, count = b.tank._batch_price, 0

    async def crossing(model):
        nonlocal count
        count += 1
        if count == 2:
            clock[0] = datetime(2026, 10, 28, 6, tzinfo=UTC)
        return await price(model)

    monkeypatch.setattr(b.tank, '_batch_price', crossing)
    await queue.process_once(b.tank)
    result = await queue.status(b.tank, job.id, b.tenants[0])
    assert result['status'] == 'queued' and result['sent_at'] is None and not b.sent
    clock[0] = datetime(2026, 10, 28, 10, tzinfo=UTC)
    await queue.process_once(b.tank)
    assert len(b.sent) == 1


@pytest.mark.asyncio
async def test_http_job_contract_and_existing_savings_columns(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    import proof
    b = ladder
    clock, _ = await prepare(b, monkeypatch)
    tenant = b.tenants[0]
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.proof_prices(model,family,input_usd,output_usd)
            VALUES('deepseek-flash','deepseek',0.0000003,0.0000012)
            ON CONFLICT(model) DO UPDATE SET input_usd=EXCLUDED.input_usd,output_usd=EXCLUDED.output_usd""")
        await conn.execute("""INSERT INTO tank.provider_standards(provider,model) VALUES('deepseek','deepseek-flash')
            ON CONFLICT(provider) DO UPDATE SET model=EXCLUDED.model""")
    req = request(b, tenant, text='Offline input', priority='offpeak')
    response = await b.client.post('/v1/route', json=req.model_dump(mode='json'))
    assert response.status_code == 200 and response.json()['status'] == 'queued'
    job_id = response.json()['id']
    await asyncio.gather(*list(b.tank._background))
    queued = await proof.snapshot(tenant)
    assert queued['ledger'][0]['outcome'] == 'queued' and queued['ledger'][0]['cost_usd'] is None
    assert (await b.client.get('/v1/route/jobs/' + job_id, params={'tenant_id': str(b.tenants[1])})).status_code == 404
    clock[0] = datetime(2026, 10, 28, 4, tzinfo=UTC)
    await queue.process_once(b.tank)
    receipt = (await proof.snapshot(tenant))['ledger'][0]
    assert receipt['outcome'] == 'delivered' and float(receipt['cost_usd']) == pytest.approx(0.00004206)
    assert float(receipt['saved_usd']) == pytest.approx(float(receipt['standard_cost_usd']) - 0.00004206)
    polled = await b.client.get('/v1/route/jobs/' + job_id, params={'tenant_id': str(tenant)})
    assert polled.status_code == 200 and polled.json()['status'] == 'completed'


@pytest.mark.asyncio
async def test_distinct_concurrent_jobs_do_not_exhaust_pool(ladder, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = ladder
    await prepare(b, monkeypatch, window=False)
    jobs = [await b.tank.run_route(request(b, b.tenants[0], text=f'Offline input {i}', priority='offpeak')) for i in range(4)]
    # The real test pool has only two connections. Each router call needs one
    # while the queue retains its advisory-lock connection.
    await asyncio.wait_for(asyncio.gather(*[
        queue.process_once(b.tank, job_id=job.id, tenant_id=b.tenants[0]) for job in jobs
    ]), timeout=10)
    assert len(b.sent) == 4
    assert all([(await queue.status(b.tank, job.id, b.tenants[0]))['status'] == 'completed' for job in jobs])
