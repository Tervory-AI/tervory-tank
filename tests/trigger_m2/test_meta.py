"""Offline M2: real SQL/vault/cards, only httpx.MockTransport for Meta."""
import asyncio
import base64
import json
import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/trigger_m1'))
from test_marketing import card_for, post
from test_marketing import env as env  # noqa: PLC0414 -- shared offline fixture
from test_marketing import m1 as m1  # noqa: PLC0414 -- shared offline fixture
from test_second import OTHER, TENANT, confirm, headers, proposal

import command
import trigger_google
import trigger_marketing_api as api
from trigger_marketing_contract import Post, Posts, Schedule, utc_now
from trigger_meta import GRAPH, PERMISSIONS, MetaFailure, context
from trigger_publisher import Publisher, publish_due
from vault import open_seal

PAGE = '123456'
PAGE_OTHER = '789012'
USER_TOKEN = 'placeholder-long-user-token'
PAGE_TOKEN = 'placeholder-page-token'
APP_SECRET = 'placeholder-meta-app-secret'
LINK = 'https://www.facebook.com/123456/posts/9001'


class FakeMeta:
    def __init__(self):
        self.calls, self.posts = [], []
        self.mode, self.revoked, self.link_mode = None, False, None
        self.pages = [{'id': PAGE, 'name': 'placeholder Page', 'tasks': ['CREATE_CONTENT'], 'access_token': PAGE_TOKEN},
                      {'id': PAGE_OTHER, 'name': 'placeholder other Page', 'tasks': ['ANALYZE'], 'access_token': 'placeholder-other-token'}]

    def __call__(self, request):
        assert request.url.host == 'graph.facebook.com'
        assert request.url.path.startswith('/v26.0/')
        assert all(value not in str(request.url) for value in (USER_TOKEN, PAGE_TOKEN, APP_SECRET, 'placeholder-code'))
        self.calls.append((request.method, request.url.path))
        path = request.url.path.removeprefix('/v26.0/')
        if path == 'oauth/access_token':
            assert request.method == 'POST'
            body = parse_qs(request.content.decode())
            assert body['client_secret'] == [APP_SECRET]
            return httpx.Response(200, json={'access_token': USER_TOKEN if 'fb_exchange_token' in body else 'placeholder-short-user-token'})
        authorization = request.headers['Authorization']
        if path == 'me/permissions':
            assert authorization == 'Bearer ' + USER_TOKEN
            if request.method == 'DELETE':
                if self.mode == 'revoke-failure':
                    return httpx.Response(503, json={'error': {'code': 2, 'message': 'placeholder revoke rejected'}})
                self.revoked = True
                return httpx.Response(200, json={'success': True})
            return httpx.Response(200, json={'data': [{'permission': p, 'status': 'granted'} for p in PERMISSIONS]})
        if path == 'me/accounts':
            assert authorization == 'Bearer ' + USER_TOKEN
            return httpx.Response(200, json={'data': self.pages})
        assert authorization == 'Bearer ' + PAGE_TOKEN
        if path == PAGE + '/feed':
            assert request.method == 'POST'
            if isinstance(self.mode, int):
                return httpx.Response(self.mode, json={'error': {'code': 200 if self.mode == 400 else 2,
                    'message': 'placeholder refusal ' + PAGE_TOKEN + ' ' + APP_SECRET}})
            if self.mode == 'connect-failure':
                raise httpx.ConnectError('placeholder connection failure', request=request)
            body = parse_qs(request.content.decode())
            item = {'id': PAGE + '_9001', 'message': body['message'][0], 'created_time': utc_now().isoformat(), 'permalink_url': LINK}
            self.posts.append(item)
            if self.mode == 'timeout':
                raise httpx.ReadTimeout('placeholder timeout', request=request)
            if self.mode == 'crash':
                raise asyncio.CancelledError('placeholder process crash')
            return httpx.Response(200, json={'id': item['id']})
        if path == PAGE + '/published_posts':
            assert request.method == 'GET'
            if self.mode == 'reconcile-failure':
                return httpx.Response(503, json={'error': {'code': 2, 'message': 'placeholder unavailable'}})
            return httpx.Response(200, json={'data': self.posts})
        if path == PAGE + '_9001':
            assert request.method == 'GET'
            if self.link_mode:
                return httpx.Response(503, json={'error': {'code': 2, 'message': 'placeholder link unavailable'}})
            return httpx.Response(200, json={'permalink_url': LINK})
        raise AssertionError('Unexpected fake Meta path')


