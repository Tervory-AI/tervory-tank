"""Gates 7+8 offline proof: request -> memory -> brain -> Tank route -> receipt -> memory.

All cost and token figures here are FAKE FIXTURE values (a fixed price per
Tank route call and fixed input/output tokens). They are not billing, not
provider spend and not a live measurement. No network or paid call is made.
"""
import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import uuid

import httpx
import pytest
import yaml

from chassis.memory import MemoryClient
from agents.tisan import builder, gates_memory

ROOT = Path(__file__).resolve().parents[1]
TENANT = '11111111-1111-4111-8111-111111111111'
OTHER_TENANT = '22222222-2222-4222-8222-222222222222'
USER = '33333333-3333-4333-8333-333333333333'
OTHER_USER = '44444444-4444-4444-8444-444444444444'
PLAN = json.loads((ROOT / 'tests/fixtures/tisan_gate6_plans.json').read_text())['cases'][0]['response']
CORRECTED = copy.deepcopy(PLAN)
CORRECTED['pages'][0]['sections'].append({'id': 'contact-1', 'type': 'contact', 'props': {}})
# Fixed fake fixture figures per Tank route call; never derived from call counts.
FAKE_COST_USD = 0.0025
FAKE_TOKENS_IN = 1200
FAKE_TOKENS_OUT = 300


ScopedClient = MemoryClient

@pytest.fixture(autouse=True)
def opt_in_existing_gate_scenarios(monkeypatch):
    monkeypatch.setenv('TISAN_BRAIN_ENABLED', 'true')


class FakeHermes:
    """Tenant-scoped records store implementing the t51 user-scope server rules
    (personal rows carry meta.user_id; declared tenant-wide rows meta.scope)."""

    def __init__(self):
        self.rows = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = urlsplit(str(request.url))
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        if request.method == 'POST' and url.path == '/memories':
            body = json.loads(request.content)
            if not body.get('user_id') and body['kind'] not in {'tisan.brand', 'heartbeat'}:
                return httpx.Response(422, json={'detail': 'user_id or tenant_wide required'})
            meta = {k: v for k, v in (body.get('meta') or {}).items() if k not in ('user_id', 'scope')}
            meta.update({'user_id': body['user_id']} if body.get('user_id') else {'scope': 'tenant'})
            body['meta'] = meta
            row = {'id': str(uuid.uuid4()), 'tenant_id': body['tenant_id'], 'text': body['text'],
                   'claim': body['text'], 'kind': body['kind'], 'meta': copy.deepcopy(body.get('meta') or {})}
            self.rows.append(row)
            return httpx.Response(201, json=row)
        if request.method == 'GET' and url.path == '/records':
            offset, limit = int(query['offset']), int(query['limit'])
            user = query.get('user_id')
            mine = [r for r in self.rows if r['tenant_id'] == query['tenant_id'] and (
                (user is not None and r['meta'].get('user_id') == user) or r['meta'].get('scope') == 'tenant'
                or (user is None and 'user_id' not in r['meta'] and 'scope' not in r['meta']))]
            return httpx.Response(200, json={'memories': copy.deepcopy(mine[offset:offset + limit])})
        if request.method == 'DELETE' and url.path.startswith('/memories/'):
            ident = url.path.rsplit('/', 1)[1]
            self.rows = [r for r in self.rows if not (r['id'] == ident and r['tenant_id'] == query['tenant_id'])]
            return httpx.Response(204)
        if url.path == '/recall':
            raise AssertionError('exact repeats must not use embedding recall')
        return httpx.Response(404)


class FakeTank:
    def __init__(self, plan=PLAN):
        self.calls = []
        self.plan = plan

    async def delegate_task(self, actor, run_id, task, payload, recall):
        """Unit fake of the typed Tank boundary; canonical tests use its real adapter."""
        assert task == 'tisan.plan' and recall == []
        replies = []
        result = await builder.make_plan(payload, actor.tenant_id, payload['contract'], self, replies, cache_allowed=False)
        return {'result': result, 'receipt': gates_memory.tank_receipt(replies)}

    async def route(self, tenant, task, messages, **kwargs):
        assert task == 'tisan.plan'
        self.calls.append(tenant)
        return {'content': json.dumps(self.plan), 'ledger_id': str(uuid.uuid4()),
                'cost_usd': FAKE_COST_USD, 'tokens_in': FAKE_TOKENS_IN, 'tokens_out': FAKE_TOKENS_OUT}


@pytest.fixture
def hermes():
    return FakeHermes()


def client(hermes, http):
    return ScopedClient(base_url='http://placeholder-hermes', api_key='placeholder-room', agent='tisan', http=http)


