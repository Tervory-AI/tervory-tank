"""SAFLII search and fetch. Saved HTML only. No network."""

from __future__ import annotations

import asyncio
import io
import json
import sys
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.zenas.core.ladder_store import LadderMemory  # noqa: E402
from agents.zenas.core.service import retrieve  # noqa: E402
from agents.zenas.pool.adapters import za_saflii  # noqa: E402
from agents.zenas.pool.adapters.za_saflii import (  # noqa: E402
    USER_AGENT,
    HostPacer,
    SafliiAdapter,
    SafliiBlocked,
    canonical_case_url,
    case_urls_in,
    is_cloudflare_block,
    is_origin_forbidden,
    public_search_url,
    search_and_fetch,
)
from agents.zenas.pool.bulk import load_wave  # noqa: E402
from agents.zenas.pool.catalogue import CATALOGUE  # noqa: E402
from agents.zenas.pool.store import MemoryStore  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "saflii"
POOL = ROOT / "agents" / "zenas" / "pool" / "fixtures" / "za" / "saflii"
CIVIL_URL = "https://www.saflii.org/za/cases/ZASCA/2023/12.html"
CRIME_URL = "https://www.saflii.org/za/cases/ZASCA/2023/99.html"
TENANT = "00000000-0000-0000-0000-0000000000a1"
WHEN = datetime(2026, 10, 16, tzinfo=timezone.utc)


def _quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAFLII_MIN_INTERVAL", "0")
    monkeypatch.setenv("SAFLII_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("SAFLII_FETCH", "urllib")
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)


def _civil() -> bytes:
    return (POOL / "2023-zasca-12.html").read_bytes()


def _criminal() -> bytes:
    return (POOL / "2023-zasca-99-criminal.html").read_bytes()


def _cloud() -> bytes:
    return (FIXTURES / "cloudflare-just-a-moment.html").read_bytes()


def _source():
    return next(item for item in CATALOGUE if item.source_id == "saflii")


def test_case_url_keeps_only_judgment_pages():
    assert canonical_case_url("https://www.saflii.org/za/cases/ZASCA/2023/12.html") == CIVIL_URL
    assert canonical_case_url("/za/cases/zasca/2023/12.html?print=1") == CIVIL_URL
    assert canonical_case_url("https://www.saflii.org/za/cases/ZASCA/2023/12.pdf") == ""
    assert canonical_case_url("https://example.invalid/za/cases/ZASCA/2023/12.html") == ""


def test_cloudflare_page_is_recognised():
    assert is_cloudflare_block(403, _cloud())
    assert is_cloudflare_block(200, _cloud())
    assert not is_cloudflare_block(200, _civil())


