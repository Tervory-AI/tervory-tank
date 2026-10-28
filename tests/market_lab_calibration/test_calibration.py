"""Offline histories and the real Tank/room API; no model, feed or live data."""
import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from core.calibration import calibration, identity, prepare_prediction
from core.http import build_router
from core.ledger import MemoryLedger, PostgresLedger
from core.pure import correct_prediction, make_prediction, resolve_prediction

OWNER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
NOW = BASE + timedelta(days=40)


def forecast(*, tenant=OWNER, at=NOW, days=1, kind="comparison:gte", feed="official", metric="volume"):
    return {**make_prediction(tenant_id=tenant, statement="Volume at least 10", metric_series_id=metric,
        comparator="gte", target=10, made_at=at, resolve_by=at + timedelta(days=days),
        rationale="Saved observations"), "kind": kind, "feed": feed}


def outcome(row, hit=True):
    deadline = datetime.fromisoformat(str(row["resolve_by"]))
    return resolve_prediction(row, [{"date": deadline.date().isoformat(), "value": 12 if hit else 5}], deadline)


def history(ledger, hits=(True, True, True, False), **kwargs):
    for index, hit in enumerate(hits):
        row = forecast(at=BASE + timedelta(days=2 * index), **kwargs)
        ledger.save_prediction(row)
        ledger.save_prediction(outcome(row, hit))


def test_known_history_and_no_invented_prior():
    ledger = MemoryLedger()
    empty = forecast()
    ledger.save_prediction(empty)
    assert ledger.predictions[-1]["confidence"] is None
    assert ledger.predictions[-1]["confidence_count"] == 0
    history(ledger)
    row = forecast()
    row.update(confidence=1, confidence_count=999)  # A caller cannot choose its confidence.
    ledger.save_prediction(row)
    assert ledger.predictions[-1]["confidence"] == .75
    assert ledger.predictions[-1]["confidence_count"] == 4
    assert ledger.predictions[-1]["horizon_seconds"] == 86400
    assert ledger.predictions[0]["confidence"] is None  # No retroactive rewrite.


@pytest.mark.parametrize("different", [{"kind": "warning:gte"}, {"feed": "another"}, {"days": 2}, {"tenant": OTHER}])
def test_only_same_tenant_kind_feed_and_horizon_count(different):
    ledger = MemoryLedger()
    history(ledger)
    history(ledger, hits=(False,) * 6, **different)
    prepared = prepare_prediction(forecast(), ledger.predictions, ledger.series)
    assert (prepared["confidence"], prepared["confidence_count"]) == (.75, 4)


def test_only_outcomes_known_at_prediction_time_count_once():
    ledger = MemoryLedger()
    history(ledger)
    original = ledger.predictions[0]
    ledger.predictions.append(outcome(original, False))  # Duplicate resolution, same deadline.
    ledger.predictions[-1]["resolved_at"] = (BASE + timedelta(days=30)).isoformat()
    pending = forecast(at=BASE)
    ledger.predictions.append(pending)
    unknown = forecast(at=BASE)
    ledger.predictions.extend([unknown, {**outcome(unknown), "outcome": "not_measurable", "score": None}])
    future = forecast(at=BASE)
    ledger.predictions.extend([future, {**outcome(future, False), "resolved_at": (NOW + timedelta(days=1)).isoformat()}])
    early = forecast(at=BASE)
    ledger.predictions.extend([early, {**outcome(early, False), "resolved_at": BASE.isoformat()}])
    ledger.predictions.append(outcome(forecast(at=BASE), False))  # Orphan link.
    ledger.predictions.append({**outcome(pending, False), "target": 99})  # A different claim.
    prepared = prepare_prediction(forecast(), ledger.predictions, [])
    assert (prepared["confidence"], prepared["confidence_count"]) == (.75, 4)


def test_cross_tenant_resolution_link_is_not_history_or_calibration():
    original = forecast(at=BASE)
    foreign = {**outcome(original), "tenant_id": OTHER}
    rows = [original, foreign]
    assert prepare_prediction(forecast(tenant=OTHER), rows, [])["confidence_count"] == 0
    assert calibration(rows, OTHER, []) == {"groups": []}
    with pytest.raises(ValueError, match="this tenant"):
        prepare_prediction(foreign, rows, [])


