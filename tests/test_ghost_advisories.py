"""GHOST-2 part 2: the advisory watcher. Every source is a local fixture; no network is used."""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from agents.ghost import advisories as adv
from agents.ghost.app import create_app
from agents.ghost.inventory import from_host_report
from agents.ghost.models import PLATFORM_TENANT
from agents.ghost.store import Store

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/ghost"
PHP = FIXTURES / "php2shell"
SENTINEL = "sentinel-secret-value-9f8e7d"


def load(name):
    return json.loads((PHP / name).read_text())


def nvd_both():
    a, b = load("nvd-CVE-2026-109618.json"), load("nvd-CVE-2026-109619.json")
    return {**a, "totalResults": 2, "vulnerabilities": a["vulnerabilities"] + b["vulnerabilities"]}


class Sources:
    """A fake internet holding only the named public sources, with per-source overrides."""

    def __init__(self, **overrides):
        self.calls: list[httpx.Request] = []
        self.overrides = overrides

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        host, path = request.url.host, request.url.path
        name = {"www.cisa.gov": "kev", "api.osv.dev": "osv", "services.nvd.nist.gov": "nvd",
                "www.php.net": "php", "nodejs.org": "node"}.get(host)
        if host == "api.github.com":
            name = {"/advisories": "github", "/repos/coollabsio/coolify/releases": "coolify",
                    "/repos/BerriAI/litellm/security-advisories": "litellm",
                    "/repos/redis/redis/releases": "redis_releases",
                    "/repos/redis/redis/security-advisories": "redis_advisories"}.get(path)
        if name in self.overrides:
            value = self.overrides[name]
            return value(request) if callable(value) else value
        if name == "kev":
            return httpx.Response(200, json=load("kev.json"), headers={"etag": '"kev-1"'})
        if name == "nvd":
            return httpx.Response(200, json=nvd_both())
        if name == "osv":
            return httpx.Response(200, json={"results": [{} for _ in json.loads(request.content or b'{"queries": []}').get("queries", [])]}) \
                if request.method == "POST" else httpx.Response(404)
        if name in {"github", "coolify", "litellm", "node", "redis_releases", "redis_advisories"}:
            return httpx.Response(200, json=[])
        if name == "php":
            return httpx.Response(200, json={})
        return httpx.Response(599)


def make_watcher(tmp_path, sources, moment):
    store = Store(tmp_path / "ghost.sqlite3")
    http = httpx.AsyncClient(transport=httpx.MockTransport(sources))
    receipts = AsyncMock()
    clock = {"now": moment}
    watcher = adv.Watcher(store, adv.Feeds(http, pause=AsyncMock()), receipts, clock=lambda: clock["now"])
    return store, http, receipts, watcher, clock


def report(store, raw, at="2026-10-21T20:00:00Z"):
    store.replace_inventory(PLATFORM_TENANT, "host:host-a", [vars(c) for c in from_host_report(raw)], at)


