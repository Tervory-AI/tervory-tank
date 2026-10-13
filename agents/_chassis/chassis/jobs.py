"""Job status decisions shared by the worker and the unit tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class JobContext:
    agent: str
    tenant_id: str
    job_id: str
    kind: str
    input: dict[str, Any]
    files: Any
    tank: Any
    memory: Any
    browser: Any


def decide_timeout(
    *,
    status: str,
    started_at: datetime | None,
    now: datetime,
    timeout_s: int,
    attempts: int,
    max_attempts: int,
) -> str | None:
    """A running job older than its timeout goes back to queued.

    Returns the new status, or None when the job should keep running.
    Once attempts are used up it is failed, so a stuck job cannot loop forever.
    """
    if status != "running":
        return None
    if started_at is not None:
        elapsed = (now - started_at).total_seconds()
        if elapsed <= timeout_s:
            return None
    if attempts < max_attempts:
        return "queued"
    return "failed"


def decide_retry(*, attempts: int, max_attempts: int) -> str:
    """After a failed attempt (attempts already counted), queue another or stop."""
    if attempts < max_attempts:
        return "queued"
    return "failed"
