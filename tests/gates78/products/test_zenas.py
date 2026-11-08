"""Gate 7/8 Zenas acceptance at real legal and control HTTP entry points.

Missing runtime is BLOCKED/FAIL, never skipped and never supplied by a local
overlay. Fixture prices describe the external gateway boundary, not billing.
"""
import asyncio
import base64
import importlib
import json
import os
import subprocess
import sys
import time
from uuid import uuid4

import asyncpg
import httpx
import pytest
from zenas_harness import (
    FIXTURE_COST,
    FIXTURE_INPUT,
    FIXTURE_OUTPUT,
    QUOTE,
    ROOT,
    SOURCE_SHA,
    USER_A,
    USER_B,
    USER_C,
    WORKSPACE_KEY,
    receipt,
    require_runtime,
    zenas,
)

__all__ = ['zenas']


async def first_answer(entry, **kwargs):
    response = await entry.answer(**kwargs)
    assert response.status_code == 200, response.text
    assert response.json().get("ok") and response.json().get("delivered")
    return response


async def owned_result(entry, user=USER_A, tenant=None):
    await first_answer(entry, user=user, tenant=tenant)
    rows = await entry.records(user, tenant)
    result = next((row for row in rows if row["kind"] == "zenas.result"), None)
    assert result is not None, "The actual legal path must remember its successful result"
    return result


def test_runtime_dependency_is_integrated():
    module = require_runtime()
    paths = {route.path for route in module.app.routes if hasattr(route, "path")}
    assert {"/answers", "/drafts", "/memory/records", "/memory/edit", "/memory/forget", "/memory/switch"} <= paths


@pytest.mark.asyncio
async def test_owner_crud_through_legal_and_memory_handlers(zenas):
    row = await owned_result(zenas)
    assert (row["meta"].get("user_id") or row["meta"].get("user")) == USER_A
    got = await zenas.request("GET", "/memory/records/"+row["id"])
    assert got.status_code == 200 and row["id"] in got.text
    corrected = {"memo": {"text": "placeholder owner-corrected commercial terms"}}
    edit = await zenas.request("POST", "/memory/edit", body={
        "tenant_id": zenas.stack.tenant, "memory_id": row["id"], "value": corrected})
    assert edit.status_code == 200 and edit.json()["ok"]
    current = await zenas.records()
    correction = next(r for r in current if r["kind"] == "zenas.correction")
    assert "placeholder owner-corrected" in json.dumps(correction)
    forgot = await zenas.request("POST", "/memory/forget", body={
        "tenant_id": zenas.stack.tenant, "memory_id": correction["id"]})
    assert forgot.status_code == 200
    assert correction["id"] not in {r["id"] for r in await zenas.records()}


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["same_tenant", "other_tenant"])
async def test_foreign_scope_cannot_read_or_mutate(zenas, scope):
    row = await owned_result(zenas)
    user = USER_B if scope == "same_tenant" else USER_C
    tenant = zenas.stack.tenant if scope == "same_tenant" else zenas.stack.other_tenant
    before = await zenas.snapshot()
    rows = await zenas.records(user, tenant)
    assert row["id"] not in {r["id"] for r in rows}
    assert "placeholder legal party" not in json.dumps(rows)
    got = await zenas.request("GET", "/memory/records/"+row["id"], user=user, tenant=tenant)
    assert got.status_code in {403, 404}
    for path, values in [("edit", {"value": "placeholder denied mutation"}), ("forget", {})]:
        response = await zenas.request("POST", "/memory/"+path, user=user, tenant=tenant,
            body={"tenant_id": tenant, "memory_id": row["id"], **values})
        assert response.status_code in {403, 404}
    publish = await zenas.request("POST", "/memory/publish", user=user, tenant=tenant,
        body={"tenant_id": tenant, "memory_id": row["id"]})
    assert publish.status_code in {403, 404, 405}
    assert await zenas.snapshot() == before


@pytest.mark.asyncio
async def test_empty_tenant_wide_declaration_does_not_permit_unowned_rows(zenas):
    memory = importlib.import_module("agents.zenas.gates_memory")
    assert memory.TENANT_WIDE == frozenset()
    response = await zenas.stack.http.post("/memories", headers={"X-Tank-Key": zenas.stack.key}, json={
        "tenant_id": zenas.stack.tenant, "kind": memory.RESULT, "text": "placeholder unowned legal answer",
        "source": "placeholder-gate78", "meta": {"tenant_wide": True}})
    assert response.status_code in {401, 403, 422}
    assert not await zenas.stack.client(USER_A).records(zenas.stack.tenant)
    personal = await owned_result(zenas)
    assert personal["id"] not in {r["id"] for r in await zenas.records(USER_B)}


@pytest.mark.asyncio
async def test_verified_owner_cannot_be_replaced_by_body_or_headers(zenas):
    await owned_result(zenas)
    before = await zenas.snapshot()
    spoof = await zenas.request("POST", "/memory/switch", body={
        "tenant_id": zenas.stack.tenant, "user_id": USER_B, "enabled": False})
    assert spoof.status_code == 403
    headers = zenas.headers()
    headers["X-Tervory-User"] = USER_B
    forged = await zenas.request("GET", "/memory/records", headers=headers)
    assert forged.status_code in {401, 403}
    assert await zenas.snapshot() == before


