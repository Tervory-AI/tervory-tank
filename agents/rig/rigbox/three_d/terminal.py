"""Tenant-scoped terminal projections and resumable, read-only event streams."""
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from rigbox.api import _auth, _ok, _tenant
from rigbox.service import RigError
from .api import engine

router = APIRouter(prefix='/v1/rig/3d/terminal')
EMPTY_COST = {'amount_usd': None, 'basis': 'unknown', 'receipt_ids': []}


def public_build(value, row, today):
    # The durable history remains complete. A terminal needs the latest state
    # of each stage, so stream size stays bounded as receipts accumulate.
    latest = {event['stage']: event for event in row.get('progress') or []}
    events = [latest[stage] for stage in ('understand', 'design', 'check', 'price') if stage in latest]
    amount = row['progress'][-1]['cost'] if row.get('progress') else dict(EMPTY_COST)
    approved = row['status'] == 'approved'
    # Ready uses actual persisted approval time. Historical jobs may have no
    # Forge/price telemetry, so leave those stages unknown rather than invent it.
    if approved:
        at = row['approved_at']
        elapsed = max(0, int((at - row['created_at']).total_seconds() * 1000))
        events.append({'id': 'approval-ready', 'stage': 'ready', 'at': at.isoformat(),
            'elapsed_ms': elapsed, 'outcome': 'delivered', 'cost': amount})
    report = row.get('report') or {}
    return {'id': str(row['id']), 'name': row['name'], 'status': row['status'],
        'model': value.public_model(row, 'centre', None) if approved else None,
        'price': {'amount': str(row['price']), 'currency': row['currency']},
        'events': events, 'cost': amount,
        'today': approved and row['approved_at'].astimezone(timezone.utc).date() == today,
        'receipt': {'job_id': str(row['id']), 'approved_at': row['approved_at'].isoformat(),
                    'sha256': report['sha256'], 'receipt_ids': report.get('receipt_ids', []), 'cost': amount} if approved else None}


async def snapshot(value, tenant):
    await value.require(tenant)
    today = datetime.now(timezone.utc).date()
    rows = await value.store.terminal_rows(tenant)
    builds = [public_build(value, row, today) for row in rows]
    return {'date': today.isoformat(), 'timezone': 'UTC',
        'counts': await value.store.terminal_counts(tenant),
        'approved': [b for b in builds if b['status'] == 'approved'],
        'live': next((b for b in builds if b['status'] in {'queued', 'running', 'draft'}), None),
        'latest': builds[0] if builds else None}


@router.get('')
async def current(request: Request):
    await _auth(request)
    return _ok(request, await snapshot(engine(request), _tenant(request)))


@router.get('/completed')
async def completed(request: Request, before: UUID | None = None, today: bool = True):
    await _auth(request)
    value, tenant = engine(request), _tenant(request)
    await value.require(tenant)
    rows = await value.store.completed(tenant, before, today)
    return _ok(request, {'builds': [public_build(value, row, datetime.now(timezone.utc).date()) for row in rows],
                         'next': str(rows[-1]['id']) if len(rows) == 20 else None})


async def updates(request, value, tenant, *, once=False):
    previous = ''
    cursor = 0
    while not await request.is_disconnected():
        try:
            # Revalidate key, origin and entitlement on every tick. This also
            # restores tenant context inside StreamingResponse's task.
            await _auth(request, count_request=False)
            if _tenant(request) != tenant:
                raise RigError('unauthorized', 'That key is not valid.', 401)
            await value.require(tenant)
            rows = await value.store.terminal_rows(tenant)
            active = [r for r in rows if r['status'] in {'queued', 'running'}]
            if active:
                row = active[cursor % len(active)]
                cursor += 1
                # Polling cannot submit, restart, reserve or approve a job.
                async with asyncio.timeout(30):
                    await value.poll(tenant, row['id'])
            data = json.dumps(await snapshot(value, tenant), separators=(',', ':'))
            identity = hashlib.sha256(data.encode()).hexdigest()
            if identity != previous:
                yield f'id: {identity}\nevent: build\ndata: {data}\n\n'
                previous = identity
            else:
                yield ': keepalive\n\n'
        except (RigError, TimeoutError) as exc:
            # No raw provider/SQL exception text reaches a public screen.
            message = exc.message if isinstance(exc, RigError) else 'The product service is not connected.'
            yield 'event: unavailable\ndata: ' + json.dumps({'message': message}) + '\n\n'
            return
        except Exception:
            yield 'event: unavailable\ndata: ' + json.dumps({'message': 'The product service is not connected.'}) + '\n\n'
            return
        if once:
            return
        await asyncio.sleep(2)


@router.get('/events')
async def events(request: Request, once: bool = False):
    await _auth(request)
    value, tenant = engine(request), _tenant(request)
    await value.require(tenant)
    headers = dict(_ok(request, {}).headers)
    for name in ('content-length', 'content-type'):
        headers.pop(name, None)
    headers.update({'Cache-Control': 'private, no-store', 'X-Accel-Buffering': 'no',
                    'Vary': 'Origin, X-Rig-Key'})
    return StreamingResponse(updates(request, value, tenant, once=once), media_type='text/event-stream', headers=headers)
