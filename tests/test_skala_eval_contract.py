from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace
import uuid

import httpx
import pytest

import skala

ROOT = Path(__file__).resolve().parents[1]
PATCH_SKILLS = (
    "base.socials base.verify ffl.ingest market.series_fetch market.shift_detect market.surge_detect "
    "reason.brief rig.ask rig.explain rig.search rig.setups scan.dependencies scan.secrets scan.static "
    "tier0.draft tier0.summarize tiger.price_ocr tisan.figma tisan.scaffold zenas.apply zenas.case_facts "
    "zenas.cite_check zenas.compose zenas.draft zenas.match zenas.plain_language zenas.review zenas.rule_card"
).split()


def package(skill):
    choices = [pkg for pkg in skala.load_packages().values() if pkg.id == skill]
    return max(choices, key=lambda pkg: tuple(map(int, pkg.version.split("."))))


def context(pkg):
    async def no_model(**kwargs):
        raise AssertionError("No real model in eval contract tests")

    def no_network(request):
        raise AssertionError("No network in eval contract tests")

    return skala.SkillContext(uuid.uuid4(), pkg.ref, pkg.agent, None, no_model,
                              httpx.AsyncClient(transport=httpx.MockTransport(no_network)))


@pytest.mark.parametrize("skill", PATCH_SKILLS)
def test_patch_keeps_skill_code_and_has_evidence(skill):
    pkg = package(skill)
    versions = sorted(pkg.path.parent.glob("*/skill.yaml"),
                      key=lambda file: tuple(map(int, file.parent.name.split("."))))
    previous = versions[-2].parent
    for source in previous.rglob("*.py"):
        original = source.read_bytes()
        if skill == "base.socials" and source.name == "run.py":
            original = original.replace(b"import re\n", b"", 1)
        assert (pkg.path / source.relative_to(previous)).read_bytes() == original
    assert len(pkg.cases) >= 5
    assert any(row.get("must_refuse") for row in pkg.cases)


def test_latest_packages_have_at_least_five_cases():
    latest = {}
    for pkg in skala.load_packages().values():
        if pkg.id not in latest or tuple(map(int, pkg.version.split("."))) > tuple(map(int, latest[pkg.id].version.split("."))):
            latest[pkg.id] = pkg
    assert all(len(pkg.cases) >= 5 for pkg in latest.values())


def test_named_expectations_are_not_inverted_or_stringified():
    rule = package("zenas.rule_card")
    cited = next(case for case in rule.cases if case["name"] == "cited element can be approved")
    assert cited["expected"]["approvable"] is True
    plain = package("zenas.plain_language")
    dropped = next(case for case in plain.cases if case["name"] == "dropping the citation keeps the original")
    assert dropped["expected"]["kept_original"] is True
    facts = package("zenas.case_facts")
    first = next(case for case in facts.cases if case["name"] == "first read keeps the judgment as published")
    assert first["expected"]["outcome"] == "enforced"


@pytest.mark.asyncio
@pytest.mark.parametrize("skill", [name for name in PATCH_SKILLS if not name.startswith("tisan.")])
async def test_deterministic_eval_cases(skill):
    pkg = package(skill)
    cases = [case for case in pkg.cases if case.get("group") != "live_model"
             and ("model" in case or not pkg.task_type or case.get("must_refuse")
                  or skill.startswith("rig.") or skill == "zenas.compose")]
    pkg = replace(pkg, cases=cases)
    result = await skala.run_evals(pkg, lambda: context(pkg))
    assert result["passed"] == len(cases), [
        (detail["name"], detail["why"]) for detail in result["details"] if not detail["passed"]]


@pytest.mark.asyncio
async def test_minimum_and_negative_evidence_gate():
    pkg = package("rig.explain")

    async def output(pkg, payload, ctx):
        return {"refused": payload["number"] == 0}

    cases = [{"input": {"number": number}, "expected": {"refused": number == 0},
              "must_refuse": number == 0} for number in range(5)]
    for subset, eligible in [(cases[:4], False), (cases, True),
                             ([dict(case, must_refuse=False) for case in cases], False),
                             ([cases[0]] * 5, False)]:
        result = await skala.run_evals(replace(pkg, cases=subset), lambda: context(pkg), execute=output)
        assert result["eligible"] is eligible


@pytest.mark.asyncio
async def test_endpoint_keeps_insufficient_evidence_out_of_staging(monkeypatch):
    from contextlib import asynccontextmanager

    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("TANK_API_KEY", secrets.token_urlsafe(24))
    monkeypatch.setenv("LITELLM_MASTER_KEY", secrets.token_urlsafe(24))
    import main

    class Connection:
        async def fetchval(self, *args):
            return "candidate"

        async def execute(self, *args):
            return None

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield Connection()

    pkg = package("rig.explain")
    monkeypatch.setattr(main, "pool", Pool)
    monkeypatch.setattr(main, "get_package", lambda *args: pkg)
    monkeypatch.setattr(main, "make_ctx", lambda *args, **kwargs: context(pkg))
    full = pkg.cases
    pkg.cases = full[:4]
    assert (await main.run_skill_evals(pkg.id, pkg.version))["state"] == "candidate"
    pkg.cases = full
    assert (await main.run_skill_evals(pkg.id, pkg.version))["state"] == "staging"


