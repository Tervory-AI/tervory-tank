"""CI minutes: docs-only changes skip CI, and ci.yml can use a self-hosted runner.

See docs/ops/self-hosted-runner.md. These tests read the workflow YAML and run the
"pick runner" script with a fake curl, so they need no network and no token.
"""
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
TISAN = WORKFLOWS / "tisan-site.yml"
DOC = ROOT / "docs" / "ops" / "self-hosted-runner.md"

FORK_GUARD = "github.event.pull_request.head.repo.full_name == github.repository"
SELF_HOSTED = '["self-hosted","linux"]'
HOSTED = '"ubuntu-latest"'


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML reads the bare key `on` as True.
    return workflow.get("on", workflow.get(True))


@pytest.mark.parametrize("path", [CI, TISAN], ids=lambda p: p.name)
def test_docs_only_changes_skip_on_push_and_pull_request(path: Path) -> None:
    triggers = _triggers(_load(path))
    assert set(triggers) == {"pull_request", "push"}
    for event in ("pull_request", "push"):
        ignored = triggers[event]["paths-ignore"]
        assert "docs/**" in ignored
        assert "**/*.md" in ignored
        # paths-ignore cannot be mixed with paths on the same event.
        assert "paths" not in triggers[event]
    assert triggers["push"]["branches"] == ["main"]


@pytest.mark.parametrize("path", [CI, TISAN], ids=lambda p: p.name)
def test_no_workflow_uses_pull_request_target(path: Path) -> None:
    # pull_request_target runs fork code with this repository's secrets.
    assert "pull_request_target" not in _triggers(_load(path))


def test_ci_keeps_job_names_and_main_push_trigger() -> None:
    text = CI.read_text(encoding="utf-8")
    jobs = _load(CI)["jobs"]
    assert set(jobs) == {"changes", "runner", "tank", "workspace", "savings-page"}
    assert "push:" in text and "branches: [main]" in text
    assert _load(CI)["permissions"] == {"contents": "read"}


def test_preflight_is_cheap_hosted_and_guarded() -> None:
    job = _load(CI)["jobs"]["runner"]
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] <= 2
    assert job["outputs"]["runner"] == "${{ steps.pick.outputs.runner }}"
    # One shell step: no checkout, no setup actions.
    assert len(job["steps"]) == 1 and "uses" not in job["steps"][0]
    # Skipped (zero minutes) unless the founder switched the runner on, and never for forks.
    assert "vars.SELF_HOSTED_RUNNER_ONLINE == 'true'" in job["if"]
    assert FORK_GUARD in job["if"]


@pytest.mark.parametrize("name", ["tank", "workspace"])
def test_main_jobs_fall_back_to_ubuntu_latest(name: str) -> None:
    job = _load(CI)["jobs"][name]
    assert job["needs"] == ["changes", "runner"]
    # Still runs when "pick runner" was skipped.
    assert "!cancelled()" in job["if"]
    runs_on = job["runs-on"]
    assert "fromJSON(needs.runner.outputs.runner)" in runs_on
    assert runs_on.rstrip(" }").endswith("|| 'ubuntu-latest'")
    # Second fork guard on the job itself, in case the preflight is ever changed.
    assert FORK_GUARD in runs_on
    # An empty output (preflight skipped) must short-circuit before fromJSON.
    assert runs_on.index("needs.runner.outputs.runner &&") < runs_on.index("fromJSON(")


def test_tisan_site_stays_on_github_hosted() -> None:
    # playwright install --with-deps needs sudo, which the self-hosted runner user must not have.
    assert _load(TISAN)["jobs"]["gate"]["runs-on"] == "ubuntu-latest"


def test_ci_carries_no_production_secrets() -> None:
    text = CI.read_text(encoding="utf-8")
    for banned in ("COOLIFY", "TANK_KEY", "TANK_API_KEY", "DATABASE_URL: postgresql://tank", "GITHUB_APP_PRIVATE_KEY"):
        assert banned not in text
    secrets = {part.split("}")[0].strip() for part in text.split("secrets.")[1:]}
    assert secrets == {"RUNNER_STATUS_TOKEN"}


def _pick_script() -> str:
    return _load(CI)["jobs"]["runner"]["steps"][0]["run"]


def _run_pick(tmp_path: Path, *, event="push", head="", switch="true", token="", api=None, curl_fails=False) -> str:
    if shutil.which("jq") is None:
        pytest.skip("jq not installed")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "curl"
    body = json.dumps(api if api is not None else {"total_count": 0, "runners": []})
    fake.write_text(
        "#!/bin/sh\n" + ("exit 22\n" if curl_fails else f"cat <<'JSON'\n{body}\nJSON\n"),
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    out = tmp_path / "output"
    out.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "GITHUB_OUTPUT": str(out),
        "SELF_HOSTED_ONLINE": switch,
        "EVENT_NAME": event,
        "HEAD_REPO": head,
        "THIS_REPO": "Tervory-AI/tervory-tank",
        "RUNNER_STATUS_TOKEN": token,
    }
    subprocess.run(["bash", "-e", "-c", _pick_script()], env=env, check=True, capture_output=True)
    lines = [line for line in out.read_text(encoding="utf-8").splitlines() if line.startswith("runner=")]
    assert len(lines) == 1
    return lines[0].removeprefix("runner=")


