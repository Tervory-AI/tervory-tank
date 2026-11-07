"""Real Skala entry-path acceptance. Absent runtime is a failure, never a skip."""
import asyncio
import importlib
import json
import os
import time
import uuid
from pathlib import Path

import asyncpg
import httpx
import pytest

from skala_fixture import skala_entry, USER_A, USER_B, TEXT, WORKSPACE_KEY, SKILL, VERSION
from hermes_lifecycle import personal_headers

# Register the owned fixture without replacing any shared fixture.
__all__ = ['skala_entry']
pytestmark = pytest.mark.asyncio


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def receipt(response):
    data = ok(response)
    assert data.get('_memory_receipts'), 'Live make_ctx/SkillContext.model did not expose its memory receipt'
    return data['_memory_receipts'][-1]


async def remembered(entry, **kwargs):
    result = receipt(await entry.run(**kwargs))
    rows = ok(await entry.control(**{k:v for k,v in kwargs.items() if k in {'tenant','user'}}))['memories']
    owned = [row for row in rows if row['kind'] == 'skala.receipt']
    assert owned, 'Actual skill route did not persist a Skala receipt in Hermes'
    assert result['ledger_id']
    return owned[0]


async def test_runtime_contract(skala_entry):
    entry = skala_entry
    root = Path(entry.runtime.__file__).resolve().parent
    for module in ('skala_gates_memory','skala_memory_api','skala_memory_client','skala_memory_wire'):
        spec = importlib.util.find_spec(module)
        assert spec and Path(spec.origin).parent == root, f'Missing integrated runtime: tank/{module}.py'
    paths = {route.path for route in entry.runtime.app.routes}
    assert {'/v1/skala/memory','/v1/skala/memory/edit','/v1/skala/memory/forget','/v1/skala/memory/off'} <= paths
    assert '/v1/skala/memory/bracket' not in paths, 'No fabricated paid-receipt shortcut'
    await remembered(entry)
    writes = [request for request in entry.network.captured if request[0:2] == ('POST','/memories')]
    assert writes
    assert all(headers['x-tank-key'] == entry.stack.key for _,_,headers,_ in writes)
    assert all('x-tervory-user-assertion' in headers for _,_,headers,_ in writes)


async def test_owner_crud(skala_entry):
    entry = skala_entry
    row = await remembered(entry)
    assert (row['meta']['user_id'],row['tenant_id']) == (USER_A,entry.stack.tenant)
    got = ok(await entry.control(memory_id=row['id']))['memories']
    assert [r['id'] for r in got] == [row['id']]
    ok(await entry.control('edit',memory_id=row['id'],text='placeholder corrected answer'))
    edited = ok(await entry.control(memory_id=row['id']))['memories'][0]
    assert edited['text'] == 'placeholder corrected answer'
    assert edited['meta']['user_id'] == USER_A
    ok(await entry.control('forget',memory_id=row['id']))
    assert row['id'] not in {r['id'] for r in ok(await entry.control())['memories']}
    assert await entry.stack.records.get('skala',entry.stack.tenant,row['id'],user_id=USER_A) is None


@pytest.mark.parametrize('foreign', ['same-tenant','other-tenant'])
@pytest.mark.parametrize('operation',['view','edit','forget','off'])
async def test_negative_controls_preserve_state(skala_entry,foreign,operation):
    entry = skala_entry
    row = await remembered(entry)
    tenant = entry.stack.other_tenant if foreign == 'other-tenant' else entry.stack.tenant
    before = await entry.rows()
    ledgers = await entry.ledger()
    result = await entry.control(operation,user=USER_B,tenant=tenant,memory_id=row['id'],
                                 text='placeholder forbidden change' if operation=='edit' else None)
    assert result.status_code in (401,403,404), result.text
    assert 'placeholder summary' not in result.text
    assert before == await entry.rows()
    assert ledgers == await entry.ledger()
    assert not ok(await entry.control(user=USER_B,tenant=tenant))['memories']
    # The real Hermes publish route must also refuse a guessed foreign row.
    body={'tenant_id':tenant,'user_id':USER_B}
    path=f"/records/{row['id']}/publish"
    headers,raw=personal_headers(entry.stack.key,'POST',path,tenant=tenant,user=USER_B,body=body)
    published=await entry.stack.http.post(path,headers=headers,content=raw)
    assert published.status_code in (401,403,404)
    assert before == await entry.rows()


