"""Tenant-owned immutable evidence and deterministic, individually cited facts."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any
from decimal import Decimal

from feeds.catalog import sources
from feeds.keys import bind_key, missing_key
from feeds.geo import area_label, mentioned_states, state_for_area


def _decode(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


async def save_check(ledger: Any, tenant_id: str, result: dict, *, at: datetime) -> dict:
    owner = uuid.UUID(str(tenant_id))
    facts = result["points"] + result["events"]
    document_id = str(uuid.uuid4()) if facts else None
    check = {"id": str(uuid.uuid4()), "tenant_id": str(owner), "source_id": result["source_id"],
             "checked_at": at.isoformat(), "rows": len(facts), "note": result["note"],
             "fixture": result["fixture"], "document_id": document_id}
    content = {key: value for key, value in result.items() if key != "fixture"}
    content.update(id=document_id, fetched_at=at.isoformat())
    if hasattr(ledger, "conn"):
        async with ledger.conn.transaction():
            if document_id:
                await ledger.conn.execute("""
                    INSERT INTO agent_market_lab.feed_documents
                    (id, tenant_id, source_id, fetched_at, fixture, content)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                """, uuid.UUID(document_id), owner, result["source_id"], at, result["fixture"], json.dumps(content))
            await ledger.conn.execute("""
                INSERT INTO agent_market_lab.feed_checks
                (id, tenant_id, source_id, checked_at, fixture, rows, note, document_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, uuid.UUID(check["id"]), owner, result["source_id"], at, result["fixture"],
                len(facts), result["note"], uuid.UUID(document_id) if document_id else None)
    else:
        ledger.feed_checks = getattr(ledger, "feed_checks", []) + [check]
        if document_id:
            ledger.feed_documents = getattr(ledger, "feed_documents", []) + [{**content, "tenant_id": str(owner), "fixture": result["fixture"]}]
    return check


async def latest_checks(ledger: Any, tenant_id: str, *, fixtures: bool = False) -> list[dict]:
    owner = uuid.UUID(str(tenant_id))
    if hasattr(ledger, "conn"):
        rows = await ledger.conn.fetch("""
            SELECT DISTINCT ON (source_id) source_id, checked_at, rows, note, document_id
            FROM agent_market_lab.feed_checks WHERE tenant_id = $1 AND fixture = $2
            ORDER BY source_id, checked_at DESC, id DESC
        """, owner, fixtures)
        return [{**dict(row), "checked_at": row["checked_at"].isoformat(),
                 "document_id": str(row["document_id"]) if row["document_id"] else None} for row in rows]
    by_source = {}
    for row in getattr(ledger, "feed_checks", []):
        if row["tenant_id"] == str(owner) and row["fixture"] == fixtures:
            by_source[row["source_id"]] = dict(row)
    return list(by_source.values())


async def document(ledger: Any, tenant_id: str, document_id: str, *, fixtures: bool = False) -> dict | None:
    owner, ident = uuid.UUID(str(tenant_id)), uuid.UUID(document_id)
    if hasattr(ledger, "conn"):
        value = await ledger.conn.fetchval("""
            SELECT content FROM agent_market_lab.feed_documents
            WHERE tenant_id = $1 AND id = $2 AND fixture = $3
        """, owner, ident, fixtures)
        return _decode(value) if value else None
    return next((dict(row) for row in getattr(ledger, "feed_documents", [])
                 if row["tenant_id"] == str(owner) and row["id"] == str(ident) and row["fixture"] == fixtures), None)


async def usable_points(ledger: Any, tenant_id: str, doc: dict) -> list[tuple[int, dict]]:
    ids = list({point["batch_id"] for point in doc["points"]})
    if not ids:
        return []
    if hasattr(ledger, "conn"):
        rows = await ledger.conn.fetch("""
            SELECT id FROM agent_market_lab.batches
            WHERE tenant_id = $1 AND id = ANY($2::text[]) AND status = 'pooled'
        """, uuid.UUID(str(tenant_id)), ids)
        allowed = {row["id"] for row in rows}
    else:
        allowed = {key for key, value in ledger.pool.batches.items()
                   if value["tenant_id"] == str(tenant_id) and value["status"] == "pooled"}
    return [(index, point) for index, point in enumerate(doc["points"]) if point["batch_id"] in allowed]


