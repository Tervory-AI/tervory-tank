"""GHOST-2 D3 Shields Up and D5 PHP2Shell replay. Local fixtures and fake transports only."""
import asyncio
import importlib.util
import json
import logging
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from agents.ghost import advisories as adv
from agents.ghost import shields as sh
from agents.ghost.app import create_app
from agents.ghost.models import PLATFORM_TENANT
from agents.ghost.store import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/ghost"
TOKEN = "cf-sentinel-token-5d4c3b2a"
ZONE, RULESET, RULE = "a" * 32, "b" * 32, "c" * 32
EDGE = [{"app": "coolify", "kind": "edge", "name": "cloudflare", "version": "current", "ecosystem": "generic"},
        {"app": "rig", "kind": "edge", "name": "direct", "version": "current", "ecosystem": "generic"}]

_spec = importlib.util.spec_from_file_location("ghost_adv_tests", ROOT / "tests/test_ghost_advisories.py")
_adv_tests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_adv_tests)
Sources = _adv_tests.Sources


class FakeCloudflare:
    def __init__(self, entrypoint=True, refuse=False):
        self.calls: list[httpx.Request] = []
        self.entrypoint, self.refuse = entrypoint, refuse

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        assert request.url.host == "api.cloudflare.com"
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        path = request.url.path.removeprefix("/client/v4")
        if self.refuse:
            return httpx.Response(403, json={"success": False, "errors": [{"message": f"bad token {TOKEN}"}]})
        if path == "/zones":
            return httpx.Response(200, json={"success": True, "result": [{"id": ZONE, "name": "tervory.com"}]})
        if path.endswith("/entrypoint") and request.method == "GET":
            if not self.entrypoint:
                return httpx.Response(404, json={"success": False})
            return httpx.Response(200, json={"success": True, "result": {"id": RULESET, "rules": [{"id": "d" * 32}]}})
        if path.endswith("/entrypoint") and request.method == "PUT":
            body = json.loads(request.content)
            return httpx.Response(200, json={"success": True, "result": {"id": RULESET, "rules": [
                {"id": RULE, "ref": body["rules"][0]["ref"]}]}})
        if path == f"/zones/{ZONE}/rulesets/{RULESET}/rules" and request.method == "POST":
            body = json.loads(request.content)
            return httpx.Response(200, json={"success": True, "result": {"id": RULESET, "rules": [
                {"id": RULE, "ref": body["ref"]}, {"id": "d" * 32}]}})
        if path == f"/zones/{ZONE}/rulesets/{RULESET}/rules/{RULE}" and request.method == "DELETE":
            return httpx.Response(200, json={"success": True, "result": {"id": RULESET, "rules": []}})
        return httpx.Response(599)


class Health:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    async def __call__(self, site):
        self.calls.append(site)
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


@pytest.fixture
def no_sockets(monkeypatch):
    """Any real network attempt fails the test."""
    def refuse(*_a, **_k):
        raise AssertionError("network call attempted")
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def make(tmp_path, transport, health):
    store = Store(tmp_path / "ghost.sqlite3")
    store.replace_inventory(PLATFORM_TENANT, "headers", EDGE, "2026-10-23T10:00:00Z")
    http = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    receipts = AsyncMock()
    shields = sh.Shields(store, http, receipts, health=health, pause=AsyncMock(),
                         clock=lambda: "2026-10-23T12:00:00Z")
    return store, http, receipts, shields


def everything(store, receipts, *responses):
    rows = store.db.execute("SELECT * FROM ghost_shields").fetchall()
    return json.dumps([rows, [str(c) for c in receipts.record.await_args_list], *responses], default=str)


