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
  POST /v1/base/run                      proxy to the Base room (passes 1-7; split_by_state = one batch per state, smallest first)
  POST /v1/base/retry                    proxy: re-queue a batch's failed records
  POST /v1/base/rerun                    proxy: re-run a batch's flagged records (e.g. no_website) with current skills
  GET  /v1/base/batches                  proxy: per-batch counts (status, tier, site/email coverage)
  GET  /v1/base/engines                  proxy: vertical engines available (e.g. ffl)
  GET  /v1/base/records?tenant_id=       proxy: enriched records, newest first
  GET  /v1/policy                        the routing policy rows
  PUT  /v1/policy/{task_type}            change a policy row (no deploy needed)

Build Pack v2, "Tank — the centrepiece". Batch queue, cache, evals and graduation
are later build-order steps and are not in this file yet.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

import graduate
import skala

log = logging.getLogger("tank")

DATABASE_URL = os.environ["DATABASE_URL"]
LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000")
LITELLM_MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]
TANK_API_KEY = os.environ["TANK_API_KEY"]
DEFAULT_REGION = os.environ.get("TANK_REGION", "us-east")

app = FastAPI(title="Tervory Tank", version="0.2.0")
_pool: asyncpg.Pool | None = None
_background: set[asyncio.Task[None]] = set()
_http: httpx.AsyncClient | None = None
_redis: aioredis.Redis | None = None
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CACHE_TTL_S = int(os.environ.get("TANK_CACHE_TTL_S", str(7 * 24 * 3600)))
_packages: dict[tuple[str, str], skala.SkillPackage] = {}
SKILL_ENV = {k: v for k, v in {"BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", ""),
                                "SEARXNG_URL": os.environ.get("SEARXNG_URL", ""),
                                "TIGER_URL": os.environ.get("TIGER_URL", "")}.items() if v}


def pool() -> asyncpg.Pool:
    assert _pool is not None, "database pool not ready"
    return _pool


# ---------- auth ----------

# SHA-256 digests of TANK_KEY_<AGENT>. Authentication reads this map, never the table.
# The table is written once per process so a removed env var is deleted, then left alone.
_agent_key_hashes: dict[str, bytes] = {}
_agent_keys_synced = False


