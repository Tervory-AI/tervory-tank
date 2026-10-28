"""What happens inside one sealed container: clone, Aider through Tank, draft pull request."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from workers.briefs import allowed_rules, outside_rules
from workers.git_guard import clone_command, push_command
from workers.github_api import ci_state, draft_body, ready_body
from workers.github_app import assert_push_branch
from workers.issues import WorkerIssue

METADATA = "/opt/tervory/workers/task/openai-tank.metadata.json"
SETTINGS_YML = "/opt/tervory/workers/task/openai-tank.settings.yml"
PROXY = "http://127.0.0.1:8765/v1"


@dataclass
class Outcome:
    status: str
    pr_url: str | None = None
    pr_number: int | None = None
    node_id: str | None = None
    sha: str | None = None
    minutes: float = 0
    cost_usd: float = 0
    ledger_ids: list[str] = field(default_factory=list)
    runtime: str = ""
    detail: str = ""

    def line(self) -> str:
        payload = {
            "status": self.status,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "node_id": self.node_id,
            "sha": self.sha,
            "minutes": round(self.minutes, 2),
            "cost_usd": round(self.cost_usd, 6),
            "ledger_ids": self.ledger_ids,
            "runtime": self.runtime,
            "detail": self.detail,
        }
        return "WORKER_RESULT " + json.dumps(payload, sort_keys=True)


def parse_result(stdout: str) -> Outcome | None:
    for line in reversed(stdout.splitlines()):
        if line.startswith("WORKER_RESULT "):
            data = json.loads(line[len("WORKER_RESULT ") :])
            return Outcome(
                status=str(data.get("status") or "failed"),
                pr_url=data.get("pr_url"),
                pr_number=data.get("pr_number"),
                node_id=data.get("node_id"),
                sha=data.get("sha"),
                minutes=float(data.get("minutes") or 0),
                cost_usd=float(data.get("cost_usd") or 0),
                ledger_ids=list(data.get("ledger_ids") or []),
                runtime=str(data.get("runtime") or ""),
                detail=str(data.get("detail") or ""),
            )
    return None


def aider_argv(message_file: str, files: list[str], *, proxy_port: int) -> list[str]:
    argv = [
        "aider",
        "--model",
        "openai/tank",
        "--weak-model",
        "openai/tank",
        "--editor-model",
        "openai/tank",
        "--openai-api-base",
        f"http://127.0.0.1:{proxy_port}/v1",
        "--edit-format",
        "whole",
        "--yes-always",
        "--no-auto-commits",
        "--no-dirty-commits",
        "--no-stream",
        "--no-pretty",
        "--no-analytics",
        "--analytics-disable",
        "--no-check-update",
        "--no-show-release-notes",
        "--no-show-model-warnings",
        "--no-suggest-shell-commands",
        "--no-auto-lint",
        "--no-auto-test",
        "--no-browser",
        "--no-gui",
        "--map-tokens",
        "0",
        "--model-metadata-file",
        METADATA,
        "--model-settings-file",
        SETTINGS_YML,
        "--message-file",
        message_file,
    ]
    for path in files:
        if path_ok(path):
            argv.extend(["--file", path])
    blob = " ".join(argv)
    for banned in ("api.openai.com", "anthropic.com", "openrouter.ai", "--openai-api-key", "sk-"):
        if banned in blob:
            raise RuntimeError("aider would not stay on Tank")
    return argv


def path_ok(path: str) -> bool:
    return bool(path) and ".." not in path.split("/") and not path.startswith("/")


def instruction(issue: WorkerIssue, rules: list[str]) -> str:
    lines = [
        f"Do the work described in {issue.brief}.",
        "Change only these paths:",
        *[f"- {rule}" for rule in rules],
        "Do not add a provider, a key, or a paid service.",
        "Do not push and do not merge.",
    ]
    return "\n".join(lines) + "\n"


def command_instruction(markdown: str, rules: list[str], followups: tuple[dict, ...]) -> str:
    return (
        "Read AGENTS.md and docs/cursor/CONTEXT.md. Complete this confirmed build brief:\n\n"
        + markdown + "\n\nFollow-ups, in order (continue the existing work):\n"
        + "\n".join(str(reply["followup_text"]) for reply in followups)
        + "\n\nChange only these approved paths:\n"
        + "\n".join(f"- {rule}" for rule in rules)
        + "\nDo not add a provider, key, or paid service. Do not push, merge, or deploy.\n"
    )


def existing_files(root: Path, rules: list[str]) -> list[str]:
    """Pass concrete files that already exist. Directories are enforced after the edit."""
    found: list[str] = []
    for rule in rules:
        if rule.endswith("/"):
            continue
        if (root / rule).is_file():
            found.append(rule)
    return found


def changed_paths(diff_names: str, untracked: str) -> list[str]:
    found: list[str] = []
    for blob in (diff_names, untracked):
        for line in blob.splitlines():
            path = line.strip()
            if path and path not in found:
                found.append(path)
    return found


def commit_paths(changed: list[str], rules: list[str]) -> list[str]:
    stray = outside_rules(changed, rules)
    if stray:
        raise RuntimeError("edit left the brief's file list: " + ", ".join(stray))
    if not changed:
        raise RuntimeError("no changes")
    return changed


def git_identity() -> list[list[str]]:
    return [
        ["git", "config", "user.name", "Tervory Worker"],
        ["git", "config", "user.email", "worker@tervory.invalid"],
    ]


def branch_commands(repo: str, directory: str, branch: str) -> list[list[str]]:
    assert_push_branch(branch)
    return [
        clone_command(repo, directory),
        ["git", "checkout", "-b", branch],
        *git_identity(),
    ]


def publish_commands(branch: str, paths: list[str]) -> list[list[str]]:
    assert_push_branch(branch)
    add = ["git", "add", "--", *paths]
    commit = ["git", "commit", "-m", f"Worker edit on {branch}"]
    return [add, commit, push_command(branch)]


def load_rules(brief_path: Path) -> list[str]:
    rules = allowed_rules(brief_path.read_text(encoding="utf-8"))
    if not rules:
        raise RuntimeError("the brief does not list files the worker may change")
    return rules


def finish_from_ci(
    *,
    check_runs: list[dict[str, object]],
    combined: str,
    summary: str,
) -> tuple[str, str | None]:
    """Return (state, body). Body is set only when CI is green and the PR may leave draft."""
    state = ci_state(check_runs, combined)
    if state != "green":
        return state, None
    return "green", ready_body(summary)


def summary_for(issue: WorkerIssue, paths: list[str], minutes: float, cost: float) -> str:
    changed = ", ".join(paths) if paths else "no files"
    return (
        f"Issue #{issue.number} ({issue.brief}) changed {changed}. "
        f"It took {minutes:.1f} minutes and the model cost was ${cost:.6f}. "
        "CI was green. This pull request is ready for review. It is not merged."
    )


def draft_for(issue: WorkerIssue) -> str:
    return draft_body(issue)
