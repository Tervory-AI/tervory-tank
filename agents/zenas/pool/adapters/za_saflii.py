"""SAFLII judgments: SCA, Constitutional Court, and High Court divisions.

Commercial and civil judgments are stored as published. Criminal matters are
dropped and their text is never stored. SAFLII's usage policy is recorded on
the catalogue row as information. It is not a switch.

The founder authorised a live load on 16 Oct 2026. Fetches identify as
ZenasResearch/1.0, wait at least a second between requests to one host, and
back off when the server asks. A Cloudflare "Just a moment" page is reported
as blocked and is not stored.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse

from agents.zenas.pool.builddoc import build_document
from agents.zenas.pool.model import LegalDocument, Section, SourceSpec

# Court code, recent-decisions page, name used on the instrument.
COURTS: tuple[tuple[str, str, str], ...] = (
    ("ZASCA", "https://www.saflii.org/za/cases/ZASCA/recent.html", "Supreme Court of Appeal"),
    ("ZACC", "https://www.saflii.org/za/cases/ZACC/recent.html", "Constitutional Court"),
    ("ZAGPJHC", "https://www.saflii.org/za/cases/ZAGPJHC/recent.html", "High Court, Gauteng, Johannesburg"),
    ("ZAGPPHC", "https://www.saflii.org/za/cases/ZAGPPHC/recent.html", "High Court, Gauteng, Pretoria"),
    ("ZAWCHC", "https://www.saflii.org/za/cases/ZAWCHC/recent.html", "High Court, Western Cape"),
    ("ZAKZDHC", "https://www.saflii.org/za/cases/ZAKZDHC/recent.html", "High Court, KwaZulu-Natal, Durban"),
    ("ZAKZPHC", "https://www.saflii.org/za/cases/ZAKZPHC/recent.html", "High Court, KwaZulu-Natal, Pietermaritzburg"),
    ("ZAECGHC", "https://www.saflii.org/za/cases/ZAECGHC/recent.html", "High Court, Eastern Cape, Makhanda"),
    ("ZAECHC", "https://www.saflii.org/za/cases/ZAECHC/recent.html", "High Court, Eastern Cape"),
    ("ZAFSHC", "https://www.saflii.org/za/cases/ZAFSHC/recent.html", "High Court, Free State"),
    ("ZANWHC", "https://www.saflii.org/za/cases/ZANWHC/recent.html", "High Court, North West"),
    ("ZALMPPHC", "https://www.saflii.org/za/cases/ZALMPPHC/recent.html", "High Court, Limpopo"),
    ("ZAMPMHC", "https://www.saflii.org/za/cases/ZAMPMHC/recent.html", "High Court, Mpumalanga"),
)

_HOST = "https://www.saflii.org"
USER_AGENT = "ZenasResearch/1.0"
# A judgment does not change. A stored copy is reused for a year.
CACHE_TTL_SECONDS = 365 * 24 * 60 * 60
SEARCH_LIMIT = 5
_CGI = f"{_HOST}/cgi-bin/sinosrch-adw.cgi"
_PAGE_URL = re.compile(r"zenas-page-url:\s*(\S+)")
_CASE_URL = re.compile(
    r"(?:https?://(?:www\.)?saflii\.org)?(/za/cases/([A-Za-z0-9]+)/(\d{4})/(\d+)\.html)",
    re.I,
)
_NEUTRAL = re.compile(r"\[(\d{4})\]\s+(ZA[A-Z]{2,6})\s+(\d+)")
_REPORT = re.compile(r"\b(\d{4})\s+\((\d+)\)\s+SA\s+(\d+)\s+\(([A-Za-z]{2,6})\)")
_CRIMINAL_NAME = re.compile(r"^\s*s\s+v\s+\S", re.I)
_LONG_DATE = re.compile(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b")
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_HREF = re.compile(r"""href=["']([^"']+)["']""", re.I)


def judgment_links(page: bytes, court: str) -> list[str]:
    """Judgment HTML links for one court. PDFs are left out."""
    text = page.decode("utf-8", errors="replace")
    found: list[str] = []
    seen: set[str] = set()
    marker = f"/za/cases/{court}/"
    for match in _HREF.finditer(text):
        href = match.group(1).split("#", 1)[0].strip()
        if href.lower().endswith(".pdf"):
            continue
        if marker not in href or not href.lower().endswith(".html"):
            continue
        if href.startswith("http://") or href.startswith("https://"):
            url = href
        elif href.startswith("/"):
            url = _HOST + href
        else:
            url = f"{_HOST}/za/cases/{court}/{href}"
        if url not in seen:
            seen.add(url)
            found.append(url)
    return found


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.case_type = ""
        self._capture: str | None = None
        self._chunks: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        names = {key.lower(): (value or "") for key, value in attrs}
        if tag.lower() == "meta" and names.get("name", "").lower() == "case-type":
            self.case_type = names.get("content", "")
        if tag.lower() in {"h1", "p", "h2"}:
            self._capture = tag.lower()
            self._chunks = []
        if tag.lower() == "title":
            self._capture = "title"
            self._chunks = []

    def handle_endtag(self, tag: str) -> None:
        if self._capture and tag.lower() == self._capture:
            text = " ".join("".join(self._chunks).split())
            if self._capture == "title" and text:
                self.title = text
            elif text:
                self.parts.append(text)
            self._capture = None
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._chunks.append(data)


def is_criminal_matter(title: str, case_type: str, heading: str) -> bool:
    """Criminal matters are dropped. The word is read from the title line, not the reasons."""
    if "criminal" in case_type.lower():
        return True
    for line in (title, heading):
        cleaned = " ".join(line.split())
        if _CRIMINAL_NAME.match(cleaned):
            return True
        first = cleaned.lower()
        if first.startswith("the state v ") or "criminal appeal" in first or "criminal trial" in first:
            return True
    return False


def _court_name(code: str) -> str:
    for court, _url, name in COURTS:
        if court == code:
            return name
    return "South African court"


def _when(text: str, year_hint: str) -> date | None:
    match = _LONG_DATE.search(text)
    if not match:
        if year_hint.isdigit():
            return date(int(year_hint), 1, 1)
        return None
    month = _MONTHS.get(match.group(2).lower())
    if not month:
        return date(int(year_hint), 1, 1) if year_hint.isdigit() else None
    try:
        return date(int(match.group(3)), month, int(match.group(1)))
    except ValueError:
        return None


def parse_judgment(blob: bytes, source: SourceSpec) -> list[LegalDocument]:
    page = _Page()
    page.feed(blob.decode("utf-8", errors="replace"))
    blob_text = " ".join(page.parts)
    heading = page.parts[0] if page.parts else page.title
    if is_criminal_matter(page.title, page.case_type, heading):
        return []
    neutral = _NEUTRAL.search(page.title) or _NEUTRAL.search(blob_text)
    report = _REPORT.search(page.title) or _REPORT.search(blob_text)
    if neutral:
        citation = f"[{neutral.group(1)}] {neutral.group(2)} {neutral.group(3)}"
        court = _court_name(neutral.group(2))
        year = neutral.group(1)
    elif report:
        citation = f"{report.group(1)} ({report.group(2)}) SA {report.group(3)} ({report.group(4)})"
        court = report.group(4).upper()
        year = report.group(1)
    else:
        return []
    paragraphs = [part for part in page.parts if part and part != citation]
    if not paragraphs:
        return []
    sections = [Section("", heading, part, []) for part in paragraphs]
    decided = _when(blob_text, year)
    return [
        build_document(
            source,
            citation=citation,
            title=heading or citation,
            level="national",
            kind="case",
            body=court,
            sections=sections,
            url=page_url_of(blob, source),
            status="published",
            doc_date=decided,
            effective_from=decided,
        )
    ]


def page_url_of(blob: bytes, source: SourceSpec) -> str:
    """Judgment URL stamped on a live fetch. Snapshots keep the catalogue URL."""
    head = blob[:500].decode("utf-8", errors="replace")
    match = _PAGE_URL.search(head)
    if match:
        return match.group(1)
    return source.canonical_url


def stamp_page_url(blob: bytes, url: str) -> bytes:
    """Remember which page these bytes came from. The comment is not judgment text."""
    if blob[:80].decode("utf-8", errors="replace").find("zenas-page-url:") >= 0:
        return blob
    note = f"<!-- zenas-page-url: {canonical_case_url(url) or url} -->\n".encode("utf-8")
    return note + blob


def canonical_case_url(url: str) -> str:
    """A judgment page is /za/cases/<COURT>/<YEAR>/<N>.html. Anything else is empty."""
    raw = (url or "").strip().split("#", 1)[0].split("?", 1)[0]
    if raw.startswith("http://") or raw.startswith("https://"):
        host = urlparse(raw).netloc.lower()
        if host not in {"www.saflii.org", "saflii.org"}:
            return ""
    match = _CASE_URL.search(raw)
    if not match:
        return ""
    court = match.group(2).upper()
    year = match.group(3)
    number = str(int(match.group(4)))
    return f"{_HOST}/za/cases/{court}/{year}/{number}.html"


def case_urls_in(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _CASE_URL.finditer(text or ""):
        url = canonical_case_url(match.group(0) if match.group(0).startswith("http") else _HOST + match.group(1))
        if url and url not in seen:
            seen.add(url)
            found.append(url)
    return found


def is_cloudflare_block(status: int, body: bytes) -> bool:
    """SAFLII answers a plain client with 403 and a Cloudflare 'Just a moment' page."""
    head = (body or b"")[:8000].lower()
    moment = b"just a moment" in head
    cloudflare = b"cloudflare" in head or b"cf-mitigated" in head or b"challenge-platform" in head
    if moment and (cloudflare or status == 403):
        return True
    return status == 403 and moment


class SafliiBlocked(Exception):
    """The page was a Cloudflare check. The judgment was not stored."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.state = "blocked"
        super().__init__(
            "blocked: SAFLII returned a Cloudflare check (Just a moment) "
            f"for {url}. The page was not stored."
        )


