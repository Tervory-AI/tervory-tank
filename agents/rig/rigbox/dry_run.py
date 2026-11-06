"""Execute Rig's recurring work in a disposable cloud database with fake I/O."""
import argparse
import asyncio
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
import socket
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg

JOBS = ('ping', 'pull_feeds', 'expire_searches', 'retry_quotes',
        'discover_quote_tenants', 'cart_sweep', 'price_events',
        'forge_retention', 'training_events')
TENANT = '11111111-1111-4111-8111-111111111111'


@contextmanager
def offline_network():
    resolve, connect, connect_ex = socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex
    def check(host):
        if host not in {'localhost', '127.0.0.1', '::1', b'localhost', b'127.0.0.1', b'::1'}:
            raise RuntimeError('Dry run refused non-loopback network access')
    def resolve_local(host, *args, **kwargs):
        check(host)
        return resolve(host, *args, **kwargs)
    def connecting(original):
        def local(sock, address):
            if isinstance(address, tuple):
                check(address[0])
            return original(sock, address)
        return local
    with patch.object(socket, 'getaddrinfo', resolve_local), \
            patch.object(socket.socket, 'connect', connecting(connect)), \
            patch.object(socket.socket, 'connect_ex', connecting(connect_ex)):
        yield


def local_database(value):
    parts = urlsplit(value)
    if (parts.scheme not in {'postgres', 'postgresql'} or parts.hostname not in
            {'127.0.0.1', 'localhost', '::1'} or parts.query or parts.fragment):
        raise ValueError('RIG_TEST_DATABASE_URL must name a disposable loopback database')
    return parts


@asynccontextmanager
async def database(url):
    parts = local_database(url)
    name = 'rig_dry_' + uuid4().hex
    conn = await asyncpg.connect(url)
    try:
        create = await conn.fetchval("SELECT format('CREATE DATABASE %I', $1::text)", name)
        await conn.execute(create)
        try:
            target = urlunsplit(parts._replace(path='/' + name))
            async with asyncpg.create_pool(target, min_size=1, max_size=4) as pool:
                yield pool
        finally:
            drop = await conn.fetchval("SELECT format('DROP DATABASE %I WITH (FORCE)', $1::text)", name)
            await conn.execute(drop)
    finally:
        await conn.close()


