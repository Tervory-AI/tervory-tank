"""Offline priority routing: real Tank/SQL, frozen clock, stubbed LiteLLM only."""
import asyncio
import json
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
    assert job.status == 'completed' and len(b.sent) == 1
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
