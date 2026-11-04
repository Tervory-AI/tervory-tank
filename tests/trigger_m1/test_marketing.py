"""M1 offline proof: isolated SQL, fake Google, actual Command and W1 checkers."""
import asyncio
import hashlib
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
sys.path.insert(0, str(ROOT / 'tests/trigger_gate2'))
import command
import trigger_google as google_module
import trigger_marketing_api as api
from test_gate2 import card_for
from test_gate2 import env as env  # noqa: PLC0414 -- pytest fixture re-export
from test_second import OTHER, TENANT, confirm
from test_second import headers as fixture_headers
from trigger_google import Google, GoogleFailure
from trigger_marketing import Marketing
from trigger_marketing_contract import (
    FORMATS,
    Calendar,
    Create,
    Edit,
    Post,
    Schedule,
    schedulable,
    utc_now,
)
from trigger_publisher import Publisher

LOCATION = 'accounts/123/locations/456'


@pytest_asyncio.fixture
async def m1(env, monkeypatch):
    google = Google(env.pool)
    google.request = AsyncMock(return_value={'name': LOCATION+'/localPosts/placeholder-post', 'searchUrl': 'https://google.com/placeholder-post'})
    store = Marketing(env.pool, google)
    monkeypatch.setattr(api, 'service', lambda: store)
    from main import app
    app.include_router(api.router)
    actor = command.Actor(TENANT, 'founder', True)
    generation = uuid4()
    await env.pool.execute("""INSERT INTO tank.trigger_gbp_connections(tenant_id,generation,status,location,user_id)
        VALUES($1,$2,'connected',$3,'founder')""", TENANT, generation, LOCATION)
    return SimpleNamespace(env=env, store=store, google=google, actor=actor, generation=generation)


async def post(m1, channel='gbp', text='A precise placeholder post.', limit=None, count=None):
    report = {'complete': True, 'format': FORMATS[channel], 'length': {'limit': limit,
              'count': len(text) if count is None else count, 'unit': 'Unicode code points'}, 'issues': [], 'issue_count': 0}
    write_id = uuid4()
    await m1.env.pool.execute("""INSERT INTO tank.trigger_writes(id,tenant_id,user_id,brief,draft,checker_results,format,write_context)
        VALUES($1,$2,'founder','placeholder brief',$3,$4::jsonb,$5,'{}')""", write_id, TENANT, text, json.dumps(report), FORMATS[channel])
    result = await m1.store.create(m1.actor, Create(channel=channel, write_id=write_id), uuid4())
    return UUID(str(result['id']))


async def approved(m1, ident):
    return await m1.store.transition(TENANT, 'post.approve', Post(post_id=ident, expected_revision=1,
        connection_generation=m1.generation, location=LOCATION), uuid4())


async def scheduled(m1, ident):
    await approved(m1, ident)
    await m1.store.transition(TENANT, 'post.schedule', Schedule(post_id=ident, expected_revision=1,
        planned_at=utc_now()+timedelta(days=1), time_zone='UTC'), uuid4())
    await m1.env.pool.execute("UPDATE tank.trigger_posts SET planned_at=now()-interval '1 minute' WHERE tenant_id=$1 AND id=$2", TENANT, ident)


@pytest.mark.asyncio
async def test_gbp_none_limit_schedules_only_once_approved_and_edit_returns_draft(m1):
    ident = await post(m1)
    args = Schedule(post_id=ident, expected_revision=1, planned_at=utc_now()+timedelta(days=1), time_zone='UTC')
    with pytest.raises(HTTPException):
        await m1.store.transition(TENANT, 'post.schedule', args, uuid4())
    await approved(m1, ident)
    result = await m1.store.transition(TENANT, 'post.schedule', args, uuid4())
    assert result['state'] == 'scheduled' and result['report']['length']['limit'] is None
    m1.store.check = AsyncMock(return_value={'complete': True, 'format': FORMATS['gbp'], 'length': {'limit': None, 'count': 10}})
    changed = await m1.store.transition(TENANT, 'post.edit', Edit(post_id=ident, expected_revision=1, text='Edited placeholder.'), uuid4())
    assert changed['state'] == 'draft' and changed['revision'] == 2 and changed['approved_revision'] is None
    with pytest.raises(HTTPException):
        await m1.store.transition(TENANT, 'post.schedule', args, uuid4())


@pytest.mark.asyncio
async def test_over_limit_stale_approval_and_foreign_tenant_refused(m1):
    ident = await post(m1, 'instagram', limit=2200, count=2201)
    assert not schedulable({'complete': True, 'format': FORMATS['instagram'], 'length': {'count': 2201, 'limit': 2200}}, 'instagram')
    with pytest.raises(HTTPException):
        await approved(m1, ident)
    with pytest.raises(HTTPException):
        await m1.store.post(OTHER, ident)
    ident = await post(m1)
    with pytest.raises(HTTPException):
        await m1.store.transition(TENANT, 'post.approve', Post(post_id=ident, expected_revision=99), uuid4())
    with pytest.raises(HTTPException):
        await m1.store.transition(TENANT, 'post.approve', Post(post_id=ident, expected_revision=1, location=LOCATION, connection_generation=uuid4()), uuid4())


