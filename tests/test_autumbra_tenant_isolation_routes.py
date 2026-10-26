"""Tenant isolation on every new Autumbra route."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents.ghost.app import create_app
from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings
from agents.ghost.store import Store

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TANK_KEY", "test-tank-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTUMBRA_FIXTURE_COMPOSE_ROOT", str(tmp_path / "compose"))
    (tmp_path / "compose").mkdir()
    app = create_app()
    with TestClient(app) as c:
        yield c


def _h():
    return {"X-Tank-Key": "test-tank-key"}


def test_settings_do_not_leak_across_tenants(client):
    body_a = {
        "tenant_id": TENANT_A,
        "site_name": "a.example",
        "shield_mode": ApplyMode.auto_when_checks_pass.value,
        "fix_mode": ApplyMode.never.value,
    }
    r = client.post("/ghost/autumbra/settings", headers=_h(), json=body_a)
    assert r.status_code == 200
    assert r.json()["receipt"]["tenant_id"] == TENANT_A
    got_b = client.get("/ghost/autumbra/settings", headers=_h(), params={"tenant_id": TENANT_B})
    assert got_b.status_code == 200
    settings_b = got_b.json()["settings"]
    assert settings_b["tenant_id"] == TENANT_B
    assert settings_b["site_name"] == ""
    assert settings_b["fix_mode"] == ApplyMode.approve_each.value
    got_a = client.get("/ghost/autumbra/settings", headers=_h(), params={"tenant_id": TENANT_A})
    assert got_a.json()["settings"]["site_name"] == "a.example"


def test_hands_and_intel_consume_scoped(client):
    client.post(
        "/ghost/autumbra/hands",
        headers=_h(),
        json={"tenant_id": TENANT_A, "hand": "host_firewall", "connected": True},
    )
    hands_b = client.get("/ghost/autumbra/hands", headers=_h(), params={"tenant_id": TENANT_B}).json()
    assert hands_b["halves"]["block_in_seconds"] is False
    hands_a = client.get("/ghost/autumbra/hands", headers=_h(), params={"tenant_id": TENANT_A}).json()
    assert hands_a["halves"]["block_in_seconds"] is True
    bundle = {
        "schema_version": "market_lab.ioc.v1",
        "bundle_id": "b1",
        "paid": False,
        "sources": [{"id": "abuse_ch_feodo", "name": "abuse.ch Feodo", "url": "https://feodotracker.abuse.ch"}],
        "indicators": [{"kind": "ip", "value": "203.0.113.9", "source_ids": ["abuse_ch_feodo"]}],
    }
    cons_a = client.post(
        "/ghost/autumbra/intel/consume",
        headers=_h(),
        json={"tenant_id": TENANT_A, "bundle": bundle},
    )
    assert cons_a.status_code == 200
    assert cons_a.json()["receipt"]["tenant_id"] == TENANT_A
    assert cons_a.json()["receipt"]["sources"][0]["via"] == "Market Lab"


def test_enforce_lifecycle_execute_isolated(client, tmp_path):
    ca = client.post(
        "/ghost/autumbra/enforce/plan-create",
        headers=_h(),
        json={"tenant_id": TENANT_A, "existing_count": 0, "execute": True},
    )
    cb = client.post(
        "/ghost/autumbra/enforce/plan-create",
        headers=_h(),
        json={"tenant_id": TENANT_B, "existing_count": 1, "execute": True},
    )
    assert ca.status_code == 200 and cb.status_code == 200
    assert ca.json()["receipt"]["outcome"] == "created"
    assert ca.json()["plan"]["network"]["name"] != cb.json()["plan"]["network"]["name"]
    assert ca.json()["plan"]["volume"] != cb.json()["plan"]["volume"]
    destroy = client.post(
        "/ghost/autumbra/enforce/plan-destroy",
        headers=_h(),
        json={"tenant_id": TENANT_A, "execute": True},
    )
    assert destroy.json()["receipt"]["outcome"] == "destroyed"


def test_owner_update_calls_sender(client):
    res = client.post(
        "/ghost/autumbra/owner-update",
        headers=_h(),
        json={
            "settings": {
                "tenant_id": TENANT_A,
                "site_name": "a.example",
                "fix_mode": ApplyMode.approve_each.value,
                "owner_email": "owner-a@example.test",
            },
            "site_name": "a.example",
            "threats_found": 1,
            "critical": [{
                "stack": "PHP", "rating": "critical",
                "advisory_id": "CVE-2026-109618",
                "advisory_url": "https://example.test/cve",
            }],
            "pr_url": "https://github.com/example/pr/1",
            "receipt_url": "https://protect.tervory.com/r/1",
            "to": "owner-a@example.test",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["sent"] is True
    assert body["transport"] == "fixture"
    assert "https://example.test/cve" in body["body"]
    assert "approve fixes yourself" in body["body"]
