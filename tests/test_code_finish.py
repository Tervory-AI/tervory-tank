"""Gate before (finish): setting names, tenant caps, fix memory, rollback, diffs, live admission.

Every HTTP proof runs the real Command router on a disposable PostgreSQL with fake
model calls only (no provider is reachable from these tests).
"""
import asyncio
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import asyncpg
import pgserver
import pytest
import pytest_asyncio

import code_admission
import code_diffs
import code_finish
import code_preflight
import command
import paid_steps
import test_command as existing

api = existing.api
ROOT = Path(__file__).resolve().parents[1]
MODEL = 'placeholder-model'
STEP = paid_steps.model_step('command.code', MODEL, agent='orchestrator')
OTHER_TENANT = {'x-tervory-tenant': str(existing.OTHER)}
BROKEN = 'def add(a, b):\n    return a - b\n'
FIXED = 'def add(a, b):\n    return a + b\n'
WRONG = 'def add(a, b):\n    return a * b\n'
FIX = code_diffs.make('calc.py', BROKEN, FIXED)
ALL = [*code_finish.SETTINGS.values(), code_admission.CONCURRENT, code_admission.PER_MINUTE,
       code_preflight.SETTING, code_preflight.BUDGET_TOKENS, code_preflight.BUDGET_USD,
       'ENGINE_CODE_GATE_ENABLED', 'ENGINE_CODE_PROGRESS_ENABLED', 'ENGINE_CODE_SLICING_ENABLED',
       'ENGINE_CODE_OUTPUT_CAPS_ENABLED', 'ENGINE_CODE_TOOL_LIMITS_ENABLED']


@pytest.fixture
def runtime(monkeypatch):
    value = existing.runtime.__wrapped__(monkeypatch)
    value.pool = lambda: command.db()
    value._roster_models = AsyncMock(return_value=[{'model_name': MODEL, 'model_info': {}}])
    return value


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name in ALL:
        monkeypatch.delenv(name, raising=False)
    code_admission.reset()
    yield
    code_admission.reset()


@pytest.fixture(scope='module')
def local_postgres(tmp_path_factory):
    server = pgserver.get_server(tmp_path_factory.mktemp('code-finish-pg'), cleanup_mode='delete')
    try:
        yield server.get_uri()
    finally:
        server.cleanup()


@pytest_asyncio.fixture
async def command_pool(monkeypatch, local_postgres):
    monkeypatch.setenv('POOL_SCHEMA_DATABASE_URL', local_postgres)
    generator = existing.command_pool.__wrapped__()
    try:
        yield await anext(generator)
    finally:
        await generator.aclose()


def enable(monkeypatch, *names):
    for name in names:
        monkeypatch.setenv(code_finish.SETTINGS[name], 'true')


def fake(pool, answers, seen, *, cost=0.01, gate=None):
    answers = list(answers)

    async def model(actor, messages, name, task, **options):
        seen.append({'messages': messages, 'task': task, 'tenant': actor.tenant_id})
        if gate is not None and len(seen) == 1:
            gate['entered'].set()
            await gate['release'].wait()
        await pool.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd,tokens_in,tokens_out,task_id) "
                           "VALUES($1,$2,'orchestrator','command.code','fixture',$3,100,50,$1)", task, actor.tenant_id, cost)
        content = answers.pop(0) if answers else json.dumps({'answer': 'Done', 'requests': []})
        return SimpleNamespace(ledger_id=task, content=content)
    return AsyncMock(side_effect=model)


def run(code=1, seconds='0.03', command_text='pytest -q'):
    output = ('.' if code == 0 else 'F') + f'\n1 {"passed" if code == 0 else "failed"} in {seconds}s'
    if code:
        output = 'calc.py:2: assert add(1, 1) == 2\n' + output
    return {'name': 'run_command', 'output': json.dumps({'arguments': {'command': command_text}, 'result': {
        'ran': True, 'code': code, 'output': output, 'timed_out': False}})}


def edited(diff, applied=True):
    result = {'applied': True} if applied is True else {'error': 'Code tool refused.'} if applied == 'error' else {'applied': False}
    return {'name': 'propose_edit', 'output': json.dumps({'arguments': {'diff': diff}, 'result': result})}


