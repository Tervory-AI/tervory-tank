"""DEPRECATED intel path — Autumbra does not own a feed list.

Founder correction (wins): Market Lab is the intel backend. Do not build a feed
list or source registry in Autumbra. New code must use
`agents.ghost.market_lab_intel` to consume Market Lab IOC bundles and name
sources on receipts.

This module remains only as a thin compatibility shim for older tests/routes
and returns an empty public list with a pointer to Market Lab.
"""
from __future__ import annotations

from typing import Any

from .market_lab_intel import source_credits_on_receipt

# Empty on purpose — Autumbra does not maintain SOURCES.
SOURCES: list[dict[str, Any]] = []

DEPRECATION = (
    "Intel backend is Market Lab. Autumbra consumes ML IOC bundles and names "
    "the source on the receipt. Clients never see a feed list."
)


def registry_public() -> list[dict[str, Any]]:
    """No Autumbra-owned feed list. Empty by design."""
    return []


def source_by_id(source_id: str) -> dict[str, Any] | None:
    return None


def credit_for(source_ids: list[str]) -> list[dict[str, str]]:
    """Legacy helper — prefer market_lab_intel.source_credits_on_receipt(bundle)."""
    # Without a Market Lab bundle Autumbra cannot invent credits.
    _ = source_ids
    return []


def may_act_on_sources(
    source_ids: list[str],
    *,
    act_on_single_source: bool,
) -> tuple[bool, str]:
    """Cross-check still applies to Market Lab-attributed source ids on a receipt."""
    cleaned = [s for s in source_ids if str(s).strip()]
    if not cleaned:
        return False, "no known source"
    if len(cleaned) == 1 and not act_on_single_source:
        return False, "single source; client requires cross-check"
    return True, "ok"


def record_track(store, tenant_id: str, source_id: str, outcome: str) -> dict[str, Any]:
    if outcome not in {"first", "confirmed", "wrong"}:
        raise ValueError("Unknown track outcome.")
    key = "autumbra_source_track"
    tracks = store.get_state(tenant_id, key, {}) or {}
    if not isinstance(tracks, dict):
        tracks = {}
    row = dict(tracks.get(source_id) or {"first": 0, "confirmed": 0, "wrong": 0})
    row[outcome] = int(row.get(outcome, 0)) + 1
    tracks[source_id] = row
    store.set_state(tenant_id, key, tracks)
    return row


def registry_with_weights(store, tenant_id: str) -> list[dict[str, Any]]:
    _ = (store, tenant_id)
    return []


def sources_accepting_support() -> list[dict[str, str]]:
    return []


def backend_status() -> dict[str, Any]:
    return {
        "owner": "Market Lab",
        "autumbra_owns_feed_list": False,
        "client_visible_feed_list": False,
        "note": DEPRECATION,
        "consume_module": "agents.ghost.market_lab_intel",
        "credit_helper": source_credits_on_receipt.__module__ + ".source_credits_on_receipt",
    }
