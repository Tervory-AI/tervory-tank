"""Both repeated Los Angeles wall times stay on the same local calendar date."""
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from test_marketing import approved
from test_marketing import env as env  # noqa: PLC0414 -- pytest fixture re-export
from test_marketing import m1 as m1  # noqa: PLC0414 -- pytest fixture re-export
from test_marketing import post
from test_second import TENANT
from trigger_marketing_contract import Calendar, Posts, Schedule


@pytest.mark.asyncio
@pytest.mark.parametrize('offset,utc_hour', [('-07:00', 8), ('-08:00', 9)])
async def test_both_dst_folds_land_on_november_first_in_calendar_and_date_filter(m1, monkeypatch, offset, utc_hour):
    monkeypatch.setattr('trigger_marketing.utc_now', lambda: datetime(2026, 10, 31, tzinfo=UTC))
    ident = await post(m1)
    await approved(m1, ident)
    result = await m1.store.transition(TENANT, 'post.schedule', Schedule(post_id=ident, expected_revision=1,
        planned_at='2026-11-01T01:30:00'+offset, time_zone='America/Los_Angeles'), uuid4())
    assert result['planned_at'].astimezone(UTC).hour == utc_hour
    calendar = await m1.store.calendar(TENANT, Calendar(start=date(2026, 11, 1), period='week'))
    assert set(calendar['days']) == {'2026-11-01'}
    assert calendar['days']['2026-11-01'][0]['id'] == ident
    assert calendar['days']['2026-11-01'][0]['time'] == '01:30:00'
    filtered = await m1.store.posts(TENANT, Posts(start=date(2026, 11, 1), end=date(2026, 11, 2)))
    assert [row['id'] for row in filtered['posts']] == [ident]
    assert not (await m1.store.posts(TENANT, Posts(start=date(2026, 10, 31), end=date(2026, 11, 1))))['posts']
    assert not (await m1.store.posts(TENANT, Posts(start=date(2026, 11, 2), end=date(2026, 11, 3))))['posts']