async def require_key(request: Request, x_tank_key: str = Header(default="")) -> str | None:
    """Accept the Workspace key, or one agent key from TANK_KEY_<AGENT>.

    Returns None for the Workspace (TANK_API_KEY, unchanged) and the agent id
    for an agent key. Agent keys are taken from the environment only, compared
    as SHA-256 bytes. A removed TANK_KEY_* stops matching. The table is synced
    once; it is never used to authenticate. The raw key is never logged.
    An agent key may call /health, /v1/route, and /v1/skills/{id}/run only.
    """
    import hmac

    global _agent_key_hashes, _agent_keys_synced

    def same(left: bytes, right: bytes) -> bool:
        if len(left) != len(right):
            return False
        return hmac.compare_digest(left, right)

    found: dict[str, bytes] = {}
    for env_name, env_val in os.environ.items():
        if not env_name.startswith("TANK_KEY_"):
            continue
        value = env_val.strip()
        if not value:
            continue
        agent = env_name[len("TANK_KEY_"):].lower()
        if not agent or not all(ch.isalnum() or ch == "_" for ch in agent):
            continue
        found[agent] = hashlib.sha256(value.encode()).digest()
    _agent_key_hashes = found

    if not _agent_keys_synced and _pool is not None:
        try:
            async with pool().acquire() as conn:
                async with conn.transaction():
                    for agent_name, digest in _agent_key_hashes.items():
                        await conn.execute(
                            """
                            INSERT INTO tank.agent_keys (agent, key_hash)
                            VALUES ($1, $2)
                            ON CONFLICT (agent) DO UPDATE SET key_hash = EXCLUDED.key_hash
                            WHERE tank.agent_keys.key_hash IS DISTINCT FROM EXCLUDED.key_hash
                            """,
                            agent_name,
                            digest.hex(),
                        )
                    await conn.execute(
                        "DELETE FROM tank.agent_keys WHERE agent <> ALL($1::text[])",
                        list(_agent_key_hashes),
                    )
            _agent_keys_synced = True
        except Exception:  # noqa: BLE001 — never log the key, the hash, or the driver error
            log.warning("agent key sync skipped")

    presented = x_tank_key or ""
    try:
        presented_bytes = presented.encode()
        workspace_bytes = TANK_API_KEY.encode()
    except UnicodeError:
        raise HTTPException(status_code=401, detail="missing or invalid X-Tank-Key") from None
    if same(presented_bytes, workspace_bytes):
        return None

    matched: str | None = None
    if presented_bytes:
        presented_hash = hashlib.sha256(presented_bytes).digest()
        for agent_name, digest in _agent_key_hashes.items():
            if same(digest, presented_hash):
                matched = agent_name
                break
    if matched is None:
        raise HTTPException(status_code=401, detail="missing or invalid X-Tank-Key")
    path = request.url.path
    skill_run = path.startswith("/v1/skills/") and path.endswith("/run") and path.count("/") == 4
    if path not in {"/health", "/v1/route"} and not skill_run:
        raise HTTPException(status_code=403, detail="This agent key cannot call that.")
    return matched


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
        # A one-shot task (chat, draft) that was mid-flight when Tank restarted did not finish.
        # Base batches are not in this list: Base resumes them in its own room.
        await conn.execute(
            "UPDATE tank.tasks SET status='failed', error='Tank restarted mid-task', finished_at=now() "
            "WHERE status IN ('queued','running') AND task_type <> 'base.enrich'"
        )
    global _http, _packages
    _http = httpx.AsyncClient(headers={"User-Agent": "TervoryBase/0.1 (+https://tervory.com)"}, timeout=15)
    global _redis
    try:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        await _redis.ping()
    except Exception as exc:  # noqa: BLE001 — the cache is an optimisation; Tank runs without it
        log.warning("redis unavailable, rung-4 cache off: %s", exc)
        _redis = None
    _packages = skala.load_packages()
    await register_packages()


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _redis:
        await _redis.aclose()
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
    max_tokens = min(req.max_tokens or policy["max_tokens_out"], policy["max_tokens_out"])

    # ---- rung 4: the cache. Same task type, model and messages → the answer we already paid for.
    # Scope comes from policy: 'tenant' keys include the tenant (answers never cross tenants);
    # 'platform' is shared (only for task types whose answers hold nothing tenant-specific).
    cache_key = None
    if _redis is not None and policy.get("cache_scope") in ("tenant", "platform"):
        scope = str(req.tenant_id) if policy["cache_scope"] == "tenant" else "platform"
        digest = hashlib.sha256(json.dumps([req.task_type, model, max_tokens, messages], sort_keys=True).encode()).hexdigest()
        cache_key = f"tank:cache:{scope}:{digest}"
        try:
            hit = await _redis.get(cache_key)
        except Exception:  # noqa: BLE001
            hit = None
        if hit:
            cached = json.loads(hit)
            ledger_id = uuid.uuid4()
            async with pool().acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tank.ledger
                      (id, tenant_id, region, agent, skill, task_type, rung, model, priority,
                       tokens_in, tokens_out, cost_usd, latency_ms, cache_hit, outcome, task_id)
                    VALUES ($1,$2,$3,$4,$5,$6,4,$7,$8,0,0,0,0,true,'delivered',$9)
                    """,
                    ledger_id, req.tenant_id, req.region or DEFAULT_REGION, req.agent, req.skill,
                    req.task_type, model, priority, task_id,
                )
            return RouteResponse(ledger_id=ledger_id, model=model, rung=4, content=cached["content"],
                                 tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=0)

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{LITELLM_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
            )
    except httpx.HTTPError as exc:
        # The gateway never answered. Still a call on the books, so the failure rate is honest.
        latency_ms = int((time.perf_counter() - started) * 1000)
        ledger_id = uuid.uuid4()
        err = f"no answer: {type(exc).__name__}: {str(exc)[:200]}"
        async with pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tank.ledger
                  (id, tenant_id, region, agent, skill, task_type, rung, model, priority,
                   tokens_in, tokens_out, cost_usd, latency_ms, cache_hit, outcome, task_id, error)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,0,0,0,$10,false,'failed',$11,$12)
                """,
                ledger_id, req.tenant_id, req.region or DEFAULT_REGION, req.agent, req.skill,
                req.task_type, policy["rung"], model, priority, latency_ms, task_id, err,
            )
        raise HTTPException(status_code=502, detail={"ledger_id": str(ledger_id), "upstream": err}) from exc
    latency_ms = int((time.perf_counter() - started) * 1000)

    outcome = "delivered" if r.status_code == 200 else "failed"
    try:
        data: dict[str, Any] = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    except ValueError:
        data = {}
    error = None
    if outcome == "failed":
        msg = ((data.get("error") or {}).get("message") if isinstance(data.get("error"), dict) else data.get("error")) or r.text
        error = f"{r.status_code}: {' '.join(str(msg).split())[:300]}"
    usage = data.get("usage") or {}
    tokens_in = int(usage.get("prompt_tokens") or 0)
    tokens_out = int(usage.get("completion_tokens") or 0)
    # LiteLLM reports the cost it computed from config.yaml prices in this header.
    cost_usd = float(r.headers.get("x-litellm-response-cost") or 0.0)
    # The gateway picks the cheapest model with funds (litellm/config.yaml); the ledger records the
    # roster model that actually answered, so spend is booked to the right provider.
    answered = r.headers.get("x-litellm-model-group") or model
    content = ""
    if outcome == "delivered":
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""

    ledger_id = uuid.uuid4()
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tank.ledger
              (id, tenant_id, region, agent, skill, task_type, rung, model, priority,
               tokens_in, tokens_out, cost_usd, latency_ms, cache_hit, outcome, task_id, error)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,false,$14,$15,$16)
            """,
            ledger_id, req.tenant_id, req.region or DEFAULT_REGION, req.agent, req.skill,
            req.task_type, policy["rung"], answered, priority, tokens_in, tokens_out, cost_usd,
            latency_ms, outcome, task_id, error,
        )

    if outcome == "failed":
        raise HTTPException(status_code=502, detail={"ledger_id": str(ledger_id), "upstream": data or r.text[:500]})

    if cache_key and content:
        try:
            await _redis.set(cache_key, json.dumps({"content": content, "ledger_id": str(ledger_id)}), ex=CACHE_TTL_S)
        except Exception:  # noqa: BLE001
            pass

    # Graduation: shadow the candidate on a share of calls; it never affects this answer.
    if policy.get("candidate_model") and float(policy.get("shadow_rate") or 0) > random.random():
        t = asyncio.create_task(_shadow(req, policy, messages, max_tokens, ledger_id, content, cost_usd))
        _background.add(t)
        t.add_done_callback(_background.discard)

    # The learning corpus: what was asked, what came back (system prompt stays in policy).
    async with pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO tank.transcripts (ledger_id, tenant_id, task_type, messages, content) VALUES ($1,$2,$3,$4::jsonb,$5)",
            ledger_id, req.tenant_id, req.task_type, json.dumps([m.model_dump() for m in req.messages]), content[:20000],
        )

    return RouteResponse(
        ledger_id=ledger_id, model=answered, rung=policy["rung"], content=content,
        tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd, latency_ms=latency_ms,
    )


async def _llm(model: str, messages: list[dict[str, str]], max_tokens: int) -> tuple[str, float]:
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
        )
    if r.status_code != 200:
        raise RuntimeError(f"{model}: {r.status_code} {r.text[:200]}")
    data = r.json()
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    return content, float(r.headers.get("x-litellm-response-cost") or 0.0)


def _shadow_budget() -> float:
    raw = os.environ.get("TANK_SHADOW_BUDGET_USD", "1")
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    return value if value >= 0 else 1.0


def _roster_path() -> Path:
    env = os.environ.get("LITELLM_CONFIG")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "litellm" / "config.yaml"


def _price_quotes() -> list[graduate.Quote]:
    path = _roster_path()
    if not path.is_file():
        return []
    return graduate.load_price_roster(path)


async def _shadow_budget_open(task_type: str) -> bool:
    async with pool().acquire() as conn:
        spent = await conn.fetchval(
            "SELECT coalesce(spent_usd, 0) FROM tank.shadow_spend WHERE task_type=$1 AND day=CURRENT_DATE",
            task_type,
        )
    return graduate.budget_open(float(spent or 0), _shadow_budget(), code=False)


async def _add_spend(conn: Any, task_type: str, amount: float) -> None:
    if amount <= 0:
        return
    await conn.execute(
        """
        INSERT INTO tank.shadow_spend (task_type, day, spent_usd)
        VALUES ($1, CURRENT_DATE, $2)
        ON CONFLICT (task_type, day) DO UPDATE
          SET spent_usd = tank.shadow_spend.spent_usd + EXCLUDED.spent_usd
        """,
        task_type, amount,
    )


async def _run_code_candidate(req: RouteRequest, cand: str, messages: list[dict[str, str]]) -> tuple[str, float]:
    """Run an approved model-free skill on the same input. A model call here is a failure."""
    parsed = graduate.parse_skill(cand)
    if parsed is None:
        raise RuntimeError("a code candidate looks like skill:id@version")
    skill_id, version = parsed
    pkg = get_package(skill_id, version)
    state = await skill_state(skill_id, version)
    problem = graduate.code_candidate_problem(cand, state=state, task_type=pkg.task_type, on_disk=True)
    if problem:
        raise RuntimeError(problem)
    if _http is None:
        raise RuntimeError("skill runner is not ready")

    async def _forbid(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("code candidate called a model")

    ctx = skala.SkillContext(
        tenant_id=req.tenant_id, skill_ref=pkg.ref, agent=pkg.agent, task_id=None,
        _model=_forbid, http=_http, env=dict(SKILL_ENV),
    )
    out = await skala.run_skill(pkg, graduate.skill_payload(messages), ctx)
    if ctx.calls:
        raise RuntimeError("code candidate called a model")
    return json.dumps(out), 0.0


async def _shadow(req: RouteRequest, policy: dict[str, Any], messages: list[dict[str, str]], max_tokens: int,
                  ledger_id: uuid.UUID, primary: str, primary_cost: float) -> None:
    """Run the candidate on the same input, score agreement with the primary, record both.
    The client already has the primary answer. Spend lands on the platform tenant.
    Code skills cost nothing and are not subject to the daily shadow budget."""
    cand = policy["candidate_model"]
    if graduate.is_semantic_cache(cand):
        # Proved by graduate.semantic_lookup (local vectors, no paid call) before it is switched on.
        return
    if graduate.is_tool(cand):
        log.warning("shadow %s skipped %s: a paid tool is not started from here", req.task_type, cand)
        return
    code = graduate.is_skill(cand)
    if not code and not await _shadow_budget_open(req.task_type):
        log.warning("shadow %s skipped %s: daily budget spent", req.task_type, cand)
        return
    cand_content, cand_cost, agreement, method, fields = None, 0.0, None, "failed", {}
    try:
        if code:
            cand_content, cand_cost = await _run_code_candidate(req, cand, messages)
        else:
            cand_content, cand_cost = await _llm(cand, messages, max_tokens)
        compared = graduate.compare(primary, cand_content, tolerance=float(policy.get("number_tolerance") or 0.01))
        if compared.method == "fields":
            agreement, method, fields = compared.agreement, "fields", compared.fields
        else:
            jp = await load_policy("tank.judge", PLATFORM_TENANT)
            jmsgs = [{"role": "system", "content": jp["system_prompt"]},
                     {"role": "user", "content": f"REQUEST:\n{messages[-1]['content'][:3000]}\n\nFIRST ANSWER:\n{primary[:4000]}\n\nSECOND ANSWER:\n{cand_content[:4000]}"}]
            verdict, jcost = await _llm(jp["model"], jmsgs, jp["max_tokens_out"])
            cand_cost += jcost
            found = re.search(r"\d{1,3}", verdict)
            agreement, method = (min(100, int(found.group())) / 100 if found else None), "judge"
    except Exception as exc:  # noqa: BLE001
        log.warning("shadow %s→%s failed: %s", policy["model"], cand, exc)
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tank.shadow (ledger_id, tenant_id, task_type, primary_model, candidate_model, primary_content,
                                     candidate_content, candidate_cost_usd, primary_cost_usd, agreement, method, fields)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb)
            """,
            ledger_id, req.tenant_id, req.task_type, policy["model"], cand, primary[:20000],
            (cand_content or "")[:20000], cand_cost, primary_cost, agreement, method, json.dumps(fields),
        )
        # The candidate's spend is platform R&D: logged, visible, not on the client's bill.
        await conn.execute(
            """
            INSERT INTO tank.ledger (tenant_id, region, agent, task_type, rung, model, priority, tokens_in, tokens_out,
                                     cost_usd, latency_ms, cache_hit, outcome)
            VALUES ($1,$2,'tank',$3,$4,$5,'batch',0,0,$6,0,false,$7)
            """,
            PLATFORM_TENANT, DEFAULT_REGION, f"{req.task_type}#shadow", 3 if code else 1, cand, cand_cost,
            "delivered" if cand_content is not None else "failed",
        )
        await _add_spend(conn, req.task_type, cand_cost)
    await _move_task(req.task_type)