@pytest.mark.asyncio
async def test_dry_run_with_empty_token_makes_no_network_call_at_all(tmp_path, monkeypatch, no_sockets):
    monkeypatch.setenv(sh.TOKEN_ENV, "")
    cf, health = FakeCloudflare(), Health(True)
    store, http, receipts, shields = make(tmp_path, cf, health)
    try:
        shield = await shields.propose(sh.ShieldRequest(site="coolify.tervory.com", kind="block_multipart_post"))
        assert shield["state"] == "proposed"
        done = await shields.raise_shield(shield["id"])
        assert done["state"] == "dry_run" and sh.mode() == "dry_run"
        assert cf.calls == [] and health.calls == []
        rule = done["plan"]["rule"]
        assert rule["action"] == "block" and 'http.host eq "coolify.tervory.com"' in rule["expression"]
        assert 'http.request.method eq "POST"' in rule["expression"]
        assert "multipart/form-data" in rule["expression"]
        assert 'not starts_with(http.request.uri.path, "/upload/")' in rule["expression"]
        assert [c["method"] for c in done["plan"]["calls"]] == ["GET", "GET", "POST", "GET"]
        assert {c.kwargs["task_type"] for c in receipts.record.await_args_list} == {"ghost.shield"}
        assert [r["step"] for r in done["receipts"]] == ["proposed", "dry_run"]
        # Undo of a dry-run is a withdrawal, still without a call.
        assert (await shields.undo(shield["id"]))["state"] == "withdrawn" and cf.calls == []
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_live_shield_is_applied_then_health_checked_and_kept(tmp_path, monkeypatch):
    monkeypatch.setenv(sh.TOKEN_ENV, TOKEN)
    cf, health = FakeCloudflare(), Health(True)
    store, http, receipts, shields = make(tmp_path, cf, health)
    try:
        shield = await shields.propose(sh.ShieldRequest(site="coolify.tervory.com", kind="block_multipart_post"))
        done = await shields.raise_shield(shield["id"])
        assert done["state"] == "up" and done["applied"]["rule_id"] == RULE
        assert [(r.method, r.url.path.removeprefix("/client/v4")) for r in cf.calls] == [
            ("GET", "/zones"), ("GET", f"/zones/{ZONE}/rulesets/phases/http_request_firewall_custom/entrypoint"),
            ("POST", f"/zones/{ZONE}/rulesets/{RULESET}/rules")]
        added = json.loads(cf.calls[-1].content)
        assert added["ref"] == shield["ref"] and added["position"] == {"before": ""}
        assert health.calls == ["coolify.tervory.com"] * 3  # Before, and twice after.
        assert [r["step"] for r in done["receipts"]] == ["proposed", "applied", "health_passed"]
        # One-tap Undo removes exactly our rule.
        undone = await shields.undo(shield["id"])
        assert undone["state"] == "undone"
        assert (cf.calls[-1].method, cf.calls[-1].url.path) == (
            "DELETE", f"/client/v4/zones/{ZONE}/rulesets/{RULESET}/rules/{RULE}")
        assert TOKEN not in everything(store, receipts, sh.public_view(undone))
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_failed_health_check_undoes_the_shield_automatically(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv(sh.TOKEN_ENV, TOKEN)
    cf, health = FakeCloudflare(), Health(True, False)
    store, http, receipts, shields = make(tmp_path, cf, health)
    try:
        shield = await shields.propose(sh.ShieldRequest(site="coolify.tervory.com", kind="challenge_bots"))
        done = await shields.raise_shield(shield["id"])
        assert done["state"] == "auto_undone"
        assert cf.calls[-1].method == "DELETE" and cf.calls[-1].url.path.endswith(f"/rules/{RULE}")
        assert [r["step"] for r in done["receipts"]] == ["proposed", "applied", "health_failed", "auto_undone"]
        assert shields.summary()["sites_broken_by_a_shield"] == 1
        assert TOKEN not in everything(store, receipts, sh.public_view(done)) + caplog.text
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_site_already_down_is_refused_and_missing_entrypoint_is_created_with_only_our_rule(tmp_path, monkeypatch):
    monkeypatch.setenv(sh.TOKEN_ENV, TOKEN)
    cf, health = FakeCloudflare(entrypoint=False), Health(False)
    store, http, receipts, shields = make(tmp_path, cf, health)
    try:
        shield = await shields.propose(sh.ShieldRequest(site="coolify.tervory.com", kind="waf_managed"))
        refused = await shields.raise_shield(shield["id"])
        assert refused["state"] == "refused" and cf.calls == []
        health.answers = [True]
        other = await shields.propose(sh.ShieldRequest(site="coolify.tervory.com", kind="rate_limit", path="/login"))
        assert (await shields.raise_shield(other["id"]))["state"] == "up"
        put = [r for r in cf.calls if r.method == "PUT"]
        assert len(put) == 1 and [r["ref"] for r in json.loads(put[0].content)["rules"]] == [other["ref"]]
        assert json.loads(put[0].content)["rules"][0]["ratelimit"]["period"] == 10
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_cloudflare_refusal_is_generic_and_never_echoes_the_token(tmp_path, monkeypatch):
    monkeypatch.setenv(sh.TOKEN_ENV, TOKEN)
    cf, health = FakeCloudflare(refuse=True), Health(True)
    store, http, receipts, shields = make(tmp_path, cf, health)
    try:
        shield = await shields.propose(sh.ShieldRequest(site="coolify.tervory.com", kind="waf_managed"))
        failed = await shields.raise_shield(shield["id"])
        assert failed["state"] == "failed" and failed["note"] == "The edge network refused the change."
        assert TOKEN not in everything(store, receipts, sh.public_view(failed))
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_sites_not_on_cloudflare_get_a_brief_and_are_never_touched(tmp_path, monkeypatch):
    monkeypatch.setenv(sh.TOKEN_ENV, TOKEN)
    cf, health = FakeCloudflare(), Health(True)
    store, http, receipts, shields = make(tmp_path, cf, health)
    try:
        shield = await shields.propose(sh.ShieldRequest(site="rig.tervory.com", kind="block_multipart_post"))
        assert shield["state"] == "brief" and shield["brief"]["for"] == "Grok"
        assert (await shields.raise_shield(shield["id"]))["state"] == "brief"
        assert cf.calls == [] and health.calls == []
        with pytest.raises(ValueError):
            await shields.propose(sh.ShieldRequest(site="example.com", kind="waf_managed"))
        cloudflare = sh.Cloudflare(http, TOKEN)
        with pytest.raises(sh.CloudflareError):
            await cloudflare.zone_id("example.com")
        with pytest.raises(sh.CloudflareError):
            await cloudflare.call("GET", "/accounts")
        with pytest.raises(sh.CloudflareError):
            await cloudflare.delete_rule(ZONE, RULESET, "../../everything")
        assert cf.calls == []
        with pytest.raises(sh.CloudflareError):
            sh.Cloudflare(http, "")
        with pytest.raises(ValueError):
            sh.rule_for("rate_limit", 'x" or true or "', "/", "ghost-x")
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_health_check_only_reaches_our_sites_over_public_addresses(monkeypatch):
    seen = []
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(302)))
    monkeypatch.setattr("agents.ghost.probes.public_addresses", lambda host: ["198.51.100.10"])
    try:
        assert await sh.site_health(http, "coolify.tervory.com") is True
        assert await sh.site_health(http, "example.com") is False
        assert [str(r.url) for r in seen] == ["https://coolify.tervory.com/"]
    finally:
        await http.aclose()


