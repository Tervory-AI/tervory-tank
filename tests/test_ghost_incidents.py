"""Ghost acceptance checks; offline fixtures, no production actions or network."""
from unittest.mock import AsyncMock

import pytest

from agents.ghost.gold_sources import candidates
from agents.ghost.investigate import Investigator, authorize_action
from agents.ghost.models import Look, Observation, PLATFORM_TENANT, Resolution, classify_message
from agents.ghost.store import Store


@pytest.fixture
def room(tmp_path):
    store = Store(tmp_path / "ghost.sqlite3")
    probes = AsyncMock()
    probes.reproduce.return_value = Observation(target="workspace", signal="health", failing=True, status_code=503)
    receipts = AsyncMock()
    yield Investigator(store, probes, receipts)
    store.close()


@pytest.mark.asyncio
async def test_failed_health_raises_deduplicated_issue_and_worker_brief(room):
    observation = Observation(target="workspace", signal="health", failing=True, status_code=503)
    item = await room.alert(observation)
    again = await room.alert(observation)
    assert again["id"] == item["id"]
    assert item["state"] == "needs_review"
    assert item["brief"]["status"] == "awaiting_founder_approval"
    assert item["brief"]["files_you_may_change"] == []
    assert "patch" not in item["brief"] and "command" not in item["brief"]
    room.probes.reproduce.assert_awaited_once()
    assert [s["step"] for s in item["steps"]] == ["opened", "recall", "reproduce", "reported"]
    assert room.receipts.record.await_count == 4


@pytest.mark.asyncio
async def test_look_and_message_start_an_investigation(room):
    room.probes.reproduce.return_value = Observation(target="workspace", signal="slow", failing=True)
    item = await room.look(classify_message("Ghost, the login page is slow"), "message")
    assert item["target"] == "workspace" and item["signal"] == "slow"
    assert item["origin"] == "message"
    assert "login page" not in str(room.store.list(PLATFORM_TENANT))


@pytest.mark.asyncio
async def test_solved_issue_is_recalled_on_next_alert_and_gold_is_monthly(room):
    item = await room.look(Look(target="workspace"))
    room.probes.reproduce.return_value = Observation(target="workspace", signal="health", failing=False)
    solved = await room.resolve(item["id"], Resolution(cause="application_bug", fix="reviewed_pr_deployed"))
    assert solved["state"] == "solved"
    room.probes.reproduce.return_value = Observation(target="workspace", signal="health", failing=True)
    repeat = await room.look(Look(target="workspace"))
    assert repeat["id"] != item["id"]
    assert repeat["previous"][0]["fix"] == "reviewed_pr_deployed"
    gold = candidates(room.store, "us-east")
    assert len(gold) == 1
    assert gold[0]["label_family"] == "ghost:incident:" + solved["solved_at"][:7]
    assert gold[0]["public"] is False
    assert await room.store.recall("another-tenant", "workspace:health") == []
    with pytest.raises(LookupError):
        room.store.get("another-tenant", item["id"])


@pytest.mark.asyncio
async def test_still_failing_issue_cannot_be_learned(room):
    item = await room.look(Look(target="workspace"))
    with pytest.raises(ValueError):
        await room.resolve(item["id"], Resolution(cause="application_bug", fix="reviewed_pr_deployed"))
    assert candidates(room.store, "us-east") == []


@pytest.mark.asyncio
async def test_human_checks_are_never_solved(room):
    item = await room.look(Look(target="workspace", signal="human_check"))
    assert item["state"] == "human_required"
    room.probes.reproduce.assert_not_awaited()
    with pytest.raises(ValueError):
        await room.resolve(item["id"], Resolution(cause="application_bug", fix="reviewed_pr_deployed"))


@pytest.mark.asyncio
async def test_receipt_failure_stops_before_browser_or_actions(room):
    room.receipts.record.side_effect = RuntimeError("Tank unavailable")
    with pytest.raises(RuntimeError):
        await room.look(Look(target="workspace"))
    room.probes.reproduce.assert_not_awaited()
    assert room.store.list(PLATFORM_TENANT)[0]["state"] == "open"


@pytest.mark.asyncio
async def test_upstream_error_never_copies_exception_text(room):
    room.probes.reproduce.side_effect = RuntimeError("sensitive upstream text")
    item = await room.look(Look(target="workspace"))
    assert item["state"] == "blocked"
    assert "sensitive upstream text" not in str(item)
    assert candidates(room.store, "us-east") == []


@pytest.mark.parametrize("action,target,state", [
    ("database_write", "tank", "failed"), ("change_key", "tank", "failed"),
    ("merge", "workspace", "failed"), ("restart_crashed_room", "workspace", "crashed"),
    ("restart_crashed_room", "radix", "healthy"), ("rerun_failed_deploy", "za", "failed"),
    ("rerun_failed_deploy", "site", "running"),
])
def test_production_writes_and_unverified_actions_refused(action, target, state):
    with pytest.raises(PermissionError):
        authorize_action(action, target, state)


def test_only_the_two_safe_actions_are_allowed():
    authorize_action("restart_crashed_room", "radix", "crashed")
    authorize_action("rerun_failed_deploy", "workspace", "failed")


def test_volume_and_gold_cannot_be_relabelled_into_another_region(tmp_path):
    path = tmp_path / "region.sqlite3"
    store = Store(path, "us-east")
    with pytest.raises(ValueError):
        candidates(store, "za")
    store.close()
    with pytest.raises(ValueError):
        Store(path, "za")


@pytest.mark.asyncio
async def test_wrong_probe_evidence_is_not_used_as_diagnosis(room):
    room.probes.reproduce.return_value = Observation(target="radix", signal="health", failing=True)
    item = await room.look(Look(target="workspace"))
    assert item["state"] == "blocked" and "brief" not in item


def test_browser_rejects_private_dns_answers(monkeypatch):
    import socket
    from agents.ghost.probes import public_addresses
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, ("127.0.0.1", 443))])
    with pytest.raises(ValueError):
        public_addresses("app.tervory.com")


@pytest.mark.asyncio
async def test_persistence_and_gold_do_not_depend_on_process_memory(tmp_path):
    path = tmp_path / "state.sqlite3"
    store = Store(path)
    item = store.open(PLATFORM_TENANT, "workspace", "health", "look")
    store.close()
    reopened = Store(path)
    assert reopened.get(PLATFORM_TENANT, item["id"])["state"] == "open"
    assert reopened.open(PLATFORM_TENANT, "workspace", "health", "alert")["id"] == item["id"]
    reopened.close()
