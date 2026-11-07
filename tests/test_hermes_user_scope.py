"""Real Hermes HTTP + PostgreSQL + local Qdrant ownership regression."""
import httpx
from hermes_lifecycle import personal_headers
import pytest

from test_agent_memory_records import memory as memory_fixture, Encoder

memory = memory_fixture
from hermes.service import create_app
from hermes.store import InMemoryStore


@pytest.mark.asyncio
async def test_same_tenant_list_never_leaks_another_user(memory, monkeypatch):
    m = memory
    monkeypatch.setenv("TANK_KEY_" + m.agent.upper(), "placeholder-agent-key")
    row = await m.records.save(m.agent, m.tenant, "placeholder private B", [],
                               meta={"user_id": "placeholder-user-b"})
    app = create_app(InMemoryStore(), Encoder(), records=m.records)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        headers, _ = personal_headers(
            "placeholder-agent-key", "GET", "/records",
            tenant=m.tenant, user="placeholder-user-a",
        )
        response = await client.get("/records", headers=headers,
                                    params={"tenant_id": m.tenant, "user_id": "placeholder-user-a"})
    assert response.status_code == 200
    assert row["id"] not in {item["id"] for item in response.json()["memories"]}


@pytest.mark.asyncio
async def test_real_app_ownership_on_every_operation(memory, monkeypatch):
    from hermes.user_scope import TENANT_WIDE_KINDS
    from test_agent_memory_records import inventory
    from hermes.publishing import Publisher
    m = memory
    monkeypatch.setenv("TANK_KEY_" + m.agent.upper(), "placeholder-agent-key")
    monkeypatch.setenv("TANK_API_KEY", "placeholder-workspace-key")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "placeholder-user-a,placeholder-user-b")
    monkeypatch.setitem(TENANT_WIDE_KINDS, m.agent, frozenset({"placeholder.shared"}))
    app = create_app(InMemoryStore(), Encoder(), records=m.records)
    key = "placeholder-agent-key"
    bare = {"X-Tank-Key": key}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        async def write(owner=None, kind="placeholder.personal", tenant=None, **changes):
            body = {
                "tenant_id": tenant or m.tenant, "text": "placeholder claim", "kind": kind,
                "source": "https://placeholder.example/evidence",
                "meta": {"user_id": owner} if owner else {}, **changes}
            if owner:
                body["user_id"] = owner
                headers, raw = personal_headers(key, "POST", "/memories", tenant=body["tenant_id"], user=owner, body=body)
                return await client.post("/memories", headers=headers, content=raw)
            return await client.post("/memories", headers=bare, json=body)
        assert (await write()).status_code == 422
        assert (await write(meta={"scope": "tenant"})).status_code == 422
        for owner in ([], {}, 4, " "):
            assert (await write(meta={"user_id": owner})).status_code == 422
        b = (await write("placeholder-user-b")).json()
        a = (await write("placeholder-user-a")).json()
        shared = (await write(kind="placeholder.shared")).json()
        # An owner on a shared kind still makes this particular row personal.
        private_shared = (await write("placeholder-user-b", kind="placeholder.shared")).json()
        foreign = (await write("placeholder-user-a", tenant=m.other)).json()
        replay = await write("placeholder-user-a", id=b["id"])
        assert replay.status_code == 409
        for user, own, other in (("placeholder-user-a", a, b), ("placeholder-user-b", b, a)):
            params = {"tenant_id": m.tenant, "user_id": user}
            list_headers, _ = personal_headers(key, "GET", "/records", tenant=m.tenant, user=user)
            rows = (await client.get("/records", params=params, headers=list_headers)).json()["memories"]
            ids = {row["id"] for row in rows}
            assert {own["id"], shared["id"]} <= ids
            assert not {other["id"], foreign["id"]} & ids
            if user.endswith("-a"):
                assert private_shared["id"] not in ids
            recall_body = {**params, "query": "placeholder query"}
            rh, rr = personal_headers(key, "POST", "/recall", tenant=m.tenant, user=user, body=recall_body)
            found = await client.post("/recall", headers=rh, content=rr)
            assert found.status_code == 200
            assert {row["id"] for row in found.json()["memories"]} == ids
            for identity in (other["id"], foreign["id"]):
                gh, _ = personal_headers(key, "GET", f"/records/{identity}", tenant=m.tenant, user=user)
                assert (await client.get("/records/" + identity, params=params, headers=gh)).status_code == 404
                dh, _ = personal_headers(key, "DELETE", f"/memories/{identity}", tenant=m.tenant, user=user)
                assert (await client.delete("/memories/" + identity, params=params, headers=dh)).status_code == 404
            oh, _ = personal_headers(key, "GET", f"/records/{own['id']}", tenant=m.tenant, user=user)
            assert (await client.get("/records/" + own["id"], params=params, headers=oh)).status_code == 200
        # Missing identity never broadens a personal read or deletion.
        unscoped = {"tenant_id": m.tenant}
        rows = (await client.get("/records", headers=bare, params=unscoped)).json()["memories"]
        assert [row["id"] for row in rows] == [shared["id"]]
        assert (await client.delete("/memories/" + b["id"], headers=bare, params=unscoped)).status_code == 404
        await Publisher(m.records).set_policy(m.agent, m.tenant, "placeholder-user-a", True, inventory())
        ws = "placeholder-workspace-key"
        admin = "placeholder-user-a"

        async def founder_publish(source_row):
            body = {"tenant_id": m.tenant, "agent": m.agent, "source_row": source_row}
            headers, raw = personal_headers(ws, "POST", "/founder/publish", tenant=m.tenant, user=admin, body=body)
            headers["X-Tervory-Admin"] = admin
            return await client.post("/founder/publish", headers=headers, content=raw)

        async def founder_get(row_id):
            headers, _ = personal_headers(ws, "GET", "/founder/records/" + row_id, tenant=m.tenant, user=admin)
            headers["X-Tervory-Admin"] = admin
            return await client.get("/founder/records/" + row_id, headers=headers)

        for row in (b, private_shared, foreign):
            denied = await founder_publish(row["id"])
            assert denied.status_code == 409
            assert denied.json()["detail"]["result"] == "missing"
            if row != foreign:
                assert (await founder_get(row["id"])).status_code == 404
        # Unsigned founder publish refused before ownership lookup.
        assert (await client.post(
            "/founder/publish",
            headers={"X-Tank-Key": ws, "X-Tervory-Admin": admin},
            json={"tenant_id": m.tenant, "agent": m.agent, "source_row": a["id"]},
        )).status_code == 401
        published = await founder_publish(a["id"])
        assert published.status_code == 200
        # User A's bulk forget leaves B's personal rows intact.
        th, _ = personal_headers(key, "DELETE", "/tenants/" + m.tenant, tenant=m.tenant, user="placeholder-user-a")
        deleted = await client.delete("/tenants/" + m.tenant, headers=th, params={"user_id": "placeholder-user-a"})
        assert deleted.status_code == 200
        assert await m.records.get(m.agent, m.tenant, b["id"]) is not None


