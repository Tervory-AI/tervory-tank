"""Request expiry must stop browser work before Tiger can retry it (offline)."""
import asyncio
import sys
import types
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from test_agent1_isolation import browser

A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
URL = "https://shop.example/product"


@pytest.fixture
def scoped(monkeypatch):
    monkeypatch.setattr(browser, "scope", lambda tenant, region: tenant)
    monkeypatch.setattr(browser, "site_origin", lambda url: "https://shop.example")
    monkeypatch.setattr(browser, "access_configured", lambda: True)
    monkeypatch.setattr(browser, "access_locks", {})
    monkeypatch.setattr(browser, "active_visits", {})
    return SimpleNamespace(started=asyncio.Event(), release=asyncio.Event(), calls=[], cleaned=[])


async def render(tenant=A, budget=1000):
    body = browser.Page(url=URL, request_timeout_ms=budget)
    return await browser.render(body, "", tenant, "us-east", "")


@pytest.mark.asyncio
async def test_queued_expiry_never_visits_or_displaces_active_owner(scoped, monkeypatch):
    async def visit(body, tenant, task, origin):
        scoped.calls.append(tenant)
        scoped.started.set()
        await scoped.release.wait()
        return {"ok": True}
    monkeypatch.setattr(browser, "visit", visit)
    owner = asyncio.create_task(render(budget=5000))
    await scoped.started.wait()
    try:
        with pytest.raises(HTTPException) as error:
            await asyncio.wait_for(render(), 1.5)
        assert error.value.status_code == 503
        assert scoped.calls == [A]
        assert browser.active_visits[(A, "https://shop.example")] is owner
        assert not owner.done()
    finally:
        scoped.release.set()
        await owner
    # The expired waiter must not start later or run again ahead of a retry.
    assert await render() == {"ok": True}
    assert scoped.calls == [A, A]
    assert not browser.active_visits


@pytest.mark.asyncio
async def test_active_expiry_cleans_up_before_retry_and_preserves_other_tenant(scoped, monkeypatch):
    async def visit(body, tenant, task, origin):
        scoped.calls.append(tenant)
        if tenant == B:
            return {"ok": True, "tenant": B}
        scoped.started.set()
        try:
            await scoped.release.wait()
            return {"ok": True}
        finally:
            scoped.cleaned.append(tenant)
    monkeypatch.setattr(browser, "visit", visit)
    expired = asyncio.create_task(render())
    await scoped.started.wait()
    assert await render(B) == {"ok": True, "tenant": B}
    with pytest.raises(HTTPException) as error:
        await asyncio.wait_for(expired, 1.5)
    assert error.value.status_code == 503
    assert scoped.cleaned == [A]
    assert not browser.active_visits
    assert not browser.access_locks[(A, "https://shop.example")].locked()
    scoped.release.set()
    assert await render() == {"ok": True}
    assert scoped.calls == [A, B, A]


@pytest.mark.asyncio
async def test_caller_cancellation_propagates_without_waiting_for_budget(scoped, monkeypatch):
    async def visit(*args):
        scoped.started.set()
        try:
            await scoped.release.wait()
        finally:
            scoped.cleaned.append(A)
    monkeypatch.setattr(browser, "visit", visit)
    task = asyncio.create_task(render(budget=5000))
    await scoped.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert scoped.cleaned == [A]
    assert not browser.active_visits
    assert not browser.access_locks[(A, "https://shop.example")].locked()


@pytest.mark.asyncio
async def test_existing_callers_without_budget_keep_successful_results(scoped, monkeypatch):
    async def visit(*args):
        return {"ok": True, "html": "real response unchanged"}
    monkeypatch.setattr(browser, "visit", visit)
    assert await browser.render(browser.Page(url=URL), "", A, "us-east", "") == {
        "ok": True, "html": "real response unchanged"}


