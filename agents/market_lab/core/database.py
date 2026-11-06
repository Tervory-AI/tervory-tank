"""Bound connection setup, statements and locks without exposing URL values."""
import asyncio
import asyncpg
from chassis.tenant_db import _tenant


async def connect(url):
    conn = await asyncio.wait_for(asyncpg.connect(url), timeout=10)
    try:
        await asyncio.wait_for(conn.execute("SET statement_timeout='30s'; SET lock_timeout='10s'"), timeout=10)
        if _tenant.get() is not None:
            await asyncio.wait_for(conn.execute("SELECT set_config('app.tenant_id', $1, false)", _tenant.get()), timeout=10)
    except BaseException:
        await conn.close()
        raise
    return conn