def _headers() -> dict[str, str]:
    return {"Accept": "text/html,application/xhtml+xml", "User-Agent": USER_AGENT}


def _interval() -> float:
    raw = os.environ.get("SAFLII_MIN_INTERVAL", "1").strip()
    try:
        return max(0.0, float(raw or "1"))
    except ValueError:
        return 1.0


def _backoff() -> float:
    raw = os.environ.get("SAFLII_BACKOFF_SECONDS", "2").strip()
    try:
        return max(0.0, float(raw or "2"))
    except ValueError:
        return 2.0


def _batch() -> int:
    raw = os.environ.get("ZA_CASE_MAX_DOCS", "8").strip()
    try:
        return max(1, int(raw or "8"))
    except ValueError:
        return 8


class HostPacer:
    """At most one request a second to a single host."""

    def __init__(self) -> None:
        self._next: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, url: str) -> None:
        interval = _interval()
        if interval <= 0:
            return
        host = (urlparse(url).netloc or "www.saflii.org").lower()
        async with self._lock:
            now = time.monotonic()
            due = self._next.get(host, 0.0)
            delay = due - now
            self._next[host] = max(now, due) + interval
        if delay > 0:
            await asyncio.sleep(delay)


_PACER = HostPacer()


async def _invoke(http_get, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    try:
        result = await http_get(url, headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        return int(exc.code), raw
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code is None:
            code = getattr(exc, "status", None)
        if code is None:
            raise
        raw = b""
        read = getattr(exc, "read", None)
        if callable(read):
            try:
                raw = read()
            except Exception:
                raw = b""
        if not isinstance(raw, bytes):
            raw = str(exc).encode("utf-8", errors="replace")
        return int(code), raw
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], int):
        status, body = result
        if isinstance(body, str):
            body = body.encode("utf-8")
        return int(status), body or b""
    if isinstance(result, str):
        result = result.encode("utf-8")
    return 200, result or b""