def _runner(status: str, labels: list[str]) -> dict:
    return {"status": status, "busy": False, "labels": [{"name": label} for label in labels]}


def test_pick_switch_off_uses_hosted(tmp_path: Path) -> None:
    assert _run_pick(tmp_path, switch="") == HOSTED
    assert _run_pick(tmp_path, switch="false") == HOSTED


def test_pick_fork_pull_request_uses_hosted(tmp_path: Path) -> None:
    online = {"runners": [_runner("online", ["self-hosted", "Linux"])]}
    assert _run_pick(tmp_path, event="pull_request", head="someone/tervory-tank", token="t", api=online) == HOSTED
    assert _run_pick(tmp_path, event="pull_request", head="someone/tervory-tank") == HOSTED


def test_pick_same_repo_pull_request_can_self_host(tmp_path: Path) -> None:
    assert _run_pick(tmp_path, event="pull_request", head="Tervory-AI/tervory-tank") == SELF_HOSTED


def test_pick_switch_on_without_token_trusts_switch(tmp_path: Path) -> None:
    assert _run_pick(tmp_path) == SELF_HOSTED


def test_pick_with_token_needs_an_online_linux_runner(tmp_path: Path) -> None:
    online = {"runners": [_runner("online", ["self-hosted", "Linux", "X64"])]}
    offline = {"runners": [_runner("offline", ["self-hosted", "Linux"])]}
    wrong_os = {"runners": [_runner("online", ["self-hosted", "macOS"])]}
    assert _run_pick(tmp_path, token="t", api=online) == SELF_HOSTED
    assert _run_pick(tmp_path, token="t", api=offline) == HOSTED
    assert _run_pick(tmp_path, token="t", api=wrong_os) == HOSTED
    assert _run_pick(tmp_path, token="t", api={"runners": []}) == HOSTED


def test_pick_api_failure_falls_back_to_hosted(tmp_path: Path) -> None:
    assert _run_pick(tmp_path, token="t", curl_fails=True) == HOSTED
    assert _run_pick(tmp_path, token="t", api={"message": "Bad credentials"}) == HOSTED


def test_runner_outputs_are_valid_json_labels() -> None:
    assert json.loads(SELF_HOSTED) == ["self-hosted", "linux"]
    assert json.loads(HOSTED) == "ubuntu-latest"
    assert SELF_HOSTED in _pick_script() and HOSTED in _pick_script()


def test_founder_doc_covers_setup_and_security() -> None:
    doc = DOC.read_text(encoding="utf-8")
    lowered = doc.lower()
    for needle in (
        "SELF_HOSTED_RUNNER_ONLINE",
        "RUNNER_STATUS_TOKEN",
        "--ephemeral",
        "--labels self-hosted,linux",
        FORK_GUARD,
        "paths-ignore",
        "required status check",
    ):
        assert needle in doc, needle
    for needle in ("unprivileged", "boston", "docker socket", "coolify", "tank key", "rootless"):
        assert needle in lowered, needle


def _scope_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ci_scope", ROOT / ".github/scripts/ci_scope.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("paths", [[], ["README.md"], ["docs/spec.json", "agents/rig/README.md"]])
def test_docs_select_no_checks(paths):
    assert _scope_module().select(paths) == {"run": False, "full": False, "tisan": False, "tests": []}


@pytest.mark.parametrize("room", ["base", "tiger", "market_lab", "radix", "rig", "tisan", "zenas"])
def test_room_changes_keep_safety_without_unrelated_room_tests(room):
    scope = _scope_module().select([f"agents/{room}/app.py", "docs/notes.md"])
    assert scope["run"] and not scope["full"]
    assert scope["tisan"] == (room == "tisan")
    for required in ("test_secrets.py", "test_agent_roles.py", "test_c10_rooms.py",
                     "test_tenant_scoping.py", "test_za_region.py", "test_zenas_schema_apply.py",
                     "test_zenas_pool_schema_postgres.py", "test_radix_business_schema.py",
                     "test_deploy_changed.py", "test_train1.py"):
        assert f"tests/{required}" in scope["tests"]
    assert any(room in path for path in scope["tests"])
    if room == "radix":
        assert "agents/radix/tests/test_live_scan.py" in scope["tests"]
    for other in ("rig", "tiger", "zenas", "tisan"):
        if other != room:
            assert f"tests/test_{other}_page.py" not in scope["tests"]


