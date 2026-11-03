"""One durable request: approved live frame -> existing build -> scanned staging.

Production remains a separate founder-only promotion operation.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid5

import httpx

from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from chassis.tenant_db import tenant_path


class Start(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    request_id: UUID
    page_id: str = Field(pattern=r'^[a-z0-9-]{1,100}$')
    brief: dict


class Journal:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS pipelines (tenant TEXT NOT NULL, id TEXT NOT NULL, '
                       'input_hash TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(tenant,id))')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=1)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, tenant, ident):
        with self.connect() as db:
            row = db.execute('SELECT result FROM pipelines WHERE tenant=? AND id=?', (tenant, ident)).fetchone()
        return json.loads(row['result']) if row else None

    def claim(self, tenant, ident, payload):
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        initial = {'tenant_id': tenant, 'request_id': ident, 'kind': 'pipeline', 'status': 'running',
                   'pipeline_status': 'requested', 'ok': False,
                   'steps': [{'state': 'requested', 'at': datetime.now(timezone.utc).isoformat()}], 'checks': []}
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT input_hash,result FROM pipelines WHERE tenant=? AND id=?', (tenant, ident)).fetchone()
            if row:
                if row['input_hash'] != fingerprint:
                    raise ValueError('request identity changed')
                # An interrupted side effect is inspected, never automatically dispatched again.
                return json.loads(row['result'])
            db.execute('INSERT INTO pipelines(tenant,id,input_hash,result) VALUES(?,?,?,?)',
                       (tenant, ident, fingerprint, json.dumps(initial)))
        return None

    def save(self, result):
        with self.connect() as db:
            db.execute('UPDATE pipelines SET result=? WHERE tenant=? AND id=?',
                       (json.dumps(result), result['tenant_id'], result['request_id']))


class Pipeline:
    def __init__(self, journal, approval, read, build, stage, gold):
        self.journal, self.approval, self.read, self.build, self.stage, self.gold = journal, approval, read, build, stage, gold

    async def approved_page(self, tenant, page_id):
        if not isinstance(page_id, str) or not page_id:
            raise ValueError('approved page required')
        approval = await self.approval(tenant, page_id)
        if not approval:
            raise ValueError('approved page required')
        reading = await self.read(tenant, approval)
        self.gold.require_visual_data(reading)
        if (reading.get('source') != 'figma' or reading.get('ready') is not True
                or self.gold.digest(reading) != approval['frame_hash']):
            raise ValueError('approved frame changed')
        if await self.approval(tenant, page_id) != approval:
            raise ValueError('page approval changed')
        return approval

    async def run(self, tenant, ident, payload):
        tenant, ident = str(UUID(tenant)), str(UUID(ident))
        prior = self.journal.claim(tenant, ident, payload)
        if prior is not None:
            return prior
        result = self.journal.get(tenant, ident)

        def progress(name, **updates):
            result.update(updates, pipeline_status=name, summary=name)
            scans = [c for c in result.get('checks', []) if c.get('name') == 'radix.repo']
            if scans:
                result['summary'] += '; ' + scans[0].get('summary', 'radix.repo')
            result['steps'].append({'state': name, 'at': datetime.now(timezone.utc).isoformat()})
            self.journal.save(result)

        try:
            progress('figma')
            approval = await self.approved_page(tenant, payload['page_id'])
            result['approval'] = {key: approval[key] for key in
                                  ('page_id', 'figma_file_id', 'figma_frame_id', 'frame_hash', 'page_hash')}
            progress('build')
            built = await self.build(tenant, ident, payload['brief'])
            result.update({k: v for k, v in built.items() if k in
                {'ok', 'slug', 'build', 'checks', 'results', 'detail', 'memory_id', 'copy_needed', 'media_needed'}})
            if built.get('ok') is not True:
                progress('blocked', status='done')
                return result
            progress('checks')
            # The real handler adds R5 to checks and memory before staging can start.
            rows = [c for c in result['checks'] if c.get('name') == 'radix.repo']
            if len(rows) != 1 or rows[0].get('ok') is not True:
                raise ValueError('repo scan required')
            if await self.approval(tenant, payload['page_id']) != approval:
                raise ValueError('page approval changed during build')
            progress('staging')
            staged = await self.stage(tenant, ident, built, payload['actor'])
            result['staging'] = {k: staged[k] for k in ('id', 'result', 'details') if k in staged}
            if staged.get('result') != 'succeeded':
                progress('staging_pending' if staged.get('result') == 'pending' else 'blocked',
                         ok=False, status='done')
            else:
                progress('awaiting_promote', ok=True, status='done', url=staged['details']['url'],
                         commit=staged['details']['commit'])
        except Exception:  # Never retain provider/API messages in a card or journal.
            progress('blocked', ok=False, status='done', detail='pipeline prerequisite or operation unavailable')
        return result


def service(ctx, pool, loader, root):
    gold = loader('tisan_gold_sources', 'gold_sources.py')
    builder = loader('tisan_builder', 'builder.py')
    figma = loader('tisan_figma', 'figma.py')
    publisher = loader('tisan_publish', 'publish.py')
    core = loader('tisan_promotion', 'promotion.py')

    async def approved(tenant, page_id):
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT page_id,figma_file_id,figma_frame_id,frame_hash,page_hash,approved_by '
                'FROM agent_tisan.page_approvals WHERE tenant_id=$1 AND page_id=$2', UUID(tenant), page_id)
        if not row:
            return None
        try:
            snapshot = gold.snapshot(root, tenant, page_id)
            if snapshot['frame_hash'] != row['frame_hash'] or snapshot['page_hash'] != row['page_hash']:
                return None
        except (ValueError, KeyError, TypeError, OSError, HTTPException):
            return None
        return dict(row)

    async def read(tenant, approval):
        return await figma.execute({'file_key': approval['figma_file_id'], 'node_id': approval['figma_frame_id']},
                                   tenant, live=True, data_root=root)

    async def build(tenant, ident, brief):
        child = SimpleNamespace(**{**vars(ctx), 'tenant_id': tenant, 'job_id': ident, 'input': brief})
        return await builder.handle(child)

    async def stage(tenant, ident, built, actor):
        # Same publisher and idempotent operation journal as the existing API.
        import asyncio
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as http:
            journal = core.Journal(root / 'promotion.sqlite3')
            publish = publisher.Publisher(core, journal, core.Coolify(http,
                os.environ.get('TISAN_COOLIFY_URL', ''), os.environ.get('TISAN_COOLIFY_TOKEN', '')),
                http, root, os.environ.get('TANK_URL', 'http://tank:8000'), os.environ.get('TANK_KEY', ''))
            body = publisher.PublishRequest(tenant_id=tenant, slug=built['slug'], build=built['build'],
                                           operation_id=uuid5(UUID(ident), 'staging'))
            row = await publish.run(body, actor)
            deadline = asyncio.get_running_loop().time() + 480
            while row['result'] == 'pending' and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(2)
                row = await publish.status(body, actor)
            return row
    return Pipeline(Journal(root / 'promotion.sqlite3'), approved, read, build, stage, gold)


async def refresh_staging(result, loader, root):
    """Inspect an acknowledged staging operation; GET never dispatches a deploy."""
    if result.get('pipeline_status') not in {'staging', 'staging_pending'}:
        return result
    core = loader('tisan_promotion', 'promotion.py')
    publisher = loader('tisan_publish', 'publish.py')
    journal = core.Journal(root / 'promotion.sqlite3')
    tenant, ident = result['tenant_id'], result['request_id']
    operation = str(uuid5(UUID(ident), 'staging'))
    row = journal.get(tenant, result['slug'], operation)
    if row is None:
        return result  # No acknowledged side effect: do not retry from a status read.
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as http:
        service = publisher.Publisher(core, journal, core.Coolify(http,
            os.environ.get('TISAN_COOLIFY_URL', ''), os.environ.get('TISAN_COOLIFY_TOKEN', '')),
            http, root, os.environ.get('TANK_URL', 'http://tank:8000'), os.environ.get('TANK_KEY', ''))
        body = publisher.PublishRequest(tenant_id=tenant, slug=result['slug'], build=result['build'], operation_id=operation)
        row = await service.status(body, row['actor'])
    result['staging'] = {key: row[key] for key in ('id', 'result', 'details')}
    if row['result'] == 'pending':
        return result
    state = 'awaiting_promote' if row['result'] == 'succeeded' else 'blocked'
    result.update(pipeline_status=state, summary=state, ok=state == 'awaiting_promote', status='done')
    if state == 'awaiting_promote':
        result.update(url=row['details']['url'], commit=row['details']['commit'])
    result['steps'].append({'state': state, 'at': datetime.now(timezone.utc).isoformat()})
    Journal(root / 'promotion.sqlite3').save(result)
    return result


def mount(app, loader):
    gold = loader('tisan_gold_sources', 'gold_sources.py')

    @app.post('/pipeline/start')
    @tenant_path('body')
    async def start(body: Start, x_tank_key: str = Header(default=''), x_tervory_admin: str = Header(default='')):
        gold.founder(x_tank_key, x_tervory_admin)
        payload = {'page_id': body.page_id, 'brief': body.brief, 'actor': x_tervory_admin}
        async with app.state.pool.acquire() as conn:
            await conn.execute("INSERT INTO agent_tisan.jobs(id,tenant_id,kind,input,status,timeout_s,max_attempts) "
                "VALUES($1,$2,'pipeline',$3::jsonb,'queued',2400,1) ON CONFLICT(id) DO NOTHING",
                body.request_id, body.tenant_id, json.dumps(payload))
            row = await conn.fetchrow('SELECT id,tenant_id,kind,input,status FROM agent_tisan.jobs '
                                     'WHERE tenant_id=$1 AND id=$2', body.tenant_id, body.request_id)
        stored = json.loads(row['input']) if row and isinstance(row['input'], str) else row['input'] if row else None
        if not row or row['kind'] != 'pipeline' or stored != payload:
            raise HTTPException(409, 'request identity changed')
        return {'request_id': str(body.request_id), 'job_id': str(body.request_id), 'tenant_id': str(body.tenant_id),
                'kind': 'pipeline', 'status': row['status']}

    @app.get('/pipeline/status/{request_id}')
    @tenant_path('tenant_id')
    async def status(request_id: UUID, tenant_id: UUID, x_tank_key: str = Header(default='')):
        gold.room_key(x_tank_key)
        root = Path(os.environ.get('DATA_DIR', '/data'))
        result = Journal(root / 'promotion.sqlite3').get(str(tenant_id), str(request_id))
        if result is None:
            async with app.state.pool.acquire() as conn:
                job = await conn.fetchrow('SELECT status FROM agent_tisan.jobs WHERE tenant_id=$1 AND id=$2 '
                                         "AND kind='pipeline'", tenant_id, request_id)
            if job is None:
                raise HTTPException(404, 'not found')
            return {'tenant_id': str(tenant_id), 'request_id': str(request_id), 'kind': 'pipeline',
                    'status': 'done' if job['status'] == 'failed' else job['status'],
                    'ok': False, 'summary': 'blocked' if job['status'] == 'failed' else job['status']}
        try:
            return await refresh_staging(result, loader, root)
        except (ValueError, KeyError, OSError, TimeoutError, httpx.HTTPError):
            return result
