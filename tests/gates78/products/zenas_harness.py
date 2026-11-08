"""Zenas entry-path wiring; Hermes, SQL, assertions and handlers stay real.

Only the external Tank/brain HTTP edge and the shared encoder are fixtures.
Do not load runtime from a product checkout or apply its proposed core patches.
"""
from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[3]
SOURCE_SHA = "a72db1aab636692a676ecd38a075c3dd3f184915"
USER_A, USER_B, USER_C = ("placeholder-user-a", "placeholder-user-b", "placeholder-user-c")
WORKSPACE_KEY = "placeholder-gate78-workspace-key"
QUOTE = "A written supply agreement requires notice before cancellation and remedies for breach."
FIXTURE_COST = .0024
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
    for key in ("savings_receipt", "receipt", "brain_receipt"):
        if isinstance(body.get(key), dict):
            return body[key]
    pytest.fail("The actual product response has no run receipt: " + str(response.status_code))


@dataclass
class ExternalProvider:
    """Only the LiteLLM/brain network boundary is recorded. Tank stays real."""
    events: list
    calls: list[dict] = field(default_factory=list)
    brain_calls: list[str] = field(default_factory=list)
    brain_reply: dict | None = None

    def send(self, request):
        body = json.loads(request.content) if request.content else {}
        path = request.url.path
        if request.url.host == "zenas-brain":
            self.brain_calls.append(path)
            self.events.append(("brain", path))
            if path == "/health":
                return httpx.Response(200, json={"ok": True, "room": "zenas"})
            if path == "/tasks" and self.brain_reply is not None:
                return httpx.Response(200, json=self.brain_reply)
            if path == "/tasks":
                return httpx.Response(404, json={"detail": "placeholder standby brain"})
            raise AssertionError("Unexpected brain path")
        assert request.url.host == "placeholder-litellm", "Unexpected external request: " + request.url.host
        if path == '/router/settings':
            import yaml
            raw = yaml.safe_load((ROOT/'litellm/config.yaml').read_text())
            return httpx.Response(200, json={'current_values':{'fallbacks':raw.get('litellm_settings',{}).get('fallbacks',[])}})
        if path == '/model/info':
            import yaml
            return httpx.Response(200, json={'data': yaml.safe_load((ROOT/'litellm/config.yaml').read_text())['model_list']})
        assert path == '/v1/chat/completions' and request.method == 'POST'
        text = '\n'.join(m['content'] for m in body['messages'])
        if 'Classify this request for Zenas' in text:
            result = {'area':'contracts','jurisdiction':'us'}
        elif 'decision_table' in text or 'elements' in text and 'exceptions' in text:
            result = {"elements": [{"id": "written", "test": "The agreement is written.",
                "citation": "Fixture section 1", "quote": QUOTE}], "exceptions": [],
                "defences": [], "remedies": [], "decision_table": [
                    {"element_id": "written", "when": {"written": True}, "finding": "met"}]}
        elif 'finding' in text and 'support' in text:
            result = {"finding": "met", "support": "placeholder signed agreement", "missing": ""}
        elif 'authority_ids' in text:
            from moot_hearing.test_reasoning import trace
            result = {"kind": "submission", "text": "placeholder supported civil argument",
                      "authority_ids": ["case-1"], "reasoning": trace()}
        else:
            result = {"text": "placeholder drafted commercial terms", "clauses": [], "issues": []}
        self.calls.append(body)
        self.events.append(('provider', body['model']))
        return httpx.Response(200, headers={'x-litellm-response-cost': str(FIXTURE_COST),
            'x-litellm-model-group': body['model']}, json={'id':'placeholder-completion',
            'choices':[{'message':{'role':'assistant','content':json.dumps(result)}, 'finish_reason':'stop'}],
            'usage':{'prompt_tokens':FIXTURE_INPUT,'completion_tokens':FIXTURE_OUTPUT}})


