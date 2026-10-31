"""Offline router/model stubs; actual Tank handlers and disposable PostgreSQL."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
import uuid

import asyncpg
import httpx
import pytest
import pytest_asyncio

import graduate
import routellm_shadow as routing


@pytest.mark.parametrize("fields", [{}, {"routellm_weak_model": "cheap"}, {"routellm_threshold": .5},
    {"routellm_weak_model": "strong", "routellm_threshold": .5},
    {"routellm_weak_model": "cheap", "routellm_threshold": float("nan")},
    {"routellm_weak_model": "skill:test@1.0.0", "routellm_threshold": .5}])
def test_off_or_invalid_never_enables_router(fields):
    assert routing.configuration({"model": "strong", **fields}) is None


def test_pin_changes_isolate_evidence_and_router_cannot_become_a_live_model():
    a = routing.Configuration("strong", "cheap", .5)
    b = routing.Configuration("strong", "cheap", .6)
    assert a.fingerprint != b.fingerprint
    assert graduate.router_cannot_serve(a.candidate)
    decision = graduate.promote_if_proven({"model": "strong", "candidate_model": a.candidate},
        graduate.Evidence(samples=200, agreement=1), datetime.now(timezone.utc), automatic=False)
    assert decision.action == "hold"


@pytest.mark.parametrize("samples,score,approved,expected", [(199, 1, True, "hold"),
    (200, .98, True, "hold"), (200, .99, False, "hold"), (200, .99, True, "promote")])
def test_model_promotion_still_requires_existing_graduation(samples, score, approved, expected):
    move = graduate.promote_if_proven({"model": "strong", "candidate_model": "cheap"},
        graduate.Evidence(samples=samples, agreement=score), datetime.now(timezone.utc), automatic=not approved)
    assert move.action == expected


@pytest_asyncio.fixture
async def real_tank(monkeypatch):
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url:
        pytest.skip("requires disposable PostgreSQL via POOL_SCHEMA_DATABASE_URL")
    if urlsplit(url).hostname not in {"localhost", "127.0.0.1"}:
        pytest.fail("proof database must be local")
    admin = await asyncpg.connect(url)
    name = "routellm_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    target = urlunsplit(urlsplit(url)._replace(path="/" + name))
    for key, value in {"DATABASE_URL": target, "TANK_API_KEY": "local-routellm-test",
                       "LITELLM_MASTER_KEY": "local-provider-stub", "TANK_REGION": "us-east",
                       "TERVORY_ADMIN_USER_IDS": "local-founder", "REDIS_URL": "redis://127.0.0.1:1/0"}.items():
        monkeypatch.setenv(key, value)
    import main as tank
    monkeypatch.setattr(tank, "DATABASE_URL", target)
    monkeypatch.setattr(tank, "TANK_API_KEY", "local-routellm-test")
    monkeypatch.setattr(tank, "REDIS_URL", "redis://127.0.0.1:1/0")
    state = SimpleNamespace(calls=[], score=.2, router_calls=0, weak_error=False, no_price=False, fallback=False)

    def provider(request):
        if request.url.path.endswith("/model/info"):
            return httpx.Response(200, json={"data": []})
        payload = json.loads(request.content)
        state.calls.append(payload)
        model = payload["model"]
        if state.weak_error and model == "flash-lite":
            return httpx.Response(503, json={"error": "local provider failure"})
        cost = {"sol": ".02", "flash-lite": ".002", "luna": ".001"}.get(model, ".001")
        headers = {"x-litellm-response-cost": cost, "x-litellm-model-group": model}
        if state.no_price and model == "flash-lite":
            headers.pop("x-litellm-response-cost")
        if state.fallback and model == "flash-lite":
            headers["x-litellm-model-group"] = "sol"
        answer = "100" if model == "luna" else ("Live policy answer" if model == "sol" else "A different shadow answer")
        return httpx.Response(200, headers=headers, json={"choices": [{"message": {"content": answer}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    def router(prompt):
        state.router_calls += 1
        if state.score is None:
            raise RuntimeError("local router unavailable")
        return state.score

    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank",
        headers={"X-Tank-Key": "local-routellm-test"})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: original(*a, **{**kw, "transport": httpx.MockTransport(provider)}))
    monkeypatch.setattr(routing, "score", router)
    tenants = (uuid.uuid4(), uuid.uuid4())
    try:
        async with tank.app.router.lifespan_context(tank.app):
            async with tank.pool().acquire() as conn:
                for tenant in tenants:
                    await conn.execute("""INSERT INTO tank.policy(tenant_id,task_type,model,shadow_rate,system_prompt)
                        VALUES($1,'routellm.proof','sol',1,'Answer the question.')""", tenant)
                await conn.execute("UPDATE tank.policy SET model='luna' WHERE task_type='tank.judge'")
            yield SimpleNamespace(tank=tank, pool=tank.pool(), client=client, tenants=tenants, state=state)
            if tank._background:
                await asyncio.gather(*list(tank._background))
    finally:
        await client.aclose()
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


async def turn(b, tenant):
    response = await b.client.post("/v1/route", json={"tenant_id": str(tenant), "task_type": "routellm.proof",
        "messages": [{"role": "user", "content": "What is two plus two?"}]})
    assert response.status_code == 200, response.text
    assert response.json()["content"] == "Live policy answer"
    assert response.json()["model"] == "sol"
    if b.tank._background:
        await asyncio.gather(*list(b.tank._background))
    async with b.pool.acquire() as conn:
        return dict(await conn.fetchrow("SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2",
            uuid.UUID(response.json()["ledger_id"]), tenant))


@pytest.mark.asyncio
async def test_real_tank_off_shadow_cost_judge_isolation_and_founder_gate(real_tank):
    b = real_tank
    a, other = b.tenants
    row = await turn(b, a)
    assert row["routellm_score"] is None and b.state.router_calls == 0
    body = {"tenant_id": str(a), "routellm_weak_model": "flash-lite", "routellm_threshold": .7}
    path = "/v1/policy/routellm.proof/routellm"
    assert (await b.client.put(path, json=body)).status_code == 404
    assert (await b.client.put(path, json=body, headers={"X-Tervory-Admin": "local-founder"})).status_code == 200
    row = await turn(b, a)
    assert row["routellm_model"] == "flash-lite" and row["routellm_score"] == .2
    assert row["routellm_status"] == "sampled"
    async with b.pool.acquire() as conn:
        sample = await conn.fetchrow("SELECT * FROM tank.shadow WHERE ledger_id=$1 AND tenant_id=$2", row["id"], a)
        assert sample["agreement"] == 1 and sample["method"] == "judge"
        shadow = await conn.fetchrow("SELECT * FROM tank.ledger WHERE id=$1", sample["candidate_ledger_id"])
        assert shadow["routellm_model_cost_usd"] == Decimal(".002")
        assert shadow["cost_usd"] == Decimal(".003")  # Includes the real judge receipt cost.
        assert shadow["routellm_sample_tenant"] == a and shadow["tenant_id"] == b.tank.PLATFORM_TENANT
        assert not await conn.fetchval("SELECT count(*) FROM tank.shadow WHERE tenant_id=$1", other)
        assert (await b.tank._load_evidence(conn, {"task_type": "routellm.proof", "candidate_model": "flash-lite"})).samples == 0
    headers = {"X-Tervory-Admin": "local-founder"}
    first = (await b.client.get("/v1/proof", params={"tenant_id": str(a)}, headers=headers)).json()
    pair = next(t for t in first["tasks"] if t["task_type"] == "routellm.proof")["shadow_pairs"][0]
    assert pair["primary_cost_usd"] == .02 and pair["could_have_cost_usd"] == .002 and pair["saved_usd"] == .018
    second = (await b.client.get("/v1/proof", params={"tenant_id": str(other)}, headers=headers)).json()
    assert second["shadows"] == [] and all(not t["shadow_pairs"] for t in second["tasks"])
    assert await routing.ladder(b.tank, other, False) == {}
    assert (await routing.ladder(b.tank, a, False))["routellm.proof"][0]["samples"] == 1
    row = await turn(b, other)
    assert row["routellm_status"] is None
    # Re-applying startup schema preserves the founder's opt-in and NULL defaults.
    # Startup applies the schema outside a tenant transaction; doing it inside one
    # holds DDL locks while load_policy waits on another connection (a deadlock).
    async with b.pool.acquire(autocommit=True) as conn:
        await conn.execute(Path("tank/schema.sql").read_text())
    assert (await b.tank.load_policy("routellm.proof", a))["routellm_weak_model"] == "flash-lite"
    assert (await b.tank.load_policy("routellm.proof", other))["routellm_weak_model"] is None
    # Source fixtures for the browser proof come from the actual Tank report.
    output = os.environ.get("ROUTELLM_PROOF_OUTPUT")
    if output:
        Path(output).mkdir(parents=True, exist_ok=True)
        Path(output, "report.json").write_text(json.dumps(first, indent=2))


@pytest.mark.asyncio
async def test_failure_strong_selection_unsampled_and_unknown_cost_leave_answer_unchanged(real_tank, monkeypatch):
    b = real_tank
    a = b.tenants[0]
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET routellm_weak_model='flash-lite',routellm_threshold=.7 WHERE tenant_id=$1", a)
    b.state.score = .8
    row = await turn(b, a)
    assert row["routellm_model"] == "sol" and row["routellm_status"] == "scored"
    b.state.score = None
    assert (await turn(b, a))["routellm_status"] == "unavailable"
    b.state.score = .2
    b.state.weak_error = True
    assert (await turn(b, a))["routellm_status"] == "sample_failed"
    b.state.weak_error = False
    b.state.fallback = True
    assert (await turn(b, a))["routellm_status"] == "sample_failed"
    b.state.fallback = False
    b.state.no_price = True
    assert (await turn(b, a))["routellm_status"] == "sampled"
    report = (await b.client.get("/v1/proof", params={"tenant_id": str(a)}, headers={"X-Tervory-Admin": "local-founder"})).json()
    assert all(not task["shadow_pairs"] for task in report["tasks"])
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET shadow_rate=.1 WHERE tenant_id=$1", a)
    monkeypatch.setattr(routing.random, "random", lambda: .9)
    count = len(b.state.calls)
    assert (await turn(b, a))["routellm_status"] == "scored"
    assert len(b.state.calls) == count+1
