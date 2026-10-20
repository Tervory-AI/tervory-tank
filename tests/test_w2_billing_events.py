"""Stripe event claims in Tank. Schema checks use a throwaway local database only."""

from __future__ import annotations

import hashlib
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import asyncpg  # noqa: E402
import httpx  # noqa: E402

import main  # noqa: E402
from chassis.roles import statements_for  # noqa: E402
from test_zenas_schema_apply import _guarded_ownership  # noqa: E402

SCHEMA_PATH = ROOT / "tank" / "schema.sql"
# tank/schema.sql on origin/main when this table was appended. The bytes before
# the billing_events appendix must stay that file.
MAIN_SCHEMA_SHA256 = "915b2d1ca01ff41c81fb92981e6fe0fe7f4d16d9d6f448a38c190317f6c88c94"
APPENDIX = "\n-- Workspace billing webhook. One row per Stripe event id.\n"
AGENTS = ("base", "tiger", "market_lab", "zenas", "rig", "radix", "tisan")
AGENT_KEY = "agent-key-billing-fixture"
EVENT_ID = "evt_fixture"


def _local_database_url() -> str:
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL", "").strip()
    if not url:
        if os.environ.get("GITHUB_ACTIONS"):
            pytest.fail("POOL_SCHEMA_DATABASE_URL is not set")
        pytest.skip("POOL_SCHEMA_DATABASE_URL is not set")
    host = (urlparse(url).hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("schema tests only run against a local throwaway database")
    return url


def _schemas() -> tuple[str, str]:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    index = sql.find(APPENDIX)
    assert index > 0, "billing_events must be appended to tank/schema.sql"
    main_sql = sql[:index]
    assert hashlib.sha256(main_sql.encode()).hexdigest() == MAIN_SCHEMA_SHA256
    assert "billing_events" not in main_sql
    assert "CREATE TABLE IF NOT EXISTS tank.billing_events" in sql[index:]
    assert "ON CONFLICT" not in sql[index:]
    return main_sql, sql


async def _apply_roles(conn, password: str) -> None:
    for agent in AGENTS:
        for statement in statements_for(agent, password):
            if "ALTER SEQUENCE" in statement:
                statement = _guarded_ownership(f"agent_{agent}")
            try:
                await conn.execute(statement)
            except Exception:
                redacted = statement.replace(password, "redacted")
                raise RuntimeError(f"agent role statement failed for {agent}: {redacted[:180]}") from None


async def _assert_table(conn) -> None:
    rows = await conn.fetch(
        """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'tank' AND table_name = 'billing_events'
        ORDER BY ordinal_position
        """
    )
    assert [row["column_name"] for row in rows] == ["event_id", "type", "received_at", "handled"]
    by_name = {row["column_name"]: row for row in rows}
    assert by_name["event_id"]["data_type"] == "text"
    assert by_name["event_id"]["is_nullable"] == "NO"
    assert by_name["event_id"]["column_default"] is None
    assert by_name["type"]["data_type"] == "text"
    assert by_name["type"]["is_nullable"] == "YES"
    assert by_name["type"]["column_default"] is None
    assert by_name["received_at"]["data_type"] == "timestamp with time zone"
    assert by_name["received_at"]["is_nullable"] == "YES"
    assert by_name["received_at"]["column_default"] is None
    assert by_name["handled"]["data_type"] == "boolean"
    assert by_name["handled"]["is_nullable"] == "YES"
    assert by_name["handled"]["column_default"] == "false"
    primary = await conn.fetchval(
        """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
        WHERE i.indrelid = 'tank.billing_events'::regclass AND i.indisprimary
        """
    )
    assert primary == "event_id"


async def _remember_row(conn) -> None:
    await conn.execute(
        """
        INSERT INTO tank.billing_events (event_id, type, received_at)
        VALUES ($1, 'plan.created', now())
        """,
        EVENT_ID,
    )


async def _assert_row_survived(conn) -> None:
    row = await conn.fetchrow(
        """
        SELECT type, handled, received_at IS NOT NULL AS received
        FROM tank.billing_events
        WHERE event_id = $1
        """,
        EVENT_ID,
    )
    assert row is not None
    assert row["type"] == "plan.created"
    assert row["handled"] is False
    assert row["received"] is True


class _Throwaway:
    """A database created for this test and dropped afterwards. Never the caller's database."""

    def __init__(self) -> None:
        self.url = _local_database_url()
        self.admin = None
        self.names: list[str] = []

    async def __aenter__(self) -> _Throwaway:
        self.admin = await asyncpg.connect(self.url)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self.admin is None:
            return
        for name in self.names:
            await self.admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await self.admin.close()

    async def connect(self):
        name = "w2bill_" + uuid.uuid4().hex
        await self.admin.execute(f'CREATE DATABASE "{name}"')
        self.names.append(name)
        return await asyncpg.connect(self.url, database=name)


@pytest.mark.asyncio
async def test_billing_events_on_an_empty_database_and_reapplied() -> None:
    _main_sql, full = _schemas()
    async with _Throwaway() as dbs:
        conn = await dbs.connect()
        try:
            assert await conn.fetchval("SELECT to_regclass('tank.billing_events')") is None
            await conn.execute(full)
            await _assert_table(conn)
            await _remember_row(conn)
            await conn.execute(full)
            await _assert_table(conn)
            await _assert_row_survived(conn)
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_billing_events_on_current_main_schema_with_agent_roles() -> None:
    main_sql, full = _schemas()
    password = "billing-schema-placeholder"
    async with _Throwaway() as dbs:
        conn = await dbs.connect()
        try:
            await conn.execute(main_sql)
            assert await conn.fetchval("SELECT to_regclass('tank.ledger')") is not None
            assert await conn.fetchval("SELECT to_regclass('tank.billing_events')") is None
            await _apply_roles(conn, password)
            await conn.execute(full)
            await _assert_table(conn)
            await _apply_roles(conn, password)
            await _remember_row(conn)
            await conn.execute(full)
            await _assert_table(conn)
            await _assert_row_survived(conn)
            for agent in AGENTS:
                role = f"agent_{agent}"
                assert not await conn.fetchval(
                    "SELECT has_table_privilege($1, 'tank.billing_events', 'SELECT')",
                    role,
                )
                assert not await conn.fetchval(
                    "SELECT has_table_privilege($1, 'tank.billing_events', 'INSERT')",
                    role,
                )
            await conn.execute("SET ROLE agent_tiger")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetchval("SELECT count(*) FROM tank.billing_events")
            await conn.execute("RESET ROLE")
            await _assert_row_survived(conn)
        finally:
            await conn.close()


def _routes() -> dict[str, object]:
    found: dict[str, object] = {}
    for route in main.app.routes:
        path = getattr(route, "path", "")
        if path in {"/v1/billing/events/claim", "/v1/billing/events/release"}:
            found[path] = route
    return found


@pytest.mark.asyncio
async def test_agent_key_is_refused_on_both_billing_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    routes = _routes()
    assert set(routes) == {"/v1/billing/events/claim", "/v1/billing/events/release"}
    for route in routes.values():
        names = [getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies]
        assert "require_key" in names
        assert "POST" in route.methods

    monkeypatch.setattr(main, "_pool", None)
    monkeypatch.setattr(main, "_agent_keys_synced", False)
    monkeypatch.setenv("TANK_KEY_TIGER", AGENT_KEY)
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://tank") as client:
        for path in ("/v1/billing/events/claim", "/v1/billing/events/release"):
            body = {"event_id": EVENT_ID, "type": "plan.created"}
            refused = await client.post(path, headers={"x-tank-key": AGENT_KEY}, json=body)
            assert refused.status_code == 403
            assert refused.json()["detail"] == "This agent key cannot call that."
            assert AGENT_KEY not in refused.text
            missing = await client.post(path, json=body)
            assert missing.status_code == 401
            blank = await client.post(
                path,
                headers={"x-tank-key": main.TANK_API_KEY},
                json={"event_id": "  ", "type": "plan.created"},
            )
            assert blank.status_code == 400
            assert "postgres" not in blank.text.lower()


@pytest.mark.asyncio
async def test_claim_is_first_once_and_release_deletes_an_unhandled_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    _main_sql, full = _schemas()
    async with _Throwaway() as dbs:
        conn = await dbs.connect()
        try:
            await conn.execute(full)
        finally:
            await conn.close()
        pool = await asyncpg.create_pool(dbs.url, database=dbs.names[-1], min_size=1, max_size=2)
        monkeypatch.setattr(main, "_pool", pool)
        monkeypatch.setattr(main, "_agent_keys_synced", False)
        monkeypatch.setenv("TANK_KEY_TIGER", AGENT_KEY)
        try:
            transport = httpx.ASGITransport(app=main.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://tank") as client:
                headers = {"x-tank-key": main.TANK_API_KEY}
                agent_headers = {"x-tank-key": AGENT_KEY}
                for path in ("/v1/billing/events/claim", "/v1/billing/events/release"):
                    refused = await client.post(
                        path,
                        headers=agent_headers,
                        json={"event_id": "evt_agent_fixture", "type": "plan.created"},
                    )
                    assert refused.status_code == 403
                    assert AGENT_KEY not in refused.text
                async with pool.acquire() as check:
                    assert await check.fetchval("SELECT count(*) FROM tank.billing_events") == 0

                first = await client.post(
                    "/v1/billing/events/claim",
                    headers=headers,
                    json={"event_id": EVENT_ID, "type": "plan.created"},
                )
                assert first.status_code == 200
                assert first.json() == {"first": True}
                assert main.TANK_API_KEY not in first.text
                second = await client.post(
                    "/v1/billing/events/claim",
                    headers=headers,
                    json={"event_id": EVENT_ID, "type": "plan.updated"},
                )
                assert second.status_code == 200
                assert second.json() == {"first": False}
                async with pool.acquire() as check:
                    row = await check.fetchrow(
                        "SELECT type, handled, received_at IS NOT NULL AS received FROM tank.billing_events WHERE event_id = $1",
                        EVENT_ID,
                    )
                    assert row["type"] == "plan.created"
                    assert row["handled"] is False
                    assert row["received"] is True
                released = await client.post(
                    "/v1/billing/events/release",
                    headers=headers,
                    json={"event_id": EVENT_ID},
                )
                assert released.status_code == 200
                assert released.json() == {"released": True}
                retried = await client.post(
                    "/v1/billing/events/claim",
                    headers=headers,
                    json={"event_id": EVENT_ID, "type": "plan.created"},
                )
                assert retried.json() == {"first": True}
                async with pool.acquire() as check:
                    await check.execute(
                        "UPDATE tank.billing_events SET handled = true WHERE event_id = $1",
                        EVENT_ID,
                    )
                kept = await client.post(
                    "/v1/billing/events/release",
                    headers=headers,
                    json={"event_id": EVENT_ID},
                )
                assert kept.status_code == 200
                assert kept.json() == {"released": False}
                still = await client.post(
                    "/v1/billing/events/claim",
                    headers=headers,
                    json={"event_id": EVENT_ID, "type": "plan.created"},
                )
                assert still.json() == {"first": False}
                async with pool.acquire() as check:
                    assert await check.fetchval(
                        "SELECT handled FROM tank.billing_events WHERE event_id = $1",
                        EVENT_ID,
                    ) is True
        finally:
            await pool.close()
