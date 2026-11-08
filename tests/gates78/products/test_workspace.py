"""Workspace Gate 7/8 acceptance against the pinned, unchanged Tank runtime.

No FakeMemory, patched Hermes, auth override, receipt stub or replacement brain.
Expected-behaviour assertions intentionally fail when the integrated runtime is
missing a dependency. Head, not this test module, decides acceptance.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest

from chassis.user_assertion import HEADER, SignedUser, sign_assertion
from hermes.service import create_app
from hermes.store import InMemoryStore
from gate78_contract import REQUIREMENTS
from workspace_fixture import USER_A, USER_B
import workspace_fixture

workspace_entry = workspace_fixture.workspace_entry

SOURCE_SHA = 'c0119aac147f3a3c2c9036b692ca858953282fa6'
ROOT = Path(__file__).resolve().parents[3]
CHAT = {'messages': [{'role': 'user', 'content': 'placeholder summarize the project'}], 'task_type': 'tier0.answer'}


async def chat(entry, **kwargs):
    response = await entry.request('chat', CHAT, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def ids(body):
    return {row['id'] for row in body.get('memories', [])}


@pytest.mark.asyncio
async def test_owner_crud_and_controls(workspace_entry):
    e = workspace_entry
    row = await e.seed()
    listed = await e.request('memory.view', {'task_key': 'placeholder-task'})
    assert listed.status_code == 200, listed.text
    assert row['id'] in ids(listed.json())
    edited = await e.request('memory.edit', {'memory_id': row['id'], 'text': 'placeholder corrected answer'})
    assert edited.status_code == 200, edited.text
    got = await e.request('memory.view', {'memory_id': row['id'], 'task_key': 'placeholder-task'})
    assert got.status_code == 200 and 'placeholder corrected answer' in got.text
    forgotten = await e.request('memory.forget', {'memory_id': row['id']})
    assert forgotten.status_code == 200, forgotten.text
    assert row['id'] not in ids((await e.request('memory.view', {'task_key': 'placeholder-task'})).json())
    assert not await e.stack.client(USER_A).recall(e.stack.tenant, 'placeholder corrected answer')


@pytest.mark.asyncio
@pytest.mark.parametrize('foreign', ['user', 'tenant'])
async def test_foreign_reads_mutations_and_receipt_leaks(workspace_entry, foreign, caplog):
    e = workspace_entry
    row = await e.seed(text='placeholder private owner content')
    scope = {'user': USER_B} if foreign == 'user' else {'tenant': e.stack.other_tenant}
    before = await e.snapshot()
    listed = await e.request('memory.view', {'task_key': 'placeholder-task'}, **scope)
    assert listed.status_code == 200, listed.text
    assert row['id'] not in ids(listed.json())
    for operation, body in [('memory.view', {'memory_id': row['id']}),
                            ('memory.edit', {'memory_id': row['id'], 'text': 'placeholder attacker'}),
                            ('memory.forget', {'memory_id': row['id']})]:
        response = await e.request(operation, body, **scope)
        assert response.status_code in {403, 404}, response.text
        assert 'placeholder private owner content' not in response.text
        assert await e.snapshot() == before
    assert not e.provider_calls
    assert 'placeholder private owner content' not in caplog.text


@pytest.mark.asyncio
async def test_declared_tenant_wide_and_personal_owner(workspace_entry):
    e = workspace_entry
    shared = await e.memory.remember(e.stack.tenant, 'placeholder shared project', 'workspace.project',
        'urn:placeholder:shared', tenant_wide=True)
    personal = await e.seed(kind='workspace.project', text='placeholder personal project')
    for user in (USER_A, USER_B):
        response = await e.request('memory.view', {'task_key': 'placeholder-task'}, user=user)
        assert response.status_code == 200, response.text
        assert shared['id'] in ids(response.json())
        assert (personal['id'] in ids(response.json())) == (user == USER_A)
    assert shared['id'] not in ids((await e.request('memory.view', {}, tenant=e.stack.other_tenant)).json())


@pytest.mark.asyncio
async def test_real_signin_rejects_header_body_and_missing_identity(workspace_entry):
    e = workspace_entry
    await e.seed()
    before = await e.snapshot()
    for extra in ({'X-Tervory-User': USER_B}, {'X-Tervory-Tenant': e.stack.other_tenant},
                  {'X-Trigger-Signin-Token': 'placeholder-invalid-token'}):
        response = await e.request('memory.control', {'control': 'off'}, extra=extra)
        assert response.status_code in {401, 403}, response.text
        assert await e.snapshot() == before
    denied = await e.client.post('/v1/command/workspace/memory.control',
        headers={'X-Tank-Key': 'placeholder-workspace-service-key'}, json={'control': 'off', 'user_id': USER_A})
    assert denied.status_code in {401, 422}
    denied = await e.request('memory.control', {'control': 'off', 'user_id': USER_B})
    assert denied.status_code in {403, 422}
    assert await e.snapshot() == before and not e.provider_calls
    # Positive signed-in ingress is essential; deny-all cannot pass this case.
    assert (await e.request('memory.view', {})).status_code == 200
    assert e.provider.calls


@pytest.mark.asyncio
async def test_missing_owner_and_body_metadata_cannot_widen(workspace_entry):
    e = workspace_entry
    before = await e.snapshot()
    payload = {'tenant_id': e.stack.tenant, 'text': 'placeholder unowned', 'kind': 'workspace.task',
               'source': 'urn:placeholder:unowned'}
    assert (await e.stack.http.post('/memories', headers={'X-Tank-Key': e.stack.key}, json=payload)).status_code == 422
    payload.update(user_id=USER_A, meta={'user_id': USER_B})
    raw = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
    token = sign_assertion('hermes', SignedUser(e.stack.tenant, USER_A, 'member'), 'POST', '/memories', raw, key=e.stack.key)
    response = await e.stack.http.post('/memories', headers={'X-Tank-Key': e.stack.key, HEADER: token}, content=raw)
    assert response.status_code in {401, 403, 422}
    assert await e.snapshot() == before


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid', ['key', 'audience', 'tenant', 'method', 'target', 'body', 'missing', 'expired', 'future'])
async def test_assertion_binding_is_real_and_fail_closed(workspace_entry, invalid):
    e = workspace_entry
    row = await e.seed()
    await e.request('memory.view', {})
    request = next(r for r in e.requests if r.method == 'POST' and r.url.path == '/recall')
    target = request.url.raw_path.decode('ascii')
    body = request.content
    settings = dict(product='hermes', user=SignedUser(e.stack.tenant, USER_A, 'member'),
                    method='POST', target=target, body=body, key=e.stack.key)
    if invalid == 'key': settings['key'] = 'placeholder-wrong-key'
    if invalid == 'audience': settings['product'] = 'trigger'
    if invalid == 'tenant': settings['user'] = SignedUser(e.stack.other_tenant, USER_A, 'member')
    if invalid == 'method': settings['method'] = 'GET'
    if invalid == 'target': settings['target'] = '/records'
    if invalid == 'expired': settings['now'] = int(time.time()) - 120
    if invalid == 'future': settings['now'] = int(time.time()) + 120
    token = sign_assertion(**settings)
    if invalid == 'body': body += b' '
    headers = {'X-Tank-Key': e.stack.key, 'Content-Type': 'application/json', HEADER: token}
    if invalid == 'missing': headers.pop(HEADER)
    response = await e.stack.http.post('/recall', headers=headers, content=body)
    assert response.status_code in {401, 403}, response.text
    assert row['id'] not in response.text
    assert (await e.request('memory.view', {})).status_code == 200


@pytest.mark.asyncio
async def test_nonce_replay_concurrent_restart_and_forget(workspace_entry):
    e = workspace_entry
    row = await e.seed()
    request = next(r for r in e.requests if r.method == 'POST' and r.url.path == '/memories')
    async def replay(http):
        return await http.request(request.method, str(request.url), headers=request.headers, content=request.content)
    replies = await asyncio.gather(replay(e.stack.http), replay(e.stack.http))
    assert all(r.status_code in {401, 403} for r in replies)
    assert (await e.request('memory.forget', {'memory_id': row['id']})).status_code == 200
    restarted = create_app(InMemoryStore(), e.stack.records.encoder, records=e.stack.records)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url='http://hermes') as http:
        assert (await replay(http)).status_code in {401, 403}
    assert not await e.stack.client(USER_A).records(e.stack.tenant)


@pytest.mark.asyncio
async def test_sql_candidates_are_owned_before_vector_limit(workspace_entry, monkeypatch):
    e = workspace_entry
    for index in range(3):
        await e.seed(user=USER_B, text=f'placeholder foreign {index}')
    row = await e.seed()
    searches = []
    original = e.stack.records.index.search
    def observe(*args, **kwargs):
        searches.append((args, kwargs))
        return original(*args, **kwargs)
    monkeypatch.setattr(e.stack.records.index, 'search', observe)
    response = await e.request('memory.view', {'task_key': 'placeholder-task'})
    assert response.status_code == 200, response.text
    assert row['id'] in ids(response.json())
    # Real client recall hits the same central SQL/vector path as the handler.
    assert (await e.stack.client(USER_A).recall(e.stack.tenant, 'placeholder', limit=1))[0]['id'] == row['id']
    searches.clear()
    assert not await e.stack.client(USER_A).recall(e.stack.other_tenant, 'placeholder', limit=1)
    assert not searches


@pytest.mark.asyncio
async def test_restricted_database_role_uses_product_entry(workspace_entry):
    e = workspace_entry
    row = await e.seed()
    role = 'placeholder_ws_' + uuid4().hex[:12]
    schema = e.stack.records.schema(e.stack.agent)
    await e.pool.execute(f'CREATE ROLE {role} NOSUPERUSER NOCREATEDB NOCREATEROLE')
    await e.pool.execute(f'GRANT USAGE,CREATE ON SCHEMA {schema} TO {role}')
    await e.pool.execute(f'GRANT USAGE,CREATE ON SCHEMA {e.engine_schema} TO {role}')
    await e.pool.execute(f'GRANT SELECT,INSERT,DELETE ON {e.engine_schema}.user_assertion_nonces TO {role}')
    await e.pool.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {schema} TO {role}')
    restricted = await asyncpg.create_pool(os.environ['MEMORY_TEST_DATABASE_URL'], min_size=1, max_size=1,
                                         server_settings={'role': role})
    original = e.stack.records.pool
    e.stack.records.pool = restricted
    try:
        assert await restricted.fetchval('SELECT current_user') == role
        assert not await restricted.fetchval('SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname=current_user')
        response = await e.request('memory.view', {'memory_id': row['id']})
        assert response.status_code == 200, response.text
        assert row['id'] in ids(response.json())
        denied = await e.request('memory.view', {'memory_id': row['id']}, user=USER_B)
        assert denied.status_code == 403 and row['id'] not in denied.text
    finally:
        e.stack.records.pool = original
        await restricted.close()
        await e.pool.execute(f'DROP OWNED BY {role}')
        await e.pool.execute(f'DROP ROLE {role}')


@pytest.mark.asyncio
async def test_actual_client_key_route_and_no_private_data_logs(workspace_entry, caplog):
    e = workspace_entry
    row = await e.seed()
    response = await e.request('memory.view', {'memory_id': row['id']})
    assert response.status_code == 200 and row['id'] in ids(response.json())
    assert all(r.headers['X-Tank-Key'] == e.stack.key for r in e.requests)
    assert all('/v1/memory' not in str(r.url) for r in e.requests)
    assert all(HEADER in r.headers for r in e.requests)
    assert e.stack.key not in caplog.text
    assert 'placeholder original answer' not in caplog.text


@pytest.mark.asyncio
async def test_default_off_has_no_memory_or_added_work(workspace_entry, monkeypatch):
    e = workspace_entry
    monkeypatch.delenv('WORKSPACE_MEMORY_ENABLED')
    before = await e.snapshot()
    e.stack.calls.clear()
    first = await chat(e)
    assert first.get('memory_bracket') in (None, {})
    # The fixed Tank core already has its own /engine corridor. An unset
    # Workspace switch adds no product recall, control lookup or memory writes.
    assert e.stack.calls and all(path.startswith('/engine/') for _, path in e.stack.calls)
    assert all(status == 200 for _, path, status in e.statuses if path.startswith('/engine/'))
    assert await e.snapshot() == before
    assert len(e.provider_calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('entry', ['chat', 'task.create'])
async def test_paid_entry_runs_real_tank_lifecycle(workspace_entry, entry):
    e = workspace_entry
    body = CHAT if entry == 'chat' else {'title': 'placeholder project', 'request': 'placeholder summarize the project'}
    if entry == 'task.create':
        refused = await e.request(entry, body)
        assert refused.status_code == 409 and not e.provider_calls
        response = await e.confirmed_task(body)
        data = response.json()
        assert data['status'] == 'confirmed', e.statuses
        board = await e.request('tasks', {}, method='GET')
        assert board.status_code == 200, board.text
        created = [row for row in board.json()['tasks'] if row['title'] == body['title'] and row['created_by'] == USER_A]
        assert len(created) == 1
        task_id = created[0]['id']
        async with asyncio.timeout(10):
            while True:
                task = await e.main.get_task(UUID(task_id), UUID(e.stack.tenant))
                if task['status'] in {'done', 'failed'}:
                    break
                await asyncio.sleep(.01)
        assert task['status'] == 'done', task.get('error')
        assert task['ledger_id']
        response = await e.request('task.receipt', {'task_id': task_id}, method='GET')
        assert response.status_code == 200, response.text
        assert response.json()['rows'][0]['tokens_in'] == 10 and response.json()['rows'][0]['tokens_out'] == 3
    else:
        response = await e.request(entry, body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(e.provider_calls) == 1
    assert result['memory_bracket']['paid_calls'] == 1
    paid_at = next(index for index, event in enumerate(e.timeline) if event[0] == 'PAID')
    assert e.timeline.index(('POST', '/recall')) < paid_at < e.timeline.index(('POST', '/memories'))
    assert result['ledger_id']
    rows = await e.stack.client(USER_A).records(e.stack.tenant)
    assert any(r['kind'] in {'workspace.receipt', 'workspace.task'} for r in rows)
    assert all((r['meta'] or {}).get('user_id') == USER_A for r in rows)


@pytest.mark.asyncio
async def test_first_repeat_changed_input_receipts_reconcile(workspace_entry):
    e = workspace_entry
    first = await chat(e)
    repeat = await chat(e)
    assert len(e.provider_calls) == 1
    assert repeat['memory_bracket']['paid_calls'] == 0
    for name in ('cost_usd', 'tokens_in', 'tokens_out'):
        assert repeat['memory_bracket'][name] == 0
    assert repeat['receipt']['baseline_cost_usd'] >= first['memory_bracket']['cost_usd'] > 0
    assert first['memory_bracket']['tokens_in'] == 10 and first['memory_bracket']['tokens_out'] == 3
    changed = await e.request('chat', {**CHAT, 'messages': [{'role': 'user', 'content': 'placeholder changed input'}]})
    assert changed.status_code == 200 and len(e.provider_calls) == 2
    row = await e.pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', UUID(first['ledger_id']))
    assert float(row['cost_usd']) == first['receipt']['cost_usd']
    assert first['memory_bracket']['cost_usd'] > 0


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['user', 'tenant', 'ineligible'])
async def test_identity_and_ineligible_task_are_cache_misses(workspace_entry, change):
    e = workspace_entry
    await chat(e)
    if change == 'ineligible':
        body = {**CHAT, 'task_type': 'tier0.draft'}
        assert (await e.request('chat', body)).status_code == 200
    else:
        assert (await e.request('chat', CHAT, **({'user': USER_B} if change == 'user' else {'tenant': e.stack.other_tenant}))).status_code == 200
    assert len(e.provider_calls) == 2


@pytest.mark.asyncio
async def test_correction_forget_and_off_invalidate_reusable_answers(workspace_entry):
    e = workspace_entry
    first = await chat(e)
    rows = await e.stack.client(USER_A).records(e.stack.tenant)
    receipt = next(r for r in rows if r['kind'] == 'workspace.receipt')
    before = len(e.provider_calls)
    edited = await e.request('memory.edit', {'memory_id': receipt['id'], 'text': 'placeholder corrected project answer'})
    assert edited.status_code == 200
    corrected = await chat(e)
    assert corrected['content'] == 'placeholder corrected project answer'
    assert len(e.provider_calls) == before
    assert corrected != first
    other = await chat(e, user=USER_B)
    assert other['content'] == 'placeholder completed answer'
    assert 'placeholder corrected project answer' not in json.dumps(other)
    assert (await e.request('memory.forget', {'memory_id': receipt['id']})).status_code == 200
    forgotten = await chat(e)
    assert forgotten['content'] != corrected['content']
    assert receipt['id'] not in json.dumps(forgotten)
    assert (await e.request('memory.control', {'control': 'off'})).status_code == 200
    await chat(e)
    await chat(e)
    assert len(e.provider_calls) >= before + 2
    assert (await e.request('memory.view', {}, user=USER_B)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize('method', ['POST', 'GET'])
async def test_memory_network_outage_is_truthful_and_no_double_payment(workspace_entry, method):
    e = workspace_entry
    e.fault.update(method=method, path='/records' if method == 'GET' else '/recall')
    if method == 'GET':
        control = await e.request('memory.view')
        assert control.status_code == 503 and not e.provider_calls
        assert e.fault['hits'] > 0
    result = await chat(e)
    assert e.fault['hits'] > 0
    assert result['memory_bracket']['memory_unavailable'] is True
    assert result['memory_bracket']['answered_from_memory'] is False
    assert len(e.provider_calls) == 1
    assert not await e.snapshot()


@pytest.mark.asyncio
async def test_post_payment_remember_failure_returns_existing_receipt_once(workspace_entry):
    e = workspace_entry
    # Fault only writes, at their real HTTP boundary, after successful recall.
    original = e.stack.http._transport
    class WriteFault(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if request.method == 'POST' and request.url.path == '/memories':
                return httpx.Response(503, json={'detail': 'placeholder write unavailable'})
            return await original.handle_async_request(request)
    e.stack.http._transport = WriteFault()
    result = await chat(e)
    assert len(e.provider_calls) == 1 and result['ledger_id']
    assert result['memory_bracket']['memory_unavailable'] is True
    assert result['memory_bracket']['paid_calls'] == 1
    assert result['memory_bracket']['tokens_in'] == 10
    assert result['memory_bracket']['tokens_out'] == 3
    assert not await e.snapshot()


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [401, 403])
async def test_auth_failure_is_not_a_memory_outage(workspace_entry, status):
    e = workspace_entry
    await e.seed()
    before = await e.snapshot()
    e.fault.update(method='POST', status=status)
    response = await e.request('chat', CHAT)
    assert response.status_code in {401, 403}, response.text
    assert not e.provider_calls and await e.snapshot() == before
    assert 'memory unavailable' not in response.text.lower()


@pytest.mark.asyncio
async def test_memory_off_is_per_user_and_does_not_recall_or_remember(workspace_entry):
    e = workspace_entry
    assert (await e.request('memory.control', {'control': 'off'})).status_code == 200
    before = await e.snapshot()
    e.stack.calls.clear()
    await chat(e)
    # Reading the signed-in user's durable control preference is necessary to
    # discover OFF. It must use SQL listing, never semantic recall or a write.
    assert e.stack.calls and all(method == 'GET' and path == '/records' for method, path in e.stack.calls)
    assert await e.snapshot() == before
    assert (await e.request('memory.view', {}, user=USER_B)).status_code == 200


@pytest.mark.asyncio
async def test_retry_and_concurrent_paid_requests_keep_accounting(workspace_entry):
    e = workspace_entry
    replies = await asyncio.gather(e.request('chat', CHAT), e.request('chat', CHAT))
    assert all(r.status_code == 200 for r in replies)
    for response in replies:
        ledger = await e.pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', UUID(response.json()['ledger_id']))
        assert str(ledger['tenant_id']) == e.stack.tenant
    before = len(e.provider_calls)
    await chat(e)
    assert len(e.provider_calls) == before


@pytest.mark.asyncio
async def test_legacy_requirements_and_product_browser_entrypoints_are_retained(workspace_entry):
    import socket
    import subprocess
    import uvicorn
    e = workspace_entry
    manifest = json.loads((Path(__file__).with_name('workspace.json')).read_text())
    assert set(manifest['cases']) == set(REQUIREMENTS)
    assert manifest['source_sha'] == SOURCE_SHA
    assert len(manifest['legacy_tests']) >= 30
    assert os.environ.get('WORKSPACE_PRODUCT_SOURCE'), 'Set WORKSPACE_PRODUCT_SOURCE to the exact reviewed product checkout'
    source = Path(os.environ['WORKSPACE_PRODUCT_SOURCE'])
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == SOURCE_SHA
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=source, text=True).strip()
    assert (source / 'workspace/app/tasks/page.tsx').is_file()
    from fastapi import Depends
    import command

    @e.app.get('/fixture/workspace/state')
    async def state(actor=Depends(command.identity)):
        assert actor.user_id == USER_A and str(actor.tenant_id) == e.stack.tenant
        paid = await e.pool.fetch('SELECT tokens_in,tokens_out,cost_usd FROM tank.ledger WHERE tenant_id=$1 AND tokens_in>0', UUID(e.stack.tenant))
        return {'provider_calls': len(e.provider_calls),
            'done_tasks': await e.pool.fetchval("SELECT count(*) FROM tank.tasks WHERE tenant_id=$1 AND created_by=$2 AND status='done'", UUID(e.stack.tenant), USER_A),
            'paid_receipts': [dict(row) for row in paid],
            'memories': await e.snapshot()}

    @e.app.post('/fixture/workspace/fault')
    async def fault(body: dict, actor=Depends(command.identity)):
        assert actor.user_id == USER_A and str(actor.tenant_id) == e.stack.tenant
        assert body['method'] in {None, 'GET', 'POST'} and body['status'] == 503
        e.fault.update(body)
        return {'ok': True}

    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(e.app, log_level='error', access_log=False, lifespan='off', timeout_graceful_shutdown=3))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    process = None
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if serving.done():
                    await serving
                await asyncio.sleep(.01)
        env = {**os.environ, 'WORKSPACE_PRODUCT_SOURCE': str(source),
            'WORKSPACE_BROWSER_BACKEND': f'http://127.0.0.1:{sock.getsockname()[1]}',
            'WORKSPACE_BROWSER_HEADERS': json.dumps(e.headers()),
            'WORKSPACE_BROWSER_OUTPUT': str(ROOT / '.tmp/workspace-browser'),
            'WORKSPACE_BROWSER_TENANT': e.stack.tenant, 'WORKSPACE_BROWSER_USER': USER_A}
        process = await asyncio.create_subprocess_exec('node', str(Path(__file__).with_name('workspace_browser.cjs')), env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        output, _ = await asyncio.wait_for(process.communicate(), timeout=100)
        assert process.returncode == 0, output.decode()
        print(output.decode())
        assert len(e.provider_calls) == 2
        assert e.fault['hits'] > 0
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        server.should_exit = True
        await serving
        sock.close()


@pytest.mark.asyncio
async def test_code_free_action_uses_real_receipt_before_any_provider(workspace_entry):
    e = workspace_entry
    before = await e.snapshot()
    response = await e.request('csv.parse', {'text': 'placeholder_name,placeholder_value\nplaceholder_item,placeholder_one\n'})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['rows'] == [{'placeholder_name': 'placeholder_item', 'placeholder_value': 'placeholder_one'}]
    assert data['receipt']['cost_usd'] == 0 and data['ledger_id']
    row = await e.pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', UUID(data['ledger_id']))
    assert row['model'] == 'code' and row['tokens_in'] == row['tokens_out'] == 0
    assert not e.provider_calls and not e.stack.calls and await e.snapshot() == before


@pytest.mark.asyncio
async def test_remembered_business_fields_are_meaningful(workspace_entry):
    e = workspace_entry
    await chat(e)
    rows = await e.stack.client(USER_A).records(e.stack.tenant)
    receipts = [row for row in rows if row['kind'] == 'workspace.receipt']
    assert receipts
    for row in receipts:
        meta = row['meta'] if isinstance(row['meta'], dict) else json.loads(row['meta'])
        assert meta['user_id'] == USER_A
        assert meta['task_key'] and meta['input_fingerprint']
        assert meta['reusable_result']
        assert 'placeholder summarize the project' in json.dumps(row)
        assert all(meta['reusable_result'].get(name) for name in ('conversations', 'projects', 'files', 'outcome'))


@pytest.mark.asyncio
async def test_shared_fixture_positive_owner_recall_reproducer(workspace_entry):
    e = workspace_entry
    row = await e.seed()
    listed = await e.stack.client(USER_A).records(e.stack.tenant)
    assert row['id'] in {r['id'] for r in listed}
    assert row['agent'] == 'workspace', 'BLOCKED shared fixture: schema default agent differs from product vector collection'
    recalled = await e.stack.client(USER_A).recall(e.stack.tenant, 'placeholder original answer')
    assert row['id'] in {r['id'] for r in recalled}


@pytest.mark.asyncio
async def test_capture_first_repeat_changed_actual_entry_metrics(workspace_entry):
    e = workspace_entry
    measurements = []
    for label, body in [('first', CHAT), ('exact_repeat', CHAT), ('changed_input', {**CHAT, 'messages': [{'role': 'user', 'content': 'placeholder changed input'}]})]:
        before = len(e.provider_calls)
        response = await e.request('chat', body)
        data = response.json()
        ledger_id = data.get('ledger_id') or (data.get('detail') or {}).get('ledger_id')
        row = await e.pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', UUID(ledger_id)) if ledger_id else None
        measurements.append({'run': label, 'http_status': response.status_code,
            'provider_calls': len(e.provider_calls)-before,
            'receipt_cost_usd': float(row['cost_usd']) if row else None,
            'would_have_cost_usd': data.get('receipt', {}).get('baseline_cost_usd'),
            'ledger_baseline_cost_usd': float(row['baseline_cost_usd']) if row and row['baseline_cost_usd'] is not None else None,
            'tokens_in': row['tokens_in'] if row else None, 'tokens_out': row['tokens_out'] if row else None,
            'outcome': row['outcome'] if row else None})
    print('WORKSPACE_GATE78_MEASUREMENTS=' + json.dumps(measurements, sort_keys=True))
    assert all(row['http_status'] == 200 for row in measurements), 'BLOCKED: no successful paid-path fixture measurement'
    assert measurements[0]['provider_calls'] == measurements[2]['provider_calls'] == 1
    assert measurements[1]['provider_calls'] == measurements[1]['tokens_in'] == measurements[1]['tokens_out'] == 0
    assert [row['receipt_cost_usd'] for row in measurements] == [.013, 0, .013]
    assert measurements[1]['would_have_cost_usd'] == measurements[1]['ledger_baseline_cost_usd']
    assert measurements[1]['would_have_cost_usd'] >= measurements[0]['receipt_cost_usd']


@pytest.mark.asyncio
@pytest.mark.parametrize('foreign', ['user', 'tenant'])
@pytest.mark.parametrize('operation', ['memory.view', 'memory.edit', 'memory.forget'])
async def test_denied_control_keeps_memory_settings_and_receipts_unchanged(workspace_entry, foreign, operation):
    e = workspace_entry
    row = await e.seed()
    assert (await e.request('memory.control', {'control': 'edit'})).status_code == 200
    scope = {'user': USER_B} if foreign == 'user' else {'tenant': e.stack.other_tenant}
    before = await e.snapshot()
    tenants = [UUID(e.stack.tenant), UUID(e.stack.other_tenant)]
    query = 'SELECT * FROM tank.ledger WHERE tenant_id=ANY($1::uuid[]) ORDER BY id'
    receipts = await e.pool.fetch(query, tenants)
    body = {'memory_id': row['id']}
    if operation == 'memory.edit':
        body['text'] = 'placeholder refused edit'
    response = await e.request(operation, body, **scope)
    assert response.status_code in {403, 404}, response.text
    assert await e.snapshot() == before
    after = await e.pool.fetch(query, tenants)
    original_ids = {row['id'] for row in receipts}
    assert [row for row in after if row['id'] in original_ids] == receipts, 'Denied controls must not mutate any existing receipt'
    audits = [row for row in after if row['id'] not in original_ids]
    assert len(audits) == 1, 'Keep exactly one sanitized caller denial audit'
    audit = audits[0]
    assert str(audit['id']) == response.json()['detail']['ledger_id']
    assert str(audit['tenant_id']) == scope.get('tenant', e.stack.tenant)
    assert audit['agent'] == 'workspace' and audit['task_type'] == 'command.turn'
    assert audit['outcome'] == 'failed' and audit['cost_usd'] == 0
    assert audit['tokens_in'] == audit['tokens_out'] == 0
    assert json.loads(audit['error']) == {'action': 'workspace.' + operation, 'status': 'denied',
        'actor_user_id': scope.get('user', USER_A)}
    for private in (row['id'], 'placeholder original answer', 'placeholder refused edit', e.stack.key):
        assert private not in str(dict(audit))
    assert not e.provider_calls


@pytest.mark.asyncio
async def test_ladder_evaluates_accepted_case_and_accounts_for_both_calls(workspace_entry):
    e = workspace_entry
    await e.pool.execute("""INSERT INTO tank.evals(tenant_id,task_type,input,expected,tolerance,verdict)
        VALUES($1,'tier0.answer',$2::jsonb,$3::jsonb,'exact','accepted')""",
        UUID(e.stack.tenant), json.dumps({'text': 'placeholder calibration request'}),
        json.dumps('placeholder completed answer'))
    first = await chat(e)
    assert len(e.provider_calls) == 2  # calibration and serving; neither hidden
    assert all(call['model'] == 'llama-small' for call in e.provider_calls)
    rows = await e.pool.fetch("SELECT task_type,cost_usd,tokens_in,tokens_out FROM tank.ledger WHERE tenant_id=$1 AND tokens_in>0", UUID(e.stack.tenant))
    assert {r['task_type'] for r in rows} == {'tier0.answer', 'tier0.answer#engine-eval'}
    assert len(rows) == 2 and sum(float(r['cost_usd']) for r in rows) == pytest.approx(.026)
    assert sum(r['tokens_in'] for r in rows) == 20 and sum(r['tokens_out'] for r in rows) == 6
    repeat = await chat(e)
    assert len(e.provider_calls) == 2 and repeat['memory_bracket']['paid_calls'] == 0
    assert first['memory_bracket']['cost_usd'] == pytest.approx(.013)


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [401, 403])
async def test_post_payment_auth_refusal_preserves_model_receipt_without_retry(workspace_entry, status):
    e = workspace_entry
    e.fault.update(method='POST', path='/memories', status=status)
    response = await e.request('chat', CHAT)
    assert response.status_code == status and e.fault['hits'] == 1
    assert len(e.provider_calls) == 1
    detail = response.json()['detail']
    row = await e.pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2', UUID(detail['ledger_id']), UUID(e.stack.tenant))
    assert row['tokens_in'] == 10 and row['tokens_out'] == 3
    assert float(row['cost_usd']) == detail['receipt']['cost_usd'] == .013
    assert detail['action_ledger_id'] != detail['ledger_id']
    assert not await e.snapshot()


@pytest.mark.asyncio
async def test_real_engine_memory_is_available_and_personally_scoped(workspace_entry):
    e = workspace_entry
    await chat(e)
    calls = [status for method, path, status in e.statuses if path.startswith('/engine/')]
    assert calls and all(status == 200 for status in calls)
    rows = await e.pool.fetch(f'SELECT tenant_id,meta FROM {e.engine_schema}.memory_records')
    assert rows
    assert all(str(row['tenant_id']) == e.stack.tenant and json.loads(row['meta'])['user_id'] == USER_A for row in rows)


@pytest.mark.asyncio
async def test_confirm_replay_does_not_enqueue_or_pay_twice(workspace_entry):
    e = workspace_entry
    result = await e.confirmed_task({'title': 'placeholder once', 'request': 'placeholder request'})
    card = result.json()['card_id']
    replies = await asyncio.gather(*[e.client.post(f'/v1/command/cards/{card}', headers=e.headers(), json={'action': 'confirm'}) for _ in range(2)])
    assert all(response.status_code in {200, 409} for response in replies)
    for task in tuple(e.main._background):
        await task
    assert await e.pool.fetchval('SELECT count(*) FROM tank.tasks WHERE tenant_id=$1', UUID(e.stack.tenant)) == 1
    assert len(e.provider_calls) == 1


async def completed_task(e, **changes):
    body = {'title': 'placeholder checkpoint task', 'request': 'placeholder checkpoint request', **changes}
    await e.confirmed_task(body)
    async with asyncio.timeout(10):
        while True:
            row = await e.pool.fetchrow('SELECT * FROM tank.tasks WHERE tenant_id=$1 AND title=$2',
                                        UUID(e.stack.tenant), body['title'])
            if row and row['status'] in {'done', 'failed'}:
                break
            await asyncio.sleep(.01)
    assert row['status'] == 'done', row['error']
    assert len(e.provider_calls) == 1
    assert not await e.pool.fetchval('SELECT count(*) FROM tank.workspace_task_memory WHERE task_id=$1', row['id'])
    return row


@pytest.mark.asyncio
async def test_completed_task_memory_is_owned_and_forget_survives_restart(workspace_entry):
    e = workspace_entry
    task = await completed_task(e)
    for scope in ({'user': USER_B}, {'tenant': e.stack.other_tenant}):
        before = await e.snapshot()
        denied = await e.request('task.receipt', {'task_id': str(task['id'])}, method='GET', **scope)
        assert denied.status_code in {403, 404}, denied.text
        assert await e.snapshot() == before
        assert not await e.pool.fetchval('SELECT count(*) FROM tank.workspace_task_memory WHERE task_id=$1', task['id'])
    result = await e.request('task.receipt', {'task_id': str(task['id'])}, method='GET')
    assert result.status_code == 200, result.text
    marker = await e.pool.fetchrow('SELECT * FROM tank.workspace_task_memory WHERE task_id=$1', task['id'])
    assert marker['state'] == 'done' and marker['user_id'] == USER_A and str(marker['tenant_id']) == e.stack.tenant
    memories = await e.snapshot()
    assert memories
    for row in memories:
        forgotten = await e.request('memory.forget', {'memory_id': str(row['id'])})
        assert forgotten.status_code == 200, forgotten.text
    await e.restart()
    e.stack.calls.clear()
    for route, body in [('tasks', {}), ('task.receipt', {'task_id': str(task['id'])})]:
        polled = await e.request(route, body, method='GET')
        assert polled.status_code == 200, polled.text
    assert not await e.snapshot() and not e.stack.calls
    assert dict(await e.pool.fetchrow('SELECT * FROM tank.workspace_task_memory WHERE task_id=$1', task['id'])) == dict(marker)
    assert len(e.provider_calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [503, 401, 403])
async def test_completed_task_remember_failure_checkpoint_survives_restart(workspace_entry, status):
    e = workspace_entry
    task = await completed_task(e)
    e.fault.update(method='POST', path='/memories', status=status)
    result = await e.request('task.receipt', {'task_id': str(task['id'])}, method='GET')
    assert result.status_code == (200 if status == 503 else status), result.text
    assert e.fault['hits'] == 1
    if status == 503:
        bracket = result.json()['memory_bracket']
        assert bracket['memory_unavailable'] and bracket['paid_calls'] == 1
        assert bracket['cost_usd'] == .013 and bracket['tokens_in'] == 10 and bracket['tokens_out'] == 3
    marker = await e.pool.fetchrow('SELECT * FROM tank.workspace_task_memory WHERE task_id=$1', task['id'])
    assert marker['state'] == ('unavailable' if status == 503 else 'denied')
    assert marker['user_id'] == USER_A and str(marker['tenant_id']) == e.stack.tenant
    paid_before = dict(await e.pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', task['ledger_id']))
    await e.restart()
    e.fault.update(method=None, path=None)
    e.stack.calls.clear()
    for _ in range(2):
        polled = await e.request('task.receipt', {'task_id': str(task['id'])}, method='GET')
        assert polled.status_code == (200 if status == 503 else 403), polled.text
    assert not e.stack.calls and not await e.snapshot()
    assert dict(await e.pool.fetchrow('SELECT * FROM tank.workspace_task_memory WHERE task_id=$1', task['id'])) == dict(marker)
    assert dict(await e.pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', task['ledger_id'])) == paid_before
    assert len(e.provider_calls) == 1


@pytest.mark.asyncio
async def test_memory_off_propagates_to_worker_and_resets_for_next_actor(workspace_entry):
    e = workspace_entry
    assert (await e.request('memory.control', {'control': 'off'})).status_code == 200
    e.stack.calls.clear()
    await completed_task(e)
    assert e.stack.calls and all(method == 'GET' and path == '/records' for method, path in e.stack.calls)
    assert not await e.pool.fetchval(f'SELECT count(*) FROM {e.engine_schema}.memory_records')
    e.stack.calls.clear()
    await chat(e, user=USER_B)
    assert ('POST', '/engine/recall') in e.stack.calls and ('POST', '/engine/remember') in e.stack.calls
    rows = await e.pool.fetch(f'SELECT meta FROM {e.engine_schema}.memory_records')
    assert rows and all(json.loads(row['meta'])['user_id'] == USER_B for row in rows)
    assert (await e.request('memory.control', {'control': 'edit'})).status_code == 200
    e.stack.calls.clear()
    await chat(e)
    assert ('POST', '/engine/recall') in e.stack.calls and ('POST', '/engine/remember') in e.stack.calls
    owners = {json.loads(row['meta'])['user_id'] for row in await e.pool.fetch(f'SELECT meta FROM {e.engine_schema}.memory_records')}
    assert owners == {USER_A, USER_B}
