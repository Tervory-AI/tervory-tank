"""Autumbra Enforce apply path — ThreatPayload objects only. Never raw logs.

Watch quarantines dirty text into ThreatPayload. Enforce reads the validated
ThreatPayload type only (not raw bytes/str/dict) and applies or undoes shields
against the fixture edge control (until a real connected hand exists).
A model is never called from Enforce. No Tank key required.
"""
from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from .client_settings import ApplyMode, ClientAutumbraSettings
from .fixture_edge import DEFAULT_CONTROL, FixtureEdgeControl
from .never_block import classify_never_block
from .shields import plan_for
from .speed_budgets import stamp_budget
from .threat_payload import ThreatPayload


def payload_fields_only(payload: ThreatPayload) -> dict[str, Any]:
    """The only input Enforce may see."""
    return payload.model_dump()


def _measure_raw_log_seen(payload: object) -> bool:
    """Measured at the Enforce boundary — not a hard-coded constant.

    True only when the caller handed something other than a ThreatPayload
    instance (raw bytes/str/dict/log). That path is refused before apply.
    """
    return not isinstance(payload, ThreatPayload)


def apply_from_payload(
    payload: object,
    *,
    settings: ClientAutumbraSettings,
    control: FixtureEdgeControl | None = None,
    source_credits: list[dict[str, str]] | None = None,
    auto_undo_on_health_fail: bool = True,
) -> dict[str, Any]:
    """ThreatPayload only → never-block → client shield_mode → fixture apply.

    Speed budgets are measured here with perf_counter. Live provider APIs stay
    behind a real connected hand; until then the fixture control mutates state
    so applied/undo are real. Failed health check auto-undoes an applied shield.
    """
    t0 = time.perf_counter()
    raw_log_seen = _measure_raw_log_seen(payload)
    if raw_log_seen:
        raise TypeError(
            "Enforce accepts ThreatPayload only. Quarantine dirty input in Watch first."
        )
    assert isinstance(payload, ThreatPayload)

    fields = payload_fields_only(payload)
    receipt: dict[str, Any] = {
        "id": str(uuid4()),
        "product": "Autumbra",
        "role": "Enforce",
        "action": fields.get("action"),
        "site": fields.get("site"),
        "kind": fields.get("kind"),
        "address": fields.get("address"),
        "input_fields": sorted(fields.keys()),
        "raw_log_seen": raw_log_seen,  # measured False for ThreatPayload
        **settings.receipt_stamp(),
    }
    if source_credits:
        receipt["sources"] = source_credits
        receipt["intel_via"] = "Market Lab"

    decision_seconds = time.perf_counter() - t0
    stamp_budget(receipt, stage="event_to_decision", seconds=decision_seconds)

    if payload.kind == "block_ip":
        address = payload.address or ""
        why = classify_never_block(address, client_own_cidrs=settings.own_cidrs)
        if why:
            receipt["outcome"] = "refused_never_block"
            receipt["note"] = f"never-block: {why}"
            receipt["applied"] = False
            return receipt

    mode = settings.shield_mode
    receipt["outcome"] = {
        ApplyMode.never: "report_only",
        ApplyMode.approve_each: "awaiting_approval",
        ApplyMode.auto_when_checks_pass: "auto_apply",
    }[mode]

    site = payload.site
    ref = f"enforce-{receipt['id'].replace('-', '')[:16]}"
    if payload.kind:
        receipt["plan"] = plan_for(
            payload.kind,
            site if "." in site else site,
            payload.path,
            ref=ref,
            address=payload.address,
        )

    edge = control or DEFAULT_CONTROL
    t1 = time.perf_counter()
    applied = False
    if (
        mode is ApplyMode.auto_when_checks_pass
        and payload.kind == "block_ip"
        and payload.address
    ):
        row = edge.apply_block_ip(site=site, address=payload.address, ref=ref)
        receipt["applied_record"] = row
        receipt["undo"] = {"rule_id": row["rule_id"], "control": "fixture_edge"}
        applied = True
        receipt["outcome"] = "applied"
    elif mode is ApplyMode.approve_each and payload.kind == "block_ip" and payload.address:
        # Still a real plan against the fixture; not applied until approved.
        receipt["undo"] = {"rule_id": None, "control": "fixture_edge", "pending": True}
    elif mode is ApplyMode.never:
        receipt["undo"] = {"rule_id": None, "control": "fixture_edge", "report_only": True}
    stamp_budget(receipt, stage="decision_to_shield", seconds=time.perf_counter() - t1)

    t2 = time.perf_counter()
    healthy = edge.health_check()
    stamp_budget(receipt, stage="health_check", seconds=time.perf_counter() - t2)
    receipt["health_ok"] = healthy

    if applied and auto_undo_on_health_fail and not healthy:
        t3 = time.perf_counter()
        undone = undo_applied(receipt, control=edge)
        stamp_budget(undone, stage="auto_undo_e2e", seconds=time.perf_counter() - t3)
        receipt["outcome"] = "auto_undone_health_failed"
        receipt["applied"] = False
        receipt["auto_undo"] = undone
        receipt["budgets"] = {
            **(receipt.get("budgets") or {}),
            **(undone.get("budgets") or {}),
        }
        receipt["control"] = "fixture_edge"
        return receipt

    receipt["applied"] = applied
    receipt["control"] = "fixture_edge"
    return receipt


def undo_applied(
    receipt: dict[str, Any],
    *,
    control: FixtureEdgeControl | None = None,
) -> dict[str, Any]:
    """One-tap undo for an Enforce receipt that was applied on the fixture control.

    Callers hand the prior receipt object from apply — never raw HTTP bytes.
    """
    t0 = time.perf_counter()
    if not isinstance(receipt, dict):
        raise TypeError("undo_applied accepts the prior Enforce receipt dict only.")
    undo = receipt.get("undo") or {}
    if not isinstance(undo, dict):
        raise TypeError("undo_applied: receipt.undo must be a dict.")
    rule_id = undo.get("rule_id")
    if not rule_id:
        raise LookupError("no applied shield to undo")
    edge = control or DEFAULT_CONTROL
    row = edge.undo(str(rule_id))
    out = {
        "id": str(uuid4()),
        "product": "Autumbra",
        "role": "Enforce",
        "action": "undo",
        "outcome": "undone",
        "undone": row,
        "prior_receipt_id": receipt.get("id"),
        "applied": False,
        "control": "fixture_edge",
    }
    stamp_budget(out, stage="auto_undo_e2e", seconds=time.perf_counter() - t0)
    return out
