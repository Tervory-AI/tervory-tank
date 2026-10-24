"""Redis in Ghost's inventory and advisory watcher.

Tank/queue runs redis:7 (lane E pins it to 7.4.x on its own branch); Chatwoot runs redis:alpine (floating).
A floating tag has no exact version, so Ghost matches it conservatively: flagged when any version the tag
could be running is affected. A pinned fixed version is never flagged. Fixture CVE ids are made up.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import httpx

from agents.ghost import advisories as adv
from agents.ghost.inventory import floating_version, from_host_report, image_components, parse_compose
from agents.ghost.models import PLATFORM_TENANT
from agents.ghost.store import Store

FIXTURE = Path(__file__).parent / "fixtures" / "ghost" / "host-a-report-2026-10-23.json"
CVE = "CVE-2026-990001"  # fixture only: Redis 7.2.0-7.2.10 and 7.4.0-7.4.5, fixed in 7.2.11 / 7.4.6


def redis(app, version):
    return {"app": app, "kind": "software", "name": "redis", "version": version, "ecosystem": "generic"}


def nvd_redis():
    match = lambda start, end: {"vulnerable": True, "criteria": "cpe:2.3:a:redis:redis:*:*:*:*:*:*:*:*",  # noqa: E731
                                "versionStartIncluding": start, "versionEndExcluding": end}
    return {"resultsPerPage": 1, "startIndex": 0, "totalResults": 1, "vulnerabilities": [{"cve": {
        "id": CVE, "published": "2026-10-22T09:00:00.000", "lastModified": "2026-10-22T09:30:00.000",
        "vulnStatus": "Analyzed", "descriptions": [{"lang": "en", "value": "Fixture: Lua script use-after-free in Redis."}],
        "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 8.8}}]},
        "configurations": [{"nodes": [{"cpeMatch": [match("7.2.0", "7.2.11"), match("7.4.0", "7.4.6")]}]}],
        "references": [{"url": "https://github.com/redis/redis/security/advisories/GHSA-fake-redi-s001"}]}}]}


def redis_repo_advisory():
    return [{"ghsa_id": "GHSA-fake-redi-s001", "cve_id": CVE, "published_at": "2026-10-22T08:00:00Z",
             "updated_at": "2026-10-22T08:00:00Z", "summary": "Fixture: Lua use-after-free", "severity": "high",
             "html_url": "https://github.com/redis/redis/security/advisories/GHSA-fake-redi-s001",
             "vulnerabilities": [
                 {"package": {"ecosystem": "", "name": "redis"}, "vulnerable_version_range": ">= 7.2.0, < 7.2.11",
                  "patched_versions": "7.2.11"},
                 {"package": {"ecosystem": "", "name": "redis"}, "vulnerable_version_range": ">= 7.4.0, < 7.4.6",
                  "patched_versions": "7.4.6"}]}]


def redis_releases():
    body = "Upgrade urgency SECURITY: See security fixes below.\n\n### Security fixes\n* (" + CVE + ") Lua use-after-free"
    return [{"tag_name": "7.4.6", "published_at": "2026-10-22T10:00:00Z", "prerelease": False, "body": body},
            {"tag_name": "7.2.11", "published_at": "2026-10-22T10:05:00Z", "prerelease": False, "body": body},
            {"tag_name": "8.2.3", "published_at": "2026-10-20T10:00:00Z", "prerelease": False,
             "body": "Upgrade urgency LOW: bug fixes only."}]


def all_rules():
    return [adv.parse_nvd(nvd_redis()["vulnerabilities"][0]),
            adv.parse_ghsa(redis_repo_advisory()[0], "vendor:redis", product="redis"),
            *adv.parse_redis_releases(redis_releases())]


def flagged(component, rules=None):
    return [m for m in adv.evaluate(rules or all_rules(), [component], {}) if m["advisory_id"] in {CVE, "REDIS-7.4.6", "REDIS-7.2.11", "REDIS-SECURITY-RELEASES"}]


def test_floating_tags_are_recorded_as_lines_or_unpinned():
    assert floating_version("7") == "7.x"
    assert floating_version("7-alpine") == "7.x"
    assert floating_version("7.4") == "7.4.x"
    assert floating_version("7.4-bookworm") == "7.4.x"
    assert floating_version("7.4.6-alpine") == "7.4.6"
    assert floating_version("7.4.6") == "7.4.6"
    assert floating_version("alpine") == "unpinned"
    assert floating_version("latest") == "unpinned"
    assert image_components("x", "redis") [1].version == "unpinned"  # no tag means latest


def test_host_report_keeps_tank_and_chatwoot_redis_apart():
    items = {(c.app, c.kind, c.name): c.version for c in from_host_report(json.loads(FIXTURE.read_text()))}
    assert items[("tank-redis", "software", "redis")] == "7.x"
    assert items[("tank-redis", "image", "redis")] == "7"
    assert items[("chatwoot-redis", "software", "redis")] == "unpinned"
    assert items[("chatwoot-redis", "image", "redis")] == "alpine"
    assert items[("coolify-redis", "software", "redis")] == "7.x"
    assert items[("tank-postgres", "image", "postgres")] == "16"
    assert ("redis", "software", "redis") not in items


def test_repo_compose_redis_today_and_once_pinned():
    today = "services:\n  tank:\n    build: .\n  redis:\n    image: redis:7\n    restart: unless-stopped\n"
    pinned = "services:\n  redis:\n    image: \"redis:7.4.6-alpine\"  # pinned\n"
    line = "services:\n  redis:\n    image: redis:7.4\n"
    get = lambda text: {(c.app, c.kind): c.version for c in parse_compose("tank", text)}  # noqa: E731
    assert get(today)[("tank-redis", "software")] == "7.x"
    assert get(pinned)[("tank-redis", "software")] == "7.4.6"
    assert get(line)[("tank-redis", "software")] == "7.4.x"


def test_redis_cve_on_7_2_and_7_4_flags_both_entries_and_not_fixed_versions():
    # Both real entries: Tank's redis:7 and Chatwoot's redis:alpine.
    for component in (redis("tank-redis", "7.x"), redis("chatwoot-redis", "unpinned"), redis("tank-redis", "7.4.x"),
                      redis("tank-redis", "7.2.x"), redis("tank-redis", "7.4.5"), redis("tank-redis", "7.2.0")):
        hits = flagged(component)
        assert any(m["advisory_id"] == CVE for m in hits), component
    # Pinned fixed versions, and lines the CVE never touched, are not flagged.
    for component in (redis("tank-redis", "7.4.6"), redis("tank-redis", "7.2.11"), redis("tank-redis", "7.4.7"),
                      redis("tank-redis", "8.2.3"), redis("tank-redis", "8.x"), redis("tank-redis", "6.2.x"),
                      redis("tank-redis", "7.0.15")):
        assert flagged(component) == [], component


def test_floating_matches_say_the_version_is_unknown_and_suggest_a_pin():
    line = next(m for m in flagged(redis("tank-redis", "7.x")) if m["advisory_id"] == CVE)
    assert line["what_to_do"]["exact_version_known"] is False
    assert line["what_to_do"]["patch_to"] == "7.4.6"  # newest fix that stays on the 7 line
    assert "Pin it to 7.4.6 or later" in line["what_to_do"]["plain"]
    unpinned = next(m for m in flagged(redis("chatwoot-redis", "unpinned")) if m["advisory_id"] == CVE)
    assert unpinned["what_to_do"]["exact_version_known"] is False and unpinned["what_to_do"]["patch_to"]
    assert "unpinned image tag" in unpinned["what_to_do"]["plain"]
    exact = next(m for m in flagged(redis("tank-redis", "7.4.5")) if m["advisory_id"] == CVE)
    assert exact["what_to_do"]["patch_to"] == "7.4.6" and "exact_version_known" not in exact["what_to_do"]


def test_each_source_alone_flags_redis():
    nvd, ghsa, *vendor = all_rules()
    for rules in ([nvd], [ghsa], vendor):
        assert flagged(redis("tank-redis", "7.x"), rules), rules[0]["source"]
        assert flagged(redis("chatwoot-redis", "unpinned"), rules), rules[0]["source"]
        assert not flagged(redis("tank-redis", "7.4.6"), rules), rules[0]["source"]
    # A release note without a security fix is not an advisory.
    assert {r["id"] for r in vendor} == {"REDIS-7.4.6", "REDIS-7.2.11"}
    # The redis-py client package (pip "redis") is a different thing from the Redis server.
    client = {"ghsa_id": "GHSA-fake-redi-spy1", "published_at": "2026-10-22T08:00:00Z", "summary": "redis-py",
              "vulnerabilities": [{"package": {"ecosystem": "pip", "name": "redis"},
                                   "vulnerable_version_range": "< 9.0.0", "patched_versions": "9.0.0"}]}
    assert not adv.evaluate([adv.parse_ghsa(client)], [redis("tank-redis", "unpinned")], {})


def test_watcher_cycle_flags_both_redis_entries_from_the_brief_sources(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("ghost_adv_tests", Path(__file__).parent / "test_ghost_advisories.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    Sources = helpers.Sources

    sources = Sources(nvd=httpx.Response(200, json=nvd_redis()),
                      redis_releases=httpx.Response(200, json=redis_releases()),
                      redis_advisories=httpx.Response(200, json=redis_repo_advisory()),
                      kev=httpx.Response(200, json={"vulnerabilities": []}))

    async def run():
        store = Store(tmp_path / "ghost.sqlite3")
        store.replace_inventory(PLATFORM_TENANT, "host:host-a",
                                [vars(c) for c in from_host_report(json.loads(FIXTURE.read_text()))], "2026-10-23T10:00:00Z")
        http = httpx.AsyncClient(transport=httpx.MockTransport(sources))
        moment = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        watcher = adv.Watcher(store, adv.Feeds(http, pause=AsyncMock()), AsyncMock(), clock=lambda: moment)
        summary = await watcher.cycle()
        await http.aclose()
        return summary, store.matches(PLATFORM_TENANT, "open")

    summary, matches = asyncio.run(run())
    redis_hits = {m["affected"]["app"] for m in matches if m["advisory_id"] == CVE}
    assert {"tank-redis", "chatwoot-redis", "coolify-redis"} <= redis_hits
    hit = next(m for m in matches if m["advisory_id"] == CVE and m["affected"]["app"] == "chatwoot-redis")
    assert hit["receipt"]["time_to_know_seconds"] == 4 * 3600  # GHSA published 08:00, flagged 12:00
    hosts = {r.url.host for r in sources.calls}
    assert hosts <= adv.ALLOWED_HOSTS
    assert any(r.url.path == "/repos/redis/redis/releases" for r in sources.calls)


def test_unpinned_tag_gets_one_vendor_finding_not_one_per_release_line():
    releases = [{"tag_name": tag, "published_at": f"2026-09-17T15:0{i}:00Z", "prerelease": False,
                 "body": "Update urgency: `SECURITY`: There are security fixes in the release."}
                for i, tag in enumerate(["8.10.2", "8.8.3", "8.2.10", "7.4.11", "7.2.16"])]
    rules = adv.parse_redis_releases(releases)
    unpinned = adv.evaluate(rules, [redis("chatwoot-redis", "unpinned")], {})
    assert len(unpinned) == 1
    assert unpinned[0]["advisory_id"] == "REDIS-SECURITY-RELEASES"
    assert unpinned[0]["what_to_do"]["patch_to"] == "8.10.2"
    # A line tag only hears about its own line(s).
    line = adv.evaluate(rules, [redis("tank-redis", "7.x")], {})
    assert sorted(m["advisory_id"] for m in line) == ["REDIS-7.2.16", "REDIS-7.4.11"]
    assert adv.evaluate(rules, [redis("tank-redis", "7.4.11")], {}) == []
