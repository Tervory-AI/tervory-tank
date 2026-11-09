"""Base's real shared-platform acceptance. Missing runtime is a failure, never a skip."""
import asyncio
import json
import time
from pathlib import Path
from uuid import uuid4

import pytest
import httpx

from chassis.user_assertion import HEADER, SignedUser, sign_assertion
from gate78_contract import REQUIREMENTS
from base_fixture import USER_A, USER_B
from base_fixture import base_entry as base_entry
from base_fixture import base_module_scope as base_module_scope

ROOT = Path(__file__).resolve().parents[3]
SOURCE_SHA = '07b5822ecfed4e46067c1d3c4d78e52ab34cb8ee'


async def owner_view(e, user=USER_A, tenant=None):
    response = await e.request('memory', {'user_id':user,'task_key':'placeholder-batch'}, method='GET', user=user, tenant=tenant)
    assert response.status_code == 200, response.text
    return response.json()['memories']


async def seed(e, user=USER_A, tenant=None, kind='base.verified', text='placeholder verified business', **meta):
    return await e.stack.client(user).remember(tenant or e.stack.tenant, text, kind, 'urn:placeholder:base',
        meta={'task_key':'placeholder-batch', **meta})


async def run(e, **kwargs):
    response = await e.submit(**kwargs)
    assert response.status_code == 202, response.text
    task_id = response.json()['task']['id']
    deadline = time.monotonic()+5
    while time.monotonic()<deadline:
        row = await e.queued(task_id, kwargs.get('tenant'))
        if row['status'] in {'done','failed'}:
            assert row['status']=='done', dict(row)
            cfg = json.loads(row['input']) if isinstance(row['input'],str) else row['input']
            return task_id,cfg
        await asyncio.sleep(.02)
    raise AssertionError('Real Base queue/worker did not complete')


@pytest.mark.asyncio
async def test_owner_worker_write_and_real_memory_controls(base_entry):
    e=base_entry
    await seed(e)
    rows=await owner_view(e)
    assert any(row['kind']=='base.verified' for row in rows)
    target=rows[0]['id']
    edited=await e.request('memory/edit', {'user_id':USER_A,'memory_id':target,'text':'placeholder corrected business'})
    assert edited.status_code==200, edited.text
    assert any('placeholder corrected business' in json.dumps(row) for row in await owner_view(e))
    forgotten=await e.request('memory/forget', {'user_id':USER_A,'memory_id':target,'memory_control':'forget'})
    assert forgotten.status_code==200,forgotten.text
    assert target not in json.dumps(await owner_view(e))
    assert not await e.stack.client(USER_A).recall(e.stack.tenant,'placeholder corrected business')


@pytest.mark.asyncio
@pytest.mark.parametrize('foreign',['user','tenant'])
async def test_personal_read_mutation_and_publish_isolation(base_entry,foreign,caplog):
    e=base_entry
    row=await seed(e,text='placeholder private business')
    user=USER_B if foreign=='user' else USER_A
    tenant=e.stack.other_tenant if foreign=='tenant' else e.stack.tenant
    assert row['id'] not in json.dumps(await owner_view(e,user,tenant))
    before=await e.snapshot()
    for path in ('memory/edit','memory/forget','memory/publish'):
        response=await e.request(path, {'user_id':user,'memory_id':row['id'], **({'text':'placeholder attacker'} if path != 'memory/forget' else {})}, user=user, tenant=tenant)
        assert response.status_code in {403,404},response.text
        assert await e.snapshot()==before
        assert 'placeholder private business' not in response.text
    assert 'placeholder private business' not in caplog.text and not e.provider_calls


@pytest.mark.asyncio
async def test_no_declared_tenant_wide_kind_refuses_unowned_personal_rows(base_entry):
    e=base_entry
    response=await e.stack.http.post('/memories',headers={'X-Tank-Key':e.stack.key},json={
        'tenant_id':e.stack.tenant,'text':'placeholder unowned','kind':'base.verified','source':'urn:placeholder:unowned'})
    assert response.status_code in {401,403,422}
    await seed(e)
    assert await owner_view(e)
    assert not await owner_view(e,USER_B)


