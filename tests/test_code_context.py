"""Send only what matters: repo-map slicing and output caps on a recorded synthetic session."""
import asyncio
import json
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pgserver
import pytest
import pytest_asyncio
from fastapi import HTTPException

from agent_skills import input_encoding
import code_context
import code_limits
import command
import prompt_cache
import test_command as existing

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/code_context'
api = existing.api
CAPS = {'command.code': 4096, 'command.code.start': 512, 'command.code.explore': 1024,
        'command.code.fix': 768, 'command.code.edit': 2048}


@pytest.fixture
def runtime(monkeypatch):
    value = existing.runtime.__wrapped__(monkeypatch)
    value.pool = lambda: command.db()
    return value


@pytest.fixture(scope='module')
def postgres(tmp_path_factory):
    server = pgserver.get_server(tmp_path_factory.mktemp('code-context-pg'), cleanup_mode='delete')
    try:
        yield server.get_uri()
    finally:
        server.cleanup()


@pytest_asyncio.fixture
async def command_pool(monkeypatch, postgres):
    monkeypatch.setenv('POOL_SCHEMA_DATABASE_URL', postgres)
    generator = existing.command_pool.__wrapped__()
    try:
        yield await anext(generator)
    finally:
        await generator.aclose()


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    for name in (code_context.SETTING, code_limits.CAPS_SETTING, code_limits.SETTING):
        monkeypatch.delenv(name, raising=False)
    code_context.CACHE.clear()
    yield
    code_context.CACHE.clear()


def session():
    return json.loads((FIXTURE / 'session.json').read_text())


def files():
    value = {}
    for turn in session()['turns']:
        for result in turn['tool_results']:
            output = json.loads(result['output'])
            if result['name'] == 'read_file':
                value[output['arguments']['path']] = output['result']['text']
    return value


def count(messages):
    encoding = input_encoding()
    return sum(len(encoding.encode(message['content'])) for message in messages)


def policies(task, tenant):
    if task not in CAPS:
        raise HTTPException(404, f'no policy for task_type {task!r}')
    return {'max_tokens_out': CAPS[task]}


async def answer(pool, task, tenant=existing.TENANT):
    await pool.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd) "
                       "VALUES($1,$2,'orchestrator','command.code','fixture',0)", task, tenant)
    return SimpleNamespace(ledger_id=task, content='{"answer":"Fixture response","requests":[]}')


def capture(monkeypatch, pool, seen, tenant=existing.TENANT):
    async def route(actor, messages, model, task, **options):
        seen.append({'messages': messages, 'options': options})
        return await answer(pool, task, actor.tenant_id)
    routed = AsyncMock(side_effect=route)
    monkeypatch.setattr(command, 'route_code', routed)
    return routed


async def replay(client, headers=None):
    """Drive the whole recorded session as the CLI does: one prompt, continuations."""
    headers = headers or {}
    thread = (await client.post('/v1/command/threads', json={}, headers=headers)).json()['thread_id']
    data = session()
    prompt = str(uuid.uuid4())
    replies = []
    for index, turn in enumerate(data['turns']):
        response = await client.post(f'/v1/command/threads/{thread}/code-turn', headers=headers, json={
            'text': data['text'], 'prompt_id': prompt, 'continuation': index > 0,
            'tool_results': turn['tool_results'], 'history': turn['history']})
        assert response.status_code == 200, response.text
        replies.append(response.json())
    return thread, replies


def recorded_tokens():
    return json.loads((FIXTURE / 'tokens.json').read_text())


# Map and cache ---------------------------------------------------------------

def test_python_map_has_files_symbols_and_signatures():
    entry = code_context.parse('shop/cart.py', files()['shop/cart.py'])
    names = {symbol.name: symbol for symbol in entry.symbols}
    assert {'CartLine', 'CartLine.amount', 'Cart', 'Cart.subtotal', 'Checkout', 'checkout_total', 'receipt_lines'} <= set(names)
    assert names['checkout_total'].signature == 'def checkout_total(cart: Cart) -> Checkout:'
    assert names['Cart'].kind == 'type' and names['Cart.add'].kind == 'method'
    assert names['checkout_total'].start < names['checkout_total'].end


