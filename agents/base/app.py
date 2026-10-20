"""Base — passes 1–7 over a batch, in its own room. It knows no industry."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import uuid
from typing import Any

from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, Field

from chassis.app import create_app
from chassis.jobs import JobContext
from gold_sources import read_candidates
from pipeline import order_states, state_of
from room import (
    SQL_BATCHES_BY_TENANT,
    SQL_RECORDS_BY_TENANT,
    SQL_REQUEUE_TASKS,
    SQL_RETRY,
    SkillClient,
    SkillError,
    UnknownEngine,
    base_loop,
    insert_batch,
    task_dict,
    wake,
)

AGENT = os.environ.get("AGENT_NAME", "base")
HEARTBEAT_TENANT = "00000000-0000-0000-0000-000000000001"
TANK_URL = os.environ.get("TANK_URL", "http://tank:8000")

log = logging.getLogger("agent")
_worker_lock = asyncio.Lock()
_worker_on = False


async def ping(ctx: JobContext) -> dict:
    result: dict = {"pong": True, "agent": ctx.agent}
    if ctx.input.get("heartbeat"):
        try:
            saved = await ctx.memory.remember(
                ctx.tenant_id,
                f"{ctx.agent} heartbeat",
                "heartbeat",
                "schedule:*/5",
            )
            result["heartbeats_seen"] = saved.get("seen")
        except Exception as exc:  # noqa: BLE001 — class name only, never the message
            log.warning("heartbeat memory failed (%s)", type(exc).__name__)
            result["memory"] = "unreachable"
    return result


app = create_app(
    agent=AGENT,
    handlers={"ping": ping},
    schedules=[
        {
            "tenant_id": HEARTBEAT_TENANT,
            "cron": "*/5 * * * *",
            "kind": "ping",
            "input": {"heartbeat": True},
        }
    ],
)


@app.get("/gold/candidates")
async def gold_candidates(
    limit: int = Query(default=200, ge=1, le=200),
    x_tank_key: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    expected = os.environ.get("TANK_KEY", "")
    if not expected or not x_tank_key or not hmac.compare_digest(x_tank_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="room key required")
    try:
        return await asyncio.to_thread(
            read_candidates, limit=limit, region=os.environ.get("TANK_REGION", "us-east"),
        )
    except (OSError, ValueError):
        raise HTTPException(status_code=503, detail="gold evidence unavailable") from None


def _skills() -> SkillClient:
    return SkillClient(app.state.http, TANK_URL, os.environ.get("TANK_KEY", ""))


async def ensure_worker() -> None:
    global _worker_on
    if _worker_on:
        return
    async with _worker_lock:
        if _worker_on or getattr(app.state, "pool", None) is None:
            return
        _worker_on = True
        asyncio.create_task(base_loop(app.state.pool, _skills()))


@app.middleware("http")
async def _boot_worker(request, call_next):  # noqa: ANN001 — Starlette's middleware signature
    await ensure_worker()
    return await call_next(request)


class BaseRun(BaseModel):
    tenant_id: uuid.UUID
    created_by: str | None = None
    batch: str = Field(min_length=1, max_length=120)
    records: list[dict[str, Any]] = Field(min_length=1, max_length=100000)
    registry: list[dict[str, Any]] | None = None
    engine: str | None = None
    preview: bool = False
    concurrency: int = 8
    split_by_state: bool = False


class BaseRetry(BaseModel):
    tenant_id: uuid.UUID
    batch: str


class BaseRerun(BaseModel):
    tenant_id: uuid.UUID
    batch: str
    flag: str = "no_website"
    preview: bool | None = None
    skill: str | None = None


def _http_skill(exc: SkillError) -> HTTPException:
    status = exc.status if exc.status in (404, 409, 400) else 502
    return HTTPException(status_code=status, detail=exc.detail or "skill call failed")


@app.post("/v1/base/run", status_code=202)
async def base_run(body: BaseRun) -> dict[str, Any]:
    """Queue a batch. With split_by_state, one batch per state, smallest first."""
    await ensure_worker()
    skills = _skills()
    try:
        versions, refs = await skills.pin(body.preview, body.engine)
        call = skills.bind(versions, body.preview, str(body.tenant_id))
    except UnknownEngine as exc:
        raise HTTPException(status_code=404, detail=f"no engine {exc.engine!r}; known: {exc.known}") from exc
    except SkillError as exc:
        raise _http_skill(exc) from exc
    tasks: list[dict[str, Any]] = []
    labels: list[str] = []
    async with app.state.pool.acquire() as conn:
        if body.split_by_state:
            groups: dict[str, list[dict[str, Any]]] = {}
            for raw in body.records:
                groups.setdefault(await state_of(raw, body.engine, call), []).append(raw)
            order = order_states(groups)
            for number, (state, records) in enumerate(order, 1):
                row = await insert_batch(
                    conn, body.tenant_id, body.created_by, f"{body.batch} · {state}", records,
                    f" · {number}/{len(order)}", body.preview, body.engine, body.concurrency, body.registry,
                )
                tasks.append(task_dict(row))
                labels.append(f"{body.batch} · {state}")
        else:
            row = await insert_batch(
                conn, body.tenant_id, body.created_by, body.batch, body.records, "",
                body.preview, body.engine, body.concurrency, body.registry,
            )
            tasks.append(task_dict(row))
            labels.append(body.batch)
    wake()
    return {
        "task": tasks[0],
        "tasks": tasks,
        "labels": labels,
        "records": len(body.records),
        "batches": len(tasks),
        "skills": refs,
    }


@app.post("/v1/base/retry")
async def base_retry(body: BaseRetry) -> dict[str, Any]:
    await ensure_worker()
    async with app.state.pool.acquire() as conn:
        count = await conn.fetchval(SQL_RETRY, body.tenant_id, body.batch)
        if count:
            await conn.execute(SQL_REQUEUE_TASKS, body.tenant_id, body.batch)
    wake()
    return {"requeued": int(count or 0)}


@app.post("/v1/base/rerun")
async def base_rerun(body: BaseRerun) -> dict[str, Any]:
    await ensure_worker()
    async with app.state.pool.acquire() as conn:
        if body.flag == "model_skipped":
            count = await conn.fetchval(
                """
                WITH r AS (UPDATE agent_base.records SET status='queued', error=NULL, updated_at=now()
                           WHERE tenant_id=$1 AND batch=$2 AND status='done'
                             AND EXISTS (SELECT 1 FROM jsonb_each(passes) p
                                         WHERE jsonb_typeof(p.value)='object' AND p.value ? 'skipped')
                           RETURNING id)
                SELECT count(*) FROM r
                """,
                body.tenant_id,
                body.batch,
            )
        elif body.skill:
            count = await conn.fetchval(
                """
                WITH r AS (UPDATE agent_base.records SET status='queued', error=NULL, updated_at=now()
                           WHERE tenant_id=$1 AND batch=$2 AND status='done'
                             AND EXISTS (SELECT 1 FROM jsonb_each(passes) p
                                         WHERE jsonb_typeof(p.value)='object' AND p.value->>'skill' = $3)
                           RETURNING id)
                SELECT count(*) FROM r
                """,
                body.tenant_id,
                body.batch,
                body.skill,
            )
        else:
            count = await conn.fetchval(
                """
                WITH r AS (UPDATE agent_base.records SET status='queued', error=NULL, updated_at=now()
                           WHERE tenant_id=$1 AND batch=$2 AND status='done'
                             AND profile->'flags'->'value' ? $3
                           RETURNING id)
                SELECT count(*) FROM r
                """,
                body.tenant_id,
                body.batch,
                body.flag,
            )
        if count:
            if body.preview is not None:
                await conn.execute(
                    """
                    UPDATE agent_base.tasks SET input = jsonb_set(input, '{preview}', to_jsonb($3::boolean))
                    WHERE tenant_id=$1 AND task_type='base.enrich'
                      AND id IN (SELECT DISTINCT task_id FROM agent_base.records WHERE tenant_id=$1 AND batch=$2)
                    """,
                    body.tenant_id,
                    body.batch,
                    body.preview,
                )
            await conn.execute(SQL_REQUEUE_TASKS, body.tenant_id, body.batch)
    wake()
    return {"requeued": int(count or 0)}


@app.get("/v1/base/batches")
async def base_batches(tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(SQL_BATCHES_BY_TENANT, tenant_id)
    return [dict(row) for row in rows]


@app.get("/v1/base/engines")
async def base_engines() -> list[str]:
    try:
        return await _skills().engines()
    except SkillError as exc:
        raise _http_skill(exc) from exc


@app.get("/v1/base/records")
async def base_records(
    tenant_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
    batch: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 5000))
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(SQL_RECORDS_BY_TENANT, tenant_id, task_id, batch, limit, max(0, offset))
    out = []
    for row in rows:
        data = dict(row)
        for key in ("raw", "profile", "passes"):
            data[key] = json.loads(data[key]) if isinstance(data[key], str) else data[key]
        out.append(data)
    return out