@pytest.mark.asyncio
@pytest.mark.parametrize('claim',['created_by','user_id'])
async def test_body_is_not_identity_and_queued_owner_is_verified(base_entry,claim):
    e=base_entry
    before=await e.snapshot()
    response=await e.submit(control='historical',**{claim:USER_B})
    assert response.status_code in {401,403,422},response.text
    assert await e.snapshot()==before
    positive=await e.submit(control='historical')
    assert positive.status_code==202,positive.text
    row=await e.queued(positive.json()['task']['id'])
    cfg=json.loads(row['input'])
    assert row['created_by']==USER_A and cfg['user_id']==USER_A
    assert cfg['created_by']==USER_A
    forwarded=next(r for r in reversed(e.requests) if r.url.host=='agent-base' and r.url.path=='/v1/base/run')
    assert HEADER in forwarded.headers, 'Queued owner must originate in a cryptographically verified request'
    assert not e.provider_calls


@pytest.mark.asyncio
async def test_actual_proxy_allowlist_and_signed_header_contract(base_entry):
    e=base_entry
    assert {'memory','memory/forget'}<=e.main._BASE_ROUTES
    assert 'memory/bracket' not in e.main._BASE_ROUTES
    assert (await e.request('memory/bracket', {'user_id':USER_A,'cost_usd':1000000})).status_code==404
    await owner_view(e)
    forwarded=[r for r in e.requests if r.url.host=='agent-base' and r.url.path=='/v1/base/memory']
    assert forwarded and HEADER in forwarded[-1].headers
    assert forwarded[-1].headers['X-Tank-Key']==e.stack.key
    assert 'TANK_API_KEY' not in forwarded[-1].headers
    assert (await e.request('memory/private-export',{},method='GET')).status_code==404


@pytest.mark.asyncio
async def test_unsigned_headers_cannot_read_personal_memory(base_entry):
    e=base_entry
    await seed(e)
    response=await e.client.get('/v1/base/memory',headers={'X-Tank-Key':'placeholder-base-workspace-key',
        'X-Tervory-User':USER_A,'X-Tervory-Tenant':e.stack.tenant},params={'tenant_id':e.stack.tenant,'user_id':USER_A,'task_key':'placeholder-batch'})
    assert response.status_code in {401,403},response.text
    # Positive signed request is required; deny-all cannot pass.
    assert await owner_view(e)


@pytest.mark.asyncio
@pytest.mark.parametrize('bad',['key','audience','tenant','method','target','body','missing','expired','future'])
async def test_room_assertion_verification_and_nonce_binding(base_entry,bad):
    e=base_entry
    await seed(e)
    target='/v1/base/memory?tenant_id='+e.stack.tenant+'&user_id='+USER_A+'&task_key=placeholder-batch'
    params=dict(product='base',user=SignedUser(e.stack.tenant,USER_A,'member'),method='GET',target=target,body=b'',key=e.stack.key)
    if bad=='key':params['key']='placeholder-wrong-key'
    if bad=='audience':params['product']='tiger'
    if bad=='tenant':params['user']=SignedUser(e.stack.other_tenant,USER_A,'member')
    if bad=='method':params['method']='POST'
    if bad=='target':params['target']='/v1/base/run'
    if bad=='body':params['body']=b'placeholder-changed-body'
    if bad=='expired':params['now']=int(time.time())-120
    if bad=='future':params['now']=int(time.time())+120
    headers={'X-Tank-Key':e.stack.key,HEADER:sign_assertion(**params)}
    if bad=='missing':headers.pop(HEADER)
    response=await e.room_http.get(target,headers=headers)
    assert response.status_code in {401,403},response.text
    assert await owner_view(e)


@pytest.mark.asyncio
async def test_restart_and_concurrent_nonce_replay_cannot_restore_forget(base_entry):
    e=base_entry
    row=await seed(e)
    assert await owner_view(e)
    request=next(r for r in e.requests if r.url.path=='/v1/base/memory')
    replies=await asyncio.gather(*(e.room_http.request(request.method,str(request.url),headers=request.headers,content=request.content) for _ in range(2)))
    assert all(r.status_code in {401,403} for r in replies)
    assert (await e.request('memory/forget',{'user_id':USER_A,'memory_id':row['id']})).status_code==200
    # Restart just the nonce-store instance; SQL remains the replay authority.
    e.app.app.state.product_nonce_stores={}
    response=await e.room_http.request(request.method,str(request.url),headers=request.headers,content=request.content)
    assert response.status_code in {401,403}
    assert row['id'] not in json.dumps(await owner_view(e))


