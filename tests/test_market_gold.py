"""Public history labels and room-key access, without database/network."""
import importlib.util
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "agents" / "market_lab"))
from gold_sources import PLATFORM_TENANT, candidates  # noqa: E402
from core.pure import series_fetch, shift_detect, surge_detect  # noqa: E402


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
    assert {r["skill_id"] for r in rows} == {"market.series_fetch", "market.surge_detect", "market.shift_detect"}
    funcs = {"market.series_fetch": series_fetch, "market.surge_detect": surge_detect, "market.shift_detect": shift_detect}
    for row in rows:
        assert funcs[row["skill_id"]](row["input"]) == row["expected"]
        assert row["public"] is True and "2025-" in row["label_source"]
    assert len(candidates(*history(), region="za", limit=3)) == 3
    assert {r["region"] for r in candidates(*history(), region="za", limit=3)} == {"za"}


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
    with pytest.raises(ValueError):
        candidates(*history(), region="unknown")


@pytest.mark.asyncio
async def test_endpoint_auth_and_tenant(monkeypatch):
    spec = importlib.util.spec_from_file_location("market_gold_app", ROOT / "agents/market_lab/app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Ledger:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def series_for(self, tenant):
            assert tenant == PLATFORM_TENANT
            return history()[0]
        async def points_for(self, tenant):
            assert tenant == PLATFORM_TENANT
            return history()[1]
    monkeypatch.setattr(module, "_ledger", Ledger)
    # Ephemeral test credential, never a deployed key.
    import secrets
    key = secrets.token_hex(24)
    monkeypatch.setenv("TANK_KEY", key)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app), base_url="http://room") as client:
        assert (await client.get("/gold/candidates")).status_code == 401
        response = await client.get("/gold/candidates?limit=3", headers={"X-Tank-Key": key})
        assert response.status_code == 200 and len(response.json()) == 3
        assert (await client.get("/gold/candidates?limit=201", headers={"X-Tank-Key": key})).status_code == 422
        monkeypatch.delenv("TANK_KEY")
        assert (await client.get("/gold/candidates", headers={"X-Tank-Key": key})).status_code == 401
