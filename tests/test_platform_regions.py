import uuid

import pytest
import tenant_regions
from fastapi import HTTPException
from test_tank_tenant_boundaries import boundary  # noqa: F401


@pytest.mark.asyncio
async def test_founder_onboarding_is_immutable_and_wrong_box_cannot_run(boundary):  # noqa: F811
    b = boundary
    tenant = uuid.uuid4()
    url = '/v1/tenants/'+str(tenant)
    assert (await b.client.get(url)).status_code == 409
    headers = {'X-Tervory-Tenant': str(tenant), 'X-Tervory-User': 'ordinary-user', 'X-Tervory-Role': 'reviewer'}
    assert (await b.client.put(url, json={'home_region': 'za'}, headers=headers)).status_code == 404
    headers['X-Tervory-User'] = 'founder-fixture'
    for _ in range(2):
        response = await b.client.put(url, json={'home_region': 'za'}, headers=headers)
        assert response.status_code == 200 and response.json()['home_region'] == 'za'
    assert (await b.client.put(url, json={'home_region': 'us-east'}, headers=headers)).status_code == 409
    assert (await b.client.get(url)).json()['home_region'] == 'za'
    client_headers = {'X-Tervory-Tenant':str(tenant), 'X-Tervory-User':'client-a'}
    assert (await b.client.get('/v1/command/tools', headers=client_headers)).status_code == 403
    for claim in (None, 'us-east', 'za'):
        with pytest.raises(HTTPException) as foreign:
            await tenant_regions.local(b.tank, tenant, claim)
        assert foreign.value.status_code == 403
    result = await b.client.post('/v1/route', json={'tenant_id': str(tenant), 'agent': 'base',
        'task_type': 'base.normalize', 'messages': [{'role': 'user', 'content': 'Do not send this.'}]})
    assert result.status_code == 403
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1', tenant) == 0
    assert await tenant_regions.local(b.tank, b.tenants[0]) == 'us-east'


def test_workspace_routes_using_record_and_regional_key():
    import subprocess
    from pathlib import Path
    result = subprocess.run(['node', 'tests/platform/regions.cjs'], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
