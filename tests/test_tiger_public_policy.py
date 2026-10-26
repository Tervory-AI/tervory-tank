"""Public-page policy: no robots gate, truthful identity, no retry after a block."""
import asyncio
import json
import os
from types import SimpleNamespace
import uuid

import httpx
import pytest

from test_agent1_browser import visitor  # noqa: F401 — shared browser fixture
from test_agent1_isolation import browser, runner
from test_tiger import TENANT_A, TENANT_B, _watch
from test_tiger_works import tiger
from tiger_works.fixture import no_paid_call
from watch import DomainLimiter, MemoryStore, run_check
from brain import robots


@pytest.mark.asyncio
@pytest.mark.parametrize("room", ["base", "tiger", "rig"])
async def test_every_room_reads_public_page_with_one_truthful_identity(visitor, monkeypatch, room):  # noqa: F811
    monkeypatch.setenv("ACCESS_ROOM", room)
    visitor.robots_text = "User-agent: *\nDisallow: /\n"
    visitor.gate.set()
    result = await visitor.visit("https://store.example/item")
    assert result["ok"]
    assert visitor.context_options["user_agent"] == "Tervory/1.0 (+https://tervory.com)"
    assert visitor.robots_calls == []
    assert "html" not in result and "<p>" not in runner.tool_result(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["captcha", "block", "403", "429", "401"])
async def test_block_stops_host_for_this_run_without_captcha_clicks(visitor, kind, tmp_path):  # noqa: F811
    visitor.gate.set()
    if kind == "captcha":
        visitor.html = '<div class="g-recaptcha">verify you are human</div><button>I am over 21</button>'
    elif kind == "block":
        visitor.html = '<h1>Your request has been blocked</h1>'
    else:
        visitor.status = int(kind)
    task = str(uuid.uuid4())
    run = robots.Run()
    first = await visitor.visit("https://store.example/item", task=task, run=run)
    assert first["challenge"] and first["reason"] == "blocked"
    assert first["url"] == "https://store.example/item" and "html" not in first
    assert visitor.scrolls == 1  # evidence/report extraction only; no scrolling or clicking
    visitor.html, visitor.status = "<p>Public page</p>", 200
    again = await visitor.visit("http://www.store.example/another", task=task, run=run)
    assert again["reason"] == "blocked" and again["url"] == "http://www.store.example/another"
    assert visitor.started == ["https://store.example/item"]
    assert_blocked_history(tmp_path, [first["url"], again["url"]], task)
    assert (await visitor.visit("https://other.example/item", task=task, run=run))["ok"]
    assert (await visitor.visit("https://store.example/item", task=task))["ok"]


@pytest.mark.asyncio
async def test_host_stop_isolated_by_tenant_room_and_check(visitor, monkeypatch):  # noqa: F811
    visitor.gate.set()
    task = str(uuid.uuid4())
    monkeypatch.setenv("ACCESS_ROOM", "tiger")
    visitor.status = 403
    assert (await visitor.visit("https://store.example/item", task=task, tenant_id=TENANT_A))["challenge"]
    visitor.status = 200
    assert (await visitor.visit("https://store.example/item", task=task, tenant_id=TENANT_B))["ok"]
    monkeypatch.setenv("ACCESS_ROOM", "base")
    assert (await visitor.visit("https://store.example/item", task=task, tenant_id=TENANT_A))["ok"]
    monkeypatch.setenv("ACCESS_ROOM", "tiger")
    assert (await visitor.visit("https://store.example/item", task=task, tenant_id=TENANT_A))["ok"]
    assert len(visitor.started) == 4


@pytest.mark.asyncio
async def test_redirect_block_stops_entry_and_destination_hosts(visitor):  # noqa: F811
    visitor.gate.set()
    visitor.redirect, visitor.status = "https://destination.example/item", 403
    task = str(uuid.uuid4())
    run = robots.Run()
    assert (await visitor.visit("https://entry.example/item", task=task, run=run))["challenge"]
    visitor.redirect, visitor.status = None, 200
    for url in ("https://entry.example/next", "https://destination.example/next"):
        assert (await visitor.visit(url, task=task, run=run))["reason"] == "blocked"
    assert visitor.started == ["https://entry.example/item"]


@pytest.mark.asyncio
async def test_queued_read_rechecks_host_after_first_read_is_blocked(visitor, tmp_path):  # noqa: F811
    visitor.status = 403
    task = str(uuid.uuid4())
    run = robots.Run()
    first = asyncio.create_task(visitor.visit("https://store.example/a", task=task, run=run))
    while not visitor.started:
        await asyncio.sleep(.001)
    second = asyncio.create_task(visitor.visit("https://store.example/b", task=task, run=run))
    await asyncio.sleep(.01)  # second read is waiting on the host lock
    visitor.gate.set()
    assert all(result["challenge"] for result in await asyncio.gather(first, second))
    assert visitor.started == ["https://store.example/a"]
    assert_blocked_history(tmp_path, ["https://store.example/a", "https://store.example/b"], task)


