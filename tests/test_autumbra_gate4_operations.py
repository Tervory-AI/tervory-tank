"""Saturday rehearsal: actual job cycles, temporary state and fake I/O only."""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio

from agents.ghost import app as watch, advisories, inventory, probes, shields, red_team
from agents.ghost.client_settings import ClientAutumbraSettings, save_settings
from agents.ghost.investigate import Investigator
from agents.ghost.models import PLATFORM_TENANT, ROOMS, SITES
from agents.ghost.shared_blocks import StandingBlocks
from agents.ghost.store import Store
from agents.ghost.threat_queue import ThreatPayloadQueue
from test_ghost_advisories import Sources, load, report


@pytest_asyncio.fixture
async def room(monkeypatch, tmp_path):
    for name in list(os.environ):
        if name.startswith(("AUTUMBRA_", "GHOST_", "COOLIFY_", "CLOUDFLARE_", "TANK_", "THREAT_")):
            monkeypatch.delenv(name)
    for name, value in {
        "DATA_DIR": str(tmp_path / "data"), "TANK_KEY": "offline-test-marker",
        "THREAT_PAYLOAD_QUEUE_ROOT": str(tmp_path / "queues"),
        "COOLIFY_URL_GHOST": "https://coolify.example.test", "COOLIFY_TOKEN_GHOST": "offline-test-marker",
        "AUTUMBRA_SMTP_HOST": "smtp.example.test", "AUTUMBRA_SMTP_FROM": "autumbra@example.test",
    }.items():
        monkeypatch.setenv(name, value)
    letters, calls = [], []
    from agents.rig.rigbox.reserve import SmtpMailer
    async def send(_self, letter):
        letters.append(letter)
    monkeypatch.setattr(SmtpMailer, "send", send)
    monkeypatch.setattr(probes, "public_addresses", lambda host: ["93.184.215.14"])
    monkeypatch.setattr(probes, "certificate_days", lambda host: 90)
    sources = Sources()

    def respond(request):
        calls.append(request)
        path, host = request.url.path, request.url.host
        if host == "coolify.example.test":
            assert request.method == "GET"
            if path == "/api/v1/applications":
                return httpx.Response(200, json=[{"name": target, "uuid": target,
                    "fqdn": SITES.get(target, ""), "status": "running"}
                    for target in {*SITES, *ROOMS, "tank"}])
            if path.startswith("/api/v1/deployments/applications/"):
                return httpx.Response(200, json={"deployments": [{"status": "finished", "created_at": "2026-11-05T00:00:00Z"}]})
            if path == "/api/v1/services":
                return httpx.Response(200, json=[])
            if path == "/api/v1/version":
                return httpx.Response(200, json="4.4.7")
        if host in inventory.WATCHED_SITES.values():
            return httpx.Response(200, headers={"x-powered-by": "PHP/8.4.23"})
        if host in {"tank", "ghost-browser"}:
            if path in {"/v1/ghost/check", "/check"}:
                body = json.loads(request.content)
                return httpx.Response(200, json={"target": body["target"], "signal": body["signal"], "failing": False})
            if path == "/v1/ledger/vendor":
                return httpx.Response(200, json={"recorded": True, "ledger_id": json.loads(request.content)["id"]})
            if path == "/v1/ghost/autumbra/savings":
                body = json.loads(request.content)
                assert body["tenant_id"] == PLATFORM_TENANT
                assert set(body["reference"]) <= {"step", "outcome"}
                return httpx.Response(200, json={"tenant_id": body["tenant_id"], "receipt_id": body["receipt_id"],
                    "would_have_cost_usd": 0.0001, "baseline_status": "priced"})
            if path == "/v1/market-lab/intel":
                return httpx.Response(200, json={"schema_version": "market_lab.ioc.v1", "paid": False,
                    "sources": [{"id": "nvd", "name": "NVD"}],
                    "indicators": [{"kind": "cve", "value": "CVE-2026-12345", "source_ids": ["nvd"]}]})
        if host in advisories.ALLOWED_HOSTS:
            return sources(request)
        pytest.fail("Unexpected dry-run boundary: " + request.method + " " + host + path)

    store = Store(tmp_path / "watch.sqlite")
    report(store, load("inventory-before.json"))
    store.replace_inventory(PLATFORM_TENANT, "repo", [{"app": "tank", "kind": "package", "name": "fastapi", "version": "0.115.6", "ecosystem": "pypi"}], "now")
    save_settings(store, ClientAutumbraSettings(tenant_id=PLATFORM_TENANT,
        site_name="example.test", owner_email="owner@example.test"))
    queue = watch.watch_threat_queue(PLATFORM_TENANT)
    memory = AsyncMock()
    memory.records.return_value = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        tank = watch.Tank(http)
        checks = probes.Probes(http, tank, "offline-test-marker")
        app = SimpleNamespace(state=SimpleNamespace(store=store, http=http, probes=checks,
            investigator=Investigator(store, checks, tank), lock=asyncio.Lock(), advisory_lock=asyncio.Lock(),
            watcher=advisories.Watcher(store, advisories.Feeds(http, pause=AsyncMock()), tank),
            shields=shields.Shields(store, http, tank), block_memory_failures=0,
            shared_blocks=StandingBlocks(memory, tank, store, watch.watch_threat_queue)))
        try:
            yield SimpleNamespace(app=app, store=store, queue=queue, letters=letters, calls=calls, memory=memory, root=tmp_path)
        finally:
            store.close()


