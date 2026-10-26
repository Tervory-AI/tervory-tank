"""Autumbra consumes Market Lab intel — it does not own a feed list.

Founder correction (wins): Market Lab is the intel backend. Autumbra must not
build a feed list or source registry. Watch/Enforce consume a versioned IOC
bundle from Market Lab and name the contributing source on every receipt.
Clients never see a feed UI.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

BUNDLE_SCHEMA = "market_lab.ioc.v1"
FORBIDDEN_SOURCES = frozenset({"youtube", "instagram", "yt", "ig"})


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def accept_ioc_bundle(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate a Market Lab IOC bundle. Public / ML research sources only at launch."""
    if not isinstance(raw, dict):
        raise ValueError("IOC bundle must be an object.")
    if raw.get("schema_version") != BUNDLE_SCHEMA:
        raise ValueError(f"schema_version must be {BUNDLE_SCHEMA}")
    if raw.get("paid") is True:
        raise ValueError("paid feeds are off at launch; public + Market Lab only")
    sources = raw.get("sources") or []
    if not isinstance(sources, list) or not sources:
        raise ValueError("sources must be a non-empty list from Market Lab")
    indicators = raw.get("indicators") or []
    if not isinstance(indicators, list):
        raise ValueError("indicators must be a list")
    cleaned_sources: list[dict[str, str]] = []
    for src in sources:
        if not isinstance(src, dict):
            raise ValueError("each source must be an object")
        sid = str(src.get("id") or "").strip().lower()
        name = str(src.get("name") or src.get("credit") or sid).strip()
        if not sid or not name:
            raise ValueError("source needs id and name")
        if sid in FORBIDDEN_SOURCES or name.lower() in FORBIDDEN_SOURCES:
            raise ValueError("YouTube and Instagram are forbidden intel sources")
        cleaned_sources.append({
            "id": sid,
            "name": name,
            "url": str(src.get("url") or ""),
            "credit": str(src.get("credit") or name),
        })
    out_inds: list[dict[str, Any]] = []
    for ind in indicators:
        if not isinstance(ind, dict):
            continue
        kind = str(ind.get("kind") or "").strip()
        value = str(ind.get("value") or "").strip()
        if not kind or not value:
            continue
        out_inds.append({
            "kind": kind,
            "value": value,
            "source_ids": [str(s) for s in (ind.get("source_ids") or [])],
        })
    return {
        "schema_version": BUNDLE_SCHEMA,
        "bundle_id": str(raw.get("bundle_id") or uuid4()),
        "published_at": str(raw.get("published_at") or now_iso()),
        "producer": "Market Lab",
        "paid": False,
        "sources": cleaned_sources,
        "indicators": out_inds,
    }


def source_credits_on_receipt(bundle: dict[str, Any], *, source_ids: list[str] | None = None) -> list[dict[str, str]]:
    """Name Market Lab sources on the receipt. Autumbra does not maintain the registry."""
    wanted = {s.lower() for s in (source_ids or [])}
    credits: list[dict[str, str]] = []
    for src in bundle.get("sources") or []:
        if wanted and src["id"] not in wanted:
            continue
        credits.append({
            "id": src["id"],
            "credit": src["credit"],
            "url": src.get("url") or "",
            "via": "Market Lab",
        })
    return credits


def receipt_for_bundle_consume(
    bundle: dict[str, Any],
    *,
    tenant_id: str,
    action: str = "intel_consume",
) -> dict[str, Any]:
    """What Autumbra did with a Market Lab bundle — never the full feed list UI."""
    return {
        "id": str(uuid4()),
        "product": "Autumbra",
        "kind": "intel_consume",
        "at": now_iso(),
        "tenant_id": tenant_id,
        "action": action,
        "producer": "Market Lab",
        "bundle_id": bundle["bundle_id"],
        "indicator_count": len(bundle.get("indicators") or []),
        "sources": source_credits_on_receipt(bundle),
        "client_visible_feed_list": False,
        "note": "Intel backend is Market Lab; Autumbra does not own a source registry.",
    }


def backend_status() -> dict[str, Any]:
    """Autumbra does not own a feed list — Market Lab does."""
    return {
        "owner": "Market Lab",
        "autumbra_owns_feed_list": False,
        "client_visible_feed_list": False,
        "note": (
            "Intel backend is Market Lab. Autumbra consumes ML IOC bundles and "
            "names the source on the receipt. Clients never see a feed list."
        ),
        "consume_module": "agents.ghost.market_lab_intel",
        "credit_helper": "agents.ghost.market_lab_intel.source_credits_on_receipt",
    }
