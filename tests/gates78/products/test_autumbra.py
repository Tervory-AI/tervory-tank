"""Gate 7/8 acceptance through Watch, Tank's corridor and the real shared Hermes stack."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlencode
import uuid

import pytest
import yaml
from gates78.products.autumbra_stack import autumbra, A, B, TASK, TEXT, COST, TOKENS_IN, TOKENS_OUT, ROOT

# Imported fixture is intentionally part of this module's public pytest surface.
__all__ = ['autumbra']
pytestmark = pytest.mark.asyncio


def query(tenant, user):
    return '?' + urlencode({'tenant_id':tenant,'user_id':user})


async def test_runtime_contract():
    import ghost_routes
    routes = {(method, route.path) for route in ghost_routes.router.routes for method in route.methods}
    expected = {('POST','/v1/ghost/autumbra/memory/recall'), ('PATCH','/v1/ghost/autumbra/memory/memories/{id}'),
                ('POST','/v1/ghost/autumbra/personal/{path:path}')}
    missing = sorted(expected - routes)
    modules = [name for name in ('agents.ghost.brain','agents.ghost.brain_service','agents.ghost.brain_state')
               if importlib.util.find_spec(name) is None]
    assert not missing and not modules, f'BLOCKED Autumbra PR #3 runtime dependency: routes={missing}, modules={modules}; do not apply proposal patches in acceptance'


@pytest.mark.parametrize('kind', ['incident','worked_fix','false_alarm','maintenance_window','baseline','correction','outcome'])
async def test_owner_crud_and_meaningful_kinds(autumbra, kind):
    b = autumbra
    row = await b.write(kind=kind)
    rid = row['id']
    assert rid in {r['id'] for r in await b.rows()}
    got = await b.request('GET', '/memory/' + rid + query(b.stack.tenant,A))
    assert got.status_code == 200 and got.json()['kind'] == kind
    assert got.json()['evidence'] and got.json()['confidence'] == 1
    recalled = await b.request('POST','/memory/recall',body={'tenant_id':b.stack.tenant,'user_id':A,'text':'failed deployment'})
    assert recalled.status_code == 200 and rid in {r['id'] for r in recalled.json()['memories']}
    edited = await b.request('PATCH','/memory/'+rid,body={'tenant_id':b.stack.tenant,'user_id':A,'text':'Owner verified resolution'})
    assert edited.status_code == 200
    assert (await b.rows())[0]['text'] == 'Owner verified resolution'
    removed = await b.request('DELETE','/memory/'+rid+query(b.stack.tenant,A))
    assert removed.status_code == 200 and await b.rows() == []
    assert ('POST','tank','/v1/ghost/autumbra/memory/memories') in b.state.network
    assert ('POST','hermes','/memories') in b.state.network


@pytest.mark.parametrize('foreign', ['same_tenant','other_tenant'])
@pytest.mark.parametrize('control', ['view','edit','forget','off','publish'])
async def test_foreign_controls_refused_without_mutation(autumbra, foreign, control):
    b = autumbra
    row = await b.write(text='placeholder-owner-private-content')
    owner_rows = await b.rows()
    tenant = b.stack.tenant if foreign == 'same_tenant' else b.stack.other_tenant
    user = B if foreign == 'same_tenant' else A
    before_state = list(b.store.db.execute('SELECT * FROM ghost_state'))
    if control == 'view':
        response = await b.request('GET','/memory/'+row['id']+query(tenant,user),user=user,tenant=tenant)
    elif control == 'edit':
        response = await b.request('PATCH','/memory/'+row['id'],user=user,tenant=tenant,
                                   body={'tenant_id':tenant,'user_id':user,'text':'forged edit'})
    elif control == 'forget':
        response = await b.request('DELETE','/memory/'+row['id']+query(tenant,user),user=user,tenant=tenant)
    elif control == 'off':
        response = await b.request('PUT','/memory/settings',user=user,tenant=tenant,
                                   body={'tenant_id':b.stack.tenant,'user_id':A,'off':True})
    else:
        response = await b.request('POST','/memory/'+row['id']+'/publish',user=user,tenant=tenant,
                                   body={'tenant_id':tenant,'user_id':user})
    assert response.status_code in {401,403,404}
    assert 'placeholder-owner-private-content' not in response.text
    assert await b.rows() == owner_rows
    assert list(b.store.db.execute('SELECT * FROM ghost_state')) == before_state
    assert await b.rows(user=user,tenant=tenant) == []


async def test_tenant_wide_standing_blocks_stay_unindexed(autumbra):
    from chassis.memory import MemoryClient
    b = autumbra
    # This service-owned path is intentionally infrastructure identity, NOT signed-user proof.
    memory = MemoryClient('http://tank:8000/v1/ghost/autumbra/memory', b.stack.key, 'ghost', b.tank._http)
    row = await memory.remember(b.stack.tenant,'198.51.100.23','blocked_address','autumbra',index=False,tenant_wide=True)
    assert row['id'] in {r['id'] for r in await memory.records(b.stack.tenant)}
    assert row['id'] not in {r['id'] for r in await memory.records(b.stack.other_tenant)}
    with pytest.raises(RuntimeError, match='422'):
        await memory.remember(b.stack.tenant,'198.51.100.24','blocked_address','autumbra',index=False,user_id=A)
    with pytest.raises(RuntimeError, match='422'):
        await memory.remember(b.stack.tenant,'198.51.100.25','blocked_address','autumbra',tenant_wide=True)
    assert not b.stack.records.encoder.calls


async def test_required_owner_unsigned_and_body_impersonation(autumbra):
    b = autumbra
    payload = {'tenant_id':b.stack.tenant,'user_id':A,'kind':'incident','text':'forged owner','evidence':['urn:fixture']}
    unsigned = await b.direct.post('/memory',json=payload)
    assert unsigned.status_code == 401
    forged = await b.request('POST','/memory',user=B,body=payload)
    assert forged.status_code == 403 and await b.rows() == []
    payload['meta'] = {'user_id':B,'scope':'tenant'}
    extra = await b.request('POST','/memory',body=payload)
    assert extra.status_code == 422
    assert await b.rows() == []


async def test_real_oidc_signed_actor_and_header_impersonation(autumbra):
    b = autumbra
    await b.write()
    assert b.provider.calls  # Actual discovery/JWK verification at the network boundary.
    assert any(h.get('x-tervory-user-assertion') for _,_,_,h in b.state.signed)
    response = await b.request('GET','/memory'+query(b.stack.tenant,A),user=B,headers={'X-Tervory-User':A})
    assert response.status_code == 403
    bad_role = await b.request('GET','/memory'+query(b.stack.tenant,A),headers={'X-Tervory-Role':'founder'})
    assert bad_role.status_code == 403
    response = await b.request('GET','/memory'+query(b.stack.tenant,A),headers={'x-trigger-signin-token':'placeholder-invalid-jwt'})
    assert response.status_code == 401 and response.json() == {'detail':'Trigger sign-in required'}
    assert len(await b.rows()) == 1


@pytest.mark.parametrize('fault',['missing','wrong_key','audience','tenant','method','target','body','expired','future'])
async def test_assertion_rejection(autumbra, fault):
    from chassis.user_assertion import SignedUser, sign_assertion, HEADER
    b = autumbra
    payload = {'tenant_id':b.stack.tenant,'user_id':A,'off':True}
    raw = json.dumps(payload).encode()
    actor = SignedUser(b.stack.other_tenant if fault == 'tenant' else b.stack.tenant,A,'member')
    token = sign_assertion('base' if fault == 'audience' else 'ghost',actor,
        'GET' if fault == 'method' else 'PUT','/memory' if fault == 'target' else '/memory/settings',
        b'{}' if fault == 'body' else raw, key='placeholder-wrong-key' if fault == 'wrong_key' else b.stack.key,
        now=int(time.time()) + (120 if fault == 'future' else -120 if fault == 'expired' else 0))
    response = await b.direct.put('/memory/settings',content=raw,
        headers={'Content-Type':'application/json', **({HEADER:token} if fault != 'missing' else {})})
    assert response.status_code == 401
    assert not b.watch.state.user_memory.is_off(b.stack.tenant,A)


async def test_assertion_replay_concurrent_and_after_worker_restart(autumbra):
    from chassis.user_assertion import SignedUser, sign_assertion, HEADER
    from agents.ghost.brain_state import BrainState
    from agents.ghost.store import Store
    b = autumbra
    row = await b.write()
    method, target, content, headers = b.state.signed[-1]
    assert (await b.request('DELETE','/memory/'+row['id']+query(b.stack.tenant,A))).status_code == 200
    replay = await b.direct.request(method,target,content=content,headers=headers)
    assert replay.status_code == 401 and await b.rows() == []
    raw = json.dumps({'tenant_id':b.stack.tenant,'user_id':A,'off':True}).encode()
    token = sign_assertion('ghost',SignedUser(b.stack.tenant,A,'member'),'PUT','/memory/settings',raw,key=b.stack.key)
    async def use():
        return await b.direct.put('/memory/settings',content=raw,headers={'Content-Type':'application/json',HEADER:token})
    replies = await asyncio.gather(use(),use())
    assert sorted(r.status_code for r in replies) == [200,401]
    path = b.store.db.execute('PRAGMA database_list').fetchone()[2]
    restarted_store = Store(Path(path))
    b.watch.state.store = restarted_store
    assert (await use()).status_code == 401
    assert await BrainState(restarted_store).claim(b.stack.tenant,'placeholder-fresh-unique-nonce',int(time.time())+60)
    restarted_store.close()
    b.watch.state.store = b.store


async def test_sql_scope_precedes_vector_limit(autumbra, monkeypatch):
    b = autumbra
    foreign = [await b.write(user=B,text=f'foreign candidate {n}') for n in range(22)]
    own = await b.write(text='owner candidate')
    searches = []
    original = b.stack.records.index.search
    def observe(*args, **kwargs):
        searches.append(kwargs.get('allowed_ids'))
        return original(*args,**kwargs)
    monkeypatch.setattr(b.stack.records.index,'search',observe)
    response = await b.request('POST','/memory/recall',body={'tenant_id':b.stack.tenant,'user_id':A,'text':'candidate'})
    assert response.status_code == 200 and {r['id'] for r in response.json()['memories']} == {own['id']}
    assert searches and all(ids is not None and own['id'] in ids for ids in searches)
    assert not any(r['id'] in ids for ids in searches for r in foreign)
    response = await b.request('POST','/memory/recall',tenant=b.stack.other_tenant,
                               body={'tenant_id':b.stack.other_tenant,'user_id':A,'text':'candidate'})
    assert response.status_code == 200 and response.json()['memories'] == []


async def test_restricted_database_role_actual_product_crud(autumbra):
    b = autumbra
    async with b.stack.records.pool.acquire() as conn:
        role = await conn.fetchrow('SELECT rolname,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
        assert role['rolname'] == b.role and not role['rolsuper'] and not role['rolbypassrls']
        # Observe the staged RLS setting; acceptance never enables it ahead of deployment.
        enabled = await conn.fetchval('SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass($1)',b.stack.records.schema('ghost')+'.memory_records')
        assert enabled is False
    row = await b.write()
    assert (await b.request('DELETE','/memory/'+row['id']+query(b.stack.tenant,A))).status_code == 200
    assert await b.rows() == []


async def test_plain_authorised_task_without_identity_has_no_personal_memory(autumbra):
    b = autumbra
    before = list(b.stack.calls)
    response = await b.direct.post('/brain/tasks',json={'tenant_id':b.stack.tenant,'user_id':A,
                    'task_type':'ghost.brain.classify_alert','text':'Workspace is slow'})
    assert response.status_code == 200 and response.json()['source'] == 'code'
    assert response.json()['user_id'] is None and b.stack.calls == before and not b.state.provider_calls
    assert (await b.direct.get('/memory'+query(b.stack.tenant,A))).status_code == 401


async def test_no_private_content_or_secrets_in_responses_receipts_logs(autumbra, caplog):
    b = autumbra
    await b.write(text='placeholder-alice-private')
    result = await b.task(user=B)
    assert 'placeholder-alice-private' not in json.dumps(result) + caplog.text
    response = await b.request('POST','/memory',body={'tenant_id':b.stack.tenant,'user_id':A,'kind':'worked_fix',
        'text':'password: EXAMPLE','evidence':['urn:fixture']})
    assert response.status_code == 200 and response.json()['saved'] is False
    assert 'EXAMPLE' not in json.dumps(await b.rows()) + caplog.text


async def test_default_off_no_memory_checkpoint_model_or_reschedule(autumbra, monkeypatch):
    b = autumbra
    monkeypatch.delenv('GHOST_BRAIN_ENABLED')
    before_calls = list(b.stack.calls)
    result = await b.request('POST','/brain/tasks',body={'task_type':TASK,'text':TEXT})
    assert result.status_code == 503 and 'GHOST_BRAIN_ENABLED' in result.text
    assert b.stack.calls == before_calls and b.state.provider_calls == []
    assert b.state.network == []
    assert b.store.db.execute('SELECT count(*) FROM ghost_brain_runs').fetchone()[0] == 0
    assert (await b.request('POST','/memory',body={'tenant_id':b.stack.tenant,'user_id':A,'kind':'incident',
            'text':'should not save','evidence':['urn:fixture']})).status_code == 503


@pytest.mark.parametrize('setting', [None, 'false'])
async def test_direct_tank_route_default_off_has_no_work(autumbra, monkeypatch, setting):
    b = autumbra
    if setting is None:
        monkeypatch.delenv('GHOST_BRAIN_ENABLED')
    else:
        monkeypatch.setenv('GHOST_BRAIN_ENABLED',setting)
    payload = {'tenant_id':b.stack.tenant,'task_type':TASK,'messages':[{'role':'user','content':TEXT}]}
    async with b.tank.pool().acquire() as conn:
        policies = await conn.fetch("SELECT semantic_cache,cache_scope,matter_matching FROM tank.policy WHERE task_type LIKE 'ghost.brain.%'")
        assert len(policies) == 4
        assert all(not p['semantic_cache'] and p['cache_scope'] == 'none' and p['matter_matching'] for p in policies)
        tables = ('ledger','engine_state','engine_evals','route_cache')
        before = [await conn.fetchval('SELECT count(*) FROM tank.'+table) for table in tables]
    response = await b.client.post('/v1/route',json=payload,headers={'X-Tank-Key':b.stack.key})
    assert response.status_code == 503 and 'GHOST_BRAIN_ENABLED' in response.text
    # Internal calls without a task id have the same gate as HTTP calls.
    from fastapi import HTTPException
    with pytest.raises(HTTPException, match='GHOST_BRAIN_ENABLED'):
        await b.tank._check_route_task(b.tank.RouteRequest(**payload),None)
    assert b.tank.model_call_refusal(TEXT,'luna',box='us-east',tenant_id=b.stack.tenant,task_type=TASK) == 'GHOST_BRAIN_ENABLED is off.'
    async with b.tank.pool().acquire() as conn:
        assert before == [await conn.fetchval('SELECT count(*) FROM tank.'+table) for table in tables]
    assert not b.state.network and not b.state.provider_calls and not b.stack.calls
    assert b.store.db.execute('SELECT count(*) FROM ghost_brain_runs').fetchone()[0] == 0


@pytest.mark.parametrize('refusal', ['service_key','signin','grant','path','method'])
async def test_shipped_ingress_auth_grant_and_allowlist(autumbra, refusal):
    b = autumbra
    if refusal == 'service_key':
        response = await b.request('GET','/memory',headers={'X-Tank-Key':'placeholder-wrong-key'})
    elif refusal == 'signin':
        response = await b.client.get('/v1/ghost/autumbra/personal/memory',
                    headers={'X-Tank-Key':b.tank.TANK_API_KEY,'X-Tervory-Tenant':b.stack.tenant,'X-Tervory-User':A})
    elif refusal == 'grant':
        response = await b.request('GET','/memory',role='member')
    elif refusal == 'path':
        response = await b.request('POST','/enforce/create',body={})
    else:
        response = await b.request('DELETE','/brain/tasks')
    assert response.status_code in {401,403,404}, response.text
    assert not b.state.network and not b.state.provider_calls
    assert b.store.db.execute('SELECT count(*) FROM ghost_brain_runs').fetchone()[0] == 0


async def test_opt_in_deployment_and_existing_boundaries():
    room = yaml.safe_load((ROOT/'agents/ghost/docker-compose.yml').read_text())
    assert 'autumbra-brain' in room['services'], 'BLOCKED: product runtime not integrated'
    assert room['services']['autumbra-brain']['profiles'] == ['brain']
    assert room['services']['ghost-sandbox']['profiles'] == ['brain']
    assert room['services']['agent-ghost']['environment']['GHOST_BRAIN_ENABLED'] == '${GHOST_BRAIN_ENABLED:-false}'
    assert room['services']['ghost-sandbox']['networks'] == ['sandbox']


async def test_actual_task_receipt_remember_and_exact_business_repeat(autumbra):
    b = autumbra
    first = await b.task()
    first_calls = len(b.state.provider_calls)
    repeat = await b.task()
    changed = await b.task(text=TEXT + ' after rollback')
    assert first['status'] == repeat['status'] == changed['status'] == 'done'
    assert first_calls == 1 and len(b.state.provider_calls) == 2
    import engine_ladder
    assert b.state.catalogue == engine_ladder.order({'model':'luna'})
    assert all(call['model'] == b.state.catalogue[0] for call in b.state.provider_calls)
    assert first['task_id'] != repeat['task_id'] != changed['task_id']
    assert (first['cost_usd'],first['tokens_in'],first['tokens_out']) == (COST,TOKENS_IN,TOKENS_OUT)
    assert (repeat['cost_usd'],repeat['tokens_in'],repeat['tokens_out']) == (0,0,0)
    assert repeat['would_have_cost_usd'] == COST and repeat['answer'] == first['answer']
    assert (changed['cost_usd'],changed['tokens_in'],changed['tokens_out']) == (COST,TOKENS_IN,TOKENS_OUT)
    assert changed['answer'] != first['answer']
    paths = [(host,path) for _,host,path in b.state.network]
    assert paths.index(('hermes','/recall')) < paths.index(('litellm','/v1/chat/completions')) < paths.index(('hermes','/memories'))
    row = next(r for r in await b.rows() if r['meta'].get('task_id') == first['task_id'])
    assert row['evidence'] and row['meta']['input_hash'] and row['meta']['tokens_in'] == TOKENS_IN
    assert row['confidence'] == 0  # Unverified model output is never asserted as human verification.
    async with b.tank.pool().acquire() as conn:
        receipts = await conn.fetch('SELECT cost_usd,tokens_in,tokens_out FROM tank.ledger WHERE tenant_id=$1 AND task_type=$2',uuid.UUID(b.stack.tenant),TASK)
    assert len(receipts) == 2 and sum(float(r['cost_usd']) for r in receipts) == 2*COST
    print(f'FAKE provider: first calls=1 cost={COST} tokens={TOKENS_IN}/{TOKENS_OUT}; exact repeat calls=0 cost=0 tokens=0/0; changed calls=1 cost={COST} tokens={TOKENS_IN}/{TOKENS_OUT}')


async def test_missing_serving_rung_does_not_bypass_ladder(autumbra):
    b = autumbra
    missing = b.state.catalogue.pop(0)
    response = await b.client.post('/v1/route',headers={'X-Tank-Key':b.stack.key},
        json={'tenant_id':b.stack.tenant,'task_type':TASK,'messages':[{'role':'user','content':TEXT}]})
    assert response.status_code == 503 and 'Engine rung unavailable: ' + missing in response.text
    assert not b.state.provider_calls


async def test_free_code_before_model(autumbra):
    b = autumbra
    result = await b.task(task_type='ghost.brain.classify_alert',text='Workspace is slow')
    assert result['source'] == 'code' and result['cost_usd'] == 0 and not b.state.provider_calls


async def test_scope_input_and_ineligible_misses(autumbra):
    b = autumbra
    await b.task()
    await b.task(user=B)
    await b.task(tenant=b.stack.other_tenant)
    await b.task(text=TEXT+' changed')
    await b.task(task_type='ghost.brain.plan_fix')
    await b.task(task_type='ghost.brain.plan_fix')
    assert len(b.state.provider_calls) == 6


async def test_correction_and_forget_invalidate_derived_answers(autumbra):
    b = autumbra
    original = await b.task()
    body = {'tenant_id':b.stack.tenant,'user_id':A,'task_type':TASK,'text':TEXT,'corrected':'Owner confirmed a maintenance window.'}
    assert (await b.request('POST','/brain/corrections',body=body)).status_code == 200
    corrected = await b.task()
    assert corrected['answer'] == body['corrected'] and len(b.state.provider_calls) == 1
    assert (await b.task(user=B))['answer'] != body['corrected']
    correction = next(r for r in await b.rows() if r['kind'] == 'correction')
    assert (await b.request('DELETE','/memory/'+correction['id']+query(b.stack.tenant,A))).status_code == 200
    fresh = await b.task()
    assert fresh['source'] == 'brain' and fresh['answer'] not in {body['corrected'],original['answer']}
    assert len(b.state.provider_calls) == 3
    old = await b.task(run_id=original['task_id'])
    assert old['answer'] is None and old['status'] == 'invalidated'


async def test_memory_off_is_per_owner_and_prevents_reuse(autumbra):
    b = autumbra
    await b.task()
    await b.task(user=B)
    assert (await b.request('PUT','/memory/settings',body={'tenant_id':b.stack.tenant,'user_id':A,'off':True})).status_code == 200
    before = list(b.stack.calls)
    await b.task()
    assert b.stack.calls == before
    assert (await b.task(user=B))['source'] == 'memory_repeat'
    assert len(b.state.provider_calls) == 3


@pytest.mark.parametrize('edge',[('POST','/recall'),('GET','/records'),('POST','/memories')])
async def test_memory_outage_truthful_and_no_second_payment(autumbra, edge):
    b = autumbra
    b.state.fault = (edge,'timeout')
    run_id = str(uuid.uuid4())
    result = await b.task(run_id=run_id)
    assert result['status'] == 'done' and result['memory_status'] == 'unavailable'
    assert result['cost_usd'] == COST and len(b.state.provider_calls) == 1
    repeated = await b.task(run_id=run_id)
    assert repeated['replayed'] and repeated['answer'] == result['answer'] and len(b.state.provider_calls) == 1


async def test_memory_auth_refusal_never_becomes_outage_fallback(autumbra):
    b = autumbra
    await b.task()
    b.state.fault = (('POST','/recall'),403)
    response = await b.request('POST','/brain/tasks',body={'tenant_id':b.stack.tenant,'user_id':A,'task_type':TASK,'text':TEXT})
    assert response.status_code == 403 and len(b.state.provider_calls) == 1
    assert 'Fixture analysis' not in response.text


async def test_concurrent_paid_retry_and_restart(autumbra):
    from agents.ghost.brain import Brain, UserMemory, classify_alert_code
    from agents.ghost.store import Store
    b = autumbra
    run_id = str(uuid.uuid4())
    replies = await asyncio.gather(b.task(run_id=run_id), b.task(run_id=run_id))
    assert len(b.state.provider_calls) == 1
    assert {r['status'] for r in replies} <= {'pending','done'}
    filename = b.store.db.execute('PRAGMA database_list').fetchone()[2]
    restarted = Store(Path(filename))
    previous = b.watch.state.brain
    b.watch.state.brain = Brain(UserMemory(b.watch.state.user_memory.memory,restarted), previous.service,[classify_alert_code])
    replay = await b.task(run_id=run_id)
    assert replay['replayed'] and replay['status'] == 'done' and len(b.state.provider_calls) == 1
    restarted.close()
    b.watch.state.brain = previous


@pytest.mark.parametrize('node',[
    'test_signup_day_zero_first_action_result_receipt_error_retry_and_undo',
    'test_missing_setting_signed_out_and_other_owner_have_no_unsafe_action'])
async def test_original_browser_journeys(node):
    path = ROOT/'tests/test_autumbra_gate5_journeys.py'
    assert path.is_file(), 'BLOCKED: integrate existing product browser journey suite with runtime'
    command = [sys.executable,'-m','pytest','-q','--tb=short','--disable-socket','--allow-unix-socket',
               '--allow-hosts=127.0.0.1,localhost,::1','--timeout=150',str(path)+'::'+node]
    result = await asyncio.to_thread(subprocess.run,command,cwd=ROOT,env={**os.environ,'PYTEST_ADDOPTS':''},
                                    capture_output=True,text=True,timeout=170)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'skipped' not in result.stdout and 'xfailed' not in result.stdout
