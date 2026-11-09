"""Signed-in check issues: one per page, no duplicates, closed on recovery. Fakes only."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = "https://github.com/Tervory-AI/tervory-tank/actions/runs/1"


def _alerts():
    path = ROOT / ".github" / "scripts" / "signed_in_alerts.py"
    spec = importlib.util.spec_from_file_location("signed_in_alerts_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["signed_in_alerts_script"] = module
    spec.loader.exec_module(module)
    return module


class FakeGitHub:
    """Keeps issues like GitHub does: open ones are listed by title."""

    def __init__(self) -> None:
        self.issues: dict[int, dict] = {}
        self.comments: list[tuple[int, str]] = []
        self.next = 100

    def ensure_label(self) -> None:
        return None

    def open_incidents(self) -> dict[str, dict[str, object]]:
        return {i["title"]: {"number": n, "body": i["body"]} for n, i in self.issues.items() if i["open"]}

    def open_issue(self, title: str, body: str) -> int:
        self.next += 1
        self.issues[self.next] = {"title": title, "body": body, "open": True}
        return self.next

    def set_body(self, number: int, body: str) -> None:
        self.issues[number]["body"] = body

    def comment(self, number: int, body: str) -> None:
        self.comments.append((number, body))

    def close(self, number: int) -> None:
        self.issues[number]["open"] = False


def row(page: str, *reasons: str) -> dict:
    return {"id": page, "url": f"https://app.tervory.com/{page}", "passed": not reasons,
            "reasons": list(reasons), "screenshot": f"{page}.png" if reasons else None}


def test_failure_opens_one_issue_and_repeats_never_duplicate() -> None:
    alerts, github, pushes = _alerts(), FakeGitHub(), []
    for _ in range(3):
        alerts.sync([row("base", "HTTP 503"), row("rig-overview")], github, RUN, "", pushes.append)
    titles = [i["title"] for i in github.issues.values() if i["open"]]
    assert titles == ["Signed-in check failed: base"]
    assert "- HTTP 503" in github.issues[101]["body"]
    assert "`base.png`" in github.issues[101]["body"]
    assert len(pushes) == 1 and pushes[0].startswith("base failed the signed-in check: HTTP 503")
    assert github.comments == []


def test_new_reason_updates_the_same_issue() -> None:
    alerts, github, pushes = _alerts(), FakeGitHub(), []
    alerts.sync([row("rig-overview", "Empty section: Next step")], github, RUN, "", pushes.append)
    done = alerts.sync([row("rig-overview", "Empty section: Next step", "Empty: Ask Rig answers")],
                       github, RUN, "", pushes.append)
    assert done == ["updated #101 Signed-in check failed: rig-overview"]
    assert len(github.issues) == 1 and len(pushes) == 1
    assert "- Empty: Ask Rig answers" in github.issues[101]["body"]
    assert github.comments[0][0] == 101 and "new reason" in github.comments[0][1]


def test_recovery_closes_the_issue_and_a_later_failure_opens_a_fresh_one() -> None:
    alerts, github, pushes = _alerts(), FakeGitHub(), []
    alerts.sync([row("sign-in-provider", "Sign-in text names the provider: ZITADEL")], github, RUN, "", pushes.append)
    done = alerts.sync([row("sign-in-provider")], github, RUN, "", pushes.append)
    assert done == ["closed #101 Signed-in check failed: sign-in-provider"]
    assert github.issues[101]["open"] is False
    assert github.comments == [(101, f"Passed again: the page shows real content. Closing. [Run]({RUN})")]
    alerts.sync([row("sign-in-provider", "HTTP 502")], github, RUN, "", pushes.append)
    assert [n for n, i in github.issues.items() if i["open"]] == [102]
    assert len(pushes) == 2


def test_passing_pages_without_an_issue_do_nothing() -> None:
    alerts, github, pushes = _alerts(), FakeGitHub(), []
    assert alerts.sync([row("tiger"), row("radix")], github, RUN, "", pushes.append) == []
    assert github.issues == {} and pushes == []


def test_push_needs_an_https_url_and_never_raises(monkeypatch) -> None:
    alerts = _alerts()
    calls = []
    monkeypatch.setattr(alerts.urllib.request, "urlopen", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(OSError()))
    alerts.push_to("")("ignored")
    alerts.push_to("http://plain.example/topic")("ignored")
    assert calls == []
    alerts.push_to("https://push.example/topic")("base failed")
    assert len(calls) == 1 and calls[0][0].data == b"base failed"
