"""Radix network wiring only; real applications, sign-in, SQL and Hermes.

Missing runtime dependencies are failures, never proposal patches or substitutes.
The external issuer is the shared local RSA fixture. No scan/provider is contacted.
"""
from __future__ import annotations

from contextlib import AsyncExitStack
import importlib.util
import json
import io
import os
import tarfile
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
import pytest_asyncio

from chassis.memory import MemoryClient
from test_command import command_pool
from tank_routing.litellm_probe import COMPLETIONS_PATH

radix_sql_pool = command_pool

ROOT = Path(__file__).resolve().parents[3]
USER_A = "placeholder-radix-owner"
USER_B = "placeholder-radix-colleague"
USER_C = "placeholder-radix-other-tenant"
PATH = "/v1/radix/memory"
WORKSPACE_KEY = "placeholder-gate78-workspace"


@pytest.fixture
def radix_runtime(monkeypatch):
    required = ["agents/radix/radix_memory_api.py", "agents/radix/radix_memory.py",
                "agents/radix/radix_brain.py", "agents/radix/radix_readiness.py",
                "agents/radix/task_runtime.py", "agents/radix/radix_brain_service.py"]
    missing = [name for name in required if not (ROOT / name).is_file()]
    assert not missing, "BLOCKED: integrate the authoritative Radix PR and fixed-core corridor: " + ", ".join(missing)
    monkeypatch.syspath_prepend(str(ROOT / "agents/radix"))
    # Load the shipped application, not a replacement route around its helpers.
    for name in ("gold_sources", "radix_memory", "radix_memory_api", "radix_brain", "task_runtime"):
        spec = importlib.util.spec_from_file_location(name, ROOT / "agents/radix" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
    spec = importlib.util.spec_from_file_location("placeholder_radix_gate78_app", ROOT / "agents/radix/app.py")
    room = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(room)
    spec = importlib.util.spec_from_file_location("placeholder_radix_brain_service", ROOT / "agents/radix/radix_brain_service.py")
    brain = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(brain)
    room.brain = brain
    import main
    return main, room


@pytest_asyncio.fixture
async def radix_stack(radix_runtime, gate78_memory, radix_sql_pool, monkeypatch, tmp_path):
    from chassis.user_assertion import PostgresNonces
    from chassis.db import ensure_schema
    from chassis.tank import TankClient
    import engine_models
    import paid_steps
    import identity_oidc
    import paid_http
    from trigger_signin_fakes import Provider, install_registry

    main, room = radix_runtime
    memory = await gate78_memory("radix")
    pool = radix_sql_pool
    monkeypatch.setenv("TANK_KEY", memory.key)
    monkeypatch.setenv("TANK_API_KEY", WORKSPACE_KEY)
    monkeypatch.setenv("CHASSIS_ADMIN_DATABASE_URL", "postgresql://placeholder@127.0.0.1/placeholder")
    monkeypatch.setenv("CHASSIS_RLS_ADMIN_ROLE", "placeholder_admin")
    monkeypatch.setattr(main, "TANK_API_KEY", WORKSPACE_KEY)
    monkeypatch.setattr(main, "pool", lambda: pool)
    monkeypatch.setattr(main, "admin_pool", lambda: pool)
    monkeypatch.setattr(main, "_roster_cache", None)
    monkeypatch.setattr(main, "LITELLM_URL", "http://placeholder-provider")
    monkeypatch.setattr(main, "LITELLM_MASTER_KEY", "placeholder-provider-key")
    monkeypatch.setenv("RADIX_USE_SYSTEM_TOOLS", "0")
    monkeypatch.delenv("ENGINE_LOCAL_URL", raising=False)
    monkeypatch.delenv("ENGINE_LARGE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", pool._connect_args[0])
    async with pool.acquire() as conn:
        await ensure_schema(conn, "radix")
    # Only the Checkov subprocess edge is recorded; scanner orchestration and
    # built-in code scanners still process the supplied archive themselves.
    checkov = tmp_path / "placeholder-checkov"
    checkov.write_text('#!/usr/bin/env python3\nimport json\nprint(json.dumps({"results":{"failed_checks":[]}}))\n')
    checkov.chmod(0o755)
    monkeypatch.setenv("CHECKOV_BIN", str(checkov))
    from scanlib import iac
    monkeypatch.setattr(iac, "checkov_bin", lambda: os.environ["CHECKOV_BIN"])
    await pool.execute("CREATE SCHEMA IF NOT EXISTS agent_radix")
    await pool.execute((ROOT / "agents/radix/schema.sql").read_text())
    for tenant in (memory.tenant, memory.other_tenant):
        await pool.execute("INSERT INTO tank.tenants(tenant_id,home_region,onboarded_by) VALUES($1,'us-east',$2)", UUID(tenant), USER_A)
        await pool.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'radix',$2)", UUID(tenant), USER_A)
    provider = Provider("us-east")
    # The real verifier requires numeric organisation IDs. Fixture users/keys
    # remain visibly synthetic, while the issuer uses its actual wire contract.
    install_registry(monkeypatch, [provider], {"10001": memory.tenant, "10002": memory.other_tenant})
    monkeypatch.setattr(identity_oidc, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    identity_oidc._cache.clear()
    from chassis.tenant_db import TenantPool
    room.app.state.pool = TenantPool(pool)
    room.brain.app.state.pool = TenantPool(pool)
    room.app.state.memory = MemoryClient("http://hermes", memory.key, "radix", memory.http)
    room.app.state.product_nonce_stores = {"radix": PostgresNonces(pool, "radix")}
    for tenant in (memory.tenant, memory.other_tenant):
        await pool.execute("INSERT INTO tank.policy(tenant_id,task_type,model,shadow_rate,cache_scope) VALUES($1,'agent.radix.think','llama-small',0,'none')", UUID(tenant))
        for model in engine_models.OPEN:
            step = paid_steps.model_step("agent.radix.think", model, agent="radix")
            async with pool.acquire() as conn:
                await paid_steps.register(conn, step, "radix", "model", "tank.policy", task="agent.radix.think", model=model)
                await conn.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto',$3)", UUID(tenant), step, USER_A)
    forwarded = []
    provider_calls = []
    task_requests = []
    brain_requests = []
    network = SimpleNamespace(fail_provider=False)
    raw_client = httpx.AsyncClient
    transport = httpx.ASGITransport(room.app)

    async def room_edge(request):
        if request.url.host == "agent-radix":
            forwarded.append((request.method, request.url.raw_path.decode(), dict(request.headers), request.content))
            return await transport.handle_async_request(request)
        if request.url.host == "radix-brain":
            brain_requests.append(request)
            return await httpx.ASGITransport(room.brain.app).handle_async_request(request)
        if request.url.host in {"tank", "placeholder-tank"}:
            if request.url.path.startswith("/v1/agents/"):
                task_requests.append(request)
            return await httpx.ASGITransport(main.app).handle_async_request(request)
        if request.url.host == "placeholder-provider":
            if request.url.path == "/router/settings":
                return httpx.Response(200, json={"current_values": {"fallbacks": []}})
            if request.url.path == "/model/info":
                return httpx.Response(200, json={"data": [{"model_name": model,
                    "litellm_params": {"model": "placeholder/" + model},
                    "model_info": {"input_cost_per_token": .001, "output_cost_per_token": .001}}
                    for model in engine_models.OPEN]})
            assert request.url.path == COMPLETIONS_PATH
            # A different checkout must see the checkpoint before the paid edge.
            assert await pool.fetchval("SELECT EXISTS(SELECT 1 FROM agent_radix.task_context WHERE stage='executing' AND execution IS NULL)")
            provider_calls.append(json.loads(request.content))
            if network.fail_provider:
                raise httpx.ReadTimeout("placeholder response lost after send", request=request)
            return httpx.Response(200, headers={"x-litellm-response-cost": "0.05"}, json={
                "choices": [{"message": {"content": "placeholder review: use bound parameters; runtime exposure is unknown."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3}})
        raise AssertionError("Unexpected network destination in Radix fixture")

    def client_at_edge(*args, **kwargs):
        kwargs.setdefault("transport", httpx.MockTransport(room_edge))
        return raw_client(*args, **kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", client_at_edge)

    async with AsyncExitStack() as opened:
        wire = await opened.enter_async_context(paid_http.Client(transport=httpx.MockTransport(room_edge)))
        monkeypatch.setattr(main, "_http", wire)
        room_wire = await opened.enter_async_context(raw_client(transport=httpx.MockTransport(room_edge)))
        room.app.state.tank = TankClient("http://tank", memory.key, "radix", room_wire)
        room.brain.app.state.tank = TankClient("http://tank", memory.key, "radix", room_wire)
        room.app.state.files = SimpleNamespace()
        room.app.state.browser = SimpleNamespace()
        tank = await opened.enter_async_context(httpx.AsyncClient(transport=httpx.ASGITransport(main.app), base_url="http://placeholder-tank"))
        product = await opened.enter_async_context(httpx.AsyncClient(transport=transport, base_url="http://agent-radix:8000"))

        def headers(user=USER_A, tenant=None):
            return {"X-Tank-Key": WORKSPACE_KEY, **provider.workspace_headers(user, tenant or memory.tenant, role="member")}

        async def snapshot():
            # Capture durable application state, not the unavoidable consumed auth nonce.
            schema = memory.records.schema("radix")
            rows = await memory.records.pool.fetch(f"SELECT row_to_json(r)::text AS row FROM {schema}.memory_records r ORDER BY id")
            business = await pool.fetch("SELECT row_to_json(r)::text AS row FROM agent_radix.business_runs r ORDER BY id")
            ledger = await pool.fetch("SELECT row_to_json(r)::text AS row FROM tank.ledger r ORDER BY id")
            points = {}
            for item in memory.records.index.client.get_collections().collections:
                values, _ = memory.records.index.client.scroll(item.name, limit=1000, with_vectors=True)
                points[item.name] = sorted([v.model_dump(mode="json") for v in values], key=lambda row: str(row["id"]))
            return json.dumps([list(map(dict, rows)), list(map(dict, business)), list(map(dict, ledger)), points], sort_keys=True)

        yield SimpleNamespace(main=main, room=room, memory=memory, pool=pool, tank=tank, product=product,
                              headers=headers, forwarded=forwarded, snapshot=snapshot, provider=provider,
                              provider_calls=provider_calls, network=network, task_requests=task_requests, brain_requests=brain_requests)


async def owner_record(stack):
    response = await stack.tank.post(PATH + "/control", headers=stack.headers(), json={"control": "edit"})
    assert response.status_code == 200, response.text
    assert stack.provider.calls, "sign-in verification did not reach the local issuer"
    await stack.memory.records.tick()
    return response.json()["id"]


def archive_source(changed=False, clean=False):
    content = "placeholder = 1\n" if clean else 'cursor.execute("SELECT * FROM placeholder WHERE name = %s" % name)\n'
    if changed:
        content += 'cursor.execute("SELECT * FROM placeholder_changed WHERE id = %s" % ident)\n'
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        data = content.encode()
        info = tarfile.TarInfo("placeholder.py")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    return output.getvalue()


async def submit_scan(s, *, user=USER_A, tenant=None, changed=False, clean=False):
    tenant = tenant or s.memory.tenant
    headers = s.headers(user, tenant)
    response = await s.tank.post("/v1/command/threads", headers=headers, json={})
    assert response.status_code == 200, response.text
    thread = response.json()["thread_id"]
    response = await s.tank.post(f"/v1/command/threads/{thread}/attachments", headers=headers,
        params={"name": "placeholder.tar"}, content=archive_source(changed, clean))
    assert response.status_code == 200, response.text
    attachment = response.json()["attachment_id"]
    response = await s.tank.post(f"/v1/command/threads/{thread}/actions", headers=headers,
        json={"tool": "radix.repo.scan", "arguments": {"attachment_id": attachment}})
    assert response.status_code == 200, response.text
    card = response.json()["card_id"]
    previous = {row["id"] for row in await s.pool.fetch("SELECT id FROM agent_radix.jobs")}
    response = await s.tank.post(f"/v1/command/cards/{card}", headers=headers, json={"action": "confirm"})
    assert response.status_code == 200, response.text
    jobs = [row["id"] for row in await s.pool.fetch("SELECT id FROM agent_radix.jobs") if row["id"] not in previous]
    assert len(jobs) == 1, response.text
    return jobs[0]


async def work_next(s, *, require_done=True):
    from chassis.worker import claim_next, run_claimed
    from chassis.app import _context
    from chassis.tenant_db import tenant_scope
    async with s.pool.acquire() as conn:
        job = await claim_next(conn, "radix")
        assert job is not None
        with tenant_scope(job["tenant_id"]):
            await run_claimed(conn, "radix", job, s.room.app.state.handlers,
                              lambda row: _context(s.room.app, "radix", row))
        done = await conn.fetchrow("SELECT status,error,result FROM agent_radix.jobs WHERE id=$1", job["id"])
    if not require_done:
        return dict(done)
    assert done["status"] == "done", dict(done)
    return json.loads(done["result"]) if isinstance(done["result"], str) else done["result"]


async def scan(s, **kwargs):
    await submit_scan(s, **kwargs)
    return await work_next(s)


async def memory_control(s, entry, suffix, body):
    if entry == "tank":
        return await s.tank.post(PATH + suffix, headers=s.headers(), json=body)
    # Extra component coverage while Head integrates Tank's registered corridor.
    # This never stands in for the separately mapped Tank-ingress scenario.
    from chassis.user_assertion import HEADER, SignedUser, sign_assertion
    raw = json.dumps(body).encode()
    headers = {"X-Tank-Key": s.memory.key, "X-Tervory-Tenant": s.memory.tenant,
               "X-Tervory-User": USER_A, "Content-Type": "application/json",
               HEADER: sign_assertion("radix", SignedUser(s.memory.tenant, USER_A, "member"),
                                      "POST", PATH + suffix, raw, key=s.memory.key)}
    return await s.product.post(PATH + suffix, headers=headers, content=raw)
