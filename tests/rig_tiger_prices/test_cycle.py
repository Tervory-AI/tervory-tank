"""Real Postgres stores and agent handlers; public HTTP is a saved offline page."""
import ipaddress
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio

from test_prices import A, B, ROOT, URL, corridor, product  # noqa: F401
from test_tiger import _load
from tiger_works.fixture import extract, no_paid_call, saved_page
from chassis.db import ensure_schema
from rigbox.store import PgStore as RigStore
from rig_watch import RigWatches, TankRig, confirmed_value
from watch import DomainLimiter, PgStore, ensure_tables

agent = _load('rig_prices_tiger_agent', ROOT / 'agents/tiger/app.py')
playbook = _load('rig_prices_playbook', ROOT / 'tank/skills/tiger.playbook/1.0.0/run.py')


@pytest_asyncio.fixture
async def database():
    dsn = os.environ.get('POOL_SCHEMA_DATABASE_URL')
    if not dsn:
        pytest.skip('Disposable local Postgres is required')
    parsed = urlsplit(dsn)
    assert parsed.hostname in {'localhost', '127.0.0.1', '::1'}, 'Local test database only'
    name = 'rig_tiger_test_' + uuid4().hex
    admin = await asyncpg.connect(dsn)
    await admin.execute('CREATE DATABASE ' + name)
    pool = None
    try:
        pool = await asyncpg.create_pool(urlunsplit(parsed._replace(path='/' + name)), min_size=1, max_size=4)
        async with pool.acquire() as conn:
            await ensure_schema(conn, 'tiger')
            await ensure_tables(conn, 'agent_tiger')
            await conn.execute((ROOT / 'agents/rig/schema.sql').read_text())
            # Repeat the additive startup paths, including both new receipt tables.
            await ensure_tables(conn, 'agent_tiger')
            await conn.execute((ROOT / 'agents/rig/schema.sql').read_text())
        yield pool
    finally:
        if pool:
            await pool.close()
        await admin.execute('DROP DATABASE ' + name)
        await admin.close()


@pytest_asyncio.fixture
async def system(database, corridor, monkeypatch):  # noqa: F811 — imported pytest fixture
    _, service, http = corridor
    rig = RigStore(database)
    service.store = rig
    for tenant in (A, B):
        await product(rig, tenant)
    tiger = PgStore(database)
    monkeypatch.setenv('TANK_URL', 'http://tank')
    monkeypatch.setenv('TANK_KEY', 'offline-tiger')
    def resolve(host, *args, **kwargs):
        try:
            address = str(ipaddress.ip_address(host))
        except ValueError:
            address = '8.8.8.8'
        return [(2, 1, 6, '', (address, 443))]
    monkeypatch.setattr('watch.socket.getaddrinfo', resolve)
    monkeypatch.setattr(agent.app.state, 'pool', database, raising=False)
    monkeypatch.setattr(agent.app.state, 'http', http, raising=False)
    monkeypatch.setattr(agent, '_limiter', DomainLimiter(0))
    state = SimpleNamespace(price='120', stock='InStock', blocked=False, reads=[], tasks=[])

    async def render(url, session, name, tenant, task):
        state.reads.append((tenant, url))
        return {'ok': not state.blocked, 'challenge': state.blocked,
                'html': saved_page(state.price, state.stock)}

    async def no_feed(*args):
        return {'found': False}

    async def skill(tenant, name, body):
        state.tasks.append(name)
        assert name == 'tiger.price_extract'
        return await extract(body['html'], body['url'])

    async def approved_skill(tenant, name, body):
        assert name == 'tiger.playbook'
        result = await playbook.run(body, None)
        assert result['model_calls'] == 0
        return result

    monkeypatch.setattr(agent, '_render', render)
    monkeypatch.setattr(agent, 'official_feed', no_feed)
    monkeypatch.setattr(agent, '_fetch_text', no_paid_call)

    def context(tenant=A, url=URL):
        return SimpleNamespace(tenant_id=tenant, input={'url': url}, job_id=uuid4(),
                               agent='tiger', files=None,
                               tank=SimpleNamespace(run_skill=skill, approved_skill=approved_skill))

    return SimpleNamespace(rig=rig, tiger=tiger, pool=database, http=http, client=TankRig(http),
                           managed=RigWatches(tiger), state=state, context=context)


async def start(system, tenants=2):
    assert await agent.rig_discover(system.context(agent.HEARTBEAT_TENANT)) == {'tenants': tenants}
    await agent.dispatch(system.context(A))
    await agent.dispatch(system.context(B))


