"""Real Base HTTP/SQL ownership boundary; only skill discovery is a fixture."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from chassis.user_assertion import HEADER, SignedUser, sign_assertion
import test_base_gate5 as fixtures

base = fixtures.base
database = fixtures.database
postgres = fixtures.postgres
KEY = 'placeholder-room-key'
OWNER = 'placeholder-owner-a'
OTHER = 'placeholder-owner-b'


@pytest_asyncio.fixture
async def entry(base, database, monkeypatch):
    monkeypatch.setenv('TANK_KEY_BASE', KEY)
    async with database.acquire() as conn:
        await conn.execute('CREATE SCHEMA agent_base')
        await fixtures.room.ensure_tables(conn, recover=False)
    base.app.state.pool = database
    monkeypatch.setattr(base, '_skills', lambda: SimpleNamespace(
        pin=AsyncMock(return_value=({}, {})), bind=lambda *args: None))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app),
                                base_url='http://local', headers={'X-Tank-Key': KEY}) as client:
        yield client, database


def payload():
    return {'tenant_id': str(uuid4()), 'request_id': str(uuid4()),
            'batch': 'placeholder batch', 'records': [{'name': 'placeholder business'}]}


def signed(body, user=OWNER, **kwargs):
    raw = json.dumps(body).encode()
    assertion = sign_assertion('base', SignedUser(body['tenant_id'], user, 'member'),
                               'POST', '/v1/base/run', raw, key=KEY, **kwargs)
    return {'content': raw, 'headers': {'content-type': 'application/json', HEADER: assertion}}


@pytest.mark.asyncio
@pytest.mark.parametrize('claim', ['forged-owner', 'unsigned-owner', 'body-user'])
async def test_unverified_owner_never_queues(entry, claim):
    client, pool = entry
    body = payload()
    if claim == 'forged-owner':
        body['created_by'] = OTHER
        response = await client.post('/v1/base/run', **signed(body))
    elif claim == 'unsigned-owner':
        body['created_by'] = OWNER
        response = await client.post('/v1/base/run', json=body)
    else:
        body['user_id'] = OTHER
        response = await client.post('/v1/base/run', **signed(body))
    assert response.status_code in {401, 403, 422}
    assert await pool.fetchval('SELECT count(*) FROM agent_base.tasks') == 0


@pytest.mark.asyncio
async def test_verified_owner_persists_and_foreign_retry_cannot_read_result(entry):
    client, pool = entry
    body = payload()
    request = signed(body)
    first = await client.post('/v1/base/run', **request)
    assert first.status_code == 202, first.text
    task = first.json()['task']
    row = await pool.fetchrow('SELECT created_by,input FROM agent_base.tasks WHERE id=$1', UUID(task['id']))
    cfg = json.loads(row['input'])
    assert task['created_by'] == row['created_by'] == OWNER
    assert cfg['user_id'] == cfg['created_by'] == cfg['verified_user_id'] == OWNER
    # Fresh signed retries are idempotent. A reused nonce or another actor is not.
    assert (await client.post('/v1/base/run', **signed(body))).json() == first.json()
    for response in [await client.post('/v1/base/run', **request),
                     await client.post('/v1/base/run', **signed(body, OTHER)),
                     await client.post('/v1/base/run', json=body)]:
        assert response.status_code in {401, 403}
        assert task['id'] not in response.text
    assert await pool.fetchval('SELECT count(*) FROM agent_base.tasks') == 1


@pytest.mark.asyncio
async def test_historical_ownerless_submission_stays_ownerless(entry):
    client, pool = entry
    body = payload()
    first = await client.post('/v1/base/run', json=body)
    assert first.status_code == 202, first.text
    assert (await client.post('/v1/base/run', json=body)).json() == first.json()
    row = await pool.fetchrow('SELECT created_by,input FROM agent_base.tasks')
    assert row['created_by'] is None
    assert 'verified_user_id' not in json.loads(row['input'])
