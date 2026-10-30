"""Tank/room wiring and unchanged training exports; no live service calls."""
import ast
import asyncio
import base64
import inspect
import json
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import yaml
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tank'))
sys.path.insert(0, str(ROOT / 'agents/_chassis'))
import storage  # noqa: E402
import training  # noqa: E402
from chassis import storage as chassis_storage  # noqa: E402
from chassis.storage_api import storage_router  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def test_s3_protocol_parity_between_isolated_build_contexts():
    for method in ('_sign', '_prefix', '_request', 'put', 'get', '_objects', 'objects', 'usage'):
        assert inspect.getsource(getattr(storage.Storage, method)) == inspect.getsource(getattr(chassis_storage.Storage, method))


def test_tank_storage_imports_without_chassis():
    imports = [node.module for node in ast.walk(ast.parse((ROOT / 'tank/storage.py').read_text())) if isinstance(node, ast.ImportFrom)]
    assert not any(name and name.startswith('chassis') for name in imports)
    dockerfile = (ROOT / 'tank/Dockerfile').read_text()
    assert (ROOT / 'tank/storage.py').is_file()
    assert '*.py' in next(line for line in dockerfile.splitlines() if line.startswith('COPY ') and '*.py' in line).split()
    assert 'app.include_router(__import__("storage").router)' in (ROOT / 'tank/main.py').read_text()


def test_compose_only_passes_own_pairs_and_boston_backup_is_persistent():
    root = yaml.safe_load((ROOT / 'docker-compose.yml').read_text())
    keys = lambda env: {name for name in env if name.startswith('R2_')}
    assert keys(root['services']['tank']['environment']) == {
        'R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_UPLOADS', 'R2_SECRET_ACCESS_KEY_UPLOADS'}
    worker = root['services']['r2-backup']
    assert not worker.get('profiles')
    assert worker['restart'] == 'unless-stopped'
    assert worker['environment']['TANK_REGION'] == 'us-east'
    assert keys(worker['environment']) == keys(root['services']['tank']['environment']) | {'R2_BACKUP_RECIPIENT'}
    assert worker['networks'] == ['default']
    za_root = yaml.safe_load((ROOT / 'docker-compose.za.yml').read_text())
    assert 'r2-backup' not in za_root['services']
    za_worker = za_root['services']['r2-backup-za']
    assert za_worker['profiles'] == ['r2-backup-za']
    assert za_worker['restart'] == 'no'
    assert za_worker['environment']['TANK_REGION'] == 'za'
    assert za_worker['environment']['AGENT_NAME'] == 'zenas'
    assert za_worker['environment']['R2_BUCKET'] == '${R2_BUCKET_ZENAS_ZA:-}'
    assert za_worker['environment']['R2_BUCKET_ZENAS_ZA'] == '${R2_BUCKET_ZENAS_ZA:-}'
    assert keys(za_worker['environment']) == {
        'R2_ACCOUNT_ID', 'R2_BUCKET', 'R2_BUCKET_ZENAS_ZA',
        'R2_ACCESS_KEY_ID_ZENAS', 'R2_SECRET_ACCESS_KEY_ZENAS', 'R2_BACKUP_RECIPIENT'}
    assert za_worker['command'] == [
        'python', 'jobs/train/backup.py', '--owner', 'zenas', '--nightly']
    for room in storage.ROOMS - {'ghost'}:
        for path in (ROOT / 'agents' / room).glob('docker-compose*.yml'):
            box = yaml.safe_load(path.read_text())
            owned = [(name, svc) for name, svc in box['services'].items() if svc.get('environment', {}).get('AGENT_NAME') == room]
            assert owned
            for name, svc in owned:
                expected = {'R2_ACCOUNT_ID', 'R2_BUCKET', f'R2_ACCESS_KEY_ID_{room.upper()}', f'R2_SECRET_ACCESS_KEY_{room.upper()}'}
                if room == 'zenas' and svc['environment'].get('TANK_REGION') == 'za':
                    expected = expected | {'R2_BUCKET_ZENAS_ZA'}
                    assert svc['environment']['R2_BUCKET'] == '${R2_BUCKET_ZENAS_ZA:-}'
                    assert svc['environment']['R2_BUCKET_ZENAS_ZA'] == '${R2_BUCKET_ZENAS_ZA:-}'
                else:
                    assert svc['environment']['R2_BUCKET'] == f'tervory-{room.replace("_", "-")}'
                if room == 'zenas' and name == 'docassemble-backup':
                    expected = expected | {'R2_BACKUP_RECIPIENT'}
                assert keys(svc['environment']) == expected
                assert svc['environment']['R2_ACCOUNT_ID'] == '${R2_ACCOUNT_ID:-}'
            if room == 'radix':
                assert keys(box['services']['egress-proxy']['environment']) == {'R2_ACCOUNT_ID'}