@pytest.mark.asyncio
async def test_real_signin_and_shared_assertion_bind_user_tenant_and_role(zenas):
    await owned_result(zenas)
    assert zenas.provider.calls, "Local signed issuer discovery/JWKS must really be verified"
    assert any("x-tervory-user-assertion" in headers for _, _, _, headers in zenas.raw_assertions)
    assertion = next(headers['x-tervory-user-assertion'] for _,_,_,headers in zenas.raw_assertions
                     if 'x-tervory-user-assertion' in headers)
    encoded = assertion.split('.')[0]
    claims = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
    assert claims['tenant_id'] == zenas.stack.tenant and claims['user_id'] == USER_A
    assert claims['role'] == 'org:admin' and claims['aud'] == 'zenas'

    # Lifecycle HMAC alone is deliberately not sufficient after fixed core #765.
    from agents.zenas.request_signing import sign_request
    raw = json.dumps({"tenant_id": zenas.stack.tenant, "enabled": False}).encode()
    lifecycle = sign_request(key=zenas.stack.key, method="POST", path="/memory/switch",
                            tenant_id=zenas.stack.tenant, user_id=USER_A, body=raw)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=zenas.room.app), base_url="http://room") as client:
        response = await client.post("/memory/switch", content=raw, headers={**lifecycle, "Content-Type": "application/json"})
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("flaw", ["missing", "key", "audience", "tenant", "method", "target", "body", "expired", "future"])
async def test_invalid_product_assertions_fail_closed(zenas, flaw):
    from chassis.user_assertion import HEADER, SignedUser, sign_assertion
    before = await zenas.snapshot()
    body = json.dumps({"tenant_id": zenas.stack.tenant, "enabled": False}, separators=(",", ":")).encode()
    actor = SignedUser(zenas.stack.tenant, USER_A, "member")
    params = {"key": zenas.stack.key, "now": int(time.time())}
    product, method, target, signed = "zenas", "POST", "/memory/switch", body
    if flaw == "key": params["key"] = "placeholder-wrong-signing-key"
    if flaw == "audience": product = "trigger"
    if flaw == "tenant": actor = SignedUser(zenas.stack.other_tenant, USER_A, "member")
    if flaw == "method": method = "GET"
    if flaw == "target": target = "/memory/forget"
    if flaw == "body": signed = b'{"placeholder":"tampered"}'
    if flaw == "expired": params["now"] -= 61
    if flaw == "future": params["now"] += 1
    assertion = sign_assertion(product, actor, method, target, signed, **params)
    headers = {"X-Tank-Key": zenas.stack.key, HEADER: assertion, "Content-Type": "application/json"}
    if flaw == "missing": headers.pop(HEADER)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=zenas.room.app), base_url="http://room") as client:
        response = await client.post("/memory/switch", content=body, headers=headers)
    assert response.status_code == 401
    assert await zenas.snapshot() == before


@pytest.mark.asyncio
async def test_nonce_replay_across_workers_cannot_restore_forgotten_data(zenas):
    from chassis.user_assertion import HEADER, SignedUser, sign_assertion
    row = await owned_result(zenas)
    body = json.dumps({"tenant_id": zenas.stack.tenant, "memory_id": row["id"]}, separators=(",", ":")).encode()
    token = sign_assertion("zenas", SignedUser(zenas.stack.tenant, USER_A, "member"), "POST", "/memory/forget", body,
                           key=zenas.stack.key)
    headers = {"X-Tank-Key": zenas.stack.key, HEADER: token, "Content-Type": "application/json"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=zenas.room.app), base_url="http://room") as client:
        first, duplicate = await asyncio.gather(*[client.post("/memory/forget", content=body, headers=headers) for _ in range(2)])
        assert sorted([first.status_code, duplicate.status_code]) == [200, 401]
        # New in-process nonce object simulates another worker/restart; SQL stays.
        zenas.room.app.state.product_nonce_stores = {}
        restarted = await client.post("/memory/forget", content=body, headers=headers)
        assert restarted.status_code == 401
    assert row["id"] not in {r["id"] for r in await zenas.records()}


@pytest.mark.asyncio
async def test_owner_sql_filter_precedes_vector_limit(zenas):
    a, b = zenas.stack.client(USER_A), zenas.stack.client(USER_B)
    for number in range(6):
        await b.remember(zenas.stack.tenant, f"placeholder foreign legal rule {number}", "zenas.fact", "placeholder-source")
    own = await a.remember(zenas.stack.tenant, "placeholder owner legal rule", "zenas.fact", "placeholder-source")
    await first_answer(zenas)
    hits = await a.recall(zenas.stack.tenant, "placeholder legal rule", limit=1)
    assert hits and hits[0]["id"] == own["id"]
    assert not await a.recall(zenas.stack.other_tenant, "placeholder legal rule", limit=1)
    assert all((row.get("meta") or {}).get("user_id") == USER_A for row in await zenas.records())


