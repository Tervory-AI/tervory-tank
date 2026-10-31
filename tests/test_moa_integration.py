"""Shared override, tenant isolation, durable budget and founder promotion tests."""
import json
import secrets
from types import SimpleNamespace
import uuid

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import moa
from gold import PLATFORM_TENANT
from test_bf2_tank_guards import _Conn, _Pool, _OkGateway, _policy_row, TENANT
from test_train1 import database as _database
from test_moa import policy
import main

database = _database


def req(task='fixture'):
    return main.RouteRequest(tenant_id=TENANT,task_type=task,
                             messages=[main.Message(role='user',content='Hello')])


@pytest.mark.asyncio
@pytest.mark.parametrize('task,seat',[('command.turn','pinned'),('fixture#moa.logic','logic')])
async def test_one_override_hook_preserves_full_receipt(monkeypatch,task,seat):
    monkeypatch.setenv('TANK_REGION','us-east')
    monkeypatch.delenv('TANK_PROVIDER_ALLOW',raising=False)
    conn=_Conn(row=_policy_row(model='original',candidate_model=None,shadow_rate=0))
    monkeypatch.setattr(main,'pool',lambda:_Pool(conn))
    monkeypatch.setattr(main,'_redis',None)
    async def roster(): return [{'name':'selected'}]
    monkeypatch.setattr(main,'list_models',roster)
    monkeypatch.setattr(main.httpx,'AsyncClient',_OkGateway)
    _OkGateway.calls=[]
    response=await main.run_route(req(task),model_override='selected')
    assert response.model=='selected' and _OkGateway.calls==['selected']
    receipt=next(q for q in conn.executes if 'INSERT INTO tank.ledger' in q[0])
    assert receipt[17]==seat and receipt[2]==TENANT
    assert conn.queries[0][1][0]==('fixture' if seat=='logic' else 'command.turn')


@pytest.mark.asyncio
async def test_override_refuses_unsupported_task_and_missing_live_model(monkeypatch):
    with pytest.raises(HTTPException) as error:
        await main.run_route(req('unrelated'),model_override='selected')
    assert error.value.status_code==403
    async def roster(): return []
    monkeypatch.setattr(main,'list_models',roster)
    with pytest.raises(HTTPException) as error:
        await main.run_route(req('fixture#moa.logic'),model_override='missing')
    assert error.value.status_code==422
    with pytest.raises(HTTPException): await main.run_route(req('fixture#moa.logic'))


@pytest.mark.asyncio
async def test_override_still_obeys_provider_allowlist_and_pause(monkeypatch):
    monkeypatch.setenv('TANK_REGION','us-east')
    conn=_Conn(row=_policy_row(model='original',candidate_model=None,shadow_rate=0))
    monkeypatch.setattr(main,'pool',lambda:_Pool(conn))
    monkeypatch.setattr(main,'_redis',None)
    async def roster(): return [{'name':'selected'}]
    monkeypatch.setattr(main,'list_models',roster)
    monkeypatch.setattr(main,'tenant_allowlist',lambda tenant:{'different'})
    with pytest.raises(HTTPException) as error:
        await main.run_route(req('fixture#moa.logic'),model_override='selected')
    assert error.value.status_code==403 and not conn.executes
    monkeypatch.setattr(main,'tenant_allowlist',lambda tenant:None)
    import controls
    async def paused(**kwargs): raise HTTPException(503,'paid work is paused')
    monkeypatch.setattr(controls,'refuse_paid',paused)
    with pytest.raises(HTTPException) as error:
        await main.run_route(req('fixture#moa.logic'),model_override='selected')
    assert error.value.status_code==503 and not conn.executes


@pytest.mark.asyncio
async def test_registered_route_forwards_complexity_and_preserves_auth(monkeypatch):
    app=FastAPI()
    seen=[]
    async def auth(): return 'base'
    async def routed(request,caller,**kwargs):
        seen.append((request,caller,kwargs))
        return dict(ledger_id=str(uuid.uuid4()),model='selected',rung=1,content='done',tokens_in=1,tokens_out=1,cost_usd=None,latency_ms=0,moa={'missing':['research']})
    row = {'model': 'selected', 'priority': 'standard', 'moa_enabled': True}
    async def load(*args): return row
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setattr(main, 'load_policy', load)
    monkeypatch.setattr(moa,'routed_request',routed)
    app.dependency_overrides[main.require_key] = auth
    app.post('/v1/route', response_model=main.RouteResponse, response_model_exclude_none=True)(main.route)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post('/v1/route',json={**req().model_dump(mode='json'),'complex_request':True,'interactive':False})
    assert response.status_code==200
    assert response.json()['moa']['missing']==['research']
    assert seen[0][0].agent=='base' and seen[0][1]=='base'
    assert seen[0][2]=={'row':row,'complex_request':True,'interactive':False}


