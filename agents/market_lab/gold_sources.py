"""Machine-labelled public history; candidates still need a human spot check."""
from __future__ import annotations

import csv
import io
import math
from datetime import date

from core.pure import areas_from_series, gap_score
from engines.ffl.engine import plan

PLATFORM_TENANT = "00000000-0000-0000-0000-000000000001"
# Explicit public-record feeds only. Uploads and live-only sources never qualify.
PUBLIC_SOURCES = frozenset({"listing_counts", "check_counts", "census_population"})


def _events(points: list[dict]) -> list[dict]:
    """Independent reference labels from observed values, not model predictions."""
    result = []
    for i in range(6, len(points)):
        history = [p["value"] for p in points[i - 6:i]]
        current = points[i]["value"]
        mean = sum(history) / 6
        spread = math.sqrt(sum((v - mean) ** 2 for v in history) / 6)
        z = (current - mean) / spread if spread else None
        pct = (current - history[-1]) / abs(history[-1]) if history[-1] else None
        if (z is None or abs(z) < 2) and (pct is None or abs(pct) < .25):
            continue
        result.append(dict(date=points[i]["date"], kind="surge" if current >= history[-1] else "drop",
                           size=round(z if z is not None else pct, 4),
                           z=None if z is None else round(z, 4), pct=None if pct is None else round(pct, 4)))
    return result


def candidates(series: list[dict], points: list[dict], *, region: str, limit: int = 200,
               today: date | None = None) -> list[dict]:
    if region not in {"us-east", "za"}:
        raise ValueError("unknown region")
    if limit <= 0:
        return []
    cutoff = (today or date.today()).isoformat()
    eligible = [s for s in series if str(s.get("tenant_id")) == PLATFORM_TENANT
                and s.get("source") in PUBLIC_SOURCES and s.get("engine") == "ffl"]
    eligible.sort(key=lambda s: s["id"])
    clean = []
    for s in eligible:
        seen = set()
        for p in sorted(points, key=lambda p: str(p["date"])):
            if p["series_id"] != s["id"]:
                continue
            stamp = str(p["date"])[:10]
            try:
                date.fromisoformat(stamp)
                value = float(p["value"])
            except (ValueError, TypeError):
                continue
            if stamp >= cutoff or not math.isfinite(value) or stamp in seen:
                continue
            seen.add(stamp)
            clean.append(dict(series_id=s["id"], date=stamp, value=value))
    out = []

    def add(skill: str, payload: dict, expected: dict, source: str) -> None:
        out.append(dict(skill_id="market." + skill, input=payload, expected=expected,
                        label_source=source, region=region, public=True))

    for s in eligible:
        history = [{"date": p["date"], "value": p["value"]} for p in clean if p["series_id"] == s["id"]]
        for end in range(2, len(history) + 1):
            observed = history[:end]
            stamp = observed[-1]["date"]
            source = f"{s['source']}:{s['ref']}:{stamp}"
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["date", "value"])
            writer.writerows((p["date"], p["value"]) for p in observed)
            fetched = stamp + "T00:00:00+00:00"
            add("series_fetch", dict(adapter="csv", text=buffer.getvalue(), series_id=s["id"],
                                     source=s["source"], fetched_at=fetched),
                dict(series_id=s["id"], points=observed, source=s["source"], fetched_at=fetched, stored=True), source)
            if end >= 7:
                add("surge_detect", {"points": observed}, {"events": _events(observed)}, source)
    bindings = plan()["bindings"]
    histories: dict[str, list[dict]] = {}
    for stamp in sorted({p["date"] for p in clean}):
        snapshot = areas_from_series(eligible, [p for p in clean if p["date"] <= stamp], bindings)
        for row in gap_score({"areas": snapshot})["ranked"]:
            area = next(a for a in snapshot if a["area"] == row["area"])
            if stamp not in {p["date"] for p in area["demand"]} & {p["date"] for p in area["supply"]}:
                continue
            history = histories.setdefault(row["area"], [])
            history.append(dict(date=stamp, value=row["gap"]))
            if len(history) < 7:
                continue
            events = [{"area": row["area"], "segment": "all", "date": e["date"],
                       "kind": "bottleneck" if e["kind"] == "surge" else "saturating", "size": e["size"]}
                      for e in _events(history)]
            add("shift_detect", {"areas": [{"area": row["area"], "gap": list(history)}]},
                {"events": events}, "gap:" + "+".join(sorted({s["source"] for s in eligible})) + ":" + row["area"] + ":" + stamp)
    # Round-robin skills so a large source cannot starve shift examples.
    groups = [[r for r in out if r["skill_id"] == "market." + skill]
              for skill in ("series_fetch", "surge_detect", "shift_detect")]
    return [group[i] for i in range(max(map(len, groups), default=0)) for group in groups if i < len(group)][:limit]
