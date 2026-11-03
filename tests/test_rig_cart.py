"""Offline store-owned checkout: protocol fakes, no stores/cards/network/models."""
import asyncio
import base64
import hmac
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/rig'))
sys.path.insert(0, str(ROOT / 'agents/_chassis'))
from rigbox.cart import Cart
from rigbox.commerce import CommerceError, Platform, signature
from rigbox.locate import SupplyStore
from rigbox.locate_live import LiveResult
from rigbox.store import MemoryStore
from rigbox.service import Service

TENANT = '20000000-0000-0000-0000-000000000001'
OTHER = '20000000-0000-0000-0000-000000000002'
NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
SESSION = 's' * 43
HOOK = 'offline-webhook-fixture'
CREDS = {'consumer_key': 'offline', 'consumer_secret': 'offline',
          'access_token': 'offline', 'webhook_secret': HOOK}


class Woo:
    """v3 -> v2 prepare_line_items: require reference, then apply overrides.

    This models documented REST behaviour only; real tax/payment collection
    remains founder acceptance. Deliberately refuses unreferenced custom lines.
    """
    def __init__(self):
        self.products = {1: {'id': 1, 'sku': 'stock', 'price': '10.00', 'stock_status': 'instock', 'stock_quantity': 5}}
        self.orders, self.calls, self.created_carriers = {}, [], 0
        self.lose_create = False

    def __call__(self, request):
        data = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, data))
        route = request.url.path.removeprefix('/wp-json/wc/v3')
        if route == '/products' and request.method == 'GET':
            return httpx.Response(200, json=[p for p in self.products.values() if p['sku'] == request.url.params['sku']])
        if route == '/products' and request.method == 'POST':
            assert data['sku'] == 'tervory-rig-line' and data['manage_stock'] is False
            assert data['status'] == 'private' and data['catalog_visibility'] == 'hidden'
            assert data['virtual'] is False and data['tax_status'] == 'taxable'
            assert data['regular_price'] == '0'
            self.created_carriers += 1
            self.products[2] = {'id': 2, **data}
            return httpx.Response(201, json=self.products[2])
        if route.startswith('/products/'):
            return httpx.Response(200, json=self.products[int(route.split('/')[-1])])
        if route == '/orders' and request.method == 'POST':
            assert data['status'] == 'pending' and 'fee_lines' not in data
            assert 'set_paid' not in data
            for item in data['line_items']:
                if 'product_id' not in item and 'sku' not in item:
                    return httpx.Response(400, json={'code': 'woocommerce_rest_required_product_reference'})
                if 'sku' in item:
                    assert item['sku'] == 'tervory-rig-line'
                    assert all(meta['key'].startswith('_') for meta in item['meta_data'])
                assert Decimal(item['total']) == Decimal(item['subtotal'])
            order_id = len(self.orders) + 1
            order = {'id': order_id, **data, 'date_paid': None,
                     'total': str(sum(Decimal(line['total']) for line in data['line_items'])),
                     'payment_url': f'https://store.example/checkout/order-pay/{order_id}/'}
            self.orders[str(order_id)] = order
            if self.lose_create:
                raise httpx.ReadTimeout('offline lost response')
            return httpx.Response(201, json=order)
        if route.startswith('/orders/'):
            order = self.orders[route.split('/')[-1]]
            if request.method == 'PUT':
                order.update(data)
            return httpx.Response(200, json=order)
        raise AssertionError((request.method, route))


class Live:
    async def check(self, tenant, source, offer):
        return LiveResult('available', Decimal('20'), 'USD', NOW, method='fake')


