"""Queue fairness and ambiguous/explicit retry boundaries on native Postgres."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_marketing import env as env  # noqa: PLC0414 -- pytest fixture re-export
from test_marketing import m1 as m1  # noqa: PLC0414 -- pytest fixture re-export
from test_marketing import post, scheduled
from test_second import TENANT
from trigger_google import GoogleFailure
from trigger_marketing_contract import Post
from trigger_publisher import Publisher, publish_due


@pytest.mark.asyncio
async def test_terminal_stores_do_not_fill_the_due_tenant_window(m1, monkeypatch):
    for _ in range(125):
        await m1.env.pool.execute("""INSERT INTO tank.trigger_posts
            (tenant_id,user_id,operation_id,channel,format,text,report,state,planned_at,retryable)
            VALUES($1,'placeholder-user',$2,'gbp','Google Business Profile post','placeholder terminal','{}','failed',now(),false)""", uuid4(), uuid4())
    ident = await post(m1)
    await scheduled(m1, ident)
    once = AsyncMock()
    monkeypatch.setattr(Publisher, 'once', once)
    await publish_due(SimpleNamespace(admin_pool=lambda: m1.env.pool, pool=lambda: m1.env.pool))
    once.assert_awaited_once_with(TENANT)


@pytest.mark.asyncio
async def test_known_failure_allows_explicit_retry_and_uncertain_state_can_be_cancelled(m1):
    ident = await post(m1)
    await scheduled(m1, ident)
    m1.google.request.side_effect = GoogleFailure(403, 'placeholder permission rejected')
    await Publisher(m1.store).once(TENANT)
    row = await m1.store.post(TENANT, ident)
    assert row['state'] == 'failed' and row['retry_at'] is None
    assert await Publisher(m1.store).once(TENANT) is None
    row = await m1.store.transition(TENANT, 'post.retry', Post(post_id=ident, expected_revision=1), uuid4())
    assert row['state'] == 'scheduled'
    claimed = await Publisher(m1.store).claim(TENANT)
    assert claimed
    await m1.env.pool.execute("UPDATE tank.trigger_posts SET lease_until=now()-interval '1 minute' WHERE tenant_id=$1 AND id=$2", TENANT, ident)
    assert await Publisher(m1.store).once(TENANT) is None
    cancelled = await m1.store.transition(TENANT, 'post.cancel', Post(post_id=ident, expected_revision=1), uuid4())
    assert cancelled['state'] == 'cancelled'


def test_unknown_iana_zone_has_normal_validation_refusal():
    from trigger_marketing_contract import Schedule
    with pytest.raises(ValueError):
        Schedule(post_id=uuid4(), planned_at='2026-11-04T12:00:00Z', time_zone='placeholder/unknown')
