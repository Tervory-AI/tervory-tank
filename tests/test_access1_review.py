"""Review regressions exercise real access routes and browser orchestration in CI.

Only the Playwright transport is replaced; vault, policy, queue, login, portal
projection and the model tool serializer run normally. No browser download.
"""
import asyncio
import importlib.util
import json
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

import access
import training
import vault
from command import Actor
import test_access1 as access_fixtures
from test_access1 import make_connection, MemoryDB
from test_agent1_isolation import browser, runner
from test_access1_feeds import MemoryStore, DomainLimiter, run_check

app = access_fixtures.app
keys = access_fixtures.keys


@pytest.fixture
def portal(app, monkeypatch, tmp_path):
    server, db, actor = app
    state = SimpleNamespace(html="<p>Public page</p>", clicks=[], urls=[], scrolls=0, fields={},
                            buttons=[], contexts=[], private_text="", room="base")
    monkeypatch.setenv("BROWSER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(browser, "held", {})
    monkeypatch.setattr(browser, "active_visits", {})
    monkeypatch.setattr(browser, "access_locks", {})
    monkeypatch.setattr(browser, "site_locks", {})
    monkeypatch.setattr(browser, "last_visit", {})
    monkeypatch.setattr(browser, "concurrency", asyncio.Semaphore(4))
    @asynccontextmanager
    async def slot(*args): yield {"retained": False}
    monkeypatch.setattr(browser, "render_slot", slot)
    async def rpc(tenant, site, action, **values):
        payload = browser.pack("request", {"tenant_id": tenant, "site": site, "action": action, **values})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://tank") as client:
            response = await client.post("/v1/access/browser/" + state.room, json=payload)
        assert response.status_code == 200
        return vault.open_envelope(state.room, "response", response.json())
    monkeypatch.setattr(browser, "access_rpc", rpc)
    class Field:
        def __init__(self, page, name): self.page, self.name, self.first = page, name, self
        async def count(self):
            return int(self.name == "#success" and self.page.context.logged_in)
        async def evaluate(self, code): return True
        async def evaluate_all(self, code):
            if self.name == "a[href]": return []
            state.fields.pop(self.name, None)
        async def fill(self, value): state.fields[self.name] = value
        async def click(self, **kwargs):
            state.clicks.append(self.name)
            assert self.name == "#submit"
            # Form submission goes only to this HTTPS origin, not a query URL.
            state.urls.append(self.page.url)
            self.page.context.logged_in = True
        async def inner_text(self): return "12.50" if self.name == "#price" else "7"
    class Button:
        def __init__(self, label, form): self.label, self.form = label, form
        async def is_visible(self): return True
        async def evaluate(self, code): return self.form
        async def click(self, **kwargs): state.clicks.append(self.label)
    class Page:
        def __init__(self, context):
            self.context = context
            async def click(*args): state.clicks.append("human")
            self.mouse = SimpleNamespace(click=click, wheel=click)
            self.keyboard = SimpleNamespace(press=click, insert_text=click)
        def on(self, *args): pass
        async def goto(self, url, **kwargs):
            self.url = url; state.urls.append(url)
            return SimpleNamespace(status=200)
        async def content(self): return state.private_text if self.context.logged_in else state.html
        async def evaluate(self, *args): state.scrolls += 1
        async def wait_for_timeout(self, *args): pass
        async def screenshot(self, **kwargs): return b"fixture"
        def locator(self, name): return Field(self, name)
        def get_by_role(self, role, name):
            buttons = [Button(label, form) for label, form in state.buttons if name.fullmatch(label)]
            async def count(): return len(buttons)
            return SimpleNamespace(count=count, nth=lambda i: buttons[i])
    class Context:
        def __init__(self, storage): self.logged_in = bool(storage and Path(storage).exists())
        async def route(self, pattern, handler): self.handler = handler
        async def new_page(self): return Page(self)
        async def storage_state(self, path):
            if self.logged_in: Path(path).write_text("{}")
    class Browser:
        async def new_context(self, **kwargs):
            context = Context(kwargs.get("storage_state")); state.contexts.append(context); return context
        async def close(self): pass
    async def launch(**kwargs): return Browser()
    @asynccontextmanager
    async def playwright(): yield SimpleNamespace(chromium=SimpleNamespace(launch=launch))
    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.async_api", SimpleNamespace(async_playwright=playwright))
    async def read(tenant, url="https://dealer.example/product", task=None):
        monkeypatch.setenv("ACCESS_ROOM", state.room)
        return await browser.visit(browser.Page(url=url), str(tenant), str(task or uuid.uuid4()), access.origin(url))
    state.read = read
    return state, db, actor


@pytest.mark.asyncio
async def test_captcha_render_reaches_tenant_queue_without_clicking(portal):
    page, db, actor = portal
    page.html = '<div class="g-recaptcha">verify you are human</div><button>I am over 21</button>'
    page.buttons = [("I am over 21", False)]
    task = uuid.uuid4()
    result = await page.read(actor.tenant_id, task=task)
    assert result["challenge"] and result["queue_id"] and not result["html"]
    assert db.queues[-1][:4] == (actor.tenant_id, "base", "https://dealer.example", "captcha")
    assert db.queues[-1][4] is not None and db.queues[-1][5] == task
    assert not page.clicks and page.scrolls == 0
    for handle in list(browser.held): await browser.dispose(handle, save=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("form,clicked", [(False, True), (True, False)])
async def test_age_confirmation_clicks_only_the_explicit_button_outside_a_form(portal, form, clicked):
    page, _, actor = portal
    page.html = '<p>Age verification: over 21</p>'
    page.buttons = [("Buy now", False), ("Accept terms", False), ("Log in", False), ("I am over 21", form)]
    result = await page.read(actor.tenant_id)
    assert result["age_confirmation"] is clicked
    assert page.clicks == (["I am over 21"] if clicked else [])


@pytest.mark.asyncio
async def test_private_login_prices_and_credentials_never_reach_another_tenant_or_model(portal, caplog):
    page, db, actor = portal
    page.room = "tiger"
    row, secrets = make_connection(actor.tenant_id, room="tiger")
    row["login_config"] = {"login_path": "/login", "username_selector": "#user", "password_selector": "#password",
        "submit_selector": "#submit", "success_selector": "#success", "totp_selector": "#otp",
        "price_selector": "#price", "quantity_selector": "#quantity"}
    db.rows[(actor.tenant_id, "tiger", row["site"])] = row
    page.private_text = " ".join(v for v in secrets.values() if v)
    task = uuid.uuid4(); messages = []
    first = await page.read(actor.tenant_id, task=task)
    messages.append(runner.tool_result(first))
    assert first["login_status"] == "logged in" and first["html"] == "" and not page.fields
    assert [r[3] for r in db.receipts] == [f"tiger:task:{task}"] * 2
    private = await page.read(actor.tenant_id, task=task)
    assert private["portal_item"]["price"] == "12.50" and private["html"] == ""
    store = MemoryStore()
    async def render(*args): return private
    async def forbidden(*args): raise AssertionError("Portal data reached a model")
    async def robots(*args): return ""
    watch = {"tenant_id": str(actor.tenant_id), "url": "https://dealer.example/product", "threshold": "0"}
    observed = await run_check(store, str(actor.tenant_id), watch, "tiger", render, forbidden, forbidden, robots, DomainLimiter(0))
    assert observed["method"] == "private_portal" and observed["price"] == "12.50"
    other = uuid.uuid4()
    assert await store.list_observations(str(other), watch["url"]) == []
    public = await page.read(other)
    assert "portal_item" not in public and "login_status" not in public
    messages.append(runner.tool_result(public))
    visible = json.dumps([page.urls, messages, db.receipts], default=str) + caplog.text
    assert all(value not in visible for value in secrets.values() if value)


@pytest.mark.asyncio
@pytest.mark.parametrize("site", ["https://Example.com", "https://example.com:443", "https://EXAMPLE.COM:443/"])
async def test_feed_price_normalizes_tigers_site(app, site):
    server, db, actor = app
    server.dependency_overrides[access.room_identity] = lambda: "tiger"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://tank") as client:
        response = await client.get("/v1/access/feeds/price", params={"tenant_id": str(actor.tenant_id), "site": site, "url": "https://Example.com:443/item"})
    assert response.status_code == 200 and response.json() == {"found": False}


@pytest.mark.asyncio
async def test_tiger_feed_client_normalized_watch_and_http_error(app, monkeypatch):
    server, db, actor = app
    server.dependency_overrides[access.room_identity] = lambda: "tiger"
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("access_review_tiger", root / "agents/tiger/app.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://tank") as client:
        monkeypatch.setattr(module.app.state, "http", client, raising=False)
        assert await module.official_feed(str(actor.tenant_id), "https://Example.com:443/product") == {"found": False}
    async def unavailable(*args, **kwargs): return httpx.Response(503)
    monkeypatch.setattr(module.app.state, "http", SimpleNamespace(get=unavailable))
    with pytest.raises(RuntimeError): await module.official_feed(str(actor.tenant_id), "https://example.com/product")


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [{"found": False}, {"error": "unavailable"}, None])
async def test_tiger_scrapes_only_an_explicit_no_feed(result):
    tenant = str(uuid.uuid4()); scraped = []
    async def feed(*args):
        if result is None: raise RuntimeError("Feed unavailable")
        return result
    async def render(*args): scraped.append(True); return {"ok": False}
    async def robots(*args): return ""
    async def forbidden(*args): raise AssertionError()
    check = run_check(MemoryStore(), tenant, {"tenant_id": tenant, "url": "https://Example.com:443/item"},
                      "tiger", render, forbidden, forbidden, robots, DomainLimiter(0), feed=feed)
    if result == {"found": False}:
        await check
        assert scraped == [True]
    else:
        with pytest.raises((RuntimeError, ValueError)): await check
        assert not scraped


@pytest.mark.asyncio
async def test_client_does_not_receive_founder_site_catalogue(app, monkeypatch):
    server, db, actor = app
    foreign = {"site": "https://other-clients-portal.example", "terms": "yes", "rotation_days": 30}
    async def fetch(sql, *args): return [foreign] if "SELECT site,terms" in sql else []
    monkeypatch.setattr(db, "fetch", fetch, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://tank") as client:
        server.dependency_overrides[access.identity] = lambda: Actor(actor.tenant_id, "client", False, frozenset({"base"}))
        response = await client.get("/v1/access/connections")
        assert response.status_code == 200 and response.json()["policies"] == [] and foreign["site"] not in response.text
        server.dependency_overrides[access.identity] = lambda: actor
        response = await client.get("/v1/access/connections")
        assert response.json()["policies"] == [foreign]


@pytest.mark.asyncio
async def test_bad_csv_is_422_without_input_echo(app):
    server, _, _ = app
    value = uuid.uuid4().hex
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://tank") as client:
        response = await client.post("/v1/access/feeds/import", json={"site": "https://dealer.example", "distributor": "rsr",
            "source": "ftp_export", "format": "csv", "contents": 'sku,price\n"' + value})
    assert response.status_code == 422 and value not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["..", "page/other", "page..other"])
async def test_facebook_identifiers_cannot_be_paths(app, value):
    server, _, actor = app
    server.dependency_overrides[access.room_identity] = lambda: "base"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://tank") as client:
        response = await client.post("/v1/access/social", json={"tenant_id": str(actor.tenant_id), "platform": "facebook", "business_id": value})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_private_portal_is_refused_before_gold_candidate_creation(monkeypatch):
    db = MemoryDB()
    async def present(*args): return True
    async def row(*args): return {"price": 12, "method": "private_portal"}
    async def forbidden(*args, **kwargs): raise AssertionError("Private observation reached gold")
    monkeypatch.setattr(db, "fetchval", present); monkeypatch.setattr(db, "fetchrow", row)
    monkeypatch.setattr(training, "runtime", lambda: SimpleNamespace(pool=lambda: db))
    monkeypatch.setattr(training, "add_candidate", forbidden)
    with pytest.raises(HTTPException) as exc:
        await training.confirm_tiger(uuid.uuid4(), training.Reviewer("founder", uuid.uuid4(), True))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_screenshots_do_not_extend_two_minute_human_permission(portal, monkeypatch):
    page, _, actor = portal
    page.html = "verify you are human"
    await page.read(actor.tenant_id)
    handle, item = next(iter(browser.held.items()))
    now = [1000.0]
    monkeypatch.setattr(browser, "time", SimpleNamespace(monotonic=lambda: now[0], time=lambda: 1000))
    async def action(name):
        payload = browser.pack("control", {"action": "live", "tenant_id": str(actor.tenant_id), "site": item.site,
            "handle": handle, "input": {"action": name, "x": 10, "y": 10}})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=browser.app), base_url="http://browser") as client:
            response = await client.post("/access/control", json=payload)
        assert response.status_code == 200
    await action("open")
    assert not item.navigation["human"]
    await action("click")
    assert item.navigation["human"] and item.navigation["human_until"] == 1120
    now[0] = 1119; await action("frame")
    assert item.navigation["human"] and item.navigation["human_until"] == 1120
    now[0] = 1120; await action("frame")
    assert not item.navigation["human"]
    # Enforce expiry at the actual browser request interceptor too.
    verdict = []
    async def abort(): verdict.append("blocked")
    async def proceed(): verdict.append("sent")
    await page.contexts[-1].handler(SimpleNamespace(request=SimpleNamespace(url=item.site + "/submit", method="POST",
        is_navigation_request=lambda: True), abort=abort, continue_=proceed))
    assert verdict == ["blocked"]
    await browser.dispose(handle, save=False)


@pytest.mark.asyncio
async def test_dismiss_closes_the_owning_browser_handle_and_status_detects_restart(portal):
    page, _, actor = portal
    page.html = "verify you are human"
    await page.read(actor.tenant_id)
    handle, item = next(iter(browser.held.items()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=browser.app), base_url="http://browser") as client:
        async def action(name, tenant):
            response = await client.post("/access/control", json=browser.pack("control", {"action": name,
                "tenant_id": str(tenant), "site": item.site, "handle": handle}))
            assert response.status_code == 200
            return browser.unpack("result", response.json())
        assert (await action("status", actor.tenant_id))["available"]
        await action("dismiss", uuid.uuid4())
        assert handle in browser.held
        await action("dismiss", actor.tenant_id)
        assert handle not in browser.held
        assert not (await action("status", actor.tenant_id))["available"]