def test_resolutions_freeze_the_original_confidence_and_corrections_recompute():
    ledger = MemoryLedger()
    history(ledger)
    row = forecast()
    ledger.save_prediction(row)
    original = ledger.predictions[-1].copy()
    assert original["confidence"] == .75
    later = forecast(at=NOW + timedelta(days=2))
    ledger.save_prediction(later)
    ledger.save_prediction(outcome(later))
    resolved = outcome(original, False)
    resolved.update(confidence=1, confidence_count=500)
    ledger.save_prediction(resolved)
    assert (ledger.predictions[-1]["confidence"], ledger.predictions[-1]["confidence_count"]) == (.75, 4)
    assert next(r for r in ledger.predictions if r["id"] == original["id"]) == original
    corrected = correct_prediction(original, made_at=(NOW + timedelta(days=4)).isoformat(),
        resolve_by=(NOW + timedelta(days=5)).isoformat())
    ledger.save_prediction(corrected)
    assert ledger.predictions[-1]["confidence"] == pytest.approx(4 / 6)
    assert ledger.predictions[-1]["confidence_count"] == 6


def test_existing_series_metadata_is_tenant_scoped_and_unknown_feeds_stay_separate():
    row = forecast(kind=None, feed=None)
    series = [{"id": "volume", "tenant_id": OTHER, "source": "wrong"},
              {"id": "volume", "tenant_id": OWNER, "source": "official"}]
    assert identity(row, series) == {"kind": "comparison:gte", "feed": "official", "horizon_seconds": 86400}
    assert identity(row, series[:1])["feed"] == "volume"
    assert identity(forecast(kind=None, feed=None, metric="other"), [])["feed"] == "other"
    assert identity(forecast(kind=None, metric="response:area:segment"), [])["kind"] == "response:gte"
    assert identity({**row, "sources": [{"warning_id": "saved-warning"}]}, series)["kind"] == "warning:gte"


def scored_pair(confidence, hit=True, *, kind="comparison:gte", tenant=OWNER):
    row = {**forecast(at=BASE, kind=kind, tenant=tenant), "confidence": confidence, "confidence_count": 10}
    # Deliberately inconsistent outcome metadata proves the original stated p wins.
    return [row, {**outcome(row, hit), "confidence": .55}]


def test_calibration_band_boundaries_include_zero_and_one_once():
    rows = [r for index in range(11) for r in scored_pair(index / 10, hit=index % 2 == 0)]
    group = calibration(rows, OWNER, [])["groups"][0]
    assert (group["resolved_count"], group["scored_count"], group["hits"]) == (11, 11, 6)
    assert group["hit_rate"] == pytest.approx(6 / 11)
    assert [b["count"] for b in group["bands"]] == [1] * 9 + [2]
    assert [b["lower"] for b in group["bands"]] == [i / 10 for i in range(10)]
    assert [b["upper"] for b in group["bands"]] == [(i + 1) / 10 for i in range(10)]
    assert [b["upper_inclusive"] for b in group["bands"]] == [False] * 9 + [True]
    assert group["bands"][9]["mean_confidence"] == pytest.approx(.95)
    assert group["bands"][9]["hit_rate"] == .5


def test_calibration_means_kind_filter_and_tenant_isolation():
    rows = scored_pair(.21) + scored_pair(.29, False)
    rows += scored_pair(.25, kind="warning:gte") + scored_pair(.25, tenant=OTHER)
    own = calibration(rows, OWNER, [])
    assert [g["kind"] for g in own["groups"]] == ["comparison:gte", "warning:gte"]
    group = calibration(rows, OWNER, [], kind="comparison:gte")["groups"][0]
    assert group["resolved_count"] == 2
    assert group["bands"][2] == {"lower": .2, "upper": .3, "upper_inclusive": False,
        "count": 2, "hits": 1, "mean_confidence": .25, "hit_rate": .5}
    assert group["bands"][0]["count"] == 0
    assert group["bands"][0]["mean_confidence"] is None
    assert group["bands"][0]["hit_rate"] is None
    assert calibration(rows, OWNER, [], kind="absent") == {"groups": []}


def test_legacy_history_informs_new_confidence_without_inventing_past_confidence():
    row = forecast(at=BASE)
    rows = [row, outcome(row)]  # No confidence was stated for this old forecast.
    assert prepare_prediction(forecast(), rows, [])["confidence"] == 1
    group = calibration(rows, OWNER, [])["groups"][0]
    assert (group["resolved_count"], group["scored_count"], group["unscored_count"]) == (1, 0, 1)
    assert group["hit_rate"] == 1
    assert all(b["count"] == 0 for b in group["bands"])
    assert prepare_prediction(outcome(row), rows, [])["confidence"] is None


@pytest.mark.asyncio
async def test_real_tank_and_room_api_authentication_and_two_tenant_isolation(monkeypatch):
    ledger = MemoryLedger()
    history(ledger)
    history(ledger, hits=(False, False), tenant=OTHER)
    ledger.save_prediction(forecast())
    ledger.save_prediction(forecast(tenant=OTHER))
    await check_api(ledger, monkeypatch, OWNER, OTHER)


