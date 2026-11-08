"""Real local PostgreSQL; fake accounting callers and fake HF Jobs only."""
import asyncio
from contextlib import aclosing
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/rig"))
from fastapi import FastAPI

import rig_savings
import rig_forge_provider
from test_train1 import database as _database
from test_rig_forge_tank import setup as forge_setup

database = _database

@pytest.mark.asyncio
async def test_code_receipts_pricing_retry_scope_and_actual_tokens(database, monkeypatch):
    pool, rt = database
    monkeypatch.setenv('TANK_KEY_RIG', 'placeholder-room')
    app = FastAPI(); app.include_router(rig_savings.build_router(rt))
    body = {'id': str(uuid4()), 'tenant_id': str(uuid4()), 'action': 'rig.ask', 'outcome': 'delivered',
            'reference_tokens_in': 1000, 'reference_tokens_out': 100, 'reference_status': 'bpe_reference',
            'cost': '0', 'cost_status': 'recorded'}
    await pool.execute("DELETE FROM tank.proof_prices WHERE model='sol'")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank') as client:
        path = '/v1/agents/rig/savings/receipts'
        assert (await client.post(path, json=body)).status_code == 401
        client.headers['X-Tank-Key'] = 'placeholder-room'
        first = await client.post(path, json=body)
        assert first.status_code == 200, first.text
        assert first.json()['cost'] == '0' and first.json()['would_have_cost'] is None
        await pool.execute("""INSERT INTO tank.proof_prices(model,family,input_usd,output_usd,active)
            VALUES('sol','openai',0.000002,0.000008,true)""")
        responses = await asyncio.gather(*(client.post(path, json=body) for _ in range(3)))
        assert all(row.status_code == 200 for row in responses)
        assert all(Decimal(row.json()['would_have_cost']) == Decimal('0.0028') for row in responses)
        assert await pool.fetchval('SELECT count(*) FROM tank.ledger WHERE id=$1', UUID(body['id'])) == 1
        row = await pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', UUID(body['id']))
        assert row['tokens_in'] == row['tokens_out'] == row['cost_usd'] == 0
        assert row['rig_reference_tokens_in'] == 1000 and row['standard_model'] == 'sol'
        for change, status in [({'tenant_id': str(uuid4())}, 409), ({'reference_tokens_in': 1}, 409),
                               ({'cost': '1'}, 422), ({'secret': 'placeholder'}, 422)]:
            assert (await client.post(path, json={**body, **change})).status_code == status
        query = '/v1/agents/rig/savings/query'
        assert (await client.post(query, json={'tenant_id': str(uuid4())})).json()['receipts'] == []
        result = await client.post(query, json={'tenant_id': body['tenant_id']})
        assert result.status_code == 200, result.text
        assert Decimal(result.json()['receipts'][0]['cost']) == 0
        assert Decimal(result.json()['receipts'][0]['would_have_cost']) == Decimal('0.0028')
        assert 'input_hash' not in result.text


class Provider:
    def __init__(self, lost=False): self.calls = []; self.lost = lost
    def run_job(self, **kwargs):
        self.calls.append(('launch', kwargs))
        if self.lost: raise TimeoutError('placeholder-private-provider-detail')
        return SimpleNamespace(id='offline-job')
    def inspect_job(self, **kwargs):
        self.calls.append(('inspect', kwargs))
        return SimpleNamespace(status=SimpleNamespace(stage='COMPLETED'))
    def cancel_job(self, **kwargs): self.calls.append(('cancel', kwargs))


async def launched(database, monkeypatch, lost=False):
    pool, rt = database
    client, scope = await forge_setup(pool, rt, monkeypatch)
    client._transport.app.include_router(rig_forge_provider.build_router(rt))
    await client.post('/v1/agents/rig/forge/reserve', json={**scope, 'method': 'trellis2', 'timeout_seconds': 600, 'cost_cap_usd': '1'})
    assert (await client.post('/v1/agents/rig/forge/claim', json=scope)).status_code == 200
    monkeypatch.setenv('HF_JOBS_NAMESPACE', 'offline'); monkeypatch.setenv('RIG_FORGE_TRELLIS_ENABLED', 'true')
    monkeypatch.setenv('R2_ACCOUNT_ID', 'a' * 32)
    provider = Provider(lost); monkeypatch.setattr(rig_forge_provider, 'provider', lambda: provider)
    def address(area, name):
        return f"https://{'a'*32}.r2.cloudflarestorage.com/tervory-rig/forge/{scope['tenant_id']}/{scope['job_id']}/{area}/{name}?X-Amz-Signature={'b'*64}&X-Amz-Expires=900"
    manifest = {**scope, 'method': 'trellis2', 'inputs': ['front.jpg'], 'timeout_seconds': 600}
    body = {**scope, 'namespace': 'offline', 'transfers': {'manifest': manifest,
        'get': {'front.jpg': address('inputs', 'front.jpg')},
        'put': {name: address('gpu', name) for name in ('result.glb', 'source.zip')}}}
    return client, scope, body, provider