async def _request(http_get, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    """One polite GET. A Cloudflare check is not retried. 429 and 5xx back off."""
    delay = _backoff()
    last = (0, b"")
    for attempt in range(3):
        await _PACER.wait(url)
        status, body = await _invoke(http_get, url, headers)
        if is_cloudflare_block(status, body):
            return status, body
        if status in (429, 503) or status >= 500:
            last = (status, body)
            if attempt < 2 and delay > 0:
                await asyncio.sleep(delay)
                delay *= 2
            continue
        return status, body
    return last


async def _urllib_get(url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    def _read() -> tuple[int, bytes]:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return int(response.status), response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read() if exc.fp else b""
            return int(exc.code), raw

    return await asyncio.to_thread(_read)


def _search_configured() -> bool:
    return bool(os.environ.get("SEARXNG_URL", "").strip() or os.environ.get("BRAVE_API_KEY", "").strip())


def _json_urls(body: bytes, *path: str) -> list[str]:
    try:
        payload = json.loads(body.decode("utf-8", errors="replace") or "{}")
    except json.JSONDecodeError:
        return []
    node = payload
    for key in path:
        if not isinstance(node, dict):
            return []
        node = node.get(key)
    if not isinstance(node, list):
        return []
    return [str(item.get("url") or "") for item in node if isinstance(item, dict)]


async def site_search(query: str, http_get) -> tuple[list[str], str]:
    """Site-restricted search. Tervory's own search first, then Brave when a key is set.

    This is the same pair the research ladder already uses (SearXNG, then Brave).
    The key stays in a header. It is never placed in the URL.
    """
    q = f"site:saflii.org/za/cases {query}".strip()
    base = os.environ.get("SEARXNG_URL", "").strip().rstrip("/")
    if base:
        url = f"{base}/search?{urlencode({'q': q, 'format': 'json', 'language': 'en', 'safesearch': 0})}"
        status, body = await _request(http_get, url, {**_headers(), "Accept": "application/json"})
        urls = case_urls_in("\n".join(_json_urls(body, "results"))) if status == 200 else []
        if not urls and status == 200:
            urls = case_urls_in(body.decode("utf-8", errors="replace"))
        if urls:
            return urls, "searxng"
    key = os.environ.get("BRAVE_API_KEY", "").strip()
    if key:
        url = "https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": q, "count": 8})
        if key in url:
            return [], ""
        status, body = await _request(
            http_get,
            url,
            {**_headers(), "Accept": "application/json", "X-Subscription-Token": key},
        )
        urls = case_urls_in("\n".join(_json_urls(body, "web", "results"))) if status == 200 else []
        if urls:
            return urls, "brave"
    return [], ""


