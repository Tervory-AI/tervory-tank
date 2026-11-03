"""Actual room routes with local fakes; no model, SMTP or external HTTP."""
import importlib.util
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
TENANT, OTHER = str(UUID(int=11)), str(UUID(int=12))


@pytest.fixture
def room(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'agents/rig'))
    spec = importlib.util.spec_from_file_location('bot_b1_rig_room', ROOT / 'agents/rig/app.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setenv('TANK_KEY', 'offline-room-placeholder')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    product = {'tenant_id': TENANT, 'id': 'ACTUAL-SKU', 'sku': 'ACTUAL-SKU',
               'url': 'https://store.invalid/exact-record', 'name': 'Owned item',
               'price': Decimal('123.45'), 'currency': 'ZAR', 'active': True, 'attributes': {}}
    service = SimpleNamespace(
        store=SimpleNamespace(products=AsyncMock(return_value=[product])),
        product=AsyncMock(return_value={'id': 'ACTUAL-SKU', 'price': {'amount': 123.45}}),
        quote=AsyncMock(return_value={'request_id': str(UUID(int=13))}),
    )
    module.app.state.rig = service
    return module.app, service


@pytest.mark.asyncio
async def test_exact_live_record_url_sku_and_decimal_are_serializable(room):
    app, service = room
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        response = await client.get('/v1/rig/products/ACTUAL-SKU',
            params={'tenant_id': TENANT, 'source_record': '1'}, headers={'x-tank-key': 'offline-room-placeholder'})
    assert response.status_code == 200, response.text
    record = response.json()['source_record']
    assert record['url'] == 'https://store.invalid/exact-record'
    assert record['sku'] == 'ACTUAL-SKU' and record['price'] == '123.45'
    service.store.products.assert_awaited_once_with(TENANT)


@pytest.mark.asyncio
async def test_quote_bridge_requires_room_identity_matching_tenant_and_region(room):
    app, service = room
    body = {'tenant_id': TENANT, 'home_region': 'us-east', 'data': {
        'product_id': 'ACTUAL-SKU', 'contact': {'name': 'Typed name', 'email': 'typed@offline.invalid'}}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        path = '/internal/trigger/bot-quote?tenant_id=' + TENANT
        assert (await client.post(path, json=body)).status_code == 401
        headers = {'x-tank-key': 'offline-room-placeholder'}
        assert (await client.post(path, json={**body, 'tenant_id': OTHER}, headers=headers)).status_code == 403
        assert (await client.post(path, json={**body, 'home_region': 'za'}, headers=headers)).status_code == 403
        service.quote.assert_not_awaited()
        result = await client.post(path, json=body, headers=headers)
        assert result.status_code == 200, result.text
    service.quote.assert_awaited_once_with(TENANT, body['data'])