@pytest.mark.parametrize("text,accepted", [
    ("A promise can be enforced (8 Del. C. § 101).", True),
    ("A promise is not enforceable (8 Del. C. § 101).", False),
    ("A promise is enforceable.", False),
    ("A promise is enforceable (8 Del. C. § 101; 9 Del. C. § 999).", False),
])
def test_wording_properties(text, accepted):
    case = {"input": {"text": "A promise is enforceable (8 Del. C. § 101).",
                       "citations": ["8 Del. C. § 101"]}, "properties": {"legal_wording": True}}
    assert skala.eval_properties(case, {"text": text}, True)[0] is accepted
    assert not skala.eval_properties(case, {"text": case["input"]["text"], "smoothed": True}, False)[0]


@pytest.mark.parametrize("changed", [
    "The buyer can respond within 10 days.",
    "The buyer must respond within 20 days.",
    "The buyer must not respond within 10 days.",
    "The buyer must respond after 10 days.",
])
def test_legal_effect_rules_reject_changed_duties(changed):
    case = {"input": {"text": "The buyer must respond within 10 days.", "citations": []},
            "properties": {"legal_wording": True}}
    assert not skala.eval_properties(case, {"text": changed}, True)[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("reply,passed", [
    ("A written promise can be enforced (8 Del. C. § 101).", True),
    ("A written promise is not enforceable (8 Del. C. § 101).", False),
])
async def test_live_model_wording_uses_properties_not_exact_text(reply, passed):
    pkg = package("zenas.plain_language")
    pkg = replace(pkg, cases=[case for case in pkg.cases if case.get("group") == "live_model"])
    ctx = context(pkg)
    async def model(**kwargs):
        return {"content": reply, "cost_usd": 0}
    ctx._model = model
    result = await skala.run_evals(pkg, lambda: ctx)
    assert result["details"][0]["passed"] is passed
    assert ctx.calls == 1


@pytest.mark.asyncio
async def test_room_route_uses_key_and_tenant(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("TANK_API_KEY", secrets.token_urlsafe(24))
    monkeypatch.setenv("LITELLM_MASTER_KEY", secrets.token_urlsafe(24))
    import main

    key = secrets.token_urlsafe(24)
    monkeypatch.setenv("TANK_KEY_TISAN", key)
    pkg = package("tisan.figma")
    ctx = context(pkg)
    def respond(request):
        assert request.url == "http://agent-tisan:8000/evals/run"
        assert request.headers["X-Tank-Key"] == key
        assert json.loads(request.content)["tenant_id"] == str(ctx.tenant_id)
        return httpx.Response(200, json={"ok": True})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(main, "_http", client)
        assert await main.run_room_eval(pkg, {}, ctx) == {"ok": True}
        monkeypatch.delenv("TANK_KEY_TISAN")
        with pytest.raises(RuntimeError):
            await main.run_room_eval(pkg, {}, ctx)


@pytest.mark.asyncio
async def test_tisan_eval_endpoint_auth_and_dispatch(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "agents/_chassis"))
    spec = importlib.util.spec_from_file_location("tisan_eval_test", ROOT / "agents/tisan/app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    seen = []
    async def execute(payload, tenant):
        seen.append((payload, tenant))
        return {"ok": True}
    monkeypatch.setattr(module, "_scaffold_module", lambda: SimpleNamespace(execute=execute))
    key = secrets.token_urlsafe(24)
    monkeypatch.setenv("TANK_KEY", key)
    tenant = str(uuid.uuid4())
    body = {"skill_id": "tisan.scaffold", "version": "1.0.1", "tenant_id": tenant, "input": {"tenant_id": "forged"}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app), base_url="http://room") as client:
        assert (await client.post("/evals/run", json=body)).status_code == 401
        assert not seen
        assert (await client.post("/evals/run", json=body, headers={"X-Tank-Key": key})).status_code == 200
        assert seen == [(body["input"], tenant)]
        body["skill_id"] = "../arbitrary"
        assert (await client.post("/evals/run", json=body, headers={"X-Tank-Key": key})).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("skill", ["tisan.figma", "tisan.scaffold"])
async def test_room_backed_cases_run_inside_room(skill, monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "agents/_chassis"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    spec = importlib.util.spec_from_file_location("tisan_case_test", ROOT / "agents/tisan/app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    async def checks(project):
        assert (project / "package.json").is_file()
        return ([{"name": name, "ok": True} for name in
                 ["npm ci", "npm run lint", "npm run build", "npm test"]], "")
    monkeypatch.setattr(module._scaffold_module(), "run_checks", checks)
    key = secrets.token_urlsafe(24)
    monkeypatch.setenv("TANK_KEY", key)
    pkg = package(skill)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app), base_url="http://room") as client:
        async def execute(pkg, payload, ctx):
            response = await client.post("/evals/run", headers={"X-Tank-Key": key},
                json={"skill_id": pkg.id, "version": pkg.version, "tenant_id": str(ctx.tenant_id), "input": payload})
            assert response.status_code == 200
            return response.json()
        result = await skala.run_evals(pkg, lambda: context(pkg), execute=execute)
    assert result["passed"] == len(pkg.cases), result["details"]
    assert result["eligible"]
