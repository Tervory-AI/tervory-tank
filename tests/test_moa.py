"""Offline MOA orchestration contracts; no provider or production credentials."""
import asyncio
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from pydantic import ValidationError

import bench
import graduate
import moa
from agents.zenas.core.engine import cite_check


def policy(**updates):
    updates.setdefault('shape', 'optimised')
    updates.setdefault('max_usd_per_request', 5)
    return moa.Policy(enabled=True, seats=[moa.Seat(name=s, model='model-'+s) for s in ('logic','context','data','speed')],
                      top_model='top', cheap_aggregator='cheap', frontier_aggregator='frontier', **updates)


def answer(model, content='supported answer', cost=.01):
    return moa.Answer(content, model, 20, 10, cost, 'receipt')


def caller(answers=None, delays=None, seen=None):
    async def call(seat, model, messages):
        if seen is not None:
            seen.append((seat, model, messages))
        if delays and seat in delays:
            await asyncio.sleep(delays[seat])
        content = (answers or {}).get(seat, 'supported answer')
        if seat == 'aggregator':
            content = (answers or {}).get(seat, '{"seat":"logic"}')
        return answer(model, content)
    return call


async def run(p=None, call=None, **kwargs):
    return await moa.execute(messages=[{'role':'user','content':'question'}], policy=p or policy(),
                             call=call or caller(), scope=('tenant','task'), breaker=moa.CircuitBreaker(), **kwargs)


@pytest.mark.asyncio
async def test_code_answer_never_calls_single_or_fans_out():
    async def code(): return answer('code', 'done', 0)
    async def forbidden(): raise AssertionError('No model should run')
    result=await moa.dispatch(policy=policy(), complex_request=True, interactive=False,
                              code=code, single=forbidden, mixture=forbidden)
    assert result.model=='code' and result.cost_usd==0


@pytest.mark.parametrize('enabled,complex_request,interactive,allow,expected',[
    (False,True,False,False,False),(True,False,False,False,False),
    (True,True,True,False,False),(True,True,True,True,True),(True,True,False,False,True)])
def test_policy_gates(enabled,complex_request,interactive,allow,expected):
    p=policy().model_copy(update={'enabled':enabled,'allow_interactive':allow})
    assert moa.should_mix(p, complex_request=complex_request, interactive=interactive)==expected
    assert not moa.Policy().enabled


@pytest.mark.asyncio
async def test_four_seats_are_parallel():
    active=set()
    all_started=asyncio.Event()
    start=None
    async def call(seat,model,messages):
        nonlocal start
        if seat!='aggregator':
            # Measure execution, excluding the deliberately lazy graph import.
            if start is None: start=time.monotonic()
            active.add(seat)
            if len(active)==4: all_started.set()
            await asyncio.wait_for(all_started.wait(),.5)
            await asyncio.sleep(.05)
        return answer(model, '{"seat":"logic"}' if seat=='aggregator' else 'supported answer')
    result=await run(call=call)
    assert len(active)==4 and len(result.results)==5
    assert all(r.status=='COMPLETE' for r in result.results)
    assert start is not None and time.monotonic()-start<.5


@pytest.mark.asyncio
async def test_timeout_partially_aggregates_and_names_critical_missing_seat():
    p=policy()
    p.seats[2]=p.seats[2].model_copy(update={'timeout_s':.03,'critical':True})
    seen=[]
    result=await run(p, caller(delays={'data':1}, seen=seen))
    assert result.missing==['data']
    assert 'Critical data may be missing' in result.content
    aggregate=next(v for v in seen if v[0]=='aggregator')
    assert aggregate[1]=='frontier'
    assert '"seat": "data", "critical": true' in aggregate[2][-1]['content']
    assert next(r for r in result.results if r.name=='data').status=='FAILED'


@pytest.mark.asyncio
@pytest.mark.parametrize('answers,expected',[({},'cheap'),({'data':'a conflicting unsupported answer'},'frontier')])
async def test_agreement_steps_aggregator_down(answers,expected):
    seen=[]
    result=await run(call=caller(answers,seen=seen))
    assert next(row[1] for row in seen if row[0]=='aggregator')==expected
    assert result.content=='supported answer'