def brief(request='one page with a hero'):
    return {'name': 'placeholder site', 'slug': 'placeholder-site', 'locale': 'en',
            'brand': {'colours': {'ink': '#111111', 'paper': '#ffffff', 'accent': '#cc3300', 'line': '#dddddd'},
                      'fonts': {'heading': 'Jost', 'body': 'Inter'}},
            'request': request}


async def run_once(hermes, *, tenant=TENANT, user=USER, request='one page with a hero'):
    """One product run with a fresh Tank client (a new process): per-run calls, fake cost and tokens."""
    tank = FakeTank()
    async with httpx.AsyncClient(transport=httpx.MockTransport(hermes.handler)) as http:
        result = await builder.execute({**brief(request), 'user_id': user}, tenant, tank=tank,
                                       memory=client(hermes, http), user=user)
    receipt = result['brain_receipt']
    assert len(tank.calls) == receipt['paid_calls']
    return result, receipt, len(tank.calls)


def figures(receipt):
    return receipt['paid_calls'], receipt['cost_usd'], receipt['tokens_in'] + receipt['tokens_out']


@pytest.mark.asyncio
async def test_request_routes_through_tank_records_receipt_and_remembers(hermes):
    result, receipt, calls = await run_once(hermes)
    assert result['ok'] is False and result['copy_needed']  # Planning finished; copy is the next step.
    assert receipt['source'] == 'tank' and receipt['memory_hit'] is False and len(receipt['ledger_ids']) == 1
    assert figures(receipt) == (1, FAKE_COST_USD, FAKE_TOKENS_IN + FAKE_TOKENS_OUT)
    kinds = sorted(r['kind'] for r in hermes.rows)
    assert kinds == ['tisan.brand', 'tisan.result']
    saved = next(r for r in hermes.rows if r['kind'] == 'tisan.result')
    assert saved['id'] == receipt['memory_id'] and saved['meta']['user_id'] == USER and saved['tenant_id'] == TENANT
    assert saved['meta']['result'] == PLAN and saved['meta']['receipt']['ledger_ids'] == receipt['ledger_ids']


@pytest.mark.asyncio
async def test_first_run_pays_once_and_exact_repeat_pays_nothing(hermes):
    _, first, first_calls = await run_once(hermes)
    _, repeat, repeat_calls = await run_once(hermes)
    assert (first_calls, figures(first)) == (1, (1, FAKE_COST_USD, FAKE_TOKENS_IN + FAKE_TOKENS_OUT))
    assert (repeat_calls, figures(repeat)) == (0, (0, 0.0, 0))
    assert repeat['source'] == 'memory' and repeat['memory_hit'] is True and repeat['ledger_ids'] == []
    print(f'GATES78_FAKE_FIXTURE first calls={first_calls} cost_usd={first["cost_usd"]} '
          f'tokens={first["tokens_in"] + first["tokens_out"]}; repeat calls={repeat_calls} '
          f'cost_usd={repeat["cost_usd"]} tokens={repeat["tokens_in"] + repeat["tokens_out"]} (fake fixture, not billing)')


@pytest.mark.asyncio
async def test_changed_input_misses_and_pays(hermes):
    await run_once(hermes)
    _, changed, calls = await run_once(hermes, request='two pages with a hero')
    assert calls == 1 and changed['memory_hit'] is False and figures(changed)[0] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('other', [{'user': OTHER_USER}, {'tenant': OTHER_TENANT}])
async def test_second_user_and_second_tenant_never_reuse(hermes, other):
    await run_once(hermes)
    _, isolated, calls = await run_once(hermes, **other)
    assert calls == 1 and isolated['memory_hit'] is False
    _, own_repeat, own_calls = await run_once(hermes, **other)
    assert own_calls == 0 and own_repeat['memory_hit'] is True
    _, original, original_calls = await run_once(hermes)
    assert original_calls == 0 and original['memory_hit'] is True


@pytest.mark.asyncio
async def test_correction_overrides_stale_result_without_paid_call(hermes):
    await run_once(hermes)
    async with httpx.AsyncClient(transport=httpx.MockTransport(hermes.handler)) as http:
        gate = gates_memory.GateMemory(client(hermes, http), TENANT, USER)
        await gate.correct('tisan.plan', [builder.manifest(), 'one page with a hero'], CORRECTED)
    assert not [r for r in hermes.rows if r['kind'] == 'tisan.result']  # Stale result invalidated.
    tank = FakeTank()
    async with httpx.AsyncClient(transport=httpx.MockTransport(hermes.handler)) as http:
        plan, receipt = await builder.remembered_plan(brief(), TENANT, builder.manifest(), tank, client(hermes, http), USER)
    assert plan == CORRECTED and tank.calls == [] and receipt['source'] == 'correction'
    assert figures(receipt) == (0, 0.0, 0)


