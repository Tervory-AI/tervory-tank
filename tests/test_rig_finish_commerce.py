"""Offline store responses: exact option SKUs and real inventory semantics."""
import json

import httpx
import pytest

from test_rig_cart import CREDS
from rigbox.commerce import CommerceError, Platform


def adapter(client, kind='bigcommerce'):
    return Platform(client, {'platform': kind, 'store_hash': 'placeholder',
        'site': 'https://placeholder.myshopify.com' if kind == 'shopify' else 'https://store.example'}, CREDS)


@pytest.mark.asyncio
@pytest.mark.parametrize('matches,pages,expected', [(1, 1, {'product_id': 31, 'variant_id': 42}),
    (0, 1, None), (2, 1, None), (1, 2, None)])
async def test_bigcommerce_exact_variant_sku_never_substitutes_another(matches, pages, expected):
    def reply(request):
        assert request.method == 'GET'
        assert request.url.path.endswith('/v3/catalog/variants')
        assert request.url.params['sku'] == 'LAMP-BLUE'
        rows = [{'id': 42 + i, 'product_id': 31, 'sku': 'LAMP-BLUE'} for i in range(matches)]
        rows.append({'id': 99, 'product_id': 31, 'sku': 'LAMP-RED'})
        return httpx.Response(200, json={'data': rows, 'meta': {'pagination': {'total_pages': pages}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        assert await adapter(client).product_mapping('LAMP-BLUE') == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('tracking,quantity', [('none', None), ('product', 7), ('variant', 3)])
@pytest.mark.parametrize('availability,disabled,visible,available', [
    ('available', False, True, True), ('disabled', False, True, False),
    ('preorder', False, True, False), ('available', True, True, False),
    ('available', False, False, False)])
async def test_bigcommerce_variant_respects_parent_availability_and_inventory(tracking, quantity, availability, disabled, visible, available):
    def reply(request):
        if request.url.path.endswith('/variants/42'):
            return httpx.Response(200, json={'data': {'id': 42, 'product_id': 31, 'calculated_price': 19.95,
                'purchasing_disabled': disabled, 'inventory_level': 3}})
        assert request.url.path.endswith('/products/31')
        return httpx.Response(200, json={'data': {'id': 31, 'availability': availability,
            'is_visible': visible, 'inventory_tracking': tracking, 'inventory_level': 7}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        result = await adapter(client).stock({'product_id': 31, 'variant_id': 42})
    assert result == {'price': '19.95', 'available': available, 'quantity': quantity}


@pytest.mark.asyncio
async def test_bigcommerce_refuses_wrong_or_missing_variant_mapping():
    def reply(request):
        if '/variants/' in request.url.path:
            return httpx.Response(200, json={'data': {'id': 42, 'product_id': 999}})
        return httpx.Response(200, json={'data': {'inventory_tracking': 'variant', 'availability': 'available'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        for mapping in ({'product_id': 31}, {'product_id': 31, 'variant_id': 42}):
            with pytest.raises(CommerceError, match='product_mapping'):
                await adapter(client).stock(mapping)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['shopify', 'woocommerce'])
@pytest.mark.parametrize('tracked,quantity', [(True, 0), (False, None)])
async def test_store_untracked_inventory_is_not_mistaken_for_zero_stock(kind, tracked, quantity):
    def reply(request):
        if kind == 'shopify':
            body = json.loads(request.content)
            assert 'inventoryItem{tracked}' in body['query']
            return httpx.Response(200, json={'data': {'productVariant': {
                'price': '12.34', 'availableForSale': True, 'inventoryQuantity': 0,
                'inventoryItem': {'tracked': tracked}}}})
        return httpx.Response(200, json={'price': '12.34', 'stock_status': 'instock',
                                       'manage_stock': tracked, 'stock_quantity': 0})
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        result = await adapter(client, kind).stock({'product_id': 31, 'variant_id': '42'})
    assert result == {'price': '12.34', 'available': True, 'quantity': quantity}


@pytest.mark.asyncio
async def test_deleted_shopify_variant_uses_existing_product_error():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={
            'data': {'productVariant': None}}))) as client:
        with pytest.raises(CommerceError, match='product'):
            await adapter(client, 'shopify').stock({'variant_id': 'gid://shopify/ProductVariant/42'})


@pytest.mark.asyncio
async def test_bigcommerce_option_sku_reaches_store_checkout_with_its_variant(monkeypatch):
    from rigbox.cart import Cart
    from rigbox.service import Service
    from rigbox.store import MemoryStore
    from test_rig_cart import TENANT, SESSION
    monkeypatch.setenv('RIG_LOCATE_HOLD_SECRET', 'placeholder-hold-signing-value-' * 2)
    created = []
    def reply(request):
        route = request.url.path
        if route.endswith('/v2/store'):
            return httpx.Response(200, json={'id': 1})
        if route.endswith('/v3/catalog/variants'):
            return httpx.Response(200, json={'data': [{'id': 42, 'product_id': 31, 'sku': 'LAMP-BLUE'}]})
        if route.endswith('/products/31'):
            return httpx.Response(200, json={'data': {'availability': 'available', 'is_visible': True,
                'inventory_tracking': 'none', 'inventory_level': 0}})
        if route.endswith('/variants/42'):
            return httpx.Response(200, json={'data': {'id': 42, 'product_id': 31, 'calculated_price': 19.95,
                'purchasing_disabled': False, 'inventory_level': 0}})
        if route.endswith('/v3/carts'):
            created.append(json.loads(request.content))
            return httpx.Response(201, json={'data': {'id': 'fixture-cart', 'cart_amount': 39.90, 'currency': {'code': 'USD'}}})
        if route.endswith('/redirect_urls'):
            return httpx.Response(201, json={'data': {'checkout_url': 'https://store.example/checkout'}})
        pytest.fail(route)
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        store = MemoryStore()
        await store.put_retailer(TENANT, 'fixture', None, None)
        await store.upsert_product(TENANT, {'sku': 'LAMP-BLUE', 'name': 'Blue lamp', 'price': '19.95',
            'currency': 'USD', 'active': True, 'brand': 'Fixture', 'category': 'Lighting', 'image_url': ''})
        async def platform(tenant, config):
            return Platform(client, config, CREDS)
        cart = Cart(Service(store), platform)
        await cart.connect(TENANT, {'platform': 'bigcommerce', 'site': 'https://store.example',
            'store_hash': 'placeholder', 'mode': 'cart', 'region': 'US', 'vault_name': 'placeholder',
            'delivery': {'ship_days': 2}})
        added = await cart.add(TENANT, SESSION, 'LAMP-BLUE', 2)
        assert added['lines'][0]['kind'] == 'stock'
        checked = await cart.checkout(TENANT, SESSION)
        assert checked['state'] == 'pending' and checked['total'] == '39.90'
        assert created == [{'line_items': [{'product_id': 31, 'variant_id': 42, 'quantity': 2}],
            'custom_items': [], 'currency': {'code': 'USD'}}]
        assert 'variant_id' not in json.dumps(added)
