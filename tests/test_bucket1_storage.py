"""Offline storage proof; every credential is generated, no live keys or R2 calls."""
import asyncio
from pathlib import Path
import secrets
import sys
import uuid
from urllib.parse import parse_qs
from xml.sax.saxutils import escape

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents' / '_chassis'))
sys.path.insert(0, str(ROOT / 'jobs' / 'train'))
from chassis.storage import PLATFORM_TENANT, ROOMS, Storage, StorageError  # noqa: E402
from chassis.storage_api import storage_router  # noqa: E402
import r2_archive  # noqa: E402
import backup  # noqa: E402


def environment(owner='base', **extra):
    return {'R2_ACCOUNT_ID': secrets.token_hex(16),
            f'R2_ACCESS_KEY_ID_{owner.upper()}': secrets.token_hex(16),
            f'R2_SECRET_ACCESS_KEY_{owner.upper()}': secrets.token_hex(32),
            **({'RADIX_EGRESS_PROXY': 'http://egress-proxy:8080'} if owner == 'radix' else {}), **extra}


class Bucket:
    def __init__(self, bucket):
        self.bucket = bucket
        self.data = {}
        self.calls = []

    def handle(self, request):
        self.calls.append(request)
        assert request.url.path.split('/')[1] == self.bucket
        assert request.url.scheme == 'https'
        assert 'authorization' in request.headers
        assert 'x-amz-content-sha256' in request.headers
        assert request.url.userinfo == b''
        key = request.url.path.split('/', 2)[2] if request.url.path.count('/') > 1 else ''
        if request.method == 'PUT':
            self.data[key] = request.content
            return httpx.Response(200)
        if key:
            return httpx.Response(200, content=self.data[key])
        params = parse_qs(request.url.query.decode(), keep_blank_values=True)
        prefix = params['prefix'][0]
        body = ''.join(f'<Contents><Key>{escape(k)}</Key><Size>{len(v)}</Size></Contents>'
                       for k, v in self.data.items() if k.startswith(prefix))
        return httpx.Response(200, text=f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{body}<IsTruncated>false</IsTruncated></ListBucketResult>')


@pytest.mark.parametrize('owner', sorted(ROOMS | {'uploads'}))
def test_own_bucket_write_read_and_usage(owner):
    async def scenario():
        bucket = Bucket('tervory-' + owner.replace('_', '-'))
        store = Storage(owner, environ=environment(owner), transport=httpx.MockTransport(bucket.handle))
        tenant = str(uuid.uuid4())
        key = await store.put(tenant, 'screenshots', 'page.png', b'public picture')
        assert await store.get(tenant, 'screenshots', 'page.png') == b'public picture'
        assert (await store.objects(tenant, 'screenshots')) == [{'key': key, 'size_bytes': 14}]
        assert await store.objects(str(uuid.uuid4()), 'screenshots') == []
        usage = await store.usage()
        assert usage['used_bytes'] == 14
        assert usage['reference_capacity_bytes'] == 10**12
        assert usage['objects'] == 1
        await store.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('owner', sorted(ROOMS | {'uploads'}))
def test_other_pair_and_missing_keys_refused_before_network(owner):
    wrong = 'tiger' if owner != 'tiger' else 'base'
    with pytest.raises(StorageError, match='missing'):
        Storage(owner, environ=environment(wrong))
    config = environment(owner)
    config.pop(f'R2_SECRET_ACCESS_KEY_{owner.upper()}')
    with pytest.raises(StorageError, match='missing'):
        Storage(owner, environ=config)
    with pytest.raises(StorageError, match='match'):
        Storage(owner, environ=environment(owner, R2_BUCKET='tervory-foreign'))
    with pytest.raises(StorageError, match='match'):
        Storage(owner, environ=environment(owner, AGENT_NAME=wrong))


def test_tank_reads_only_uploads_pair():
    class Tracked(dict):
        def get(self, key, *args):
            reads.append(key)
            return super().get(key, *args)
    reads = []
    env = Tracked(environment('uploads'))
    async def scenario():
        store = Storage('uploads', environ=env)
        await store.close()
    asyncio.run(scenario())
    assert [key for key in reads if key.startswith('R2_ACCESS_KEY_ID_')] == ['R2_ACCESS_KEY_ID_UPLOADS']
    assert [key for key in reads if key.startswith('R2_SECRET_ACCESS_KEY_')] == ['R2_SECRET_ACCESS_KEY_UPLOADS']


@pytest.mark.parametrize('name', ['../foreign', '/tervory-other', 'a//b', 'https://foreign', 'a/../b', 'a?x', 'a%2fb', 'a\\b'])
def test_object_cannot_escape_prefix(name):
    async def scenario():
        bucket = Bucket('tervory-base')
        store = Storage('base', environ=environment(), transport=httpx.MockTransport(bucket.handle))
        with pytest.raises(StorageError):
            await store.put(PLATFORM_TENANT, 'datasets', name, b'public data')
        assert bucket.calls == []
        await store.close()
    asyncio.run(scenario())


def test_za_refuses_client_data_before_network():
    async def scenario():
        bucket = Bucket('tervory-zenas-za')
        env = environment('zenas', TANK_REGION='za', R2_BUCKET_ZENAS_ZA='tervory-zenas-za',
                          R2_BUCKET='tervory-zenas-za')
        store = Storage('zenas', environ=env, transport=httpx.MockTransport(bucket.handle))
        with pytest.raises(StorageError, match='ZA client data'):
            await store.put(PLATFORM_TENANT, 'backups', 'dump.age', b'encrypted')
        with pytest.raises(StorageError, match='ZA client data'):
            await store.put(str(uuid.uuid4()), 'datasets', 'judgment.pdf', b'client', public=True)
        assert not bucket.calls
        await store.put(PLATFORM_TENANT, 'datasets', 'judgment.pdf', b'public judgment', public=True)
        await store.close()
    asyncio.run(scenario())


def test_za_zenas_requires_region_bucket_name():
    with pytest.raises(StorageError, match='R2_BUCKET_ZENAS_ZA is required'):
        Storage('zenas', environ=environment('zenas', TANK_REGION='za'))
    with pytest.raises(StorageError, match='must be tervory-zenas-za'):
        Storage('zenas', environ=environment(
            'zenas', TANK_REGION='za', R2_BUCKET_ZENAS_ZA='tervory-zenas',
            R2_BUCKET='tervory-zenas'))
    with pytest.raises(StorageError, match='only valid for ZA Zenas'):
        Storage('zenas', environ=environment(
            'zenas', R2_BUCKET_ZENAS_ZA='tervory-zenas-za',
            R2_BUCKET='tervory-zenas-za'))
    store = Storage('zenas', environ=environment(
        'zenas', TANK_REGION='za', R2_BUCKET_ZENAS_ZA='tervory-zenas-za',
        R2_BUCKET='tervory-zenas-za'))
    assert store.bucket == 'tervory-zenas-za'
    us = Storage('zenas', environ=environment('zenas', R2_BUCKET='tervory-zenas'))
    assert us.bucket == 'tervory-zenas'


def test_za_zenas_backup_writes_public_platform_prefix(monkeypatch):
    bucket = Bucket('tervory-zenas-za')
    env = environment(
        'zenas', TANK_REGION='za', AGENT_NAME='zenas',
        R2_BUCKET_ZENAS_ZA='tervory-zenas-za', R2_BUCKET='tervory-zenas-za')
    monkeypatch.setenv('TANK_REGION', 'za')
    monkeypatch.setattr(
        backup, 'Storage',
        lambda owner: Storage(owner, environ=env, transport=httpx.MockTransport(bucket.handle)))

    async def encrypt(path):
        path.write_bytes(b'age-encryption.org/v1\nencrypted za fixture')

    monkeypatch.setattr(backup, 'encrypted_dump', encrypt)
    result = asyncio.run(backup.backup_once('zenas'))
    assert result['bucket'] == 'tervory-zenas-za'
    assert result['key'].startswith(f'za/{PLATFORM_TENANT}/backups/')
    assert '/database.dump.age/' in result['key']
    assert bucket.calls[-1].method == 'GET'


def test_zenas_backup_refused_outside_za(monkeypatch):
    monkeypatch.delenv('TANK_REGION', raising=False)
    with pytest.raises(StorageError, match='TANK_REGION=za'):
        asyncio.run(backup.backup_once('zenas'))


def test_usage_paginates_and_never_reports_partial_total():
    async def scenario():
        calls = []
        def handle(request):
            calls.append(request)
            page = len(calls)
            if page == 1:
                return httpx.Response(200, text='<ListBucketResult><Contents><Key>a</Key><Size>7</Size></Contents><IsTruncated>true</IsTruncated><NextContinuationToken>a+b/=</NextContinuationToken></ListBucketResult>')
            assert parse_qs(request.url.query.decode())['continuation-token'] == ['a+b/=']
            return httpx.Response(200, text='<ListBucketResult><Contents><Key>b</Key><Size>11</Size></Contents><IsTruncated>false</IsTruncated></ListBucketResult>')
        store = Storage('base', environ=environment(), transport=httpx.MockTransport(handle))
        assert (await store.usage())['used_bytes'] == 18
        await store.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('status', [301, 307, 403, 500])
def test_error_and_redirect_are_sanitized(status):
    async def scenario():
        calls = []
        config = environment()
        def handle(request):
            calls.append(request)
            return httpx.Response(status, text=config['R2_SECRET_ACCESS_KEY_BASE'], headers={'location': 'https://evil.example'})
        store = Storage('base', environ=config, transport=httpx.MockTransport(handle))
        with pytest.raises(StorageError) as caught:
            await store.usage()
        assert config['R2_SECRET_ACCESS_KEY_BASE'] not in str(caught.value)
        assert len(calls) == 1
        await store.close()
    asyncio.run(scenario())


def test_room_api_auth_and_missing_configuration(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    for key in ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_BASE', 'R2_SECRET_ACCESS_KEY_BASE'):
        monkeypatch.delenv(key, raising=False)
    room_key = secrets.token_hex(24)
    monkeypatch.setenv('TANK_KEY', room_key)
    app = FastAPI()
    app.include_router(storage_router('base'))
    client = TestClient(app)
    assert client.get('/storage/usage').status_code == 404
    assert client.get('/storage/usage', headers={'X-Tank-Key': room_key}).status_code == 503
    response = client.put('/storage/objects/work/page.html', params={'tenant_id': PLATFORM_TENANT}, content=b'public file', headers={'X-Tank-Key': room_key})
    assert response.status_code == 503


def test_archive_chunks_then_lists_dated_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(r2_archive, 'MAX_OBJECT_BYTES', 4)
    source = tmp_path / 'public.jsonl'
    source.write_bytes(b'public data')
    async def scenario():
        bucket = Bucket('tervory-base')
        store = Storage('base', environ=environment(), transport=httpx.MockTransport(bucket.handle))
        result = await r2_archive.archive_file(store, source, 'datasets', tenant_id=PLATFORM_TENANT)
        assert len(result['parts']) == 3
        assert b''.join(bucket.data[f'us-east/{PLATFORM_TENANT}/datasets/'+p['name']] for p in result['parts']) == source.read_bytes()
        assert result['key'].endswith('/manifest.json')
        assert bucket.calls[-1].method == 'GET'
        assert result['size_bytes'] == 11
        await store.close()
    asyncio.run(scenario())


def test_backup_writes_and_lists_only_encrypted_dated_objects(monkeypatch):
    bucket = Bucket('tervory-uploads')
    paths = []
    monkeypatch.setattr(backup, 'Storage', lambda owner: Storage(owner, environ=environment(owner), transport=httpx.MockTransport(bucket.handle)))
    async def encrypt(path):
        paths.append(path)
        path.write_bytes(b'age-encryption.org/v1\nencrypted fixture')
    monkeypatch.setattr(backup, 'encrypted_dump', encrypt)
    result = asyncio.run(backup.backup_once())
    assert '/backups/' in result['key']
    assert '/database.dump.age/' in result['key']
    assert bucket.calls[-1].method == 'GET'
    assert not paths[0].exists()
    assert all(b'age-encryption.org/v1' in data for key, data in bucket.data.items() if not key.endswith('manifest.json'))


def test_backup_encryption_failure_uploads_nothing(monkeypatch):
    bucket = Bucket('tervory-uploads')
    monkeypatch.setattr(backup, 'Storage', lambda owner: Storage(owner, environ=environment(owner), transport=httpx.MockTransport(bucket.handle)))
    async def fail(path):
        raise StorageError('Encryption failed')
    monkeypatch.setattr(backup, 'encrypted_dump', fail)
    with pytest.raises(StorageError):
        asyncio.run(backup.backup_once())
    assert not bucket.calls


def test_backup_missing_pair_never_dumps(monkeypatch):
    monkeypatch.setattr(backup, 'Storage', lambda owner: Storage(owner, environ={}))
    async def fail(path):
        pytest.fail('dump must not start')
    monkeypatch.setattr(backup, 'encrypted_dump', fail)
    with pytest.raises(StorageError):
        asyncio.run(backup.backup_once())


def test_tank_adapter_only_has_uploads_credentials():
    import importlib.util
    spec = importlib.util.spec_from_file_location('bucket1_tank_storage', ROOT / 'tank/storage.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Tracked(dict):
        def get(self, key, *args):
            reads.append(key)
            return super().get(key, *args)
    reads = []
    env = Tracked(environment('uploads'))
    async def scenario():
        store = module.uploads(environ=env)
        await store.close()
        with pytest.raises(module.StorageError, match='only UPLOADS'):
            module.Storage('ghost', environ=env)
    asyncio.run(scenario())
    assert [key for key in reads if key.startswith('R2_ACCESS_KEY_ID_')] == ['R2_ACCESS_KEY_ID_UPLOADS']
    assert [key for key in reads if key.startswith('R2_SECRET_ACCESS_KEY_')] == ['R2_SECRET_ACCESS_KEY_UPLOADS']


def test_archive_restore_checks_hashes_before_replacing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(r2_archive, 'MAX_OBJECT_BYTES', 4)
    source = tmp_path / 'public.data'
    source.write_bytes(b'public archive')
    target = tmp_path / 'restored.data'
    async def scenario():
        bucket = Bucket('tervory-base')
        store = Storage('base', environ=environment(), transport=httpx.MockTransport(bucket.handle))
        archived = await r2_archive.archive_file(store, source, 'datasets', tenant_id=PLATFORM_TENANT)
        prefix = f'us-east/{PLATFORM_TENANT}/datasets/'
        name = archived['key'].removeprefix(prefix)
        await r2_archive.restore_archive(store, name, target, 'datasets', tenant_id=PLATFORM_TENANT)
        assert target.read_bytes() == source.read_bytes()
        bucket.data[prefix + archived['parts'][0]['name']] = b'corrupt'
        with pytest.raises(StorageError, match='integrity'):
            await r2_archive.restore_archive(store, name, target, 'datasets', tenant_id=PLATFORM_TENANT)
        assert target.read_bytes() == source.read_bytes()
        assert sorted(p.name for p in tmp_path.iterdir()) == ['public.data', 'restored.data']
        await store.close()
    asyncio.run(scenario())


def test_training_room_command_archives_without_hf(tmp_path, monkeypatch):
    import importlib.util
    import json
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('bucket1_export', ROOT / 'jobs/train/export_snapshot.py')
    export = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export)
    source = tmp_path / 'training.jsonl'
    source.write_text(json.dumps({'public': True, 'client_matter': False, 'scope': 'platform',
                     'region': 'us-east', 'holdout': False, 'active': True, 'task_type': 'base.test',
                     'input': {'public': 'example'}, 'output': {'ok': True}}) + '\n')
    bucket = Bucket('tervory-base')
    monkeypatch.setattr(export, 'Storage', lambda room: Storage(room, environ=environment(room), transport=httpx.MockTransport(bucket.handle)))
    def no_hf(*args, **kwargs):
        pytest.fail('A room archive must never use Hugging Face')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(HfApi=no_hf))
    monkeypatch.delenv('HF_TOKEN', raising=False)
    monkeypatch.delenv('HF_ORG', raising=False)
    result = asyncio.run(export.export('base', source, '2026-10-21'))
    assert result['key'].endswith('manifest.json')
    archived = b''.join(value for key, value in bucket.data.items() if not key.endswith('manifest.json'))
    assert archived == source.read_bytes()
    def unavailable(room):
        raise StorageError('Missing storage credentials')
    monkeypatch.setattr(export, 'Storage', unavailable)
    with pytest.raises(StorageError):
        asyncio.run(export.export('base', source, '2026-10-21'))


@pytest.mark.parametrize('owner', sorted(ROOMS | {'uploads'}))
@pytest.mark.parametrize('prefix', ['R2_ACCESS_KEY_ID_', 'R2_SECRET_ACCESS_KEY_'])
def test_foreign_credential_presence_refused_before_http(owner, prefix, monkeypatch):
    wrong = 'TIGER' if owner != 'tiger' else 'BASE'
    env = environment(owner, **{prefix + wrong: ''})
    def no_http(**kwargs):
        pytest.fail('Mixed credential owners must fail before constructing HTTP')
    monkeypatch.setattr(httpx, 'AsyncClient', no_http)
    with pytest.raises(StorageError, match='Foreign R2 credentials'):
        Storage(owner, environ=env)


def test_missing_backup_recipient_does_not_start_process_or_create_file(tmp_path, monkeypatch):
    monkeypatch.delenv('R2_BACKUP_RECIPIENT', raising=False)
    async def no_process(*args, **kwargs):
        pytest.fail('process must not start')
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', no_process)
    output = tmp_path / 'database.age'
    with pytest.raises(StorageError, match='recipient'):
        asyncio.run(backup.encrypted_dump(output))
    assert not output.exists()


def test_backup_children_receive_only_needed_credentials(monkeypatch):
    generated_credential = secrets.token_hex(16)
    monkeypatch.setenv('DATABASE_URL', f'postgresql://agent_base:{generated_credential}@postgres:5432/tervory')
    monkeypatch.setenv('R2_SECRET_ACCESS_KEY_BASE', secrets.token_hex(32))
    monkeypatch.setenv('HF_TOKEN', secrets.token_hex(32))
    monkeypatch.setenv('TANK_KEY', secrets.token_hex(32))
    env = backup.backup_environment()
    assert env['PGPASSWORD'] == generated_credential
    assert env['PGHOST'] == 'postgres'
    assert not ({'DATABASE_URL', 'R2_SECRET_ACCESS_KEY_BASE', 'HF_TOKEN', 'TANK_KEY'} & env.keys())
    assert not any(key.startswith('PG') for key in backup.tool_environment())


def test_storage_destination_cannot_be_reassigned():
    async def scenario():
        store = Storage('base', environ=environment())
        for field in ('bucket', 'host', 'owner'):
            with pytest.raises(AttributeError):
                setattr(store, field, 'foreign')
        await store.close()
    asyncio.run(scenario())


def test_qdrant_configuration_requires_internal_url_and_recipient(monkeypatch):
    monkeypatch.setenv('R2_BACKUP_RECIPIENT', 'age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p')
    monkeypatch.setenv('QDRANT_URL', 'http://qdrant:6333')
    monkeypatch.setenv('QDRANT_API_KEY', 'fixture-key')
    monkeypatch.setattr(backup.shutil, 'which', lambda name: '/usr/bin/' + name)
    assert backup.qdrant_configuration()[0] == 'http://qdrant:6333'
    monkeypatch.setenv('QDRANT_URL', 'https://evil.example/qdrant')
    with pytest.raises(StorageError, match='QDRANT_URL'):
        backup.qdrant_configuration()
    monkeypatch.setenv('QDRANT_URL', 'http://qdrant:6333')
    monkeypatch.delenv('QDRANT_API_KEY')
    with pytest.raises(StorageError, match='QDRANT_API_KEY'):
        backup.qdrant_configuration()


def test_qdrant_backup_writes_encrypted_dated_objects(monkeypatch, tmp_path):
    bucket = Bucket('tervory-uploads')
    monkeypatch.setenv('R2_BACKUP_RECIPIENT', 'age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p')
    monkeypatch.setenv('QDRANT_URL', 'http://qdrant:6333')
    monkeypatch.setenv('QDRANT_API_KEY', 'fixture-key')
    monkeypatch.setattr(backup.shutil, 'which', lambda name: '/usr/bin/' + name)
    monkeypatch.setattr(backup, 'Storage', lambda owner: Storage(owner, environ=environment(owner), transport=httpx.MockTransport(bucket.handle)))

    async def encrypt(collection, path):
        assert collection == 'mem_zenas'
        path.write_bytes(b'age-encryption.org/v1\nqdrant fixture')

    monkeypatch.setattr(backup, 'encrypted_qdrant_snapshot', encrypt)

    async def collections():
        return ['mem_zenas']

    monkeypatch.setattr(backup, 'list_qdrant_collections', collections)
    results = asyncio.run(backup.qdrant_backup_once())
    assert len(results) == 1
    assert results[0]['collection'] == 'mem_zenas'
    assert '/backups/' in results[0]['key']
    assert '/qdrant/mem_zenas.snapshot.age/' in results[0]['key']
    assert results[0]['size_bytes'] > 0
    assert all(b'age-encryption.org/v1' in data for key, data in bucket.data.items() if not key.endswith('manifest.json'))


def test_qdrant_backup_failure_uploads_nothing(monkeypatch):
    bucket = Bucket('tervory-uploads')
    monkeypatch.setenv('R2_BACKUP_RECIPIENT', 'age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p')
    monkeypatch.setenv('QDRANT_URL', 'http://qdrant:6333')
    monkeypatch.setenv('QDRANT_API_KEY', 'fixture-key')
    monkeypatch.setattr(backup.shutil, 'which', lambda name: '/usr/bin/' + name)
    monkeypatch.setattr(backup, 'Storage', lambda owner: Storage(owner, environ=environment(owner), transport=httpx.MockTransport(bucket.handle)))

    async def collections():
        return ['mem_zenas']

    async def fail(collection, path):
        raise StorageError('Qdrant snapshot encryption failed')

    monkeypatch.setattr(backup, 'list_qdrant_collections', collections)
    monkeypatch.setattr(backup, 'encrypted_qdrant_snapshot', fail)
    with pytest.raises(StorageError):
        asyncio.run(backup.qdrant_backup_once())
    assert not bucket.data


def test_compose_r2_backup_depends_on_qdrant():
    import yaml
    worker = yaml.safe_load((ROOT / 'docker-compose.yml').read_text())['services']['r2-backup']
    assert worker['environment']['QDRANT_URL'] == 'http://qdrant:6333'
    assert worker['environment']['QDRANT_API_KEY'] == '${QDRANT_API_KEY}'
    assert worker['depends_on']['qdrant']['condition'] == 'service_healthy'
    assert 'qdrant_configuration' in worker['healthcheck']['test'][-1]
