"""Founder home setting: each tenant's home is written by the Tank in that region.

Static checks on the Workspace source. No network, no model.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TANK_TS = (ROOT / "workspace" / "app" / "api" / "zenas" / "tank.ts").read_text(encoding="utf-8")
ROUTE = (ROOT / "workspace" / "app" / "api" / "zenas" / "tenants" / "route.ts").read_text(encoding="utf-8")


def test_tenants_route_writes_on_the_home_regions_tank() -> None:
    assert "zenasIn(home, \"tenants\"" in ROUTE
    assert "isFounder(userId)" in ROUTE
    assert "NOT_CONNECTED" in ROUTE


def test_other_region_tank_is_https_with_its_own_key_and_forced_home() -> None:
    assert "TANK_URL_ZA" in TANK_TS and "TANK_API_KEY_ZA" in TANK_TS
    assert 'parsed.protocol !== "https:"' in TANK_TS
    assert "withHome(path, init, region, true)" in TANK_TS


def test_matter_routes_stay_on_this_regions_tank() -> None:
    api = ROOT / "workspace" / "app" / "api" / "zenas"
    for route in api.rglob("route.ts"):
        if route.parent.name == "tenants":
            continue
        assert "zenasIn(" not in route.read_text(encoding="utf-8"), route
