"""Durable shield table for one client's Enforce box.

Shields survive Enforce restart. Held under DATA_DIR. A restart that cannot
restore a previously applied shield writes a receipt — never a silent drop.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fixture_edge import FixtureEdgeControl


SHIELDS_FILE = "shields.json"
PENDING_FILE = "pending_approvals.json"


def shields_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / SHIELDS_FILE


def pending_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / PENDING_FILE


def load_control(data_dir: Path | str, *, tenant_id: str, site: str = "") -> FixtureEdgeControl:
    """Build a FixtureEdgeControl restored from the client's durable box."""
    control = FixtureEdgeControl(tenant_id=tenant_id, site=site)
    path = shields_path(data_dir)
    if not path.exists():
        return control
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return control
    blocked = raw.get("blocked") if isinstance(raw, dict) else None
    if isinstance(blocked, dict):
        for rule_id, row in blocked.items():
            if isinstance(row, dict) and isinstance(rule_id, str):
                control.blocked[rule_id] = dict(row)
    if isinstance(raw, dict) and "healthy" in raw:
        control.healthy = bool(raw["healthy"])
    return control


def persist_control(data_dir: Path | str, control: FixtureEdgeControl) -> Path:
    path = shields_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tenant_id": control.tenant_id,
        "site": control.site,
        "healthy": control.healthy,
        "blocked": {k: dict(v) for k, v in control.blocked.items()},
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def load_pending(data_dir: Path | str) -> dict[str, dict[str, Any]]:
    path = pending_path(data_dir)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}


def persist_pending(data_dir: Path | str, pending: dict[str, dict[str, Any]]) -> Path:
    path = pending_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pending, sort_keys=True, default=str), encoding="utf-8")
    return path


def restart_drop_receipts(
    *,
    prior_blocked: dict[str, dict[str, Any]],
    restored_blocked: dict[str, dict[str, Any]],
    tenant_id: str,
) -> list[dict[str, Any]]:
    """If a restart lost shields that were durable, emit a receipt per lost shield."""
    from datetime import datetime, timezone
    from uuid import uuid4

    lost = set(prior_blocked) - set(restored_blocked)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[dict[str, Any]] = []
    for rule_id in sorted(lost):
        row = prior_blocked[rule_id]
        out.append({
            "id": str(uuid4()),
            "product": "Autumbra",
            "role": "Enforce",
            "kind": "restart_shield_drop",
            "outcome": "dropped_on_restart",
            "timestamp": now,
            "tenant_id": tenant_id,
            "rule_id": rule_id,
            "address": row.get("address"),
            "site": row.get("site"),
            "note": "Shield could not be restored after Enforce restart.",
        })
    return out
