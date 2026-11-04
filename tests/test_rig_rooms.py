"""Offline store rooms: real lifecycle profile, signed API and production data paths."""
import hashlib
import hmac
import json
import time
from pathlib import Path

import httpx
import pytest
import yaml

from agents.ghost import enforce_lifecycle
from agents.ghost.enforce_api import create_app
from agents.ghost.rig_lifecycle import CoolifyRigBackend, SETTINGS, plan_create, plan_destroy
from rigbox.rooms import api_base, require_owner
from rigbox.service import RigError

A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'
ROOT = Path(__file__).resolve().parents[1]
KEY = 'fixture-lifecycle-key'
TOKEN = 'fixture-coolify-token'


class FakeCoolify:
    """Record the actual Coolify HTTP contract, including retained-volume DELETE."""
    def __init__(self):
        self.apps, self.envs, self.calls = [], {}, []
        self.failure = None

    def __call__(self, request):
        assert request.headers['authorization'] == 'Bearer ' + TOKEN
        self.calls.append(request)
        path = request.url.path.removeprefix('/api/v1')
        if self.failure and request.method == self.failure:
            raise httpx.ReadTimeout('fixture transport failure', request=request)
        if request.method == 'GET':
            assert path == '/applications'
            return httpx.Response(200, json=self.apps)
        if request.method == 'POST':
            assert path == '/applications/private-github-app'
            body = json.loads(request.content)
            assert body['server_uuid'] == 'fixture-server'
            assert body['instant_deploy'] is False and body['is_auto_deploy_enabled'] is False
            row = {**body, 'uuid': 'fixture-app-' + str(len(self.calls)), 'status': 'exited'}
            self.apps.append(row)
            return httpx.Response(201, json={'uuid': row['uuid']})
        if request.method == 'PATCH':
            assert path.endswith('/envs/bulk')
            self.envs[path.split('/')[2]] = {item['key']: item['value'] for item in json.loads(request.content)['data']}
            return httpx.Response(201, content=b'ack')
        assert request.method == 'DELETE'
        assert dict(request.url.params) == {'delete_configurations': 'true', 'delete_volumes': 'false',
                                           'delete_connected_networks': 'true', 'docker_cleanup': 'false'}
        self.apps = [row for row in self.apps if row['uuid'] != path.split('/')[-1]]
        return httpx.Response(200, content=b'ack')


def backend(http):
    return CoolifyRigBackend(enforce_lifecycle.Coolify(http, 'https://fixture.invalid', TOKEN),
        project='fixture-project', server='fixture-server', environment='fixture-test', github_app='fixture-source')


def signed(path, body, *, key=KEY, timestamp=None):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    message = f'{timestamp}\nPOST\n{path}\n'.encode() + body
    return {'X-Lifecycle-Timestamp': timestamp, 'X-Lifecycle-Signature': hmac.new(key.encode(), message, hashlib.sha256).hexdigest(),
            'Content-Type': 'application/json'}


@pytest.mark.asyncio
async def test_profile_reuses_lifecycle_and_preserves_other_room():
    assert issubclass(CoolifyRigBackend, enforce_lifecycle.CoolifyEnforceBackend)
    fake = FakeCoolify()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as http:
        rooms = backend(http)
        first = await rooms.create(plan_create(A))
        second = await rooms.create(plan_create(B))
        assert first['outcome'] == second['outcome'] == 'created'
        assert first['uuid'] != second['uuid']
        assert first['storage_prefix'] != second['storage_prefix']
        assert first['volume'] != second['volume']
        assert first['database_volume'] != second['database_volume']
        assert len(await rooms.list()) == 2
        assert fake.envs[first['uuid']]['RIG_ROOM_TENANT'] == A
        assert fake.envs[second['uuid']]['RIG_ROOM_TENANT'] == B
        assert 'RIG_ROOM_DB_PASSWORD' in first['founder_fills']
        assert 'RIG_COOLIFY_TOKEN' not in first['founder_fills']
        assert (await rooms.destroy(plan_destroy(A)))['outcome'] == 'destroyed'
        assert [row['uuid'] for row in await rooms.list()] == [second['uuid']]
        assert (await rooms.destroy(plan_destroy(A)))['outcome'] == 'absent'
        # Same prefix is insufficient provenance for destruction.
        fake.apps[0]['description'] = 'not-our-resource'
        with pytest.raises(enforce_lifecycle.Refused):
            await rooms.destroy(plan_destroy(B))
    assert TOKEN not in json.dumps([first, second])


