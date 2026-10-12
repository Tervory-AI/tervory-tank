"""Tank: the only path to any model in Tervory.

Endpoints
  GET  /health                           liveness
  POST /v1/route                         the one call agents and the Workspace make
  POST /v1/tasks                         queue a task (runs in the background through /v1/route logic)
  GET  /v1/tasks?tenant_id=              the board: a tenant's tasks, newest first
  GET  /v1/tasks/{id}?tenant_id=         one task
  POST /v1/ledger/{id}/feedback          a person's verdict on an answer: accepted | rejected
  GET  /v1/ledger/summary                spend by model and rung for a tenant (the client's ledger view)
  GET  /v1/skills                        Skala registry: every package and its state
  POST /v1/skills/{id}/{ver}/evals       run a package's golden cases; candidate -> staging on pass
  POST /v1/skills/{id}/{ver}/approve     human sign-off; previous approved version retires
  POST /v1/skills/{id}/{ver}/retire      take a version out of service
  POST /v1/skills/{id}/run               run an approved skill (preview=true allows staging/candidate)
  POST /v1/base/run                      Base passes 1-2 over a batch of records (a task)
  GET  /v1/base/records?tenant_id=       enriched records, newest first
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

import skala

DATABASE_URL = os.environ["DATABASE_URL"]
LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000")
LITELLM_MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]
TANK_API_KEY = os.environ["TANK_API_KEY"]
DEFAULT_REGION = os.environ.get("TANK_REGION", "us-east")

app = FastAPI(title="Tervory Tank", version="0.2.0")
_pool: asyncpg.Pool | None = None
_background: set[asyncio.Task[None]] = set()
_http: httpx.AsyncClient | None = None
_packages: dict[tuple[str, str], skala.SkillPackage] = {}
SKILL_ENV = {k: v for k, v in {"BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", "")}.items() if v}


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
    max_tokens: int | None = None          # a skill may ask for fewer than the policy's cap


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
    global _http, _packages
    _http = httpx.AsyncClient(headers={"User-Agent": "TervoryBase/0.1 (+https://tervory.com)"}, timeout=15)
    _packages = skala.load_packages()
    await register_packages()


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _http:
        await _http.aclose()
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
            json={"model": model, "messages": messages, "max_tokens": min(req.max_tokens or policy["max_tokens_out"], policy["max_tokens_out"])},
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



# ---------- Skala: skills ----------

async def register_packages() -> None:
    """Mirror the skills/ folder into tank.skills. New packages arrive as candidates;
    existing rows keep their state (approval is a human act, not a deploy side-effect)."""
    async with pool().acquire() as conn:
        await conn.execute("UPDATE tank.skills SET present=false")
        for pkg in _packages.values():
            await conn.execute(
                """
                INSERT INTO tank.skills (id, version, agent, rung, task_type, description, eval_threshold, cases, present)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,true)
                ON CONFLICT (id, version) DO UPDATE SET
                  agent=$3, rung=$4, task_type=$5, description=$6, eval_threshold=$7, cases=$8, present=true, updated_at=now()
                """,
                pkg.id, pkg.version, pkg.agent, pkg.rung, pkg.task_type, pkg.description,
                pkg.eval_threshold, len(pkg.cases),
            )


def get_package(skill_id: str, version: str) -> skala.SkillPackage:
    pkg = _packages.get((skill_id, version))
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"no package {skill_id}@{version} on disk")
    return pkg


async def skill_state(skill_id: str, version: str) -> str | None:
    async with pool().acquire() as conn:
        return await conn.fetchval("SELECT state FROM tank.skills WHERE id=$1 AND version=$2", skill_id, version)


async def approved_version(skill_id: str) -> str | None:
    async with pool().acquire() as conn:
        return await conn.fetchval(
            "SELECT version FROM tank.skills WHERE id=$1 AND state='approved' AND present ORDER BY approved_at DESC LIMIT 1",
            skill_id,
        )


async def _model_for_skill(**kw: Any) -> dict[str, Any]:
    """What a skill's ctx.model() calls: the normal route, tagged with the skill."""
    req = RouteRequest(
        tenant_id=kw["tenant_id"], agent=kw["agent"], task_type=kw["task_type"], skill=kw["skill"],
        messages=[Message(**m) for m in kw["messages"]], max_tokens=kw.get("max_tokens"),
    )
    res = await run_route(req, task_id=kw.get("task_id"))
    return res.model_dump()