def test_other_languages_and_broken_python_use_the_local_pattern_map():
    entry = code_context.parse('web/cart.ts', 'export interface Line {\n  sku: string\n}\n\nexport async function total(lines: Line[]) {\n  return 1\n}\n'
                               'export const add = (a: number) => a + 1\n')
    assert [(s.name, s.kind) for s in entry.symbols] == [('Line', 'type'), ('total', 'function'), ('add', 'function')]
    broken = code_context.parse('x.py', 'def ok(a):\n    return a\n\ndef broken(:\n')
    assert [s.name for s in broken.symbols] == ['ok', 'broken']


def test_cache_reuses_parse_by_content_hash():
    cache = code_context.RepoMapCache()
    key = ('t', 'u', 'repo')
    cache.update(key, 'p', {'a.py': 'def f():\n    return 1\n'}, set(), None, ['a.py'])
    cache.update(key, 'p', {'a.py': 'def f():\n    return 1\n'}, set(), None, ['a.py'])
    assert cache.parses == 1
    entries, _, _ = cache.update(key, 'p', {'a.py': 'def g():\n    return 2\n'}, set(), None, ['a.py'])
    assert cache.parses == 2 and [s.name for s in entries['a.py'].symbols] == ['g']


def test_cache_is_scoped_to_tenant_user_and_repo():
    cache = code_context.RepoMapCache()
    text = 'def secret_formula():\n    return 42\n'
    cache.update(('tenant-a', 'user-1', 'repo'), 'p', {'a.py': text}, set(), None, ['a.py'])
    for key in [('tenant-b', 'user-1', 'repo'), ('tenant-a', 'user-2', 'repo'), ('tenant-a', 'user-1', 'other')]:
        entries, paths, diff = cache.update(key, 'p', {}, set(), None, [])
        assert entries == {} and paths == [] and diff is None
        assert cache.paths(key) == set()
    # The same content in another tenant is parsed again, never shared.
    cache.update(('tenant-b', 'user-1', 'repo'), 'p', {'a.py': text}, set(), None, ['a.py'])
    assert cache.parses == 2


def test_cache_is_bounded_and_expires(monkeypatch):
    monkeypatch.setattr(code_context, 'MAX_SCOPE_BYTES', 1000)
    monkeypatch.setattr(code_context, 'MAX_SCOPES', 2)
    cache = code_context.RepoMapCache()
    cache.update(('t', 'u', 'r'), 'p', {'a.py': 'x = 1\n' * 10, 'b.py': 'y = 2\n' * 10}, set(), None, [], now=0)
    assert cache.paths(('t', 'u', 'r')) == {'b.py'}
    cache.update(('t', 'u', 's'), 'p', {}, set(), None, [], now=1)
    cache.update(('t', 'u', 'v'), 'p', {}, set(), None, [], now=2)
    assert cache.keys() == [('t', 'u', 's'), ('t', 'u', 'v')]
    cache.update(('t', 'u', 'w'), 'p', {}, set(), None, [], now=2 + code_context.TTL_SECONDS + 1)
    assert cache.keys() == [('t', 'u', 'w')]
    assert cache.size == sum(scope.size for scope in cache.scopes.values())


