"""coolify-ops op=zenas-renormalise: fake Coolify, no network.

The op runs the re-normalise job inside the deployed ZA room as a Coolify
scheduled task (the nightly task's container), dry run unless apply=true, and
prints only a fixed projection of the job's report.
"""
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("renorm_op", ROOT / ".github/scripts/zenas_renormalise_op.py")
op = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(op)

APP, NAME, NIGHTLY = op.TARGETS["za"]
BASE = f"/applications/{APP}"
TASK = "renormtask0001"
REPORT = {
    "dry_run": True,
    "counts": {"rows": 20, "batches": 2, "changed": 1, "unchanged": 19},
    "changed": [{"document_id": "cac:cac 103", "citation": "CAC 103", "suspect_spaces_before": 9,
                 "suspect_spaces_after": 0, "secret": "DO_NOT_PRINT"}],
    "last_document_id": "cac:cac 120",
}
OUTPUT = ("2026-10-31 renormalise batch 1: {\"rows\": 10}\nDATABASE_URL=DO_NOT_PRINT\n"
          + json.dumps(REPORT, indent=2) + "\n")


class FakeCoolify:
    def __init__(self, existing=True, running=False, finish="success", execute_code=200):
        self.calls = []
        self.tasks = [{"uuid": NIGHTLY, "name": op.NIGHTLY_NAME, "container": "agent-zenas", "command": "DO_NOT_PRINT"}]
        if existing:
            self.tasks.append({"uuid": TASK, "name": op.TASK_NAME, "command": "old"})
        self.executions = [{"id": 1, "status": "running" if running else "success",
                            "started_at": "2026-10-30T01:00:00Z", "finished_at": None if running else "2026-10-30T01:10:00Z",
                            "message": "old run DO_NOT_PRINT"}]
        self.finish = finish
        self.execute_code = execute_code
        self.queued = False
        self.polls = 0

    def __call__(self, method, path, body=None):
        assert path in op.allowed_paths(APP, TASK)
        self.calls.append((method, path, body))
        if (method, path) == ("GET", BASE):
            return 200, {"uuid": APP, "name": NAME}
        if (method, path) == ("GET", BASE + "/scheduled-tasks"):
            return 200, self.tasks
        if (method, path) == ("POST", BASE + "/scheduled-tasks"):
            return 201, {"uuid": TASK}
        if (method, path) == ("PATCH", f"{BASE}/scheduled-tasks/{TASK}"):
            return 200, None
        if (method, path) == ("POST", f"{BASE}/scheduled-tasks/{TASK}/execute"):
            self.queued = self.execute_code == 200
            return self.execute_code, None
        if (method, path) == ("GET", f"{BASE}/scheduled-tasks/{TASK}/executions"):
            rows = list(self.executions)
            if self.queued:
                self.polls += 1
                done = self.polls >= 2
                rows.append({"id": 2, "status": self.finish if done else "running",
                             "started_at": "2026-10-31T20:00:00Z",
                             "finished_at": "2026-10-31T20:05:00Z" if done else None,
                             "message": OUTPUT if done else ""})
            return 200, rows
        raise AssertionError((method, path))


def env(**kw):
    base = {"REGION": "za", "APPLY": "false", "SOURCE": "", "LIMIT": "", "AFTER": ""}
    base.update(kw)
    return base


def run(fake, **kw):
    return op.run(fake, env(**kw), sleep=lambda s: None, clock=iter(range(0, 10_000, 5)).__next__)


def test_dry_run_by_default_in_the_nightly_container():
    fake = FakeCoolify()
    result = run(fake, SOURCE="cac", LIMIT="20")
    patch = next(body for method, path, body in fake.calls if method == "PATCH")
    assert patch["command"] == ("python -m agents.zenas.pool.renormalise --batch-size 25 "
                                "--source cac --limit 20 --dry-run")
    assert "--apply" not in patch["command"]
    assert patch["container"] == "agent-zenas"  # the same container the nightly job runs in
    assert patch["enabled"] is False  # never on a schedule
    assert result["apply"] is False
    assert result["execution"]["status"] == "success"
    assert result["report"] == {
        "dry_run": True,
        "counts": {"batches": 2, "changed": 1, "rows": 20, "unchanged": 19},
        "changed": [{"document_id": "cac:cac 103", "suspect_spaces_before": 9, "suspect_spaces_after": 0}],
        "last_document_id": "cac:cac 120",
    }
    assert "DO_NOT_PRINT" not in json.dumps(result)


@pytest.mark.parametrize("value", ["", "false", "FALSE"])
def test_anything_but_true_is_a_dry_run(value):
    fake = FakeCoolify()
    run(fake, APPLY=value)
    patch = next(body for method, path, body in fake.calls if method == "PATCH")
    assert patch["command"].endswith("--dry-run")


def test_apply_only_with_explicit_true():
    fake = FakeCoolify()
    result = run(fake, APPLY="true", AFTER="cac:cac 120")
    patch = next(body for method, path, body in fake.calls if method == "PATCH")
    assert patch["command"].endswith("--after 'cac:cac 120' --apply")
    assert result["apply"] is True


def test_creates_the_task_once_when_missing():
    fake = FakeCoolify(existing=False)
    result = run(fake)
    creates = [body for method, path, body in fake.calls if method == "POST" and path.endswith("/scheduled-tasks")]
    assert len(creates) == 1 and creates[0]["name"] == op.TASK_NAME and creates[0]["enabled"] is False
    assert result["task_uuid"] == TASK