def make_ctx(pkg: skala.SkillPackage, tenant_id: uuid.UUID, task_id: uuid.UUID | None = None, preview: bool = False) -> skala.SkillContext:
    assert _http is not None
    ref = pkg.ref + ("#preview" if preview else "")
    return skala.SkillContext(tenant_id=tenant_id, skill_ref=ref, agent=pkg.agent, task_id=task_id,
                              _model=_model_for_skill, http=_http, env=dict(SKILL_ENV))


# Evals and previews run under the platform tenant so their model spend never lands on a client.
PLATFORM_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")


@app.get("/v1/skills", dependencies=[Depends(require_key)])
async def list_skills() -> list[dict[str, Any]]:
    async with pool().acquire() as conn:
        rows = await conn.fetch("SELECT * FROM tank.skills ORDER BY agent, id, version")
    return [dict(r) for r in rows]


class EvalRun(BaseModel):
    by: str | None = None


@app.post("/v1/skills/{skill_id}/{version}/evals", dependencies=[Depends(require_key)])
async def run_skill_evals(skill_id: str, version: str, body: EvalRun | None = None) -> dict[str, Any]:
    pkg = get_package(skill_id, version)
    if not pkg.cases:
        raise HTTPException(status_code=400, detail="package has no eval cases; a skill without evals cannot leave candidate")
    result = await skala.run_evals(pkg, lambda: make_ctx(pkg, PLATFORM_TENANT, preview=True))
    passed_gate = result["score"] >= pkg.eval_threshold
    async with pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO tank.skill_evals (skill_id, version, score, passed, total, cost_usd, details, ran_by) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8)",
            skill_id, version, result["score"], result["passed"], result["total"], result["cost_usd"],
            json.dumps(result["details"]), body.by if body else None,
        )
        state = await conn.fetchval("SELECT state FROM tank.skills WHERE id=$1 AND version=$2", skill_id, version)
        new_state = state
        if state == "candidate" and passed_gate:
            new_state = "staging"
        elif state == "staging" and not passed_gate:
            new_state = "candidate"   # it regressed; back it goes
        await conn.execute(
            "UPDATE tank.skills SET last_eval_score=$3, last_eval_at=now(), state=$4, updated_at=now() WHERE id=$1 AND version=$2",
            skill_id, version, result["score"], new_state,
        )
    result["state"] = new_state
    result["gate"] = "passed" if passed_gate else "failed"
    return result


class Approval(BaseModel):
    by: str = Field(min_length=1)


@app.post("/v1/skills/{skill_id}/{version}/approve", dependencies=[Depends(require_key)])
async def approve_skill(skill_id: str, version: str, body: Approval) -> dict[str, Any]:
    """Human sign-off. Only a version in staging (evals passed) can be approved."""
    get_package(skill_id, version)
    async with pool().acquire() as conn:
        state = await conn.fetchval("SELECT state FROM tank.skills WHERE id=$1 AND version=$2", skill_id, version)
        if state != "staging":
            raise HTTPException(status_code=409, detail=f"state is {state!r}; run evals until it reaches staging first")
        async with conn.transaction():
            await conn.execute(
                "UPDATE tank.skills SET state='retired', updated_at=now() WHERE id=$1 AND state='approved' AND version<>$2",
                skill_id, version,
            )
            await conn.execute(
                "UPDATE tank.skills SET state='approved', approved_by=$3, approved_at=now(), updated_at=now() WHERE id=$1 AND version=$2",
                skill_id, version, body.by,
            )
    return {"ok": True, "skill": f"{skill_id}@{version}", "state": "approved"}


