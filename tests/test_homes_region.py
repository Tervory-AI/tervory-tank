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


# Z7 founder feeds, scores, and the review switch talk to the other box.
# They send a source name or on/off. Matter routes stay on this box.
FOUNDER_BOX = {
    "feeds/region/route.ts",
    "feeds/region/load/route.ts",
    "selftest/route.ts",
    "review-switch/route.ts",
}


def test_matter_routes_stay_on_this_regions_tank() -> None:
    api = ROOT / "workspace" / "app" / "api" / "zenas"
    for route in api.rglob("route.ts"):
        rel = route.relative_to(api).as_posix()
        if route.parent.name == "tenants" or rel in FOUNDER_BOX:
            continue
        assert "zenasIn(" not in route.read_text(encoding="utf-8"), route


def test_founder_box_routes_carry_no_matter() -> None:
    api = ROOT / "workspace" / "app" / "api" / "zenas"
    for rel in FOUNDER_BOX:
        text = (api / rel).read_text(encoding="utf-8")
        assert "zenasIn(" in text
        assert "matter_id" not in text
        assert "tenant_id" not in text
