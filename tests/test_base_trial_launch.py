"""Founder trial forwarding, platform selection, and independent truth wiring."""

import json
import sys
import types
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest

from test_b3_base_room import ROOT, _load
from sources import trial_selection
from sources.vendor_ledger import PLATFORM_TENANT
import main as tank


class Pool:
    def __init__(self, conn):
        self.conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


@pytest.mark.asyncio
async def test_founder_proxy_replaces_credentials_and_ignores_input(monkeypatch):
    monkeypatch.setenv("TANK_API_KEY", "workspace-placeholder")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder-placeholder")
    monkeypatch.setenv("TANK_KEY_BASE", "base-placeholder")
    forwarded = []

    async def transport(request):
        forwarded.append(request)
        assert request.url.path == "/context-dev/trial"
        assert request.headers["x-tank-key"] == "base-placeholder"
        assert "x-tervory-admin" not in request.headers
        assert json.loads(request.content) == {"tenant_id": PLATFORM_TENANT}
        return httpx.Response(200, json={"records_sent": 1})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as room:
        monkeypatch.setattr(tank, "_http", room)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank") as client:
            for headers in ({}, {"X-Tank-Key": "workspace-placeholder"}, {
                "X-Tank-Key": "base-placeholder", "X-Tervory-Admin": "founder-placeholder",
            }, {"X-Tank-Key": "workspace-placeholder", "X-Tervory-Admin": "client-placeholder"}):
                response = await client.post("/v1/base/context-dev/trial", headers=headers)
                assert response.status_code == 404
            assert not forwarded
            headers = {"X-Tank-Key": "workspace-placeholder", "X-Tervory-Admin": "founder-placeholder"}
            response = await client.post("/v1/base/context-dev/trial", headers=headers, json={
                "tenant_id": str(uuid.uuid4()), "checked_answers": {"website": "forged"},
            })
            assert response.status_code == 200
            assert response.json()["records_sent"] == 1
            monkeypatch.delenv("TANK_KEY_BASE")
            assert (await client.post("/v1/base/context-dev/trial", headers=headers)).status_code == 503


@pytest.mark.asyncio
async def test_latest_completed_platform_selection_is_bounded(monkeypatch):
    conn = AsyncMock()
    conn.fetchval.return_value = uuid.uuid4()
    conn.fetch.return_value = [
        {"id": uuid.uuid4(), "raw": "{}", "profile": json.dumps({"website": {"value": "https://stripe.com"}})}
        for _ in range(60)
    ]
    monkeypatch.setattr(trial_selection, "official_truth", lambda: {})
    run, records = await trial_selection.latest_trial(Pool(conn))
    assert run == str(conn.fetchval.return_value)
    assert len(records) == 50
    assert all(row["checked_answers"] == {} for row in records)
    for call in (conn.fetchval.call_args, conn.fetch.call_args):
        assert "tenant_id=$1" in call.args[0]
        assert call.args[1] == uuid.UUID(PLATFORM_TENANT)
        assert "status='done'" in call.args[0]
    assert "finished_at DESC" in conn.fetchval.call_args.args[0]
    assert "NOT (passes ? 'context_dev')" in conn.fetch.call_args.args[0]
    assert conn.fetch.call_args.args[2] == conn.fetchval.return_value
    conn.fetchval.return_value = None
    assert await trial_selection.latest_trial(Pool(conn)) == (None, [])