@app.post("/v1/skills/{skill_id}/{version}/retire", dependencies=[Depends(require_key)])
async def retire_skill(skill_id: str, version: str, body: Approval) -> dict[str, Any]:
    async with pool().acquire() as conn:
        n = await conn.execute("UPDATE tank.skills SET state='retired', updated_at=now() WHERE id=$1 AND version=$2", skill_id, version)
    if n.endswith(" 0"):
        raise HTTPException(status_code=404, detail="no such skill version")
    return {"ok": True, "skill": f"{skill_id}@{version}", "state": "retired", "by": body.by}


class SkillRun(BaseModel):
    tenant_id: uuid.UUID
    input: dict[str, Any]
    version: str | None = None      # default: the approved version
    preview: bool = False           # owner testing: allows candidate/staging; labelled in the ledger


@app.post("/v1/skills/{skill_id}/run", dependencies=[Depends(require_key)])
async def run_one_skill(skill_id: str, body: SkillRun) -> dict[str, Any]:
    version = body.version or await approved_version(skill_id)
    if version is None:
        raise HTTPException(status_code=409, detail=f"{skill_id} has no approved version")
    pkg = get_package(skill_id, version)
    state = await skill_state(skill_id, version)
    if state != "approved" and not body.preview:
        raise HTTPException(status_code=409, detail=f"{pkg.ref} is {state!r}; only approved versions run for clients")
    ctx = make_ctx(pkg, body.tenant_id, preview=body.preview)
    out = await skala.run_skill(pkg, body.input, ctx)
    out["_cost_usd"] = round(ctx.cost_usd, 6)
    return out


# ---------- Base: passes 1-2 over a batch ----------

BASE_PASSES_12 = ["base.normalize", "base.resolve", "base.find_site", "base.scrape_site", "base.extract"]


class BaseRun(BaseModel):
    tenant_id: uuid.UUID
    created_by: str | None = None
    batch: str = Field(min_length=1, max_length=120)
    records: list[dict[str, Any]] = Field(min_length=1, max_length=2000)
    registry: list[dict[str, Any]] | None = None   # optional engine registry for pass 1b; defaults to the batch itself
    preview: bool = False                           # allow unapproved skill versions (owner testing)
    concurrency: int = 4


async def _resolve_versions(preview: bool) -> dict[str, skala.SkillPackage]:
    out: dict[str, skala.SkillPackage] = {}
    for sid in BASE_PASSES_12:
        ver = await approved_version(sid)
        if ver is None:
            if not preview:
                raise HTTPException(status_code=409, detail=f"{sid} has no approved version; approve it in Skills or run with preview")
            # preview: newest package on disk
            cands = sorted((v for (i, v) in _packages if i == sid), reverse=True)
            if not cands:
                raise HTTPException(status_code=404, detail=f"no package for {sid}")
            ver = cands[0]
        out[sid] = get_package(sid, ver)
    return out


def _merge(profile: dict[str, Any], fields: dict[str, Any]) -> None:
    """Keep the higher-confidence value per field."""
    for k, v in fields.items():
        if not isinstance(v, dict):
            continue
        if k not in profile or int(v.get("confidence") or 0) >= int(profile[k].get("confidence") or 0):
            profile[k] = v


