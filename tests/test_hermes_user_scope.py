"""Real Hermes HTTP + PostgreSQL + local Qdrant ownership regression."""
import httpx
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
        response = await client.get("/records", headers={"X-Tank-Key": "placeholder-agent-key"},
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
    headers = {"X-Tank-Key": "placeholder-agent-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        async def write(owner=None, kind="placeholder.personal", tenant=None, **changes):
            return await client.post("/memories", headers=headers, json={
                "tenant_id": tenant or m.tenant, "text": "placeholder claim", "kind": kind,
                "source": "https://placeholder.example/evidence",
                "meta": {"user_id": owner} if owner else {}, **changes})
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
            rows = (await client.get("/records", params=params, headers=headers)).json()["memories"]
            ids = {row["id"] for row in rows}
            assert {own["id"], shared["id"]} <= ids
            assert not {other["id"], foreign["id"]} & ids
            if user.endswith("-a"):
                assert private_shared["id"] not in ids
            found = await client.post("/recall", headers=headers, json={**params, "query": "placeholder query"})
            assert found.status_code == 200
            assert {row["id"] for row in found.json()["memories"]} == ids
            for identity in (other["id"], foreign["id"]):
                assert (await client.get("/records/" + identity, params=params, headers=headers)).status_code == 404
                assert (await client.delete("/memories/" + identity, params=params, headers=headers)).status_code == 404
            assert (await client.get("/records/" + own["id"], params=params, headers=headers)).status_code == 200
        # Missing identity never broadens a personal read or deletion.
        unscoped = {"tenant_id": m.tenant}
        rows = (await client.get("/records", headers=headers, params=unscoped)).json()["memories"]
        assert [row["id"] for row in rows] == [shared["id"]]
        assert (await client.delete("/memories/" + b["id"], headers=headers, params=unscoped)).status_code == 404
        await Publisher(m.records).set_policy(m.agent, m.tenant, "placeholder-user-a", True, inventory())
        founder_headers = {"X-Tank-Key": "placeholder-workspace-key", "X-Tervory-Admin": "placeholder-user-a"}
        for row in (b, private_shared, foreign):
            denied = await client.post("/founder/publish", headers=founder_headers,
                json={"tenant_id": m.tenant, "agent": m.agent, "source_row": row["id"]})
            assert denied.status_code == 409
            assert denied.json()["detail"]["result"] == "missing"
            if row != foreign:
                assert (await client.get("/founder/records/" + row["id"], headers=founder_headers)).status_code == 404
        published = await client.post("/founder/publish", headers=founder_headers,
            json={"tenant_id": m.tenant, "agent": m.agent, "source_row": a["id"]})
        assert published.status_code == 200
        # User A's bulk forget leaves B's personal rows intact.
        deleted = await client.delete("/tenants/" + m.tenant, headers=headers, params={"user_id": "placeholder-user-a"})
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