# ---------- graduation: the ladder ----------

_POLICY_MOVE = """
    SELECT task_type, model, candidate_model, previous_model, rung, eval_threshold,
           min_shadow_samples, max_reject_rate, auto_promote, field_floors,
           semantic_cache, promoted_at, number_tolerance, shadow_rate
    FROM tank.policy
    WHERE task_type=$1 AND tenant_id IS NULL
"""


class CandidateBody(BaseModel):
    candidate_model: str | None = None
    shadow_rate: float = Field(default=1.0, ge=0, le=1)
    by: str | None = None


class PromoteBody(BaseModel):
    by: str | None = None


class SearchBody(BaseModel):
    by: str | None = None
    force: bool = False


class AutoBody(BaseModel):
    auto_promote: bool
    by: str | None = None


def _num(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _rung_for(name: str | None) -> tuple[int, bool]:
    text = str(name or "")
    if text.startswith("skill:"):
        return 3, False
    if text.startswith("cache:"):
        return 4, True
    return 1, False


async def _load_evidence(conn: Any, policy: dict[str, Any]) -> graduate.Evidence:
    task_type = policy["task_type"]
    candidate = policy.get("candidate_model")
    if candidate:
        rows = await conn.fetch(
            """
            SELECT agreement, fields FROM tank.shadow
            WHERE task_type=$1 AND candidate_model=$2 AND agreement IS NOT NULL
            """,
            task_type, candidate,
        )
        agreements = [float(row["agreement"]) for row in rows if row["agreement"] is not None]
        feedback = await conn.fetchrow(
            """
            SELECT count(*) FILTER (WHERE feedback='rejected') AS rejected,
                   count(*) FILTER (WHERE feedback IS NOT NULL) AS judged
            FROM tank.ledger
            WHERE task_type=$1 AND ts > now() - interval '30 days'
            """,
            task_type,
        )
        return graduate.Evidence(
            samples=len(agreements),
            agreement=(sum(agreements) / len(agreements)) if agreements else None,
            fields=graduate.average_fields([dict(row) for row in rows]),
            rejected=int(feedback["rejected"] or 0),
            judged=int(feedback["judged"] or 0),
        )
    promoted_at = policy.get("promoted_at")
    if promoted_at is None:
        return graduate.Evidence()
    feedback = await conn.fetchrow(
        """
        SELECT count(*) FILTER (WHERE feedback='rejected') AS rejected,
               count(*) FILTER (WHERE feedback IS NOT NULL) AS judged
        FROM tank.ledger
        WHERE task_type=$1 AND ts >= $2
        """,
        task_type, promoted_at,
    )
    live = await conn.fetchval(
        """
        SELECT avg(agreement) FROM tank.shadow
        WHERE task_type=$1 AND created_at >= $2 AND primary_model=$3 AND agreement IS NOT NULL
        """,
        task_type, promoted_at, policy["model"],
    )
    return graduate.Evidence(
        rejected=int(feedback["rejected"] or 0),
        judged=int(feedback["judged"] or 0),
        live_agreement=float(live) if live is not None else None,
    )


async def _apply_move(conn: Any, move: graduate.Move, before: dict[str, Any], by: str) -> None:
    task_type = before["task_type"]
    if move.action == "promote":
        updated = await conn.execute(
            """
            UPDATE tank.policy
            SET previous_model=model, model=$2, candidate_model=NULL, shadow_rate=0,
                rung=$3, semantic_cache=$4, promoted_at=now(), updated_at=now()
            WHERE task_type=$1 AND tenant_id IS NULL AND candidate_model IS NOT NULL
            """,
            task_type, move.policy["model"], int(move.policy["rung"]), bool(move.policy.get("semantic_cache")),
        )
        if str(updated).endswith(" 0"):
            return
        await conn.execute(
            """
            INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user, detail)
            VALUES ($1,'promote',$2,$3,$4,$5::jsonb)
            """,
            task_type, before["model"], move.policy["model"], by,
            json.dumps({"automatic": by == "tank"}),
        )
        return
    if move.action != "rollback":
        return
    updated = await conn.execute(
        """
        UPDATE tank.policy
        SET model=previous_model, previous_model=NULL, promoted_at=NULL, semantic_cache=$2,
            rung=$3, shadow_rate=0, updated_at=now()
        WHERE task_type=$1 AND tenant_id IS NULL AND previous_model IS NOT NULL AND promoted_at IS NOT NULL
        """,
        task_type, bool(move.policy.get("semantic_cache")), int(move.policy["rung"]),
    )
    if str(updated).endswith(" 0"):
        return
    await conn.execute(
        """
        INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user, detail)
        VALUES ($1,'rollback',$2,$3,$4,$5::jsonb)
        """,
        task_type, before["model"], move.policy["model"], by,
        json.dumps({"automatic": True, "reason": move.reason}),
    )


async def _move_task(task_type: str, *, by: str = "tank", automatic: bool = True) -> graduate.Move | None:
    """Promote a proven candidate, or roll back a promotion that slipped in its first 7 days."""
    async with pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(_POLICY_MOVE + " FOR UPDATE", task_type)
            if row is None:
                return None
            policy = dict(row)
            evidence = await _load_evidence(conn, policy)
            now = datetime.now(timezone.utc)
            if automatic:
                move = graduate.apply(policy, evidence, now)
            else:
                move = graduate.promote_if_proven(policy, evidence, now, automatic=False)
            if move.action != "hold":
                await _apply_move(conn, move, policy, by)
            return move


async def _move_all() -> None:
    async with pool().acquire() as conn:
        names = await conn.fetch(
            "SELECT task_type FROM tank.policy WHERE tenant_id IS NULL AND task_type <> 'tank.judge'"
        )
    for row in names:
        try:
            await _move_task(row["task_type"])
        except Exception as exc:  # noqa: BLE001 — one task must not blank the ladder
            log.warning("graduation watch %s skipped: %s", row["task_type"], exc)


def _note(row: Any) -> str | None:
    detail = row["detail"] or {}
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except json.JSONDecodeError:
            detail = {}
    if not isinstance(detail, dict):
        detail = {}
    if row["action"] == "rollback":
        why = detail.get("reason") or "quality dropped"
        return f"Rolled back to {row['to_model']}: {why}."
    if detail.get("automatic"):
        return f"Promoted to {row['to_model']} on the samples."
    return None


async def _code_quotes(conn: Any) -> list[graduate.Quote]:
    rows = await conn.fetch(
        """
        SELECT id, version FROM tank.skills
        WHERE state='approved' AND present AND task_type IS NULL
        """
    )
    quotes: list[graduate.Quote] = []
    for row in rows:
        ref = f"skill:{row['id']}@{row['version']}"
        try:
            pkg = get_package(row["id"], row["version"])
        except HTTPException:
            continue
        if graduate.code_candidate_problem(ref, state="approved", task_type=pkg.task_type, on_disk=True):
            continue
        quotes.append(graduate.Quote(ref, 0.0, funds=True, kind="code"))
    return quotes


async def _screen_cases(conn: Any, task_type: str) -> list[tuple[Any, list[dict[str, str]], dict[str, Any]]]:
    evals = await conn.fetch(
        "SELECT input, expected FROM tank.evals WHERE task_type=$1 ORDER BY created_at DESC LIMIT 12",
        task_type,
    )
    transcripts = await conn.fetch(
        "SELECT messages, content FROM tank.transcripts WHERE task_type=$1 ORDER BY created_at DESC LIMIT 8",
        task_type,
    )
    cases: list[tuple[Any, list[dict[str, str]], dict[str, Any]]] = []
    for row in evals:
        payload = row["input"]
        expected = row["expected"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(expected, str):
            try:
                expected = json.loads(expected)
            except json.JSONDecodeError:
                pass
        body = payload if isinstance(payload, dict) else {"text": str(payload)}
        messages = [{"role": "user", "content": json.dumps(body) if isinstance(payload, dict) else str(payload)}]
        cases.append((expected, messages, body))
    for row in transcripts:
        messages = row["messages"]
        if isinstance(messages, str):
            messages = json.loads(messages)
        if not isinstance(messages, list):
            continue
        clean = [{"role": str(m.get("role") or "user"), "content": str(m.get("content") or "")} for m in messages if isinstance(m, dict)]
        cases.append((row["content"], clean, graduate.skill_payload(clean)))
    return cases


async def _screen_skill(pkg: skala.SkillPackage, cases: list[tuple[Any, list[dict[str, str]], dict[str, Any]]], tolerance: float) -> float | None:
    if not cases or _http is None:
        return None

    async def _forbid(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("code candidate called a model")

    ctx = skala.SkillContext(
        tenant_id=PLATFORM_TENANT, skill_ref=pkg.ref, agent=pkg.agent, task_id=None,
        _model=_forbid, http=_http, env={},
    )
    scores: list[float] = []
    for expected, _messages, payload in cases:
        try:
            out = await skala.run_skill(pkg, payload, ctx)
            scores.append(graduate.score_pair(expected, out, tolerance=tolerance))
        except Exception:  # noqa: BLE001 — a broken case drops that sample, not the search
            scores.append(0.0)
    if ctx.calls:
        return 0.0
    return sum(scores) / len(scores) if scores else None


async def _screen_model(name: str, task_type: str, cases: list[tuple[Any, list[dict[str, str]], dict[str, Any]]], tolerance: float, max_tokens: int) -> float | None:
    scores: list[float] = []
    for expected, messages, _payload in cases:
        if not await _shadow_budget_open(task_type):
            break
        content, cost = await _llm(name, messages, max_tokens)
        async with pool().acquire() as conn:
            await _add_spend(conn, task_type, cost)
        scores.append(graduate.score_pair(expected, content, tolerance=tolerance))
    return sum(scores) / len(scores) if scores else None


async def _check_code_candidate(conn: Any, candidate: str) -> str | None:
    parsed = graduate.parse_skill(candidate)
    if parsed is None:
        return graduate.code_candidate_problem(candidate, state=None, task_type=None, on_disk=False)
    skill_id, version = parsed
    try:
        pkg = get_package(skill_id, version)
        on_disk = True
        task_type = pkg.task_type
    except HTTPException:
        on_disk = False
        task_type = None
    state = await conn.fetchval("SELECT state FROM tank.skills WHERE id=$1 AND version=$2", skill_id, version)
    return graduate.code_candidate_problem(candidate, state=state, task_type=task_type, on_disk=on_disk)


@app.get("/v1/graduation", dependencies=[Depends(require_key)])
async def graduation() -> list[dict[str, Any]]:
    """Every platform policy with its ladder: paid model, cheaper model, code."""
    await _move_all()
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.task_type, p.rung, p.model, p.candidate_model, p.shadow_rate, p.previous_model, p.eval_threshold,
                   p.cache_scope, p.priority, p.min_shadow_samples, p.max_reject_rate, p.auto_promote,
                   p.semantic_cache, p.promoted_at,
                   (SELECT count(*) FROM tank.shadow s WHERE s.task_type=p.task_type AND s.candidate_model=p.candidate_model AND s.agreement IS NOT NULL) AS n,
                   (SELECT avg(agreement) FROM tank.shadow s WHERE s.task_type=p.task_type AND s.candidate_model=p.candidate_model) AS agreement,
                   (SELECT avg(candidate_cost_usd) FROM tank.shadow s WHERE s.task_type=p.task_type AND s.candidate_model=p.candidate_model) AS cand_cost,
                   (SELECT avg(primary_cost_usd) FROM tank.shadow s WHERE s.task_type=p.task_type AND s.candidate_model=p.candidate_model) AS prim_cost,
                   (SELECT count(*) FROM tank.ledger l WHERE l.task_type=p.task_type AND l.ts > now() - interval '30 days') AS calls_30d,
                   (SELECT coalesce(sum(cost_usd),0) FROM tank.ledger l WHERE l.task_type=p.task_type AND l.ts > now() - interval '30 days') AS cost_30d,
                   (SELECT count(*) FROM tank.ledger l WHERE l.task_type=p.task_type AND l.cache_hit) AS cache_hits
            FROM tank.policy p WHERE p.tenant_id IS NULL AND p.task_type <> 'tank.judge'
            ORDER BY cost_30d DESC, p.task_type
            """
        )
        ranks = await conn.fetch("SELECT * FROM tank.graduation_rank")
        notes = await conn.fetch(
            """
            SELECT DISTINCT ON (task_type) task_type, action, from_model, to_model, detail, created_at
            FROM tank.policy_log
            WHERE action IN ('promote', 'rollback') AND created_at > now() - interval '14 days'
            ORDER BY task_type, created_at DESC
            """
        )
        states = await conn.fetch("SELECT * FROM tank.search_state")
        code_quotes = await _code_quotes(conn)
    price_quotes = _price_quotes()
    roster_fp, price_fp = graduate.fingerprints([*price_quotes, *code_quotes])
    by_rank: dict[str, list[Any]] = {}
    for rank in ranks:
        by_rank.setdefault(rank["task_type"], []).append(rank)
    by_note = {row["task_type"]: _note(row) for row in notes}
    by_state = {row["task_type"]: row for row in states}
    now = datetime.now(timezone.utc)
    out = []
    for r in rows:
        d = dict(r)
        n = int(d["n"] or 0)
        agr = _num(d["agreement"])
        thr = float(d["eval_threshold"] or 0.95)
        minimum = int(d["min_shadow_samples"] or 30)
        d["n"] = n
        d["agreement"] = agr
        d["eligible"] = bool(d["candidate_model"]) and n >= minimum and agr is not None and agr >= thr
        prim = _num(d["prim_cost"])
        cand = _num(d["cand_cost"])
        d["prim_cost"] = prim
        d["cand_cost"] = cand
        d["saving_pct"] = (round((1 - cand / prim) * 100) if prim and prim > 0 and cand is not None else None)
        calls = int(d["calls_30d"] or 0)
        task_ranks = by_rank.get(d["task_type"], [])
        ranked_view = [{
            "name": rank["candidate"],
            "kind": rank["kind"],
            "status": rank["status"],
            "shadow_n": int(rank["shadow_n"] or 0),
            "shadow_agreement": _num(rank["shadow_agreement"]),
            "cost_per_call": _num(rank["cost_per_call"]) if rank["cost_per_call"] is not None else _num(rank["price_usd"]),
        } for rank in task_ranks]
        steps = graduate.ladder_from_policy(
            model=d["model"],
            previous_model=d["previous_model"],
            candidate_model=d["candidate_model"],
            calls_30d=calls,
            prim_cost=prim,
            cand_cost=0.0 if graduate.is_skill(d["candidate_model"]) else cand,
            shadow_n=n,
            shadow_agreement=agr,
            ranked=ranked_view,
        )
        state = by_state.get(d["task_type"])
        due = graduate.research_reason(
            state["searched_at"] if state else None,
            now,
            roster_fp,
            price_fp,
            state["roster_fingerprint"] if state else None,
            state["price_fingerprint"] if state else None,
        )
        d["ladder"] = {
            "steps": steps,
            "proposed": (state["proposed"] if state else None),
            "note": by_note.get(d["task_type"]),
            "research_due": due,
            "auto_promote": bool(d["auto_promote"]) if d["auto_promote"] is not None else True,
        }
        out.append(d)
    return out


@app.put("/v1/graduation/{task_type}/candidate", dependencies=[Depends(require_key)])
async def set_candidate(task_type: str, body: CandidateBody) -> dict[str, Any]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow("SELECT model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL", task_type)
        if row is None:
            raise HTTPException(status_code=404, detail="no such platform policy")
        if body.candidate_model and body.candidate_model == row["model"]:
            raise HTTPException(status_code=400, detail="candidate must differ from the current model")
        if graduate.is_skill(body.candidate_model):
            problem = await _check_code_candidate(conn, str(body.candidate_model))
            if problem:
                raise HTTPException(status_code=400, detail=problem)
        await conn.execute(
            "UPDATE tank.policy SET candidate_model=$2, shadow_rate=$3, updated_at=now() WHERE task_type=$1 AND tenant_id IS NULL",
            task_type, body.candidate_model, body.shadow_rate if body.candidate_model else 0,
        )
        await conn.execute(
            "INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user, detail) VALUES ($1,'candidate',$2,$3,$4,$5::jsonb)",
            task_type, row["model"], body.candidate_model, body.by, json.dumps({"shadow_rate": body.shadow_rate}),
        )
    return {"ok": True}


@app.post("/v1/graduation/{task_type}/promote", dependencies=[Depends(require_key)])
async def promote(task_type: str, body: PromoteBody) -> dict[str, Any]:
    """Promote only when the shadow bar is cleared. The previous model stays for rollback."""
    move = await _move_task(task_type, by=body.by or "founder", automatic=False)
    if move is None:
        raise HTTPException(status_code=404, detail="no such platform policy")
    if move.action != "promote":
        if move.reason == "no candidate":
            raise HTTPException(status_code=400, detail="no candidate to promote")
        raise HTTPException(status_code=409, detail=move.reason or "not proven")
    return {"ok": True, "model": move.policy["model"], "previous_model": move.policy["previous_model"]}


@app.post("/v1/graduation/{task_type}/rollback", dependencies=[Depends(require_key)])
async def rollback(task_type: str, body: PromoteBody) -> dict[str, Any]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT model, previous_model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL",
            task_type,
        )
        if row is None or not row["previous_model"]:
            raise HTTPException(status_code=400, detail="nothing to roll back to")
        rung, semantic = _rung_for(row["previous_model"])
        await conn.execute(
            """
            UPDATE tank.policy
            SET model=previous_model, previous_model=NULL, promoted_at=NULL, semantic_cache=$2,
                rung=$3, shadow_rate=0, updated_at=now()
            WHERE task_type=$1 AND tenant_id IS NULL
            """,
            task_type, semantic, rung,
        )
        await conn.execute(
            "INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user, detail) VALUES ($1,'rollback',$2,$3,$4,$5::jsonb)",
            task_type, row["model"], row["previous_model"], body.by, json.dumps({"automatic": False}),
        )
    return {"ok": True, "model": row["previous_model"]}


@app.put("/v1/graduation/{task_type}/auto", dependencies=[Depends(require_key)])
async def set_auto_promote(task_type: str, body: AutoBody) -> dict[str, Any]:
    async with pool().acquire() as conn:
        updated = await conn.execute(
            "UPDATE tank.policy SET auto_promote=$2, updated_at=now() WHERE task_type=$1 AND tenant_id IS NULL",
            task_type, body.auto_promote,
        )
        if str(updated).endswith(" 0"):
            raise HTTPException(status_code=404, detail="no such platform policy")
        await conn.execute(
            "INSERT INTO tank.policy_log (task_type, action, by_user, detail) VALUES ($1,'auto',$2,$3::jsonb)",
            task_type, body.by, json.dumps({"auto_promote": body.auto_promote}),
        )
    return {"ok": True, "auto_promote": body.auto_promote}


@app.post("/v1/graduation/{task_type}/search", dependencies=[Depends(require_key)])
async def search_task(task_type: str, body: SearchBody | None = None) -> dict[str, Any]:
    """Screen cheaper roster models and approved code skills. Shadow the cheapest survivor next."""
    body = body or SearchBody()
    async with pool().acquire() as conn:
        policy = await conn.fetchrow(_POLICY_MOVE, task_type)
        if policy is None:
            raise HTTPException(status_code=404, detail="no such platform policy")
        code_quotes = await _code_quotes(conn)
        price_quotes = _price_quotes()
        roster = [*price_quotes, *code_quotes]
        roster_fp, price_fp = graduate.fingerprints(roster)
        state = await conn.fetchrow("SELECT * FROM tank.search_state WHERE task_type=$1", task_type)
        due = graduate.research_reason(
            state["searched_at"] if state else None,
            datetime.now(timezone.utc),
            roster_fp,
            price_fp,
            state["roster_fingerprint"] if state else None,
            state["price_fingerprint"] if state else None,
        )
        if due is None and not body.force:
            return {"ok": True, "skipped": True, "proposed": state["proposed"] if state else None, "research_due": None}
        cases = await _screen_cases(conn, task_type)
        tolerance = float(policy["number_tolerance"] or 0.01)
        max_tokens = int(await conn.fetchval(
            "SELECT max_tokens_out FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL", task_type,
        ) or 512)
        shadow_rows = await conn.fetch(
            """
            SELECT candidate_model, count(*) AS n, avg(agreement) AS agreement
            FROM tank.shadow
            WHERE task_type=$1 AND agreement IS NOT NULL
            GROUP BY candidate_model
            """,
            task_type,
        )
        field_rows = await conn.fetch(
            """
            SELECT candidate_model, fields FROM tank.shadow
            WHERE task_type=$1 AND agreement IS NOT NULL
            ORDER BY created_at DESC LIMIT 400
            """,
            task_type,
        )
        spend = await conn.fetchrow(
            """
            SELECT count(*) AS calls,
                   avg(cost_usd) FILTER (WHERE cache_hit = false AND cost_usd > 0) AS cost
            FROM tank.ledger
            WHERE task_type=$1 AND ts > now() - interval '30 days' AND outcome='delivered'
            """,
            task_type,
        )
    screens: dict[str, float] = {}
    serving = str(policy["model"])
    serving_price = next((quote.price for quote in roster if quote.name == serving), None)
    cheaper = [
        quote for quote in roster
        if quote.name != serving and (quote.kind == "code" or (serving_price is None or quote.price < serving_price))
    ]
    cheaper.sort(key=lambda quote: (quote.price, quote.name))
    for quote in cheaper:
        if quote.kind == "code":
            parsed = graduate.parse_skill(quote.name)
            if parsed is None:
                continue
            try:
                pkg = get_package(parsed[0], parsed[1])
            except HTTPException:
                continue
            score = await _screen_skill(pkg, cases, tolerance)
        else:
            if not cases:
                continue
            try:
                score = await _screen_model(quote.name, task_type, cases, tolerance, max_tokens)
            except Exception as exc:  # noqa: BLE001 — one model failing the screen is a miss, not a crash
                log.warning("screen %s/%s failed: %s", task_type, quote.name, exc)
                score = 0.0
        if score is not None:
            screens[quote.name] = score
    shadows = {
        row["candidate_model"]: (int(row["n"]), _num(row["agreement"]))
        for row in shadow_rows
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in field_rows:
        grouped.setdefault(row["candidate_model"], []).append(dict(row))
    field_map = {name: graduate.average_fields(rows) for name, rows in grouped.items()}
    floors = policy["field_floors"] if isinstance(policy["field_floors"], dict) else {}
    result = graduate.search(
        serving=serving,
        roster=roster,
        screens=screens,
        shadows=shadows,
        field_scores_by_name=field_map,
        calls_30d=int(spend["calls"] or 0),
        serving_cost=_num(spend["cost"]),
        threshold=float(policy["eval_threshold"] or 0.97),
        min_samples=int(policy["min_shadow_samples"] or 30),
        floors={str(key): float(value) for key, value in floors.items()},
    )
    async with pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM tank.graduation_rank WHERE task_type=$1", task_type)
            for row in result.ranked:
                await conn.execute(
                    """
                    INSERT INTO tank.graduation_rank
                      (task_type, candidate, kind, price_usd, screen_agreement, shadow_n, shadow_agreement,
                       cost_per_call, monthly_saving_usd, status)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    task_type, row.name, row.kind, row.price, row.screen_agreement, row.shadow_n,
                    row.shadow_agreement, row.cost_per_call, row.monthly_saving_usd, row.status,
                )
            await conn.execute(
                """
                INSERT INTO tank.search_state
                  (task_type, roster_fingerprint, price_fingerprint, searched_at, reason, proposed)
                VALUES ($1,$2,$3,now(),$4,$5)
                ON CONFLICT (task_type) DO UPDATE SET
                  roster_fingerprint=EXCLUDED.roster_fingerprint,
                  price_fingerprint=EXCLUDED.price_fingerprint,
                  searched_at=now(),
                  reason=EXCLUDED.reason,
                  proposed=EXCLUDED.proposed
                """,
                task_type, roster_fp, price_fp, due or "search", result.proposed,
            )
            current = policy["candidate_model"]
            dropped = {row.name for row in result.ranked if row.status == "dropped"}
            if result.next_shadow and (current is None or current in dropped):
                await conn.execute(
                    """
                    UPDATE tank.policy SET candidate_model=$2, shadow_rate=1, updated_at=now()
                    WHERE task_type=$1 AND tenant_id IS NULL
                    """,
                    task_type, result.next_shadow,
                )
                await conn.execute(
                    """
                    INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user, detail)
                    VALUES ($1,'candidate',$2,$3,$4,$5::jsonb)
                    """,
                    task_type, serving, result.next_shadow, body.by or "tank",
                    json.dumps({"shadow_rate": 1, "search": True}),
                )
    if result.proposed:
        await _move_task(task_type)
    return {"ok": True, "skipped": False, "research_due": due, **result.as_dict()}


@app.post("/v1/route", response_model=RouteResponse)
async def route(req: RouteRequest, caller: str | None = Depends(require_key)) -> RouteResponse:
    if caller:
        req = req.model_copy(update={"agent": caller})
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


def _vkey(v: str) -> tuple[int, ...]:
    return tuple(int(x) if x.isdigit() else 0 for x in v.split("."))


async def staging_version(skill_id: str) -> str | None:
    async with pool().acquire() as conn:
        rows = await conn.fetch("SELECT version FROM tank.skills WHERE id=$1 AND state='staging' AND present", skill_id)
    vs = [r["version"] for r in rows]
    return max(vs, key=_vkey) if vs else None


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


def known_engines() -> list[str]:
    return sorted({i.split(".")[0] for (i, _v) in _packages if i.endswith(".ingest")})


async def _pick_version(skill_id: str, preview: bool) -> str:
    """Approved version, or — for owner testing — a newer staging version, else the newest package."""
    ver = await approved_version(skill_id)
    if preview:
        staged = await staging_version(skill_id)
        if staged and (ver is None or _vkey(staged) > _vkey(ver)):
            ver = staged
    if ver is None:
        if not preview:
            raise HTTPException(status_code=409, detail=f"{skill_id} has no approved version")
        cands = sorted((v for (i, v) in _packages if i == skill_id), key=_vkey, reverse=True)
        if not cands:
            raise HTTPException(status_code=404, detail=f"no package for {skill_id}")
        ver = cands[0]
    return ver


class SkillRun(BaseModel):
    tenant_id: uuid.UUID
    input: dict[str, Any]
    version: str | None = None      # default: the approved version
    preview: bool = False           # owner testing: allows candidate/staging; labelled in the ledger


@app.get("/v1/skills/{skill_id}/run", dependencies=[Depends(require_key)])
async def describe_skill(skill_id: str, preview: bool = False) -> dict[str, Any]:
    """Which version Base should pin, and which engines exist. Does not run the skill."""
    version = await _pick_version(skill_id, preview)
    pkg = get_package(skill_id, version)
    return {"skill": skill_id, "version": version, "ref": pkg.ref, "engines": known_engines()}


@app.post("/v1/skills/{skill_id}/run")
async def run_one_skill(
    skill_id: str,
    body: SkillRun,
    caller: str | None = Depends(require_key),
) -> dict[str, Any]:
    version = body.version or await _pick_version(skill_id, body.preview)
    pkg = get_package(skill_id, version)
    if caller:
        shared: list[str] = []
        try:
            import yaml
            meta = yaml.safe_load((pkg.path / "skill.yaml").read_text(encoding="utf-8")) or {}
            raw = meta.get("shared_with") or []
            if isinstance(raw, str):
                raw = [raw]
            if isinstance(raw, list):
                shared = [str(item) for item in raw]
        except Exception:  # noqa: BLE001 — a skill we cannot read is not shared
            shared = []
        if caller != pkg.agent and caller not in shared:
            raise HTTPException(status_code=403, detail="That skill belongs to another agent.")
    state = await skill_state(skill_id, version)
    if state != "approved" and not body.preview:
        raise HTTPException(status_code=409, detail=f"{pkg.ref} is {state!r}; only approved versions run for clients")
    ctx = make_ctx(pkg, body.tenant_id, preview=body.preview)
    if caller:
        ctx.agent = caller
    out = await skala.run_skill(pkg, body.input, ctx)
    out["_cost_usd"] = round(ctx.cost_usd, 6)
    return out


# ---------- Base: the room owns the worker; Tank only proxies ----------

BASE_AGENT_URL = os.environ.get("BASE_AGENT_URL", "http://agent-base:8000")
_BASE_ROUTES = {"run", "retry", "rerun", "batches", "engines", "records"}


@app.api_route("/v1/base/{path:path}", methods=["GET", "POST"], dependencies=[Depends(require_key)])
async def base_proxy(path: str, request: Request) -> Response:
    """Forward /v1/base/* to the Base room. The Workspace key is checked here and not sent on."""
    if path not in _BASE_ROUTES:
        raise HTTPException(status_code=404, detail="no such base route")
    if _http is None:
        raise HTTPException(status_code=503, detail="Base room is unreachable")
    body = await request.body()
    headers = {}
    content_type = request.headers.get("content-type")
    if content_type:
        headers["content-type"] = content_type
    try:
        resp = await _http.request(
            request.method,
            BASE_AGENT_URL.rstrip("/") + "/v1/base/" + path,
            content=body if body else None,
            params=list(request.query_params.multi_items()),
            headers=headers,
            timeout=600,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Base room is unreachable") from None
    return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))


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
    # A verdict on a real answer is a golden case: accepted → "this is right", rejected → "never this".
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tank.evals (task_type, input, expected, tolerance, source, tenant_id, ledger_id, verdict, note)
            SELECT t.task_type, t.messages, jsonb_build_object('text', t.content), 'semantic', 'tester_feedback',
                   t.tenant_id, t.ledger_id, $2, $3
            FROM tank.transcripts t WHERE t.ledger_id = $1
            ON CONFLICT (ledger_id) WHERE ledger_id IS NOT NULL
            DO UPDATE SET verdict = EXCLUDED.verdict, note = EXCLUDED.note
            """,
            ledger_id, body.feedback, body.note,
        )
    return {"ok": True, "ledger_id": str(ledger_id), "feedback": body.feedback}


@app.get("/v1/evals/summary", dependencies=[Depends(require_key)])
async def evals_summary() -> list[dict[str, Any]]:
    """Golden cases per task type, split by where they came from and the verdict."""
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT task_type, count(*) AS cases,
                   count(*) FILTER (WHERE source='tester_feedback' AND verdict='accepted') AS accepted,
                   count(*) FILTER (WHERE source='tester_feedback' AND verdict='rejected') AS rejected,
                   count(*) FILTER (WHERE source='manual') AS manual
            FROM tank.evals GROUP BY task_type ORDER BY task_type
            """
        )
    return [dict(r) for r in rows]


# ---------- the client's ledger view ----------

@app.get("/v1/ledger/failures", dependencies=[Depends(require_key)])
async def ledger_failures(tenant_id: uuid.UUID, days: int = 30) -> list[dict[str, Any]]:
    """Failed calls grouped by day, task and reason (reason is recorded from 13 Oct 2026; older rows show none)."""
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT date_trunc('day', ts)::date AS day, task_type, coalesce(skill,'') AS skill,
                   coalesce(split_part(error, ':', 1), 'not recorded') AS reason,
                   count(*) AS calls, round(avg(latency_ms)) AS avg_ms, min(error) AS example
            FROM tank.ledger
            WHERE tenant_id=$1 AND outcome='failed' AND ts > now() - make_interval(days => $2)
            GROUP BY 1,2,3,4 ORDER BY 1 DESC, calls DESC
            """, tenant_id, days,
        )
    return [dict(r) for r in rows]


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

app.include_router(__import__("admin").router)