@pytest.mark.asyncio
async def test_memory_off_and_forget_are_honoured(hermes):
    await run_once(hermes)
    async with httpx.AsyncClient(transport=httpx.MockTransport(hermes.handler)) as http:
        gate = gates_memory.GateMemory(client(hermes, http), TENANT, USER)
        assert {r['kind'] for r in await gate.view()} == {'tisan.brand', 'tisan.result'}
        await gate.set_enabled(False)
    before = len(hermes.rows)
    _, off, off_calls = await run_once(hermes)
    assert off_calls == 1 and off['memory_hit'] is False and off['memory_id'] is None
    assert len(hermes.rows) == before  # Nothing new is remembered while memory is off.
    async with httpx.AsyncClient(transport=httpx.MockTransport(hermes.handler)) as http:
        gate = gates_memory.GateMemory(client(hermes, http), TENANT, USER)
        await gate.set_enabled(True)
        # The user's personal result is forgotten; the brand is declared tenant-wide (t51) and stays.
        assert await gate.forget() == 1
        assert sorted(r['kind'] for r in await gate.view()) == ['tisan.brand', 'tisan.memory_setting']
    _, forgotten, calls = await run_once(hermes)
    assert calls == 1 and forgotten['memory_hit'] is False


@pytest.mark.asyncio
async def test_switch_off_keeps_the_previous_path(hermes, monkeypatch):
    monkeypatch.setenv('TISAN_BRAIN_ENABLED', 'false')
    tank = FakeTank()
    async with httpx.AsyncClient(transport=httpx.MockTransport(hermes.handler)) as http:
        plan, receipt = await builder.remembered_plan(brief(), TENANT, builder.manifest(), tank, client(hermes, http), USER)
    assert plan == PLAN and receipt is None and hermes.rows == [] and len(tank.calls) == 1


def test_remembered_list_is_defined_and_brain_is_off_by_default(monkeypatch):
    assert set(gates_memory.REMEMBERS) == {'tisan.brand', 'tisan.section', 'tisan.quote', 'tisan.result',
                                           'tisan.correction', 'tisan.memory_setting', 'tisan.outcome'}
    monkeypatch.delenv('TISAN_BRAIN_ENABLED', raising=False)
    assert gates_memory.brain_enabled() is False
    box = yaml.safe_load((ROOT / 'agents/tisan/docker-compose.yml').read_text())
    room = box['services']['agent-tisan']['environment']
    assert room['TISAN_BRAIN_ENABLED'] == '${TISAN_BRAIN_ENABLED:-false}'
    assert 'TISAN_BRAIN_URL' not in room  # Private discovery belongs to Tank.
    assert box['services']['tisan-brain']['environment']['TISAN_BRAIN_ENABLED'] == '${TISAN_BRAIN_ENABLED:-false}'
    assert box['services']['tisan-brain']['profiles'] == ['brain']
    assert box['services']['tisan-brain']['environment']['TANK_URL'] == 'http://tank:8000'
    docker = (ROOT / 'agents/tisan/Dockerfile').read_text()
    assert 'COPY agents/tisan/gates_memory.py agents/tisan/memory_api.py agents/tisan/brain_service.py agents/tisan/plan_jobs.py /app/' in docker


def test_gate_memory_uses_the_chassis_client_not_a_second_store():
    source = (ROOT / 'agents/tisan/gates_memory.py').read_text()
    for banned in ('qdrant', 'sqlite', 'asyncpg', 'redis', 'open(', 'httpx'):
        assert banned not in source


@pytest.mark.asyncio
async def test_exact_repeat_is_answered_from_memory_with_would_have_cost(hermes):
    _, first, first_calls = await run_once(hermes)
    assert first_calls == 1 and first['answered_from_memory'] is False
    assert first['cost_usd'] == FAKE_COST_USD and first['tokens_in'] == FAKE_TOKENS_IN
    for _ in range(2):  # Fixed fake cost per call: repeats never multiply it.
        _, repeat, calls = await run_once(hermes)
        assert calls == 0 and repeat['answered_from_memory'] is True and repeat['paid_calls'] == 0
        assert repeat['cost_usd'] == 0.0 and repeat['tokens_in'] == 0 and repeat['tokens_out'] == 0
        assert repeat['would_have_cost_usd'] == FAKE_COST_USD and repeat['would_have_paid_calls'] == 1
        assert repeat['would_have_tokens_in'] == FAKE_TOKENS_IN
    _, changed, changed_calls = await run_once(hermes, request='two pages with a hero')
    assert changed_calls == 1 and changed['answered_from_memory'] is False and changed['cost_usd'] == FAKE_COST_USD


