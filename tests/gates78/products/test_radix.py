"""Radix acceptance through registered ingress, real workers and signed Hermes.

Runtime dependencies remain explicit: no helper-only or source-only acceptance.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid

import asyncpg
import pytest

from chassis.user_assertion import HEADER, PostgresNonces, SignedUser, sign_assertion
from radix_fixture import (
    PATH, ROOT, USER_A, USER_B, USER_C, owner_record, memory_control, scan, submit_scan, work_next, archive_source,
    radix_runtime as radix_runtime, radix_sql_pool as radix_sql_pool,
    radix_stack as radix_stack,
)


@pytest.mark.asyncio
async def test_owner_controls_use_signed_route_and_real_hermes(radix_stack):
    s = radix_stack
    record = await owner_record(s)
    assert s.forwarded and HEADER.lower() in s.forwarded[0][2]
    assert s.memory.calls, "the shipped MemoryClient never reached Hermes"
    recalled = await s.tank.get(PATH, headers=s.headers())
    assert recalled.status_code == 200 and any(row["id"] == record for row in recalled.json()["memories"])
    view = await s.tank.get(PATH, headers=s.headers(), params={"memory_id": record})
    assert view.status_code == 200
    assert view.json()["memories"][0]["id"] == record
    edited = await s.tank.post(PATH + "/edit", headers=s.headers(), json={"memory_id": record, "text": "placeholder-owner-correction", "memory_control": "edit"})
    assert edited.status_code == 200, edited.text
    view = await s.tank.get(PATH, headers=s.headers(), params={"memory_id": record})
    assert "placeholder-owner-correction" in view.text
    forgotten = await s.tank.post(PATH + "/forget", headers=s.headers(), json={"memory_id": record})
    assert forgotten.status_code == 200
    view = await s.tank.get(PATH, headers=s.headers(), params={"memory_id": record})
    assert view.status_code in (403, 404)
    assert "placeholder-owner-correction" not in view.text


@pytest.mark.parametrize("other_tenant", [False, True], ids=["same-tenant", "other-tenant"])
@pytest.mark.parametrize("action", ["view", "edit", "forget", "off", "publish"])
@pytest.mark.asyncio
async def test_eight_foreign_control_denials_leave_state_unchanged(radix_stack, other_tenant, action, caplog):
    s = radix_stack
    record = await owner_record(s)
    edited = await s.tank.post(PATH + "/edit", headers=s.headers(), json={"memory_id": record,
        "text": "placeholder-owner-private", "memory_control": "edit"})
    assert edited.status_code == 200
    await s.memory.records.tick()
    before = await s.snapshot()
    headers = s.headers(USER_C if other_tenant else USER_B, s.memory.other_tenant if other_tenant else s.memory.tenant)
    if action == "view":
        response = await s.tank.get(PATH, headers=headers, params={"memory_id": record})
    else:
        body = {"memory_id": record}
        if action == "edit":
            body["text"] = "placeholder-forged-correction"
        if action == "off":
            body["control"] = "off"
        response = await s.tank.post(PATH + ("/control" if action == "off" else "/" + action), headers=headers, json=body)
    assert response.status_code in (403, 404), response.text
    assert await s.snapshot() == before
    assert USER_A not in response.text
    assert "placeholder-owner-private" not in response.text + caplog.text
    assert s.memory.key not in caplog.text and "placeholder-forged-correction" not in caplog.text
    owner = await s.tank.get(PATH, headers=s.headers(), params={"memory_id": record})
    assert owner.status_code == 200 and owner.json()["memories"][0]["id"] == record


@pytest.mark.asyncio
async def test_signin_body_and_header_impersonation(radix_stack):
    s = radix_stack
    await owner_record(s)
    before = await s.snapshot()
    for injected in ({"user_id": USER_B}, {"tenant_id": s.memory.other_tenant}, {"meta": {"user_id": USER_B}}):
        response = await s.tank.post(PATH + "/control", headers=s.headers(), json={"control": "off", **injected})
        assert response.status_code in (400, 403, 422)
        assert await s.snapshot() == before
    headers = s.headers()
    headers["X-Tervory-User"] = USER_B
    response = await s.tank.post(PATH + "/control", headers=headers, json={"control": "off"})
    assert response.status_code in (401, 403)
    assert await s.snapshot() == before
    assert (await s.tank.get(PATH)).status_code in (401, 403)
    assert await s.snapshot() == before


@pytest.mark.parametrize("fault", ["missing", "wrong-key", "audience", "tenant", "method", "target", "body", "expired", "future"])
@pytest.mark.asyncio
async def test_product_assertion_rejections_do_not_mutate(radix_stack, fault):
    s = radix_stack
    await owner_record(s)
    before = await s.snapshot()
    body = b'{"control":"off"}'
    actor = SignedUser(s.memory.other_tenant if fault == "tenant" else s.memory.tenant, USER_A, "member")
    assertion = sign_assertion("tiger" if fault == "audience" else "radix", actor,
        "GET" if fault == "method" else "POST", PATH if fault == "target" else PATH + "/control",
        b"{}" if fault == "body" else body, key="placeholder-wrong-key" if fault == "wrong-key" else s.memory.key,
        now=int(time.time()) + (60 if fault == "future" else -120 if fault == "expired" else 0))
    headers = {"X-Tank-Key": s.memory.key, "X-Tervory-Tenant": s.memory.tenant, "X-Tervory-User": USER_A,
               "Content-Type": "application/json"}
    if fault != "missing":
        headers[HEADER] = assertion
    response = await s.product.post(PATH + "/control", headers=headers, content=body)
    assert response.status_code in (401, 403), response.text
    assert await s.snapshot() == before


@pytest.mark.asyncio
async def test_nonce_replay_after_restart_and_forget(radix_stack):
    s = radix_stack
    record = await owner_record(s)
    method, path, headers, body = s.forwarded[0]
    response = await s.tank.post(PATH + "/forget", headers=s.headers(), json={"memory_id": record})
    assert response.status_code == 200
    before = await s.snapshot()
    s.room.app.state.product_nonce_stores = {"radix": PostgresNonces(s.pool, "radix")}
    replay = await s.product.request(method, path, headers=headers, content=body)
    assert replay.status_code == 401
    assert await s.snapshot() == before
    body = json.dumps({"control": "view"}).encode()
    headers[HEADER.lower()] = sign_assertion("radix", SignedUser(s.memory.tenant, USER_A, "member"),
                                            "POST", PATH + "/control", body, key=s.memory.key)
    responses = await asyncio.gather(*[s.product.post(PATH + "/control", headers=headers, content=body) for _ in range(2)])
    assert sorted(r.status_code for r in responses) == [200, 401]


@pytest.mark.asyncio
async def test_owner_off_does_not_change_colleague(radix_stack):
    s = radix_stack
    await owner_record(s)
    response = await s.tank.post(PATH + "/control", headers=s.headers(), json={"control": "off"})
    assert response.status_code == 200
    await s.memory.records.tick()
    owner = await s.tank.get(PATH, headers=s.headers())
    other = await s.tank.get(PATH, headers=s.headers(USER_B))
    assert owner.status_code == other.status_code == 200
    assert owner.json() == {"memories": [], "memory_control": "off"}
    assert other.json()["memory_control"] != "off"
    assert other.json()["memories"] == []


@pytest.mark.parametrize("kind", ["radix.site_scan", "radix.finding", "radix.fix", "radix.accepted_risk",
    "radix.false_positive", "radix.correction", "radix.receipt", "radix.task", "radix.memory_control"])
@pytest.mark.asyncio
async def test_personal_kind_has_no_unowned_escape(radix_stack, kind):
    s = radix_stack
    await owner_record(s)
    before = await s.snapshot()
    response = await s.memory.http.post("/memories", headers={"X-Tank-Key": s.memory.key}, json={
        "agent": "radix", "tenant_id": s.memory.tenant, "text": "placeholder-unowned", "kind": kind,
        "source": "placeholder-unowned", "meta": {}})
    assert response.status_code in (401, 403, 422)
    assert await s.snapshot() == before


@pytest.mark.asyncio
async def test_sql_candidates_are_scoped_before_vector(radix_stack, monkeypatch):
    s = radix_stack
    owner = await owner_record(s)
    other = await s.tank.post(PATH + "/control", headers=s.headers(USER_B), json={"control": "view"})
    assert other.status_code == 200
    foreign = other.json()["id"]
    await s.memory.records.tick()
    observed = []
    search = s.memory.records.index.search

    def observe(*args, **kwargs):
        observed.append(kwargs.get("allowed_ids"))
        return search(*args, **kwargs)

    monkeypatch.setattr(s.memory.records.index, "search", observe)
    response = await s.tank.get(PATH, headers=s.headers())
    assert response.status_code == 200
    assert observed and all(ids is not None and owner in ids and foreign not in ids for ids in observed)
    observed.clear()
    response = await s.tank.get(PATH, headers=s.headers(USER_C, s.memory.other_tenant))
    assert response.status_code == 200 and response.json()["memories"] == []
    assert observed == [], "empty SQL scope must not invoke vector search"


@pytest.mark.asyncio
async def test_product_memory_path_under_restricted_database_role(radix_stack, monkeypatch):
    s = radix_stack
    owner = await owner_record(s)
    records = s.memory.records
    admin = records.pool
    schema = records.schema("radix")
    role = "placeholder_radix_" + uuid.uuid4().hex
    restricted = None
    await admin.execute(f"CREATE ROLE {role} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE")
    try:
        from hermes.user_assertion import PostgresNonces
        await PostgresNonces(admin, schema.removeprefix("agent_")).setup()
        # Match the provisioned role, only in its own disposable product schema.
        await admin.execute(f"GRANT USAGE, CREATE ON SCHEMA {schema} TO {role}")
        await admin.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {role}")
        restricted = await asyncpg.create_pool(os.environ["MEMORY_TEST_DATABASE_URL"], min_size=1, max_size=1,
                                              server_settings={"role": role})
        identity = await restricted.fetchrow("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
        assert identity["current_user"] == role and not identity["rolsuper"] and not identity["rolbypassrls"]
        monkeypatch.setattr(records, "pool", restricted)
        response = await s.tank.get(PATH, headers=s.headers(), params={"memory_id": owner})
        assert response.status_code == 200
        before = await s.snapshot()
        response = await s.tank.post(PATH + "/forget", headers=s.headers(USER_B), json={"memory_id": owner})
        assert response.status_code in (403, 404)
        assert await s.snapshot() == before
        response = await s.tank.post(PATH + "/forget", headers=s.headers(), json={"memory_id": owner})
        assert response.status_code == 200
    finally:
        monkeypatch.setattr(records, "pool", admin)
        if restricted:
            await restricted.close()
        await admin.execute(f"DROP OWNED BY {role}")
        await admin.execute(f"DROP ROLE {role}")


def test_brain_deployment_remains_opt_in():
    import yaml
    services = yaml.safe_load((ROOT / "agents/radix/docker-compose.yml").read_text())["services"]
    brains = [value for name, value in services.items() if "brain" in name]
    assert brains and all(value.get("profiles") for value in brains)
    for value in services.values():
        assert "RADIX_BRAIN_ENABLED:-true" not in json.dumps(value)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("RADIX_MEMORY_ENABLED", "true")
    monkeypatch.setenv("RADIX_BRAIN_ENABLED", "true")


@pytest.mark.asyncio
async def test_worker_first_repeat_changed_accounting(radix_stack, enabled):
    s = radix_stack
    first = await scan(s)
    receipt = first["receipt"]
    assert receipt["status"] == "completed"
    assert (receipt["cost_usd"], receipt["tokens_in"], receipt["tokens_out"]) == (.05, 10, 3)
    assert len(s.provider_calls) == 1
    assert [r.url.path for r in s.task_requests] == ["/v1/agents/radix/delegate", "/v1/agents/radix/tasks"]
    assert len(s.brain_requests) == 1
    assert receipt["tank_receipt"]["room"] == "radix"
    assert receipt["tank_receipt"]["region"] == "us-east"
    assert receipt["tank_receipt"]["outcome"] == "delivered"
    assert [step["action"] for step in receipt["steps"]] == ["code_skill", "recall", "brain_route", "remember"]
    assert first["findings"] and receipt["result"]["findings"]
    second = await scan(s)
    assert second["scan_id"] != first["scan_id"]
    assert second["receipt"]["answered_from_memory"]
    assert (second["receipt"]["cost_usd"], second["receipt"]["tokens_in"], second["receipt"]["tokens_out"]) == (0, 0, 0)
    assert second["receipt"]["would_have_cost"] == .05
    assert len(s.provider_calls) == 1
    third = await scan(s, changed=True)
    assert not third["receipt"]["answered_from_memory"] and len(s.provider_calls) == 2
    assert (third["receipt"]["cost_usd"], third["receipt"]["tokens_in"], third["receipt"]["tokens_out"]) == (.05, 10, 3)
    ledger = await s.pool.fetch("SELECT cost_usd,tokens_in,tokens_out FROM tank.ledger WHERE tenant_id=$1 AND task_type='agent.radix.think'", uuid.UUID(s.memory.tenant))
    assert len(ledger) == len(s.provider_calls) == 2
    assert sum(float(row["cost_usd"]) for row in ledger) == .10
    rows = await s.pool.fetch("SELECT user_id,receipt FROM agent_radix.task_context")
    assert len(rows) == 3 and all(row["user_id"] == USER_A and row["receipt"] for row in rows)
    print("Radix recorded fixture: first $0.05 10/3 tokens 1 provider; repeat $0 0/0 tokens 0 providers; changed $0.05 10/3 tokens 1 provider")


@pytest.mark.asyncio
async def test_repeat_misses_other_user_and_tenant(radix_stack, enabled):
    s = radix_stack
    await scan(s)
    b = await scan(s, user=USER_B)
    c = await scan(s, user=USER_C, tenant=s.memory.other_tenant)
    assert not b["receipt"]["answered_from_memory"] and not c["receipt"]["answered_from_memory"]
    assert len(s.provider_calls) == 3
    assert b["receipt"]["user_id"] == USER_B and c["receipt"]["tenant_id"] == s.memory.other_tenant


@pytest.mark.asyncio
async def test_default_off_and_unsigned_plain_scan(radix_stack, monkeypatch):
    s = radix_stack
    monkeypatch.delenv("RADIX_MEMORY_ENABLED", raising=False)
    monkeypatch.delenv("RADIX_BRAIN_ENABLED", raising=False)
    result = await scan(s)
    assert "receipt" not in result and not s.memory.calls and not s.provider_calls
    assert await s.pool.fetchval("SELECT count(*) FROM agent_radix.task_context") == 0
    monkeypatch.setenv("RADIX_MEMORY_ENABLED", "true")
    monkeypatch.setenv("RADIX_BRAIN_ENABLED", "true")
    import base64
    response = await s.product.post("/jobs", headers={"X-Tank-Key": s.memory.key}, json={
        "tenant_id": s.memory.tenant, "kind": "scan", "input": {"source": "b64:" + base64.b64encode(archive_source()).decode(), "ref": "placeholder.tar", "user_id": USER_A}})
    assert response.status_code == 201
    result = await work_next(s)
    assert "receipt" not in result and not s.memory.calls and not s.provider_calls
    assert await s.pool.fetchval("SELECT count(*) FROM agent_radix.task_context") == 0


@pytest.mark.asyncio
async def test_code_first_and_incomplete_scan_never_uses_brain(radix_stack, enabled, monkeypatch):
    s = radix_stack
    result = await scan(s, clean=True)
    assert result["scan_complete"] and result["findings"] == []
    assert result["receipt"]["paid_calls"] == 0 and not s.provider_calls
    monkeypatch.setenv("CHECKOV_BIN", "/placeholder/missing-checkov")
    incomplete = await scan(s, changed=True)
    assert not incomplete["scan_complete"]
    assert incomplete["receipt"]["status"] == "incomplete" and not s.provider_calls
    repeat = await scan(s, changed=True)
    assert not repeat["receipt"]["answered_from_memory"] and not s.provider_calls


@pytest.mark.parametrize("entry", ["tank", "room"])
@pytest.mark.asyncio
async def test_correction_and_forget_invalidate_durable_answers(radix_stack, enabled, entry):
    s = radix_stack
    first = await scan(s)
    memory_id = next(step["memory_id"] for step in first["receipt"]["steps"] if step["action"] == "remember")
    edited = await memory_control(s, entry, "/edit", {"memory_id": memory_id, "text": "placeholder-correction: the parameter is already bound"})
    assert edited.status_code == 200, edited.text
    corrected = await scan(s)
    assert corrected["receipt"]["paid_calls"] == 0 and len(s.provider_calls) == 1
    assert "placeholder-correction" in json.dumps(corrected["receipt"]["result"])
    outsider = await scan(s, user=USER_B)
    assert "placeholder-correction" not in json.dumps(outsider)
    assert len(s.provider_calls) == 2
    forgotten = await memory_control(s, entry, "/forget", {"memory_id": memory_id})
    assert forgotten.status_code == 200
    after = await scan(s)
    assert "placeholder-correction" not in json.dumps(after) and not after["receipt"]["answered_from_memory"]
    assert len(s.provider_calls) == 3
    rows = await s.memory.records.list("radix", s.memory.tenant, user_id=USER_A)
    assert all("placeholder-correction" not in json.dumps(row) for row in rows)


@pytest.mark.parametrize("entry", ["tank", "room"])
@pytest.mark.asyncio
async def test_memory_off_applies_to_only_one_worker_owner(radix_stack, enabled, entry):
    s = radix_stack
    await scan(s)
    await scan(s, user=USER_B)
    response = await memory_control(s, entry, "/control", {"control": "off"})
    assert response.status_code == 200
    before = len(s.memory.calls)
    owner = await scan(s)
    calls = s.memory.calls[before:]
    assert not owner["receipt"]["answered_from_memory"] and owner["receipt"]["memory_control"] == "off"
    assert all(path != "/recall" and method != "POST" for method, path in calls)
    other = await scan(s, user=USER_B)
    assert other["receipt"]["answered_from_memory"] and len(s.provider_calls) == 3


@pytest.mark.parametrize("phase", ["list", "recall", "remember"])
@pytest.mark.asyncio
async def test_memory_outage_and_paid_checkpoint_retry(radix_stack, enabled, phase):
    import httpx
    s = radix_stack
    transport = s.memory.http._transport
    async def edge(request):
        fail = ((phase == "list" and request.method == "GET") or
                (phase == "recall" and request.url.path == "/recall") or
                (phase == "remember" and request.method == "POST" and request.url.path == "/memories"))
        if fail:
            return httpx.Response(503, json={"detail": "placeholder memory unavailable"})
        return await transport.handle_async_request(request)
    s.memory.http._transport = httpx.MockTransport(edge)
    try:
        job = await submit_scan(s)
        result = await work_next(s)
        assert result["receipt"]["memory_unavailable"] and result["receipt"]["cost_usd"] == .05
        assert len(s.provider_calls) == 1
        await s.pool.execute("UPDATE agent_radix.jobs SET status='queued',run_at=now() WHERE id=$1", job)
        again = await work_next(s)
        assert again["receipt"] == result["receipt"] and len(s.provider_calls) == 1
    finally:
        s.memory.http._transport = transport


@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.asyncio
async def test_memory_auth_failure_never_serves_private_cache(radix_stack, enabled, status):
    import httpx
    s = radix_stack
    await scan(s)
    transport = s.memory.http._transport
    s.memory.http._transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"detail": "placeholder scope refused"}))
    try:
        await submit_scan(s)
        result = await work_next(s, require_done=False)
        assert result["status"] != "done" and result["result"] is None
        assert len(s.provider_calls) == 1
    finally:
        s.memory.http._transport = transport


@pytest.mark.asyncio
async def test_concurrent_runs_share_owner_cache_and_keep_two_receipts(radix_stack, enabled):
    s = radix_stack
    a, b = await submit_scan(s), await submit_scan(s)
    results = await asyncio.gather(work_next(s), work_next(s))
    assert {item["scan_id"] for item in results} == {str(a), str(b)}
    assert sorted(item["receipt"]["paid_calls"] for item in results) == [0, 1]
    assert len(s.provider_calls) == 1
    assert await s.pool.fetchval("SELECT count(*) FROM agent_radix.task_context WHERE receipt IS NOT NULL") == 2


@pytest.mark.asyncio
async def test_provider_failure_is_unknown_and_never_recharged(radix_stack, enabled):
    s = radix_stack
    s.network.fail_provider = True
    job = await submit_scan(s)
    result = await work_next(s)
    assert result["receipt"]["status"] == "failed" and result["receipt"]["cost_usd"] is None
    assert result["receipt"]["result"]["status"] == "unknown"
    assert result["receipt"]["tank_receipt"]["cost_status"] == "unknown_upper_bound"
    assert result["receipt"]["tank_receipt"]["cost_usd"] > 0
    assert "none-reported" not in json.dumps(result)
    calls = len(s.provider_calls)
    await s.pool.execute("UPDATE agent_radix.jobs SET status='queued',run_at=now() WHERE id=$1", job)
    await work_next(s)
    assert len(s.provider_calls) == calls


@pytest.mark.asyncio
async def test_existing_squad_and_domain_authorization_are_preserved(radix_stack, enabled):
    s = radix_stack
    response = await s.tank.post("/v1/radix/passive/scans", headers=s.headers(), json={
        "tenant_id": s.memory.tenant, "target": "https://placeholder.invalid/", "artifact": "commit:" + "0" * 40})
    assert response.status_code in (401, 403)
    await s.pool.execute("DELETE FROM tank.tenant_squad WHERE tenant_id=$1", uuid.UUID(s.memory.tenant))
    response = await s.tank.post("/v1/command/radix/repo/scan", headers=s.headers(), json={"attachment_id": str(uuid.uuid4())})
    assert response.status_code == 403
    assert not s.forwarded and not s.provider_calls


@pytest.mark.asyncio
async def test_post_payment_auth_failure_retry_uses_checkpoint(radix_stack, enabled):
    import httpx
    s = radix_stack
    transport = s.memory.http._transport
    async def edge(request):
        if request.method == "POST" and request.url.path == "/memories":
            return httpx.Response(403, json={"detail": "placeholder signed user denied"})
        return await transport.handle_async_request(request)
    s.memory.http._transport = httpx.MockTransport(edge)
    try:
        job = await submit_scan(s)
        failed = await work_next(s, require_done=False)
        assert failed["status"] != "done" and failed["result"] is None
        assert len(s.provider_calls) == 1
        row = await s.pool.fetchrow("SELECT execution,receipt FROM agent_radix.task_context WHERE job_id=$1", job)
        assert row["execution"] and row["receipt"] is None
    finally:
        s.memory.http._transport = transport
    await s.pool.execute("UPDATE agent_radix.jobs SET run_at=now() WHERE id=$1", job)
    recovered = await work_next(s)
    assert recovered["receipt"]["status"] == "completed" and recovered["receipt"]["cost_usd"] == .05
    assert len(s.provider_calls) == 1


@pytest.mark.asyncio
async def test_job_receipt_is_owner_scoped_through_tank(radix_stack, enabled):
    s = radix_stack
    result = await scan(s)
    url = "/v1/command/radix/repo/findings"
    own = await s.tank.get(url, headers=s.headers(), params={"scan_id": result["scan_id"]})
    assert own.status_code == 200 and own.json()["scan_complete"]
    before = len(s.provider_calls)
    for user, tenant in ((USER_B, s.memory.tenant), (USER_C, s.memory.other_tenant)):
        denied = await s.tank.get(url, headers=s.headers(user, tenant), params={"scan_id": result["scan_id"]})
        assert denied.status_code == 404
        assert "placeholder review" not in denied.text and USER_A not in denied.text
    assert len(s.provider_calls) == before


@pytest.mark.asyncio
async def test_tank_receipt_view_matches_worker(radix_stack, enabled):
    s = radix_stack
    result = await scan(s)
    own = await s.tank.get("/v1/command/radix/repo/findings", headers=s.headers(),
                           params={"scan_id": result["scan_id"]})
    assert own.status_code == 200
    assert own.json()["receipt"] == result["receipt"]


@pytest.mark.asyncio
async def test_uncertain_execution_is_never_reissued(radix_stack, enabled):
    s = radix_stack
    job = await submit_scan(s)
    await s.pool.execute("UPDATE agent_radix.task_context SET stage='executing' WHERE job_id=$1", job)
    result = await work_next(s)
    assert result["receipt"]["status"] == "uncertain"
    assert result["receipt"]["cost_usd"] is None and result["receipt"]["paid_calls"] is None
    assert not s.provider_calls


@pytest.mark.parametrize("operation", ["tasks", "delegate"])
@pytest.mark.parametrize("fault", ["missing", "wrong-key", "user", "tenant", "target", "expired", "body", "run", "region", "other-room", "off", "squad"])
@pytest.mark.asyncio
async def test_private_task_boundary_denials(radix_stack, enabled, monkeypatch, operation, fault):
    s = radix_stack
    path = "/v1/agents/radix/" + operation
    body = {"tenant_id": s.memory.tenant, "user_id": USER_A, "run_id": str(uuid.uuid4())}
    body.update({"messages": [{"role": "user", "content": "placeholder"}]} if operation == "tasks" else
                {"task_key": "radix.site_risk", "input": {}, "recall": []})
    actor = SignedUser(s.memory.tenant, USER_A, "member")
    if fault == "user": body["user_id"] = USER_B
    if fault == "tenant": body["tenant_id"] = s.memory.other_tenant
    if fault == "other-room":
        # Exercise a registered, enabled foreign room, not a missing Base route.
        # Base's own integrated task endpoint correctly rejects at authentication
        # (401); its absence previously yielded the generic unavailable-room 403.
        path = path.replace("/radix/", "/tiger/")
        monkeypatch.setenv("TANK_KEY_TIGER", "placeholder-foreign-room-key")
        monkeypatch.setenv("TIGER_BRAIN_ENABLED", "true")
    if fault == "off": monkeypatch.delenv("RADIX_BRAIN_ENABLED", raising=False)
    if fault == "squad":
        await s.pool.execute("DELETE FROM tank.tenant_squad WHERE tenant_id=$1", uuid.UUID(s.memory.tenant))
    raw = json.dumps(body).encode()
    headers = {"X-Tank-Key": s.memory.key, "Content-Type": "application/json", "X-Home-Region": "za" if fault == "region" else "us-east"}
    headers[HEADER] = sign_assertion("radix", actor, "POST", path + ("/wrong" if fault == "target" else ""), raw,
                                   key="placeholder-wrong-key" if fault == "wrong-key" else s.memory.key,
                                   now=int(time.time()) - 120 if fault == "expired" else None)
    if fault == "missing": headers.pop(HEADER)
    if fault == "body":
        body["messages" if operation == "tasks" else "input"] = [{"role": "user", "content": "altered"}] if operation == "tasks" else {"altered": True}
        raw = json.dumps(body).encode()
    if fault == "run":
        body["run_id"] = str(uuid.uuid4())
        raw = json.dumps(body).encode()
    before = await s.snapshot()
    response = await s.tank.post(path, headers=headers, content=raw)
    expected = 409 if fault == "off" else 403 if fault in {"user", "region", "squad"} else 401
    assert response.status_code == expected, response.text
    assert await s.snapshot() == before and not s.provider_calls and not s.brain_requests
    if fault == "other-room":
        assert response.json() == {"detail": "Owning room key required."}
        # Even the foreign service key cannot authorize a Radix user assertion
        # for Tiger; audience verification must fail before any task or spend.
        headers["X-Tank-Key"] = "placeholder-foreign-room-key"
        headers[HEADER] = sign_assertion("radix", actor, "POST", path, raw,
                                       key="placeholder-foreign-room-key")
        response = await s.tank.post(path, headers=headers, content=raw)
        assert response.status_code == 401, response.text
        assert response.json() == {"detail": "Signed user required for memory"}
        assert await s.snapshot() == before and not s.provider_calls and not s.brain_requests


@pytest.mark.parametrize("fault", ["missing", "service-key", "wrong-key", "user", "tenant", "target", "expired", "run", "region", "off"])
@pytest.mark.asyncio
async def test_private_service_requires_signed_scoped_actor(radix_stack, enabled, monkeypatch, fault):
    import httpx
    s = radix_stack
    tenant = s.memory.other_tenant if fault == "tenant" else s.memory.tenant
    user = USER_B if fault == "user" else USER_A
    path = f"/tasks?tenant_id={tenant}&user_id={user}"
    body = {"task_key": "radix.site_risk", "input": {}, "recall": [], "run_id": str(uuid.uuid4())}
    raw = json.dumps(body).encode()
    headers = {"X-Tank-Key": "placeholder-wrong-key" if fault == "service-key" else s.memory.key,
               "Content-Type": "application/json", "X-Home-Region": "za" if fault == "region" else "us-east"}
    headers[HEADER] = sign_assertion("radix", SignedUser(s.memory.tenant, USER_A, "member"), "POST",
                                   path + ("&altered=1" if fault == "target" else ""), raw,
                                   key="placeholder-wrong-key" if fault == "wrong-key" else s.memory.key,
                                   now=int(time.time()) - 120 if fault == "expired" else None)
    if fault == "missing": headers.pop(HEADER)
    if fault == "off": monkeypatch.delenv("RADIX_BRAIN_ENABLED", raising=False)
    if fault == "run":
        body["run_id"] = str(uuid.uuid4())
        raw = json.dumps(body).encode()
    before = await s.snapshot()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(s.room.brain.app), base_url="http://placeholder") as client:
        response = await client.post(path, headers=headers, content=raw)
    expected = 409 if fault == "off" else 403 if fault in {"user", "region"} else 401
    assert response.status_code == expected, response.text
    assert await s.snapshot() == before and not s.provider_calls and not s.task_requests


@pytest.mark.asyncio
async def test_private_task_replay_and_real_receipt(radix_stack, enabled):
    s = radix_stack
    result = await scan(s)
    receipt = result["receipt"]["tank_receipt"]
    from chassis.task_contract import paid_identity
    assert receipt["task_id"] == paid_identity(s.memory.tenant, USER_A, result["scan_id"])
    raw = await s.pool.fetchval("SELECT receipt FROM tank.agent_receipts WHERE tenant_id=$1 AND ledger_id=$2",
                               uuid.UUID(s.memory.tenant), uuid.UUID(receipt["ledger_id"]))
    assert (json.loads(raw) if isinstance(raw, str) else raw) == receipt
    before = await s.snapshot()
    for request in list(s.task_requests):
        response = await s.tank.post(request.url.path, headers=dict(request.headers), content=request.content)
        assert response.status_code == 401
    request = s.brain_requests[0]
    import httpx
    async with httpx.AsyncClient(transport=httpx.ASGITransport(s.room.brain.app), base_url="http://placeholder") as client:
        response = await client.post(request.url.raw_path.decode(), headers=dict(request.headers), content=request.content)
    assert response.status_code == 401
    assert await s.snapshot() == before and len(s.provider_calls) == 1


@pytest.mark.asyncio
async def test_private_task_keeps_paid_admission(radix_stack, enabled):
    s = radix_stack
    await s.pool.execute("UPDATE tank.paid_step_settings SET mode='ask' WHERE tenant_id=$1", uuid.UUID(s.memory.tenant))
    result = await scan(s)
    assert result["receipt"]["status"] == "failed" and not s.provider_calls
    assert not await s.pool.fetchval("SELECT 1 FROM tank.agent_receipts WHERE tenant_id=$1", uuid.UUID(s.memory.tenant))
    assert await s.pool.fetchval("SELECT count(*) FROM tank.paid_step_approvals WHERE tenant_id=$1", uuid.UUID(s.memory.tenant)) == 1