def read(path, text):
    return {'name': 'read_file', 'output': json.dumps({'arguments': {'path': path}, 'result': {'exists': True, 'text': text}})}


def fixing(*requests):
    return json.dumps({'answer': 'Fixing', 'requests': list(requests)})


def git_apply(tmp_path, name, before, diff):
    """Apply a diff exactly as the CLI does: git apply in a scratch repo."""
    folder = tmp_path / uuid.uuid4().hex
    folder.mkdir()
    subprocess.run(['git', 'init', '--quiet'], cwd=folder, check=True)
    (folder / name).write_text(before)
    done = subprocess.run(['git', 'apply', '--unidiff-zero', '--whitespace=nowarn'], cwd=folder, input=diff,
                          text=True, capture_output=True)
    assert done.returncode == 0, done.stderr
    return (folder / name).read_text()


async def new_thread(client, headers=None):
    return (await client.post('/v1/command/threads', json={}, headers=headers or {})).json()['thread_id']


async def turn(client, thread, text, prompt, results=(), *, continuation=False, headers=None, **extra):
    reply = await client.post(f'/v1/command/threads/{thread}/code-turn', headers=headers or {}, json={
        'text': text, 'prompt_id': prompt, 'continuation': continuation, 'tool_results': list(results), **extra})
    assert reply.status_code == 200, reply.text
    return reply.json()


async def thread_state(pool, thread):
    return json.loads(await pool.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1', uuid.UUID(thread)))


async def routed(pool, tenant=existing.TENANT):
    await pool.execute("INSERT INTO tank.policy(task_type,tenant_id,model,max_tokens_out) VALUES('command.code',$1,$2,1000)",
                       tenant, MODEL)
    await pool.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES($1,'fixture',0.000001,0.000002) "
                       "ON CONFLICT(model) DO UPDATE SET input_usd=EXCLUDED.input_usd,output_usd=EXCLUDED.output_usd,active=true", MODEL)
    async with pool.acquire() as conn:
        await paid_steps.register(conn, STEP, 'model', 'model', 'tank.policy', task='command.code', model=MODEL)
    await pool.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto','founder') "
                       "ON CONFLICT(tenant_id,step_id) DO UPDATE SET mode=EXCLUDED.mode", tenant, STEP)


# 1. Setting names

def test_every_engine_code_setting_read_in_tank_is_in_env_example():
    pattern = re.compile(r'\bENGINE_CODE_[A-Z0-9_]*[A-Z0-9]\b')
    read_in_tank = {name for path in (ROOT / 'tank').rglob('*.py') for name in pattern.findall(path.read_text())}
    listed = {line.split('=', 1)[0] for line in (ROOT / '.env.example').read_text().splitlines() if '=' in line and not line.startswith('#')}
    assert {'ENGINE_CODE_PREFLIGHT_ENABLED', 'ENGINE_CODE_BUDGET_TOKENS', 'ENGINE_CODE_BUDGET_USD'} <= read_in_tank
    assert set(code_finish.SETTINGS.values()) <= read_in_tank
    assert read_in_tank - listed == set()
    lines = (ROOT / '.env.example').read_text().splitlines()
    for name in read_in_tank:
        index = lines.index(name + '=')  # blank by default
        assert lines[index - 1].startswith('# '), name  # one-line comment each


@pytest.mark.parametrize('value', [None, '', 'false', '1', 'TRUE', ' true', 'true '])
def test_only_the_literal_true_switches_a_control_on(monkeypatch, value):
    for name in code_finish.SETTINGS:
        if value is None:
            monkeypatch.delenv(code_finish.SETTINGS[name], raising=False)
        else:
            monkeypatch.setenv(code_finish.SETTINGS[name], value)
        assert code_finish.on(name) is False
    assert __import__('code_caps').enabled() is False


# Unset-setting compatibility at the HTTP boundary.

async def scenario(client, pool):
    """Two rounds with repeated reads, a whole-file answer, a failing then passing check."""
    thread = await new_thread(client)
    prompt = str(uuid.uuid4())
    window = [read('calc.py', BROKEN), run(1), read('calc.py', BROKEN)]
    first = await turn(client, thread, 'Fix add in calc.py', prompt, window)
    second = await turn(client, thread, 'Fix add in calc.py', prompt, [*window, edited(FIX), run(0)], continuation=True)
    return thread, [first, second]