@pytest.mark.asyncio
async def test_restricted_database_role_keeps_same_scope(zenas):
    pool = zenas.stack.records.pool
    schema = zenas.stack.records.schema("zenas")
    role = "placeholder_zenas_" + uuid4().hex
    await pool.execute(f'CREATE ROLE "{role}" LOGIN PASSWORD \'placeholder\' NOSUPERUSER NOBYPASSRLS')
    try:
        await pool.execute(f'GRANT USAGE,CREATE ON SCHEMA "{schema}" TO "{role}"')
        await pool.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
        restricted = await asyncpg.create_pool(os.environ["MEMORY_TEST_DATABASE_URL"], user=role, password="placeholder", min_size=1,max_size=1)
        try:
            assert not await restricted.fetchval('SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user')
            zenas.stack.records.pool = restricted
            row = await owned_result(zenas)
            assert row["id"] not in {r["id"] for r in await zenas.records(USER_B)}
        finally:
            zenas.stack.records.pool = pool
            await restricted.close()
    finally:
        await pool.execute(f'DROP OWNED BY "{role}"')
        await pool.execute(f'DROP ROLE "{role}"')


@pytest.mark.asyncio
async def test_controls_need_identity_but_plain_authorised_ask_can_run(zenas):
    before = await zenas.snapshot()
    headers = {"X-Tank-Key": "placeholder-gate78-workspace-key"}
    control = await zenas.request("GET", "/memory/records", headers=headers)
    assert control.status_code in {401,403}
    plain = await zenas.request("POST", "/answers", headers=headers, body=zenas.body)
    assert plain.status_code == 200
    assert await zenas.snapshot() == before


@pytest.mark.asyncio
async def test_no_foreign_content_in_results_receipts_or_logs(zenas, caplog):
    secret = "placeholder-private-other-attorney-position"
    await zenas.stack.client(USER_B).remember(zenas.stack.tenant, secret, "zenas.position", "placeholder-source")
    response = await first_answer(zenas)
    assert secret not in response.text and secret not in caplog.text
    assert secret not in json.dumps(await zenas.records())
    assert zenas.stack.key not in response.text and zenas.stack.key not in caplog.text


@pytest.mark.asyncio
async def test_shipped_memory_adapter_uses_actual_hermes_contract(zenas):
    await owned_result(zenas)
    assert ("POST", "/memories") in zenas.stack.calls and ("GET", "/records") in zenas.stack.calls
    assert all(not path.startswith("/v1/memory") for _, path in zenas.stack.calls)
    assert type(zenas.room.app.state.memory).__module__ == "chassis.memory"


@pytest.mark.asyncio
async def test_unset_memory_and_brain_switches_add_no_work(zenas, monkeypatch):
    monkeypatch.delenv("ZENAS_MEMORY_ENABLED", raising=False)
    monkeypatch.delenv("ZENAS_BRAIN_ENABLED", raising=False)
    before = await zenas.snapshot()
    count = len(zenas.stack.calls)
    response = await first_answer(zenas)
    assert not response.json().get("memory_hit")
    assert not zenas.worker.calls and len(zenas.stack.calls) == count
    assert await zenas.snapshot() == before
    assert not importlib.import_module("agents.zenas.zenas_brain").brain_enabled()
    for filename in ("docker-compose.yml", "docker-compose.za.yml"):
        import yaml
        compose = yaml.safe_load((ROOT/"agents/zenas"/filename).read_text())
        room_env = compose['services']['agent-zenas']['environment']
        assert room_env['ZENAS_MEMORY_ENABLED'] == '${ZENAS_MEMORY_ENABLED:-false}'
        assert room_env['ZENAS_BRAIN_ENABLED'] == '${ZENAS_BRAIN_ENABLED:-false}'
        brains = [service for name,service in compose["services"].items() if "brain" in name]
        assert brains and all("brain" in service.get("profiles", []) for service in brains)


@pytest.mark.asyncio
async def test_actual_task_recall_receipt_then_remember_order(zenas,monkeypatch):
    monkeypatch.setenv("ZENAS_BRAIN_ENABLED","true")
    response = await first_answer(zenas)
    stages = [kind for kind,_ in zenas.events]
    assert "memory" in stages and "tank" in stages and stages.index("memory") < stages.index("tank")
    assert any(path == "/tasks" for path in zenas.worker.calls)
    last_tank = max(i for i,(kind,_) in enumerate(zenas.events) if kind == "tank")
    assert any(kind == "memory" and path == "/memories" for kind,path in zenas.events[last_tank+1:])
    bill = receipt(response)
    assert bill["cost_usd"] == len(zenas.model.calls)*FIXTURE_COST


@pytest.mark.asyncio
async def test_code_first_refusal_never_calls_brain_or_paid_gateway(zenas,monkeypatch):
    monkeypatch.setenv("ZENAS_BRAIN_ENABLED","true")
    response = await zenas.answer(changes={"question":"How can I defend a criminal prosecution?"})
    assert response.status_code in {200,403,422}
    assert not zenas.model.calls and not zenas.worker.calls


@pytest.mark.asyncio
async def test_exact_repeat_new_run_id_has_zero_actual_paid_calls(zenas):
    initial = await first_answer(zenas)
    count = len(zenas.model.calls)
    assert count > 0
    first = receipt(initial)
    again = await first_answer(zenas, run_id=str(uuid4()))
    bill = receipt(again)
    assert len(zenas.model.calls) == count
    assert again.json().get("memory_hit") or bill.get("answered_from_memory")
    assert bill["cost_usd"] == 0 and bill["tokens_in"] == bill["tokens_out"] == 0
    assert bill["would_have_cost"]["cost_usd"] == first["cost_usd"]
    assert again.json().get("memo") == initial.json().get("memo"), "Keep the legal-answer response contract on a hit"


