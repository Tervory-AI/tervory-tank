"""Real Postgres migration and durable trial checks; no provider calls."""

import json
import os
import sys
import uuid
from pathlib import Path

import httpx
import pytest

from test_zenas_schema_apply import _apply_roles

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/base"))

from sources.trial import run_trial  # noqa: E402
from sources.vendor_ledger import SCHEMA, TankVendorLedger, flush_pending  # noqa: E402


@pytest.mark.asyncio
@pytest.mark.parametrize("upgrade", [False, True])
async def test_schema_and_durable_trial(monkeypatch, upgrade):
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url:
        pytest.skip("POOL_SCHEMA_DATABASE_URL is not set")
    import asyncpg

    admin = await asyncpg.connect(url)
    database = "context_test_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{database}"')
    conn = await asyncpg.connect(url, database=database)
    base_pool = None
    try:
        schema = (ROOT / "tank/schema.sql").read_text()
        additions = [
            line for line in schema.splitlines()
            if "ALTER TABLE tank.ledger ADD COLUMN IF NOT EXISTS" in line
            and (" vendor " in line or " units " in line)
        ]
        assert len(additions) == 2
        before = schema
        for line in additions:
            before = before.replace(line + "\n", "")
        legacy = uuid.uuid4()
        tenant, run = uuid.uuid4(), uuid.uuid4()
        if upgrade:
            await conn.execute(before)
            for agent in ("base", "tiger", "market_lab", "rig", "tisan", "radix", "zenas"):
                await _apply_roles(conn, agent)
            await conn.execute(
                "INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model) VALUES($1,$2,'base','old','code')",
                legacy, tenant,
            )
            original = dict(await conn.fetchrow("SELECT * FROM tank.ledger WHERE id=$1", legacy))
        await conn.execute(schema)
        await conn.execute(schema)
        columns = await conn.fetch(
            "SELECT column_name,data_type,is_nullable FROM information_schema.columns "
            "WHERE table_schema='tank' AND table_name='ledger' AND column_name IN ('vendor','units')"
        )
        assert {tuple(row.values()) for row in columns} == {
            ("vendor", "text", "YES"), ("units", "numeric", "YES"),
        }
        if upgrade:
            kept = dict(await conn.fetchrow("SELECT * FROM tank.ledger WHERE id=$1", legacy))
            assert kept.pop("vendor") is None
            assert kept.pop("units") is None
            assert kept == original
        await conn.execute(
            "INSERT INTO tank.ledger(tenant_id,agent,task_type,model) VALUES($1,'base','old','code')", tenant,
        )
        assert await conn.fetchval(
            "SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND (vendor IS NOT NULL OR units IS NOT NULL)", tenant,
        ) == 0
        await _apply_roles(conn, "base")
        await conn.execute("SET ROLE agent_base")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("INSERT INTO tank.ledger(tenant_id) VALUES($1)", tenant)
        await conn.execute(SCHEMA)
        await conn.execute(SCHEMA)
        await conn.execute("RESET ROLE")
        base_pool = await asyncpg.create_pool(
            url, database=database, min_size=1, max_size=3, server_settings={"role": "agent_base"},
        )
        await conn.execute(
            "INSERT INTO agent_base.tasks(id,tenant_id,title,status) VALUES($1,$2,'trial','done')", run, tenant,
        )
        ids = [uuid.uuid4() for _ in range(3)]
        for record in ids:
            await conn.execute(
                "INSERT INTO agent_base.records(id,tenant_id,task_id,raw,profile,status) "
                "VALUES($1,$2,$3,'{}','{\"name\":\"Base answer\"}','done')", record, tenant, run,
            )
        monkeypatch.setenv("CONTEXT_DEV_API_KEY", "test-placeholder")
        monkeypatch.setenv("CONTEXT_DEV_MAX_CREDITS", "20")
        monkeypatch.setenv("TANK_REGION", "us-east")
        monkeypatch.setenv("TANK_KEY", "base-placeholder")
        monkeypatch.setenv("TANK_URL", "http://tank.test")
        calls, posted = [], []
        unavailable = True

        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setenv("LITELLM_MASTER_KEY", "test-placeholder")
        monkeypatch.setenv("TANK_API_KEY", "workspace-placeholder")
        import main as tank

        async def transport(request):
            if request.url.host == "tank.test":
                body = json.loads(request.content)
                if unavailable:
                    return httpx.Response(503)
                response = await tank.vendor_ledger(tank.VendorCall(**body), agent="base")
                posted.append(body)
                return httpx.Response(200, json=response)
            assert await conn.fetchval(
                "SELECT count(*) FROM agent_base.context_dev_calls WHERE tenant_id=$1 AND run_id=$2 AND result IS NULL",
                tenant, run,
            ) == 1
            calls.append(json.loads(request.content))
            return httpx.Response(
                200, headers={"X-Credits-Used": "10"},
                json=json.loads((ROOT / "tests/fixtures/context-dev/brand-documented.json").read_text()),
            )

        tank_pool = await asyncpg.create_pool(url, database=database, min_size=1, max_size=2)
        monkeypatch.setattr(tank, "pool", lambda: tank_pool)
        selected = [{"record_id": str(record), "domain": "stripe.com"} for record in ids]
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            try:
                with pytest.raises(ValueError):
                    await run_trial(base_pool, http, str(uuid.uuid4()), str(run), selected)
                assert calls == []
                with pytest.raises(RuntimeError, match="ledger unavailable"):
                    await run_trial(base_pool, http, str(tenant), str(run), selected[:1])
                assert len(calls) == 1
                unavailable = False
                await flush_pending(base_pool, http)
                answer = await run_trial(base_pool, http, str(tenant), str(run), selected)
                assert len(calls) == 2
                assert answer["results"][2]["status"] == "credit_limit"
                await run_trial(base_pool, http, str(tenant), str(run), selected)
                assert len(calls) == 2
                assert len(posted) == 2
                duplicate = await tank.vendor_ledger(tank.VendorCall(**posted[0]), agent="base")
                assert duplicate["recorded"] is True
                assert await conn.fetchval(
                    "SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND vendor='context.dev'",
                    tank.PLATFORM_TENANT,
                ) == 2
                profile = await conn.fetchval(
                    "SELECT profile FROM agent_base.records WHERE tenant_id=$1 AND id=$2", tenant, ids[0],
                )
                assert json.loads(profile) == {"name": "Base answer"}
                candidate = await conn.fetchval(
                    "SELECT passes->'context_dev' FROM agent_base.records WHERE tenant_id=$1 AND id=$2", tenant, ids[0],
                )
                assert json.loads(candidate)["credits"] == 10
                other_run = uuid.uuid4()
                await conn.execute(
                    "INSERT INTO agent_base.tasks(id,tenant_id,title,status) VALUES($1,$2,'crash','done')",
                    other_run, tenant,
                )
                await conn.execute(
                    "UPDATE agent_base.records SET task_id=$3 WHERE tenant_id=$1 AND id=$2",
                    tenant, ids[2], other_run,
                )
                async with base_pool.acquire() as base:
                    await TankVendorLedger(base, http, tenant_id=str(tenant), run_id=str(other_run)).reserve(
                        {"call_id": str(uuid.uuid4()), "record_id": str(ids[2]), "reserved_credits": 10}, 20,
                    )
                await flush_pending(base_pool, http)
                recovered = await run_trial(base_pool, http, str(tenant), str(other_run), selected[2:])
                assert recovered["results"][0]["status"] == "unknown"
                assert posted[-1]["units"] is None
                assert posted[-1]["outcome"] == "unverified"
                assert len(calls) == 2
            finally:
                await tank_pool.close()
    finally:
        if base_pool:
            await base_pool.close()
        await conn.close()
        await admin.execute(f'DROP DATABASE "{database}"')
        await admin.close()
