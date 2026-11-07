"""Zenas entry-path wiring; Hermes, SQL, assertions and handlers stay real.

Only the external Tank/brain HTTP edge and the shared encoder are fixtures.
Do not load runtime from a product checkout or apply its proposed core patches.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import importlib
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[3]
SOURCE_SHA = "d37e9fa31826c32eddd095b66496333ee2ff31a4"
USER_A, USER_B, USER_C = ("placeholder-user-a", "placeholder-user-b", "placeholder-user-c")
WORKSPACE_KEY = "placeholder-gate78-workspace-key"
QUOTE = "A written commercial agreement binds the contracting parties."
FIXTURE_COST = .0025
FIXTURE_INPUT = 1200
FIXTURE_OUTPUT = 300
REQUIRED_RUNTIME = ("app", "gates_memory", "memory_api", "request_signing", "zenas_brain")


def require_runtime():
    missing = [f"agents/zenas/{name}.py" for name in REQUIRED_RUNTIME
               if not (ROOT / f"agents/zenas/{name}.py").is_file()]
    if missing:
        pytest.fail("BLOCKED: authoritative product runtime " + SOURCE_SHA +
                    " is not integrated into this Tank candidate: " + ", ".join(missing), pytrace=False)
    return importlib.import_module("agents.zenas.app")


def receipt(response):
    body = response.json()
    # Existing product envelopes are accepted, but absence is never a fake zero.
    for key in ("receipt", "brain_receipt", "savings_receipt"):
        if isinstance(body.get(key), dict):
            return body[key]
    pytest.fail("The actual product response has no run receipt: " + str(response.status_code))


@dataclass
class ExternalTank:
    events: list
    calls: list[dict] = field(default_factory=list)
    brain_calls: list[str] = field(default_factory=list)
    ledgers: dict[str, dict] = field(default_factory=dict)

    def send(self, request):
        """External Tank service fixture, reached via the shipped TankClient.

        These are gateway fixture prices/tokens, never live provider billing.
        Unexpected services/paths fail rather than making a network request.
        """
        body = json.loads(request.content) if request.content else {}
        path = request.url.path
        if request.url.host == "zenas-brain":
            self.brain_calls.append(path)
            self.events.append(("brain", path))
            if path == "/health":
                return httpx.Response(200, json={"ok": True, "room": "zenas"})
            if path == "/tasks":
                return httpx.Response(404, json={"detail": "placeholder standby brain"})
            raise AssertionError("Unexpected brain path")
        assert request.url.host == "placeholder-tank"
        if path == "/v1/skala/zenas.scope/run":
            from agents.zenas.core.scope_rules import classify
            payload = body["input"]
            ident = str(uuid4())
            self.ledgers[ident] = {"cost_usd": 0, "tokens_in": 0, "tokens_out": 0}
            return httpx.Response(200, json={**classify(payload["text"], payload.get("jurisdiction")),
                "_ledger_id": ident, "_ledger_ids": [], "_cost_usd": 0})
        if path == "/v1/zenas/savings/quote":
            rows = [self.ledgers[ident] for ident in body["ledger_ids"]]
            return httpx.Response(200, json={"cost": sum(row["cost_usd"] for row in rows),
                "would have cost": sum(row["cost_usd"] for row in rows),
                "tokens_in": sum(row["tokens_in"] for row in rows),
                "tokens_out": sum(row["tokens_out"] for row in rows),
                "baseline_model": "placeholder-paid-model"})
        assert path == "/v1/route" and request.method == "POST"
        self.calls.append(body)
        self.events.append(("tank", body["task_type"]))
        task = body["task_type"]
        if task == "zenas.rule_card":
            result = {"elements": [{"id": "written", "test": "The agreement is written.",
                "citation": "Fixture section 1", "quote": QUOTE}], "exceptions": [],
                "defences": [], "remedies": [], "decision_table": [
                    {"element_id": "written", "when": {"written": True}, "finding": "met"}]}
        elif task == "zenas.apply":
            result = {"finding": "met", "support": "placeholder signed agreement", "missing": ""}
        elif task == "moot.counsel":
            from moot_hearing.test_reasoning import trace
            result = {"kind": "submission", "text": "placeholder supported civil argument",
                      "authority_ids": ["case-1"], "reasoning": trace()}
        else:
            result = {"text": "placeholder drafted commercial terms", "clauses": [], "issues": []}
        ident = str(uuid4())
        self.ledgers[ident] = {"cost_usd": FIXTURE_COST, "tokens_in": FIXTURE_INPUT, "tokens_out": FIXTURE_OUTPUT}
        return httpx.Response(200, json={"content": json.dumps(result), "model": "placeholder-paid-model",
            "ledger_id": ident, "cost_usd": FIXTURE_COST,
            "tokens_in": FIXTURE_INPUT, "tokens_out": FIXTURE_OUTPUT, "rung": 1})


@dataclass
class ZenasEntry:
    stack: object
    room: object
    tank: object
    http: httpx.AsyncClient
    product_http: httpx.AsyncClient
    provider: object
    model: ExternalTank
    events: list
    body: dict
    raw_assertions: list = field(default_factory=list)

    def headers(self, user=USER_A, tenant=None):
        tenant = tenant or self.stack.tenant
        return {**self.provider.workspace_headers(user, tenant), "X-Tank-Key": WORKSPACE_KEY}

    async def request(self, method, path, *, user=USER_A, tenant=None, body=None, headers=None, run_id=None):
        tenant = tenant or self.stack.tenant
        auth = self.headers(user, tenant) if headers is None else headers
        auth = {**auth, "Idempotency-Key": run_id or str(uuid4())}
        params = {"tenant_id": tenant, "home_region": self.body["home_region"]}
        return await self.http.request(method, "/v1/zenas"+path, params=params,
                                       json=body, headers=auth)

    async def answer(self, *, user=USER_A, tenant=None, changes=None, run_id=None):
        payload = {**self.body, **(changes or {}), "tenant_id": tenant or self.stack.tenant}
        return await self.request("POST", "/answers", user=user, tenant=tenant, body=payload, run_id=run_id)

    async def records(self, user=USER_A, tenant=None):
        response = await self.request("GET", "/memory/records", user=user, tenant=tenant)
        assert response.status_code == 200, response.text
        return response.json()["memories"]

    async def snapshot(self):
        schema = self.stack.records.schema("zenas")
        return await self.stack.records.pool.fetch(f"SELECT to_jsonb(m) AS value FROM {schema}.memory_records m ORDER BY id")


@pytest_asyncio.fixture
async def zenas(gate78_memory, monkeypatch, request):
    # Runtime absence is an explicit dependency failure, not a skip or a private
    # runtime/core overlay. Head integrates runtime separately before acceptance.
    room = require_runtime()
    region = getattr(request, "param", "us-east")
    stack = await gate78_memory("zenas")
    pool = stack.records.pool
    monkeypatch.setenv("DATABASE_URL", os.environ["MEMORY_TEST_DATABASE_URL"])
    monkeypatch.setenv("TANK_REGION", region)
    monkeypatch.setenv("TANK_KEY", stack.key)
    monkeypatch.setenv("TANK_KEY_ZENAS", stack.key)
    monkeypatch.setenv("TANK_API_KEY", WORKSPACE_KEY)
    monkeypatch.setenv("ZENAS_PII_KEY", base64.urlsafe_b64encode(b"placeholder-zenas-gate78-key-value"[:32]).decode())
    monkeypatch.setenv("ZENAS_MEMORY_ENABLED", "true")
    monkeypatch.setenv("ZENAS_BRAIN_ENABLED", "false")
    monkeypatch.setenv("ZENAS_REVIEW", "off")
    monkeypatch.setenv("TANK_URL", "http://placeholder-tank")
    before = {r[0] for r in await pool.fetch("SELECT nspname FROM pg_namespace")}
    from agents.zenas.core.store import PgStore
    from agents.zenas.core.law_pool import bind_law_pool
    from agents.zenas.pool.store import PostgresStore
    from chassis.memory import MemoryClient
    from agents.zenas.core.outbound import TankClient
    from zenas_finish.test_source_freshness import save
    from trigger_signin_fakes import native_provider, ORG
    import paid_http

    await pool.execute((ROOT/"tank/schema.sql").read_text())
    await PgStore(pool).apply_schema()
    async with pool.acquire() as conn:
        await PostgresStore(conn, home_region=region).apply_schema()
    for tenant in (stack.tenant, stack.other_tenant):
        await PgStore(pool).register_tenant(tenant, region)
    doc, _ = await save(pool, region=region, text=QUOTE)
    events = []
    model = ExternalTank(events)
    outbound = httpx.AsyncClient(transport=httpx.MockTransport(model.send))
    room.app.state.pool = pool
    room.app.state.http = outbound
    room.app.state.configuration = {"ok": True}
    room.app.state.tank = TankClient("http://placeholder-tank", stack.key, "zenas", outbound)
    room.app.state.memory = MemoryClient("http://hermes", stack.key, "zenas", stack.http)
    bind_law_pool(room.app, home_region=region)

    async def memory_trace(req):
        events.append(("memory", req.url.path))
    stack.http.event_hooks["request"].append(memory_trace)
    body = {"tenant_id": stack.tenant, "home_region": region,
        "jurisdiction": "za" if region == "za" else "us",
        "question": "What does the written commercial agreement require under placeholder " +
                    "".join(chr(97+int(c, 16)) for c in uuid4().hex) + "?",
        "features": {"written": True, "facts": {"delivery": "placeholder goods delivered"},
            "parties": ["placeholder legal party"], "documents": ["placeholder signed agreement"],
            "positions": ["placeholder claimant position"], "house_style": "placeholder concise wording",
            "clauses": ["placeholder confidentiality clause"], "deadlines": ["placeholder response deadline"],
            "student_context": "placeholder clinic-law learning", "visitor_context": "placeholder moot visitor"},
        "passages": [{"doc_id": doc.id, "version_id": doc.version_id, "citation": doc.citation,
                      "text": QUOTE, "jurisdiction": doc.jurisdiction, "status": "effective"}]}
    tank = importlib.import_module("main")
    assert hasattr(tank, "zenas_proxy"), "Real Tank proxy required, not a shortcut route"
    monkeypatch.setattr(tank, "TANK_API_KEY", WORKSPACE_KEY)
    monkeypatch.setattr(tank, "_pool", pool)
    monkeypatch.setattr(tank, "_agent_keys_synced", True)
    bindings = {ORG: stack.tenant, "10002": stack.other_tenant}
    provider = native_provider(monkeypatch, bindings)
    assertions = []

    async def assertion_trace(req):
        assertions.append((req.method, req.url.raw_path.decode(), req.content, dict(req.headers)))
    product_http = paid_http.Client(transport=httpx.ASGITransport(app=room.app), follow_redirects=False,
                                   event_hooks={"request": [assertion_trace]})
    monkeypatch.setattr(tank, "_http", product_http)
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank")
    try:
        yield ZenasEntry(stack, room, tank, http, product_http, provider, model, events, body, assertions)
    finally:
        await http.aclose()
        await product_http.aclose()
        await outbound.aclose()
        # Only fixture-created schemas in this disposable loopback database.
        for schema in ("zenas_pool", "agent_zenas", "agent_tank", "tank"):
            if schema not in before:
                await pool.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