def test_slice_picks_targets_types_and_diff_deterministically():
    encoding = input_encoding()
    entries = {path: code_context.parse(path, text) for path, text in files().items()}
    diff = json.loads(session()['turns'][3]['tool_results'][1]['output'])['result']['output']
    locations = [('shop/cart.py', 57)]
    scope = sorted(entries)
    first = code_context.build_slice(entries, scope, [], diff, locations, {'checkout_total'}, encoding)
    second = code_context.build_slice(entries, scope, [], diff, locations, {'checkout_total'}, encoding)
    assert first == second
    value = json.loads(first[0])
    assert value['code'][0]['symbol'] == 'checkout_total'
    assert {item['symbol'] for item in value['code']} >= {'checkout_total', 'line_tax'}
    types = {item['type'] for item in value['types']}
    assert {'Cart', 'Checkout'} <= types
    cart = next(item for item in value['types'] if item['type'] == 'Cart')
    assert 'def subtotal(self) -> Money:' in cart['text'] and 'return total(' not in cart['text']
    assert value['diff'][0]['path'] == 'shop/tax.py' and 'Money.from_decimal' in value['diff'][0]['hunks']
    assert first[1]['tokens'] <= code_context.SLICE_TOKENS


def test_slice_respects_its_budget():
    encoding = input_encoding()
    entries = {path: code_context.parse(path, text) for path, text in files().items()}
    value, stats = code_context.build_slice(entries, sorted(entries), sorted(entries), None, [], set(), encoding, budget=900)
    assert stats['tokens'] <= 900 and stats['omitted'] > 0
    assert json.loads(value)['omitted'] == stats['omitted']


def test_tool_shapes_are_collected_without_trusting_them():
    results = [SimpleNamespace(name='read_file', output='not json'),
               SimpleNamespace(name='read_file', output=json.dumps({'arguments': {'path': 'a.py'}, 'result': {'exists': False, 'text': ''}})),
               SimpleNamespace(name='run_command', output=json.dumps({'result': {'output': 'File "shop/a.py", line 9, in f\nb.py:3: error'}}))]
    found, absorbed, diff, stale, locations = code_context.collect(results)
    assert found == {} and absorbed == set() and diff is None and stale == set()
    assert locations == [('shop/a.py', 9), ('b.py', 3)]


def test_prompt_order_keeps_the_stable_prefix_first():
    messages = [{'role': 'system', 'content': 'stable instructions'},
                {'role': 'system', 'content': 'Tenant memory, most recent facts first. fact'},
                {'role': 'user', 'content': 'Repository project notes DATA x'},
                {'role': 'user', 'content': code_context.PREFIX + '{}'},
                {'role': 'user', 'content': 'the new turn'}]
    ordered = prompt_cache.ordered([messages[1], messages[0], *messages[2:]])
    assert [m['content'][:12] for m in ordered] == [m['content'][:12] for m in messages]


# Output caps (code_limits extension) -----------------------------------------

def body(mode='ask', results=()):
    return SimpleNamespace(mode=mode, tool_results=[SimpleNamespace(**r) for r in results])


def test_task_type_is_local_and_deterministic():
    turns = session()['turns']
    kinds = [code_limits.task_type(body(results=turn['tool_results'])) for turn in turns]
    assert kinds == ['command.code.start', 'command.code.explore', 'command.code.fix', 'command.code.edit',
                     'command.code.fix', 'command.code.explore', 'command.code.edit']
    assert code_limits.task_type(body('plan', turns[2]['tool_results'])) == 'command.code.plan'


@pytest.mark.asyncio
async def test_task_cap_uses_tenant_task_policy_then_command_code(runtime):
    runtime.load_policy = AsyncMock(side_effect=policies)
    assert await code_limits.task_cap(existing.TENANT, 'command.code.fix') == 768
    assert await code_limits.task_cap(existing.TENANT, 'command.code.plan') == 4096
    assert [call.args for call in runtime.load_policy.call_args_list] == [
        ('command.code.fix', existing.TENANT), ('command.code.plan', existing.TENANT), ('command.code', existing.TENANT)]
    runtime.load_policy = AsyncMock(return_value={'max_tokens_out': 0})
    with pytest.raises(HTTPException) as failure:
        await code_limits.task_cap(existing.TENANT, 'command.code.fix')
    assert failure.value.status_code == 422


