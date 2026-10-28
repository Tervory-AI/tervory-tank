"""PR #410 review: disposable SQL, local tokenizer, no model or external calls."""
import uuid

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from test_agent_memory_records import Encoder, inventory, memory as memory_fixture
from hermes.publishing import Publisher
from hermes.record_schema import PLATFORM_TENANT
from hermes.records import Records
from hermes.service import create_app
from hermes.store import InMemoryStore

memory = memory_fixture


def credentials(monkeypatch, agent):
    monkeypatch.setenv("TANK_API_KEY", "offline-workspace")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "offline-founder")
    monkeypatch.setenv("TANK_KEY_" + agent.upper(), "offline-room")
    return {"X-Tank-Key": "offline-workspace", "X-Tervory-Admin": "offline-founder"}


@pytest.mark.asyncio
async def test_id_read_authorization_exact_fields_unknown_and_collision(memory, monkeypatch):
    import memory_routes

    m = memory
    headers = credentials(monkeypatch, m.agent)
    rows = [await m.records.save(m.agent, tenant, "private offline claim", [])
            for tenant in (m.tenant, m.other)]
    app = create_app(InMemoryStore(), Encoder(), records=m.records)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://hermes") as client:
        for row in rows:
            path = "/founder/records/" + row["id"]
            response = await client.get(path, headers=headers)
            assert response.status_code == 200
            fields = {"id", "tenant_id", "agent", "claim", "evidence", "confidence",
                      "last_verified", "embed_model", "created_at", "updated_at"}
            assert set(response.json()) == fields
            assert response.json() == {key: row[key] for key in fields}
            for denied in ({}, {"X-Tank-Key": "offline-workspace"},
                           {**headers, "X-Tervory-Admin": "offline-client"},
                           {**headers, "X-Tank-Key": "offline-room"}):
                assert (await client.get(path, headers=denied)).status_code == 404
        unknown = "/founder/records/" + str(uuid.uuid4())
        assert (await client.get(unknown, headers=headers)).status_code == 404

        async def proxy(method, path, actor, **kwargs):
            response = await client.request(method, path, headers={**headers, "X-Tervory-Admin": actor})
            if not response.is_success:
                raise HTTPException(response.status_code, response.json()["detail"])
            return response.json()

        monkeypatch.setattr(memory_routes, "hermes", proxy)
        tank = FastAPI()
        tank.include_router(memory_routes.router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank), base_url="http://tank") as t:
            trusted = {"X-Tank-Key": "offline-workspace", "X-Tervory-User": "offline-founder",
                       "X-Tervory-Tenant": PLATFORM_TENANT}
            for row in rows:
                path = "/v1/memory/records/" + row["id"]
                assert (await t.get(path, headers=trusted)).json()["tenant_id"] == row["tenant_id"]
                for tenant in (m.tenant, m.other):
                    for role in ("", "reviewer", "founder"):
                        denied = {**trusted, "X-Tervory-User": "offline-client",
                                  "X-Tervory-Tenant": tenant, "X-Tervory-Role": role}
                        assert (await t.get(path, headers=denied)).status_code == 404
                assert (await t.get(path, headers={**trusted, "X-Tank-Key": "offline-room"})).status_code == 404
                assert (await t.get(path)).status_code == 404
            assert (await t.get(unknown.replace("/founder", "/v1/memory"), headers=trusted)).status_code == 404
            # Moving auth off the router must not open the existing admin corridor.
            assert (await t.get("/v1/memory/records", headers=trusted)).status_code == 404
        await m.records.save(m.peer, m.other, "different row", [], row_id=rows[0]["id"])
        assert (await client.get("/founder/records/" + rows[0]["id"], headers=headers)).status_code == 409