@pytest.mark.asyncio
async def test_php2shell_flagged_in_one_cycle_with_time_to_know_and_resolved_after_update(tmp_path):
    sources = Sources()
    moment = datetime(2026, 10, 21, 14, 40, tzinfo=timezone.utc)
    store, http, receipts, watcher, clock = make_watcher(tmp_path, sources, moment)
    try:
        report(store, load("inventory-before.json"))
        summary = await watcher.cycle()
        assert summary["sources"]["cisa_kev"] == "ok" and summary["sources"]["nvd"] == "ok"
        assert summary["new_matches"] == 2
        found = {m["advisory_id"]: m for m in store.matches(PLATFORM_TENANT, "open")}
        php, coolify = found["CVE-2026-109618"], found["CVE-2026-109619"]
        assert php["affected"] == {"app": "coolify", "kind": "runtime", "name": "php", "version": "8.4.23", "ecosystem": "generic"}
        assert php["severity"] == {"cvss": 9.8, "label": "critical", "known_exploited": True}
        assert php["what_to_do"]["patch_to"] == "8.4.27"
        assert coolify["what_to_do"]["patch_to"] == "4.4.7" and coolify["severity"]["known_exploited"]
        receipt = php["receipt"]
        assert receipt["advisory_published"] == "2026-10-21T14:00:00Z"
        assert receipt["flagged_at"] == "2026-10-21T14:40:00Z"
        assert receipt["time_to_know_seconds"] == 2400 and receipt["status"] == "recorded"
        assert all(call.kwargs == {"task_type": "ghost.advisory"} for call in receipts.record.await_args_list)
        assert receipts.record.await_count == 2

        clock["now"] = moment + timedelta(minutes=15)
        again = await watcher.cycle()
        assert again["new_matches"] == 0 and again["open"] == 2
        assert receipts.record.await_count == 2  # Receipts are not repeated.

        report(store, json.loads((FIXTURES / "host-a-report-2026-10-23.json").read_text()), at="2026-10-23T22:05:12Z")
        clock["now"] = moment + timedelta(days=2)
        after = await watcher.cycle()
        assert after["resolved"] == 2 and after["open"] == 0
        resolved = store.matches(PLATFORM_TENANT, "resolved")
        assert {m["resolution"] for m in resolved} == {"updated"}
        assert all(m["resolved_receipt"]["status"] == "recorded" for m in resolved)
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_only_named_public_hosts_are_ever_called(tmp_path):
    sources = Sources()
    store, http, _receipts, watcher, _clock = make_watcher(tmp_path, sources, datetime.now(timezone.utc))
    try:
        report(store, load("inventory-before.json"))
        store.replace_inventory(PLATFORM_TENANT, "repo", [{"app": "tank", "kind": "package", "name": "fastapi",
                                                           "version": "0.115.6", "ecosystem": "pypi"}], "t")
        await watcher.cycle()
        assert {r.url.host for r in sources.calls} <= adv.ALLOWED_HOSTS
        assert {(r.method, r.url.host) for r in sources.calls if r.method != "GET"} == {("POST", "api.osv.dev")}
        assert not any("authorization" in {k.lower() for k in r.headers} or "apikey" in str(r.url).lower()
                       for r in sources.calls)
        # Every named source was asked, and nothing else.
        hosts = {r.url.host for r in sources.calls}
        assert hosts == adv.ALLOWED_HOSTS
        feeds = adv.Feeds(http)
        with pytest.raises(PermissionError):
            await feeds.get("https://example.com/feed.json")
        with pytest.raises(PermissionError):
            await feeds.request("POST", adv.GHSA_URL, json={})
        with pytest.raises(PermissionError):
            await feeds.get("http://api.osv.dev/v1/vulns/x")
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_osv_hit_is_rechecked_with_our_own_ranges(tmp_path):
    vuln = {"id": "GHSA-test-0001", "aliases": ["CVE-2026-0001"], "published": "2026-10-20T00:00:00Z",
            "modified": "2026-10-20T00:00:00Z", "summary": "test",
            "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
            "affected": [{"package": {"ecosystem": "PyPI", "name": "FastAPI"},
                          "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.115.7"}]}]},
                         {"package": {"ecosystem": "PyPI", "name": "uvicorn"},
                          "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.1"}]}]}]}

    def osv(request):
        if request.method == "POST":
            queries = json.loads(request.content)["queries"]
            return httpx.Response(200, json={"results": [{"vulns": [{"id": vuln["id"], "modified": vuln["modified"]}]} for _ in queries]})
        return httpx.Response(200, json=vuln)

    sources = Sources(osv=osv)
    store, http, _r, watcher, _c = make_watcher(tmp_path, sources, datetime(2026, 10, 21, tzinfo=timezone.utc))
    try:
        store.replace_inventory(PLATFORM_TENANT, "repo", [
            {"app": "tank", "kind": "package", "name": "fastapi", "version": "0.115.6", "ecosystem": "pypi"},
            {"app": "tank", "kind": "package", "name": "uvicorn", "version": "0.32.1", "ecosystem": "pypi"}], "t")
        summary = await watcher.cycle()
        matches = store.matches(PLATFORM_TENANT, "open")
        assert summary["new_matches"] == 1 and [m["affected"]["name"] for m in matches] == ["fastapi"]
        assert matches[0]["advisory_id"] == "CVE-2026-0001" and matches[0]["severity"]["cvss"] == 9.8
        assert matches[0]["what_to_do"]["patch_to"] == "0.115.7"
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_github_and_vendor_notes_are_parsed_and_merged_by_cve(tmp_path):
    ghsa = [{"ghsa_id": "GHSA-aaaa-bbbb-cccc", "cve_id": "CVE-2026-109618", "published_at": "2026-10-21T13:00:00Z",
             "updated_at": "2026-10-21T13:00:00Z", "severity": "critical", "summary": "php",
             "vulnerabilities": [{"package": {"ecosystem": "pip", "name": "LiteLLM"},
                                  "vulnerable_version_range": ">= 1.0.0, < 1.106.1", "first_patched_version": "1.106.1"}]}]
    node = [{"version": "v24.23.0", "date": "2026-10-20", "security": True}, {"version": "v24.22.1", "date": "2026-09-01", "security": False}]
    php = {"8.4.27": {"date": "21 Oct 2026", "tags": ["security"]}, "8.4.26": {"date": "02 Oct 2026", "tags": []}}
    coolify = [{"tag_name": "v4.4.7", "published_at": "2026-10-21T15:00:00Z", "body": "Fixes CVE-2026-109619 security issue", "prerelease": False},
               {"tag_name": "v4.5.0-beta.1", "published_at": "2026-10-22T15:00:00Z", "body": "security", "prerelease": True}]
    sources = Sources(github=httpx.Response(200, json=ghsa), node=httpx.Response(200, json=node),
                      php=httpx.Response(200, json=php), coolify=httpx.Response(200, json=coolify),
                      nvd=httpx.Response(200, json={"totalResults": 0, "vulnerabilities": []}))
    store, http, _r, watcher, _c = make_watcher(tmp_path, sources, datetime(2026, 10, 21, 16, tzinfo=timezone.utc))
    try:
        report(store, load("inventory-before.json"))
        report_raw = {"litellm": {"litellm_pkg": "1.106.0"}}
        store.replace_inventory(PLATFORM_TENANT, "host:host-b", [vars(c) for c in from_host_report(report_raw)], "t")
        await watcher.cycle()
        found = {(m["advisory_id"], m["affected"]["name"]): m for m in store.matches(PLATFORM_TENANT, "open")}
        assert found[("CVE-2026-109618", "litellm")]["what_to_do"]["patch_to"] == "1.106.1"
        assert found[("CVE-2026-109618", "litellm")]["severity"]["known_exploited"] is True
        assert found[("PHP-8.4.27", "php")]["what_to_do"]["patch_to"] == "8.4.27"
        assert found[("NODE-24.23.0", "node")]["affected"]["version"] == "24.22.1"
        assert found[("CVE-2026-109619", "coolify")]["first_source"] == "vendor:coolify"
        github_call = next(r for r in sources.calls if r.url.path == "/advisories")
        assert github_call.url.params["sort"] == "updated"
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_a_failing_source_is_reported_without_detail_and_never_resolves_issues(tmp_path):
    moment = datetime(2026, 10, 21, 14, 40, tzinfo=timezone.utc)
    store, http, _r, watcher, clock = make_watcher(tmp_path, Sources(), moment)
    try:
        report(store, load("inventory-before.json"))
        await watcher.cycle()
        watcher.feeds = adv.Feeds(httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r: httpx.Response(500, text=f"boom {SENTINEL}"))), pause=AsyncMock())
        clock["now"] = moment + timedelta(minutes=15)
        summary = await watcher.cycle()
        # OSV has nothing to ask (no packages in this inventory); every other source failed.
        assert {k for k, v in summary["sources"].items() if v == "unavailable"} == {"cisa_kev", "github", "nvd", "vendor_notes"}
        assert summary["open"] == 2 and summary["resolved"] == 0
        assert SENTINEL not in json.dumps(summary)
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_tank_down_keeps_receipt_pending_then_records_it(tmp_path):
    store, http, receipts, watcher, clock = make_watcher(tmp_path, Sources(), datetime(2026, 10, 21, 14, 40, tzinfo=timezone.utc))
    try:
        receipts.record.side_effect = RuntimeError("Tank did not accept the request.")
        report(store, load("inventory-before.json"))
        await watcher.cycle()
        assert {m["receipt"]["status"] for m in store.matches(PLATFORM_TENANT, "open")} == {"pending"}
        receipts.record.side_effect = None
        await watcher.cycle()
        assert {m["receipt"]["status"] for m in store.matches(PLATFORM_TENANT, "open")} == {"recorded"}
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_nvd_paging_respects_public_rate_limit(tmp_path):
    pages = []

    def nvd(request):
        pages.append(dict(request.url.params))
        if "cveId" in request.url.params:
            return httpx.Response(200, json={"totalResults": 0, "vulnerabilities": []})
        return httpx.Response(200, json={"totalResults": 4001, "vulnerabilities": [{"cve": {}}] * 2000})

    store, http, _r, watcher, _c = make_watcher(tmp_path, Sources(nvd=nvd), datetime(2026, 10, 21, tzinfo=timezone.utc))
    try:
        await watcher.cycle()
        windows = [p for p in pages if "cveId" not in p]
        assert len(windows) == 3 and [p["startIndex"] for p in windows] == ["0", "2000", "4000"]
        assert all("apiKey" not in p for p in pages)
        assert watcher.feeds.pause.await_count >= 2
        assert all(c.args == (adv.NVD_PAUSE_SECONDS,) for c in watcher.feeds.pause.await_args_list)
    finally:
        await http.aclose()
        store.close()


