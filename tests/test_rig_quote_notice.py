"""Offline store notice isolation, exact receipts and prohibited fields."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from test_custom_nation_rig import store as notice_store  # noqa: F401 -- shared disposable DB fixture
from rigbox.api import LinkIn, QuoteIn
from rigbox.quotes.notice import notice
from rigbox.quotes.service import QuoteService
from rigbox.quotes.store import MemoryQuotes, PgQuotes
from rigbox.retailer import Retailer
from rigbox.service import RecordingHandoff, RigError, Service
from rigbox.store import PgStore


@pytest.mark.asyncio
async def test_notice_settings_receipts_and_tenant_isolation(notice_store):  # noqa: F811 -- pytest fixture
    store = notice_store
    a, b = str(uuid4()), str(uuid4())
    settings = Retailer(Service(store))
    original = {"text": "Offline notice <&> exactly.  ", "url": "https://shop.example.test/privacy"}
    await settings.set_settings(a, {"name": "Offline A", "email": "a@example.test", "quote_notice": original})
    await settings.set_settings(b, {"name": "Offline B", "email": "b@example.test"})
    # Legacy forms/imports omit notice fields and must preserve them.
    await settings.set_settings(a, {"name": "Offline A", "email": "a@example.test"})
    await store.put_retailer(a, "offline-a", "a@example.test", None, "Offline A")
    assert (await store.retailer(a))["quote_notice"] == original
    for invalid in (None, {}, {"text": "text", "url": "javascript:alert(1)"}):
        with pytest.raises(ValueError):
            await settings.set_settings(a, {"name": "Offline A", "email": "a@example.test", "quote_notice": invalid})
        assert (await store.retailer(a))["quote_notice"] == original
    if isinstance(store, PgStore):
        await store.apply_schema()
        store = PgStore(store.pool)
    sender = RecordingHandoff()
    quotes = PgQuotes(store.pool) if isinstance(store, PgStore) else MemoryQuotes(store)
    rig = QuoteService(store, None, sender, quotes)
    shown = await rig.privacy_notice(a)
    assert shown == notice(original)
    assert await rig.privacy_notice(b) is None
    for version in (None, "old-version"):
        with pytest.raises(RigError) as error:
            await rig.link_quote(a, "https://product.example.test/item", "", notice_version=version)
        assert error.value.status == 409
        assert await store.quotes_for(a) == []
    before = datetime.now(timezone.utc)
    ack = await rig.link_quote(a, "https://product.example.test/item", "", notice_version=shown["version"])
    rows = await store.quotes_for(a)
    evidence = rows[0]["payload"]["notice_receipt"]
    assert evidence.items() >= shown.items()
    assert before <= datetime.fromisoformat(evidence["submitted_at"]) <= datetime.now(timezone.utc)
    assert rows[0]["id"] == ack["request_id"]
    changed = {**original, "text": "Changed offline notice"}
    await Retailer(Service(store)).set_settings(a, {"name": "Offline A", "email": "a@example.test", "quote_notice": changed})
    assert (await rig.privacy_notice(a))["version"] != shown["version"]
    assert (await store.quotes_for(a))[0]["payload"]["notice_receipt"] == evidence
    with pytest.raises(RigError):
        await rig.link_quote(b, "https://product.example.test/item", "", notice_version=shown["version"])
    assert await store.quotes_for(b) == []


@pytest.mark.parametrize("field", ["card", "card_number", "bank_account", "id_number", "financial_details"])
@pytest.mark.asyncio
async def test_financial_fields_never_enter_quote_payload(notice_store, field):  # noqa: F811 -- pytest fixture
    store = notice_store
    tenant = str(uuid4())
    quotes = PgQuotes(store.pool) if isinstance(store, PgStore) else MemoryQuotes(store)
    rig = QuoteService(store, None, RecordingHandoff(), quotes)
    with pytest.raises(RigError):
        await rig.link_quote(tenant, "https://product.example.test/item", "", contact={field: "offline-rejected"})
    assert await store.quotes_for(tenant) == []
    for model in (LinkIn, QuoteIn):
        with pytest.raises(ValidationError):
            model.model_validate({field: "offline-rejected"})


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", ["neutral", "custom-nation"])
@pytest.mark.parametrize("width", [390, 1440])
async def test_shipped_notice_stale_recovery_and_real_receipts(real_chromium, monkeypatch, tmp_path, theme, width):
    import asyncio
    import socket
    from fastapi import FastAPI
    from playwright.async_api import expect
    import uvicorn
    from rigbox.api import mount
    from rigbox.quotes.hosting import mount as mount_widget
    from rigbox.quotes.sample import KEY, TENANT, seed
    from rigbox.store import MemoryStore

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{sock.getsockname()[1]}"
    monkeypatch.setenv("RIG_SAMPLE_ORIGIN", base)
    monkeypatch.setenv("RIG_WIDGET_PUBLISHABLE_KEY", KEY)
    store = MemoryStore()
    await seed(store)
    async def set_notice(text):
        await store.put_retailer(TENANT, "offline", None, None, "Offline",
                                 quote_notice={"text": text, "url": "https://shop.example.test/privacy"})
    await set_notice("Offline policy one <&>.")
    app = FastAPI()
    app.state.rig = QuoteService(store, None, RecordingHandoff(), MemoryQuotes(store))
    mount(app)
    mount_widget(app)
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        for _ in range(200):
            if server.started:
                break
            if task.done():
                await task
                pytest.fail("Offline server did not start")
            await asyncio.sleep(0.01)
        assert server.started
        page = await real_chromium.new_page(viewport={"width": width, "height": 1000})
        notice_fetches = []

        async def offline_only(route):
            if not route.request.url.startswith(base + "/"):
                return await route.abort()
            if "/v1/rig/privacy-notice" in route.request.url:
                notice_fetches.append(route.request.url)
                if len(notice_fetches) == 2:
                    # The refetch when the quote form opens, slow as on a busy CI runner.
                    await asyncio.sleep(0.5)
            await route.continue_()
        await page.route("**/*", offline_only)
        await page.goto(base + "/widget/test")
        await page.locator("tervory-rig").evaluate('(el, theme) => el.setAttribute("theme", theme)', theme)
        await page.get_by_role("searchbox").fill("Core")
        await page.get_by_role("button", name="Search", exact=True).click()
        await page.locator('[data-action="quote-product"]').first.click()
        await expect(page.locator("form.quote [data-quote-privacy]")).to_have_text("Offline policy one <&>.")
        # Opening the form refetches the notice and keeps showing the last one meanwhile, with
        # Send disabled. Wait for that fetch to finish, or a slow one can return policy two after
        # set_notice below and the first Send then succeeds (ci run 41246928486).
        await expect(page.locator('form.quote button[type="submit"]')).to_be_enabled()
        await page.locator("#quote-name").fill("Offline Shopper")
        await page.locator("#quote-email").fill("shopper@example.test")
        await set_notice("Offline policy two.")
        await page.locator('form.quote button[type="submit"]').click()
        await expect(page.locator("form.quote [data-quote-privacy]")).to_have_text("Offline policy two.")
        assert await store.quotes_for(TENANT) == []
        await page.locator('form.quote button[type="submit"]').click()
        await expect(page.locator('[data-action="close-quote"]')).to_be_visible()
        for _ in range(100):
            if await store.quotes_for(TENANT):
                break
            await asyncio.sleep(0.01)
        rows = await store.quotes_for(TENANT)
        assert len(rows) == 1
        assert rows[0]["payload"]["notice_receipt"]["text"] == "Offline policy two."
        await page.locator('[data-action="close-quote"]').click()
        await page.get_by_role("searchbox").fill("zzzzzzzzzzzzzz")
        await page.get_by_role("button", name="Search", exact=True).click()
        await expect(page.locator(".link-form [data-quote-privacy]")).to_have_text("Offline policy two.")
        for field, value in {"url": "https://product.example.test/item", "name": "Offline Shopper",
                             "email": "shopper@example.test", "phone": "+1 202-555-0123"}.items():
            await page.locator(f"#link-{field}").fill(value)
        await set_notice("Offline policy three.")
        await page.locator('.link-form button[type="submit"]').click()
        await expect(page.locator(".link-form [data-quote-privacy]")).to_have_text("Offline policy three.")
        assert len(await store.quotes_for(TENANT)) == 1
        await page.screenshot(path=str(tmp_path / f"offline-notice-{theme}-{width}.png"))
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        await page.locator('.link-form button[type="submit"]').click()
        for _ in range(100):
            if len(await store.quotes_for(TENANT)) == 2:
                break
            await asyncio.sleep(0.01)
        rows = await store.quotes_for(TENANT)
        assert len(rows) == 2
        evidence = rows[-1]["payload"]["notice_receipt"]
        assert evidence["text"] == "Offline policy three."
        assert evidence["version"] == (await app.state.rig.privacy_notice(TENANT))["version"]
        assert datetime.fromisoformat(evidence["submitted_at"]).tzinfo is not None
        await page.close()
    finally:
        server.should_exit = True
        await task
        sock.close()
