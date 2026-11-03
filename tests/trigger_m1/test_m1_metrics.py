"""Publication evidence stays within existing report figures and tenant bounds."""
from datetime import timedelta

import pytest
from case_study_sources import trigger
from case_study_templates import empty_figures
from test_marketing import env as env  # noqa: PLC0414 -- pytest fixture re-export
from test_marketing import m1 as m1  # noqa: PLC0414 -- pytest fixture re-export
from test_marketing import post, scheduled
from test_second import OTHER, TENANT
from trigger_marketing_contract import utc_now
from trigger_publisher import Publisher


@pytest.mark.asyncio
async def test_published_count_uses_existing_figure_and_receipt_bounds(m1):
    ident = await post(m1)
    await scheduled(m1, ident)
    await Publisher(m1.store).once(TENANT)
    start, end = utc_now() - timedelta(days=1), utc_now() + timedelta(days=1)
    region = await m1.env.pool.fetchval('SELECT region FROM tank.ledger WHERE tenant_id=$1 LIMIT 1', TENANT)
    for tenant, selected_region, expected in ((TENANT, region, 1), (OTHER, region, 0), (TENANT, 'placeholder-other', 0)):
        figures = empty_figures('trigger', start.date(), end.date())
        original_keys = set(figures)
        await trigger(m1.env.pool, tenant, selected_region, start, end, figures)
        assert set(figures) == original_keys
        assert figures['trigger.drafts']['published_posts'] == expected
        assert figures['trigger.drafts']['published_posts_source'] == 'tank.trigger_posts.published_at'
        assert figures['trigger.drafts']['review_replies'] == 0
    figures = empty_figures('trigger', start.date(), end.date())
    await trigger(m1.env.pool, TENANT, region, end, end + timedelta(days=1), figures)
    assert figures['trigger.drafts']['published_posts'] == 0
