"""Job 8: isolated retailer settings and the existing embed path; no live store writes."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock
import sys

import asyncpg
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/rig'))

from rigbox.retailer import Retailer  # noqa: E402
from rigbox.service import Service  # noqa: E402
from rigbox.store import MemoryStore, PgStore  # noqa: E402
from rigbox.quotes.keys import embed_snippet  # noqa: E402
from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database  # noqa: E402
from test_rig_quotes_browser import widget_server  # noqa: E402,F401 -- existing offline browser fixture


@pytest_asyncio.fixture(params=['memory', 'postgres'])
async def store(request):
    if request.param == 'memory':
        yield MemoryStore()
        return
    admin = _admin_url()
    name = 'rig_job8_' + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            result = PgStore(pool)
            await result.apply_schema()
            await result.apply_schema()
            yield result
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_theme_is_persisted_per_store_and_used_by_its_snippet(store, monkeypatch):
    a, b = str(uuid4()), str(uuid4())
    retailer = Retailer(Service(store))
    await retailer.set_settings(a, {'name': 'Offline A', 'email': 'a@example.test', 'theme': 'custom-nation', 'tenant_id': b})
    await retailer.set_settings(b, {'name': 'Offline B', 'email': 'b@example.test'})
    for tenant, expected in [(a, 'custom-nation'), (b, 'neutral')]:
        assert (await store.retailer(tenant))['theme'] == expected
        assert (await retailer.panel(tenant))['settings']['theme'] == expected
    # Existing admin forms submit only name/email and must retain the saved skin.
    await retailer.set_settings(a, {'name': 'Offline A updated', 'email': 'updated@example.test'})
    assert (await store.retailer(a))['theme'] == 'custom-nation'
    # Legacy importer calls also preserve it.
    await store.put_retailer(a, 'offline-a', 'updated@example.test', None, 'Offline A updated')
    if isinstance(store, PgStore):
        await store.apply_schema()
        retailer = Retailer(Service(PgStore(store.pool)))  # Reload after reapplication.
    assert (await retailer.store.retailer(a))['theme'] == 'custom-nation'
    assert (await retailer.store.retailer(b))['theme'] == 'neutral'

    # Exercise the real snippet path without issuing even a test key.
    issue = AsyncMock(return_value={'publishable_key': 'offline-placeholder', 'origins': ['https://example.test']})
    monkeypatch.setattr('rigbox.quotes.keys.issue_embed_key', issue)
    monkeypatch.setattr(retailer.store, 'products', AsyncMock(return_value=[{'sku': 'offline-only'}]))
    for tenant, expected in [(a, 'custom-nation'), (b, 'neutral')]:
        result = await retailer.embed_key(tenant, {'origins': ['https://example.test'], 'theme': 'ignored', 'tenant_id': b})
        assert f'theme="{expected}"' in result['snippet']
        assert issue.call_args.args[1] == tenant
        assert 'integrity="sha384-' in result['snippet']
    assert 'theme="neutral"' in embed_snippet('offline-placeholder')


@pytest.mark.asyncio
@pytest.mark.parametrize('theme', ['unknown', '', None, {}, [], 'custom-nation" onclick="alert(1)'])
async def test_unknown_theme_is_refused_before_any_write(theme):
    store = MemoryStore()
    retailer = Retailer(Service(store))
    a, b = str(uuid4()), str(uuid4())
    for tenant in (a, b):
        await retailer.set_settings(tenant, {'name': 'Offline', 'email': 'shop@example.test'})
        before = await store.retailer(tenant)
        with pytest.raises(ValueError):
            await retailer.set_settings(tenant, {'name': 'Changed', 'email': 'changed@example.test', 'theme': theme})
        assert await store.retailer(tenant) == before
        with pytest.raises(ValueError):
            embed_snippet('offline-placeholder', theme=theme)


@pytest.mark.asyncio
async def test_invalid_stored_theme_cannot_issue_an_embed_key(monkeypatch):
    store = SimpleNamespace(retailer=AsyncMock(return_value={'email': 'shop@example.test', 'theme': 'unknown'}),
                            products=AsyncMock(return_value=[{'sku': 'offline-only'}]))
    retailer = Retailer(SimpleNamespace(store=store))
    issue = AsyncMock()
    monkeypatch.setattr('rigbox.quotes.keys.issue_embed_key', issue)
    with pytest.raises(ValueError):
        await retailer.embed_key(str(uuid4()), {'origins': ['https://example.test']})
    issue.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('theme', ['neutral', 'custom-nation'])
@pytest.mark.parametrize('width', [390, 1440])
async def test_shipped_privacy_slots_are_empty_hidden_and_have_no_link(real_chromium, widget_server, theme, width):  # noqa: F811
    from playwright.async_api import expect
    page = await real_chromium.new_page(viewport={'width': width, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(widget_server + '/') else route.abort())
    await page.goto(widget_server + '/widget/test')
    await page.locator('tervory-rig').evaluate('(el, theme) => el.setAttribute("theme", theme)', theme)
    await page.get_by_role('searchbox').fill('Core')
    await page.get_by_role('button', name='Search', exact=True).click()
    await page.locator('[data-action="quote-product"]').first.click()
    quote_slot = page.locator('form.quote [data-quote-privacy]')
    await expect(quote_slot).to_have_count(1)
    await expect(quote_slot).to_have_attribute('hidden', '')
    await expect(quote_slot).to_be_hidden()
    assert await quote_slot.inner_html() == ''
    assert await quote_slot.locator('a,input,button').count() == 0
    await page.locator('[data-action="close-quote"]').click()
    await page.get_by_role('searchbox').fill('zzzzzzzzzzzzzz')
    await page.get_by_role('button', name='Search', exact=True).click()
    link_slot = page.locator('.link-form [data-quote-privacy]')
    await expect(link_slot).to_have_count(1)
    await expect(link_slot).to_be_hidden()
    assert await link_slot.inner_html() == ''
    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert not errors
    await page.close()
