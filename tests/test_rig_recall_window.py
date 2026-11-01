"""Saved searches are read and kept only inside a recent window.

The live lookup filters in SQL: newest first, at most 500, one retailer.
The nightly clean-up deletes older rows from that table only.
"""

from __future__ import annotations

from rig_fixture_loader import load_catalogue

import asyncio
import importlib.util
import inspect
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.recall import recall_days  # noqa: E402
from rigbox.service import Service  # noqa: E402
from rigbox.store import MemoryStore, PgStore  # noqa: E402

CATALOGUES = ROOT / "tests" / "fixtures" / "rig_catalogues"
CN = "33333333-3333-4333-8333-333333333333"
EXAMPLE = "11111111-1111-4111-8111-111111111111"
VERSION = "window-v1"


class Models:
    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, task_type, messages
        return ""


def _when(days: int = 0, seconds: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days, seconds=seconds)


def _saved(name: str, when: datetime) -> dict:
    return {
        "id": name,
        "query": name,
        "host": "",
        "signature": name,
        "limit": 12,
        "ids": [name],
        "exact_match": True,
        "message": None,
        "parts": [{"part": name, "ids": [name], "exact_match": True, "message": None, "limit": 12}],
        "created_at": when,
    }


def test_the_window_defaults_to_90_days_and_can_be_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RIG_SEARCH_RECALL_DAYS", raising=False)
    assert recall_days() == 90
    monkeypatch.setenv("RIG_SEARCH_RECALL_DAYS", "14")
    assert recall_days() == 14
    monkeypatch.setenv("RIG_SEARCH_RECALL_DAYS", "nope")
    assert recall_days() == 90


def test_the_lookup_query_filters_orders_and_caps() -> None:
    source = inspect.getsource(PgStore.searches_for)
    assert "tenant_id = $1" in source
    assert "created_at >= now()" in source
    assert "ORDER BY created_at DESC" in source
    assert "LIMIT 500" in source
    delete = inspect.getsource(PgStore.expire_searches)
    assert "DELETE FROM agent_rig.searches" in delete
    assert "products" not in delete.lower()


@pytest.mark.asyncio
async def test_the_window_excludes_old_rows_and_returns_newest_first() -> None:
    store = MemoryStore()
    await store.add_search(CN, VERSION, _saved("older", _when(10)))
    await store.add_search(CN, VERSION, _saved("newer", _when(1)))
    await store.add_search(CN, VERSION, _saved("ancient", _when(120)))
    await store.add_search(EXAMPLE, VERSION, _saved("other-retailer", _when(1)))
    rows = await store.searches_for(CN, VERSION, 90)
    assert [row["query"] for row in rows] == ["newer", "older"]
    wider = await store.searches_for(CN, VERSION, 200)
    assert [row["query"] for row in wider] == ["newer", "older", "ancient"]


@pytest.mark.asyncio
async def test_the_read_stops_at_500() -> None:
    store = MemoryStore()
    now = datetime.now(timezone.utc)
    for index in range(501):
        await store.add_search(CN, VERSION, _saved(f"row-{index:04d}", now - timedelta(seconds=index)))
    rows = await store.searches_for(CN, VERSION, 90)
    assert len(rows) == 500
    assert rows[0]["query"] == "row-0000"
    assert rows[-1]["query"] == "row-0499"
    assert all(row["query"] != "row-0500" for row in rows)


@pytest.mark.asyncio
async def test_a_search_uses_the_configured_window(monkeypatch: pytest.MonkeyPatch) -> None:
    import rigbox.service as service_mod

    calls: list[str] = []
    original = service_mod.rank_room

    def tracking(payload: dict) -> dict:
        calls.append(str(payload["q"]))
        return original(payload)

    monkeypatch.setattr(service_mod, "rank_room", tracking)
    monkeypatch.setenv("RIG_SEARCH_RECALL_DAYS", "30")
    service = Service(MemoryStore(), Models())
    report = await load_catalogue(service, CATALOGUES / "customnation")
    assert report["products"]["rejected"] == []
    await service.search(CN, "optic for lumaworks", 12)
    service.store.searches[0]["created_at"] = _when(40)
    calls.clear()
    await service.search(CN, "optic for lumaworks", 12)
    assert calls == ["optic for lumaworks"]
    service.store.searches = [service.store.searches[0]]
    monkeypatch.setenv("RIG_SEARCH_RECALL_DAYS", "90")
    calls.clear()
    again = await service.search(CN, "optic for lumaworks", 12)
    assert calls == []
    assert again["parts"][0]["reused"] is True


@pytest.mark.asyncio
async def test_cleanup_deletes_only_old_rows_for_every_retailer() -> None:
    store = MemoryStore()
    await store.add_search(CN, VERSION, _saved("cn-old", _when(100)))
    await store.add_search(CN, VERSION, _saved("cn-new", _when(2)))
    await store.add_search(EXAMPLE, VERSION, _saved("ex-old", _when(100)))
    await store.add_search(EXAMPLE, VERSION, _saved("ex-new", _when(2)))
    store._products[(CN, "STI-P-9")] = {"sku": "STI-P-9", "tenant_id": CN}
    deleted = await store.expire_searches(90)
    assert deleted == 2
    left = {(row["tenant_id"], row["query"]) for row in store.searches}
    assert left == {(CN, "cn-new"), (EXAMPLE, "ex-new")}
    assert (CN, "STI-P-9") in store._products
    assert await store.expire_searches(90) == 0


