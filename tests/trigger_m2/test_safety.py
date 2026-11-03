"""Native tenant RLS, stale consent/binding, reconciliation and transport guards."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import asyncpg
import httpx
import pytest
from fastapi import HTTPException

from test_meta import PAGE, PAGE_OTHER, TENANT, OTHER, facebook
from test_meta import m2 as m2  # noqa: PLC0414 -- shared fixture
from test_marketing import env as env  # noqa: PLC0414 -- shared fixture
from test_marketing import m1 as m1  # noqa: PLC0414 -- shared fixture
from test_marketing import card_for
from test_second import confirm
from trigger_meta import GRAPH, Meta, MetaFailure
from trigger_publisher import Publisher

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_native_meta_rls_rollout_is_idempotent_and_blocks_foreign_rows(m2):
    pool = m2.env.pool
    await m2.store.meta.connect(m2.actor)
    tables = ['trigger_meta_connections', 'trigger_meta_states']
    assert not await pool.fetchval("SELECT bool_or(relrowsecurity) FROM pg_class WHERE relnamespace='tank'::regnamespace AND relname=ANY($1::text[])", tables)
    await pool.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
    ddl = '-- Trigger M2:' + (ROOT/'tank/schema.sql').read_text().split('-- Trigger M2:')[1].split('-- BEGIN GENERATED AGENT MEMORY')[0]
    await pool.execute(ddl)
    await pool.execute(ddl)
    assert await pool.fetchval("SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class WHERE relnamespace='tank'::regnamespace AND relname=ANY($1::text[])", tables)
    await pool.execute("INSERT INTO tank.trigger_meta_connections(tenant_id,generation,status,user_id) VALUES($1,$2,'disconnected','placeholder-other')", OTHER, uuid4())
    await pool.execute("""INSERT INTO tank.trigger_meta_states(tenant_id,state_hash,user_id,generation,sealed,expires_at)
        VALUES($1,'placeholder-state','placeholder-user',$2,'placeholder-ciphertext',now()+interval '1 minute')""", OTHER, uuid4())
    await pool.execute('CREATE ROLE placeholder_trigger_m2 NOLOGIN NOBYPASSRLS')
    try:
        await pool.execute('GRANT USAGE ON SCHEMA tank TO placeholder_trigger_m2')
        await pool.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON tank.trigger_meta_connections,tank.trigger_meta_states TO placeholder_trigger_m2')
        async with pool.acquire() as conn, conn.transaction():
            await conn.execute('SET LOCAL ROLE placeholder_trigger_m2')
            await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(TENANT))
            assert await conn.fetchval('SELECT count(*) FROM tank.trigger_meta_connections') == 1
            assert await conn.fetchval('SELECT count(*) FROM tank.trigger_meta_states') == 1
            assert await conn.execute("UPDATE tank.trigger_meta_connections SET user_id='placeholder-refused' WHERE tenant_id=$1", OTHER) == 'UPDATE 0'
            assert await conn.execute('DELETE FROM tank.trigger_meta_states WHERE tenant_id=$1', OTHER) == 'DELETE 0'
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute("""INSERT INTO tank.trigger_meta_states(tenant_id,state_hash,user_id,generation,sealed,expires_at)
                        VALUES($1,'placeholder-forbidden','placeholder-user',$2,'placeholder-sealed',now())""", OTHER, uuid4())
    finally:
        await pool.execute('DROP OWNED BY placeholder_trigger_m2')
        await pool.execute('DROP ROLE placeholder_trigger_m2')


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['unavailable', 'malformed', 'changed-binding'])
async def test_failed_reconciliation_cannot_authorise_another_publish(m2, failure):
    ident, _ = await facebook(m2)
    m2.fake.mode = 'timeout'
    await Publisher(m2.store).once(TENANT)
    if failure == 'unavailable':
        m2.fake.mode = 'reconcile-failure'
    elif failure == 'malformed':
        m2.fake.posts[0]['created_time'] = 'placeholder invalid timestamp'
    else:
        await m2.env.pool.execute('UPDATE tank.trigger_meta_connections SET generation=$2 WHERE tenant_id=$1', TENANT, uuid4())
    _, card = await card_for(m2.env, 'trigger.post.retry', {'post_id': str(ident)}, user='founder')
    await confirm(m2.env, card, user='founder')
    assert (await m2.store.post(TENANT, ident))['delivery'] == 'uncertain'
    assert await Publisher(m2.store).once(TENANT) is None
    assert len(m2.fake.posts) == 1


@pytest.mark.asyncio
async def test_complete_reconciliation_without_match_requires_confirm_before_one_retry(m2):
    ident, _ = await facebook(m2)
    m2.fake.mode = 'timeout'
    await Publisher(m2.store).once(TENANT)
    m2.fake.posts.clear()  # Fake models an external send that did not persist.
    m2.fake.mode = None
    assert await Publisher(m2.store).once(TENANT) is None
    _, card = await card_for(m2.env, 'trigger.post.retry', {'post_id': str(ident)}, user='founder')
    assert (await confirm(m2.env, card, user='founder'))['result']['state'] == 'scheduled'
    await Publisher(m2.store).once(TENANT)
    assert await Publisher(m2.store).once(TENANT) is None
    assert len(m2.fake.posts) == 1


@pytest.mark.asyncio
async def test_page_change_cannot_redirect_an_approved_post(m2):
    ident, generation = await facebook(m2)
    m2.fake.pages[1]['tasks'] = ['CREATE_CONTENT']
    await m2.store.meta.select(TENANT, PAGE_OTHER, generation)
    assert await Publisher(m2.store).claim(TENANT) is None
    assert (await m2.store.post(TENANT, ident))['location'] == PAGE
    assert not m2.fake.posts
    # A new approval must use the current Page, not a stale preview.
    with pytest.raises(HTTPException):
        await m2.store.transition(TENANT, 'post.schedule', SimpleNamespace(post_id=ident, expected_revision=1), uuid4())


@pytest.mark.asyncio
async def test_callback_racing_disconnect_cannot_resurrect_a_grant(m2, monkeypatch):
    from urllib.parse import parse_qs, urlsplit
    from trigger_meta import TOKEN

    link = await m2.store.meta.connect(m2.actor)
    state = parse_qs(urlsplit(link['url']).query)['state'][0]
    generation = await m2.env.pool.fetchval('SELECT generation FROM tank.trigger_meta_connections WHERE tenant_id=$1', TENANT)
    entered, release = asyncio.Event(), asyncio.Event()
    original = m2.store.meta.http
    async def exchange(method, url, **kwargs):
        if url == TOKEN and 'code' in kwargs.get('data', {}):
            entered.set()
            await release.wait()
        return await original(method, url, **kwargs)
    monkeypatch.setattr(m2.store.meta, 'http', exchange)
    callback = asyncio.create_task(m2.store.meta.callback(m2.actor, state, 'placeholder-code'))
    await asyncio.wait_for(entered.wait(), 5)
    await m2.store.meta.disconnect(TENANT, generation)
    release.set()
    with pytest.raises(HTTPException):
        await callback
    assert await m2.env.pool.fetchval('SELECT sealed FROM tank.trigger_meta_connections WHERE tenant_id=$1', TENANT) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('failure,uncertain,retryable', [
    ('connect', False, True), ('read', True, False), ('write', True, False),
    ('malformed', True, False), ('oversized', True, False), ('html-503', True, False),
])
async def test_meta_transport_distinguishes_unsent_from_unknown_send(monkeypatch, failure, uncertain, retryable):
    import trigger_google
    original = httpx.AsyncClient
    def handler(request):
        if failure in {'connect', 'read', 'write'}:
            error = {'connect': httpx.ConnectError, 'read': httpx.ReadTimeout, 'write': httpx.WriteError}[failure]
            raise error('placeholder transport error', request=request)
        return httpx.Response(503 if failure == 'html-503' else 200, content=b'x'*2_000_001 if failure == 'oversized' else b'placeholder malformed response')
    monkeypatch.setattr(trigger_google.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    from trigger_google import GoogleFailure
    meta = Meta(None)
    with pytest.raises(GoogleFailure) as caught:
        response = await meta.http('POST', GRAPH + PAGE + '/feed', may_have_sent=True)
        meta.result(response, may_have_sent=True)
    assert caught.value.uncertain is uncertain
    assert caught.value.retryable is retryable
    assert str(caught.value) == ''


@pytest.mark.parametrize('code', [None, [], {}, 'placeholder-bad-code'])
def test_malformed_graph_error_code_is_sanitised_failure(code):
    with pytest.raises(MetaFailure):
        Meta.result(httpx.Response(400, json={'error': {'code': code, 'message': 'placeholder error'}}))