class OutageHermes(FakeHermes):
    """The memory service itself is down (503), after a result was stored."""

    def __init__(self):
        super().__init__()
        self.down = False

    def handler(self, request):
        if self.down:
            return httpx.Response(503, json={'detail': 'memory store unreachable'})
        return super().handler(request)


@pytest.mark.asyncio
async def test_memory_outage_answers_without_memory_and_never_serves_a_stored_repeat():
    hermes = OutageHermes()
    await run_once(hermes)
    stored = len(hermes.rows)
    hermes.down = True
    _, receipt, calls = await run_once(hermes)  # The exact repeat is stored, but memory is down.
    assert calls == 1 and receipt['memory'] == 'memory unavailable' and receipt['memory_hit'] is False
    assert receipt['answered_from_memory'] is False and receipt['memory_id'] is None
    hermes.down = False
    assert len(hermes.rows) == stored


class ScopeErrorHermes(FakeHermes):
    def handler(self, request):
        return httpx.Response(422, json={'detail': 'scope error'})


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['missing-user', 'invalid-user', 'invalid-tenant', 'hermes-scope-error'])
async def test_scope_and_identity_errors_refuse_and_are_not_outages(case):
    hermes = ScopeErrorHermes() if case == 'hermes-scope-error' else FakeHermes()
    calls = []

    async def brain():
        calls.append(1)
        return {'plan': 'p'}, gates_memory.tank_receipt([{'cost_usd': FAKE_COST_USD}])
    tenant = 'not-a-uuid' if case == 'invalid-tenant' else TENANT
    user = {'missing-user': '', 'invalid-user': 'bad user/../x'}.get(case, USER)
    async with httpx.AsyncClient(transport=httpx.MockTransport(hermes.handler)) as http:
        with pytest.raises((ValueError, RuntimeError)) as refused:
            await gates_memory.run(client(hermes, http), tenant, user, 'tisan.plan', {'b': 1}, brain)
    assert not gates_memory.is_outage(refused.value)
    assert calls == [] and hermes.rows == []


@pytest.mark.asyncio
async def test_unverified_task_cannot_select_private_cached_work_and_keeps_paid_receipt(hermes):
    tank = FakeTank()
    async with httpx.AsyncClient(transport=httpx.MockTransport(hermes.handler)) as http:
        memory = client(hermes, http)
        for _ in range(2):
            result = await builder.execute(brief(), TENANT, tank=tank, memory=memory, user=None)
            assert result['brain_receipt']['paid_calls'] == 1
            assert result['brain_receipt']['cost_usd'] == FAKE_COST_USD
            assert result['brain_receipt']['memory_id'] is None
    assert len(tank.calls) == 2 and hermes.rows == []


@pytest.mark.asyncio
async def test_run_bound_client_preserves_the_actual_approved_secret_scan(tmp_path):
    from chassis.tank import TankClient
    from test_tisan_quality import transport
    (tmp_path / 'safe.py').write_text('value = 1\n')
    calls = []
    async with httpx.AsyncClient(transport=transport(calls)) as http:
        original = TankClient('http://placeholder-tank', 'placeholder-room', 'tisan', http)
        bound = builder.run_tank(original, str(uuid.uuid4()))
        checked = await builder._scaffold()._secret_check(tmp_path, TENANT, bound)
    assert checked['ok'] is True and checked['findings'] == []
    assert calls == [('GET', '/v1/skala/scan.secrets/run'), ('POST', '/v1/skala/scan.secrets/run')]


@pytest.mark.asyncio
async def test_distinct_bound_jobs_keep_the_existing_default_off_plan_cache(monkeypatch):
    from chassis.tank import TankClient
    monkeypatch.setenv('TISAN_BRAIN_ENABLED', 'false')
    calls = []
    def route(request):
        assert request.url.path == '/v1/route'
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={'content': json.dumps(PLAN), 'ledger_id': str(uuid.uuid4()),
            'cost_usd': FAKE_COST_USD, 'tokens_in': FAKE_TOKENS_IN, 'tokens_out': FAKE_TOKENS_OUT})
    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        tank = TankClient('http://placeholder-tank', 'placeholder-room', 'tisan', http)
        for _ in range(2):
            result = await builder.execute(brief(), TENANT, tank=tank, run_id=str(uuid.uuid4()))
            assert result['copy_needed'] and 'brain_receipt' not in result
    assert len(calls) == 1 and calls[0]['paid_run_id']
