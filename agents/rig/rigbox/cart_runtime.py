"""US-only wiring. Credentials stay in the existing Tank vault at rest."""
import asyncio
import os

from chassis.tenant_db import tenant_scope
from rigbox.cart import Cart
from rigbox.commerce import CommerceError, Platform


class Platforms:
    def __init__(self, http, tank):
        self.http, self.tank = http, tank

    async def __call__(self, tenant, config):
        from chassis.public_urls import check_url
        # Reuse the rooms' existing public-address check. Never follow redirects
        # with store credentials. Tests replace this boundary, not live DNS.
        try:
            await asyncio.to_thread(check_url, config['site'])
            response = await self.http.post(self.tank._base + '/v1/vaults/rig.vault/commerce/resolve',
                headers={'x-rig-retailer-key': os.environ.get('RIG_RETAILER_KEY', '')},
                json={'tenant_id': str(tenant), 'name': config['vault_name']},
                timeout=20, follow_redirects=False)
            if response.status_code != 200:
                raise ValueError()
            return Platform(self.http, config, response.json()['credential'])
        except Exception:
            raise CommerceError('connection_unavailable') from None


def install(service, http, tank):
    if os.environ.get('TANK_REGION', 'us-east') != 'us-east':
        return None
    service.cart = Cart(service, Platforms(http, tank))

    async def sweep_tenant(tenant):
        with tenant_scope(tenant):
            try:
                await service.cart.sweep(tenant)
            except Exception:
                # No remote body/exception/credential in logs. Durable rows keep
                # uncertain states for the next pass and private order view.
                return

    async def loop():
        while True:
            with tenant_scope(None, administrative=True):
                tenants = await service.store.tenant_ids()
            await asyncio.gather(*(sweep_tenant(tenant) for tenant in tenants))
            await asyncio.sleep(1)

    return asyncio.create_task(loop())
