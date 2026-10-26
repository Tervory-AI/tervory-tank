"""Full pipe: Watch → queue → Enforce → shield → health → auto-undo fail → receipt.

One fixture attack travels the product path without the test calling Enforce apply
directly. Budgets are measured from those receipts.
"""
from __future__ import annotations

from pathlib import Path

from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings
from agents.ghost.fixture_edge import FixtureEdgeControl
from agents.ghost.never_block import ActionCap
from agents.ghost.speed_budgets import budgets_ok
from agents.ghost.threat_queue import (
    ThreatPayloadQueue,
    enforce_drain_once,
    run_pipe_fixture_attack,
    watch_enqueue_fixture_attack,
)


TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_fixture_attack_travels_watch_queue_enforce_without_direct_apply(tmp_path: Path):
    queue = ThreatPayloadQueue(tmp_path / "q")
    control = FixtureEdgeControl(tenant_id=TENANT)
    settings = ClientAutumbraSettings(
        tenant_id=TENANT,
        site_name="coolify.tervory.com",
        shield_mode=ApplyMode.auto_when_checks_pass,
    )
    raw_log = "2026-10-26T12:00:01Z src=203.0.113.200 path=/admin scanner=nuclei"
    # Product path only — do not call apply_from_payload from this test.
    result = run_pipe_fixture_attack(
        queue=queue,
        settings=settings,
        raw_log=raw_log,
        site="coolify.tervory.com",
        address="203.0.113.200",
        control=control,
        action_cap=ActionCap(limit=100),
    )
    watch = result["watch"]
    enforce = result["enforce"]
    assert watch["queued"] is True
    assert watch["raw_log_kept"] is False
    assert "event_to_decision" in watch["budgets"]
    assert enforce is not None
    assert enforce["applied"] is True
    assert enforce["raw_log_seen"] is False
    assert enforce["health_ok"] is True
    assert enforce["address"] == "203.0.113.200"
    assert len(control.list_blocked()) == 1
    ok, fails = budgets_ok(enforce)
    assert ok, fails
    # Measured, not caller constants.
    assert 0.0 <= enforce["budgets"]["event_to_decision"]["seconds"] < 2.0
    assert 0.0 <= enforce["budgets"]["decision_to_shield"]["seconds"] < 10.0
    assert 0.0 <= enforce["budgets"]["health_check"]["seconds"] < 30.0
    # Receipt was written by Enforce drain, not by the test.
    written = queue.list_receipts()
    assert len(written) == 1
    assert written[0]["id"] == enforce["id"]


def test_pipe_auto_undo_on_failed_health_check(tmp_path: Path):
    queue = ThreatPayloadQueue(tmp_path / "q")
    control = FixtureEdgeControl(tenant_id=TENANT)
    control.set_healthy(False)
    settings = ClientAutumbraSettings(
        tenant_id=TENANT,
        shield_mode=ApplyMode.auto_when_checks_pass,
    )
    watch_enqueue_fixture_attack(
        queue=queue,
        raw_log="src=198.51.100.44 attacking /login",
        site="coolify.tervory.com",
        address="198.51.100.44",
    )
    receipt = enforce_drain_once(
        queue, settings=settings, control=control, action_cap=ActionCap()
    )
    assert receipt is not None
    assert receipt["outcome"] == "auto_undone_health_failed"
    assert receipt["applied"] is False
    assert control.list_blocked() == []
    assert "auto_undo_e2e" in receipt["budgets"]


def test_action_cap_used_on_product_path(tmp_path: Path):
    queue = ThreatPayloadQueue(tmp_path / "q")
    control = FixtureEdgeControl(tenant_id=TENANT)
    settings = ClientAutumbraSettings(
        tenant_id=TENANT,
        shield_mode=ApplyMode.auto_when_checks_pass,
    )
    cap = ActionCap(limit=1)
    raw = "src=203.0.113.10 path=/a"
    run_pipe_fixture_attack(
        queue=queue, settings=settings, raw_log=raw, site="coolify.tervory.com",
        address="203.0.113.10", control=control, action_cap=cap,
    )
    watch_enqueue_fixture_attack(
        queue=queue, raw_log="src=203.0.113.11 path=/b",
        site="coolify.tervory.com", address="203.0.113.11",
    )
    second = enforce_drain_once(queue, settings=settings, control=control, action_cap=cap)
    assert second["outcome"] == "refused_action_cap"
    assert second["applied"] is False


