"""Autumbra Enforce apply path — ThreatPayload objects only. Never raw logs.

Watch quarantines dirty text into ThreatPayload. Enforce reads the validated
ThreatPayload type only (not raw bytes/str/dict) and applies, approves, or
undoes shields against the fixture edge control (until a real connected hand
exists). A model is never called from Enforce. No Tank key required.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from .client_settings import ApplyMode, ClientAutumbraSettings
from .durable_shields import load_pending, persist_control, persist_pending
from .fixture_edge import DEFAULT_CONTROL, FixtureEdgeControl
from .never_block import classify_never_block
from .shields import plan_for
from .speed_budgets import stamp_budget, utc_now
from .threat_payload import ThreatAction, ThreatPayload

# Pending approvals expire if never approved (seconds). Overridable in tests.
PENDING_APPROVAL_TTL_SEC = 7 * 24 * 3600


def payload_fields_only(payload: ThreatPayload) -> dict[str, Any]:
    """The only input Enforce may see."""
    return payload.model_dump()


def _measure_raw_log_seen(payload: object) -> bool:
    """Measured at the Enforce boundary — not a hard-coded constant."""
    return not isinstance(payload, ThreatPayload)


def _persist(data_dir: Path | str | None, control: FixtureEdgeControl) -> None:
    if data_dir is None:
        return
    persist_control(data_dir, control)


def apply_from_payload(
    payload: object,
    *,
    settings: ClientAutumbraSettings,
    control: FixtureEdgeControl | None = None,
    source_credits: list[dict[str, str]] | None = None,
    auto_undo_on_health_fail: bool = True,
    data_dir: Path | str | None = None,
) -> dict[str, Any]:
    """ThreatPayload only → never-block → client shield_mode → fixture apply."""
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
        "raw_log_seen": raw_log_seen,
        "timestamp": utc_now(),
        "tenant_id": settings.tenant_id,
        "advisory_url": fields.get("advisory_url"),
        "cve_ids": list(fields.get("cve_ids") or []),
        "severity": fields.get("severity"),
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
        _persist(data_dir, edge)
    elif mode is ApplyMode.approve_each and payload.kind == "block_ip" and payload.address:
        receipt["undo"] = {"rule_id": None, "control": "fixture_edge", "pending": True}
        if data_dir is not None:
            pending = load_pending(data_dir)
            pending[receipt["id"]] = {
                "receipt_id": receipt["id"],
                "site": site,
                "address": payload.address,
                "kind": payload.kind,
                "created_at": utc_now(),
                "expires_at_epoch": time.time() + PENDING_APPROVAL_TTL_SEC,
                "payload": fields,
            }
            persist_pending(data_dir, pending)
    elif mode is ApplyMode.never:
        receipt["undo"] = {"rule_id": None, "control": "fixture_edge", "report_only": True}
    stamp_budget(receipt, stage="decision_to_shield", seconds=time.perf_counter() - t1)

    t2 = time.perf_counter()
    healthy = edge.health_check()
    stamp_budget(receipt, stage="health_check", seconds=time.perf_counter() - t2)
    receipt["health_ok"] = healthy

    if applied and auto_undo_on_health_fail and not healthy:
        # Full event→undo window starts at apply begin for budget honesty.
        undone = undo_applied(receipt, control=edge, data_dir=data_dir)
        stamp_budget(undone, stage="auto_undo_e2e", seconds=time.perf_counter() - t0)
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
    data_dir: Path | str | None = None,
) -> dict[str, Any]:
    """One-tap undo for an Enforce receipt that was applied on the fixture control."""
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
    _persist(data_dir, edge)
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
        "timestamp": utc_now(),
        "tenant_id": receipt.get("tenant_id"),
    }
    stamp_budget(out, stage="auto_undo_e2e", seconds=time.perf_counter() - t0)
    return out


def undo_from_payload(
    payload: ThreatPayload,
    *,
    control: FixtureEdgeControl | None = None,
    settings: ClientAutumbraSettings,
    data_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Undo via validated ThreatPayload door (from outside Enforce through the queue)."""
    if payload.action is not ThreatAction.undo_shield:
        raise TypeError("undo_from_payload requires action=undo_shield")
    edge = control or DEFAULT_CONTROL
    rule_id = (payload.rule_id or "").strip()
    if not rule_id and payload.prior_receipt_id and data_dir is not None:
        # Resolve rule_id from founder console / receipts on the queue box later;
        # for durable box, scan blocked by prior ref if needed.
        for row in edge.list_blocked():
            if payload.prior_receipt_id.replace("-", "")[:16] in str(row.get("ref") or ""):
                rule_id = row["rule_id"]
                break
    if not rule_id:
        return {
            "id": str(uuid4()),
            "product": "Autumbra",
            "role": "Enforce",
            "action": "undo_shield",
            "outcome": "undo_failed",
            "note": "no applied shield matched",
            "applied": False,
            "timestamp": utc_now(),
            "tenant_id": settings.tenant_id,
            **settings.receipt_stamp(),
        }
    prior = {"id": payload.prior_receipt_id, "undo": {"rule_id": rule_id}, "tenant_id": settings.tenant_id}
    try:
        out = undo_applied(prior, control=edge, data_dir=data_dir)
    except LookupError:
        return {
            "id": str(uuid4()),
            "product": "Autumbra",
            "role": "Enforce",
            "action": "undo_shield",
            "outcome": "undo_failed",
            "note": "shield not found",
            "applied": False,
            "timestamp": utc_now(),
            "tenant_id": settings.tenant_id,
            **settings.receipt_stamp(),
        }
    out["action"] = "undo_shield"
    out["tenant_id"] = settings.tenant_id
    out.update(settings.receipt_stamp())
    return out


