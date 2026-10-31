"""radix.* 1.0.1: eval-only patches, plus per-box regional eval inputs (ZA staging gate)."""
import json
import uuid

import httpx
import pytest

import skala

SKILLS = ("radix.verify_business", "radix.entity_links", "radix.account_links",
          "radix.site_risk", "radix.business_risk")
REFUSE = {"ok": False, "error": "invalid_business_evidence"}


def packages():
    return {(p.id, p.version): p for p in skala.load_packages().values()}


def context(pkg):
    async def no_model(**kwargs):
        raise AssertionError("radix never calls a model")

    def no_network(request):
        raise AssertionError("radix never calls the network")

    # Evals run under the platform tenant, as on the boxes.
    return skala.SkillContext(skala.PLATFORM_TENANT, pkg.ref, pkg.agent, None, no_model,
                              httpx.AsyncClient(transport=httpx.MockTransport(no_network)))


def with_region(value, region):
    if isinstance(value, dict):
        return {k: region if k == "region" else with_region(v, region) for k, v in value.items()}
    if isinstance(value, list):
        return [with_region(v, region) for v in value]
    return value


@pytest.mark.parametrize("skill", SKILLS)
def test_patch_keeps_code_and_boston_fingerprints(skill, monkeypatch):
    monkeypatch.setenv("TANK_REGION", "us-east")
    pkgs = packages()
    old, new = pkgs[(skill, "1.0.0")], pkgs[(skill, "1.0.1")]
    assert (new.path / "run.py").read_bytes() == (old.path / "run.py").read_bytes()
    assert (new.path / "skill.yaml").read_text().replace('"version": "1.0.1"', '"version": "1.0.0"') == \
        (old.path / "skill.yaml").read_text()
    old_lines = (old.path / "evals/cases.jsonl").read_text(encoding="utf-8").splitlines()
    assert (new.path / "evals/cases.jsonl").read_text(encoding="utf-8").splitlines()[:len(old_lines)] == old_lines
    assert {skala.evidence_hash(c) for c in old.cases} <= {skala.evidence_hash(c) for c in new.cases}
    assert not (new.path / "evals/cases.us-east.jsonl").exists()


@pytest.mark.parametrize("skill", SKILLS)
def test_za_inputs_differ_only_by_region(skill, monkeypatch):
    monkeypatch.setenv("TANK_REGION", "us-east")
    shared = packages()[(skill, "1.0.1")].cases
    monkeypatch.setenv("TANK_REGION", "za")
    regional = packages()[(skill, "1.0.1")].cases
    assert [c["name"] for c in regional] == [c["name"] for c in shared]
    for here, there in zip(regional, shared):
        assert {k: v for k, v in here.items() if k != "input"} == {k: v for k, v in there.items() if k != "input"}
        assert here["input"] == with_region(there["input"], "za")


@pytest.mark.asyncio
@pytest.mark.parametrize("region", ("us-east", "za"))
@pytest.mark.parametrize("skill", SKILLS)
async def test_patch_passes_and_is_eligible_on_each_box(skill, region, monkeypatch):
    monkeypatch.setenv("TANK_REGION", region)
    pkg = packages()[(skill, "1.0.1")]
    assert {c["input"]["region"] for c in pkg.cases} == {region}
    result = await skala.run_evals(pkg, lambda: context(pkg))
    assert result["passed"] == result["total"] == 12, result["details"]
    assert result["eligible"] is True, result["evidence_reason"]
    refusals = [c for c in pkg.cases if c.get("must_refuse")]
    assert len(refusals) == 5 and all(c["expected"] == REFUSE for c in refusals)


@pytest.mark.asyncio
@pytest.mark.parametrize("skill", SKILLS)
async def test_each_refusal_breaks_a_passing_case(skill, monkeypatch):
    """The refusals fail because of their one change, not because of the box region."""
    monkeypatch.setenv("TANK_REGION", "za")
    pkg = packages()[(skill, "1.0.1")]
    positive = pkg.cases[0]
    assert (await skala.run_skill(pkg, json.loads(json.dumps(positive["input"])), context(pkg)))["ok"] is True
    for case in pkg.cases:
        if case.get("must_refuse"):
            assert case["input"] != positive["input"]
            out = await skala.run_skill(pkg, case["input"], context(pkg))
            assert {k: out.get(k) for k in REFUSE} == REFUSE


def write_package(root, overlay):
    pkg = root / "demo.skill" / "1.0.0"
    (pkg / "evals").mkdir(parents=True)
    (pkg / "skill.yaml").write_text("id: demo.skill\nversion: 1.0.0\n")
    (pkg / "run.py").write_text("async def run(payload, ctx):\n    return {'ok': True}\n")
    shared = {"name": "a", "input": {"region": "us-east"}, "expected": {"ok": True}, "tolerance": "exact"}
    (pkg / "evals/cases.jsonl").write_text(json.dumps(shared) + "\n")
    if overlay is not None:
        (pkg / "evals/cases.za.jsonl").write_text(json.dumps(overlay) + "\n")
    return shared


@pytest.mark.parametrize("overlay", (
    {"name": "a", "input": {"region": "za"}, "expected": {"ok": False}, "tolerance": "exact"},
    {"name": "a", "input": {"region": "za"}, "expected": {"ok": True}, "tolerance": "contains"},
    {"name": "a", "input": {"region": "za"}, "expected": {"ok": True}, "tolerance": "exact", "must_refuse": True},
    {"name": "b", "input": {"region": "za"}, "expected": {"ok": True}, "tolerance": "exact"},
))
def test_regional_cases_fail_closed_unless_only_input_changes(tmp_path, monkeypatch, overlay):
    write_package(tmp_path, overlay)
    monkeypatch.setenv("TANK_REGION", "za")
    assert skala.load_packages(tmp_path) == {}


def test_regional_cases_apply_only_on_their_own_box(tmp_path, monkeypatch):
    overlay = {"name": "a", "input": {"region": "za"}, "expected": {"ok": True}, "tolerance": "exact"}
    shared = write_package(tmp_path, overlay)
    monkeypatch.setenv("TANK_REGION", "us-east")
    assert skala.load_packages(tmp_path)[("demo.skill", "1.0.0")].cases == [shared]
    monkeypatch.setenv("TANK_REGION", "za")
    assert skala.load_packages(tmp_path)[("demo.skill", "1.0.0")].cases == [overlay]