async def test_no_declared_tenant_wide_kind(skala_entry):
    from hermes.user_scope import wide_kinds
    entry=skala_entry
    row=await remembered(entry)
    assert wide_kinds('skala') == []
    assert not ok(await entry.control(user=USER_B))['memories']
    for kind in ('skala.receipt','skala.skill_used'):
        body={'tenant_id':entry.stack.tenant,'text':'placeholder unowned row','kind':kind,'source':'placeholder-source','meta':{}}
        result=await entry.stack.http.post('/memories',headers={'X-Tank-Key':entry.stack.key},json=body)
        assert result.status_code in (400,401,403,422), result.text
    assert row['id'] in {r['id'] for r in ok(await entry.control())['memories']}


async def test_signin_body_impersonation_and_plain_tasks(skala_entry):
    entry=skala_entry
    owner=await remembered(entry)
    before=await entry.rows()
    # Genuine user B JWT cannot select owner A using a body or query.
    for operation in ('view','edit','forget','off'):
        result=await entry.control(operation,user=USER_A,headers=entry.headers(USER_B),memory_id=owner['id'],
                                   text='placeholder hijack' if operation=='edit' else None)
        assert result.status_code in (401,403),result.text
    assert before == await entry.rows()
    bare={'X-Tank-Key':WORKSPACE_KEY,'X-User-Id':USER_A,'X-Tervory-Tenant':entry.stack.tenant}
    for operation in ('view','edit','forget','off'):
        result=await entry.control(operation,headers=bare,memory_id=owner['id'],text='placeholder' if operation=='edit' else None)
        assert result.status_code in (401,403)
    plain=await entry.run('placeholder unsigned plain task',headers={'X-Tank-Key':WORKSPACE_KEY},extra={'user_id':USER_A})
    ok(plain)
    assert await entry.rows() == before
    assert len(entry.provider_calls)==2
    assert entry.issuer.calls, 'Actual local issuer/JWKS verification was not exercised'


@pytest.mark.parametrize('fault',['missing','wrong-key','audience','tenant','method','target','body','expired','future'])
async def test_assertion_rejection_on_shipped_client(skala_entry,fault):
    from chassis.user_assertion import sign_assertion, SignedUser
    entry=skala_entry
    await remembered(entry)
    before=await entry.rows()
    count=len(entry.provider_calls)
    def corrupt(request):
        actor=SignedUser(entry.stack.tenant,USER_A,'member')
        product,method,target,body,key,now='skala',request.method,request.url.raw_path.decode(),request.content,entry.stack.key,int(time.time())
        if fault=='missing':
            request.headers.pop('X-Tervory-User-Assertion',None)
            return
        if fault=='wrong-key': key='placeholder-wrong-key'
        if fault=='audience': product='tiger'
        if fault=='tenant': actor=SignedUser(entry.stack.other_tenant,USER_A,'member')
        if fault=='method': method='DELETE'
        if fault=='target': target='/placeholder-other-target'
        if fault=='body': body=b'placeholder altered body'
        if fault=='expired': now-=120
        if fault=='future': now+=120
        request.headers['X-Tervory-User-Assertion']=sign_assertion(product,actor,method,target,body,key=key,now=now)
    entry.network.mutate=corrupt
    result=await entry.control()
    assert result.status_code in (401,403), result.text
    assert await entry.rows()==before
    assert len(entry.provider_calls)==count
    assert 401 in entry.network.statuses


async def test_nonce_replay_restart_cannot_restore_forgotten_record(skala_entry):
    from hermes.service import create_app
    from hermes.store import InMemoryStore
    entry=skala_entry
    row=await remembered(entry)
    write=next(r for r in entry.network.captured if r[0:2]==('POST','/memories'))
    ok(await entry.control('forget',memory_id=row['id']))
    async def replay():
        app=create_app(InMemoryStore(),entry.stack.records.encoder,records=entry.stack.records)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://hermes') as client:
            return (await client.request(write[0],write[1],headers=write[2],content=write[3])).status_code
    assert await asyncio.gather(replay(),replay()) == [401,401]
    assert await entry.stack.records.get('skala',entry.stack.tenant,row['id'],user_id=USER_A) is None
    assert not ok(await entry.control())['memories']


