"""Scheduled checks retain attempts and enqueue once; external services are fake."""
import asyncio
import os
from datetime import timedelta
from unittest.mock import AsyncMock
from urllib.parse import urlsplit
from uuid import uuid4

import asyncpg
import httpx
import pytest

from test_tiger import NOW, TENANT_A, TENANT_B, _watch
from watch import BadWatch, DomainLimiter, MemoryStore, PgStore, check_threshold, dispatch_tenant, ensure_tables, run_check
from chassis.db import ensure_schema


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [httpx.ReadTimeout('placeholder private detail'), TimeoutError(), None])
async def test_failed_browser_attempt_is_saved_and_respects_interval(failure):
    store = MemoryStore()
    watch = await store.create_watch(_watch())
    render = AsyncMock(side_effect=failure) if failure else AsyncMock(return_value=None)
    forbidden = AsyncMock(side_effect=AssertionError('no extraction or paid fallback'))
    result = await run_check(store, TENANT_A, watch, 'tiger', render, forbidden, forbidden,
                             forbidden, DomainLimiter(0), now=lambda: NOW)
    assert result['status'] == 'error' and result['alerts'] == []
    assert result['observation']['price'] is None
    assert result['observation']['evidence'] == 'unread'
    assert await store.latest_observation(TENANT_B, watch['url']) is None
    assert (await dispatch_tenant(store, TENANT_A, NOW + timedelta(minutes=59)))['queued'] == []
    assert (await dispatch_tenant(store, TENANT_A, NOW + timedelta(hours=1)))['queued'] == [watch['url']]


@pytest.mark.asyncio
async def test_cancellation_still_reaches_job_worker():
    store = MemoryStore()
    watch = await store.create_watch(_watch())
    render = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await run_check(store, TENANT_A, watch, 'tiger', render, None, None, None, DomainLimiter(0))
    assert store.observations == []


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity'])
def test_threshold_requires_finite_amount(value):
    with pytest.raises(BadWatch):
        check_threshold(value)


@pytest.mark.asyncio
async def test_parallel_dispatch_and_rig_queue_share_one_job_per_tenant():
    dsn = os.environ['POOL_SCHEMA_DATABASE_URL']
    assert urlsplit(dsn).hostname in {'127.0.0.1', 'localhost', '::1'}
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=8)
    name = 'finish_' + uuid4().hex
    schema = 'agent_' + name
    try:
        async with pool.acquire() as conn:
            await ensure_schema(conn, name)
            await ensure_tables(conn, schema)
            assert await conn.fetchval("SELECT to_regclass($1)", schema + ".matches") is not None
            assert await conn.fetchval("SELECT to_regclass($1)", schema + ".memory_records") is not None
        store = PgStore(pool, schema)
        a = await store.create_watch(_watch())
        b = await store.create_watch(_watch(TENANT_B))
        results = await asyncio.gather(*(store.enqueue_check(TENANT_A, a['url']) for _ in range(16)),
                                       dispatch_tenant(store, TENANT_A, NOW))
        assert sum(value is True for value in results) + len(results[-1]['queued']) == 1
        assert await store.enqueue_check(TENANT_B, b['url'])
        async with pool.acquire() as conn:
            assert await conn.fetchval(f'SELECT count(*) FROM {schema}.jobs') == 2
            await conn.execute(f"UPDATE {schema}.jobs SET status='done'")
        await store.update_watch(TENANT_A, a['id'], {'enabled': False})
        assert not await store.enqueue_check(TENANT_A, a['url'])
        assert not await store.enqueue_check(TENANT_A, 'https://placeholder.example/missing')
        assert await store.enqueue_check(TENANT_B, b['url'])
    finally:
        async with pool.acquire() as conn:
            await conn.execute(f'DROP SCHEMA {schema} CASCADE')
        await pool.close()
