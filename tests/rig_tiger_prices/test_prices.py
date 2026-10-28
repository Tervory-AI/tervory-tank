"""Offline Rig/Tank/Tiger integration. Test identities and catalogues only."""
import sys
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'agents/rig'))
sys.path.insert(0, str(ROOT / 'agents/_chassis'))
sys.path.insert(0, str(ROOT / 'agents/tiger'))
sys.path.insert(0, str(ROOT / 'tests'))

import access  # noqa: E402
from rigbox.retailer_server import create_retailer_app  # noqa: E402
from rigbox.service import Service  # noqa: E402
from rigbox.store import MemoryStore as RigMemory  # noqa: E402

A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'
URL = 'https://shop.example/item'
NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


async def product(store, tenant, sku='item', url=URL):
    await store.upsert_product(tenant, dict(sku=sku, name='Offline item', brand='Offline',
        category='test', price='10', currency='USD', url=url, active=True))


@pytest_asyncio.fixture
async def corridor(monkeypatch):
    store = RigMemory()
    service = Service(store)
    for tenant in (A, B):
        await product(store, tenant)
    rig = create_retailer_app(service)
    # Public, non-secret fixture strings. No deployment credentials are read.
    monkeypatch.setenv('TANK_KEY_TIGER', 'offline-tiger')
    monkeypatch.setenv('RIG_RETAILER_KEY', 'offline-rig')
    monkeypatch.setattr(access.httpx, 'AsyncClient', lambda **kw: AsyncClient(transport=ASGITransport(app=rig), **kw))
    tank = FastAPI()
    tank.include_router(access.router)
    async with AsyncClient(transport=ASGITransport(app=tank), base_url='http://tank',
                           headers={'x-tank-key': 'offline-tiger'}) as client:
        yield store, service, client


def update(tenant=A, sku='item', url=URL, price='12', stamp=NOW):
    return dict(tenant_id=tenant, sku=sku, url=url, observed_at=stamp.isoformat(),
                price=price, currency='USD', active=True)


@pytest.mark.asyncio
async def test_receiver_and_discovery_are_tiger_only_and_tenant_scoped(corridor):
    store, _, client = corridor
    denied = await client.get('/v1/access/rig/tiger/tenants', headers={'x-tank-key': 'wrong'})
    assert denied.status_code == 401
    assert set((await client.get('/v1/access/rig/tiger/tenants')).json()['tenants']) == {A, B}
    rows = (await client.get('/v1/access/rig/tiger/products', params={'tenant_id': A})).json()
    assert rows == {'tenant_id': A, 'products': [{'sku': 'item', 'url': URL, 'name': 'Offline item'}]}
    response = await client.post('/v1/access/rig/tiger', json=update())
    assert response.status_code == 200 and response.json() == {'updated': True}
    assert Decimal((await store.products(A))[0]['price']) == 12
    assert str((await store.products(B))[0]['price']) == '10'
    foreign = await client.post('/v1/access/rig/tiger', json=update(tenant=str(UUID(int=3))))
    assert foreign.json() == {'updated': False}


@pytest.mark.asyncio
@pytest.mark.parametrize('reason', ['feed', 'deleted', 'no_url', 'new_url'])
async def test_eligibility_and_late_delivery_refuse_ineligible_product(corridor, reason):
    store, _, client = corridor
    if reason == 'feed':
        await store.save_cost(A, {'sku': 'item'})
    elif reason == 'deleted':
        await store.delete_products(A, ['item'])
    else:
        await product(store, A, url='' if reason == 'no_url' else URL + '/new')
    rows = (await client.get('/v1/access/rig/tiger/products', params={'tenant_id': A})).json()['products']
    assert not any(row['url'] == URL for row in rows)
    result = await client.post('/v1/access/rig/tiger', json=update(price='99'))
    assert result.json() == {'updated': False}
    assert str((await store.products(B))[0]['price']) == '10'
    if reason != 'deleted':
        assert str((await store.products(A))[0]['price']) == '10'


@pytest.mark.asyncio
async def test_repeated_and_out_of_order_delivery_cannot_regress_price(corridor):
    store, _, client = corridor
    newer = update(price='20', stamp=NOW + timedelta(minutes=1))
    assert (await client.post('/v1/access/rig/tiger', json=newer)).json()['updated']
    assert (await client.post('/v1/access/rig/tiger', json=update())).json()['updated']
    assert (await client.post('/v1/access/rig/tiger', json=newer)).json()['updated']
    assert Decimal((await store.products(A))[0]['price']) == 20
