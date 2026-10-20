"""Public history labels and room-key access, without database/network."""
import importlib.util
import sys
import tracemalloc
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "agents" / "market_lab"))
spec = importlib.util.spec_from_file_location("market_lab_gold_test_sources", ROOT / "agents/market_lab/gold_sources.py")
gold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gold)
PLATFORM_TENANT, candidates = gold.PLATFORM_TENANT, gold.candidates
from core.pure import series_fetch  # noqa: E402


def history():
    series, points = [], []
    for area in ("one", "two"):
        for source, prefix in (("listing_counts", "count:state:"), ("check_counts", "total:")):
            sid = source + area
            series.append(dict(id=sid, tenant_id=PLATFORM_TENANT, source=source, ref=prefix + area, engine="ffl"))
            for month in range(1, 9):
                points.append(dict(series_id=sid, date=f"2025-{month:02}-01", value=100 if month < 7 or area == "two" else 300 if source == "check_counts" else 20))
    return series, points


def test_labels_match_skills_and_limit():
    rows = candidates(*history(), region="us-east", today=date(2026, 1, 1))
    assert {r["skill_id"] for r in rows} == {"market.series_fetch"}
    for row in rows:
        assert series_fetch(row["input"]) == row["expected"]
        assert row["public"] is True and "2025-" in row["label_source"]
        assert "census_population" not in row["label_source"]
    assert len(candidates(*history(), region="us-east", limit=3)) == 3
    assert candidates(*history(), region="za", limit=3) == []


def test_private_live_only_and_future_excluded():
    series, points = history()
    for row in series:
        row["tenant_id"] = "another-tenant"
    assert candidates(series, points, region="us-east") == []
    for row in series:
        row.update(tenant_id=PLATFORM_TENANT, source="fred")
    assert candidates(series, points, region="us-east") == []
    for row in series:
        row["source"] = "upload"
    assert candidates(series, points, region="us-east") == []
    assert candidates(*history(), region="us-east", today=date(2025, 1, 1)) == []
    assert candidates(*history(), region="unknown") == []


def test_large_stream_is_lazy_and_memory_bounded():
    source = history()[0][0]
    consumed = 0

    def points():
        nonlocal consumed
        for index in range(1_000_000):
            consumed += 1
            yield {"series_id": source["id"], "date": (date(1900, 1, 1) + timedelta(days=index)).isoformat(), "value": index}

    tracemalloc.start()
    try:
        rows = candidates([source], points(), region="us-east", limit=200)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert consumed == 201
    assert len(rows) == 200
    assert max(len(row["expected"]["points"]) for row in rows) == gold.MAX_HISTORY
    assert peak < 5_000_000
    assert len(candidates([source], points(), region="us-east", limit=1)) == 1
    assert consumed == 203


class Connection:
    def __init__(self):
        self.scanned = 0
        self.fetched = 0

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def cursor(self, sql, tenant, sources, *, prefetch):
        assert str(tenant) == PLATFORM_TENANT and "tenant_id=$1" in sql
        assert set(sources) == gold.PUBLIC_SOURCES and prefetch == 1

        async def rows():
            for row in history()[0]:
                self.scanned += 1
                yield row
        return rows()

    async def fetch(self, sql, tenant, series_id, cutoff, count):
        self.fetched += 1
        assert str(tenant) == PLATFORM_TENANT
        assert "s.tenant_id=$1" in sql and "LIMIT $4" in sql
        assert count <= gold.MAX_HISTORY + 200
        return [point for point in history()[1] if point["series_id"] == series_id][:count]


@pytest.mark.asyncio
async def test_database_reader_stops_at_limit():
    conn = Connection()
    assert len(await gold.collect(conn, region="us-east", limit=3)) == 3
    assert conn.scanned == conn.fetched == 1
    for region in ("za", "invalid"):
        assert await gold.collect(conn, region=region, limit=3) == []
    assert conn.scanned == 1


@pytest.mark.asyncio
async def test_endpoint_auth_and_tenant(monkeypatch):
    spec = importlib.util.spec_from_file_location("market_gold_app", ROOT / "agents/market_lab/app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Ledger:
        conn = Connection()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
    monkeypatch.setattr(module, "_ledger", Ledger)
    # Ephemeral test credential, never a deployed key.
    import secrets
    key = secrets.token_hex(24)
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("TANK_REGION", "us-east")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app), base_url="http://room") as client:
        assert (await client.get("/gold/candidates")).status_code == 401
        response = await client.get("/gold/candidates?limit=3", headers={"X-Tank-Key": key})
        assert response.status_code == 200 and len(response.json()) == 3
        assert (await client.get("/gold/candidates?limit=201", headers={"X-Tank-Key": key})).status_code == 422
        for region in ("za", "invalid"):
            monkeypatch.setenv("TANK_REGION", region)
            assert (await client.get("/gold/candidates", headers={"X-Tank-Key": key})).json() == []
        monkeypatch.setenv("TANK_KEY", "non-ascii-é")
        assert (await client.get("/gold/candidates", headers={"X-Tank-Key": key})).status_code == 401
        monkeypatch.delenv("TANK_KEY")
        assert (await client.get("/gold/candidates", headers={"X-Tank-Key": key})).status_code == 401
