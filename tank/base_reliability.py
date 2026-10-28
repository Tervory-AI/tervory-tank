"""Per-source reliability for Base, measured from the founder's saved audits (job 6, F8).

Each reviewed audit has a human verdict per sampled record (correct / wrong / unsure).
A record's verified fields each name the page they came from (`source_url`). A source is
the kind of page: the business's own site, a social profile, an archived copy, and so on.
For every (source, field) pair the score is correct / (correct + wrong) over the records
whose verified field came from that source, with a Wilson 95% lower bound so a handful of
records never looks perfect.

The verdict is per record, not per field: a wrong record counts against every source that
supplied one of its verified fields. Scores hold source kinds, field names and counts only,
never a tenant, record, URL or value. They are stored once for the platform.
No model calls and no network reads.
"""
from __future__ import annotations

from collections import defaultdict
import json
import math
from statistics import NormalDist
from typing import Any, Iterable

from base_source_scores import SOURCES, classify, prefer  # noqa: F401 (public helpers)
from vendor_meter import PLATFORM

def wilson_lower(correct: int, total: int, confidence: float = .95) -> float | None:
    if total <= 0:
        return None
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    p = correct / total
    denominator = 1 + z * z / total
    center = p + z * z / (2 * total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return max(0.0, (center - half) / denominator)


def _obj(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def scores(audits: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scores from reviewed audits: one row per (source, field) with at least one resolved record."""
    tally: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"correct": 0, "wrong": 0})
    audit_count = 0
    for audit in audits:
        verdicts = _obj(audit.get("verdicts")) or {}
        records = _obj(audit.get("records")) or []
        if not verdicts:
            continue
        audit_count += 1
        for record in records:
            verdict = verdicts.get(str(record.get("record_id")))
            if verdict not in {"correct", "wrong"}:
                continue
            fields = _obj(record.get("fields")) or {}
            website = (fields.get("website") or {}).get("value") or (fields.get("website") or {}).get("source_url")
            for name, field in fields.items():
                if not isinstance(field, dict):
                    continue
                if not field.get("verified"):
                    continue
                kind = classify(field.get("source_url"), website, field.get("source_kind") or field.get("source"))
                if kind:
                    tally[(kind, name)][verdict] += 1
    rows = []
    for (source, field), count in sorted(tally.items()):
        checked = count["correct"] + count["wrong"]
        rows.append({"source": source, "field": field, "correct": count["correct"], "wrong": count["wrong"],
                     "checked": checked, "accuracy": count["correct"] / checked,
                     "wilson_lower": wilson_lower(count["correct"], checked), "audits": audit_count})
    return rows


async def recompute(conn) -> list[dict[str, Any]]:
    """Recompute every score from all reviewed audits, in one transaction. Counts only."""
    async with conn.transaction():
        # Serialize before reading audit inputs: a slower earlier recompute must
        # never overwrite the counts from a newly committed audit.
        await conn.execute("SELECT pg_advisory_xact_lock(4810512)")
        audits = await conn.fetch("SELECT records, verdicts FROM tank.base_audits WHERE reviewed_at IS NOT NULL")
        rows = scores(dict(row) for row in audits)
        await conn.execute("DELETE FROM tank.base_source_reliability WHERE owner_id=$1", PLATFORM)
        for row in rows:
            await conn.execute(
                """INSERT INTO tank.base_source_reliability
                (owner_id, source, field, correct, wrong, checked, accuracy, wilson_lower, audits, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,now())""",
                PLATFORM, row["source"], row["field"], row["correct"], row["wrong"], row["checked"],
                row["accuracy"], row["wilson_lower"], row["audits"])
    return rows


async def read(conn) -> list[dict[str, Any]]:
    rows = await conn.fetch("""SELECT source, field, correct, wrong, checked, accuracy, wilson_lower, audits, updated_at
        FROM tank.base_source_reliability WHERE owner_id=$1
        ORDER BY field, wilson_lower DESC NULLS LAST, source""", PLATFORM)
    return [dict(row) for row in rows]


async def table(conn) -> dict[tuple[str, str], float]:
    """(source, field) -> Wilson lower bound, for `prefer`."""
    return {(row["source"], row["field"]): float(row["wilson_lower"] or 0) for row in await read(conn)}