async def _enrich_one(rec_id: uuid.UUID, raw: dict[str, Any], registry: list[dict[str, Any]],
                      pkgs: dict[str, skala.SkillPackage], tenant_id: uuid.UUID, task_id: uuid.UUID, preview: bool) -> None:
    profile: dict[str, Any] = {}
    passes: dict[str, Any] = {}
    async with pool().acquire() as conn:
        await conn.execute("UPDATE base.records SET status='running', updated_at=now() WHERE id=$1", rec_id)
    try:
        # 1a normalise
        p = pkgs["base.normalize"]; ctx = make_ctx(p, tenant_id, task_id, preview)
        norm = await skala.run_skill(p, raw, ctx)
        _merge(profile, norm.get("fields") or {})
        passes["1a"] = {"skill": p.ref, "ms": norm.get("_ms")}

        # 1b resolve against the registry
        p = pkgs["base.resolve"]; ctx = make_ctx(p, tenant_id, task_id, preview)
        res = await skala.run_skill(p, {"record": norm, "registry": registry}, ctx)
        if res.get("match"):
            profile["registry_match"] = {"value": res["match"].get("id"), "source": f"registry:{res['verdict']}", "confidence": int(res.get("score") or 0)}
        passes["1b"] = {"skill": p.ref, "ms": res.get("_ms"), "verdict": res.get("verdict"), "score": res.get("score")}

        name = (profile.get("name") or {}).get("value") or raw.get("name") or ""
        city = (profile.get("city") or {}).get("value") or ""
        state = (profile.get("state") or {}).get("value") or ""

        # 2a website
        p = pkgs["base.find_site"]; ctx = make_ctx(p, tenant_id, task_id, preview)
        site = await skala.run_skill(p, {"name": name, "city": city, "state": state, "website": raw.get("website") or raw.get("url") or ""}, ctx)
        if site.get("website"):
            profile["website"] = site["website"]
        passes["2a"] = {"skill": p.ref, "ms": site.get("_ms"), "source": (site.get("website") or {}).get("source")}

        url = (profile.get("website") or {}).get("value")
        if url:
            # 2b scrape
            p = pkgs["base.scrape_site"]; ctx = make_ctx(p, tenant_id, task_id, preview)
            scr = await skala.run_skill(p, {"website": url}, ctx)
            src = "site"
            if scr.get("emails"):
                profile["emails"] = {"value": scr["emails"][:5], "source": src, "confidence": 80}
            if scr.get("phones"):
                _merge(profile, {"phone": {"value": scr["phones"][0], "source": src, "confidence": 80}})
                profile["phones"] = {"value": scr["phones"][:3], "source": src, "confidence": 80}
            if scr.get("socials"):
                profile["socials"] = {"value": scr["socials"], "source": src, "confidence": 85}
            passes["2b"] = {"skill": p.ref, "ms": scr.get("_ms"), "pages": len(scr.get("pages") or []), "error": scr.get("error")}

            # 2c extract
            if (scr.get("text") or "") and len(scr["text"]) >= 40:
                p = pkgs["base.extract"]; ctx = make_ctx(p, tenant_id, task_id, preview)
                ex = await skala.run_skill(p, {"name": name, "text": scr["text"]}, ctx)
                conf = int(ex.get("confidence") or 0)
                for k in ("categories", "services", "description", "people"):
                    if ex.get(k):
                        profile[k] = {"value": ex[k], "source": "site:model", "confidence": conf}
                passes["2c"] = {"skill": p.ref, "ms": ex.get("_ms"), "cost_usd": round(ctx.cost_usd, 6)}

        # provisional overall confidence (pass 7 will own this properly)
        core = [profile.get(k, {}).get("confidence", 0) for k in ("name", "city", "state", "website")]
        bonus = 10 if profile.get("emails") else 0
        confidence = min(100, int(sum(core) / len(core)) + bonus)
        async with pool().acquire() as conn:
            await conn.execute(
                "UPDATE base.records SET status='done', profile=$2::jsonb, passes=$3::jsonb, confidence=$4, updated_at=now() WHERE id=$1",
                rec_id, json.dumps(profile), json.dumps(passes), confidence,
            )
    except Exception as exc:  # noqa: BLE001
        async with pool().acquire() as conn:
            await conn.execute(
                "UPDATE base.records SET status='failed', error=$2, profile=$3::jsonb, passes=$4::jsonb, updated_at=now() WHERE id=$1",
                rec_id, str(exc)[:1000], json.dumps(profile), json.dumps(passes),
            )