@pytest_asyncio.fixture
async def m2(m1, monkeypatch):
    monkeypatch.setenv('TRIGGER_META_APP_ID', 'placeholder-meta-app-id')
    monkeypatch.setenv('TRIGGER_META_APP_SECRET', APP_SECRET)
    monkeypatch.setenv('TANK_VAULT_KEY', base64.urlsafe_b64encode(b'placeholder-vault-key-for-tests!!').decode())
    fake = FakeMeta()
    original = httpx.AsyncClient
    def client(**kwargs):
        if 'transport' not in kwargs:
            assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
            kwargs['transport'] = httpx.MockTransport(fake)
        return original(**kwargs)
    monkeypatch.setattr(trigger_google.httpx, 'AsyncClient', client)
    m1.fake = fake
    return m1


async def connected(m2, *, select=True):
    result = await m2.store.meta.connect(m2.actor)
    state = parse_qs(urlsplit(result['url']).query)['state'][0]
    assert (await m2.store.meta.callback(m2.actor, state, 'placeholder-code'))['status'] == 'connected'
    row = await m2.env.pool.fetchrow('SELECT * FROM tank.trigger_meta_connections WHERE tenant_id=$1', TENANT)
    if select:
        await m2.store.meta.select(TENANT, PAGE, row['generation'])
    return row['generation']


async def facebook(m2):
    generation = await connected(m2)
    ident = await post(m2, channel='facebook')
    await m2.store.transition(TENANT, 'post.approve', Post(post_id=ident, expected_revision=1, location=PAGE, connection_generation=generation), uuid4())
    await m2.store.transition(TENANT, 'post.schedule', Schedule(post_id=ident, expected_revision=1,
        planned_at=utc_now()+timedelta(days=1), time_zone='UTC'), uuid4())
    await m2.env.pool.execute("UPDATE tank.trigger_posts SET planned_at=now()-interval '1 minute' WHERE tenant_id=$1 AND id=$2", TENANT, ident)
    return ident, generation


@pytest.mark.asyncio
async def test_state_single_use_user_tenant_bound_and_real_vault_is_scoped(m2, caplog):
    result = await m2.store.meta.connect(m2.actor)
    query = parse_qs(urlsplit(result['url']).query)
    assert query['response_type'] == ['code'] and set(query['scope'][0].split(',')) == set(PERMISSIONS)
    assert not {'code_challenge', 'code_verifier', 'client_secret'} & set(query)
    state = query['state'][0]
    for actor in (command.Actor(OTHER, m2.actor.user_id, True), command.Actor(TENANT, 'placeholder-other-user', True)):
        with pytest.raises(HTTPException):
            await m2.store.meta.callback(actor, state, 'placeholder-code')
    assert m2.fake.calls == []
    response = await m2.store.meta.callback(m2.actor, state, 'placeholder-code')
    assert response == {'status': 'connected'}
    with pytest.raises(HTTPException):
        await m2.store.meta.callback(m2.actor, state, 'placeholder-code')
    row = await m2.env.pool.fetchrow('SELECT * FROM tank.trigger_meta_connections WHERE tenant_id=$1', TENANT)
    assert USER_TOKEN not in row['sealed']
    assert open_seal(row['sealed'], context(TENANT, str(row['generation']))) == {'user_token': USER_TOKEN}
    for scope in (context(OTHER, str(row['generation'])), context(TENANT, str(uuid4()))):
        with pytest.raises(HTTPException):
            open_seal(row['sealed'], scope)
    assert USER_TOKEN not in str(response) + caplog.text and APP_SECRET not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['expired', 'denied', 'reconnected', 'disconnected'])
async def test_bad_or_superseded_state_never_installs_tokens(m2, failure):
    link = await m2.store.meta.connect(m2.actor)
    state = parse_qs(urlsplit(link['url']).query)['state'][0]
    if failure == 'expired':
        await m2.env.pool.execute("UPDATE tank.trigger_meta_states SET expires_at=now()-interval '1 minute' WHERE tenant_id=$1", TENANT)
    elif failure == 'reconnected':
        await m2.store.meta.connect(m2.actor)
    elif failure == 'disconnected':
        row = await m2.env.pool.fetchrow('SELECT generation FROM tank.trigger_meta_connections WHERE tenant_id=$1', TENANT)
        await m2.store.meta.disconnect(TENANT, row['generation'])
    with pytest.raises(HTTPException):
        await m2.store.meta.callback(m2.actor, state, None if failure == 'denied' else 'placeholder-code', 'access_denied' if failure == 'denied' else None)
    assert not m2.fake.calls
    assert await m2.env.pool.fetchval('SELECT sealed FROM tank.trigger_meta_connections WHERE tenant_id=$1', TENANT) is None