# ---------- D5: PHP2Shell replay, end to end through Ghost's routes ----------

@pytest.mark.asyncio
async def test_php2shell_replay_flags_proposes_dry_run_shield_and_resolves(tmp_path, monkeypatch, caplog, no_sockets):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("TANK_KEY", "ghost-test")
    monkeypatch.setenv(sh.TOKEN_ENV, "")
    monkeypatch.setenv("COOLIFY_TOKEN_GHOST", "coolify-sentinel-77")
    sources, cf = Sources(), FakeCloudflare()

    def internet(request):
        if request.url.host == "api.cloudflare.com":
            return cf(request)
        return sources(request)

    moment = {"now": datetime(2026, 10, 21, 14, 40, tzinfo=timezone.utc)}
    app = create_app()
    store = Store(tmp_path / "ghost.sqlite3")
    http = httpx.AsyncClient(transport=httpx.MockTransport(internet))
    receipts = AsyncMock()
    app.state.store, app.state.advisory_lock, app.state.http = store, asyncio.Lock(), http
    app.state.watcher = adv.Watcher(store, adv.Feeds(http, pause=AsyncMock()), receipts, clock=lambda: moment["now"])
    health = Health(True)
    app.state.shields = sh.Shields(store, http, receipts, health=health, pause=AsyncMock())
    key = {"X-Tank-Key": "ghost-test", "content-type": "application/json"}
    bodies = []
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ghost") as client:
            before = json.loads((FIXTURES / "php2shell/inventory-before.json").read_text())
            first = await client.post("/ghost/inventory/report", headers=key,
                                      json={"source": "host:host-a", "host_report": before})
            assert first.status_code == 200
            sites = {"source": "headers", "components": EDGE}
            assert (await client.post("/ghost/inventory/report", json=sites, headers=key)).status_code == 200

            # 1. Flagged within one cycle.
            cycle = (await client.post("/ghost/advisories/pull", headers=key)).json()
            assert cycle["new_matches"] == 2
            # 2. A dry-run proposal for coolify.tervory.com: block multipart POST on non-upload paths.
            listed = (await client.get("/ghost/shields", headers=key)).json()
            bodies.append(listed)
            assert listed["mode"] == "dry_run"
            block = [s for s in listed["shields"] if s["kind"] == "block_multipart_post"]
            assert len(block) == 1 and block[0]["site"] == "coolify.tervory.com" and block[0]["state"] == "proposed"
            assert block[0]["plan"]["plain"] == ("Block file-upload style POST requests on coolify.tervory.com, "
                                                 "except on its real upload paths.")
            assert (await client.post(f"/ghost/shields/{block[0]['id']}/raise")).status_code == 404
            tapped = await client.post(f"/ghost/shields/{block[0]['id']}/raise", headers=key)
            bodies.append(tapped.json())
            assert tapped.json()["state"] == "dry_run"
            assert cf.calls == [] and health.calls == []
            tile = (await client.get("/ghost/summary", headers=key)).json()
            bodies.append(tile)
            assert tile["open_by_severity"] == {"known_exploited": 2} and tile["sites_broken_by_a_shield"] == 0
            assert tile["time_to_know_seconds"]["worst"] == 2400 < tile["time_to_know_seconds"]["target"]

            # 3. Resolved once the inventory shows Coolify 4.4.7 on PHP 8.4.27.
            after = (FIXTURES / "host-a-report-2026-10-23.json").read_bytes()
            assert (await client.post("/ghost/inventory/report", content=after, headers=key)).status_code == 200
            moment["now"] += timedelta(days=2)
            assert (await client.post("/ghost/advisories/pull", headers=key)).json()["resolved"] == 2
            final = (await client.get("/ghost/shields", headers=key)).json()
            bodies.append(final)
            assert {s["state"] for s in final["shields"]} == {"not_needed"}
            assert (await client.get("/ghost/summary", headers=key)).json()["open_total"] == 0
        assert cf.calls == []
        assert {r.url.host for r in sources.calls} <= adv.ALLOWED_HOSTS
        # 4. No secret value in any log, receipt or response.
        text = everything(store, receipts, *bodies) + caplog.text
        assert "coolify-sentinel-77" not in text and "ghost-test" not in text
    finally:
        await http.aclose()
        store.close()


def test_compose_airgap_watch_has_no_cf_write_token():
    """Air gap correction: Watch has no Cloudflare write credential; Enforce does (by name)."""
    compose = (ROOT / "agents/ghost/docker-compose.yml").read_text()
    assert "CLOUDFLARE_API_TOKEN_GHOST" not in compose
    assert "TANK_KEY: ${TANK_KEY_GHOST:-}" in compose
    enforce = (ROOT / "agents/ghost/docker-compose.enforce.yml").read_text()
    assert "CLOUDFLARE_API_TOKEN_ENFORCE: ${CLOUDFLARE_API_TOKEN_ENFORCE:-}" in enforce
    assert "internal: true" in enforce
    env = (ROOT / ".env.example").read_text()
    assert "\nCLOUDFLARE_API_TOKEN_ENFORCE=\n" in env
    assert "AUTUMBRA_CF_WEBHOOK_SECRET=" in env
