"""Bound GPT-Researcher's existing SearXNG retriever and HTML extractor.

Search snippets are never evidence. Only successfully fetched public pages in
this request's search results can become citations. Redirects are not followed.
"""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import urlsplit

import requests
from gpt_researcher.retrievers.searx import searx
from gpt_researcher.scraper.beautiful_soup.beautiful_soup import BeautifulSoupScraper
from gpt_researcher.utils.url_security import validate_url

SEARX_URL = "http://searxng:8080/search"
USER_AGENT = "Tervory/1.0 (+https://tervory.com)"
MAX_BYTES = 2 * 1024 * 1024


def search_get(url, **kwargs):
    if url != SEARX_URL:
        raise ValueError("Search endpoint is fixed")
    response = requests.get(url, **kwargs, allow_redirects=False)
    if response.status_code != 200:
        raise requests.RequestException("Search unavailable")
    return response


# Replace only the retriever module's transport, not requests globally. Upstream
# still owns the SearXNG response parsing; a redirect cannot select another engine.
searx.requests = SimpleNamespace(get=search_get, exceptions=requests.exceptions)


def public_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.username or parts.password or parts.port not in (None, 80, 443):
        raise ValueError("Public HTTP page required")
    return validate_url(url, allow_private=False)


class Sources:
    def __init__(self):
        self.allowed: set[str] = set()
        self.pages: dict[str, dict] = {}
        self.searches: dict[str, list] = {}
        self.attempted: set[str] = set()
        self.stopped_hosts: set[str] = set()
        self.last_fetch: dict[str, float] = {}
        self.lock = threading.Lock()

    def retriever(self):
        owner = self

        class Search(searx.SearxSearch):
            def get_searxng_url(self):
                return "http://searxng:8080/"

            def search(self, max_results=5):
                with owner.lock:
                    if self.query in owner.searches:
                        return owner.searches[self.query]
                    if len(owner.searches) >= 3:
                        return []
                    owner.searches[self.query] = []
                    rows = super().search(min(max_results, 5))
                    accepted = []
                    for row in rows:
                        try:
                            public_url(row["href"])
                        except (ValueError, OSError):
                            continue
                        owner.allowed.add(row["href"])
                        accepted.append(row)
                    owner.searches[self.query] = accepted
                    return accepted

        return Search

    def _page(self, url):
        # The lock serializes this run's page fetches and per-host spacing, even
        # when upstream schedules several subqueries concurrently.
        with self.lock:
            if url in self.pages:
                return self.pages[url]
            host = urlsplit(url).hostname
            if (url not in self.allowed or url in self.attempted or
                    host in self.stopped_hosts or len(self.attempted) >= 5):
                return None
            self.attempted.add(url)
            try:
                public_url(url)
                time.sleep(max(0, self.last_fetch.get(host, 0) + 2 - time.monotonic()))
                self.last_fetch[host] = time.monotonic()
                with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15,
                                  allow_redirects=False, stream=True) as response:
                    if response.status_code in {401, 403, 429}:
                        self.stopped_hosts.add(host)
                    if response.status_code != 200:
                        return None
                    if "text/html" not in response.headers.get("Content-Type", "").lower():
                        return None
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > MAX_BYTES:
                            return None
                        chunks.append(chunk)
                    response._content = b"".join(chunks)
                    lower = response.text.lower()
                    if any(marker in lower for marker in (
                        "captcha", "cf-chl-", "verify you are human", "access denied",
                        "sign in to continue", "log in to continue", "subscribe to continue",
                        '"isaccessibleforfree":false', '"isaccessibleforfree": false',
                    )):
                        self.stopped_hosts.add(host)
                        return None

                    class Page(BeautifulSoupScraper):
                        def _fetch(self):
                            return response  # No upstream HTTP retry or alternate scraper.

                    content, _, title = Page(url).scrape()
                    if not content.strip():
                        return None
                    page = {"url": url, "title": title or host, "raw_content": content[:24000],
                            "fetched_at": datetime.now(timezone.utc).isoformat()}
                    self.pages[url] = page
                    return page
            except (requests.RequestException, ValueError, OSError):
                return None

    async def browse_urls(self, urls):
        result = []
        for url in urls:
            page = await asyncio.to_thread(self._page, url)
            if page:
                result.append(page)
        return result