async def run(url, selected='all'):
    # All model, mail, store, source and bus boundaries below are in-process
    # fakes. Only the validated loopback PostgreSQL address can be contacted.
    from chassis.db import ensure_schema
    from rigbox.cart import Cart
    from rigbox.quotes.service import QuoteService
    from rigbox.quotes.store import PgQuotes
    from rigbox.store import PgStore
    from rigbox import price_events, training
    from forge.retention import sweep

    spec = importlib.util.spec_from_file_location('rig_offline_jobs', Path(__file__).parents[1] / 'app.py')
    room = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(room)
    assert set(room.app.state.handlers) <= set(JOBS)
    results = {}
    chosen = JOBS if selected == 'all' else (selected,)
    async with database(url) as pool:
        store, quotes = PgStore(pool), PgQuotes(pool)
        await store.apply_schema()
        async with pool.acquire() as conn:
            await ensure_schema(conn, 'rig')
        sender = SimpleNamespace(send=AsyncMock())
        service = QuoteService(store, None, sender, quotes)
        room.app.state.pool, room.app.state.rig = pool, service
        ctx = SimpleNamespace(tenant_id=TENANT, agent='rig', job_id='offline',
                              input={'heartbeat': True}, memory=SimpleNamespace(remember=AsyncMock(return_value={'seen': 1})))
        for job in chosen:
            if job == 'ping':
                result = await room.ping(ctx)
                assert result['pong'] and ctx.memory.remember.await_count == 1
            elif job == 'pull_feeds':
                await store.put_feed(TENANT, 'csv', 'https://placeholder.example/catalogue.csv', 'USD')
                body = b'sku,name,brand,category,price,image_url\ndry-product,Offline product,Placeholder,parts,1,https://placeholder.example/product.png\n'
                room.app.state.http = None
                with patch('rigbox.feed_runtime.fetch', AsyncMock(return_value=body)):
                    result = await room.pull_feeds(ctx)
                    assert result['reports'][0]['added'] == 1
                    again = await room.pull_feeds(ctx)
                    assert again['reports'][0]['updated'] == 1
                assert len(await store.receipts(TENANT)) == 2
            elif job == 'expire_searches':
                await store.add_search(TENANT, 'dry', {'id': 'old', 'query': 'old', 'host': '',
                    'signature': 'old', 'limit': 1, 'ids': [], 'exact_match': False, 'parts': [],
                    'message': None, 'created_at': datetime.now(timezone.utc) - timedelta(days=1000)})
                maintenance = SimpleNamespace(tenant_id=room.HEARTBEAT_TENANT, job_id='offline')
                result = await room.expire_searches(maintenance)
                assert result == {'deleted': 1}
                assert await room.expire_searches(maintenance) == {'deleted': 0}
            elif job == 'retry_quotes':
                await quotes.create(TENANT, {'id': 'offline-quote', 'payload': {}, 'contact': {}})
                result = await room.retry_quotes(ctx)
                assert result == {'attempted': 1} and sender.send.await_count == 1
                assert await room.retry_quotes(ctx) == {'attempted': 0}
                assert (await quotes.status(TENANT, 'offline-quote'))['status'] == 'sent'
            elif job == 'discover_quote_tenants':
                await store.put_feed(TENANT, 'csv', 'https://placeholder.example/catalogue.csv', 'USD')
                result = await room.discover_quote_tenants(ctx)
                assert result['tenants'] >= 1
                await room.discover_quote_tenants(ctx)
                rows = await pool.fetch("SELECT kind,count(*) FROM agent_rig.schedules WHERE tenant_id=$1 GROUP BY kind", UUID(TENANT))
                assert {row['kind']: row['count'] for row in rows} == {'pull_feeds': 1, 'retry_quotes': 1}
            elif job == 'cart_sweep':
                platform = SimpleNamespace(read=AsyncMock(return_value={'paid': False}), cancel=AsyncMock())
                cart = Cart(service, AsyncMock(return_value=platform))
                await cart.rows.put(TENANT, 'co_offline', {'id': 'co_offline', 'state': 'pending',
                    'expires_at': '2000-01-01T00:00:00+00:00', 'config': {}, 'remote': {}, 'lines': []})
                await cart.sweep(TENANT)
                assert (await cart.rows.get(TENANT, 'co_offline'))['state'] == 'expired'
                assert platform.cancel.await_count == 1
                result = {'expired': 1}
            elif job == 'price_events':
                page = 'https://placeholder.example/watch'
                await store.upsert_product(TENANT, {'sku': 'dry-watch', 'name': 'Offline watch',
                    'brand': 'Placeholder', 'category': 'parts', 'price': '1', 'currency': 'USD',
                    'url': page, 'active': True})
                # Feed-owned catalogues are deliberately excluded from Tiger.
                await pool.execute('UPDATE agent_rig.feeds SET watch_indexed=true')
                message = {'id': 'offline-message', 'event_id': str(uuid4()), 'facts': {
                    'watch_id': str(uuid4()), 'observation_id': str(uuid4()), 'sku': 'dry-watch',
                    'page_id': hashlib.sha256(page.encode()).hexdigest(), 'previous_price': '1',
                    'price': '2', 'currency': 'USD', 'observed_at': datetime.now(timezone.utc).isoformat()}}
                async def bus(http, tenant, operation, body):
                    assert tenant == TENANT
                    return {'messages': [message]} if operation == 'receive' else {}
                with patch.object(price_events, 'request', bus):
                    for _ in range(2):
                        assert await price_events.consume_tenant(service, None, TENANT, 'offline') == 1
                assert await pool.fetchval('SELECT count(*) FROM agent_rig.price_history') == 1
                result = {'receipts': 1}
            elif job == 'forge_retention':
                with tempfile.TemporaryDirectory(prefix='rig-dry-forge-') as folder:
                    work = Path(folder) / TENANT / str(uuid4())
                    work.mkdir(parents=True)
                    (work / 'request.json').write_text('{}')
                    (work / 'pending-receipt.json').write_text('{}')
                    (work / 'intermediate').write_bytes(b'offline')
                    sweep(Path(folder), set())
                    assert not (work / 'intermediate').exists()
                    assert (work / 'pending-receipt.json').exists()
                    assert (work / 'state.json').exists()
                result = {'retained_receipts': 1}
            elif job == 'training_events':
                async with pool.acquire() as conn:
                    for _ in range(2):
                        await training.enqueue(conn, TENANT, 'rig_no_result', 'offline-event',
                                               {'q': 'offline'}, {'results': []})
                assert await pool.fetchval("SELECT count(*) FROM agent_rig.training_events WHERE source_ref='offline-event'") == 1
                result = {'events': 1, 'model_calls': 0}
            results[job] = {'ok': True, 'result': result}
    return {'dry_run': True, 'external_calls': 0, 'jobs': results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', required=True)
    parser.add_argument('--job', choices=('all', *JOBS), default='all')
    args = parser.parse_args()
    url = os.environ.get('RIG_TEST_DATABASE_URL', '')
    if not url:
        print(json.dumps({'ok': False, 'missing_settings': ['RIG_TEST_DATABASE_URL']}))
        return 2
    try:
        local_database(url)
        with offline_network():
            result = asyncio.run(run(url, args.job))
    except Exception as error:
        # Never print database URLs, provider responses or exception messages.
        print(json.dumps({'ok': False, 'dry_run': True, 'error': type(error).__name__}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
