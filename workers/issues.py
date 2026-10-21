"""An issue becomes a task when it has the label worker and names one brief."""

from __future__ import annotations

import re
from dataclasses import dataclass

LABEL = "worker"
# Added by the service after MAX_FAILURES failures in a row. Remove it to retry the task.
FAILED_LABEL = "worker-failed"
BRIEF_RE = re.compile(r"(?<![\w./-])docs/cursor/([A-Za-z0-9][A-Za-z0-9._-]{0,120}\.md)\b")
BRANCH_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class WorkerIssue:
    number: int
    title: str
    body: str
    brief: str

    @property
    def stem(self) -> str:
        return self.brief.rsplit("/", 1)[-1][: -len(".md")]

    @property
    def branch(self) -> str:
        stem = BRANCH_STEM_RE.sub("-", self.stem).strip("-") or "brief"
        return f"worker/{stem}-{self.number}"


def briefs_named(body: str) -> list[str]:
    found: list[str] = []
    for match in BRIEF_RE.finditer(body or ""):
        path = match.group(0)
        if ".." in path.split("/"):
            continue
        if path not in found:
            found.append(path)
    return found


def issue_from_api(payload: dict[str, object]) -> WorkerIssue | None:
    """Return a task, or None when this issue is not one worker brief."""
    if "pull_request" in payload:
        return None
    labels = payload.get("labels") or []
    names: list[str] = []
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict) and isinstance(label.get("name"), str):
                names.append(label["name"])
            elif isinstance(label, str):
                names.append(label)
    if LABEL not in names or FAILED_LABEL in names:
        return None
    number = payload.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        return None
    body = payload.get("body") if isinstance(payload.get("body"), str) else ""
    briefs = briefs_named(body)
    if len(briefs) != 1:
        return None
    title = payload.get("title") if isinstance(payload.get("title"), str) else f"Issue {number}"
    return WorkerIssue(number=number, title=title.strip() or f"Issue {number}", body=body, brief=briefs[0])


def needs_brief_comment(payload: dict[str, object]) -> bool:
    """Labelled, not a pull request, and not exactly one brief. The service comments once."""
    if "pull_request" in payload:
        return False
    labels = payload.get("labels") or []
    names = []
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict) and isinstance(label.get("name"), str):
                names.append(label["name"])
    if LABEL not in names:
        return False
    body = payload.get("body") if isinstance(payload.get("body"), str) else ""
    return len(briefs_named(body)) != 1