@pytest.mark.asyncio
async def test_signed_room_requests_reject_other_keys_replays_and_changed_bodies(monkeypatch):
    fake = FakeCoolify()
    for name in SETTINGS:
        monkeypatch.setenv(name, 'fixture-setting')
    monkeypatch.setenv('RIG_LIFECYCLE_KEY', KEY)
    monkeypatch.setenv('AUTUMBRA_LIFECYCLE_KEY', 'fixture-autumbra-key')
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as coolify:
        monkeypatch.setattr(CoolifyRigBackend, 'from_env', classmethod(lambda cls, http: backend(coolify)))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url='http://fixture') as client:
            path = '/rig/rooms/create'
            body = json.dumps({'tenant_id': A}).encode()
            for headers, content in [({}, body), (signed(path, body, key='fixture-autumbra-key'), body),
                                     (signed(path, body, timestamp=0), body),
                                     (signed(path, body), json.dumps({'tenant_id': B}).encode())]:
                assert (await client.post(path, content=content, headers=headers)).status_code == 401
            assert not fake.calls
            response = await client.post(path, content=body, headers=signed(path, body))
            assert response.status_code == 200 and response.json()['receipt']['outcome'] == 'created'
            # A repeated create never creates a second application.
            assert (await client.post(path, content=body, headers=signed(path, body))).status_code == 422
            monkeypatch.delenv(SETTINGS[0])
            path = '/rig/rooms/list'
            assert (await client.post(path, content=body, headers=signed(path, body))).status_code == 503


@pytest.mark.asyncio
async def test_unknown_mutation_is_not_retried():
    fake = FakeCoolify()
    fake.failure = 'POST'
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        result = await backend(client).create(plan_create(A))
    assert result['outcome'] == 'unknown'
    assert len([call for call in fake.calls if call.method == 'POST']) == 1


def test_room_template_binding_and_no_privileged_or_shared_data(monkeypatch):
    compose = yaml.safe_load((ROOT / 'agents/rig/docker-compose.room.yml').read_text())
    assert set(compose['services']) == {'room', 'database'}
    assert compose['networks']['private']['internal'] is True
    assert compose['services']['database']['networks'] == ['private']
    for service in compose['services'].values():
        assert not service.get('privileged') and not service.get('ports')
        assert '/var/run/docker.sock' not in str(service)
    control = yaml.safe_load((ROOT / 'agents/ghost/docker-compose.yml').read_text())
    for name in (*SETTINGS, 'RIG_LIFECYCLE_KEY'):
        assert name in control['services']['enforce-lifecycle']['environment']
        assert name not in control['services']['agent-ghost']['environment']
    monkeypatch.setenv('RIG_ROOM_TENANT', A)
    assert api_base() == 'https://rig.tervory.com/v1/rig/rooms/' + A
    require_owner(A)
    with pytest.raises(RigError) as denied:
        require_owner(B)
    assert denied.value.status == 403
    from rigbox.quotes.keys import embed_snippet
    assert 'api-base="' + api_base() + '"' in embed_snippet('rk_pub_fixture')
    monkeypatch.delenv('RIG_ROOM_TENANT')
    assert 'api-base="https://rig.tervory.com"' in embed_snippet('rk_pub_fixture')


@pytest.mark.asyncio
async def test_room_database_binding_is_idempotent_and_cannot_rebind(monkeypatch):
    import asyncpg
    from uuid import UUID, uuid4
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    from rigbox.store import PgStore
    from rigbox.rooms import bind_database
    admin = _admin_url()
    name = 'rig_room_' + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=3)
        try:
            await PgStore(pool).apply_schema()
            monkeypatch.setenv('RIG_ROOM_TENANT', A)
            await bind_database(pool)
            await bind_database(pool)
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO agent_rig.retailers(tenant_id,name,slug) VALUES($1,$2,'fixture')", UUID(A), 'Store A')
                with pytest.raises(asyncpg.CheckViolationError):
                    await conn.execute("INSERT INTO agent_rig.retailers(tenant_id,name,slug) VALUES($1,$2,'fixture')", UUID(B), 'Store B')
                assert await conn.fetchval('SELECT count(*) FROM agent_rig.retailers WHERE tenant_id=$1', UUID(B)) == 0
            monkeypatch.setenv('RIG_ROOM_TENANT', B)
            with pytest.raises(RuntimeError, match='belongs to another store'):
                await bind_database(pool)
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)