@pytest.mark.asyncio
async def test_page_selection_is_owned_generation_bound_and_never_returns_credentials(m2, caplog):
    generation = await connected(m2, select=False)
    pages = await m2.store.meta.pages(TENANT)
    assert pages == [{'page_id': PAGE, 'name': 'placeholder Page'}]
    for tenant, page_id, gen in [(OTHER, PAGE, generation), (TENANT, PAGE_OTHER, generation), (TENANT, PAGE, uuid4())]:
        with pytest.raises(HTTPException):
            await m2.store.meta.select(tenant, page_id, gen)
    response = await m2.store.meta.select(TENANT, PAGE, generation)
    row = await m2.env.pool.fetchrow('SELECT * FROM tank.trigger_meta_connections WHERE tenant_id=$1', TENANT)
    bundle = open_seal(row['sealed'], context(TENANT, str(generation)))
    assert bundle == {'user_token': USER_TOKEN, 'page_token': PAGE_TOKEN}
    assert all(value not in str(response)+str(pages)+caplog.text+row['sealed'] for value in (USER_TOKEN, PAGE_TOKEN, APP_SECRET))


@pytest.mark.asyncio
async def test_due_facebook_publishes_once_keeps_id_link_and_code_receipt(m2):
    ident, _ = await facebook(m2)
    await asyncio.gather(Publisher(m2.store).once(TENANT), Publisher(m2.store).once(TENANT))
    assert await Publisher(m2.store).once(TENANT) is None
    row = await m2.store.post(TENANT, ident)
    assert (row['state'], row['delivery'], row['platform_id'], row['platform_url']) == ('published', 'done', PAGE+'_9001', LINK)
    assert len(m2.fake.posts) == 1
    receipt = await m2.env.pool.fetchrow('SELECT cost_usd,tokens_in,tokens_out FROM tank.ledger WHERE tenant_id=$1 AND id=$2', TENANT, row['ledger_id'])
    assert receipt['cost_usd'] == receipt['tokens_in'] == receipt['tokens_out'] == 0
    assert m2.env.model.await_count == m2.env.planner.await_count == 0
    result = await m2.store.posts(TENANT, Posts(channel='facebook'))
    assert result['items'][0]['status'] == 'published' and result['items'][0]['url'] == LINK


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['timeout', 'crash'])
async def test_possibly_sent_or_crashed_send_never_automatically_repeats(m2, mode):
    ident, _ = await facebook(m2)
    m2.fake.mode = mode
    if mode == 'crash':
        with pytest.raises(asyncio.CancelledError):
            await Publisher(m2.store).once(TENANT)
        await m2.env.pool.execute("UPDATE tank.trigger_posts SET lease_until=now()-interval '1 minute' WHERE tenant_id=$1 AND id=$2", TENANT, ident)
    else:
        await Publisher(m2.store).once(TENANT)
    assert await Publisher(m2.store).once(TENANT) is None
    row = await m2.store.post(TENANT, ident)
    assert row['delivery'] == 'uncertain' and len(m2.fake.posts) == 1
    m2.fake.mode = None
    _, card = await card_for(m2.env, 'trigger.post.retry', {'post_id': str(ident)}, user='founder')
    result = await confirm(m2.env, card, user='founder')
    assert result['status'] == 'confirmed' and result['result']['status'] == 'published'
    assert result['result']['url'] == LINK
    assert await Publisher(m2.store).once(TENANT) is None and len(m2.fake.posts) == 1


@pytest.mark.asyncio
async def test_meta_refusal_fails_once_with_sanitised_message(m2, caplog):
    ident, _ = await facebook(m2)
    m2.fake.mode = 400
    await Publisher(m2.store).once(TENANT)
    row = await m2.store.post(TENANT, ident)
    assert row['state'] == 'failed' and not row['retryable'] and row['retry_at'] is None
    assert 'placeholder refusal' in row['platform_error']
    assert PAGE_TOKEN not in row['platform_error']+caplog.text and APP_SECRET not in row['platform_error']+caplog.text
    assert await Publisher(m2.store).once(TENANT) is None
    assert sum(method == 'POST' and path.endswith('/feed') for method, path in m2.fake.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [429, 503])
async def test_known_transient_meta_refusals_backoff_at_most_three_attempts(m2, status):
    ident, _ = await facebook(m2)
    m2.fake.mode = status
    for attempt in range(1, 4):
        before = utc_now()
        await Publisher(m2.store).once(TENANT)
        row = await m2.store.post(TENANT, ident)
        assert row['attempts'] == attempt and row['state'] == 'failed'
        if attempt < 3:
            assert before+timedelta(seconds=30*2**attempt-1) <= row['retry_at'] <= utc_now()+timedelta(seconds=30*2**attempt)
            assert await Publisher(m2.store).once(TENANT) is None
            await m2.env.pool.execute("UPDATE tank.trigger_posts SET retry_at=now()-interval '1 second' WHERE tenant_id=$1 AND id=$2", TENANT, ident)
        else:
            assert row['retry_at'] is None
    assert await Publisher(m2.store).once(TENANT) is None
    assert len(m2.fake.posts) == 0


