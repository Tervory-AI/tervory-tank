"""Public feed candidates. A past point is labelled only after its later value is known.

Shift and surge use the same detection the room already runs, on points whose
value 28 days later is already stored. A fetched point labels series_fetch
only when it matches the stored official value. Private and other-region
feeds are skipped.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from core.pure import series_fetch, shift_detect, surge_detect

WINDOW_DAYS = 28
MAX_CANDIDATES = 200
MAX_SNAPSHOT_BYTES = 20_000_000
PLATFORM_TENANT = "00000000-0000-0000-0000-000000000001"
_FEED = re.compile(r"[A-Za-z0-9_.:-]{1,80}")
_REGIONS = {"us-east", "za"}


def _month(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = value.isoformat() if hasattr(value, "isoformat") else str(value).strip()
    if len(text) < 7 or text[4] != "-" or not (text[:4].isdigit() and text[5:7].isdigit()):
        return None
    if not 1 <= int(text[5:7]) <= 12:
        return None
    return text[:7]


def _family(name: str, synthetic: bool) -> str:
    return name.replace(":", "-synthetic:", 1) if synthetic else name


def _stamp(value: Any) -> date | None:
    text = str(value or "").strip()
    if len(text) < 10 or text[4] != "-" or text[7] != "-":
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return float(int(number)) if number.is_integer() else number


def _same(left: float, right: float) -> bool:
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except InvalidOperation:
        return False


def _points(rows: Any) -> list[dict[str, Any]]:
    parsed: list[tuple[date, dict[str, Any]]] = []
    if not isinstance(rows, list):
        return []
    for row in rows:
        if not isinstance(row, dict):
            continue
        stamp = _stamp(row.get("date"))
        number = _number(row.get("value"))
        if stamp is None or number is None:
            continue
        item = {"date": stamp.isoformat(), "value": number}
        fetched_at = row.get("fetched_at")
        if isinstance(fetched_at, str) and fetched_at.strip():
            item["fetched_at"] = fetched_at.strip()
        parsed.append((stamp, item))
    parsed.sort(key=lambda item: item[0])
    return [item for _, item in parsed]


def mature_points(rows: Any, *, window_days: int = WINDOW_DAYS) -> list[dict[str, Any]]:
    """Points that have a stored value at least ``window_days`` later."""
    points = _points(rows)
    kept: list[dict[str, Any]] = []
    for index, point in enumerate(points):
        horizon = date.fromisoformat(point["date"]) + timedelta(days=window_days)
        if any(date.fromisoformat(later["date"]) >= horizon for later in points[index + 1 :]):
            kept.append({key: value for key, value in point.items() if key != "fetched_at"})
    return kept


def _public_feed(feed: Any, region: str) -> tuple[str, bool] | None:
    if not isinstance(feed, dict) or feed.get("public") is not True or feed.get("region") != region:
        return None
    tenant = feed.get("tenant_id")
    if tenant not in (None, PLATFORM_TENANT):
        return None
    name = feed.get("feed")
    if not isinstance(name, str) or _FEED.fullmatch(name) is None:
        return None
    return name, feed.get("synthetic") is True


def _row(
    *,
    skill: str,
    payload: dict[str, Any],
    expected: dict[str, Any],
    source: str,
    family: str,
    region: str,
) -> dict[str, Any]:
    return {
        "skill_id": skill,
        "input": payload,
        "expected": expected,
        "label_source": source[:500],
        "label_family": family,
        "region": region,
        "public": True,
    }


def _surge_rows(feed: dict[str, Any], name: str, region: str, synthetic: bool) -> list[dict[str, Any]]:
    points = mature_points(feed.get("points"))
    rows: list[dict[str, Any]] = []
    for index, point in enumerate(points):
        history = points[: index + 1]
        month = point["date"][:7]
        rows.append(_row(
            skill="market.surge_detect",
            payload={"points": history},
            expected=surge_detect({"points": history}),
            source=f"later-value:{name}:{point['date']}",
            family=_family(f"later-value:{name}:{month}", synthetic),
            region=region,
        ))
    return rows


def _shift_rows(feed: dict[str, Any], name: str, region: str, synthetic: bool) -> list[dict[str, Any]]:
    prepared: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    areas = feed.get("areas")
    if not isinstance(areas, list):
        return []
    for area in areas:
        if not isinstance(area, dict) or not isinstance(area.get("area"), str) or not area["area"].strip():
            continue
        gaps = mature_points(area.get("gap") if area.get("gap") is not None else area.get("points"))
        if gaps:
            prepared.append((area, gaps))
    rows: list[dict[str, Any]] = []
    for area, gaps in prepared:
        for index, point in enumerate(gaps):
            history: list[dict[str, Any]] = []
            for other, other_gaps in prepared:
                trimmed = [item for item in other_gaps if item["date"] <= point["date"]]
                if not trimmed:
                    continue
                history.append({
                    "area": str(other["area"]),
                    "segment": str(other.get("segment") or "all"),
                    "gap": trimmed,
                })
            month = point["date"][:7]
            rows.append(_row(
                skill="market.shift_detect",
                payload={"areas": history},
                expected=shift_detect({"areas": history}),
                source=f"later-value:{name}:{area['area']}:{point['date']}",
                family=_family(f"later-value:{name}:{month}", synthetic),
                region=region,
            ))
    return rows


def _fetch_rows(feed: dict[str, Any], name: str, region: str, synthetic: bool) -> list[dict[str, Any]]:
    official = {point["date"]: point["value"] for point in _points(feed.get("official"))}
    series_id = feed.get("series_id") if isinstance(feed.get("series_id"), str) and feed["series_id"].strip() else name
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for point in _points(feed.get("fetched")):
        if point["date"] in seen or point["date"] not in official or not _same(point["value"], official[point["date"]]):
            continue
        seen.add(point["date"])
        fetched_at = point.get("fetched_at") or f"{point['date']}T00:00:00+00:00"
        payload = {
            "adapter": "csv",
            "series_id": series_id,
            "source": name,
            "fetched_at": fetched_at,
            "text": f"date,value\n{point['date']},{point['value']}\n",
        }
        month = _month(point["date"])
        if month is None:
            continue
        rows.append(_row(
            skill="market.series_fetch",
            payload=payload,
            expected=series_fetch(payload),
            source=f"official-match:{name}:{series_id}:{point['date']}",
            family=_family(f"official-match:{name}:{month}", synthetic),
            region=region,
        ))
    return rows


def candidates(feeds: Iterable[dict[str, Any]], *, region: str, limit: int = 200) -> list[dict[str, Any]]:
    if region not in _REGIONS or limit <= 0:
        return []
    cap = min(int(limit), MAX_CANDIDATES)
    output: list[dict[str, Any]] = []
    for feed in feeds:
        parsed = _public_feed(feed, region)
        if parsed is None:
            continue
        name, synthetic = parsed
        try:
            built = (
                _surge_rows(feed, name, region, synthetic)
                + _shift_rows(feed, name, region, synthetic)
                + _fetch_rows(feed, name, region, synthetic)
            )
        except (TypeError, ValueError, KeyError, ArithmeticError):
            continue
        for row in built:
            output.append(row)
            if len(output) >= cap:
                return output
    return output


def read_candidates(*, limit: int, region: str) -> list[dict[str, Any]]:
    """Read this box's public feed snapshot. A missing file is an empty pull."""
    if region not in _REGIONS:
        return []
    path = Path(os.environ.get("DATA_DIR", "/data")) / "gold" / region / "public-feeds.jsonl"
    if not path.exists():
        return []
    if path.is_symlink() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("invalid feed snapshot")

    def rows() -> Iterable[dict[str, Any]]:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict):
                    yield value

    return candidates(rows(), region=region, limit=limit)