@pytest.mark.asyncio
@pytest.mark.parametrize('lost', [False, True])
async def test_tank_launch_once_receipt_scope_and_lost_response(database, monkeypatch, lost):
    pool, _ = database
    client, scope, body, provider = await launched(database, monkeypatch, lost)
    async with aclosing(client):
        path = '/v1/agents/rig/forge/launch'
        answers = await asyncio.gather(*(client.post(path, json=body) for _ in range(3)))
        assert sorted(row.status_code for row in answers) == ([409,409,503] if lost else [200,409,409])
        assert len(provider.calls) == 1
        payload = provider.calls[0][1]
        assert payload['image'].endswith('a'*64) and payload['timeout'] == 600
        assert set(payload['secrets']) == {'FORGE_TRANSFERS'} and 'HF_JOBS_TOKEN' not in json.dumps(payload)
        row = await pool.fetchrow('SELECT * FROM tank.rig_forge_jobs WHERE tenant_id=$1', UUID(scope['tenant_id']))
        assert row['provider_started'] and 'X-Amz-Signature' not in str(dict(row))
        for operation in ('inspect', 'cancel'):
            result = await client.post('/v1/agents/rig/forge/' + operation, json=scope)
            assert result.status_code == (409 if lost else 200), result.text
            assert (await client.post('/v1/agents/rig/forge/' + operation, json={**scope, 'tenant_id': str(uuid4())})).status_code == 404
        assert 'placeholder-private-provider-detail' not in ''.join(row.text for row in answers)
        ledger = await pool.fetchrow('SELECT * FROM tank.ledger WHERE tenant_id=$1', UUID(scope['tenant_id']))
        assert ledger['cost_usd'] > 0 and ledger['standard_cost_usd'] is None
        assert await pool.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1', UUID(scope['tenant_id'])) == 1


@pytest.mark.asyncio
async def test_provider_capabilities_and_missing_settings_block_before_launch(database, monkeypatch):
    pool, _ = database
    original = rig_forge_provider.provider
    client, scope, body, provider = await launched(database, monkeypatch)
    path = '/v1/agents/rig/forge/launch'
    async with aclosing(client):
        for mutate in ('url', 'tenant', 'filename'):
            altered = json.loads(json.dumps(body))
            if mutate == 'url': altered['transfers']['get']['front.jpg'] = 'https://other.invalid/forbidden'
            if mutate == 'tenant': altered['transfers']['manifest']['tenant_id'] = str(uuid4())
            if mutate == 'filename': altered['transfers']['manifest']['inputs'] = [{}]
            assert (await client.post(path, json=altered)).status_code in (403,422)
        monkeypatch.setattr(rig_forge_provider, 'provider', original)
        monkeypatch.delenv('HF_JOBS_TOKEN', raising=False)
        answer = await client.post(path, json=body)
        assert answer.status_code == 503 and 'HF_JOBS_TOKEN' in answer.text
        assert not provider.calls
        assert not await pool.fetchval('SELECT provider_started FROM tank.rig_forge_jobs WHERE tenant_id=$1', UUID(scope['tenant_id']))


@pytest.mark.asyncio
async def test_room_gpu_calls_tank_without_provider_credentials(monkeypatch):
    from agents.rig.forge.gpu import GPU
    monkeypatch.delenv('HF_JOBS_TOKEN', raising=False); monkeypatch.setenv('RIG_FORGE_TRELLIS_ENABLED', 'true')
    scope = {'tenant_id': str(uuid4()), 'job_id': str(uuid4()), 'home_region': 'us-east'}
    actions = []
    async def relay(action, body):
        actions.append(action)
        if action == 'reserve': return {**scope, 'image': 'ghcr.io/placeholder/job@sha256:' + 'a'*64, 'timeout_seconds': 60, 'flavor': 'a10g-small'}
        if action == 'launch': return {'provider_job_id': 'offline-job'}
        if action == 'inspect': return {'stage': 'COMPLETED'}
        return {}
    async def save(value): assert value == 'offline-job'
    assert await GPU().run(scope, 'trellis2', transfers={}, timeout=60, cap='1', relay=relay,
                           save_provider=save, namespace='offline') == 'offline-job'
    assert actions == ['reserve','claim','launch','steps','inspect','steps','complete']
    source = (Path(__file__).resolve().parents[1] / 'agents/rig/forge/gpu.py').read_text()
    assert 'huggingface_hub' not in source and 'HfApi' not in source


