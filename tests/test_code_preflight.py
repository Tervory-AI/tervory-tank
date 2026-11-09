"""Gate before: preflight before the first paid code model call (fake model calls only)."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pgserver
import pytest
import pytest_asyncio

import code_preflight
import command
import paid_steps
import test_command as existing

api = existing.api
MODEL = 'placeholder-model'
STEP = paid_steps.model_step('command.code', MODEL, agent='orchestrator')


@pytest.fixture
def runtime(monkeypatch):
    value = existing.runtime.__wrapped__(monkeypatch)
    value.pool = lambda: command.db()
    value._roster_models = AsyncMock(return_value=[{'model_name': MODEL, 'model_info': {}}])
    return value


@pytest.fixture(autouse=True)
def opt_in(monkeypatch):
    monkeypatch.setenv(code_preflight.SETTING, 'true')
    for name in (code_preflight.BUDGET_TOKENS, code_preflight.BUDGET_USD):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope='module')
def local_postgres(tmp_path_factory):
    server = pgserver.get_server(tmp_path_factory.mktemp('code-preflight-pg'), cleanup_mode='delete')
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


async def routed(pool, tenant=existing.TENANT, *, mode='auto', max_out=1000):
    await pool.execute("INSERT INTO tank.policy(task_type,tenant_id,model,max_tokens_out) VALUES('command.code',$1,$2,$3)",
                       tenant, MODEL, max_out)
    await pool.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES($1,'fixture',0.000001,0.000002) "
                       "ON CONFLICT(model) DO UPDATE SET input_usd=EXCLUDED.input_usd,output_usd=EXCLUDED.output_usd,active=true", MODEL)
    async with pool.acquire() as conn:
        await paid_steps.register(conn, STEP, 'model', 'model', 'tank.policy', task='command.code', model=MODEL)
    if mode:
        await pool.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,$3,'founder') "
                           "ON CONFLICT(tenant_id,step_id) DO UPDATE SET mode=EXCLUDED.mode", tenant, STEP, mode)


def fake(pool, answers, seen, *, tokens=(100, 50), cost=0.01):
    answers = list(answers)

    async def model(actor, messages, name, task, **options):
        run = paid_steps.current.get()
        seen.append({'messages': messages, 'run': run, 'task': task})
        await pool.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd,tokens_in,tokens_out,task_id) "
                           "VALUES($1,$2,'orchestrator','command.code','fixture',$3,$4,$5,$1)", task, actor.tenant_id, cost, *tokens)
        content = answers.pop(0) if answers else json.dumps({'answer': 'Done', 'requests': []})
        return SimpleNamespace(ledger_id=task, content=content)
    return AsyncMock(side_effect=model)


def read(path, text='x = 1'):
    return {'name': 'read_file', 'output': json.dumps({'arguments': {'path': path}, 'result': {'exists': True, 'text': text}})}


async def thread_state(pool, thread):
    return json.loads(await pool.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1', uuid.UUID(thread)))


async def new_thread(client):
    return (await client.post('/v1/command/threads', json={})).json()['thread_id']


# Unit proofs of the deterministic local rung.

@pytest.mark.parametrize('setting', [None, '', 'false', '1', 'TRUE', ' true', 'true ', 'yes'])
def test_only_the_literal_true_enables(monkeypatch, setting):
    if setting is None:
        monkeypatch.delenv(code_preflight.SETTING, raising=False)
    else:
        monkeypatch.setenv(code_preflight.SETTING, setting)
    assert code_preflight.enabled() is False
    monkeypatch.setenv(code_preflight.SETTING, 'true')
    assert code_preflight.enabled() is True


@pytest.mark.parametrize('text,expected', [
    ('Fix the failing test', True), ('make it better', True), ('Improve things in the app somehow please today', True),
    ('Fix tank/command.py so it returns 404', False), ('Rename parse_plan to read_plan everywhere', False),
    ('Add a retry with backoff to the http client helper', False), ('Handle the KeyError in the loader', False),
])
def test_intent_triage_is_deterministic(text, expected):
    assert code_preflight.vague(text) is expected


def test_task_splitter_separates_asks():
    assert code_preflight.split('In tank/a.py:\n1. Add a flag\n2) Remove the dead branch\n   in the loader') == [
        'In tank/a.py:\nAdd a flag', 'In tank/a.py:\nRemove the dead branch\nin the loader']
    assert code_preflight.split('- one thing\n- another thing') == ['one thing', 'another thing']
    assert code_preflight.split('Fix tank/a.py. Also update docs/b.md; then bump the version.') == [
        'Fix tank/a.py.', 'Also update docs/b.md;', 'then bump the version.']
    assert code_preflight.split('Fix the bug in tank/a.py and add a test') == ['Fix the bug in tank/a.py and add a test']


def test_splitter_and_triage_stay_linear_on_hostile_text():
    import time
    for text in ['* ' + '  ' * 10000 + 'x', 'a.' + ' ' * 20000 + 'also b', 'x. ' * 6000, '1) ' + '\t' * 20000]:
        started = time.monotonic()
        code_preflight.split(text)
        code_preflight.vague(text)
        assert time.monotonic() - started < 1
    assert code_preflight.split('- a\n-  b  ') == ['a', 'b']


def test_paths_are_relative_and_bounded():
    text = 'Edit ./tank/a.py, `web/App.tsx` and Dockerfile. Not /etc/passwd, ../x.py, e.g. or https://x.io/a.js.'
    assert code_preflight.paths_in(text) == ['tank/a.py', 'web/App.tsx', 'Dockerfile']
    assert len(code_preflight.paths_in(' '.join(f'f{n}.py' for n in range(50)))) == code_preflight.MAX_FILES
    assert code_preflight.match_files('Add a retry to the http client helper',
                                      ['tank/http_client.py', 'tank/helpers.py', 'README.md', '../escape/http_client.py']) == ['tank/http_client.py']


@pytest.mark.parametrize('tokens,usd,expected', [
    ('', '', {}), ('5000', '', {'tokens': 5000}), ('', '0.25', {'usd': code_preflight.Decimal('0.25')}),
])
def test_budget_settings_are_strict(monkeypatch, tokens, usd, expected):
    monkeypatch.setenv(code_preflight.BUDGET_TOKENS, tokens)
    monkeypatch.setenv(code_preflight.BUDGET_USD, usd)
    assert code_preflight.budget() == expected


@pytest.mark.parametrize('name,value', [(code_preflight.BUDGET_TOKENS, '0'), (code_preflight.BUDGET_TOKENS, '1e6'),
                                        (code_preflight.BUDGET_TOKENS, ' 5'), (code_preflight.BUDGET_USD, '0'),
                                        (code_preflight.BUDGET_USD, '-1'), (code_preflight.BUDGET_USD, 'nan'),
                                        (code_preflight.BUDGET_USD, '1.1234567')])
def test_invalid_budget_settings_are_refused(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(code_preflight.SettingError):
        code_preflight.budget()


def test_scope_lock_on_results_and_requests():
    results = [command.CodeResult(**read('tank/a.py')), command.CodeResult(**read('tank/secret.py')),
               command.CodeResult(name='search', output=json.dumps({'arguments': {'pattern': 'x'}, 'result': {'matches': [
                   {'file': 'tank/a.py', 'line': 1, 'text': 'x'}, {'file': 'tank/b.py', 'line': 2, 'text': 'x'}]}})),
               command.CodeResult(name='git', output=json.dumps({'arguments': {'action': 'diff'}, 'result': {
                   'output': '--- a/tank/b.py\n+++ b/tank/b.py\n@@ -1 +1 @@\n-a\n+b\n'}})),
               command.CodeResult(name='run_command', output='{"result":{"ran":true,"code":0}}')]
    kept, outside = code_preflight.scope(results, {'tank/a.py'})
    assert outside == [{'name': 'read_file', 'paths': ['tank/secret.py']}, {'name': 'git', 'paths': ['tank/b.py']}]
    search = json.loads(kept[1].output)['result']
    assert [m['file'] for m in search['matches']] == ['tank/a.py'] and search['outside_plan_dropped'] == 1
    assert [r.name for r in kept] == ['read_file', 'search', 'run_command']
    content = json.dumps({'answer': 'Reading', 'requests': [
        {'name': 'read_file', 'arguments': {'path': 'tank/a.py'}}, {'name': 'read_file', 'arguments': {'path': 'tank/z.py'}},
        {'name': 'propose_edit', 'arguments': {'diff': '--- a/tank/a.py\n+++ b/tank/z.py\n'}},
        {'name': 'run_command', 'arguments': {'command': 'pytest'}}]})
    shaped = json.loads(code_preflight.shape(content, {'tank/a.py'}, 1, 1))
    assert [r['name'] for r in shaped['requests']] == ['read_file', 'run_command']
    assert 'tank/z.py' in shaped['answer'] and "outside this task's plan" in shaped['answer']
    unchanged = json.dumps({'answer': 'ok', 'requests': [{'name': 'read_file', 'arguments': {'path': 'tank/a.py'}}]})
    assert code_preflight.shape(unchanged, {'tank/a.py'}, 1, 1) == unchanged


# HTTP-boundary proofs with the real Command router, Postgres and fake model calls.

@pytest.mark.asyncio
@pytest.mark.parametrize('setting', [None, '', 'false', 'TRUE', ' true'])
async def test_unset_setting_keeps_mains_exact_http_behaviour(api, monkeypatch, setting):
    if setting is None:
        monkeypatch.delenv(code_preflight.SETTING, raising=False)
    else:
        monkeypatch.setenv(code_preflight.SETTING, setting)
    monkeypatch.setenv(code_preflight.BUDGET_TOKENS, '1')
    client, pool = api
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    thread = await new_thread(client)
    prompt = str(uuid.uuid4())
    for number in range(3):
        reply = await client.post(f'/v1/command/threads/{thread}/code-turn', json={
            'text': 'Fix it', 'prompt_id': prompt, 'continuation': number > 0, 'tool_results': [read('anything/else.py')]})
        assert reply.status_code == 200 and 'preflight' not in reply.json()
        assert reply.json()['turn']['cost_usd'] == 0.01
    assert len(seen) == 3 and seen[0]['run'] is None
    assert seen[0]['messages'][1] == {'role': 'user', 'content': 'Fix it'}
    state = await thread_state(pool, thread)
    assert 'code_preflight' not in state and 'code_preflight_question' not in state
    assert all('code_preflight' not in step for step in state['steps'].values())


@pytest.mark.asyncio
async def test_vague_prompt_gets_one_free_question_then_plans(api, monkeypatch):
    client, pool = api
    await routed(pool)
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    thread = await new_thread(client)
    asked = await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': 'Fix the failing test'})
    result = asked.json()
    assert asked.status_code == 200 and result['preflight']['status'] == 'question'
    assert result['answer'] == code_preflight.QUESTION and result['requests'] == [] and not seen
    assert result['turn']['cost_usd'] == result['receipt']['totals']['cost_usd'] == 0
    ledger = await pool.fetch("SELECT model,cost_usd,rung FROM tank.ledger WHERE tenant_id=$1", existing.TENANT)
    assert [(r['model'], float(r['cost_usd']), r['rung']) for r in ledger] == [('code', 0.0, 3)]
    # The reply is never questioned again: one clarifying question per ask.
    reply = await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': 'tests/test_x.py'})
    assert reply.status_code == 200 and 'preflight' not in reply.json() and len(seen) == 1
    sent = seen[0]['messages'][1]['content']
    assert sent.startswith('Fix the failing test\n\nClarification: tests/test_x.py') and '["tests/test_x.py"]' in sent


@pytest.mark.asyncio
async def test_split_tasks_run_in_order_with_own_run_quote_and_receipt(api, monkeypatch):
    client, pool = api
    await routed(pool)
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    thread = await new_thread(client)
    prompt = str(uuid.uuid4())
    text = '1. Add a retry flag to tank/client.py\n2. Document the flag in docs/client.md'
    first = await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': text, 'prompt_id': prompt})
    assert first.status_code == 200, first.text
    assert 'Task 1 of 2 is done' in first.json()['answer']
    assert 'tank/client.py' in seen[0]['messages'][1]['content'] and 'docs/client.md' not in seen[0]['messages'][1]['content']
    body = {'text': text, 'prompt_id': prompt, 'continuation': True}
    second = await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)
    assert second.status_code == 200 and 'Task' not in second.json()['answer']
    assert seen[1]['messages'][1]['content'].startswith('Document the flag in docs/client.md')
    assert seen[0]['run'].run_id != seen[1]['run'].run_id and seen[0]['run'].tenant_id == existing.TENANT
    done = await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)
    result = done.json()
    assert result['preflight']['status'] == 'complete' and len(seen) == 2 and result['turn']['cost_usd'] == 0
    receipts = result['preflight']['receipts']
    assert [r['calls'] for r in receipts] == [1, 1] and [r['actual_usd'] for r in receipts] == [0.01, 0.01]
    assert all(r['quoted_usd'] > 0 for r in receipts)
    state = await thread_state(pool, thread)
    quoted = state['steps'][str(seen[0]['task'])]['code_preflight']
    assert quoted['status'] == 'quoted' and quoted['authorization'] == 'automatic'
    assert quoted['quote']['rung'] == 'frontier' and quoted['quote']['files'] == ['tank/client.py']
    assert quoted['quote']['tokens_out_limit'] == 1000 and quoted['quote']['price_status'] == 'priced'
    assert quoted['quote']['cost_usd_estimate'] == pytest.approx(quoted['quote']['tokens_in_estimate'] * 1e-6 + 1000 * 2e-6)
    assert MODEL not in json.dumps(quoted)
    actual = [r for r in state['receipts'] if r['step_id'] == str(seen[0]['task'])]
    assert len(actual) == 1 and actual[0]['cost_usd'] == 0.01
    approvals = await pool.fetch('SELECT run_id,state,authorization_mode FROM tank.paid_step_approvals WHERE tenant_id=$1', existing.TENANT)
    assert sorted(r['run_id'] for r in approvals) == sorted([seen[0]['run'].run_id, seen[1]['run'].run_id])
    assert {r['authorization_mode'] for r in approvals} == {'automatic'}
    again = await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)
    assert again.json()['preflight']['status'] == 'complete' and len(seen) == 2


@pytest.mark.asyncio
async def test_plan_first_lists_files_and_drops_the_listing(api, monkeypatch):
    client, pool = api
    await routed(pool)
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    thread = await new_thread(client)
    prompt = str(uuid.uuid4())
    text = 'Add a retry with backoff to the http client helper'
    listing = await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': text, 'prompt_id': prompt})
    assert listing.json()['preflight']['status'] == 'listing' and not seen
    assert listing.json()['requests'] == [{'name': 'list_files', 'arguments': {}}]
    files = {'name': 'list_files', 'output': json.dumps({'arguments': {}, 'result': {
        'files': ['tank/http_client.py', 'tank/helpers.py', 'README.md'], 'truncated': False}})}
    planned = await client.post(f'/v1/command/threads/{thread}/code-turn', json={
        'text': text, 'prompt_id': prompt, 'continuation': True, 'tool_results': [files]})
    assert planned.status_code == 200 and len(seen) == 1
    sent = [m['content'] for m in seen[0]['messages']]
    assert '["tank/http_client.py"]' in sent[1] and not any('README.md' in item for item in sent)
    state = await thread_state(pool, thread)
    assert state['code_preflight']['tasks'][0]['plan']['files'] == ['tank/http_client.py']
    second = {'text': 'Add a retry with backoff to the gateway proxy layer', 'prompt_id': str(uuid.uuid4())}
    other = await client.post(f'/v1/command/threads/{thread}/code-turn', json=second)
    assert other.json()['preflight']['status'] == 'listing'
    unmatched = await client.post(f'/v1/command/threads/{thread}/code-turn', json={
        **second, 'continuation': True, 'tool_results': [files]})
    assert unmatched.json()['preflight']['status'] == 'needs_files' and len(seen) == 1


@pytest.mark.asyncio
async def test_scope_lock_refuses_and_reports_outside_files(api, monkeypatch):
    client, pool = api
    await routed(pool)
    seen = []
    answer = json.dumps({'answer': 'Reading', 'requests': [
        {'name': 'read_file', 'arguments': {'path': 'tank/a.py'}}, {'name': 'read_file', 'arguments': {'path': 'tank/other.py'}}]})
    monkeypatch.setattr(command, 'route_code', fake(pool, [answer], seen))
    thread = await new_thread(client)
    prompt = str(uuid.uuid4())
    body = {'text': 'Fix the off-by-one in tank/a.py', 'prompt_id': prompt}
    first = (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).json()
    assert first['requests'] == [{'name': 'read_file', 'arguments': {'path': 'tank/a.py'}}]
    assert 'read_file tank/other.py' in first['answer']
    body.update(continuation=True, tool_results=[read('tank/a.py'), read('tank/other.py', 'PRIVATE_TEXT')])
    refused = (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).json()
    assert refused['preflight']['status'] == 'outside_plan' and len(seen) == 1
    assert refused['preflight']['refused'] == [{'name': 'read_file', 'paths': ['tank/other.py']}]
    assert refused['turn']['cost_usd'] == 0
    body['tool_results'] = [read('tank/a.py')]
    latched = (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).json()
    assert latched['preflight']['status'] == 'outside_plan' and len(seen) == 1
    assert 'PRIVATE_TEXT' not in json.dumps(await thread_state(pool, thread))


@pytest.mark.asyncio
async def test_ask_waits_for_approval_then_proceeds_and_denial_stops(api, monkeypatch):
    client, pool = api
    await routed(pool, mode='ask')
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    thread = await new_thread(client)
    prompt = str(uuid.uuid4())
    body = {'text': 'Fix the off-by-one in tank/a.py', 'prompt_id': prompt}
    waiting = (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).json()
    assert waiting['preflight']['status'] == 'awaiting_approval' and not seen
    assert waiting['preflight']['quote']['files'] == ['tank/a.py'] and waiting['turn']['cost_usd'] == 0
    approval = uuid.UUID(waiting['preflight']['approval_id'])
    body['continuation'] = True
    still = (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).json()
    assert still['preflight']['approval_id'] == str(approval) and not seen
    await paid_steps.decide(existing.TENANT, approval, user='founder', approve=True, reason='Quote accepted')
    went = await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)
    assert went.status_code == 200 and 'preflight' not in went.json() and len(seen) == 1
    assert (await thread_state(pool, thread))['steps'][str(seen[0]['task'])]['code_preflight']['authorization'] == 'approved'
    denied_prompt = {'text': 'Fix the off-by-one in tank/b.py', 'prompt_id': str(uuid.uuid4())}
    pending = (await client.post(f'/v1/command/threads/{thread}/code-turn', json=denied_prompt)).json()
    await paid_steps.decide(existing.TENANT, uuid.UUID(pending['preflight']['approval_id']), user='founder', approve=False, reason='No')
    stopped = (await client.post(f'/v1/command/threads/{thread}/code-turn', json={**denied_prompt, 'continuation': True})).json()
    assert stopped['preflight']['status'] == 'declined' and len(seen) == 1


@pytest.mark.asyncio
async def test_token_budget_stops_before_the_next_paid_call(api, monkeypatch):
    client, pool = api
    await routed(pool, max_out=100)
    seen = []
    more = json.dumps({'answer': 'Reading', 'requests': [{'name': 'read_file', 'arguments': {'path': 'tank/a.py'}}]})
    monkeypatch.setattr(command, 'route_code', fake(pool, [more, more], seen, tokens=(3000, 100)))
    monkeypatch.setenv(code_preflight.BUDGET_TOKENS, '7000')
    thread = await new_thread(client)
    prompt = str(uuid.uuid4())
    body = {'text': 'Fix the off-by-one in tank/a.py', 'prompt_id': prompt}
    assert 'preflight' not in (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).json()
    body.update(continuation=True, tool_results=[read('tank/a.py')])
    stopped = (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).json()
    assert stopped['preflight']['status'] == 'budget' and len(seen) == 1 and stopped['turn']['cost_usd'] == 0
    progress = stopped['preflight']['progress']
    assert progress['calls'] == 1 and progress['tokens_in'] == 3000 and progress['tokens_out'] == 100
    assert progress['actual_usd'] == 0.01 and progress['task'] == 1 and progress['tasks_done'] == 0
    assert stopped['preflight']['cap'] == {'tokens': 7000}
    latched = (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).json()
    assert latched['preflight']['status'] == 'budget' and len(seen) == 1


@pytest.mark.asyncio
async def test_dollar_budget_and_invalid_setting(api, monkeypatch):
    client, pool = api
    await routed(pool)
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    thread = await new_thread(client)
    monkeypatch.setenv(code_preflight.BUDGET_USD, 'lots')
    invalid = (await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': 'Fix the bug in tank/a.py now'})).json()
    assert invalid['preflight']['status'] == 'setting' and code_preflight.BUDGET_USD in invalid['answer'] and not seen
    monkeypatch.setenv(code_preflight.BUDGET_USD, '0.001')
    capped = (await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': 'Fix the bug in tank/a.py now'})).json()
    assert capped['preflight']['status'] == 'budget' and capped['preflight']['cap'] == {'usd': 0.001} and not seen
    assert capped['preflight']['quote']['cost_usd_estimate'] > 0.001


@pytest.mark.asyncio
async def test_tenant_and_user_isolation(api, monkeypatch):
    client, pool = api
    await routed(pool)
    await routed(pool, existing.OTHER)
    seen = []
    monkeypatch.setattr(command, 'route_code', fake(pool, [], seen))
    monkeypatch.setenv(code_preflight.BUDGET_TOKENS, '20000')
    thread = await new_thread(client)
    prompt = str(uuid.uuid4())
    body = {'text': 'Fix the bug in tank/a.py now', 'prompt_id': prompt}
    assert (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).status_code == 200
    task = seen[0]['task']
    # Another tenant's spend recorded against the same task id never counts here.
    await pool.execute("INSERT INTO tank.ledger(tenant_id,agent,task_type,model,cost_usd,tokens_in,tokens_out,task_id) "
                       "VALUES($1,'orchestrator','command.code','fixture',5,900000,900000,$2)", existing.OTHER, task)
    async with pool.acquire() as conn:
        used = await code_preflight.spent(conn, existing.TENANT, [str(task)])
    assert used['calls'] == 1 and used['tokens_in'] == 100
    for headers in [{'x-tervory-user': 'other-user'}, {'x-tervory-tenant': str(existing.OTHER)}]:
        foreign = await client.post(f'/v1/command/threads/{thread}/code-turn',
                                    json={**body, 'continuation': True}, headers=headers)
        assert foreign.status_code == 404
    other_thread = (await client.post('/v1/command/threads', json={}, headers={'x-tervory-tenant': str(existing.OTHER)})).json()['thread_id']
    reply = await client.post(f'/v1/command/threads/{other_thread}/code-turn', json=body, headers={'x-tervory-tenant': str(existing.OTHER)})
    assert reply.status_code == 200 and len(seen) == 2
    assert seen[1]['run'].tenant_id == existing.OTHER and seen[1]['run'].run_id != seen[0]['run'].run_id
    rows = await pool.fetch('SELECT tenant_id,run_id FROM tank.paid_step_approvals ORDER BY tenant_id')
    assert {(r['tenant_id'], r['run_id']) for r in rows} == {(existing.TENANT, seen[0]['run'].run_id),
                                                             (existing.OTHER, seen[1]['run'].run_id)}


@pytest.mark.asyncio
async def test_replayed_request_id_is_refused_without_changing_the_task(api, monkeypatch):
    client, pool = api
    await routed(pool)
    seen = []
    more = json.dumps({'answer': 'Reading', 'requests': [{'name': 'read_file', 'arguments': {'path': 'tank/a.py'}}]})
    monkeypatch.setattr(command, 'route_code', fake(pool, [more, more], seen))
    thread = await new_thread(client)
    prompt = str(uuid.uuid4())
    await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': 'Fix the bug in tank/a.py now', 'prompt_id': prompt})
    body = {'text': 'Fix the bug in tank/a.py now', 'prompt_id': prompt, 'continuation': True,
            'request_id': str(uuid.uuid4()), 'tool_results': [read('tank/a.py')]}
    assert (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).status_code == 200
    before = (await thread_state(pool, thread))['code_preflight']
    assert (await client.post(f'/v1/command/threads/{thread}/code-turn', json=body)).status_code == 409
    assert (await thread_state(pool, thread))['code_preflight'] == before
    assert len(before['tasks'][0]['turns']) == 2 and len(seen) == 2
