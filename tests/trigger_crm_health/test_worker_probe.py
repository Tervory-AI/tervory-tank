"""Exercise the actual Compose probe without broker, Django, or task execution."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import yaml

COMPOSE = Path(__file__).resolve().parents[2] / "ops/trigger-crm/docker-compose.yml"


@pytest.mark.parametrize("reply,expected", [
    ({"celery@test-worker": {"ok": "pong"}}, 0),
    (None, 1),
    ({}, 1),
    ({"celery@other-worker": {"ok": "pong"}}, 1),
    ({"celery@test-worker": {"error": "failed"}}, 1),
])
def test_probe_requires_exact_worker_pong(monkeypatch, reply, expected):
    health = yaml.safe_load(COMPOSE.read_text())["services"]["celery-worker"]["healthcheck"]
    calls = {}

    def inspect(**kwargs):
        calls["inspect"] = kwargs
        return SimpleNamespace(ping=lambda: reply)

    def client(name, **kwargs):
        calls["client"] = kwargs
        return SimpleNamespace(control=SimpleNamespace(inspect=inspect))

    monkeypatch.setitem(sys.modules, "celery", SimpleNamespace(Celery=client))
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://test-broker/0")
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "must_not_import_django")
    monkeypatch.setattr("socket.gethostname", lambda: "test-worker")
    with pytest.raises(SystemExit) as result:
        exec(compile(health["test"][3], str(COMPOSE), "exec"), {})
    assert result.value.code == expected
    assert calls["client"] == {
        "broker": "redis://test-broker/0", "fixups": [], "set_as_current": False,
    }
    assert calls["inspect"] == {"destination": ["celery@test-worker"], "timeout": 5}
    assert health["timeout"] == "10s"
    assert health["retries"] == 3
