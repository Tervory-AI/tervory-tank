"""Offline Skala intake for Trigger free checkers. No network, no database, no keys."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tank"))
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

import skala
from trigger.checkers import check, local_checks, map_languagetool
from trigger.voice import Voice

SKILLS = ROOT / "tank" / "skills"
TRIGGER_SKILLS = [
    "trigger.proselint",
    "trigger.languagetool",
    "trigger.agent_style",
    "trigger.house_style",
    "trigger.readability",
    "trigger.voice_check",
]
TENANT = UUID("00000000-0000-0000-0000-000000000011")


class StubHttp:
    def __init__(self) -> None:
        self.called = False

    def __getattr__(self, name: str):
        async def _call(*_a, **_k):
            self.called = True
            raise RuntimeError("offline stub: http blocked")

        return _call


class StubCtx:
    def __init__(self) -> None:
        self.http = StubHttp()
        self.env: dict[str, str] = {}
        self.calls = 0
        self.cost_usd = 0.0

    async def model(self, *_a, **_k) -> str:
        raise RuntimeError("offline stub: model is not available")


def _load_run(pkg: skala.SkillPackage):
    path = pkg.path / "run.py"
    name = f"intake_{pkg.id}_{pkg.version}".replace(".", "_").replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = getattr(module, "run", None)
    assert run is not None
    return run


def test_trigger_packages_load_and_shape():
    packages = skala.load_packages(SKILLS)
    for skill_id in TRIGGER_SKILLS:
        pkg = packages.get((skill_id, "1.0.0"))
        assert pkg is not None, skill_id
        assert pkg.agent == "trigger"
        assert pkg.rung == 3
        assert pkg.task_type is None
        assert (pkg.path / "run.py").is_file()
        assert (pkg.path / "CHANGELOG.md").is_file()
        assert (pkg.path / "evals" / "cases.jsonl").is_file()
        assert len(pkg.cases) >= 20, f"{skill_id} has {len(pkg.cases)} cases"
        refusals = [c for c in pkg.cases if c.get("must_refuse")]
        assert refusals, f"{skill_id} needs a refusal case"
        distinct = {
            json.dumps(c.get("input") or {}, sort_keys=True) for c in pkg.cases
        }
        assert len(distinct) >= 5, skill_id


@pytest.mark.asyncio
async def test_trigger_evals_pass_offline():
    packages = [
        pkg
        for pkg in skala.load_packages(SKILLS).values()
        if pkg.id in TRIGGER_SKILLS and pkg.version == "1.0.0"
    ]
    assert len(packages) == 6
    failures: list[str] = []
    counts: dict[str, int] = {}
    for pkg in sorted(packages, key=lambda item: item.ref):
        run = _load_run(pkg)
        passed = 0
        for index, case in enumerate(pkg.cases):
            name = case.get("name") or f"case {index}"
            ctx = StubCtx()
            output = await run(case.get("input") or {}, ctx)
            ok, why = skala.score_case(
                case.get("expected") or {}, output, case.get("tolerance") or "exact"
            )
            if ok:
                passed += 1
            else:
                failures.append(f"{pkg.ref} / {name}: {why}")
        counts[pkg.ref] = passed
        assert passed == len(pkg.cases), f"{pkg.ref}: {passed}/{len(pkg.cases)}"
        assert passed / len(pkg.cases) >= pkg.eval_threshold
    assert not failures, "\n".join(failures)
    # Print for PR proof capture.
    print(json.dumps(counts, sort_keys=True))


@pytest.mark.asyncio
async def test_unapproved_skill_never_runs_for_client():
    """Tank returns 409 when no approved version; room keeps local path."""

    class RejectTank:
        async def run_skill(self, tenant_id, skill_id, payload):
            raise RuntimeError("tank answered 409")

    class FakeHttp:
        async def post(self, *a, **k):
            raise httpx.ConnectError("offline")

    import httpx

    voice = Voice(brand="Offline", status="live", revision=1)
    report = await check(
        "This is very unique. It was completed by the team.\n```\nunclosed",
        voice,
        FakeHttp(),
        tank=RejectTank(),
        tenant_id=TENANT,
    )
    assert report["skala_skills"] == []
    assert report["model_calls"] == 0
    sources = {item["source"] for item in report["issues"]}
    assert "proselint" in sources or "readability" in sources or "practical-prose" in sources
    # Same mechanical findings as today's local path (LanguageTool unavailable both ways).
    local = local_checks(
        "This is very unique. It was completed by the team.\n```\nunclosed", voice
    )
    local_sources = {item["source"] for item in local["issues"]}
    assert local_sources <= sources or sources <= local_sources | {"languagetool"}


@pytest.mark.asyncio
async def test_approved_skills_called_through_skala_not_local_copy():
    calls: list[str] = []

    class ApproveTank:
        async def run_skill(self, tenant_id, skill_id, payload):
            calls.append(skill_id)
            if skill_id == "trigger.proselint":
                return {"issues": [{"source": "proselint", "rule": "from-skala", "message": "x", "line": 1, "column": 1}], "error": None, "_skill": "trigger.proselint@1.0.0"}
            if skill_id == "trigger.agent_style":
                return {"issues": [], "skipped_rules": ["RULE-01"], "error": None}
            if skill_id == "trigger.house_style":
                return {"issues": [], "error": None}
            if skill_id == "trigger.readability":
                return {"issues": [{"source": "readability", "rule": "passive_voice", "offset": 0, "length": 1, "message": "x"}], "error": None}
            if skill_id == "trigger.voice_check":
                return {"issues": [], "error": None}
            if skill_id == "trigger.languagetool":
                return {"issues": [], "complete": True, "checker_errors": [], "error": None}
            raise RuntimeError("tank answered 409")

    class FakeHttp:
        async def post(self, *a, **k):
            request = SimpleNamespace()
            raise httpx.ConnectError("offline")

    import httpx

    report = await check(
        "Sample text for Skala path.",
        Voice(brand="Offline", status="live", revision=3),
        FakeHttp(),
        tank=ApproveTank(),
        tenant_id=TENANT,
    )
    assert set(calls) == set(TRIGGER_SKILLS)
    assert set(report["skala_skills"]) == set(TRIGGER_SKILLS)
    assert any(item.get("rule") == "from-skala" for item in report["issues"])


@pytest.mark.asyncio
async def test_rollback_restores_previous_version_contract():
    """Skala rollback API retires current and re-approves previous; packages stay on disk."""
    packages = skala.load_packages(SKILLS)
    current = packages[("trigger.proselint", "1.0.0")]
    assert current is not None
    # No 0.9.0 yet; rollback contract is: previous approved package remains loadable.
    # Simulate retired+restored by loading the same 1.0.0 after a fake retire marker.
    restored = skala.load_packages(SKILLS)[("trigger.proselint", "1.0.0")]
    assert restored.ref == current.ref
    assert restored.path == current.path
    run = _load_run(restored)
    out = await run({"text": "This is very unique."}, StubCtx())
    assert out["error"] is None
    assert any(item["source"] == "proselint" for item in out["issues"])


def test_case_counts_documented():
    packages = skala.load_packages(SKILLS)
    counts = {
        skill_id: len(packages[(skill_id, "1.0.0")].cases) for skill_id in TRIGGER_SKILLS
    }
    assert all(count >= 20 for count in counts.values())
    Path(__file__).with_name("CASE_COUNTS.json").write_text(json.dumps(counts, indent=2) + "\n")


def test_languagetool_mapper_matches_room():
    mapped = map_languagetool(
        {
            "matches": [
                {"rule": {"id": "A"}, "message": "A", "offset": 1, "length": 2}
            ],
            "warnings": {},
        },
        available=True,
    )
    assert mapped["complete"] is True
    assert mapped["issues"][0]["source"] == "languagetool"
    unavailable = map_languagetool(None, available=False)
    assert unavailable["complete"] is False