@pytest.mark.asyncio
@pytest.mark.parametrize("change",["question","facts","jurisdiction","user","tenant"])
async def test_meaningful_changes_and_other_owners_do_not_hit(zenas,change):
    await first_answer(zenas)
    kwargs = {}
    if change == "question": kwargs["changes"] = {"question":"What remedies follow breach of a written supply agreement?"}
    if change == "facts": kwargs["changes"] = {"features":{**zenas.body["features"],"written":False}}
    if change == "jurisdiction": kwargs["changes"] = {"jurisdiction":"both"}
    if change == "user": kwargs["user"] = USER_B
    if change == "tenant": kwargs.update(user=USER_C,tenant=zenas.stack.other_tenant)
    response = await zenas.answer(**kwargs)
    assert not response.json().get("memory_hit")
    assert not receipt(response).get("answered_from_memory")


@pytest.mark.asyncio
async def test_correction_changes_only_the_owners_next_answer(zenas):
    row = await owned_result(zenas)
    correction = {"memo":{"text":"placeholder corrected owner-only legal position"}}
    edited = await zenas.request("POST","/memory/edit",body={"tenant_id":zenas.stack.tenant,
        "memory_id":row["id"],"value":correction})
    assert edited.status_code == 200
    before = len(zenas.model.calls)
    owner = await first_answer(zenas)
    assert "placeholder corrected owner-only" in owner.text and len(zenas.model.calls) == before
    other = await first_answer(zenas,user=USER_B)
    assert "placeholder corrected owner-only" not in other.text


@pytest.mark.asyncio
async def test_forget_invalidates_reusable_answer(zenas):
    row = await owned_result(zenas)
    response = await zenas.request("POST","/memory/forget",body={"tenant_id":zenas.stack.tenant,"memory_id":row["id"]})
    assert response.status_code == 200
    again = await first_answer(zenas)
    assert not receipt(again).get("answered_from_memory")
    assert row["id"] not in json.dumps(again.json())


@pytest.mark.asyncio
async def test_off_disables_only_that_users_recall_and_remember(zenas):
    await owned_result(zenas)
    await owned_result(zenas,USER_B)
    response = await zenas.request("POST","/memory/switch",body={"tenant_id":zenas.stack.tenant,"enabled":False})
    assert response.status_code == 200
    before = len([c for c in zenas.stack.calls if c == ("POST","/memories")])
    again = await first_answer(zenas)
    assert not receipt(again).get("answered_from_memory")
    assert len([c for c in zenas.stack.calls if c == ("POST","/memories")]) == before
    other = await first_answer(zenas,user=USER_B)
    assert receipt(other).get("answered_from_memory")


@pytest.mark.asyncio
@pytest.mark.parametrize("failure",["list","recall","remember"])
async def test_memory_outage_is_truthful_and_never_repeats_paid_work(zenas,failure):
    transport = zenas.stack.http._transport
    class Outage(httpx.AsyncBaseTransport):
        async def handle_async_request(self,request):
            bad = ((failure == "list" and request.method == "GET" and request.url.path == "/records") or
                   (failure == "recall" and request.url.path == "/recall") or
                   (failure == "remember" and request.method == "POST" and request.url.path == "/memories"))
            if bad: return httpx.Response(503,json={"detail":"placeholder memory outage"})
            return await transport.handle_async_request(request)
    zenas.stack.http._transport = Outage()
    ident = str(uuid4())
    try:
        first = await first_answer(zenas,run_id=ident)
        bill = receipt(first)
        assert bill.get("memory_status") == "memory unavailable"
        count = len(zenas.model.calls)
        replay = await first_answer(zenas,run_id=ident)
        assert replay.json() == first.json() and len(zenas.model.calls) == count
    finally:
        zenas.stack.http._transport = transport


@pytest.mark.asyncio
async def test_authentication_failure_is_not_reported_as_memory_outage(zenas):
    await owned_result(zenas)
    zenas.room.app.state.memory._api_key = "placeholder-wrong-room-key"
    response = await zenas.answer()
    assert response.status_code in {401,403}
    assert "memory unavailable" not in response.text.lower()


@pytest.mark.asyncio
async def test_receipts_reconcile_and_remembered_legal_fields_are_meaningful(zenas):
    response = await first_answer(zenas)
    bill = receipt(response)
    assert bill["cost_usd"] == len(zenas.model.calls)*FIXTURE_COST
    assert bill["tokens_in"] == len(zenas.model.calls)*FIXTURE_INPUT
    assert bill["tokens_out"] == len(zenas.model.calls)*FIXTURE_OUTPUT
    material = json.dumps(await zenas.records())
    for value in ("placeholder goods delivered","placeholder legal party","placeholder signed agreement",
                  "placeholder claimant position","placeholder concise wording","placeholder confidentiality clause",
                  "placeholder response deadline","placeholder clinic-law learning","placeholder moot visitor"):
        assert value in material, "Meaningful personal context must survive the real request, not just a kind declaration"


@pytest.mark.asyncio
async def test_retry_and_concurrent_requests_pay_at_most_once(zenas):
    ident = str(uuid4())
    first, second = await asyncio.gather(zenas.answer(run_id=ident),zenas.answer(run_id=ident))
    assert first.status_code in {200,409} and second.status_code in {200,409}
    successful = first if first.status_code == 200 else second
    assert successful.status_code == 200
    count = len(zenas.model.calls)
    replay = await first_answer(zenas,run_id=ident)
    assert replay.json() == successful.json() and len(zenas.model.calls) == count


