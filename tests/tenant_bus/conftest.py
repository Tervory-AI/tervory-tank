"""Disposable local stores only; no production connections or model services."""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

ROOT = Path(__file__).resolve().parents[2]
for path in ('', 'tank', 'agents/_chassis', 'agents/rig', 'agents/tiger', 'tests'):
    sys.path.insert(0, str(ROOT / path))
os.environ.setdefault('DATABASE_URL', 'postgresql://localhost/offline')
os.environ.setdefault('LITELLM_MASTER_KEY', 'offline-only')
os.environ.setdefault('TANK_API_KEY', 'offline-workspace')

import event_bus  # noqa: E402
import main  # noqa: E402
from chassis.db import ensure_schema  # noqa: E402
from rigbox.store import PgStore  # noqa: E402
from watch import ensure_tables  # noqa: E402

A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'


@pytest.fixture(scope='session')
def redis_url():
    url = os.environ.get('TENANT_BUS_REDIS_URL')
    if url:
        assert urlsplit(url).hostname in {'localhost', '127.0.0.1', '::1'}
        yield url  # Dedicated test Redis; its selected database is cleared below.
        return
    name = 'tenant-bus-test-' + uuid4().hex
    docker = ['docker', '--host=unix:///var/run/docker.sock']
    env = {k: v for k, v in os.environ.items() if k not in {
        'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'}}
    subprocess.run([*docker, 'run', '-d', '--rm', '--name', name, '-p', '127.0.0.1::6379',
                    'redis:7.4.12'], check=True, capture_output=True, env=env)
    try:
        port = subprocess.check_output([*docker, 'port', name, '6379'], text=True, env=env).strip().rsplit(':', 1)[1]
        yield 'redis://127.0.0.1:' + port + '/0'
    finally:
        subprocess.run([*docker, 'rm', '-f', name], check=True, capture_output=True, env=env)


@pytest_asyncio.fixture
async def bus(redis_url):
    client = Redis.from_url(redis_url, decode_responses=True)
    deadline = time.monotonic() + 10
    while True:
        try:
            await client.ping()
            break
        except ConnectionError:
            if time.monotonic() >= deadline:
                raise
            await asyncio.sleep(0.1)
    await client.flushdb()
    try:
        yield event_bus.Bus(client, maxlen=3, retry_ms=0)
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def database():
    url = os.environ.get('POOL_SCHEMA_DATABASE_URL')
    if not url:
        pytest.skip('Set POOL_SCHEMA_DATABASE_URL to a disposable local Postgres')
    parsed = urlsplit(url)
    assert parsed.hostname in {'localhost', '127.0.0.1', '::1'}
    name = 'tenant_bus_' + uuid4().hex
    admin = await asyncpg.connect(url)
    await admin.execute('CREATE DATABASE ' + name)
    pool = None
    try:
        pool = await asyncpg.create_pool(urlunsplit(parsed._replace(path='/' + name)), min_size=1, max_size=5)
        async with pool.acquire() as conn:
            await conn.execute((ROOT / 'tank/schema.sql').read_text())
            await ensure_schema(conn, 'tiger')
            await ensure_tables(conn, 'agent_tiger')
        store = PgStore(pool)
        await store.apply_schema()
        await store.apply_schema()  # Existing helper, additive/idempotent startup.
        yield pool
    finally:
        if pool:
            await pool.close()
        await admin.execute('DROP DATABASE ' + name)
        await admin.close()


@pytest_asyncio.fixture
async def corridor(bus, database, monkeypatch):
    for key in list(os.environ):
        if key.startswith('TANK_KEY_'):
            monkeypatch.delenv(key)
    for agent in {*event_bus.EVENTS.values(), 'rig'}:
        monkeypatch.setenv('TANK_KEY_' + agent.upper(), 'offline-' + agent)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'offline-founder')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setenv('TANK_URL', 'http://tank')
    monkeypatch.setattr(main, '_pool', database)
    monkeypatch.setattr(main, 'TANK_API_KEY', 'offline-workspace')
    monkeypatch.setattr(main, '_agent_keys_synced', True)
    monkeypatch.setattr(event_bus, 'bus', lambda: bus)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://tank') as http:
        yield http
