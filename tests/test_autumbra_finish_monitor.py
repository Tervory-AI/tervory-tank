import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agents.ghost import app as ghost
from agents.ghost.investigate import Investigator
from agents.ghost.inventory import Component
from agents.ghost.models import Look, Observation, PLATFORM_TENANT
from agents.ghost.store import Store


@pytest.mark.asyncio
async def test_monitor_schedules_promised_signals_and_survives_unavailable_feed():
    seen = []

    async def reproduce(check):
        seen.append((check.target.value, check.signal.value))
        if check.signal.value == "deploy":
            raise RuntimeError("unavailable")
        return Observation(target=check.target, signal=check.signal, failing=True)

    state = SimpleNamespace(lock=asyncio.Lock(), probes=SimpleNamespace(reproduce=reproduce),
                            investigator=AsyncMock())
    await ghost.monitor_once(SimpleNamespace(state=state))
    for target in (*ghost.ROOMS, "tank"):
        assert (target, "health") in seen and (target, "slow") in seen
    assert {("workspace", "errors"), ("tank", "errors"), ("tank", "ci"), ("tank", "radix")} <= set(seen)
    assert ("za", "deploy") not in seen
    failures = sum(signal == "deploy" for _, signal in seen)
    assert failures > 0 and state.monitor["unavailable_checks"] == failures
    assert state.investigator.alert.await_count == len(seen) - failures
    assert len(seen) == len(set(seen))


@pytest.mark.asyncio
@pytest.mark.parametrize("first", ["blocked", "not_reproduced"])
async def test_alert_recovers_same_incident_after_transient_evidence(tmp_path, first):
    store = Store(tmp_path / "incidents.sqlite")
    try:
        probe = AsyncMock()
        probe.reproduce.side_effect = (RuntimeError("unavailable") if first == "blocked" else
                                       None)
        probe.reproduce.return_value = Observation(target="workspace", signal="health", failing=False)
        investigator = Investigator(store, probe, AsyncMock())
        item = await investigator.look(Look(target="workspace"))
        assert item["state"] == first
        probe.reproduce.side_effect = None
        probe.reproduce.return_value = Observation(target="workspace", signal="health", failing=True)
        recovered = await investigator.alert(probe.reproduce.return_value)
        assert recovered["id"] == item["id"]
        assert recovered["state"] == "needs_review"
        assert len(store.list(PLATFORM_TENANT)) == 1
        assert len({row["ledger_id"] for row in recovered["steps"]}) == len(recovered["steps"])
    finally:
        store.close()


@pytest.mark.asyncio
async def test_partial_header_refresh_retains_failed_host_and_clears_successful_empty(tmp_path, monkeypatch):
    store = Store(tmp_path / "inventory.sqlite")
    old = [vars(Component(app, "runtime", "php", "8.4.23")) for app in ("site", "workspace")]
    store.replace_inventory(PLATFORM_TENANT, "headers", old, "2026-11-01T00:00:00Z")
    monkeypatch.setattr(ghost.inv, "WATCHED_SITES", {"site": "site.example", "workspace": "app.example"})
    monkeypatch.setattr(ghost.inv, "fetch_coolify", AsyncMock(return_value=None))

    async def headers(http, app, host):
        if app == "workspace":
            raise RuntimeError("unavailable")
        return []

    monkeypatch.setattr(ghost.inv, "fetch_headers", headers)
    app = SimpleNamespace(state=SimpleNamespace(store=store, http=None, advisory_lock=asyncio.Lock()))
    try:
        result = await ghost.refresh_inventory(app)
        assert result["headers"] == "1_of_2"
        remaining = store.inventory(PLATFORM_TENANT)
        assert [row["app"] for row in remaining] == ["workspace"]
        assert remaining[0]["seen_at"] == "2026-11-01T00:00:00Z"
        assert store.get_state(PLATFORM_TENANT, "inventory_refreshed")["complete"] is False
        refresh = AsyncMock()
        monkeypatch.setattr(ghost, "refresh_inventory", refresh)
        monkeypatch.setattr(ghost.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))
        with pytest.raises(asyncio.CancelledError):
            await ghost.nightly(app)
        refresh.assert_awaited_once_with(app)
    finally:
        store.close()


def test_scoped_inventory_cannot_retire_other_sources_or_tenants(tmp_path):
    store = Store(tmp_path / "inventory.sqlite")
    component = vars(Component("site", "runtime", "php", "8.4.23"))
    try:
        for tenant, source in (("a", "headers"), ("a", "repo"), ("b", "headers")):
            store.replace_inventory(tenant, source, [component], "old")
        with pytest.raises(ValueError):
            store.replace_inventory("a", "headers", [component], "new", apps={"workspace"})
        store.replace_inventory("a", "headers", [], "new", apps={"site"})
        assert [row["source"] for row in store.inventory("a")] == ["repo"]
        assert len(store.inventory("b")) == 1
    finally:
        store.close()