def test_usage_auth_errors_and_zero_are_distinct(monkeypatch):
    founder_key = secrets.token_hex(16)
    monkeypatch.setenv('TANK_API_KEY', founder_key)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder-fixture')
    for room in storage.ROOMS:
        monkeypatch.setenv(f'TANK_KEY_{room.upper()}', secrets.token_hex(16))
    class Uploads:
        async def usage(self):
            return {'bucket': 'tervory-uploads', 'used_bytes': 12, 'objects': 1, 'measured_at': '2026-10-21T00:00:00Z'}
        async def close(self):
            pass
    monkeypatch.setattr(storage, 'uploads', Uploads)
    observed = []
    def room(request):
        observed.append(request)
        assert request.headers.get('authorization') is None
        assert request.url.host.startswith('agent-')
        if request.url.host != 'agent-base':
            return httpx.Response(503)
        return httpx.Response(200, json={'bucket': 'tervory-base', 'used_bytes': 0, 'objects': 0, 'measured_at': '2026-10-21T00:00:00Z'})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(storage.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(room), **kwargs))
    app = FastAPI()
    app.include_router(storage.router)
    async def scenario():
        async with real_client(transport=httpx.ASGITransport(app=app), base_url='http://tank') as client:
            assert (await client.get('/v1/admin/storage/usage')).status_code == 404
            assert not observed
            response = await client.get('/v1/admin/storage/usage', headers={'X-Tank-Key': founder_key, 'X-Tervory-Admin': 'founder-fixture'})
            assert response.status_code == 200
            result = response.json()
            assert len(result['buckets']) == 9 and result['complete'] is False
            by_bucket = {row['bucket']: row for row in result['buckets']}
            assert by_bucket['tervory-base']['used_bytes'] == 0
            assert 'used_bytes' not in by_bucket['tervory-ghost']
            assert by_bucket['tervory-ghost']['error']
    run(scenario())


@pytest.mark.parametrize('agent', sorted(storage.ROOMS))
def test_training_archives_through_owner_before_hf_without_changing_payload(monkeypatch, agent):
    monkeypatch.setenv('TANK_REGION', 'us-east')
    room_secret = secrets.token_hex(16)
    monkeypatch.setenv(f'TANK_KEY_{agent.upper()}', room_secret)
    monkeypatch.setattr(training, 'runtime', lambda: SimpleNamespace(box_region=lambda: 'us-east'))
    objects, events = {}, []
    rows = [{'scope': 'platform', 'region': 'us-east', 'public': True, 'client_matter': False,
             'holdout': False, 'active': True, 'input': {'public': 'fixture'}, 'output': {'ok': True}}]
    expected = ('\n'.join(training.encoded(row) for row in rows) + '\n').encode()
    def room(request):
        assert request.url.host == 'agent-' + agent.replace('_', '-')
        assert request.headers['X-Tank-Key'] == room_secret
        assert 'authorization' not in request.headers
        assert request.url.params['tenant_id'] == storage.PLATFORM_TENANT
        assert request.url.params['region'] == 'us-east'
        if request.method == 'PUT':
            events.append('archive')
            objects[request.url.path] = request.content
            return httpx.Response(200)
        events.append('verify')
        return httpx.Response(200, content=objects[request.url.path])
    def hf(request):
        assert events[-1] in {'verify', 'hf'}
        events.append('hf')
        if request.url.path.endswith('/commit/main'):
            payload = json.loads(request.content.splitlines()[1])['value']
            assert base64.b64decode(payload['content']) == expected
            assert payload['path'] == 'snapshots/us-east/2026-10-21.jsonl'
        return httpx.Response(200, json={'private': True})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(storage.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(room), **kwargs))
    async def scenario():
        async with real_client(transport=httpx.MockTransport(hf), headers={'Authorization': 'Bearer ' + secrets.token_hex(16)}) as client:
            await training.upload_dataset(client, 'fixture', agent, '2026-10-21', rows)
    run(scenario())
    assert events == ['archive', 'archive', 'verify', 'hf', 'hf', 'hf']
    assert next(value for path, value in objects.items() if path.endswith('part-000000')) == expected


