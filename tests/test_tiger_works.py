"""Tiger's saved-page job, browser boundary and alert preferences; offline."""
import json
import os
import subprocess
import uuid
from datetime import timedelta

import httpx
import pytest

from test_agent1_browser import visitor  # noqa: F401 — shared browser fixture
from test_agent1_isolation import browser, runner
from test_tiger import ROOT, TENANT_A, TENANT_B, NOW, _load, _watch
from tiger_works.fixture import LABEL, URL, extract, no_paid_call, robots_fixture, saved_page
from watch import DomainLimiter, MemoryStore, PgStore, ensure_tables, run_check

tiger = _load("tiger_works_app", ROOT / "agents/tiger/app.py")


@pytest.mark.asyncio
@pytest.mark.parametrize("room,opt_in,html_expected", [("tiger", True, True), ("tiger", False, False), ("base", True, False), ("rig", True, False)])
async def test_markup_is_only_returned_to_tiger_price_reader(visitor, monkeypatch, room, opt_in, html_expected):  # noqa: F811
    monkeypatch.setenv("ACCESS_ROOM", room)
    async def no_age_button(*args):
        return False
    monkeypatch.setattr(browser, "confirm_age", no_age_button)
    visitor.html = saved_page()
    visitor.gate.set()
    result = await browser.render(browser.Page(url=URL, price_reader=opt_in), os.environ["TANK_KEY"],
                                  TENANT_A, "us-east", str(uuid.uuid4()))
    assert ("html" in result) is html_expected
    assert result["ok"]
    if html_expected:
        assert (await extract(result["html"], URL))["items"][0]["price"] == "120.00"
    assert "<script" not in runner.tool_result(result)
    assert '"html"' not in runner.tool_result(result)


