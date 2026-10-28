"""Tank: the only path to any model in Tervory.

Endpoints
  GET  /health                           liveness
  POST /v1/route                         the one call agents and the Workspace make
  POST /v1/tasks                         queue a task (runs in the background through /v1/route logic)
  GET  /v1/tasks?tenant_id=              the board: a tenant's tasks, newest first
  GET  /v1/tasks/{id}?tenant_id=         one task
  POST /v1/ledger/{id}/feedback          a person's verdict on an answer: accepted | rejected
  GET  /v1/ledger/summary                spend by model and rung for a tenant (the client's ledger view)
  GET  /v1/skala                        Skala registry: every package, its state, and 30-day call cost
  POST /v1/skala/{id}/{ver}/evals       run a package's golden cases; candidate -> staging on pass
  POST /v1/skala/{id}/{ver}/approve     human sign-off; previous approved version retires
  POST /v1/skala/{id}/{ver}/retire      take a version out of service
  POST /v1/skala/{id}/run               run an approved skill (preview=true allows staging/candidate)
  POST /v1/base/run                      proxy to the Base room (passes 1-7; split_by_state = one batch per state, smallest first)
  POST /v1/base/retry                    proxy: re-queue a batch's failed records
  POST /v1/base/rerun                    proxy: re-run a batch's flagged records (e.g. no_website) with current skills
  GET  /v1/base/batches                  proxy: per-batch counts (status, tier, site/email coverage)
  GET  /v1/base/engines                  proxy: vertical engines available (e.g. ffl)
  GET  /v1/base/records?tenant_id=       proxy: enriched records, newest first
  GET  /v1/policy                        the routing policy rows
  PUT  /v1/policy/{task_type}            change a policy row (no deploy needed)
  GET  /v1/models                       the roster LiteLLM serves, with USD per million tokens
  GET  /v1/rig/search                    proxy: one tenant's catalogue search
  GET  /v1/rig/graph/{id}                proxy: fit graph for one product
  POST /v1/rig/compare                   proxy: prices for a selection already made
  POST /v1/rig/ask                       proxy: a catalogue question (model call is /v1/route)
  GET  /v1/rig/products/{id}             proxy: one product
  GET  /v1/rig/catalogues                proxy: product and fit counts for one catalogue
  GET  /v1/market/quarantine             founder: batches waiting in Market Lab
  POST /v1/market/quarantine/{batch}/release   founder: let a held batch into the pool
  POST /v1/market/quarantine/{batch}/reject    founder: keep a held batch out
  POST /v1/market/quarantine/{batch}/remove    founder: drop a batch and mark it removed

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
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import asyncpg
import httpx
from command_stream import StreamFailure, TokenSink, completion as stream_completion
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

import batch_providers
import graduate
import semantic_cache
import routellm_shadow
import skala
import skill_costs

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
_pii_detect = None
_skill_home: contextvars.ContextVar[str | None] = contextvars.ContextVar("zenas_skill_home", default=None)

app = FastAPI(title="Tervory Tank", version="0.2.0")
_pool: asyncpg.Pool | None = None
_background: set[asyncio.Task[None]] = set()
_batch_task: asyncio.Task[None] | None = None
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
    """Home used by /v1/route, /v1/tasks, /v1/skala/*/run and background tasks.

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


# Same ids as agents/zenas/core/release_mask.py COURT_SOURCES. Tank's image
# does not include that package. A test checks the two sets stay equal.
# Legislation sources are not in this set.
_COURT_SOURCES = frozenset(
    {
        "courtlistener",
        "cap",
        "saflii",
        "govza-gazette",
        "concourt",
        "sca",
        "cac",
        "comptrib",
        "sars-taxcourt",
        "landcourt",
        "ocj-highcourt",
        "labour-court",
        "labour-appeal",
        "special-tribunal",
    }
)
# require_key returns this for TANK_KEY_ZENAS. The request body cannot set it.
_ZENAS_CALLER = "zenas"
# The two prompts Zenas builds after it has read the pool. Anything else is
# not that read. Convert's head is agents/zenas/core/convert.py _PROMPT_HEAD.
_CONVERT_HEAD = (
    "Read this judgment as published. Copy the facts in the court's own words, "
    "as a continuous passage from the judgment. Name the question, the elements, "
    "and the holding. Cite only this case. Every quote must appear in the judgment "
    "word for word. For each issue the court decided, give the question, the order "
    "in the court's own words, and pointers to the reasoning. Do not shorten the "
    "reasoning and do not put a length cap on it. Mark likely ratio only on the "
    "exact words the decision rests on, and always label that marking likely. "
    "Mark obiter only where the court's own words show it "
    "(obiter, it is unnecessary to decide, I express no view). "
    "Keep each minority or dissent separate, labelled, and do not merge it into "
    "the majority. Reply with JSON only:\n"
    '{"facts":"","question":"","elements":[{"element_id":"","finding":"met|not_met|unclear","quote":""}],'
    '"holding":"","citations":[{"citation":"","quote":""}],'
    '"issues":[{"question":"","reasoning_pointer":{"paragraphs":[]},"order":"",'
    '"likely_ratio_pointer":{"paragraphs":[]},"obiter_pointer":{"paragraphs":[]},'
    '"minority":[{"judge":"","pointer":{"paragraphs":[]}}]}]}\n\n'
    "Citation: "
)
_FACTS_PREFIX = (
    "Read this judgment as published. Reply with JSON only: "
    '{"features":{},"narrative":"","element_findings":[{"element_id":"","finding":"met|not_met|unclear","reasoning":"","basis":[]}],"outcome":""}\n\n'
)
_POOL_MATCH_SQL = """
SELECT source_id, text, citation
FROM zenas_pool.documents
WHERE kind = 'case'
  AND effective_to IS NULL
  AND status IS DISTINCT FROM 'superseded'
  AND source_id = ANY($2::text[])
  AND char_length(text) >= 40
  AND char_length($1) >= char_length(text)
  AND right($1::text, char_length(text)) = text
""".strip()


def _zenas_pool_prefix(prefix: str, citation: str) -> bool:
    """True when the text before the stored judgment is that row's own wrapper.

    The citation is the one stored on the row. A caller cannot fill that
    line with other text.
    """
    if prefix == _FACTS_PREFIX:
        return True
    return bool(citation) and prefix == _CONVERT_HEAD + citation + "\n\n"


def _pool_read_candidate(text: str, *, caller: str | None, task_type: str | None, skill: str | None) -> bool:
    """The three names a caller can try to set. The database check is still ahead."""
    return caller == _ZENAS_CALLER and (task_type or "") == "zenas.case_facts" and not skill and bool(text)


async def zenas_pool_prompt(
    text: str,
    *,
    caller: str | None,
    task_type: str | None,
    skill: str | None,
) -> bool:
    """Whether this prompt is a judgment Tank just read from the pool.

    The caller cannot vouch for this. Tank loads zenas_pool.documents itself
    and accepts the prompt only when all of these are true: require_key
    returned the Zenas room (TANK_KEY_ZENAS), the task is zenas.case_facts,
    the call is not a Skala run, the prompt ends with a stored case whose
    source_id is in the court list, and the text before that case is either
    the facts wrapper or the convert wrapper plus that row's own citation.
    An added sentence, a different citation, a different wrapper, or a body
    field does not match a row, so the identifier rule still applies.
    """
    if not _pool_read_candidate(text, caller=caller, task_type=task_type, skill=skill):
        return False
    if not prompt_has_identifier(text):
        return False
    try:
        async with pool().acquire() as conn:
            rows = await conn.fetch(_POOL_MATCH_SQL, text, list(_COURT_SOURCES))
    except Exception:  # noqa: BLE001 — a failed read is not proof, and the text is not logged
        return False
    for row in rows:
        judgment = str(row["text"] or "")
        source = str(row["source_id"] or "")
        citation = str(row["citation"] or "")
        if source not in _COURT_SOURCES or len(judgment) < 40 or not text.endswith(judgment):
            continue
        if _zenas_pool_prefix(text[: -len(judgment)], citation):
            return True
    return False


def model_call_refusal(
    text: str,
    model: str | None,
    *,
    box: str,
    tenant_id: str,
    task_type: str | None = None,
    caller: str | None = None,
    skill: str | None = None,
    pool_read: bool = False,
) -> str | None:
    """Whether this model call must be refused before anything is stored or sent.

    In za, a prompt that still contains an identifier is refused unless the
    model runs in South Africa and the tenant's allow-list includes it.
    The identifier rule is skipped only when caller is the Zenas room key,
    the task is zenas.case_facts, this is not a Skala run, and pool_read is
    true. pool_read is true only after zenas_pool_prompt has matched the
    text to a court row. China-provider and allow-list refusals still apply.
    The Workspace key, every other room key, and a task name alone do not
    skip the rule. model=None asks the early question: is there any
    permitted SA model at all? Pure-code skills do not call this.
    """
    here = normalize_box(box)
    allow = tenant_allowlist(tenant_id)
    public_record = _pool_read_candidate(text, caller=caller, task_type=task_type, skill=skill) and pool_read
    if here != ZA_REGION:
        if model is not None and allow is not None and model not in allow:
            return ALLOW_REFUSAL
        return None
    hosted = sa_hosted_models()
    if prompt_has_identifier(text) and not public_record:
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


HOMES_PRINCIPAL = "founder-homes"
_HOMES_DENIED = "This homes key cannot call that."
_HOMES_LOAD = re.compile(r"^/v1/zenas/pool/sources/([A-Za-z0-9._-]{1,80})/load$")
_HOMES_FEEDS = frozenset({"/v1/zenas/selftest", "/v1/zenas/review-switch", "/v1/zenas/cases/convert"})


def _explicit_home_is_za(query_home: str | None, parsed: dict | None) -> bool:
    """True only when every stated home is za and at least one home is stated."""
    if query_home is not None and query_home != ZA_REGION:
        return False
    body_home = None
    if isinstance(parsed, dict) and "home_region" in parsed:
        body_home = parsed.get("home_region")
        if body_home != ZA_REGION:
            return False
    return query_home == ZA_REGION or body_home == ZA_REGION


async def _homes_tenant_body(request: Request) -> None:
    """POST /v1/zenas/tenants may name a tenant and home_region=za, nothing else."""
    query_home = request.query_params.get("home_region")
    if query_home is not None and query_home != ZA_REGION:
        raise HTTPException(status_code=403, detail=_HOMES_DENIED)
    try:
        parsed = json.loads(await request.body() or b"null")
    except (json.JSONDecodeError, UnicodeDecodeError):
        parsed = None
    if not isinstance(parsed, dict) or parsed.get("home_region") != ZA_REGION:
        raise HTTPException(status_code=403, detail=_HOMES_DENIED)
    if set(parsed) - {"tenant_id", "home_region"}:
        raise HTTPException(status_code=403, detail=_HOMES_DENIED)


async def _homes_founder_feed(request: Request, path: str) -> bool:
    """ZA founder feeds: status, one load, self-test, review switch, case conversion. Home must be za.

    Returns False when the path is not one of those routes. A matching route
    with the wrong home, a body, or extra fields is refused here. Allowed
    bodies are the fields those routes already take (source, review). They
    carry no document, matter, or client text.
    """
    method = request.method
    load = _HOMES_LOAD.fullmatch(path)
    allowed = (
        (method == "GET" and path == "/v1/zenas/pool/status")
        or (method == "POST" and load is not None)
        or (method in {"GET", "POST"} and path in _HOMES_FEEDS)
    )
    if not allowed:
        return False
    raw = await request.body()
    parsed: dict | None = None
    if method == "GET":
        if raw:
            raise HTTPException(status_code=403, detail=_HOMES_DENIED)
    elif raw:
        try:
            loaded = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=403, detail=_HOMES_DENIED) from None
        if not isinstance(loaded, dict):
            raise HTTPException(status_code=403, detail=_HOMES_DENIED)
        parsed = loaded
    if path in {"/v1/zenas/selftest", "/v1/zenas/cases/convert"}:
        if parsed and set(parsed) - {"home_region"}:
            raise HTTPException(status_code=403, detail=_HOMES_DENIED)
    elif path == "/v1/zenas/review-switch":
        if method == "POST" and (
            not parsed or set(parsed) - {"home_region", "review"} or parsed.get("review") not in {"on", "off"}
        ):
            raise HTTPException(status_code=403, detail=_HOMES_DENIED)
    elif load is not None and parsed:
        if set(parsed) - {"home_region", "source"}:
            raise HTTPException(status_code=403, detail=_HOMES_DENIED)
        if "source" in parsed and parsed.get("source") != load.group(1):
            raise HTTPException(status_code=403, detail=_HOMES_DENIED)
    if not _explicit_home_is_za(request.query_params.get("home_region"), parsed):
        raise HTTPException(status_code=403, detail=_HOMES_DENIED)
    return True


async def _homes_key_scope(request: Request) -> None:
    """TANK_HOMES_KEY on the ZA Tank only.

    It may set a za tenant's home. It may also read pool status, load one
    source, read or run the self-test, read or set the review switch, and read
    or run case conversion, each only with home_region=za. Those routes return names, counts, dates,
    errors and scores. Documents, matters and client data stay refused.
    The Boston Workspace holds this key. It never holds the ZA TANK_API_KEY.
    """
    if box_region() != ZA_REGION:
        raise HTTPException(status_code=403, detail=_HOMES_DENIED)
    path = request.url.path.rstrip("/")
    if request.method == "POST" and path == "/v1/zenas/tenants":
        await _homes_tenant_body(request)
        return
    if await _homes_founder_feed(request, path):
        return
    raise HTTPException(status_code=403, detail=_HOMES_DENIED)


async def require_key(request: Request, x_tank_key: str = Header(default="")) -> str | None:
    """Accept the Workspace key, or one agent key from TANK_KEY_<AGENT>.

    Returns None for the Workspace (TANK_API_KEY, unchanged) and the agent id
    for an agent key. Agent keys are taken from the environment only, compared
    as SHA-256 bytes. A removed TANK_KEY_* stops matching. The table is synced
    once; it is never used to authenticate. The raw key is never logged.
    An agent key may call /health, /v1/route, and /v1/skala/{id}/run only.
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
    # An empty key must not match an empty header. Whitespace is empty.
    if TANK_API_KEY.strip() and presented.strip() and same(presented_bytes, workspace_bytes):
        return None

    homes_key = os.environ.get("TANK_HOMES_KEY", "").strip()
    if homes_key and presented_bytes and same(presented_bytes, homes_key.encode()):
        await _homes_key_scope(request)
        return HOMES_PRINCIPAL

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
    skill_run = path.startswith("/v1/skala/") and path.endswith("/run") and path.count("/") == 4
    ghost_route = matched == "ghost" and (request.method, path) in __import__("ghost_routes").ROOM_METHODS
    vendor_write = request.method == "POST" and path == "/v1/ledger/vendor"
    batch_route = path == "/v1/route/batch" or (request.method == "GET" and path.startswith("/v1/route/batch/"))
    event_route = request.method == "POST" and path in {"/v1/events/publish", "/v1/events/receive", "/v1/events/settle"}
    if path not in {"/health", "/v1/route"} and not batch_route and not skill_run and not vendor_write and not ghost_route and not event_route:
        raise HTTPException(status_code=403, detail="This agent key cannot call that.")
    return matched


# ---------- models ----------

class Message(BaseModel):
    role: str
    content: str


class RouteRequest(BaseModel):
    complex_request: bool = False
    interactive: bool = True
    tenant_id: uuid.UUID
    agent: str = "tier0"
    task_type: str = "tier0.answer"
    priority: str | None = None          # overrides the policy's priority if set
    skill: str | None = None
    region: str | None = None
    home_region: str | None = None
    case_ref: str | None = None          # isolates internal bench samples in the cache
    messages: list[Message] = Field(min_length=1)
    max_tokens: int | None = Field(default=None, ge=1)          # a skill may ask for fewer than the policy's cap


class RouteResponse(BaseModel):
    ledger_id: uuid.UUID
    model: str
    rung: int
    content: str
    tokens_in: int
    tokens_out: int
    cost_usd: float | None
    latency_ms: int
    moa_run_id: uuid.UUID | None = None
    moa: dict[str, Any] | None = None
    finish_reason: str = ""
    escalation: list[dict[str, Any]] = Field(default_factory=list)
    batch: bool = False
    baseline_cost_usd: float | None = None
    discount_usd: float | None = None


class PolicyRow(BaseModel):
    task_type: str
    tenant_id: uuid.UUID | None = None
    rung: int = Field(default=1, ge=1, le=4)
    model: str
    priority: str = "standard"
    batch_eligible: bool = False
    cache_scope: str = "none"
    max_tokens_out: int = 1024
    system_prompt: str | None = None
    eval_threshold: float = graduate.DEFAULT_THRESHOLD
    escalation_model: str | None = None
    confidence_floor: float = Field(default=0.8, ge=0, le=1)
    acceptance_window_s: int = Field(default=86400, ge=0, le=2592000)
    semantic_cache: bool = False
    matter_matching: bool = False
    max_cost_usd: float = Field(default=1, gt=0)


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


async def _warn_unapproved_policy_pins() -> None:
    async with pool().acquire() as conn:
        rows = await conn.fetch("""SELECT p.task_type,p.tenant_id,p.model,s.state
            FROM tank.policy p LEFT JOIN tank.skills s
              ON s.id=split_part(substr(btrim(p.model),7),'@',1)
              AND s.version=split_part(substr(btrim(p.model),7),'@',2)
            WHERE btrim(p.model) LIKE 'skill:%' AND s.state IS DISTINCT FROM 'approved'
            ORDER BY p.task_type,p.tenant_id""")
    for row in rows:
        log.warning("Policy pins non-approved skill: task=%s tenant=%s model=%s state=%s; code cannot serve",
                    row["task_type"], row["tenant_id"] or "platform", row["model"], row["state"] or "missing")


@app.on_event("startup")
async def _startup() -> None:
    """Open the pool, then apply the schema. Every statement in schema.sql is
    idempotent (IF NOT EXISTS / ON CONFLICT DO NOTHING), so this is safe on
    every start and means the database can never be missing Tank's tables."""
    if not os.environ.get("TANK_API_KEY", "").strip():
        raise RuntimeError("TANK_API_KEY is empty")
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
    _http = httpx.AsyncClient(headers={"User-Agent": "Tervory/1.0 (+https://tervory.com)"}, timeout=15, event_hooks={"request": [__import__("controls").paid_host_hook], "response": [__import__("controls").paid_response_hook]})
    global _redis
    try:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        await _redis.ping()
    except Exception as exc:  # noqa: BLE001 — the cache is an optimisation; Tank runs without it
        log.warning("redis unavailable, rung-4 cache off: %s", exc)
        _redis = None
    _packages = skala.load_packages()
    await register_packages()
    await _warn_unapproved_policy_pins()
    global _batch_task
    _batch_task = asyncio.create_task(_batch_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _batch_task:
        _batch_task.cancel()
        await asyncio.gather(_batch_task, return_exceptions=True)
    if _redis:
        await _redis.aclose()
    if _http:
        await _http.aclose()
    if _pool:
        await _pool.close()


def tank_sha() -> str:
    """Git SHA baked into the image. Empty until a build sets TANK_GIT_SHA."""
    return os.environ.get("TANK_GIT_SHA", "").strip() or "unknown"


@app.get("/health")
async def health() -> dict[str, Any]:
    async with pool().acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"ok": True, "region": DEFAULT_REGION, "sha": tank_sha()}


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
async def list_policy(tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    """This tenant's rows, plus platform defaults. Not another tenant's prompt."""
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM tank.policy
            WHERE tenant_id = $1 OR tenant_id IS NULL
            ORDER BY task_type, tenant_id NULLS FIRST
            """,
            tenant_id,
        )
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        owner = item.get("tenant_id")
        if owner is not None and str(owner) != str(tenant_id):
            continue
        out.append(item)
    return out


@app.put("/v1/policy/{task_type}", dependencies=[Depends(require_key)])
async def put_policy(task_type: str, body: PolicyRow) -> dict[str, Any]:
    if body.task_type != task_type:
        raise HTTPException(status_code=400, detail="task_type in path and body differ")
    body.model = body.model.strip()
    if graduate.router_cannot_serve(body.model) or (graduate.is_skill(body.model) and body.rung != 3):
        raise HTTPException(status_code=400, detail=graduate.ROUTER_BLOCK)
    if graduate.is_skill(body.model):
        parsed = graduate.parse_skill(body.model)
        pkg = get_package(*parsed)
        await __import__("agent_skills").guard_submission_owner(__import__("sys").modules[__name__], pkg, body.tenant_id or PLATFORM_TENANT)
        problem = graduate.code_candidate_problem(body.model, state=await skill_state(*parsed), task_type=pkg.task_type, on_disk=True)
        if problem:
            raise HTTPException(409, problem)
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tank.policy
              (task_type, tenant_id, rung, model, priority, batch_eligible, cache_scope,
               max_tokens_out, system_prompt, eval_threshold, escalation_model,confidence_floor,acceptance_window_s,semantic_cache,matter_matching,max_cost_usd,updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16, now())
            ON CONFLICT (task_type, COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid))
            DO UPDATE SET rung=$3, model=$4, priority=$5, batch_eligible=$6, cache_scope=$7,
                          max_tokens_out=$8, system_prompt=$9, eval_threshold=$10, escalation_model=$11,confidence_floor=$12,
                          acceptance_window_s=$13,semantic_cache=$14,matter_matching=$15,max_cost_usd=$16,updated_at=now()
            """,
            body.task_type, body.tenant_id, body.rung, body.model, body.priority,
            body.batch_eligible, body.cache_scope, body.max_tokens_out, body.system_prompt,
            body.eval_threshold, body.escalation_model, body.confidence_floor, body.acceptance_window_s,
            body.semantic_cache, body.matter_matching, body.max_cost_usd,
        )
    return {"ok": True}


# ---------- the one call ----------

# Roster names that are Gemini. Gemini 3 Flash thinks at high unless told otherwise,
# and those thought tokens come out of max_tokens.
_GEMINI_MODELS = frozenset({"flash", "flash-lite", "argon"})
_JSON_OBJECT_MODELS = _GEMINI_MODELS | frozenset(
    {"luna", "sol", "astra", "grok", "grok-top", "grok-build"}
)


def _gemini_model(model: str) -> bool:
    name = (model or "").strip().lower()
    return name in _GEMINI_MODELS or "gemini" in name


def _json_object_model(model: str) -> bool:
    name = (model or "").strip().lower()
    if name in _JSON_OBJECT_MODELS or _gemini_model(name):
        return True
    return name.startswith("gpt") or name.startswith("openai/") or "grok" in name


def case_facts_generation(model: str) -> dict[str, Any]:
    """JSON output, and low thinking for Gemini, for zenas.case_facts only.

    Gemini 3 Flash defaults to high thinking. Thought tokens come out of
    max_tokens, so the answer comes back empty. reasoning_effort low is what
    LiteLLM maps to thinking_level low on Gemini 3, and to a small thinking
    budget on Gemini 2.5. A thinking budget on its own does not set that
    level on Gemini 3, so it is not sent. JSON mode goes only to models that
    support a JSON object.
    """
    body: dict[str, Any] = {}
    if _json_object_model(model):
        body["response_format"] = {"type": "json_object"}
    if _gemini_model(model):
        body["reasoning_effort"] = "low"
    return body


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    return ""


def _choice_answer(data: dict[str, Any]) -> tuple[str, str]:
    choices = data.get("choices") or [{}]
    choice = choices[0] if isinstance(choices, list) and choices else {}
    if not isinstance(choice, dict):
        return "", ""
    message = choice.get("message") or {}
    if not isinstance(message, dict):
        message = {}
    return _content_text(message.get("content")), str(choice.get("finish_reason") or "")


# The shared override gate for Command and MoA. Never persist policy changes
# to pin one call; MoA uses the parent task's policy limits.
MODEL_OVERRIDE_TASK_TYPES = frozenset({"command.turn"})
MOA_SEAT_TASK = re.compile(r"[a-zA-Z0-9_.-]+#moa\.[a-z][a-z0-9_]{0,79}")


def override_allowed(task_type: str) -> bool:
    return task_type in MODEL_OVERRIDE_TASK_TYPES or MOA_SEAT_TASK.fullmatch(task_type) is not None


def _plain_value(value: Any) -> Any:
    """Drop explicitly labelled HTML fields; never parse or rewrite prompt text."""
    if isinstance(value, dict):
        return {k: _plain_value(v) for k, v in value.items() if str(k).lower() not in {"html", "raw_html"}}
    if isinstance(value, list):
        return [_plain_value(v) for v in value]
    return value


def _plain_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    result = []
    for message in messages:
        text = message["content"]
        try:
            value = json.loads(text)
        except (ValueError, TypeError):
            value = text
        clean = _plain_value(value)
        # Preserve the original bytes unless labelled HTML fields were removed.
        result.append({"role": message["role"], "content": text if clean == value else json.dumps(clean)})
    return result


def _contains_html(value: Any) -> bool:
    """Recognize explicit markup, not mathematical '<' text or invented tag names.

    This is a refusal check, never an HTML parser or prompt transformation.
    Labelled html/raw_html fields are removed separately by _plain_value.
    """
    if isinstance(value, dict):
        return any(_contains_html(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_html(v) for v in value)
    if not isinstance(value, str):
        return False
    tags = "html|head|body|title|script|style|template|div|span|p|a|b|i|em|strong|table|tr|td|th|ul|ol|li|h[1-6]|form|button|section|article|pre|code"
    attributes = r'''(?:\s+[a-z_:][\w:.-]*\s*=\s*(?:"[^"]*"|'[^']*'))*\s*'''
    return bool(re.search(
        rf"<!doctype\s+html\b|<!--.*?-->|<(?P<tag>{tags})(?:\s+[^<>]*?)?>.*?</(?P=tag)\s*>|<(?:br|hr|img|input|meta|link){attributes}/?>",
        value, re.I | re.S,
    ))


def _storage_mask(value: Any) -> Any:
    """Never fail a completed call while retaining its transcript; redact on failure."""
    try:
        if _contains_html(value):
            return "[omitted: HTML]"
        return _screen_mask(_plain_value(value))
    except Exception:
        return "[omitted: masking unavailable]"


async def _refuse_input(req: RouteRequest, policy: dict[str, Any], error: str,
                        task_id: uuid.UUID | None = None) -> None:
    receipt = await _record_local(req, policy, model=str(policy.get("model", "skill")),
                                  rung=int(policy.get("rung", 3)), content="", outcome="failed",
                                  error=error, task_id=task_id, masked_messages=[])
    raise HTTPException(422, {"error": error, "ledger_id": str(receipt.ledger_id),
                              "receipt": receipt.model_dump(mode="json")})


async def _preflight_mask(req: RouteRequest, policy: dict[str, Any], messages: list[dict[str, str]],
                          task_id: uuid.UUID | None = None) -> Any:
    try:
        original = _screen_mask(_plain_messages([m.model_dump() for m in req.messages]))
        # Include policy/system text before any code or paid execution.
        _screen_mask(_plain_messages(messages))
        json.dumps(original)
        return original
    except Exception:
        await _refuse_input(req, policy, "Input could not be masked; no execution was started", task_id)


async def _check_route_task(req: RouteRequest, task_id: uuid.UUID | None) -> None:
    if task_id is None:
        return
    async with pool().acquire() as conn:
        status = await conn.fetchval("SELECT status FROM tank.tasks WHERE id=$1 AND tenant_id=$2", task_id, req.tenant_id)
        if status is None and req.agent == "base":
            status = await conn.fetchval("SELECT status FROM agent_base.tasks WHERE id=$1 AND tenant_id=$2", task_id, req.tenant_id)
            # The Base brain continues after its free pipeline marks the batch
            # done. Explicit cancellation/failure still stops further work.
            if status == "done":
                return
    if status is None:
        raise HTTPException(404, "No task for this tenant")
    if status in {"cancelled", "canceled", "failed", "done"}:
        raise HTTPException(409, "Task is no longer running")


async def _record_local(req: RouteRequest, policy: dict[str, Any], *, model: str, rung: int,
                        content: str, task_id: uuid.UUID | None = None, outcome: str = "delivered",
                        escalation: list[dict[str, Any]] | None = None, latency_ms: int = 0,
                        error: str | None = None, route_seat: str | None = None,
                        masked_messages: Any = None) -> RouteResponse:
    ledger_id = uuid.uuid4()
    # Retain an example even for code/cache runs, but never raw identifiers/HTML.
    clean = masked_messages if masked_messages is not None else _storage_mask(_plain_messages([m.model_dump() for m in req.messages]))
    output = _storage_mask(content)
    async with pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO tank.ledger(id,tenant_id,region,agent,skill,task_type,rung,model,priority,
                cost_usd,latency_ms,cache_hit,outcome,task_id,error,escalation,accept_after,route_seat)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,0,$10,$11,$12,$13,$14,$15::jsonb,
                now()+make_interval(secs=>$16),$17)""",
                ledger_id, req.tenant_id, box_region(), req.agent, req.skill, req.task_type, rung, model,
                req.priority or policy.get("priority", "standard"), latency_ms, rung == 4, outcome,
                task_id, error, json.dumps(escalation or []), int(policy.get("acceptance_window_s", 86400)), route_seat,
            )
            await conn.execute(
                "INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content) VALUES($1,$2,$3,$4::jsonb,$5)",
                ledger_id, req.tenant_id, req.task_type, json.dumps(clean), output[:20000],
            )
    return RouteResponse(ledger_id=ledger_id, model=model, rung=rung, content=content, tokens_in=0,
                         tokens_out=0, cost_usd=0, latency_ms=latency_ms, escalation=escalation or [])


def _cache_identity(req: RouteRequest, policy: dict[str, Any], messages: list[dict[str, str]],
                    max_tokens: int, route_seat: str | None) -> tuple[str, str, str]:
    # Whole policy revision, pinned skill, system messages, matter and generation
    # limits participate. Even legacy platform/region scopes stay tenant-local.
    context = [policy, req.skill, req.case_ref, route_seat, max_tokens, box_region(),
               [m for m in messages if m["role"] != "user"]]
    context_hash = hashlib.sha256(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()
    exact = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()
    return context_hash, exact, graduate.semantic_form(messages)


async def _cache_read(req: RouteRequest, policy: dict[str, Any], identity: tuple[str, str, str]) -> str | None:
    if (policy.get("cache_scope") not in {"tenant", "platform", "region"}
            or (policy.get("matter_matching") and not req.case_ref)):
        return None
    context, exact, form = identity
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT c.input_hash,c.semantic_form,c.vector,c.tenant_id,t.content
            FROM tank.route_cache c JOIN tank.ledger l ON l.id=c.ledger_id AND l.tenant_id=c.tenant_id
            JOIN tank.transcripts t ON t.ledger_id=l.id AND t.tenant_id=c.tenant_id
            WHERE c.tenant_id=$1 AND c.region=$2 AND c.task_type=$3 AND c.context_hash=$4
              AND c.expires_at>now() AND l.outcome='delivered' AND l.feedback IS DISTINCT FROM 'rejected'
              AND (c.input_hash=$5 OR ($6 AND c.semantic_form=$7))
            ORDER BY (c.input_hash=$5) DESC LIMIT 1""",
            req.tenant_id, box_region(), req.task_type, context, exact,
            bool(policy.get("semantic_cache")) and req.task_type != "command.turn" and (not policy.get("matter_matching") or bool(req.case_ref)), form,
        )
    if not rows:
        return None
    row = dict(rows[0])
    if row["input_hash"] == exact:
        return row["content"]
    row["vector"] = json.loads(row["vector"]) if isinstance(row["vector"], str) else row["vector"]
    hit = graduate.semantic_lookup(graduate.semantic_vector(form), [row], tenant_id=str(req.tenant_id), scope="tenant")
    return hit["content"] if hit else None


async def _cache_write(req: RouteRequest, policy: dict[str, Any], identity: tuple[str, str, str], ledger_id: uuid.UUID) -> None:
    if (policy.get("cache_scope") not in {"tenant", "platform", "region"}
            or (policy.get("matter_matching") and not req.case_ref)):
        return
    context, exact, form = identity
    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO tank.route_cache(tenant_id,region,task_type,context_hash,input_hash,semantic_form,vector,ledger_id,expires_at)
            VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8,now()+make_interval(secs=>$9))
            ON CONFLICT(tenant_id,region,task_type,context_hash,input_hash) DO UPDATE
            SET ledger_id=EXCLUDED.ledger_id,vector=EXCLUDED.vector,semantic_form=EXCLUDED.semantic_form,expires_at=EXCLUDED.expires_at""",
            req.tenant_id, box_region(), req.task_type, context, exact, form,
            json.dumps(graduate.semantic_vector(form)), ledger_id, CACHE_TTL_S,
        )


async def run_route(
    req: RouteRequest,
    task_id: uuid.UUID | None = None,
    caller: str | None = None,
    *,
    model_override: str | None = None,
    _defer_paid: bool = False,
    _paid_policy: dict[str, Any] | None = None,
    _prior_escalation: list[dict[str, Any]] | None = None,
    _paid_limit: float | None = None,
    _on_token: TokenSink | None = None,
) -> RouteResponse:
    """Pick the model from policy, call it through LiteLLM, write the ledger row.
    Used directly by /v1/route and in the background by tasks."""
    await _check_route_task(req, task_id)
    box = box_region()
    foreign = home_region_refusal(call_home(req.home_region, box), box)
    if foreign:
        # Empty, unknown, or the other region's text is not written.
        raise HTTPException(status_code=403, detail=foreign)
    client_text = "\n".join(m.content for m in req.messages)
    pool_read = await zenas_pool_prompt(
        client_text, caller=caller, task_type=req.task_type, skill=req.skill
    )
    early = model_call_refusal(
        client_text,
        None,
        box=box,
        tenant_id=str(req.tenant_id),
        task_type=req.task_type,
        caller=caller,
        skill=req.skill,
        pool_read=pool_read,
    )
    if early:
        raise HTTPException(status_code=403, detail=early)

    seat = MOA_SEAT_TASK.fullmatch(req.task_type)
    if seat and model_override is None:
        raise HTTPException(status_code=400, detail="A MoA seat requires a model override")
    if model_override is not None:
        if not override_allowed(req.task_type):
            raise HTTPException(status_code=403, detail="Model override is not enabled for this task type")
        if model_override not in {row["name"] for row in await list_models()}:
            raise HTTPException(status_code=422, detail="Model is not on the roster")
    policy = await load_policy(req.task_type.partition("#moa.")[0], req.tenant_id)
    if _paid_policy is not None:
        policy = _paid_policy
    if model_override is not None:
        policy = {**policy, "model": model_override, "rung": 1, "candidate_model": None, "shadow_rate": 0}
    route_seat = req.task_type.partition("#moa.")[2] if seat else (
        "pinned" if req.task_type == "command.turn" and model_override is not None else None)
    model = str(policy["model"]).strip()
    # skill: and cache: are not model names. Do not send them to LiteLLM.
    if graduate.router_cannot_serve(model):
        raise HTTPException(status_code=400, detail=graduate.ROUTER_BLOCK)
    priority = req.priority or policy["priority"]

    messages = [m.model_dump() for m in req.messages]
    if policy["system_prompt"]:
        messages = [{"role": "system", "content": policy["system_prompt"]}, *messages]
    if req.task_type == "zenas.case_facts" and any(str(message.get("content", "")).startswith(_CONVERT_HEAD) for message in messages):
        messages.insert(0, {"role": "system", "content": (
            "For this judgment conversion use facts_pointer and element quote_pointer objects instead of copying text. "
            "Each pointer is {\"paragraphs\":[1,2]} or {\"first\":\"first eight words\",\"last\":\"last eight words\"}. "
            "Select at least 200 characters of facts. Return question, holding, elements and citations as JSON."
        )})
    max_tokens = min(req.max_tokens or policy["max_tokens_out"], policy["max_tokens_out"])
    generation = case_facts_generation(model) if req.task_type == "zenas.case_facts" else {}
    if model_override is not None:
        generation = {**generation, "disable_fallbacks": True}
    sent = "\n".join(str(item.get("content") or "") for item in messages)
    holds_identifier = prompt_has_identifier(sent)
    blocked = model_call_refusal(
        sent,
        None if graduate.is_skill(model) or int(policy["rung"]) == 3 else model,
        box=box,
        tenant_id=str(req.tenant_id),
        task_type=req.task_type,
        caller=caller,
        skill=req.skill,
        pool_read=pool_read,
    )
    if blocked and int(policy["rung"]) not in {3, 4}:
        raise HTTPException(status_code=403, detail=blocked)

    # Validate ownership/version before reuse; an unavailable approval escalates.
    code_problem = None
    if graduate.is_skill(model):
        parsed = graduate.parse_skill(model)
        pkg = get_package(*parsed)
        await __import__("agent_skills").guard_submission_owner(__import__("sys").modules[__name__], pkg, req.tenant_id)
        state = await skill_state(*parsed)
        problem = graduate.code_candidate_problem(model, state=state, task_type=pkg.task_type, on_disk=True)
        if state != "approved":
            code_problem = "skill_not_approved"
        elif problem:
            raise HTTPException(409, problem)
        if int(policy["rung"]) != 3:
            raise HTTPException(409, "A skill policy must start at rung 3")
    transcript_messages = await _preflight_mask(req, policy, messages, task_id)
    identity = _cache_identity(req, policy, messages, max_tokens, route_seat)
    cache_policy, cache_probe = dict(policy), None
    if not holds_identifier and code_problem is None:
        hit = await _cache_read(req, policy, identity)
        if hit is not None:
            await _check_route_task(req, task_id)
            return await _record_local(req, policy, model=model, rung=4, content=hit, task_id=task_id, route_seat=route_seat)
        cache_probe = await semantic_cache.lookup(__import__("sys").modules[__name__], req, cache_policy, identity, messages)
        if await semantic_cache.may_serve(__import__("sys").modules[__name__], req, cache_policy, cache_probe):
            await _check_route_task(req, task_id)
            return await _record_local(req, policy, model=semantic_cache.CANDIDATE, rung=4,
                                       content=cache_probe.content, task_id=task_id, route_seat=route_seat)

    escalation: list[dict[str, Any]] = list(_prior_escalation or [])
    if int(policy["rung"]) == 4:
        escalation.append({"from_rung": 4, "to_rung": 3, "reason": "cache_miss", "model": model})
        policy = {**policy, "rung": 3}
    if int(policy["rung"]) == 3:
        started_code = time.perf_counter()
        content = ""
        reason = code_problem or "no_code_skill"
        if graduate.is_skill(model) and code_problem is None:
            try:
                async with asyncio.timeout(30):
                    content, _cost = await _run_code_candidate(req, model, messages)
                reason = graduate.code_failure(json.loads(content), float(policy.get("confidence_floor", 0.8)))
            except HTTPException as exc:
                if exc.status_code in {403, 404, 409}:
                    raise
                reason = "skill_error"
            except Exception:
                reason = "skill_error"
        await _check_route_task(req, task_id)
        if reason is None:
            result = await _record_local(req, policy, model=model, rung=3, content=content, task_id=task_id,
                                         latency_ms=int((time.perf_counter()-started_code)*1000))
            if not holds_identifier and _storage_mask(content) == content:
                await _cache_write(req, policy, identity, result.ledger_id)
                semantic_cache.schedule(__import__("sys").modules[__name__], req, cache_policy, identity,
                                        messages, cache_probe, result.ledger_id, content, 0.0)
            return result
        escalation.append({"from_rung": 3, "to_rung": 2, "reason": reason, "model": model})
        attempt = await _record_local(req, policy, model=model, rung=3, content=content, task_id=task_id,
                                      outcome="unverified", escalation=escalation, error=reason)
        escalation[-1]["ledger_id"] = str(attempt.ledger_id)
        model = policy.get("escalation_model") or policy.get("previous_model") or (model if not graduate.is_skill(model) else None)
        if not model or graduate.is_skill(model) or graduate.router_cannot_serve(model):
            raise HTTPException(409, {"ledger_id": str(attempt.ledger_id), "error": "No paid escalation model in policy"})
        policy = {**policy, "model": model, "rung": 2}
        generation = case_facts_generation(model) if req.task_type == "zenas.case_facts" else {}

    # Code may parse labelled HTML. Prompt text is never parsed or rewritten.
    messages = _plain_messages(messages)
    if _contains_html(messages):
        await _refuse_input(req, policy, "HTML must be supplied in html/raw_html fields with separately extracted text", task_id)
    sent = "\n".join(m["content"] for m in messages)
    blocked = model_call_refusal(sent, model, box=box, tenant_id=str(req.tenant_id),
                                 task_type=req.task_type, caller=caller, skill=req.skill, pool_read=pool_read)
    if blocked:
        raise HTTPException(403, blocked)
    await _check_route_task(req, task_id)
    if _defer_paid and not holds_identifier:
        raise _DeferredRoute(req, policy, messages, max_tokens, generation, escalation,
                             semantic_cache.batch_snapshot(cache_policy, identity, cache_probe))
    if _paid_limit is not None:
        prices = await _batch_price(model)
        if _call_upper(messages, max_tokens, prices) > _paid_limit:
            raise HTTPException(409, "Task cost cap prevents another call")
        generation = {**generation, "disable_fallbacks": True}
    await __import__("controls").refuse_paid(paid=True, task=req.task_type, path="route")
    started = time.perf_counter()
    try:
        if _on_token is not None and req.task_type == "command.turn":
            r = await stream_completion(LITELLM_URL, LITELLM_MASTER_KEY,
                                        {"model": model, "messages": messages, "max_tokens": max_tokens, **generation}, _on_token)
        else:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(
                    f"{LITELLM_URL}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                    json={"model": model, "messages": messages, "max_tokens": max_tokens, **generation},
                )
    except StreamFailure as exc:
        ledger_id = uuid.uuid4()
        async with pool().acquire() as conn:
            await conn.execute(
                "INSERT INTO tank.ledger "
                "(id,tenant_id,region,agent,skill,task_type,rung,model,priority,tokens_in,tokens_out,cost_usd,"
                "latency_ms,cache_hit,outcome,task_id,error,route_seat,escalation,cost_status) "
                "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,false,'failed',$14,$15,$16,$17::jsonb,$18)",
                ledger_id, req.tenant_id, req.region or DEFAULT_REGION, req.agent, req.skill, req.task_type,
                policy["rung"], exc.model, priority, exc.tokens_in, exc.tokens_out, exc.cost_usd or 0,
                int((time.perf_counter() - started) * 1000), task_id, "incomplete stream", route_seat, json.dumps(escalation),
                # Existing NOT NULL storage convention: not_set is never shown as zero spend.
                "not_set" if exc.cost_usd is None else "set",
            )
        raise HTTPException(502, {"ledger_id": str(ledger_id)}) from None
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
                   tokens_in, tokens_out, cost_usd, latency_ms, cache_hit, outcome, task_id, error, route_seat, escalation)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,0,0,0,$10,false,'failed',$11,$12,$13,$14::jsonb)
                """,
                ledger_id, req.tenant_id, req.region or DEFAULT_REGION, req.agent, req.skill,
                req.task_type, policy["rung"], model, priority, latency_ms, task_id, err, route_seat, json.dumps(escalation),
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
    finish_reason = ""
    if outcome == "delivered":
        content, finish_reason = _choice_answer(data)

    ledger_id = uuid.uuid4()
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tank.ledger
              (id, tenant_id, region, agent, skill, task_type, rung, model, priority,
               tokens_in, tokens_out, cost_usd, latency_ms, cache_hit, outcome, task_id, error, route_seat,escalation,accept_after)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,false,$14,$15,$16,$17,$18::jsonb,now()+make_interval(secs=>$19))
            """,
            ledger_id, req.tenant_id, req.region or DEFAULT_REGION, req.agent, req.skill,
            req.task_type, policy["rung"], answered, priority, tokens_in, tokens_out, cost_usd,
            latency_ms, outcome, task_id, error, route_seat, json.dumps(escalation), int(policy.get("acceptance_window_s", 86400)),
        )

    if outcome == "failed":
        upstream: Any = "provider error" if holds_identifier else (data or r.text[:500])
        raise HTTPException(status_code=502, detail={"ledger_id": str(ledger_id), "upstream": upstream})

    # Graduation: shadow the candidate on a share of calls; it never affects this answer.
    # An identifier prompt is not copied to a second provider or into the transcript.
    if not holds_identifier and policy.get("candidate_model") and float(policy.get("shadow_rate") or 0) > random.random():
        t = asyncio.create_task(_shadow(req, policy, messages, max_tokens, ledger_id, content, cost_usd))
        _background.add(t)
        t.add_done_callback(_background.discard)

    if not holds_identifier and model_override is None and routellm_shadow.configuration(policy):
        t = asyncio.create_task(routellm_shadow.observe(
            __import__("sys").modules[__name__], req, policy, messages, max_tokens,
            ledger_id, content, cost_usd, answered, "x-litellm-response-cost" in r.headers))
        _background.add(t)
        t.add_done_callback(_background.discard)

    masked_content = _storage_mask(content)
    if not holds_identifier:
        async with pool().acquire() as conn:
            await conn.execute(
                "INSERT INTO tank.transcripts (ledger_id,tenant_id,task_type,messages,content) VALUES($1,$2,$3,$4::jsonb,$5)",
                ledger_id, req.tenant_id, req.task_type,
                json.dumps(transcript_messages),
                masked_content[:20000],
            )
    if content and not holds_identifier and masked_content == content:
        await _cache_write(req, policy, identity, ledger_id)
        semantic_cache.schedule(__import__("sys").modules[__name__], req, cache_policy, identity,
                                messages, cache_probe, ledger_id, content, cost_usd)
    return RouteResponse(
        ledger_id=ledger_id, model=answered, rung=policy["rung"], content=content,
        tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd, latency_ms=latency_ms,
        finish_reason=finish_reason, escalation=escalation,
    )


async def _llm(model: str, messages: list[dict[str, str]], max_tokens: int, *, receipt: dict | None = None) -> tuple[str, float]:
    messages = _plain_messages(messages)
    if _contains_html(messages):
        raise ValueError("HTML is not model input; supply extracted text")
    _screen_mask(messages)
    await __import__("controls").refuse_paid(path="_llm")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens,
                  **({"disable_fallbacks": True} if receipt is not None else {})},
        )
    if r.status_code != 200:
        raise RuntimeError(f"{model}: {r.status_code} {r.text[:200]}")
    data = r.json()
    if receipt is not None:
        usage = data.get("usage") or {}
        receipt.update(model=r.headers.get("x-litellm-model-group") or model,
                       cost=float(r.headers["x-litellm-response-cost"]) if "x-litellm-response-cost" in r.headers else None,
                       tokens_in=int(usage.get("prompt_tokens") or 0), tokens_out=int(usage.get("completion_tokens") or 0))
        if receipt["model"] != model:
            raise RuntimeError("shadow provider returned a different model")
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


# The roster LiteLLM actually serves. The Tank image has no copy of litellm/config.yaml,
# so the file roster above is empty in production; LiteLLM's own /model/info is the source.
_ROSTER_TTL_S = 300
_roster_cache: tuple[float, list[dict[str, Any]]] | None = None


def _roster_row(item: Any) -> dict[str, Any] | None:
    """One served model in roster shape: name, provider model and prices only, never a key."""
    if not isinstance(item, dict):
        return None
    name = str(item.get("model_name") or "").strip()
    if not name:
        return None
    params = item.get("litellm_params") if isinstance(item.get("litellm_params"), dict) else {}
    info = item.get("model_info") if isinstance(item.get("model_info"), dict) else {}

    def price(key: str) -> float | None:
        value = info.get(key)
        if value is None:
            value = params.get(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number >= 0 else None

    return {
        "model_name": name,
        "litellm_params": {"model": str(params.get("model") or "")},
        "model_info": {
            "input_cost_per_token": price("input_cost_per_token"),
            "output_cost_per_token": price("output_cost_per_token"),
        },
    }


async def _roster_models() -> list[dict[str, Any]]:
    """Models LiteLLM serves, with per-token prices, cached five minutes. The file roster is the fallback."""
    global _roster_cache
    now = time.time()
    if _roster_cache is not None and now - _roster_cache[0] < _ROSTER_TTL_S:
        return _roster_cache[1]
    rows: list[dict[str, Any]] = []
    if _http is not None and hasattr(_http, "get"):
        try:
            response = await _http.get(
                f"{LITELLM_URL}/model/info",
                headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                timeout=10,
            )
            if response.status_code == 200:
                payload = response.json()
                data = payload.get("data") if isinstance(payload, dict) else None
                seen: set[str] = set()
                for item in data or []:
                    row = _roster_row(item)
                    if row is not None and row["model_name"] not in seen:
                        seen.add(row["model_name"])
                        rows.append(row)
        except Exception:  # noqa: BLE001 - a missing or odd LiteLLM answer falls back to the file roster
            rows = []
    if rows:
        _roster_cache = (now, rows)  # only LiteLLM's live answer is cached
        return rows
    path = _roster_path()
    if not path.is_file():
        return []
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [row for row in (_roster_row(item) for item in raw.get("model_list") or []) if row]


async def _live_price_quotes() -> list[graduate.Quote]:
    """Price quotes for the cheapest-model search, from the served roster."""
    rows = await _roster_models()
    return graduate.quotes_from_roster(
        [{**row, "model_info": {key: (value or 0) for key, value in row["model_info"].items()}} for row in rows]
    )


def _per_million(value: Any) -> float | None:
    return round(float(value) * 1_000_000, 4) if isinstance(value, (int, float)) else None


@app.get("/v1/models", dependencies=[Depends(require_key)])
async def list_models() -> list[dict[str, Any]]:
    """The served roster for the Tank page: name, provider model, USD per million tokens. No keys."""
    out = [
        {
            "name": row["model_name"],
            "provider_model": row["litellm_params"]["model"],
            "input_usd_per_m": _per_million(row["model_info"].get("input_cost_per_token")),
            "output_usd_per_m": _per_million(row["model_info"].get("output_cost_per_token")),
        }
        for row in await _roster_models()
    ]
    return sorted(out, key=lambda m: ((m["input_usd_per_m"] or 0) + (m["output_usd_per_m"] or 0), m["name"]))


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
    await __import__("agent_skills").guard_submission_owner(__import__("sys").modules[__name__], pkg, req.tenant_id)
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
        _model=_forbid, http=_http, env={k: v for k, v in SKILL_ENV.items() if not k.endswith(("_KEY", "_TOKEN"))},
    )
    out = await skala.run_skill(pkg, graduate.skill_payload(messages), ctx)
    if ctx.calls or ctx.cost_usd:
        raise RuntimeError("code candidate attempted paid work")
    return json.dumps(out), 0.0


async def _shadow(req: RouteRequest, policy: dict[str, Any], messages: list[dict[str, str]], max_tokens: int,
                  ledger_id: uuid.UUID, primary: str, primary_cost: float, *,
                  routellm: tuple | None = None, cache_content: str | None = None) -> dict | None:
    """Run the candidate on the same input, score agreement with the primary, record both.
    The client already has the primary answer. Spend lands on the platform tenant.
    Code skills cost nothing and are not subject to the daily shadow budget."""
    cache = cache_content is not None
    cand = semantic_cache.CANDIDATE if cache else policy["candidate_model"]
    if not cache and graduate.is_semantic_cache(cand):
        # Proved by graduate.semantic_lookup (local vectors, no paid call) before it is switched on.
        return
    if graduate.is_tool(cand):
        log.warning("shadow %s skipped %s: a paid tool is not started from here", req.task_type, cand)
        return
    code = graduate.is_skill(cand)
    budget_open = code or await _shadow_budget_open(req.task_type)
    if not cache and not budget_open:
        log.warning("shadow %s skipped %s: daily budget spent", req.task_type, cand)
        return
    cand_content, cand_cost, agreement, method, fields = None, 0.0, None, "failed", {}
    receipt: dict = {}
    try:
        if cache:
            cand_content = cache_content
        elif code:
            cand_content, cand_cost = await _run_code_candidate(req, cand, messages)
        else:
            cand_content, cand_cost = await _llm(cand, messages, max_tokens, **({"receipt": receipt} if routellm else {}))
        compared = graduate.compare(primary, cand_content, tolerance=float(policy.get("number_tolerance") or 0.01))
        if compared.method == "fields":
            agreement, method, fields = compared.agreement, "fields", compared.fields
        elif cache and (len(primary) > 4000 or len(cand_content) > 4000):
            # A truncated prose comparison cannot prove the entire cached answer.
            method = "answer_too_long"
        elif not budget_open:
            method = "budget_exhausted"
        else:
            jp = await load_policy("tank.judge", PLATFORM_TENANT)
            jmsgs = [{"role": "system", "content": jp["system_prompt"]},
                     {"role": "user", "content": f"REQUEST:\n{messages[-1]['content'][:3000]}\n\nFIRST ANSWER:\n{primary[:4000]}\n\nSECOND ANSWER:\n{cand_content[:4000]}"}]
            verdict, jcost = await _llm(jp["model"], jmsgs, jp["max_tokens_out"])
            cand_cost += jcost
            found = re.search(r"\d{1,3}", verdict)
            agreement, method = (min(100, int(found.group())) / 100 if found else None), "judge"
    except Exception as exc:  # noqa: BLE001
        log.warning("shadow %s→%s failed: %s", policy["model"], cand, type(exc).__name__ if routellm else exc)
    if routellm:
        config, primary_known = routellm
        await routellm_shadow.save(__import__("sys").modules[__name__], req, config, ledger_id,
            primary, primary_cost, primary_known, cand_content, max(cand_cost, receipt.get("cost") or 0),
            receipt, agreement, method, fields)
        return
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
        # Paid R&D stays on platform. Zero-cost code evidence remains tenant-owned.
        shadow_ledger = await conn.fetchval(
            """
            INSERT INTO tank.ledger (tenant_id, region, agent, task_type, rung, model, priority, tokens_in, tokens_out,
                                     cost_usd, latency_ms, cache_hit, outcome)
            VALUES ($1,$2,'tank',$3,$4,$5,'batch',0,0,$6,0,false,$7) RETURNING id
            """,
            req.tenant_id if code else PLATFORM_TENANT, DEFAULT_REGION, f"{req.task_type}#shadow", 3 if code else 1, cand, cand_cost,
            "delivered" if cand_content is not None else "failed",
        )
        if code:
            await conn.execute("INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content) VALUES($1,$2,$3,$4::jsonb,$5)",
                shadow_ledger, req.tenant_id, req.task_type+"#shadow", json.dumps(_storage_mask(_plain_messages(messages))),
                _storage_mask(cand_content or "")[:20000])
        await _add_spend(conn, req.task_type, cand_cost)
    if not cache:
        await _move_task(req.task_type)
    return {"agreement": agreement, "method": method, "evaluation_cost_usd": cand_cost}


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
            if graduate.is_skill(policy.get("candidate_model")):
                problem = await _check_code_candidate(conn, policy["candidate_model"])
                if problem:
                    return graduate.Move("hold", policy, problem)
                skill_id, version = graduate.parse_skill(policy["candidate_model"])
                owner = await conn.fetchrow("SELECT tenant_id,region FROM tank.agent_skill_submissions WHERE skill_id=$1 AND version=$2", skill_id, version)
                if owner and (owner["tenant_id"] != PLATFORM_TENANT or owner["region"] != box_region()):
                    return graduate.Move("hold", policy, "Private code cannot become a global policy")
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
        SELECT s.id,s.version FROM tank.skills s
        LEFT JOIN tank.agent_skill_submissions p ON p.skill_id=s.id AND p.version=s.version
        WHERE s.state='approved' AND s.present AND s.task_type IS NULL
          AND (p.skill_id IS NULL OR (p.tenant_id=$1 AND p.region=$2))
        """, PLATFORM_TENANT, box_region(),
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


def _screen_mask(value: Any) -> Any:
    """Mask identifiers/email in text without interpreting angle brackets."""
    if isinstance(value, dict):
        return {_screen_mask(k): _screen_mask(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_screen_mask(v) for v in value]
    if not isinstance(value, str):
        return value
    masked = pii_module().detect(value)["text"]
    return re.sub(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", "[EMAIL]", masked, flags=re.I)


async def _screen_cases(conn: Any, task_type: str) -> list[tuple[Any, list[dict[str, str]], dict[str, Any]]]:
    # A global policy must never learn by replaying a client's conversations.
    # Approval and platform ownership are both required; holdouts remain unseen.
    evals = await conn.fetch(
        """SELECT g.input,g.expected FROM tank.gold_examples g
        WHERE g.tenant_id=$1 AND g.region=$2 AND g.status='checked'
          AND g.checked_by IS NOT NULL AND g.checked_at IS NOT NULL
          AND NOT g.holdout AND (NOT g.auto_label OR g.auto_approved)
          AND (g.skill_id=$3 OR EXISTS (SELECT 1 FROM tank.skills s WHERE s.id=g.skill_id AND s.task_type=$3))
        ORDER BY g.created_at DESC,g.id LIMIT 20""",
        PLATFORM_TENANT, box_region(), task_type,
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
        if _contains_html([payload, expected]):
            continue
        try:
            payload, expected = _screen_mask(payload), _screen_mask(expected)
        except ValueError:
            continue
        body = payload if isinstance(payload, dict) else {"text": str(payload)}
        messages = [{"role": "user", "content": json.dumps(body)}]
        cases.append((expected, messages, body))
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
        if _contains_html([messages, expected]):
            continue
        try:
            messages, expected = _screen_mask(messages), _screen_mask(expected)
        except ValueError:
            continue
        if model_call_refusal(json.dumps(messages), name, box=box_region(), tenant_id=str(PLATFORM_TENANT)):
            continue
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
async def graduation(
    tenant_id: uuid.UUID | None = None,
    x_tank_key: str = Header(default=""),
    x_tervory_admin: str = Header(default=""),
) -> list[dict[str, Any]]:
    """Read the ladder. A page load does not promote or roll back.

    Call counts, spend, shadow samples, agreement, and rank costs are this
    tenant's when the request names one. The mix is returned only to a founder.
    """
    import admin as tank_admin

    founder = tank_admin.founder_allowed(x_tank_key, x_tervory_admin)
    # $2 is true only for the founder view with no tenant. A named tenant never mixes.
    founder_mix = founder and tenant_id is None
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.task_type, p.rung, p.model, p.candidate_model, p.shadow_rate, p.previous_model, p.eval_threshold,
                   p.cache_scope, p.priority, p.min_shadow_samples, p.max_reject_rate, p.auto_promote,
                   p.semantic_cache, p.promoted_at,
                   (SELECT count(*) FROM tank.shadow s
                     WHERE s.task_type=p.task_type AND s.candidate_model=p.candidate_model AND s.agreement IS NOT NULL
                       AND (($1::uuid IS NOT NULL AND s.tenant_id = $1) OR $2::bool)) AS n,
                   (SELECT avg(agreement) FROM tank.shadow s
                     WHERE s.task_type=p.task_type AND s.candidate_model=p.candidate_model
                       AND (($1::uuid IS NOT NULL AND s.tenant_id = $1) OR $2::bool)) AS agreement,
                   (SELECT avg(candidate_cost_usd) FROM tank.shadow s
                     WHERE s.task_type=p.task_type AND s.candidate_model=p.candidate_model
                       AND (($1::uuid IS NOT NULL AND s.tenant_id = $1) OR $2::bool)) AS cand_cost,
                   (SELECT avg(primary_cost_usd) FROM tank.shadow s
                     WHERE s.task_type=p.task_type AND s.candidate_model=p.candidate_model
                       AND (($1::uuid IS NOT NULL AND s.tenant_id = $1) OR $2::bool)) AS prim_cost,
                   (SELECT count(*) FROM tank.ledger l
                     WHERE l.task_type=p.task_type AND l.ts > now() - interval '30 days'
                       AND (($1::uuid IS NOT NULL AND l.tenant_id = $1) OR $2::bool)) AS calls_30d,
                   (SELECT coalesce(sum(cost_usd),0) FROM tank.ledger l
                     WHERE l.task_type=p.task_type AND l.ts > now() - interval '30 days'
                       AND (($1::uuid IS NOT NULL AND l.tenant_id = $1) OR $2::bool)) AS cost_30d,
                   (SELECT count(*) FROM tank.ledger l
                     WHERE l.task_type=p.task_type AND l.cache_hit
                       AND (($1::uuid IS NOT NULL AND l.tenant_id = $1) OR $2::bool)) AS cache_hits
            FROM tank.policy p WHERE p.tenant_id IS NULL AND p.task_type <> 'tank.judge'
            ORDER BY cost_30d DESC, p.task_type
            """,
            tenant_id,
            founder_mix,
        )
        ranks = await conn.fetch(
            """
            SELECT * FROM tank.graduation_rank
            WHERE task_type IN (SELECT task_type FROM tank.policy WHERE tenant_id IS NULL)
            """
        )
        notes = await conn.fetch(
            """
            SELECT DISTINCT ON (task_type) task_type, action, from_model, to_model, detail, created_at
            FROM tank.policy_log
            WHERE action IN ('promote', 'rollback') AND created_at > now() - interval '14 days'
              AND task_type IN (SELECT task_type FROM tank.policy WHERE tenant_id IS NULL)
            ORDER BY task_type, created_at DESC
            """
        )
        states = await conn.fetch(
            """
            SELECT * FROM tank.search_state
            WHERE task_type IN (SELECT task_type FROM tank.policy WHERE tenant_id IS NULL)
            """
        )
        code_quotes = await _code_quotes(conn)
    router_steps = await routellm_shadow.ladder(__import__("sys").modules[__name__], tenant_id, founder_mix)
    price_quotes = await _live_price_quotes()
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
        thr = float(d["eval_threshold"] or graduate.DEFAULT_THRESHOLD)
        minimum = int(d["min_shadow_samples"] or graduate.DEFAULT_MIN_SAMPLES)
        prim = _num(d["prim_cost"])
        cand = _num(d["cand_cost"])
        calls = int(d["calls_30d"] or 0)
        ordinary = tenant_id is None and not founder
        if ordinary:
            # No tenant and not a founder: do not return totals mixed across tenants.
            n = 0
            agr = None
            prim = None
            cand = None
            calls = 0
            d["calls_30d"] = 0
            d["cost_30d"] = None
            d["cache_hits"] = 0
            d["saving_pct"] = None
        else:
            d["saving_pct"] = (round((1 - cand / prim) * 100) if prim and prim > 0 and cand is not None else None)
        d["n"] = n
        d["agreement"] = agr
        d["eligible"] = bool(d["candidate_model"]) and n >= minimum and agr is not None and agr >= thr
        d["prim_cost"] = prim
        d["cand_cost"] = cand
        task_ranks = by_rank.get(d["task_type"], [])
        ranked_view = []
        for rank in task_ranks:
            if founder_mix:
                cost = _num(rank["cost_per_call"]) if rank["cost_per_call"] is not None else _num(rank["price_usd"])
                samples = int(rank["shadow_n"] or 0)
                agree = _num(rank["shadow_agreement"])
            else:
                # Rank rows are stored for the platform. A tenant sees only the
                # shadow totals the query already limited to that tenant.
                same = d["candidate_model"] is not None and rank["candidate"] == d["candidate_model"]
                cost = cand if same else None
                samples = n if same else 0
                agree = agr if same else None
            ranked_view.append({
                "name": rank["candidate"],
                "kind": rank["kind"],
                "status": rank["status"],
                "shadow_n": samples,
                "shadow_agreement": agree,
                "cost_per_call": cost,
            })
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
        steps.extend(router_steps.get(d["task_type"], []))
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


@app.post("/v1/graduation/{task_type}/promote",
          dependencies=[Depends(require_key), Depends(__import__("admin").require_admin)])
async def promote(task_type: str, body: PromoteBody) -> dict[str, Any]:
    """Promote only when the shadow bar is cleared. The previous model stays for rollback."""
    move = await _move_task(task_type, by=body.by or "founder", automatic=False)
    if move is None:
        raise HTTPException(status_code=404, detail="no such platform policy")
    if move.action != "promote":
        if move.reason == "no candidate":
            raise HTTPException(status_code=400, detail="no candidate to promote")
        if move.reason == graduate.ROUTER_BLOCK:
            raise HTTPException(status_code=400, detail=move.reason)
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
        if graduate.router_cannot_serve(row["previous_model"]):
            raise HTTPException(status_code=400, detail=graduate.ROUTER_BLOCK)
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
        price_quotes = await _live_price_quotes()
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
        threshold=float(policy["eval_threshold"] or graduate.DEFAULT_THRESHOLD),
        min_samples=int(policy["min_shadow_samples"] or graduate.DEFAULT_MIN_SAMPLES),
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


@app.post("/v1/route", response_model=RouteResponse, response_model_exclude_none=True)
async def route(body: RouteRequest, caller: str | None = Depends(require_key)):
    if caller:
        body = body.model_copy(update={"agent": caller})
    foreign = home_region_refusal(call_home(body.home_region, box_region()), box_region())
    if foreign:
        raise HTTPException(403, foreign)
    if "#moa." in body.task_type:
        raise HTTPException(403, "Submit the original task; MoA seats are internal")
    row = await load_policy(body.task_type, body.tenant_id)
    if not row.get("moa_enabled") or int(row.get("rung", 1)) in {3, 4} or graduate.is_skill(row.get("model")):
        return await run_route(body, caller=caller)
    return await __import__("moa").routed_request(
        body, caller, row=row, complex_request=body.complex_request, interactive=body.interactive
    )


# ---------- provider batches (independent of the task queue worker) ----------

class _DeferredRoute(Exception):
    def __init__(self, req, policy, messages, max_tokens, generation, escalation, cache_snapshot=None):
        self.req, self.policy = req, policy
        self.messages, self.max_tokens = messages, max_tokens
        self.generation, self.escalation = generation, escalation
        self.cache_snapshot = cache_snapshot


class BatchRequest(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    requests: list[RouteRequest] = Field(min_length=1, max_length=1000)


def _batch_min() -> int:
    return max(1, int(os.environ.get("TANK_BATCH_MIN", "50")))


async def _batch_price(model: str) -> dict[str, Any]:
    row = next((r for r in await _roster_models() if r["model_name"] == model), None)
    if not row:
        raise HTTPException(409, "No price for the selected model")
    info = row["model_info"]
    if info.get("input_cost_per_token") is None or info.get("output_cost_per_token") is None:
        raise HTTPException(409, "No price for the selected model")
    native = row["litellm_params"]["model"]
    provider, _, name = native.partition("/")
    return {"input": float(info["input_cost_per_token"]), "output": float(info["output_cost_per_token"]),
            "provider": provider, "native": name,
            "discount": batch_providers.charge_multiplier(provider, name) or 1.0}


def _call_upper(messages: list[dict[str, str]], max_tokens: int, prices: dict[str, Any]) -> float:
    # UTF-8 bytes bound BPE tokens; reserve additional framing tokens. No provider
    # fallback in a capped retry, since a different model has a different price.
    tokens = len(json.dumps(messages, ensure_ascii=False).encode()) + 1024
    return tokens * prices["input"] + max_tokens * prices["output"]


async def _batch_gateway(method: str, path: str, *, model: str | None = None, **kwargs) -> httpx.Response:
    await __import__("controls").refuse_paid(path="route/batch")
    async with httpx.AsyncClient(timeout=60) as client:
        headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"}
        if path.startswith("/anthropic/"):
            headers["anthropic-version"] = "2023-06-01"
        if model:
            headers["x-litellm-model"] = model
        response = await client.request(method, f"{LITELLM_URL}{path}", headers=headers, **kwargs)
    response.raise_for_status()
    return response


@app.post("/v1/route/batch")
async def route_batch(body: BatchRequest, caller: str | None = Depends(require_key)) -> dict[str, Any]:
    tenant = body.requests[0].tenant_id
    task = body.requests[0].task_type
    if any(r.tenant_id != tenant or r.task_type != task for r in body.requests):
        raise HTTPException(422, "A batch has one tenant and one task type")
    if "#moa." in task or override_allowed(task):
        raise HTTPException(422, "This task requires the foreground route")
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode="json", exclude={"id"}), sort_keys=True).encode()).hexdigest()
    async with pool().acquire() as conn:
        existing = await conn.fetchrow("SELECT id,request_hash FROM tank.batches WHERE id=$1 AND tenant_id=$2", body.id, tenant)
    if existing:
        if existing["request_hash"] != fingerprint:
            raise HTTPException(409, "Batch id already has different requests")
        return await batch_status(body.id, tenant)
    policy = await load_policy(task, tenant)
    eligible = bool(policy.get("batch_eligible")) and not policy.get("moa_enabled")
    eligible = eligible and len(body.requests) >= _batch_min() and not any(r.interactive for r in body.requests)
    local, deferred = [], []
    for position, req in enumerate(body.requests):
        if caller:
            req = req.model_copy(update={"agent": caller})
        try:
            result = await run_route(req, caller=caller, _defer_paid=eligible,
                                     _paid_limit=float(policy["max_cost_usd"]))
            local.append({**result.model_dump(mode="json"), "position": position, "item_id": str(uuid.uuid5(body.id, str(position)))})
        except _DeferredRoute as item:
            item.position = position
            deferred.append(item)
    if not deferred:
        return {"id": str(body.id), "status": "completed", "results": local, "batch": False}
    # Free/code/cache results have already finished. Only work still needing a
    # model is submitted; no interactive request enters this durable queue.
    prices = await _batch_price(deferred[0].policy["model"])
    if not all(batch_providers.compatible(prices, item.messages, item.generation) for item in deferred):
        for item in deferred:
            result = await run_route(item.req, caller=caller, _paid_policy=item.policy,
                                     _prior_escalation=item.escalation, _paid_limit=float(item.policy["max_cost_usd"]))
            local.append({**result.model_dump(mode="json"), "position": item.position, "item_id": str(uuid.uuid5(body.id, str(item.position)))})
        return {"id": str(body.id), "status": "completed", "results": local, "batch": False}
    reservations = [_call_upper(d.messages, d.max_tokens, prices) * prices["discount"] for d in deferred]
    if any(cost > float(item.policy["max_cost_usd"]) for item, cost in zip(deferred, reservations)):
        raise HTTPException(409, "Task cost cap prevents this batch")
    async with pool().acquire() as conn:
        async with conn.transaction():
            inserted = await conn.fetchval(
                """INSERT INTO tank.batches(id,tenant_id,region,task_type,model,count,provider,estimated_cost_usd,caller,request_hash)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT DO NOTHING RETURNING id""",
                body.id, tenant, box_region(), task, deferred[0].policy["model"], len(body.requests), prices["provider"], sum(reservations), caller, fingerprint,
            )
            if inserted:
                for item, reservation in zip(deferred, reservations):
                    snapshot = {"routing": item.policy, "messages": item.messages, "max_tokens": item.max_tokens,
                                "generation": item.generation, "escalation": item.escalation,
                                "semantic_cache": item.cache_snapshot}
                    clean_req = item.req.model_copy(update={"messages": [Message(**m) for m in _plain_messages([m.model_dump() for m in item.req.messages])]})
                    await conn.execute(
                        """INSERT INTO tank.batch_items(batch_id,tenant_id,item_id,request,policy,prices,reserved_usd,position)
                        VALUES($1,$2,$3,$4::jsonb,$5::jsonb,$6::jsonb,$7,$8)""",
                        body.id, tenant, uuid.uuid5(body.id, str(item.position)), clean_req.model_dump_json(), json.dumps(snapshot, default=str), json.dumps(prices), reservation, item.position,
                    )
                for result in local:
                    await conn.execute("""INSERT INTO tank.batch_items(batch_id,tenant_id,item_id,request,policy,prices,status,ledger_id,position)
                        VALUES($1,$2,$3,'{}','{}','{}','completed',$4,$5)""",
                        body.id, tenant, uuid.UUID(result["item_id"]), uuid.UUID(result["ledger_id"]), result["position"])
                    await conn.execute("UPDATE tank.ledger SET batch=true,batch_id=$3,batch_baseline_cost_usd=0,batch_discount_usd=0 WHERE id=$1 AND tenant_id=$2",
                        uuid.UUID(result["ledger_id"]), tenant, body.id)
            else:
                winner = await conn.fetchrow("SELECT request_hash FROM tank.batches WHERE id=$1 AND tenant_id=$2", body.id, tenant)
                if winner is None or winner["request_hash"] != fingerprint:
                    raise HTTPException(409, "Batch id is unavailable or has different requests")
    result = await batch_status(body.id, tenant)
    return result


@app.get("/v1/route/batch/{batch_id}", dependencies=[Depends(require_key)])
async def batch_status(batch_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, Any]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tank.batches WHERE id=$1 AND tenant_id=$2 AND region=$3", batch_id, tenant_id, box_region())
        if row is None:
            raise HTTPException(404, "No batch for this tenant")
        items = await conn.fetch(
            """SELECT i.item_id,i.position,i.status,i.error,l.id AS ledger_id,l.model,l.rung,l.cost_usd,
            coalesce(l.batch_baseline_cost_usd,l.baseline_cost_usd) AS baseline_cost_usd,
            l.tokens_in,l.tokens_out,l.latency_ms,l.batch,l.escalation,t.content
            FROM tank.batch_items i LEFT JOIN tank.ledger l ON l.id=i.ledger_id AND l.tenant_id=i.tenant_id
            LEFT JOIN tank.transcripts t ON t.ledger_id=l.id AND t.tenant_id=i.tenant_id
            WHERE i.batch_id=$1 AND i.tenant_id=$2 ORDER BY i.position""", batch_id, tenant_id,
        )
    results = []
    for item in items:
        value = dict(item)
        baseline, actual = value.get("baseline_cost_usd"), value.get("cost_usd")
        value["discount_usd"] = float(baseline - actual) if baseline is not None and actual is not None else None
        results.append(value)
    return {**dict(row), "completion_window": "24h", "results": results}


def _batch_obj(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


async def _batch_fallback(conn: Any, batch: Any, item: Any) -> None:
    """Claim exactly one normal retry. Unknown/in-flight submissions are never retried."""
    claimed = await conn.fetchval(
        """UPDATE tank.batch_items SET attempts=1,status='retrying' WHERE batch_id=$1 AND tenant_id=$2
        AND item_id=$3 AND attempts=0 AND ledger_id IS NULL RETURNING item_id""",
        batch["id"], batch["tenant_id"], item["item_id"],
    )
    if not claimed:
        return
    snapshot = _batch_obj(item["policy"])
    req = RouteRequest.model_validate(_batch_obj(item["request"]))
    remaining = float(snapshot["routing"]["max_cost_usd"]) - float(item["reserved_usd"])
    try:
        current = await load_policy(req.task_type, req.tenant_id)
        if str(current["updated_at"]) != str(snapshot["routing"]["updated_at"]):
            raise HTTPException(409, "Policy changed before retry")
        remaining = min(remaining, float(current["max_cost_usd"])-float(item["reserved_usd"]))
        result = await run_route(req, caller=batch["caller"], _paid_policy=snapshot["routing"],
                                 _prior_escalation=snapshot["escalation"], _paid_limit=remaining)
        await conn.execute("""UPDATE tank.ledger SET batch=true,batch_id=$3,
            batch_baseline_cost_usd=cost_usd,batch_discount_usd=0 WHERE id=$1 AND tenant_id=$2""",
            result.ledger_id, req.tenant_id, batch["id"])
        await conn.execute("""UPDATE tank.batch_items SET status='completed',ledger_id=$4
            WHERE batch_id=$1 AND tenant_id=$2 AND item_id=$3""", batch["id"], req.tenant_id, item["item_id"], result.ledger_id)
    except Exception as exc:
        # Errors are operational codes, never echoed provider/client text.
        reason = "cost_cap" if isinstance(exc, HTTPException) and exc.status_code == 409 else "normal_retry_failed"
        receipt = exc.detail.get("ledger_id") if isinstance(exc, HTTPException) and isinstance(exc.detail, dict) else None
        ledger_id = uuid.UUID(str(receipt)) if receipt else None
        if ledger_id:
            await conn.execute("""UPDATE tank.ledger SET batch=true,batch_id=$3,
                batch_baseline_cost_usd=cost_usd,batch_discount_usd=0 WHERE id=$1 AND tenant_id=$2""",
                ledger_id, req.tenant_id, batch["id"])
        await conn.execute("""UPDATE tank.batch_items SET status='failed',error=$4,ledger_id=$5
            WHERE batch_id=$1 AND tenant_id=$2 AND item_id=$3""", batch["id"], req.tenant_id, item["item_id"], reason, ledger_id)


async def _batch_result(conn: Any, batch: Any, item: Any, result: dict[str, Any]) -> None:
    response = result.get("response") or {}
    data = response.get("body") or {}
    if response.get("status_code") != 200 or not isinstance(data, dict):
        await _batch_fallback(conn, batch, item)
        return
    content, finish = _choice_answer(data)
    if not content:
        await _batch_fallback(conn, batch, item)
        return
    usage = data.get("usage") or {}
    tokens_in, tokens_out = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    prices, snapshot = _batch_obj(item["prices"]), _batch_obj(item["policy"])
    baseline = Decimal(tokens_in)*Decimal(str(prices["input"])) + Decimal(tokens_out)*Decimal(str(prices["output"]))
    actual = baseline*Decimal(str(prices["discount"]))
    req = RouteRequest.model_validate(_batch_obj(item["request"]))
    ledger_id = uuid.uuid4()
    async with conn.transaction():
        # Item lock plus unique ledger assignment makes repeated provider polls idempotent.
        locked = await conn.fetchrow("SELECT ledger_id,status FROM tank.batch_items WHERE batch_id=$1 AND tenant_id=$2 AND item_id=$3 FOR UPDATE", batch["id"], req.tenant_id, item["item_id"])
        if locked["ledger_id"] is not None or locked["status"] in {"failed", "retrying"}:
            return
        await conn.execute(
            """INSERT INTO tank.ledger(id,tenant_id,region,agent,skill,task_type,rung,model,priority,
            tokens_in,tokens_out,cost_usd,latency_ms,outcome,batch,batch_id,baseline_model,baseline_cost_usd,
            baseline_status,escalation,accept_after,batch_baseline_cost_usd,batch_discount_usd)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,'batch',$9,$10,$11,0,'delivered',true,$12,$8,$13,'measured',$14::jsonb,
                   now()+make_interval(secs=>$15),$13,$13::numeric-$11::numeric)""",
            ledger_id, req.tenant_id, box_region(), req.agent, req.skill, req.task_type,
            snapshot["routing"]["rung"], batch["model"], tokens_in, tokens_out, actual,
            batch["id"], baseline, json.dumps(snapshot["escalation"]), int(snapshot["routing"]["acceptance_window_s"]),
        )
        await conn.execute("""INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content)
            VALUES($1,$2,$3,$4::jsonb,$5)""", ledger_id, req.tenant_id, req.task_type,
            json.dumps(_storage_mask(_plain_messages([m.model_dump() for m in req.messages]))), _storage_mask(content)[:20000])
        await conn.execute("""UPDATE tank.batch_items SET status='completed',ledger_id=$4,reserved_usd=$5
            WHERE batch_id=$1 AND tenant_id=$2 AND item_id=$3""", batch["id"], req.tenant_id, item["item_id"], ledger_id, actual)
    semantic_cache.schedule_batch(__import__("sys").modules[__name__], req, snapshot, ledger_id, content, float(actual))


async def _process_batch(conn: Any, batch: Any) -> None:
    items = await conn.fetch("SELECT * FROM tank.batch_items WHERE batch_id=$1 AND tenant_id=$2 ORDER BY item_id", batch["id"], batch["tenant_id"])
    if batch["status"] == "queued":
        # Lock holder marks the submission boundary before contacting a provider.
        # A crash here is visibly uncertain; it must not silently buy the work twice.
        await conn.execute("UPDATE tank.batches SET status='submitting',submitted_at=now() WHERE id=$1 AND tenant_id=$2", batch["id"], batch["tenant_id"])
        lines = []
        for item in items:
            if item["ledger_id"] is not None:
                continue
            snapshot, prices = _batch_obj(item["policy"]), _batch_obj(item["prices"])
            req = RouteRequest.model_validate(_batch_obj(item["request"]))
            current = await load_policy(req.task_type, req.tenant_id)
            if str(current["updated_at"]) != str(snapshot["routing"]["updated_at"]):
                raise ValueError("policy_changed")
            blocked = model_call_refusal(json.dumps(snapshot["messages"]), batch["model"], box=box_region(), tenant_id=str(req.tenant_id))
            if blocked:
                raise ValueError("provider_not_allowed")
            lines.append(json.dumps({"custom_id": str(item["item_id"]), "method": "POST", "url": "/v1/chat/completions",
                "body": {"model": prices["native"], "messages": snapshot["messages"], "max_tokens": snapshot["max_tokens"], **snapshot["generation"]}}))
        provider_id, file_id = await batch_providers.submit(_batch_gateway, batch, lines)
        await conn.execute("""UPDATE tank.batches SET status='submitted',provider_id=$3,input_file_id=$4
            WHERE id=$1 AND tenant_id=$2""", batch["id"], batch["tenant_id"], provider_id, file_id)
        return
    if batch["status"] in {"submitting", "retrying"}:
        # Only a restarted process can see these states while holding the batch
        # advisory lock. Surface uncertainty, and never repeat a submitted call.
        await conn.execute("UPDATE tank.batch_items SET status='failed',error='interrupted_attempt' WHERE batch_id=$1 AND tenant_id=$2 AND ledger_id IS NULL", batch["id"], batch["tenant_id"])
    else:
        state = await batch_providers.status(_batch_gateway, batch)
        if state["status"] not in {"completed", "failed", "expired", "cancelled"}:
            if (datetime.now(timezone.utc)-batch["submitted_at"]).total_seconds() >= 86400:
                if batch["error"] != "24h deadline exceeded; awaiting provider cancellation":
                    await batch_providers.cancel(_batch_gateway, batch)
                    await conn.execute("UPDATE tank.batches SET error='24h deadline exceeded; awaiting provider cancellation' WHERE id=$1 AND tenant_id=$2", batch["id"], batch["tenant_id"])
            return
        outputs = {}
        if state.get("output_file_id"):
            outputs = await batch_providers.results(_batch_gateway, batch, state["output_file_id"])
        await conn.execute("UPDATE tank.batches SET status='retrying' WHERE id=$1 AND tenant_id=$2", batch["id"], batch["tenant_id"])
        for item in items:
            if item["ledger_id"] is not None or item["status"] == "failed":
                continue
            result = outputs.get(str(item["item_id"]))
            if result:
                await _batch_result(conn, batch, item, result)
            else:
                await _batch_fallback(conn, batch, item)
    await conn.execute(
        """UPDATE tank.batches b SET finished_at=now(),
        status=CASE WHEN EXISTS(SELECT 1 FROM tank.batch_items i WHERE i.batch_id=b.id AND i.tenant_id=b.tenant_id AND i.status='failed')
          THEN 'failed' ELSE 'completed' END,
        actual_cost_usd=(SELECT coalesce(sum(l.cost_usd),0) FROM tank.batch_items i JOIN tank.ledger l ON l.id=i.ledger_id AND l.tenant_id=i.tenant_id WHERE i.batch_id=b.id AND i.tenant_id=b.tenant_id),
        error=CASE WHEN EXISTS(SELECT 1 FROM tank.batch_items i WHERE i.batch_id=b.id AND i.tenant_id=b.tenant_id AND i.status='failed') THEN 'Some items failed; see item errors' ELSE NULL END
        WHERE b.id=$1 AND b.tenant_id=$2""", batch["id"], batch["tenant_id"],
    )


async def process_batches_once() -> None:
    async with pool().acquire() as conn:
        rows = await conn.fetch("SELECT id,tenant_id FROM tank.batches WHERE region=$1 AND status IN ('queued','submitting','submitted','retrying') ORDER BY created_at LIMIT 20", box_region())
        for row in rows:
            lock = int.from_bytes(row["id"].bytes[:8], "big", signed=True)
            if not await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock):
                continue
            try:
                batch = await conn.fetchrow("SELECT * FROM tank.batches WHERE id=$1 AND tenant_id=$2", row["id"], row["tenant_id"])
                if batch["status"] not in {"queued", "submitting", "submitted", "retrying"}:
                    continue
                await _process_batch(conn, batch)
            except (httpx.HTTPError, ValueError, KeyError):
                # Poll failures are retriable; submission ambiguity is surfaced
                # on the next pass, with no second provider submission.
                await conn.execute("UPDATE tank.batches SET error='Provider operation interrupted; retrying status check' WHERE id=$1 AND tenant_id=$2", row["id"], row["tenant_id"])
            finally:
                await conn.execute("SELECT pg_advisory_unlock($1)", lock)


async def _batch_loop() -> None:
    while True:
        try:
            await process_batches_once()
        except Exception:
            log.warning("Batch maintenance failed; retrying")
        await asyncio.sleep(10)


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
    early = model_call_refusal(
        text, None, box=box, tenant_id=str(body.tenant_id), task_type=body.task_type
    )
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
PLATFORM_TENANT = skala.PLATFORM_TENANT


class VendorCall(BaseModel):
    model_config = {"extra": "forbid"}
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = PLATFORM_TENANT
    agent: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    task_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,119}$")
    vendor: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,79}$")
    units: Decimal = Field(gt=0, le=1000, max_digits=18, decimal_places=6)
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=6)
    outcome: Literal["delivered", "failed", "unverified"]
    region: Literal["us-east", "za"]


@app.post("/v1/ledger/vendor")
async def vendor_ledger(body: VendorCall, agent: str | None = Depends(require_key)) -> dict[str, Any]:
    if agent is None or agent == HOMES_PRINCIPAL or agent != body.agent:
        raise HTTPException(status_code=403, detail="an agent may record only its own vendor calls")
    if not body.task_type.startswith(f"{agent}."):
        raise HTTPException(status_code=403, detail="task type must belong to the calling agent")
    if body.tenant_id != PLATFORM_TENANT:
        raise HTTPException(status_code=403, detail="vendor calls belong to the platform tenant")
    if body.region != box_region():
        raise HTTPException(status_code=403, detail="vendor call region must match this Tank")
    if body.cost_usd != 0:
        raise HTTPException(status_code=422, detail="credit calls must have zero dollar cost")
    async with pool().acquire() as conn:
        inserted = await conn.fetchval(
            """
            INSERT INTO tank.ledger
                (id, tenant_id, region, agent, task_type, model, vendor, units, cost_usd, outcome, rung)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,1)
            ON CONFLICT (id) DO NOTHING RETURNING id
            """,
            body.id, PLATFORM_TENANT, body.region, agent, body.task_type,
            f"vendor:{body.vendor}", body.vendor, body.units, body.cost_usd, body.outcome,
        )
        if inserted is None:
            same = await conn.fetchval(
                """
                SELECT 1 FROM tank.ledger WHERE id=$1 AND tenant_id=$2 AND region=$3
                  AND agent=$4 AND task_type=$5 AND vendor=$6
                  AND units IS NOT DISTINCT FROM $7::numeric AND cost_usd=$8 AND outcome=$9
                """,
                body.id, PLATFORM_TENANT, body.region, agent, body.task_type,
                body.vendor, body.units, body.cost_usd, body.outcome,
            )
            if same != 1:
                raise HTTPException(status_code=409, detail="vendor call id already used")
    return {"ledger_id": str(body.id), "recorded": True}


@app.get("/v1/skala", dependencies=[Depends(require_key)])
async def list_skills(
    tenant_id: uuid.UUID | None = None,
    all_tenants: bool = False,
    x_tank_key: str = Header(default=""),
    x_tervory_admin: str = Header(default=""),
) -> list[dict[str, Any]]:
    """Public packages and this tenant's submissions; all submissions require founder identity."""
    if all_tenants:
        await __import__("admin").require_admin(x_tank_key, x_tervory_admin)
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT s.* FROM tank.skills s
            LEFT JOIN tank.agent_skill_submissions p ON p.skill_id=s.id AND p.version=s.version
            WHERE p.skill_id IS NULL OR (p.tenant_id=$1 AND p.region=$2) OR $3
            ORDER BY s.agent,s.id,s.version""", tenant_id, box_region(), all_tenants,
        )
        if tenant_id is None:
            costs = await skill_costs.fetch_call_costs(conn, PLATFORM_TENANT, box_region())
        else:
            costs = await skill_costs.fetch_call_costs(conn, tenant_id, box_region())
    return skill_costs.attach_call_costs([dict(r) for r in rows], costs)


class EvalRun(BaseModel):
    by: str | None = None


async def run_room_eval(pkg: skala.SkillPackage, payload: dict[str, Any], ctx: skala.SkillContext) -> dict[str, Any]:
    key = os.environ.get("TANK_KEY_TISAN", "")
    if pkg.id not in {"tisan.figma", "tisan.scaffold"} or not key or _http is None:
        raise RuntimeError("eval room is unavailable")
    response = await _http.post(
        "http://agent-tisan:8000/evals/run",
        headers={"X-Tank-Key": key},
        json={"skill_id": pkg.id, "version": pkg.version, "tenant_id": str(ctx.tenant_id), "input": payload},
        timeout=660,
        follow_redirects=False,
    )
    if response.status_code != 200:
        raise RuntimeError("eval room refused the case")
    result = response.json()
    if not isinstance(result, dict):
        raise RuntimeError("invalid eval room result")
    return result


@app.post("/v1/skala/{skill_id}/{version}/evals", dependencies=[Depends(require_key)])
async def run_skill_evals(skill_id: str, version: str, body: EvalRun | None = None) -> dict[str, Any]:
    pkg = get_package(skill_id, version)
    if not pkg.cases:
        raise HTTPException(status_code=400, detail="package has no eval cases; a skill without evals cannot leave candidate")
    here = box_region()
    result = await skala.run_evals(
        pkg, lambda: __import__("skala_revalidation").eval_context(
            __import__("sys").modules[__name__], pkg,
            make_ctx(pkg, PLATFORM_TENANT, preview=True, home_region=here)),
        execute=run_room_eval if pkg.id in {"tisan.figma", "tisan.scaffold"} else None,
    )
    if __import__("skala_revalidation").ACTIVE.get() is not None:
        return await __import__("skala_revalidation").record(
            __import__("sys").modules[__name__], result, body.by if body else None)
    passed_gate = result["score"] >= pkg.eval_threshold and result["eligible"]
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
        elif state == "approved" and not passed_gate:
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
    confirmed: bool = False
    review_token: str | None = None
    token: str | None = None


@app.post("/v1/skala/approvals/preview", dependencies=[Depends(require_key)])
async def preview_skill_approvals(body: Approval) -> dict[str, Any]:
    return await skala.bulk_preview(pool(), _packages, body.by, region=box_region())


@app.post("/v1/skala/approvals/confirm", dependencies=[Depends(require_key)])
async def confirm_skill_approvals(body: Approval) -> dict[str, Any]:
    return await skala.bulk_confirm(pool(), _packages, body.by, body.token or "", body.confirmed, region=box_region())


@app.get("/v1/skala/approvals/status", dependencies=[Depends(require_key)])
async def skill_approval_status() -> list[dict[str, Any]]:
    async with pool().acquire() as conn:
        return [await skala.review_evidence(conn, pkg, region=box_region()) for pkg in _packages.values()]


@app.post("/v1/skala/{skill_id}/{version}/source-review", dependencies=[Depends(require_key)])
async def review_skill_source(skill_id: str, version: str, body: Approval) -> dict[str, Any]:
    return await skala.source_review(pool(), get_package(skill_id, version), body.by)


@app.post("/v1/skala/{skill_id}/{version}/approve", dependencies=[Depends(require_key)])
async def approve_skill(skill_id: str, version: str, body: Approval) -> dict[str, Any]:
    return await skala.change_version(pool(), get_package(skill_id, version), body.by, "approve",
                                     region=box_region(), confirmed=body.confirmed, review_token=body.review_token)


@app.post("/v1/skala/{skill_id}/{version}/rollback", dependencies=[Depends(require_key)])
async def rollback_skill(skill_id: str, version: str, body: Approval) -> dict[str, Any]:
    return await skala.change_version(pool(), get_package(skill_id, version), body.by, "rollback",
                                     region=box_region(), confirmed=body.confirmed)


@app.post("/v1/skala/{skill_id}/{version}/retire", dependencies=[Depends(require_key)])
async def retire_skill(skill_id: str, version: str, body: Approval) -> dict[str, Any]:
    return await skala.retire_version(pool(), skill_id, version, body.by)


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


@app.get("/v1/skala/{skill_id}/run", dependencies=[Depends(require_key)])
async def describe_skill(skill_id: str, preview: bool = False) -> dict[str, Any]:
    """Which version Base should pin, and which engines exist. Does not run the skill."""
    version = await _pick_version(skill_id, preview)
    pkg = get_package(skill_id, version)
    return {"skill": skill_id, "version": version, "ref": pkg.ref, "engines": known_engines()}


@app.post("/v1/skala/{skill_id}/run")
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
    __import__("skala_intake").guard_preview(skill_id, caller, body.preview)
    version = body.version or await _pick_version(skill_id, body.preview)
    pkg = get_package(skill_id, version)
    await __import__("agent_skills").guard_submission_owner(
        __import__("sys").modules[__name__], pkg, body.tenant_id,
    )
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
    if caller == "base":
        await __import__("agent_skills").guard_base_run(__import__("sys").modules[__name__], pkg, body, ctx)
    request = RouteRequest(tenant_id=body.tenant_id, agent=caller or pkg.agent,
                           task_type=pkg.task_type or pkg.id, skill=pkg.ref,
                           messages=[Message(role="user", content=json.dumps(body.input))])
    try:
        receipt_policy = await load_policy(request.task_type, body.tenant_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        receipt_policy = {"priority": "standard", "acceptance_window_s": 86400}
    await _preflight_mask(request, receipt_policy, [m.model_dump() for m in request.messages], ctx.task_id)
    try:
        out = await skala.run_skill(pkg, body.input, ctx)
    except Exception:
        if pkg.task_type is None and not ctx.calls and not ctx.cost_usd:
            await _record_local(request, receipt_policy, model="skill:"+pkg.ref, rung=3,
                                content="", outcome="failed", error="skill_error", task_id=ctx.task_id)
        raise
    if not ctx.calls and not ctx.cost_usd:
        receipt = await _record_local(request, receipt_policy, model="skill:"+pkg.ref, rung=3,
                                      content=json.dumps(out), outcome="unverified" if body.preview else "delivered", task_id=ctx.task_id)
        out["_ledger_id"] = str(receipt.ledger_id)
        out["_receipt"] = receipt.model_dump(mode="json")
    out["_cost_usd"] = round(ctx.cost_usd, 6)
    return out


# ---------- Base: the room owns the worker; Tank only proxies ----------

BASE_AGENT_URL = os.environ.get("BASE_AGENT_URL", "http://agent-base:8000")
_BASE_ROUTES = {"run", "retry", "rerun", "batches", "engines", "records"}


@app.post("/v1/base/context-dev/trial", dependencies=[Depends(__import__("admin").require_admin)])
async def base_context_trial() -> Response:
    key = os.environ.get("TANK_KEY_BASE", "")
    if _http is None or not key:
        raise HTTPException(status_code=503, detail="Base trial is unavailable")
    try:
        response = await _http.post(
            BASE_AGENT_URL.rstrip("/") + "/context-dev/trial",
            json={"tenant_id": str(PLATFORM_TENANT)},
            headers={"X-Tank-Key": key},
            timeout=3600, follow_redirects=False,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Trial interrupted; refresh results before trying again") from None
    return Response(content=response.content, status_code=response.status_code, media_type="application/json")


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


# ---------- Zenas: the room on this server only ----------

_LOCAL_ZENAS_HOSTS = frozenset({"agent-zenas", "localhost", "127.0.0.1"})
_ZENAS_PATH = re.compile(
    r"^(consents|matters|pool|pool/status|health|review|selftest|review-switch|cases/convert|rule-cards|worked|matches|training-pairs|drafts|tenants|answers|moot/fixtures|moot/published)$"
    r"|^(matters|documents|rule-cards|worked)/[0-9a-fA-F-]{36}$"
    r"|^matters/[0-9a-fA-F-]{36}/documents$"
    r"|^matters/[0-9a-fA-F-]{36}/release$"
    r"|^documents/[0-9a-fA-F-]{36}/reviews$"
    r"|^pool/sources/[A-Za-z0-9._-]{1,80}/load$"
    r"|^moot/problems/[A-Za-z0-9._-]{1,80}/counsel/(appellant|respondent)$"
    r"|^moot/problems/[A-Za-z0-9._-]{1,80}/(edit|lock)$"
    r"|^regulations/(watches|changes)$"
    r"|^regulations/watches/[0-9a-fA-F-]{36}$"
    r"|^moot/matches/ai-ai$"
    r"|^moot/matches/student$"
    r"|^moot/matches/[0-9a-fA-F-]{36}/publish$"
)


def zenas_box_region() -> str:
    """Region for /v1/zenas/*. Unset or unknown is refused. There is no us-east default.

    Other Tank routes still use box_region(), which follows the Boston compose
    default. Zenas does not.
    """
    raw = os.environ.get("TANK_REGION", "").strip().lower()
    if raw not in (US_REGION, ZA_REGION):
        raise HTTPException(status_code=409, detail="TANK_REGION must be us-east or za")
    return raw


def zenas_upstream(path: str) -> str:
    """URL of a Zenas route on this server. Any other host is refused."""
    cleaned = (path or "").strip().strip("/")
    if not _ZENAS_PATH.fullmatch(cleaned):
        raise HTTPException(status_code=404, detail="no such zenas route")
    raw = os.environ.get("ZENAS_AGENT_URL", "http://agent-zenas:8000").strip()
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in _LOCAL_ZENAS_HOSTS or parsed.username:
        raise HTTPException(status_code=403, detail="Zenas stays in this region")
    return raw.rstrip("/") + "/" + cleaned


# A load detail is one short operational line. A judgment does not belong in it.
_DETAIL_LIMIT = 240
_URL = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_SK_SECRET = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
# Same marks the pool refuses to fetch. An env var name such as
# COURTLISTENER_API_TOKEN has no '=' and stays.
_KEYED_URL_MARKS = ("api_key=", "token=", "password=", "secret=", "?key=", "&key=")


def _scrub_public_text(text: str) -> str:
    """Remove keyed URLs and sk- secrets. Other words stay."""

    def drop_url(match: re.Match[str]) -> str:
        url = match.group(0)
        lowered = url.lower()
        if any(mark in lowered for mark in _KEYED_URL_MARKS):
            return ""
        return url

    cleaned = _SK_SECRET.sub("", _URL.sub(drop_url, text))
    if cleaned == text:
        return text
    return " ".join(cleaned.split())


def public_feed(value: Any) -> Any:
    """Drop key material from a pool status payload. key_name and key_set stay.

    Each source's last_status and a short detail stay, so the feeds page can
    show why a load failed. A URL that carries a key does not.
    """
    if isinstance(value, list):
        return [public_feed(item) for item in value]
    if isinstance(value, str):
        return _scrub_public_text(value)
    if not isinstance(value, dict):
        return value
    kept: dict[str, Any] = {}
    for key, item in value.items():
        lowered = str(key).lower()
        if lowered not in {"key_name", "key_set"} and "key" in lowered:
            continue
        if any(part in lowered for part in ("secret", "password", "token")):
            continue
        if lowered == "detail":
            text = item if isinstance(item, str) else ""
            kept[key] = _scrub_public_text(text)[:_DETAIL_LIMIT]
            continue
        if lowered == "last_status":
            kept[key] = _scrub_public_text(item) if isinstance(item, str) else item
            continue
        kept[key] = public_feed(item)
    return kept


def _pool_report(path: str) -> bool:
    """Pool status and a single-source load both return source rows. Strip keys from either."""
    return path in {"pool", "pool/status"} or (path.startswith("pool/sources/") and path.endswith("/load"))


def annotate_key_set(payload: Any) -> Any:
    """Say whether a named key is set. Never copy the value."""
    if not isinstance(payload, dict):
        return payload
    sources = payload.get("sources")
    if not isinstance(sources, list):
        return payload
    for row in sources:
        if not isinstance(row, dict):
            continue
        name = row.get("key_name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,80}", name):
            row["key_name"] = "none"
            continue
        row["key_set"] = bool(os.environ.get(name, "").strip())
    return payload


def _request_home(raw: bytes, query_home: str | None) -> str | None:
    """The home on this request. An explicit empty value stays empty.

    TODO(Thread C): cross-check this against the tenant record's home.
    That column is yours; do not add it here. Do not fill a missing value in.
    """
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict) and "home_region" in parsed:
            value = parsed.get("home_region")
            if value is None:
                return ""
            return str(value)
    return query_home


ZENAS_TIMEOUT = 60.0
ZENAS_LOAD_TIMEOUT_DEFAULT = 900.0


def zenas_timeout(path: str) -> float:
    """Seconds Tank waits for the Zenas room.

    A source load (pool/sources/{id}/load) can run for minutes (the
    Constitutional Court waits between calls), so it gets ZENAS_LOAD_TIMEOUT
    (default 900). Every other call keeps 60 seconds.
    """
    parts = path.strip().strip("/").split("/")
    if len(parts) == 4 and parts[0] == "pool" and parts[1] == "sources" and parts[3] == "load":
        raw = os.environ.get("ZENAS_LOAD_TIMEOUT", "").strip()
        try:
            value = float(raw) if raw else ZENAS_LOAD_TIMEOUT_DEFAULT
        except ValueError:
            value = ZENAS_LOAD_TIMEOUT_DEFAULT
        return value if value > 0 else ZENAS_LOAD_TIMEOUT_DEFAULT
    return ZENAS_TIMEOUT


@app.api_route("/v1/zenas/{path:path}", methods=["GET", "POST"], dependencies=[Depends(require_key)])
async def zenas_proxy(path: str, request: Request) -> Response:
    """Forward /v1/zenas/* to the Zenas room on this server only.

    A missing, empty, unknown or foreign home is refused before the room is
    called, and nothing is stored here. The room URL is not taken from the request.
    """
    raw = await request.body()
    box = zenas_box_region()
    foreign = home_region_refusal(_request_home(raw, request.query_params.get("home_region")), box)
    if foreign:
        raise HTTPException(status_code=403, detail=foreign)
    target = zenas_upstream(path)
    if _http is None:
        raise HTTPException(status_code=503, detail="Zenas room is unreachable")
    headers: dict[str, str] = {}
    if path.startswith("regulations/"):
        headers["X-Tank-Key"] = os.environ.get("TANK_KEY_ZENAS", "")
    content_type = request.headers.get("content-type")
    if content_type:
        headers["content-type"] = content_type
    try:
        resp = await _http.request(
            request.method,
            target,
            content=raw if raw else None,
            params=list(request.query_params.multi_items()),
            headers=headers,
            timeout=zenas_timeout(path),
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Zenas room is unreachable") from None
    content = resp.content
    media = resp.headers.get("content-type")
    cleaned = path.strip().strip("/")
    if _pool_report(cleaned) and media and "json" in media:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, (dict, list)):
            content = json.dumps(annotate_key_set(public_feed(data))).encode()
    return Response(content=content, status_code=resp.status_code, media_type=media)


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
    async with pool().acquire() as conn:
        async with conn.transaction():
            await __import__("training").collect_ledger(conn, body.tenant_id)
            if body.feedback == "rejected":
                await conn.execute("""DELETE FROM tank.route_cache c WHERE c.tenant_id=$1
                    AND c.task_type=(SELECT task_type FROM tank.ledger WHERE tenant_id=$1 AND id=$2)""",
                    body.tenant_id, ledger_id)
    return {"ok": True, "ledger_id": str(ledger_id), "feedback": body.feedback}


@app.get("/v1/evals/summary", dependencies=[Depends(require_key)])
async def evals_summary(
    tenant_id: uuid.UUID | None = None,
    all_tenants: bool = False,
    x_tank_key: str = Header(default=""),
    x_tervory_admin: str = Header(default=""),
) -> list[dict[str, Any]]:
    """One tenant's cases; a cross-tenant total requires Tank's founder identity gate."""
    if all_tenants:
        await __import__("admin").require_admin(x_tank_key, x_tervory_admin)
    elif tenant_id is None:
        raise HTTPException(422, "tenant_id is required")
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT task_type, count(*) AS cases,
                   count(*) FILTER (WHERE source='tester_feedback' AND verdict='accepted') AS accepted,
                   count(*) FILTER (WHERE source='tester_feedback' AND verdict='rejected') AS rejected,
                   count(*) FILTER (WHERE source='manual') AS manual
            FROM tank.evals WHERE tenant_id=$1 OR $2
            GROUP BY task_type ORDER BY task_type
            """, tenant_id, all_tenants,
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
                   sum(cost_usd) FILTER (WHERE cost_status='set') AS cost_usd,
                   count(*) FILTER (WHERE cost_status='not_set') AS unpriced,
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
            SELECT count(*) AS calls, coalesce(sum(cost_usd) FILTER (WHERE cost_status='set'),0) AS cost_usd,
                   count(*) FILTER (WHERE cost_status='not_set') AS unpriced,
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
        "unpriced": int(totals["unpriced"] or 0),
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
    for key in ("url", "label", "engine", "every", "enabled", "threshold", "alert_price", "alert_stock",
                "alert_new_product", "alert_below_cost", "alert_market_gap"):
        if key in body:
            forwarded[key] = body[key]
    resp = await _tiger_call("POST", "/watchlist", [], json.dumps(forwarded).encode())
    return _tiger_response(resp, tenant_id)


@app.patch("/v1/tiger/watchlist/{watch_id}", dependencies=[Depends(require_key)])
async def tiger_update_watch(watch_id: uuid.UUID, request: Request) -> Response:
    body = await _tiger_body(request)
    tenant_id = _tiger_tenant(request, body)
    forwarded = {"tenant_id": str(tenant_id)}
    for key in ("url", "label", "engine", "every", "enabled", "threshold", "alert_price", "alert_stock",
                "alert_new_product", "alert_below_cost", "alert_market_gap"):
        if key in body:
            forwarded[key] = body[key]
    resp = await _tiger_call("PATCH", f"/watchlist/{watch_id}", [], json.dumps(forwarded).encode())
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


# ---------- workers panel (read only) ----------


@app.get("/v1/workers", dependencies=[Depends(require_key)])
async def workers_panel() -> dict[str, Any]:
    """Worker status for the Tank page, from the host workers' heartbeat (WORKERS-2).
    Read only: no write, no outbound call. See workers_status.panel."""
    return await __import__("workers_status").panel()


# ---------- billing events (Workspace key only) ----------

class BillingEventClaim(BaseModel):
    event_id: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=255)


class BillingEventRelease(BaseModel):
    event_id: str = Field(min_length=1, max_length=255)


class BillingEventHandled(BaseModel):
    event_id: str = Field(min_length=1, max_length=255)


def _billing_text(value: str, label: str) -> str:
    text = value.strip()
    if not text or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise HTTPException(status_code=400, detail=f"{label} is required")
    return text


@app.post("/v1/billing/events/claim", dependencies=[Depends(require_key)])
async def claim_billing_event(body: BillingEventClaim) -> dict[str, bool]:
    """Store a Stripe event id once. The first caller gets first=true."""
    event_id = _billing_text(body.event_id, "event_id")
    event_type = _billing_text(body.type, "type")
    try:
        async with pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tank.billing_events (event_id, type, received_at)
                VALUES ($1, $2, now())
                ON CONFLICT (event_id) DO NOTHING
                RETURNING event_id
                """,
                event_id,
                event_type,
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Billing event could not be stored.") from None
    return {"first": row is not None}


@app.post("/v1/billing/events/release", dependencies=[Depends(require_key)])
async def release_billing_event(body: BillingEventRelease) -> dict[str, bool]:
    """Delete an unhandled claim so Stripe's retry can run."""
    event_id = _billing_text(body.event_id, "event_id")
    try:
        async with pool().acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM tank.billing_events
                WHERE event_id = $1 AND handled IS NOT TRUE
                """,
                event_id,
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Billing event could not be released.") from None
    return {"released": result == "DELETE 1"}


@app.post("/v1/billing/events/handled", dependencies=[Depends(require_key)])
async def mark_billing_event_handled(body: BillingEventHandled) -> dict[str, bool]:
    """Mark a stored claim handled so a later release leaves it in place."""
    event_id = _billing_text(body.event_id, "event_id")
    try:
        async with pool().acquire() as conn:
            result = await conn.execute(
                """
                UPDATE tank.billing_events
                SET handled = true
                WHERE event_id = $1
                """,
                event_id,
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Billing event could not be marked handled.") from None
    return {"handled": result == "UPDATE 1"}


app.include_router(__import__("admin").router)
app.include_router(__import__("controls").router)
app.include_router(__import__("workers_status").router)
app.include_router(__import__("workers_status").founder_router)
app.include_router(__import__("dashboards").router)

app.include_router(__import__("gold").router)
app.include_router(__import__("training").router)
app.include_router(__import__("storage").router)
app.include_router(__import__("bench").router)
app.include_router(__import__("proof").router)
app.include_router(routellm_shadow.router)
app.include_router(__import__("proof").client_router)
app.include_router(__import__("case_studies").router)
app.include_router(__import__("event_bus").router)
app.include_router(__import__("agent_skills").build_router(__import__("sys").modules[__name__]))
app.include_router(__import__("base_product").build_router(__import__("sys").modules[__name__]))
app.include_router(__import__("rig_brain_routes").build_router(__import__("sys").modules[__name__]))
app.include_router(__import__("moa").router)


@app.get("/v1/training/graduation")
async def training_graduation(actor=Depends(__import__("gold").require_reviewer)):
    if not actor.founder:
        raise HTTPException(404, "not found")
    async with pool().acquire() as conn:
        return await graduate.training_table(conn, actor.tenant, box_region())


@app.api_route("/v1/tisan/gold/{action}", methods=["GET", "POST"],
               dependencies=[Depends(__import__("admin").require_admin)])
async def tisan_gold_proxy(action: str, request: Request) -> Response:
    """Founder-only fixed corridor for reviewing and approving saved Tisan pages."""
    if (request.method, action) not in {("GET", "pages"), ("POST", "approve")}:
        raise HTTPException(status_code=404, detail="not found")
    key = os.environ.get("TANK_KEY_TISAN", "")
    if _http is None or not key:
        raise HTTPException(status_code=503, detail="Tisan room is unavailable")
    raw = await request.body()
    if len(raw) > 8192:
        raise HTTPException(status_code=413, detail="request too large")
    try:
        response = await _http.request(
            request.method, f"http://agent-tisan:8000/gold/{action}",
            params=list(request.query_params.multi_items()), content=raw or None,
            headers={"X-Tank-Key": key, "X-Tervory-Admin": request.headers.get("x-tervory-admin", ""),
                     "Content-Type": "application/json"}, timeout=30,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Tisan room is unavailable") from None
    return Response(content=response.content, status_code=response.status_code, media_type="application/json")


# ---------- Rig: the room owns the catalogues; Tank only proxies reads ----------
# The Workspace is not on Rig's corridor. These routes check the caller's tenant,
# forward to the Rig room with TANK_KEY_RIG, and return the room's JSON.
# Ask is the paid call. The room sends it back through POST /v1/route (task type
# rig.ask), which loads policy and writes the ledger. This proxy does not call a
# model and does not write a second ledger row. No shopper key is sent or stored.

RIG_AGENT_URL = "http://agent-rig:8000"
_RIG_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_RIG_SECRET_TEXT = re.compile(r"rk_(?:pub|adm)_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{8,}")
_RIG_DROP = frozenset({
    "key", "keys", "key_hash", "secret", "password", "token", "webhook", "email", "origins",
})
_RIG_DOWN = "Rig did not answer."


def _rig_tenant(request: Request, body: dict[str, Any] | None = None) -> uuid.UUID:
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


def _rig_limit(value: str | None) -> int:
    try:
        number = int(value) if value else 12
    except ValueError:
        return 12
    if number < 1:
        return 1
    if number > 50:
        return 50
    return number


def _rig_foreign(value: Any, tenant_id: uuid.UUID) -> bool:
    """True when a payload names a tenant other than the caller."""
    if isinstance(value, list):
        return any(_rig_foreign(item, tenant_id) for item in value)
    if not isinstance(value, dict):
        return False
    if "tenant_id" in value and not _same_tenant(value.get("tenant_id"), tenant_id):
        return True
    return any(_rig_foreign(item, tenant_id) for item in value.values())


def _rig_scrub(value: Any) -> Any:
    """Drop key material before a room payload leaves Tank."""
    if isinstance(value, list):
        return [_rig_scrub(item) for item in value]
    if isinstance(value, str):
        return _RIG_SECRET_TEXT.sub("", value)
    if not isinstance(value, dict):
        return value
    kept: dict[str, Any] = {}
    for key, item in value.items():
        name = str(key).lower()
        if name in _RIG_DROP or "secret" in name or name.endswith("_key"):
            continue
        kept[str(key)] = _rig_scrub(item)
    return kept


async def _rig_body(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if len(raw) > 8192:
        raise HTTPException(status_code=413, detail="request too large")
    if not raw:
        return {}
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="body must be json") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be an object")
    return body


async def _rig_call(method: str, path: str, params: list[tuple[str, str]], content: bytes | None, *, timeout: float) -> Any:
    key = os.environ.get("TANK_KEY_RIG", "").strip()
    if _http is None or not key:
        raise HTTPException(status_code=502, detail=_RIG_DOWN)
    headers = {"X-Tank-Key": key, "Accept": "application/json"}
    if content is not None:
        headers["Content-Type"] = "application/json"
    try:
        return await _http.request(
            method,
            RIG_AGENT_URL + path,
            params=params,
            content=content,
            headers=headers,
            timeout=timeout,
            follow_redirects=False,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail=_RIG_DOWN) from None


def _rig_response(resp: Any, tenant_id: uuid.UUID) -> Response:
    raw = resp.content or b""
    if not raw or len(raw) > 1_000_000:
        raise HTTPException(status_code=502, detail=_RIG_DOWN)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail=_RIG_DOWN) from None
    if _rig_foreign(payload, tenant_id):
        raise HTTPException(status_code=403, detail="tenant mismatch")
    try:
        encoded = json.dumps(_rig_scrub(payload)).encode()
    except (TypeError, ValueError):
        raise HTTPException(status_code=502, detail=_RIG_DOWN) from None
    return Response(content=encoded, status_code=resp.status_code, media_type="application/json")


def _rig_id(value: str) -> str:
    if not _RIG_ID.fullmatch(value):
        raise HTTPException(status_code=400, detail="bad id")
    return value


@app.get("/v1/rig/search", dependencies=[Depends(require_key)])
async def rig_search(request: Request) -> Response:
    tenant_id = _rig_tenant(request)
    params = [
        ("tenant_id", str(tenant_id)),
        ("q", (request.query_params.get("q") or "").strip()[:200]),
        ("limit", str(_rig_limit(request.query_params.get("limit")))),
    ]
    return _rig_response(await _rig_call("GET", "/v1/rig/search", params, None, timeout=30), tenant_id)


@app.get("/v1/rig/graph/{product_id}", dependencies=[Depends(require_key)])
async def rig_graph(product_id: str, request: Request) -> Response:
    item = _rig_id(product_id)
    tenant_id = _rig_tenant(request)
    params = [("tenant_id", str(tenant_id))]
    return _rig_response(await _rig_call("GET", f"/v1/rig/graph/{item}", params, None, timeout=30), tenant_id)


@app.get("/v1/rig/products/{product_id}", dependencies=[Depends(require_key)])
async def rig_product(product_id: str, request: Request) -> Response:
    item = _rig_id(product_id)
    tenant_id = _rig_tenant(request)
    params = [("tenant_id", str(tenant_id))]
    return _rig_response(await _rig_call("GET", f"/v1/rig/products/{item}", params, None, timeout=30), tenant_id)


@app.post("/v1/rig/compare", dependencies=[Depends(require_key)])
async def rig_compare(request: Request) -> Response:
    body = await _rig_body(request)
    tenant_id = _rig_tenant(request, body)
    ids = body.get("product_ids")
    if not isinstance(ids, list) or not ids or len(ids) > 24:
        raise HTTPException(status_code=400, detail="bad id")
    clean = [_rig_id(item) for item in ids if isinstance(item, str)]
    if len(clean) != len(ids):
        raise HTTPException(status_code=400, detail="bad id")
    payload = json.dumps({"product_ids": clean}).encode()
    resp = await _rig_call("POST", "/v1/rig/compare", [("tenant_id", str(tenant_id))], payload, timeout=30)
    return _rig_response(resp, tenant_id)


@app.post("/v1/rig/ask", dependencies=[Depends(require_key)])
async def rig_ask(request: Request) -> Response:
    """Forward the question. The room's model call is POST /v1/route, task type rig.ask.

    run_route loads that task's policy row and writes the ledger. A question the
    catalogue cannot answer does not call a model. This handler does not.
    """
    body = await _rig_body(request)
    tenant_id = _rig_tenant(request, body)
    product_id = body.get("product_id")
    if not isinstance(product_id, str):
        raise HTTPException(status_code=400, detail="bad id")
    question = body.get("question")
    forwarded: dict[str, Any] = {
        "product_id": _rig_id(product_id),
        "question": question.strip()[:500] if isinstance(question, str) else "",
    }
    if isinstance(body.get("setup"), dict):
        forwarded["setup"] = body["setup"]
    payload = json.dumps(forwarded).encode()
    resp = await _rig_call("POST", "/v1/rig/ask", [("tenant_id", str(tenant_id))], payload, timeout=150)
    return _rig_response(resp, tenant_id)


@app.get("/v1/rig/catalogues", dependencies=[Depends(require_key)])
async def rig_catalogues(request: Request) -> Response:
    """Product and fit counts for the caller's catalogue."""
    tenant_id = _rig_tenant(request)
    resp = await _rig_call("GET", "/catalogues", [("tenant_id", str(tenant_id))], None, timeout=30)
    return _rig_response(resp, tenant_id)


# ---------- Market Lab quarantine: the room holds the batches; Tank only proxies ----------
# The Workspace is not on the room corridor. These routes check the founder,
# forward with TANK_KEY_MARKET_LAB, and return the room's JSON. Remove also
# marks the batch removed in training lineage after the room accepts it.

MARKET_AGENT_URL = "http://agent-market-lab:8000"
_MARKET_BATCH = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_MARKET_ACTIONS = frozenset({"release", "reject", "remove"})
_MARKET_DOWN = "Market Lab did not answer."


async def _market_call(method: str, path: str) -> Any:
    key = os.environ.get("TANK_KEY_MARKET_LAB", "").strip()
    if _http is None or not key:
        raise HTTPException(status_code=502, detail=_MARKET_DOWN)
    try:
        return await _http.request(
            method,
            MARKET_AGENT_URL + path,
            headers={"X-Tank-Key": key, "Accept": "application/json"},
            timeout=30,
            follow_redirects=False,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail=_MARKET_DOWN) from None


def _market_ok(resp: Any) -> dict[str, Any]:
    if getattr(resp, "status_code", 0) < 200 or getattr(resp, "status_code", 0) >= 300:
        raise HTTPException(status_code=502, detail=_MARKET_DOWN)
    raw = getattr(resp, "content", b"") or b""
    if not raw or len(raw) > 1_000_000:
        raise HTTPException(status_code=502, detail=_MARKET_DOWN)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail=_MARKET_DOWN) from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail=_MARKET_DOWN)
    return payload


@app.get("/v1/market/quarantine")
async def market_quarantine_list(actor=Depends(__import__("gold").require_reviewer)) -> dict[str, Any]:
    if not actor.founder:
        raise HTTPException(status_code=404, detail="not found")
    return _market_ok(await _market_call("GET", "/quarantine"))


@app.post("/v1/market/quarantine/{batch_id}/{action}")
async def market_quarantine_act(
    batch_id: str,
    action: str,
    actor=Depends(__import__("gold").require_reviewer),
) -> dict[str, Any]:
    if not actor.founder or action not in _MARKET_ACTIONS or _MARKET_BATCH.fullmatch(batch_id) is None:
        raise HTTPException(status_code=404, detail="not found")
    payload = _market_ok(await _market_call("POST", f"/quarantine/{batch_id}/{action}"))
    if action != "remove":
        return payload
    try:
        async with pool().acquire() as conn:
            models = await __import__("training").retire_batch(conn, actor.tenant, batch_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail=_MARKET_DOWN) from None
    return {**payload, "models": models}

# GHOST-1: isolated founder panel, room checks, sealed Radix handoff and bounded recovery.
app.include_router(__import__("ghost_routes").router)
# MODELS-2: research stays in its own module; generic routing is unchanged.
__import__("research").register(app, globals())

# COMMAND-1A: conversation routes live in their own module.
app.include_router(__import__("command").router)
app.include_router(__import__("trigger_routes").router)

# ACCESS-1: scoped connections and browser-only credential handoff.
app.include_router(__import__("access").router)

# RIG-5F: additive GPU reservation and receipt routes.
app.include_router(__import__("rig_forge_routes").build_router(__import__("sys").modules[__name__]))

# RIG-5: additive Workspace proxy registration.
app.include_router(__import__("rig_three_d").build_router(__import__("sys").modules[__name__]))

app.include_router(__import__("market_lab_routes").build_router(__import__("sys").modules[__name__]))

# Tenant-specific semantic-cache approval; no policy promotion is automatic.
app.include_router(semantic_cache.build_router(__import__("sys").modules[__name__]))

# Free room checker intake uses the existing registry, evals and founder approval.
__import__("skala_intake").install(app, __import__("sys").modules[__name__])

app.include_router(__import__("vault_routes").build_router(__import__("sys").modules[__name__]))

# B3: process committed model changes through the existing skill-eval handler.
__import__("skala_revalidation").install(app, __import__("sys").modules[__name__])
