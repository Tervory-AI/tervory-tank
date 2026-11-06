import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient

from agents.ghost import app as watch, enforce_app, configuration, enforce_api


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    for name in list(os.environ):
        if name.startswith(("AUTUMBRA_", "COOLIFY_", "CLOUDFLARE_", "THREAT_", "TANK_")) or name in {"SITE_NAME", "TENANT_ID"}:
            monkeypatch.delenv(name)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))


@pytest.mark.parametrize("value", [None, "", "   "])
def test_watch_starts_idle_without_key_and_never_opens_storage_or_network(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("TANK_KEY", value)
    monkeypatch.setattr(watch, "Store", lambda *a: pytest.fail("unconfigured Watch opened storage"))
    monkeypatch.setattr(watch.httpx, "AsyncClient", lambda **kw: pytest.fail("unconfigured Watch created HTTP client"))
    with TestClient(watch.create_app()) as client:
        health = client.get("/health").json()
        assert health["ok"] and not health["ready"]
        assert health["missing_settings"] == ["TANK_KEY"]
        assert client.post("/look", json={"target": "site"}).status_code == 503
        assert client.post("/ghost/autumbra/enforce/plan-create", json={"execute": True}).status_code == 503


@pytest.mark.parametrize("name,value", [("TANK_REGION", "invalid"), ("DATA_DIR", "file")])
def test_bad_watch_storage_or_region_reports_setting_without_crashing(monkeypatch, tmp_path, name, value):
    monkeypatch.setenv("TANK_KEY", "offline-test-marker")
    if name == "DATA_DIR":
        file = tmp_path / "file"
        file.write_text("occupied")
        value = str(file)
    monkeypatch.setenv(name, value)
    with TestClient(watch.create_app()) as client:
        health = client.get("/health").json()
        assert not health["ready"] and health["invalid_settings"] == [name]
        if name == "DATA_DIR":
            assert value not in json.dumps(health)


def test_enforce_missing_provider_preserves_queue_without_fake_actions(monkeypatch, tmp_path):
    from agents.ghost.threat_queue import ThreatPayloadQueue
    from test_autumbra_cloudflare_hand import payload, TENANT
    queue = ThreatPayloadQueue(tmp_path / "queue")
    identity = queue.put(payload("block_ip"))
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE", str(queue.root))
    monkeypatch.setenv("TENANT_ID", TENANT)
    monkeypatch.setenv("SITE_NAME", "tervory.com")
    monkeypatch.setattr(enforce_app, "select_control", lambda **kw: pytest.fail("provider selected without settings"))
    app = enforce_app.create_enforce_app()
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["ok"] and not health["ready"]
        assert health["blocked"] == 0 and health["verified_blocked"] is None
        assert "CLOUDFLARE_API_TOKEN_ENFORCE" in health["missing_settings"]
        assert "AUTUMBRA_HEALTH_SECRET" in health["detail"]
        assert enforce_app.drain_once_for_enforce(app=app) is None
        assert client.post("/v1/drain-once").json() == {"drained": False, "receipt": None}
        assert (queue.root / "inbox" / (identity + ".json")).exists()
        assert queue.list_receipts() == []


def test_enforce_bad_data_dir_stays_available_and_inactive(monkeypatch, tmp_path):
    path = tmp_path / "file"
    path.write_text("occupied")
    monkeypatch.setenv("DATA_DIR", str(path))
    with TestClient(enforce_app.create_enforce_app()) as client:
        health = client.get("/health").json()
        assert health["ok"] and not health["ready"]
        assert "DATA_DIR" in health["invalid_settings"]
        assert not health["drain_loop_running"]


@pytest.mark.parametrize("missing", configuration.FEATURE_SETTINGS["enforce"])
def test_each_missing_enforce_setting_prevents_provider_selection(monkeypatch, tmp_path, missing):
    values = {name: "offline-test-marker" for name in configuration.FEATURE_SETTINGS["enforce"]}
    values.update(TENANT_ID="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", SITE_NAME="tervory.com",
                  THREAT_PAYLOAD_QUEUE=str(tmp_path / "queue"))
    for name, value in values.items():
        if name != missing:
            monkeypatch.setenv(name, value)
    monkeypatch.setattr(enforce_app, "select_control", lambda **kw: pytest.fail("provider selected without " + missing))
    app = enforce_app.create_enforce_app()
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["ok"] and not health["ready"]
        assert health["missing_settings"] == [missing]
        assert missing in health["detail"]
        assert enforce_app.drain_once_for_enforce(app=app) is None


def test_browser_missing_key_names_setting_and_refuses_probe():
    from agents.ghost.browser import app
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["ok"] and not health["ready"] and health["missing_settings"] == ["TANK_KEY"]
        assert client.post("/check", json={"target": "site"}).status_code == 404


def test_lifecycle_missing_auth_starts_but_refuses_execution():
    with TestClient(enforce_api.create_app()) as client:
        health = client.get("/health").json()
        assert health["ok"] and not health["ready"]
        assert "AUTUMBRA_LIFECYCLE_KEY" in health["missing_settings"]
        assert client.post("/ghost/autumbra/enforce/plan-create", json={"execute": True}).status_code == 401


@pytest.mark.parametrize("feature,names", configuration.FEATURE_SETTINGS.items())
def test_every_missing_setting_is_named_without_exposing_values(monkeypatch, feature, names):
    assert configuration.setting_status(feature)["missing_settings"] == list(names)
    for name in names:
        monkeypatch.setenv(name, "offline-private-marker")
    status = configuration.setting_status(feature)
    assert status["configured"] and not status["missing_settings"]
    assert "offline-private-marker" not in json.dumps(status)


@pytest.mark.parametrize("value", ["broken", "NaN", "Infinity", "-Infinity", "-3", "0", "99999999"])
@pytest.mark.parametrize("name,default,minimum", [("AUTUMBRA_WEEKLY_INTERVAL_SEC", 3600, 1), ("ENFORCE_DRAIN_INTERVAL_SEC", 1, .05)])
def test_bad_scheduler_interval_has_bounded_finite_fallback(monkeypatch, value, name, default, minimum):
    monkeypatch.setenv(name, value)
    interval = configuration.interval_seconds(name, default, minimum, 3600)
    assert minimum <= interval <= 3600


def test_health_observer_names_missing_settings_without_starting_transport(monkeypatch, capsys):
    from agents.ghost import site_health
    def stop(_seconds):
        raise KeyboardInterrupt
    monkeypatch.setattr(site_health.time, "sleep", stop)
    monkeypatch.setattr(site_health.httpx, "HTTPTransport", lambda **kw: pytest.fail("transport opened"))
    with pytest.raises(KeyboardInterrupt):
        site_health.main()
    output = capsys.readouterr()
    assert "SITE_NAME" in output.err and "AUTUMBRA_HEALTH_SECRET" in output.err
