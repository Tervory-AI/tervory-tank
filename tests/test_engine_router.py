"""Per-request router and scoreboard: pure decisions, real Postgres, real Tank HTTP.

No provider is called: every model answer comes from httpx.MockTransport fakes.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import random
import statistics
import time
from types import SimpleNamespace
import uuid

import pytest

import request_router as router
import router_scoreboard as scoreboard
from router_scoreboard import ALL, Entry
import test_core1_proof
import test_tank_routellm
import test_tank_tenant_boundaries
import test_train1

# Reused disposable-Postgres fixtures (each skips itself without a test database).
boundary = test_tank_tenant_boundaries.boundary
real_tank = test_tank_routellm.real_tank
database = test_train1.database

NOW = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
BAR = .99


def entry(model, price, quality, difficulty=ALL, *, available=True, p95=800, error=0.0, cooling=False,
          age=timedelta(minutes=1), n=50):
    return Entry(model=model, difficulty=difficulty, quality=quality, quality_n=n if quality is not None else 0,
                 p50_ms=p95 // 2 if p95 else None, p95_ms=p95, error_rate=error, price_usd=price,
                 available=available, cooldown_until=NOW + timedelta(minutes=2) if cooling else None,
                 refreshed_at=NOW - age)


def ladder_board():
    return [
        entry('sol', .02, .995),                 # the ladder's pick: passes, most expensive
        entry('luna', .004, .97),                # fails the whole task ...
        entry('luna', .004, .995, 0),            # ... but passes easy requests
        entry('flash-lite', .001, .98),          # cheapest, fails whole task
        entry('flash-lite', .001, .985, 0),      # and still fails easy requests
        entry('llama-small', .0005, 1.0, available=False),  # passes but not on the roster
        entry('qwen-small', None, 1.0),          # unknown price is never treated as free
        entry('gpt-oss', .03, 1.0),              # passes but dearer than the ladder's pick
    ]


def test_picks_lowest_cost_passing_model_at_difficulty():
    board = ladder_board()
    assert router.choose(board, ladder_model='sol', bar=BAR, difficulty=.1, now=NOW) == (
        'luna', 'cheaper_model_passes_at_difficulty')
    # Hard request: no difficulty evidence, whole-task evidence decides, nothing cheaper passes.
    assert router.choose(board, ladder_model='sol', bar=BAR, difficulty=.95, now=NOW) == (
        'sol', 'ladder_pick_cheapest_passing')
    # Difficulty unavailable: whole-task evidence only.
    assert router.choose(board, ladder_model='sol', bar=BAR, difficulty=None, now=NOW)[0] == 'sol'
    # Difficulty evidence that fails vetoes a model that passes on the whole task.
    vetoed = [*board, entry('nano', .0001, 1.0), entry('nano', .0001, .9, 0)]
    assert router.choose(vetoed, ladder_model='sol', bar=BAR, difficulty=.1, now=NOW)[0] == 'luna'
    assert router.choose(vetoed, ladder_model='sol', bar=BAR, difficulty=.5, now=NOW)[0] == 'nano'
    # A higher task bar removes luna too.
    assert router.choose(board, ladder_model='sol', bar=.999, difficulty=.1, now=NOW)[0] == 'sol'
    # Privacy and region refusals are never routed to.
    assert router.choose(board, ladder_model='sol', bar=BAR, difficulty=.1, now=NOW,
                         refused=lambda model: model == 'luna')[0] == 'sol'


def test_never_picks_below_the_bar_or_above_the_ladder_price_randomised():
    rng = random.Random(20261109)
    names = ['sol', 'luna', 'flash-lite', 'llama-small', 'qwen-small', 'gpt-oss', 'local']
    for _ in range(2000):
        rows = [entry('sol', .02, .995)]
        for name in names[1:]:
            price = rng.choice([None, 0.0, .0001, .001, .01, .02, .05])
            rows.append(entry(name, price, rng.choice([None, .5, .98, .99, .995, 1.0]), available=rng.random() > .2))
            if rng.random() > .5:
                rows.append(entry(name, price, rng.choice([None, .9, .99, 1.0]), rng.randrange(5)))
        difficulty = rng.choice([None, rng.random()])
        bar = rng.choice([.99, .995])
        model, _ = router.choose(rows, ladder_model='sol', bar=bar, difficulty=difficulty, now=NOW)
        if model == 'sol':
            continue
        level = scoreboard.bucket(difficulty)
        whole = {e.model: e for e in rows if e.difficulty == ALL}
        at = {e.model: e for e in rows if e.difficulty == level}

        def passes(name):
            if name in at and at[name].quality is not None:
                return at[name].quality >= bar
            return whole[name].quality is not None and whole[name].quality >= bar
        assert passes(model), (model, rows)
        assert whole[model].available and whole[model].price_usd < .02
        cheaper = [e for e in whole.values() if e.model != 'sol' and e.available and e.price_usd is not None
                   and e.price_usd < whole[model].price_usd and passes(e.model)]
        assert not cheaper, (model, cheaper)


def test_empty_stale_or_unpriced_board_keeps_todays_routing():
    assert router.choose([], ladder_model='sol', bar=BAR, difficulty=.1, now=NOW) == (None, 'empty_board')
    stale = [entry(e.model, e.price_usd, e.quality, e.difficulty, age=timedelta(hours=27)) for e in ladder_board()]
    assert router.choose(stale, ladder_model='sol', bar=BAR, difficulty=.1, now=NOW) == (None, 'stale_board')
    unpriced = [entry('sol', None, .995), entry('luna', .001, 1.0)]
    assert router.choose(unpriced, ladder_model='sol', bar=BAR, difficulty=.1, now=NOW) == (None, 'ladder_pick_unpriced')
    # Stale per-difficulty rows are ignored even when the whole-task rows are fresh.
    mixed = [entry('sol', .02, .995), entry('luna', .004, .97), entry('luna', .004, .995, 0, age=timedelta(hours=30))]
    assert router.choose(mixed, ladder_model='sol', bar=BAR, difficulty=.1, now=NOW)[0] == 'sol'


def test_latency_aware_skips_cooldowns_unhealthy_and_slow_models():
    base = [entry('sol', .02, .995, p95=1000), entry('luna', .004, 1.0, p95=1200), entry('flash-lite', .001, 1.0, p95=1000)]
    assert router.choose(base, ladder_model='sol', bar=BAR, difficulty=None, now=NOW)[0] == 'flash-lite'
    for slow in (entry('flash-lite', .001, 1.0, p95=1600), entry('flash-lite', .001, 1.0, cooling=True),
                 entry('flash-lite', .001, 1.0, error=.2), entry('flash-lite', .001, 1.0, p95=None)):
        board = [base[0], base[1], slow]
        # Cost-only routing (today's LiteLLM strategy) still takes it ...
        assert router.choose(board, ladder_model='sol', bar=BAR, difficulty=None, now=NOW)[0] == 'flash-lite'
        # ... latency-aware routing moves to the healthy, fast-enough model.
        assert router.choose(board, ladder_model='sol', bar=BAR, difficulty=None, now=NOW, latency=True)[0] == 'luna'


@pytest.mark.parametrize('value', [None, '', ' ', 'TRUE', 'True', '1', 'yes', 'on', ' true', 'true '])
def test_only_the_literal_true_switches_anything_on(monkeypatch, value):
    for name in (router.SETTING, router.LATENCY_SETTING):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    assert not router.enabled() and not router.latency_enabled() and not scoreboard.enabled()
    monkeypatch.setenv(router.SETTING, 'true')
    monkeypatch.setenv(router.LATENCY_SETTING, 'true')
    assert router.enabled() and router.latency_enabled() and scoreboard.enabled()


def test_bucket_and_quality_composition():
    assert [scoreboard.bucket(v) for v in (0, .19, .2, .5, .99, 1)] == [0, 0, 1, 2, 4, 4]
    assert scoreboard.bucket(None) is None and scoreboard.bucket(float('nan')) is None and scoreboard.bucket(1.5) is None
    # The weakest qualifying signal wins; small shadow samples do not qualify.
    assert scoreboard.compose((1.0, 3), (None, 0), (.95, 25), (.99, 25), whole_task=True) == (.95, 53)
    assert scoreboard.compose((1.0, 3), (None, 0), (.5, 19), (None, 0), whole_task=True) == (1.0, 3)
    assert scoreboard.compose((None, 0), (None, 0), (1.0, 19), (None, 0), whole_task=False) == (None, 0)
    assert scoreboard._deepeval({'scores': {'correctness': 1, 'faithfulness': .9, 'task': 1}}) == .9
    assert scoreboard._deepeval('{"reason": "DeepEval unavailable"}') is None
    assert scoreboard._model_name('routellm:flash-lite:abcdef0123456789') == 'flash-lite'


class FakeRuntime:
    PLATFORM_TENANT = uuid.UUID(int=0)

    def __init__(self, refusals=()):
        self.refusals = set(refusals)

    def box_region(self):
        return 'us-east'

    def pool(self):
        return None

    async def zenas_pool_prompt(self, *args, **kwargs):
        return False

    def model_call_refusal(self, text, model, **kwargs):
        return 'refused' if model in self.refusals else None


def request(text='Classify: I was charged twice.'):
    return SimpleNamespace(tenant_id=uuid.uuid4(), task_type='engine.classify', skill=None,
                           messages=[SimpleNamespace(role='user', content=text)])


def fixture_router(monkeypatch, board, *, promoted=True, score=.1):
    async def read(pool, tenant, region, task):
        return [Entry(**{**e.__dict__, 'refreshed_at': datetime.now(timezone.utc)}) for e in board]

    async def fixed(req):
        return score

    async def is_promoted(*args):
        return promoted
    monkeypatch.setattr(scoreboard, 'read', read)
    monkeypatch.setattr(router, 'difficulty', fixed)
    monkeypatch.setattr(router, 'promoted', is_promoted)
    monkeypatch.setattr(router, 'schedule_refresh', lambda *args: None)


@pytest.mark.asyncio
async def test_shadow_until_listed_and_proven_then_served_with_ladder_fallback(monkeypatch):
    fixture_router(monkeypatch, ladder_board())
    policy = {'model': 'sol', 'rung': 1, 'eval_threshold': .99, 'fallbacks': [],
              '_engine': {'free': False, 'baseline_model': 'sol'}}
    monkeypatch.delenv(router.SERVE_SETTING, raising=False)
    shadow = await router.route(FakeRuntime(), request(), policy)
    assert shadow['model'] == 'sol' and shadow['fallbacks'] == []
    assert shadow['_router']['mode'] == 'shadow' and shadow['_router']['chosen_model'] == 'luna'
    monkeypatch.setenv(router.SERVE_SETTING, 'other.task, engine.classify')
    served = await router.route(FakeRuntime(), request(), policy)
    assert served['model'] == 'luna' and served['fallbacks'] == ['sol'] and served['rung'] == 1
    assert served['_router']['mode'] == 'served' and served['_engine']['router_from'] == 'sol'
    assert policy['model'] == 'sol'  # the ladder's policy is never mutated
    fixture_router(monkeypatch, ladder_board(), promoted=False)
    assert (await router.route(FakeRuntime(), request(), policy))['_router']['mode'] == 'shadow'
    fixture_router(monkeypatch, ladder_board())
    refused = await router.route(FakeRuntime(refusals={'luna'}), request(), policy)
    assert refused['model'] == 'sol' and refused['_router']['chosen_model'] == 'sol'
    free = await router.route(FakeRuntime(), request(), {**policy, '_engine': {'free': True}})
    assert free['model'] == 'sol' and free['_router']['reason'] == 'ladder_pick_free_or_code'

    async def broken(*args):
        raise RuntimeError('board unavailable')
    monkeypatch.setattr(scoreboard, 'read', broken)
    failed = await router.route(FakeRuntime(), request(), policy)
    assert failed['model'] == 'sol' and failed['_router']['mode'] == 'fallback'
    assert failed['_router']['reason'] == 'router_unavailable:RuntimeError'


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


@pytest.mark.asyncio
async def test_decision_time_per_request_on_a_fixture(monkeypatch):
    """Board lookup plus choice, per request, with RouteLLM's measured CPU cost reported separately."""
    models = ['sol', 'luna', 'flash-lite', 'llama-small', 'gpt-oss-small', 'qwen-small', 'gpt-oss', 'llama']
    rng = random.Random(7)
    board = [entry('sol', .02, .995)]
    for name in models[1:]:
        price = rng.choice([.0005, .001, .004, .01])
        board.append(entry(name, price, rng.choice([.97, .99, 1.0])))
        board.extend(entry(name, price, rng.choice([.98, .995, 1.0]), b) for b in range(5))
    fixture_router(monkeypatch, board, promoted=False, score=None)
    policy = {'model': 'sol', 'rung': 1, 'eval_threshold': .99, '_engine': {'free': False}}
    times, measured = [], []
    for i in range(2000):
        started = time.perf_counter()
        decided = await router.route(FakeRuntime(), request(f'fixture {i}'), policy)
        times.append((time.perf_counter() - started) * 1000)
        measured.append(decided['_router']['decision_ms'])
    p50, p95 = percentile(measured, .5), percentile(measured, .95)
    print(f'router decision (board lookup + choice) p50={p50:.3f} ms p95={p95:.3f} ms over {len(measured)} requests; '
          f'RouteLLM difficulty adds the measured 65-67 ms CPU (PRs #786/#790), bounded at '
          f'{router.SCORE_TIMEOUT_S * 1000:.0f} ms')
    assert all(m >= 0 for m in measured) and statistics.median(times) >= statistics.median(measured) * .5
    assert p95 < 5, (p50, p95)


