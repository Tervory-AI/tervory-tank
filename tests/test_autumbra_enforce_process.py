"""Enforce is a real separately runnable process: own entrypoint, no Tank key, apply+undo."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings
from agents.ghost.enforce_app import create_enforce_app, submit_payload
from agents.ghost.enforce_apply import apply_from_payload, undo_applied
from agents.ghost.fixture_edge import FixtureEdgeControl, reset_default_control
from agents.ghost.speed_budgets import budgets_ok
from agents.ghost.threat_payload import accept_threat_payload

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _payload(address: str = "203.0.113.44"):
    return accept_threat_payload({
        "schema_version": "ghost.threat.v1",
        "action": "propose_shield",
        "site": "coolify.tervory.com",
        "kind": "block_ip",
        "address": address,
        "cve_ids": ["CVE-2026-109618"],
        "severity": "critical",
        "reason": "fixture attacking address on coolify",
        "confidence": 0.95,
    })


def test_enforce_app_starts_without_tank_key(monkeypatch):
    monkeypatch.delenv("TANK_KEY", raising=False)
    reset_default_control()
    client = TestClient(create_enforce_app())
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["role"] == "enforce"
    assert body["tank_key_configured"] is False


def test_enforce_http_refuses_raw_body():
    reset_default_control()
    client = TestClient(create_enforce_app())
    res = client.post("/v1/apply", content=b'{"raw":"log line secret"}')
    assert res.status_code == 415
    assert res.json()["raw_log_seen"] is True


def test_apply_and_undo_against_fixture_control():
    control = FixtureEdgeControl(tenant_id=TENANT)
    settings = ClientAutumbraSettings(
        tenant_id=TENANT,
        shield_mode=ApplyMode.auto_when_checks_pass,
        site_name="coolify.tervory.com",
    )
    receipt = apply_from_payload(_payload(), settings=settings, control=control)
    assert receipt["applied"] is True
    assert receipt["raw_log_seen"] is False
    assert receipt["outcome"] == "applied"
    assert len(control.list_blocked()) == 1
    ok, fails = budgets_ok(receipt)
    assert ok, fails
    # Budgets were measured (not caller-supplied constants).
    assert receipt["budgets"]["event_to_decision"]["seconds"] < 2.0
    undone = undo_applied(receipt, control=control)
    assert undone["outcome"] == "undone"
    assert control.list_blocked() == []
    ok2, fails2 = budgets_ok(undone)
    assert ok2, fails2


def test_enforce_rejects_non_threatpayload_raw_inputs():
    settings = ClientAutumbraSettings(tenant_id=TENANT, shield_mode=ApplyMode.auto_when_checks_pass)
    control = FixtureEdgeControl(tenant_id=TENANT)
    for raw in (
        b'{"schema_version":"ghost.threat.v1"}',
        '{"schema_version":"ghost.threat.v1"}',
        {"schema_version": "ghost.threat.v1", "action": "propose_shield", "site": "coolify.tervory.com"},
        "GET /admin HTTP/1.1\\nAuthorization: Bearer secret",
    ):
        with pytest.raises(TypeError, match="ThreatPayload only"):
            apply_from_payload(raw, settings=settings, control=control)  # type: ignore[arg-type]


def test_submit_payload_in_process_door():
    reset_default_control()
    app = create_enforce_app()
    settings = ClientAutumbraSettings(
        tenant_id=TENANT,
        shield_mode=ApplyMode.auto_when_checks_pass,
    )
    receipt = submit_payload(_payload("198.51.100.20"), app=app, settings=settings)
    assert receipt["applied"] is True
    assert receipt["address"] == "198.51.100.20"


def test_compose_uses_enforce_app_not_ghost_app():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "agents/ghost/docker-compose.enforce.yml").read_text()
    assert "ghost.enforce_app:app" in text
    assert "ghost.app:app" not in text
    assert "No TANK_KEY" in text
    # Env block must not declare TANK_KEY=
    assert "TANK_KEY:" not in text and "TANK_KEY=" not in text