def test_local_summaries_are_deterministic_and_bounded():
    encoding = input_encoding()
    turns = session()['turns']
    listing = SimpleNamespace(**turns[1]['tool_results'][0])
    assert code_limits.summary_text(listing).startswith('[local summary: 247 files in 3 folders]')
    search = SimpleNamespace(**turns[5]['tool_results'][1])
    assert code_limits.summary_text(search).startswith('[local summary: 33 matches in 2 files]')
    passing = SimpleNamespace(**turns[6]['tool_results'][1])
    summary = code_limits.summary_text(passing)
    assert summary.startswith('[local summary: command succeeded; ') and len(summary.splitlines()) == 21
    status = SimpleNamespace(name='git', output=json.dumps({'result': {'output': ' M a.py\n M b.py\n?? c.py'}}))
    assert code_limits.summary_text(status) == '[local summary: changed files by status] ?? 1, M 2'
    failing = SimpleNamespace(**turns[2]['tool_results'][2])
    assert code_limits.summary_text(failing) == code_limits.diagnostic_text(failing)
    for turn in turns:
        rows = [SimpleNamespace(**row) for row in turn['tool_results']]
        if rows:
            value, stats = code_limits.render(rows, 768, encoding, summarize=True)
            assert value == code_limits.render(rows, 768, encoding, summarize=True)[0]
            assert len(encoding.encode(value)) <= 768 and stats['tokens_after'] <= 768


# HTTP boundary ---------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize('value', [None, '', ' ', 'false', 'TRUE', '1', 'yes', 'true '])
async def test_unset_or_other_values_keep_mains_exact_request(api, runtime, monkeypatch, value):
    client, pool = api
    runtime.load_policy = AsyncMock(side_effect=AssertionError('disabled features load no policy'))
    baseline = []
    capture(monkeypatch, pool, baseline)
    await replay(client)
    if value is None:
        assert all(item['options'] == {} for item in baseline)
        return
    # 'true ' strips to the literal and is the only enabling spelling here.
    for name in (code_context.SETTING, code_limits.CAPS_SETTING):
        monkeypatch.setenv(name, value)
    if value.strip() == 'true':
        runtime.load_policy = AsyncMock(side_effect=policies)
    seen = []
    capture(monkeypatch, pool, seen)
    _, replies = await replay(client)
    if value.strip() == 'true':
        assert all('context' in reply for reply in replies) and runtime.load_policy.await_count
        return
    assert [item['messages'] for item in seen] == [item['messages'] for item in baseline]
    assert all(item['options'] == {} for item in seen) and all('context' not in reply for reply in replies)
    assert code_context.CACHE.keys() == [] and code_context.CACHE.parses == 0
    runtime.load_policy.assert_not_awaited()


