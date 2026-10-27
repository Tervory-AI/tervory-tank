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
    assert boston["services"]["qdrant"]["image"] == "qdrant/qdrant:v1.20.0"
    assert south_africa["services"]["qdrant"]["image"] == "qdrant/qdrant:v1.20.0"


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


def _coolify_apps(monkeypatch, watchdog, apps: list[dict]) -> None:
    monkeypatch.setenv("COOLIFY_TOKEN", "test-token")
    monkeypatch.setenv("COOLIFY_URL", "https://coolify.example")
    payload = json.dumps(apps).encode()

    class _Response:
        status = 200

        def read(self) -> bytes:
            return payload

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

    monkeypatch.setattr(watchdog.urllib.request, "urlopen", lambda *_a, **_k: _Response())


class _FakeGitHub:
    def __init__(self, open_titles: dict[str, int]) -> None:
        self.issues = {title: {"number": number, "body": "status exited:unhealthy"} for title, number in open_titles.items()}
        self.opened: list[str] = []
        self.closed: list[int] = []
        self.comments: list[tuple[int, str]] = []

    def ensure_label(self) -> None:
        return None

    def open_incidents(self) -> dict[str, dict[str, object]]:
        return dict(self.issues)

    def open_issue(self, title: str, detail: str) -> int:
        self.opened.append(title)
        return 999

    def comment(self, number: int, body: str) -> None:
        self.comments.append((number, body))

    def close(self, number: int) -> None:
        self.closed.append(number)

    def set_body(self, number: int, body: str) -> None:
        return None


def _sync(monkeypatch, watchdog, results, fake: _FakeGitHub) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "Tervory-AI/tervory-tank")
    monkeypatch.setattr(watchdog, "GitHub", lambda repo, token: fake)
    watchdog.sync_issues(results)


ZA_APPS = [
    {"name": "tervory-tank-za", "status": "exited:unhealthy", "uuid": "za-uuid"},
    {"name": "agent-zenas-za", "status": "exited:unhealthy", "uuid": "zenas-za-uuid"},
    {"name": "tervory-tank", "status": "running:unknown", "uuid": "xnmc0jkz8j9i5jh1jwanbsfv"},
]


def test_za_offline_skips_za_apps_and_keeps_their_issues_open(monkeypatch) -> None:
    monkeypatch.setenv("ZA_OFFLINE", "true")
    watchdog = _watchdog()
    _coolify_apps(monkeypatch, watchdog, ZA_APPS)
    results = watchdog.coolify_results()
    by_name = {item.thing: item for item in results}
    assert by_name["Coolify tervory-tank-za"].state == "skip"
    assert by_name["Coolify agent-zenas-za"].state == "skip"
    assert by_name["Coolify tervory-tank"].state == "ok"
    assert not any(item.state == "down" for item in results)

    # #214 and #215 stay open (no recovery comment, no close), and nothing new opens.
    fake = _FakeGitHub({"Down: Coolify agent-zenas-za": 214, "Down: Coolify tervory-tank-za": 215})
    _sync(monkeypatch, watchdog, results, fake)
    assert fake.closed == [] and fake.comments == [] and fake.opened == []


def test_za_offline_unset_or_false_keeps_todays_behaviour(monkeypatch) -> None:
    for value in (None, "false", "yes"):
        if value is None:
            monkeypatch.delenv("ZA_OFFLINE", raising=False)
        else:
            monkeypatch.setenv("ZA_OFFLINE", value)
        watchdog = _watchdog()
        _coolify_apps(monkeypatch, watchdog, ZA_APPS)
        by_name = {item.thing: item for item in watchdog.coolify_results()}
        assert by_name["Coolify tervory-tank-za"].state == "down"
        assert by_name["Coolify agent-zenas-za"].state == "down"


def test_deleted_app_issue_is_closed_and_never_reopened(monkeypatch) -> None:
    monkeypatch.delenv("ZA_OFFLINE", raising=False)
    watchdog = _watchdog()
    # tervory-workers was deleted from Coolify on 21 Oct, so it is not in the list.
    _coolify_apps(monkeypatch, watchdog, [
        {"name": "tervory-tank", "status": "running:unknown", "uuid": watchdog.MAIN_APP},
    ])
    results = watchdog.coolify_results()
    assert "Coolify tervory-workers" not in {item.thing for item in results}
    fake = _FakeGitHub({"Down: Coolify tervory-workers": 229, "Down: rig.tervory.com": 300})
    _sync(monkeypatch, watchdog, results, fake)
    assert fake.closed == [229]
    assert fake.comments == [(229, "closed: this app no longer exists in Coolify")]
    assert fake.opened == []


def test_deleted_app_check_waits_for_a_clean_coolify_list(monkeypatch) -> None:
    monkeypatch.delenv("ZA_OFFLINE", raising=False)
    watchdog = _watchdog()
    open_titles = ["Down: Coolify tervory-workers"]
    # Coolify API down: nothing is treated as deleted.
    down = [watchdog.Result("Coolify", "down", "HTTP 502")]
    assert watchdog.gone_apps(down, open_titles) == []
    # One unreadable row: the missing app could be that row, so wait.
    partial = [watchdog.Result("Coolify", "ok", "HTTP 200"), watchdog.Result("Coolify", "down", "unreadable application")]
    assert watchdog.gone_apps(partial, open_titles) == []
    # Clean list without it: gone.
    clean = [watchdog.Result("Coolify", "ok", "HTTP 200")]
    assert [item.thing for item in watchdog.gone_apps(clean, open_titles)] == ["Coolify tervory-workers"]


def test_za_offline_never_treats_missing_za_apps_as_deleted(monkeypatch) -> None:
    monkeypatch.setenv("ZA_OFFLINE", "true")
    watchdog = _watchdog()
    clean = [watchdog.Result("Coolify", "ok", "HTTP 200")]
    titles = ["Down: Coolify tervory-tank-za", "Down: Coolify agent-zenas-za", "Down: Coolify tervory-workers"]
    assert [item.thing for item in watchdog.gone_apps(clean, titles)] == ["Coolify tervory-workers"]