@pytest.mark.asyncio
async def test_difficulty_scorer_is_bounded_and_failure_tolerant(monkeypatch):
    import routellm_shadow

    def slow(prompt):
        time.sleep(1)
        return .3
    monkeypatch.setattr(routellm_shadow, 'score', slow)
    monkeypatch.setattr(router, 'SCORE_TIMEOUT_S', .05)
    started = time.perf_counter()
    assert await router.difficulty(request()) is None
    assert time.perf_counter() - started < .5

    def broken(prompt):
        raise RuntimeError('RouteLLM checkpoint revision mismatch')
    monkeypatch.setattr(routellm_shadow, 'score', broken)
    assert await router.difficulty(request()) is None
    monkeypatch.setattr(routellm_shadow, 'score', lambda prompt: .42)
    assert await router.difficulty(request()) == .42
    await asyncio.sleep(1.1)  # the timed-out thread finishes and releases its slot
    assert router._scoring == 0


async def seed_ledger(conn, tenant, task, model, latencies, *, cost, failures=0, routellm=None, recent_failure=False):
    ids = []
    for i, latency in enumerate(latencies):
        ids.append(await conn.fetchval('''INSERT INTO tank.ledger(tenant_id,region,agent,task_type,model,cost_usd,latency_ms,
            outcome,routellm_score) VALUES($1,'us-east','tier0',$2,$3,$4,$5,'delivered',$6) RETURNING id''',
            tenant, task, model, cost, latency, routellm))
    for _ in range(failures):
        await conn.execute('''INSERT INTO tank.ledger(tenant_id,region,agent,task_type,model,cost_usd,latency_ms,outcome,ts)
            VALUES($1,'us-east','tier0',$2,$3,0,10,'failed',now()-$4::interval)''', tenant, task, model,
            timedelta(seconds=30) if recent_failure else timedelta(hours=1))
    return ids