@pytest.mark.asyncio
async def test_two_publishers_and_restart_never_double_post_and_record_zero_receipt(m1):
    ident = await post(m1)
    await scheduled(m1, ident)
    await asyncio.gather(Publisher(m1.store).once(TENANT), Publisher(m1.store).once(TENANT))
    await Publisher(Marketing(m1.env.pool, m1.google)).once(TENANT)
    m1.google.request.assert_awaited_once()
    row = await m1.store.post(TENANT, ident)
    assert row['state'] == 'published' and row['platform_id'].endswith('/placeholder-post')
    ledger = await m1.env.pool.fetchrow('SELECT cost_usd,tokens_in,tokens_out FROM tank.ledger WHERE tenant_id=$1 AND id=$2', TENANT, row['ledger_id'])
    assert ledger['cost_usd'] == ledger['tokens_in'] == ledger['tokens_out'] == 0


@pytest.mark.asyncio
async def test_crash_after_durable_claim_never_replays_uncertain_post(m1):
    ident = await post(m1)
    await scheduled(m1, ident)
    assert await Publisher(m1.store).claim(TENANT)
    await m1.env.pool.execute("UPDATE tank.trigger_posts SET lease_until=now()-interval '1 minute' WHERE tenant_id=$1 AND id=$2", TENANT, ident)
    assert await Publisher(m1.store).once(TENANT) is None
    row = await m1.store.post(TENANT, ident)
    assert row['state'] == 'failed' and row['delivery'] == 'uncertain' and not row['retryable']
    m1.google.request.assert_not_awaited()
    result = await m1.store.transition(TENANT, 'post.retry', Post(post_id=ident, expected_revision=1), uuid4())
    assert result['state'] == 'scheduled'
    assert m1.google.request.await_args.args[1] == 'GET'


@pytest.mark.asyncio
async def test_google_too_long_is_failed_with_exact_message_no_auto_retry_edit_drafts(m1):
    ident = await post(m1)
    await scheduled(m1, ident)
    m1.google.request.side_effect = GoogleFailure(400, 'placeholder summary too long')
    await Publisher(m1.store).once(TENANT)
    assert await Publisher(m1.store).once(TENANT) is None
    row = await m1.store.post(TENANT, ident)
    assert row['state'] == 'failed' and row['platform_error'] == 'placeholder summary too long'
    assert not row['retryable'] and row['retry_at'] is None
    m1.google.request.assert_awaited_once()
    m1.store.check = AsyncMock(return_value={'complete': True, 'format': FORMATS['gbp'], 'length': {'limit': None, 'count': 2}})
    row = await m1.store.transition(TENANT, 'post.edit', Edit(post_id=ident, expected_revision=1, text='placeholder edit'), uuid4())
    assert row['state'] == 'draft' and row['approved_revision'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [429, 503])
async def test_backoff_fixed_limit_and_confirmed_retry(m1, status):
    ident = await post(m1)
    await scheduled(m1, ident)
    m1.google.request.side_effect = GoogleFailure(status, 'placeholder retryable message')
    for attempt in range(1, 4):
        await Publisher(m1.store).once(TENANT)
        row = await m1.store.post(TENANT, ident)
        assert row['attempts'] == attempt and row['state'] == 'failed'
        assert await Publisher(m1.store).once(TENANT) is None
        if attempt<3:
            assert row['retry_at'] > utc_now()
            await m1.env.pool.execute("UPDATE tank.trigger_posts SET retry_at=now()-interval '1 second' WHERE tenant_id=$1 AND id=$2", TENANT, ident)
    assert row['retry_at'] is None and m1.google.request.await_count == 3
    thread, card = await card_for(m1.env, 'trigger.post.retry', {'post_id': str(ident)}, user='founder')
    result = await confirm(m1.env, card, user='founder')
    assert result['status'] == 'confirmed' and result['result']['state'] == 'scheduled'
    assert thread


@pytest.mark.parametrize('stamp,zone,valid', [
    ('2026-11-01T01:30:00-07:00','America/Los_Angeles',True),
    ('2026-11-01T01:30:00-08:00','America/Los_Angeles',True),
    ('2026-03-08T02:30:00-08:00','America/Los_Angeles',False),
    ('2026-11-01T01:30:00','America/Los_Angeles',False),
])
def test_dst_iana_zone_requires_real_local_offset(stamp, zone, valid):
    if valid:
        assert Schedule(post_id=uuid4(), planned_at=stamp, time_zone=zone)
    else:
        with pytest.raises(ValueError):
            Schedule(post_id=uuid4(), planned_at=stamp, time_zone=zone)