@pytest.mark.asyncio
async def test_new_watch_cannot_dispatch_before_rig_binding_commits(system, monkeypatch):
    original = system.tiger.create_watch

    async def create(row):
        saved = await original(row)
        assert saved['enabled'] is False
        await agent.dispatch_tenant(system.tiger, A, datetime.now(timezone.utc))
        assert not await system.tiger.check_open(A, URL)
        return saved

    monkeypatch.setattr(system.tiger, 'create_watch', create)
    await system.managed.sync(A, system.client)
    assert (await system.tiger.get_watch(A, URL))['enabled']
    assert await system.managed.managed(A, URL)
    assert await system.tiger.check_open(A, URL)


@pytest.mark.asyncio
async def test_one_cycle_price_stock_and_tenant_isolation(system):
    await start(system)
    for tenant in (A, B):
        rows = await system.tiger.list_watches(tenant)
        assert len(rows) == 1 and rows[0]['enabled'] and rows[0]['every'] == '6h'
        assert await system.tiger.check_open(tenant, URL)
    await agent.check(system.context(A))
    assert (await system.rig.products(A))[0]['price'] == 120
    assert (await system.rig.products(B))[0]['price'] == 10
    system.state.price, system.state.stock = '145', 'OutOfStock'
    await agent.check(system.context(A))
    changed = (await system.rig.products(A))[0]
    assert changed['price'] == 145 and changed['active'] is False
    assert (await system.rig.products(B))[0]['price'] == 10
    # Out-of-stock is not deletion: the watch must see it come back into stock.
    assert (await system.tiger.get_watch(A, URL))['enabled']
    system.state.stock = 'InStock'
    await agent.check(system.context(A))
    assert (await system.rig.products(A))[0]['active'] is True
    assert set(system.state.tasks) == {'tiger.price_extract'}


@pytest.mark.asyncio
@pytest.mark.parametrize('reason', ['feed', 'deleted', 'no_url'])
async def test_product_becoming_ineligible_stops_before_next_read(system, reason):
    await start(system)
    if reason == 'feed':
        async with system.pool.acquire() as conn:
            await conn.execute('''INSERT INTO agent_rig.supplier_costs(tenant_id,sku,cost,currency,provider,site)
                VALUES($1,'item',10,'USD','shopify','https://feed.example')''', UUID(A))
    elif reason == 'deleted':
        async with system.rig.atomic(A) as store:
            await store.delete_products(A, ['item'])
    else:
        await product(system.rig, A, url='')
    # No dispatch first: the queued check itself must revalidate its product.
    result = await agent.check(system.context(A))
    assert result['status'] == 'skipped' and system.state.reads == []
    assert not (await system.tiger.get_watch(A, URL))['enabled']
    assert (await system.tiger.get_watch(B, URL))['enabled']
    assert not await system.tiger.check_open(A, URL)
    async with system.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_tiger.rig_targets WHERE tenant_id=$1', UUID(A)) == 0


@pytest.mark.asyncio
async def test_deleted_product_is_never_discovered_even_if_reimport_attempted(system):
    async with system.rig.atomic(A) as store:
        await store.delete_products(A, ['item'])
    assert await system.rig.upsert_product(A, dict(sku='item', name='Offline', brand='Offline',
        category='test', price=1, currency='USD', url=URL)) == 'skipped'
    await start(system, tenants=1)
    assert await system.tiger.list_watches(A) == []
    assert not await system.tiger.check_open(A, URL)
    assert (await agent.check(system.context(A)))['status'] == 'skipped'
    assert system.state.reads == []


@pytest.mark.asyncio
async def test_failed_send_is_durable_retries_without_rereading_and_keeps_tenant(system, monkeypatch):
    await start(system)
    original = system.http.request
    state = {'fail': True, 'posts': 0}

    async def request(method, url, **kw):
        if method == 'POST' and url.endswith('/rig/tiger'):
            state['posts'] += 1
            if state['fail']:
                return httpx.Response(503, request=httpx.Request(method, url))
        return await original(method, url, **kw)

    monkeypatch.setattr(system.http, 'request', request)
    await agent.check(system.context(A))
    assert state['posts'] == 1
    assert (await system.rig.products(A))[0]['price'] == 10
    async with system.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT pending,attempts,next_attempt_at>now() AS delayed FROM agent_tiger.rig_targets WHERE tenant_id=$1', UUID(A))
        assert row['pending'] and row['attempts'] == 1 and row['delayed']
    restarted = RigWatches(PgStore(system.pool))
    assert await restarted.deliver(A, system.client) == 0
    async with system.pool.acquire() as conn:
        await conn.execute('UPDATE agent_tiger.rig_targets SET next_attempt_at=now() WHERE tenant_id=$1', UUID(A))
    state['fail'] = False
    assert await restarted.deliver(A, system.client) == 1
    assert (await system.rig.products(A))[0]['price'] == 120
    assert (await system.rig.products(B))[0]['price'] == 10
    assert len(system.state.reads) == 1 and state['posts'] == 2
    assert await restarted.deliver(A, system.client) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('reason', ['feed', 'deleted'])
