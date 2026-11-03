"""Private statistical patterns, written and listed through SQL-first Hermes."""

from __future__ import annotations

import json
from uuid import NAMESPACE_URL, uuid5


FIELDS = {"pair_id", "upstream_source", "upstream_ref", "downstream_source",
          "lag_days", "episodes", "hits", "hit_rate"}


def claim(config: dict, stats: dict) -> dict:
    # Deliberately do not copy a summary, series, watch, product or URL.
    return {
        "pair_id": config["id"],
        "upstream_source": config["source"],
        "upstream_ref": config["ref"],
        "downstream_source": config["downstream_source"],
        "lag_days": {"min": stats["lag_min"], "max": stats["lag_max"], "median": stats["lag_median"]},
        "episodes": stats["episode_count"], "hits": stats["hits"],
        "hit_rate": stats["hit_rate"],
    }


async def remember(memory: object, tenant: str, config: dict, stats: dict, document_id: str) -> bool:
    text = json.dumps(claim(config, stats), sort_keys=True, separators=(",", ":"))
    # A retry after a lost HTTP response addresses the same existing Hermes row.
    identity = str(uuid5(NAMESPACE_URL, tenant + ":warning_pattern:" + document_id))
    saved = await memory.remember(tenant, text, "warning_pattern", document_id,
                                  evidence=[document_id], record_id=identity)
    return bool(isinstance(saved, dict) and saved.get("id"))


async def listing(memory: object, tenant: str, plan: dict) -> dict:
    """One latest private and published record per configured pair; no recall."""
    configs = {row["id"]: row for row in plan["pairs"]}
    result = {"patterns": [], "published": []}
    for tier, key in (("client", "patterns"), ("platform", "published")):
        seen = set()
        rows = await memory.records(tenant, tier=tier)
        for row in sorted(rows, key=lambda item: (str(item.get("created_at", "")), str(item.get("id", ""))), reverse=True):
            if row.get("tier") != tier or (tier == "client" and str(row.get("tenant_id")) != tenant):
                continue
            try:
                value = json.loads(row["claim"])
            except (KeyError, ValueError, TypeError):
                continue
            if not isinstance(value, dict) or set(value) != FIELDS:
                continue
            config = configs.get(value["pair_id"])
            if config is None or value["pair_id"] in seen:
                continue
            if any(value[field] != config[config_field] for field, config_field in (
                ("upstream_source", "source"), ("upstream_ref", "ref"), ("downstream_source", "downstream_source")
            )):
                continue
            seen.add(value["pair_id"])
            result[key].append({"id": row["id"], "claim": value, "evidence": row.get("evidence") or [], "tier": tier})
    return result
