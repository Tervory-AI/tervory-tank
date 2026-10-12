"""Tank: the only path to any model in Tervory.

Endpoints
  GET  /health                           liveness
  POST /v1/route                         the one call agents and the Workspace make
  POST /v1/tasks                         queue a task (runs in the background through /v1/route logic)
  GET  /v1/tasks?tenant_id=              the board: a tenant's tasks, newest first
  GET  /v1/tasks/{id}?tenant_id=         one task
  POST /v1/ledger/{id}/feedback          a person's verdict on an answer: accepted | rejected
  GET  /v1/ledger/summary                spend by model and rung for a tenant (the client's ledger view)
  GET  /v1/policy                        the routing policy rows
  PUT  /v1/policy/{task_type}            change a policy row (no deploy needed)

Build Pack v2, "Tank — the centrepiece". Batch queue, cache, evals and graduation
are later build-order steps and are not in this file yet.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import Any, Literal

import asyncpg
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

DATABASE_URL = os.environ["DATABASE_URL"]
LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000")
LITELLM_MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]
TANK_API_KEY = os.environ["TANK_API_KEY"]
DEFAULT_REGION = os.environ.get("TANK_REGION", "us-east")

app = FastAPI(title="Tervory Tank", version="0.2.0")
_pool: asyncpg.Pool | None = None
_background: set[asyncio.Task[None]] = set()


def pool() -> asyncpg.Pool:
    assert _pool is not None, "database pool not ready"
    return _pool


# ---------- auth ----------

async def require_key(x_tank_key: str = Header(default="")) -> None:
    if x_tank_key != TANK_API_KEY:
        raise HTTPException(status_code=401, detail="missing or invalid X-Tank-Key")


# ---------- models ----------

class Message(BaseModel):
    role: str
    content: str


class RouteRequest(BaseModel):
    tenant_id: uuid.UUID
    agent: str = "tier0"
    task_type: str = "tier0.answer"
    priority: str | None = None          # overrides the policy's priority if set
    skill: str | None = None
    region: str | None = None
    messages: list[Message] = Field(min_length=1)


class RouteResponse(BaseModel):
    ledger_id: uuid.UUID
    model: str
    rung: int
    content: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int


class PolicyRow(BaseModel):
    task_type: str
    tenant_id: uuid.UUID | None = None
    rung: int = 1
    model: str
    priority: str = "standard"
    batch_eligible: bool = False
    cache_scope: str = "none"
    max_tokens_out: int = 1024
    system_prompt: str | None = None
    eval_threshold: float = 0.97


class TaskCreate(BaseModel):
    tenant_id: uuid.UUID
    created_by: str | None = None
    title: str = Field(min_length=1, max_length=200)
    agent: str = "tier0"
    task_type: str = "tier0.answer"
    messages: list[Message] = Field(min_length=1)


class Feedback(BaseModel):
    tenant_id: uuid.UUID
    feedback: Literal["accepted", "rejected"]
    note: str | None = Field(default=None, max_length=1000)
    by: str | None = None


# ---------- lifecycle ----------

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


@app.on_event("startup")
async def _startup() -> None:
    """Open the pool, then apply the schema. Every statement in schema.sql is
    idempotent (IF NOT EXISTS / ON CONFLICT DO NOTHING), so this is safe on
    every start and means the database can never be missing Tank's tables."""
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        ddl = f.read()
    async with _pool.acquire() as conn:
        await conn.execute(ddl)
        # Anything left 'running' from before a restart did not finish.
        await conn.execute(
            "UPDATE tank.tasks SET status='failed', error='Tank restarted mid-task', finished_at=now() "
            "WHERE status IN ('queued','running')"
        )


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _pool:
        await _pool.close()


@app.get("/health")
async def health() -> dict[str, Any]:
    async with pool().acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"ok": True, "region": DEFAULT_REGION}


# ---------- policy ----------

async def load_policy(task_type: str, tenant_id: uuid.UUID) -> dict[str, Any]:
    """Tenant-specific row first, then the platform default."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM tank.policy
            WHERE task_type = $1 AND (tenant_id = $2 OR tenant_id IS NULL)
            ORDER BY tenant_id NULLS LAST
            LIMIT 1
            """,
            task_type,
            tenant_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail=f"no policy for task_type {task_type!r}")
    return dict(row)


@app.get("/v1/policy", dependencies=[Depends(require_key)])
async def list_policy() -> list[dict[str, Any]]:
    async with pool().acquire() as conn:
        rows = await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type, tenant_id NULLS FIRST")
    return [dict(r) for r in rows]