def test_refuses_while_a_run_is_still_running():
    fake = FakeCoolify(running=True)
    with pytest.raises(op.OpError, match="still running"):
        run(fake)
    assert not any(method in {"PATCH", "POST"} for method, _, _ in fake.calls)


@pytest.mark.parametrize("bad", [
    {"REGION": "us"}, {"REGION": ""}, {"APPLY": "yes"}, {"SOURCE": "cac;rm -rf /"},
    {"LIMIT": "0"}, {"LIMIT": "-5"}, {"LIMIT": "10 --apply"}, {"AFTER": "x$(id)"}, {"AFTER": "a`b`"},
])
def test_bad_inputs_stop_before_any_call(bad):
    fake = FakeCoolify()
    with pytest.raises(op.OpError):
        run(fake, **bad)
    assert fake.calls == []


def test_wrong_application_stops_before_any_write():
    fake = FakeCoolify()
    original = fake.__call__

    def wrong(method, path, body=None):
        if (method, path) == ("GET", BASE):
            return 200, {"uuid": APP, "name": "agent-zenas"}  # Boston's name
        return original(method, path, body)

    with pytest.raises(op.OpError):
        op.run(wrong, env(), sleep=lambda s: None, clock=lambda: 0)
    assert not any(method != "GET" for method, _, _ in fake.calls)


def test_execute_unsupported_fails_cleanly():
    fake = FakeCoolify(execute_code=404)
    with pytest.raises(op.OpError, match="HTTP 404"):
        run(fake)


def test_still_running_at_the_wait_limit_points_to_report(monkeypatch):
    fake = FakeCoolify()
    monkeypatch.setattr(op, "WAIT_SECONDS", 0)
    result = op.run(fake, env(), sleep=lambda s: None, clock=lambda: 0)
    assert result["execution"]["status"] == "running"
    assert "zenas-renormalise-report" in result["next"]


def test_report_reads_the_latest_run_only():
    fake = FakeCoolify()
    fake.executions.append({"id": 3, "status": "failed", "started_at": "2026-10-31T21:00:00Z",
                            "finished_at": "2026-10-31T21:01:00Z", "message": "Traceback DO_NOT_PRINT"})
    out = op.report(fake, env())
    assert out["execution"]["status"] == "failed" and out["report"] is None
    assert "DO_NOT_PRINT" not in json.dumps(out)
    assert all(method == "GET" for method, _, _ in fake.calls)


def test_main_prints_no_bodies(capsys, monkeypatch):
    monkeypatch.setenv("REGION", "za")
    fake = FakeCoolify()
    fake.executions[0]["message"] = OUTPUT
    assert op.main(["report"], call=lambda m, p, b=None: fake(m, p, b)) == 0
    printed = capsys.readouterr().out
    assert '"rows": 20' in printed
    assert "DO_NOT_PRINT" not in printed


def test_transport_only_fixed_paths_and_host(monkeypatch):
    monkeypatch.setenv("COOLIFY_URL", "https://untrusted.invalid")
    monkeypatch.setenv("COOLIFY_TOKEN", "offline-placeholder")
    with pytest.raises(op.OpError):
        op.api("GET", BASE)
    monkeypatch.setenv("COOLIFY_URL", op.HOST)
    for path in (f"/applications/{NIGHTLY}", "/applications/xnmc0jkz8j9i5jh1jwanbsfv/envs", "/deploy?uuid=" + APP,
                 BASE + "/envs", f"{BASE}/scheduled-tasks/../envs"):
        with pytest.raises(op.OpError):
            op.api("POST", path)


def test_workflow_wires_the_op_without_generic_api_shell():
    workflow = yaml.safe_load((ROOT / ".github/workflows/coolify-ops.yml").read_text())
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert inputs["apply"]["type"] == "boolean" and inputs["apply"]["default"] is False
    assert inputs["region"]["default"] == ""
    steps = workflow["jobs"]["op"]["steps"]
    run_step = next(s for s in steps if s.get("if") == "inputs.op == 'zenas-renormalise'")
    assert run_step["run"] == "python3 .github/scripts/zenas_renormalise_op.py run"
    report_step = next(s for s in steps if s.get("if") == "inputs.op == 'zenas-renormalise-report'")
    assert report_step["run"] == "python3 .github/scripts/zenas_renormalise_op.py report"
    generic = next(s for s in steps if s.get("name") == "Run")
    assert "inputs.op != 'zenas-renormalise'" in generic["if"]
    assert "inputs.op != 'zenas-renormalise-report'" in generic["if"]
    check = next(s for s in steps if s.get("name") == "Check inputs")
    assert "zenas-renormalise|zenas-renormalise-report" in check["run"]
    assert 'test "$REGION" = za' in check["run"]
    # Inputs reach the script through env only, never interpolated into a shell line.
    env_block = workflow["jobs"]["op"]["env"]
    assert env_block["APPLY"] == "${{ inputs.apply }}" and env_block["AFTER"] == "${{ inputs.after }}"
    for step in steps:
        assert "inputs.after" not in str(step.get("run", "")) and "inputs.source" not in str(step.get("run", ""))
    # Not a deploy: it never joins the coolify-deploy group, so it never waits on or blocks a deploy.
    assert "zenas-renormalise" not in workflow["concurrency"]["group"]


def test_doc_describes_the_op():
    doc = (ROOT / "docs/ops/ZENAS-ZA-RENORMALISE.md").read_text()
    assert "op=zenas-renormalise" in doc and "apply=true" in doc and "zenas-renormalise-report" in doc
