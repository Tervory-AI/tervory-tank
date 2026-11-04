"""The scheduled worker must not cancel a bounded weekly infrastructure scan early."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from chassis import worker

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_weekly_infra_reaches_its_scan_budget_through_the_real_worker(monkeypatch):
    path = ROOT / 'agents/radix/app.py'
    spec = importlib.util.spec_from_file_location('placeholder_radix_scheduler', path)
    room = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(room)
    from active_policy import LEASE_SECONDS, SCAN_SECONDS
    import passive_watch

    pool = object()
    room.app.state.pool = pool
    async def tick(actual):
        assert actual is pool
        return {'count': 1, 'kind': 'infra', 'scan_id': 'placeholder-scan'}
    monkeypatch.setattr(passive_watch, 'tick', tick)
    async def measured_wait(awaitable, *, timeout):
        # Advance a fixture's logical clock to the scan deadline, with no sleep.
        if timeout < SCAN_SECONDS + 30:
            awaitable.close()
            pytest.fail('scheduled worker cancels infrastructure before its scan/control budget')
        assert timeout < LEASE_SECONDS
        return await awaitable
    monkeypatch.setattr(worker.asyncio, 'wait_for', measured_wait)
    result = await worker.run_with_timeout(room.app.state.handlers['watch_tick'],
        SimpleNamespace(), room.app.state.job_timeouts['watch_tick'])
    assert result['count'] == 1 and result['kind'] == 'infra'