def shape(reply):
    return {key: reply[key] for key in ('answer', 'requests', 'cards', 'turn')} | {'keys': sorted(reply)}


@pytest.mark.asyncio
@pytest.mark.parametrize('value', [None, '', 'false', 'TRUE', ' true', '1'])
async def test_unset_settings_keep_mains_exact_http_behaviour(api, monkeypatch, value):
    client, pool = api
    answers = [fixing({'name': 'propose_edit', 'arguments': {'path': 'calc.py', 'diff': FIXED}},
                      {'name': 'run_command', 'arguments': {'command': 'pytest -q'}})]
    await pool.execute("INSERT INTO tank.code_task_caps(tenant_id,max_tokens,updated_by) VALUES($1,1,'founder')", existing.TENANT)
    signature = code_finish.signature('pytest -q', json.loads(run(1)['output'])['result']['output'])
    await pool.execute("INSERT INTO tank.code_fix_memory(tenant_id,signature,command,diffs,files,created_by) "
                       "VALUES($1,$2,'pytest -q',$3,$4,'founder')", existing.TENANT, signature, [FIX], ['calc.py'])
    # main: the hooks bypassed entirely (the functions main had before this change).
    baseline = []
    with monkeypatch.context() as main:
        main.setattr(code_preflight, 'before_paid_call', code_preflight.preflight)
        main.setattr(code_preflight, 'paid_call', code_preflight.planned_call)
        main.setattr(command, 'route_code', fake(pool, answers, baseline))
        _, expected = await scenario(client, pool)
    for name in code_finish.SETTINGS.values():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    monkeypatch.setenv(code_admission.CONCURRENT, 'not-a-number')
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, answers, seen))
    thread, replies = await scenario(client, pool)
    assert [shape(reply) for reply in replies] == [shape(reply) for reply in expected]
    assert [item['messages'] for item in seen] == [item['messages'] for item in baseline] and len(seen) == 2
    state = await thread_state(pool, thread)
    assert code_finish.STATE not in state and all('code_finish' not in step for step in state['steps'].values())
    memory = await pool.fetchrow('SELECT hits,status FROM tank.code_fix_memory WHERE tenant_id=$1', existing.TENANT)
    assert (memory['hits'], memory['status']) == (0, 'good')
    assert await pool.fetchval('SELECT count(*) FROM tank.code_fix_memory') == 1
    assert (await client.get('/v1/command/code/caps')).status_code == 404
    for method in ('PUT', 'POST', 'DELETE'):
        for payload in ({'max_tokens': 5}, {'max_tokens': 'bad'}):
            assert (await client.request(method, '/v1/command/code/caps', json=payload)).status_code == 404
    assert (await client.get('/v1/command/code/caps', headers={'x-tank-key': 'wrong'})).status_code == 404
    assert await pool.fetchval('SELECT max_tokens FROM tank.code_task_caps WHERE tenant_id=$1', existing.TENANT) == 1


# 2. A tenant's own cap per code task

