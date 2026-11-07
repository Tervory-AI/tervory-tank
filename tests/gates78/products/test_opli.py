"""Gate 7/8 acceptance enters the deployed OPLI command corridor."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

import asyncpg
import httpx
import pytest

from chassis.user_assertion import SignedUser, sign_assertion
from hermes.service import create_app
from hermes.store import InMemoryStore
from hermes.user_scope import TENANT_WIDE_KINDS

from opli_fixture import OWNER, OTHER_USER, ANSWER, WORKSPACE_KEY, opli as opli


@pytest.mark.asyncio
async def test_shared_fixture_positive_recall(gate78_memory):
    stack = await gate78_memory("opli")
    owner = stack.client(OWNER)
    saved = await owner.remember(stack.tenant, "placeholder collection probe", "opli.receipt", "urn:placeholder:probe")
    listed = await owner.records(stack.tenant)
    assert saved["id"] in {r["id"] for r in listed}
    recalled = await owner.recall(stack.tenant, "placeholder collection probe")
    assert saved["id"] in {r["id"] for r in recalled}, {"stored_agent": listed[0]["agent"], "recall_agent": stack.agent}


async def owned_rows(opli, user=OWNER, tenant=None):
    return await opli.stack.client(user).records(tenant or opli.stack.tenant)


async def run_and_row(opli, **kwargs):
    response = await opli.turn(**kwargs)
    assert response.status_code == 200, response.text
    rows = await owned_rows(opli, kwargs.get("user", OWNER), kwargs.get("tenant"))
    return response.json(), next(row for row in rows if row["kind"] == "opli.receipt")


async def control(opli, action, memory_id=None, *, user=OWNER, tenant=None, **body):
    if memory_id is not None:
        body["memory_id"] = memory_id
    headers = opli.headers(user, tenant)
    if action == "view":
        return await opli.api.get("/v1/command/opli/memory.view", params=body, headers=headers)
    return await opli.api.post("/v1/command/opli/memory." + action, json=body, headers=headers)


@pytest.mark.asyncio
async def test_task_path(opli):
    response = await opli.turn()
    assert response.status_code == 200, response.text
    assert len(opli.gateway.calls) == 1
    assert opli.events.index("POST /recall") < opli.events.index("provider") < opli.events.index("POST /memories")
    assert response.json()["answer"] == opli.gateway.answer


@pytest.mark.asyncio
async def test_owner_crud(opli):
    _, row = await run_and_row(opli)
    listed = await control(opli, "view")
    assert listed.status_code == 200
    assert row["id"] in {r["id"] for r in listed.json()["memories"]}
    got = await control(opli, "view", row["id"])
    assert got.status_code == 200, got.text
    edited = await control(opli, "edit", row["id"], text="correction=placeholder corrected result")
    assert edited.status_code == 200, edited.text
    assert (await control(opli, "view", row["id"])).json()["memories"][0]["claim"] == "correction=placeholder corrected result"
    forgotten = await control(opli, "forget", row["id"])
    assert forgotten.status_code == 200, forgotten.text
    assert not await owned_rows(opli)


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign", ["user", "tenant"])
@pytest.mark.parametrize("action,body", [("view", {}), ("edit", {"text": "placeholder forged"}),
                                         ("forget", {}), ("control", {"control": "off"})])
async def test_foreign_controls_unchanged(opli, foreign, action, body):
    _, row = await run_and_row(opli)
    before = await owned_rows(opli)
    user = OTHER_USER if foreign == "user" else OWNER
    tenant = opli.stack.other_tenant if foreign == "tenant" else opli.stack.tenant
    rejected = await control(opli, action, row["id"], user=user, tenant=tenant, **body)
    assert rejected.status_code in (403, 404), rejected.text
    assert ANSWER not in rejected.text
    assert await owned_rows(opli) == before
    assert await owned_rows(opli, user, tenant) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign", ["user", "tenant"])
async def test_foreign_publish_unchanged(opli, foreign):
    _, row = await run_and_row(opli)
    before = await owned_rows(opli)
    rejected = await opli.api.post("/v1/command/opli/memory.publish", headers=opli.headers(
        OTHER_USER if foreign == "user" else OWNER,
        opli.stack.other_tenant if foreign == "tenant" else opli.stack.tenant), json={"memory_id": row["id"]})
    assert rejected.status_code == 404  # OPLI exposes no publication tool.
    assert await owned_rows(opli) == before


@pytest.mark.asyncio
async def test_declared_tenant_wide(opli):
    assert TENANT_WIDE_KINDS["opli"] == frozenset({"opli.repo_map", "opli.convention"})
    client = opli.stack.client(OWNER)
    shared = await client.remember(opli.stack.tenant, "placeholder shared layout", "opli.repo_map", "urn:placeholder:shared", tenant_wide=True)
    private = await client.remember(opli.stack.tenant, "placeholder personal layout", "opli.repo_map", "urn:placeholder:private")
    listed = await control(opli, "view", user=OTHER_USER)
    assert listed.status_code == 200
    ids = {r["id"] for r in listed.json()["memories"]}
    assert shared["id"] in ids and private["id"] not in ids
    other = await control(opli, "view", tenant=opli.stack.other_tenant)
    assert other.json()["memories"] == []
    with pytest.raises(RuntimeError, match="hermes answered 4"):
        await client.remember(opli.stack.tenant, "placeholder widen", "opli.receipt", "urn:placeholder:refused", tenant_wide=True)


@pytest.mark.asyncio
async def test_required_owner_and_strict_input(opli):
    response = await opli.api.post("/v1/command/opli/memory.control", headers={"X-Tank-Key": WORKSPACE_KEY},
                                   json={"control": "off", "user_id": OWNER, "tenant_id": opli.stack.tenant})
    assert response.status_code == 401
    thread = await opli.thread()
    for extra in ({"user_id": OTHER_USER}, {"tenant_id": opli.stack.other_tenant}, {"meta": {"user_id": OTHER_USER}}):
        rejected = await opli.turn(thread, **extra)
        assert rejected.status_code == 422, rejected.text
    unsigned = await opli.stack.http.post("/memories", headers={"X-Tank-Key": opli.stack.key}, json={
        "tenant_id": opli.stack.tenant, "text": "placeholder widen", "kind": "opli.receipt", "source": "urn:placeholder:refused"})
    assert unsigned.status_code in (400, 401, 422)
    assert await owned_rows(opli) == [] and opli.gateway.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("attack", ["missing", "header-user", "header-tenant", "bad-signature", "role"])
async def test_signed_actor(opli, attack):
    headers = opli.headers()
    if attack == "missing":
        headers.pop("X-Trigger-Signin-Token", None)
        headers.pop("x-trigger-signin-token", None)
    elif attack == "header-user":
        headers["X-Tervory-User"] = OTHER_USER
    elif attack == "header-tenant":
        headers["X-Tervory-Tenant"] = opli.stack.other_tenant
    elif attack == "bad-signature":
        headers["x-trigger-signin-token"] = "placeholder-invalid"
    else:
        headers["X-Tervory-Role"] = "founder"
    response = await opli.api.post("/v1/command/opli/memory.control", headers=headers, json={"control": "off"})
    assert response.status_code in (401, 403), response.text
    assert await owned_rows(opli) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("attack", ["key", "audience", "tenant", "user", "method", "target", "body", "missing", "expired", "future"])
async def test_assertion_rejection(opli, attack):
    def mutate(request):
        actor = SignedUser(opli.stack.other_tenant if attack == "tenant" else opli.stack.tenant,
                           OTHER_USER if attack == "user" else OWNER, "member")
        token = sign_assertion("opli" if attack == "audience" else "hermes", actor,
            "DELETE" if attack == "method" else request.method,
            "/placeholder-wrong" if attack == "target" else request.url.raw_path.decode(),
            b"placeholder-tampered" if attack == "body" else request.content,
            key="placeholder-wrong-key" if attack == "key" else opli.stack.key,
            now=int(time.time()) + (60 if attack == "future" else -120 if attack == "expired" else 0))
        if attack == "missing":
            request.headers.pop("X-Tervory-User-Assertion", None)
        else:
            request.headers["X-Tervory-User-Assertion"] = token
    opli.failure.mutate = mutate
    response = await control(opli, "control", control="off")
    assert response.status_code in (401, 403), response.text
    assert await owned_rows(opli) == [] and opli.gateway.calls == []


@pytest.mark.asyncio
async def test_replay_cannot_restore_forgotten(opli):
    response = await control(opli, "control", control="edit")
    assert response.status_code == 200, response.text
    captured = next(r for r in opli.requests if r.url.path == "/memories")
    replayed = await asyncio.gather(*[opli.stack.http.request(captured.method, str(captured.url),
        content=captured.content, headers=captured.headers) for _ in range(2)])
    assert [r.status_code for r in replayed] == [401, 401]
    fresh_headers = dict(captured.headers)
    fresh_headers["x-tervory-user-assertion"] = sign_assertion("hermes", SignedUser(opli.stack.tenant, OWNER, "member"),
        captured.method, captured.url.raw_path.decode(), captured.content, key=opli.stack.key)
    concurrent = await asyncio.gather(*[opli.stack.http.request(captured.method, str(captured.url),
        content=captured.content, headers=fresh_headers) for _ in range(2)])
    assert sorted(r.status_code for r in concurrent) == [201, 401]
    added = next(r.json()["id"] for r in concurrent if r.status_code == 201)
    assert (await control(opli, "forget", added)).status_code == 200
    # Delete through the product control, then reconstruct a worker against the same SQL nonce wall.
    forgotten = await control(opli, "forget", response.json()["id"])
    assert forgotten.status_code == 200, forgotten.text
    restarted = create_app(InMemoryStore(), opli.stack.records.encoder, records=opli.stack.records)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(restarted)) as http:
        retry = await http.request(captured.method, str(captured.url), content=captured.content, headers=captured.headers)
    assert retry.status_code == 401 and not await owned_rows(opli)


@pytest.mark.asyncio
async def test_sql_before_vector(opli, monkeypatch):
    _, own = await run_and_row(opli)
    for i in range(40):
        await opli.stack.client(OTHER_USER).remember(opli.stack.tenant, f"placeholder foreign {i}", "opli.receipt", "urn:placeholder:foreign")
    search = opli.stack.records.index.search
    candidates = []
    def observe(*args, **kwargs):
        candidates.append(kwargs["allowed_ids"])
        assert kwargs["allowed_ids"] == [own["id"]]
        return search(*args, **kwargs)
    monkeypatch.setattr(opli.stack.records.index, "search", observe)
    response = await control(opli, "view")
    assert response.status_code == 200 and candidates
    assert [r["id"] for r in response.json()["memories"]] == [own["id"]]
    candidates.clear()
    assert (await control(opli, "view", user="placeholder-no-memory")).json()["memories"] == []
    assert candidates == []


@pytest.mark.asyncio
async def test_controls_need_identity_plain_task_preserved(opli):
    thread = await opli.thread()
    for action in ("view", "edit", "forget", "control"):
        path = "/v1/command/opli/memory." + action
        response = await opli.api.request("GET" if action == "view" else "POST", path,
                                         headers={"X-Tank-Key": WORKSPACE_KEY})
        assert response.status_code == 401
    response = await opli.turn(thread, memory_control="off")
    assert response.status_code == 200 and response.json()["answer"] == ANSWER
    assert not await owned_rows(opli)


@pytest.mark.asyncio
async def test_no_content_leak(opli, caplog):
    await run_and_row(opli)
    opli.gateway.answer = "placeholder other answer"
    response = await opli.turn(user=OTHER_USER)
    assert response.status_code == 200
    assert ANSWER not in response.text and ANSWER not in caplog.text
    for request in opli.gateway.calls[1:]:
        assert ANSWER not in json.dumps(request)
    secret = "password=placeholder-private-value"
    row = (await owned_rows(opli))[0]
    response = await control(opli, "edit", row["id"], text=secret)
    assert response.status_code in (400, 422), response.text
    assert secret not in response.text + caplog.text + json.dumps(await owned_rows(opli))


@pytest.mark.asyncio
async def test_runtime_contract(opli):
    await run_and_row(opli)
    writes = [r for r in opli.requests if r.url.path == "/memories"]
    assert writes and type(opli.memory).__module__ == "chassis.memory"
    for request in writes:
        assert request.headers["X-Tank-Key"] == opli.stack.key != WORKSPACE_KEY
        assert request.headers["X-Tervory-User"] == OWNER
        assert request.headers["X-Tervory-User-Assertion"]
        assert json.loads(request.content)["meta"]["user_id"] == OWNER


@pytest.mark.asyncio
async def test_default_off(opli, monkeypatch):
    monkeypatch.delenv("OPLI_MEMORY_ENABLED")
    monkeypatch.delenv("OPLI_BRAIN_ENABLED", raising=False)
    response = await opli.turn()
    assert response.status_code == 200, response.text
    assert all(r.url.path.startswith("/engine/") for r in opli.requests)
    assert len(opli.gateway.calls) == 1
    assert "memory_bracket" not in response.json()


@pytest.mark.asyncio
async def test_exact_repeat_receipts(opli, record_property):
    thread = await opli.thread()
    responses, evidence = [], []
    for label, text in (("first", "Summarise placeholder repository"),
                        ("exact-repeat", "Summarise placeholder repository"),
                        ("changed-input", "Summarise placeholder repository tests")):
        before = len(opli.gateway.calls)
        response = await opli.turn(thread, text=text)  # Independent prompt ID, not an idempotency retry.
        responses.append(response)
        evidence.append({"run": label, "provider_calls": len(opli.gateway.calls) - before,
                         "receipt": response.json().get("memory_bracket")})
    first, repeat, changed = responses
    assert [r.status_code for r in (first, repeat, changed)] == [200, 200, 200]
    record_property("fixture_costs_only", json.dumps(evidence))
    print("OPLI_FIXTURE_RECEIPTS " + json.dumps(evidence))
    assert len(opli.gateway.calls) == 2
    for response in (first, changed):
        bracket = response.json()["memory_bracket"]
        assert (bracket["paid_calls"], bracket["cost_usd"], bracket["tokens_in"], bracket["tokens_out"]) == (1, .0024, 80, 80)
    zero = repeat.json()["memory_bracket"]
    assert (zero["paid_calls"], zero["cost_usd"], zero["tokens_in"], zero["tokens_out"]) == (0, 0, 0, 0)
    assert zero["would_have_cost_usd"] == .0024
    assert repeat.json()["answer"] == first.json()["answer"]


@pytest.mark.asyncio
@pytest.mark.parametrize("miss", ["text", "user", "tenant", "tool-request"])
async def test_misses(opli, miss):
    thread = await opli.thread()
    if miss == "tool-request":
        opli.gateway.requests = [{"name": "run_command", "arguments": {"command": "echo placeholder"}}]
    first = await opli.turn(thread)
    assert first.status_code == 200, first.text
    second = await opli.turn(thread if miss in ("text", "tool-request") else None,
        user=OTHER_USER if miss == "user" else OWNER,
        tenant=opli.stack.other_tenant if miss == "tenant" else None,
        text="Changed placeholder task" if miss == "text" else "Summarise placeholder repository")
    assert second.status_code == 200, second.text
    assert len(opli.gateway.calls) == 2
    assert second.json()["memory_bracket"]["answered_from_memory"] is False


@pytest.mark.asyncio
async def test_correction_owner_only(opli):
    thread = await opli.thread()
    _, row = await run_and_row(opli, thread_id=thread)
    corrected = "placeholder corrected answer"
    edit = await control(opli, "edit", row["id"], text="correction=" + corrected)
    assert edit.status_code == 200, edit.text
    repeat = await opli.turn(thread)
    assert repeat.status_code == 200 and corrected in repeat.json()["answer"]
    assert len(opli.gateway.calls) == 1
    foreign = await opli.turn(user=OTHER_USER)
    assert foreign.status_code == 200 and corrected not in foreign.text
    assert len(opli.gateway.calls) == 2


@pytest.mark.asyncio
async def test_forget_invalidates_answer(opli):
    thread = await opli.thread()
    _, row = await run_and_row(opli, thread_id=thread)
    removed = await control(opli, "forget", row["id"])
    assert removed.status_code == 200, removed.text
    opli.gateway.answer = "placeholder new result"
    repeat = await opli.turn(thread)
    assert repeat.status_code == 200 and repeat.json()["answer"] == opli.gateway.answer
    assert len(opli.gateway.calls) == 2 and ANSWER not in json.dumps(await owned_rows(opli))


@pytest.mark.asyncio
async def test_memory_off_owner_only(opli):
    thread = await opli.thread()
    await run_and_row(opli, thread_id=thread)
    response = await control(opli, "control", control="off")
    assert response.status_code == 200
    opli.events.clear()
    repeat = await opli.turn(thread)
    assert repeat.status_code == 200
    assert repeat.json()["memory_bracket"]["answered_from_memory"] is False
    assert "POST /memories" not in opli.events
    recalls = [json.loads(r.content) for r in opli.requests if r.url.path == "/recall"]
    assert recalls[-1]["kind"] == "opli.memory_control"  # Only the control lookup is permitted.
    other = await opli.thread(OTHER_USER)
    assert (await opli.turn(other, user=OTHER_USER)).status_code == 200
    assert (await opli.turn(other, user=OTHER_USER)).json()["memory_bracket"]["answered_from_memory"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/recall", "/records", "/memories"])
async def test_outage_truthful_no_paid_retry(opli, path):
    if path == "/records":
        _, row = await run_and_row(opli)
        before = len(opli.gateway.calls)
        opli.failure.path = path
        response = await control(opli, "view", row["id"])
        assert response.status_code == 503, response.text
        assert "unavailable" in response.text.lower()
        assert ANSWER not in response.text and len(opli.gateway.calls) == before
        return
    opli.failure.path = path
    response = await opli.turn()
    assert response.status_code == 200, response.text
    assert response.json()["memory_bracket"]["memory_unavailable"] is True
    assert len(opli.gateway.calls) == 1
    assert response.json()["memory_bracket"]["paid_calls"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_auth_not_outage(opli, status):
    thread = await opli.thread()
    await run_and_row(opli, thread_id=thread)
    opli.failure.path, opli.failure.status = "/recall", status
    response = await opli.turn(thread)
    assert response.status_code in (401, 403), response.text
    assert ANSWER not in response.text and len(opli.gateway.calls) == 1


@pytest.mark.asyncio
async def test_meaningful_remembered_fields(opli):
    response, row = await run_and_row(opli)
    assert row["evidence"][0].startswith("opli:task:")
    assert "placeholder/repository" in row["claim"] and ANSWER in row["claim"]
    assert row["meta"]["reusable_result"]["outcome"] == ANSWER
    assert response["memory_bracket"]["cost_usd"] == .0024 and len(opli.gateway.calls) == 1
    ledgers = await opli.pool.fetch("SELECT cost_usd,tokens_in,tokens_out FROM tank.ledger WHERE tenant_id=$1", uuid.UUID(opli.stack.tenant))
    assert len(ledgers) == 1 and float(ledgers[0]["cost_usd"]) == .0024
    assert (ledgers[0]["tokens_in"], ledgers[0]["tokens_out"]) == (80, 80)


@pytest.mark.asyncio
async def test_retry_concurrency(opli):
    thread = await opli.thread()
    prompt = str(uuid.uuid4())
    opli.gateway.release.clear()
    first = asyncio.create_task(opli.turn(thread, prompt_id=prompt))
    await asyncio.wait_for(opli.gateway.entered.wait(), 5)
    concurrent = await opli.turn(thread, prompt_id=prompt)
    opli.gateway.release.set()
    response = await first
    assert response.status_code == 200 and concurrent.status_code == 409
    retry = await opli.turn(thread, prompt_id=prompt)
    assert retry.status_code == 409, retry.text
    assert len(opli.gateway.calls) == 1
    assert await opli.pool.fetchval("SELECT count(*) FROM tank.tasks WHERE tenant_id=$1", uuid.UUID(opli.stack.tenant)) == 1


@pytest.mark.asyncio
async def test_restricted_database_role(opli, monkeypatch):
    records = opli.stack.records
    admin = records.pool
    schema = records.schema("opli")
    role = "opli_placeholder_" + uuid.uuid4().hex[:16]
    await admin.execute(f"CREATE ROLE {role} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS")
    await admin.execute(f"GRANT USAGE, CREATE ON SCHEMA {schema} TO {role}")
    await admin.execute(f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO {role}")
    await admin.execute(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA {schema} TO {role}")
    restricted = await asyncpg.create_pool(os.environ["MEMORY_TEST_DATABASE_URL"], min_size=1, max_size=1,
                                         server_settings={"role": role})
    try:
        flags = await restricted.fetchrow("SELECT rolsuper,rolbypassrls,rolcreatedb FROM pg_roles WHERE rolname=current_user")
        assert tuple(flags.values()) == (False, False, False)
        monkeypatch.setattr(records, "pool", restricted)
        response = await control(opli, "control", control="edit")
        assert response.status_code == 200, response.text
        assert (await control(opli, "view", response.json()["id"])).status_code == 200
        before = await owned_rows(opli)
        denied = await control(opli, "forget", response.json()["id"], user=OTHER_USER)
        assert denied.status_code in (403, 404) and await owned_rows(opli) == before
        assert (await control(opli, "forget", response.json()["id"])).status_code == 200
    finally:
        records.pool = admin
        await restricted.close()
        await admin.execute(f"DROP OWNED BY {role}")
        await admin.execute(f"DROP ROLE {role}")


@pytest.mark.asyncio
async def test_existing_code_skill_before_model(opli, monkeypatch):
    import skala
    packages = skala.load_packages()
    assert ("base.normalize", "1.0.0") in packages
    monkeypatch.setattr(opli.tank, "_packages", packages)
    await opli.pool.execute("INSERT INTO tank.skills(id,version,agent,rung,state) VALUES('base.normalize','1.0.0','base',3,'approved')")
    await opli.pool.execute("UPDATE tank.policy SET model='skill:base.normalize@1.0.0',rung=3 WHERE task_type='command.code'")
    response = await opli.turn(text=json.dumps({"name": "placeholder business", "address": "placeholder street",
        "city": "placeholder town", "state": "placeholder", "zip": "placeholder 00000", "phone": "placeholder 0000000000"}))
    assert response.status_code == 200, response.text
    assert opli.gateway.calls == [], [dict(row) for row in await opli.pool.fetch("SELECT model,rung,outcome,error FROM tank.ledger")]
    bracket = response.json()["memory_bracket"]
    assert (bracket["paid_calls"], bracket["cost_usd"], bracket["tokens_in"], bracket["tokens_out"]) == (0, 0, 0, 0)
    assert "placeholder" in response.json()["answer"]
    assert await opli.pool.fetchval("SELECT count(*) FROM tank.ledger WHERE rung=3 AND cost_usd=0") == 1


@pytest.mark.timeout(600)
def test_cli_acceptance_retained(tmp_path):
    """Execute the existing worksheet, not a replacement CLI or selected subset."""
    root = Path(__file__).resolve().parents[3]
    junit = tmp_path / "opli-cli.xml"
    env = {**os.environ, "PYTEST_ADDOPTS": "", "POOL_SCHEMA_DATABASE_URL": os.environ["MEMORY_TEST_DATABASE_URL"]}
    assert (root / "cli/node_modules/csv-parse/package.json").is_file(), "CLI dependencies required"
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/acceptance/test_cli.py",
        "--disable-socket", "--allow-unix-socket", "--allow-hosts=127.0.0.1,localhost,::1", "--junitxml=" + str(junit)],
        cwd=root, env=env, capture_output=True, text=True, timeout=580)
    assert result.returncode == 0, result.stdout + result.stderr
    cases = list(ET.parse(junit).iter("testcase"))
    assert len(cases) >= 104
    assert all(not any(case.find(flag) is not None for flag in ("skipped", "failure", "error")) for case in cases)