def test_process_wiring_watch_enqueue_enforce_drain(tmp_path: Path, monkeypatch):
    """Product path via app.py + enforce_app.py process doors — not library-only."""
    from agents.ghost.app import enqueue_fixture_attack_for_watch
    from agents.ghost.enforce_app import create_enforce_app, drain_once_for_enforce
    from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings
    from agents.ghost.fixture_edge import FixtureEdgeControl
    from agents.ghost.never_block import ActionCap
    from agents.ghost.threat_queue import ThreatPayloadQueue

    qpath = tmp_path / "product-q"
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE", str(qpath))
    monkeypatch.setenv("TENANT_ID", TENANT)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "edata"))
    queue = ThreatPayloadQueue(qpath)
    watch = enqueue_fixture_attack_for_watch(
        raw_log="2026-10-26T12:00:01Z src=203.0.113.200 path=/admin scanner=nuclei",
        site="coolify.tervory.com",
        address="203.0.113.200",
        queue=queue,
    )
    assert watch["queued"] is True
    assert watch["raw_log_kept"] is False
    control = FixtureEdgeControl(tenant_id=TENANT)
    settings = ClientAutumbraSettings(
        tenant_id=TENANT,
        site_name="coolify.tervory.com",
        shield_mode=ApplyMode.auto_when_checks_pass,
    )
    app = create_enforce_app()
    app.state.control = control
    app.state.settings = settings
    app.state.action_cap = ActionCap(limit=100)
    app.state.threat_queue = queue
    receipt = drain_once_for_enforce(app=app)
    assert receipt is not None
    assert receipt["applied"] is True
    assert receipt["raw_log_seen"] is False
    assert receipt["address"] == "203.0.113.200"
    assert len(control.list_blocked()) == 1
    assert len(queue.list_receipts()) == 1


def test_watch_http_enqueue_and_enforce_http_drain(tmp_path: Path, monkeypatch):
    """HTTP process doors: Watch fixture-attack route + Enforce /v1/drain-once."""
    from fastapi.testclient import TestClient

    from agents.ghost.app import create_app
    from agents.ghost.enforce_app import create_enforce_app
    from agents.ghost.client_settings import ApplyMode, ClientAutumbraSettings
    from agents.ghost.fixture_edge import FixtureEdgeControl, reset_default_control
    from agents.ghost.never_block import ActionCap

    qpath = tmp_path / "http-q"
    monkeypatch.setenv("TANK_KEY", "test-tank-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "wdata"))
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE", str(qpath))
    monkeypatch.setenv("TENANT_ID", TENANT)
    # Keep background drain from racing the explicit /v1/drain-once proof.
    monkeypatch.setenv("ENFORCE_DRAIN_INTERVAL_SEC", "3600")
    reset_default_control()
    watch_app = create_app()
    with TestClient(watch_app) as watch_client:
        res = watch_client.post(
            "/ghost/autumbra/queue/fixture-attack",
            headers={"X-Tank-Key": "test-tank-key"},
            json={
                "raw_log": "src=203.0.113.77 path=/wp-login.php",
                "site": "coolify.tervory.com",
                "address": "203.0.113.77",
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["queued"] is True
        assert body["raw_log_kept"] is False

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "edata"))
    control = FixtureEdgeControl(tenant_id=TENANT)
    settings = ClientAutumbraSettings(
        tenant_id=TENANT,
        shield_mode=ApplyMode.auto_when_checks_pass,
        site_name="coolify.tervory.com",
    )
    enforce_app = create_enforce_app()
    with TestClient(enforce_app) as enforce_client:
        # Lifespan attaches queue from env; re-bind modes/control for auto-apply.
        enforce_app.state.control = control
        enforce_app.state.settings = settings
        enforce_app.state.action_cap = ActionCap(limit=100)
        health = enforce_client.get("/health").json()
        assert health["threat_payload_queue_configured"] is True
        assert health["drain_loop_running"] is True
        assert health["drain_entrypoint"] == "ghost.enforce_app:drain_once_for_enforce"
        drained = enforce_client.post("/v1/drain-once")
        assert drained.status_code == 200, drained.text
        payload = drained.json()
        assert payload["drained"] is True
        receipt = payload["receipt"]
        assert receipt["applied"] is True
        assert receipt["raw_log_seen"] is False
        assert receipt["address"] == "203.0.113.77"
        # Empty queue + no body parse.
        empty = enforce_client.post("/v1/drain-once")
        assert empty.status_code == 200
        assert empty.json()["drained"] is False
        refuse = enforce_client.post("/v1/drain-once", content=b'{"raw_log":"nope"}')
        assert refuse.status_code == 415