def cgi_url(query: str) -> str:
    return _CGI + "?" + urlencode(
        {
            "method": "auto",
            "query": query,
            "meta": "/za/cases",
            "mask_path": "/za/cases",
            "results": "20",
            "rank": "on",
            "callback": "off",
            "view": "relevance",
        }
    )


def _saflii_source() -> SourceSpec:
    from agents.zenas.pool.catalogue import CATALOGUE

    return next(item for item in CATALOGUE if item.source_id == "saflii")


def _excerpt(document: LegalDocument, limit: int = 480) -> str:
    text = " ".join(document.text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _result(
    *,
    ok: bool,
    state: str,
    query: str,
    reason: str = "",
    found_via: str = "",
    excerpts: list[dict] | None = None,
    blocked_urls: list[str] | None = None,
) -> dict:
    return {
        "ok": ok,
        "state": state,
        "reason": reason,
        "query": query,
        "found_via": found_via,
        "excerpts": excerpts or [],
        "blocked_urls": blocked_urls or [],
    }


def _blocked(query: str, url: str, found_via: str = "") -> dict:
    return _result(
        ok=False,
        state="blocked",
        query=query,
        found_via=found_via,
        reason=(
            "blocked: SAFLII returned a Cloudflare check (Just a moment) "
            f"for {url}. The page was not stored."
        ),
        blocked_urls=[url],
    )


def _now(moment: datetime | None) -> datetime:
    if moment is None:
        return datetime.now(timezone.utc)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


async def _cached(store, url: str, now: datetime) -> bytes | None:
    if store is None or not hasattr(store, "get_page_cache"):
        return None
    from agents.zenas.pool.region import RegionError

    try:
        body = await store.get_page_cache(url, now=now)
    except RegionError:
        return None
    if not body:
        return None
    if isinstance(body, str):
        return body.encode("utf-8")
    return body


async def _remember(store, url: str, blob: bytes, now: datetime) -> None:
    if store is None or not hasattr(store, "put_page_cache"):
        return
    from agents.zenas.pool.region import RegionError

    try:
        await store.put_page_cache(
            url,
            blob.decode("utf-8", errors="replace"),
            ttl_seconds=CACHE_TTL_SECONDS,
            fetched_at=now,
        )
    except RegionError:
        return


async def _keep(store, blob: bytes, now: datetime) -> None:
    if store is None:
        return
    from agents.zenas.pool.ingest import ingest_snapshot
    from agents.zenas.pool.region import RegionError

    try:
        await ingest_snapshot(store, _saflii_source(), [blob], on=now.date(), region="za")
    except RegionError:
        return


def _parse_resume(resume: str) -> tuple[int, int]:
    if not resume or resume == "done":
        return 0, 0
    court, _, offset = resume.partition(":")
    try:
        return max(0, int(court)), max(0, int(offset or "0"))
    except ValueError:
        return 0, 0


async def _load_indexes(http_get, resume: str) -> tuple[list[bytes], str]:
    if resume == "done":
        return [], "done"
    court_i, offset = _parse_resume(resume)
    headers = _headers()
    blobs: list[bytes] = []
    batch = _batch()
    while court_i < len(COURTS) and len(blobs) < batch:
        code, index_url, _name = COURTS[court_i]
        status, page = await _request(http_get, index_url, headers)
        if is_cloudflare_block(status, page):
            raise SafliiBlocked(index_url)
        links = judgment_links(page, code)
        while offset < len(links) and len(blobs) < batch:
            url = links[offset]
            offset += 1
            status, body = await _request(http_get, url, headers)
            if is_cloudflare_block(status, body):
                raise SafliiBlocked(url)
            blobs.append(stamp_page_url(body, url))
        if offset >= len(links):
            court_i += 1
            offset = 0
    if court_i >= len(COURTS):
        return blobs, "done"
    return blobs, f"{court_i}:{offset}"


async def search_and_fetch(
    query: str,
    *,
    http_get=None,
    search=None,
    store=None,
    limit: int = SEARCH_LIMIT,
    live: bool = False,
    now: datetime | None = None,
) -> dict:
    """Find SAFLII judgment pages, fetch the top ones, and return excerpts.

    Candidate URLs come from the injected search, or from SearXNG then Brave
    (the ladder's existing search), with SAFLII's own sinosrch-adw.cgi as the
    fallback. Each kept page is cached by URL. Criminal matters are dropped.
    """
    text = " ".join((query or "").split())
    moment = _now(now)
    if not text:
        return _result(ok=False, state="empty", query="", reason="No query.")
    cap = max(1, min(int(limit or SEARCH_LIMIT), 10))
    getter = http_get
    urls: list[str] = []
    via = ""
    if search is not None:
        found = await search(text)
        urls = case_urls_in("\n".join(str(item) for item in (found or [])))
        via = "search" if urls else ""
    elif live or _search_configured():
        getter = http_get or _urllib_get
        urls, via = await site_search(text, getter)
    elif http_get is None:
        return _result(
            ok=False,
            state="not_configured",
            query=text,
            reason="No search provider is configured.",
        )

    if not urls and (getter is not None or live or _search_configured()):
        getter = getter or http_get or _urllib_get
        target = cgi_url(text)
        status, body = await _request(getter, target, _headers())
        if is_cloudflare_block(status, body):
            return _blocked(text, target, via)
        urls = case_urls_in(body.decode("utf-8", errors="replace"))
        if urls:
            via = "saflii-cgi"
    if not urls:
        return _result(
            ok=True,
            state="empty",
            query=text,
            found_via=via,
            reason="No SAFLII judgment pages matched.",
        )

    source = _saflii_source()
    excerpts: list[dict] = []
    blocked: list[str] = []
    used_cache = False
    getter = getter or http_get or _urllib_get
    for url in urls[:cap]:
        cached = await _cached(store, url, moment)
        if cached is not None:
            status, blob, from_cache = 200, cached, True
            used_cache = True
        else:
            status, blob = await _request(getter, url, _headers())
            from_cache = False
            if is_cloudflare_block(status, blob):
                blocked.append(url)
                break
        stamped = stamp_page_url(blob, url)
        documents = parse_judgment(stamped, source)
        if not documents:
            continue
        if not from_cache:
            await _remember(store, url, blob, moment)
        await _keep(store, stamped, moment)
        for document in documents:
            excerpts.append(
                {
                    "citation": document.citation,
                    "url": document.url,
                    "title": document.title,
                    "court": document.body,
                    "excerpt": _excerpt(document),
                    "doc_id": document.id,
                    "version_id": document.version_id,
                }
            )
    if blocked and not excerpts:
        return _blocked(text, blocked[0], "cache" if used_cache else via)
    if not excerpts:
        return _result(
            ok=True,
            state="empty",
            query=text,
            found_via="cache" if used_cache else via,
            reason="No civil judgment was stored.",
            blocked_urls=blocked,
        )
    return _result(
        ok=True,
        state="ok",
        query=text,
        found_via="cache" if used_cache and not blocked else via,
        excerpts=excerpts,
        blocked_urls=blocked,
    )


def _unstamp(blob: bytes) -> bytes:
    if blob.startswith(b"<!-- zenas-page-url:"):
        _line, _sep, rest = blob.partition(b"\n")
        return rest
    return blob


class SafliiAdapter:
    source_id = "saflii"

    async def remember_pages(self, store, blobs: list[bytes]) -> None:
        """Keep each civil judgment HTML, keyed by its URL, for the long cache lifetime."""
        moment = datetime.now(timezone.utc)
        source = _saflii_source()
        for blob in blobs:
            url = page_url_of(blob, source)
            if not canonical_case_url(url):
                continue
            if not parse_judgment(blob, source):
                continue
            await _remember(store, url, _unstamp(blob), moment)

    async def fetch(self, http_get) -> list[bytes]:
        blobs, _cursor = await self.fetch_bulk(http_get, resume="")
        return blobs

    async def fetch_bulk(self, http_get, *, resume: str = "") -> tuple[list[bytes], str]:
        return await _load_indexes(http_get, resume)

    async def search_and_fetch(self, query: str, **kwargs) -> dict:
        return await search_and_fetch(query, **kwargs)

    def parse(self, blob: bytes, source: SourceSpec) -> list[LegalDocument]:
        return parse_judgment(blob, source)
