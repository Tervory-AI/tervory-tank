"""Request expiry must stop browser work before Tiger can retry it (offline)."""
import asyncio
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