@pytest.mark.asyncio
async def test_sql_scope_before_vector_limit_and_restricted_role(base_entry,monkeypatch):
    e=base_entry
    for _ in range(4):await seed(e,USER_B)
    row=await seed(e)
    assert row['id'] in json.dumps(await owner_view(e))
    assert len(await owner_view(e,USER_B))>=4
    role='placeholder_base_'+uuid4().hex[:10]
    schema=e.stack.records.schema('base')
    await e.pool.execute(f'CREATE ROLE {role} NOSUPERUSER NOCREATEDB NOCREATEROLE')
    await e.pool.execute(f'GRANT USAGE,CREATE ON SCHEMA {schema} TO {role}')
    await e.pool.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {schema} TO {role}')
    import asyncpg,os
    restricted=await asyncpg.create_pool(os.environ['MEMORY_TEST_DATABASE_URL'],min_size=1,max_size=1,server_settings={'role':role})
    original=e.stack.records.pool
    e.stack.records.pool=restricted
    try:
        assert not await restricted.fetchval('SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname=current_user')
        assert row['id'] in json.dumps(await owner_view(e))
        assert row['id'] not in json.dumps(await owner_view(e,USER_B))
        assert (await e.stack.client(USER_A).recall(e.stack.tenant,'placeholder',limit=1))[0]['id']==row['id']
    finally:
        e.stack.records.pool=original
        await restricted.close()
        await e.pool.execute(f'DROP OWNED BY {role}')
        await e.pool.execute(f'DROP ROLE {role}')


@pytest.mark.asyncio
async def test_real_drive_batch_fresh_ids_repeat_and_changed_business_receipts(base_entry,monkeypatch):
    e=base_entry
    monkeypatch.setenv('BASE_BRAIN_URL','http://base-brain:8000')
    measurements=[]
    ids=[]
    for label,count in [('first',1),('repeat',1),('changed',2)]:
        before=len(e.provider_calls)
        response=await e.submit(count=count)
        if response.status_code==202:
            task_id=response.json()['task']['id'];ids.append(task_id)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                row=await e.queued(task_id)
                if row['status'] in {'done','failed'}:break
                await asyncio.sleep(.02)
            cfg=json.loads(row['input'])
            receipt=cfg.get('brain_receipt') or {}
        else:receipt={}
        measurements.append({'run':label,'http':response.status_code,'actual_provider_calls':len(e.provider_calls)-before,
            'cost_usd':receipt.get('cost_usd'),'tokens_in':receipt.get('tokens_in'),'tokens_out':receipt.get('tokens_out')})
    print('BASE_GATE78_MEASUREMENTS='+json.dumps(measurements,sort_keys=True))
    assert all(row['http']==202 for row in measurements),measurements
    assert len(set(ids))==3
    assert measurements[0]['actual_provider_calls']>0 and measurements[2]['actual_provider_calls']>0
    assert measurements[1]['actual_provider_calls']==measurements[1]['cost_usd']==measurements[1]['tokens_in']==measurements[1]['tokens_out']==0
    assert all(r.url.path!='/memory/bracket' for r in e.requests)
    assert await owner_view(e)


@pytest.mark.asyncio
@pytest.mark.parametrize('change',['user','tenant','business','ineligible'])
async def test_changed_inputs_and_foreign_owners_never_reuse(base_entry,monkeypatch,change):
    e=base_entry
    monkeypatch.setenv('BASE_BRAIN_URL','http://base-brain:8000')
    await run(e)
    options={'user':USER_B} if change=='user' else {'tenant':e.stack.other_tenant} if change=='tenant' else {'count':2} if change=='business' else {'preview':True}
    before=len(e.provider_calls)
    if change=='ineligible':
        response=await e.submit(**options)
        assert response.status_code in {403,409},response.text
    else:
        _,cfg=await run(e,**options)
        assert not cfg['brain_receipt'].get('answered_from_memory')
        assert len(e.provider_calls)>before