@pytest.mark.parametrize("path", ["tank/main.py", "agents/_chassis/chassis/db.py", "workspace/app/page.tsx",
                                  "agents/_template/app.py", "agents/vshop/app.py", "agents/check_isolation.sh",
                                  ".github/workflows/ci.yml", "tests/test_rig.py", "docker-compose.yml"])
def test_shared_or_unknown_paths_run_everything(path):
    assert _scope_module().select(["agents/rig/app.py", path]) == {
        "run": True, "full": True, "tisan": True, "tests": ["."]}


def test_multiple_rooms_select_union():
    module = _scope_module()
    combined = module.select(["agents/rig/app.py", "agents/tisan/app.py"])
    assert not combined["full"] and combined["tisan"]
    assert set(combined["tests"]) == set(module.select(["agents/rig/app.py"])["tests"]) | set(
        module.select(["agents/tisan/app.py"])["tests"])


def test_changed_paths_includes_deletions_and_both_sides_of_rename(tmp_path, monkeypatch):
    module = _scope_module()
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path).decode().strip()
    git("init", "-q")
    git("config", "user.email", "ci@example.invalid")
    git("config", "user.name", "CI test")
    (tmp_path / "tank").mkdir()
    (tmp_path / "tank/old.py").write_text("old content\n")
    (tmp_path / "removed.py").write_text("removed\n")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (tmp_path / "agents/rig").mkdir(parents=True)
    git("mv", "tank/old.py", "agents/rig/new.py")
    git("rm", "removed.py")
    git("commit", "-qm", "head")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setenv("DIFF_BASE", base)
    monkeypatch.setenv("DIFF_HEAD", git("rev-parse", "HEAD"))
    for event in ("pull_request", "push"):
        monkeypatch.setenv("EVENT_NAME", event)
        paths = module.changed_paths()
        assert set(paths) == {"tank/old.py", "agents/rig/new.py", "removed.py"}
        assert module.select(paths)["full"]


def test_workflows_use_scope_and_do_not_hide_failed_detection():
    ci = _load(CI)["jobs"]
    for path in (CI, TISAN):
        changes = _load(path)["jobs"]["changes"]
        assert changes["steps"][0]["with"]["fetch-depth"] == 0
        assert changes["steps"][1]["run"] == "python3 .github/scripts/ci_scope.py"
    assert "needs.changes.result == 'success'" in ci["tank"]["if"]
    assert "needs.changes.outputs.full == 'true'" in ci["workspace"]["if"]
    assert "needs.changes.outputs.tisan == 'true'" in _load(TISAN)["jobs"]["gate"]["if"]
    step = next(step for step in ci["tank"]["steps"] if step.get("name") == "Secret scan and tests")
    assert step["run"] == "python3 .github/scripts/ci_scope.py test"
    assert step["env"]["TEST_TARGETS"] == "${{ needs.changes.outputs.tests }}"


@pytest.mark.parametrize("room", ["base", "tiger", "market_lab", "radix", "rig", "tisan", "zenas"])
def test_every_test_mentioning_room_is_selected(room):
    selected = set(_scope_module().select([f"agents/{room}/app.py"])["tests"])
    mentioning = set()
    for directory in (ROOT / "tests", ROOT / "agents"):
        for path in directory.rglob("*.py"):
            if not (path.name.startswith("test_") or path.name.endswith("_test.py")):
                continue
            text = path.read_text(encoding="utf-8")
            if f"agents/{room}" in text or f"agents.{room}" in text:
                mentioning.add(str(path.relative_to(ROOT)))
    assert mentioning <= selected, sorted(mentioning - selected)


@pytest.mark.parametrize("reference", ["agents/market_lab", "agents.market_lab"])
@pytest.mark.parametrize("relative", ["tests/nested/test_unrelated.py", "agents/rig/tests/unrelated_test.py"])
def test_reference_selection_is_recursive_and_independent_of_filename(tmp_path, monkeypatch, reference, relative):
    module = _scope_module()
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text(f"# Covers {reference}\n", encoding="utf-8")
    unrelated = tmp_path / "tests/test_unmentioned.py"
    unrelated.parent.mkdir(parents=True, exist_ok=True)
    unrelated.write_text("# No room reference\n", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    assert module.select(["agents/market_lab/app.py"])["tests"] == [relative]


def test_review_reported_cross_room_tests_are_selected():
    module = _scope_module()
    for room, path in (("market_lab", "tests/test_candidate_eval_runtime.py"),
                       ("rig", "tests/test_train1.py"), ("zenas", "tests/test_train1.py"),
                       ("zenas", "tests/test_deploy_changed.py")):
        assert path in module.select([f"agents/{room}/app.py"])["tests"]