@pytest.mark.asyncio
@pytest.mark.parametrize("login", [False, True])
async def test_tiger_budget_is_forwarded_on_both_reads_before_transport_timeout(monkeypatch, login):
    import httpx
    from test_tiger_works import tiger

    requests = []

    async def answer(request):
        import json
        body = json.loads(request.content)
        assert body["request_timeout_ms"] == 45000
        assert body["request_timeout_ms"] < request.extensions["timeout"]["read"] * 1000
        assert request.extensions["timeout"]["read"] == 50
        assert request.headers["X-Tenant-ID"] == A
        requests.append(body)
        if login and len(requests) == 1:
            return httpx.Response(200, json={"ok": True, "login_status": "logged in"})
        return httpx.Response(200, json={"ok": True, "html": "unchanged"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        monkeypatch.setattr(tiger.app.state, "http", client, raising=False)
        assert (await tiger._render(URL, "", "tiger", A))["html"] == "unchanged"
    assert len(requests) == (2 if login else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["storage", "close", "exit", "entry", "launch", "read"])
async def test_actual_visit_bounds_cleanup_and_releases_admission(scoped, monkeypatch, tmp_path, phase):
    # Run the real visit/_visit, replacing only browser resources and public I/O.
    state = SimpleNamespace(storage=False, close=False, exit=False, closed=False)
    never = asyncio.Event()
    monkeypatch.setattr(browser, "CLEANUP_STEP_TIMEOUT_S", .02, raising=False)
    monkeypatch.setattr(browser, "public_url", lambda url: ("shop.example", 443))
    monkeypatch.setattr(browser, "storage_for", lambda *a, **kw: tmp_path / "cookies.json")
    monkeypatch.setenv("BROWSER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(browser, "held", {})
    monkeypatch.setattr(browser, "site_locks", {})
    monkeypatch.setattr(browser, "last_visit", {})
    monkeypatch.setattr(browser, "concurrency", asyncio.Semaphore(1))

    async def policy(*args): return {"state": "public"}
    async def allow(*args): pass
    async def no_age(*args): return False
    async def project(page, result, *args, **kwargs): return result
    monkeypatch.setattr(browser, "access_rpc", policy)
    monkeypatch.setattr(browser, "require_allowed", allow)
    monkeypatch.setattr(browser, "confirm_age", no_age)
    monkeypatch.setattr(browser, "public_result", project)

    class Page:
        url = URL
        main_frame = object()
        def on(self, *args): pass
        async def goto(self, *args, **kwargs):
            if phase == "read": await never.wait()
            return SimpleNamespace(status=200)
        async def content(self): return "<p>Public product</p>"
        async def evaluate(self, *args): pass
        async def wait_for_timeout(self, *args): pass

    class Context:
        async def route(self, *args): pass
        async def new_page(self): return Page()
        async def storage_state(self, **kwargs):
            state.storage = True
            if phase == "storage": await never.wait()

    class Browser:
        async def new_context(self, **kwargs): return Context()
        async def close(self):
            state.close = True
            if phase == "close": await never.wait()
            state.closed = True

    async def launch(**kwargs):
        if phase == "launch": await never.wait()
        return Browser()

    class Manager:
        async def __aenter__(self):
            if phase == "entry": await never.wait()
            return SimpleNamespace(chromium=SimpleNamespace(launch=launch))
        async def __aexit__(self, *args):
            state.exit = True
            if phase == "exit": await never.wait()
            state.closed = True  # driver shutdown also owns its browser children

    package = types.ModuleType("playwright")
    api = types.ModuleType("playwright.async_api")
    api.async_playwright = Manager
    monkeypatch.setitem(sys.modules, "playwright", package)
    monkeypatch.setitem(sys.modules, "playwright.async_api", api)
    if phase in {"entry", "launch", "read"}:
        with pytest.raises(HTTPException) as error:
            await asyncio.wait_for(render(), 1.5)
        assert error.value.status_code == 503
    else:
        assert (await asyncio.wait_for(render(), 1.5))["ok"]
    assert state.exit
    if phase not in {"entry", "launch"}: assert state.close
    assert state.closed
    if phase == "read": assert not state.storage
    assert not browser.active_visits
    assert not browser.access_locks[(A, "https://shop.example")].locked()
    assert not browser.site_locks["shop.example"].locked()
    assert browser.concurrency._value == 1