@pytest.mark.asyncio
@pytest.mark.parametrize('control',['correction','forget','off'])
async def test_durable_correction_forget_and_off_controls(base_entry,monkeypatch,control):
    e=base_entry
    monkeypatch.setenv('BASE_BRAIN_URL','http://base-brain:8000')
    _,first=await run(e)
    rows=await owner_view(e)
    assert rows
    if control=='correction':
        response=await e.request('memory/edit',{'user_id':USER_A,'memory_id':rows[0]['id'],'text':'placeholder corrected business'})
    elif control=='forget':
        response=await e.request('memory/forget',{'user_id':USER_A,'memory_id':rows[0]['id']})
    else:
        response=await e.request('memory/control',{'user_id':USER_A,'control':'off'})
    assert response.status_code==200,response.text
    _,second=await run(e,control='off' if control=='off' else 'edit')
    assert second!=first
    if control=='forget':
        assert rows[0]['id'] not in json.dumps(second)
    elif control=='correction':
        assert 'placeholder corrected business' in json.dumps(second)
    else:
        assert not second['brain_receipt'].get('answered_from_memory')
    assert not await owner_view(e,USER_B)


@pytest.mark.asyncio
@pytest.mark.parametrize('path',['/recall','/records','/memories'])
async def test_real_storage_outage_is_truthful_without_double_payment(base_entry,monkeypatch,path):
    e=base_entry
    monkeypatch.setenv('BASE_BRAIN_URL','http://base-brain:8000')
    e.faults['path']=path
    _,cfg=await run(e)
    receipt=cfg['brain_receipt']
    assert receipt['memory_bracket']['memory_unavailable'] is True
    assert not receipt.get('answered_from_memory')
    if path=='/memories':assert len(e.provider_calls)==1
    assert not await e.snapshot()


@pytest.mark.asyncio
@pytest.mark.parametrize('status',[401,403])
async def test_memory_auth_failure_never_degrades_to_paid(base_entry,status):
    e=base_entry
    await seed(e)
    before=await e.snapshot()
    e.faults.update(path='/records',status=status)
    response=await e.request('memory',{'user_id':USER_A,'task_key':'placeholder-batch'},method='GET')
    assert response.status_code in {401,403},response.text
    assert not e.provider_calls and await e.snapshot()==before


@pytest.mark.asyncio
async def test_default_off_and_historical_no_memory_path(base_entry,monkeypatch):
    e=base_entry
    before=await e.snapshot()
    response=await e.submit(control='historical')
    assert response.status_code==202,response.text
    await asyncio.sleep(.05)
    assert await e.snapshot()==before
    assert not [r for r in e.requests if r.url.host=='base-brain']
    assert not [r for r in e.requests if r.url.host=='hermes']
    monkeypatch.setenv('BASE_BRAIN_URL','http://base-brain:8000')
    _,cfg=await run(e,control='off')
    assert not [r for r in e.requests if r.url.host=='hermes' and r.url.path in {'/recall','/memories'}]
    assert cfg['brain_receipt']['status']=='done'


def test_all_original_requirements_and_real_worker_are_retained():
    manifest=json.loads(Path(__file__).with_name('base.json').read_text())
    assert set(manifest['cases'])==set(REQUIREMENTS)
    assert manifest['source_sha']==SOURCE_SHA and len(manifest['legacy_tests'])>=35
    worker=(ROOT/'agents/base/base_brain.py').read_text()
    assert 'async def drive_batch' in worker and 'run_code_first' in worker
    assert (ROOT/'agents/base/gates_memory.py').exists(), 'Base memory runtime has not been integrated into Tank main'