async def test_shared_watch_pending_removed_when_products_become_ineligible(system, monkeypatch, reason):
    await product(system.rig, A, sku='second')
    await start(system)
    assert len(await system.tiger.list_watches(A)) == 1
    async def failed(*args):
        raise httpx.ConnectError('Offline failure')
    monkeypatch.setattr(TankRig, 'send', failed)
    await agent.check(system.context(A))
    async with system.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_tiger.rig_targets WHERE tenant_id=$1 AND pending IS NOT NULL', UUID(A)) == 2
    if reason == 'feed':
        async with system.pool.acquire() as conn:
            await conn.executemany('''INSERT INTO agent_rig.supplier_costs(tenant_id,sku,cost,currency,provider,site)
                VALUES($1,$2,10,'USD','shopify','https://feed.example')''', [(UUID(A), sku) for sku in ('item', 'second')])
    else:
        async with system.rig.atomic(A) as store:
            await store.delete_products(A, ['item', 'second'])
    assert await system.managed.deliver(A, system.client) == 0
    assert not (await system.tiger.get_watch(A, URL))['enabled']
    assert (await system.rig.products(B))[0]['price'] == 10


@pytest.mark.asyncio
async def test_shared_url_updates_each_sku_once_with_one_read(system):
    await product(system.rig, A, sku='second')
    await start(system)
    await agent.check(system.context(A))
    assert {row['sku']: row['price'] for row in await system.rig.products(A)} == {'item': 120, 'second': 120}
    assert system.state.reads == [(A, URL)]
    assert (await system.rig.products(B))[0]['price'] == 10


@pytest.mark.asyncio
async def test_scope_blocks_private_urls_and_challenges_never_publish(system):
    await product(system.rig, A, sku='private', url='http://127.0.0.1/internal')
    await start(system)
    assert len(await system.tiger.list_watches(A)) == 1
    system.state.blocked = True
    result = await agent.check(system.context(A))
    assert result['status'] == 'blocked'
    assert (await system.rig.products(A))[0]['price'] == 10
    async with system.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_tiger.rig_targets WHERE pending IS NOT NULL') == 0


@pytest.mark.asyncio
async def test_legacy_feed_provenance_never_becomes_a_page_watch(system):
    await product(system.rig, A, sku='unfed', url=URL + '/unfed')
    await system.rig.put_feed(A, 'shopify', 'https://shop.example/products.json', 'USD')
    assert await system.rig.watch_products(A) == []  # Pre-existing provenance is unknown until refresh.
    feed = {'products': [{'id': 1, 'title': 'Offline item', 'vendor': 'Offline', 'product_type': 'test',
        'handle': 'item', 'images': [{'src': 'https://shop.example/item.jpg'}],
        'variants': [{'id': 2, 'sku': 'item', 'price': '10', 'available': True}]}]}
    async def fetch(url):
        return feed
    from rigbox.service import Service
    await Service(system.rig).pull_feeds(A, fetch)
    rows = await system.rig.watch_products(A)
    assert [row['sku'] for row in rows] == ['unfed']
    await start(system)
    assert [row['url'] for row in await system.tiger.list_watches(A)] == [URL + '/unfed']
    assert await Service(system.rig).apply_watch(A, 'item', {'price': '99'}) is False
    assert (await system.rig.products(B))[0]['price'] == 10


@pytest.mark.asyncio
async def test_url_change_cancels_old_read_and_rebinds_to_new_page(system):
    await start(system)
    await product(system.rig, A, url=URL + '/new')
    assert (await agent.check(system.context(A)))['status'] == 'skipped'
    assert system.state.reads == []
    assert (await system.tiger.get_watch(A, URL + '/new'))['enabled']
    assert not (await system.tiger.get_watch(A, URL))['enabled']
    await agent.check(system.context(A, URL + '/new'))
    assert (await system.rig.products(A))[0]['price'] == 120


@pytest.mark.asyncio
async def test_observation_and_delivery_state_rollback_together(system, monkeypatch):
    await start(system)
    import rig_watch
    async def unavailable(*args):
        raise RuntimeError('Offline durable-write failure')
    monkeypatch.setattr(rig_watch, 'record_observation', unavailable)
    with pytest.raises(RuntimeError, match='durable-write'):
        await agent.check(system.context(A))
    assert await system.tiger.latest_observation(A, URL) is None
    assert (await system.rig.products(A))[0]['price'] == 10


@pytest.mark.parametrize('mutation', [dict(method='unread'), dict(issue='missing_stock'), dict(currency=None),
                                    dict(availability="can't read"), dict(price='NaN'), dict(product_name=None)])
def test_incomplete_observations_never_queue(mutation):
    row = dict(method='jsonld', issue=None, currency='USD', availability='InStock', price='12', product_name='Offline')
    row.update(mutation)
    assert confirmed_value(row) is None
