"""Base-only signed planning adapter. Existing legacy endpoints remain unchanged.

The worker performs free passes and the personal memory bracket. This service
only plans unresolved work through Tank; it never talks to Hermes or a provider.
"""
import asyncio
from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from chassis.sqlite_nonces import SQLiteNonces
from chassis.user_assertion import SignedUser, signed_user, sign_assertion
app = FastAPI()


class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    task_id: UUID
    user_id: str = Field(min_length=1, max_length=200)
    home_region: str
    batch: str = Field(min_length=1, max_length=120)
    count: int = Field(ge=1, le=100000)
    engine: str | None = None
    evidence: list[dict] = Field(default_factory=list, max_length=20)


def state_file():
    root = Path(os.environ.get('DATA_DIR', '/data'))
    if root.is_symlink():
        raise ValueError('Invalid Base data directory')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root / 'personal-plans.sqlite3'


def reserve(body):
    raw = json.dumps(body.model_dump(mode='json'), sort_keys=True, separators=(',', ':'))
    digest = hashlib.sha256(raw.encode()).hexdigest()
    with closing(sqlite3.connect(state_file(), timeout=5)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS plans (tenant TEXT, task TEXT, owner TEXT, digest TEXT, receipt TEXT, PRIMARY KEY(tenant,task))')
        row = db.execute('SELECT owner,digest,receipt FROM plans WHERE tenant=? AND task=?',
                         (str(body.tenant_id), str(body.task_id))).fetchone()
        if row:
            if row[:2] != (body.user_id, digest):
                raise HTTPException(403, 'Base planning ownership mismatch')
            if row[2]:
                return json.loads(row[2])
            raise HTTPException(409, 'Base planning receipt pending; do not resubmit')
        db.execute('INSERT INTO plans VALUES (?,?,?,?,NULL)',
                   (str(body.tenant_id), str(body.task_id), body.user_id, digest))


def save(body, receipt):
    with closing(sqlite3.connect(state_file(), timeout=5)) as db, db:
        db.execute('UPDATE plans SET receipt=? WHERE tenant=? AND task=? AND owner=?',
            (json.dumps(receipt), str(body.tenant_id), str(body.task_id), body.user_id))


@app.post('/personal/tasks')
async def personal_task(body: Plan, request: Request):
    key = os.environ.get('TANK_KEY', '')
    supplied = request.headers.get('x-tank-key', '')
    if not key or not hmac.compare_digest(key, supplied):
        raise HTTPException(401, 'Base room key required')
    if body.home_region != os.environ.get('TANK_REGION', 'us-east') or body.home_region != 'us-east':
        raise HTTPException(403, 'Base planning region mismatch')
    actor = await signed_user(request, tenant_id=str(body.tenant_id), product='base', required=True,
        nonces=SQLiteNonces(state_file().with_name('personal-nonces.sqlite3')))
    if actor.user_id != body.user_id:
        raise HTTPException(403, 'Base planning owner mismatch')
    if len(json.dumps(body.model_dump(mode='json')).encode()) > 32768:
        raise HTTPException(413, 'Base planning evidence exceeds its limit')
    previous = await asyncio.to_thread(reserve, body)
    if previous is not None:
        return previous
    path = '/v1/agents/base/tasks'
    payload = dict(tenant_id=str(body.tenant_id), user_id=actor.user_id, run_id=str(body.task_id),
        messages=[{'role': 'user', 'content': 'Plan the unresolved Base business batch using its recorded evidence: '
                   + json.dumps({'batch': body.batch, 'count': body.count, 'engine': body.engine})}])
    raw = json.dumps(payload, separators=(',', ':')).encode()
    headers = {'X-Tank-Key': key, 'X-Home-Region': body.home_region, 'Content-Type': 'application/json',
        'X-Tervory-User-Assertion': sign_assertion('base', SignedUser(str(body.tenant_id), actor.user_id, actor.role),
                                                'POST', path, raw, key=key)}
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(os.environ.get('TANK_URL', 'http://tank:8000').rstrip('/') + path,
                                     content=raw, headers=headers, follow_redirects=False)
    if response.status_code != 200:
        raise HTTPException(503, 'Base planning unavailable; check the retained receipt before retrying')
    data = response.json()
    row = data['receipt']
    if (row.get('tenant_id'), row.get('task_id'), row.get('room'), row.get('region')) != (
            str(body.tenant_id), str(body.task_id), 'base', body.home_region):
        raise HTTPException(503, 'Base planning receipt scope mismatch')
    UUID(row['ledger_id'])
    summary = data['choices'][0]['message']['content']
    receipt = dict(tenant_id=str(body.tenant_id), user_id=actor.user_id, task_id=str(body.task_id),
        room='base', region=body.home_region, status='done', summary=summary,
        model_receipts=[row], evidence=body.evidence, steps=[{'action': 'tank_plan', 'ledger_id': row['ledger_id']}])
    await asyncio.to_thread(save, body, receipt)
    return receipt


@app.get('/health')
async def health():
    return {'status': 'ok'}