@pytest.mark.asyncio
async def test_retries_concurrency_and_meaningful_receipts(base_entry,monkeypatch):
    e=base_entry
    monkeypatch.setenv('BASE_BRAIN_URL','http://base-brain:8000')
    request_id=uuid4()
    responses=await asyncio.gather(e.submit(request_id=request_id),e.submit(request_id=request_id))
    # Existing try-advisory submission contract returns 409 while the winner commits.
    assert all(r.status_code in {202,409} for r in responses),[r.text for r in responses]
    assert any(r.status_code==202 for r in responses)
    responses = [await e.submit(request_id=request_id) if r.status_code==409 else r for r in responses]
    assert all(r.status_code==202 for r in responses),[r.text for r in responses]
    assert responses[0].json()['task']['id']==responses[1].json()['task']['id']
    task_id=responses[0].json()['task']['id']
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        row=await e.queued(task_id)
        if row['status'] in {'done','failed'}:break
        await asyncio.sleep(.02)
    assert row['status']=='done',dict(row)
    cfg=json.loads(row['input'])
    receipt=cfg['brain_receipt']
    assert receipt['model_receipts'] and e.provider_calls
    assert sum(r['tokens_in'] for r in receipt['model_receipts'])==400*len(e.provider_calls)
    assert sum(r['tokens_out'] for r in receipt['model_receipts'])==80*len(e.provider_calls)
    rows=await owner_view(e)
    assert rows and all((r.get('meta') or {}).get('user_id')==USER_A for r in rows)
    assert any('placeholder-business' in json.dumps(r) for r in rows)
    assert all((r.get('meta') or {}).get('reusable_result') for r in rows if r['kind']=='base.receipt')


@pytest.mark.asyncio
async def test_free_passes_precede_real_drive_batch(base_entry,monkeypatch):
    import sys
    e=base_entry
    monkeypatch.setenv('BASE_BRAIN_URL','http://base-brain:8000')
    events=[]
    previous=sys.getprofile()
    def observe(frame,event,arg):
        if event=='call' and frame.f_code.co_name in {'_run_batch','drive_batch'} and '/agents/base/' in frame.f_code.co_filename:
            events.append(frame.f_code.co_name)
    sys.setprofile(observe)
    try:
        await run(e,control='historical')
    finally:
        sys.setprofile(previous)
    assert '_run_batch' in events and 'drive_batch' in events
    assert events.index('_run_batch')<events.index('drive_batch')