async def document_page(ledger: Any, tenant_id: str, document_id: str, offset: int = 0, *, fixtures: bool = False) -> dict | None:
    doc = await document(ledger, tenant_id, document_id, fixtures=fixtures)
    if doc is None:
        return None
    active = {index for index, _ in await usable_points(ledger, tenant_id, doc)}
    return {**doc, "offset": offset, "point_count": len(doc["points"]), "event_count": len(doc["events"]),
            "points": [{**point, "geo_name": area_label(point["geo"], point["geo_level"], point["title"]),
                        "withdrawn": index not in active} for index, point in enumerate(doc["points"])
                       if offset <= index < offset + 200], "events": doc["events"][offset:offset + 200]}


async def overview(ledger: Any, tenant_id: str, engine: str = "ffl", *, fixtures: bool = False) -> dict:
    checks = {row["source_id"]: row for row in await latest_checks(ledger, tenant_id, fixtures=fixtures)}
    feeds = []
    for source in sources(engine):
        spec = bind_key(source)
        check = checks.get(spec.id, {})
        rows = int(check.get("rows", 0))
        note = check.get("note") or ("Off, needs key" if missing_key(spec) else "Off, not fetched yet")
        if rows:
            note = check.get("note") or ""
        feeds.append({"id": spec.id, "name": spec.name, "kind": "copy" if spec.allow_bulk else "linked",
                      "rows": rows, "state": "on" if spec.allow_bulk and rows > 0 else "off",
                      "note": note, "checked_at": check.get("checked_at"), "document_id": check.get("document_id")})
    return {"feeds": feeds, "on_count": sum(feed["state"] == "on" for feed in feeds)}


def _words(text: str) -> set[str]:
    stop = {"a", "an", "the", "what", "which", "how", "is", "are", "was", "were", "in", "of", "for", "to", "and", "my", "market", "latest", "show", "me", "has", "changed", "with", "from", "about"}
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in stop}


async def answer(ledger: Any, tenant_id: str, question: str, *, fixtures: bool = False) -> dict:
    terms = _words(question)
    states = mentioned_states(question)
    years = set(re.findall(r"\b(?:19|20)\d{2}\b", question))
    ranked = []
    for check in await latest_checks(ledger, tenant_id, fixtures=fixtures):
        if not check["document_id"] or not check["rows"]:
            continue
        doc = await document(ledger, tenant_id, check["document_id"], fixtures=fixtures)
        if not doc:
            continue
        latest = {}
        for index, point in await usable_points(ledger, tenant_id, doc):
            if states and state_for_area(point["geo"]) not in states:
                continue
            if years and point["date"][:4] not in years:
                continue
            key = point["series_id"]
            if key not in latest or point["date"] >= latest[key][1]["date"]:
                latest[key] = (index, point)
        for index, point in latest.values():
            words = _words(f'{doc["name"]} {point["title"]} {point["geo"]} {point["unit"]}')
            score = len(terms & words)
            if not score:
                continue
            value = format(Decimal(str(point["value"])), ",f").rstrip("0").rstrip(".") if "." in str(point["value"]) else format(Decimal(str(point["value"])), ",f")
            text = f'{point["title"]}: {value} {point["unit"]} ({point["date"]}).'
            ranked.append((score, point["date"], {"text": text, "href": f'/market-lab/sources/{doc["id"]}?row={index}#point-{index}', "name": doc["name"]}))
        for index, event in enumerate(doc["events"]):
            if states and state_for_area(event["geo"]) not in states:
                continue
            if years and event["date"][:4] not in years:
                continue
            if event["kind"] == "changed":
                continue
            score = len(terms & _words(f'{doc["name"]} {event["title"]} {event["geo"]}'))
            if score:
                ranked.append((score, event["date"], {"text": f'{event["title"]} ({event["date"]}).', "href": f'/market-lab/sources/{doc["id"]}?row={index}#event-{index}', "name": doc["name"]}))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    facts = [row[2] for row in ranked[:5]]
    return {"content": "Here is what the stored sources show. These observations do not establish a cause or a forecast." if facts else "No stored evidence answers that question yet. Refresh the feeds or ask about a feed shown below.", "facts": facts, "sources": [{"name": fact["name"], "href": fact["href"]} for fact in facts]}