@pytest.mark.asyncio
async def test_self_moa_repeats_one_model_without_collapsing_seats():
    seen=[]
    await run(policy(shape='self'), caller(seen=seen))
    assert len([r for r in seen if r[0]!='aggregator' and r[1]=='top'])==4


@pytest.mark.asyncio
async def test_synthesis_returns_aggregator_answer():
    result=await run(policy(mode='synthesize'), caller({'aggregator':'merged answer'}))
    assert result.content=='merged answer'


@pytest.mark.asyncio
async def test_bad_selection_and_all_failures_are_visible_errors():
    with pytest.raises(moa.Unavailable,match='select'):
        await run(call=caller({'aggregator':'{"seat":"invented"}'}))
    async def failed(*args): raise moa.CallFailure(400)
    with pytest.raises(moa.Unavailable,match='No seats answered'):
        await run(call=failed)


@pytest.mark.asyncio
async def test_retry_only_transient_errors_and_account_for_every_attempt():
    calls=[]
    async def transient(seat,model,messages):
        calls.append(seat)
        if len(calls)==1: raise moa.CallFailure(429,answer(model,'',.001))
        return answer(model)
    result=await moa.run_seat(moa.Seat(name='logic',model='one'),[],policy(),transient,moa.CircuitBreaker(),('t','task'))
    assert result.status=='COMPLETE' and len(calls)==2
    assert moa.total_cost([result])==pytest.approx(.011)
    calls.clear()
    async def forbidden(seat,model,messages):
        calls.append(seat)
        raise moa.CallFailure(403)
    result=await moa.run_seat(moa.Seat(name='logic',model='one'),[],policy(),forbidden,moa.CircuitBreaker(),('t','task'))
    assert result.status=='FAILED' and len(calls)==1


@pytest.mark.asyncio
async def test_circuit_breaker_is_tenant_and_model_scoped():
    breaker=moa.CircuitBreaker()
    seat=moa.Seat(name='logic',model='one')
    p=policy(breaker_failures=1)
    calls=[]
    async def failed(*args):
        calls.append(1)
        raise moa.CallFailure(400)
    await moa.run_seat(seat,[],p,failed,breaker,('a','task'))
    result=await moa.run_seat(seat,[],p,failed,breaker,('a','task'))
    assert result.error=='Circuit open' and len(calls)==1
    await moa.run_seat(seat,[],p,failed,breaker,('b','task'))
    assert len(calls)==2


@pytest.mark.asyncio
async def test_legal_agreement_does_not_pass_invented_citation():
    invented=json.dumps({'statements':[{'citation':'Invented v Nobody [2026] ZACC 999','quote':'invented finding'}]})
    async def library_check(content):
        return cite_check(json.loads(content)['statements'],[])['passed']
    with pytest.raises(moa.LegalRejected,match='cite_check'):
        await run(call=caller({s:invented for s in ('logic','context','data','speed')}), legal=True, legal_check=library_check)
    with pytest.raises(moa.LegalRejected,match='library-backed'):
        await run(legal=True)


def test_swap_is_only_proposed_after_one_hundred_and_not_automatically_applied():
    row={'current_model':'current','candidate_model':'candidate','status':'complete',
         'current_cost':.02,'candidate_cost':.01,'against_current':1.,'against_final':1.}
    rows=[dict(row) for _ in range(99)]
    assert graduate.moa_seat_proposal(rows,current='current',candidate='candidate') is None
    rows.append(dict(row))
    proposal=graduate.moa_seat_proposal(rows,current='current',candidate='candidate')
    assert proposal['status']=='proposed' and proposal['requires_founder']
    assert all(r['current_model']=='current' for r in rows)
    rows[0]['candidate_cost']=None
    assert graduate.moa_seat_proposal(rows,current='current',candidate='candidate') is None