@app.put("/v1/policy/{task_type}", dependencies=[Depends(require_key)])
async def put_policy(task_type: str, body: PolicyRow) -> dict[str, Any]:
    if body.task_type != task_type:
        raise HTTPException(status_code=400, detail="task_type in path and body differ")
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tank.policy
              (task_type, tenant_id, rung, model, priority, batch_eligible, cache_scope,
               max_tokens_out, system_prompt, eval_threshold, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10, now())
            ON CONFLICT (task_type, COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid))
            DO UPDATE SET rung=$3, model=$4, priority=$5, batch_eligible=$6, cache_scope=$7,
                          max_tokens_out=$8, system_prompt=$9, eval_threshold=$10, updated_at=now()
            """,
            body.task_type, body.tenant_id, body.rung, body.model, body.priority,
            body.batch_eligible, body.cache_scope, body.max_tokens_out, body.system_prompt,
            body.eval_threshold,
        )
    return {"ok": True}


# ---------- the one call ----------

async def run_route(req: RouteRequest, task_id: uuid.UUID | None = None) -> RouteResponse:
    """Pick the model from policy, call it through LiteLLM, write the ledger row.
    Used directly by /v1/route and in the background by tasks."""
    policy = await load_policy(req.task_type, req.tenant_id)
    model = policy["model"]
    priority = req.priority or policy["priority"]

    messages = [m.model_dump() for m in req.messages]
    if policy["system_prompt"]:
        messages = [{"role": "system", "content": policy["system_prompt"]}, *messages]

    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
            json={"model": model, "messages": messages, "max_tokens": policy["max_tokens_out"]},
        )
    latency_ms = int((time.perf_counter() - started) * 1000)

    outcome = "delivered" if r.status_code == 200 else "failed"
    data: dict[str, Any] = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    usage = data.get("usage") or {}
    tokens_in = int(usage.get("prompt_tokens") or 0)
    tokens_out = int(usage.get("completion_tokens") or 0)
    # LiteLLM reports the cost it computed from config.yaml prices in this header.
    cost_usd = float(r.headers.get("x-litellm-response-cost") or 0.0)
    content = ""
    if outcome == "delivered":
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""

    ledger_id = uuid.uuid4()
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tank.ledger
              (id, tenant_id, region, agent, skill, task_type, rung, model, priority,
               tokens_in, tokens_out, cost_usd, latency_ms, cache_hit, outcome, task_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,false,$14,$15)
            """,
            ledger_id, req.tenant_id, req.region or DEFAULT_REGION, req.agent, req.skill,
            req.task_type, policy["rung"], model, priority, tokens_in, tokens_out, cost_usd,
            latency_ms, outcome, task_id,
        )

    if outcome == "failed":
        raise HTTPException(status_code=502, detail={"ledger_id": str(ledger_id), "upstream": data or r.text[:500]})

    return RouteResponse(
        ledger_id=ledger_id, model=model, rung=policy["rung"], content=content,
        tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd, latency_ms=latency_ms,
    )


@app.post("/v1/route", response_model=RouteResponse, dependencies=[Depends(require_key)])
async def route(req: RouteRequest) -> RouteResponse:
    return await run_route(req)


# ---------- tasks: the board ----------

TASK_COLUMNS = "id, tenant_id, created_by, agent, task_type, title, status, result, error, ledger_id, created_at, started_at, finished_at"


def task_dict(row: asyncpg.Record, ledger: asyncpg.Record | None = None) -> dict[str, Any]:
    d = dict(row)
    d["call"] = dict(ledger) if ledger else None
    return d


async def _run_task(task_id: uuid.UUID, req: RouteRequest) -> None:
    async with pool().acquire() as conn:
        await conn.execute("UPDATE tank.tasks SET status='running', started_at=now() WHERE id=$1", task_id)
    try:
        res = await run_route(req, task_id=task_id)
        async with pool().acquire() as conn:
            await conn.execute(
                "UPDATE tank.tasks SET status='done', result=$2, ledger_id=$3, finished_at=now() WHERE id=$1",
                task_id, res.content, res.ledger_id,
            )
    except Exception as exc:  # noqa: BLE001 — anything that stops a task is recorded on the task
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        if isinstance(detail, dict):
            ledger_id = detail.get("ledger_id")
            detail = json.dumps(detail)[:1000]
        else:
            ledger_id = None
        async with pool().acquire() as conn:
            await conn.execute(
                "UPDATE tank.tasks SET status='failed', error=$2, ledger_id=$3, finished_at=now() WHERE id=$1",
                task_id, str(detail), uuid.UUID(ledger_id) if ledger_id else None,
            )


