"""Bounded public CSV labels. Event labels await independent later evidence."""
from __future__ import annotations

import csv
import io
import math
import uuid
from collections import deque
from collections.abc import Iterable
from datetime import date
from typing import Any

PLATFORM_TENANT = "00000000-0000-0000-0000-000000000001"
PUBLIC_SOURCES = frozenset({"listing_counts", "check_counts", "census_population"})
MAX_HISTORY = 90
MAX_CANDIDATES = 200


def candidates(series: Iterable[dict], points: Iterable[dict], *, region: str, limit: int = 200,
               today: date | None = None) -> list[dict]:
    """Read date-ordered points lazily; single-pass streams represent one series."""
    if region != "us-east" or limit <= 0:
        return []
    limit = min(limit, MAX_CANDIDATES)
    cutoff = (today or date.today()).isoformat()
    output = []
    for source in series:
        if (
            str(source.get("tenant_id")) != PLATFORM_TENANT
            or source.get("source") not in PUBLIC_SOURCES or source.get("engine") != "ffl"
        ):
            continue
        history: deque[dict] = deque(maxlen=MAX_HISTORY)
        previous = ""
        for point in points:
            if point.get("series_id") != source["id"]:
                continue
            stamp = str(point.get("date", ""))[:10]
            try:
                date.fromisoformat(stamp)
                value = float(point["value"])
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
            if stamp >= cutoff or stamp <= previous or not math.isfinite(value):
                continue
            previous = stamp
            history.append({"date": stamp, "value": value})
            if len(history) < 2:
                continue
            observed = list(history)
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["date", "value"])
            writer.writerows((point["date"], point["value"]) for point in observed)
            fetched = stamp + "T00:00:00+00:00"
            output.append({
                "skill_id": "market.series_fetch",
                "input": {"adapter": "csv", "text": buffer.getvalue(), "series_id": source["id"],
                          "source": source["source"], "fetched_at": fetched},
                "expected": {"series_id": source["id"], "points": observed, "source": source["source"],
                             "fetched_at": fetched, "stored": True},
                "label_source": f"{source['source']}:{source['ref']}:{stamp}",
                "region": region, "public": True,
            })
            if len(output) >= limit:
                return output
    return output


async def collect(conn: Any, *, region: str, limit: int, today: date | None = None) -> list[dict]:
    if region != "us-east" or limit <= 0:
        return []
    limit = min(limit, MAX_CANDIDATES)
    cutoff = today or date.today()
    tenant = uuid.UUID(PLATFORM_TENANT)
    output = []
    async with conn.transaction():
        async for source in conn.cursor(
            "SELECT id,tenant_id,source,ref,engine FROM agent_market_lab.series "
            "WHERE tenant_id=$1 AND source=ANY($2::text[]) AND engine='ffl' ORDER BY id",
            tenant, sorted(PUBLIC_SOURCES), prefetch=1,
        ):
            points = await conn.fetch(
                "SELECT series_id,date,value FROM ("
                "SELECT p.series_id,p.date,p.value FROM agent_market_lab.points p "
                "JOIN agent_market_lab.series s ON s.id=p.series_id "
                "WHERE s.tenant_id=$1 AND p.series_id=$2 AND p.date<$3 "
                "ORDER BY p.date DESC LIMIT $4) recent ORDER BY date",
                tenant, source["id"], cutoff.isoformat(), MAX_HISTORY + limit - len(output),
            )
            output.extend(candidates([source], points, region=region, limit=limit - len(output), today=cutoff))
            if len(output) >= limit:
                break
    return output