def test_failed_archive_prevents_all_hf_requests(monkeypatch):
    monkeypatch.setattr(training, 'runtime', lambda: SimpleNamespace(box_region=lambda: 'us-east'))
    monkeypatch.setattr(training, 'archive_training_snapshot', AsyncMock(side_effect=storage.StorageError('Missing pair')))
    async def scenario():
        def no_hf(request):
            pytest.fail('HF must not be called')
        async with httpx.AsyncClient(transport=httpx.MockTransport(no_hf)) as client:
            with pytest.raises(storage.StorageError):
                await training.upload_dataset(client, 'fixture', 'base', '2026-10-21', [])
    run(scenario())


def test_tank_snapshot_uses_only_uploads(monkeypatch):
    monkeypatch.setenv('TANK_REGION', 'us-east')
    values = {}
    class Uploads:
        async def put(self, tenant, category, name, data, **kwargs):
            assert tenant == storage.PLATFORM_TENANT and category == 'training'
            values[name] = data
        async def get(self, tenant, category, name, **kwargs):
            return values[name]
        async def close(self):
            pass
    monkeypatch.setattr(storage, 'uploads', Uploads)
    run(storage.archive_training_snapshot('tank', '2026-10-21', b'public snapshot', region='us-east'))
    assert len(values) == 2


def test_room_refuses_region_mismatch_before_any_request(monkeypatch):
    room_key = secrets.token_hex(16)
    monkeypatch.setenv('TANK_KEY', room_key)
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setenv('R2_ACCOUNT_ID', secrets.token_hex(16))
    monkeypatch.setenv('R2_ACCESS_KEY_ID_ZENAS', secrets.token_hex(16))
    monkeypatch.setenv('R2_SECRET_ACCESS_KEY_ZENAS', secrets.token_hex(32))
    calls = []
    async def put(*args, **kwargs):
        calls.append(args)
    monkeypatch.setattr(chassis_storage.Storage, 'put', put)
    app = FastAPI()
    app.include_router(storage_router('zenas'))
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://room') as client:
            response = await client.put('/storage/objects/training/snapshot.jsonl', content=b'public fixture',
                params={'tenant_id': storage.PLATFORM_TENANT, 'public': 'true', 'region': 'za'}, headers={'X-Tank-Key': room_key})
            assert response.status_code == 409
    run(scenario())
    assert not calls


def test_no_private_identity_in_backup_image_check():
    check = (ROOT / 'jobs/train/check_backup_image.py').read_text()
    assert 'age-keygen' not in check
    assert '--identity' not in check
    assert '--decrypt' not in check
    compose = yaml.safe_load((ROOT / 'docker-compose.yml').read_text())
    worker = compose['services']['r2-backup']
    assert not any('PRIVATE' in key or 'IDENTITY' in key for key in worker['environment'])


def test_backup_nightly_configuration_fails_before_wait(monkeypatch):
    sys.path.insert(0, str(ROOT / 'jobs/train'))
    import backup
    monkeypatch.delenv('R2_ACCOUNT_ID', raising=False)
    async def no_wait(*args):
        pytest.fail('Invalid configuration must fail before sleeping')
    monkeypatch.setattr(asyncio, 'sleep', no_wait)
    with pytest.raises(chassis_storage.StorageError):
        run(backup.main('uploads', True))


