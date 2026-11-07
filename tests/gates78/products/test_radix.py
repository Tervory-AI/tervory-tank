"""Radix acceptance contribution. BLOCKED cases deliberately fail, never skip.

The control scenarios below are executable after Head integrates the recorded
runtime dependency. Gate 8 has no shipped paid task entrypoint; its explicit
blockers prevent the manifest from falsely certifying helper-only unit tests.
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
    PATH, ROOT, USER_A, USER_B, USER_C, blocked_task_contract, owner_record,
    radix_runtime as radix_runtime, radix_sql_pool as radix_sql_pool,
    radix_stack as radix_stack,
)


@pytest.mark.asyncio
async def test_owner_controls_use_signed_route_and_real_hermes(radix_stack):
    s = radix_stack
    record = await owner_record(s)
    assert s.forwarded and HEADER.lower() in s.forwarded[0][2]
    assert s.memory.calls, "the shipped MemoryClient never reached Hermes"
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
@pytest.mark.parametrize("action", ["view", "edit", "forget", "off"])
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
        await admin.execute(f"GRANT USAGE ON SCHEMA {schema} TO {role}")
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


@pytest.mark.parametrize("requirement", [
    "G7.owner_crud-recall-list-publish",
    "G8.default_off", "G8.task_path", "G8.free_first", "G8.exact_repeat", "G8.misses",
    "G8.correction", "G8.forget", "G8.memory_off", "G8.outage", "G8.auth_not_outage",
    "G8.receipts", "G8.retry_concurrency", "G8.product_regressions",
])
def test_unavailable_task_path_blocks_acceptance(requirement):
    blocked_task_contract(requirement)