async def setup(monkeypatch):
    monkeypatch.setenv('RIG_LOCATE_HOLD_SECRET', 'offline-price-hold-fixture-' * 2)
    store, fake = MemoryStore(), Woo()
    await store.put_retailer(TENANT, 'invented-us-store', None, None, locate_enabled=True)
    for sku, title, price, out in [('stock', 'Stock item', '10', False), ('located', 'Located item', '30', True),
                                   ('back', 'Back order item', '40', True)]:
        await store.upsert_product(TENANT, {'sku': sku, 'name': title, 'price': price, 'currency': 'USD',
            'active': True, 'brand': 'Invented', 'category': 'Parts', 'image_url': '',
            'attributes': {'stock': {'status': 'out_of_stock' if out else 'in_stock'}}})
    await store.save_rule(TENANT, {'freight': '0', 'duty_percent': '0', 'margin_percent': '0'})
    supply = SupplyStore(store)
    await supply.source(TENANT, {'id': 'private-source', 'site': 'https://private-supplier.example',
        'provider': 'api', 'approved': True, 'priority': 1, 'max_offer_age_seconds': 3600,
        'vendor_name': 'Private Supplier', 'order_email': 'private@private-supplier.example'})
    store.supply_state[TENANT]['offers'] = [{'tenant_id': TENANT, 'source_id': 'private-source', 'sku': 'private-part',
        'gtin': None, 'brand': '', 'mpn': '', 'quantity': '5', 'status': 'available', 'eta': '2026-11-12',
        'ship_days': 9, 'region': 'US', 'cost': '20', 'currency': 'USD', 'seen_at': NOW,
        'url': 'https://private-supplier.example/part'}]
    store.supply_state[TENANT]['maps'] = [{'tenant_id': TENANT, 'source_id': 'private-source',
                                          'product_sku': 'located', 'offer_sku': 'private-part'}]
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake))
    config = {'mode': 'cart', 'region': 'US', 'delivery': {'ship_days': 2}, 'platform': 'woocommerce',
              'site': 'https://store.example', 'vault_name': 'store-platform', 'products': {'stock': {'product_id': 1}}}
    service = Service(store)
    service.locate_checker = Live()
    calls = []

    async def confirmed(tenant, payload):
        # Contract fake for the parallel branch's shared idempotent step.
        if payload['reference'] not in {call[1]['reference'] for call in calls}:
            calls.append((tenant, payload))
    service.store_confirms_payment = confirmed
    async def platforms(tenant, config):
        return Platform(client, config, CREDS)
    clock = [NOW]
    cart = Cart(service, platforms, clock=lambda: clock[0])
    await cart.connect(TENANT, config)
    return cart, fake, config, calls, clock, client


def signed(raw, platform='woocommerce', now=NOW):
    if platform == 'bigcommerce':
        stamp = str(int(now.timestamp()))
        message = b'event-id.' + stamp.encode() + b'.' + raw
        return {'webhook-id': 'event-id', 'webhook-timestamp': stamp,
                'webhook-signature': 'v1,' + base64.b64encode(hmac.digest(HOOK.encode(), message, 'sha256')).decode()}
    name = 'x-wc-webhook-signature' if platform == 'woocommerce' else 'x-shopify-hmac-sha256'
    return {name: base64.b64encode(hmac.digest(HOOK.encode(), raw, 'sha256')).decode()}


