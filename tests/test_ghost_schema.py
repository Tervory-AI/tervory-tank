"""CI uses its temporary Postgres: apply to empty database, reapply, retain state."""
import os
import uuid
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_ghost_schema_empty_and_reapply():
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url:
        pytest.skip("POOL_SCHEMA_DATABASE_URL is not set")
    import asyncpg
    admin = await asyncpg.connect(url)
    name = "ghost_test_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    conn = await asyncpg.connect(url, database=name)
    try:
        schema = (Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text()
        await conn.execute(schema)
        identity, tenant = uuid.uuid4(), uuid.uuid4()
        await conn.execute("INSERT INTO tank.ghost_recovery(tenant_id,id,action,target,status) VALUES($1,$2,'restart_crashed_room','base','uncertain')", tenant, identity)
        await conn.execute(schema)
        assert await conn.fetchval("SELECT status FROM tank.ghost_recovery WHERE tenant_id=$1 AND id=$2", tenant, identity) == "uncertain"
        assert await conn.fetchval("SELECT status FROM tank.ghost_recovery WHERE tenant_id=$1 AND id=$2", uuid.uuid4(), identity) is None
    finally:
        await conn.close()
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()