@pytest.mark.asyncio
async def test_model_receipt_links_existing_ledger_without_second_charge(database, monkeypatch):
    pool, rt = database; tenant, identity = uuid4(), uuid4()
    monkeypatch.setenv('TANK_KEY_RIG', 'placeholder-room')
    await pool.execute("""INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd,tokens_in,tokens_out)
        VALUES($1,$2,'rig','rig.ask','sol',0.001,100,10)""", identity, tenant)
    app = FastAPI(); app.include_router(rig_savings.build_router(rt))
    body = {'id': str(uuid4()), 'tenant_id': str(tenant), 'action': 'rig.ask', 'outcome': 'delivered',
            'reference_tokens_in': 100, 'reference_tokens_out': 10, 'reference_status': 'bpe_reference',
            'cost': '0.001', 'cost_status': 'recorded', 'model_ledger_ids': [str(identity)]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://tank',headers={'X-Tank-Key':'placeholder-room'}) as client:
        for _ in range(2):
            result = await client.post('/v1/agents/rig/savings/receipts',json=body)
            assert result.status_code == 200, result.text
            assert result.json()['ledger_id'] == str(identity)
        assert (await client.post('/v1/agents/rig/savings/receipts',json={**body,'tenant_id':str(uuid4())})).status_code == 422
        assert await pool.fetchval('SELECT count(*) FROM tank.ledger') == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', [False, True])
async def test_brain_tools_use_tank_ladder_and_existing_ledger(database, monkeypatch, bad):
    import rig_brain_routing
    from agent_skills import Chat
    pool, rt = database; tenant, task, identifier = uuid4(), uuid4(), uuid4()
    await pool.execute("""INSERT INTO tank.ledger(id,tenant_id,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out)
        VALUES($1,$2,'rig','agent.rig.think',2,'offline-local',0,10,5)""", identifier, tenant)
    calls = []
    async def route(request, caller):
        calls.append(request)
        assert caller == 'rig' and request.tenant_id == tenant and request.task_type == 'agent.rig.think'
        assert request.home_region == 'us-east' and request.max_tokens == 4096
        assert 'paid-provider-override' not in json.dumps(request.messages)
        return SimpleNamespace(ledger_id=identifier, model='offline-local', tokens_in=10, tokens_out=5, cost_usd=0,
            content=json.dumps({'content': None, 'tool_calls': [{'name': 'forbidden' if bad else 'skala_run', 'arguments': {'skill_id': 'rig.search'}}]}))
    rt.RouteRequest = SimpleNamespace; rt.route = route
    body = Chat(model='paid-provider-override', messages=[{'role':'user','content':'Find the scope'}], tools=[
        {'type':'function','function':{'name':'skala_run','parameters':{'type':'object','properties':{'skill_id':{'type':'string'}},'required':['skill_id'],'additionalProperties':False}}}])
    answer = await rig_brain_routing.complete(rt, body, tenant, task, 'us-east')
    assert await rig_brain_routing.complete(rt, body, tenant, task, 'us-east') == answer
    assert len(calls) == 1 and answer['receipt']['ledger_id'] == str(identifier)
    assert answer['usage']['total_tokens'] == 15
    assert await pool.fetchval('SELECT count(*) FROM tank.ledger') == 1
    assert await pool.fetchval('SELECT count(*) FROM tank.agent_receipts WHERE tenant_id=$1', tenant) == 1
    if bad:
        assert answer['receipt']['outcome'] == 'failed' and 'tool_calls' not in answer['choices'][0]['message']
    else:
        assert answer['choices'][0]['message']['tool_calls'][0]['function']['name'] == 'skala_run'
    source = (Path(__file__).resolve().parents[1] / 'agents/rig/rig_brain/runner.py').read_text()
    assert 'base_url=tank + "/v1/agents/rig"' in source


from test_rig_3d_engine import rig as _rig

rig = _rig


@pytest.mark.asyncio
async def test_forge_command_actions_keep_review_and_postgres_receipts(rig, monkeypatch):
    from test_rig_3d_engine import TENANT, job
    from rigbox.savings import Receipts
    engine, pool, client, _ = rig
    monkeypatch.setenv('TANK_KEY', 'placeholder-room'); monkeypatch.setenv('RIG_ROOM_TENANT', str(TENANT))
    request = job(); headers = {'X-Tank-Key': 'placeholder-room'}
    async def call(operation, args, admin=True):
        return await client.post('/v1/rig/internal/tools/forge.' + operation, headers=headers,
            json={'tenant_id': str(TENANT), 'actor': 'placeholder-reviewer', 'administrator': admin, 'arguments': args})
    args = request.model_dump(mode='json', exclude={'tenant_id'})
    assert (await call('submit', args, False)).status_code == 403
    first = await call('submit', args)
    assert first.status_code == 200, first.text
    assert first.json()['receipt']['cost'] == '0'
    assert (await call('approve', {'id': str(request.id), 'review': {'scale': True, 'appearance': True, 'attachment_points': True}})).status_code == 409
    assert (await call('poll', {'id': str(request.id)})).json()['result']['status'] == 'draft'
    approved = await call('approve', {'id': str(request.id), 'review': {'scale': True, 'appearance': True, 'attachment_points': True}})
    assert approved.status_code == 200 and approved.json()['result']['approved']
    rows = await Receipts(engine.catalogue.store).rows(TENANT)
    assert any(row['action'] == 'rig.3d.submit' for row in rows)
    assert any(row['action'] == 'rig.3d.approve' and row['outcome'] == 'delivered' for row in rows)
    assert await Receipts(engine.catalogue.store).rows(uuid4()) == []
    before = len(rows)
    for _ in range(3): await engine.poll(TENANT, request.id)
    assert len(await Receipts(engine.catalogue.store).rows(TENANT)) == before