@pytest.mark.asyncio
@pytest.mark.parametrize('channel', ['instagram', 'linkedin', 'x'])
async def test_other_channels_stay_scheduled_due_in_own_local_calendar(m1, channel):
    ident = await post(m1, channel)
    await scheduled(m1, ident)
    assert await Publisher(m1.store).once(TENANT) is None
    data = await m1.store.calendar(TENANT, Calendar(start=utc_now().date(), period='week'))
    own = next(row for rows in data['days'].values() for row in rows if row['id'] == ident)
    assert own['due'] and own['state'] == 'scheduled'
    m1.google.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancelled_claim_is_not_sent(m1):
    ident = await post(m1)
    await scheduled(m1, ident)
    assert await Publisher(m1.store).claim(TENANT)
    row = await m1.store.transition(TENANT, 'post.cancel', Post(post_id=ident, expected_revision=1), uuid4())
    assert row['state'] == 'cancelled'
    assert await Publisher(m1.store).once(TENANT) is None
    m1.google.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_unconfirmed_and_member_actions_never_execute(m1, monkeypatch):
    calls = AsyncMock()
    monkeypatch.setattr(api, 'execute', calls)
    response = await m1.env.client.post('/v1/trigger/marketing/gbp.reply.send', json={'reply_id': str(uuid4())}, headers=fixture_headers())
    assert response.status_code == 409
    calls.assert_not_awaited()
    with pytest.raises(HTTPException):
        await api.authority(command.Actor(TENANT, 'placeholder-member', False, frozenset({'trigger'})), 'trigger.posts')


@pytest.mark.asyncio
async def test_reply_put_is_confirmed_and_identical_text_is_not_sent_twice(m1):
    write = uuid4()
    await m1.env.pool.execute("INSERT INTO tank.trigger_writes(id,tenant_id,user_id,brief,draft,checker_results) VALUES($1,$2,'founder','placeholder','placeholder reply','{}')", write, TENANT)
    await m1.env.pool.execute("INSERT INTO tank.trigger_gbp_reviews VALUES($1,$2,'placeholder-review','FIVE','placeholder customer text',now())", TENANT, LOCATION)
    reply = await m1.env.pool.fetchval("""INSERT INTO tank.trigger_gbp_replies(tenant_id,location,review_id,generation,write_id,text,report)
        VALUES($1,$2,'placeholder-review',$3,$4,'placeholder reply','{"complete":true}') RETURNING id""", TENANT, LOCATION, m1.generation, write)
    for _ in range(2):
        _, card = await card_for(m1.env, 'trigger.gbp.reply.send', {'reply_id': str(reply)}, user='founder')
        result = await confirm(m1.env, card, user='founder')
        assert result['status'] == 'confirmed', result
        assert result['result']['state'] == 'sent'
    m1.google.request.assert_awaited_once()
    assert m1.google.request.await_args.args[1] == 'PUT'
    assert m1.google.request.await_args.args[2].endswith('/reviews/placeholder-review/reply')


@pytest.mark.asyncio
async def test_oauth_state_user_tenant_pkce_refresh_only_and_disconnect(m1, monkeypatch, caplog):
    monkeypatch.setenv('TRIGGER_GOOGLE_OAUTH_CLIENT_ID', 'placeholder-client')
    monkeypatch.setenv('TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET', 'placeholder-client-secret')
    def sealed(data, context):
        return json.dumps({'placeholder': data, 'context': context})
    def opened(data, context):
        value = json.loads(data)
        assert value['context'] == context
        return value['placeholder']
    monkeypatch.setattr(google_module, 'seal', sealed)
    monkeypatch.setattr(google_module, 'open_seal', opened)
    google = Google(m1.env.pool)
    google.http = AsyncMock(return_value=httpx.Response(200, json={'refresh_token': 'placeholder-refresh-token',
        'access_token': 'placeholder-access-token', 'scope': google_module.SCOPE}))
    link = await google.connect(m1.actor)
    params = parse_qs(urlsplit(link['url']).query)
    assert params['code_challenge_method'] == ['S256'] and params['access_type'] == ['offline']
    state = params['state'][0]
    stored = await m1.env.pool.fetchrow('SELECT * FROM tank.trigger_gbp_states WHERE tenant_id=$1', TENANT)
    assert stored['state_hash'] == hashlib.sha256(state.encode()).hexdigest()
    for actor in [command.Actor(OTHER, 'founder', True), command.Actor(TENANT, 'placeholder-other-user', True)]:
        with pytest.raises(HTTPException):
            await google.callback(actor, state, 'placeholder-code')
    result = await google.callback(m1.actor, state, 'placeholder-code')
    row = await m1.env.pool.fetchrow('SELECT * FROM tank.trigger_gbp_connections WHERE tenant_id=$1', TENANT)
    assert 'placeholder-refresh-token' in row['sealed'] and 'placeholder-access-token' not in row['sealed']
    assert 'token' not in json.dumps(result) and 'placeholder-refresh-token' not in caplog.text
    with pytest.raises(HTTPException):
        await google.callback(m1.actor, state, 'placeholder-code')
    google.http.return_value = httpx.Response(200, json={})
    await google.disconnect(TENANT, row['generation'])
    assert google.http.await_args.args[:2] == ('POST', google_module.REVOKE)
    assert google.http.await_args.kwargs['data'] == {'token': 'placeholder-refresh-token'}
    assert await m1.env.pool.fetchval('SELECT sealed FROM tank.trigger_gbp_connections WHERE tenant_id=$1', TENANT) is None
