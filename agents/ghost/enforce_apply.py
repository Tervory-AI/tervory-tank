"""Autumbra Enforce apply path — ThreatPayload fields only. Never raw logs.

Watch quarantines dirty text into ThreatPayload. Enforce reads the validated
ThreatPayload type only (not raw bytes/str) and applies (or dry-plans) shields
according to the client's shield_mode. A model is never called from Enforce.
Market Lab source credits may be stamped on the receipt; Autumbra does not own
the feed registry.
"""
from __future__ import annotations

import os
from typing import Any

from .client_settings import ApplyMode, ClientAutumbraSettings
from .never_block import classify_never_block
from .shields import plan_for
from .speed_budgets import stamp_budget
from .threat_payload import ThreatPayload

ENFORCE_TOKEN_ENV = "AUTUMBRA_EDGE_CREDENTIAL"


def enforce_token_configured() -> bool:
    return bool(os.environ.get(ENFORCE_TOKEN_ENV, "").strip())


def payload_fields_only(payload: ThreatPayload) -> dict[str, Any]:
    """The only input Enforce may see."""
    return payload.model_dump()


def apply_from_payload(
    payload: ThreatPayload,
    *,
    settings: ClientAutumbraSettings,
    source_credits: list[dict[str, str]] | None = None,
    decision_seconds: float = 0.01,
    apply_seconds: float = 0.01,
    health_seconds: float = 0.01,
) -> dict[str, Any]:
    """ThreatPayload only → never-block → client shield_mode → dry plan.

    Live edge calls stay behind the Enforce token env (empty = dry). This
    function never accepts raw logs, bytes, or unvalidated dicts — Watch must
    hand a ThreatPayload. Optional source_credits come from Market Lab consume.
    """
    if not isinstance(payload, ThreatPayload):
        raise TypeError(
            "Enforce accepts ThreatPayload only. Quarantine dirty input in Watch first."
        )

    fields = payload_fields_only(payload)
    receipt: dict[str, Any] = {
        "product": "Autumbra",
        "role": "Enforce",
        "action": fields.get("action"),
        "site": fields.get("site"),
        "kind": fields.get("kind"),
        "address": fields.get("address"),
        "input_fields": sorted(fields.keys()),
        "raw_log_seen": False,
        **settings.receipt_stamp(),
    }
    if source_credits:
        receipt["sources"] = source_credits
        receipt["intel_via"] = "Market Lab"
    stamp_budget(receipt, stage="event_to_decision", seconds=decision_seconds)

    if payload.kind == "block_ip":
        address = payload.address or ""
        why = classify_never_block(address, client_own_cidrs=settings.own_cidrs)
        if why:
            receipt["outcome"] = "refused_never_block"
            receipt["note"] = f"never-block: {why}"
            return receipt

    mode = settings.shield_mode
    receipt["outcome"] = {
        ApplyMode.never: "report_only",
        ApplyMode.approve_each: "awaiting_approval",
        ApplyMode.auto_when_checks_pass: "auto_apply_planned",
    }[mode]

    if payload.kind:
        receipt["plan"] = plan_for(
            payload.kind,
            payload.site if "." in payload.site else payload.site,
            payload.path,
            ref="enforce-dry",
            address=payload.address,
        )
    stamp_budget(receipt, stage="decision_to_shield", seconds=apply_seconds)
    stamp_budget(receipt, stage="health_check", seconds=health_seconds)
    receipt["live_token_configured"] = enforce_token_configured()
    receipt["applied"] = False  # Live apply remains founder/client gated.
    return receipt
