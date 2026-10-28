"""The shared wire contract maps onto existing room rows without new columns."""
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from chassis.app import _context, create_app
from chassis.job_contract import Job
from test_bus import A, B
from test_tiger import _load

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_shared_and_legacy_jobs_use_existing_room_table(database, monkeypatch):
    monkeypatch.setenv('TANK_REGION', 'us-east')
    app = create_app('tiger', {})
    app.state.pool, app.state.job_timeouts = database, {}
    for name in ('files', 'tank', 'memory', 'browser'):
        setattr(app.state, name, None)
    wire = Job(tenant_id=A, region='us-east', agent='tiger', skill='check',
               input={'tenant_id': B}, priority='batch', engine='core')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://room') as http:
        response = await http.post('/jobs', json=wire.model_dump(mode='json'))
        assert response.status_code == 201
        async with database.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM agent_tiger.jobs WHERE id=$1 AND tenant_id=$2',
                                      UUID(response.json()['id']), UUID(A))
        assert Job.from_room(row, agent='tiger', region='us-east') == wire
        ctx = _context(app, 'tiger', row)
        assert ctx.tenant_id == A and ctx.kind == 'check' and ctx.input == wire.input
        legacy = await http.post('/jobs', json={'tenant_id': A, 'kind': 'ping', 'input': {}})
        assert legacy.status_code == 201
        for changed in ({'agent': 'rig'}, {'region': 'za'}):
            assert (await http.post('/jobs', json={**wire.model_dump(mode='json'), **changed})).status_code == 422
        for metadata in ([], {'region': 'za'}):
            response = await http.post('/jobs', json={'tenant_id': A, 'kind': 'check', 'input': {'_job_contract': metadata}})
            assert response.status_code == 422


@pytest.mark.asyncio
async def test_base_worker_takes_tenant_from_task_not_json(database, monkeypatch):
    sys.path.insert(0, str(ROOT / 'agents/base'))
    room = _load('bus_base_identity', ROOT / 'agents/base/room.py')
    async with database.acquire() as conn:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_base')
        await room.ensure_tables(conn)
        row = await room.insert_batch(conn, UUID(A), None, 'offline', [], '', False, None, 1, None)
        await conn.execute('UPDATE agent_base.tasks SET input=$2::jsonb WHERE id=$1', row['id'], json.dumps({'tenant_id': B}))
    monkeypatch.delenv('BASE_BRAIN_URL', raising=False)
    async def run(pool, task_id, cfg, call):
        assert task_id == row['id'] and cfg['tenant_id'] == A
        raise asyncio.CancelledError
    monkeypatch.setattr(room, '_run_batch', run)
    class Skills:
        async def pin(self, *args):
            return {}, {}
        def bind(self, versions, preview, tenant):
            assert tenant == A
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(room.base_loop(database, Skills()), 2)