async def test_sql_scope_precedes_vector_limit(skala_entry,monkeypatch):
    entry=skala_entry
    for index in range(3):
        await remembered(entry,text=f'placeholder foreign document {index}',user=USER_B)
    own=await remembered(entry)
    allowed={uuid.UUID(own['id'])}
    search=entry.stack.records.index.search
    calls=[]
    def observe(*args,**kwargs):
        ids={uuid.UUID(str(x)) for x in kwargs['allowed_ids']}
        assert ids <= allowed
        calls.append(ids)
        return search(*args,**kwargs)
    monkeypatch.setattr(entry.stack.records.index,'search',observe)
    assert receipt(await entry.run())['answered_from_memory'] is True
    assert [r['id'] for r in ok(await entry.control())['memories']] == [own['id']]
    assert calls
    calls.clear()
    assert receipt(await entry.run(tenant=entry.stack.other_tenant))['answered_from_memory'] is False
    assert calls == []


async def test_restricted_hermes_role(skala_entry,monkeypatch):
    entry=skala_entry
    schema=entry.stack.records.schema('skala')
    role='placeholder_skala_'+uuid.uuid4().hex[:12]
    admin=entry.stack.records.pool
    await admin.execute(f'CREATE ROLE {role} NOSUPERUSER NOBYPASSRLS NOLOGIN')
    restricted=None
    try:
        await admin.execute(f'GRANT USAGE ON SCHEMA {schema} TO {role}')
        await admin.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {schema} TO {role}')
        await admin.execute(f'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {role}')
        restricted=await asyncpg.create_pool(os.environ['MEMORY_TEST_DATABASE_URL'],min_size=1,max_size=1,
                                            server_settings={'role':role},statement_cache_size=0,ssl=False)
        flags=await restricted.fetchrow('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
        assert not flags['rolsuper'] and not flags['rolbypassrls']
        monkeypatch.setattr(entry.stack.records,'pool',restricted)
        await remembered(entry)
        assert not ok(await entry.control(user=USER_B))['memories']
    finally:
        monkeypatch.setattr(entry.stack.records,'pool',admin)
        if restricted:
            await restricted.close()
        await admin.execute(f'DROP OWNED BY {role}')
        await admin.execute(f'DROP ROLE {role}')


async def test_no_foreign_content_in_responses_receipts_logs(skala_entry,caplog):
    entry=skala_entry
    row=await remembered(entry)
    private='placeholder owner-only correction'
    ok(await entry.control('edit',memory_id=row['id'],text=private))
    response=await entry.run(user=USER_B)
    other=receipt(response)
    assert other['answered_from_memory'] is False
    assert private not in response.text
    assert private not in caplog.text
    assert entry.stack.key not in caplog.text
    assert private not in json.dumps(entry.provider_calls[-1])
    refused=await entry.control('edit',memory_id=row['id'],text='placeholder api_key=placeholder-secret')
    assert refused.status_code in (400,422)
    assert 'placeholder-secret' not in json.dumps(ok(await entry.control()))


async def test_defaults_off_no_new_memory_or_brain(skala_entry,monkeypatch):
    entry=skala_entry
    monkeypatch.delenv('SKALA_MEMORY_ENABLED',raising=False)
    monkeypatch.delenv('SKALA_BRAIN_ENABLED',raising=False)
    ok(await entry.run())
    ok(await entry.run())
    assert len(entry.provider_calls)==2
    assert await entry.rows()==[]
    assert entry.network.captured==[]
    assert not os.environ.get('SKALA_BRAIN_ENABLED')


@pytest.mark.parametrize('skill,version',[(SKILL,VERSION),('tier0.classify','1.0.0')])
async def test_task_path_recall_receipt_remember(skala_entry,skill,version):
    entry=skala_entry
    result=receipt(await entry.run(skill=skill,version=version))
    events=entry.events
    read=next(i for i,v in enumerate(events) if v[0]=='hermes' and v[2]=='/recall')
    provider=next(i for i,v in enumerate(events) if v[0]=='provider')
    write=next(i for i,v in enumerate(events) if v[0:3]==('hermes','POST','/memories'))
    assert read < provider < write
    assert result['paid_calls']==len(entry.provider_calls)==1
    rows=ok(await entry.control())['memories']
    assert any(skill+'@'+version in row['meta']['skills_used'] and version in row['meta']['versions_worked'] for row in rows)
    assert result['brain_enabled'] is False


async def test_free_skill_precedes_model_and_memory(skala_entry):
    entry=skala_entry
    data=ok(await entry.run(''))
    assert data['error']=='empty input'
    assert len(entry.provider_calls)==0
    assert entry.network.captured==[]
    assert data['_cost_usd']==0
    assert data['_receipt']['tokens_in']==data['_receipt']['tokens_out']==0


async def test_first_repeat_changed_costs(skala_entry,record_property):
    entry=skala_entry
    metrics=[]
    responses=[]
    for label,text in [('first',TEXT),('exact-repeat',TEXT),('changed-input',TEXT+' placeholder changed deadline')]:
        count=len(entry.provider_calls)
        before={str(row['id']) for row in await entry.ledger()}
        response=await entry.run(text)
        responses.append(response)
        ok(response)
        rows=[row for row in await entry.ledger() if str(row['id']) not in before]
        metrics.append({'run':label,'cost_usd':sum(float(row['cost_usd']) for row in rows),
                        'tokens_in':sum(row['tokens_in'] for row in rows),'tokens_out':sum(row['tokens_out'] for row in rows),
                        'provider_calls':len(entry.provider_calls)-count})
    print('SKALA_FIXTURE_METRICS '+json.dumps(metrics,sort_keys=True))
    record_property('skala_fixture_metrics',json.dumps(metrics,sort_keys=True))
    assert [m['provider_calls'] for m in metrics]==[1,0,1],metrics
    assert metrics[1]['cost_usd']==metrics[1]['tokens_in']==metrics[1]['tokens_out']==0
    repeat=receipt(responses[1])
    assert repeat['answered_from_memory'] is True
    assert repeat['would_have_cost']=={'cost_usd':.05,'tokens_in':10,'tokens_out':3}


@pytest.mark.parametrize('change',['input','user','tenant','ineligible'])
async def test_nonidentical_and_ineligible_miss(skala_entry,change):
    entry=skala_entry
    await remembered(entry)
    args={'text':TEXT+' placeholder changed'} if change=='input' else {'user':USER_B} if change=='user' else {'tenant':entry.stack.other_tenant} if change=='tenant' else {'skill':'tier0.classify','version':'1.0.0'}
    if change=='ineligible':
        # classify uses route.request, which is not an eligible repeat task type.
        receipt(await entry.run(**args))
    count=len(entry.provider_calls)
    result=receipt(await entry.run(**args))
    assert len(entry.provider_calls)==count+1
    assert result['answered_from_memory'] is False


async def test_correction_then_forget_invalidates_repeat(skala_entry):
    entry=skala_entry
    row=await remembered(entry)
    corrected='placeholder use the corrected company result'
    ok(await entry.control('edit',memory_id=row['id'],text=corrected))
    count=len(entry.provider_calls)
    response=await entry.run()
    assert ok(response)['text']==corrected
    assert receipt(response)['answered_from_memory'] is True
    assert len(entry.provider_calls)==count
    assert corrected not in (await entry.run(user=USER_B)).text
    ok(await entry.control('forget',memory_id=row['id']))
    count=len(entry.provider_calls)
    result=receipt(await entry.run())
    assert result['answered_from_memory'] is False
    assert len(entry.provider_calls)==count+1
    assert corrected not in json.dumps(result)


async def test_off_is_per_user_and_disables_reuse(skala_entry):
    entry=skala_entry
    await remembered(entry)
    await remembered(entry,user=USER_B)
    ok(await entry.control('off'))
    before=await entry.rows()
    count=len(entry.provider_calls)
    result=receipt(await entry.run())
    assert result['memory_enabled'] is False and result['answered_from_memory'] is False
    assert len(entry.provider_calls)==count+1
    assert await entry.rows()==before
    other=receipt(await entry.run(user=USER_B))
    assert other['memory_enabled'] is True and other['answered_from_memory'] is True
    assert len(entry.provider_calls)==count+1


@pytest.mark.parametrize('operation',[('POST','/recall'),('GET','/records'),('POST','/memories')])
async def test_outage_and_post_payment_retry(skala_entry,operation):
    entry=skala_entry
    await remembered(entry)
    entry.network.outage=operation
    count=len(entry.provider_calls)
    run_id=uuid.uuid4()
    if operation==('GET','/records'):
        result=await entry.control()
        assert result.status_code==503,result.text
        assert 'unavailable' in result.text.lower()
        assert len(entry.provider_calls)==count
        return
    response=await entry.run(TEXT+' placeholder outage task',run_id=run_id)
    result=receipt(response)
    assert result['memory_unavailable'] is True and result['answered_from_memory'] is False
    assert len(entry.provider_calls)==count+1
    # Same durable run after a remember failure must use the existing paid checkpoint.
    if operation==('POST','/memories'):
        entry.network.outage=None
        again=receipt(await entry.run(TEXT+' placeholder outage task',run_id=run_id))
        assert len(entry.provider_calls)==count+1
        assert again['ledger_id']==result['ledger_id']


@pytest.mark.parametrize('status',[401,403])
async def test_auth_failure_is_not_outage_or_cached_answer(skala_entry,status):
    entry=skala_entry
    await remembered(entry)
    entry.network.outage=('POST','/recall')
    entry.network.status=status
    count=len(entry.provider_calls)
    result=await entry.run()
    assert result.status_code in (401,403),result.text
    assert 'placeholder summary' not in result.text
    assert len(entry.provider_calls)==count


async def test_same_run_concurrency_and_retry(skala_entry):
    entry=skala_entry
    run_id=uuid.uuid4()
    results=await asyncio.gather(entry.run(run_id=run_id),entry.run(run_id=run_id))
    assert all(r.status_code in (200,409) for r in results)
    assert any(r.status_code==200 for r in results)
    again=receipt(await entry.run(run_id=run_id))
    assert len(entry.provider_calls)==1
    assert len(await entry.ledger())==1
    assert again['user_id']==USER_A
    assert all((json.loads(row['meta']) if isinstance(row['meta'],str) else row['meta'])['user_id']==USER_A for row in await entry.rows())


async def test_signed_product_control_consumes_durable_nonce(skala_entry):
    from chassis.user_assertion import sign_assertion, SignedUser
    entry=skala_entry
    row=await remembered(entry)
    body={'tenant_id':entry.stack.tenant,'user_id':USER_A,'memory_id':row['id'],'text':'placeholder assertion correction'}
    raw=json.dumps(body,sort_keys=True,separators=(',',':')).encode()
    target='/v1/skala/memory/edit'
    assertion=sign_assertion('skala',SignedUser(entry.stack.tenant,USER_A,'member'),'POST',target,raw,key=entry.stack.key)
    headers={'X-Tank-Key':WORKSPACE_KEY,'Content-Type':'application/json','X-Tervory-User-Assertion':assertion}
    ok(await entry.client.post(target,headers=headers,content=raw))
    before=await entry.rows()
    # A new HTTP connection cannot reuse the consumed nonce.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=entry.runtime.app),base_url='http://placeholder-tank') as worker:
        replay=await worker.post(target,headers=headers,content=raw)
    assert replay.status_code==401,replay.text
    assert before==await entry.rows()
    altered={**body,'user_id':USER_B}
    fresh=sign_assertion('skala',SignedUser(entry.stack.tenant,USER_A,'member'),'POST',target,raw,key=entry.stack.key)
    rejected=await entry.client.post(target,headers={**headers,'X-Tervory-User-Assertion':fresh},json=altered)
    assert rejected.status_code==401
    assert before==await entry.rows()


async def test_invalid_real_issuer_signature_refuses_all_work(skala_entry):
    entry=skala_entry
    headers=entry.headers()
    encoded=headers['x-trigger-signin-token'].split('.')
    encoded[2]=('A' if encoded[2][0]!='A' else 'B')+encoded[2][1:]
    headers['x-trigger-signin-token']='.'.join(encoded)
    result=await entry.run(headers=headers)
    assert result.status_code in (401,403),result.text
    assert await entry.rows()==[]
    assert entry.provider_calls==[]


async def test_preview_uses_same_verified_model_bracket(skala_entry):
    entry=skala_entry
    result=receipt(await entry.run(preview=True))
    assert result['user_id']==USER_A and result['tenant_id']==entry.stack.tenant
    assert result['paid_calls']==len(entry.provider_calls)==1
    assert result['brain_enabled'] is False
    assert any(request[0:2]==('POST','/memories') for request in entry.network.captured)


async def test_approval_evals_use_platform_receipts_without_personal_reuse(skala_entry):
    entry=skala_entry
    path=f'/v1/skala/{SKILL}/{VERSION}/evals'
    # This is the actual manual approval handler and its committed eval cases.
    # It must execute model-backed cases, even when personal memory is enabled.
    result=ok(await entry.client.post(path,json={'by':'placeholder-reviewer'},headers=entry.headers()))
    assert result['total'] > 0
    assert entry.provider_calls
    rows=await entry.ledger(str(entry.runtime.PLATFORM_TENANT))
    assert sum(float(row['cost_usd']) for row in rows)==pytest.approx(.05*len(entry.provider_calls))
    assert sum(row['tokens_in'] for row in rows)==10*len(entry.provider_calls)
    assert sum(row['tokens_out'] for row in rows)==3*len(entry.provider_calls)
    assert await entry.ledger()==[]
    assert await entry.rows()==[]
    assert entry.network.captured==[]
