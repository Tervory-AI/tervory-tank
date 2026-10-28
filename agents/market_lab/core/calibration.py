"""Prediction confidence from recorded outcomes, without models or I/O.

The ledger is append-only. Count one measurable resolution per original forecast,
and compare calibration against the confidence stored when that forecast was made.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from math import isfinite
from typing import Any

FIELDS = ("kind", "feed", "horizon_seconds", "confidence", "confidence_count")


def timestamp(value: Any) -> datetime:
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def resolves(row: dict) -> str | None:
    targets = {str(source["resolves"]) for source in row.get("sources") or []
               if isinstance(source, dict) and source.get("resolves")}
    return next(iter(targets)) if len(targets) == 1 else None


def identity(row: dict, series: list[dict]) -> dict:
    """Use explicit metadata, otherwise the existing forecast/series identifiers.

    Older rows have no kind/feed columns. Warning markers, response-series prefixes
    and comparators identify their existing families without parsing display text.
    An unregistered series is its own feed; unrelated unknown feeds never pool.
    """
    metric = str(row["metric_series_id"])
    warning = any(isinstance(s, dict) and s.get("warning_id") for s in row.get("sources") or [])
    family = "warning" if warning else "response" if metric.startswith("response:") else "comparison"
    feed = next((s["source"] for s in series if str(s["tenant_id"]) == str(row["tenant_id"])
                 and str(s["id"]) == metric), None)
    horizon = int((timestamp(row["resolve_by"]) - timestamp(row["made_at"])).total_seconds())
    if horizon < 0:
        raise ValueError("Prediction horizon must not be negative")
    return {"kind": row.get("kind") or f"{family}:{row['comparator']}",
            "feed": row.get("feed") or feed or metric,
            "horizon_seconds": horizon}


def resolved_pairs(rows: list[dict], tenant_id: str, *, as_of: datetime | None = None) -> list[tuple[dict, dict]]:
    own = [row for row in rows if str(row["tenant_id"]) == str(tenant_id)]
    originals = {str(row["id"]): row for row in own if row.get("outcome") is None and resolves(row) is None}
    known = [row for row in own if row.get("outcome") in {"hit", "miss"} and row.get("resolved_at") is not None]
    seen, result = set(), []
    for outcome in sorted(known, key=lambda r: (timestamp(r["resolved_at"]), str(r["id"]))):
        ident = resolves(outcome)
        original = originals.get(ident)
        if original is None or ident in seen:
            continue
        resolved_at = timestamp(outcome["resolved_at"])
        if resolved_at < timestamp(original["resolve_by"]):
            continue
        if as_of is not None and (resolved_at > as_of or timestamp(original["made_at"]) >= as_of):
            continue
        # A link alone cannot substitute another claim for the original one.
        if any(outcome[field] != original[field] for field in ("metric_series_id", "comparator", "target")):
            continue
        seen.add(ident)
        result.append((original, outcome))
    return result


def prepare_prediction(row: dict, history: list[dict], series: list[dict]) -> dict:
    """Stamp every new forecast; resolutions inherit, never recalculate, its p."""
    tenant = str(row["tenant_id"])
    if row.get("outcome") is not None:
        parent = resolves(row)
        original = next((r for r in history if str(r["tenant_id"]) == tenant
                         and str(r["id"]) == parent and r.get("outcome") is None), None)
        if original is None:
            raise ValueError("Resolution requires this tenant's original prediction")
        return {**row, **identity(original, series), "confidence": original.get("confidence"),
                "confidence_count": original.get("confidence_count") or 0}
    key = identity(row, series)
    comparable = [outcome for original, outcome in resolved_pairs(history, tenant, as_of=timestamp(row["made_at"]))
                  if str(original["id"]) != str(row["id"]) and identity(original, series) == key]
    count = len(comparable)
    hits = sum(outcome["outcome"] == "hit" for outcome in comparable)
    return {**row, **key, "confidence": hits / count if count else None, "confidence_count": count}


def calibration(rows: list[dict], tenant_id: str, series: list[dict], *, kind: str | None = None) -> dict:
    grouped: dict[str, list[tuple[dict, dict]]] = {}
    for original, outcome in resolved_pairs(rows, tenant_id):
        name = identity(original, series)["kind"]
        if kind is None or name == kind:
            grouped.setdefault(name, []).append((original, outcome))
    groups = []
    for name, pairs in sorted(grouped.items()):
        buckets: list[list[tuple[float, bool]]] = [[] for _ in range(10)]
        for original, outcome in pairs:
            raw = original.get("confidence")
            if raw is None or not original.get("confidence_count"):
                continue  # Never retroactively assign confidence to historical rows.
            value = float(raw)
            if not isfinite(value) or not 0 <= value <= 1:
                continue
            band = min(9, int(Decimal(str(value)) * 10))
            buckets[band].append((value, outcome["outcome"] == "hit"))
        bands = []
        for index, bucket in enumerate(buckets):
            count = len(bucket)
            hits = sum(hit for _, hit in bucket)
            bands.append({"lower": index / 10, "upper": (index + 1) / 10,
                          "upper_inclusive": index == 9, "count": count, "hits": hits,
                          "mean_confidence": sum(p for p, _ in bucket) / count if count else None,
                          "hit_rate": hits / count if count else None})
        scored = sum(len(bucket) for bucket in buckets)
        groups.append({"kind": name, "resolved_count": len(pairs), "scored_count": scored,
                       "unscored_count": len(pairs) - scored,
                       "hits": sum(outcome["outcome"] == "hit" for _, outcome in pairs),
                       "hit_rate": sum(outcome["outcome"] == "hit" for _, outcome in pairs) / len(pairs),
                       "bands": bands})
    return {"groups": groups}
