"""Wraith stub: schema-gated dry enforcer. Disabled unless GHOST_WRAITH_ENABLED=1.

This is not a Dual-LLM bunker and not live edge control. It only accepts a
validated ThreatPayload and returns a would-enforce dry response. No Cloudflare
calls, no auto-patch, no host changes. Founder Shield tap remains the only path
that can change the edge (via Ghost Shields Up).
"""
from __future__ import annotations

import os

from .threat_payload import ThreatAction, ThreatPayload

ENABLED_ENV = "GHOST_WRAITH_ENABLED"
# Also honour WRAITH_ENABLED as an alias (same default OFF).
ENABLED_ALIASES = (ENABLED_ENV, "WRAITH_ENABLED")


def enabled() -> bool:
    for name in ENABLED_ALIASES:
        if os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}:
            return True
    return False


def would_enforce(payload: ThreatPayload) -> dict:
    """Dry response only. Caller must already have validated via accept_threat_payload."""
    if not enabled():
        raise RuntimeError("Wraith is disabled.")
    return {
        "enforced": False,
        "would_enforce": True,
        "action": payload.action.value,
        "site": payload.site,
        "kind": payload.kind,
        "match_id": payload.match_id,
        "severity": payload.severity.value,
        "note": (
            "Dry stub only. No edge change. No auto-patch. "
            "Founder must still tap Shield on Ghost proposals."
        ),
        "flag": ENABLED_ENV,
    }