async def _run_base_batch(task_id: uuid.UUID, body: BaseRun, rec_ids: list[uuid.UUID], pkgs: dict[str, skala.SkillPackage]) -> None:
    async with pool().acquire() as conn:
        await conn.execute("UPDATE tank.tasks SET status='running', started_at=now() WHERE id=$1", task_id)
    # Registry for pass 1b: what the client supplied, else the batch itself (finds duplicates).
    norm_pkg = pkgs["base.normalize"]
    registry = body.registry
    if registry is None:
        registry = []
        for i, raw in enumerate(body.records):
            n = await skala.run_skill(norm_pkg, raw, make_ctx(norm_pkg, body.tenant_id, task_id, body.preview))
            f = n.get("fields") or {}
            registry.append({"id": str(rec_ids[i]), "name_key": f.get("name_key", {}).get("value", ""),
                             "city": str(f.get("city", {}).get("value", "")).lower(), "state": str(f.get("state", {}).get("value", "")).lower()})
    sem = asyncio.Semaphore(max(1, min(body.concurrency, 8)))

    async def one(i: int) -> None:
        async with sem:
            # exclude the record itself from its own registry so it matches siblings, not itself
            reg = [r for r in registry if r.get("id") != str(rec_ids[i])] if body.registry is None else registry
            await _enrich_one(rec_ids[i], body.records[i], reg, pkgs, body.tenant_id, task_id, body.preview)

    await asyncio.gather(*(one(i) for i in range(len(rec_ids))))
    async with pool().acquire() as conn:
        done, failed, cost = await conn.fetchrow(
            """
            SELECT count(*) FILTER (WHERE status='done'), count(*) FILTER (WHERE status='failed'),
                   (SELECT coalesce(sum(cost_usd),0) FROM tank.ledger WHERE task_id=$1)
            FROM base.records WHERE task_id=$1
            """, task_id,
        )
        await conn.execute(
            "UPDATE tank.tasks SET status='done', result=$2, finished_at=now() WHERE id=$1",
            task_id, f"{done} enriched, {failed} failed, model spend ${float(cost):.4f}",
        )


@app.post("/v1/base/run", dependencies=[Depends(require_key)], status_code=202)
async def base_run(body: BaseRun) -> dict[str, Any]:
    pkgs = await _resolve_versions(body.preview)
    async with pool().acquire() as conn:
        task = await conn.fetchrow(
            f"""
            INSERT INTO tank.tasks (tenant_id, created_by, agent, task_type, title, input)
            VALUES ($1,$2,'base','base.enrich',$3,$4::jsonb) RETURNING {TASK_COLUMNS}
            """,
            body.tenant_id, body.created_by, f"Base passes 1-2: {body.batch} ({len(body.records)} records)",
            json.dumps({"batch": body.batch, "count": len(body.records), "preview": body.preview}),
        )
        rec_ids: list[uuid.UUID] = []
        for raw in body.records:
            rid = await conn.fetchval(
                "INSERT INTO base.records (tenant_id, task_id, batch, raw) VALUES ($1,$2,$3,$4::jsonb) RETURNING id",
                body.tenant_id, task["id"], body.batch, json.dumps(raw),
            )
            rec_ids.append(rid)
    t = asyncio.create_task(_run_base_batch(task["id"], body, rec_ids, pkgs))
    _background.add(t)
    t.add_done_callback(_background.discard)
    return {"task": task_dict(task), "records": len(rec_ids), "skills": {k: v.ref for k, v in pkgs.items()}}


@app.get("/v1/base/records", dependencies=[Depends(require_key)])
async def base_records(tenant_id: uuid.UUID, task_id: uuid.UUID | None = None, limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 2000))
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, task_id, batch, raw, profile, passes, confidence, status, error, created_at, updated_at
            FROM base.records WHERE tenant_id=$1 AND ($2::uuid IS NULL OR task_id=$2)
            ORDER BY created_at DESC LIMIT $3
            """, tenant_id, task_id, limit,
        )
    out = []
    for r in rows:
        d = dict(r)
        for k in ("raw", "profile", "passes"):
            d[k] = json.loads(d[k]) if isinstance(d[k], str) else d[k]
        out.append(d)
    return out


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
