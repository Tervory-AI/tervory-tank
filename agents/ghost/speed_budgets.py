"""Speed budgets for Autumbra shields. Model opinion never sits on the critical path."""
from __future__ import annotations

from typing import Any

# Seconds.
EVENT_TO_DECISION_RULE = 2.0
DECISION_TO_SHIELD = 10.0
HEALTH_CHECK = 30.0
AUTO_UNDO_E2E = 60.0


def stamp_budget(receipt: dict[str, Any], *, stage: str, seconds: float) -> dict[str, Any]:
    budgets = dict(receipt.get("budgets") or {})
    budgets[stage] = {"seconds": float(seconds), "at": stage}
    receipt["budgets"] = budgets
    return receipt


def budgets_ok(receipt: dict[str, Any]) -> tuple[bool, list[str]]:
    """Assert fixture/live receipts meet the product budgets."""
    budgets = receipt.get("budgets") or {}
    fails: list[str] = []
    checks = (
        ("event_to_decision", EVENT_TO_DECISION_RULE),
        ("decision_to_shield", DECISION_TO_SHIELD),
        ("health_check", HEALTH_CHECK),
        ("auto_undo_e2e", AUTO_UNDO_E2E),
    )
    for key, limit in checks:
        entry = budgets.get(key)
        if entry is None:
            continue  # Only assert stages that ran.
        seconds = float(entry.get("seconds", 9999))
        if seconds > limit:
            fails.append(f"{key} {seconds}s > {limit}s")
    return (not fails), fails