@pytest.mark.asyncio
async def test_scoreboard_refresh_from_receipts_evals_and_shadows_and_tenant_isolation(boundary, monkeypatch):
    b = boundary
    a, other = b.tenants
    platform = b.tank.PLATFORM_TENANT
    task = 'router.fixture'
    async with b.pool.acquire() as conn:
        parents = await seed_ledger(conn, a, task, 'sol', list(range(100, 2100, 100)), cost=.02,
                                    failures=1, routellm=.1, recent_failure=True)
        await seed_ledger(conn, a, task, 'luna', [300] * 5, cost=.004)
        await conn.execute('''INSERT INTO tank.engine_evals(tenant_id,region,task_type,model,revision,agreement,samples)
            VALUES($1,'us-east',$2,'sol','r1',.995,12),($1,'us-east',$2,'luna','r1',.97,12)''', a, task)
        for parent in parents:
            await conn.execute('''INSERT INTO tank.shadow(ledger_id,tenant_id,task_type,primary_model,candidate_model,
                primary_content,agreement,method,quality) VALUES($1,$2,$3,'sol','routellm:luna:0123456789abcdef','x',1,'deepeval',
                '{"scores":{"correctness":1,"faithfulness":1,"task":0.995}}'::jsonb)''', parent, a, task)
        # The other tenant: different models and evidence that must never leak into tenant a's board.
        await seed_ledger(conn, other, task, 'gpt-oss', [50] * 5, cost=.0001)
        await conn.execute('''INSERT INTO tank.engine_evals(tenant_id,region,task_type,model,revision,agreement,samples)
            VALUES($1,'us-east',$2,'gpt-oss','r1',1,12)''', other, task)
    await scoreboard.record_bench(b.pool, platform_tenant=platform, region='us-east', task_type=task, model='flash-lite',
                                  score=1.0, cost_per_call=.001, samples=30, per_case=[(.1, 1.0)] * 30)
    roster = {'sol', 'luna', 'gpt-oss', 'flash-lite'}
    for tenant in (a, other):
        assert await scoreboard.refresh(b.pool, tenant, 'us-east', task, roster=roster, platform_tenant=platform) > 0
    rows = await scoreboard.read(b.pool, a, 'us-east', task)
    by = {(e.model, e.difficulty): e for e in rows}
    assert {e.model for e in rows} == {'sol', 'luna'}
    sol = by['sol', ALL]
    assert sol.p50_ms == 1050 and sol.p95_ms == 1905 and sol.price_usd == pytest.approx(.02)
    assert sol.error_rate == pytest.approx(1 / 21) and sol.cooling(datetime.now(timezone.utc))
    assert sol.quality == pytest.approx(.995) and sol.available
    luna_whole, luna_easy = by['luna', ALL], by['luna', 0]
    assert luna_whole.quality == pytest.approx(.97)          # gold vetoes the whole task
    assert luna_easy.quality == pytest.approx(.995) and luna_easy.quality_n == 40  # 20 shadows + 20 DeepEval
    assert luna_whole.price_usd == pytest.approx(.004) and not luna_whole.cooling(datetime.now(timezone.utc))
    # The decision is a lookup over this board: luna for easy requests, sol otherwise.
    now = datetime.now(timezone.utc)
    assert router.choose(rows, ladder_model='sol', bar=BAR, difficulty=.1, now=now)[0] == 'luna'
    assert router.choose(rows, ladder_model='sol', bar=BAR, difficulty=.9, now=now)[0] == 'sol'
    # Tenant isolation of scoreboard reads: neither tenant sees the other's or the platform's rows.
    other_rows = await scoreboard.read(b.pool, other, 'us-east', task)
    assert {e.model for e in other_rows} == {'gpt-oss'}
    assert all(e.model != 'gpt-oss' for e in rows) and all(e.model != 'flash-lite' for e in rows)
    assert await scoreboard.read(b.pool, uuid.uuid4(), 'us-east', task) == []
    assert await scoreboard.read(b.pool, a, 'za', task) == []
    platform_rows = await scoreboard.read(b.pool, platform, 'us-east', task)
    assert {(e.model, e.difficulty) for e in platform_rows} == {('flash-lite', ALL), ('flash-lite', 0)}
    assert all(e.quality == 1.0 for e in platform_rows)
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.router_scoreboard WHERE tenant_id=$1', a) == 3
        assert await conn.fetchval('SELECT count(*) FROM tank.router_scoreboard WHERE tenant_id=$1', other) == 1