@pytest.mark.asyncio
async def test_founder_routes_are_not_available_to_reviewers(monkeypatch):
    key=secrets.token_urlsafe(32)
    monkeypatch.setenv('TANK_API_KEY',key)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS','founder')
    app=FastAPI();app.include_router(moa.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        for headers in ({},{'x-tank-key':key,'x-tervory-admin':'reviewer'}):
            assert (await client.get('/v1/moa',headers=headers)).status_code==404
            assert (await client.post('/v1/moa/promote',headers=headers,json={})).status_code==404


@pytest.mark.asyncio
async def test_schema_defaults_reapplication_and_seat_baseline(database,monkeypatch):
    from pathlib import Path
    pool,rt=database
    monkeypatch.setattr(moa,'runtime',lambda:rt)
    await pool.execute("INSERT INTO tank.policy(task_type,model,baseline_model) VALUES('fixture','current','top')")
    assert not await pool.fetchval("SELECT moa_enabled FROM tank.policy WHERE task_type='fixture'")
    await pool.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES('top','fixture',.01,.02)")
    receipt=await pool.fetchrow('''INSERT INTO tank.ledger(tenant_id,agent,task_type,model,route_seat,tokens_in,tokens_out)
        VALUES($1,'base','fixture#moa.logic','current','logic',20,10) RETURNING *''',PLATFORM_TENANT)
    assert receipt['baseline_model']=='top' and float(receipt['baseline_cost_usd'])==pytest.approx(.4)
    await pool.execute("UPDATE tank.policy SET moa_enabled=true WHERE task_type='fixture'")
    await pool.execute((Path(__file__).resolve().parents[1]/'tank/schema.sql').read_text())
    assert await pool.fetchval("SELECT moa_enabled FROM tank.policy WHERE task_type='fixture'")


@pytest.mark.asyncio
async def test_evidence_is_tenant_and_region_scoped(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(moa,'runtime',lambda:rt)
    other=uuid.uuid4()
    for tenant,region in [(TENANT,'us-east'),(other,'us-east'),(TENANT,'za')]:
        await pool.execute('''INSERT INTO tank.moa_runs(tenant_id,region,task_type,config_hash,shape,mode,kind)
            VALUES($1,$2,'fixture','hash','diverse','select','live')''',tenant,region)
    data=await moa.evidence(TENANT)
    assert len(data['runs'])==1 and data['runs'][0]['tenant_id']==TENANT and data['runs'][0]['region']=='us-east'


@pytest.mark.asyncio
async def test_seat_promotion_rechecks_threshold_and_disables_for_rebench(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(moa,'runtime',lambda:rt)
    p=policy();p.seats[0].candidate='candidate'
    config=p.model_dump();config['enabled']=False
    await pool.execute("INSERT INTO tank.policy(task_type,model,moa_config) VALUES('fixture','current',$1::jsonb)",json.dumps(config))
    row=dict(await pool.fetchrow("SELECT * FROM tank.policy WHERE task_type='fixture'"))
    fingerprint=moa.config_hash(row)
    body=moa.Promote(task_type='fixture',config_hash=fingerprint,seat='logic')
    with pytest.raises(HTTPException) as error: await moa.promote(body,'founder')
    assert error.value.status_code==409
    for _ in range(100):
        run=await pool.fetchval('''INSERT INTO tank.moa_runs(tenant_id,region,task_type,config_hash,shape,mode,kind)
            VALUES($1,'us-east','fixture',$2,'optimised','select','live') RETURNING id''',PLATFORM_TENANT,fingerprint)
        await pool.execute('''INSERT INTO tank.moa_shadow(run_id,tenant_id,region,task_type,config_hash,seat,
            current_model,candidate_model,status,against_current,against_final,current_cost,candidate_cost,receipt)
            VALUES($1,$2,'us-east','fixture',$3,'logic','model-logic','candidate','complete',1,1,.02,.01,'{}')''',
            run,PLATFORM_TENANT,fingerprint)
    async def valid(config): pass
    monkeypatch.setattr(moa,'validate_models',valid)
    result=await moa.promote(body,'founder')
    assert not result['enabled'] and result['config']['seats'][0]['model']=='candidate'
    with pytest.raises(HTTPException) as error: await moa.promote(body,'founder')
    assert error.value.status_code==409


@pytest.mark.asyncio
async def test_bench_cap_reserves_before_router_and_does_not_promote(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(moa,'runtime',lambda:rt)
    import controls
    monkeypatch.setattr(controls,'db',lambda:pool)
    called=[]
    async def load(*args): return {'max_tokens_out':100,'system_prompt':None}
    async def route(*args,**kwargs): called.append(1);raise AssertionError('Budget exhausted')
    rt.load_policy=load;rt.run_route=route;rt.RouteRequest=main.RouteRequest
    run=await moa.new_budget_run('fixture','hash','self')
    from decimal import Decimal
    call=moa.call_adapter(req(),None,budget_run=run,cap=Decimal(0),
                          book={'selected':{'input':Decimal('.1'),'output':Decimal('.1')}},nonce='fixture')
    with pytest.raises(moa.CallFailure) as error: await call('logic','selected',[{'role':'user','content':'x'}])
    assert error.value.status==402 and not called
    assert await pool.fetchval('SELECT count(*) FROM tank.bench_calls')==0


@pytest.mark.asyncio
async def test_legal_checker_fetches_library_ignores_fabricated_passages(monkeypatch):
    async def fetch(*args): return []
    observed=[]
    async def skill(name,body,caller):
        observed.append((name,body.input))
        return {'passed':False,'blocked':True}
    rt=SimpleNamespace(pool=lambda:SimpleNamespace(fetch=fetch),box_region=lambda:'us-east',
                       run_one_skill=skill,SkillRun=main.SkillRun)
    monkeypatch.setattr(moa,'runtime',lambda:rt)
    content=json.dumps({'citations':[{'citation':'Invented [2026] 999','quote':'false'}],
                        'passages':[{'citation':'Invented [2026] 999','text':'false'}]})
    assert not await moa.legal_checker(req('zenas.draft'),content)
    assert not observed  # model-supplied passages are rejected before any skill call
    content=json.dumps({'citations':[{'citation':'Invented [2026] 999','quote':'false'}]})
    assert not await moa.legal_checker(req('zenas.draft'),content)
    assert observed[0][0]=='zenas.cite_check' and observed[0][1]['passages']==[]


@pytest.mark.asyncio
async def test_all_seven_bench_shapes_use_routed_receipts_and_never_enable(database,monkeypatch):
    import bench
    import controls
    from decimal import Decimal
    pool,rt=database
    monkeypatch.setattr(moa,'runtime',lambda:rt)
    monkeypatch.setattr(controls,'db',lambda:pool)
    p=policy(bench_enabled=True)
    p.enabled=False
    await pool.execute("INSERT INTO tank.policy(task_type,model,moa_config) VALUES('fixture','top',$1::jsonb)",json.dumps(p.model_dump()))
    row=dict(await pool.fetchrow("SELECT * FROM tank.policy WHERE task_type='fixture'"))
    async def load(*args): return row
    models={s.model for s in p.seats}|{'top','cheap','frontier'}
    async def roster():
        return [{'model_name':m,'litellm_params':{'model':'openai/'+m},
                 'model_info':{'input_cost_per_token':.00001,'output_cost_per_token':.00001}} for m in models]
    async def cases(*args): return [{'ref':'fixture','kind':'eval','input':'question','expected':'supported answer'}]
    called=[]
    async def routed(request,caller=None,*,model_override=None):
        called.append(request)
        assert request.task_type.startswith('fixture#moa.') and model_override in models
        seat=request.task_type.split('#moa.')[1]
        content='{"seat":"logic"}' if seat.startswith('aggregator') else 'supported answer'
        ledger=await pool.fetchval('''INSERT INTO tank.ledger(tenant_id,agent,task_type,model,tokens_in,tokens_out,cost_usd)
            VALUES($1,'bench',$2,$3,20,10,.0003) RETURNING id''',PLATFORM_TENANT,request.task_type,model_override)
        return main.RouteResponse(ledger_id=ledger,model=model_override,rung=1,content=content,
                                  tokens_in=20,tokens_out=10,cost_usd=.0003,latency_ms=0)
    # Synthesis needs a final answer, while the select judge must choose a seat.
    original=routed
    async def routed_by_instruction(request,caller=None,*,model_override=None):
        result=await original(request,caller,model_override=model_override)
        if 'Synthesize' in request.messages[-1].content:
            return result.model_copy(update={'content':'supported answer'})
        return result
    rt.load_policy=load;rt._roster_models=roster;rt.RouteRequest=main.RouteRequest;rt.run_route=routed_by_instruction
    monkeypatch.setattr(bench,'cases_for',cases)
    results=await moa.bench_task(row,bench.price_book(await roster()),'us-east',Decimal(5),force=True)
    assert len(results)==7 and all(r['status']=='complete' for r in results)
    assert len(called)==31
    assert await pool.fetchval('SELECT count(*) FROM tank.bench_calls WHERE charged_usd IS NOT NULL')==31
    assert await pool.fetchval('SELECT count(*) FROM tank.moa_runs WHERE status=\'complete\'')==7
    assert not await pool.fetchval("SELECT moa_enabled FROM tank.policy WHERE task_type='fixture'")
    assert await pool.fetchval("SELECT model FROM tank.policy WHERE task_type='fixture'")=='top'


@pytest.mark.asyncio
async def test_command_override_is_keyword_only(monkeypatch):
    monkeypatch.setenv('TANK_REGION','us-east')
    monkeypatch.delenv('TANK_PROVIDER_ALLOW',raising=False)
    conn=_Conn(row=_policy_row(model='original',candidate_model=None,shadow_rate=0))
    monkeypatch.setattr(main,'pool',lambda:_Pool(conn))
    monkeypatch.setattr(main,'_redis',None)
    async def roster(): return [{'name':'selected'}]
    monkeypatch.setattr(main,'list_models',roster)
    monkeypatch.setattr(main.httpx,'AsyncClient',_OkGateway)
    _OkGateway.calls=[]
    result=await main.run_route(req('command.turn'),model_override='selected')
    assert result.model=='selected' and _OkGateway.calls==['selected']
    assert 'model_override' not in main.RouteRequest.model_fields
    assert not hasattr(main.RouteRequest(**req().model_dump(),model_override='selected'),'model_override')


@pytest.mark.asyncio
async def test_moa_legal_scope_uses_approved_code_rules_and_refuses_criminal(monkeypatch):
    from pathlib import Path
    async def version(*args): return '1.0.0'
    rt=SimpleNamespace(_pick_version=version,box_region=lambda:'us-east',
        get_package=lambda *args:SimpleNamespace(path=Path(__file__).resolve().parents[1]/'tank/skills/zenas.scope/1.0.0'))
    monkeypatch.setattr(moa,'runtime',lambda:rt)
    criminal=req('zenas.draft').model_copy(update={'messages':[main.Message(role='user',content='Criminal defense for a murder charge')]})
    assert not await moa.legal_scope(criminal)
    civil=req('zenas.draft').model_copy(update={'messages':[main.Message(role='user',content='A supply agreement dispute')]})
    assert await moa.legal_scope(civil)


@pytest.mark.asyncio
@pytest.mark.parametrize('upstream_status',[400,429,503])
async def test_adapter_uses_recorded_provider_status_for_retry_policy(monkeypatch,upstream_status):
    ledger=str(uuid.uuid4())
    async def load(*args): return {'max_tokens_out':100,'system_prompt':None}
    async def route(*args,**kwargs): raise HTTPException(502,{'ledger_id':ledger,'upstream':'omitted'})
    async def fetchrow(sql,*args):
        assert 'tenant_id=$2' in sql and args[1]==TENANT
        return {'model':'selected','tokens_in':20,'tokens_out':0,'cost_usd':.001,'error':str(upstream_status)+': omitted'}
    rt=SimpleNamespace(load_policy=load,run_route=route,RouteRequest=main.RouteRequest,
                       box_region=lambda:'us-east',pool=lambda:SimpleNamespace(fetchrow=fetchrow))
    monkeypatch.setattr(moa,'runtime',lambda:rt)
    with pytest.raises(moa.CallFailure) as error:
        await moa.call_adapter(req(),None)('logic','selected',[{'role':'user','content':'question'}])
    assert error.value.status==upstream_status
    assert moa.retryable(error.value)==(upstream_status!=400)
    assert error.value.receipt.ledger_id==ledger and error.value.receipt.cost_usd==.001


@pytest.mark.asyncio
async def test_public_seat_alias_cannot_bypass_disabled_policy(monkeypatch):
    async def forbidden(*args,**kwargs): raise AssertionError('No policy or model call allowed')
    rt=SimpleNamespace(box_region=lambda:'us-east',call_home=lambda home,box:box,
                       home_region_refusal=lambda home,box:None,load_policy=forbidden,run_route=forbidden)
    monkeypatch.setattr(moa,'runtime',lambda:rt)
    with pytest.raises(HTTPException) as error:
        await moa.routed_request(req('fixture#moa.logic'))
    assert error.value.status_code==403


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [403, 503])
async def test_refused_live_attempt_costs_zero_and_is_not_unknown(monkeypatch, status):
    async def load(*args): return {'max_tokens_out': 32, 'system_prompt': None}
    async def refused(*args, **kwargs): raise HTTPException(status, 'Policy refusal')
    rt = SimpleNamespace(load_policy=load, run_route=refused, RouteRequest=main.RouteRequest,
                         box_region=lambda: 'us-east')
    monkeypatch.setattr(moa, 'runtime', lambda: rt)
    result = await moa.run_seat(moa.Seat(name='logic', model='selected'), [{'role':'user','content':'Hello'}], policy(),
                               moa.call_adapter(req(), None), moa.CircuitBreaker(), ('tenant', 'task'))
    assert result.status == 'FAILED' and not result.unknown_spend
    assert len(result.attempts) == 1 and moa.total_cost([result]) == 0


@pytest.mark.asyncio
async def test_alias_to_perplexity_is_refused_even_in_research_seat(monkeypatch):
    async def roster(): return [{'model_name': 'innocent-alias', 'litellm_params': {'model': 'perplexity/sonar'}}]
    monkeypatch.setattr(moa, 'runtime', lambda: SimpleNamespace(_roster_models=roster))
    config = moa.Policy(seats=[moa.Seat(name='research', model='innocent-alias')])
    with pytest.raises(HTTPException, match='not permitted'):
        await moa.validate_models(config)


def priced_roster(config):
    return [{'model_name': m, 'litellm_params': {'model': 'openai/'+m},
             'model_info': {'input_cost_per_token': .00001, 'output_cost_per_token': .00002}}
            for m in {s.model for s in config.seats} | {'top', 'cheap', 'frontier'}]


@pytest.mark.asyncio
async def test_over_cap_refused_before_any_run_or_seat_starts(monkeypatch):
    config = policy(max_usd_per_request=.00001)
    async def roster(): return priced_roster(config)
    def forbidden(): raise AssertionError('No run may be written or seat called')
    monkeypatch.setattr(moa, 'runtime', lambda: SimpleNamespace(_roster_models=roster, pool=forbidden))
    row = {'moa_enabled': True, 'moa_config': config.model_dump(), 'max_tokens_out': 100, 'model': 'top'}
    with pytest.raises(HTTPException) as error:
        await moa.run_mixture(req(), row)
    assert error.value.status_code == 409 and 'exceeds' in error.value.detail


@pytest.mark.asyncio
async def test_quote_includes_all_seats_larger_aggregator_and_every_retry(monkeypatch):
    import bench
    from decimal import Decimal
    config = policy(max_attempts=3)
    row = {'max_tokens_out': 100, 'system_prompt': 'Policy prompt'}
    book = bench.price_book(priced_roster(config))
    calls = []
    def quote(messages, max_tokens, price):
        calls.append((messages, max_tokens, price))
        return Decimal(2) if price is book['frontier'] else Decimal(1)
    monkeypatch.setattr(bench, 'reserve_quote', quote)
    assert moa.request_quote(req(), row, config, book) == 18  # (4 seats + max(1,2)) * 3
    assert len(calls) == 6 and all(c[1] == 100 for c in calls)
    assert all(c[0][0]['content'] == 'Policy prompt' for c in calls)
    assert 'Proposals' in calls[-1][0][-1]['content'] or 'proposals' in calls[-1][0][-1]['content']


@pytest.mark.asyncio
async def test_request_reservations_bound_concurrent_attempts_and_do_not_refund_unknowns():
    import asyncio
    import bench
    from decimal import Decimal
    book = {'selected': {'input': Decimal('.001'), 'output': Decimal('.002')}}
    quote = bench.reserve_quote([], 10, book['selected'])
    budget = moa.RequestBudget(quote * 2, book)
    async def attempt():
        budget.reserve('selected', [], 10)
        await asyncio.sleep(0)
    results = await asyncio.gather(*(attempt() for _ in range(3)), return_exceptions=True)
    refused = [r for r in results if isinstance(r, moa.CallFailure)]
    assert len(refused) == 1 and refused[0].receipt.cost_usd == 0 and budget.remaining == 0


def test_langgraph_is_lazy_pinned_and_tracing_is_off():
    from pathlib import Path
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, '-c', "import sys, moa; assert 'langgraph.graph' not in sys.modules"], check=True)
    constraints = (root/'tank/constraints-langgraph.txt').read_text()
    for package in ('langgraph', 'langchain-core', 'langsmith', 'langgraph-checkpoint', 'langgraph-prebuilt', 'langgraph-sdk'):
        assert package+'==' in constraints
    docker = (root/'tank/Dockerfile').read_text()
    assert 'LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false' in docker
    assert 'constraints-langgraph.txt' in docker


@pytest.mark.asyncio
async def test_disabled_route_does_not_import_or_call_moa(monkeypatch):
    import builtins
    original_import = builtins.__import__
    def without_moa(name, *args, **kwargs):
        if name == 'moa':
            raise AssertionError('Disabled routes must not depend on MoA')
        return original_import(name, *args, **kwargs)
    async def load(*args): return {'priority': 'standard', 'moa_enabled': False, 'moa_config': 'stale and invalid'}
    async def single(request, caller):
        assert request.agent == caller == 'base'
        return 'ordinary route'
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setattr(main, 'load_policy', load)
    monkeypatch.setattr(main, 'run_route', single)
    monkeypatch.setattr(builtins, '__import__', without_moa)
    assert await main.route(req(), 'base') == 'ordinary route'


@pytest.mark.asyncio
@pytest.mark.parametrize('stored', ['invalid json', '[]', [], 123, {'shape': 'obsolete'},
                                   {'enabled': True}, {'seats': [{'name': 'logic', 'model': 'sonar'}]}])
async def test_stale_config_logs_and_falls_back_to_single_route(monkeypatch, caplog, stored):
    row = {'task_type': 'fixture', 'tenant_id': TENANT, 'model': 'selected', 'priority': 'standard',
           'moa_enabled': True, 'moa_config': stored}
    async def load(*args): return row
    async def single(*args, **kwargs): return 'ordinary route'
    async def forbidden(*args): raise AssertionError('No seats may start')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setattr(moa, 'runtime', lambda: main)
    monkeypatch.setattr(main, 'load_policy', load)
    monkeypatch.setattr(main, 'run_route', single)
    monkeypatch.setattr(moa, 'validate_models', forbidden)
    assert await main.route(req().model_copy(update={'complex_request': True, 'interactive': False}), None) == 'ordinary route'
    assert 'Invalid MoA config for task fixture' in caplog.text and 'MoA disabled' in caplog.text
    assert not moa.config_for(row).enabled


@pytest.mark.asyncio
@pytest.mark.parametrize('enabled', [False, True])
async def test_missing_code_package_stays_refused_without_running_seats(monkeypatch, enabled):
    row = _policy_row(model='skill:base.fixture@1.0.0', moa_enabled=enabled,
                      moa_config=policy().model_dump())
    async def load(*args): return row
    async def forbidden(*args, **kwargs): raise AssertionError('No skill or seat may run')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.delenv('TANK_PROVIDER_ALLOW', raising=False)
    monkeypatch.setattr(main, 'load_policy', load)
    monkeypatch.setattr(main, '_run_code_candidate', forbidden)
    monkeypatch.setattr(moa, 'runtime', lambda: main)
    monkeypatch.setattr(moa, 'run_mixture', forbidden)
    with pytest.raises(HTTPException) as error:
        await main.route(req().model_copy(update={'complex_request': True, 'interactive': False}), None)
    assert error.value.status_code == 404 and 'no package' in error.value.detail


@pytest.mark.asyncio
async def test_shadow_billing_cannot_bypass_source_tenant_allowlist(monkeypatch):
    async def load(*args): return {'max_tokens_out': 32, 'system_prompt': None}
    async def forbidden(*args, **kwargs): raise AssertionError('No call or reservation allowed')
    monkeypatch.setattr(moa, 'runtime', lambda: main)
    monkeypatch.setattr(main, 'load_policy', load)
    monkeypatch.setattr(main, 'run_route', forbidden)
    monkeypatch.setattr(main, 'tenant_allowlist', lambda tenant: {'different'} if str(tenant) == str(TENANT) else None)
    with pytest.raises(moa.CallFailure) as error:
        await moa.call_adapter(req(), None, shadow=True)('logic', 'candidate', [{'role': 'user', 'content': 'Hello'}])
    assert error.value.receipt.cost_usd == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('upstream_status', [200, 400])
async def test_shadow_seat_receipts_bill_platform_never_client(database, monkeypatch, upstream_status):
    """Real router + real ledger, including a failed provider's billable usage."""
    import controls
    pool, _ = database
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.delenv('TANK_PROVIDER_ALLOW', raising=False)
    monkeypatch.setattr(main, 'pool', lambda: pool)
    monkeypatch.setattr(main, '_redis', None)
    monkeypatch.setattr(main, '_shadow_budget', lambda: 5)
    monkeypatch.setattr(moa, 'runtime', lambda: main)
    monkeypatch.setattr(moa, '_breaker', moa.CircuitBreaker())
    monkeypatch.setattr(controls, 'db', lambda: pool)
    config = policy(max_attempts=1)
    config.seats[0].candidate = 'candidate'
    await pool.execute("INSERT INTO tank.policy(task_type,model,baseline_model,max_tokens_out) VALUES('fixture','top','top',32)")
    await pool.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES('top','fixture',.001,.002)")
    row = dict(await pool.fetchrow("SELECT * FROM tank.policy WHERE task_type='fixture'"))
    row.update(moa_enabled=True, moa_config=config.model_dump())
    async def roster():
        return [{'model_name': 'candidate', 'litellm_params': {'model': 'openai/candidate'},
                 'model_info': {'input_cost_per_token': .00001, 'output_cost_per_token': .00002}}]
    async def listed(): return [{'name': 'candidate'}]
    monkeypatch.setattr(main, '_roster_models', roster)
    monkeypatch.setattr(main, 'list_models', listed)
    calls = []
    class Gateway(_OkGateway):
        async def post(self, url, **kwargs):
            calls.append(kwargs['json']['model'])
            return httpx.Response(upstream_status, headers={'x-litellm-response-cost': '.0004'},
                json={'choices': [{'message': {'content': 'ok'}}],
                      'usage': {'prompt_tokens': 20, 'completion_tokens': 10}, 'error': {'message': 'fixture refusal'}})
    monkeypatch.setattr(main.httpx, 'AsyncClient', Gateway)
    run = await pool.fetchval('''INSERT INTO tank.moa_runs(tenant_id,region,task_type,config_hash,shape,mode,kind)
        VALUES($1,'us-east','fixture',$2,'optimised','select','live') RETURNING id''', TENANT, moa.config_hash(row))
    current = moa.Result('logic', 'model-logic', 'COMPLETE', moa.Answer('ok', 'model-logic', 20, 10, .001))
    await moa.shadow_seats(req(), row, moa.Mixture('ok', [current], 1, []), run, 'base')
    assert calls == ['candidate']
    assert await pool.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1', TENANT) == 0
    ledger = await pool.fetchrow('SELECT * FROM tank.ledger WHERE tenant_id=$1', PLATFORM_TENANT)
    assert ledger['agent'] == 'shadow' and ledger['route_seat'] == 'logic'
    assert float(ledger['cost_usd']) == pytest.approx(.0004)
    assert ledger['outcome'] == ('delivered' if upstream_status == 200 else 'failed')
    assert ledger['tokens_in'] == 20 and ledger['tokens_out'] == 10
    shadow = await pool.fetchrow('SELECT * FROM tank.moa_shadow WHERE tenant_id=$1 AND run_id=$2', TENANT, run)
    evidence = json.loads(shadow['receipt'])
    assert evidence['attempts'][0]['ledger_id'] == str(ledger['id'])
    assert evidence['attempts'][0]['cost_usd'] == pytest.approx(.0004)
    assert float(shadow['candidate_cost']) == pytest.approx(.0004)
    if upstream_status == 200:
        assert evidence['answer']['baseline_model'] == 'top'
        assert evidence['answer']['baseline_cost_usd'] == pytest.approx(.04)
        charge = await pool.fetchval('SELECT charged_usd FROM tank.bench_calls WHERE ledger_id=$1 AND tenant_id=$2', ledger['id'], PLATFORM_TENANT)
        assert float(charge) == pytest.approx(.0004)