def test_cvss3_scores():
    assert adv.cvss3_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == 9.8
    assert adv.cvss3_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H") == 10.0
    assert adv.cvss3_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N") == 6.1
    assert adv.cvss3_score("CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:N/I:N/A:N") == 0.0
    assert adv.cvss3_score("garbage") is None


def test_base_image_lines_are_not_range_checked():
    rule = {"ecosystem": "generic", "name": "python", "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "3.12.8"}]}]}
    line = {"app": "rig", "kind": "runtime", "name": "python", "version": "3.12", "ecosystem": "generic"}
    exact = {**line, "version": "3.12.7"}
    assert adv.rule_targets(rule, line) is False
    assert adv.rule_targets(rule, exact) and adv.rule_applies(rule, exact) is True


@pytest.mark.asyncio
async def test_routes_need_the_key_and_never_echo_secrets(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("TANK_KEY", "ghost-test")
    monkeypatch.setenv("COOLIFY_TOKEN_GHOST", SENTINEL)
    app = create_app()
    store = Store(tmp_path / "room.sqlite3")
    calls = []

    def internet(request):
        calls.append(request)
        if request.url.host == "coolify.tervory.com":
            assert request.method == "GET"
            return httpx.Response(401, text=f"bad token {SENTINEL}")
        return Sources()(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(internet))
    monkeypatch.setattr("agents.ghost.probes.public_addresses", lambda host: ["203.0.113.10"])
    app.state.store, app.state.http, app.state.advisory_lock = store, http, asyncio.Lock()
    app.state.watcher = adv.Watcher(store, adv.Feeds(http, pause=AsyncMock()), AsyncMock())
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ghost") as client:
            for method, path in (("GET", "/ghost/inventory"), ("POST", "/ghost/inventory/refresh"),
                                 ("POST", "/ghost/advisories/pull"), ("GET", "/ghost/advisories/matches")):
                assert (await client.request(method, path)).status_code == 404
            key = {"X-Tank-Key": "ghost-test"}
            await client.post("/ghost/inventory/report", headers=key,
                              json={"source": "host:host-a", "host_report": load("inventory-before.json")})
            texts = []
            for method, path in (("POST", "/ghost/inventory/refresh"), ("POST", "/ghost/advisories/pull"),
                                 ("GET", "/ghost/advisories/matches"), ("GET", "/ghost/inventory")):
                response = await client.request(method, path, headers=key)
                assert response.status_code == 200
                texts.append(response.text)
            refreshed = json.loads(texts[0])
            assert refreshed["coolify"] == "unavailable"
            assert len(json.loads(texts[2])["matches"]) == 2
        dump = "\n".join(str(row) for table in ("ghost_inventory", "ghost_advisories", "ghost_matches", "ghost_state")
                         for row in store.db.execute(f"SELECT * FROM {table}"))
        everything = "\n".join(texts) + dump + caplog.text
        assert SENTINEL not in everything
        assert any(r.headers.get("authorization") == "Bearer " + SENTINEL for r in calls if r.url.host == "coolify.tervory.com")
        assert not any(SENTINEL in str(r.url) or SENTINEL in r.content.decode(errors="ignore") for r in calls)
    finally:
        await http.aclose()
        store.close()


def test_coolify_notes_flag_only_the_same_release_line_and_only_real_fixes():
    releases = [
        {"tag_name": "v4.5.0", "published_at": "2026-10-23T10:41:38Z", "prerelease": False,
         "body": "## Features\n- Added server patching (beta) with automatic security updates per server"},
        {"tag_name": "v4.4.7", "published_at": "2026-10-21T14:12:45Z", "prerelease": False,
         "body": "This release fixes multiple critical CVEs. Security fix release for v4.4."},
        {"tag_name": "v4.3.24", "published_at": "2026-10-21T14:31:14Z", "prerelease": False,
         "body": "Backports the v4.4.7 security fixes. Fixes CVE-2026-109619."},
        {"tag_name": "v4.6.0-beta.1", "published_at": "2026-10-23T12:00:00Z", "prerelease": True,
         "body": "Security fix"},
    ]
    rules = {r["id"]: r for r in adv.parse_coolify_releases(releases)}
    assert set(rules) == {"COOLIFY-4.4.7", "COOLIFY-4.3.24"}
    assert rules["COOLIFY-4.3.24"]["aliases"] == ["CVE-2026-109619"]

    def hit(version):
        comp = {"app": "coolify", "kind": "software", "name": "coolify", "version": version, "ecosystem": "generic"}
        return sorted(r["id"] for r in rules.values() if any(adv.rule_applies(a, comp) for a in r["affected"]))

    assert hit("4.4.7") == [] and hit("4.5.0") == []
    assert hit("4.4.6") == ["COOLIFY-4.4.7"]
    assert hit("4.3.20") == ["COOLIFY-4.3.24"]