@pytest.mark.asyncio
async def test_sql_filters_before_vector_search_and_limit(memory, monkeypatch):
    m = memory
    for i in range(5):
        await m.records.save(m.agent, m.tenant, f"placeholder private {i}", [], meta={"user_id": "placeholder-user-b"})
    own = await m.records.save(m.agent, m.tenant, "placeholder own", [], meta={"user_id": "placeholder-user-a"})
    original = m.records.index.search
    calls = []
    def search(*args, **kwargs):
        calls.append(kwargs["allowed_ids"])
        assert kwargs["allowed_ids"] == [own["id"]]
        return original(*args, **kwargs)
    monkeypatch.setattr(m.records.index, "search", search)
    found = await m.records.recall(m.agent, m.tenant, "placeholder query", None, 1, "client", user_id="placeholder-user-a")
    assert [r["id"] for r in found] == [own["id"]]
    assert calls
    calls.clear()
    assert await m.records.recall(m.agent, m.tenant, "placeholder query", None, 1, "client", user_id="placeholder-absent") == []
    assert calls == []


@pytest.mark.asyncio
async def test_chassis_sends_verified_owner_on_all_personal_calls():
    from chassis.memory import MemoryClient
    seen = []
    async def respond(request):
        seen.append(request)
        return httpx.Response(200, json={"memories": []})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = MemoryClient("http://placeholder", "placeholder-key", "opli", http)
        tenant = "11111111-1111-1111-1111-111111111111"
        user = "placeholder-user-a"
        with pytest.raises(ValueError):
            await client.remember(tenant, "placeholder claim", "placeholder.personal", "placeholder-source")
        await client.remember(tenant, "placeholder claim", "placeholder.personal", "placeholder-source", user_id=user)
        await client.recall(tenant, "placeholder query", user_id=user)
        await client.records(tenant, user_id=user)
        await client.forget(tenant, tenant, user_id=user)
    import json
    assert json.loads(seen[0].content)["meta"]["user_id"] == user
    assert json.loads(seen[1].content)["user_id"] == user
    assert seen[2].url.params["user_id"] == user
    assert seen[3].url.params["user_id"] == user
    for req in seen:
        assert req.headers["X-Tank-Key"] == "placeholder-key"
        assert req.headers["X-Tervory-User"] == user
        assert req.headers["X-Tervory-Tenant"] == tenant
        assert req.headers["X-Lifecycle-Timestamp"]
        assert req.headers["X-Lifecycle-Signature"]