@dataclass
class ZenasEntry:
    stack: object
    room: object
    tank: object
    http: httpx.AsyncClient
    product_http: httpx.AsyncClient
    provider: object
    model: ExternalProvider
    events: list
    body: dict
    raw_assertions: list = field(default_factory=list)
    matters: dict = field(default_factory=dict)

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
        payload = {**self.body, "matter_id": self.matters[tenant or self.stack.tenant], **(changes or {}), "tenant_id": tenant or self.stack.tenant}
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
    monkeypatch.setenv("ZENAS_PII_KEY", b"placeholder-zenas-gate78-key-value"[:32].hex())
    monkeypatch.setenv("ZENAS_MEMORY_ENABLED", "true")
    monkeypatch.setenv("ZENAS_BRAIN_ENABLED", "false")
    monkeypatch.setenv("ZENAS_REVIEW", "off")
    monkeypatch.setenv("TANK_URL", "http://tank:8000")
    monkeypatch.setenv("HERMES_URL", "http://hermes:8000")
    before = {r[0] for r in await pool.fetch("SELECT nspname FROM pg_namespace")}
    import paid_http
    from chassis.memory import MemoryClient
    from trigger_signin_fakes import ORG, native_provider
    from zenas_finish.test_source_freshness import save

    from agents.zenas.core.law_pool import bind_law_pool
    from agents.zenas.core.outbound import TankClient
    from agents.zenas.core.store import PgStore
    from agents.zenas.pool.store import PostgresStore

    await pool.execute((ROOT/"tank/schema.sql").read_text())
    await PgStore(pool).apply_schema()
    async with pool.acquire() as conn:
        await PostgresStore(conn, home_region=region).apply_schema()
    matters = {}
    for tenant in (stack.tenant, stack.other_tenant):
        await PgStore(pool).register_tenant(tenant, region)
        row = await PgStore(pool).add_matter({'tenant_id': tenant, 'jurisdiction': 'za' if region == 'za' else 'us',
            'area':'contracts', 'title':'placeholder supply agreement', 'created_by':USER_A})
        matters[tenant] = row['id']
    # A distinct legal document avoids another test's public compiled-law cache
    # while keeping the actual search, compile and paid-admission path intact.
    salt = ''.join(chr(ord('a') + int(c, 16)) for c in uuid4().hex)
    question = f"What does a written supply agreement require for {salt}?"
    doc, _ = await save(pool, region=region, text=QUOTE + ' ' + salt)
    events = []
    model = ExternalProvider(events)
    tank = importlib.import_module("main")
    for key, value in {'TANK_API_KEY': WORKSPACE_KEY, 'LITELLM_URL': 'http://placeholder-litellm',
                       'LITELLM_MASTER_KEY':'placeholder-provider-key'}.items():
        monkeypatch.setattr(tank, key, value)
    monkeypatch.setattr(tank, '_pool', pool)
    monkeypatch.setattr(tank, '_admin_pool', None)
    monkeypatch.setattr(tank, '_roster_cache', None)
    import skala
    packages = skala.load_packages()
    monkeypatch.setattr(tank, '_packages', {key:value for key,value in packages.items() if key[0] == 'zenas.scope'})
    await tank.register_packages()
    await pool.execute("UPDATE tank.skills SET state='approved', approved_at=now() WHERE id='zenas.scope'")
    await pool.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES('llama-small','llama',0.000001,0.000004) ON CONFLICT(model) DO UPDATE SET input_usd=excluded.input_usd,output_usd=excluded.output_usd")
    await pool.execute("INSERT INTO tank.baseline_settings(task_type,override_model) VALUES('zenas.rule_card','llama-small') ON CONFLICT(task_type) DO UPDATE SET override_model=excluded.override_model")
    tasks = ('zenas.scope','zenas.rule_card','zenas.apply','zenas.draft','zenas.review_contract','zenas.plain',
             'moot.counsel','moot.judge')
    for tenant in (stack.tenant, stack.other_tenant):
        from uuid import UUID
        for task in tasks:
            await pool.execute("INSERT INTO tank.policy(task_type,tenant_id,model,priority,cache_scope,system_prompt) VALUES($1,$2,'llama-small','urgent','none','placeholder legal fixture') ON CONFLICT DO NOTHING", task, UUID(tenant))
            import paid_steps
            step = paid_steps.model_step(task, 'llama-small', agent='zenas')
            async with pool.acquire() as conn:
                await paid_steps.register(conn, step, 'zenas', 'model', 'placeholder fixture', task=task, model='llama-small')
                await conn.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto','placeholder-admin') ON CONFLICT DO NOTHING", UUID(tenant), step)
    base_client = httpx.AsyncClient
    class OfflineTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, req):
            if req.url.host in {'agent-zenas', 'localhost', '127.0.0.1'}:
                assertions.append((req.method, req.url.raw_path.decode(), req.content, dict(req.headers)))
                return await httpx.ASGITransport(app=room.app).handle_async_request(req)
            if req.url.host == 'tank':
                return await httpx.ASGITransport(app=tank.app).handle_async_request(req)
            if req.url.host == 'hermes':
                return await httpx.ASGITransport(app=stack.app).handle_async_request(req)
            return model.send(req)
    class ProviderClient(base_client):
        def __init__(self, *args, **kwargs):
            if kwargs.get('transport') is None:
                kwargs['transport'] = OfflineTransport()
            super().__init__(*args, **kwargs)
    monkeypatch.setattr(httpx, 'AsyncClient', ProviderClient)
    import engine_memory
    monkeypatch.setattr(engine_memory, 'HTTP', ProviderClient)
    edge_http = ProviderClient()
    async def tank_trace(req):
        if req.url.path == '/v1/route':
            events.append(('tank', req.url.path))
    outbound = base_client(transport=httpx.ASGITransport(app=tank.app),
                           event_hooks={'request': [tank_trace]})
    room.app.state.pool = pool
    room.app.state.http = edge_http
    room.app.state.configuration = {"ok": True}
    room.app.state.tank = TankClient("http://tank:8000", stack.key, "zenas", outbound)
    room.app.state.memory = MemoryClient("http://hermes", stack.key, "zenas", stack.http)
    bind_law_pool(room.app, home_region=region)

    async def memory_trace(req):
        events.append(("memory", req.url.path))
    stack.http.event_hooks["request"].append(memory_trace)
    body = {"tenant_id": stack.tenant, "home_region": region, "matter_id": matters[stack.tenant],
        "jurisdiction": "za" if region == "za" else "us",
        "question": question,
        "features": {"written": True, "facts": {"delivery": "placeholder goods delivered"},
            "parties": ["placeholder legal party"], "documents": ["placeholder signed agreement"],
            "positions": ["placeholder claimant position"], "house_style": "placeholder concise wording",
            "clauses": ["placeholder confidentiality clause"], "deadlines": ["placeholder response deadline"],
            "student_context": "placeholder clinic-law learning", "visitor_context": "placeholder moot visitor"},
        "passages": [{"doc_id": doc.id, "version_id": doc.version_id, "citation": doc.citation,
                      "text": QUOTE, "jurisdiction": doc.jurisdiction, "status": "effective"}]}
    assert hasattr(tank, "zenas_proxy"), "Real Tank proxy required, not a shortcut route"
    monkeypatch.setattr(tank, "TANK_API_KEY", WORKSPACE_KEY)
    monkeypatch.setattr(tank, "_pool", pool)
    monkeypatch.setattr(tank, "_agent_keys_synced", True)
    bindings = {ORG: stack.tenant, "10002": stack.other_tenant}
    provider = native_provider(monkeypatch, bindings)
    assertions = []

    product_http = paid_http.Client(transport=OfflineTransport(), follow_redirects=False,
                                   event_hooks={})
    monkeypatch.setattr(tank, "_http", product_http)
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank")
    try:
        yield ZenasEntry(stack, room, tank, http, product_http, provider, model, events, body, assertions, matters)
    finally:
        await http.aclose()
        await product_http.aclose()
        await outbound.aclose()
        await edge_http.aclose()
        # Only fixture-created schemas in this disposable loopback database.
        for schema in ("zenas_pool", "agent_zenas", "agent_tank", "tank"):
            if schema not in before:
                await pool.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