@pytest.mark.asyncio
async def test_same_tenant_run_id_cannot_replay_another_users_private_response(zenas):
    row=await owned_result(zenas)
    private='placeholder confidential owner correction'
    edit=await zenas.request('POST','/memory/edit',body={'tenant_id':zenas.stack.tenant,
        'memory_id':row['id'],'value':{'memo':{'text':private}}})
    assert edit.status_code==200
    ident=str(uuid4())
    owner=await first_answer(zenas,run_id=ident)
    assert private in owner.text
    other=await zenas.answer(user=USER_B,run_id=ident)
    assert other.status_code in {401,403,409}
    assert private not in other.text


@pytest.mark.asyncio
async def test_stateful_moot_ai_turns_never_reuse_a_legal_answer(zenas,monkeypatch):
    from moot_hearing.test_hearing import problem
    from trigger_signin_fakes import set_founders

    from agents.zenas.core.moot.hearing import Actor, change
    from agents.zenas.core.moot.hearing_store import HearingStore
    set_founders(monkeypatch,USER_A)
    owner=Actor(zenas.stack.tenant,USER_A,zenas.body['home_region'],True)
    store=HearingStore(zenas.stack.records.pool)
    before=len(zenas.model.calls)
    for _ in range(2):
        source=problem();source['region']=zenas.body['home_region']
        state=await store.create(owner,str(uuid4()),source,{seat:{'kind':'ai'} for seat in ('applicant','respondent','judge')})
        for action in ('lock','start'):
            state=await store.mutate(owner,state['id'],str(uuid4()),state['revision'],action,{},
                lambda s,a,r,p,op=action:change(s,a,r,op,p))
        headers={**zenas.headers(),'X-Moot-Actor':USER_A,'X-Moot-Tenant':zenas.stack.tenant}
        response=await zenas.request('POST',f"/moot/hearings/{state['id']}/ai",headers=headers,
            body={'request_id':str(uuid4()),'revision':state['revision']})
        assert response.status_code==200,response.text
        assert response.json()['hearing']['receipts']
    assert len(zenas.model.calls)==before+2
    assert not any((row.get('meta') or {}).get('task_key','').startswith('moot.')
                   for row in await zenas.records() if row['kind']=='zenas.result')


@pytest.mark.asyncio
@pytest.mark.parametrize("zenas",["us-east","za"],indirect=True)
async def test_region_jurisdiction_and_draft_entry_paths(zenas):
    response = await first_answer(zenas)
    assert zenas.body["jurisdiction"] in json.dumps(response.json()).lower()
    foreign = await zenas.answer(changes={"home_region":"za" if zenas.body["home_region"] == "us-east" else "us-east"})
    assert foreign.status_code == 403
    draft = {"tenant_id":zenas.stack.tenant,"home_region":zenas.body["home_region"],
        "jurisdiction":zenas.body["jurisdiction"],"template":"nda",
        "terms":{"parties":"placeholder parties","confidentiality":"placeholder private agreement",
                 "term":"placeholder fixed term","return":"placeholder return documents"}}
    first = await zenas.request("POST","/drafts",body=draft)
    assert first.status_code == 201
    again = await zenas.request("POST","/drafts",body=draft)
    assert again.status_code == 201 and receipt(again).get("answered_from_memory")
    for key in ('text', 'sentences', 'docx_base64', 'document_id', 'state'):
        assert again.json()[key] == first.json()[key]
    book = await zenas.request('POST', '/playbooks', body={
        'tenant_id': zenas.stack.tenant, 'home_region': zenas.body['home_region'],
        'name': 'placeholder review positions', 'template': 'nda',
        'positions': [{'kind': 'confidentiality', 'text': 'Keep the information confidential.'}]})
    assert book.status_code == 201, book.text
    review = {'tenant_id': zenas.stack.tenant, 'home_region': zenas.body['home_region'],
        'playbook_id': book.json()['playbook']['id'], 'text': 'Keep the information confidential.',
        'matter_id': zenas.matters[zenas.stack.tenant]}
    first = await zenas.request('POST', '/contract-reviews', body=review)
    assert first.status_code == 200 and first.json()['ok'], first.text
    calls = len(zenas.model.calls)
    again = await zenas.request('POST', '/contract-reviews', body=review)
    assert again.status_code == 200 and receipt(again)['answered_from_memory'], again.text
    assert len(zenas.model.calls) == calls
    for key in ('findings', 'deviations', 'docx_base64', 'document_id', 'state'):
        assert again.json()[key] == first.json()[key]


