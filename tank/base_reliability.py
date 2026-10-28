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
import logging
import math
from statistics import NormalDist
from typing import Any, Iterable
from urllib.parse import urlsplit

from base_evidence import FIELDS, social_network

log = logging.getLogger(__name__)

SOURCES = ("own_site", "social_profile", "archive", "google_places", "opencorporates", "other_web")
_ARCHIVE_HOSTS = ("web.archive.org", "archive.org", "archive.ph", "archive.today")
_PLACES_HOSTS = ("maps.google.com", "google.com/maps", "maps.app.goo.gl", "goo.gl/maps")


def _host(url: Any) -> str:
    if not isinstance(url, str):
        return ""
    try:
        return (urlsplit(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _same_site(host: str, site: str) -> bool:
    return bool(host and site) and (host == site or host.endswith("." + site) or site.endswith("." + host))


def classify(source_url: Any, website_url: Any) -> str | None:
    """The kind of page a verified field came from; None when there is no usable URL."""
    host = _host(source_url)
    if not host:
        return None
    url = str(source_url).lower()
    if any(host == h or host.endswith("." + h) for h in _ARCHIVE_HOSTS):
        return "archive"
    if any(marker in url for marker in _PLACES_HOSTS):
        return "google_places"
    if host == "opencorporates.com" or host.endswith(".opencorporates.com"):
        return "opencorporates"
    if social_network(str(source_url)):
        return "social_profile"
    if _same_site(host, _host(website_url)):
        return "own_site"
    return "other_web"


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
            for name in FIELDS:
                field = fields.get(name) or {}
                if not field.get("verified"):
                    continue
                kind = classify(field.get("source_url"), website)
                if kind:
                    tally[(kind, name)][verdict] += 1
    rows = []
    for (source, field), count in sorted(tally.items()):
        checked = count["correct"] + count["wrong"]
        rows.append({"source": source, "field": field, "correct": count["correct"], "wrong": count["wrong"],
                     "checked": checked, "accuracy": count["correct"] / checked,
                     "wilson_lower": wilson_lower(count["correct"], checked), "audits": audit_count})
    return rows


def prefer(candidates: list[dict[str, Any]], field: str, table: dict[tuple[str, str], float]) -> dict[str, Any] | None:
    """Of several values for one field, keep the one whose source scores highest.

    `candidates` are field dicts with `source_url` (and the record's website in `website`).
    Unscored sources rank below scored ones; ties keep the first candidate. Both values are
    meant to stay in the record's evidence; this only picks which one is kept as the value.
    """
    best, best_score = None, -1.0
    for candidate in candidates:
        kind = classify(candidate.get("source_url"), candidate.get("website"))
        score = table.get((kind, field), -0.5) if kind else -1.0
        if best is None or score > best_score:
            best, best_score = candidate, score
    return best


async def recompute(conn) -> list[dict[str, Any]]:
    """Recompute every score from all reviewed audits, in one transaction. Counts only."""
    audits = await conn.fetch("SELECT records, verdicts FROM tank.base_audits WHERE reviewed_at IS NOT NULL")
    rows = scores(dict(row) for row in audits)
    async with conn.transaction():
        await conn.execute("DELETE FROM tank.base_source_reliability")
        for row in rows:
            await conn.execute(
                """INSERT INTO tank.base_source_reliability
                (source, field, correct, wrong, checked, accuracy, wilson_lower, audits, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,now())""",
                row["source"], row["field"], row["correct"], row["wrong"], row["checked"],
                row["accuracy"], row["wilson_lower"], row["audits"])
    return rows


async def read(conn) -> list[dict[str, Any]]:
    rows = await conn.fetch("""SELECT source, field, correct, wrong, checked, accuracy, wilson_lower, audits, updated_at
        FROM tank.base_source_reliability ORDER BY field, wilson_lower DESC NULLS LAST, source""")
    return [dict(row) for row in rows]


async def table(conn) -> dict[tuple[str, str], float]:
    """(source, field) -> Wilson lower bound, for `prefer`."""
    return {(row["source"], row["field"]): float(row["wilson_lower"] or 0) for row in await read(conn)}
