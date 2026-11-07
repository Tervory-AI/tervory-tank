"""Real storage signing, scheduled job dispatch and receipts with offline services."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from agents.tisan import archive, scaffold
from chassis.storage import Storage as SignedStorage, StorageError
from chassis.memory import MemoryClient
from chassis.db import ensure_schema, ensure_schedules
from chassis.worker import enqueue_due
from test_command import command_pool as command_pool
from test_tisan_publish import build, TENANT, OTHER


def wire_storage(monkeypatch, module=archive, *, changed=False, missing=False):
    settings = {'AGENT_NAME':'tisan', 'TANK_REGION':'us-east', 'R2_ACCOUNT_ID':'0'*32,
                'R2_ACCESS_KEY_ID_TISAN':'placeholder', 'R2_SECRET_ACCESS_KEY_TISAN':'placeholder'}
    if missing:
        settings.pop('R2_SECRET_ACCESS_KEY_TISAN')
    objects, calls = {}, []
    def request(req):
        assert req.url.host == '0'*32 + '.r2.cloudflarestorage.com'
        assert req.headers.get('authorization', '').startswith('AWS4-HMAC-SHA256 ')
        assert req.headers['x-amz-content-sha256'] == hashlib.sha256(req.content).hexdigest()
        calls.append((req.method, req.url.path))
        if req.method == 'PUT':
            objects[req.url.path] = req.content
            return httpx.Response(200)
        assert req.method == 'GET'
        return httpx.Response(200, content=b'placeholder changed' if changed else objects[req.url.path])
    def factory(owner):
        assert owner == 'tisan'
        return SignedStorage(owner, environ=settings, transport=httpx.MockTransport(request))
    monkeypatch.setattr(module, 'Storage', factory)
    return objects, calls


@pytest.mark.asyncio
async def test_private_archive_roundtrip_and_retry_use_signed_immutable_keys(tmp_path, monkeypatch):
    build(tmp_path)
    objects, calls = wire_storage(monkeypatch)
    records = []
    def remember(req):
        assert req.url.path == '/memories'
        payload = json.loads(req.content)
        records.append(payload)
        return httpx.Response(201, json={'id':payload['id'], 'seen':len(records)})
    async with httpx.AsyncClient(transport=httpx.MockTransport(remember)) as http:
        memory = MemoryClient('http://placeholder-hermes', 'placeholder', 'tisan', http, user_id='placeholder-user')
        first = await archive.export(TENANT, {'slug':'site','build':1}, root=tmp_path, memory=memory)
        again = await archive.export(TENANT, {'slug':'site','build':1}, root=tmp_path, memory=memory)
    assert first['ok'] and first['public'] is False
    assert first['objects'] == again['objects'] and len(objects) == 2
    assert first['memory_id'] == again['memory_id']
    assert len(calls) == 8 and all(p.startswith('/tervory-tisan/us-east/'+TENANT+'/work/builds/site/') for _,p in calls)
    raw = (tmp_path/'builds'/TENANT/'site/1.tar.gz').read_bytes()
    assert first['archive_sha256'] == hashlib.sha256(raw).hexdigest()
    receipt = json.loads((tmp_path/'builds'/TENANT/'site/1.archive.json').read_text())
    assert receipt['archive_sha256'] == first['archive_sha256']
    assert datetime.fromisoformat(receipt['recorded_at']).tzinfo is not None
    assert all(row['tenant_id'] == TENANT and row['kind']=='build' and row['index'] is False for row in records)
    assert records[0]['id'] == records[1]['id']


@pytest.mark.asyncio
async def test_corrupt_provider_readback_never_creates_a_success_receipt(tmp_path, monkeypatch):
    build(tmp_path)
    wire_storage(monkeypatch, changed=True)
    memory = SimpleNamespace(remember=AsyncMock())
    with pytest.raises(StorageError):
        await archive.export(TENANT, {'slug':'site','build':1}, root=tmp_path, memory=memory)
    assert not (tmp_path/'builds'/TENANT/'site/1.archive.json').exists()
    memory.remember.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_storage_binding_makes_no_outbound_request(tmp_path, monkeypatch):
    build(tmp_path)
    _, calls = wire_storage(monkeypatch, missing=True)
    with pytest.raises(StorageError, match='TISAN'):
        await archive.export(TENANT, {'slug':'site','build':1}, root=tmp_path)
    assert calls == []
    assert not (tmp_path/'builds'/TENANT/'site/1.archive.json').exists()


@pytest.mark.asyncio
async def test_failed_or_foreign_scan_receipt_never_reaches_storage(tmp_path, monkeypatch):
    build(tmp_path)
    _, calls = wire_storage(monkeypatch)
    with pytest.raises((ValueError, OSError)):
        await archive.export(OTHER, {'slug':'site','build':1}, root=tmp_path)
    file = tmp_path/'builds'/TENANT/'site/1.json'
    manifest = json.loads(file.read_text())
    manifest['checks'][-1]['critical'] = 1
    file.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='repo scan required'):
        await archive.export(TENANT, {'slug':'site','build':1}, root=tmp_path)
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [
    {'slug':'../site','build':1}, {'slug':'site','build':True},
    {'slug':'site','build':1,'bucket':'tervory-rig'}, {'slug':'site','build':1,'tenant_id':OTHER},
])
async def test_archive_input_cannot_override_owner_or_select_ambiguous_build(tmp_path, monkeypatch, payload):
    _, calls = wire_storage(monkeypatch)
    with pytest.raises(ValueError):
        await archive.export(TENANT, payload, root=tmp_path)
    assert calls == []


@pytest.mark.asyncio
async def test_archive_job_uses_the_same_room_handler_and_survives_memory_outage(tmp_path, monkeypatch):
    from agents.tisan import app as room
    build(tmp_path)
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    module = room._load_beside(room._figma_cache(), 'tisan_archive', 'archive.py')
    wire_storage(monkeypatch, module)
    memory = SimpleNamespace(remember=AsyncMock(side_effect=RuntimeError('placeholder private error')))
    ctx = SimpleNamespace(tenant_id=TENANT, job_id=str(uuid4()), input={'slug':'site','build':1}, memory=memory)
    result = await room.app.state.handlers['archive'](ctx)
    assert result['ok'] and result['memory'] == 'unreachable'
    assert 'placeholder private error' not in json.dumps(result)
    assert room.app.state.job_timeouts['archive'] == room.SCAFFOLD_TIMEOUT_S
    saved = json.loads((tmp_path/'builds'/TENANT/'site/1.archive.json').read_text())
    assert saved == result


@pytest.mark.asyncio
async def test_saturday_heartbeat_enqueues_once_per_slot_and_writes_private_receipt(command_pool):
    from agents.tisan import app as room
    async with command_pool.acquire() as conn:
        schema = await ensure_schema(conn, 'tisan')
        await ensure_schedules(conn, schema, room.app.state.schedules)
        clock = datetime(2026,11,7,0,0,tzinfo=timezone.utc)
        await enqueue_due(conn, 'tisan', clock, room.app.state.job_timeouts)
        await enqueue_due(conn, 'tisan', clock+timedelta(seconds=30), room.app.state.job_timeouts)
        jobs = await conn.fetch("SELECT * FROM agent_tisan.jobs WHERE kind='ping'")
        assert len(jobs) == 1 and str(jobs[0]['tenant_id']) == room.HEARTBEAT_TENANT
        job = jobs[0]
        await enqueue_due(conn, 'tisan', clock+timedelta(minutes=5), room.app.state.job_timeouts)
        assert await conn.fetchval("SELECT count(*) FROM agent_tisan.jobs WHERE kind='ping'") == 2
    recorded = []
    def remember(req):
        body = json.loads(req.content)
        recorded.append(body)
        return httpx.Response(201,json={'id':str(uuid4()),'seen':len(recorded)})
    async with httpx.AsyncClient(transport=httpx.MockTransport(remember)) as http:
        memory = MemoryClient('http://placeholder-hermes','placeholder','tisan',http)
        tank = SimpleNamespace(route=AsyncMock(side_effect=AssertionError('model call forbidden')))
        ctx = SimpleNamespace(agent='tisan',tenant_id=str(job['tenant_id']),job_id=str(job['id']),
                              input=json.loads(job['input']) if isinstance(job['input'],str) else job['input'],memory=memory,tank=tank)
        result = await room.ping(ctx)
        assert result['heartbeats_seen'] == 1
        tank.route.assert_not_awaited()
    assert recorded[0]['tenant_id'] == room.HEARTBEAT_TENANT
    assert recorded[0]['kind'] == 'heartbeat' and recorded[0]['source'] == 'schedule:*/5'
    assert recorded[0]['index'] is False


def test_production_environment_installs_the_locked_dev_toolchain_offline(tmp_path, monkeypatch):
    template = Path(__file__).resolve().parents[1]/'agents/tisan/templates/next-site'
    for name in ['package.json','package-lock.json']:
        shutil.copy2(template/name, tmp_path/name)
    monkeypatch.setenv('TISAN_NPM_OFFLINE','1')
    env = {**os.environ,'NODE_ENV':'production','PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD':'1'}
    install = subprocess.run(scaffold._npm_ci_args(), cwd=tmp_path, env=env, text=True,capture_output=True,timeout=120)
    assert install.returncode == 0, install.stdout + install.stderr
    compiler = subprocess.run(['node','-e','console.log(require("typescript/package.json").version)'],
                             cwd=tmp_path,env=env,text=True,capture_output=True,timeout=10)
    assert compiler.returncode == 0, compiler.stderr
    assert compiler.stdout.strip() == json.loads((template/'package.json').read_text())['devDependencies']['typescript']


def test_archive_cli_imports_in_the_flat_room_layout(tmp_path):
    root = Path(__file__).resolve().parents[1]
    for name in ['archive.py','publish.py','repo_scan.py','storage.py']:
        shutil.copy2(root/'agents/tisan'/name,tmp_path/name)
    shutil.copytree(root/'agents/_chassis/chassis',tmp_path/'chassis')
    import sys
    code = 'import sys;sys.path.insert(0,sys.argv[1]);import archive;sys.argv=["archive.py","--help"];archive.main()'
    result = subprocess.run([sys.executable,'-I','-c',code,str(tmp_path)],cwd=tmp_path,
                            capture_output=True,text=True,timeout=10)
    assert result.returncode == 0, result.stderr
    assert '--tenant' in result.stdout and '--build' in result.stdout
    assert 'agents/tisan/archive.py' in (root/'agents/tisan/Dockerfile').read_text()
