"""Tank's storage adapter: uploads credentials only; room usage stays remote.

Packaging prerequisite: install the shared chassis.storage module in the Tank
image before registering this router. No room R2 credential is read here.
"""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException

from admin import require_admin
from chassis.storage import CAPACITY_BYTES, ROOMS, Storage, StorageError

router = APIRouter(prefix='/v1/admin/storage', dependencies=[Depends(require_admin)])


def uploads(**kwargs) -> Storage:
    return Storage('uploads', **kwargs)


@router.get('/usage')
async def usage() -> dict:
    """Live measurements only. Missing rooms are errors, never fabricated zeroes."""
    buckets = []
    store = None
    try:
        store = uploads()
        buckets.append(await store.usage())
    except StorageError:
        buckets.append({'bucket': 'tervory-uploads', 'error': 'Storage unavailable'})
    finally:
        if store is not None:
            await store.close()
    async with httpx.AsyncClient(timeout=30, trust_env=False, follow_redirects=False) as http:
        for room in sorted(ROOMS):
            bucket = 'tervory-' + room.replace('_', '-')
            suffix = room.upper()
            key = os.environ.get(f'TANK_KEY_{suffix}', '')
            if not key:
                buckets.append({'bucket': bucket, 'error': 'Room is not configured'})
                continue
            # Fixed local room host; caller cannot choose a URL or another region.
            host = 'agent-' + room.replace('_', '-')
            try:
                response = await http.get(f'http://{host}:8000/storage/usage', headers={'X-Tank-Key': key})
                response.raise_for_status()
                measured = response.json()
                if measured.get('bucket') != bucket or type(measured.get('used_bytes')) is not int or measured['used_bytes'] < 0:
                    raise ValueError('Invalid measurement')
                buckets.append({k: measured[k] for k in ('bucket', 'used_bytes', 'objects', 'measured_at')})
            except (httpx.HTTPError, ValueError, KeyError):
                buckets.append({'bucket': bucket, 'error': 'Room storage unavailable'})
    if all('error' in row for row in buckets):
        raise HTTPException(503, 'Storage measurements are unavailable')
    return {'buckets': buckets, 'reference_capacity_bytes': CAPACITY_BYTES,
            'complete': not any('error' in row for row in buckets)}
