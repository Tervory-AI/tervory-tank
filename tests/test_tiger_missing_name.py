"""Missing product data is recorded as an error, with tenant-local name retention."""
import json
from datetime import timedelta

import pytest

from test_tiger import ROOT, NOW, TENANT_A, TENANT_B, _watch
from tiger_works.fixture import extract, no_paid_call, robots_fixture
from watch import DomainLimiter, MemoryStore, run_check

FIXTURES = ROOT / 'tests/tiger_missing_name/fixtures'


async def check(store, watch, filename, tick=0):
    html = (FIXTURES / filename).read_text()
    async def render(*args):
        return {'ok': True, 'html': html}
    return await run_check(store, watch['tenant_id'], watch, 'tiger', render, extract,
                           no_paid_call, robots_fixture, DomainLimiter(0),
                           now=lambda: NOW + timedelta(minutes=tick))


@pytest.mark.asyncio
@pytest.mark.parametrize('filename,issue', [('no-name.html', 'missing_name'), ('no-currency.html', 'missing_currency')])
async def test_missing_name_or_currency_has_no_price_or_alert(filename, issue):
    store = MemoryStore()
    watch = await store.create_watch(_watch())
    result = await check(store, watch, filename)
    assert result['observation']['issue'] == issue
    assert result['price'] is None and result['observation']['price'] is None
    assert result['observation']['ts'] == NOW.isoformat()
    assert result['observation']['url'] == watch['url']
    assert store.alerts == []


@pytest.mark.asyncio
async def test_read_name_survives_missing_name_block_and_error_without_crossing_tenants():
    store = MemoryStore()
    a = await store.create_watch(_watch())
    b = await store.create_watch({**_watch(), 'tenant_id': TENANT_B})
    first = await check(store, a, 'named.html')
    assert first['observation']['product_name'] == 'Desk lamp'
    missing = await check(store, a, 'no-name.html', 1)
    assert missing['observation']['product_name'] is None
    assert missing['observation']['last_product_name'] == 'Desk lamp'
    other = await check(store, b, 'no-name.html', 1)
    assert other['observation']['last_product_name'] is None
    for i, page in enumerate([{'challenge': True}, {'ok': False, 'error': 'timeout'}], 2):
        async def render(*args): return page
        result = await run_check(store, TENANT_A, a, 'tiger', render, no_paid_call, no_paid_call,
                                 no_paid_call, DomainLimiter(0), now=lambda: NOW + timedelta(minutes=i))
        assert result['observation']['last_product_name'] == 'Desk lamp'
        assert result['alerts'] == []
    assert store.alerts == []
    recovered = await check(store, a, 'named.html', 4)
    assert recovered['observation']['product_name'] == 'Desk lamp'
    assert recovered['price'] == '24.00'


@pytest.mark.asyncio
async def test_a_real_page_heading_can_supply_a_name_but_document_title_and_label_cannot():
    store = MemoryStore()
    watch = await store.create_watch({**_watch(), 'label': 'Manual label'})
    html = (FIXTURES / 'no-name.html').read_text()
    for i, (heading, expected) in enumerate([('<title>Store website</title>', None), ('<h1>Desk lamp</h1>', 'Desk lamp')]):
        async def render(*args): return {'ok': True, 'html': html.replace('<body>', '<body>'+heading)}
        result = await run_check(store, TENANT_A, watch, 'tiger', render, extract, no_paid_call,
                                 robots_fixture, DomainLimiter(0), now=lambda: NOW + timedelta(minutes=i))
        assert result['observation']['product_name'] == expected
        assert bool(result['price']) == bool(expected)


def test_name_metadata_remains_valid_json_for_unicode_and_long_layouts():
    from watch import _reading_evidence, _reading_fields
    name = '灯' * 300
    value = _reading_evidence(json.dumps({'layout': {'dom': 'x' * 1800}}), name, name)
    assert len(value) <= 8000
    assert json.loads(value)["layout"]["dom"] == "x" * 1800
    assert _reading_fields(value)['product_name'] == name


@pytest.mark.asyncio
@pytest.mark.parametrize('name', [None, '', '   ', 'Untitled page', 'UNTITLED PAGE'])
@pytest.mark.parametrize('source', ['page', 'feed'])
async def test_missing_or_placeholder_names_never_create_a_price_or_alert(name, source):
    store = MemoryStore()
    watch = await store.create_watch(_watch())
    await check(store, watch, 'named.html')
    item = {'name': name, 'price': '1.00', 'currency': 'USD', 'quantity': 1,
            'availability': 'https://schema.org/InStock'}
    async def render(*args):
        html = '<script type="application/ld+json">' + json.dumps({
            '@type': 'Product', 'name': name, 'offers': {'@type': 'Offer', 'price': '1.00',
            'priceCurrency': 'USD', 'availability': 'https://schema.org/InStock'}}) + '</script>'
        return {'ok': True, 'html': html}
    async def feed(*args): return {'found': True, 'item': item, 'receipt': {}}
    result = await run_check(store, TENANT_A, watch, 'tiger', render, extract, no_paid_call,
                             robots_fixture, DomainLimiter(0), now=lambda: NOW + timedelta(minutes=1),
                             feed=feed if source == 'feed' else None)
    assert result['price'] is None and result['alerts'] == []
    assert result['observation']['issue'] == 'missing_name'
    assert result['observation']['last_product_name'] == 'Desk lamp'
