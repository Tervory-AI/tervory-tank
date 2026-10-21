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
    assert 'storage.py' in next(line for line in dockerfile.splitlines() if line.startswith('COPY main.py'))
    assert 'app.include_router(__import__("storage").router)' in (ROOT / 'tank/main.py').read_text()


def test_compose_only_passes_own_pairs_and_boston_backup_is_opt_in():
    root = yaml.safe_load((ROOT / 'docker-compose.yml').read_text())
    keys = lambda env: {name for name in env if name.startswith('R2_')}
    assert keys(root['services']['tank']['environment']) == {
        'R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_UPLOADS', 'R2_SECRET_ACCESS_KEY_UPLOADS'}
    worker = root['services']['r2-backup']
    assert worker['profiles'] == ['r2-backup']
    assert worker['restart'] == 'no'
    assert worker['environment']['TANK_REGION'] == 'us-east'
    assert keys(worker['environment']) == keys(root['services']['tank']['environment']) | {'R2_BACKUP_RECIPIENT'}
    assert worker['networks'] == ['default']
    assert 'r2-backup' not in yaml.safe_load((ROOT / 'docker-compose.za.yml').read_text())['services']
    for room in storage.ROOMS - {'ghost'}:
        for path in (ROOT / 'agents' / room).glob('docker-compose*.yml'):
            box = yaml.safe_load(path.read_text())
            owned = [svc for svc in box['services'].values() if svc.get('environment', {}).get('AGENT_NAME') == room]
            assert owned
            for svc in owned:
                expected = {'R2_ACCOUNT_ID', 'R2_BUCKET', f'R2_ACCESS_KEY_ID_{room.upper()}', f'R2_SECRET_ACCESS_KEY_{room.upper()}'}
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
