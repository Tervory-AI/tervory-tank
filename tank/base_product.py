"""Base reference, work, evidence, comparison and expense routes."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import suppress
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import io
import json
import logging
import os
import re
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from admin import require_admin
from base_metrics import COUNTS, compare, cost_rows, counts, csv_text, export_records, latest, matches, selected
from base_repository import BaseStore, encoded
from vendor_meter import PLATFORM, price

log = logging.getLogger("tank.base_product")
PRICES = {"apollo.contact", "brave.search.query", "google.places.request", "context.dev.credit"}


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: uuid.UUID
    request_id: uuid.UUID
    created_by: str = Field(min_length=1, max_length=200)
    name: str = Field(default="Reference list", min_length=1, max_length=50)
    states: list[str] = Field(default_factory=list, max_length=60)
    types: list[str] = Field(default_factory=list, max_length=15)
    include_collectors: bool = False


class Upload(Selection):
    records: list[dict[str, Any]] = Field(min_length=1, max_length=1000)


class ApolloUpload(BaseModel):
    tenant_id: uuid.UUID
    csv: str = Field(min_length=1, max_length=2_000_000)


class PriceChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=8)
    free_pass: bool = False


class CreditReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID
    tenant_id: uuid.UUID
    record_id: uuid.UUID
    run_id: uuid.UUID
    units: Decimal = Field(gt=0, le=1000)
    outcome: str = Field(pattern="^(delivered|failed|unverified)$")
    region: str = Field(pattern="^us-east$")


def dimensions(states: str | list[str], kinds: str | list[str]) -> tuple[list[str], list[str]]:
    states = states.split(",") if isinstance(states, str) else states
    kinds = kinds.split(",") if isinstance(kinds, str) else kinds
    states = sorted({value.strip().upper() for value in states if value.strip()})
    kinds = sorted({value.strip().zfill(2) for value in kinds if value.strip()})
    if any(not re.fullmatch(r"[A-Z]{2}", value) for value in states) or any(not re.fullmatch(r"\d{2}", value) for value in kinds):
        raise HTTPException(422, "Choose valid state and licence type codes.")
    return states, kinds


def clean(value: Any) -> Any:
    return json.loads(encoded(value))


def download(text: str, name: str) -> Response:
    return Response(text, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{name}.csv"', "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


def build_router(rt: Any, store: BaseStore | None = None, *, background: bool = True) -> APIRouter:
    store = store or BaseStore(rt)
    if hasattr(rt, "make_ctx"):
        __import__("vendor_meter").install(rt)
    router = APIRouter(prefix="/v1/base-product")
    background_task: asyncio.Task | None = None

    async def workspace(x_tank_key: str = Header(default="")) -> None:
        expected = os.environ.get("TANK_API_KEY", "")
        if not expected or not hmac.compare_digest(expected, x_tank_key):
            raise HTTPException(401, "Workspace required.")
        if rt.box_region() != "us-east":
            raise HTTPException(403, "This public reference belongs to the US workspace.")

    async def room(x_tank_key: str = Header(default="")) -> None:
        expected = os.environ.get("TANK_KEY_BASE", "")
        if not expected or not hmac.compare_digest(expected, x_tank_key):
            raise HTTPException(401, "Base corridor required.")

    async def view(tenant: uuid.UUID, states: str = "", types: str = "", include_collectors: bool = False) -> tuple[list, list]:
        regions, kinds = dimensions(states, types)
        reference = [row for row in await store.reference() if selected(row, regions, kinds, include_collectors)]
        records = [row for row in await store.results(tenant) if selected(row, regions, kinds, include_collectors)]
        return reference, records

    @router.get("/reference", dependencies=[Depends(workspace)])
    async def reference(tenant_id: uuid.UUID, states: str = "", types: str = "", include_collectors: bool = False,
                        offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
        if isinstance(store, BaseStore):
            from base_queries import reference_page
            regions, kinds = dimensions(states, types)
            return clean(await reference_page(store, regions, kinds, include_collectors, offset, limit))
        all_rows = await store.reference()
        regions, kinds = dimensions(states, types)
        rows = [row for row in all_rows if selected(row, regions, kinds, include_collectors)]
        files = await store.reference_history()
        changes: list[dict[str, Any]] = []
        if len(files) > 1:
            before = {row["licence_key"]: row for row in await store.reference(files[1]["id"])}
            after = {row["licence_key"]: row for row in all_rows}
            for key in sorted(before.keys() | after.keys()):
                old, new = before.get(key), after.get(key)
                change = "new" if old is None else "lapsed" if new is None else "moved" if old["address"] != new["address"] else None
                if change and selected(new or old, regions, kinds, include_collectors):
                    changes.append({"licence_key": key, "change": change, "previous": old and old["address"], "current": new and new["address"]})
        return clean({"file": files[0] if files else None, "total_all": len(all_rows), "selected": len(rows),
                      "collectors": sum(row["licence_type"] == "03" for row in all_rows), "groups": counts(rows, []),
                      "rows": rows[offset:offset + limit], "changes": changes, "history": files})

    @router.post("/reference/batches", dependencies=[Depends(workspace)])
    async def start(body: Selection) -> dict[str, Any]:
        states, kinds = dimensions(body.states, body.types)
        file = await store.latest_file()
        if file is None:
            raise HTTPException(503, "The platform reference is not available yet.")
        rows = [row for row in await store.reference(file["id"]) if selected(row, states, kinds, body.include_collectors)]
        if not rows:
            raise HTTPException(422, "No reference licences match this selection.")
        groups: dict[str, list] = defaultdict(list)
        for row in rows:
            groups[row["state"]].append(row)
        identity = await store.create_campaign(body.tenant_id, body.request_id, body.name, body.created_by, file["id"],
            {"states": states, "types": kinds, "include_collectors": body.include_collectors}, groups)
        await store.dispatch(body.tenant_id)
        return clean({"id": identity, "records": len(rows), "states": len(groups), "batches": await store.campaigns(body.tenant_id)})

    @router.post("/uploads", dependencies=[Depends(workspace)])
    async def upload(body: Upload) -> dict[str, Any]:
        groups: dict[str, list] = defaultdict(list)
        for row in body.records:
            # Caller-supplied internal metadata never becomes reference or cost attribution.
            row = {key: value for key, value in row.items() if not key.startswith("_base_")}
            state = str(row.get("state") or "unspecified").strip().upper()
            if state != "UNSPECIFIED" and not re.fullmatch(r"[A-Z]{2}", state):
                raise HTTPException(422, "Use two-letter state codes in the CSV.")
            groups[state].append(row)
        identity = await store.create_campaign(body.tenant_id, body.request_id, body.name, body.created_by, None, {}, groups)
        await store.dispatch(body.tenant_id)
        return clean({"id": identity, "records": len(body.records), "states": len(groups), "batches": await store.campaigns(body.tenant_id)})

    @router.get("/numbers", dependencies=[Depends(workspace)])
    async def numbers(tenant_id: uuid.UUID, states: str = "", types: str = "", include_collectors: bool = False) -> dict[str, Any]:
        if isinstance(store, BaseStore):
            from base_queries import numbers as query_numbers
            regions, kinds = dimensions(states, types)
            metrics = await query_numbers(store, tenant_id, regions, kinds, include_collectors)
        else:
            reference, results = await view(tenant_id, states, types, include_collectors)
            ledger = await store.ledger(tenant_id)
            metrics = {"groups": counts(reference, results), "costs": cost_rows(results, ledger),
                       "unattributed_calls": sum(row.get("record_id") is None for row in ledger)}
        campaigns = await store.campaigns(tenant_id)
        return clean({"reference": await store.latest_file(), **metrics,
                      "states": campaigns, "states_done": sum(row["status"] == "done" for row in campaigns),
                      "verified_definition": "A completed record with at least one independently sourced website, phone or email.",
                      "failure_definition": "A record missing any requested field; one record can have several failure reasons."})

    @router.get("/records", dependencies=[Depends(workspace)])
    async def records(tenant_id: uuid.UUID, states: str = "", types: str = "", include_collectors: bool = False,
                      metric: str = "all", reason: str | None = None, batch: str | None = None,
                      offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
        if metric not in {*COUNTS, "all"}:
            raise HTTPException(422, "Unknown record count.")
        if isinstance(store, BaseStore):
            from base_queries import record_page
            regions, kinds = dimensions(states, types)
            return clean(await record_page(store, tenant_id, regions, kinds, include_collectors, metric, reason, offset, limit, batch))
        _, results = await view(tenant_id, states, types, include_collectors)
        rows = [row for row in latest([item for item in results if not batch or item.get("batch") == batch]) if matches(row, metric, reason)]
        return clean({"total": len(rows), "rows": rows[offset:offset + limit]})

    @router.get("/records.csv", dependencies=[Depends(workspace)])
    async def export(tenant_id: uuid.UUID, states: str = "", types: str = "", include_collectors: bool = False,
                     metric: str = "all", reason: str | None = None, batch: str | None = None) -> Response:
        if metric not in {*COUNTS, "all", "licensees"}:
            raise HTTPException(422, "Unknown record count.")
        if isinstance(store, BaseStore) and metric != "licensees":
            from base_queries import record_page
            regions, kinds = dimensions(states, types)
            async def stream():
                # A stable read snapshot prevents new completed rows from
                # shifting pages while a client downloads a large list.
                async with rt.pool().acquire() as conn, conn.transaction(isolation="repeatable_read", readonly=True):
                    from contextlib import asynccontextmanager
                    class SnapshotPool:
                        @asynccontextmanager
                        async def acquire(self):
                            yield conn
                    from types import SimpleNamespace
                    reader = SimpleNamespace(rt=SimpleNamespace(pool=SnapshotPool))
                    offset = 0
                    while True:
                        page = await record_page(reader, tenant_id, regions, kinds, include_collectors, metric, reason, offset, 500, batch)
                        text = export_records(page["rows"])
                        yield text if offset == 0 else text.partition("\n")[2]
                        offset += len(page["rows"])
                        if offset >= page["total"]:
                            break
            return StreamingResponse(stream(), media_type="text/csv; charset=utf-8", headers={
                "Content-Disposition": 'attachment; filename="base-records.csv"', "Cache-Control": "private, no-store"})
        reference, results = await view(tenant_id, states, types, include_collectors)
        if metric == "licensees":
            return download(csv_text(reference, ["licence_key", "licence_number", "state", "licence_type", "name", "source_url", "checked_at", "published_on"]), "reference-licences")
        if metric not in {*COUNTS, "all"}:
            raise HTTPException(422, "Unknown record count.")
        return download(export_records([row for row in latest([item for item in results if not batch or item.get("batch") == batch]) if matches(row, metric, reason)]), "base-records")

    @router.get("/ledger", dependencies=[Depends(workspace)])
    async def ledger_rows(tenant_id: uuid.UUID, state: str | None = None, month: str | None = None,
                          rung: int | None = Query(None, ge=1, le=4), include_collectors: bool = False, types: str = "",
                          offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
        regions, kinds = dimensions(state or "", types)
        state = regions[0] if regions else None
        if month and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise HTTPException(422, "Choose a valid month.")
        if isinstance(store, BaseStore):
            from base_queries import ledger_page
            return clean(await ledger_page(store, tenant_id, state, month, rung, kinds, include_collectors, offset, limit))
        results = {str(row["record_id"]): row for row in await store.results(tenant_id)}
        rows = []
        for row in await store.ledger(tenant_id):
            record = results.get(str(row.get("record_id")))
            if record and not include_collectors and record["licence_type"] == "03":
                continue
            if kinds and (not record or record["licence_type"] not in kinds):
                continue
            if state and (not record or record["state"] != state) or month and str(row["ts"])[:7] != month:
                continue
            if rung is not None and (4 if row.get("cache_hit") else row["rung"]) != rung:
                continue
            receipt = {key: row.get(key) for key in ("id", "record_id", "ts", "rung", "cache_hit", "cost_usd", "cost_status", "vendor", "units", "vendor_cost_status", "vendor_list_cost_usd", "outcome")}
            if row.get("cost_status") == "not_set":
                receipt.update(cost_usd=None, status="price not set")
            rows.append(receipt)
        return clean({"total": len(rows), "rows": rows[offset:offset + limit]})

    @router.post("/comparison", dependencies=[Depends(workspace)])
    async def import_apollo(body: ApolloUpload) -> dict[str, Any]:
        reader = csv.DictReader(io.StringIO(body.csv.lstrip("\ufeff")))
        known = {row["licence_key"]: row for row in latest(await store.results(body.tenant_id)) if row.get("licence_key")}
        rows = []
        seen = set()
        for raw in reader:
            if None in raw or any(value is None for value in raw.values()):
                raise HTTPException(422, "The Apollo CSV has an incomplete row.")
            row = {key.strip().lower().replace(" ", "_"): value.strip() for key, value in raw.items()}
            key = row.get("licence_key", "")
            if key not in known or key in seen:
                raise HTTPException(422, "Each Apollo row needs a unique licence_key from this workspace's Base records.")
            seen.add(key)
            rows.append({"licence_key": key, "base_snapshot": {name: known[key][name] for name in
                         ("record_id", "licence_key", "state", "licence_type", "fields", "checked_at")},
                         "fields": {"website": row.get("website") or row.get("company_website"),
                "phone": row.get("phone") or row.get("company_phone"), "email": row.get("email") or row.get("emails")}})
        if not rows:
            raise HTTPException(422, "The Apollo CSV has no rows.")
        identity = await store.save_apollo(body.tenant_id, hashlib.sha256(body.csv.encode()).hexdigest(), rows)
        return {"id": str(identity), "records": len(rows)}

    @router.get("/comparison", dependencies=[Depends(workspace)])
    async def comparison(tenant_id: uuid.UUID, states: str = "", types: str = "", include_collectors: bool = False) -> dict[str, Any]:
        apollo = await store.apollo(tenant_id)
        if not apollo:
            return {"states": [], "rows": []}
        regions, kinds = dimensions(states, types)
        from base_metrics import obj
        apollo = [row for row in apollo if not row.get("base_snapshot") or selected(obj(row["base_snapshot"]), regions, kinds, include_collectors)]
        if all(row.get("base_snapshot") for row in apollo):
            return clean(compare([], apollo))
        results = [row for row in await store.results(tenant_id) if selected(row, regions, kinds, include_collectors)]
        return clean(compare(results, apollo))

    @router.get("/pairs", dependencies=[Depends(workspace)])
    async def pairs(tenant_id: uuid.UUID) -> dict[str, Any]:
        async with rt.pool().acquire() as conn:
            rows = await conn.fetch("""SELECT id,input,output,source,source_ref,created_at FROM tank.training_pairs
                WHERE tenant_id=$1 AND region=$2 AND source='base_verified' ORDER BY created_at DESC LIMIT 200""", tenant_id, rt.box_region())
        return clean({"rows": [dict(row) for row in rows]})

    @router.post("/reference/refresh", dependencies=[Depends(workspace), Depends(require_admin)])
    async def refresh() -> dict[str, Any]:
        return clean(await store.refresh())

    @router.get("/prices", dependencies=[Depends(workspace), Depends(require_admin)])
    async def prices() -> dict[str, Any]:
        async with rt.pool().acquire() as conn:
            found = {code: await price(conn, code, datetime.now(timezone.utc)) for code in sorted(PRICES)}
        return clean({"rows": [{"code": code, "unit_price": row["unit_price"] if row and row["price_status"] == "set" else None,
                                 "free_pass": bool(row and row["free_pass"]),
                                 "status": "priced" if row and row["price_status"] == "set" else "price not set"} for code, row in found.items()]})

    @router.put("/prices/{code}", dependencies=[Depends(workspace), Depends(require_admin)])
    async def set_price(code: str, body: PriceChange) -> dict[str, Any]:
        if code not in PRICES or body.free_pass and code != "context.dev.credit":
            raise HTTPException(422, "Unsupported price setting.")
        async with rt.pool().acquire() as conn:
            row = await conn.fetchrow("""INSERT INTO tank.price_book(tenant_id,outcome_type,unit_price,currency,note,free_pass,price_status)
                VALUES($1,$2,$3,'USD','Founder-set expense price',$4,$5) RETURNING id,unit_price,free_pass,price_status""",
                PLATFORM, code, body.unit_price or Decimal(0), body.free_pass, "not_set" if body.unit_price is None else "set")
        return clean({**dict(row), "unit_price": body.unit_price, "status": "price not set" if row["price_status"] == "not_set" else "priced"})

    @router.post("/context-dev", dependencies=[Depends(room)])
    async def context_receipt(body: CreditReceipt) -> dict[str, Any]:
        if body.tenant_id != PLATFORM or body.region != rt.box_region():
            raise HTTPException(403, "Context trials belong to this platform region.")
        async with rt.pool().acquire() as conn:
            async with conn.transaction():
                old = await conn.fetchrow("SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2", body.id, body.tenant_id)
                if old:
                    if old["vendor"] != "context.dev" or old["units"] != body.units or old["outcome"] != body.outcome:
                        raise HTTPException(409, "This credit receipt already records another call.")
                    return {"ledger_id": str(body.id), "recorded": True}
                quote = await price(conn, "context.dev.credit", datetime.now(timezone.utc))
                rate = quote["unit_price"] if quote and quote["price_status"] == "set" else None
                list_cost = rate * body.units if rate is not None else None
                free = bool(quote and quote["free_pass"])
                actual = None if body.outcome == "unverified" else Decimal(0) if free else list_cost
                await conn.execute("""INSERT INTO tank.ledger
                    (id,tenant_id,region,agent,task_type,task_id,model,vendor,units,rung,cost_usd,outcome,
                     vendor_cost_status,vendor_unit_price,vendor_price_id,vendor_list_cost_usd,cost_status)
                    VALUES($1,$2,$3,'base','base.context_dev',$4,'vendor:context.dev','context.dev',$5,1,$6,$7,$8,$9,$10,$11,$12)""",
                    body.id, body.tenant_id, body.region, body.run_id, body.units, actual or Decimal(0), body.outcome,
                    "free_pass" if free else "unpriced" if rate is None else "priced", rate, quote["id"] if quote else None, list_cost,
                    "not_set" if actual is None or body.outcome == "unverified" else "set")
                await conn.execute("INSERT INTO tank.base_ledger_links(tenant_id,record_id,ledger_id) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                                   body.tenant_id, body.record_id, body.id)
        return {"ledger_id": str(body.id), "recorded": True}

    async def run_background() -> None:
        while True:
            try:
                if rt.box_region() == "us-east":
                    try:
                        await store.adopt()
                        if await store.due_refresh():
                            await store.refresh()
                    except Exception:
                        # Preserve a durable site block. A reference outage must
                        # not prevent independent CSV results from being collected.
                        if await store.due_refresh():
                            await store.reference_check("unavailable", "The official reference update could not be completed.")
                    for tenant in await store.tenants():
                        try:
                            await store.collect(tenant)
                            await store.dispatch(tenant)
                        except Exception as exc:
                            log.warning("Base tenant collection deferred (%s)", type(exc).__name__)
            except Exception as exc:
                log.warning("Base reference/result collection deferred (%s)", type(exc).__name__)
            await asyncio.sleep(15)

    @router.on_event("startup")
    async def startup() -> None:
        nonlocal background_task
        if background:
            background_task = asyncio.create_task(run_background())

    @router.on_event("shutdown")
    async def shutdown() -> None:
        if background_task:
            background_task.cancel()
            with suppress(asyncio.CancelledError):
                await background_task
    return router