@pytest.mark.asyncio
async def test_link_read_failure_retains_id_and_read_recovers_without_resending(m2):
    ident, _ = await facebook(m2)
    m2.fake.link_mode = 'placeholder failure'
    await Publisher(m2.store).once(TENANT)
    row = await m2.store.post(TENANT, ident)
    assert row['state'] == 'published' and row['platform_id'] == PAGE+'_9001' and row['platform_url'] is None
    m2.fake.link_mode = None
    assert (await m2.store.posts(TENANT, Posts(channel='facebook')))['items'][0]['url'] == LINK
    assert len(m2.fake.posts) == 1


@pytest.mark.asyncio
async def test_other_channels_and_disconnected_page_never_claimed(m2):
    for channel in ('instagram', 'linkedin', 'x'):
        ident = await post(m2, channel=channel)
        await m2.env.pool.execute("""UPDATE tank.trigger_posts SET state='scheduled',approved_revision=revision,
            planned_at=now()-interval '1 minute' WHERE tenant_id=$1 AND id=$2""", TENANT, ident)
    assert await Publisher(m2.store).claim(TENANT) is None
    ident, generation = await facebook(m2)
    await m2.store.meta.disconnect(TENANT, generation)
    assert m2.fake.revoked
    assert await Publisher(m2.store).claim(TENANT) is None
    once = AsyncMock()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Publisher, 'once', once)
        await publish_due(SimpleNamespace(admin_pool=lambda: m2.env.pool, pool=lambda: m2.env.pool))
        once.assert_not_awaited()
    assert not m2.fake.posts


@pytest.mark.asyncio
@pytest.mark.parametrize('failed', [False, True])
async def test_disconnect_revokes_then_clears_and_retains_token_on_refusal(m2, failed):
    generation = await connected(m2)
    if failed:
        m2.fake.mode = 'revoke-failure'
        with pytest.raises(MetaFailure):
            await m2.store.meta.disconnect(TENANT, generation)
    else:
        assert (await m2.store.meta.disconnect(TENANT, generation))['status'] == 'disconnected'
    row = await m2.env.pool.fetchrow('SELECT sealed,page_id,status FROM tank.trigger_meta_connections WHERE tenant_id=$1', TENANT)
    assert bool(row['sealed']) is failed
    assert (row['page_id'] is not None) is failed
    assert row['status'] == ('connected' if failed else 'disconnected')
    assert m2.fake.revoked is not failed


@pytest.mark.asyncio
async def test_existing_cards_confirm_meta_admin_actions_and_zero_receipt(m2):
    _, card = await proposal(m2.env, 'trigger.meta.connect', user='admin', role='org:admin')
    assert not m2.fake.calls
    result = await confirm(m2.env, card, user='admin', role='org:admin')
    assert result['status'] == 'confirmed'
    state = parse_qs(urlsplit(result['result']['url']).query)['state'][0]
    callback = await m2.env.client.post('/v1/command/trigger-meta/oauth/callback',
        json={'state': state, 'code': 'placeholder-code'}, headers=headers(user='admin', role='org:admin'))
    assert callback.status_code == 200 and callback.json() == {'status': 'connected'}
    _, card = await proposal(m2.env, 'trigger.meta.pages', user='admin', role='org:admin')
    result = await confirm(m2.env, card, user='admin', role='org:admin')
    assert result['result']['items'] == [{'page_id': PAGE, 'name': 'placeholder Page'}]
    ledger = await m2.env.pool.fetchrow('SELECT cost_usd FROM tank.ledger WHERE tenant_id=$1 AND id=$2', TENANT, UUID(result['result']['ledger_id']))
    assert ledger['cost_usd'] == 0
    _, card = await proposal(m2.env, 'trigger.meta.page.select: ' + json.dumps({'page_id': PAGE}), user='admin', role='org:admin')
    assert (await confirm(m2.env, card, user='admin', role='org:admin'))['status'] == 'confirmed'
    _, card = await proposal(m2.env, 'trigger.meta.disconnect', user='admin', role='org:admin')
    assert not m2.fake.revoked
    assert (await confirm(m2.env, card, user='admin', role='org:admin'))['status'] == 'confirmed'
    assert m2.fake.revoked and m2.env.model.await_count == m2.env.planner.await_count == 0
    member = command.Actor(TENANT, 'placeholder-member', False)
    for tool in ('meta.connect', 'meta.pages', 'meta.page.select', 'meta.disconnect'):
        assert 'trigger.'+tool not in command.allowed_tools(member)
    unconfirmed = await m2.env.client.post('/v1/trigger/marketing/meta.connect', json={}, headers=headers(user='admin', role='org:admin'))
    assert unconfirmed.status_code == 409