@pytest.mark.asyncio
async def test_carrier_mixed_order_privacy_and_posted_prices(monkeypatch):
    cart, fake, config, _, _, client = await setup(monkeypatch)
    try:
        await cart.connect(TENANT, config)
        assert fake.created_carriers == 1
        for sku in ('stock', 'located', 'back'):
            result = await cart.add(TENANT, SESSION, sku, 2, back_order=sku == 'back')
        assert [line['delivery'] for line in result['lines']] == [
            {'ship_days': 2}, {'ship_days': 9, 'eta': '2026-11-12'}, {'status': 'back_order'}]
        checkout = await cart.checkout(TENANT, SESSION)
        assert checkout['state'] == 'pending' and checkout['checkout_url'].startswith('https://store.example/')
        order = fake.orders['1']
        assert [line['total'] for line in order['line_items']] == ['20.00', '40.00', '80.00']
        assert order['line_items'][0]['product_id'] == 1
        assert [line['name'] for line in order['line_items'][1:]] == ['Located item', 'Back order item']
        assert order['total'] == '140.00'  # No real-store tax or collection claim.
        exposed = json.dumps([result, checkout, order, fake.calls])
        for private in ('Private Supplier', 'private-supplier.example', 'private-source', 'private-part', 'unit_cost'):
            assert private not in exposed
        assert all(meta['key'].startswith('_') for line in order['line_items'] for meta in line['meta_data'])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_checkout_recheck_and_lost_create_never_duplicate(monkeypatch):
    cart, fake, _, _, _, client = await setup(monkeypatch)
    try:
        await cart.add(TENANT, SESSION, 'stock', 1)
        fake.products[1]['price'] = '11.00'
        with pytest.raises(CommerceError, match='recheck_changed'):
            await cart.checkout(TENANT, SESSION)
        assert not fake.orders
        fake.products[1]['price'] = '10.00'
        fake.lose_create = True
        first, second = await asyncio.gather(cart.checkout(TENANT, SESSION), cart.checkout(TENANT, SESSION))
        assert first['id'] == second['id'] and len(fake.orders) == 1
        assert first['state'] == second['state'] == 'create_unknown'
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_expiry_release_and_late_signed_payment_honoured_once(monkeypatch):
    cart, fake, _, calls, clock, client = await setup(monkeypatch)
    try:
        await cart.add(TENANT, SESSION, 'located', 1)
        result = await cart.checkout(TENANT, SESSION)
        clock[0] += timedelta(seconds=299)
        await cart.sweep(TENANT)
        assert fake.orders['1']['status'] == 'pending'
        clock[0] += timedelta(seconds=1)
        await cart.sweep(TENANT)
        assert fake.orders['1']['status'] == 'cancelled'
        row = await cart.rows.get(TENANT, result['id'])
        assert row['state'] == 'expired'
        held = cart.store.supply_state[TENANT]['holds'][row['lines'][0]['hold_id']]
        assert held['used_at'] == clock[0]
        fake.orders['1'].update(status='processing', date_paid=clock[0].isoformat())
        raw = b'{"id":1}'
        with pytest.raises(CommerceError, match='signature'):
            await cart.webhook(TENANT, raw, {'x-wc-webhook-signature': 'invalid'})
        await cart.webhook(TENANT, raw, signed(raw))
        await cart.webhook(TENANT, raw, signed(raw))
        raw2 = b'{"id":1,"changed":true}'
        await cart.webhook(TENANT, raw2, signed(raw2))
        assert len(calls) == 1 and calls[0][1]['kind'] == 'locate'
        assert (await cart.order(TENANT, SESSION, result['id']))['late_payment'] is True
        with pytest.raises(CommerceError, match='not_found'):
            await cart.order(TENANT, 'other-session-' * 4, result['id'])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_quote_default_tenant_isolation_and_total_verification(monkeypatch):
    cart, fake, _, calls, _, client = await setup(monkeypatch)
    try:
        assert await cart.store.commerce_config(OTHER) == {'mode': 'quote'}
        with pytest.raises(CommerceError, match='cart_disabled'):
            await cart.add(OTHER, SESSION, 'stock', 1)
        await cart.add(TENANT, SESSION, 'stock', 1)
        await cart.checkout(TENANT, SESSION)
        fake.orders['1'].update(status='processing', date_paid=NOW.isoformat(), total='1.00')
        raw = b'{"id":1}'
        with pytest.raises(CommerceError, match='order_mismatch'):
            await cart.webhook(TENANT, raw, signed(raw))
        assert calls == []
    finally:
        await client.aclose()


@pytest.mark.parametrize('platform', ['shopify', 'woocommerce', 'bigcommerce'])
def test_official_raw_body_signatures_and_timestamp(platform):
    raw = b'{"id":19}'
    headers = signed(raw, platform)
    signature(platform, raw, headers, HOOK, now=NOW.timestamp())
    with pytest.raises(CommerceError, match='signature'):
        signature(platform, raw + b' ', headers, HOOK, now=NOW.timestamp())
    if platform == 'bigcommerce':
        with pytest.raises(CommerceError, match='signature'):
            signature(platform, raw, headers, HOOK, now=NOW.timestamp() + 301)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['shopify', 'bigcommerce'])
