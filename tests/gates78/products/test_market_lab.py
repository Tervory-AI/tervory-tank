"""Market Lab Gate 7/8: shipped ask, worker and controls on the shared stack.

Missing product runtime is a hard dependency failure, not an acceptance pass.
No private product checkout, unapplied patch, fake memory or replacement signer.
"""
from __future__ import annotations

import asyncio
import json
import time
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest

from market_lab_platform_fixture import A, B, KEY, SOURCE_TEXT, SOURCE_URL, market_runtime

# Export the uniquely named owned fixture to pytest, without a shared conftest edit.
__all__ = ["market_runtime"]
pytestmark = pytest.mark.asyncio


def accepted(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def receipt(body):
    result = body.get("memory_receipt", body)
    assert all(key in result for key in ("cost_usd", "tokens_in", "tokens_out", "answered_from_memory")), result
    return result


async def remember_owner(runtime):
    reply=await runtime.ask()
    assert reply.status_code==200,(reply.text,runtime.failed_edges)
    body = accepted(reply)
    assert not [edge for edge in runtime.failed_edges if edge[0]=='/v1/route'], runtime.failed_edges
    rows = await runtime.rows()
    assert rows and body.get("facts"), (body, rows, runtime.failed_edges)
    return rows


async def test_signed_owner_crud_and_meaningful_research_fields(market_runtime):
    r = market_runtime
    rows = await remember_owner(r)
    target = next(row for row in rows if row["kind"] == "market_lab.receipt")
    view = accepted(await r.controls(params={"task_key": "market.research", "memory_id": target["id"]}))
    assert target["id"] in {row["id"] for row in view["memories"]}
    fields = " ".join(str(row) for row in rows)
    for meaningful in ("questions", "trusted_sources", "reports", "outcome", "receipt", SOURCE_URL, SOURCE_TEXT):
        assert meaningful in fields
    edited = accepted(await r.controls("/edit", method="POST", json={"memory_id": target["id"], "text": "placeholder corrected observation", "memory_control": "edit"}))
    assert edited["id"] == target["id"]
    after = accepted(await r.controls(params={"memory_id": target["id"]}))
    assert "placeholder corrected observation" in json.dumps(after)
    accepted(await r.controls("/forget", method="POST", json={"memory_id": target["id"]}))
    assert target["id"] not in {row["id"] for row in await r.rows()}
    assert r.issuer.calls and r.assertions
    assert all(not path.startswith("/v1/memory") for _, path in r.stack.calls)


@pytest.mark.parametrize("foreign", ["same-tenant", "other-tenant"])
async def test_foreign_reads_mutations_and_publish_leave_state_unchanged(market_runtime, foreign, caplog):
    r = market_runtime
    rows = await remember_owner(r)
    target = rows[0]["id"]
    tenant = r.stack.other_tenant if foreign == "other-tenant" else r.stack.tenant
    before = await r.rows()
    for suffix, method, payload in [
        ("", "GET", None),
        ("/edit", "POST", {"memory_id": target, "text": "placeholder foreign mutation"}),
        ("/forget", "POST", {"memory_id": target}),
        ("/control", "POST", {"control": "off", "memory_id": target}),
    ]:
        kwargs = {"params": {"memory_id": target}} if payload is None else {"json": payload}
        response = await r.controls(suffix, method=method, user=B, tenant=tenant, **kwargs)
        assert response.status_code in {403, 404}, response.text
        assert SOURCE_TEXT not in response.text and KEY not in response.text
        assert await r.rows() == before
    fresh = accepted(await r.controls(user=B, tenant=tenant))
    assert SOURCE_TEXT not in json.dumps(fresh)
    assert SOURCE_TEXT not in caplog.text and KEY not in caplog.text


async def test_declared_shared_kinds_and_unowned_personal_rows(market_runtime):
    r = market_runtime
    await remember_owner(r)
    from hermes.user_scope import wide_kinds
    declared = r.gates.tenant_wide_kinds()
    assert set(declared) <= set(wide_kinds("market_lab")), "Do not invent a tenant-wide kind in a product-only patch"
    before = await r.rows()
    # Negative infrastructure call: not claimed as proof of a signed-in actor.
    from chassis.memory import MemoryClient
    anonymous = MemoryClient("http://hermes", KEY, "market_lab", r.stack.http)
    with pytest.raises(ValueError):
        await anonymous.remember(r.stack.tenant, "placeholder unowned personal", "market_lab.receipt", "urn:placeholder:scope")
    assert await r.rows() == before
    for kind in declared:
        row = await anonymous.remember(r.stack.tenant, "placeholder shared record", kind,
            "urn:placeholder:shared", tenant_wide=True)
        shared_view=accepted(await r.controls(user=B))
        assert row['id'] in {x['id'] for x in shared_view['memories']}
        personal = await r.stack.client(A).remember(r.stack.tenant, "placeholder owner on shared kind", kind, "urn:placeholder:personal")
        personal_view=accepted(await r.controls(user=B))
        assert personal["id"] not in {x["id"] for x in personal_view["memories"]}


async def test_real_signin_body_impersonation_and_missing_identity(market_runtime):
    r = market_runtime
    await remember_owner(r)
    for field, value in [("user_id", B), ("tenant_id", r.stack.other_tenant), ("role", "founder")]:
        response = await r.request("POST", "/market/ask", json={"tenant_id": r.stack.tenant, "question": "placeholder impersonation", field: value})
        assert response.status_code in {401, 403, 422}, response.text
    assert (await r.ask(headers={"X-Tervory-User": B})).status_code == 403
    before = await r.rows()
    request = httpx.Request("GET", "http://agent-market-lab:8000/v1/market-lab/memory", headers={"X-Tank-Key": KEY, "X-Tervory-Tenant": r.stack.tenant, "X-Tervory-User": A})
    response = await r.direct(request)
    assert response.status_code == 401 and SOURCE_TEXT not in (await response.aread()).decode()
    memory_before = len(r.memory_attempts)
    paid_before = len(r.calls)
    plain = httpx.Request("POST", "http://agent-market-lab:8000/market/ask", headers={"X-Tank-Key": KEY}, json={"tenant_id": r.stack.tenant, "question": "placeholder market observation"})
    completed = await r.direct(plain)
    assert completed.status_code == 200 and json.loads(await completed.aread()).get('facts')
    assert len(r.memory_attempts) == memory_before and len(r.calls) > paid_before
    assert await r.rows() == before



@pytest.mark.parametrize("defect", ["key", "audience", "tenant", "method", "target", "body", "missing", "expired", "future"])
async def test_nonce_assertion_rejections_cannot_return_cached_private_data(market_runtime, monkeypatch, defect):
    r = market_runtime
    await remember_owner(r)
    import product_identity as identity
    original = identity.sign
    def altered(product, user, method, target, body, **kwargs):
        if defect == "key": kwargs["key"] = "placeholder-wrong-key"
        if defect == "audience": product = "trigger"
        if defect == "tenant": user = identity.User(r.stack.other_tenant, user.user_id, user.role)
        if defect == "method": method = "DELETE"
        if defect == "target": target = "/placeholder-wrong-target"
        if defect == "body": body = b"placeholder tampered body"
        if defect == "expired": kwargs["now"] = int(time.time()) - 61
        if defect == "future": kwargs["now"] = int(time.time()) + 61
        return "" if defect == "missing" else original(product, user, method, target, body, **kwargs)
    monkeypatch.setattr(identity, "sign", altered)
    before = await r.rows()
    response = await r.controls()
    assert response.status_code == 401, response.text
    assert SOURCE_TEXT not in response.text and await r.rows() == before
    paid_before = len(r.calls)
    memory_before=len(r.memory_attempts)
    if defect=='missing':
        r.public_page['text']='placeholder fresh anonymous observation'
    task = await r.ask()
    if defect=='missing':
        body=accepted(task)
        assert not body.get('answered_from_memory') and SOURCE_TEXT not in task.text
        assert 'placeholder fresh anonymous observation' in task.text
        assert len(r.calls)>paid_before and len(r.memory_attempts)==memory_before
    else:
        assert task.status_code in {401,403,502}, task.text
        assert SOURCE_TEXT not in task.text and not task.json().get('answered_from_memory')
        assert len(r.calls)==paid_before
    assert await r.rows()==before



async def test_durable_nonce_concurrency_restart_and_forget_replay(market_runtime, monkeypatch):
    r = market_runtime
    rows = await remember_owner(r)
    import product_identity as identity
    original = identity.sign
    def reused(*args, **kwargs):
        return original(*args, **kwargs, nonce="placeholder-market-concurrent-nonce")
    monkeypatch.setattr(identity, "sign", reused)
    payload={'memory_id':rows[0]['id'],'text':'placeholder signed write correction','memory_control':'edit'}
    one, two = await asyncio.gather(*(r.controls('/edit',method='POST',json=payload) for _ in range(2)))
    assert sorted([one.status_code, two.status_code]) == [200, 401]
    captured = next(req for req in reversed(r.assertions) if req.url.path.endswith('/edit'))
    write_bytes=captured.content
    write_headers=dict(captured.headers)
    monkeypatch.setattr(identity, "sign", original)
    accepted(await r.controls("/forget", method="POST", json={"memory_id": rows[0]["id"]}))
    before=await r.rows()
    replay=httpx.Request('POST',str(captured.url),headers=write_headers,content=write_bytes)
    assert (await r.direct(replay)).status_code==401
    assert await r.rows()==before
    previous=r.product.app
    fresh=r.fresh_product()
    assert fresh is not previous
    replay=httpx.Request('POST',str(captured.url),headers=write_headers,content=write_bytes)
    assert (await r.direct(replay)).status_code==401
    assert await r.rows()==before and rows[0]['id'] not in {row['id'] for row in before}



async def test_sql_scope_precedes_vector_search_and_limit(market_runtime, monkeypatch):
    r = market_runtime
    await remember_owner(r)
    accepted(await r.ask(user=B))
    a_ids = {row["id"] for row in await r.rows()}
    b_ids = {row["id"] for row in await r.rows(user=B)}
    calls = []
    original = r.stack.records.index.search
    def observed(*args, **kwargs):
        allowed = set(kwargs["allowed_ids"])
        calls.append(allowed)
        assert allowed <= a_ids and not (allowed & b_ids)
        return original(*args, **kwargs)
    monkeypatch.setattr(r.stack.records.index, "search", observed)
    accepted(await r.controls(params={"task_key": "market.research"}))
    assert calls
    count = len(calls)
    accepted(await r.controls(tenant=r.stack.other_tenant))
    assert len(calls) == count


async def test_owner_path_with_restricted_database_role(market_runtime, gate78_database):
    r = market_runtime
    await remember_owner(r)
    schema = r.stack.records.schema("market_lab")
    role = "placeholder_market_" + uuid4().hex[:16]
    original = r.stack.records.pool
    await original.execute(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE')
    await original.execute(f'GRANT USAGE,CREATE ON SCHEMA "{schema}" TO "{role}"')
    await original.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
    await original.execute(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"')
    async def restricted(connection):
        await connection.execute(f'SET ROLE "{role}"')
    pool = await asyncpg.create_pool(gate78_database, min_size=1, max_size=1, init=restricted)
    r.stack.records.pool = pool
    try:
        assert not await pool.fetchval("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user")
        assert not await pool.fetchval("SELECT has_database_privilege(current_database(),'CREATE')")
        own = accepted(await r.controls(params={"task_key": "market.research"}))
        assert own["memories"]
        foreign = accepted(await r.controls(user=B))
        assert SOURCE_TEXT not in json.dumps(foreign)
    finally:
        r.stack.records.pool = original
        await pool.close()
        await original.execute(f'DROP OWNED BY "{role}"')
        await original.execute(f'DROP ROLE "{role}"')


async def test_default_off_and_code_steps_before_added_work(market_runtime, monkeypatch):
    r = market_runtime
    monkeypatch.delenv("MARKET_LAB_MEMORY_ENABLED", raising=False)
    monkeypatch.delenv("MARKET_LAB_BRAIN_ENABLED", raising=False)
    fresh=r.fresh_product()
    assert not fresh.state.market_lab_brain_enabled
    before = len(r.memory_attempts)
    paid_before=len(r.calls)
    body = accepted(await r.ask())
    assert body.get("facts") and not await r.rows()
    assert len(r.memory_attempts) == before
    assert len(r.calls)>paid_before
    assert not any(host == "market-lab-brain" for host, _ in r.outbound)
    # Existing deterministic no-question refusal happens before every added step.
    calls = len(r.calls)
    assert (await r.ask(question="")).status_code == 422
    assert len(r.calls) == calls
    assert not r.product.app.state.market_lab_brain_enabled


async def test_http_exact_repeat_changed_input_and_user_tenant_misses(market_runtime):
    r = market_runtime
    before = len(r.calls)
    first = receipt(accepted(await r.ask()))
    paid = len(r.calls) - before
    assert paid > 0 and first["cost_usd"] == pytest.approx(paid * .05)
    assert (first["tokens_in"], first["tokens_out"]) == (paid * 10, paid * 3)
    second = receipt(accepted(await r.ask()))
    assert len(r.calls) == before + paid
    assert second["answered_from_memory"] and second["cost_usd"] == 0
    assert (second["tokens_in"], second["tokens_out"]) == (0, 0)
    assert second["would_have_cost"] == pytest.approx(first["cost_usd"])
    changed=None
    changed_calls=None
    for kwargs in ({"question": "placeholder changed meaningful input"}, {"user": B}, {"tenant": r.stack.other_tenant}):
        count = len(r.calls)
        result = receipt(accepted(await r.ask(**kwargs)))
        assert len(r.calls) > count and not result["answered_from_memory"]
        delta=len(r.calls)-count
        assert result["cost_usd"] == pytest.approx(delta * .05)
        assert (result['tokens_in'],result['tokens_out'])==(delta*10,delta*3)
        if 'question' in kwargs:
            changed=result
            changed_calls=delta
    rows = await r.bill()
    assert sum(float(row["cost_usd"]) for row in rows) == pytest.approx(len(r.calls) * .05 - sum(float(row["cost_usd"]) for row in await r.bill(r.stack.other_tenant)))
    print("FIXTURE_COSTS", json.dumps({"first": first, "repeat": second, "provider_calls_first": paid, "provider_calls_repeat": 0, "changed":changed,"provider_calls_changed":changed_calls}))


async def test_correction_and_forget_invalidate_reusable_answers(market_runtime):
    r = market_runtime
    await remember_owner(r)
    row = next(row for row in await r.rows() if row["kind"] == "market_lab.receipt")
    accepted(await r.controls("/edit", method="POST", json={"memory_id": row["id"], "text": "correction=placeholder corrected market observation", "memory_control": "edit"}))
    corrected = accepted(await r.ask())
    assert "placeholder corrected market observation" in json.dumps(corrected)
    assert SOURCE_TEXT not in json.dumps(corrected.get("facts", []))
    accepted(await r.controls("/forget", method="POST", json={"memory_id": row["id"]}))
    count=len(r.calls)
    again = accepted(await r.ask())
    assert len(r.calls)>count and not again.get('answered_from_memory')
    assert "placeholder corrected market observation" not in json.dumps(again)
    assert await r.rows() and row["id"] not in {old["id"] for old in await r.rows()}


async def test_memory_off_is_user_scoped_and_blocks_reuse(market_runtime):
    r = market_runtime
    await remember_owner(r)
    accepted(await r.ask(user=B))
    accepted(await r.controls("/control", method="POST", json={"control": "off"}))
    count = len(r.calls)
    first = receipt(accepted(await r.ask()))
    assert len(r.calls)>count and not first['answered_from_memory']
    count=len(r.calls)
    second = receipt(accepted(await r.ask()))
    assert len(r.calls)>count and not second['answered_from_memory']
    assert accepted(await r.controls())["memories"] == []
    count = len(r.calls)
    peer = receipt(accepted(await r.ask(user=B)))
    assert peer["answered_from_memory"] and len(r.calls) == count


@pytest.mark.parametrize("phase", ["recall", "list", "remember"])
async def test_outages_are_truthful_and_do_not_expose_private_cache(market_runtime, phase):
    r = market_runtime
    rows = await remember_owner(r)
    r.unavailable.add({"recall": "/recall", "list": "/records", "remember": "/memories"}[phase])
    if phase == "list":
        count = len(r.calls)
        response = await r.controls(params={"memory_id": rows[0]["id"]})
        assert response.status_code == 503 and SOURCE_TEXT not in response.text
        assert len(r.calls) == count
        return
    before=len(r.calls)
    attempts=len(r.memory_attempts)
    body = accepted(await r.ask(question="placeholder different outage question"))
    assert body.get("memory_unavailable") or body.get("memory_receipt", {}).get("memory_unavailable")
    assert not body.get("answered_from_memory")
    assert len(r.calls) > before and len(r.memory_attempts)>attempts


async def test_research_worker_remember_failure_and_replay_never_pay_twice(market_runtime):
    r = market_runtime
    r.unavailable.add("/memories")
    queued = accepted(await r.request("POST", "/jobs", json={"tenant_id": r.stack.tenant, "kind": "research", "input": {"question": "placeholder worker observation"}}),status=201)
    ident = UUID(queued["id"])
    from chassis.app import _context
    from chassis.worker import claim_next,run_claimed
    from chassis.tenant_db import tenant_scope
    async with r.pool.acquire() as conn:
        job=await claim_next(conn,'market_lab')
    class FinishOutage:
        def __init__(self, conn): self.conn=conn
        async def execute(self, sql,*args):
            if "SET status = 'done'" in sql:
                raise OSError('placeholder finish unavailable')
            return await self.conn.execute(sql,*args)
    with tenant_scope(r.stack.tenant):
        async with r.pool.acquire() as conn:
            await run_claimed(FinishOutage(conn),'market_lab',job,r.product.app.state.handlers,lambda job:_context(r.product.app,'market_lab',job))
    saved=await r.pool.fetchval('SELECT result FROM agent_market_lab.executions WHERE tenant_id=$1 AND job_id=$2',UUID(r.stack.tenant),ident)
    first=json.loads(saved) if isinstance(saved,str) else dict(saved)
    assert first.get('facts') or first.get('citations')
    assert first.get('memory_unavailable') or first.get('memory_receipt',{}).get('memory_unavailable')
    assert ('POST','/memories') in r.memory_attempts
    paid=len(r.calls)
    assert paid>0
    await r.pool.execute("UPDATE agent_market_lab.jobs SET run_at=now() WHERE tenant_id=$1 AND id=$2",UUID(r.stack.tenant),ident)
    async def claim():
        async with r.pool.acquire() as conn:return await claim_next(conn,'market_lab')
    claims=await asyncio.gather(claim(),claim())
    assert sum(job is not None for job in claims)==1
    retry=next(job for job in claims if job is not None)
    assert retry['attempts']==2
    with tenant_scope(r.stack.tenant):
        async with r.pool.acquire() as conn:
            await run_claimed(conn,'market_lab',retry,r.product.app.state.handlers,lambda job:_context(r.product.app,'market_lab',job))
    row=await r.pool.fetchrow('SELECT status,result FROM agent_market_lab.jobs WHERE tenant_id=$1 AND id=$2',UUID(r.stack.tenant),ident)
    final=json.loads(row['result']) if isinstance(row['result'],str) else dict(row['result'])
    assert row['status']=='done' and final==first and len(r.calls)==paid



async def test_worker_body_user_is_not_verified_owner(market_runtime):
    r = market_runtime
    queued = accepted(await r.request("POST", "/jobs", json={"tenant_id": r.stack.tenant, "kind": "research", "input": {"question": "placeholder worker body spoof", "user_id": B}}),status=201)
    from chassis.app import _context
    from chassis.worker import claim_next,run_claimed
    async with r.pool.acquire() as conn:
        job=await claim_next(conn,'market_lab')
        assert str(job['id'])==queued['id']
        await run_claimed(conn,'market_lab',job,r.product.app.state.handlers,lambda job:_context(r.product.app,'market_lab',job))
    owner=await r.pool.fetchrow('SELECT user_id,role FROM agent_market_lab.job_actors WHERE tenant_id=$1 AND job_id=$2',UUID(r.stack.tenant),UUID(queued['id']))
    assert owner['user_id']==A and owner['role']=='org:admin'
    assert await r.rows(user=B) == []
    assert await r.rows(user=A), "Verified enqueue identity must survive the worker path"


async def test_code_research_passages_precede_brain_and_paid_network(market_runtime):
    r = market_runtime
    before = len(r.calls)
    queued = accepted(await r.request("POST", "/jobs", json={"tenant_id": r.stack.tenant, "kind": "research", "input": {
        "question": "placeholder supplied research evidence", "passages": [
            {"claim": SOURCE_TEXT, "url": SOURCE_URL, "date": "2026-11-07"}]}}),status=201)
    from chassis.app import _context
    from chassis.worker import claim_next,run_claimed
    async with r.pool.acquire() as conn:
        job=await claim_next(conn,'market_lab')
        assert str(job['id'])==queued['id']
        await run_claimed(conn,'market_lab',job,r.product.app.state.handlers,lambda job:_context(r.product.app,'market_lab',job))
    raw=await r.pool.fetchval('SELECT result FROM agent_market_lab.jobs WHERE tenant_id=$1 AND id=$2',UUID(r.stack.tenant),UUID(queued['id']))
    result=json.loads(raw) if isinstance(raw,str) else raw
    assert result["citations"] and SOURCE_URL in json.dumps(result)
    assert len(r.calls) == before
    assert not any(host == "market-lab-brain" for host, _ in r.outbound)
    assert result["run_receipt"]["cost"] == 0
    assert not result.get("answered_from_memory", False)


async def test_supported_publish_owner_and_foreign_denials(market_runtime):
    r=market_runtime
    r.allow_founders()
    rows=await remember_owner(r)
    from test_agent_memory_records import inventory
    body={'agent':'market_lab','tenant_id':r.stack.tenant,'enabled':True,'identifiers':inventory()}
    accepted(await r.request('POST','/v1/memory/publish-policy',json=body))
    target=rows[0]['id']
    before=await r.rows()
    for user,tenant in ((B,r.stack.tenant),(A,r.stack.other_tenant)):
        denied=await r.request('POST','/v1/memory/publish',user=user,tenant=tenant,
            json={'agent':'market_lab','tenant_id':tenant,'source_row':target})
        assert denied.status_code in {403,409} and SOURCE_TEXT not in denied.text
        assert await r.rows()==before
    published=accepted(await r.request('POST','/v1/memory/publish',json={
        'agent':'market_lab','tenant_id':r.stack.tenant,'source_row':target}))
    assert published['result']=='published' and published['published_row']
