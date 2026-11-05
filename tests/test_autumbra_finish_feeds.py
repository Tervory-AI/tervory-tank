import json
import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from agents.ghost import advisories as adv
from agents.ghost.models import PLATFORM_TENANT as TENANT
from agents.ghost.store import Store
from test_ghost_advisories import Sources, load, make_watcher, report

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


def ghsa(identity="GHSA-finish-1", **extra):
    return {"ghsa_id": identity, "published_at": "2026-11-01T00:00:00Z",
            "updated_at": "2026-11-04T00:00:00Z", "severity": "high",
            "vulnerabilities": [{"package": {"ecosystem": "pip", "name": "fastapi"},
                                 "vulnerable_version_range": "< 1.0", "first_patched_version": "1.0"}], **extra}


def package(store):
    store.replace_inventory(TENANT, "repo", [{"app": "tank", "kind": "package", "name": "fastapi",
        "version": "0.115.6", "ecosystem": "pypi"}], adv.iso(NOW))


@pytest.mark.asyncio
async def test_github_all_pages_and_atomic_cursor_after_failed_second_page(tmp_path):
    failed = True

    def github(request):
        if "after" in request.url.params:
            return httpx.Response(503) if failed else httpx.Response(200, json=[ghsa("GHSA-finish-2")])
        return httpx.Response(200, json=[ghsa()], headers={"link": '<https://api.github.com/advisories?after=next>; rel="next"'})

    store, http, _, watcher, _ = make_watcher(tmp_path, Sources(github=github), NOW)
    try:
        package(store)
        result = await watcher.cycle()
        assert result["sources"]["github"] == "unavailable"
        assert store.get_state(TENANT, "ghsa_cursor") is None
        assert not store.advisories(TENANT)
        failed = False
        result = await watcher.cycle()
        assert result["new_matches"] == 2
        assert len(store.advisories(TENANT)) == 2
        assert store.get_state(TENANT, "ghsa_cursor") == adv.iso(NOW - timedelta(hours=1))
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("next_url", ["https://attacker.example/page", "https://api.github.com/user",
    "https://api.github.com:444/advisories", "https://api.github.com/advisories"])
