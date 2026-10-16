"""Tank /health reports the image SHA, and Coolify can check that endpoint.

No database and no network. Coolify marks a compose stack running:unknown when
any running service has no health check, so every long-running service has one.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import yaml

import main

ROOT = Path(__file__).resolve().parents[1]


class _Conn:
    async def fetchval(self, query: str) -> int:
        assert query == "SELECT 1"
        return 1

    async def __aenter__(self) -> _Conn:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _Pool:
    def acquire(self) -> _Conn:
        return _Conn()


def test_health_includes_sha(monkeypatch) -> None:
    monkeypatch.setenv("TANK_GIT_SHA", "abc1234")
    monkeypatch.setattr(main, "pool", lambda: _Pool())
    body = asyncio.run(main.health())
    assert body["ok"] is True
    assert body["region"]
    assert body["sha"] == "abc1234"


def test_health_sha_is_unknown_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("TANK_GIT_SHA", raising=False)
    monkeypatch.setattr(main, "pool", lambda: _Pool())
    body = asyncio.run(main.health())
    assert body["sha"] == "unknown"


def test_compose_healthcheck_targets_tank_health() -> None:
    dockerfile = (ROOT / "tank" / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG SOURCE_COMMIT=" in dockerfile
    assert "ENV TANK_GIT_SHA=" in dockerfile
    for name in ("docker-compose.yml", "docker-compose.za.yml"):
        compose = yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))
        services = compose["services"]
        command = " ".join(services["tank"]["healthcheck"]["test"])
        assert "http://127.0.0.1:8000/health" in command
        assert services["tank"]["build"]["args"]["SOURCE_COMMIT"] == "${SOURCE_COMMIT:-}"
        for service, spec in services.items():
            if spec.get("exclude_from_hc") is True:
                continue
            assert "healthcheck" in spec, f"{name} {service} has no health check"
    boston = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    south_africa = yaml.safe_load((ROOT / "docker-compose.za.yml").read_text(encoding="utf-8"))
    assert boston["services"]["qdrant"]["image"] == "qdrant/qdrant:v1.19.2"
    assert south_africa["services"]["qdrant"]["image"] == "qdrant/qdrant:v1.19.2"


def _watchdog():
    path = ROOT / ".github" / "scripts" / "watchdog.py"
    spec = importlib.util.spec_from_file_location("watchdog_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["watchdog_script"] = module
    spec.loader.exec_module(module)
    return module


def test_coolify_api_success_can_close_the_coolify_issue(monkeypatch) -> None:
    watchdog = _watchdog()
    monkeypatch.setenv("COOLIFY_TOKEN", "test-token")
    monkeypatch.setenv("COOLIFY_URL", "https://coolify.example")
    payload = json.dumps([
        {"name": "tervory-tank-za", "status": "running:unknown", "uuid": "za-uuid"},
        {"name": "tervory-tank", "status": "running:unknown", "uuid": watchdog.MAIN_APP},
    ]).encode()

    class _Response:
        status = 200

        def read(self) -> bytes:
            return payload

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

    monkeypatch.setattr(watchdog.urllib.request, "urlopen", lambda *_a, **_k: _Response())
    results = {item.thing: item for item in watchdog.coolify_results()}
    assert results["Coolify"].state == "ok"
    assert results["Coolify"].detail == "HTTP 200"
    assert results["Coolify tervory-tank-za"].state == "down"
    assert results["Coolify tervory-tank"].state == "ok"