def test_requests_are_spaced_per_host(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SAFLII_MIN_INTERVAL", "0.12")
    asyncio.run(_spaced())


async def _spaced():
    pacer = HostPacer()
    started = time.monotonic()
    await pacer.wait("https://www.saflii.org/za/cases/ZASCA/recent.html")
    await pacer.wait(CIVIL_URL)
    assert time.monotonic() - started >= 0.12


def test_search_uses_saved_pages_and_stores_them(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    asyncio.run(_search_stores())


async def _search_stores():
    calls: list[str] = []
    agents: list[str] = []
    hits = [CIVIL_URL, CRIME_URL, "https://www.saflii.org/za/cases/ZASCA/2023/12.pdf"]

    async def search(_query: str) -> list[str]:
        return list(hits)

    async def http_get(url, headers):
        calls.append(url)
        agents.append(headers.get("User-Agent", ""))
        if url == CRIME_URL:
            return _criminal()
        return _civil()

    store = MemoryStore(home_region="za")
    found = await search_and_fetch(
        "bill of lading",
        search=search,
        http_get=http_get,
        store=store,
        now=WHEN,
    )
    assert found["state"] == "ok"
    assert found["found_via"] == "search"
    assert len(found["excerpts"]) == 1
    excerpt = found["excerpts"][0]
    assert excerpt["citation"] == "[2023] ZASCA 12"
    assert excerpt["url"] == CIVIL_URL
    assert "bill of lading" in excerpt["excerpt"].lower()
    assert calls == [CIVIL_URL, CRIME_URL]
    assert set(agents) == {USER_AGENT}
    text = await store.all_text()
    assert "Dlamini" not in text
    assert "bill of lading" in text.lower()
    assert CIVIL_URL in store.page_cache
    assert CRIME_URL not in store.page_cache

    hits[:] = [CIVIL_URL]
    again = await search_and_fetch(
        "bill of lading",
        search=search,
        http_get=http_get,
        store=store,
        now=WHEN,
    )
    assert again["found_via"] == "cache"
    assert calls == [CIVIL_URL, CRIME_URL]
    assert again["excerpts"][0]["citation"] == "[2023] ZASCA 12"


def test_a_stale_copy_is_fetched_again(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    asyncio.run(_stale())


async def _stale():
    calls: list[str] = []

    async def search(_query: str) -> list[str]:
        return [CIVIL_URL]

    async def http_get(url, headers):
        del headers
        calls.append(url)
        return _civil()

    store = MemoryStore(home_region="za")
    await search_and_fetch("bill of lading", search=search, http_get=http_get, store=store, now=WHEN)
    body, _fetched, ttl = store.page_cache[CIVIL_URL]
    store.page_cache[CIVIL_URL] = (body, WHEN - timedelta(days=400), ttl)
    await search_and_fetch("bill of lading", search=search, http_get=http_get, store=store, now=WHEN)
    assert calls == [CIVIL_URL, CIVIL_URL]


def test_cgi_is_the_fallback_when_search_has_no_case_url(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    asyncio.run(_cgi())


async def _cgi():
    seen: list[str] = []

    async def search(_query: str) -> list[str]:
        return ["https://example.invalid/notes"]

    async def http_get(url, headers):
        del headers
        seen.append(url)
        if "sinosrch-adw.cgi" in url:
            assert "bill+of+lading" in url or "bill of lading" in url
            return (FIXTURES / "sinosrch-results.html").read_bytes()
        if url == CIVIL_URL:
            return _civil()
        return b"<html></html>"

    found = await search_and_fetch("bill of lading", search=search, http_get=http_get, now=WHEN)
    assert found["found_via"] == "saflii-cgi"
    assert found["excerpts"][0]["url"] == CIVIL_URL
    assert any("sinosrch-adw.cgi" in url for url in seen)
    assert CIVIL_URL in seen


def test_searx_is_used_before_brave_and_the_key_stays_out_of_the_url(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    monkeypatch.setenv("SEARXNG_URL", "http://search.test")
    monkeypatch.setenv("BRAVE_API_KEY", "secret-token-value")
    asyncio.run(_searx_then_page())


async def _searx_then_page():
    seen: list[tuple[str, dict]] = []

    async def http_get(url, headers):
        seen.append((url, dict(headers)))
        if url.startswith("http://search.test/"):
            assert "secret-token-value" not in url
            assert "site%3Asaflii.org" in url or "site:saflii.org" in url
            body = json.dumps({"results": [{"url": CIVIL_URL}]})
            return body.encode()
        if "api.search.brave.com" in url:
            raise AssertionError("Brave was called after SearXNG returned a judgment")
        return _civil()

    found = await search_and_fetch("bill of lading", http_get=http_get, live=True, now=WHEN)
    assert found["found_via"] == "searxng"
    assert found["excerpts"][0]["citation"] == "[2023] ZASCA 12"
    assert all("secret-token-value" not in url for url, _headers in seen)


def test_brave_header_carries_the_key(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    monkeypatch.setenv("BRAVE_API_KEY", "secret-token-value")
    asyncio.run(_brave())


async def _brave():
    seen: list[tuple[str, dict]] = []

    async def http_get(url, headers):
        seen.append((url, dict(headers)))
        if "api.search.brave.com" in url:
            assert "secret-token-value" not in url
            assert headers["X-Subscription-Token"] == "secret-token-value"
            body = json.dumps({"web": {"results": [{"url": CIVIL_URL}]}})
            return body.encode()
        return _civil()

    found = await search_and_fetch("carrier", http_get=http_get, live=True, now=WHEN)
    assert found["found_via"] == "brave"
    assert found["state"] == "ok"


def test_a_cloudflare_check_is_blocked_and_not_stored(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    asyncio.run(_blocked())


async def _blocked():
    calls: list[str] = []

    async def search(_query: str) -> list[str]:
        return [CIVIL_URL, CRIME_URL]

    async def http_get(url, headers):
        del headers
        calls.append(url)
        raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=io.BytesIO(_cloud()))

    store = MemoryStore(home_region="za")
    found = await search_and_fetch("bill of lading", search=search, http_get=http_get, store=store, now=WHEN)
    assert found["ok"] is False
    assert found["state"] == "blocked"
    assert "Just a moment" in found["reason"]
    assert found["excerpts"] == []
    assert calls == [CIVIL_URL]
    assert store.page_cache == {}
    assert await store.all_text() == ""


def test_a_busy_server_backs_off_then_returns_the_page(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    asyncio.run(_backoff())


async def _backoff():
    calls = {"n": 0}

    async def search(_query: str) -> list[str]:
        return [CIVIL_URL]

    async def http_get(url, headers):
        del url, headers
        calls["n"] += 1
        if calls["n"] < 3:
            return 503, b"busy"
        return 200, _civil()

    found = await search_and_fetch("bill of lading", search=search, http_get=http_get, now=WHEN)
    assert calls["n"] == 3
    assert found["state"] == "ok"
    assert found["excerpts"][0]["citation"] == "[2023] ZASCA 12"


def test_index_pages_load_over_time_and_a_block_is_recorded(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    monkeypatch.setenv("ZA_CASE_MAX_DOCS", "1")
    asyncio.run(_waves())


async def _waves():
    index = (FIXTURES / "zasca-recent.html").read_bytes()
    seen: list[str] = []

    async def get(url, headers):
        assert headers["User-Agent"] == USER_AGENT
        seen.append(url)
        if url.endswith("/ZASCA/recent.html"):
            return index
        if url.endswith("/2023/12.html"):
            return _civil()
        if url.endswith("/2023/99.html"):
            return _criminal()
        return b"<html></html>"

    store = MemoryStore()
    first = await load_wave(store, region="za", only=[_source()], live=True, http_get=get, on=WHEN.date())
    row = first["sources"][0]
    assert row["last_status"] == "ok"
    assert row["documents"] == 1
    assert "Dlamini" not in await store.all_text()
    assert CIVIL_URL in store.page_cache
    assert CRIME_URL not in store.page_cache
    cursor = await store.get_checkpoint("saflii")
    assert cursor == "0:1"

    second = await load_wave(store, region="za", only=[_source()], live=True, http_get=get, on=WHEN.date())
    again = second["sources"][0]
    assert again["documents"] == 1
    assert "Dlamini" not in await store.all_text()
    assert CRIME_URL not in store.page_cache
    assert await store.get_checkpoint("saflii") == "1:0"

    async def blocked(url, headers):
        del headers
        raise SafliiBlocked(url)

    third = await load_wave(store, region="za", only=[_source()], live=True, http_get=blocked, on=WHEN.date())
    stopped = third["sources"][0]
    assert stopped["last_status"] == "error"
    assert "blocked" in stopped["detail"].lower()
    assert "just a moment" in stopped["detail"].lower()
    assert stopped["documents"] == 1
    assert seen[0].endswith("/ZASCA/recent.html")


def test_the_adapter_method_delegates(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    asyncio.run(_method())


async def _method():
    async def search(_query: str) -> list[str]:
        return [CIVIL_URL]

    async def http_get(url, headers):
        del url, headers
        return _civil()

    found = await SafliiAdapter().search_and_fetch("bill of lading", search=search, http_get=http_get, now=WHEN)
    assert found["excerpts"][0]["citation"] == "[2023] ZASCA 12"


def test_research_merges_a_saflii_excerpt_and_reports_a_block(monkeypatch: pytest.MonkeyPatch):
    asyncio.run(_research(monkeypatch))


async def _research(monkeypatch: pytest.MonkeyPatch):
    ladder = LadderMemory()
    await ladder.register_tenant(TENANT, "za")
    called = {"n": 0}

    async def fake(query, **kwargs):
        del kwargs
        called["n"] += 1
        assert query == "bill of lading"
        return {
            "ok": True,
            "state": "ok",
            "reason": "",
            "excerpts": [
                {
                    "citation": "[2023] ZASCA 12",
                    "url": CIVIL_URL,
                    "title": "Alpha Shipping",
                    "excerpt": "This commercial appeal is about a bill of lading.",
                    "doc_id": "d1",
                    "version_id": "v1",
                }
            ],
        }

    monkeypatch.setattr("agents.zenas.pool.adapters.za_saflii.search_and_fetch", fake)
    found = await retrieve(
        ladder,
        None,
        tenant_id=TENANT,
        home_region="za",
        box_region="za",
        jurisdiction="za",
        query="bill of lading",
        kind="case",
    )
    assert found["ok"] is True
    assert found["saflii_state"] == "ok"
    assert found["passages"][0]["citation"] == "[2023] ZASCA 12"
    assert found["passages"][0]["url"] == CIVIL_URL
    assert called["n"] == 1

    async def blocked(query, **kwargs):
        del query, kwargs
        return {
            "ok": False,
            "state": "blocked",
            "reason": "blocked: SAFLII returned a Cloudflare check (Just a moment).",
            "excerpts": [],
        }

    monkeypatch.setattr("agents.zenas.pool.adapters.za_saflii.search_and_fetch", blocked)
    stopped = await retrieve(
        ladder,
        None,
        tenant_id=TENANT,
        home_region="za",
        box_region="za",
        jurisdiction="za",
        query="bill of lading",
        kind="case",
    )
    assert stopped["ok"] is True
    assert stopped["saflii_state"] == "blocked"
    assert stopped["passages"] == []
    assert "Just a moment" in stopped["saflii_reason"]

    called["n"] = 0
    monkeypatch.setattr("agents.zenas.pool.adapters.za_saflii.search_and_fetch", fake)
    us = await retrieve(
        ladder,
        None,
        tenant_id=TENANT,
        home_region="za",
        box_region="za",
        jurisdiction="us",
        query="bill of lading",
        kind="case",
        corpus=[
            {
                "doc_id": "us1",
                "version_id": "v1",
                "citation": "8 Del. C. § 101",
                "text": "A written promise.",
                "jurisdiction": "us",
                "status": "effective",
            }
        ],
    )
    assert us["passages"][0]["citation"] == "8 Del. C. § 101"
    assert "saflii_state" not in us
    assert called["n"] == 0


def test_an_encoded_search_link_is_a_judgment_url():
    encoded = "uddg=https%3A%2F%2Fwww.saflii.org%2Fza%2Fcases%2FZASCA%2F2023%2F12.html"
    assert case_urls_in(encoded) == [CIVIL_URL]


def test_public_web_search_is_used_when_the_room_has_no_search_network(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    asyncio.run(_web_search())


async def _web_search():
    seen: list[str] = []
    page = (FIXTURES / "duckduckgo-results.html").read_bytes()

    async def http_get(url, headers):
        del headers
        seen.append(url)
        if "duckduckgo.com" in url:
            assert "site%3Asaflii.org%2Fza%2Fcases" in url or "site:saflii.org/za/cases" in url
            return page
        if "sinosrch-adw.cgi" in url:
            raise AssertionError("the cgi fallback ran after web search found a judgment")
        if url == CIVIL_URL:
            return _civil()
        return b"<html></html>"

    found = await search_and_fetch("bill of lading", http_get=http_get, live=True, now=WHEN)
    assert found["found_via"] == "web"
    assert found["state"] == "ok"
    assert found["excerpts"][0]["citation"] == "[2023] ZASCA 12"
    assert found["excerpts"][0]["url"] == CIVIL_URL
    assert any(url == public_search_url("bill of lading") for url in seen)


def test_an_empty_searx_result_falls_through_to_web_search(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    monkeypatch.setenv("SEARXNG_URL", "http://search.test")
    asyncio.run(_searx_empty_then_web())


async def _searx_empty_then_web():
    page = (FIXTURES / "duckduckgo-results.html").read_bytes()

    async def http_get(url, headers):
        del headers
        if url.startswith("http://search.test/"):
            return b'{"results":[]}'
        if "duckduckgo.com" in url:
            return page
        if url == CIVIL_URL:
            return _civil()
        return b"<html></html>"

    found = await search_and_fetch("bill of lading", http_get=http_get, live=True, now=WHEN)
    assert found["found_via"] == "web"
    assert found["excerpts"][0]["citation"] == "[2023] ZASCA 12"


def test_origin_403_is_blocked_and_not_stored(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    asyncio.run(_forbidden())


async def _forbidden():
    body = (
        b"<html><head><title>403 Forbidden</title></head><body><h1>Forbidden</h1>"
        b"<p>You don't have permission to access this resource.</p>"
        b"<address>Apache/2.4.52 (Ubuntu)</address></body></html>"
    )

    async def search(_query: str) -> list[str]:
        return [CIVIL_URL]

    async def http_get(url, headers):
        del url, headers
        return 403, body

    assert is_origin_forbidden(403, body)
    assert not is_cloudflare_block(403, body)
    store = MemoryStore(home_region="za")
    found = await search_and_fetch("bill of lading", search=search, http_get=http_get, store=store, now=WHEN)
    assert found["state"] == "blocked"
    assert "403 Forbidden" in found["reason"]
    assert "Just a moment" not in found["reason"]
    assert found["excerpts"] == []
    assert await store.get_page_cache(CIVIL_URL, now=WHEN) is None


def test_the_stock_loader_uses_the_browser(monkeypatch: pytest.MonkeyPatch):
    _quiet(monkeypatch)
    monkeypatch.setenv("SAFLII_FETCH", "browser")
    asyncio.run(_stock_browser(monkeypatch))


async def _stock_browser(monkeypatch: pytest.MonkeyPatch):
    seen: list[str] = []

    async def browser(url, headers):
        del headers
        seen.append(url)
        return 403, _cloud()

    monkeypatch.setattr(za_saflii, "_browser_get", browser)
    from agents.zenas.pool.nightly import urllib_get

    with pytest.raises(SafliiBlocked) as caught:
        await SafliiAdapter().fetch_bulk(urllib_get, resume="")
    assert seen
    assert seen[0].endswith("/recent.html")
    assert "Just a moment" in str(caught.value)
