"""Public-page policy: no robots gate, truthful identity, no retry after a block."""
import asyncio
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
async def test_block_stops_host_for_this_run_without_captcha_clicks(visitor, kind):  # noqa: F811
    visitor.gate.set()
    if kind == "captcha":
        visitor.html = '<div class="g-recaptcha">verify you are human</div><button>I am over 21</button>'
    elif kind == "block":
        visitor.html = '<h1>Your request has been blocked</h1>'
    else:
        visitor.status = int(kind)
    task = str(uuid.uuid4())
    first = await visitor.visit("https://store.example/item", task=task)
    assert first["challenge"] and first["reason"] == "blocked"
    assert first["url"] == "https://store.example/item" and "html" not in first
    assert visitor.scrolls == 1  # evidence/report extraction only; no scrolling or clicking
    visitor.html, visitor.status = "<p>Public page</p>", 200
    again = await visitor.visit("http://www.store.example/another", task=task)
    assert again["reason"] == "blocked" and again["url"] == "http://www.store.example/another"
    assert visitor.started == ["https://store.example/item"]
    assert (await visitor.visit("https://other.example/item", task=task))["ok"]
    assert (await visitor.visit("https://store.example/item", task=str(uuid.uuid4())))["ok"]


@pytest.mark.asyncio
async def test_host_stop_isolated_by_tenant_room_and_task(visitor, monkeypatch):  # noqa: F811
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
    assert (await visitor.visit("https://store.example/item", task=task, tenant_id=TENANT_A))["challenge"]
    assert len(visitor.started) == 3


@pytest.mark.asyncio
async def test_redirect_block_stops_entry_and_destination_hosts(visitor):  # noqa: F811
    visitor.gate.set()
    visitor.redirect, visitor.status = "https://destination.example/item", 403
    task = str(uuid.uuid4())
    assert (await visitor.visit("https://entry.example/item", task=task))["challenge"]
    visitor.redirect, visitor.status = None, 200
    for url in ("https://entry.example/next", "https://destination.example/next"):
        assert (await visitor.visit(url, task=task))["reason"] == "blocked"
    assert visitor.started == ["https://entry.example/item"]


@pytest.mark.asyncio
async def test_queued_read_rechecks_host_after_first_read_is_blocked(visitor):  # noqa: F811
    visitor.status = 403
    task = str(uuid.uuid4())
    first = asyncio.create_task(visitor.visit("https://store.example/a", task=task))
    while not visitor.started:
        await asyncio.sleep(.001)
    second = asyncio.create_task(visitor.visit("https://store.example/b", task=task))
    visitor.gate.set()
    assert all(result["challenge"] for result in await asyncio.gather(first, second))
    assert visitor.started == ["https://store.example/a"]


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
async def test_pdf_block_records_url_and_prevents_a_second_download(visitor):  # noqa: F811
    task = str(uuid.uuid4())
    visitor.status = 403
    first = await visitor.visit("https://store.example/price.pdf", task=task)
    second = await visitor.visit("https://store.example/another.pdf", task=task)
    assert first["reason"] == second["reason"] == "blocked"
    assert first["url"] == "https://store.example/price.pdf"
    assert visitor.robots_calls == ["https://store.example/price.pdf"]
    assert visitor.request_options[0]["headers"]["User-Agent"] == robots.USER_AGENT
    assert "html" not in first and "html" not in second


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
    assert len(visitor.started) == 1


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
