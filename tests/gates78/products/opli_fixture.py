"""OPLI's shipped HTTP corridor; only the issuer and LiteLLM network are faked."""
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
import uuid

import asyncpg
import httpx
import pytest_asyncio

from chassis.memory import MemoryClient
from trigger_signin_fakes import native_provider, ORG, set_founders

ROOT = Path(__file__).resolve().parents[3]
OWNER = "placeholder-opli-owner"
OTHER_USER = "placeholder-opli-other"
WORKSPACE_KEY = "placeholder-opli-workspace-key"
ANSWER = "placeholder owner result"


class OpliGateway:
    def __init__(self, events):
        self.calls = []
        self.events = events
        self.answer = ANSWER
        self.requests = []
        self.status = 200
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.release.set()

    async def __call__(self, request):
        assert request.url.host == "placeholder-litellm"
        if request.url.path == "/model/info":
            return httpx.Response(200, json={"data": [{
                "model_name": name, "litellm_params": {"model": "openai/placeholder-model"},
                "model_info": {"input_cost_per_token": .00001, "output_cost_per_token": .00002},
            } for name in ("llama-small", "gpt-oss-small", "qwen-small", "gpt-oss", "llama", "placeholder-frontier")]})
        if request.url.path == "/router/settings":
            return httpx.Response(200, json={"current_values": {"fallbacks": []}})
        assert request.method == "POST" and request.url.path == "/v1/chat/completions"
        self.calls.append(json.loads(request.content))
        self.events.append("provider")
        self.entered.set()
        await self.release.wait()
        return httpx.Response(self.status, headers={"x-litellm-response-cost": "0.0024"}, json={
            "choices": [{"message": {"content": json.dumps({"answer": self.answer, "requests": self.requests})},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 80, "completion_tokens": 80, "total_tokens": 160},
        })


@pytest_asyncio.fixture
async def opli(gate78_memory, monkeypatch):
    stack = await gate78_memory("opli")
    url = os.environ["MEMORY_TEST_DATABASE_URL"]
    admin = await asyncpg.connect(url)
    database = "opli_gate78_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{database}"')
    pool = await asyncpg.create_pool(urlunsplit(urlsplit(url)._replace(path="/" + database)), min_size=1, max_size=5)
    events, requests = [], []
    gateway = OpliGateway(events)
    client_type = httpx.AsyncClient
    gateway_http = client_type(transport=httpx.MockTransport(gateway))
    hermes_transport = httpx.ASGITransport(stack.app)
    failure = SimpleNamespace(path=None, status=503, mutate=None)

    async def hermes_edge(request):
        assert request.url.host == "hermes"
        if failure.mutate is not None:
            failure.mutate(request)
        requests.append(request)
        events.append(request.method + " " + request.url.path)
        if request.url.path == failure.path:
            return httpx.Response(failure.status, json={"detail": "placeholder storage unavailable"})
        return await hermes_transport.handle_async_request(request)

    memory_http = client_type(transport=httpx.MockTransport(hermes_edge))
    try:
        async with pool.acquire() as conn:
            await conn.execute((ROOT / "tank/schema.sql").read_text())
            from savings_defaults import initialize
            await initialize(conn)
            import paid_steps
            for tenant in (stack.tenant, stack.other_tenant):
                await conn.execute("""INSERT INTO tank.policy(task_type,tenant_id,model,rung,cache_scope,semantic_cache,
                    max_tokens_out,shadow_rate) VALUES('command.code',$1,'placeholder-frontier',1,'none',false,512,0)""",
                    uuid.UUID(tenant))
                for model in ("llama-small", "placeholder-frontier"):
                    step = paid_steps.model_step("command.code", model, agent="orchestrator")
                    await paid_steps.register(conn, step, "model", "model", "tank.policy", task="command.code", model=model)
                    await conn.execute("""INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by)
                        VALUES($1,$2,'auto','placeholder-opli-admin')""", uuid.UUID(tenant), step)
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setenv("TANK_API_KEY", WORKSPACE_KEY)
        monkeypatch.setenv("LITELLM_MASTER_KEY", "placeholder-gateway-key")
        monkeypatch.setenv("TANK_REGION", "us-east")
        monkeypatch.setenv("OPLI_MEMORY_ENABLED", "true")
        set_founders(monkeypatch, "placeholder-unrelated-founder")
        import main as tank
        import command
        import engine_memory
        monkeypatch.setattr(engine_memory, "HTTP", lambda **kwargs: client_type(transport=httpx.MockTransport(hermes_edge), **kwargs))
        monkeypatch.setattr(tank, "_pool", pool)
        monkeypatch.setattr(tank, "_admin_pool", None)
        monkeypatch.setattr(tank, "_redis", None)
        monkeypatch.setattr(tank, "_roster_cache", None)
        monkeypatch.setattr(tank, "TANK_API_KEY", WORKSPACE_KEY)
        monkeypatch.setattr(tank, "LITELLM_URL", "http://placeholder-litellm")
        monkeypatch.setattr(tank, "_http", gateway_http)
        monkeypatch.setattr(tank, "httpx", SimpleNamespace(
            AsyncClient=lambda **kwargs: client_type(transport=httpx.MockTransport(gateway), **kwargs),
            HTTPError=httpx.HTTPError, Response=httpx.Response))
        # The actual adapter's documented app.state.memory seam carries the shipped
        # MemoryClient. No product method, route, identity or receipt is replaced.
        memory = MemoryClient("http://hermes", stack.key, "opli", memory_http)
        monkeypatch.setattr(command, "app", SimpleNamespace(state=SimpleNamespace(memory=memory)), raising=False)
        issuer = native_provider(monkeypatch, {ORG: stack.tenant, "10002": stack.other_tenant})
        api = client_type(transport=httpx.ASGITransport(tank.app, raise_app_exceptions=False), base_url="http://tank")

        def headers(user=OWNER, tenant=None):
            return {"X-Tank-Key": WORKSPACE_KEY,
                    **issuer.workspace_headers(user, tenant or stack.tenant, "member")}

        async def thread(user=OWNER, tenant=None):
            response = await api.post("/v1/command/threads", json={"title": "placeholder Opli task"}, headers=headers(user, tenant))
            assert response.status_code == 200, response.text
            return response.json()["thread_id"]

        async def turn(thread_id=None, *, text="Summarise placeholder repository", user=OWNER, tenant=None, **extra):
            thread_id = thread_id or await thread(user, tenant)
            return await api.post("/v1/command/opli/code-turn", headers=headers(user, tenant), json={
                "thread_id": thread_id, "text": text, "prompt_id": str(uuid.uuid4()), "repo": "placeholder/repository", **extra})

        yield SimpleNamespace(stack=stack, pool=pool, api=api, gateway=gateway, headers=headers, thread=thread,
                              turn=turn, events=events, requests=requests, failure=failure, memory=memory, issuer=issuer, tank=tank)
        await api.aclose()
    finally:
        gateway.release.set()
        await memory_http.aclose()
        await gateway_http.aclose()
        await pool.close()
        await admin.execute(f'DROP DATABASE "{database}" WITH (FORCE)')
        await admin.close()
