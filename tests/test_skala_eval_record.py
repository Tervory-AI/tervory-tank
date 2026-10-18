"""The expanded Skala record shows each case's goal and the result that came back.

A pass count on its own is not a record. Passing cases are included. The pass or
fail flag is the one score_case already returned.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import skala

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "tank" / "skills"
PAGE = ROOT / "workspace" / "app" / "skala" / "page.tsx"


class NetworkBlocked(Exception):
    """Raised by the stub HTTP client. A skill that needs the network hits this."""


class StubHttp:
    async def get(self, *_args: object, **_kwargs: object) -> None:
        raise NetworkBlocked("get")

    async def post(self, *_args: object, **_kwargs: object) -> None:
        raise NetworkBlocked("post")


class Ctx:
    def __init__(self) -> None:
        self.http = StubHttp()
        self.env: dict[str, str] = {}
        self.cost_usd = 0.0


def _render(payload: dict) -> dict:
    proc = subprocess.run(
        ["node", "--experimental-strip-types", str(ROOT / "tests" / "render_skala_record.ts")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _assert_record(payload: dict, cases: list[dict]) -> None:
    shown = _render(payload)
    assert shown["ok"] is True
    assert len(shown["cases"]) == len(cases)
    for case, detail, line in zip(cases, payload["details"], shown["cases"], strict=True):
        assert detail["goal"] == case.get("expected", {})
        assert line["name"] == (detail["name"] or f"case {detail['case']}")
        assert line["passed"] is detail["passed"]
        assert json.loads(line["goal"]) == detail["goal"]
        assert json.loads(line["result"]) == detail["result"]
        if str(detail["why"]).startswith("error:"):
            assert detail["passed"] is False
        else:
            ok, why = skala.score_case(detail["goal"], detail["result"], case.get("tolerance") or "exact")
            assert detail["passed"] is ok
            assert detail["why"] == why


def _assert_bare_count_is_refused(payload: dict) -> None:
    bare = {
        "passed": payload["passed"],
        "total": payload["total"],
        "details": [
            {"case": detail["case"], "name": detail["name"], "passed": detail["passed"], "why": detail["why"]}
            for detail in payload["details"]
        ],
    }
    shown = _render(bare)
    assert shown["ok"] is False
    text = json.dumps(shown)
    assert "11/11" not in text
    assert "passed" not in text.lower()


@pytest.mark.asyncio
async def test_record_shows_the_real_goal_and_result_and_refuses_a_bare_pass_count(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(_pkg: skala.SkillPackage, payload: dict, _ctx: Ctx) -> dict:
        if payload["kind"] == "match":
            return {"site": "https://example.com"}
        return {"site": "https://other.example"}

    original_run = skala.run_skill
    monkeypatch.setattr(skala, "run_skill", fake_run)
    pkg = skala.SkillPackage(
        id="example.record",
        version="1.0.0",
        agent="base",
        rung=3,
        task_type=None,
        description="A record check.",
        input_schema={},
        output_schema={},
        eval_threshold=1.0,
        path=ROOT,
        cases=[
            {"name": "match", "input": {"kind": "match"}, "expected": {"site": "https://example.com"}, "tolerance": "exact"},
            {"name": "miss", "input": {"kind": "miss"}, "expected": {"site": "https://example.com"}, "tolerance": "exact"},
        ],
    )
    result = await skala.run_evals(pkg, Ctx)
    assert result["passed"] == 1
    assert result["total"] == 2
    assert [detail["passed"] for detail in result["details"]] == [True, False]
    _assert_record(result, pkg.cases)
    _assert_bare_count_is_refused(result)

    real = skala.load_packages(SKILLS)[("base.find_site", "1.6.0")]
    monkeypatch.setattr(skala, "run_skill", original_run)
    live = await skala.run_evals(real, Ctx)
    assert live["total"] == len(real.cases) == 11
    assert len(live["details"]) == 11
    _assert_record(live, real.cases)
    _assert_bare_count_is_refused(live)


def test_page_lists_every_case_and_does_not_print_a_pass_count() -> None:
    # The squad page replaced the old skills console. The case record still lives in record.ts.
    record = (PAGE.parent / "record.ts").read_text(encoding="utf-8")
    view = (PAGE.parent / "view.tsx").read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    assert "caseRecord" in record
    assert "splitPackages" in record
    assert "<h1>Skala</h1>" in view
    assert "{r.passed}/{r.total} passed" not in page
    assert "{r.passed}/{r.total} passed" not in view
    assert "approve" not in view.lower()
    for face in ("Jost", "Inter", "JetBrains", "next/font"):
        assert face not in page
    assert not (PAGE.parent / "layout.tsx").exists()
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--test", str(ROOT / "tests" / "skala_eval_record.test.ts")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