@pytest.mark.asyncio
async def test_tiger_opt_in_does_not_return_challenge_html(visitor, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ACCESS_ROOM", "tiger")
    visitor.html = '<div class="g-recaptcha">verify you are human</div>'
    visitor.gate.set()
    result = await browser.render(browser.Page(url=URL, price_reader=True), os.environ["TANK_KEY"],
                                  TENANT_A, "us-east", str(uuid.uuid4()))
    assert result["challenge"] and "html" not in result


@pytest.mark.asyncio
async def test_agent_requests_markup_and_preserves_tenant(monkeypatch):
    async def answer(request):
        assert json.loads(request.content)["price_reader"] is True
        assert request.headers["X-Tenant-ID"] == TENANT_A
        return httpx.Response(200, json={"ok": True, "html": saved_page()})
    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        monkeypatch.setattr(tiger.app.state, "http", client, raising=False)
        assert (await tiger._render(URL, "session", "tiger", TENANT_A))["html"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["miss", "http", "timeout", "json", "shape"])
async def test_failed_or_missing_feed_reads_public_page_without_robots_gate(monkeypatch, failure):
    calls = []
    async def answer(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("unavailable", request=request)
        if failure == "http":
            return httpx.Response(503)
        if failure == "json":
            return httpx.Response(200, text="not json")
        return httpx.Response(200, json={"found": False} if failure == "miss" else [])
    async def render(*args):
        calls.append(args)
        return {"ok": True, "html": saved_page()}
    async def robots(url):
        raise AssertionError("Public reads must not fetch robots.txt")
    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        monkeypatch.setattr(tiger.app.state, "http", client, raising=False)
        result = await run_check(MemoryStore(), TENANT_A, {**_watch(), "url": URL}, "tiger", render,
                                 extract, no_paid_call, robots, DomainLimiter(0), feed=tiger.official_feed)
    assert result["status"] == "observed"
    assert len(calls) == 1
    assert result["price"] == "120.00"


@pytest.mark.asyncio
@pytest.mark.parametrize("price_on,stock_on", [(True, True), (True, False), (False, True), (False, False)])
@pytest.mark.parametrize("source", ["page", "feed", "portal"])
async def test_preferences_apply_to_saved_readings_and_changes(price_on, stock_on, source):
    store = MemoryStore()
    watch = await store.create_watch({**_watch(), "url": URL, "alert_price": price_on, "alert_stock": stock_on})
    for index, (price, stock) in enumerate([("120", "InStock"), ("115", "InStock"), ("115", "InStock"), ("115", "OutOfStock")]):
        item = {"name": LABEL, "price": price, "currency": "USD", "quantity": 1 if stock == "InStock" else 0}
        async def feed(*args):
            return {"found": source == "feed", "item": item, "receipt": {"source": "fixture"}}
        async def render(*args):
            assert source != "feed"
            return {"ok": True, "portal_item": item} if source == "portal" else {"ok": True, "html": saved_page(price, stock)}
        result = await run_check(store, TENANT_A, watch, "tiger", render, extract, no_paid_call,
                                 robots_fixture, DomainLimiter(0), feed=feed, now=lambda: NOW + timedelta(minutes=index))
        assert result["status"] == "observed"
        assert len(result["alerts"]) == (int(price_on) if index == 1 else int(stock_on) if index == 3 else 0)
    assert len(await store.list_observations(TENANT_A, URL)) == 4
    assert [row["kind"] for row in store.alerts] == (["price"] if price_on else []) + (["stock"] if stock_on else [])
    assert await store.list_observations(TENANT_B, URL) == []
    assert await store.list_alerts(TENANT_B, None) == []
    result = await run_check(store, TENANT_B, watch, "tiger", no_paid_call, no_paid_call,
                             no_paid_call, no_paid_call, DomainLimiter(0), feed=no_paid_call)
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_alert_preferences_reach_tank_and_tiger_routes(monkeypatch):
    from test_tg2_tiger_watchlist import _request, _json
    import main as tank
    store = MemoryStore()
    monkeypatch.setattr(tiger, "_store", lambda: store)
    async def call(method, path, params, content):
        saved = await tiger.create_watch(tiger.WatchIn(**json.loads(content)))
        return _json(201, saved)
    monkeypatch.setattr(tank, "_tiger_call", call)
    # Literal public IP avoids DNS during offline URL validation.
    body = {**_watch(), "url": "https://8.8.8.8/item", "alert_price": False, "alert_stock": False}
    response = await tank.tiger_create_watch(_request("POST", "/v1/tiger/watchlist", body=json.dumps(body).encode()))
    saved = json.loads(response.body)
    assert saved["alert_price"] is False and saved["alert_stock"] is False
    updated = await tiger.update_watch(uuid.UUID(saved["id"]), tiger.WatchPatch(tenant_id=TENANT_A, alert_stock=True))
    assert updated["alert_price"] is False and updated["alert_stock"] is True
    defaults = tiger._fields(tiger.WatchIn(**{**_watch(), "url": "https://8.8.8.8/item"}), partial=False)
    assert defaults["alert_price"] and defaults["alert_stock"]


@pytest.mark.asyncio
async def test_two_tenants_cannot_read_or_remove_each_others_saved_page_job(monkeypatch):
    from test_tg2_tiger_watchlist import URL_A
    import main as tank

    # Use a public literal IP so watch creation does not need network/DNS.
    url = "https://8.8.8.8/item"
    store = MemoryStore()
    monkeypatch.setattr(tiger, "_store", lambda: store)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tiger.app)) as room:
        monkeypatch.setattr(tank, "_http", room)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank",
                                     headers={"X-Tank-Key": tank.TANK_API_KEY}) as client:
            ids = {}
            for tenant, prices in ((TENANT_A, ("120", "115")), (TENANT_B, ("200", "210"))):
                created = await client.post("/v1/tiger/watchlist", json={
                    **_watch(tenant), "url": url, "label": tenant, "alert_stock": False,
                })
                assert created.status_code == 201
                watch = created.json()
                ids[tenant] = watch["id"]
                for index, price in enumerate(prices):
                    async def render(*args):
                        assert args[-1] == tenant
                        return {"ok": True, "html": saved_page(price)}
                    checked = await run_check(store, tenant, watch, "tiger", render, extract, no_paid_call,
                                              robots_fixture, DomainLimiter(0), now=lambda: NOW + timedelta(minutes=index))
                    assert checked["price"] == price + ".00"

            for tenant, other, prices in ((TENANT_A, TENANT_B, {"120.00", "115.00"}),
                                          (TENANT_B, TENANT_A, {"200.00", "210.00"})):
                for path, key, extra in (("watchlist", "watches", {}),
                                         ("observations", "observations", {"url": url}),
                                         ("alerts", "alerts", {})):
                    response = await client.get(f"/v1/tiger/{path}", params={"tenant_id": tenant, **extra})
                    assert response.status_code == 200
                    rows = response.json()[key]
                    assert rows and all(row["tenant_id"] == tenant for row in rows)
                    assert other not in response.text
                    if key == "watches":
                        assert [row["id"] for row in rows] == [ids[tenant]]
                    elif key == "observations":
                        assert {row["price"] for row in rows} == prices
                    else:
                        assert len(rows) == 1 and {rows[0]["before"], rows[0]["after"]} == prices
                denied = await client.delete(f"/v1/tiger/watchlist/{ids[other]}", params={"tenant_id": tenant})
                assert denied.status_code == 404
                mismatch = await client.post("/v1/tiger/watchlist", params={"tenant_id": tenant},
                                             json={**_watch(other), "url": URL_A})
                assert mismatch.status_code == 403
            assert len(store.watches) == 2
            assert len(store.observations) == 4 and len(store.alerts) == 2
            unauthenticated = await client.get("/v1/tiger/watchlist", params={"tenant_id": TENANT_A},
                                               headers={"X-Tank-Key": ""})
            assert unauthenticated.status_code == 401