@pytest.mark.asyncio
async def test_tenant_cap_tightens_under_the_platform_ceiling(api, monkeypatch):
    client, pool = api
    enable(monkeypatch, 'caps')
    monkeypatch.setenv(code_preflight.SETTING, 'true')
    monkeypatch.setenv(code_preflight.BUDGET_TOKENS, '1000000')
    await routed(pool)
    await routed(pool, existing.OTHER)
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    member = {'x-tervory-user': 'member'}
    assert (await client.put('/v1/command/code/caps', json={'max_tokens': 10}, headers=member)).status_code == 403
    assert (await client.get('/v1/command/code/caps', headers=member)).status_code == 403
    admin = {'x-tervory-user': 'tenant-admin', 'x-tervory-role': 'org:admin'}
    assert (await client.put('/v1/command/code/caps', json={'max_usd': '0'}, headers=admin)).status_code == 422
    assert (await client.put('/v1/command/code/caps', json={'max_tokens': 10, 'extra': 1}, headers=admin)).status_code == 422
    assert (await client.put('/v1/command/code/caps', json={'max_tokens': '10'}, headers=admin)).status_code == 422
    assert (await client.post('/v1/command/code/caps', json={}, headers=admin)).status_code == 405
    saved = (await client.put('/v1/command/code/caps', json={'max_tokens': 10}, headers=admin)).json()
    assert saved == {'tenant': {'tokens': 10, 'usd': None}, 'platform': {'tokens': 1000000, 'usd': None},
                     'effective': {'tokens': 10, 'usd': None}}
    text = 'Fix the off-by-one in tank/a.py'
    thread = await new_thread(client)
    held = await turn(client, thread, text, str(uuid.uuid4()))
    assert held['preflight']['status'] == 'budget' and held['preflight']['cap'] == {'tokens': 10} and not seen
    assert held['turn']['cost_usd'] == 0
    # The other tenant has no row: today's behaviour, under the platform cap only.
    other = await new_thread(client, OTHER_TENANT)
    paid = await turn(client, other, text, str(uuid.uuid4()), headers=OTHER_TENANT)
    assert 'preflight' not in paid and len(seen) == 1 and seen[0]['tenant'] == existing.OTHER
    assert (await client.get('/v1/command/code/caps', headers=OTHER_TENANT)).json()['tenant'] == {'tokens': None, 'usd': None}
    # Above the platform cap the ceiling wins.
    raised = (await client.put('/v1/command/code/caps', json={'max_tokens': 10 ** 9})).json()
    assert raised['effective'] == {'tokens': 1000000, 'usd': None}
    assert 'preflight' not in await turn(client, await new_thread(client), text, str(uuid.uuid4())) and len(seen) == 2
    # With no platform dollar cap the tenant's dollar cap applies on its own.
    await client.put('/v1/command/code/caps', json={'max_usd': '0.000001'})
    usd = await turn(client, await new_thread(client), text, str(uuid.uuid4()))
    assert usd['preflight']['status'] == 'budget' and usd['preflight']['cap'] == {'usd': 0.000001} and len(seen) == 2
    cleared = (await client.put('/v1/command/code/caps', json={'max_tokens': None, 'max_usd': None})).json()
    assert cleared['tenant'] == {'tokens': None, 'usd': None}
    assert await pool.fetchval('SELECT count(*) FROM tank.code_task_caps') == 0
    # Switched off, a stored row is ignored.
    await pool.execute("INSERT INTO tank.code_task_caps(tenant_id,max_tokens,updated_by) VALUES($1,1,'founder')", existing.TENANT)
    monkeypatch.delenv(code_finish.SETTINGS['caps'])
    assert 'preflight' not in await turn(client, await new_thread(client), text, str(uuid.uuid4())) and len(seen) == 3


@pytest.mark.asyncio
async def test_cap_and_fix_memory_tables_are_tenant_isolated_under_rls(api):
    _, pool = api
    async with pool.acquire() as conn:
        await conn.execute((ROOT / 'db/migrations/tenant_rls/tank.sql').read_text())
        for table in ('code_task_caps', 'code_fix_memory'):
            flags = await conn.fetchrow("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=$1::regclass", 'tank.' + table)
            assert flags['relrowsecurity'] and flags['relforcerowsecurity']
        role = 'code_finish_' + uuid.uuid4().hex[:12]
        await conn.execute(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS')
        await conn.execute(f'GRANT USAGE ON SCHEMA tank TO {role}')
        await conn.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON tank.code_task_caps,tank.code_fix_memory TO {role}')
        signature = 'a' * 64
        async with conn.transaction():
            await conn.execute(f'SET LOCAL ROLE {role}')
            await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(existing.TENANT))
            await conn.execute("INSERT INTO tank.code_task_caps(tenant_id,max_tokens,updated_by) VALUES($1,5,'a')", existing.TENANT)
            await conn.execute("INSERT INTO tank.code_fix_memory(tenant_id,signature,command,diffs,files,created_by) "
                               "VALUES($1,$2,'pytest',$3,$4,'a')", existing.TENANT, signature, [FIX], ['calc.py'])
        for table in ('code_task_caps', 'code_fix_memory'):
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE {role}')
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(existing.OTHER))
                assert await conn.fetchval(f'SELECT count(*) FROM tank.{table}') == 0
                assert await conn.execute(f'UPDATE tank.{table} SET tenant_id=$1', existing.OTHER) == 'UPDATE 0'
                assert await conn.execute(f'DELETE FROM tank.{table}') == 'DELETE 0'
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute(f'SET LOCAL ROLE {role}')
                    await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(existing.OTHER))
                    await conn.execute("INSERT INTO tank.code_task_caps(tenant_id,max_tokens,updated_by) VALUES($1,5,'b')", existing.TENANT)
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE {role}')
                await conn.execute("SELECT set_config('app.tenant_id','',true)")
                assert await conn.fetchval(f'SELECT count(*) FROM tank.{table}') == 0
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE {role}')
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(existing.TENANT))
                assert await conn.fetchval(f'SELECT count(*) FROM tank.{table}') == 1


