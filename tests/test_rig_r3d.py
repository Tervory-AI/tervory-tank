"""Live terminal boundaries, recorded HF/CPU conversion and command journeys."""
import asyncio
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from test_rig_3d_engine import rig as rig, job, TENANT, WITHOUT_3D, PUBLIC_KEY, PLAIN_KEY
from test_rig_3d_uploads import files
from rigbox.three_d import command
from rigbox.three_d.assets import R2Assets
from rigbox.three_d.contracts import Review
from rigbox.three_d.forge import BrainForge, add_anchors
from rigbox.three_d.terminal import snapshot, updates
from agents.rig.forge import service as worker
from agents.rig.forge.gpu import GPU, GPUError
from agents.rig.forge.progress import cost
from agents.rig.forge.storage import Storage

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('database_setting', ['', 'postgresql://offline.invalid/forbidden'])
def test_forge_deployed_dry_run_without_database_checkout_or_test_runner(tmp_path, database_setting):
    import shutil
    import sys
    # Match the room image layout: no scripts, tests, Forge binaries or checkout.
    shutil.copytree(ROOT / 'agents/rig/rigbox', tmp_path / 'rigbox',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(ROOT / 'agents/_chassis/chassis', tmp_path / 'chassis',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('english-20k.txt.gz', 'shopping.txt'):
        shutil.copy2(ROOT / 'agents/rig' / name, tmp_path / name)
    env = dict(os.environ, PYTHONPATH=str(tmp_path), PYTHONDONTWRITEBYTECODE='1')
    for name in ('RIG_TEST_DATABASE_URL', 'POOL_SCHEMA_DATABASE_URL', 'DATABASE_URL',
                 'TANK_KEY', 'RIG_AGENT_URL', 'RIG_FORGE_TRELLIS_ENABLED'):
        env.pop(name, None)
    if database_setting:
        env.update({name: database_setting for name in
                    ('RIG_TEST_DATABASE_URL', 'POOL_SCHEMA_DATABASE_URL', 'DATABASE_URL')})
    code = '''
import asyncio, json, runpy, socket, sys
import asyncpg
def forbidden(*args, **kwargs):
    raise AssertionError('Dry run attempted external I/O')
socket.getaddrinfo = socket.socket.connect = socket.socket.connect_ex = forbidden
asyncpg.connect = asyncpg.create_pool = forbidden
sys.argv = ['rig-forge', '--dry-run']
try:
    runpy.run_module('rigbox.three_d.command', run_name='__main__')
except SystemExit as result:
    assert result.code == 0
assert 'pytest' not in sys.modules
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    proof = json.loads(result.stdout)
    assert proof['dry_run'] and 'no database' in proof['source']
    assert [row['photos'] for row in proof['runs']] == [1, 3]
    assert all(row['status'] == 'approved' and row['receipts'] for row in proof['runs'])
    recorded = ROOT / 'tests/fixtures/rig_r3d/approved.glb'
    assert (tmp_path / 'rigbox/three_d/offline/approved.glb').read_bytes() == recorded.read_bytes()
    assert all(row['sha256'] == hashlib.sha256(recorded.read_bytes()).hexdigest() for row in proof['runs'])


@pytest.mark.asyncio
async def test_terminal_day_zero_auth_tenant_and_no_automatic_conversion(rig):
    engine, pool, client, _ = rig
    url = '/v1/rig/3d/terminal'
    assert (await client.get(url)).status_code == 401
    assert (await client.get(url, headers={'X-Rig-Key': PLAIN_KEY})).status_code == 403
    assert (await client.get(url, headers={'X-Rig-Key': PUBLIC_KEY, 'Origin': 'https://foreign.example'})).status_code == 403
    async def forbidden(*args): raise AssertionError('Read-only terminal must never submit')
    engine.forge.submit = forbidden
    result = await client.get(url, headers={'X-Rig-Key': PUBLIC_KEY})
    assert result.status_code == 200
    data = result.json()
    assert data['approved'] == [] and data['live'] is None and data['latest'] is None
    assert data['counts'] == {'approved': 0, 'today': 0, 'active': 0} and data['timezone'] == 'UTC'
    assert await pool.fetchval('SELECT count(*) FROM agent_rig.rig_3d_jobs') == 0
    event = await client.get(url + '/events?once=true', headers={'X-Rig-Key': PUBLIC_KEY})
    assert event.status_code == 200 and 'event: build' in event.text and 'no-store' in event.headers['cache-control']
    assert 'text/event-stream' in event.headers['content-type']


@pytest.mark.asyncio
async def test_terminal_stream_measured_events_receipts_utc_and_revocation(rig):
    engine, pool, client, _ = rig
    request = job(); await engine.submit(TENANT, request)
    identity = str(uuid4())
    event = {'id': '0', 'stage': 'design', 'at': '2026-11-06T10:00:00+00:00', 'elapsed_ms': 1234,
             'outcome': 'delivered', 'cost': {'amount_usd': '0.10', 'basis': 'upper_bound', 'receipt_ids': [identity]}}
    await engine.store.record_progress(TENANT, request.id, [event, event])
    await engine.store.record_progress(WITHOUT_3D, request.id, [{**event, 'id': 'foreign'}])
    assert (await engine.store.job(TENANT, request.id))['progress'] == [event]
    result = await client.get('/v1/rig/3d/terminal/events?once=true', headers={'X-Rig-Key': PUBLIC_KEY})
    data = json.loads(next(line[6:] for line in result.text.splitlines() if line.startswith('data: ')))
    assert data['live']['status'] == 'draft' and data['live']['model'] is None
    assert data['live']['events'][0] == event and data['counts']['active'] == 1
    assert data['live']['events'][1]['stage'] == 'price' and data['live']['events'][1]['elapsed_ms'] >= 0
    assert data['live']['cost']['basis'] == 'upper_bound'
    await engine.approve(TENANT, request.id, Review(scale=True, appearance=True, attachment_points=True), 'offline-reviewer')
    data = await snapshot(engine, TENANT)
    assert data['live'] is None and data['counts'] == {'approved': 1, 'today': 1, 'active': 0}
    build = data['approved'][0]
    assert build['receipt']['job_id'] == str(request.id) and build['model']['sha256'] == build['receipt']['sha256']
    assert [row['stage'] for row in build['events']] == ['design', 'price', 'ready']
    assert build['events'][-1]['at'] == build['receipt']['approved_at']
    assert 'reviewer' not in json.dumps(data) and 'inputs' not in json.dumps(data)
    await pool.execute("UPDATE agent_rig.rig_3d_jobs SET approved_at=date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' - interval '1 second' WHERE tenant_id=$1", TENANT)
    data = await snapshot(engine, TENANT)
    assert data['counts']['today'] == 0 and data['approved'][0]['today'] is False
    await engine.store.set_entitlement(TENANT, False, None, 'USD')
    assert (await client.get('/v1/rig/3d/terminal/events?once=true', headers={'X-Rig-Key': PUBLIC_KEY})).status_code == 403


def test_ledger_cost_deduplicates_claim_completion_and_never_fabricates_actual_bill():
    identifier = str(uuid4())
    receipt = {'ledger_id': identifier, 'cost_usd': '0.125', 'cost_basis': 'upper_bound'}
    assert cost([receipt, receipt]) == {'amount_usd': '0.125', 'basis': 'upper_bound', 'receipt_ids': [identifier]}
    assert cost([{'reserved_usd': '99'}, {'ledger_id': identifier, 'cost_usd': 'NaN'}])['amount_usd'] is None
    assert cost([{**receipt, 'cost_usd': '0', 'cost_basis': 'recorded'}])['basis'] == 'recorded'


class BytesStream(httpx.AsyncByteStream):
    def __init__(self, data): self.data = data
    async def __aiter__(self): yield self.data


class RecordedObjects(httpx.AsyncBaseTransport):
    def __init__(self): self.objects = {}; self.writes = []
    async def handle_async_request(self, request):
        key = request.url.path.removeprefix('/tervory-rig/')
        if request.method == 'PUT':
            data = await request.aread()
            if request.headers.get('if-none-match') == '*' and key in self.objects:
                return httpx.Response(412, stream=BytesStream(b''))
            self.objects[key] = data; self.writes.append(key)
            return httpx.Response(200, stream=BytesStream(b''))
        data = self.objects.get(key)
        return httpx.Response(200 if data is not None else 404, stream=BytesStream(data or b''),
                              headers={'Content-Length': str(len(data or b''))})
    def generate_presigned_url(self, operation, **kwargs):
        return 'https://offline.invalid/' + kwargs['Params']['Key']
    def get_object(self, **kwargs):
        data = self.objects[kwargs['Key']]; return {'Body': io.BytesIO(data), 'ContentLength': len(data)}
    def put_object(self, **kwargs): self.objects[kwargs['Key']] = kwargs['Body'].read()


@pytest.mark.asyncio
@pytest.mark.parametrize('photo_count', [1, 3])
async def test_r3d_recorded_photos_hf_real_cpu_approval_receipt_and_resume(rig, tmp_path, monkeypatch, photo_count):
    engine, pool, client, _ = rig
    monkeypatch.setenv('RIG_FORGE_TRELLIS_ENABLED', 'true'); monkeypatch.setenv('HF_JOBS_NAMESPACE', 'offline')
    recording = json.loads((ROOT / 'tests/fixtures/rig_r3d/hf-responses.json').read_text())
    objects = RecordedObjects(); storage = files(objects)
    engine.assets = R2Assets(storage)
    request = job(source='ai', inputs=[f'{TENANT}/uploads/offline.jpg'], dimensions_mm=(20,30,40),
                  anchors={'attach': {'position_mm': [0,0,0], 'quaternion': [0,0,0,1]}}, cost_cap_usd=1)
    photos = []
    for n in range(photo_count):
        photo = tmp_path / f'{n}.jpg'; photo.write_bytes(b'\xff\xd8\xff' + b'offline-photo' * (n + 1)); photos.append(photo)
    request, uploads = command.prepare(request.model_dump(mode='json'), photos)
    starts, inspections, relay_calls, tasks = [], [], [], {}
    work = tmp_path / 'worker'; work.mkdir()
    class Provider:
        def run_job(self, **kwargs):
            starts.append(kwargs)
            assert kwargs['command'][-1] == 'trellis2'
            assert len(json.loads(kwargs['secrets']['FORGE_TRANSFERS'])['get']) == photo_count
            assert set(kwargs['secrets']) == {'FORGE_TRANSFERS'} and 'HF_JOBS_TOKEN' not in kwargs['env']
            return SimpleNamespace(**recording['run_job'])
        def inspect_job(self, **kwargs):
            inspections.append(kwargs)
            response = recording['inspect_job'][min(len(inspections)-1, 1)]
            if response['status']['stage'] == 'COMPLETED':
                objects.objects[f'forge/{TENANT}/{request.id}/gpu/result.glb'] = (ROOT / 'tests/fixtures/rig_forge_models/ai-sample.glb').read_bytes()
            return SimpleNamespace(status=SimpleNamespace(**response['status']))
        def cancel_job(self, **kwargs): raise AssertionError('Successful run must not cancel')
    async def wait(_): await asyncio.sleep(0)
    monkeypatch.setattr(worker, 'GPU', lambda: GPU(Provider(), wait=wait))
    ledger = uuid4()
    async def relay(action, body):
        relay_calls.append((action, body))
        if action == 'reserve': return {**body, **recording['authorization']}
        stage = body.get('stage', 'gpu_job')
        return {'ledger_id': str(ledger if action in {'claim','complete'} else uuid4()),
                'tenant_id': str(TENANT), 'task_id': str(request.id), 'stage': stage,
                'outcome': body.get('outcome', 'delivered'),
                'cost_usd': '0.10' if action in {'claim','complete'} else '0',
                'cost_basis': 'upper_bound' if action in {'claim','complete'} else 'recorded'}
    monkeypatch.setattr(worker, 'relay', relay)
    async def brain(req):
        if req.method == 'POST':
            body = worker.Job.model_validate(json.loads(req.content))
            if body.job_id not in tasks:
                tasks[body.job_id] = asyncio.create_task(worker.perform(body, work, Storage(str(TENANT), str(request.id), client=objects)))
        else:
            assert req.url.params['tenant_id'] == str(TENANT)
        path = work / 'state.json'
        return httpx.Response(200, json=json.loads(path.read_text()) if path.exists() else {'status':'queued'})
    monkeypatch.setenv('TANK_KEY', 'placeholder-r3d-room')
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(brain)) as relay_client:
            engine.forge = BrainForge(relay_client, 'placeholder-r3d-room', storage)
            client.headers['X-Tank-Key'] = 'placeholder-r3d-room'
            corridor = command.Corridor(client, request, 'offline-human-reviewer')
            output = tmp_path / 'output'; review_path = tmp_path / 'review.json'
            result = await command.run(request, uploads, output, review_path, corridor, storage, wait=wait)
            assert result['status'] == 'awaiting_review' and not (output / 'approved.glb').exists()
            assert (await snapshot(engine, TENANT))['approved'] == []
            state = json.loads((work / 'state.json').read_text())
            assert state['status'] == 'draft' and state['report']['checks']['gltf_validator']
            elapsed = [event['elapsed_ms'] for event in state['progress']]
            assert elapsed == sorted(elapsed) and elapsed[-1] > 0
            assert {'understand','design','check'} <= {event['stage'] for event in state['progress']}
            review_path.write_text(json.dumps({'job_id': str(request.id), 'sha256': '0'*64,
                'review': {'scale': True, 'appearance': True, 'attachment_points': True}}))
            with pytest.raises(command.CommandError, match='checksum'):
                await command.run(request, uploads, output, review_path, corridor, storage, wait=wait)
            assert (await engine.store.job(TENANT, request.id))['status'] == 'draft' and len(starts) == 1
            review_path.write_text(json.dumps({'job_id': str(request.id), 'sha256': result['sha256'],
                'review': {'scale': True, 'appearance': True, 'attachment_points': True}}))
            result = await command.run(request, uploads, output, review_path, corridor, storage, wait=wait)
            assert result['status'] == 'approved' and result['receipt_ids']
            assert hashlib.sha256((output / 'approved.glb').read_bytes()).hexdigest() == result['sha256']
            # Real CPU tools can emit different GLB bytes across supported hosts.
            # Bind approval to this run's validated/uploaded bytes, never a stale recording.
            raw = objects.objects[f'forge/{TENANT}/{request.id}/drafts/model.glb']
            converted = add_anchors(raw, request)
            assert result['sha256'] == hashlib.sha256(converted).hexdigest()
            assert (output / 'approved.glb').read_bytes() == converted
            again = await command.run(request, uploads, output, review_path, corridor, storage, wait=wait)
            assert again == result and len(starts) == 1 and len(inspections) == 2
            wall = await snapshot(engine, TENANT)
            assert wall['counts']['today'] == 1 and wall['approved'][0]['cost']['amount_usd'] == '0.10'
            assert wall['approved'][0]['receipt']['sha256'] == result['sha256']
            assert [action for action, _ in relay_calls].count('claim') == 1
            print(json.dumps({'dry_run': True, 'source': 'recorded HF responses; real CPU tools',
                'photos': photo_count, 'status': result['status'], 'sha256': result['sha256'], 'receipts': len(result['receipt_ids'])}))
    finally:
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        await storage.close()


@pytest.mark.asyncio
async def test_r3d_disabled_trellis_stops_before_budget_or_provider(monkeypatch):
    monkeypatch.delenv('RIG_FORGE_TRELLIS_ENABLED', raising=False)
    async def forbidden(*args): raise AssertionError('No side effects')
    with pytest.raises(GPUError, match='disabled'):
        await GPU(object()).run({}, 'trellis2', transfers={}, timeout=60, cap='1', relay=forbidden,
                                save_provider=forbidden, namespace='offline')


@pytest.mark.parametrize('defect', ['symlink','wrong_extension','too_many','changed_output'])
def test_r3d_command_validates_files_before_any_side_effect(tmp_path, defect):
    request = job(source='ai', inputs=[f'{TENANT}/uploads/photo.jpg'])
    photo = tmp_path / 'photo.jpg'; photo.write_bytes(b'\xff\xd8\xffoffline')
    if defect == 'symlink':
        other = tmp_path / 'link.jpg'; other.symlink_to(photo); photo = other
    elif defect == 'wrong_extension': photo.write_bytes(b'<html>not a photo')
    elif defect == 'changed_output':
        command.write_file(tmp_path, 'receipt.json', b'original')
        with pytest.raises(command.CommandError): command.write_file(tmp_path, 'receipt.json', b'changed')
        return
    with pytest.raises((command.CommandError, ValueError)):
        command.prepare(request.model_dump(mode='json'), [photo] * (5 if defect == 'too_many' else 1))


@pytest.mark.asyncio
async def test_r3d_completed_history_is_paged_and_tenant_scoped(rig):
    engine, pool, client, _ = rig
    request = job(); await engine.submit(TENANT, request); await engine.poll(TENANT, request.id)
    await engine.approve(TENANT, request.id, Review(scale=True, appearance=True, attachment_points=True), 'offline-reviewer')
    for _ in range(22):
        await pool.execute('''INSERT INTO agent_rig.rig_3d_jobs
            (tenant_id,id,product_id,request,status,report,review,reviewed_by,approved_at)
            SELECT tenant_id,$3,product_id,request,status,report,review,reviewed_by,now()
            FROM agent_rig.rig_3d_jobs WHERE tenant_id=$1 AND id=$2''', TENANT, request.id, uuid4())
    headers = {'X-Rig-Key': PUBLIC_KEY}; url = '/v1/rig/3d/terminal/completed'
    first = (await client.get(url, headers=headers)).json()
    second = (await client.get(url, headers=headers, params={'before': first['next']})).json()
    assert len(first['builds']) == 20 and len(second['builds']) == 3 and second['next'] is None
    assert len({row['id'] for row in first['builds'] + second['builds']}) == 23
    assert (await client.get(url, headers=headers, params={'before': str(uuid4())})).json()['builds'] == []
    assert (await client.get(url, headers={'X-Rig-Key': PLAIN_KEY})).status_code == 403
    assert (await snapshot(engine, TENANT))['counts']['today'] == 23
    await pool.execute("UPDATE agent_rig.rig_3d_jobs SET created_at=now()-interval '1 year',approved_at=now() WHERE tenant_id=$1 AND id=$2", TENANT, request.id)
    assert (await snapshot(engine, TENANT))['approved'][0]['id'] == str(request.id)


@pytest.mark.asyncio
async def test_r3d_command_missing_settings_and_timeout_are_safe(tmp_path, monkeypatch):
    monkeypatch.delenv('TANK_KEY', raising=False); monkeypatch.delenv('RIG_AGENT_URL', raising=False)
    with pytest.raises(command.CommandError, match='TANK_KEY, RIG_AGENT_URL'):
        await command.live(SimpleNamespace())
    request = job()
    async def timeout(_): raise httpx.ReadTimeout('private provider detail')
    async with httpx.AsyncClient(base_url='http://offline.invalid', transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(command.CommandError, match='same job identifier') as failure:
            await command.Corridor(client, request, 'offline-reviewer').call('submit')
        assert 'private' not in str(failure.value)


@pytest.mark.asyncio
async def test_r3d_open_stream_rechecks_entitlement_without_spending_http_rate_budget(rig):
    engine, pool, client, _ = rig
    request = SimpleNamespace(method='GET', headers={'x-rig-key': PUBLIC_KEY},
        app=client._transport.app, client=SimpleNamespace(host='127.0.0.1'), state=SimpleNamespace(),
        scope={'route': SimpleNamespace(path='/v1/rig/3d/terminal/events')}, is_disconnected=AsyncMock(return_value=False))
    stream = updates(request, engine, str(TENANT))
    try:
        assert 'event: build' in await anext(stream)
        assert await pool.fetchval('SELECT count(*) FROM agent_rig.rate_counts') == 0
        await engine.store.set_entitlement(TENANT, False, None, 'USD')
        assert 'event: unavailable' in await anext(stream)
        with pytest.raises(StopAsyncIteration): await anext(stream)
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_r3d_one_command_waits_for_actual_review_then_exports_approved_glb(rig, tmp_path, monkeypatch):
    engine, _, client, _ = rig
    monkeypatch.setenv('TANK_KEY', 'placeholder-r3d-room')
    client.headers['X-Tank-Key'] = 'placeholder-r3d-room'
    request = job(); output = tmp_path / 'one-command'; review = tmp_path / 'review.json'
    async def reviewer():
        while not (output / 'report.json').exists(): await asyncio.sleep(.01)
        assert (await engine.store.job(TENANT, request.id))['status'] == 'draft'
        assert not (output / 'approved.glb').exists()
        report = json.loads((output / 'report.json').read_text())
        # This is the offline human boundary; the command never writes its own review.
        review.write_text(json.dumps({'job_id': str(request.id), 'sha256': report['sha256'],
            'review': {'scale': True, 'appearance': True, 'attachment_points': True}}))
    task = asyncio.create_task(reviewer())
    async def wait(_): await asyncio.sleep(.01)
    try:
        result = await command.run(request, [], output, review,
            command.Corridor(client, request, 'offline-reviewer'), SimpleNamespace(put=AsyncMock()),
            wait=wait, review_wait_seconds=10)
        await task
        assert result['status'] == 'approved' and (output / 'approved.glb').exists()
    finally:
        task.cancel(); await asyncio.gather(task, return_exceptions=True)


def test_r3d_touch_terminal_and_wall_browser():
    result = subprocess.run(['node', str(ROOT / 'tests/rig_r3d_browser.mjs')], cwd=ROOT,
                            capture_output=True, text=True, timeout=100)
    assert result.returncode == 0, result.stdout + result.stderr
