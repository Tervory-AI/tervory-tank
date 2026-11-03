"""Actual Confirm retries reconcile uncertain sends before allowing another POST."""
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from test_marketing import LOCATION, card_for, post, scheduled
from test_marketing import env as env  # noqa: PLC0414 -- pytest fixture re-export
from test_marketing import m1 as m1  # noqa: PLC0414 -- pytest fixture re-export
from test_second import TENANT, confirm
from trigger_google import GoogleFailure
from trigger_publisher import Publisher


async def uncertain(m1):
    ident = await post(m1)
    await scheduled(m1, ident)
    m1.google.request.side_effect = GoogleFailure(503, uncertain=True)
    await Publisher(m1.store).once(TENANT)
    row = await m1.store.post(TENANT, ident)
    assert row['delivery'] == 'uncertain'
    return ident, row


@pytest.mark.asyncio
@pytest.mark.parametrize('found', [True, False])
async def test_confirmed_uncertain_retry_lists_all_pages_and_never_reposts_a_match(m1, found):
    ident, row = await uncertain(m1)
    existing = {'name': LOCATION+'/localPosts/placeholder-found', 'searchUrl': 'https://google.com/placeholder-found',
                'summary': row['text'], 'createTime': (row['claimed_at']+timedelta(seconds=1)).isoformat()}
    old = {**existing, 'createTime': (row['claimed_at']-timedelta(seconds=1)).isoformat()}
    calls = []
    async def request(tenant, method, url, **kwargs):
        assert tenant == TENANT and url.endswith(LOCATION+'/localPosts')
        calls.append(method)
        if method == 'GET':
            assert kwargs['conn'] is not None
            if not kwargs['params'].get('pageToken'):
                return {'localPosts': [old, {**existing, 'summary': 'placeholder other text'}], 'nextPageToken': 'placeholder-next'}
            return {'localPosts': [existing] if found else []}
        return existing
    m1.google.request.side_effect = request
    _, card = await card_for(m1.env, 'trigger.post.retry', {'post_id': str(ident)}, user='founder')
    result = await confirm(m1.env, card, user='founder')
    assert result['status'] == 'confirmed', result
    if found:
        assert result['result']['state'] == 'published'
        assert result['result']['platform_id'] == existing['name']
        assert result['result']['platform_url'] == existing['searchUrl']
    else:
        assert result['result']['state'] == 'scheduled'
    await asyncio.gather(Publisher(m1.store).once(TENANT), Publisher(m1.store).once(TENANT))
    await Publisher(m1.store).once(TENANT)
    assert calls == (['GET', 'GET'] if found else ['GET', 'GET', 'POST'])
    assert (await m1.store.post(TENANT, ident))['state'] == 'published'


@pytest.mark.asyncio
async def test_uncertain_cancel_is_confirmed_without_another_google_call(m1):
    ident, _ = await uncertain(m1)
    m1.google.request.reset_mock()
    _, card = await card_for(m1.env, 'trigger.post.cancel', {'post_id': str(ident)}, user='founder')
    result = await confirm(m1.env, card, user='founder')
    assert result['status'] == 'confirmed' and result['result']['state'] == 'cancelled'
    assert await Publisher(m1.store).once(TENANT) is None
    m1.google.request.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['outage', 'unreadable', 'changed_binding'])
async def test_incomplete_reconciliation_never_authorizes_another_post(m1, failure):
    ident, row = await uncertain(m1)
    if failure == 'outage':
        m1.google.pages = AsyncMock(side_effect=GoogleFailure(503))
    elif failure == 'unreadable':
        m1.google.pages = AsyncMock(return_value=[{'summary': row['text'], 'name': LOCATION+'/localPosts/placeholder', 'createTime': 'placeholder invalid'}])
    else:
        await m1.env.pool.execute("UPDATE tank.trigger_gbp_connections SET location='accounts/123/locations/789' WHERE tenant_id=$1", TENANT)
    _, card = await card_for(m1.env, 'trigger.post.retry', {'post_id': str(ident)}, user='founder')
    await confirm(m1.env, card, user='founder')
    assert (await m1.store.post(TENANT, ident))['delivery'] == 'uncertain'
    assert await Publisher(m1.store).once(TENANT) is None
    assert m1.google.request.await_count == 1  # Only the original uncertain POST.