# 3. Error-to-fix memory

async def fixture_task(client, thread, *, seconds):
    """One coding task in a thread: the client reports the same failing check up front."""
    prompt = str(uuid.uuid4())
    replies = [await turn(client, thread, 'Make the calc tests pass', prompt, [run(1, seconds)])]
    while replies[-1]['requests'] and len(replies) < 4:
        window = [run(1, seconds)]
        for request in replies[-1]['requests']:
            if request['name'] == 'read_file':
                window.append(read(request['arguments']['path'], BROKEN))
            elif request['name'] == 'propose_edit':
                window.append(edited(request['arguments']['diff']))
            elif request['name'] == 'run_command':
                window.append(run(0, seconds))
        replies.append(await turn(client, thread, 'Make the calc tests pass', prompt, window, continuation=True))
    return replies


@pytest.mark.asyncio
async def test_same_error_three_times_costs_zero_after_the_first_fix_is_remembered(api, monkeypatch):
    client, pool = api
    enable(monkeypatch, 'memory')
    seen = []
    model = fake(pool, [fixing({'name': 'propose_edit', 'arguments': {'diff': FIX}},
                               {'name': 'run_command', 'arguments': {'command': 'pytest -q'}})], seen)
    monkeypatch.setattr(command, 'route_code', model)
    thread = await new_thread(client)
    costs = []
    for seconds in ('0.03', '0.05', '1.20'):  # durations differ; the error signature does not
        replies = await fixture_task(client, thread, seconds=seconds)
        costs.append(round(sum(reply['turn']['cost_usd'] for reply in replies), 6))
        if seconds != '0.03':
            assert [reply['finish']['status'] for reply in replies] == ['fix_memory', 'fix_memory_done']
            assert replies[0]['requests'] == [{'name': 'read_file', 'arguments': {'path': 'calc.py'}},
                                              {'name': 'propose_edit', 'arguments': {'path': None, 'diff': FIX}},
                                              {'name': 'run_command', 'arguments': {'command': 'pytest -q'}}]
            assert all(row['cost_usd'] == 0 for reply in replies for row in reply['receipt']['rows'])
    assert costs == [0.02, 0.0, 0.0] and len(seen) == 2
    entry = await pool.fetchrow('SELECT * FROM tank.code_fix_memory WHERE tenant_id=$1', existing.TENANT)
    assert entry['status'] == 'good' and entry['hits'] == 2 and list(entry['diffs']) == [FIX]
    assert list(entry['files']) == ['calc.py'] and entry['command'] == 'pytest -q'
    ledger = await pool.fetch("SELECT model,cost_usd FROM tank.ledger WHERE tenant_id=$1 AND model='code'", existing.TENANT)
    assert len(ledger) == 4 and all(row['cost_usd'] == 0 for row in ledger)


