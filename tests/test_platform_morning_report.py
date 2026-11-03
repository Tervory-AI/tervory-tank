"""Real SQL report claims; the SMTP boundary is stubbed, never contacted."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
import morning_report as report
from gold import PLATFORM_TENANT
from test_tank_tenant_boundaries import boundary  # noqa: F401


def test_pacific_schedule_and_dst():
    assert report.window(datetime(2026, 11, 3, 14, 59, tzinfo=timezone.utc)) is None
    for stamp, hours in [('2026-03-08T14:00:00+00:00', 23), ('2026-11-01T15:00:00+00:00', 25)]:
        start, end = report.window(datetime.fromisoformat(stamp))
        assert (end-start).total_seconds() == hours*3600


@pytest.mark.asyncio
@pytest.mark.parametrize('fails', [False, True])
async def test_durable_claim_and_report(boundary, monkeypatch, fails):  # noqa: F811
    b = boundary
    for name in ('TO', 'SMTP_HOST', 'SMTP_FROM'):
        monkeypatch.setenv('FOUNDER_REPORT_'+name, 'offline@example.test')
    monkeypatch.setattr(report, 'deploys', AsyncMock(return_value={'available': False, 'runs': []}))
    send = Mock(side_effect=TimeoutError() if fails else None)
    monkeypatch.setattr(report, 'send', send)
    clock = datetime(2026, 11, 3, 15, tzinfo=timezone.utc)
    await report.process(b.tank, clock)
    await report.process(b.tank, clock)
    assert send.call_count == 1
    body = send.call_args.args[0].get_content()
    assert 'graduation_candidates' in body and 'failed_jobs' in body and 'known_savings_usd' in body
    async with b.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM tank.morning_reports WHERE tenant_id=$1', PLATFORM_TENANT)
        assert row['status'] == ('uncertain' if fails else 'sent')