def test_missing_official_matches_never_uses_profile_as_truth(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert trial_selection.official_truth() == {}
    rows = [{"id": uuid.uuid4(), "raw": {}, "profile": {
        "website": {"value": "https://stripe.com"}, "phone": {"value": "unverified"},
    }}]
    selected = trial_selection.select_records(rows, {})
    assert selected[0]["checked_answers"] == {}
    assert "phone" not in selected[0]
    rows[0]["profile"]["website"]["value"] = "https://localhost"
    assert trial_selection.select_records(rows, {}) == []


def test_optional_gold_validator_supplies_only_official_truth(monkeypatch, tmp_path):
    gold = types.ModuleType("base_gold.gold_sources")
    gold.MAX_SNAPSHOT_BYTES = 20000000
    seen = []

    def candidates(rows, *, region):
        seen.extend(rows)
        assert region == "us-east"
        return [{
            "skill_id": "base.find_site", "expected": {"website": {"value": "https://example.com"}},
            "label_source": "ATF active licences · 2026-10-20",
        }] if rows[0]["official"]["active"] else []

    gold.candidates = candidates
    monkeypatch.setitem(sys.modules, "base_gold", types.ModuleType("base_gold"))
    monkeypatch.setitem(sys.modules, "base_gold.gold_sources", gold)
    engine = types.ModuleType("engines.ffl.atf_gold")
    engine.licence_id = lambda raw: raw.get("licence", "")
    monkeypatch.setitem(sys.modules, "engines", types.ModuleType("engines"))
    monkeypatch.setitem(sys.modules, "engines.ffl", types.ModuleType("engines.ffl"))
    monkeypatch.setitem(sys.modules, "engines.ffl.atf_gold", engine)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TANK_REGION", "us-east")
    directory = tmp_path / "gold" / "us-east"
    directory.mkdir(parents=True)
    snapshot = {
        "source_id": "atf-active",
        "official": {"id": "list-1", "active": True, "phone": "6175550100",
                     "address": "10 Main St", "city": "Boston", "state": "MA", "zip": "02110"},
        "site": {"phone": "not copied", "socials": ["not copied"]},
    }
    path = directory / "official-matches.jsonl"
    path.write_text(json.dumps(snapshot) + "\n")
    truth = trial_selection.official_truth()
    assert seen == [snapshot]
    selected = trial_selection.select_records([{
        "id": uuid.uuid4(), "raw": {"licence": "list-1"},
        "profile": {"website": {"value": "https://wrong.example.com"}},
    }], truth)
    assert selected[0]["checked_answers"] == {
        "website": "https://example.com", "phone": "6175550100", "address": "10 Main St, Boston, MA, 02110",
    }
    assert selected[0]["label_source"] == "ATF active licences · 2026-10-20"
    snapshot["official"]["phone"] = ""
    path.write_text(json.dumps(snapshot) + "\n")
    assert "phone" not in trial_selection.official_truth()["list-1"]["checked_answers"]
    snapshot["official"]["active"] = False
    path.write_text(json.dumps(snapshot) + "\n")
    assert trial_selection.official_truth() == {}


@pytest.mark.asyncio
async def test_room_auto_selection_and_cap_response(monkeypatch):
    base = _load("base_trial_launch_app", ROOT / "agents/base/app.py")
    monkeypatch.setenv("TANK_KEY", "base-placeholder")
    monkeypatch.setattr(base.app.state, "pool", object(), raising=False)
    monkeypatch.setattr(base.app.state, "http", object(), raising=False)
    run = str(uuid.uuid4())
    records = [{"record_id": str(uuid.uuid4()), "url": "https://stripe.com", "checked_answers": {}}]
    select = AsyncMock(return_value=(run, records))
    runner = AsyncMock(return_value={"results": [{"record_id": records[0]["record_id"], "status": "candidate"}], "records_sent": 1,
                                    "message": "credit cap reached"})
    monkeypatch.setattr(base, "latest_trial", select)
    monkeypatch.setattr(base, "run_trial", runner)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app), base_url="http://base") as client:
        headers = {"X-Tank-Key": "base-placeholder"}
        assert (await client.post("/context-dev/trial", json={"tenant_id": PLATFORM_TENANT})).status_code == 401
        assert (await client.post("/context-dev/trial", json={"tenant_id": str(uuid.uuid4())}, headers=headers)).status_code == 403
        select.assert_not_called()
        response = await client.post("/context-dev/trial", json={"tenant_id": PLATFORM_TENANT}, headers=headers)
        assert response.json()["records_sent"] == 1
        assert response.json()["message"] == "credit cap reached"
        assert response.json()["comparison_records"][0]["passes"]["context_dev_checked"] == {"checked": False, "expected": {}}
        assert runner.await_args.args[2:] == (PLATFORM_TENANT, run, records)
        select.return_value = (None, [])
        assert (await client.post("/context-dev/trial", json={"tenant_id": PLATFORM_TENANT}, headers=headers)).json()["records_sent"] == 0
