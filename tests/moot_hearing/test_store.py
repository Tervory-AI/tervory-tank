"""Real Postgres CAS tests in a uniquely named, disposable database only.

Hosted CI supplies pooltest on loopback. Local execution requires an explicit
MOOT_TEST_DATABASE_URL ending in _test; production URLs are always refused.
"""
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

from agents.zenas.core.moot.hearing import Actor, HearingError, change, turn, view
from agents.zenas.core.moot.hearing_store import HearingStore
from .test_hearing import hearing, problem, HUMANS, OWNER


@pytest_asyncio.fixture
async def pg_store():
    configured = os.environ.get("MOOT_TEST_DATABASE_URL")
    source = configured or (os.environ.get("POOL_SCHEMA_DATABASE_URL") if os.environ.get("GITHUB_ACTIONS") == "true" else None)
    if not source:
        pytest.skip("requires isolated MOOT_TEST_DATABASE_URL or hosted CI pooltest")
    parsed = urlsplit(source)
    assert parsed.hostname in ("127.0.0.1", "localhost", "::1"), "loopback disposable Postgres required"
    database = parsed.path.lstrip("/")
    assert database.endswith("_test") if configured else database.startswith("pooltest")
    name = "moot_" + uuid4().hex + "_test"
    admin = await asyncpg.connect(source)
    await admin.execute(f'CREATE DATABASE "{name}"')
    target = urlunsplit(parsed._replace(path="/" + name))
    pool = None
    try:
        pool = await asyncpg.create_pool(target, min_size=1, max_size=4)
        async with pool.acquire() as conn:
            await conn.execute("CREATE SCHEMA agent_zenas")
            await conn.execute(Path("agents/zenas/core/moot/hearing_schema.sql").read_text())
        yield HearingStore(pool)
    finally:
        if pool:
            await pool.close()
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()


def transition(action):
    return lambda s, actor, revision, payload: change(s, actor, revision, action, payload)


async def new(store):
    seats = hearing()["seats"]
    s = await store.create(OWNER, str(uuid4()), problem(), seats)
    for action in ("lock", "start"):
        s = await store.mutate(OWNER, s["id"], str(uuid4()), s["revision"], action, {}, transition(action))
    return s


@pytest.mark.asyncio
async def test_duplicate_human_turn_survives_restart_and_only_one_event(pg_store):
    s = await new(pg_store)
    req = str(uuid4())
    args = (HUMANS["applicant"], s["id"], req, s["revision"], "turn", {"kind": "submission", "text": "Actual human argument"})
    fn = lambda state, actor, rev, payload: turn(state, actor, rev, payload)
    first, retry = await asyncio.gather(pg_store.mutate(*args, fn), HearingStore(pg_store.pool).mutate(*args, fn))
    assert first == retry
    saved = await HearingStore(pg_store.pool).load(HUMANS["applicant"], s["id"])
    assert len(saved["transcript"]) == 1
    async with pg_store.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM agent_zenas.moot_hearing_events WHERE hearing_id=$1 AND kind='turn'", UUID(s["id"])) == 1
    with pytest.raises(HearingError, match="idempotency_conflict"):
        await pg_store.mutate(*args[:-1], {"kind": "submission", "text": "changed retry"}, fn)


@pytest.mark.asyncio
async def test_handover_and_turn_compete_one_revision_wins(pg_store):
    s = await new(pg_store)
    commands = [
        pg_store.mutate(OWNER, s["id"], str(uuid4()), s["revision"], "handover", {"seat": "applicant", "controller": {"kind": "ai"}}, transition("handover")),
        pg_store.mutate(HUMANS["applicant"], s["id"], str(uuid4()), s["revision"], "turn", {"kind": "submission", "text": "student"}, lambda s, a, r, p: turn(s, a, r, p)),
    ]
    results = await asyncio.gather(*commands, return_exceptions=True)
    assert sum(isinstance(r, dict) for r in results) == 1
    assert sum(isinstance(r, HearingError) for r in results) == 1
    saved = await pg_store.load(OWNER, s["id"])
    assert saved["revision"] == s["revision"] + 1


@pytest.mark.asyncio
async def test_replay_projects_current_roles_never_old_judge_authority(pg_store):
    # A founder create retry returns current state, not a saved initial controller map.
    create_req = str(uuid4()); p = problem(); seats = hearing()["seats"]
    s = await pg_store.create(OWNER, create_req, p, seats)
    s = await pg_store.mutate(OWNER, s["id"], str(uuid4()), s["revision"], "handover", {"seat": "judge", "controller": {"kind": "ai"}}, transition("handover"))
    retry = await pg_store.create(OWNER, create_req, p, seats)
    assert retry["revision"] == s["revision"] and retry["seats"]["judge"]["kind"] == "ai"
    with pytest.raises(HearingError, match="not_found"):
        await pg_store.load(HUMANS["judge"], s["id"])
    other = Actor(str(uuid4()), OWNER.user_id, "us-east", True)
    with pytest.raises(HearingError, match="not_found"):
        await pg_store.load(other, s["id"])
    assert "never counsel" not in json.dumps(view(retry, HUMANS["applicant"], "applicant"))


def test_schema_is_additive_and_in_room_startup_schema():
    sql = Path("agents/zenas/core/moot/hearing_schema.sql").read_text()
    assert sql in Path("agents/zenas/schema.sql").read_text()
    assert "DROP " not in sql and "CREATE TABLE IF NOT EXISTS" in sql
