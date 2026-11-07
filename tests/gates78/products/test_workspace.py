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

SOURCE_SHA = '9b6b5148113c015512369ebf8a6bbd68fca3ee07'
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
    assert not e.stack.calls and await e.snapshot() == before
    assert len(e.provider_calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('entry', ['chat', 'task.create'])
async def test_paid_entry_runs_real_tank_lifecycle(workspace_entry, entry):
    e = workspace_entry
    body = CHAT if entry == 'chat' else {'title': 'placeholder project', 'request': 'placeholder summarize the project'}
    response = await e.request(entry, body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(e.provider_calls) == 1
    assert result['memory_bracket']['paid_calls'] == 1
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
    assert 'placeholder corrected project answer' in json.dumps(corrected)
    assert corrected != first
    assert (await e.request('memory.forget', {'memory_id': receipt['id']})).status_code == 200
    assert receipt['id'] not in json.dumps(await chat(e))
    assert (await e.request('memory.control', {'control': 'off'})).status_code == 200
    await chat(e)
    await chat(e)
    assert len(e.provider_calls) >= before + 2
    assert (await e.request('memory.view', {}, user=USER_B)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize('method', ['POST', 'GET'])
async def test_memory_network_outage_is_truthful_and_no_double_payment(workspace_entry, method):
    e = workspace_entry
    e.fault['method'] = method
    result = await chat(e)
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
    assert not e.stack.calls and await e.snapshot() == before
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


def test_legacy_requirements_and_product_browser_entrypoints_are_retained():
    manifest = json.loads((Path(__file__).with_name('workspace.json')).read_text())
    assert set(manifest['cases']) == set(REQUIREMENTS)
    assert manifest['source_sha'] == SOURCE_SHA
    assert len(manifest['legacy_tests']) >= 30
    # This is a deliberately strict dependency test, not simulated browser proof:
    # the deployed Tank tree must actually contain Workspace's approved controls.
    components = (ROOT / 'workspace/app').rglob('*.tsx')
    controls = [path for path in components if any(name in path.read_text() for name in ('/api/memory', 'viewWorkspaceMemory', 'setWorkspaceMemoryControl'))]
    assert controls, 'BLOCKED: no rendered personal-memory controls entry; approved empty/error/off browser proof is unavailable'


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
            'tokens_in': row['tokens_in'] if row else None, 'tokens_out': row['tokens_out'] if row else None,
            'outcome': row['outcome'] if row else None})
    print('WORKSPACE_GATE78_MEASUREMENTS=' + json.dumps(measurements, sort_keys=True))
    assert all(row['http_status'] == 200 for row in measurements), 'BLOCKED: no successful paid-path fixture measurement'
    assert measurements[0]['provider_calls'] == measurements[2]['provider_calls'] == 1
    assert measurements[1]['provider_calls'] == measurements[1]['tokens_in'] == measurements[1]['tokens_out'] == 0