@pytest.mark.asyncio
async def test_recorded_session_tokens_before_and_after(api, runtime, monkeypatch):
    client, pool = api
    runtime.load_policy = AsyncMock(side_effect=policies)
    expected = recorded_tokens()
    measured = {}
    for name, settings in [('main', ()), ('slicing', (code_context.SETTING,)),
                           ('output_caps', (code_limits.CAPS_SETTING,)),
                           ('both', (code_context.SETTING, code_limits.CAPS_SETTING))]:
        for setting in (code_context.SETTING, code_limits.CAPS_SETTING):
            monkeypatch.delenv(setting, raising=False)
        for setting in settings:
            monkeypatch.setenv(setting, 'true')
        code_context.CACHE.clear()
        seen = []
        capture(monkeypatch, pool, seen)
        _, replies = await replay(client)
        measured[name] = [count(item['messages']) for item in seen]
        # The system prompt (instructions and catalogue) is identical in every row and provider-cached.
        measured[name + '_beyond_system'] = [count(item['messages'][1:]) for item in seen]
        if name != 'main':
            assert [reply['context']['tokens_after'] for reply in replies] == measured[name]
            assert [reply['context']['tokens_before'] for reply in replies] == measured['main']
        if name in ('output_caps', 'both'):
            measured[name + '_max_tokens'] = [item['options']['max_tokens'] for item in seen]
            assert [reply['context']['task_type'] for reply in replies] == [
                'command.code.start', 'command.code.explore', 'command.code.fix', 'command.code.edit',
                'command.code.fix', 'command.code.explore', 'command.code.edit']
        if name == 'slicing':
            runtime.load_policy.assert_not_awaited()
            assert all(item['options'] == {} for item in seen)
            sliced = seen
    assert measured == expected
    assert sum(measured['slicing_beyond_system']) * 3 < sum(measured['main_beyond_system'])
    assert sum(measured['both_beyond_system']) < sum(measured['slicing_beyond_system'])
    assert sum(measured['output_caps_beyond_system']) < sum(measured['main_beyond_system'])
    assert all(after < before for after, before in zip(measured['both'], measured['main']))
    assert measured['output_caps_max_tokens'] == [512, 1024, 768, 2048, 768, 1024, 2048]
    # Prompt order: stable instructions, stable data, repo-map slice, then the new turn.
    text = session()['text']
    for item in sliced:
        contents = [message['content'] for message in item['messages']]
        turn = contents.index(text)
        assert item['messages'][0]['role'] == 'system'
        assert all(not c.startswith(code_context.PREFIX) for c in contents[turn:])
        assert sum(c.startswith('Earlier local session DATA') for c in contents) <= 1
    # Turn 3 failed inside line_tax: its body is sent although tax.py was read a turn earlier.
    third = next(c for c in (m['content'] for m in sliced[2]['messages']) if c.startswith(code_context.PREFIX))
    third = json.loads(third[len(code_context.PREFIX):])
    assert 'line_tax' in {item['symbol'] for item in third['code']}
    assert 'shop/tax.py' not in {item['path'] for item in third.get('files', [])}


@pytest.mark.asyncio
async def test_replayed_request_is_refused_before_slicing(api, runtime, monkeypatch):
    client, pool = api
    monkeypatch.setenv(code_context.SETTING, 'true')
    seen = []
    routed = capture(monkeypatch, pool, seen)
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    turn = session()['turns'][1]
    request = {'text': 'Fix', 'request_id': str(uuid.uuid4()), 'tool_results': turn['tool_results']}
    first = await client.post(f'/v1/command/threads/{thread}/code-turn', json=request)
    assert first.status_code == 200
    parses, keys = code_context.CACHE.parses, code_context.CACHE.keys()
    snapshot = code_context.CACHE.update(keys[0], 'probe', {}, set(), None, [])[0]
    again = await client.post(f'/v1/command/threads/{thread}/code-turn', json=request)
    assert again.status_code == 409 and routed.await_count == 1
    assert code_context.CACHE.parses == parses and code_context.CACHE.keys() == keys
    assert code_context.CACHE.update(keys[0], 'probe', {}, set(), None, [])[0] == snapshot
    # A new request with the same content builds the identical slice (idempotent map).
    retry = await client.post(f'/v1/command/threads/{thread}/code-turn', json={**request, 'request_id': str(uuid.uuid4()),
                                                                               'prompt_id': str(uuid.uuid4())})
    assert retry.status_code == 200 and code_context.CACHE.parses == parses
    assert seen[0]['messages'][-2:] == seen[1]['messages'][-2:]