@pytest.mark.asyncio
async def test_pg_preferences_and_additive_migration():
    statements = []
    class Connection:
        def transaction(self):
            return self
        async def fetchval(self, sql, *args):
            return "public"
        async def execute(self, sql, *args):
            statements.append(sql)
        async def fetchrow(self, sql, *args):
            if "INSERT INTO" in sql:
                assert args[-5:] == (False, True, True, True, True)
            else:
                assert "tenant_id = $1" in sql
            return {**_watch(), "alert_price": False, "alert_stock": True}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
    class Pool:
        def acquire(self):
            return Connection()
    await ensure_tables(Connection())
    assert sum(sql.count("ADD COLUMN IF NOT EXISTS alert_") for sql in statements) == 5
    saved = await PgStore(Pool()).create_watch({**_watch(), "alert_price": False, "alert_stock": True})
    assert saved["alert_price"] is False and saved["alert_stock"] is True


def test_workspace_actions_and_safe_unread_display():
    result = subprocess.run(["node", "--test", "tests/tiger_works/workspace.test.cjs"], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
async def test_real_chromium_markup_stores_history_and_one_price_alert(real_chromium, monkeypatch, tmp_path):
    monkeypatch.setenv("ACCESS_ROOM", "tiger")
    context = await real_chromium.new_context(java_script_enabled=False)
    await context.route("**/*", lambda route: route.abort())
    page = await context.new_page()
    store = MemoryStore()
    watch = await store.create_watch({**_watch(), "url": URL})
    try:
        for index, price in enumerate(["120", "115", "115"]):
            html = saved_page(price)
            await page.set_content(html)
            result = await browser.public_result(page, {"ok": True, "url": URL}, html, tmp_path,
                                                 str(uuid.uuid4()), price_reader=True)
            async def render(*args):
                return result
            checked = await run_check(store, TENANT_A, watch, "tiger", render, extract, no_paid_call,
                                      robots_fixture, DomainLimiter(0), now=lambda: NOW + timedelta(minutes=index))
            assert checked["price"] == price + ".00"
            assert "<script" not in runner.tool_result(result)
        assert len(store.observations) == 3
        assert [(a["kind"], a["before"], a["after"]) for a in store.alerts] == [("price", "120.00", "115.00")]
    finally:
        await context.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["captcha", "403", "blocked", "timeout", "error", "price_missing", "stock_missing"])
async def test_failed_page_attempts_never_create_alerts(failure):
    store = MemoryStore()
    watch = await store.create_watch({**_watch(), "url": URL})
    original = (ROOT / "tests/tiger_before_deploy/fixtures/jsonld-shop.html").read_text()
    page = {"ok": True, "html": original}

    async def render(*args):
        return page

    await run_check(store, TENANT_A, watch, "tiger", render, extract, no_paid_call,
                    robots_fixture, DomainLimiter(0), now=lambda: NOW)
    changed = original.replace("24.00", "19.00")
    page = {
        "captcha": {"challenge": True},
        "403": {"status": 403},
        "blocked": {"blocked_by_check": True},
        "timeout": {"ok": False, "error": "timeout"},
        "error": {"ok": False, "error": "load failed"},
        "price_missing": {"ok": True, "html": (ROOT / "tests/tiger_alert_page/fixtures/known/no-price.html").read_text()},
        "stock_missing": {"ok": True, "html": changed.replace("https://schema.org/InStock", "Ships today")},
    }[failure]
    result = await run_check(store, TENANT_A, watch, "tiger", render, extract, no_paid_call,
                             robots_fixture, DomainLimiter(0), now=lambda: NOW + timedelta(minutes=1))
    assert result["alerts"] == [] and store.alerts == []
    assert result["observation"]["url"] == URL
    assert result["observation"]["ts"] == (NOW + timedelta(minutes=1)).isoformat()
    if failure == "stock_missing":
        # The reader's partial price stays in its audit record, but the check
        # sends no alert and Workspace hides the incomplete reading's price.
        assert result["price"] == "19.00"
        assert result["stock"] == "can't read"
    else:
        assert result["observation"]["price"] is None
