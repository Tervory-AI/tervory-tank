"""Five learn tests for base.find_site 1.7.0. No network, no live Brave key, no batch.

Nothing learned: SearXNG misses, then Brave may be called once. Brave also misses: the next
call is AUTO, the cheapest funded model, and Perplexity is not called. Learned: a later lookup
of that same kind makes zero requests to the Brave search address, and the site is confirmed
by the learned phone or street. The lesson removed: Brave may be called again. A free proxy
appears in the trace only when one is configured.

The lesson for a run is ctx.learned_kinds. An empty set means nothing is learned. Clearing
the set removes the lesson. A free proxy is ctx.env["FREE_PROXY_URL"]; unset means that step
is absent. AUTO is a ctx.model call. The fake gateway answers as the cheapest funded quote.

The approved 1.7.0 package is not edited here. These tests only state the ladder.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
from graduate import Quote

ROOT = pathlib.Path(__file__).resolve().parents[1]
_PATH = ROOT / "tank/skills/base.find_site/1.7.0/run.py"
_SPEC = importlib.util.spec_from_file_location("find_site_170_learn", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
fs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fs)

BRAVE_SEARCH = "https://api.search.brave.com/res/v1/web/search"
SEARX_SEARCH = "http://search.test/search"
PROXY_URL = "http://proxy.test:9/fetch"
MISS = "https://listings.example"

# dry is cheaper and has no funds. mite is the cheapest model with funds.
# perplexity costs more and must not be the call after Brave.
QUOTES = [
    Quote("dry", 0.001, funds=False),
    Quote("mite", 0.01, funds=True),
    Quote("perplexity", 0.02, funds=True),
    Quote("luna", 0.20, funds=True),
]

# Two businesses, one kind. The page does not say the business name, so 1.7.0 can
# accept it only by this record's phone or this record's street.
TEACH = {
    "first_party:phone": {
        "name": "Cedar Wick LLC", "phone": "503-555-0148", "street": "18 Lark St",
        "host": "https://north-counter.example", "body": "Call us at 503-555-0148 today.",
    },
    "first_party:address": {
        "name": "Cedar Wick LLC", "phone": "503-555-0148", "street": "18 Lark St",
        "host": "https://south-counter.example", "body": "Our shop is at 18 Lark Street.",
    },
}
LATER = {
    "first_party:phone": {
        "name": "Maple Hinge LLC", "phone": "971-555-0162", "street": "42 Pine Ave",
        "host": "https://east-counter.example", "body": "Reach us at 971-555-0162.",
    },
    "first_party:address": {
        "name": "Maple Hinge LLC", "phone": "971-555-0162", "street": "42 Pine Ave",
        "host": "https://west-counter.example", "body": "Find us at 42 Pine Avenue.",
    },
}


def cheapest_funded(quotes: list[Quote]) -> str:
    funded = [quote for quote in quotes if quote.funds and quote.kind == "model"]
    assert funded, "the fixture needs one funded model"
    return min(funded, key=lambda quote: (quote.price, quote.name)).name


class Response:
    def __init__(self, status_code: int, text: str, url: str, payload: dict | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self.url = url
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class World:
    """One lookup. The HTTP client is fake. The model gateway is fake. Nothing leaves the process."""

    def __init__(
        self,
        searx: list[str],
        brave: list[str],
        pages: dict[str, tuple[int, str, str]],
        learned: set[str] | None = None,
        proxy: str | None = None,
    ) -> None:
        self.searx = searx
        self.brave = brave
        self.pages = pages
        self.trace: list[tuple[str, str]] = []
        self.learned_kinds = set(learned or ())
        self.quotes = list(QUOTES)
        self.env = {"SEARXNG_URL": "http://search.test", "BRAVE_API_KEY": "test-key"}
        if proxy:
            self.env["FREE_PROXY_URL"] = proxy
        self.http = self

    async def get(self, url: str, **_kwargs: object) -> Response:
        self.trace.append(("http", url))
        if url.startswith(SEARX_SEARCH):
            return Response(200, "", url, {"results": [{"url": item} for item in self.searx]})
        if url.startswith(BRAVE_SEARCH):
            return Response(200, "", url, {"web": {"results": [{"url": item} for item in self.brave]}})
        if "proxy.test" in url:
            return Response(200, "", url, {"results": []})
        page = self.pages.get(url.rstrip("/"))
        if page is None:
            return Response(404, "missing", url)
        status, text, final = page
        return Response(status, text, final)

    async def post(self, *_args: object, **_kwargs: object) -> Response:
        raise AssertionError("Tiger is not part of these tests")

    async def model(self, messages: list[dict[str, str]], task_type: str, max_tokens: int | None = None) -> str:
        del messages, max_tokens
        # Asking for Perplexity by name is that call. Otherwise AUTO answers as the cheapest funded quote.
        name = "perplexity" if "perplexity" in task_type.lower() else cheapest_funded(self.quotes)
        self.trace.append(("model", f"{name}|{task_type}"))
        return ""


def html(title: str, body: str) -> str:
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


def ok(root: str, title: str, body: str) -> tuple[int, str, str]:
    return 200, html(title, body), root


def pages_for(kind: str) -> dict[str, tuple[int, str, str]]:
    pages = {MISS: ok(MISS, "Listings", "No details listed yet.")}
    for book in (TEACH, LATER):
        spec = book[kind]
        pages[spec["host"]] = ok(spec["host"], "Counter", spec["body"])
    return pages


def payload_for(spec: dict[str, str]) -> dict[str, str]:
    return {
        "name": spec["name"], "city": "Bend", "state": "OR",
        "phone": spec["phone"], "zip": "97701", "address": spec["street"],
    }


def urls(trace: list[tuple[str, str]]) -> list[str]:
    return [item for kind, item in trace if kind == "http"]


def brave_count(trace: list[tuple[str, str]]) -> int:
    return sum(1 for url in urls(trace) if url.startswith(BRAVE_SEARCH))


def first_index(trace: list[tuple[str, str]], prefix: str) -> int | None:
    for index, (kind, item) in enumerate(trace):
        if kind == "http" and item.startswith(prefix):
            return index
    return None


def model_calls(trace: list[tuple[str, str]]) -> list[tuple[str, str]]:
    found = []
    for kind, item in trace:
        if kind == "model":
            name, task_type = item.split("|", 1)
            found.append((name, task_type))
    return found


async def lookup(
    kind: str,
    book: dict[str, dict[str, str]],
    *,
    learned: set[str] | None = None,
    proxy: str | None = None,
    searx_hit: bool,
    brave_hit: bool,
) -> tuple[dict, list[tuple[str, str]]]:
    spec = book[kind]
    world = World(
        searx=[spec["host"] + "/"] if searx_hit else [MISS + "/"],
        brave=[spec["host"] + "/"] if brave_hit else [MISS + "/from-brave"],
        pages=pages_for(kind),
        learned=learned,
        proxy=proxy,
    )
    # A brave miss still has to be a page with neither this phone nor this street.
    if not brave_hit:
        world.pages[MISS + "/from-brave"] = ok(MISS + "/from-brave", "Listings", "No details listed yet.")
    out = await fs.run(payload_for(spec), world)
    return out, world.trace


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["first_party:phone", "first_party:address"])
async def test_nothing_learned_brave_once_after_searxng(kind: str) -> None:
    out, trace = await lookup(kind, TEACH, learned=set(), proxy=None, searx_hit=False, brave_hit=True)
    searx_at = first_index(trace, SEARX_SEARCH)
    brave_at = first_index(trace, BRAVE_SEARCH)
    assert searx_at is not None, "SearXNG was not requested"
    assert brave_at is not None, "Nothing is learned and SearXNG missed. Brave may be called once"
    assert searx_at < brave_at, "Brave ran before SearXNG"
    assert brave_count(trace) == 1
    assert model_calls(trace) == []
    assert not any("proxy.test" in url for url in urls(trace))
    assert not any("perplexity" in url.lower() for url in urls(trace))
    assert out["evidence"] == kind
    assert out["website"]["value"] == TEACH[kind]["host"]
    assert out["website"]["source"] == "search:brave"


@pytest.mark.asyncio
async def test_brave_miss_next_call_is_cheapest_funded_model() -> None:
    kind = "first_party:phone"
    out, trace = await lookup(kind, TEACH, learned=set(), proxy=None, searx_hit=False, brave_hit=False)
    assert first_index(trace, SEARX_SEARCH) is not None
    assert brave_count(trace) == 1
    assert first_index(trace, SEARX_SEARCH) < first_index(trace, BRAVE_SEARCH)  # type: ignore[operator]
    guesses = [item.rstrip("/") for item in fs._guesses(TEACH[kind]["name"])]
    guessed = [url for url in urls(trace) if any(url.rstrip("/").startswith(guess) for guess in guesses)]
    calls = model_calls(trace)
    if not calls:
        pytest.fail(
            "Brave missed. The next call is AUTO, the cheapest model with funds. "
            f"No model call was made. Domain guesses fetched: {guessed or 'none'}."
        )
    assert len(calls) == 1
    name, task_type = calls[0]
    assert name == cheapest_funded(QUOTES)
    assert "perplexity" not in name.lower()
    assert "perplexity" not in task_type.lower()
    assert not any("perplexity" in url.lower() for url in urls(trace))
    assert guessed == [], "AUTO is the step after Brave. A domain guess ran first"
    assert out["website"]["source"] != "search:brave"
    assert "perplexity" not in str(out).lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["first_party:phone", "first_party:address"])
async def test_learned_kind_makes_zero_brave_calls(kind: str) -> None:
    taught, teaching = await lookup(kind, TEACH, learned=set(), proxy=None, searx_hit=False, brave_hit=True)
    assert brave_count(teaching) == 1
    assert taught["evidence"] == kind
    lesson = {taught["evidence"]}

    # The same later inputs with the lesson absent. A SearXNG page this confirmation
    # accepts is not, by itself, a learned skip: Brave may still be called.
    _, bare = await lookup(kind, LATER, learned=set(), proxy=None, searx_hit=True, brave_hit=True)
    assert brave_count(bare) >= 1, (
        "Nothing learned: SearXNG returned a page this confirmation accepts, and Brave was not called. "
        "That is the loop the skill already has. It is not a learned skip."
    )

    out, trace = await lookup(kind, LATER, learned=lesson, proxy=None, searx_hit=True, brave_hit=True)
    assert brave_count(trace) == 0, "A learned kind made a request to the Brave search address"
    assert out["evidence"] == kind
    assert out["website"]["value"] == LATER[kind]["host"]
    assert out["website"]["source"] not in {"search:brave", "search:brave+tiger"}
    assert not any("perplexity" in url.lower() for url in urls(trace))


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["first_party:phone", "first_party:address"])
async def test_removing_the_lesson_allows_brave_again(kind: str) -> None:
    taught, teaching = await lookup(kind, TEACH, learned=set(), proxy=None, searx_hit=False, brave_hit=True)
    assert brave_count(teaching) == 1
    assert taught["evidence"] == kind
    lesson = {taught["evidence"]}

    learned_out, learned_trace = await lookup(kind, LATER, learned=lesson, proxy=None, searx_hit=True, brave_hit=True)
    assert brave_count(learned_trace) == 0
    assert learned_out["evidence"] == kind

    lesson.clear()
    _, bare = await lookup(kind, LATER, learned=lesson, proxy=None, searx_hit=True, brave_hit=True)
    assert brave_count(bare) >= 1, (
        "The lesson was removed and Brave stayed at zero requests. The skip was not learning."
    )


@pytest.mark.asyncio
async def test_free_proxy_only_when_configured() -> None:
    kind = "first_party:phone"
    _, quiet = await lookup(kind, TEACH, learned=set(), proxy=None, searx_hit=False, brave_hit=True)
    assert brave_count(quiet) == 1
    assert not any("proxy.test" in url for url in urls(quiet)), "No proxy is configured, and one appeared in the trace"

    _, open_run = await lookup(kind, LATER, learned=set(), proxy=PROXY_URL, searx_hit=True, brave_hit=True)
    searx_at = first_index(open_run, SEARX_SEARCH)
    proxy_at = first_index(open_run, PROXY_URL)
    brave_at = first_index(open_run, BRAVE_SEARCH)
    assert searx_at is not None, "SearXNG was not requested"
    assert proxy_at is not None, "A free proxy is configured, and the trace has no request to it"
    assert brave_at is not None, "Nothing is learned, so Brave may be called after the proxy"
    assert searx_at < proxy_at < brave_at

    out, learned = await lookup(kind, LATER, learned={kind}, proxy=PROXY_URL, searx_hit=True, brave_hit=True)
    assert brave_count(learned) == 0, "A learned kind made a request to the Brave search address"
    assert out["evidence"] == kind
    assert out["website"]["source"] not in {"search:brave", "search:brave+tiger"}
    assert not any("perplexity" in url.lower() for url in urls(learned))