async def check_api(ledger, monkeypatch, owner, other):
    @asynccontextmanager
    async def context():
        yield ledger

    room = FastAPI()
    room.include_router(build_router(key_ok=lambda key: key == "test-placeholder-room", ledger_context=context))
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/calibration_test")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "test-placeholder")
    monkeypatch.setenv("TANK_API_KEY", "test-placeholder-workspace")
    monkeypatch.setenv("TANK_KEY_MARKET_LAB", "test-placeholder-room")
    spec = importlib.util.spec_from_file_location("calibration_tank_app", ROOT / "tank/main.py")
    tank = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, tank)
    spec.loader.exec_module(tank)
    visited = []

    async def only_room(request):
        assert request.url.host == "agent-market-lab"
        assert request.url.path in {"/market/predictions", "/market/calibration"}
        visited.append(request.url.path)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room), event_hooks={"request": [only_room]}) as corridor:
        tank._http = corridor  # Any attempted model/search/provider call fails only_room.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank.test") as client:
            for operation in ("predictions", "calibration"):
                path = "/v1/market-lab/" + operation
                assert (await client.post(path, json={"tenant_id": owner})).status_code == 401
                assert (await client.post(path, json={"tenant_id": owner}, headers={"x-tank-key": "test-placeholder-room"})).status_code == 403
                response = await client.post(path, json={"tenant_id": owner}, headers={"x-tank-key": "test-placeholder-workspace"})
                assert response.status_code == 200, response.text
                assert response.headers["cache-control"] == "private, no-store"
                if operation == "predictions":
                    rows = response.json()["predictions"]
                    assert all(r["tenant_id"] == owner for r in rows)
                    pending = [r for r in rows if r["made_at"].startswith("2026-02-10") and r["outcome"] is None]
                    assert (pending[0]["confidence"], pending[0]["confidence_count"]) == (.75, 4)
                else:
                    group = response.json()["groups"][0]
                    assert (group["resolved_count"], group["hits"], group["hit_rate"]) == (4, 3, .75)
                foreign = await client.post(path, json={"tenant_id": other}, headers={"x-tank-key": "test-placeholder-workspace"})
                if operation == "predictions":
                    assert all(r["tenant_id"] == other for r in foreign.json()["predictions"])
                    assert all(r["confidence"] in {None, 0} for r in foreign.json()["predictions"])
                else:
                    assert foreign.json()["groups"][0]["hit_rate"] == 0
                filtered = await client.post(path, json={"tenant_id": owner, "kind": "absent"}, headers={"x-tank-key": "test-placeholder-workspace"})
                assert filtered.json() == ({"predictions": []} if operation == "predictions" else {"groups": []})
        assert (await corridor.post("http://agent-market-lab/market/calibration", json={"tenant_id": owner})).status_code == 401
    assert set(visited) == {"/market/predictions", "/market/calibration"}


@pytest.mark.asyncio
async def test_postgres_round_trip_schema_idempotence_and_real_tank(monkeypatch):
    target = os.environ.get("DATABASE_URL", "")
    url = urlsplit(target)
    if url.hostname not in {"127.0.0.1", "localhost"} or not url.path.endswith("_test"):
        pytest.skip("requires an explicitly selected loopback *_test database")
    import asyncpg
    conn = await asyncpg.connect(target)
    transaction = conn.transaction()
    await transaction.start()
    try:
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        await ledger.apply_schema()
        owner, other = str(uuid4()), str(uuid4())
        for tenant, hits in ((owner, (True, True, True, False)), (other, (False, False))):
            for index, hit in enumerate(hits):
                row = forecast(tenant=tenant, at=BASE + timedelta(days=2 * index))
                await ledger.save_prediction(row)
                await ledger.save_prediction(outcome(row, hit))
            await ledger.save_prediction(forecast(tenant=tenant))
        await check_api(ledger, monkeypatch, owner, other)
        saved = [r for r in await ledger.predictions_for(owner) if r["made_at"] == NOW][0]
        await ledger.save_prediction(outcome(saved, False))
        readback = await ledger.predictions_for(owner)
        resolved = next(r for r in readback if r["outcome"] == "miss" and r["made_at"] == NOW)
        assert (resolved["confidence"], resolved["confidence_count"]) == (.75, 4)
        band = calibration(readback, owner, [], kind="comparison:gte")["groups"][0]["bands"][7]
        assert (band["count"], band["mean_confidence"], band["hit_rate"]) == (1, .75, 0)
    finally:
        await transaction.rollback()
        await conn.close()