async def test_pagination_rejects_redirected_or_repeated_endpoints(next_url):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=[], headers={"link": f'<{next_url}>; rel="next"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises((PermissionError, RuntimeError)):
            await adv.Feeds(http).pages(adv.GHSA_URL)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_osv_batch_pagination_and_more_than_150_advisories(tmp_path):
    pages, fetched = [], []

    def osv(request):
        if request.method == "POST":
            query = json.loads(request.content)["queries"][0]
            pages.append(query)
            if query.get("page_token") == "next":
                result = {"vulns": [{"id": "OSV-finish-151"}]}
            else:
                result = {"vulns": [{"id": f"OSV-finish-{i}"} for i in range(151)], "next_page_token": "next"}
            return httpx.Response(200, json={"results": [result]})
        identity = request.url.path.rsplit("/", 1)[1]
        fetched.append(identity)
        return httpx.Response(200, json={"id": identity, "published": adv.iso(NOW), "affected": []})

    store, http, _, watcher, _ = make_watcher(tmp_path, Sources(osv=osv), NOW)
    try:
        package(store)
        found = await watcher.pull_osv(adv.Cycle(NOW))
        assert len(found) == len(fetched) == 152
        assert len(pages) == 2 and pages[1]["page_token"] == "next"
        assert pages[1]["package"] == pages[0]["package"]
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_nvd_exhausts_busy_feed_and_catches_up_old_cursor_without_gap(tmp_path):
    calls = []

    def nvd(request):
        params = dict(request.url.params)
        calls.append(params)
        index = int(params["startIndex"])
        return httpx.Response(200, json={"startIndex": index, "totalResults": 6001,
            "vulnerabilities": [{"cve": {}}] * min(2000, 6001 - index)})

    store, http, _, watcher, _ = make_watcher(tmp_path, Sources(nvd=nvd), NOW)
    try:
        old = NOW - timedelta(days=200)
        store.set_state(TENANT, "nvd_cursor", adv.iso(old))
        cycle = adv.Cycle(NOW)
        await watcher.pull_nvd(cycle)
        assert [int(p["startIndex"]) for p in calls] == [0, 2000, 4000, 6000]
        assert calls[0]["lastModStartDate"].startswith(old.date().isoformat())
        assert calls[0]["lastModEndDate"].startswith((old + timedelta(days=119)).date().isoformat())
        assert store.get_state(TENANT, "nvd_cursor") == adv.iso(old)
        assert cycle.cursors["nvd_cursor"] == adv.iso(old + timedelta(days=119, minutes=-5))
        assert watcher.feeds.pause.await_count == 3
    finally:
        await http.aclose()
        store.close()


def test_feed_database_failure_rolls_back_both_rows_and_cursor(tmp_path):
    store = Store(tmp_path / "store.sqlite")
    try:
        store.db.execute("CREATE TRIGGER fail_cursor BEFORE INSERT ON ghost_state BEGIN SELECT RAISE(ABORT, 'offline failure'); END")
        with pytest.raises(sqlite3.IntegrityError):
            store.save_feed(TENANT, [adv.parse_ghsa(ghsa())], adv.iso(NOW), {"ghsa_cursor": adv.iso(NOW)})
        assert store.advisories(TENANT) == []
        assert store.get_state(TENANT, "ghsa_cursor") is None
    finally:
        store.close()


@pytest.mark.asyncio
async def test_withdrawal_resolves_and_retries_receipt_after_store_reopen(tmp_path):
    withdrawn = False
    sources = Sources(github=lambda r: httpx.Response(200, json=[ghsa(withdrawn_at=adv.iso(NOW) if withdrawn else None)]))
    store, http, receipts, watcher, _ = make_watcher(tmp_path, sources, NOW)
    try:
        package(store)
        await watcher.cycle()
        issue = store.matches(TENANT, "open")[0]
        assert issue["what_to_do"]["patch_to"] == "1.0"
        withdrawn = True
        receipts.record.side_effect = RuntimeError("offline")
        await watcher.cycle()
        resolved = store.matches(TENANT, "resolved")[0]
        assert resolved["resolved_receipt"]["status"] == "pending"
        attempted_id = receipts.record.await_args.args[0]
        store.close()
        store = Store(tmp_path / "ghost.sqlite3")
        watcher.store = store
        receipts.record.side_effect = None
        await watcher.cycle()
        resolved = store.matches(TENANT, "resolved")[0]
        assert resolved["resolved_receipt"]["status"] == "recorded"
        assert resolved["resolved_receipt"]["ledger_id"] == attempted_id
        before = receipts.record.await_count
        await watcher.cycle()
        assert receipts.record.await_count == before
    finally:
        await http.aclose()
        store.close()


def test_osv_and_nvd_withdrawals_are_tombstones():
    osv = adv.parse_osv({"id": "OSV-finish", "published": adv.iso(NOW), "withdrawn": adv.iso(NOW),
        "affected": [{"package": {"ecosystem": "PyPI", "name": "fastapi"}, "versions": ["0.115.6"]}]})
    nvd = adv.parse_nvd({"cve": {"id": "CVE-2026-12345", "published": adv.iso(NOW), "vulnStatus": "Rejected"}})
    assert osv["affected"] == nvd["affected"] == []


@pytest.mark.asyncio
async def test_osv_withdrawn_record_is_refetched_when_batch_no_longer_reports_it(tmp_path):
    stored = {"id": "OSV-withdrawn", "published": adv.iso(NOW), "affected": [
        {"package": {"ecosystem": "PyPI", "name": "fastapi"}, "versions": ["0.115.6"]}]}

    def osv(request):
        if request.method == "POST":
            return httpx.Response(200, json={"results": [{}]})
        return httpx.Response(200, json={**stored, "withdrawn": adv.iso(NOW)})

    store, http, _, watcher, _ = make_watcher(tmp_path, Sources(osv=osv), NOW)
    try:
        package(store)
        store.save_advisory(TENANT, adv.parse_osv(stored), adv.iso(NOW))
        await watcher.match(adv.Cycle(NOW))
        assert len(store.matches(TENANT, 'open')) == 1
        await watcher.cycle()
        assert store.matches(TENANT, 'open') == []
        assert len(store.matches(TENANT, 'resolved')) == 1
    finally:
        await http.aclose()
        store.close()


@pytest.mark.asyncio
async def test_nvd_bootstrap_finds_older_installed_software_advisories_once(tmp_path):
    calls = []

    def nvd(request):
        params = dict(request.url.params)
        calls.append(params)
        if params.get('virtualMatchString') == 'cpe:2.3:a:php:php:*:*:*:*:*:*:*:*':
            return httpx.Response(200, json=load('nvd-CVE-2026-109618.json'))
        return httpx.Response(200, json={'totalResults': 0, 'vulnerabilities': []})

    store, http, _, watcher, _ = make_watcher(tmp_path,
        Sources(nvd=nvd, kev=httpx.Response(200, json={'vulnerabilities': []})), NOW)
    try:
        store.replace_inventory(TENANT, 'repo', [{'app': 'site', 'kind': 'runtime', 'name': 'php',
            'version': '8.4.23', 'ecosystem': 'generic'}], adv.iso(NOW))
        result = await watcher.cycle()
        assert result['sources']['nvd'] == 'ok' and result['new_matches'] == 1
        assert store.matches(TENANT, 'open')[0]['advisory_id'] == 'CVE-2026-109618'
        assert store.get_state(TENANT, 'nvd_product:php:php') == adv.iso(NOW)
        await watcher.cycle()
        assert sum('virtualMatchString' in call for call in calls) == 1
    finally:
        await http.aclose()
        store.close()