@pytest.mark.asyncio
async def test_stale_board_falls_back_and_promotion_needs_proof(boundary):
    b = boundary
    a = b.tenants[0]
    task = 'router.proof'
    async with b.pool.acquire() as conn:
        await conn.execute('''INSERT INTO tank.router_scoreboard(tenant_id,region,task_type,model,difficulty,quality,quality_n,
            price_usd,available,p95_ms,error_rate,refreshed_at) VALUES
            ($1,'us-east',$2,'sol',-1,.995,10,.02,true,900,0,now()-interval '30 hours'),
            ($1,'us-east',$2,'luna',-1,1,40,.004,true,900,0,now()-interval '30 hours')''', a, task)
    rows = await scoreboard.read(b.pool, a, 'us-east', task)
    assert router.choose(rows, ladder_model='sol', bar=BAR, difficulty=None, now=datetime.now(timezone.utc)) == (
        None, 'stale_board')
    # Too few shadow decisions: not proven, even with perfect agreement.
    async with b.pool.acquire() as conn:
        parents = await seed_ledger(conn, a, task, 'sol', [100] * PROMOTE, cost=.02)
        for i, parent in enumerate(parents):
            await conn.execute('''INSERT INTO tank.router_decisions(tenant_id,region,task_type,ledger_id,mode,ladder_model,
                chosen_model,served_model,decision_ms,reason) VALUES($1,'us-east',$2,$3,'shadow','sol','luna','sol',.2,'x')''',
                a, task, parent)
            if i < router.PROMOTE_MIN_COMPARED:
                await conn.execute('''INSERT INTO tank.shadow(ledger_id,tenant_id,task_type,primary_model,candidate_model,
                    primary_content,agreement) VALUES($1,$2,$3,'sol','luna','x',$4)''', parent, a, task,
                    .98 if i == 0 else 1)
    proof = await router.prove(b.pool, a, 'us-east', task, BAR)
    assert proof == {'proven': True, 'decisions': PROMOTE, 'compared': router.PROMOTE_MIN_COMPARED,
                     'agreement': pytest.approx((29 + .98) / 30)}
    assert await router.promoted(b.pool, a, 'us-east', task)
    assert not await router.promoted(b.pool, b.tenants[1], 'us-east', task)
    assert not (await router.prove(b.pool, a, 'us-east', task, .9999))['proven']
    assert not await router.promoted(b.pool, a, 'us-east', task)  # a failed re-check demotes
    assert (await router.prove(b.pool, a, 'us-east', task, BAR))['proven']
    async with b.pool.acquire() as conn:
        await conn.execute('''DELETE FROM tank.router_decisions d WHERE tenant_id=$1 AND task_type=$2 AND NOT EXISTS
            (SELECT 1 FROM tank.shadow s WHERE s.tenant_id=d.tenant_id AND s.ledger_id=d.ledger_id)''', a, task)
    thin = await router.prove(b.pool, a, 'us-east', task, BAR)
    assert thin['decisions'] == router.PROMOTE_MIN_COMPARED and thin['proven']  # thin evidence keeps a promotion
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.shadow SET agreement=0 WHERE tenant_id=$1 AND task_type=$2", a, task)
    assert not (await router.prove(b.pool, a, 'us-east', task, BAR))['proven']  # a measured shortfall ends it
    times = await router.decision_times(b.pool, a, 'us-east', task)
    assert times['n'] == router.PROMOTE_MIN_COMPARED and times['p50_ms'] == pytest.approx(.2) and times['p95_ms'] == pytest.approx(.2)
    assert (await router.decision_times(b.pool, b.tenants[1], 'us-east', task))['n'] == 0


