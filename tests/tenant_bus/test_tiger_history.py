"""Saved-page Tiger check -> real Tank -> Redis -> Rig -> founder JSON."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
import socket
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import httpx
import pytest

from chassis import events
from rigbox.price_events import consume_tenant, save_price
from rigbox.store import PgStore as RigStore
from rig_watch import publish_price_changed
from watch import DomainLimiter, PgStore as TigerStore, external_observation, run_check
from tiger_works.fixture import extract, no_paid_call, saved_page
from test_bus import A, B, EVENT, scope
from test_tiger import ROOT, _load

URL = 'https://shop.example/item'


@asynccontextmanager
async def real_tank(database, redis_url, root, tmp_path):
    async with database.acquire() as conn:
        name = await conn.fetchval('SELECT current_database()')
    parsed = urlsplit(os.environ['POOL_SCHEMA_DATABASE_URL'])
    dsn = urlunsplit(parsed._replace(path='/' + name))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    output = tmp_path / 'tank.log'
    with output.open('w+') as stream:
        env = {**os.environ, 'DATABASE_URL': dsn, 'REDIS_URL': redis_url,
               'LITELLM_URL': 'http://127.0.0.1:9', 'TANK_API_KEY': 'offline-workspace',
               'LITELLM_MASTER_KEY': 'offline-only', 'PYTHONUNBUFFERED': '1',
               'HTTP_PROXY': 'http://127.0.0.1:9', 'HTTPS_PROXY': 'http://127.0.0.1:9',
               'ALL_PROXY': 'http://127.0.0.1:9', 'NO_PROXY': '127.0.0.1,localhost'}
        for key in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'):
            env.pop(key, None)
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1',
                                    '--port', str(port)], cwd=root / 'tank', env=env, stdout=stream, stderr=stream)
        try:
            async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', trust_env=False) as http:
                for _ in range(120):
                    assert process.poll() is None, output.read_text()[-4000:]
                    try:
                        if (await http.get('/health', timeout=1)).status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    await asyncio.sleep(0.25)
                else:
                    pytest.fail('Tank startup did not finish: ' + output.read_text()[-4000:])
                assert 'Application startup complete' in output.read_text()
                lines = output.read_text().splitlines()
                start = next(i for i, line in enumerate(lines) if 'Waiting for application startup' in line)
                print('REAL TANK STARTUP TAIL\n' + '\n'.join(lines[start:]))
                yield http
        finally:
            process.terminate()
            process.wait(timeout=20)


async def consume_on_rig_startup(database, monkeypatch, bus):
    """Run the actual Rig lifespan; park unrelated scheduled work in this proof."""
    import importlib
    chassis_app = importlib.import_module('chassis.app')
    async def parked(*args, **kwargs):
        await asyncio.Future()
    monkeypatch.setattr(chassis_app, 'job_loop', parked)
    monkeypatch.setattr(chassis_app, 'schedule_loop', parked)
    monkeypatch.setenv('AGENT_NAME', 'rig')
    monkeypatch.delenv('CATALOGUE_DIR', raising=False)
    monkeypatch.delenv('RIG_RETAILER_KEY', raising=False)
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    monkeypatch.setenv('no_proxy', '127.0.0.1,localhost')
    async with database.acquire() as conn:
        name = await conn.fetchval('SELECT current_database()')
    parsed = urlsplit(os.environ['POOL_SCHEMA_DATABASE_URL'])
    monkeypatch.setenv('DATABASE_URL', urlunsplit(parsed._replace(path='/' + name)))
    room = _load('bus_rig_lifespan', ROOT / 'agents/rig/app.py')
    async with room.app.router.lifespan_context(room.app):
        tasks = [task for task in asyncio.all_tasks() if task.get_coro().__name__ == 'consume_loop']
        assert len(tasks) == 1
        async with asyncio.timeout(10):
            while True:
                async with database.acquire() as conn:
                    rows = await conn.fetchval('SELECT count(*) FROM agent_rig.price_history WHERE tenant_id=$1', UUID(A))
                if rows == 1 and (await bus.redis.xpending(scope().stream(EVENT), 'rig'))['pending'] == 0:
                    break
                await asyncio.sleep(0.05)
    assert tasks[0].done()  # Normal Rig shutdown also stops its consumer.


async def cycle(database, http, monkeypatch, bus):
    rig, tiger = RigStore(database), TigerStore(database)
    for tenant in (A, B):
        await rig.upsert_product(tenant, dict(id='real-catalogue-id', sku='item', name='Offline item', brand='Offline',
            category='test', price='10', currency='USD', url=URL, active=True))
    watch = await tiger.create_watch(dict(tenant_id=A, url=URL, label='Offline item', engine='core',
        every='1h', enabled=True, threshold='0', alert_price=False, alert_stock=False))
    async with database.acquire() as conn:
        await conn.execute('''INSERT INTO agent_tiger.rig_targets(tenant_id,sku,url,watch_id)
            VALUES($1,'item',$2,$3)''', UUID(A), URL, UUID(watch['id']))
        # Product ids need not equal SKU; history uses the stored id.
        await conn.execute("UPDATE agent_rig.products SET id='real-catalogue-id' WHERE tenant_id=$1", UUID(A))
    original = events.request
    async def through_tank(unused_http, tenant, operation, body):
        return await original(http, tenant, operation, body)
    monkeypatch.setattr(events, 'request', through_tank)
    monkeypatch.setattr(events, '_retry_after', 0)
    monkeypatch.setenv('TANK_URL', str(http.base_url).rstrip('/'))
    monkeypatch.setenv('TANK_KEY', 'offline-tiger')
    state = {'price': '120'}
    async def render(*args):
        return {'ok': True, 'html': saved_page(state['price'])}
    async def check():
        return await run_check(tiger, A, watch, 'tiger', render, extract, no_paid_call,
                               no_paid_call, DomainLimiter(0))
    first = await check()
    assert first['status'] == 'observed'
    assert await bus.redis.xlen(scope().stream(EVENT)) == 0
    state['price'] = '145'
    changed = await check()
    assert changed['status'] == 'observed'
    assert changed['alerts'] == []  # Rig's mail-disabled watches must still publish.
    assert await bus.redis.xlen(scope().stream(EVENT)) == 1
    await publish_price_changed(tiger, A, watch, first['observation'], changed['observation'])
    assert await bus.redis.xlen(scope().stream(EVENT)) == 1  # Replayed completion is deduplicated.
    await check()
    assert await bus.redis.xlen(scope().stream(EVENT)) == 1  # Unchanged reading is not a price change.
    monkeypatch.setenv('TANK_KEY', 'offline-rig')
    service = SimpleNamespace(store=rig)
    assert await consume_tenant(service, http, B, str(uuid4())) == 0
    await consume_on_rig_startup(database, monkeypatch, bus)
    assert await consume_tenant(service, http, A, str(uuid4())) == 0
    raw = (await bus.redis.xrange(scope().stream(EVENT)))[0][1]
    message = {'event_id': raw['event_id'], 'facts': json.loads(raw['facts'])}
    await save_price(service, A, message)  # Crash after INSERT, before ACK: replay is harmless.
    async with database.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_rig.price_history WHERE tenant_id=$1', UUID(A)) == 1
        assert await conn.fetchval('SELECT count(*) FROM agent_rig.price_history WHERE tenant_id=$1', UUID(B)) == 0
        assert await conn.fetchval('SELECT price FROM agent_rig.products WHERE tenant_id=$1', UUID(A)) == Decimal('10')
    auth = {'X-Tank-Key': 'offline-workspace', 'X-Tervory-User': 'offline-founder', 'X-Tervory-Tenant': A}
    path = '/v1/agents/rig/price-history'
    query = {'tenant_id': A, 'product_id': 'real-catalogue-id'}
    response = await http.get(path, params=query, headers=auth)
    assert response.status_code == 200 and response.headers['cache-control'] == 'private, no-store'
    proof = response.json()
    assert len(proof['history']) == 1 and Decimal(proof['history'][0]['price']) == 145
    assert proof['history'][0]['event_id'] == message['event_id'] and not proof['has_more']
    other = await http.get(path, params={**query, 'tenant_id': B}, headers=auth)
    assert other.json()['history'] == []
    for user in ('client-a', 'client-b'):
        denied = await http.get(path, params=query, headers={**auth, 'X-Tervory-User': user, 'X-Tervory-Admin': 'true'})
        assert denied.status_code == 403
    assert (await http.get(path, params=query, headers={**auth, 'X-Tank-Key': 'offline-rig'})).status_code == 401
    # A late delivery cannot create history after a product is removed.
    async with rig.atomic(A) as locked:
        await locked.delete_products(A, ['item'])
    await save_price(service, A, {**message, 'event_id': str(uuid4())})
    async with database.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_rig.price_history WHERE tenant_id=$1', UUID(A)) == 1
    print('OFFLINE TIGER -> TANK -> REDIS -> RIG STARTUP CONSUMER -> FOUNDER JSON\n' + json.dumps(proof, sort_keys=True))
    return proof


@pytest.mark.asyncio
async def test_saved_tiger_check_through_real_tank(corridor, database, bus, redis_url, monkeypatch, tmp_path):
    from pathlib import Path
    async with real_tank(database, redis_url, Path(__file__).resolve().parents[2], tmp_path) as http:
        await cycle(database, http, monkeypatch, bus)


@pytest.mark.asyncio
async def test_feed_completion_emits_once_after_saved_observation(database, monkeypatch):
    tiger = TigerStore(database)
    watch = await tiger.create_watch(dict(tenant_id=A, url=URL, label='Offline', engine='core', every='1h',
                                        enabled=True, threshold='0', alert_price=False, alert_stock=False))
    published = []
    async def capture(tenant, event, ref, facts):
        saved = await tiger.latest_observation(tenant, URL)
        assert saved['id'] == facts['observation_id']
        published.append((tenant, event, ref, facts))
    monkeypatch.setattr(events, 'publish', capture)
    stamp = datetime.now(timezone.utc)
    item = dict(price='10', currency='USD', quantity=5, name='Offline')
    for price in ('10', '12', '12'):
        stamp += timedelta(seconds=1)
        await external_observation(tiger, A, watch, {**item, 'price': price}, 'official_feed', {}, lambda: stamp)
    assert len(published) == 1
    assert published[0][0:2] == (A, EVENT)
    assert published[0][3]['sku'] is None