def approve_pending(
    payload: ThreatPayload,
    *,
    control: FixtureEdgeControl | None = None,
    settings: ClientAutumbraSettings,
    data_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Apply a pending shield on approval (ThreatPayload door)."""
    if payload.action is not ThreatAction.approve_shield:
        raise TypeError("approve_pending requires action=approve_shield")
    if data_dir is None:
        return {
            "id": str(uuid4()),
            "product": "Autumbra",
            "role": "Enforce",
            "action": "approve_shield",
            "outcome": "approve_failed",
            "note": "no durable pending store",
            "applied": False,
            "timestamp": utc_now(),
            "tenant_id": settings.tenant_id,
            **settings.receipt_stamp(),
        }
    pending = load_pending(data_dir)
    rid = str(payload.prior_receipt_id or "")
    row = pending.pop(rid, None)
    if row is None:
        return {
            "id": str(uuid4()),
            "product": "Autumbra",
            "role": "Enforce",
            "action": "approve_shield",
            "outcome": "approve_failed",
            "note": "pending shield not found or already expired",
            "applied": False,
            "timestamp": utc_now(),
            "tenant_id": settings.tenant_id,
            **settings.receipt_stamp(),
        }
    if float(row.get("expires_at_epoch") or 0) < time.time():
        persist_pending(data_dir, pending)
        return {
            "id": str(uuid4()),
            "product": "Autumbra",
            "role": "Enforce",
            "action": "approve_shield",
            "outcome": "expired",
            "note": "pending shield expired before approval",
            "prior_receipt_id": rid,
            "applied": False,
            "timestamp": utc_now(),
            "tenant_id": settings.tenant_id,
            **settings.receipt_stamp(),
        }
    edge = control or DEFAULT_CONTROL
    address = str(row.get("address") or "")
    site = str(row.get("site") or payload.site)
    ref = f"approve-{rid.replace('-', '')[:16]}"
    applied_row = edge.apply_block_ip(site=site, address=address, ref=ref)
    _persist(data_dir, edge)
    persist_pending(data_dir, pending)
    return {
        "id": str(uuid4()),
        "product": "Autumbra",
        "role": "Enforce",
        "action": "approve_shield",
        "outcome": "applied",
        "applied": True,
        "applied_record": applied_row,
        "undo": {"rule_id": applied_row["rule_id"], "control": "fixture_edge"},
        "prior_receipt_id": rid,
        "address": address,
        "site": site,
        "timestamp": utc_now(),
        "tenant_id": settings.tenant_id,
        "control": "fixture_edge",
        **settings.receipt_stamp(),
    }


def expire_pending_approvals(
    *,
    data_dir: Path | str,
    settings: ClientAutumbraSettings,
    queue_write: Any | None = None,
) -> list[dict[str, Any]]:
    """Expire unapproved pending shields with a receipt each."""
    pending = load_pending(data_dir)
    now = time.time()
    expired: list[dict[str, Any]] = []
    keep: dict[str, dict[str, Any]] = {}
    for rid, row in pending.items():
        if float(row.get("expires_at_epoch") or 0) < now:
            receipt = {
                "id": str(uuid4()),
                "product": "Autumbra",
                "role": "Enforce",
                "action": "approve_shield",
                "outcome": "expired",
                "note": "pending shield expired; never approved",
                "prior_receipt_id": rid,
                "address": row.get("address"),
                "site": row.get("site"),
                "applied": False,
                "timestamp": utc_now(),
                "tenant_id": settings.tenant_id,
                **settings.receipt_stamp(),
            }
            expired.append(receipt)
            if queue_write is not None:
                queue_write(receipt)
        else:
            keep[rid] = row
    persist_pending(data_dir, keep)
    return expired