@pytest.mark.asyncio
async def test_blocked_host_subrequests_are_aborted(visitor):  # noqa: F811
    visitor.gate.set()
    visitor.status = 403
    await visitor.visit("https://store.example/item")
    request = SimpleNamespace(url="https://store.example/image.png", method="GET", is_navigation_request=lambda: False)
    actions = []
    async def abort():
        actions.append("abort")
    async def proceed():
        actions.append("continue")
    await visitor.request_handler(SimpleNamespace(request=request, abort=abort, continue_=proceed))
    assert actions == ["abort"]


@pytest.mark.asyncio
async def test_pdf_block_records_url_and_prevents_a_second_download(visitor, tmp_path):  # noqa: F811
    task = str(uuid.uuid4())
    visitor.status = 403
    run = robots.Run()
    first = await visitor.visit("https://store.example/price.pdf", task=task, run=run)
    second = await visitor.visit("https://store.example/another.pdf", task=task, run=run)
    assert first["reason"] == second["reason"] == "blocked"
    assert first["url"] == "https://store.example/price.pdf"
    assert visitor.robots_calls == ["https://store.example/price.pdf"]
    assert visitor.request_options[0]["headers"]["User-Agent"] == robots.USER_AGENT
    assert "html" not in first and "html" not in second
    assert_blocked_history(tmp_path, [first["url"], second["url"]], task)


@pytest.mark.asyncio
async def test_tiger_records_blocked_url_without_extracting_or_retrying(visitor, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ACCESS_ROOM", "tiger")
    visitor.gate.set()
    visitor.status = 403
    task = str(uuid.uuid4())
    store = MemoryStore()
    async def render(url, session, agent, tenant):
        return await browser.render(browser.Page(url=url, price_reader=True), os.environ["TANK_KEY"], tenant, "us-east", task)
    for _ in range(2):
        result = await run_check(store, TENANT_A, _watch(), "tiger", render, no_paid_call,
                                 no_paid_call, no_paid_call, DomainLimiter(0))
        assert result["status"] == result["observation"]["method"] == "blocked"
        assert result["observation"]["url"] == _watch()["url"]
        assert result["observation"]["price"] is None and result["alerts"] == []
    assert len(visitor.started) == 2  # a new check starts clean, even with the same task ID


@pytest.mark.asyncio
async def test_tiger_browser_http_403_is_a_blocked_observation(monkeypatch):
    async def answer(request):
        return httpx.Response(403)
    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        monkeypatch.setattr(tiger.app.state, "http", client, raising=False)
        result = await run_check(MemoryStore(), TENANT_A, _watch(), "tiger", tiger._render,
                                 no_paid_call, no_paid_call, no_paid_call, DomainLimiter(0))
    assert result["observation"]["method"] == "blocked"
    assert result["observation"]["url"] == _watch()["url"]


@pytest.mark.asyncio
async def test_removing_robots_gate_keeps_private_destination_validation():
    with pytest.raises(ValueError):
        await robots.require_allowed(None, "http://169.254.169.254/latest")


def assert_blocked_history(directory, urls, task):
    entries = [json.loads(line) for path in directory.rglob("history.jsonl") for line in path.read_text().splitlines()]
    assert len(entries) == len(urls)
    assert [entry["url"] for entry in entries] == urls
    assert all(entry["reason"] == "blocked" and entry["human_check"] and not entry["ok"] for entry in entries)
    assert all(entry["task_id"] == task and entry["action"] == "browser" for entry in entries)


@pytest.mark.asyncio
@pytest.mark.parametrize("task", ["", str(uuid.uuid4())], ids=["omitted-task", "reused-task"])
async def test_each_check_starts_with_empty_stopped_hosts(visitor, task, tmp_path):  # noqa: F811
    visitor.gate.set()
    visitor.status = 403
    assert (await visitor.visit("https://store.example/item", task=task))["reason"] == "blocked"
    old_request_handler = visitor.request_handler
    visitor.status = 200
    result = await visitor.visit("https://store.example/item", task=task)
    assert result["ok"] and not result["challenge"]
    assert len(visitor.started) == 2
    # Starting another check must not clear the first check's own guard.
    actions = []
    async def abort(): actions.append("abort")
    async def proceed(): actions.append("continue")
    request = SimpleNamespace(url="https://store.example/image.png", method="GET", is_navigation_request=lambda: False)
    route = SimpleNamespace(request=request, abort=abort, continue_=proceed)
    await old_request_handler(route)
    await visitor.request_handler(route)
    assert actions == ["abort", "continue"]
    entries = [json.loads(line) for path in tmp_path.rglob("history.jsonl") for line in path.read_text().splitlines()]
    assert [entry["ok"] for entry in entries] == [False, True]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 429])