def _load_rig_app():
    rig = str(ROOT / "agents" / "rig")
    chassis = str(ROOT / "agents" / "_chassis")
    for path in (chassis, rig):
        if path not in sys.path:
            sys.path.insert(0, path)
    spec = importlib.util.spec_from_file_location("rig_window_app", ROOT / "agents" / "rig" / "app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rig_window_app"] = module
    spec.loader.exec_module(module)
    return module


def test_the_nightly_job_logs_how_many_rows_it_deleted(capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_rig_app()
    nightly = [item for item in module.app.state.schedules if item["kind"] == "expire_searches"]
    assert len(nightly) == 1
    assert nightly[0]["cron"] == "0 3 * * *"

    class Stub:
        async def expire_searches(self) -> int:
            return 4

    module.app.state.rig = Stub()
    ctx = SimpleNamespace(tenant_id="00000000-0000-0000-0000-000000000001", job_id="job-1")
    result = asyncio.run(module.expire_searches(ctx))
    assert result == {"deleted": 4}
    line = capsys.readouterr().out.strip().splitlines()[-1]
    logged = json.loads(line)
    assert json.loads(logged["msg"]) == {"deleted": 4}


def _admin_url() -> str:
    for name in ("RIG_TEST_DATABASE_URL", "POOL_SCHEMA_DATABASE_URL"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    if os.environ.get("GITHUB_ACTIONS"):
        pytest.fail("POOL_SCHEMA_DATABASE_URL is not set")
    pytest.skip("POOL_SCHEMA_DATABASE_URL is not set")
    return ""


def _database_url(admin: str, name: str) -> str:
    parts = urlsplit(admin)
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, "", ""))


async def _create_database(admin: str, name: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(admin)
    try:
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


async def _drop_database(admin: str, name: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(admin)
    try:
        await conn.fetch(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid()
            """,
            name,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
    finally:
        await conn.close()


def test_postgres_window_order_cap_and_cleanup() -> None:
    admin = _admin_url()
    name = "rig_window_" + uuid4().hex[:12]
    url = _database_url(admin, name)
    asyncio.run(_create_database(admin, name))
    try:
        asyncio.run(_postgres_cases(url))
    finally:
        asyncio.run(_drop_database(admin, name))


async def _postgres_cases(url: str) -> None:
    import asyncpg

    pool = await asyncpg.create_pool(url)
    try:
        store = PgStore(pool)
        await store.apply_schema()
        index = await pool.fetchval(
            """
            SELECT indexdef FROM pg_indexes
            WHERE schemaname = 'agent_rig' AND indexname = 'searches_tenant_created'
            """
        )
        assert index is not None
        assert "tenant_id" in index
        assert "created_at DESC" in index

        await store.add_search(CN, VERSION, _saved("older", _when(10)))
        await store.add_search(CN, VERSION, _saved("newer", _when(1)))
        await store.add_search(CN, VERSION, _saved("ancient", _when(120)))
        await store.add_search(EXAMPLE, VERSION, _saved("other-retailer", _when(1)))

        recent = await store.searches_for(CN, VERSION, 90)
        assert [row["query"] for row in recent] == ["newer", "older"]
        wider = await store.searches_for(CN, VERSION, 200)
        assert [row["query"] for row in wider] == ["newer", "older", "ancient"]
        short = await store.searches_for(CN, VERSION, 5)
        assert [row["query"] for row in short] == ["newer"]

        now = datetime.now(timezone.utc)
        for index_no in range(501):
            await store.add_search(
                CN,
                "cap-v",
                _saved(f"row-{index_no:04d}", now - timedelta(seconds=index_no)),
            )
        capped = await store.searches_for(CN, "cap-v", 90)
        assert len(capped) == 500
        assert capped[0]["query"] == "row-0000"
        assert capped[-1]["query"] == "row-0499"

        await pool.execute(
            """
            INSERT INTO agent_rig.products
                (tenant_id, id, sku, name, brand, category, price, currency)
            VALUES ($1, 'keep-me', 'keep-me', 'Keep', 'Brand', 'pistol', 1, 'ZAR')
            """,
            UUID(CN),
        )
        await store.add_search(CN, "clean-v", _saved("cn-old", _when(100)))
        await store.add_search(CN, "clean-v", _saved("cn-new", _when(2)))
        await store.add_search(EXAMPLE, "clean-v", _saved("ex-old", _when(100)))
        await store.add_search(EXAMPLE, "clean-v", _saved("ex-new", _when(2)))
        deleted = await store.expire_searches(90)
        assert deleted == 3
        left = await pool.fetch("SELECT tenant_id::text, query FROM agent_rig.searches ORDER BY query")
        # The cap-v and window rows that are still inside 90 days stay, plus the two recent clean rows.
        names = {row["query"] for row in left}
        assert "cn-old" not in names
        assert "ex-old" not in names
        assert "ancient" not in names
        assert "cn-new" in names and "ex-new" in names
        assert "newer" in names and "older" in names
        assert await pool.fetchval("SELECT count(*) FROM agent_rig.products WHERE sku = 'keep-me'") == 1
        assert await store.expire_searches(90) == 0
        assert await pool.fetchval("SELECT count(*) FROM agent_rig.products WHERE sku = 'keep-me'") == 1
    finally:
        await pool.close()