def test_original_gate_nodes_are_preserved_in_manifest():
    manifest = json.loads((ROOT/"tests/gates78/products/zenas.json").read_text())
    assert manifest["source_sha"] == SOURCE_SHA
    nodes = manifest["legacy_tests"]
    assert any("gates_7_8_memory.py::" in node for node in nodes)
    assert any("gates_7_8_hermes_contract.py::" in node for node in nodes)
    assert len(nodes) == 32 and len(nodes) == len(set(nodes))
    targets = sorted({node.split('::')[0] for node in nodes})
    missing = [target for target in targets if not (ROOT / target).is_file()]
    assert not missing, 'BLOCKED: original regression modules not integrated: ' + ', '.join(missing)
    path = ROOT / '.tmp/gates78' / ('zenas-legacy-' + uuid4().hex + '.json')
    env = {**os.environ, 'PYTHONPATH':os.pathsep.join(str(ROOT/part) for part in ('','tank','agents','agents/_chassis','tests','tests/gates78'))}
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        '-p', 'gate78_result', '--gate78-result', str(path), '--disable-socket', '--allow-unix-socket',
        '--allow-hosts=localhost,127.0.0.1,::1', '--timeout=120', *targets],
        check=False, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(path.read_text())
    assert evidence['exit_code'] == 0 and not evidence['collection_errors']
    assert evidence['cases'] and all(value == 'PASS' for value in evidence['cases'].values())
    executed = {node.split('[', 1)[0] for node in evidence['cases']}
    assert set(nodes) <= executed, 'An original regression was not executed'
    print(result.stdout.strip().splitlines()[-1], str(path.relative_to(ROOT)))


@pytest.mark.asyncio
async def test_real_ledger_reconciliation_and_first_repeat_changed_evidence(zenas):
    from uuid import UUID
    measurements = []
    for label, changes in [('first', {}), ('exact_repeat', {}),
            ('changed_input', {'question': 'What notice does a written supply agreement require?'})]:
        before = len(zenas.model.calls)
        response = await first_answer(zenas, changes=changes)
        bill = receipt(response)
        rows = await zenas.stack.records.pool.fetch("""SELECT id,cost_usd,tokens_in,tokens_out,model,rung
            FROM tank.ledger WHERE tenant_id=$1 AND agent='zenas' AND id=ANY($2::uuid[])""",
            UUID(zenas.stack.tenant), [UUID(ident) for ident in bill['ledger_ids']])
        charged = [row for row in rows if row['rung'] != 3]
        assert all(row['cost_usd'] == 0 and row['tokens_in'] == row['tokens_out'] == 0 for row in rows if row['rung'] == 3)
        calls = len(zenas.model.calls)-before
        assert len(charged) == calls
        assert bill['cost'] == sum(float(row['cost_usd']) for row in charged)
        assert bill['tokens_in'] == sum(row['tokens_in'] for row in charged)
        assert bill['tokens_out'] == sum(row['tokens_out'] for row in charged)
        measurements.append({'scenario':label,'provider_calls':calls,'cost':bill['cost'],
            'would_have_cost':bill['would have cost'],'tokens_in':bill['tokens_in'],'tokens_out':bill['tokens_out']})
    assert measurements[0]['provider_calls'] > 0 and measurements[2]['provider_calls'] > 0
    assert measurements[1]['provider_calls'] == 0 and measurements[1]['tokens_in'] == measurements[1]['tokens_out'] == 0
    view = await zenas.request('GET','/receipts')
    assert view.status_code == 200 and len(view.json()['receipts']) == 3
    empty = await zenas.request('GET','/receipts',user=USER_C,tenant=zenas.stack.other_tenant)
    assert empty.status_code == 200 and empty.json()['receipts'] == []
    print('ZENAS_GATE78_COSTS=' + json.dumps(measurements, sort_keys=True))


@pytest.mark.asyncio
async def test_forget_and_correction_tombstone_private_command_replays(zenas):
    initial_id = str(uuid4())
    await first_answer(zenas, run_id=initial_id)
    row = next(row for row in await zenas.records() if row['kind'] == 'zenas.result')
    private = 'placeholder corrected confidential position'
    edited = await zenas.request('POST','/memory/edit',body={'tenant_id':zenas.stack.tenant,
        'memory_id':row['id'],'value':{'memo':{'text':private}}})
    assert edited.status_code == 200
    calls = len(zenas.model.calls)
    old = await zenas.answer(run_id=initial_id)
    assert old.status_code == 409 and private not in old.text and len(zenas.model.calls) == calls
    ident = str(uuid4())
    corrected = await first_answer(zenas, run_id=ident)
    assert private in corrected.text and len(zenas.model.calls) == calls
    forgotten = await zenas.request('POST','/memory/forget',body={'tenant_id':zenas.stack.tenant,
        'memory_id':edited.json()['memory']['id']})
    assert forgotten.status_code == 200
    replay = await zenas.answer(run_id=ident)
    assert replay.status_code == 409 and private not in replay.text and len(zenas.model.calls) == calls


@pytest.mark.asyncio
async def test_completed_code_brain_gap_never_falls_through_to_paid_provider(zenas,monkeypatch):
    from chassis.user_assertion import SignedUser
    from agents.zenas.zenas_brain import brain_then_route
    monkeypatch.setenv('ZENAS_BRAIN_ENABLED','true')
    actor = SignedUser(zenas.stack.tenant, USER_A, 'org:admin')
    ident = str(uuid4())
    # The real free rung is the approved scope classifier, not an invented legal rule card.
    response = await brain_then_route(None, zenas.room.app.state.tank, tenant_id=actor.tenant_id,
        task_type='zenas.scope', messages=[{'role':'user','content':'Review a written supply agreement.'}],
        actor=actor, run_id=ident)
    assert '/tasks' in zenas.worker.calls and zenas.model.calls == []
    assert json.loads(response['content'])['in_scope'] is True
    assert response['model'] == 'code' and response['cost_usd'] == 0
    assert response['tokens_in'] == response['tokens_out'] == 0
    again = await brain_then_route(None, zenas.room.app.state.tank, tenant_id=actor.tenant_id,
        task_type='zenas.scope', messages=[{'role':'user','content':'Review a written supply agreement.'}],
        actor=actor, run_id=ident)
    assert again['ledger_id'] == response['ledger_id'] and zenas.model.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("zenas", ["us-east", "za"], indirect=True)
