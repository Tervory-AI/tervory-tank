"""UTC boundaries, durable deduplication, retries and lifespan cancellation."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import gold
import training

from test_train1 import database as _database

database = _database


def utc(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


@pytest.mark.parametrize('operation,now,expected', [
    ('export', '2026-10-18T01:59:59', '2026-10-17T02:00:00'),
    ('export', '2026-10-18T02:00:00', '2026-10-18T02:00:00'),
    ('retest', '2026-10-18T05:59:59', '2026-10-11T06:00:00'),
    ('retest', '2026-10-18T06:00:00', '2026-10-18T06:00:00'),
    ('retest', '2026-10-24T23:59:59', '2026-10-18T06:00:00'),
])
def test_utc_schedule_boundaries(operation, now, expected):
    assert training.scheduled_slot(operation, utc(now)) == utc(expected)
    assert training.scheduled_slot(operation, utc(now).astimezone(timezone(timedelta(hours=2)))) == utc(expected)


@pytest.mark.parametrize('region,holdout,active,expected', [
    ('za', False, True, True), ('us-east', False, True, True),
    ('unknown', False, True, False), ('za', True, True, False),
    ('us-east', False, False, False),
])
def test_export_eligibility_only_checks_region_holdout_active(region, holdout, active, expected):
    # No content/detector needed: reviewed names and email addresses are retained.
    assert training.exportable(dict(region=region, holdout=holdout, active=active)) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['export', 'retest'])
async def test_timer_durable_completion_concurrency_retry_and_region(database, monkeypatch, operation):
    pool, rt = database
    calls = []
    entered, release = asyncio.Event(), asyncio.Event()
    now = utc('2026-10-18T06:00:00')
    fail = True

    async def collect():
        pass

    async def work(**kwargs):
        calls.append(kwargs)
        entered.set()
        await release.wait()
        if fail:
            raise RuntimeError('fixture failure')
        return {'status': 'complete', 'results': []}

    monkeypatch.setattr(training, 'collect_once', collect)
    monkeypatch.setattr(training, 'export_once', work)
    monkeypatch.setattr(gold, 'retest', work)
    monkeypatch.setenv('TRAINING_JOB_KEY', '')  # Local timer does not need an HTTP key.
    task = asyncio.create_task(training.scheduled_once(operation, now))
    await asyncio.wait_for(entered.wait(), 3)
    await training.scheduled_once(operation, now)  # Another worker cannot overlap.
    assert len(calls) == 1
    release.set()
    with pytest.raises(RuntimeError):
        await task
    fail = False
    await training.scheduled_once(operation, now)  # Failed operation retries.
    assert len(calls) == 2
    if operation == 'retest':
        assert calls[-1]['since'] == now
    else:
        assert calls[-1]['day'] == now.date()
    await training.scheduled_once(operation, now + timedelta(minutes=1))
    assert len(calls) == 2  # Completion survives a new invocation / worker.
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.policy_log WHERE task_type='training.schedule'") == 1
    rt.box_region = lambda: 'za'
    await training.scheduled_once(operation, now)
    assert len(calls) == 3
    rt.box_region = lambda: 'unknown'
    await training.scheduled_once(operation, now)
    assert len(calls) == 3
    rt.box_region = lambda: 'us-east'
    await training.scheduled_once(operation, now + timedelta(days=7 if operation == 'retest' else 1))
    assert len(calls) == 4


@pytest.mark.asyncio
async def test_unconfigured_export_can_retry_when_configured(database, monkeypatch):
    for name in ('HF_TOKEN', 'HF_ORG', 'TRAINING_JOB_KEY'):
        monkeypatch.setenv(name, '')
    await training.scheduled_once('export', utc('2026-10-18T02:00:00'))
    pool, _ = database
    async with pool.acquire() as conn:
        assert not await conn.fetchval("SELECT 1 FROM tank.policy_log WHERE task_type='training.schedule'")


@pytest.mark.asyncio
async def test_lifespan_starts_and_cancels_all_three_background_loops(monkeypatch):
    started, stopped = set(), set()

    async def loop(operation='collect'):
        started.add(operation)
        try:
            await asyncio.Event().wait()
        finally:
            stopped.add(operation)

    monkeypatch.setattr(training, 'collector_loop', loop)
    monkeypatch.setattr(training, 'schedule_loop', loop)
    async with training.lifespan(None):
        await asyncio.sleep(0)
        assert started == {'collect', 'export', 'retest', 'gold'}
    assert stopped == started
