"""Watchdog: Coolify's running:unknown is a health-check gap, not an outage. Fakes only.

From 2 Nov to 9 Nov 2026 every watchdog run failed on "Coolify Autumbra" and "Coolify
Autumbra Enforce - tervory.com" reporting running:unknown (issues #735 and #611) while every
public probe returned HTTP 200. Coolify says running:unknown only when every container is
running and none is unhealthy but at least one has no health check.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The application list shape the watchdog read on 8 Nov (names and statuses from run 42532518928).
APPS = [
    {"name": "Autumbra", "status": "running:unknown", "uuid": "autumbra-uuid"},
    {"name": "Autumbra Enforce - tervory.com", "status": "running:unknown", "uuid": "enforce-uuid"},
    {"name": "agent-rig", "status": "running:healthy", "uuid": "rig-uuid"},
    {"name": "tervory-tank", "status": "running:healthy", "uuid": "xnmc0jkz8j9i5jh1jwanbsfv"},
]


def _watchdog():
    path = ROOT / ".github" / "scripts" / "watchdog.py"
    spec = importlib.util.spec_from_file_location("watchdog_unknown_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["watchdog_unknown_script"] = module
    spec.loader.exec_module(module)
    return module


def _coolify(monkeypatch, watchdog, apps: list[dict]) -> list:
    monkeypatch.setenv("COOLIFY_TOKEN", "test-token")
    monkeypatch.setenv("COOLIFY_URL", "https://coolify.tervory.com")
    monkeypatch.delenv("ZA_OFFLINE", raising=False)
    payload = json.dumps(apps).encode()

    class Response:
        status = 200

        def read(self) -> bytes:
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

    monkeypatch.setattr(watchdog.urllib.request, "urlopen", lambda *_a, **_k: Response())
    return watchdog.coolify_results()


class FakeGitHub:
    def __init__(self, open_titles: dict[str, int]) -> None:
        self.issues = {title: {"number": n, "body": "status running:unknown"} for title, n in open_titles.items()}
        self.opened: list[str] = []
        self.closed: list[int] = []
        self.comments: list[tuple[int, str]] = []

    def ensure_label(self) -> None:
        return None

    def open_incidents(self):
        return dict(self.issues)

    def open_issue(self, title: str, detail: str) -> int:
        self.opened.append(title)
        number = 900 + len(self.opened)
        self.issues[title] = {"number": number, "body": detail}
        return number

    def comment(self, number: int, body: str) -> None:
        self.comments.append((number, body))

    def close(self, number: int) -> None:
        self.closed.append(number)
        self.issues = {t: i for t, i in self.issues.items() if i["number"] != number}

    def set_body(self, number: int, body: str) -> None:
        return None


def _sync(monkeypatch, watchdog, results, fake) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "Tervory-AI/tervory-tank")
    monkeypatch.setattr(watchdog, "GitHub", lambda repo, token: fake)
    watchdog.sync_issues(results)


def test_running_unknown_is_a_gap_and_the_run_passes(monkeypatch) -> None:
    watchdog = _watchdog()
    results = _coolify(monkeypatch, watchdog, APPS)
    by = {r.thing: r for r in results}
    assert by["Coolify Autumbra"].state == "gap"
    assert by["Coolify Autumbra Enforce - tervory.com"].state == "gap"
    assert by["Coolify agent-rig"].state == "ok"
    monkeypatch.setattr(watchdog, "collect", lambda: results)
    _sync_target = FakeGitHub({})
    monkeypatch.setattr(watchdog, "GitHub", lambda repo, token: _sync_target)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "Tervory-AI/tervory-tank")
    assert watchdog.main() == 0


@pytest.mark.parametrize("status", ["running:unhealthy", "exited:unhealthy", "exited", "degraded:unhealthy",
                                    "restarting", "starting:unknown", "unreadable"])
def test_real_outages_still_fail(monkeypatch, status) -> None:
    watchdog = _watchdog()
    results = _coolify(monkeypatch, watchdog, [{"name": "Autumbra", "status": status, "uuid": "a"}])
    row = {r.thing: r for r in results}["Coolify Autumbra"]
    assert row.state == "down"
    assert row.detail == f"status {status}"
    monkeypatch.setattr(watchdog, "collect", lambda: results)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert watchdog.main() == 1


def test_gap_moves_the_down_issue_to_one_health_check_issue(monkeypatch) -> None:
    watchdog = _watchdog()
    results = _coolify(monkeypatch, watchdog, APPS)
    fake = FakeGitHub({"Down: Coolify Autumbra": 735, "Down: Coolify Autumbra Enforce - tervory.com": 611})
    _sync(monkeypatch, watchdog, results, fake)
    assert fake.opened == ["No health check: Coolify Autumbra", "No health check: Coolify Autumbra Enforce - tervory.com"]
    assert fake.closed == [735, 611]
    assert fake.comments[0] == (735, f"Not down: {watchdog.GAP_DETAIL} Tracked in #901.")
    # The next run changes nothing: no second issue, no comment.
    fake.comments.clear()
    _sync(monkeypatch, watchdog, results, fake)
    assert len(fake.opened) == 2 and fake.comments == [] and fake.closed == [735, 611]


def test_healthy_again_closes_the_health_check_issue(monkeypatch) -> None:
    watchdog = _watchdog()
    healthy = [dict(app, status="running:healthy") for app in APPS]
    results = _coolify(monkeypatch, watchdog, healthy)
    fake = FakeGitHub({"No health check: Coolify Autumbra": 950})
    _sync(monkeypatch, watchdog, results, fake)
    assert fake.closed == [950] and fake.opened == []
    assert fake.comments == [(950, "recovered: Coolify reports running:healthy")]


def test_gap_that_turns_into_an_outage_opens_a_down_issue(monkeypatch) -> None:
    watchdog = _watchdog()
    results = _coolify(monkeypatch, watchdog, [{"name": "Autumbra", "status": "degraded:unhealthy", "uuid": "a"}])
    fake = FakeGitHub({"No health check: Coolify Autumbra": 950})
    _sync(monkeypatch, watchdog, results, fake)
    assert fake.opened == ["Down: Coolify Autumbra"]
    assert fake.closed == []


def test_deleted_app_closes_its_health_check_issue(monkeypatch) -> None:
    watchdog = _watchdog()
    results = _coolify(monkeypatch, watchdog, APPS[2:])
    fake = FakeGitHub({"No health check: Coolify Autumbra": 950})
    _sync(monkeypatch, watchdog, results, fake)
    assert fake.closed == [950]
    assert fake.comments == [(950, "closed: this app no longer exists in Coolify")]