async def test_private_brain_dispatch_preserves_real_policy_identity_and_receipts(zenas, monkeypatch):
    monkeypatch.setenv('ZENAS_BRAIN_ENABLED', 'true')
    response = await first_answer(zenas)
    assert zenas.worker.calls[:2] == ['/health', '/tasks']
    assert len(zenas.model.calls) > 0
    bill = receipt(response)
    assert bill['cost'] == len(zenas.model.calls) * FIXTURE_COST
    assert bill['tokens_in'] == len(zenas.model.calls) * FIXTURE_INPUT
    assert bill['tokens_out'] == len(zenas.model.calls) * FIXTURE_OUTPUT
    assert zenas.worker.actors
    assert all(a.tenant_id == zenas.stack.tenant and a.user_id == USER_A and a.role == 'org:admin' for a in zenas.worker.actors)
    assert all(r.extensions['timeout']['read'] == 5 for r in zenas.worker.requests)
    assert response.json()['memory']['status'] == 'ok'
    # A second real worker shares the durable replay wall; tests never verify the token themselves.
    from agents.zenas.core.brain_service import create_app
    forwarded = next(r for r in zenas.worker.requests if r.url.path == '/tasks')
    second = create_app(pool=zenas.stack.records.pool, http=zenas.room.app.state.tank._http)
    count = len(zenas.model.calls)
    async with second.router.lifespan_context(second):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=second)) as http:
            replay = await http.post(str(forwarded.url), content=forwarded.content, headers=forwarded.headers)
            assert replay.status_code == 401
    assert len(zenas.model.calls) == count


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [302, 401, 403, 503, 'timeout'])
async def test_private_brain_failures_never_redirect_or_pay_fallback(zenas, monkeypatch, status):
    monkeypatch.setenv('ZENAS_BRAIN_ENABLED', 'true')
    zenas.worker.fault = status
    response = await zenas.answer()
    assert response.status_code == (status if status in {401,403} else 503)
    assert not zenas.model.calls
    assert zenas.worker.calls == ['/health', '/tasks']
    assert not response.json().get('memory_hit')


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['tenant_id','task_id','room','ledger_id','cost_usd','tokens_in'])
async def test_private_brain_forged_receipts_fail_closed_without_second_payment(zenas, monkeypatch, field):
    monkeypatch.setenv('ZENAS_BRAIN_ENABLED', 'true')
    def forged(data):
        data['receipt'][field] = (str(uuid4()) if field in {'tenant_id','task_id','ledger_id'} else
                                  'placeholder-other-room' if field == 'room' else 999)
    zenas.worker.corrupt = forged
    response = await zenas.answer()
    assert response.status_code == 503
    assert len(zenas.model.calls) == 1
    assert zenas.worker.calls == ['/health', '/tasks']
    assert not response.json().get('memory_hit')


@pytest.mark.asyncio
async def test_typed_room_client_keeps_paid_admission_and_person_run_replay(zenas, monkeypatch):
    from uuid import UUID

    import paid_steps
    from chassis.tank import TankClient
    from chassis.user_assertion import SignedUser
    monkeypatch.setenv('ZENAS_BRAIN_ENABLED', 'true')
    tenant, pool = zenas.stack.tenant, zenas.stack.records.pool
    actor = SignedUser(tenant, USER_A, 'org:admin')
    step = paid_steps.model_step('agent.zenas.think','llama-small',agent='zenas')
    await pool.execute("UPDATE tank.paid_step_settings SET mode='ask' WHERE tenant_id=$1 AND step_id=$2", UUID(tenant), step)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=zenas.tank.app)) as http:
        client = TankClient('http://tank:8000', zenas.stack.key, 'zenas', http)
        messages = [{'role':'user','content':'Review the written civil supply agreement and its notice terms.'}]
        ident = str(uuid4())
        with pytest.raises(httpx.HTTPStatusError) as error:
            await client.room_task(actor, ident, messages)
        assert error.value.response.status_code == 409 and not zenas.model.calls
        assert error.value.response.json()['detail']['code'] == 'paid_step_approval_required'
        await pool.execute("UPDATE tank.paid_step_settings SET mode='auto' WHERE tenant_id=$1 AND step_id=$2", UUID(tenant), step)
        # A fresh authorized run does not reuse the earlier approval claim.
        ident = str(uuid4())
        first = await client.room_task(actor, ident, messages)
        count = len(zenas.model.calls)
        again = await client.room_task(actor, ident, messages)
        assert again == first and len(zenas.model.calls) == count == 1
        other = await client.room_task(SignedUser(tenant, USER_B, 'org:admin'), ident, messages)
        assert other['receipt']['task_id'] != first['receipt']['task_id']
        assert len(zenas.model.calls) == 2
        monkeypatch.setenv('ZENAS_BRAIN_ENABLED', 'false')
        with pytest.raises(httpx.HTTPStatusError) as error:
            await client.room_task(actor, str(uuid4()), messages)
        assert error.value.response.status_code == 409 and len(zenas.model.calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("zenas", ["us-east", "za"], indirect=True)
async def test_typed_embeddings_use_real_same_region_tank_and_local_encoder(zenas, monkeypatch):
    from uuid import UUID

    from agents.zenas.core.savings import Run, current
    from chassis.tank import TankClient
    from zenas_za_meaning_search.test_hermes_law import stack

    from agents.zenas.pool.embed import LAW_MODEL, HermesLawClient
    region = zenas.body['home_region']
    qdrant, encoder, app = stack(region)
    monkeypatch.setattr(zenas.tank, 'law_transport', httpx.ASGITransport(app=app), raising=False)
    token = current.set(Run(zenas.stack.tenant, 'placeholder embeddings'))
    try:
        client = HermesLawClient(region=region, transport=httpx.ASGITransport(app=zenas.tank.app))
        vectors = await client.embed([QUOTE])
        assert len(vectors) == 1 and QUOTE in encoder.calls and not zenas.model.calls
        row = await zenas.stack.records.pool.fetchrow("SELECT * FROM tank.ledger WHERE tenant_id=$1 AND task_type='zenas.embeddings'", UUID(zenas.stack.tenant))
        assert row['region'] == region and row['agent'] == 'zenas' and row['cost_usd'] == 0
        assert row['tokens_in'] == row['tokens_out'] == 0
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=zenas.tank.app)) as http:
            tank = TankClient('http://tank:8000', zenas.stack.key, 'zenas', http)
            before = len(encoder.calls)
            with pytest.raises(RuntimeError):
                await tank.law_embeddings(zenas.stack.tenant, 'za' if region == 'us-east' else 'us-east',
                    client.jurisdiction, LAW_MODEL, [QUOTE])
            assert len(encoder.calls) == before
    finally:
        current.reset(token)
        qdrant.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', ['missing','key','user','tenant','region','room','replay'])