PROMOTE = router.PROMOTE_MIN_DECISIONS


async def post(b, tenant):
    response = await b.client.post('/v1/route', json={'tenant_id': str(tenant), 'task_type': 'routellm.proof',
                                                     'messages': [{'role': 'user', 'content': 'What is two plus two?'}]})
    assert response.status_code == 200, response.text
    if b.tank._background:
        await asyncio.gather(*list(b.tank._background))
    await router.drain()
    return response.json()


async def router_rows(b):
    async with b.pool.acquire() as conn:
        return [await conn.fetchval(f'SELECT count(*) FROM tank.{table}')
                for table in ('router_scoreboard', 'router_decisions', 'router_promotions')]


@pytest.mark.asyncio
async def test_http_unset_settings_keep_main_behaviour_then_receipt_shows_decision(real_tank, monkeypatch):
    b = real_tank
    a, other = b.tenants
    original_route, original_receipt = router.route, router.receipt

    async def never(*args, **kwargs):
        raise AssertionError('the router must not run while its setting is off')
    monkeypatch.setattr(router, 'route', never)
    monkeypatch.setattr(router, 'receipt', never)
    baseline = None
    for value in (None, '', 'TRUE', '1', 'yes', ' true'):
        for name in (router.SETTING, router.LATENCY_SETTING):
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        body = await post(b, a)
        assert body['model'] == 'sol' and body['content'] == 'Live policy answer'
        assert 'router' not in (body.get('engine') or {})
        shape = (sorted(body), sorted(body.get('engine') or {}))
        baseline = baseline or shape
        assert shape == baseline
    assert await router_rows(b) == [0, 0, 0]

    # Switched on: a shadow decision on every receipt, the ladder's pick still serves.
    monkeypatch.setattr(router, 'route', original_route)
    monkeypatch.setattr(router, 'receipt', original_receipt)
    monkeypatch.setenv(router.SETTING, 'true')
    monkeypatch.delenv(router.LATENCY_SETTING, raising=False)
    body = await post(b, a)
    decision = body['engine']['router']
    assert body['model'] == 'sol' and decision['served_model'] == 'sol' and decision['ladder_model'] == 'sol'
    assert decision['mode'] == 'fallback' and decision['reason'] == 'empty_board' and decision['decision_ms'] >= 0
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.router_decisions WHERE tenant_id=$1', a) == 1
        assert await conn.fetchval('SELECT count(*) FROM tank.router_scoreboard WHERE tenant_id=$1', a) >= 1
        assert await conn.fetchval('SELECT count(*) FROM tank.router_scoreboard WHERE tenant_id=$1', other) == 0
        await conn.execute('''INSERT INTO tank.router_scoreboard(tenant_id,region,task_type,model,difficulty,quality,quality_n,
            price_usd,available,p95_ms,error_rate) VALUES
            ($1,'us-east','routellm.proof','sol',-1,.995,10,.02,true,900,0),
            ($1,'us-east','routellm.proof','luna',-1,1,40,.001,true,900,0)
            ON CONFLICT(tenant_id,region,task_type,model,difficulty) DO UPDATE SET quality=excluded.quality,
            quality_n=excluded.quality_n,price_usd=excluded.price_usd,available=true,refreshed_at=now()''', a)
    body = await post(b, a)
    assert body['model'] == 'sol' and body['engine']['router']['mode'] == 'shadow'
    assert body['engine']['router']['chosen_model'] == 'luna'
    # Listed but not proven: still shadow. Listed and proven: the cheaper passing model serves.
    monkeypatch.setenv(router.SERVE_SETTING, 'routellm.proof')
    assert (await post(b, a))['engine']['router']['mode'] == 'shadow'
    async with b.pool.acquire() as conn:
        # The background proof check already ran and found nothing proven.
        assert await conn.fetchval("SELECT proven FROM tank.router_promotions WHERE tenant_id=$1", a) is False
        await conn.execute('''UPDATE tank.router_promotions SET proven=true WHERE tenant_id=$1''', a)

    body = await post(b, a)
    assert body['model'] == 'luna' and body['engine']['router']['mode'] == 'served'
    assert body['engine']['router']['served_model'] == 'luna'
    async with b.pool.acquire() as conn:
        served = await conn.fetchrow('SELECT model,cost_usd FROM tank.ledger WHERE id=$1', uuid.UUID(body['ledger_id']))
        assert served['model'] == 'luna'
        assert await conn.fetchval("SELECT count(*) FROM tank.router_decisions WHERE tenant_id=$1 AND mode='served'", a) == 1
    # The other tenant shares nothing: its board is empty, so it keeps today's routing.
    other_body = await post(b, other)
    assert other_body['model'] == 'sol' and other_body['engine']['router']['reason'] == 'empty_board'


