"""Polling for the isolated research image; no operation POST is repeated."""
import asyncio
import time
from uuid import UUID


async def result(client, key, tenant, value):
    identity = str(UUID(value['paid_run_id']))
    if UUID(value['tenant_id']) != UUID(tenant):
        raise RuntimeError('Foreign paid run')
    deadline = time.monotonic()+25*3600
    while time.monotonic() < deadline:
        response = await client.get('http://tank:8000/v1/paid-runs/'+identity,
            params={'tenant_id':tenant}, headers={'X-Tank-Key':key}, timeout=30, follow_redirects=False)
        response.raise_for_status()
        row = response.json()
        if row['status'] == 'completed':
            if not 200 <= int(row.get('response_status') or 500) < 300 or not isinstance(row.get('result'),dict):
                raise RuntimeError('Paid run failed')
            return row['result']
        if row['status'] in {'cancelled','interrupted'}:
            raise RuntimeError('Paid run interrupted without replay')
        await asyncio.sleep(1)
    raise RuntimeError('Paid run wait expired without replay')