async def test_tank_task_adapter_rejects_scope_and_nonce_before_private_dispatch(zenas, monkeypatch, bad):
    from chassis.user_assertion import SignedUser, sign_assertion
    monkeypatch.setenv('ZENAS_BRAIN_ENABLED', 'true')
    actor = SignedUser(zenas.stack.tenant, USER_A, 'org:admin')
    path = '/v1/agents/base/delegate' if bad == 'room' else '/v1/agents/zenas/delegate'
    body = {'tenant_id':actor.tenant_id, 'user_id':USER_B if bad == 'user' else USER_A,
            'run_id':str(uuid4()), 'task_key':'zenas.rule_card', 'input':{'messages':[]}, 'recall':[]}
    if bad == 'tenant':
        body['tenant_id'] = zenas.stack.other_tenant
    raw = json.dumps(body, separators=(',',':')).encode()
    headers = {'X-Tank-Key':WORKSPACE_KEY if bad == 'key' else zenas.stack.key,
               'X-Home-Region':('za' if zenas.body['home_region'] == 'us-east' else 'us-east') if bad == 'region' else zenas.body['home_region'],
               'Content-Type':'application/json',
               'X-Tervory-User-Assertion':sign_assertion('zenas',actor,'POST',path,raw,key=zenas.stack.key)}
    if bad == 'missing':
        headers.pop('X-Tervory-User-Assertion')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=zenas.tank.app)) as http:
        first = await http.post('http://tank'+path,content=raw,headers=headers)
        if bad == 'replay':
            assert first.status_code == 422 and zenas.worker.calls == ['/health','/tasks']
            second = await http.post('http://tank'+path,content=raw,headers=headers)
            assert second.status_code == 401 and zenas.worker.calls == ['/health','/tasks']
        else:
            assert first.status_code in {401,403}, first.text
            assert not zenas.worker.calls
    assert not zenas.model.calls


@pytest.mark.asyncio
async def test_completed_private_task_without_output_never_pays_fallback(zenas, monkeypatch):
    monkeypatch.setenv('ZENAS_BRAIN_ENABLED', 'true')
    def empty(data):
        data['result'] = {'content': ''}
    zenas.worker.corrupt = empty
    response = await zenas.answer()
    assert response.status_code == 503 and len(zenas.model.calls) == 1
    rows = await zenas.request('GET', '/receipts')
    assert rows.status_code == 200
    assert any(r['cost'] == FIXTURE_COST for r in rows.json()['receipts'])


@pytest.mark.asyncio
async def test_private_receipt_reconciliation_preserves_provider_precision(zenas, monkeypatch):
    from decimal import Decimal
    from uuid import UUID

    from chassis.tank import TankClient
    from chassis.user_assertion import SignedUser
    monkeypatch.setenv('ZENAS_BRAIN_ENABLED', 'true')
    zenas.model.response_cost = 0.002400004
    actor = SignedUser(zenas.stack.tenant, USER_A, 'org:admin')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=zenas.tank.app)) as http:
        client = TankClient('http://tank:8000', zenas.stack.key, 'zenas', http)
        data = await client.delegate_task(actor, str(uuid4()), 'zenas.rule_card',
            {'messages':[{'role':'user','content':'Review the written civil supply agreement and its notice terms.'}]}, [])
    bill = data['receipt']
    assert bill['cost_usd'] == 0.002400004 and len(zenas.model.calls) == 1
    row = await zenas.stack.records.pool.fetchrow('SELECT cost_usd FROM tank.ledger WHERE tenant_id=$1 AND id=$2',
        UUID(zenas.stack.tenant), UUID(bill['ledger_id']))
    assert row['cost_usd'] == Decimal('0.00240000')