async def one_tick(monkeypatch, entrypoint, app):
    async def stop(_delay):
        raise asyncio.CancelledError
    monkeypatch.setattr(asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        await entrypoint(app)


JOBS = {
    "watch": watch.watch, "inventory": watch.nightly, "advisories": advisories.watch,
    "standing_blocks": watch._standing_blocks_loop, "weekly_mail": watch._weekly_owner_email_loop,
    "action_mail": watch._act_owner_email_loop, "market_lab": watch._market_lab_intel_loop,
    "exercises": watch._exercise_loop, "savings": watch._receipt_savings_loop,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("job", JOBS)
async def test_scheduled_job_one_cycle_offline(job, room, monkeypatch):
    if job == "action_mail":
        monkeypatch.setattr(watch, "smtp_available_since", lambda: 1)
        room.queue.write_receipt({"id": "offline-action", "tenant_id": PLATFORM_TENANT,
            "applied": True, "timestamp": (datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat()})
    await one_tick(monkeypatch, JOBS[job], room.app)
    if job == "watch":
        assert room.app.state.monitor == {"running": True, "unavailable_checks": 0}
        assert room.store.list(PLATFORM_TENANT) == []
        checked = [json.loads(r.content) for r in room.calls if r.url.path in {"/check", "/v1/ghost/check"}]
        assert {row["target"] for row in checked} == {*SITES, *ROOMS, "tank"}
    elif job == "inventory":
        assert room.store.get_state(PLATFORM_TENANT, "inventory_refreshed")["complete"]
        assert room.store.inventory(PLATFORM_TENANT)
    elif job == "advisories":
        cycle = room.store.get_state(PLATFORM_TENANT, "last_cycle")
        assert {name: cycle["sources"][name] for name in ("cisa_kev", "osv", "github", "nvd", "vendor_notes")} == {
            name: "ok" for name in ("cisa_kev", "osv", "github", "nvd", "vendor_notes")}
        assert room.store.matches(PLATFORM_TENANT, "open")
        assert any(r.url.path == "/v1/ledger/vendor" for r in room.calls)
    elif job == "standing_blocks":
        room.memory.records.assert_awaited_once_with(PLATFORM_TENANT)
        assert room.app.state.block_memory_failures == 0
    elif job in {"weekly_mail", "action_mail"}:
        assert len(room.letters) == 1
        assert room.letters[0]["to"] == "owner@example.test"
        await one_tick(monkeypatch, JOBS[job], room.app)
        assert len(room.letters) == 1
    elif job == "market_lab":
        assert room.app.state.intel_status == "connected"
        assert len(room.queue.list_receipts()) == 1
        await one_tick(monkeypatch, JOBS[job], room.app)
        assert len(room.queue.list_receipts()) == 1
    elif job == "exercises":
        rows = room.store.get_state(PLATFORM_TENANT, "exercise_receipts")
        assert len(rows) == len(red_team.EXERCISES) * len(red_team.OWN_SITES)
        assert all(r["result"] != "failed" for r in rows)
        assert room.queue.list_receipts() == []
    elif job == "savings":
        assert room.app.state.savings_status == {"priced": 0, "unavailable": 0}
        assert room.queue.list_receipts() == []


def test_dry_run_registry_covers_every_watch_schedule():
    import ast
    tree = ast.parse(Path(watch.__file__).read_text())
    scheduled = {ast.unparse(node.args[0].func) for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and ast.unparse(node.func) == "asyncio.create_task"}
    assert scheduled == {"watch", "nightly", "advisory_watch.watch", "_standing_blocks_loop",
        "_weekly_owner_email_loop", "_act_owner_email_loop", "_market_lab_intel_loop", "_exercise_loop",
        "_receipt_savings_loop"}
    assert len(JOBS) == len(scheduled)


@pytest.mark.asyncio
async def test_enforce_schedule_uses_mock_provider_and_resumes_without_repeat(tmp_path, monkeypatch):
    from agents.ghost import enforce_app
    from agents.ghost.never_block import ActionCap
    from test_autumbra_cloudflare_hand import FakeCloudflare, edge, settings, payload, undo_payload
    api = FakeCloudflare("block_ip")
    control = edge(api)
    queue = ThreatPayloadQueue(tmp_path / "queue")
    queue.put(payload("block_ip"))
    app = SimpleNamespace(state=SimpleNamespace(threat_queue=queue, settings=settings(), control=control,
        data_dir=tmp_path, action_cap=ActionCap(limit=100)))
    sleeps = 0
    async def tick(_delay):
        nonlocal sleeps
        sleeps += 1
        if sleeps > 1:
            raise asyncio.CancelledError
    monkeypatch.setattr(asyncio, "sleep", tick)
    with pytest.raises(asyncio.CancelledError):
        await enforce_app._queue_drain_loop(app)
    receipt, = queue.list_receipts()
    assert receipt["applied"] and receipt["control"] == "cloudflare"
    before = list(api.calls)
    assert enforce_app.drain_once_for_enforce(app=app) is None
    assert api.calls == before
    queue.put(undo_payload(receipt))
    undone = enforce_app.drain_once_for_enforce(app=app)
    assert undone["outcome"] == "undone"
    assert len(api.rules) == 1 and api.rules[0]["ref"] == "somebody-else"


def test_health_observer_command_writes_signed_result_from_fake_response(tmp_path, monkeypatch):
    from agents.ghost import site_health
    monkeypatch.setenv("SITE_NAME", "tervory.com")
    monkeypatch.setenv("AUTUMBRA_HEALTH_SECRET", "offline-test-marker")
    monkeypatch.setattr(site_health, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(site_health, "HEALTH_DIR", tmp_path)
    monkeypatch.setattr(site_health.httpx, "HTTPTransport", lambda **kw: httpx.MockTransport(lambda r: httpx.Response(200)))
    def stop(_seconds):
        raise KeyboardInterrupt
    monkeypatch.setattr(site_health.time, "sleep", stop)
    with pytest.raises(KeyboardInterrupt):
        site_health.main()
    assert site_health.read_health("tervory.com")
    result = json.loads((tmp_path / "tervory.com.json").read_text())
    assert result["result"]["status"] == 200
    assert "offline-test-marker" not in json.dumps(result)


def test_inventory_commands_use_local_recorded_facts(tmp_path, capsys):
    (tmp_path / "requirements.txt").write_text("fastapi==0.115.6\n")
    assert inventory.main(["scan-repo", str(tmp_path)]) == 0
    assert any(row["name"] == "fastapi" for row in json.loads(capsys.readouterr().out)["components"])
    fixture = Path(__file__).parent / "fixtures/ghost/php2shell/inventory-before.json"
    assert inventory.main(["host-report", str(fixture)]) == 0
    assert json.loads(capsys.readouterr().out)["components"]


@pytest.mark.asyncio
async def test_training_candidate_handoff_stays_private_and_unapproved(room, monkeypatch):
    import training
    from agents.ghost.gold_sources import candidates
    monkeypatch.setattr(training, "runtime", lambda: SimpleNamespace(box_region=lambda: "us-east"))
    assert candidates(room.store, "us-east") == []
    item = room.store.open(PLATFORM_TENANT, "workspace", "health", "look")
    await room.store.remember(PLATFORM_TENANT, {**item, "state": "solved", "cause": "application_bug",
        "fix": "reviewed_pr_deployed", "solved_at": "2026-11-05T12:00:00+00:00"})
    row, = candidates(room.store, "us-east")
    assert training.valid_auto_candidate(row, "ghost", "us-east")
    assert not training.exportable({**row, "tenant_id": PLATFORM_TENANT, "active": True, "holdout": False, "client_matter": False})
    assert row["public"] is False


def test_hf_dogfood_command_stays_offline(monkeypatch):
    from agents.ghost.dogfood_hf import dogfood_watch_triage
    monkeypatch.setenv("AUTUMBRA_HF_LIVE", "0")
    result = dogfood_watch_triage(live=False, fixtures_path=Path(__file__).parent / "fixtures/autumbra_dogfood/synthetic_siem.jsonl")
    assert result["live_hf"] is False
    assert result["zero_ingestion"] is True


def test_isolation_probe_command_uses_fake_dns_and_connections(monkeypatch, capsys):
    from agents.ghost import enforce_isolation_probe as probe
    monkeypatch.delenv("TANK_KEY", raising=False)
    monkeypatch.setenv("AUTUMBRA_ROLE", "enforce")
    monkeypatch.setattr(probe, "try_resolve", lambda host: False)
    monkeypatch.setattr(probe, "try_connect", lambda *args, **kw: False)
    assert probe.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["report"]["ok"] and not result["probe"]["public_443"]
