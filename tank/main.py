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
import contextvars
import hashlib
import json
import random
import re
import logging
import os
import time
import uuid
from typing import Any, Literal

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

import skala

log = logging.getLogger("tank")

DATABASE_URL = os.environ["DATABASE_URL"]
LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000")
LITELLM_MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]
TANK_API_KEY = os.environ["TANK_API_KEY"]
DEFAULT_REGION = os.environ.get("TANK_REGION", "us-east")
US_REGION = "us-east"
ZA_REGION = "za"
ZA_HOME_MESSAGE = "needs the South Africa region"
US_HOME_MESSAGE = "needs the United States region"
IDENTIFIER_REFUSAL = "A personal identifier cannot be sent to a provider outside South Africa."
ALLOW_REFUSAL = "This provider is not on the tenant's allow-list."
_CHINA_PROVIDERS = frozenset({"deepseek", "moonshot", "kimi"})
_pii_detect = None
_skill_home: contextvars.ContextVar[str | None] = contextvars.ContextVar("zenas_skill_home", default=None)

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


def normalize_home(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw == "us":
        return US_REGION
    return raw


def normalize_box(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in ("", "us", US_REGION):
        return US_REGION
    return raw


def box_region() -> str:
    """This process's region, read on each call so tests can switch it."""
    return normalize_box(os.environ.get("TANK_REGION", DEFAULT_REGION))


HOME_REQUIRED = "home region must be us-east or za"


def call_home(home: str | None, box: str | None = None) -> str | None:
    """Home used by /v1/route, /v1/tasks, /v1/skills/*/run and background tasks.

    A missing value is this server's TANK_REGION, so the live Workspace and
    agent rooms keep working. An empty string is not missing: it is returned
    unchanged and then refused. /v1/zenas/* does not call this.
    """
    if home is None:
        return normalize_box(box) if box is not None else box_region()
    return home


def home_region_refusal(home: str | None, box: str | None = None) -> str | None:
    """Refuse an empty, unknown, or other-region home before any write or call.

    None is refused here too. Callers that may omit the field pass call_home()
    first. The Zenas proxy calls this directly, so a missing home stays refused.

    TODO(Thread C): the authoritative home region will live on the tenant
    record. That column is yours; do not add it here. The value on this
    request is only a cross-check against that column. Read it once the
    column exists, and keep refusing when the two disagree or either is missing.
    """
    home_region = normalize_home(home)
    if home_region not in (US_REGION, ZA_REGION):
        return HOME_REQUIRED
    here = normalize_box(box) if box is not None else box_region()
    if home_region == here:
        return None
    if home_region == ZA_REGION:
        return ZA_HOME_MESSAGE
    return US_HOME_MESSAGE


def pii_module() -> Any:
    """zenas.pii detect, loaded once. Pure code: no model and no network."""
    global _pii_detect
    if _pii_detect is None:
        import importlib.util

        path = os.path.join(os.path.dirname(__file__), "skills", "zenas.pii", "1.0.0", "detect.py")
        spec = importlib.util.spec_from_file_location("zenas_pii_detect_tank", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("zenas.pii detect is missing")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _pii_detect = module
    return _pii_detect


def prompt_has_identifier(text: str) -> bool:
    found = pii_module().detect(text or "")
    return bool(found.get("matches"))


def sa_hosted_models() -> frozenset[str]:
    """Model names that run in South Africa.

    The commented za-local slot in litellm/config.za.yaml is not active.
    ZA_HOSTED_MODELS names the ones that are. hosted_in: za in that file counts too.
    """
    names = {part.strip() for part in os.environ.get("ZA_HOSTED_MODELS", "").split(",") if part.strip()}
    path = os.path.join(os.path.dirname(__file__), "..", "litellm", "config.za.yaml")
    if os.path.isfile(path):
        import yaml

        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        for item in data.get("model_list") or []:
            info = item.get("model_info") or {}
            if str(info.get("hosted_in") or "").lower() != ZA_REGION:
                continue
            provider = str((item.get("litellm_params") or {}).get("model") or "").split("/", 1)[0].lower()
            if provider in _CHINA_PROVIDERS:
                continue
            name = str(item.get("model_name") or "").strip()
            if name:
                names.add(name)
    return frozenset(names)


def tenant_allowlist(tenant_id: str) -> frozenset[str] | None:
    """Models this tenant may call, or None when the tenant has no narrower list.

    TANK_PROVIDER_ALLOW is a JSON object of tenant id to model names. It holds
    names only. A table tank.tenant_providers can replace it later; until that
    table exists this environment value is the list.
    """
    raw = os.environ.get("TANK_PROVIDER_ALLOW", "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or tenant_id not in data:
        return None
    names = data.get(tenant_id)
    if not isinstance(names, list):
        return frozenset()
    return frozenset(str(item).strip() for item in names if str(item).strip())


def _china_model(model: str) -> bool:
    head = model.split("/", 1)[0].lower()
    return head in _CHINA_PROVIDERS or model.lower() in _CHINA_PROVIDERS


def model_call_refusal(text: str, model: str | None, *, box: str, tenant_id: str) -> str | None:
    """Whether this model call must be refused before anything is stored or sent.

    In za, a prompt that still contains an identifier is refused unless the
    model runs in South Africa and the tenant's allow-list includes it.
    model=None asks the early question: is there any permitted SA model at all?
    Pure-code skills do not call this.
    """
    here = normalize_box(box)
    allow = tenant_allowlist(tenant_id)
    if here != ZA_REGION:
        if model is not None and allow is not None and model not in allow:
            return ALLOW_REFUSAL
        return None
    if model is not None and _china_model(model):
        return ALLOW_REFUSAL
    hosted = sa_hosted_models()
    if prompt_has_identifier(text):
        permitted = hosted if allow is None else hosted & allow
        if model is None:
            return None if permitted else IDENTIFIER_REFUSAL
        if model not in permitted:
            return IDENTIFIER_REFUSAL
        return None
    if model is not None and allow is not None and model not in allow:
        return ALLOW_REFUSAL
    return None


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
    home_region: str | None = None
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
    home_region: str | None = None
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
    box = box_region()
    foreign = home_region_refusal(call_home(req.home_region, box), box)
    if foreign:
        # Empty, unknown, or the other region's text is not written.
        raise HTTPException(status_code=403, detail=foreign)
    client_text = "\n".join(m.content for m in req.messages)
    early = model_call_refusal(client_text, None, box=box, tenant_id=str(req.tenant_id))
    if early:
        raise HTTPException(status_code=403, detail=early)

    policy = await load_policy(req.task_type, req.tenant_id)
    model = policy["model"]
    priority = req.priority or policy["priority"]

    messages = [m.model_dump() for m in req.messages]
    if policy["system_prompt"]:
        messages = [{"role": "system", "content": policy["system_prompt"]}, *messages]
    max_tokens = min(req.max_tokens or policy["max_tokens_out"], policy["max_tokens_out"])
    sent = "\n".join(str(item.get("content") or "") for item in messages)
    holds_identifier = prompt_has_identifier(sent)
    blocked = model_call_refusal(sent, model, box=box, tenant_id=str(req.tenant_id))
    if blocked:
        raise HTTPException(status_code=403, detail=blocked)

    # ---- rung 4: the cache. Same task type, model and messages → the answer we already paid for.
    # Scope comes from policy: 'tenant' keys include the tenant (answers never cross tenants);
    # 'platform' is shared (only for task types whose answers hold nothing tenant-specific).
    cache_key = None
    if not holds_identifier and _redis is not None and policy.get("cache_scope") in ("tenant", "platform"):
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
        if holds_identifier:
            error = "provider error omitted; the prompt contained a personal identifier"
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
        upstream: Any = "provider error" if holds_identifier else (data or r.text[:500])
        raise HTTPException(status_code=502, detail={"ledger_id": str(ledger_id), "upstream": upstream})

    if cache_key and content:
        try:
            await _redis.set(cache_key, json.dumps({"content": content, "ledger_id": str(ledger_id)}), ex=CACHE_TTL_S)
        except Exception:  # noqa: BLE001
            pass

    # Graduation: shadow the candidate on a share of calls; it never affects this answer.
    # An identifier prompt is not copied to a second provider or into the transcript.
    if not holds_identifier and policy.get("candidate_model") and float(policy.get("shadow_rate") or 0) > random.random():
        t = asyncio.create_task(_shadow(req, policy, messages, max_tokens, ledger_id, content, cost_usd))
        _background.add(t)
        t.add_done_callback(_background.discard)

    # The learning corpus: what was asked, what came back (system prompt stays in policy).
    # Personal identifiers are never written here, even when an SA-hosted model saw them.
    if not holds_identifier:
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


def _json_obj(s: str) -> dict[str, Any] | None:
    a, b = s.find("{"), s.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        v = json.loads(s[a:b + 1])
        return v if isinstance(v, dict) else None
    except json.JSONDecodeError:
        return None


def _norm(v: Any) -> str:
    return " ".join(str(v).lower().split())


async def _shadow(req: RouteRequest, policy: dict[str, Any], messages: list[dict[str, str]], max_tokens: int,
                  ledger_id: uuid.UUID, primary: str, primary_cost: float) -> None:
    """Run the candidate on the same input, score agreement with the primary, record both.
    Spend lands on the platform tenant, never the client's."""
    cand = policy["candidate_model"]
    cand_content, cand_cost, agreement, method = None, 0.0, None, "failed"
    try:
        cand_content, cand_cost = await _llm(cand, messages, max_tokens)
        pj, cj = _json_obj(primary), _json_obj(cand_content)
        if pj is not None and cj is not None and pj:
            keys = set(pj) | set(cj)
            same = sum(1 for k in keys if _norm(pj.get(k)) == _norm(cj.get(k)))
            agreement, method = same / len(keys), "json"
        else:
            jp = await load_policy("tank.judge", PLATFORM_TENANT)
            jmsgs = [{"role": "system", "content": jp["system_prompt"]},
                     {"role": "user", "content": f"REQUEST:\n{messages[-1]['content'][:3000]}\n\nFIRST ANSWER:\n{primary[:4000]}\n\nSECOND ANSWER:\n{cand_content[:4000]}"}]
            verdict, jcost = await _llm(jp["model"], jmsgs, jp["max_tokens_out"])
            cand_cost += jcost
            m = re.search(r"\d{1,3}", verdict)
            agreement, method = (min(100, int(m.group())) / 100 if m else None), "judge"
    except Exception as exc:  # noqa: BLE001
        log.warning("shadow %s→%s failed: %s", policy["model"], cand, exc)
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tank.shadow (ledger_id, tenant_id, task_type, primary_model, candidate_model, primary_content,
                                     candidate_content, candidate_cost_usd, primary_cost_usd, agreement, method)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            """,
            ledger_id, req.tenant_id, req.task_type, policy["model"], cand, primary[:20000],
            (cand_content or "")[:20000], cand_cost, primary_cost, agreement, method,
        )
        # The candidate's spend is platform R&D: logged, visible, not on the client's bill.
        await conn.execute(
            """
            INSERT INTO tank.ledger (tenant_id, region, agent, task_type, rung, model, priority, tokens_in, tokens_out,
                                     cost_usd, latency_ms, cache_hit, outcome)
            VALUES ($1,$2,'tank',$3,1,$4,'batch',0,0,$5,0,false,$6)
            """,
            PLATFORM_TENANT, DEFAULT_REGION, f"{req.task_type}#shadow", cand, cand_cost,
            "delivered" if cand_content is not None else "failed",
        )


# ---------- graduation: the ladder ----------

class CandidateBody(BaseModel):
    candidate_model: str | None = None
    shadow_rate: float = Field(default=1.0, ge=0, le=1)
    by: str | None = None


class PromoteBody(BaseModel):
    by: str | None = None


@app.get("/v1/graduation", dependencies=[Depends(require_key)])
async def graduation() -> list[dict[str, Any]]:
    """Every platform policy with its candidate and what the shadow runs say so far."""
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.task_type, p.rung, p.model, p.candidate_model, p.shadow_rate, p.previous_model, p.eval_threshold,
                   p.cache_scope, p.priority,
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
    out = []
    for r in rows:
        d = dict(r)
        n = int(d["n"] or 0)
        agr = float(d["agreement"]) if d["agreement"] is not None else None
        thr = float(d["eval_threshold"] or 0.95)
        d["eligible"] = bool(d["candidate_model"]) and n >= 30 and agr is not None and agr >= thr
        d["saving_pct"] = (round((1 - float(d["cand_cost"]) / float(d["prim_cost"])) * 100) if d["prim_cost"] and float(d["prim_cost"]) > 0 and d["cand_cost"] is not None else None)
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
    """The human step: make the candidate the model. Previous model is kept for rollback."""
    async with pool().acquire() as conn:
        row = await conn.fetchrow("SELECT model, candidate_model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL", task_type)
        if row is None or not row["candidate_model"]:
            raise HTTPException(status_code=400, detail="no candidate to promote")
        await conn.execute(
            """
            UPDATE tank.policy SET previous_model=model, model=candidate_model, candidate_model=NULL, shadow_rate=0, updated_at=now()
            WHERE task_type=$1 AND tenant_id IS NULL
            """, task_type,
        )
        await conn.execute(
            "INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user) VALUES ($1,'promote',$2,$3,$4)",
            task_type, row["model"], row["candidate_model"], body.by,
        )
    return {"ok": True, "model": row["candidate_model"], "previous_model": row["model"]}


@app.post("/v1/graduation/{task_type}/rollback", dependencies=[Depends(require_key)])
async def rollback(task_type: str, body: PromoteBody) -> dict[str, Any]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow("SELECT model, previous_model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL", task_type)
        if row is None or not row["previous_model"]:
            raise HTTPException(status_code=400, detail="nothing to roll back to")
        await conn.execute(
            "UPDATE tank.policy SET model=previous_model, previous_model=NULL, updated_at=now() WHERE task_type=$1 AND tenant_id IS NULL",
            task_type,
        )
        await conn.execute(
            "INSERT INTO tank.policy_log (task_type, action, from_model, to_model, by_user) VALUES ($1,'rollback',$2,$3,$4)",
            task_type, row["model"], row["previous_model"], body.by,
        )
    return {"ok": True, "model": row["previous_model"]}


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
    box = box_region()
    home = call_home(body.home_region, box)
    foreign = home_region_refusal(home, box)
    if foreign:
        raise HTTPException(status_code=403, detail=foreign)
    text = "\n".join(m.content for m in body.messages)
    early = model_call_refusal(text, None, box=box, tenant_id=str(body.tenant_id))
    if early:
        raise HTTPException(status_code=403, detail=early)
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
    req = RouteRequest(
        tenant_id=body.tenant_id, agent=body.agent, task_type=body.task_type,
        home_region=home, messages=body.messages,
    )
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
        home_region=kw.get("home_region"),
        messages=[Message(**m) for m in kw["messages"]], max_tokens=kw.get("max_tokens"),
    )
    res = await run_route(req, task_id=kw.get("task_id"))
    return res.model_dump()


def make_ctx(pkg: skala.SkillPackage, tenant_id: uuid.UUID, task_id: uuid.UUID | None = None, preview: bool = False, home_region: str | None = None) -> skala.SkillContext:
    assert _http is not None
    ref = pkg.ref + ("#preview" if preview else "")
    chosen = _skill_home.get() if home_region is None else home_region
    if chosen is None:
        # Evals and previews run as this server. A skill run sets the context
        # var to call_home() before it builds a context.
        chosen = box_region()

    async def _model(**kw: Any) -> dict[str, Any]:
        kw["home_region"] = chosen
        return await _model_for_skill(**kw)

    return skala.SkillContext(tenant_id=tenant_id, skill_ref=ref, agent=pkg.agent, task_id=task_id,
                              _model=_model, http=_http, env=dict(SKILL_ENV))


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
    here = box_region()
    result = await skala.run_evals(
        pkg, lambda: make_ctx(pkg, PLATFORM_TENANT, preview=True, home_region=here),
    )
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
    home_region: str | None = None


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
    box = box_region()
    home = call_home(body.home_region, box)
    foreign = home_region_refusal(home, box)
    if foreign:
        raise HTTPException(status_code=403, detail=foreign)
    token = _skill_home.set(home)
    try:
        return await _run_one_skill(skill_id, body, caller)
    finally:
        _skill_home.reset(token)


async def _run_one_skill(
    skill_id: str,
    body: SkillRun,
    caller: str | None,
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


# ---------- Tiger: the room owns the watches; Tank only proxies ----------
# The Workspace is not on Tiger's corridor. These routes forward to the Tiger
# agent and stamp the caller's tenant_id on the way. Rows for any other tenant
# are dropped before the response leaves Tank.

TIGER_AGENT_URL = "http://agent-tiger:8000"
_TIGER_LIST_KEYS = ("watches", "observations", "alerts")


def _tiger_tenant(request: Request, body: dict[str, Any] | None = None) -> uuid.UUID:
    """The tenant this call is for. Query and body must name the same one."""
    named = [value.strip() for key, value in request.query_params.multi_items() if key == "tenant_id" and value.strip()]
    if body is not None and body.get("tenant_id") not in (None, ""):
        named.append(str(body["tenant_id"]).strip())
    if not named:
        raise HTTPException(status_code=400, detail="tenant_id is required")
    parsed: list[uuid.UUID] = []
    for item in named:
        try:
            parsed.append(uuid.UUID(item))
        except ValueError:
            raise HTTPException(status_code=400, detail="tenant_id is not a valid id") from None
    if any(item != parsed[0] for item in parsed):
        raise HTTPException(status_code=403, detail="tenant mismatch")
    return parsed[0]


def _same_tenant(value: Any, tenant_id: uuid.UUID) -> bool:
    try:
        return uuid.UUID(str(value)) == tenant_id
    except (ValueError, TypeError, AttributeError):
        return False


def _tiger_keep(payload: Any, tenant_id: uuid.UUID) -> Any | None:
    """Keep rows for this tenant only. A row with no tenant_id is dropped."""

    def own(row: Any) -> bool:
        return isinstance(row, dict) and "tenant_id" in row and _same_tenant(row.get("tenant_id"), tenant_id)

    if isinstance(payload, list):
        return [row for row in payload if own(row)]
    if not isinstance(payload, dict):
        return payload
    if any(isinstance(payload.get(key), list) for key in _TIGER_LIST_KEYS):
        scoped = dict(payload)
        for key in _TIGER_LIST_KEYS:
            rows = payload.get(key)
            if isinstance(rows, list):
                scoped[key] = [row for row in rows if own(row)]
        if "tenant_id" in scoped and not _same_tenant(scoped.get("tenant_id"), tenant_id):
            scoped.pop("tenant_id")
        return scoped
    if "tenant_id" in payload and not _same_tenant(payload.get("tenant_id"), tenant_id):
        return None
    return payload


def _tiger_response(resp: Any, tenant_id: uuid.UUID) -> Response:
    raw = resp.content or b""
    if resp.status_code == 204 or not raw:
        return Response(status_code=resp.status_code)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return Response(content=raw, status_code=resp.status_code, media_type=resp.headers.get("content-type"))
    scoped = _tiger_keep(payload, tenant_id)
    if scoped is None:
        return Response(
            content=json.dumps({"detail": "no such watch"}).encode(),
            status_code=404,
            media_type="application/json",
        )
    return Response(content=json.dumps(scoped).encode(), status_code=resp.status_code, media_type="application/json")


async def _tiger_body(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not raw:
        return {}
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="body must be json") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be an object")
    return body


async def _tiger_call(method: str, path: str, params: list[tuple[str, str]], content: bytes | None) -> Any:
    if _http is None:
        raise HTTPException(status_code=503, detail="Tiger is unreachable")
    headers = {"content-type": "application/json"} if content else {}
    try:
        return await _http.request(
            method,
            TIGER_AGENT_URL.rstrip("/") + path,
            content=content,
            params=params,
            headers=headers,
            timeout=30,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Tiger is unreachable") from None


def _tiger_query(request: Request, name: str) -> str | None:
    values = [value for key, value in request.query_params.multi_items() if key == name]
    if not values:
        return None
    if any(value != values[0] for value in values):
        raise HTTPException(status_code=400, detail=f"{name} mismatch")
    return values[0]


@app.get("/v1/tiger/watchlist", dependencies=[Depends(require_key)])
async def tiger_list_watches(request: Request) -> Response:
    tenant_id = _tiger_tenant(request)
    resp = await _tiger_call("GET", "/watchlist", [("tenant_id", str(tenant_id))], None)
    return _tiger_response(resp, tenant_id)


@app.post("/v1/tiger/watchlist", dependencies=[Depends(require_key)])
async def tiger_create_watch(request: Request) -> Response:
    body = await _tiger_body(request)
    tenant_id = _tiger_tenant(request, body)
    forwarded: dict[str, Any] = {"tenant_id": str(tenant_id)}
    for key in ("url", "label", "engine", "every", "enabled", "threshold"):
        if key in body:
            forwarded[key] = body[key]
    resp = await _tiger_call("POST", "/watchlist", [], json.dumps(forwarded).encode())
    return _tiger_response(resp, tenant_id)


@app.delete("/v1/tiger/watchlist/{watch_id}", dependencies=[Depends(require_key)])
async def tiger_delete_watch(watch_id: uuid.UUID, request: Request) -> Response:
    body = await _tiger_body(request)
    tenant_id = _tiger_tenant(request, body)
    resp = await _tiger_call("DELETE", f"/watchlist/{watch_id}", [("tenant_id", str(tenant_id))], None)
    return _tiger_response(resp, tenant_id)


@app.get("/v1/tiger/observations", dependencies=[Depends(require_key)])
async def tiger_observations(request: Request) -> Response:
    tenant_id = _tiger_tenant(request)
    url = (_tiger_query(request, "url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    resp = await _tiger_call("GET", "/observations", [("tenant_id", str(tenant_id)), ("url", url)], None)
    return _tiger_response(resp, tenant_id)


@app.get("/v1/tiger/alerts", dependencies=[Depends(require_key)])
async def tiger_alerts(request: Request) -> Response:
    tenant_id = _tiger_tenant(request)
    params = [("tenant_id", str(tenant_id))]
    url = _tiger_query(request, "url")
    if url:
        params.append(("url", url.strip()))
    resp = await _tiger_call("GET", "/alerts", params, None)
    return _tiger_response(resp, tenant_id)


app.include_router(__import__("admin").router)