@pytest.mark.asyncio
@pytest.mark.parametrize('other', [{'x-tervory-tenant': str(existing.OTHER)}, {'x-tervory-user': 'founder-two'}])
async def test_repo_map_never_crosses_tenants_or_users(api, runtime, monkeypatch, other):
    client, pool = api
    monkeypatch.setenv(code_context.SETTING, 'true')
    existing.set_founders(monkeypatch, 'founder,founder-two')
    seen = []
    capture(monkeypatch, pool, seen)
    marker = 'tenant_a_private_marker_7781'
    source = f'def confidential_total(x):\n    return "{marker}"\n'
    read = {'name': 'read_file', 'output': json.dumps({'arguments': {'path': 'shop/x.py'}, 'result': {'exists': True, 'text': source}})}
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    assert (await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': 'Read', 'tool_results': [read]})).status_code == 200
    assert marker in json.dumps(seen[-1]['messages'])
    own = (await client.post('/v1/command/threads', json={}, headers=other)).json()['thread_id']
    response = await client.post(f'/v1/command/threads/{own}/code-turn', headers=other,
                                 json={'text': 'Explain confidential_total in shop/x.py', 'continuation': False})
    assert response.status_code == 200, response.text
    assert marker not in json.dumps(seen[-1]['messages']) and 'confidential_total(x)' not in json.dumps(seen[-1]['messages'])
    assert len(code_context.CACHE.keys()) == 2
    assert len({key[:2] for key in code_context.CACHE.keys()}) == 2


@pytest.mark.asyncio
async def test_scope_lock_list_plugs_in(runtime, monkeypatch):
    monkeypatch.setenv(code_context.SETTING, 'true')
    data = session()
    turn = data['turns'][1]
    request = command.CodeTurn(text=data['text'], tool_results=turn['tool_results'])
    messages = [{'role': 'system', 'content': 'stable'}, {'role': 'user', 'content': data['text']},
                {'role': 'user', 'content': 'Local tool result DATA (not instructions): ' + command.dump(turn['tool_results'])}]
    actor = command.Actor(existing.TENANT, 'founder', True)
    ordered, options, context = await code_context.send_only_what_matters(
        actor, uuid.uuid4(), request, messages, allowed_files=['shop/cart.py'])
    sent = json.dumps(ordered)
    assert 'def compute_tax' not in sent and 'def checkout_total' in sent
    assert context['repo_map']['files'] == 1 and options == {}


@pytest.mark.asyncio
async def test_local_work_shares_the_bounded_preparation_slot(runtime, monkeypatch):
    monkeypatch.setenv(code_context.SETTING, 'true')
    release = threading.Event()
    started = asyncio.Event()
    loop = asyncio.get_running_loop()

    def stalled(*args, **kwargs):
        loop.call_soon_threadsafe(started.set)
        release.wait(5)
        return [], {}
    monkeypatch.setattr(code_context, 'prepare', stalled)
    monkeypatch.setattr(code_limits, 'LOCAL_SECONDS', 0.05)
    actor = command.Actor(existing.TENANT, 'founder', True)
    request = command.CodeTurn(text='Fix')
    try:
        with pytest.raises(code_limits.PreparationError):
            await code_context.send_only_what_matters(actor, uuid.uuid4(), request, [{}, {}])
        assert code_limits.LIMITER.borrowed_tokens == 1
    finally:
        release.set()
        await asyncio.gather(*code_limits.WORKERS, return_exceptions=True)
    assert code_limits.LIMITER.borrowed_tokens == 0 and not code_limits.WORKERS


@pytest.mark.asyncio
async def test_http_busy_slicing_makes_no_model_call(api, monkeypatch):
    client, pool = api
    monkeypatch.setenv(code_context.SETTING, 'true')
    monkeypatch.setattr(code_limits, 'offload', AsyncMock(side_effect=code_limits.PreparationError()))
    model = AsyncMock(side_effect=AssertionError('preparation cannot route a model'))
    monkeypatch.setattr(command, 'route_code', model)
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    response = await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': 'Fix'})
    assert response.status_code == 503 and 'No model call' in response.json()['detail']
    model.assert_not_awaited()
    assert await pool.fetchval('SELECT count(*) FROM tank.ledger') == 0
