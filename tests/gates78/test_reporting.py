"""A partial run, an empty mapping or an omitted/xfailing case cannot certify gates."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from gate78_contract import PRODUCTS, REQUIREMENTS
from gate78_result import Evidence

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("gate78_runner", ROOT / "scripts/gates_7_8.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def manifest(root):
    directory = root / "tests/gates78/products"
    directory.mkdir(parents=True)
    (directory / "test_opli.py").write_text("def test_real_entry():\n    assert True\n")
    data = {"product": "opli", "source_sha": "a" * 40,
            "entrypoints": ["POST /v1/command/opli/code-turn"],
            "legacy_tests": ["tests/opli_agent/test_gates_7_8.py::test_existing"],
            "cases": {key: ["tests/gates78/products/test_opli.py::test_real_entry"] for key in REQUIREMENTS}}
    path = directory / "opli.json"
    path.write_text(json.dumps(data))
    return path, data


def test_missing_product_is_not_pass(tmp_path):
    assert "error" in runner.load_product("opli", tmp_path)


def test_manifest_requires_every_gate_and_real_product_module(tmp_path):
    path, data = manifest(tmp_path)
    assert "error" not in runner.load_product("opli", tmp_path)
    del data["cases"]["G7.same_tenant"]
    path.write_text(json.dumps(data))
    assert "error" in runner.load_product("opli", tmp_path)


@pytest.mark.parametrize("bad", [[], ["tests/test_hermes_user_scope.py::test_shared"], ["../placeholder.py::test_bad"]])
def test_shared_unit_proof_cannot_replace_product_entry_path(tmp_path, bad):
    path, data = manifest(tmp_path)
    data["cases"]["G7.owner_crud"] = bad
    path.write_text(json.dumps(data))
    assert "error" in runner.load_product("opli", tmp_path)


def test_missing_parameterized_case_and_failed_session_are_not_pass():
    node = "tests/gates78/products/test_opli.py::test_real_entry"
    evidence = {"exit_code": 0, "cases": {node + "[owner]": "PASS", node + "[other]": "FAIL"}}
    assert runner.mapped_outcome([node], evidence) == "FAIL"
    evidence["cases"][node + "[other]"] = "PASS"
    assert runner.mapped_outcome([node], evidence) == "PASS"
    assert runner.mapped_outcome([node + "[missing]"], evidence) == "FAIL"
    evidence["exit_code"] = 1
    assert runner.mapped_outcome([node], evidence) == "FAIL"


@pytest.mark.parametrize("phase,outcome,xfail", [
    ("setup", "failed", False), ("call", "failed", False), ("teardown", "failed", False),
    ("call", "skipped", False), ("call", "skipped", True), ("call", "passed", True),
])
def test_evidence_rejects_errors_skips_and_expected_failures(tmp_path, phase, outcome, xfail):
    evidence = Evidence(tmp_path / "results.json")
    node = "test_placeholder.py::test_placeholder"
    session = SimpleNamespace(items=[SimpleNamespace(nodeid=node)], exitstatus=0)
    evidence.pytest_collection_finish(session)
    for step in ("setup", "call", "teardown"):
        report = SimpleNamespace(nodeid=node, when=step, outcome=outcome if step == phase else "passed")
        if step == phase and xfail:
            report.wasxfail = "placeholder"
        evidence.pytest_runtest_logreport(report)
    evidence.pytest_sessionfinish(session, 0)
    assert session.exitstatus == 1
    assert json.loads(evidence.path.read_text())["cases"][node] == "FAIL"


def test_evidence_requires_collection_and_all_three_phases(tmp_path):
    evidence = Evidence(tmp_path / "results.json")
    session = SimpleNamespace(items=[], exitstatus=0)
    evidence.pytest_sessionfinish(session, 0)
    assert session.exitstatus == 1
    node = "test_placeholder.py::test_placeholder"
    evidence.selected = [node]
    evidence.outcomes = {node: {"setup": "passed", "call": "passed"}}
    evidence.pytest_sessionfinish(session, 0)
    assert session.exitstatus == 1
    evidence.outcomes[node]["teardown"] = "passed"
    session.exitstatus = 0
    evidence.pytest_sessionfinish(session, 0)
    assert json.loads(evidence.path.read_text())["cases"][node] == "PASS"


def test_foundation_summary_cannot_claim_product_acceptance():
    report = {"tank_sha": "a" * 40, "dirty": False, "core": "PASS", "overall": "INCOMPLETE",
              "products": {p: {"gate7": "MISSING", "gate8": "MISSING"} for p in PRODUCTS}}
    summary = runner.status_table(report)
    assert "Overall acceptance: **INCOMPLETE**" in summary
    assert summary.count("| MISSING | MISSING |") == 12
    assert "Head review is required" in summary


@pytest.mark.parametrize("mode,expected", [([], 1), (["--core"], 0), (["--submitted"], 0), (["--product", "opli"], 1)])
def test_runner_scope_never_turns_missing_products_into_pass(tmp_path, monkeypatch, mode, expected):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setenv("MEMORY_TEST_DATABASE_URL", "postgresql://placeholder@127.0.0.1/placeholder_test")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(runner.sys, "argv", ["gates_7_8.py", *mode])
    monkeypatch.setattr(runner.subprocess, "check_output", lambda command, **kw: "a" * 40 if command[1] == "rev-parse" else "")
    monkeypatch.setattr(runner, "run_tests", lambda *args: {"exit_code": 0, "cases": {"placeholder_core": "PASS"}})
    assert runner.main() == expected
    report = json.loads(next((tmp_path / ".tmp/gates78").glob("*/report.json")).read_text())
    assert report["overall"] == "INCOMPLETE"
    assert all(row["gate7"] == row["gate8"] == "MISSING" for row in report["products"].values())


def test_migration_mode_rejects_invalid_submission(tmp_path, monkeypatch):
    path, data = manifest(tmp_path)
    data["cases"].pop("G7.replay")
    path.write_text(json.dumps(data))
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setenv("MEMORY_TEST_DATABASE_URL", "postgresql://placeholder@127.0.0.1/placeholder_test")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(runner.sys, "argv", ["gates_7_8.py", "--submitted"])
    monkeypatch.setattr(runner.subprocess, "check_output", lambda command, **kw: "a" * 40 if command[1] == "rev-parse" else "")
    monkeypatch.setattr(runner, "run_tests", lambda *args: {"exit_code": 0, "cases": {"placeholder_core": "PASS"}})
    assert runner.main() == 1


def test_market_lab_dependency_target_is_required_and_isolated(tmp_path, monkeypatch):
    import hashlib
    import os
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    requirements = tmp_path / 'researcher/requirements.txt'
    requirements.parent.mkdir()
    requirements.write_text('gpt-researcher==0.16.1\n')
    output = tmp_path / 'proof.json'
    output.write_text(json.dumps({'exit_code': 0, 'cases': {'placeholder': 'PASS'}}))
    seen = []
    monkeypatch.setattr(runner.subprocess, 'run', lambda command, **kw: (seen.append(kw['env']) or SimpleNamespace(returncode=0)))
    node = 'tests/gates78/products/test_market_lab.py::test_signed_owner_crud_and_meaningful_research_fields'
    with pytest.raises(RuntimeError, match='pinned researcher'):
        runner.run_tests([node], output)
    target = tmp_path / '.tmp/researcher-test-deps' / hashlib.sha256(requirements.read_bytes()).hexdigest()
    (target / 'gpt_researcher').mkdir(parents=True)
    (target / 'gpt_researcher/__init__.py').write_text('')
    runner.run_tests([node], output)
    runner.run_tests(['tests/gates78/test_stack.py'], output)
    assert seen[0]['PYTHONPATH'].split(os.pathsep)[0] == str(target)
    assert str(target) not in seen[1]['PYTHONPATH'].split(os.pathsep)
    assert seen[0]['PYTEST_ADDOPTS'] == seen[1]['PYTEST_ADDOPTS'] == ''


def test_required_gates_job_owns_market_lab_without_extending_main_deadlines():
    import yaml
    root = Path(__file__).resolve().parents[2]
    jobs = yaml.safe_load((root / '.github/workflows/ci.yml').read_text())['jobs']
    assert 'gates78' in jobs['ci-ok']['needs']
    assert jobs['tank']['timeout-minutes'] == 36
    job = jobs['gates78']
    assert job['runs-on'] == 'ubuntu-latest'
    proof = next(step for step in job['steps'] if step.get('name') == 'Gate 7/8 foundation and every submitted product')
    assert 'python scripts/gates_7_8.py --submitted' in proof['run']
    assert proof['timeout-minutes'] == 18
    install = next(step for step in job['steps'] if step.get('name') == 'Install shared and isolated researcher test dependencies')
    assert '--no-deps --target "$target" -r researcher/requirements.txt' in install['run']
    assert install['timeout-minutes'] == 10
    assert not any('scripts/gates_7_8.py' in step.get('run', '') for step in jobs['tank']['steps'])
