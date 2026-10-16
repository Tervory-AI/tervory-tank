"""SAFLII judgments: SCA, Constitutional Court, and High Court divisions.

Commercial and civil judgments are stored as published. Criminal matters are
dropped and their text is never stored. SAFLII's usage policy is recorded on
the catalogue row as information. It is not a switch.

The founder authorised a live load on 16 Oct 2026. A live fetch opens real
Chrome (Patchright or Playwright) so the Cloudflare check can finish, then
reuses that browser's cookies. The plain client still identifies as
ZenasResearch/1.0. Either way, at most one request a second goes to one host.
A Cloudflare "Just a moment" page, or a 403 from SAFLII after that check, is
reported as blocked and is not stored.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from urllib.parse import unquote, urlencode, urlparse

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
    # Public search pages hide the judgment address inside an encoded redirect.
    raw = unquote(unquote(text or ""))
    for match in _CASE_URL.finditer(raw):
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


def is_origin_forbidden(status: int, body: bytes) -> bool:
    """SAFLII's own server refused the page after the Cloudflare check."""
    if status != 403 or is_cloudflare_block(status, body):
        return False
    head = (body or b"")[:2500].lower()
    refused = b"forbidden" in head and (
        b"don't have permission" in head or b"do not have permission" in head or b"apache" in head
    )
    return refused


class SafliiBlocked(Exception):
    """The page was a Cloudflare check, or SAFLII refused it. Nothing was stored."""

    def __init__(self, url: str, *, forbidden: bool = False) -> None:
        self.url = url
        self.state = "blocked"
        self.forbidden = forbidden
        if forbidden:
            message = (
                "blocked: SAFLII's server returned 403 Forbidden for "
                f"{url} after the Cloudflare check. The page was not stored."
            )
        else:
            message = (
                "blocked: SAFLII returned a Cloudflare check (Just a moment) "
                f"for {url}. The page was not stored."
            )
        super().__init__(message)


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
        if is_cloudflare_block(status, body) or is_origin_forbidden(status, body):
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


def _browser_wanted() -> bool:
    return os.environ.get("SAFLII_FETCH", "browser").strip().lower() not in {"urllib", "plain"}