@pytest.mark.asyncio
async def test_a_wrong_remembered_fix_is_rolled_back_and_marked_bad(api, monkeypatch, tmp_path):
    client, pool = api
    enable(monkeypatch, 'memory')
    wrong = code_diffs.make('calc.py', BROKEN, WRONG)
    signature = code_finish.signature('pytest -q', json.loads(run(1)['output'])['result']['output'])
    await pool.execute("INSERT INTO tank.code_fix_memory(tenant_id,signature,command,diffs,files,created_by) "
                       "VALUES($1,$2,'pytest -q',$3,$4,'someone')", existing.TENANT, signature, [wrong], ['calc.py'])
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    thread, prompt = await new_thread(client), str(uuid.uuid4())
    served = await turn(client, thread, 'Make the calc tests pass', prompt, [run(1)])
    assert served['finish']['status'] == 'fix_memory' and not seen
    window = [run(1), read('calc.py', BROKEN), edited(wrong), run(1, '0.04')]
    undone = await turn(client, thread, 'Make the calc tests pass', prompt, window, continuation=True)
    assert undone['finish']['status'] == 'fix_memory_rollback' and undone['turn']['cost_usd'] == 0 and not seen
    inverse = undone['requests'][0]['arguments']['diff']
    assert inverse == code_diffs.invert(wrong) and git_apply(tmp_path, 'calc.py', WRONG, inverse) == BROKEN
    entry = await pool.fetchrow('SELECT status,bad_reason FROM tank.code_fix_memory WHERE tenant_id=$1', existing.TENANT)
    assert (entry['status'], entry['bad_reason']) == ('bad', 'did_not_fix')
    paid = await turn(client, thread, 'Make the calc tests pass', prompt, [*window, edited(inverse)], continuation=True)
    assert 'finish' not in paid and len(seen) == 1
    assert 'rolled back' in seen[0]['messages'][-1]['content']
    # A bad entry is never served again.
    again = await turn(client, await new_thread(client), 'Make the calc tests pass', str(uuid.uuid4()), [run(1)])
    assert 'finish' not in again and len(seen) == 2


@pytest.mark.asyncio
async def test_fix_memory_is_tenant_isolated(api, monkeypatch):
    client, pool = api
    enable(monkeypatch, 'memory')
    seen = []
    answer = fixing({'name': 'propose_edit', 'arguments': {'diff': FIX}}, {'name': 'run_command', 'arguments': {'command': 'pytest -q'}})
    monkeypatch.setattr(command, 'route_code', fake(pool, [answer, json.dumps({'answer': 'Done', 'requests': []}), answer], seen))
    await fixture_task(client, await new_thread(client), seconds='0.03')
    assert len(seen) == 2
    other = await new_thread(client, OTHER_TENANT)
    reply = await turn(client, other, 'Make the calc tests pass', str(uuid.uuid4()), [run(1)], headers=OTHER_TENANT)
    assert 'finish' not in reply and len(seen) == 3 and seen[-1]['tenant'] == existing.OTHER
    rows = await pool.fetch('SELECT tenant_id FROM tank.code_fix_memory')
    assert [row['tenant_id'] for row in rows] == [existing.TENANT]
    # Another user of the same tenant gets the tenant's memory.
    colleague = {'x-tervory-user': 'colleague'}
    shared = await turn(client, await new_thread(client, colleague), 'Make the calc tests pass', str(uuid.uuid4()), [run(1)],
                        headers=colleague)
    assert shared['finish']['status'] == 'fix_memory' and len(seen) == 3


# 4. Rollback to the last green checkpoint

def progress(tree, tests, stage=3):
    return {'tree': tree * 64, 'tests_passed': tests, 'build_stage': stage}


@pytest.mark.asyncio
async def test_a_paid_round_that_loses_tests_rolls_back_to_the_last_green_checkpoint(api, monkeypatch, tmp_path):
    client, pool = api
    enable(monkeypatch, 'rollback')
    monkeypatch.setenv('ENGINE_CODE_GATE_ENABLED', 'true')
    monkeypatch.setenv('ENGINE_CODE_PROGRESS_ENABLED', 'true')
    seen = []
    worse = code_diffs.make('calc.py', FIXED, WRONG)
    monkeypatch.setattr(command, 'route_code', fake(pool, [fixing({'name': 'propose_edit', 'arguments': {'diff': worse}})], seen))
    thread, prompt = await new_thread(client), str(uuid.uuid4())
    text = 'Refactor add in calc.py'
    green = [run(0)]
    first = await turn(client, thread, text, prompt, green, progress=progress('a', 5))
    assert 'finish' not in first and len(seen) == 1
    window = [*green, edited(worse), run(1)]
    back = await turn(client, thread, text, prompt, window, continuation=True, progress=progress('b', 3))
    assert back['finish']['status'] == 'rollback' and back['turn']['cost_usd'] == 0 and len(seen) == 1
    assert back['finish']['to'] == {'tests_passed': 5, 'build_stage': 3} and back['finish']['checkpoint'] == 'a' * 64
    inverse = back['requests'][0]['arguments']['diff']
    assert git_apply(tmp_path, 'calc.py', WRONG, inverse) == FIXED
    assert back['requests'][1] == {'name': 'run_command', 'arguments': {'command': 'pytest -q'}}
    # The next envelope must be back at the green tree before any paid call.
    window += [edited(inverse), run(0)]
    refused = await turn(client, thread, text, prompt, window, continuation=True, progress=progress('c', 5))
    assert refused['finish']['status'] == 'rollback_unconfirmed' and len(seen) == 1
    # The client's window rolls on; the old failure has left it.
    confirmed = await turn(client, thread, text, prompt, [*window[3:], run(0, '0.07')], continuation=True,
                           progress=progress('a', 5))
    assert 'finish' not in confirmed and len(seen) == 2
    assert 'rolled back to the last checkpoint where the checks passed' in seen[1]['messages'][-1]['content']


