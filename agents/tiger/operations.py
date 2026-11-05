"""One offline command previews every Tiger schedule from a scoped snapshot."""
import argparse
import asyncio
from datetime import datetime
import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx


class Snapshot:
    def __init__(self, data, tenant):
        if data.get('tenant_id') != tenant:
            raise ValueError('Snapshot belongs to another tenant')
        for group in ('watches', 'observations'):
            if any(row.get('tenant_id', tenant) != tenant for row in data.get(group, [])):
                raise ValueError('Snapshot contains another tenant')
        self.data, self.tenant = data, tenant

    def scope(self, tenant):
        if tenant != self.tenant:
            raise ValueError('Snapshot scope changed')

    async def enabled_watches(self, tenant):
        self.scope(tenant)
        return [row for row in self.data.get('watches', []) if row['enabled']]

    async def latest_observation(self, tenant, url):
        self.scope(tenant)
        rows = [row for row in self.data.get('observations', []) if row['url'] == url]
        return max(rows, key=lambda row: datetime.fromisoformat(row['ts'])) if rows else None

    async def check_open(self, tenant, url):
        self.scope(tenant)
        return url in self.data.get('open_jobs', [])

    async def pending_mail(self, tenant, now):
        self.scope(tenant)
        return self.data.get('pending_mail', [])


async def preview(data, tenant, at):
    spec = importlib.util.spec_from_file_location('tiger_operations_agent', Path(__file__).with_name('app.py'))
    agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent)
    from rig_watch import RigWatches, TankRig
    store = Snapshot(data, tenant)
    async def recorded(request):
        if request.method != 'GET':
            raise AssertionError('Dry-run attempted a write')
        if request.url.path.endswith('/tenants'):
            return httpx.Response(200, json={'tenants': data.get('rig_tenants', [])})
        store.scope(request.url.params.get('tenant_id'))
        return httpx.Response(200, json={'tenant_id': tenant, 'products': data.get('rig_products', [])})
    async with httpx.AsyncClient(transport=httpx.MockTransport(recorded)) as http:
        rig = TankRig(http)
        dispatch = await agent.dry_dispatch(store, rig, tenant, at)
        tenants = await RigWatches(SimpleNamespace(pool=None, schema='agent_tiger')).discover(rig, dry_run=True)
        heartbeat = await agent.ping(SimpleNamespace(agent='tiger', tenant_id=agent.HEARTBEAT_TENANT,
                                               input={'heartbeat': True, 'dry_run': True}))
    return {'dry_run': True, 'tenant_id': tenant, 'at': at.isoformat(),
            'dispatch': dispatch, 'rig_discover': {'tenants': tenants}, 'ping': heartbeat}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', required=True)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--at', required=True)
    args = parser.parse_args()
    at = datetime.fromisoformat(args.at)
    if at.tzinfo is None:
        raise ValueError('Preview time needs a timezone')
    result = asyncio.run(preview(json.loads(Path(args.snapshot).read_text()), str(UUID(args.tenant)), at))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Dry-run incomplete; check the snapshot, tenant and time. Source details are withheld.') from None