def _headed() -> bool:
    flag = os.environ.get("SAFLII_HEADED", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    return bool(os.environ.get("DISPLAY", "").strip())


def _client(http_get):
    """Use the injected client in tests. A live load uses the browser."""
    if http_get is None:
        return _live_get if _browser_wanted() else _urllib_get
    if _browser_wanted():
        from agents.zenas.pool import nightly

        if http_get is nightly.urllib_get:
            return _live_get
    return http_get


class _ChromeSession:
    """One real Chrome window. The Cloudflare click happens before any debugger attaches.

    Later fetches reuse that window's cookies. Playwright reads the page; it does
    not launch the browser, because a browser Playwright starts does not get past
    the check.
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._play = None
        self._browser = None
        self._page = None
        self._lock = asyncio.Lock()
        self._port = int(os.environ.get("SAFLII_CHROME_PORT", "9333") or "9333")

    async def get(self, url: str) -> tuple[int, bytes]:
        async with self._lock:
            if self._page is None:
                await self._open_without_a_debugger(url)
                await self._clear_check()
                await self._attach()
            else:
                response = await self._page.goto(url, wait_until="domcontentloaded", timeout=45000)
                title = (await self._page.title()).lower()
                if "just a moment" in title:
                    await self._clear_check()
                status = int(response.status) if response is not None else 0
                return _page_result(status, (await self._page.content()).encode("utf-8"), await self._page.title())
            return _page_result(0, (await self._page.content()).encode("utf-8"), await self._page.title())

    async def _open_without_a_debugger(self, url: str) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        chrome = os.environ.get("SAFLII_CHROME", "").strip() or shutil.which("google-chrome") or "/usr/local/bin/google-chrome"
        profile = os.environ.get("SAFLII_CHROME_PROFILE", "/tmp/zenas-saflii-chrome").strip() or "/tmp/zenas-saflii-chrome"
        os.makedirs(profile, exist_ok=True)
        self._proc = subprocess.Popen(
            [
                chrome,
                f"--user-data-dir={profile}",
                f"--remote-debugging-port={self._port}",
                "--no-first-run",
                "--no-default-browser-check",
                "--window-position=40,40",
                "--window-size=1100,760",
                *(["--headless=new"] if not _headed() else []),
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(5)

    async def _attach(self) -> None:
        try:
            from patchright.async_api import async_playwright
        except ImportError:
            from playwright.async_api import async_playwright
        self._play = await async_playwright().start()
        self._browser = await self._play.chromium.connect_over_cdp(f"http://127.0.0.1:{self._port}")
        context = self._browser.contexts[0]
        self._page = context.pages[0] if context.pages else await context.new_page()

    async def _clear_check(self) -> None:
        """Click the checkbox with the desktop mouse. No debugger is required."""
        for _ in range(4):
            if "just a moment" not in _window_title().lower():
                return
            aimed = _ocr_checkbox()
            if aimed is not None and shutil.which("xdotool"):
                subprocess.run(["xdotool", "mousemove", "--sync", str(aimed[0]), str(aimed[1])], check=False)
                subprocess.run(["xdotool", "click", "--delay", "80", "1"], check=False)
            await asyncio.sleep(4)


def _page_result(status: int, body: bytes, title: str) -> tuple[int, bytes]:
    lowered = title.lower()
    if "just a moment" in lowered or is_cloudflare_block(status, body):
        return 403, body
    if "forbidden" in lowered or is_origin_forbidden(403, body):
        return 403, body
    if status >= 400:
        return 200, body
    return status or 200, body


def _window_title() -> str:
    if not shutil.which("xdotool"):
        return ""
    try:
        return subprocess.check_output(["xdotool", "getactivewindow", "getwindowname"], text=True).strip()
    except subprocess.CalledProcessError:
        return ""


def _ocr_checkbox() -> tuple[int, int] | None:
    """Screen position of the Turnstile checkbox, read from the words beside it."""
    if not (shutil.which("tesseract") and shutil.which("ffmpeg") and shutil.which("xdotool")):
        return None
    display = os.environ.get("DISPLAY", "").strip()
    if not display:
        return None
    try:
        width, height = subprocess.check_output(["xdotool", "getdisplaygeometry"], text=True).split()
        path = "/tmp/zenas-saflii-screen.png"
        subprocess.check_call(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "x11grab", "-video_size", f"{width}x{height}", "-i", display,
                "-frames:v", "1", path,
            ],
            timeout=15,
        )
        raw = subprocess.check_output(
            ["tesseract", path, "stdout", "tsv"],
            stderr=subprocess.DEVNULL,
            timeout=20,
            text=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return None
    for line in raw.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        if parts[11].strip().lower() not in {"verify", "verifying..."}:
            continue
        try:
            left, top, _width, word_height = (int(parts[6]), int(parts[7]), int(parts[8]), int(parts[9]))
        except ValueError:
            continue
        return left - 18, top + word_height // 2
    return None


_CHROME = _ChromeSession()


async def _browser_get(url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    """Fetch through real Chrome. The browser keeps its own identity and cookies."""
    del headers
    return await _CHROME.get(url)


async def _live_get(url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    if not _browser_wanted():
        return await _urllib_get(url, headers)
    try:
        return await _browser_get(url, headers)
    except Exception:
        return await _urllib_get(url, headers)


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
    When that network is not configured, or it returns nothing, a public web
    search is used. The key stays in a header. It is never placed in the URL.
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
    urls, via = await _public_search(query, http_get)
    if urls:
        return urls, via
    return [], ""


def public_search_url(query: str) -> str:
    """A public site-restricted search. It does not use the Zenas search network."""
    q = f"site:saflii.org/za/cases {query}".strip()
    return "https://html.duckduckgo.com/html/?" + urlencode({"q": q})


async def _public_search(query: str, http_get) -> tuple[list[str], str]:
    """Public search stays on the plain client.

    The browser session is reserved for SAFLII. Opening a search page in it
    first attaches the debugger before the Cloudflare check, and the check
    then does not complete.
    """
    url = public_search_url(query)
    headers = {**_headers(), "Accept": "text/html"}
    client = _urllib_get if http_get is _live_get else http_get
    try:
        status, body = await _request(client, url, headers)
    except Exception:
        return [], ""
    if not _search_page_has_cases(status, body):
        return [], ""
    return case_urls_in(body.decode("utf-8", errors="replace")), "web"


def _search_page_has_cases(status: int, body: bytes) -> bool:
    if status != 200 or is_cloudflare_block(status, body) or is_origin_forbidden(status, body):
        return False
    return bool(case_urls_in(body.decode("utf-8", errors="replace")))


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


def _blocked(query: str, url: str, found_via: str = "", *, forbidden: bool = False) -> dict:
    return _result(
        ok=False,
        state="blocked",
        query=query,
        found_via=found_via,
        reason=str(SafliiBlocked(url, forbidden=forbidden)),
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
        if is_cloudflare_block(status, page) or is_origin_forbidden(status, page):
            raise SafliiBlocked(index_url, forbidden=is_origin_forbidden(status, page))
        links = judgment_links(page, code)
        while offset < len(links) and len(blobs) < batch:
            url = links[offset]
            offset += 1
            status, body = await _request(http_get, url, headers)
            if is_cloudflare_block(status, body) or is_origin_forbidden(status, body):
                raise SafliiBlocked(url, forbidden=is_origin_forbidden(status, body))
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
    (the ladder's existing search). A public web search is next, for a room
    that cannot reach that network, and SAFLII's own sinosrch-adw.cgi is last.
    A live fetch uses real Chrome unless a client was injected. Each kept page
    is cached by URL. Criminal matters are dropped.
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
        getter = _client(http_get)
        urls, via = await site_search(text, getter)
    elif http_get is None:
        return _result(
            ok=False,
            state="not_configured",
            query=text,
            reason="No search provider is configured.",
        )

    if not urls and (getter is not None or live or _search_configured()):
        getter = getter or _client(http_get)
        target = cgi_url(text)
        status, body = await _request(getter, target, _headers())
        if is_cloudflare_block(status, body) or is_origin_forbidden(status, body):
            return _blocked(text, target, via, forbidden=is_origin_forbidden(status, body))
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
    blocked_forbidden = False
    getter = getter or _client(http_get)
    for url in urls[:cap]:
        cached = await _cached(store, url, moment)
        if cached is not None:
            status, blob, from_cache = 200, cached, True
            used_cache = True
        else:
            status, blob = await _request(getter, url, _headers())
            from_cache = False
            if is_cloudflare_block(status, blob) or is_origin_forbidden(status, blob):
                blocked.append(url)
                blocked_forbidden = is_origin_forbidden(status, blob)
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
        return _blocked(text, blocked[0], "cache" if used_cache else via, forbidden=blocked_forbidden)
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
        return await _load_indexes(_client(http_get), resume)

    async def search_and_fetch(self, query: str, **kwargs) -> dict:
        return await search_and_fetch(query, **kwargs)

    def parse(self, blob: bytes, source: SourceSpec) -> list[LegalDocument]:
        return parse_judgment(blob, source)