@pytest.mark.asyncio
async def test_tank_uses_existing_hermes_headers_fixed_origin_and_validation_shape(monkeypatch):
    import memory_routes

    credentials(monkeypatch, "tank")
    calls = []
    validation = [{"type": "value_error", "loc": ["body", "claim"], "msg": "Value error"}]
    status = 200

    def respond(request):
        calls.append(request)
        return httpx.Response(status, json={"id": "offline-id"} if status == 200 else {"detail": validation})

    original = httpx.AsyncClient

    def client(**kwargs):
        assert kwargs == {"timeout": 40, "trust_env": False, "follow_redirects": False}
        return original(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(memory_routes.httpx, "AsyncClient", client)
    assert await memory_routes.hermes("GET", "/founder/records/offline-id", "offline-founder") == {"id": "offline-id"}
    request = calls[0]
    assert str(request.url) == "http://hermes:8000/founder/records/offline-id"
    assert request.method == "GET"
    assert request.headers["X-Tank-Key"] == "offline-workspace"
    assert request.headers["X-Tervory-Admin"] == "offline-founder"
    status = 422
    with pytest.raises(HTTPException) as rejected:
        await memory_routes.hermes("POST", "/founder/memories", "offline-founder", body={})
    assert rejected.value.status_code == 422 and rejected.value.detail == validation


@pytest.mark.asyncio
@pytest.mark.parametrize("reviewed,empty", [(True, True), (False, True), (False, False)])
async def test_empty_or_unreviewed_inventory_stays_off_and_legacy_policy_refuses(memory, monkeypatch, reviewed, empty):
    m = memory
    headers = credentials(monkeypatch, m.agent)
    identifiers = {key: [] for key in ("names", "emails", "phones", "addresses", "client_domains")} if empty else inventory()
    identifiers["reviewed"] = reviewed
    publisher = Publisher(m.records)
    row = await m.records.save(m.agent, m.tenant, "Alice approves weekly deliveries.", [])
    await publisher.set_policy(m.agent, m.tenant, "offline-founder", True, inventory())
    await publisher.set_policy(m.agent, m.other, "offline-founder", True, inventory())
    s = m.records.schema(m.agent)
    app = create_app(InMemoryStore(), Encoder(), records=m.records)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://hermes") as client:
        response = await client.post("/founder/publish-policy", headers=headers, json={
            "tenant_id": m.tenant, "agent": m.agent, "enabled": True, "identifiers": identifiers,
        })
        assert response.status_code == 422
        assert await m.pool.fetchval(f"SELECT enabled FROM {s}.memory_publish_policy WHERE tenant_id=$1", uuid.UUID(m.tenant)) is False
        body = {"tenant_id": m.tenant, "agent": m.agent, "source_row": row["id"]}
        assert (await client.post("/founder/publish", headers=headers, json=body)).status_code == 403
        # Simulate a policy saved before the fix, in the isolated test schema.
        await m.pool.execute(f"UPDATE {s}.memory_publish_policy SET enabled=true WHERE tenant_id=$1", uuid.UUID(m.tenant))
        response = await client.post("/founder/publish", headers=headers, json=body)
        assert response.status_code == 409 and response.json()["detail"]["result"] == "refused"
        assert await m.pool.fetchval(f"SELECT enabled FROM {s}.memory_publish_policy WHERE tenant_id=$1", uuid.UUID(m.tenant)) is False
        assert await m.pool.fetchval(f"SELECT enabled FROM {s}.memory_publish_policy WHERE tenant_id=$1", uuid.UUID(m.other)) is True
        assert await m.records.list(m.agent, m.tenant, "platform") == []
        assert await m.pool.fetchval(f"SELECT count(*) FROM {s}.memory_publish_log WHERE tenant_id=$1 AND result='refused'", uuid.UUID(m.tenant)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("founder", [True, False])
async def test_api_counts_encoder_subword_and_special_tokens_before_saving(memory, monkeypatch, tmp_path, founder):
    from tokenizers import Tokenizer, models, pre_tokenizers, processors
    from tank import semantic_encoder

    m = memory
    headers = credentials(monkeypatch, m.agent)
    tokenizer = Tokenizer(models.WordPiece({"[UNK]": 0, "[CLS]": 1, "[SEP]": 2, "piece": 3, "##s": 4}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.post_processor = processors.TemplateProcessing(single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 1), ("[SEP]", 2)])
    tokenizer.enable_truncation(512)  # LocalEncoder must disable this when loading.
    tokenizer.save(str(tmp_path / "tokenizer.json"))
    (tmp_path / "revision").write_text(semantic_encoder.MODEL_REVISION)
    monkeypatch.setattr(semantic_encoder, "MODEL_PATH", tmp_path)
    encoder = semantic_encoder.LocalEncoder()
    calls = []

    def vector(text):
        calls.append(text)
        return [1., 0., 0., 0.]

    monkeypatch.setattr(encoder, "embed", vector)
    m.records.encoder = encoder
    accepted = "pieces " * 255  # 510 subwords plus CLS/SEP: exactly 512.
    rejected = accepted + "piece"  # 513 tokens, but only 256 whitespace words.
    app = create_app(InMemoryStore(), Encoder(), records=m.records)
    path, field = ("/founder/memories", "claim") if founder else ("/memories", "text")
    if not founder:
        headers = {"X-Tank-Key": "offline-room"}
    base = {"tenant_id": m.tenant, "agent": m.agent}
    if not founder:
        base.update(kind="fact", source="https://offline.example/proof")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://hermes") as client:
        response = await client.post(path, headers=headers, json={**base, "id": str(uuid.uuid4()), field: accepted})
        assert response.status_code == (200 if founder else 201)
        assert encoder._model is None  # Validation never loads/invokes a model.
        assert len(encoder._tokenizer.encode(accepted).ids) == 512
        assert len(encoder._tokenizer.encode(rejected).ids) == 513
        rejected_id = str(uuid.uuid4())
        response = await client.post(path, headers=headers, json={**base, "id": rejected_id, field: rejected})
        assert response.status_code == 422
        error = response.json()["detail"][0]
        assert error["loc"] == ["body", field] and error["type"] == "value_error"
        assert "Semantic input exceeds encoder context" in error["msg"]
        assert await m.records.get(m.agent, m.tenant, rejected_id) is None
        assert await m.pool.fetchval(f"SELECT count(*) FROM {m.records.schema(m.agent)}.memory_index_jobs") == 0
        assert calls == [accepted]
        # Missing/wrong pin fails closed, without a whitespace-count fallback.
        (tmp_path / "revision").write_text("wrong-pin")
        m.records.encoder = semantic_encoder.LocalEncoder()
        response = await client.post(path, headers=headers, json={**base, "id": rejected_id, field: "piece"})
        assert response.status_code == 503
        assert await m.records.get(m.agent, m.tenant, rejected_id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["encoder", "index"])
async def test_five_failures_terminal_across_restart_replay_and_scan(memory, failure):
    m = memory
    original_embed = m.records.encoder.embed
    original_upsert = m.records.index.upsert
    failures = []

    def fail(*args):
        failures.append(1)
        raise OSError("private driver text must not be recorded")

    if failure == "encoder":
        m.records.encoder.embed = fail
    else:
        m.records.index.upsert = fail
    row = await m.records.save(m.agent, m.tenant, "unchanged offline input", [])
    tenant, ident = uuid.UUID(m.tenant), uuid.UUID(row["id"])
    s = m.records.schema(m.agent)
    for attempt in range(2, 6):
        assert not await m.records.process_one(m.agent, tenant, ident, m.records.model)
        job = await m.pool.fetchrow(f"SELECT * FROM {s}.memory_index_jobs WHERE row_id=$1", ident)
        assert job["attempts"] == attempt
        assert job["last_error"] == ("embed_failed" if attempt == 5 else "OSError")
    restarted = Records(m.pool, m.records.index, m.records.encoder, m.records.model, list(m.records.agents))
    assert not await restarted.process_one(m.agent, tenant, ident, restarted.model)
    await restarted.save(m.agent, m.tenant, row["claim"], [], row_id=row["id"])
    await m.pool.execute(f"UPDATE {s}.memory_index_jobs SET run_at=now()")
    await restarted.tick()
    assert len(failures) == 5
    job = await m.pool.fetchrow(f"SELECT * FROM {s}.memory_index_jobs WHERE row_id=$1", ident)
    assert job["attempts"] == 5 and job["last_error"] == "embed_failed"
    assert (await restarted.get(m.agent, m.tenant, row["id"]))["claim"] == row["claim"]
    m.records.encoder.embed = original_embed
    m.records.index.upsert = original_upsert
    healthy = await restarted.save(m.agent, m.other, "other tenant still works", [])
    assert healthy["index_pending"] is False
    assert await restarted.get(m.agent, m.other, row["id"]) is None
    # A new pin is a different job; unchanged old input never resets its budget.
    upgraded = Records(m.pool, m.records.index, Encoder(), "offline-pin-v2", list(m.records.agents))
    await upgraded.tick()
    assert (await upgraded.get(m.agent, m.tenant, row["id"]))["embed_model"] == "offline-pin-v2"
    # Deletion must still remove vectors, even after more than five failures.
    original_delete = m.records.index.delete
    m.records.index.delete = fail
    assert await upgraded.forget(m.agent, m.tenant, row["id"]) == 1
    for _ in range(6):
        await upgraded.process_one(m.agent, tenant, ident, "offline-pin-v2", "delete")
    job = await m.pool.fetchrow(f"SELECT * FROM {s}.memory_index_jobs WHERE row_id=$1 AND target_model='offline-pin-v2'", ident)
    assert job["attempts"] == 6 and job["last_error"] == "OSError"
    m.records.index.delete = original_delete
    assert await upgraded.process_one(m.agent, tenant, ident, "offline-pin-v2", "delete")
