"""Radix network wiring only; real applications, sign-in, SQL and Hermes.

Missing runtime dependencies are failures, never proposal patches or substitutes.
The external issuer is the shared local RSA fixture. No scan/provider is contacted.
"""
from __future__ import annotations

from contextlib import AsyncExitStack
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
import pytest_asyncio

from chassis.memory import MemoryClient
from test_command import command_pool

radix_sql_pool = command_pool

ROOT = Path(__file__).resolve().parents[3]
USER_A = "placeholder-radix-owner"
USER_B = "placeholder-radix-colleague"
USER_C = "placeholder-radix-other-tenant"
PATH = "/v1/radix/memory"
WORKSPACE_KEY = "placeholder-gate78-workspace"


@pytest.fixture
def radix_runtime(monkeypatch):
    required = ["agents/radix/memory_api.py", "agents/radix/gates_memory.py",
                "agents/radix/radix_brain.py", "agents/radix/readiness.py",
                "tank/radix_memory_routes.py"]
    missing = [name for name in required if not (ROOT / name).is_file()]
    assert not missing, "BLOCKED: integrate the authoritative Radix PR and fixed-core corridor: " + ", ".join(missing)
    monkeypatch.syspath_prepend(str(ROOT / "agents/radix"))
    # Load the shipped application, not a replacement route around its helpers.
    for name in ("gold_sources", "gates_memory", "memory_api", "radix_brain"):
        spec = importlib.util.spec_from_file_location(name, ROOT / "agents/radix" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
    spec = importlib.util.spec_from_file_location("placeholder_radix_gate78_app", ROOT / "agents/radix/app.py")
    room = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(room)
    import main
    from fastapi.routing import iter_route_contexts
    assert PATH in {route.path for route in iter_route_contexts(main.app.routes)}, "BLOCKED: Tank has no registered Radix memory route"
    return main, room


@pytest_asyncio.fixture
async def radix_stack(radix_runtime, gate78_memory, radix_sql_pool, monkeypatch):
    from chassis.user_assertion import PostgresNonces
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
    await pool.execute("CREATE SCHEMA IF NOT EXISTS agent_radix")
    await pool.execute((ROOT / "agents/radix/schema.sql").read_text())
    for tenant in (memory.tenant, memory.other_tenant):
        await pool.execute("INSERT INTO tank.tenants(tenant_id,home_region,onboarded_by) VALUES($1,'us-east',$2)", UUID(tenant), USER_A)
        await pool.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'radix',$2)", UUID(tenant), USER_A)
    provider = Provider("us-east")
    install_registry(monkeypatch, [provider], {"placeholder-org-a": memory.tenant, "placeholder-org-c": memory.other_tenant})
    monkeypatch.setattr(identity_oidc, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    identity_oidc._cache.clear()
    room.app.state.pool = pool
    room.app.state.memory = MemoryClient("http://hermes", memory.key, "radix", memory.http)
    room.app.state.product_nonce_stores = {"radix": PostgresNonces(pool, "radix")}
    forwarded = []
    transport = httpx.ASGITransport(room.app)

    async def room_edge(request):
        assert request.url.host == "agent-radix", "unexpected network destination"
        forwarded.append((request.method, request.url.raw_path.decode(), dict(request.headers), request.content))
        return await transport.handle_async_request(request)

    async with AsyncExitStack() as opened:
        wire = await opened.enter_async_context(paid_http.Client(transport=httpx.MockTransport(room_edge)))
        monkeypatch.setattr(main, "_http", wire)
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
                              headers=headers, forwarded=forwarded, snapshot=snapshot, provider=provider)


async def owner_record(stack):
    response = await stack.tank.post(PATH + "/control", headers=stack.headers(), json={"control": "edit"})
    assert response.status_code == 200, response.text
    assert stack.provider.calls, "sign-in verification did not reach the local issuer"
    await stack.memory.records.tick()
    return response.json()["id"]


def blocked_task_contract(requirement):
    """Never turn missing behavioural evidence into a passing source-code check."""
    pytest.fail(
        f"BLOCKED {requirement}: the Radix PR's run_with_memory/analyze_via_memory are not called by "
        "app.scan or verify.routes.attach; JobContext has no durable verified user; the shipped "
        "brain exposes /health, not /tasks. No real paid task/receipt entry path exists to exercise "
        "this requirement. Integrate a reviewed runtime contract, then replace this blocker with "
        "the corresponding entry-path scenario; legacy FakeMemory evidence cannot pass it."
    )