@pytest.mark.asyncio
@pytest.mark.parametrize('setting', [None, 'TRUE', 'true'])
async def test_nightly_bench_writes_the_board_only_when_switched_on(database, monkeypatch, setting):
    import bench
    import controls
    import routellm_shadow
    from decimal import Decimal
    pool, rt = database
    monkeypatch.setattr(controls, 'db', lambda: pool)
    monkeypatch.setattr(bench, 'runtime', lambda: rt)

    async def models():
        return test_core1_proof.roster()
    rt._roster_models = models
    rt.LITELLM_MASTER_KEY = 'fixture-only'
    async with pool.acquire() as conn:
        rt.DATABASE_URL = test_train1.URL.rsplit('/', 1)[0] + '/' + await conn.fetchval('SELECT current_database()')

    async def call(model, messages, max_tokens):
        return dict(model=model, content='{"answer":"yes"}', tokens_in=100, tokens_out=20,
                    cost=Decimal('.012') if model == 'cheap' else Decimal('.12'), ok=True)
    monkeypatch.setattr(bench, 'call_model', call)
    monkeypatch.setattr(routellm_shadow, 'score', lambda prompt: .1)  # CPU difficulty fixture
    monkeypatch.setenv('TANK_BENCH_MAX_USD', '5')
    if setting is None:
        monkeypatch.delenv(router.SETTING, raising=False)
    else:
        monkeypatch.setenv(router.SETTING, setting)
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.policy(task_type,model,max_tokens_out) VALUES ('fixture','expensive',10)")
        await conn.execute("""INSERT INTO tank.evals(task_type,input,expected) VALUES('fixture','{"text":"test"}','{"answer":"yes"}')""")
    await bench.tick()
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.route_evidence WHERE task_type='fixture'") == 2
        rows = await conn.fetch("""SELECT tenant_id,model,difficulty,bench_score,bench_n,bench_cost_usd,quality
            FROM tank.router_scoreboard ORDER BY model,difficulty""")
    if setting != 'true':
        assert rows == []
        return
    assert [(r['model'], r['difficulty']) for r in rows] == [('cheap', -1), ('cheap', 0), ('expensive', -1), ('expensive', 0)]
    assert all(r['tenant_id'] == test_core1_proof.PLATFORM_TENANT for r in rows)
    whole = {r['model']: r for r in rows if r['difficulty'] == -1}
    assert whole['cheap']['bench_score'] == 1 and whole['cheap']['bench_n'] == 1
    assert whole['cheap']['bench_cost_usd'] == Decimal('.012') and whole['cheap']['quality'] == 1
    # One case is too few to pass at a difficulty; the whole-task bench row passes like the ladder's gold.
    assert all(r['quality'] is None for r in rows if r['difficulty'] == 0)