@pytest.mark.parametrize('failed_agent', ['base', 'tiger'])
@pytest.mark.parametrize('region', ['us-east', 'za'])
def test_export_storage_failure_isolated_and_retries_only_unfinished_agent(monkeypatch, failed_agent, region):
    from contextlib import asynccontextmanager
    from datetime import date
    import gold
    agents = ['base', 'tiger', 'zenas']
    done, batches, archives, hf_agents = set(), set(), [], []
    unavailable = {failed_agent}
    monkeypatch.setenv('HF_TOKEN', secrets.token_hex(16))
    monkeypatch.setenv('HF_ORG', 'fixture')
    monkeypatch.setattr(gold, 'AGENTS', agents)

    class Connection:
        async def fetchval(self, query, *args):
            if 'pg_try_advisory_lock' in query:
                return True
            if 'training_exports' in query:
                return args[1] in done
            if 'removed_batches' in query:
                return False
            pytest.fail('Unexpected database lookup')
        async def fetch(self, query, *args):
            if 'DISTINCT tenant_id' in query:
                return [{'tenant_id': gold.PLATFORM_TENANT}]
            agent = args[1]
            return [{'tenant_id': gold.PLATFORM_TENANT, 'region': region,
                     'holdout': False, 'active': True, 'public': True, 'client_matter': False,
                     'task_type': agent + '.fixture', 'input': '{}', 'output': '{}',
                     'batch_id': agent + '-batch', 'currency': None, 'unit': None}]
        async def execute(self, query, *args):
            if 'INSERT INTO tank.training_snapshot_batches' in query:
                batches.add(args[3])
            elif 'INSERT INTO tank.training_exports' in query:
                done.add(args[1])
    @asynccontextmanager
    async def acquire():
        yield Connection()
    rt = SimpleNamespace(pool=lambda: SimpleNamespace(acquire=acquire), box_region=lambda: region)
    monkeypatch.setattr(training, 'runtime', lambda: rt)
    async def archive(agent, day, data, **kwargs):
        archives.append(agent)
        if agent in unavailable:
            raise storage.StorageError('Missing storage configuration')
    monkeypatch.setattr(training, 'archive_training_snapshot', archive)
    def hf(request):
        if request.url.path.endswith('/api/repos/create'):
            agent = json.loads(request.content)['name'].removeprefix('tervory-public-')
            assert archives[-1] == agent and agent not in unavailable
            hf_agents.append(agent)
        return httpx.Response(200, json={'private': True})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(hf), **kw))
    async def scenario():
        day = date(2026, 10, 21)
        assert await training.export_once(day=day) == {'status': 'incomplete', 'exported': 2}
        assert done == set(agents) - {failed_agent}
        assert batches == done
        assert hf_agents == [agent for agent in agents if agent != failed_agent]
        assert archives == agents  # Failure never aborts the remaining agents.
        unavailable.clear()
        assert await training.export_once(day=day) == {'status': 'complete', 'exported': 1}
        assert archives == agents + [failed_agent]
        assert done == batches == set(agents)
        assert hf_agents[-1] == failed_agent
    run(scenario())


def test_tank_refuses_foreign_pair_presence(monkeypatch):
    env = {'R2_ACCOUNT_ID': secrets.token_hex(16),
           'R2_ACCESS_KEY_ID_UPLOADS': secrets.token_hex(16),
           'R2_SECRET_ACCESS_KEY_UPLOADS': secrets.token_hex(32),
           'R2_SECRET_ACCESS_KEY_GHOST': ''}
    def no_http(**kwargs):
        pytest.fail('Mixed credentials must fail before HTTP')
    monkeypatch.setattr(httpx, 'AsyncClient', no_http)
    with pytest.raises(storage.StorageError, match='Foreign R2 credentials'):
        storage.uploads(environ=env)