@pytest.mark.asyncio
async def test_receipt_includes_each_seat_both_baselines_and_no_prompt_text():
    result=await run()
    record=moa.receipt(result.results,policy(),{'top':(.01,.02)},20,10)
    assert len(record['seats'])==5
    assert record['cost_usd']==pytest.approx(.05)
    assert record['all_frontier_usd']==pytest.approx(2.)
    assert record['single_top_usd']==pytest.approx(.4)
    assert record['saved_vs_frontier_usd']==pytest.approx(1.95)
    assert record['saved_vs_single_usd']==pytest.approx(.35)
    assert 'supported answer' not in json.dumps(record)
    result.results[0].unknown_spend=True
    record=moa.receipt(result.results,policy(),{'top':(.01,.02)},20,10)
    assert record['cost_usd'] is None and record['saved_vs_frontier_usd'] is None


@pytest.mark.parametrize('model', ['research-fast', 'research-low', 'research-medium', 'research-high', 'perplexity/sonar', 'openrouter/perplexity/sonar-pro', 'sonar-pro'])
@pytest.mark.parametrize('seat', ['logic', 'research'])
def test_research_presets_are_refused_in_every_seat(model, seat):
    with pytest.raises(ValidationError, match='not permitted'):
        moa.Policy(seats=[moa.Seat(name=seat, model=model)])
    with pytest.raises(ValidationError, match='not permitted'):
        moa.Policy(seats=[moa.Seat(name=seat, model='allowed', candidate=model)])
    with pytest.raises(ValidationError, match='not permitted'):
        moa.Policy(cheap_aggregator=model)


def test_bench_compares_all_shapes_and_modes_on_same_suite_without_enabling():
    shapes=bench.moa_shapes(policy().model_dump())
    assert len(shapes)==7 and all(not s['enabled'] for s in shapes)
    rows=[dict(s,suite_hash='same',score=1.,cost_per_call=.1,status='complete') for s in shapes]
    rows[-1]['cost_per_call']=.01
    winner=bench.choose_moa_shape(rows)
    assert winner['shape']=='optimised' and winner['mode']=='synthesize' and winner['requires_founder']
    rows[0]['suite_hash']='different'
    assert bench.choose_moa_shape(rows) is None


@pytest.mark.asyncio
async def test_single_bench_shape_calls_only_top_model():
    seen=[]
    result=await run(policy(shape='single'),caller(seen=seen))
    assert [(seat,model) for seat,model,_ in seen]==[('single','top')]
    assert result.content=='supported answer' and len(result.results)==1


def test_negation_and_unmeasured_prices_do_not_claim_agreement_or_savings():
    assert moa.agreement([answer('a','The rule applies'),answer('b','The rule does not apply')])==0
    result=moa.Result('logic','a','COMPLETE',answer=answer('a'),attempts=[answer('a')])
    record=moa.receipt([result],policy(),{},20,10)
    assert record['all_frontier_usd'] is None and record['single_top_usd'] is None
    assert record['saved_vs_frontier_usd'] is None and record['saved_vs_single_usd'] is None


def test_both_aggregator_candidates_have_independent_evidence_seats():
    p=policy(cheap_candidate='cheap-next',frontier_candidate='frontier-next')
    seats={s.name:s for s in moa.shadow_seat_configs(p)}
    assert seats['aggregator_low'].model=='cheap' and seats['aggregator_low'].candidate=='cheap-next'
    assert seats['aggregator_high'].model=='frontier' and seats['aggregator_high'].candidate=='frontier-next'


def test_enabled_policy_requires_positive_finite_request_cap():
    for cap in (None, 0, -1, float('inf'), float('nan')):
        with pytest.raises(ValidationError):
            policy(max_usd_per_request=cap)
    assert moa.Policy().max_usd_per_request is None


@pytest.mark.asyncio
async def test_legal_partial_result_keeps_cited_json_and_missing_metadata():
    p = policy()
    p.seats[2].timeout_s = .02
    content = json.dumps({'citations': [{'citation': 'Real case', 'quote': 'Verified words'}]})
    async def checked(value): return value == content
    result = await run(p, caller({s: content for s in ('logic', 'context', 'speed')}, delays={'data': 1}),
                       legal=True, legal_check=checked)
    assert json.loads(result.content) == json.loads(content)
    assert result.missing == ['data']
