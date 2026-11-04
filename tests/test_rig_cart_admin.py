"""Signed-in cart admin boundary and sealed credentials, entirely offline."""
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

import access
import command
from test_rig_cart import TENANT, OTHER, setup
from rigbox.cart_api import commerce_operation
from rigbox.commerce import CommerceError


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['commerce-connect', 'commerce-orders', 'store-delivery'])
async def test_cart_admin_rejects_ordinary_member_before_dispatch(monkeypatch, operation):
    app = FastAPI()
    app.include_router(access.router)
    app.dependency_overrides[access.identity] = lambda: command.Actor(
        UUID(TENANT), 'placeholder-member', False, frozenset({'rig'}))
    dispatch = AsyncMock()
    monkeypatch.setattr(access, 'rig_request', dispatch)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://placeholder.example') as api:
        response = await api.post('/v1/access/rig/admin/' + operation, json={'data': {}})
    assert response.status_code == 403
    dispatch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("platform,primary", [("shopify", {"access_token": "placeholder-access"}),
    ("woocommerce", {"consumer_key": "placeholder-key", "consumer_secret": "placeholder-secret"}),
    ("bigcommerce", {"access_token": "placeholder-access"})])
@pytest.mark.parametrize("preserve", [False, True])
async def test_cart_admin_credentials_sealed_not_forwarded_returned_or_logged(monkeypatch, caplog, platform, primary, preserve):
    app = FastAPI()
    app.include_router(access.router)
    actor = command.Actor(UUID(TENANT), 'placeholder-admin', False, frozenset({'rig'}), True)
    app.dependency_overrides[access.identity] = lambda: actor
    sealed, written, forwarded = [], [], []

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield self

        async def fetchval(self, sql, *args):
            assert args == (actor.tenant_id, "placeholder-commerce")
            return 'placeholder-previous-envelope' if preserve else None

        async def execute(self, sql, *args):
            assert 'INSERT INTO tank.vault_items' in sql
            written.append(args)
    monkeypatch.setattr(access, 'db', lambda: Pool())
    def seal(value, context):
        sealed.append((value, context))
        return 'placeholder-encrypted-envelope'
    monkeypatch.setattr(access.vault, 'seal', seal)
    async def room(who, operation, data):
        forwarded.append((who.tenant_id, operation, data))
        return {'saved': True}
    monkeypatch.setattr(access, 'rig_request', room)
    monkeypatch.setattr(access.vault, 'open_seal', lambda envelope, context: {'value': json.dumps({'webhook_secret': 'placeholder-webhook'})})
    credential = {**primary, 'webhook_secret': 'placeholder-webhook'}
    config = {'mode': 'cart', 'platform': platform, 'vault_name': 'placeholder-commerce',
              'credential': primary if preserve else credential}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://placeholder.example') as api:
        response = await api.post('/v1/access/rig/admin/commerce-connect', json={'data': config})
    assert response.status_code == 200 and response.json() == {'saved': True}
    assert len(sealed) == 1
    assert json.loads(sealed[0][0]['value']) == credential
    assert sealed[0][1] == f'plugins:v1:{TENANT}:rig.vault:secret:placeholder-commerce'
    assert written[0][0] == actor.tenant_id and written[0][-1] == 'placeholder-encrypted-envelope'
    assert forwarded == [(actor.tenant_id, 'commerce-connect', {k: v for k, v in config.items() if k != 'credential'})]
    assert all(value not in response.text + caplog.text for value in credential.values())


@pytest.mark.asyncio
async def test_delivery_and_orders_use_only_account_tenant(monkeypatch):
    cart, _, config, _, _, client = await setup(monkeypatch)
    try:
        for invalid in ({'min_days': True, 'max_days': 1}, {'min_days': -1, 'max_days': 3},
                        {'min_days': 4, 'max_days': 3}, {'min_days': 1, 'max_days': 61},
                        {'min_days': 1.5, 'max_days': 3}, {'min_days': 1, 'max_days': 3, 'tenant_id': OTHER}):
            with pytest.raises(CommerceError, match='delivery'):
                await commerce_operation(cart, TENANT, 'store-delivery', invalid)
        assert (await cart.store.commerce_config(TENANT)) == config
        assert await commerce_operation(cart, TENANT, 'store-delivery', {'min_days': 2, 'max_days': 3}) == {'saved': True}
        assert (await cart.store.commerce_config(TENANT))['delivery'] == {'min_days': 2, 'max_days': 3}
        await cart.rows.put(OTHER, 'co_placeholder-other', {'id': 'co_placeholder-other', 'state': 'placed',
                            'expires_at': 'placeholder', 'lines': []})
        assert await commerce_operation(cart, TENANT, 'orders', {}) == {'orders': []}
        with pytest.raises(CommerceError, match='invalid'):
            await commerce_operation(cart, TENANT, 'orders', {'tenant_id': OTHER})
    finally:
        await client.aclose()
