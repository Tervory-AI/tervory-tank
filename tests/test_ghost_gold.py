"""Ghost joins shared review intake without making incident memory public."""
from datetime import date
import secrets

import gold
import httpx
import pytest
import pytest_asyncio
import training

from agents.ghost.gold_sources import candidates
from agents.ghost.store import Store
from agents.ghost.models import PLATFORM_TENANT
from test_train1 import database as _database

database = _database


@pytest_asyncio.fixture
async def incident(tmp_path):
    store = Store(tmp_path / "ghost.sqlite3")
    item = store.open(PLATFORM_TENANT, "workspace", "health", "look")
    await store.remember(PLATFORM_TENANT, item | dict(
        state="solved", cause="application_bug", fix="reviewed_pr_deployed", solved_at="2026-10-21T12:00:00+00:00"))
    yield candidates(store, "us-east")[0]
    store.close()


def test_ghost_registered_for_founder_review_and_room_collection(incident):
    assert "ghost" in gold.AGENTS and "ghost" in training.ROOMS
    assert training.valid_auto_candidate(incident, "ghost", "us-east")
    assert not training.exportable(dict(incident, tenant_id=gold.PLATFORM_TENANT,
                                       active=True, holdout=False, client_matter=False))


@pytest.mark.parametrize("changes", [
    {"public": True}, {"public": None}, {"client_matter": True}, {"tenant_id": "client"},
    {"region": "za"}, {"skill_id": "base.find_site"}, {"label_family": "ghost:incident:2026-13"},
    {"label_family": "other:2026-10"}, {"label_source": "other:incident"},
])
def test_ghost_registration_does_not_relax_privacy_or_scope(incident, changes):
    assert not training.valid_auto_candidate(incident | changes, "ghost", "us-east")


def test_other_rooms_cannot_supply_ghost_or_private_labels(incident):
    assert not training.valid_auto_candidate(incident, "base", "us-east")
    assert not training.valid_auto_candidate(incident | {"skill_id": "base.find_site"}, "base", "us-east")


@pytest.mark.asyncio
async def test_incident_reaches_shared_intake_once_as_private_unapproved_candidate(database, monkeypatch, incident):
    pool, _ = database
    monkeypatch.setattr(training, "ROOMS", ("ghost",))
    key = secrets.token_urlsafe(20)
    monkeypatch.setenv("TANK_KEY_GHOST", key)
    real_client = httpx.AsyncClient

    def respond(request):
        assert request.url.host == "agent-ghost"
        assert request.url.path == "/gold/candidates"
        assert request.headers["X-Tank-Key"] == key
        return httpx.Response(200, json=[incident])

    monkeypatch.setattr(training.httpx, "AsyncClient", lambda **kw: real_client(
        transport=httpx.MockTransport(respond), **kw))
    first = await training.collect_room_gold(date(2026, 10, 21))
    second = await training.collect_room_gold(date(2026, 10, 21))
    assert first["inserted"] == 1 and first["rejected"] == 0
    assert second["duplicates"] == 1
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM tank.gold_examples WHERE tenant_id=$1 AND agent='ghost'", gold.PLATFORM_TENANT)
        assert len(rows) == 1
        row = rows[0]
        assert row["region"] == "us-east" and row["skill_id"] == "ghost.incident"
        assert row["label_family"] == incident["label_family"]
        assert row["public"] is False and row["status"] == "candidate" and not row["auto_approved"]
        assert await conn.fetchval("SELECT count(*) FROM tank.training_pairs WHERE tenant_id=$1", gold.PLATFORM_TENANT) == 0