async def test_shopify_and_bigcommerce_create_native_and_custom_lines(kind):
    seen = []
    def handler(request):
        data = json.loads(request.content)
        seen.append((request.url.path, data))
        if kind == 'shopify':
            if 'draftOrderCreate' in data['query']:
                items = data['variables']['input']['lineItems']
                assert items[0] == {'quantity': 1, 'variantId': 'gid://shopify/ProductVariant/1'}
                assert [item['originalUnitPrice'] for item in items[1:]] == ['20.00', '30.00']
                assert all('variantId' not in item for item in items[1:])
                return httpx.Response(200, json={'data': {'draftOrderCreate': {'userErrors': [], 'draftOrder': {
                    'id': 'gid://shopify/DraftOrder/7', 'invoiceUrl': 'https://shop.myshopify.com/invoice',
                    'totalPriceSet': {'shopMoney': {'amount': '60.00', 'currencyCode': 'USD'}}}}}})
            assert 'draftOrderDelete' in data['query']
            return httpx.Response(200, json={'data': {'draftOrderDelete': {'deletedId': '7', 'userErrors': []}}})
        if request.url.path.endswith('/v3/carts'):
            assert data['line_items'] == [{'product_id': 1, 'quantity': 1}]
            assert [line['list_price'] for line in data['custom_items']] == [20, 30]
            assert [line['name'] for line in data['custom_items']] == ['Located', 'Back order']
            return httpx.Response(201, json={'data': {'id': 'cart-7', 'cart_amount': 60, 'currency': {'code': 'USD'}}})
        if request.url.path.endswith('/redirect_urls'):
            return httpx.Response(201, json={'data': {'checkout_url': 'https://store.example/checkout'}})
        raise AssertionError(request.url)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        config = {'platform': kind, 'site': 'https://shop.myshopify.com' if kind == 'shopify' else 'https://store.example',
                  'store_hash': 'abc123'}
        adapter = Platform(client, config, CREDS)
        lines = [{'id': 'line-' + str(i), 'title': name, 'quantity': 1, 'price': str(price) + '.00',
                  'kind': source, 'delivery': {'ship_days': 10},
                  'platform_product': {'variant_id': 'gid://shopify/ProductVariant/1'} if kind == 'shopify' else {'product_id': 1}}
                 for i, (name, price, source) in enumerate([('Stock', 10, 'stock'), ('Located', 20, 'locate'), ('Back order', 30, 'back_order')])]
        result = await adapter.create('co-offline', lines, 'USD')
        assert result['total'] == '60.00' and result['url'].startswith('https://')
        assert 'supplier' not in json.dumps(seen)


@pytest.mark.asyncio
async def test_backend_routes_origin_admin_boundary_and_no_new_wording(monkeypatch):
    from fastapi import FastAPI
    from rigbox.api import mount
    from rigbox.cart_api import mount as mount_cart
    from rigbox.service import Service, hash_key
    cart, fake, _, _, _, client = await setup(monkeypatch)
    try:
        key = 'rk_pub_offline_cart'
        await cart.store.put_key(TENANT, hash_key(key), 'publishable', ['https://widget.example'])
        app = FastAPI()
        app.state.rig = Service(cart.store)
        app.state.rig.cart = cart
        mount(app)
        mount_cart(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://rig.example') as api:
            headers = {'x-rig-key': key, 'origin': 'https://widget.example'}
            result = await api.post('/v1/rig/cart/session', json={}, headers=headers)
            assert result.status_code == 200
            token = result.json()['session']
            result = await api.post('/v1/rig/cart/add', json={'session': token, 'product_id': 'stock', 'quantity': 1}, headers=headers)
            assert result.status_code == 200 and len(result.json()['lines']) == 1
            assert result.headers['access-control-allow-origin'] == 'https://widget.example'
            assert result.headers['cache-control'] == 'no-store'
            result = await api.post('/v1/rig/cart/checkout', json={'session': token, 'card': 'forbidden-field'}, headers=headers)
            assert result.status_code == 409 and result.json() == {'error': {'code': 'invalid'}}
            assert not fake.orders
            result = await api.post('/v1/rig/admin/commerce/orders', json={}, headers=headers)
            assert result.status_code == 403
            result = await api.post('/v1/rig/cart/view', json={'session': token}, headers={'x-rig-key': key})
            assert result.status_code == 409 and result.json() == {'error': {'code': 'origin'}}
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_shared_confirmation_gate_paid_retry_and_quote_switch_recovery(monkeypatch):
    cart, fake, _, calls, clock, client = await setup(monkeypatch)
    try:
        await cart.add(TENANT, SESSION, 'stock', 1)
        shared = cart.service.store_confirms_payment
        del cart.service.store_confirms_payment
        with pytest.raises(CommerceError, match='store_confirmation_unavailable'):
            await cart.checkout(TENANT, SESSION)
        assert not fake.orders
        cart.service.store_confirms_payment = shared
        checkout = await cart.checkout(TENANT, SESSION)
        await cart.connect(TENANT, {'mode': 'quote'})
        clock[0] += timedelta(seconds=300)
        await cart.sweep(TENANT)
        assert fake.orders['1']['status'] == 'cancelled'
        fake.orders['1'].update(status='processing', date_paid=clock[0].isoformat())
        raw = b'{"id":1}'
        await cart.webhook(TENANT, raw, signed(raw))
        assert len(calls) == 1
        config = await cart.store.commerce_config(TENANT)
        await cart.store.save_commerce_config(TENANT, {**config, 'mode': 'cart'})
        assert (await cart.checkout(TENANT, SESSION))['id'] == checkout['id']
        assert len(fake.orders) == 1
    finally:
        await client.aclose()
