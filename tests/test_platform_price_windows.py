from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import price_windows
import priority_queue
import pytest
from fastapi import HTTPException
from test_tank_tenant_boundaries import boundary  # noqa: F401

SETTINGS = {'timezone': 'UTC', 'charge_multiplier': .5, 'windows': [
    {'days': list(range(7)), 'start': '04:00', 'end': '05:00'},
    {'days': list(range(7)), 'start': '06:00', 'end': '07:00', 'charge_multiplier': .2}]}
AT = datetime(2026, 11, 3, 2, tzinfo=UTC)


def test_cheapest_within_deadline_and_provider_completion_budget():
    info = {'offpeak': SETTINGS}
    choose = lambda hours, batch=None: price_windows.choose(info, at=AT, deadline=AT+timedelta(hours=hours), batch_discount=batch)
    assert choose(8)['not_before'].hour == 6
    assert choose(3)['not_before'].hour == 4
    assert choose(1)['not_before'] == AT  # No cheaper window fits; do not wait past the deadline.
    assert choose(48, .1)['dispatch_mode'] == 'batch'
    assert choose(8, .1)['dispatch_mode'] == 'direct'  # A 24h provider batch cannot fit.
    for deadline in (AT, AT-timedelta(seconds=1), AT+timedelta(days=8)):
        with pytest.raises(HTTPException):
            price_windows.choose(info, at=AT, deadline=deadline, batch_discount=None)


def test_dst_spring_gap_and_repeated_hour():
    settings = {'timezone': 'America/Los_Angeles', 'charge_multiplier': .5,
                'windows': [{'days': [6], 'start': '02:00', 'end': '04:00'}]}
    at = datetime(2026, 3, 8, 9, tzinfo=UTC)
    plan = price_windows.choose({'offpeak': settings}, at=at, deadline=at+timedelta(hours=4), batch_discount=None)
    assert plan['not_before'] == datetime(2026, 3, 8, 10, tzinfo=UTC)
    assert price_windows.multiplier(settings, plan['not_before']) == .5
    settings['windows'][0].update(start='01:00', end='02:00')
    at = datetime(2026, 11, 1, 7, tzinfo=UTC)
    assert price_windows.choose({'offpeak': settings}, at=at, deadline=at+timedelta(hours=4), batch_discount=None)['not_before'].hour == 8


@pytest.mark.asyncio
@pytest.mark.parametrize('expired', [False, True])
async def test_persisted_schedule_waits_then_dispatches_once(boundary, monkeypatch, expired):  # noqa: F811
    b = boundary
    clock = [AT]
    monkeypatch.setattr(priority_queue, 'now', lambda: clock[0])
    monkeypatch.setattr(b.tank, '_roster_models', AsyncMock(return_value=[{'model_name': 'luna', 'model_info': {'offpeak': SETTINGS}}]))
    monkeypatch.setattr(b.tank, '_batch_price', AsyncMock(return_value={'discount': 1, 'provider': 'unsupported', 'native': 'offline'}))
    monkeypatch.setattr(b.tank, '_call_upper', lambda *args: .01)
    policy = await b.tank.load_policy('base.normalize', b.tenants[0])
    req = b.tank.RouteRequest(tenant_id=b.tenants[0], task_type='base.normalize', priority='offpeak',
        deadline_at=AT+timedelta(hours=8), messages=[b.tank.Message(role='user', content='Offline input')])
    item = b.tank._DeferredRoute(req, policy, [{'role':'user','content':'Offline input'}], 100, {}, [], None)
    queued = await priority_queue.enqueue(b.tank, item)
    assert queued.not_before.hour == 6
    execute = AsyncMock(return_value=SimpleNamespace(model_dump=lambda **kw: {'content': 'done', 'ledger_id': str(queued.id)}))
    monkeypatch.setattr(b.tank, 'run_route', execute)
    await priority_queue.process_once(b.tank, job_id=queued.id, tenant_id=req.tenant_id)
    execute.assert_not_awaited()
    clock[0] = AT+timedelta(hours=9 if expired else 4)
    await priority_queue.process_once(b.tank, job_id=queued.id, tenant_id=req.tenant_id)
    await priority_queue.process_once(b.tank, job_id=queued.id, tenant_id=req.tenant_id)
    assert execute.await_count == (0 if expired else 1)
    result = await priority_queue.status(b.tank, queued.id, req.tenant_id)
    assert result['status'] == ('failed' if expired else 'completed')
    assert result['error'] == ('deadline_exceeded' if expired else None)