@pytest.mark.asyncio
async def test_rollback_needs_a_paid_round_and_stops_for_undo_on_new_files(api, monkeypatch):
    client, pool = api
    enable(monkeypatch, 'rollback')
    monkeypatch.setenv('ENGINE_CODE_GATE_ENABLED', 'true')
    monkeypatch.setenv('ENGINE_CODE_PROGRESS_ENABLED', 'true')
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    created = '--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+x = 1\n'
    thread, prompt = await new_thread(client), str(uuid.uuid4())
    await turn(client, thread, 'Add new.py', prompt, [run(0)], progress=progress('a', 5))
    held = await turn(client, thread, 'Add new.py', prompt, [run(0), edited(created), run(1)], continuation=True,
                      progress=progress('b', 4))
    assert held['finish']['status'] == 'rollback_needs_undo' and held['requests'] == [] and len(seen) == 1
    # Without progress evidence nothing is rolled back.
    plain = await turn(client, await new_thread(client), 'Add new.py', str(uuid.uuid4()), [run(1)])
    assert 'finish' not in plain and len(seen) == 2


# 5. Diffs in and out

LONG = ''.join(f'def f{n}(x):\n    return x + {n}\n\n' for n in range(150))


def test_minimal_diffs_and_inverses_apply_with_git(tmp_path):
    cases = [(BROKEN, FIXED), (LONG, LONG.replace('x + 7\n', 'x - 7\n')), ('a\nb', 'a\nc'), ('-- x\n++ y\n', '--- x\n+++ y\n'),
             ('one\n\ntwo\n', 'one\ntwo\n'), (LONG, LONG + 'tail')]
    for before, after in cases:
        diff = code_diffs.make('m.py', before, after)
        assert git_apply(tmp_path, 'm.py', before, diff) == after
        assert git_apply(tmp_path, 'm.py', after, code_diffs.invert(diff)) == before
        assert code_finish.diff_files(diff) == (['m.py'], False)
    rewrite = code_diffs.make('m.py', 'old\n', 'brand new\n')
    assert code_diffs.whole_rewrite(rewrite, 'old\n') == 'brand new\n'
    assert code_diffs.whole_rewrite(code_diffs.make('m.py', LONG, LONG.replace('x + 7', 'x - 7')), LONG) is None


@pytest.mark.asyncio
async def test_diffs_in_and_out_cut_what_is_sent(api, monkeypatch, tmp_path):
    client, pool = api
    after = LONG.replace('x + 7\n', 'x - 7\n')
    whole_hunk = '--- a/big.py\n+++ b/big.py\n@@ -1,{} +1,{} @@\n'.format(LONG.count('\n'), after.count('\n')) + \
        ''.join('-' + line + '\n' for line in LONG.splitlines()) + ''.join('+' + line + '\n' for line in after.splitlines())
    answers = [fixing({'name': 'propose_edit', 'arguments': {'path': 'big.py', 'diff': after}}),
               fixing({'name': 'propose_edit', 'arguments': {'diff': whole_hunk}})]
    window = [read('big.py', LONG), run(1), read('big.py', LONG)]

    async def send(seen):
        monkeypatch.setattr(command, 'route_code', fake(pool, list(answers), seen))
        thread, prompt = await new_thread(client), str(uuid.uuid4())
        first = await turn(client, thread, 'Fix f7 in big.py', prompt, window)
        second = await turn(client, thread, 'Fix f7 in big.py', prompt, window, continuation=True)
        return first, second

    before_seen, after_seen = [], []
    plain = await send(before_seen)
    enable(monkeypatch, 'diffs')
    shaped = await send(after_seen)
    assert plain[0]['requests'][0]['arguments']['diff'] == after  # off: the whole file passes through
    for reply in shaped:
        edit = reply['requests'][0]['arguments']
        assert edit['path'] is None and edit['diff'].startswith('--- a/big.py\n+++ b/big.py\n')
        assert len(edit['diff']) < 0.1 * len(after)
        assert git_apply(tmp_path, 'big.py', LONG, edit['diff']) == after
    sent_before = len(json.dumps(before_seen[0]['messages']))
    sent_after = len(json.dumps(after_seen[0]['messages']))
    assert sent_after < sent_before - len(LONG) * 0.9  # the earlier copy of big.py is a pointer
    assert code_diffs.INSTRUCTION in after_seen[0]['messages'][-1]['content']
    # A diff that could not apply: the model may send the whole file for that path.
    failed = await turn(client, await new_thread(client), 'Fix f7 in big.py', str(uuid.uuid4()),
                        [read('big.py', LONG), edited(code_diffs.make('big.py', 'nope\n', 'x\n'), 'error')])
    assert failed['requests'] == [] and len(after_seen) == 3
    assert 'could not apply' in after_seen[2]['messages'][-1]['content']


