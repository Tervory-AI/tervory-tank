"""D1/D2/D3: offline SQL + local Qdrant, no model downloads or client data.

Set MEMORY_TEST_DATABASE_URL to a disposable loopback PostgreSQL database.
Every test creates unique schemas; no production migration/backfill is exercised.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.parse import urlsplit
import uuid

import asyncpg
import httpx
import pytest
import pytest_asyncio
from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hermes.deidentify import deidentify  # noqa: E402
from hermes.publishing import Publisher  # noqa: E402
from hermes.record_index import RecordIndex, collection  # noqa: E402
from hermes.record_schema import (
    AGENTS,
    BEGIN,
    PLATFORM_TENANT,
    generated_block,
    schema_sql,
)  # noqa: E402
from hermes.records import Records, public_row  # noqa: E402
from hermes.references import reference_corpora  # noqa: E402
from hermes.service import create_app  # noqa: E402
from hermes.store import InMemoryStore  # noqa: E402


class Encoder:
    def __init__(self):
        self.calls = []

    def validate(self, text):
        # Tokenizer boundaries are exercised with LocalEncoder in test_review.py.
        pass

    def embed(self, text):
        self.calls.append(text)
        return [1.0, 0.0, 0.0, 0.0]


@pytest_asyncio.fixture
async def memory():
    url = os.environ.get("MEMORY_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set MEMORY_TEST_DATABASE_URL to a disposable local PostgreSQL database"
        )
    if urlsplit(url).hostname not in ("localhost", "127.0.0.1", "::1"):
        pytest.fail("Memory integration tests require a loopback test database")
    pool = await asyncpg.create_pool(
        url, min_size=1, max_size=1, statement_cache_size=0, ssl=False, timeout=10
    )
    name = "memtest_" + uuid.uuid4().hex[:12]
    index = RecordIndex(QdrantClient(":memory:"), 4)
    records = Records(pool, index, Encoder(), "offline-pin-v1", [name, name + "_peer"])
    await records.setup()
    try:
        yield SimpleNamespace(
            records=records,
            pool=pool,
            agent=name,
            peer=name + "_peer",
            tenant=str(uuid.uuid4()),
            other=str(uuid.uuid4()),
        )
    finally:
        # Disposable test schemas only. Terminate avoids socket-close differences
        # between native PostgreSQL and the optional PGlite local test runner.
        async with pool.acquire() as conn:
            for agent in records.agents:
                await conn.execute(
                    f"DROP SCHEMA IF EXISTS {records.schema(agent)} CASCADE"
                )
        pool.terminate()
        index.client.close()


def inventory(**changes):
    return dict(
        reviewed=True,
        names=["alice rowan"],
        emails=["alice@client.example"],
        phones=["+27 21 555 0199"],
        addresses=["42 harbour road, unit 8"],
        client_domains=["client.example"],
        **changes,
    )


def test_all_agent_schema_files_use_one_generator():
    for agent in AGENTS:
        path = ROOT / (
            "tank/schema.sql"
            if agent == "tank"
            else f"agents/{'_template' if agent == 'template' else agent}/schema.sql"
        )
        text = path.read_text()
        assert text.count(BEGIN) == 1
        assert text.endswith(generated_block(agent))
    assert "CREATE SCHEMA" not in generated_block("radix")


@pytest.mark.parametrize(
    "private",
    [
        "alice rowan",
        "Alice",
        "alice@client.example",
        "+27 21 555 0199",
        "42 harbour road, unit 8",
        "https://client.example/account",
        "https://portal.client.example/account",
        "client.example/private",
        "https%3A%2F%2Fclient.example%2Fprivate",
        "11111111-1111-1111-1111-111111111111",
    ],
)
def test_deidentifier_removes_each_identity_type(private):
    claim, evidence = deidentify(
        "retain this useful fact: " + private,
        [
            "https://client.example/account",
            "urn:tervory:command:private",
            "https://public.example/paper",
            "https://public.example/?name=alice",
        ],
        "11111111-1111-1111-1111-111111111111",
        inventory(),
    )
    assert private.lower() not in claim.lower()
    assert "retain this useful fact" in claim
    assert evidence == ["https://public.example/paper"]


def test_deidentifier_general_patterns_and_fail_closed():
    claim, _ = deidentify(
        "retain: Bob Smith; bob@unknown.example; +1 (415) 555-0198; 123 Main Street",
        [],
        str(uuid.uuid4()),
        inventory(),
    )
    for value in ("Bob", "Smith", "bob@", "415", "123 Main"):
        assert value not in claim
    for bad in ({}, {"reviewed": True}, {**inventory(), "reviewed": False}):
        with pytest.raises(ValueError):
            deidentify("retain fact", [], str(uuid.uuid4()), bad)
    with pytest.raises(ValueError):
        deidentify("alice rowan", [], str(uuid.uuid4()), inventory())


def test_reference_registry_keeps_zenas_in_place_and_read_only():
    for region in ("za", "us-east"):
        entries = reference_corpora("zenas", region)
        assert len(entries) == 1
        assert entries[0]["read_only"] is True
        assert entries[0]["search"] == "/law/search"
    assert reference_corpora("tiger", "za") == []


@pytest.mark.asyncio
async def test_schema_empty_reapply_and_agent_role(memory):
    m = memory
    await m.records.setup()
    async with m.pool.acquire() as c:
        columns = {
            r["column_name"]
            for r in await c.fetch(
                """SELECT column_name FROM information_schema.columns
            WHERE table_schema=$1 AND table_name='memory_records' """,
                m.records.schema(m.agent),
            )
        }
        assert {
            "id",
            "tenant_id",
            "agent",
            "claim",
            "evidence",
            "confidence",
            "last_verified",
            "embed_model",
            "created_at",
            "updated_at",
        } <= columns
        # The restricted role only has its pre-provisioned schema, no CREATE DATABASE.
        role = m.records.schema(m.peer)
        await c.execute(f"CREATE ROLE {role}")
        await c.execute(
            f"GRANT USAGE, CREATE ON SCHEMA {m.records.schema(m.peer)} TO {role}"
        )
    await m.records.setup()
    async with m.pool.acquire() as c:
        try:
            await c.execute(f"SET ROLE {role}")
            await c.execute(schema_sql(m.peer, include_schema=False))
        finally:
            await c.execute("RESET ROLE")
            await c.execute(f"DROP SCHEMA {m.records.schema(m.peer)} CASCADE")
            await c.execute(f"DROP ROLE {role}")


@pytest.mark.asyncio
async def test_commit_before_encoder_vector_and_durable_retry(memory):
    m = memory
    original = m.records.process_one
    order = []

    async def observe_commit(agent, tenant, ident, model, operation="upsert"):
        async with m.pool.acquire() as c:
            assert not c.is_in_transaction()
            assert (
                await c.fetchval(
                    f"SELECT claim FROM {m.records.schema(agent)}.memory_records WHERE tenant_id=$1 AND id=$2",
                    tenant,
                    ident,
                )
                == "fixture fact"
            )
            assert (
                await c.fetchval(
                    f"SELECT count(*) FROM {m.records.schema(agent)}.memory_index_jobs WHERE tenant_id=$1 AND row_id=$2",
                    tenant,
                    ident,
                )
                == 1
            )
        order.append("committed row and job")
        return await original(agent, tenant, ident, model, operation)

    m.records.process_one = observe_commit
    real_upsert = m.records.index.upsert

    def failed_vector(row, vector, model):
        assert order == ["committed row and job"]
        assert m.records.encoder.calls == ["fixture fact"]
        order.append("vector")
        # Simulate lost acknowledgement AFTER Qdrant accepts the point.
        real_upsert(row, vector, model)
        raise OSError("private driver URL must never enter the retry log")

    m.records.index.upsert = failed_vector
    row = await m.records.save(
        m.agent,
        m.tenant,
        "fixture fact",
        ["https://public.example/proof"],
        confidence=0.8,
    )
    assert row["index_pending"] is True and row["embed_model"] == ""
    assert order == ["committed row and job", "vector"]
    s = m.records.schema(m.agent)
    job = await m.pool.fetchrow(
        f"SELECT * FROM {s}.memory_index_jobs WHERE tenant_id=$1", uuid.UUID(m.tenant)
    )
    assert job["attempts"] == 1 and job["last_error"] == "OSError"
    # A new worker instance resumes the persisted job, using the same row id.
    m.records.index.upsert = real_upsert
    restarted = Records(
        m.pool, m.records.index, Encoder(), m.records.model, list(m.records.agents)
    )
    assert await restarted.process_one(
        m.agent, uuid.UUID(m.tenant), uuid.UUID(row["id"]), restarted.model
    )
    stored = await restarted.get(m.agent, m.tenant, row["id"])
    assert stored["embed_model"] == restarted.model and stored["confidence"] == 0.8
    assert (
        await m.pool.fetchval(
            f"SELECT count(*) FROM {s}.memory_index_jobs WHERE tenant_id=$1",
            uuid.UUID(m.tenant),
        )
        == 0
    )
    points, _ = m.records.index.client.scroll(
        collection(m.agent, restarted.model), with_vectors=False
    )
    assert len(points) == 1
    assert points[0].payload["row_id"] == row["id"]
    assert not {"claim", "evidence", "text", "meta"} & points[0].payload.keys()


@pytest.mark.asyncio
async def test_sql_failure_never_calls_encoder_or_vector(memory):
    m = memory
    with pytest.raises(asyncpg.CheckViolationError):
        await m.records.save(m.agent, m.tenant, "", [])
    assert m.records.encoder.calls == []
    assert m.records.index.client.get_collections().collections == []


@pytest.mark.asyncio
async def test_encoder_failure_keeps_record_and_job(memory):
    m = memory

    def unavailable(_):
        raise RuntimeError("encoder unavailable")

    m.records.encoder.embed = unavailable
    row = await m.records.save(m.agent, m.tenant, "fact survives", [])
    assert row["index_pending"] is True
    assert (await m.records.get(m.agent, m.tenant, row["id"]))[
        "claim"
    ] == "fact survives"
    assert m.records.index.client.get_collections().collections == []


@pytest.mark.asyncio
async def test_reembed_only_stale_rows_with_tenant_scope(memory):
    m = memory
    stale = await m.records.save(
        m.agent, m.tenant, "stale fact", ["https://public.example/source"]
    )
    fresh = await m.records.save(m.agent, m.tenant, "fresh fact", [])
    other = await m.records.save(m.agent, m.other, "other tenant", [])
    s = m.records.schema(m.agent)
    await m.pool.execute(
        f"UPDATE {s}.memory_records SET embed_model=$3 WHERE tenant_id=$1 AND id=$2",
        uuid.UUID(m.tenant),
        uuid.UUID(fresh["id"]),
        "offline-pin-v2",
    )
    upgraded = Records(
        m.pool, m.records.index, Encoder(), "offline-pin-v2", list(m.records.agents)
    )
    assert await upgraded.schedule_stale(m.agent, m.tenant) == 1
    assert await upgraded.schedule_stale(m.agent, m.tenant) == 0
    jobs = await m.pool.fetch(
        f"SELECT row_id FROM {s}.memory_index_jobs WHERE tenant_id=$1",
        uuid.UUID(m.tenant),
    )
    assert [str(j["row_id"]) for j in jobs] == [stale["id"]]
    await upgraded.process_one(
        m.agent, uuid.UUID(m.tenant), uuid.UUID(stale["id"]), upgraded.model
    )
    assert upgraded.encoder.calls == ["stale fact"]
    assert (await upgraded.get(m.agent, m.tenant, stale["id"]))["evidence"] == stale[
        "evidence"
    ]
    assert (await upgraded.get(m.agent, m.other, other["id"]))[
        "embed_model"
    ] == "offline-pin-v1"


@pytest.mark.asyncio
async def test_tenant_agent_tier_isolation_and_idempotent_replay(memory):
    m = memory
    ident = str(uuid.uuid4())
    row = await m.records.save(m.agent, m.tenant, "private fact", [], row_id=ident)
    again = await m.records.save(m.agent, m.tenant, "private fact", [], row_id=ident)
    assert row["id"] == again["id"]
    assert len(await m.records.list(m.agent, m.tenant)) == 1
    assert await m.records.list(m.peer, m.tenant) == []
    assert await m.records.list(m.agent, m.other) == []
    assert await m.records.list(m.agent, m.tenant, "platform") == []
    with pytest.raises(ValueError):
        await m.records.save(m.agent, m.other, "private fact", [], row_id=ident)
    # Even a poisoned index cannot bypass authoritative SQL tenant filtering.
    m.records.index.search = lambda *args: [(ident, 1.0)]
    assert await m.records.recall(m.agent, m.other, "query", None, 8, "client") == []
    assert await m.records.recall(m.peer, m.tenant, "query", None, 8, "client") == []


@pytest.mark.asyncio
async def test_delete_is_scoped_and_old_tombstone_cannot_remove_recreated_row(memory):
    m = memory
    row = await m.records.save(m.agent, m.tenant, "fact", [])
    assert await m.records.forget(m.agent, m.other, row["id"]) == 0
    assert await m.records.forget(m.agent, m.tenant, row["id"]) == 1
    assert await m.records.recall(m.agent, m.tenant, "fact", None, 8, "client") == []
    await m.records.save(m.agent, m.tenant, "fact", [], row_id=row["id"])
    await m.records.tick()
    assert (
        len(await m.records.recall(m.agent, m.tenant, "fact", None, 8, "client")) == 1
    )


@pytest.mark.asyncio
async def test_publish_off_refuses_and_logs_without_platform_data(memory):
    m = memory
    row = await m.records.save(m.agent, m.tenant, "private fixture", [])
    publisher = Publisher(m.records)
    assert (await publisher.publish(m.agent, m.tenant, row["id"], "founder-fixture"))[
        "result"
    ] == "disabled"
    assert await m.records.list(m.agent, m.tenant, "platform") == []
    log = await m.pool.fetchrow(
        f"SELECT * FROM {m.records.schema(m.agent)}.memory_publish_log WHERE tenant_id=$1",
        uuid.UUID(m.tenant),
    )
    assert log["actor"] == "founder-fixture" and log["happened_at"]
    assert str(log["source_row"]) == row["id"] and log["result"] == "disabled"
    assert log["published_row"] is None


# Short private tokens can turn up by chance in a uuid, the memtest_ hex agent
# name or the timestamp microseconds, so they are only looked for in the
# fields that carry client content. Long or unique strings are checked across
# the whole published record.
PUBLISH_SHORT_PRIVATE = ("alice", "555", "harbour")
PUBLISH_CONTENT_FIELDS = ("claim", "evidence", "meta")
PUBLISH_LONG_PRIVATE = (
    "+27 21 555 0199",
    "555 0199",
    "alice rowan",
    "42 harbour road",
    "client.example",
)


def _publish_leaks(published: dict, tenant: str, row_id: str) -> list[str]:
    """Private strings found in a published row: whole record for long ones, content fields for short ones."""
    whole = json.dumps(published, default=str)
    content = json.dumps(
        {field: published.get(field) for field in PUBLISH_CONTENT_FIELDS}, default=str
    )
    leaks = [
        f"record:{token}"
        for token in (str(tenant), str(row_id), *PUBLISH_LONG_PRIVATE)
        if token in whole
    ]
    leaks += [f"content:{token}" for token in PUBLISH_SHORT_PRIVATE if token in content]
    return leaks


def test_publish_leak_check_ignores_random_555_but_catches_real_leaks():
    tenant, row_id = str(uuid.uuid4()), str(uuid.uuid4())
    clean = {
        "id": "b971213e-21d7-519c-ba11-555aa41dc3d7",
        "tenant_id": PLATFORM_TENANT,
        "agent": "memtest_55509ce12d4b",
        "claim": "weekly deliveries; [IDENTITY]; [IDENTITY]; [IDENTITY]; [IDENTITY]; [URL]",
        "evidence": ["https://public.example/source"],
        "meta": {},
        "created_at": "2026-10-31T20:15:41.555123+00:00",
    }
    # The old whole-record scan for "555" flagged this clean row; the new check does not.
    assert "555" in json.dumps(clean)
    assert _publish_leaks(clean, tenant, row_id) == []
    for field, value in (
        ("claim", "weekly deliveries; call 555"),
        ("evidence", ["https://public.example/555"]),
        ("meta", {"phone": "555"}),
    ):
        assert _publish_leaks({**clean, field: value}, tenant, row_id) == ["content:555"]
    assert "record:+27 21 555 0199" in _publish_leaks(
        {**clean, "note": "+27 21 555 0199"}, tenant, row_id
    )
    assert _publish_leaks({**clean, "source_tenant": tenant}, tenant, row_id) == [
        f"record:{tenant}"
    ]
    assert _publish_leaks({**clean, "source_row": row_id}, tenant, row_id) == [
        f"record:{row_id}"
    ]
    assert _publish_leaks({**clean, "claim": "alice at 42 harbour road"}, tenant, row_id) == [
        "record:42 harbour road",
        "content:alice",
        "content:harbour",
    ]


@pytest.mark.asyncio
async def test_explicit_publish_scrubs_and_optin_is_per_client_agent(memory):
    m = memory
    row = await m.records.save(
        m.agent,
        m.tenant,
        f"weekly deliveries; alice rowan; {m.tenant}; +27 21 555 0199; 42 harbour road, unit 8; https://client.example/x",
        ["https://client.example/private", "https://public.example/source"],
        confidence=0.75,
        meta={"private": "alice@client.example"},
    )
    publisher = Publisher(m.records)
    await publisher.set_policy(m.agent, m.tenant, "founder-fixture", True, inventory())
    assert (await publisher.publish(m.peer, m.tenant, row["id"], "founder-fixture"))[
        "result"
    ] == "disabled"
    assert (await publisher.publish(m.agent, m.other, row["id"], "founder-fixture"))[
        "result"
    ] == "disabled"
    result = await publisher.publish(m.agent, m.tenant, row["id"], "founder-fixture")
    assert result["result"] == "published"
    published = await m.records.get(
        m.agent, m.tenant, result["published_row"], "platform"
    )
    assert published["tenant_id"] == PLATFORM_TENANT
    assert published["evidence"] == ["https://public.example/source"]
    assert published["meta"] == {} and published["confidence"] == 0.75
    leaks = _publish_leaks(published, m.tenant, row["id"])
    assert not leaks, (leaks, published)
    assert (await publisher.publish(m.agent, m.tenant, row["id"], "founder-fixture"))[
        "result"
    ] == "already_published"
    assert len(await m.records.list(m.agent, m.tenant, "platform")) == 1
    assert (
        await m.pool.fetchval(
            f"SELECT count(*) FROM {m.records.schema(m.agent)}.memory_publish_log WHERE tenant_id=$1",
            uuid.UUID(m.tenant),
        )
        == 2
    )
    await publisher.set_policy(m.agent, m.tenant, "founder-fixture", False, {})
    assert (await publisher.publish(m.agent, m.tenant, row["id"], "founder-fixture"))[
        "result"
    ] == "disabled"


@pytest.mark.asyncio
async def test_founder_chat_to_sql_row_and_http_authorization(memory, monkeypatch):
    """Actual command.route_turn -> Hermes ASGI -> SQL. Model path must not run."""
    import command
    import memory_routes

    m = memory
    monkeypatch.setenv("TANK_API_KEY", "memory-workspace-fixture")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder-fixture")
    monkeypatch.setenv("TANK_KEY_" + m.agent.upper(), "memory-agent-fixture")
    app = create_app(InMemoryStore(), Encoder(), records=m.records)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://hermes"
    ) as http:
        headers = {
            "X-Tank-Key": "memory-workspace-fixture",
            "X-Tervory-Admin": "founder-fixture",
        }
        for denied in (
            {"X-Tank-Key": "memory-workspace-fixture"},
            {
                "X-Tank-Key": "memory-agent-fixture",
                "X-Tervory-Admin": "founder-fixture",
            },
        ):
            response = await http.post(
                "/founder/publish-policy",
                headers=denied,
                json={"tenant_id": m.tenant, "agent": m.agent, "enabled": True},
            )
            assert response.status_code == 404

        async def transport(method, path, actor, *, body=None, params=None):
            response = await http.request(
                method,
                path,
                json=body,
                params=params,
                headers={**headers, "X-Tervory-Admin": actor},
            )
            assert response.status_code == 200, response.text
            return response.json()

        monkeypatch.setattr(memory_routes, "hermes", transport)
        for incomplete in ({}, {"identifiers": {"reviewed": True}}):
            refused_policy = await http.post(
                "/founder/publish-policy",
                headers=headers,
                json={
                    "tenant_id": m.tenant,
                    "agent": m.agent,
                    "enabled": True,
                    **incomplete,
                },
            )
            assert refused_policy.status_code == 422

        # Only Tank's existing zero-cost receipt dependency is substituted.
        # The real command actor check, remember route, Hermes auth and SQL run.
        class Ledger:
            async def fetchval(self, sql, *args):
                assert "INSERT INTO tank.ledger" in sql and args[0] == uuid.UUID(
                    m.tenant
                )
                return uuid.uuid4()

        async def no_model(*args, **kwargs):
            pytest.fail("Explicit remember must not call a model")

        monkeypatch.setitem(
            sys.modules,
            "main",
            SimpleNamespace(
                pool=lambda: Ledger(),
                box_region=lambda: "us-east",
                Message=object,
                RouteRequest=object,
                run_route=no_model,
            ),
        )
        turn = uuid.UUID("33333333-3333-4333-8333-333333333333")
        actor = command.Actor(uuid.UUID(m.tenant), "founder-fixture", False)
        reply = await command.route_turn(
            actor,
            [
                {
                    "role": "user",
                    "content": f"Remember for {m.agent} that fixture deliveries happen on Tuesdays.",
                }
            ],
            task_id=turn,
        )
        memory_id = str(uuid.uuid5(turn, "memory:" + m.agent))
        assert json.loads(reply.content) == {
            "text": "fixture deliveries happen on Tuesdays.\n\n" + memory_id,
            "actions": [],
        }
        listing = await http.get(
            "/founder/records",
            headers=headers,
            params={"tenant_id": m.tenant, "agent": m.agent},
        )
        row = listing.json()["memories"][0]
        assert row["claim"] == "fixture deliveries happen on Tuesdays."
        assert row["evidence"] == ["urn:tervory:command:" + str(turn)]
        assert row["confidence"] == 0.5 and row["last_verified"] is None
        assert row["embed_model"] == "offline-pin-v1"
        # Acceptance evidence is read directly back from the real test database.
        dbrow = await m.pool.fetchrow(
            f"SELECT * FROM {m.records.schema(m.agent)}.memory_records WHERE tenant_id=$1 AND id=$2",
            uuid.UUID(m.tenant),
            uuid.UUID(row["id"]),
        )
        assert public_row(dbrow) == row
        from fastapi import FastAPI

        tank_app = FastAPI()
        tank_app.include_router(memory_routes.router)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=tank_app), base_url="http://tank"
        ) as tank_http:
            inspected = await tank_http.get(
                "/v1/memory/records/" + memory_id,
                headers={"X-Tank-Key": "memory-workspace-fixture",
                         "X-Tervory-User": "founder-fixture",
                         "X-Tervory-Tenant": PLATFORM_TENANT},
            )
        assert inspected.status_code == 200
        assert inspected.json() == {key: row[key] for key in (
            "id", "tenant_id", "agent", "claim", "evidence", "confidence",
            "last_verified", "embed_model", "created_at", "updated_at",
        )}
        path = os.environ.get("MEMORY_PROOF_PATH")
        if path:
            Path(path).write_text(
                json.dumps(
                    {
                        "database": await m.pool.fetchval("SELECT version()"),
                        "fixture_only": True,
                        "entrypoint": "command.route_turn -> Hermes -> SQL -> GET /v1/memory/records/{id}",
                        "chat": json.loads(reply.content),
                        "row": inspected.json(),
                        "browser_path": "/api/memory/records/" + memory_id,
                    },
                    indent=2,
                )
                + "\n"
            )
        refused = await http.post(
            "/founder/publish",
            headers=headers,
            json={"tenant_id": m.tenant, "agent": m.agent, "source_row": row["id"]},
        )
        assert (
            refused.status_code == 403
            and refused.json()["detail"]["result"] == "disabled"
        )


@pytest.mark.asyncio
async def test_new_write_works_during_vector_outage_and_legacy_delete_is_scoped(
    memory, monkeypatch
):
    from hermes.store import Memory

    m = memory
    monkeypatch.setenv("TANK_KEY_" + m.agent.upper(), "agent-fixture")
    legacy = InMemoryStore()
    ident = str(uuid.uuid4())
    legacy.add(
        "mem_" + m.agent,
        Memory(ident, m.tenant, "old fact", "fact", [], {}, 1, "fixture"),
        [1.0, 0.0, 0.0, 0.0],
    )
    app = create_app(legacy, Encoder(), records=m.records)

    def unavailable(*args):
        raise OSError("offline vector outage")

    m.records.index.upsert = unavailable
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://hermes"
    ) as http:
        headers = {"X-Tank-Key": "agent-fixture"}
        response = await http.post(
            "/memories",
            headers=headers,
            json={
                "tenant_id": m.tenant,
                "text": "new fact",
                "kind": "fact",
                "source": "https://public.example/source",
            },
        )
        assert response.status_code == 201 and response.json()["index_pending"] is True
        for tenant, status in ((m.other, 404), (m.tenant, 200)):
            deleted = await http.delete(
                "/memories/" + ident, headers=headers, params={"tenant_id": tenant}
            )
            assert deleted.status_code == status