@pytest.mark.parametrize("resource_type", ["script", "image", "font", "xhr", "fetch", "document"])
@pytest.mark.parametrize("host", ["store.example", "tracker.example"])
async def test_subresource_refusal_never_stops_host(visitor, status, resource_type, host):  # noqa: F811
    visitor.gate.set()
    visitor.responses = [(resource_type, status, f"https://{host}/asset")]
    run = robots.Run()
    first = await visitor.visit("https://store.example/item", run=run)
    assert first["ok"] and not first["challenge"]
    assert not run.stopped_hosts
    visitor.responses = []
    assert (await visitor.visit(f"https://{host}/next", run=run))["ok"]


@pytest.mark.asyncio
async def test_request_guard_short_circuit_is_audited(visitor, monkeypatch, tmp_path):  # noqa: F811
    async def block(context, url, timeout, run):
        robots.stop_host(run, url)
        raise robots.HostBlocked(url)
    monkeypatch.setattr(browser, 'require_allowed', block)
    task = str(uuid.uuid4())
    result = await visitor.visit('https://store.example/item', task=task)
    assert result['reason'] == 'blocked' and visitor.started == []
    assert_blocked_history(tmp_path, ['https://store.example/item'], task)


@pytest.mark.asyncio
@pytest.mark.parametrize('document_status', [200, 403, 429])
async def test_real_browser_document_and_asset_refusals(real_chromium, monkeypatch, tmp_path, document_status):
    """Real response/frame events; every network request is fulfilled offline."""
    from contextlib import asynccontextmanager
    from urllib.parse import urlsplit
    import playwright.async_api

    monkeypatch.setenv('BROWSER_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ACCESS_ROOM', 'tiger')
    monkeypatch.delenv('ACCESS_BROWSER_KEY_TIGER', raising=False)
    monkeypatch.setattr(browser, 'site_locks', {})
    monkeypatch.setattr(browser, 'last_visit', {})
    monkeypatch.setattr(browser, 'concurrency', asyncio.Semaphore(4))
    seen = []
    html = '''<!doctype html><style>
      @font-face {font-family: fixture; src: url('/font.woff2')}
      p {font-family: fixture}
      </style><p>Public price USD 120.00</p>
      <script src="/script.js"></script><img src="/image.png">
      <iframe src="https://tracker.example/frame"></iframe>'''

    class Context:
        def __init__(self, inner): self.inner = inner
        def __getattr__(self, name): return getattr(self.inner, name)
        async def route(self, pattern, guard):
            async def respond(route):
                request = route.request
                seen.append((request.url, request.resource_type, request.headers['user-agent']))
                async def proceed():
                    path = urlsplit(request.url).path
                    status = document_status if path == '/item' else (429 if path in {'/image.png', '/frame'} else 403)
                    await route.fulfill(status=status, content_type='text/html', body=html if path == '/item' else 'Refused')
                await guard(SimpleNamespace(request=request, abort=route.abort, continue_=proceed))
            await self.inner.route(pattern, respond)

    contexts = []
    class Browser:
        async def new_context(self, **options):
            # Only container transport is substituted; the real visitor sets UA
            # and installs its normal guard on every offline fixture request.
            options.pop('proxy', None)
            inner = await real_chromium.new_context(**options)
            contexts.append(inner)
            return Context(inner)
        async def close(self):
            for context in contexts: await context.close()
    async def launch(**options): return Browser()
    @asynccontextmanager
    async def manager(): yield SimpleNamespace(chromium=SimpleNamespace(launch=launch))
    monkeypatch.setattr(playwright.async_api, 'async_playwright', manager)
    run = robots.Run()
    task = str(uuid.uuid4())
    url = 'https://store.example/item'
    result = await browser.visit(browser.Page(url=url, price_reader=True, settle_ms=500),
                                 TENANT_A, task, browser.site_origin(url), run=run)
    assert seen and all(agent == robots.USER_AGENT for _, _, agent in seen)
    if document_status == 200:
        assert {'document', 'script', 'image', 'font'} <= {kind for _, kind, _ in seen}
        assert any(address == 'https://tracker.example/frame' for address, _, _ in seen)
        assert result['ok'] and not result['challenge'] and not run.stopped_hosts
        assert 'USD 120.00' in result['html']
        assert '<p>' not in runner.tool_result(result)
    else:
        assert result['reason'] == 'blocked' and result['url'] == url
        assert robots.host_stopped(run, url) and 'html' not in result
        assert_blocked_history(tmp_path, [url], task)


@pytest.mark.asyncio
async def test_stopped_connection_audit_keeps_origin_only(visitor, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(browser, 'access_configured', lambda: True)
    url, task = 'https://store.example/private/path?session=fixture', str(uuid.uuid4())
    run = robots.Run()
    robots.stop_host(run, url)
    result = await visitor.visit(url, task=task, run=run)
    assert result['reason'] == 'blocked' and result['url'] == url
    assert_blocked_history(tmp_path, ['https://store.example'], task)
    assert visitor.started == []
