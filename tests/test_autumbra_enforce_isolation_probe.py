"""Isolation network test viewpoint: inside a fixture client's Enforce container."""
from pathlib import Path

import yaml

from agents.ghost.enforce_isolation_probe import FORBIDDEN_RESOLVE, evaluate_probe
from agents.ghost.enforce_lifecycle import assert_tenant_isolation, plan_create

ROOT = Path(__file__).resolve().parents[1]
TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_probe_pass_when_dark_inside_enforce():
    probe = {
        "resolve": {h: False for h in FORBIDDEN_RESOLVE},
        "public_443": False,
        "shares_network_with_other_client": False,
        "has_tank_key": False,
        "role": "enforce",
    }
    report = evaluate_probe(probe)
    assert report["ok"] is True
    assert report["viewpoint"] == "inside_fixture_enforce"


def test_probe_fails_if_tank_or_other_client_visible():
    probe = {
        "resolve": {h: (h == "tank") for h in FORBIDDEN_RESOLVE},
        "public_443": False,
        "shares_network_with_other_client": True,
        "has_tank_key": True,
        "role": "enforce",
    }
    report = evaluate_probe(probe)
    assert report["ok"] is False
    assert any("tank" in f for f in report["fails"])


def test_compose_internal_and_two_fixture_plans_isolated():
    raw = yaml.safe_load((ROOT / "agents/ghost/docker-compose.enforce.yml").read_text())
    assert raw["networks"]["enforce_internal"]["internal"] is True
    a = plan_create(TENANT_A, existing_count=0)
    b = plan_create(TENANT_B, existing_count=1)
    assert_tenant_isolation(a, b)
    assert a["isolation"]["shares_network_with_other_clients"] is False
    assert a["isolation"]["shares_network_with_tank"] is False
    assert a["cap"]["status"] == "held_until_measured"