@app.post("/v1/tasks", dependencies=[Depends(require_key)], status_code=202)
async def create_task(body: TaskCreate) -> dict[str, Any]:
    # Fail fast on a bad task_type rather than queueing a task that can only fail.
    await load_policy(body.task_type, body.tenant_id)
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            f"""
            INSERT INTO tank.tasks (tenant_id, created_by, agent, task_type, title, input)
            VALUES ($1,$2,$3,$4,$5,$6::jsonb)
            RETURNING {TASK_COLUMNS}
            """,
            body.tenant_id, body.created_by, body.agent, body.task_type, body.title,
            json.dumps([m.model_dump() for m in body.messages]),
        )
    req = RouteRequest(tenant_id=body.tenant_id, agent=body.agent, task_type=body.task_type, messages=body.messages)
    t = asyncio.create_task(_run_task(row["id"], req))
    _background.add(t)
    t.add_done_callback(_background.discard)
    return task_dict(row)


@app.get("/v1/tasks", dependencies=[Depends(require_key)])
async def list_tasks(tenant_id: uuid.UUID, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT t.*, l.model, l.rung, l.cost_usd, l.latency_ms, l.feedback
            FROM (SELECT {TASK_COLUMNS} FROM tank.tasks WHERE tenant_id=$1 ORDER BY created_at DESC LIMIT $2) t
            LEFT JOIN tank.ledger l ON l.id = t.ledger_id
            ORDER BY t.created_at DESC
            """,
            tenant_id, limit,
        )
    return [dict(r) for r in rows]


@app.get("/v1/tasks/{task_id}", dependencies=[Depends(require_key)])
async def get_task(task_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, Any]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT t.*, l.model, l.rung, l.cost_usd, l.latency_ms, l.feedback
            FROM (SELECT {TASK_COLUMNS} FROM tank.tasks WHERE id=$1 AND tenant_id=$2) t
            LEFT JOIN tank.ledger l ON l.id = t.ledger_id
            """,
            task_id, tenant_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="no such task for this tenant")
    return dict(row)


# ---------- feedback: the outcome column ----------

@app.post("/v1/ledger/{ledger_id}/feedback", dependencies=[Depends(require_key)])
async def ledger_feedback(ledger_id: uuid.UUID, body: Feedback) -> dict[str, Any]:
    """A person's verdict on one answer. The tenant_id in the body must match the row,
    so one tenant can never rate — or even discover — another tenant's calls."""
    async with pool().acquire() as conn:
        updated = await conn.fetchval(
            """
            UPDATE tank.ledger
            SET feedback=$3, feedback_note=$4, feedback_at=now(), feedback_by=$5
            WHERE id=$1 AND tenant_id=$2 AND outcome='delivered'
            RETURNING id
            """,
            ledger_id, body.tenant_id, body.feedback, body.note, body.by,
        )
    if updated is None:
        raise HTTPException(status_code=404, detail="no delivered call with that id for this tenant")
    return {"ok": True, "ledger_id": str(ledger_id), "feedback": body.feedback}


# ---------- the client's ledger view ----------

@app.get("/v1/ledger/summary", dependencies=[Depends(require_key)])
async def ledger_summary(tenant_id: uuid.UUID, days: int = 30) -> dict[str, Any]:
    async with pool().acquire() as conn:
        by_model = await conn.fetch(
            """
            SELECT model, rung, count(*) AS calls,
                   sum(tokens_in) AS tokens_in, sum(tokens_out) AS tokens_out,
                   sum(cost_usd) AS cost_usd,
                   count(*) FILTER (WHERE outcome = 'delivered') AS delivered,
                   count(*) FILTER (WHERE feedback = 'accepted') AS accepted,
                   count(*) FILTER (WHERE feedback = 'rejected') AS rejected
            FROM tank.ledger
            WHERE tenant_id = $1 AND ts > now() - make_interval(days => $2)
            GROUP BY model, rung ORDER BY cost_usd DESC
            """,
            tenant_id, days,
        )
        totals = await conn.fetchrow(
            """
            SELECT count(*) AS calls, coalesce(sum(cost_usd),0) AS cost_usd,
                   count(*) FILTER (WHERE outcome = 'delivered') AS delivered,
                   count(*) FILTER (WHERE feedback = 'accepted') AS accepted,
                   count(*) FILTER (WHERE feedback = 'rejected') AS rejected
            FROM tank.ledger
            WHERE tenant_id = $1 AND ts > now() - make_interval(days => $2)
            """,
            tenant_id, days,
        )
    delivered = int(totals["delivered"] or 0)
    accepted = int(totals["accepted"] or 0)
    rejected = int(totals["rejected"] or 0)
    cost = float(totals["cost_usd"] or 0)
    rated = accepted + rejected
    return {
        "tenant_id": str(tenant_id),
        "days": days,
        "calls": int(totals["calls"] or 0),
        "delivered": delivered,
        "accepted": accepted,
        "rejected": rejected,
        "acceptance_rate": round(accepted / rated, 4) if rated else None,
        "cost_usd": round(cost, 6),
        "cost_per_delivered_usd": round(cost / delivered, 6) if delivered else None,
        "cost_per_accepted_usd": round(cost / accepted, 6) if accepted else None,
        "by_model": [dict(r) for r in by_model],
    }