# 6. Admission control on live code traffic

@pytest.mark.asyncio
async def test_admission_caps_concurrent_paid_calls_per_tenant_with_a_clear_hold(api, monkeypatch):
    client, pool = api
    enable(monkeypatch, 'admission')
    monkeypatch.setenv(code_admission.CONCURRENT, '1')
    seen, gate = [], {'entered': asyncio.Event(), 'release': asyncio.Event()}
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen, gate=gate))
    first = asyncio.create_task(turn(client, await new_thread(client), 'Explain calc.py', str(uuid.uuid4())))
    await asyncio.wait_for(gate['entered'].wait(), 10)
    held = await turn(client, await new_thread(client), 'Explain calc.py', str(uuid.uuid4()))
    assert held['finish']['status'] == 'busy' and held['finish']['admission']['reason'] == 'concurrent'
    assert 'No model call was made' in held['answer'] and held['turn']['cost_usd'] == 0 and len(seen) == 1
    other = await turn(client, await new_thread(client, OTHER_TENANT), 'Explain calc.py', str(uuid.uuid4()), headers=OTHER_TENANT)
    assert 'finish' not in other and len(seen) == 2
    gate['release'].set()
    assert 'finish' not in await first
    again = await turn(client, await new_thread(client), 'Explain calc.py', str(uuid.uuid4()))
    assert 'finish' not in again and len(seen) == 3


@pytest.mark.asyncio
async def test_admission_caps_paid_calls_per_minute_and_refuses_bad_settings(api, monkeypatch):
    client, pool = api
    enable(monkeypatch, 'admission')
    monkeypatch.setenv(code_admission.PER_MINUTE, '2')
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    for _ in range(2):
        assert 'finish' not in await turn(client, await new_thread(client), 'Explain calc.py', str(uuid.uuid4()))
    held = await turn(client, await new_thread(client), 'Explain calc.py', str(uuid.uuid4()))
    assert held['finish']['admission']['reason'] == 'per_minute' and 1 <= held['finish']['admission']['retry_after_s'] <= 60
    assert len(seen) == 2
    monkeypatch.setenv(code_admission.PER_MINUTE, '0')
    invalid = await turn(client, await new_thread(client, OTHER_TENANT), 'Explain calc.py', str(uuid.uuid4()), headers=OTHER_TENANT)
    assert invalid['finish']['status'] == 'setting' and len(seen) == 2


def test_admission_slots_expire_and_release():
    code_admission.reset()
    assert code_admission.admit('t', 'a', now=0) is None
    assert code_admission.admit('t', 'b', now=1) is None
    assert code_admission.admit('t', 'c', now=2)['reason'] == 'concurrent'
    assert code_admission.admit('u', 'c', now=2) is None  # another tenant has its own slots
    code_admission.release('t', 'a')
    assert code_admission.admit('t', 'c', now=3) is None
    assert code_admission.admit('t', 'd', now=4)['reason'] == 'concurrent'
    assert code_admission.admit('t', 'd', now=3 + code_admission.HOLD_SECONDS) is None  # unreleased slots expire
