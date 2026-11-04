"""Each test file the main offline suite skips is really run by the side workflow named for it.

offline_suite.SIDE_WORKFLOW lists, by name, test files that rig-forge.yml or tenant-rls.yml
already run, so the main suite no longer runs them a second time. These checks read the
workflow YAML literally, so a file cannot drop out of the main suite without its side
workflow running it, and no file ends up tested by neither. No network, no token.
"""
import importlib.util
import re
import shlex
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# Files the main suite never ran because they skip themselves outside their own job. Only
# these may sit outside their side workflow's pull_request paths filter.
SELF_SKIPPING = {
    "tests/autumbra_a2/test_compose_probe.py":
        "pytestmark = pytest.mark.skipif(os.environ.get('AUTUMBRA_A2_CI_PROBE') != '1'",
}


def _suite():
    spec = importlib.util.spec_from_file_location("offline_suite", ROOT / ".github/scripts/offline_suite.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SUITE = _suite()


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    return workflow.get("on", workflow.get(True))


def _pytest_targets(run: str) -> set[str]:
    """Test paths given to every `python -m pytest` command in a step's run script."""
    targets = set()
    script = run.replace("\\\n", " ")
    for line in script.splitlines():
        words = shlex.split(line, comments=True)
        for i, word in enumerate(words):
            if word == "pytest" and i and words[i - 1] == "-m":
                for arg in words[i + 1:]:
                    if arg in ("|", "2>&1", "&&", ";") or arg.startswith((">", "2>")):
                        break
                    if not arg.startswith("-") and arg.endswith(".py"):
                        targets.add(arg)
    return targets


def _matches(pattern: str, path: str) -> bool:
    regex = re.escape(pattern).replace(r"\*\*", "\0").replace(r"\*", "[^/]*").replace("\0", ".*")
    return re.fullmatch(regex, path) is not None


def _split(owner: str) -> tuple[str, str]:
    workflow, job = (part.strip() for part in owner.split(":"))
    return workflow, job


def test_skip_list_is_exact_file_names():
    assert SUITE.SIDE_WORKFLOW, "the skip list is empty"
    for path in SUITE.SIDE_WORKFLOW:
        assert not any(c in path for c in "*?[") and path.endswith(".py"), path
        assert (ROOT / path).is_file(), path
        assert not any(path == p or path.startswith(p + "/") for p in SUITE.ALONE + SUITE.ELSEWHERE), path


def test_main_run_leaves_out_every_skipped_file():
    ignores = SUITE.main_ignores()
    for path in SUITE.SIDE_WORKFLOW:
        assert f"--ignore={path}" in ignores
    # Nothing else was added: the isolated groups and ELSEWHERE are unchanged.
    assert set(ignores) == {f"--ignore={p}" for p in [*SUITE.ALONE, *SUITE.ELSEWHERE, *SUITE.SIDE_WORKFLOW]}


@pytest.mark.parametrize("path", sorted(SUITE.SIDE_WORKFLOW))
def test_owning_job_runs_the_file(path):
    workflow_name, job_name = _split(SUITE.SIDE_WORKFLOW[path])
    job = _workflow(workflow_name)["jobs"][job_name]
    run = set()
    for step in job["steps"]:
        if "run" in step:
            run |= _pytest_targets(step["run"])
    assert path in run, f"{workflow_name} job {job_name} does not run {path}: {sorted(run)}"


@pytest.mark.parametrize("path", sorted(SUITE.SIDE_WORKFLOW))
def test_owning_workflow_runs_on_pull_requests_that_change_the_file(path):
    workflow_name, _ = _split(SUITE.SIDE_WORKFLOW[path])
    pull_request = _triggers(_workflow(workflow_name))["pull_request"] or {}
    paths = pull_request.get("paths")
    if path in SELF_SKIPPING:
        assert SELF_SKIPPING[path] in (ROOT / path).read_text(encoding="utf-8")
        return
    assert paths is None or any(_matches(p, path) for p in paths), (workflow_name, path, paths)


def test_pytest_target_parser_reads_the_real_commands():
    assert _pytest_targets("python -m pytest -q -s tests/a.py tests/b.py 2>&1 | tee x.log") == {"tests/a.py", "tests/b.py"}
    assert _pytest_targets("tool python -m pytest -q \\\n  tests/c.py\n") == {"tests/c.py"}
    assert _pytest_targets("python -m pytest -q --junitxml=r.xml") == set()
