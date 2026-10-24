"""rig-forge.yml uses the CI-2 concurrency rule: cancel superseded PR runs, never main.

Self-contained on purpose: #257 adds the shared helpers to tests/test_ci_minutes_workflows.py,
and this branch does not include #257 yet. Once both are merged, this can fold into that
file's parametrised concurrency tests. Reads the YAML only; no network, no token.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FORGE = ROOT / ".github" / "workflows" / "rig-forge.yml"
GROUP = "${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}"
CANCEL = "${{ github.event_name == 'pull_request' }}"


def _workflow() -> dict:
    return yaml.safe_load(FORGE.read_text(encoding="utf-8"))


class _Ctx(dict):
    """Attribute access for a GitHub expression context; missing keys are falsy."""

    def __getattr__(self, name):
        value = self.get(name, _Ctx())
        return _Ctx(value) if isinstance(value, dict) else value


def _eval(expression: str, github: dict) -> object:
    """Evaluate the tiny subset used here (==, ||), same approach as #257's tests."""
    body = expression.strip()
    assert body.startswith("${{") and body.endswith("}}"), expression
    body = body[3:-2].strip().replace("||", " or ")
    return eval(body, {"__builtins__": {}}, {"github": _Ctx(github)})  # noqa: S307 - test-only, our own YAML


def _github(event: str, *, pr: int | None = None, run_id: str = "1") -> dict:
    ctx = {"workflow": "rig-forge", "event_name": event, "run_id": run_id, "event": {}}
    if pr is not None:
        ctx["event"] = {"pull_request": {"number": pr}}
    return ctx


def _group(github: dict) -> str:
    left, right = _workflow()["concurrency"]["group"].split("}}-${{")
    return f"{_eval(left + '}}', github)}-{_eval('${{' + right, github)}"


def _cancels(github: dict) -> bool:
    return _eval(_workflow()["concurrency"]["cancel-in-progress"], github) is True


def test_rig_forge_has_the_ci2_concurrency_block() -> None:
    workflow = _workflow()
    assert workflow["name"] == "rig-forge"
    assert workflow["concurrency"] == {"group": GROUP, "cancel-in-progress": CANCEL}
    for name, job in workflow["jobs"].items():
        assert "concurrency" not in job, name


def test_rig_forge_second_pr_push_cancels_first_but_other_prs_and_main_are_safe() -> None:
    first, second = _github("pull_request", pr=254, run_id="1"), _github("pull_request", pr=254, run_id="2")
    assert _group(first) == _group(second) == "rig-forge-254"
    assert _cancels(second)
    assert _group(_github("pull_request", pr=255)) != _group(first)
    # Any non-PR run (main push, dispatch) gets its own group and is never cancelled.
    main_a, main_b = _github("push", run_id="9001"), _github("push", run_id="9002")
    assert not _cancels(main_a) and not _cancels(main_b)
    assert _group(main_a) == "rig-forge-9001" != _group(main_b)
