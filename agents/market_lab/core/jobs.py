"""Scheduled work for the Market Lab box.

Listing counts are stored. FRED is read and refused by the ledger. Predictions
are inserted, never updated.
"""

from __future__ import annotations

import importlib
import inspect
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from core.pure import (
    areas_from_series,
    fred_is_link_only,
    gap_score,
    opportunity_rows,
    prediction_for_recommendation,
    research_answer,
    resolve_prediction,
    series_fetch,
    surge_detect,
)

_ENGINE = re.compile(r"^[a-z][a-z0-9_]*$")


def load_engine(name: str) -> Any:
    if not isinstance(name, str) or _ENGINE.fullmatch(name) is None:
        raise ValueError("engine is required")
    return importlib.import_module(f"engines.{name}.engine")


async def perform_refresh(
    *,
    tenant_id: str,
    engine: str,
    ledger: Any,
    fixtures: str | None = None,
    fred_bodies: dict[str, Any] | None = None,
    live: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    module = load_engine(engine)
    spec = module.plan()
    clock = _clock(now)
    fetched_at = clock.replace(microsecond=0).isoformat()
    if not fred_is_link_only(engine):
        raise RuntimeError("fred terms allow a copy; refusing to run")
    stored_rows = 0
    events = 0
    for supply in spec["supply"]:
        if supply["source"] != "listing_counts":
            continue
        if not fixtures and not live:
            raise RuntimeError("refusing to open the network")
        if fixtures:
            loaded_states = _listing_states(fixtures, engine, supply["source"], fetched_at)
        else:
            loaded_states = _listing_states_live(engine, supply["source"], fetched_at)
        for item in loaded_states:
            series_id = item["series_id"]
            ref = series_id.split(":", 1)[1]
            await _call(
                ledger.save_series,
                {
                    "id": f"{tenant_id}:{series_id}",
                    "tenant_id": tenant_id,
                    "source": item["source"],
                    "ref": ref,
                    "unit": supply.get("unit") or "count",
                    "engine": engine,
                },
            )
            stamped = [{**point, "fetched_at": fetched_at} for point in item["points"]]
            stored_rows += await _call(
                ledger.save_points,
                f"{tenant_id}:{series_id}",
                tenant_id,
                stamped,
                stored=True,
                source=item["source"],
            )
            surge = surge_detect({"points": item["points"], **spec["surge"]})
            for event in surge["events"]:
                saved = await _call(
                    ledger.save_event,
                    f"{tenant_id}:{series_id}",
                    tenant_id,
                    event,
                )
                events += int(bool(saved))
    fred_read: list[dict[str, Any]] = []
    for cost in spec["costs"]:
        body = None if fred_bodies is None else fred_bodies.get(cost["ref"])
        if body is None and live:
            body = await _live_fred(str(cost["ref"]))
        if body is None:
            continue
        fetched = series_fetch(
            {
                "adapter": "fred",
                "series_id": cost["ref"],
                "body": body,
                "fetched_at": fetched_at,
            }
        )
        if fetched["stored"]:
            raise RuntimeError("fred points were marked for storage")
        await _call(
            ledger.save_points,
            f"{tenant_id}:fred:{cost['ref']}",
            tenant_id,
            fetched["points"],
            stored=False,
            source="fred",
        )
        fred_read.append(
            {
                "ref": cost["ref"],
                "points": len(fetched["points"]),
                "stored": False,
                "source": "fred",
            }
        )
    return {
        "listings_stored": stored_rows,
        "events": events,
        "fred": fred_read,
        "fred_stored": 0,
    }


async def perform_opportunities(
    *,
    tenant_id: str,
    engine: str,
    ledger: Any,
    areas: list[dict[str, Any]] | None = None,
    signals: dict[str, Any] | None = None,
    memory: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    module = load_engine(engine)
    spec = module.plan()
    clock = _clock(now)
    if areas is None:
        series_rows = await _call(ledger.series_for, tenant_id)
        point_rows = await _call(ledger.points_for, tenant_id)
        # points_for does not include tenant on the row; series id is enough.
        for point in point_rows:
            point.setdefault("series_id", point["series_id"])
        areas = areas_from_series(series_rows, point_rows, spec["bindings"], None)
    scored = gap_score({"areas": areas})
    found = opportunity_rows(scored["ranked"], module.products(), signals or {})
    for row in scored["ranked"]:
        await _call(
            ledger.save_opportunity,
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "made_at": clock,
                "area": row["area"],
                "segment": row["segment"],
                "demand_idx": row["demand_idx"],
                "supply_idx": row["supply_idx"],
                "gap": row["gap"],
                "saturation": row["saturation"],
                "reachability": row["reachability"],
                "trend": row["trend"],
                "rank": row["rank"],
                "evidence": {
                    "recommendation": f"{row['recommendation']} marketing",
                    "per_capita": row.get("per_capita"),
                    "products": [item for item in found if item["area"] == row["area"]],
                },
            },
        )
        await _call(
            ledger.save_prediction,
            prediction_for_recommendation(
                row,
                tenant_id=tenant_id,
                made_at=clock,
                targets=spec.get("response_targets"),
            ),
        )
    if found:
        writeup = "; ".join(
            f"{item['rank']}. {item['area']} / {item['segment']} / {item['product']}" for item in found
        )
    else:
        writeup = "No product gap this month."
    await _call(
        ledger.save_report,
        {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "made_at": clock,
            "question": "Where is demand outrunning supply?",
            "answer": writeup,
            "citations": [],
        },
    )
    if memory is not None:
        await memory.remember(tenant_id, writeup, "report", "schedule:opportunities")
    return {
        "top_area": scored["top_area"],
        "top_recommendation": scored["top_recommendation"],
        "ranked": scored["ranked"],
        "products": found,
    }


async def perform_resolve(
    *,
    tenant_id: str,
    ledger: Any,
    points_by_series: dict[str, list[dict[str, Any]]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    clock = _clock(now)
    existing = await _call(ledger.predictions_for, tenant_id)
    resolved_ids = set()
    for row in existing:
        for source in row.get("sources") or []:
            if isinstance(source, dict) and source.get("resolves"):
                resolved_ids.add(str(source["resolves"]))
    written = 0
    outcomes: list[dict[str, Any]] = []
    for row in existing:
        if row.get("outcome") or str(row["id"]) in resolved_ids:
            continue
        series_id = str(row["metric_series_id"])
        if points_by_series is not None and series_id in points_by_series:
            points = points_by_series[series_id]
        else:
            points = await _call(ledger.points_for, tenant_id, series_id)
        nxt = resolve_prediction(row, points, clock)
        if nxt is None:
            continue
        if row.get("statement") != nxt["statement"] or row.get("target") != nxt["target"]:
            raise RuntimeError("resolution changed the prediction")
        await _call(ledger.save_prediction, nxt)
        written += 1
        outcomes.append({"id": nxt["id"], "resolves": row["id"], "outcome": nxt["outcome"], "score": nxt["score"]})
    return {"resolved": written, "outcomes": outcomes}


async def perform_research(
    *,
    tenant_id: str,
    ledger: Any,
    question: str,
    passages: list[dict[str, Any]] | None = None,
    model_text: str | None = None,
    memory: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    clock = _clock(now)
    payload: dict[str, Any] = {"question": question}
    if passages is not None:
        payload["passages"] = passages
    if model_text is not None:
        payload["model_text"] = model_text
    answer = research_answer(payload)
    report_id = str(uuid.uuid4())
    await _call(
        ledger.save_report,
        {
            "id": report_id,
            "tenant_id": tenant_id,
            "made_at": clock,
            "question": question,
            "answer": answer["answer"],
            "citations": answer["citations"],
        },
    )
    if memory is not None and answer["answer"]:
        source = answer["citations"][0]["url"] if answer["citations"] else f"report:{report_id}"
        await memory.remember(tenant_id, answer["answer"], "report", source)
    return answer


def _listing_states(fixtures: str, engine: str, source_id: str, fetched_at: str) -> list[dict[str, Any]]:
    """One feeds run, then every state count series from that source."""
    import sqlite3
    import sys
    import tempfile
    from pathlib import Path

    root = _market_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from feeds.runner import run

    with tempfile.TemporaryDirectory() as folder:
        target = str(Path(folder) / "feeds.sqlite")
        run(
            "sqlite:///" + target,
            engine=engine,
            source=source_id,
            backfill=True,
            fixtures=fixtures,
            live=False,
        )
        conn = sqlite3.connect(target)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT s.ref, p.date, p.value
                FROM points p
                JOIN series s ON s.id = p.series_id
                WHERE s.source_id = ? AND s.ref LIKE 'count:state:%'
                ORDER BY s.ref, p.date, p.revision
                """,
                (source_id,),
            ).fetchall()
        finally:
            conn.close()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["ref"]), []).append(
            {"date": str(row["date"])[:10], "value": float(row["value"])}
        )
    return [
        {
            "series_id": f"{source_id}:{ref}",
            "points": points,
            "source": source_id,
            "fetched_at": fetched_at,
            "stored": True,
        }
        for ref, points in sorted(grouped.items())
    ]


def _listing_states_live(engine: str, source_id: str, fetched_at: str) -> list[dict[str, Any]]:
    import sqlite3
    import sys
    import tempfile
    from pathlib import Path

    root = _market_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from feeds.runner import run

    with tempfile.TemporaryDirectory() as folder:
        target = str(Path(folder) / "feeds.sqlite")
        run(
            "sqlite:///" + target,
            engine=engine,
            source=source_id,
            backfill=False,
            live=True,
        )
        conn = sqlite3.connect(target)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT s.ref, p.date, p.value
                FROM points p
                JOIN series s ON s.id = p.series_id
                WHERE s.source_id = ? AND s.ref LIKE 'count:state:%'
                ORDER BY s.ref, p.date
                """,
                (source_id,),
            ).fetchall()
        finally:
            conn.close()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["ref"]), []).append(
            {"date": str(row["date"])[:10], "value": float(row["value"])}
        )
    return [
        {
            "series_id": f"{source_id}:{ref}",
            "points": points,
            "source": source_id,
            "fetched_at": fetched_at,
            "stored": True,
        }
        for ref, points in sorted(grouped.items())
    ]


async def _live_fred(series_id: str) -> dict[str, Any]:
    import httpx

    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FRED_API_KEY is not set")
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": series_id, "api_key": key, "file_type": "json"},
            )
    except httpx.HTTPError:
        raise RuntimeError("fred read failed") from None
    if response.status_code >= 400:
        raise RuntimeError("fred read failed")
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("fred read failed")
    return body


def _market_root() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[1])


def _clock(now: datetime | None) -> datetime:
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    return clock.astimezone(timezone.utc)


async def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result
