"""apply_schema under a held lock: each statement gets a lock_timeout, retries
with backoff, then fails cleanly (logged) instead of waiting forever."""
import asyncio
import logging
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "tests"))
import rigbox.store as rig_store
from rigbox.store import PgStore


def fast(monkeypatch):
    monkeypatch.setattr(rig_store, "SCHEMA_LOCK_TIMEOUT", "200ms", raising=False)
    monkeypatch.setattr(rig_store, "SCHEMA_LOCK_ATTEMPTS", 3, raising=False)
    monkeypatch.setattr(rig_store, "SCHEMA_LOCK_BACKOFF", 0.05, raising=False)


async def held(url):
    # Another session holds ACCESS EXCLUSIVE on agent_rig.quotes, like a long
    # migration or a stuck transaction would.
    import asyncpg
    conn = await asyncpg.connect(url)
    tx = conn.transaction()
    await tx.start()
    await conn.execute("LOCK TABLE agent_rig.quotes IN ACCESS EXCLUSIVE MODE")
    return conn, tx


@pytest.mark.asyncio
@pytest.mark.parametrize("released", [False, True])
async def test_apply_schema_times_out_retries_and_fails_cleanly_under_a_held_lock(monkeypatch, caplog, released):
    import asyncpg
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    admin = _admin_url()
    name = "rig_schemalock_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        url = _database_url(admin, name)
        pool = await asyncpg.create_pool(url)
        try:
            store = PgStore(pool)
            await store.apply_schema()
            fast(monkeypatch)
            holder, tx = await held(url)
            release = None
            try:
                if released:
                    async def let_go():
                        await asyncio.sleep(0.3)  # after the first timeout, before the attempts run out
                        await tx.rollback()
                    release = asyncio.create_task(let_go())
                started = time.monotonic()
                with caplog.at_level(logging.WARNING, logger="agent"):
                    if released:
                        await asyncio.wait_for(store.apply_schema(), 15)
                    else:
                        with pytest.raises(asyncpg.exceptions.LockNotAvailableError):
                            await asyncio.wait_for(store.apply_schema(), 15)
                elapsed = time.monotonic() - started
            finally:
                if release is not None:
                    await release
                else:
                    await tx.rollback()
                await holder.close()
            retries = [r for r in caplog.records if r.levelno == logging.WARNING and "lock timeout, retry" in r.getMessage()]
            exhausted = [r for r in caplog.records if r.levelno == logging.ERROR and "lock not acquired" in r.getMessage()]
            if released:
                assert retries and not exhausted
            else:
                assert len(retries) == 2 and len(exhausted) == 1  # 3 attempts, then a clean failure
                assert elapsed < 10
            async with pool.acquire() as conn:
                assert await conn.fetchval("SHOW lock_timeout") == "0"  # SET LOCAL never leaks to the session
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)
