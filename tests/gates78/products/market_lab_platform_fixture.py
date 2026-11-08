"""Market Lab entry wiring; no replacement Hermes, SQL ownership or receipts.

Only OIDC issuer, LiteLLM, public search/page HTTP and DNS are deterministic
network boundaries. Runtime is imported exclusively from this Tank candidate.
Missing runtime dependencies fail tests, never skip or load a private overlay.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[3]
PRODUCT_SOURCE = "30ebf40f6915f36defea7d15ae2a86e84eea4090"
A = "placeholder-market-owner"
B = "placeholder-market-peer"
KEY = "placeholder-gate78-product-key"
WORKSPACE_KEY = "placeholder-market-workspace-key"
SOURCE_URL = "https://www.bls.gov/placeholder-recorded-research"
SOURCE_TEXT = "placeholder recorded market observation increased by four units."


def require_runtime():
    required = ["agents/market_lab/gates_memory.py", "agents/market_lab/memory_api.py",
                "agents/market_lab/market_lab_brain.py", "agents/market_lab/core/savings.py"]
    missing = [p for p in required if not (ROOT / p).is_file()]
    if missing:
        pytest.fail("BLOCKED: Tank candidate lacks authoritative product runtime " + PRODUCT_SOURCE
                    + ": " + ", ".join(missing)
                    + ". Integrate product PR #1; do not patch Hermes or vendor.", pytrace=False)
    if importlib.util.find_spec("gpt_researcher") is None:
        pytest.fail("BLOCKED: actual researcher requires its committed GPTResearcher dependency closure; no shortcut researcher permitted", pytrace=False)


@pytest_asyncio.fixture
async def market_runtime(gate78_memory, gate78_database, monkeypatch):
    require_runtime()
    product_root = ROOT/'agents/market_lab'
    roots = {'researcher'} | {p.stem for p in product_root.glob('*.py')} | {p.name for p in product_root.iterdir() if p.is_dir() and p.name != "__pycache__"}
    saved_modules = {name: mod for name,mod in sys.modules.items() if name.split('.')[0] in roots}
    for name in saved_modules:
        del sys.modules[name]
    stack = await gate78_memory("market-lab")
    database = "placeholder_market_g78_" + uuid4().hex
    admin = await asyncpg.connect(gate78_database)
    await admin.execute(f'CREATE DATABASE "{database}"')
    parsed = urlsplit(gate78_database)
    url = urlunsplit(parsed._replace(path="/" + database))
    pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
    client_type = httpx.AsyncClient
    opened = []
    try:
        for name, value in {"DATABASE_URL": url, "TANK_API_KEY": WORKSPACE_KEY,
                            "TANK_KEY": KEY, "TANK_KEY_MARKET_LAB": KEY,
                            "LITELLM_MASTER_KEY": "placeholder-model-key", "TANK_REGION": "us-east",
                            "AGENT_NAME": "market_lab", "MARKET_LAB_MEMORY_ENABLED": "true",
                            "MARKET_LAB_BRAIN_ENABLED": "true"}.items():
            monkeypatch.setenv(name, value)
        monkeypatch.syspath_prepend(str(ROOT / "agents/market_lab"))
        product = importlib.import_module("app")
        gates = importlib.import_module("gates_memory")
        tank = importlib.import_module("main")
        assert Path(product.__file__).resolve() == product_root/'app.py'
        assert Path(gates.__file__).resolve() == product_root/'gates_memory.py'
        assert Path(importlib.import_module('core.http').__file__).resolve() == product_root/'core/http.py'
        assert Path(tank.__file__).resolve() == ROOT/'tank/main.py'
        researcher = importlib.import_module("researcher.app")
        assert Path(researcher.__file__).resolve() == ROOT/"researcher/app.py"
        sources = importlib.import_module("researcher.sources")
        await pool.execute((ROOT / "tank/schema.sql").read_text())
        from chassis.db import ensure_schema
        await ensure_schema(pool, "market_lab")
        async with pool.acquire() as conn:
            await importlib.import_module("core.ledger").PostgresLedger(conn).apply_schema()
        for tenant in (stack.tenant, stack.other_tenant):
            await pool.execute("INSERT INTO tank.tenants(tenant_id,home_region,onboarded_by) VALUES($1,'us-east','placeholder-owner')", UUID(tenant))
            await pool.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'market_lab','placeholder-owner')", UUID(tenant))
        await pool.execute("UPDATE tank.policy SET model='llama-small',rung=1,cache_scope='none',baseline_model='llama-small',candidate_model=NULL,shadow_rate=0 WHERE task_type='market.research'")
        await pool.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES('llama-small','placeholder-family',.005,0)")
        from paid_steps import model_step
        step = model_step("market.research", "llama-small", agent="market_lab")
        await pool.execute("INSERT INTO tank.paid_steps(step_id,product,kind,source) VALUES($1,'market_lab','model','placeholder-fixture-model') ON CONFLICT DO NOTHING", step)
        for tenant in (stack.tenant, stack.other_tenant):
            await pool.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto','placeholder-owner')", UUID(tenant), step)
        monkeypatch.setattr(tank, "_pool", pool)
        monkeypatch.setattr(tank, "_admin_pool", None)
        monkeypatch.setattr(tank, "_redis", None)
        monkeypatch.setattr(tank, "_roster_cache", (time.time(), [{"model_name": "llama-small",
            "litellm_params":{"model":"openai/placeholder-market-model"},
            "model_info": {"input_cost_per_token": .005, "output_cost_per_token": 0}}]))
        product.app.state.pool = pool
        product.app.state.files = None
        product.app.state.browser = None
        product.app.state.tank = None
        from chassis.memory import MemoryClient
        product.app.state.memory = MemoryClient('http://hermes', KEY, 'market_lab')
        assert product.app.state.memory._user_id is None
        research_app = researcher.create_app()
        provider_calls, outbound, assertions, memory_attempts = [], [], [], []
        unavailable = set()
        failed_edges=[]
        public_page={"text":SOURCE_TEXT}

        async def edge(request):
            host, path = request.url.host, request.url.path
            outbound.append((host, path))
            if host == "hermes":
                memory_attempts.append((request.method,path))
                if path in unavailable:
                    return httpx.Response(503, json={"detail": "placeholder memory unavailable"})
                return await stack.http.request(request.method, request.url.raw_path.decode(),
                    content=request.content, headers=dict(request.headers))
            if host == "agent-market-lab":
                assertions.append(request)
                return await httpx.ASGITransport(app=product.app).handle_async_request(request)
            if host == "market-research":
                return await httpx.ASGITransport(app=research_app).handle_async_request(request)
            if host == "tank":
                response=await httpx.ASGITransport(app=tank.app).handle_async_request(request)
                if response.status_code>=400:
                    failed_edges.append((path,response.status_code,(await response.aread()).decode()[:300]))
                return response
            if host == 'market-lab-brain':
                return httpx.Response(200,json={'status':'accepted'})
            if host == "litellm":
                if path.endswith("chat/completions"):
                    body = json.loads(request.content)
                    provider_calls.append(body)
                    prompt = json.dumps(body.get("messages", []))
                    content = json.dumps({"claims": [{"text": public_page["text"], "url": SOURCE_URL, "quote": public_page["text"]}]}) if "claims" in prompt else json.dumps(["placeholder market observation"])
                    return httpx.Response(200, json={"choices": [{"message": {"content": content}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 3}},
                        headers={"x-litellm-response-cost": "0.05", "x-litellm-model-group": "llama-small"})
                if path.endswith('/router/settings'):
                    return httpx.Response(200,json={'current_values':{'fallbacks':[]}})
                return httpx.Response(200, json={"data": [{"model_name": "llama-small", "litellm_params":{"model":"openai/placeholder-market-model"}, "model_info": {"input_cost_per_token": .005, "output_cost_per_token": 0}}]})
            raise AssertionError("Unexpected network edge " + str(request.url))

        transport = httpx.MockTransport(edge)
        import paid_http
        http = paid_http.Client(transport=transport, timeout=180)
        opened.append(http)
        monkeypatch.setattr(tank, "_http", http)
        monkeypatch.setattr(tank, "httpx", SimpleNamespace(AsyncClient=lambda **kw: client_type(transport=transport, **kw), HTTPError=httpx.HTTPError))
        brain=importlib.import_module('market_lab_brain')
        monkeypatch.setattr(brain,'httpx',SimpleNamespace(AsyncClient=lambda **kw:client_type(transport=transport,**kw)))
        adapter = importlib.import_module("core.research_adapter")
        monkeypatch.setattr(adapter, "httpx", SimpleNamespace(AsyncClient=lambda **kw: client_type(transport=transport, **kw), HTTPError=httpx.HTTPError))
        memory_http = client_type(transport=transport, timeout=30)
        opened.append(memory_http)
        product.app.state.memory._http = memory_http
        research_app.state.tank_transport = transport
        research_app.state.model_transport = httpx.ASGITransport(app=research_app)
        original_dns = socket.getaddrinfo
        def dns(host, *args, **kwargs):
            if host == "www.bls.gov":
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
            return original_dns(host, *args, **kwargs)
        monkeypatch.setattr(socket, "getaddrinfo", dns)
        def public_get(target, **kwargs):
            import requests
            response = requests.Response(); response.status_code = 200; response.url = target
            if target == sources.SEARX_URL:
                data = json.dumps({"results": [{"url": SOURCE_URL, "content": "placeholder search observation"}]})
                response.headers["Content-Type"] = "application/json"
            else:
                assert target == SOURCE_URL
                data = "<html><title>placeholder source</title><p>" + public_page["text"] + "</p></html>"
                response.headers["Content-Type"] = "text/html"
            response._content = data.encode(); response._content_consumed = True
            return response
        monkeypatch.setattr(sources.requests, "get", public_get)

        import identity_oidc as oidc
        from trigger_signin_fakes import Provider, install_registry, set_founders, ORG
        provider = Provider("us-east")
        install_registry(monkeypatch, [provider], {ORG: stack.tenant, str(int(ORG)+1): stack.other_tenant})
        monkeypatch.setattr(oidc, "http_client", lambda: client_type(transport=httpx.MockTransport(provider)))
        import memory_routes
        monkeypatch.setattr(memory_routes,'httpx',SimpleNamespace(
            AsyncClient=lambda **kw: client_type(transport=transport, **kw),HTTPError=httpx.HTTPError,URL=httpx.URL))
        oidc._cache.clear()
        client = client_type(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank")
        opened.append(client)
        required_paths = {'/v1/market-lab/{operation}', '/v1/market-lab/memory', '/v1/market-lab/jobs'}
        actual_paths = set(tank.app.openapi()['paths'])
        if not required_paths <= actual_paths:
            pytest.fail('BLOCKED: actual Tank Market Lab allowlist needs gates78-current-core.patch; no shortcut ingress permitted', pytrace=False)

        class Runtime:
            async def request(self, method, path, *, user=A, tenant=None, **kwargs):
                tenant = tenant or stack.tenant
                headers = {"X-Tank-Key": WORKSPACE_KEY, **provider.workspace_headers(user, tenant)}
                headers.update(kwargs.pop("headers", {}))
                path = {'/market/ask':'/v1/market-lab/ask','/jobs':'/v1/market-lab/jobs'}.get(path,path)
                return await client.request(method, path, headers=headers, **kwargs)

            async def ask(self, question="placeholder market observation", **kwargs):
                tenant = kwargs.get("tenant") or stack.tenant
                return await self.request("POST", "/market/ask", json={"tenant_id": tenant, "question": question}, **kwargs)

            async def controls(self, operation="", *, method="GET", **kwargs):
                return await self.request(method, "/v1/market-lab/memory" + operation, **kwargs)

            async def rows(self, user=A, tenant=None):
                return await stack.records.list(stack.agent, tenant or stack.tenant, user_id=user, limit=100)

            async def bill(self, tenant=None):
                return [dict(row) for row in await pool.fetch("SELECT id,cost_usd,tokens_in,tokens_out FROM tank.ledger WHERE tenant_id=$1 AND task_type='market.research' ORDER BY ts,id", UUID(tenant or stack.tenant))]

            def allow_founders(self):
                set_founders(monkeypatch,A+','+B)

            def fresh_product(self):
                fresh = importlib.reload(product)
                fresh.app.state.pool = pool
                fresh.app.state.memory = MemoryClient('http://hermes',KEY,'market_lab',memory_http)
                fresh.app.state.files = fresh.app.state.browser = fresh.app.state.tank = None
                return fresh.app

            async def direct(self, request):
                return await httpx.ASGITransport(app=product.app).handle_async_request(request)

        result = Runtime()
        result.__dict__.update(stack=stack, pool=pool, url=url, product=product, gates=gates, http=http,
            client=client, calls=provider_calls, outbound=outbound, assertions=assertions,
            unavailable=unavailable, issuer=provider, transport=transport, memory_attempts=memory_attempts,failed_edges=failed_edges,public_page=public_page)
        yield result
    finally:
        for name in list(sys.modules):
            if name.split('.')[0] in roots:
                del sys.modules[name]
        sys.modules.update(saved_modules)
        for client in reversed(opened):
            await client.aclose()
        await pool.close()
        await admin.execute(f'DROP DATABASE "{database}"')
        await admin.close()