@pytest.mark.asyncio
@pytest.mark.parametrize('accounting', ['recorded', 'missing_price', 'ledger_unavailable'])
async def test_drive_batch_persisted_inputs_and_unknown_accounting(gate78_memory, monkeypatch, accounting, base_module_scope):
    """Real worker/SQL/Hermes/signing; brain/ledger HTTP is an offline provider fixture."""
    import importlib
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import UUID

    import httpx

    stack = await gate78_memory('base')
    monkeypatch.syspath_prepend(str(ROOT / 'agents/base'))
    worker = importlib.import_module('base_brain')
    route = importlib.import_module('brain_route')
    room = importlib.import_module('room')
    pool = stack.records.pool
    async with pool.acquire() as conn:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_base')
        await room.ensure_tables(conn, recover=False)
    monkeypatch.setenv('BASE_BRAIN_URL', 'http://base-brain.test')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    posts = []
    real_http = httpx.AsyncClient

    def provider(request):
        if request.url.host == 'base-brain.test':
            body = json.loads(request.content)
            posts.append(body['task_id'])
            return httpx.Response(200, json={
                'tenant_id': stack.tenant, 'task_id': body['task_id'],
                'room': 'base', 'status': 'done', 'model_receipts': [],
            })
        assert request.url.host == 'tank.test'
        if accounting == 'ledger_unavailable':
            return httpx.Response(503, json={'detail': 'placeholder ledger outage'})
        return httpx.Response(200, json={'receipts': [{
            'ledger_id': str(uuid4()), 'cost_usd': None if accounting == 'missing_price' else .00056,
            'tokens_in': 400, 'tokens_out': 80,
        }]})

    transport = httpx.MockTransport(provider)
    # Keep the real product task/receipt routine; replace its HTTP edge only.
    monkeypatch.setattr(route, 'httpx', SimpleNamespace(AsyncClient=lambda **kw: real_http(transport=transport, **kw)))
    tenant = UUID(stack.tenant)
    rows = [{'name': 'placeholder-one', 'source': {'sha256': 'placeholder-source-a'}},
            {'name': 'placeholder-two', 'nested_id': str(uuid4())}]
    cfg = {'tenant_id': stack.tenant, 'batch': 'placeholder-identical-label', 'count': 2,
           'engine': None, 'preview': False, 'registry': None, 'model_spend': 0,
           'user_id': USER_A, 'created_by': USER_A, 'verified_user_id': USER_A,
           'refs': {'base.normalize': 'base.normalize@1.0.0'}, 'engine_data_version': '1.0.0',
           'memory_control': 'edit'}

    async def task(raws):
        task_id = uuid4()
        async with pool.acquire() as conn:
            await room.insert_batch(conn, tenant, USER_A, cfg['batch'], raws, '', False, None, 1, None, task_id=task_id)
        return task_id, dict(cfg)

    async def stored(task_id):
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT status,input FROM agent_base.tasks WHERE tenant_id=$1 AND id=$2', tenant, task_id)
            return row['status'], json.loads(row['input']) if isinstance(row['input'], str) else row['input']

    skills = SimpleNamespace(memory=stack.client(USER_A), _base='http://tank.test', _headers=lambda: {'X-Tank-Key': stack.key},
                             _http=real_http(transport=transport))
    try:
        first_id, first = await task(rows)
        if accounting != 'recorded':
            with pytest.raises(RuntimeError, match='cost is not recorded'):
                await worker.drive_batch(pool, skills, first_id, first, AsyncMock())
            status, saved = await stored(first_id)
            assert status == 'failed'
            assert saved['brain_spend'] is saved['model_spend'] is None
            assert saved['brain_receipt']['memory_bracket']['cost_usd'] is None
            assert len(posts) == 1
            assert await stack.client(USER_A).records(stack.tenant) == []
            return
        await worker.drive_batch(pool, skills, first_id, first, AsyncMock())
        assert (await stored(first_id))[0] == 'done'
        assert first['brain_spend'] == pytest.approx(.00056)
        # Actual signed Hermes records, not an in-process memory dictionary.
        memories = await stack.client(USER_A).records(stack.tenant)
        assert len(memories) == 1 and memories[0]['kind'] == 'base.receipt'
        assert await stack.client(USER_B).records(stack.tenant) == []
        repeat_id, repeat = await task(list(reversed(rows)))
        assert repeat_id != first_id
        await worker.drive_batch(pool, skills, repeat_id, repeat, AsyncMock())
        assert repeat['brain_receipt']['answered_from_memory'] is True
        assert len(posts) == 1
        # Same label/count/options with changed record content, then provenance.
        for field in ('name', 'source'):
            changed = json.loads(json.dumps(rows))
            changed[0][field] = 'placeholder-changed' if field == 'name' else {'sha256': 'placeholder-source-b'}
            changed_id, changed_cfg = await task(changed)
            await worker.drive_batch(pool, skills, changed_id, changed_cfg, AsyncMock())
            assert changed_cfg['brain_receipt']['memory_bracket']['answered_from_memory'] is False
            assert changed_cfg['brain_spend'] == pytest.approx(.00056)
            assert changed_id != first_id
        assert len(posts) == 3
    finally:
        await skills._http.aclose()
        async with pool.acquire() as conn:
            await conn.execute('DELETE FROM agent_base.records WHERE tenant_id=$1', tenant)
            await conn.execute('DELETE FROM agent_base.tasks WHERE tenant_id=$1', tenant)


@pytest.mark.asyncio
async def test_personal_planner_keeps_signed_owner_and_durable_receipt(base_entry, monkeypatch):
    """Real Base service and Tank ledger; no repeated gateway call after completion."""
    from chassis.user_assertion import SignedUser, sign_assertion
    e = base_entry
    monkeypatch.setenv('BASE_BRAIN_URL', 'http://base-brain:8000')
    await run(e)
    sent = next(request for request in e.requests if request.url.path == '/personal/tasks')
    before = len(e.provider_calls)
    # The exact wire request cannot be replayed, even if its work already finished.
    replay = await httpx.ASGITransport(app=e.brain.app).handle_async_request(sent)
    assert replay.status_code == 401
    body = json.loads(sent.content)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=e.brain.app), base_url='http://base-brain') as client:
        for user, expected in ((USER_A, 200), (USER_B, 403)):
            raw = json.dumps({**body, 'user_id': user}, separators=(',', ':')).encode()
            signed = sign_assertion('base', SignedUser(body['tenant_id'], user, 'member'),
                'POST', '/personal/tasks', raw, key=e.stack.key)
            result = await client.post('/personal/tasks', content=raw,
                headers={'X-Tank-Key': e.stack.key, 'Content-Type': 'application/json', HEADER: signed})
            assert result.status_code == expected, result.text
    assert len(e.provider_calls) == before
