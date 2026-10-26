"""Tenant isolation on every new Autumbra route."""
from __future__ import annotations

import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient

from agents.ghost.app import create_app
from agents.ghost.client_settings import ApplyMode
from agents.ghost.webhooks import CF_SECRET_ENV, reset_drop_counts

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TANK_KEY", "test-tank-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTUMBRA_FIXTURE_COMPOSE_ROOT", str(tmp_path / "compose"))
    monkeypatch.setenv(CF_SECRET_ENV, "edge-secret")
    (tmp_path / "compose").mkdir()
    reset_drop_counts()
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
        "owner_email": "a@example.test",
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
    cons_b = client.post(
        "/ghost/autumbra/intel/consume",
        headers=_h(),
        json={"tenant_id": TENANT_B, "bundle": {**bundle, "bundle_id": "b2"}},
    )
    assert cons_b.json()["receipt"]["tenant_id"] == TENANT_B


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


def test_owner_update_calls_sender_from_client_settings(client):
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
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["sent"] is True
    assert body["to"] == "owner-a@example.test"
    assert body["transport"] == "fixture"
    assert "https://example.test/cve" in body["body"]
    assert "approve fixes yourself" in body["body"]
    assert "[" not in body["body"]


def test_owner_update_without_owner_email_fails(client):
    res = client.post(
        "/ghost/autumbra/owner-update",
        headers=_h(),
        json={
            "settings": {
                "tenant_id": TENANT_A,
                "site_name": "a.example",
                "fix_mode": ApplyMode.approve_each.value,
            },
            "threats_found": 0,
            "critical": [],
            "receipt_url": "https://protect.tervory.com/r/1",
            "checks_run": 1,
        },
    )
    assert res.status_code == 422


def test_exercise_permission_does_not_cross_tenants(client):
    # Tenant A has no red_team_permission; cannot run against a non-own site.
    client.post(
        "/ghost/autumbra/settings",
        headers=_h(),
        json={
            "tenant_id": TENANT_A,
            "site_name": "a.example",
            "red_team_permission": False,
            "owner_email": "a@example.test",
        },
    )
    client.post(
        "/ghost/autumbra/settings",
        headers=_h(),
        json={
            "tenant_id": TENANT_B,
            "site_name": "b.example",
            "red_team_permission": True,
            "owner_email": "b@example.test",
        },
    )
    # A tries to exercise B's site using A's settings (no permission) -> 403
    denied = client.post(
        "/ghost/autumbra/exercises/run",
        headers=_h(),
        json={
            "tenant_id": TENANT_A,
            "exercise_id": "path_scan_fixture",
            "target_site": "b.example",
        },
    )
    assert denied.status_code == 403
    # B with permission on own site -> ok
    ok = client.post(
        "/ghost/autumbra/exercises/run",
        headers=_h(),
        json={
            "tenant_id": TENANT_B,
            "exercise_id": "path_scan_fixture",
            "target_site": "b.example",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["kind"] == "exercise"


def test_sources_and_jobs_and_webhook_isolated_surface(client):
    sources = client.get("/ghost/autumbra/sources", headers=_h(), params={"tenant_id": TENANT_A})
    assert sources.status_code == 200
    assert sources.json()["sources"] == []
    jobs = client.get("/ghost/autumbra/jobs", headers=_h())
    assert jobs.status_code == 200
    assert any(j["id"] == "autumbra_weekly_owner_update" for j in jobs.json()["jobs"])
    exercises = client.get("/ghost/autumbra/exercises", headers=_h())
    assert exercises.status_code == 200
    body = b'{"event":"x"}'
    # Webhook: no tank key required; bad sig dropped.
    dropped = client.post("/ghost/autumbra/webhooks/edge", content=body)
    assert dropped.status_code == 401
    sig = hmac.new(b"edge-secret", body, hashlib.sha256).hexdigest()
    accepted = client.post(
        "/ghost/autumbra/webhooks/edge",
        content=body,
        headers={"X-Autumbra-Signature": sig, "X-Autumbra-Timestamp": str(int(time.time()))},
    )
    assert accepted.status_code == 200
