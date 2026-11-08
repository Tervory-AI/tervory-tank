"""Rig Gate 7/8 entry-path acceptance. Missing runtime fails; never skips.

The manifest preserves all original gates. Product unit fakes and the old t51
proposal are deliberately not imported into this canonical contribution.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import pytest
import yaml
from products.rig_fixture import ROOT, USER_A, USER_B, USER_C, require_runtime, rig_wire

__all__ = ['rig_wire']


def created(response):
    assert response.status_code == 200, response.text
    return response.json()['memory']['id']


@pytest.mark.asyncio
async def test_owner_crud_persists_and_forget_removes_vector(rig_wire):
    wire = rig_wire
    identity = created(await wire.edit())
    rows = await wire.rows()
    row = next(row for row in rows if row['id'] == identity)
    assert row['meta']['user_id'] == USER_A and row['text'] == 'placeholder private build'
    created(await wire.edit('placeholder corrected build', memory_id=identity))
    rows = await wire.rows()
    assert any(row['text'] == 'placeholder corrected build' for row in rows)
    assert all(row['text'] != 'placeholder private build' for row in rows)
    for row in rows:
        response = await wire.request('POST', '/memory/forget', body={'memory_id': row['id']})
        assert response.status_code == 200, response.text
    assert await wire.rows() == []
    # Infrastructure cross-check of SQL/vector deletion, not signed-in user proof.
    assert await wire.stack.client(USER_A).recall(wire.stack.tenant, 'placeholder') == []


@pytest.mark.asyncio
@pytest.mark.parametrize('foreign', ['same_tenant', 'other_tenant'])
@pytest.mark.parametrize('operation', ['read', 'edit', 'forget', 'publish'])
async def test_foreign_ids_never_read_or_mutate(rig_wire, foreign, operation):
    wire = rig_wire
    identity = created(await wire.edit())
    before = await wire.persistent()
    user, tenant = (USER_B, wire.stack.tenant) if foreign == 'same_tenant' else (USER_C, wire.stack.other_tenant)
    if operation == 'read':
        assert not any(row['id'] == identity for row in await wire.rows(user, tenant))
    elif operation == 'edit':
        response = await wire.edit('placeholder stolen edit', user=user, tenant=tenant, memory_id=identity)
        assert response.status_code in (403, 404), response.text
    else:
        response = await wire.request('POST', '/memory/' + operation, user=user, tenant=tenant,
                                      body={'memory_id': identity})
        assert response.status_code in (403, 404), response.text
    assert await wire.persistent() == before
    assert (await wire.rows())[0]['text'] == 'placeholder private build'


@pytest.mark.asyncio
async def test_declared_store_preference_shared_but_owned_preference_private(rig_wire):
    wire = rig_wire
    from hermes.user_scope import TENANT_WIDE_KINDS
    assert 'rig.store_preference' in TENANT_WIDE_KINDS['rig'], (
        'BLOCKED: reviewed Rig kind declaration is absent from current fixed core')
    shared = await wire.stack.client('').remember(wire.stack.tenant,
        'placeholder shared store preference', 'rig.store_preference',
        'urn:placeholder:rig:store', tenant_wide=True)
    personal = created(await wire.edit('placeholder personal preference', kind='rig.store_preference'))
    assert {row['id'] for row in await wire.rows()} >= {shared['id'], personal}
    assert {row['id'] for row in await wire.rows(USER_B)} == {shared['id']}
    assert await wire.rows(USER_C, wire.stack.other_tenant) == []
    rejected = await wire.request('POST', '/memory/forget', user=USER_B, body={'memory_id': personal})
    assert rejected.status_code in (403, 404)
    assert any(row['id'] == personal for row in await wire.rows())


@pytest.mark.asyncio
async def test_required_owner_body_and_header_impersonation(rig_wire):
    wire = rig_wire
    for changes in ({'user_id': USER_B}, {'tenant_id': wire.stack.other_tenant},
                    {'meta': {'user_id': USER_B, 'tenant_wide': True}}):
        response = await wire.edit(**changes)
        assert response.status_code in (401, 403, 422), response.text
    headers = wire.headers()
    headers['X-Tervory-User'] = USER_B
    response = await wire.request('POST', '/memory/edit', body={
        'text': 'placeholder impersonation', 'kind': 'rig.build', 'source': 'urn:placeholder'}, headers=headers)
    assert response.status_code == 403
    response = await wire.request('POST', '/memory/edit', body={
        'text': 'placeholder no identity', 'kind': 'rig.build', 'source': 'urn:placeholder'},
        headers={'X-Tank-Key': 'placeholder-gate78-workspace-key'})
    assert response.status_code == 401
    assert await wire.persistent() == []
    assert wire.provider.calls  # Real JWT signature/JWKS verification ran.


@pytest.mark.asyncio
@pytest.mark.parametrize('flaw', ['key', 'audience', 'tenant', 'method', 'target', 'body',
                                   'missing', 'expired', 'future'])
async def test_product_assertion_rejects_each_binding(rig_wire, flaw):
    from chassis.user_assertion import HEADER, SignedUser, sign_assertion
    wire = rig_wire
    raw = json.dumps({'tenant_id': wire.stack.tenant, 'text': 'placeholder forged',
                      'kind': 'rig.build', 'source': 'urn:placeholder'}).encode()
    actor = SignedUser(wire.stack.other_tenant if flaw == 'tenant' else wire.stack.tenant, USER_A, 'org:admin')
    token = sign_assertion('placeholder-wrong' if flaw == 'audience' else 'rig', actor,
        'GET' if flaw == 'method' else 'POST', '/memory/forget' if flaw == 'target' else '/memory/edit',
        b'placeholder-changed' if flaw == 'body' else raw,
        key='placeholder-wrong-key' if flaw == 'key' else wire.stack.key,
        now=int(time.time()) + (5 if flaw == 'future' else -61 if flaw == 'expired' else 0))
    headers = {'X-Tank-Key': wire.stack.key, 'Content-Type': 'application/json'}
    if flaw != 'missing':
        headers[HEADER] = token
    before = await wire.persistent()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=wire.product), base_url='http://agent-rig:8000') as direct:
        response = await direct.post('/memory/edit', content=raw, headers=headers)
    assert response.status_code == 401, response.text
    assert await wire.persistent() == before


@pytest.mark.asyncio
async def test_nonce_concurrency_restart_and_forgotten_write_replay(rig_wire):
    from chassis.user_assertion import HEADER, PostgresNonces
    wire = rig_wire
    identity = created(await wire.edit())
    captured = wire.captured[-1]
    assert captured.headers.get(HEADER), 'Tank must attach the current nonce-protected assertion'
    raw, headers = captured.content, dict(captured.headers)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=wire.product), base_url='http://agent-rig:8000') as direct:
        answers = await asyncio.gather(*(direct.post(captured.url.raw_path.decode(), content=raw, headers=headers) for _ in range(4)))
        assert all(answer.status_code == 401 for answer in answers)
        forgotten = await wire.request('POST', '/memory/forget', body={'memory_id': identity})
        assert forgotten.status_code == 200
        restarted = PostgresNonces(wire.pool, 'rig')
        restarted.schema = wire.stack.records.schema('rig')
        wire.product.state.product_nonce_stores = {'rig': restarted}
        replay = await direct.post(captured.url.raw_path.decode(), content=raw, headers=headers)
        assert replay.status_code == 401
    assert await wire.rows() == []


@pytest.mark.asyncio
async def test_sql_scope_before_vector_and_limit(rig_wire, monkeypatch):
    wire = rig_wire
    owner = created(await wire.edit())
    foreign = created(await wire.edit('placeholder peer private', user=USER_B))
    observed = []
    index = wire.stack.records.index
    original = index.search

    def search(*args, **kwargs):
        observed.append(kwargs.get('allowed_ids'))
        return original(*args, **kwargs)

    monkeypatch.setattr(index, 'search', search)
    # Actual task must recall; no direct-client recall counted as product proof.
    await wire.build()
    assert observed and any(owner in (ids or []) for ids in observed)
    assert all(foreign not in (ids or []) for ids in observed)
    observed.clear()
    await wire.build(user=USER_C, tenant=wire.stack.other_tenant)
    assert not observed or all(ids == [] for ids in observed)


@pytest.mark.asyncio
async def test_controls_under_restricted_database_role_and_rls(rig_wire, gate78_database, monkeypatch):
    wire = rig_wire
    schema = wire.stack.records.schema('rig')
    role = 'placeholder_rig_' + uuid4().hex
    async with wire.pool.acquire() as conn:
        await conn.execute(f'CREATE ROLE {role} NOSUPERUSER NOBYPASSRLS')
        await conn.execute(f'GRANT USAGE, CREATE ON SCHEMA {schema} TO {role}')
        await conn.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {role}')
    import asyncpg
    from chassis.user_assertion import PostgresNonces

    async def role_setup(conn):
        await conn.execute(f'SET ROLE {role}')

    restricted = await asyncpg.create_pool(gate78_database, min_size=1, max_size=1,
                                           setup=role_setup, ssl=False)
    monkeypatch.setattr(wire.stack.records, 'pool', restricted)
    wire.product.state.pool = restricted
    nonces = PostgresNonces(restricted, 'rig')
    nonces.schema = schema
    wire.product.state.product_nonce_stores = {'rig': nonces}
    try:
        async with restricted.acquire() as conn:
            privileges = await conn.fetchrow('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
            assert not privileges['rolsuper'] and not privileges['rolbypassrls']
            guarded = await conn.fetchval("SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass($1)", schema + '.jobs')
        identity = created(await wire.edit())
        assert any(row['id'] == identity for row in await wire.rows())
        assert await wire.rows(USER_B) == []
        assert (await wire.request('POST', '/memory/forget', user=USER_B,
                                  body={'memory_id': identity})).status_code in (403, 404)
        if guarded:
            assert await restricted.fetchval("SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass($1)",
                                            schema + '.user_assertion_nonces')
    finally:
        monkeypatch.setattr(wire.stack.records, 'pool', wire.pool)
        await restricted.close()
        async with wire.pool.acquire() as conn:
            await conn.execute(f'DROP OWNED BY {role}')
            await conn.execute(f'DROP ROLE {role}')



@pytest.mark.asyncio
async def test_controls_off_is_per_user_and_plain_shopper_without_identity_runs(rig_wire):
    wire = rig_wire
    created(await wire.edit())
    peer = created(await wire.edit('placeholder peer fact', user=USER_B))
    response = await wire.request('POST', '/memory/switch', body={'enabled': False})
    assert response.status_code == 200 and response.json()['memory_enabled'] is False
    assert await wire.rows() == []
    assert any(row['id'] == peer for row in await wire.rows(USER_B))
    before = await wire.persistent()
    answer = await wire.request('GET', '/v1/rig/search',
        headers={'X-Tank-Key': 'placeholder-gate78-workspace-key'})
    assert answer.status_code == 200, answer.text
    assert await wire.persistent() == before
    assert not wire.provider_calls


@pytest.mark.asyncio
async def test_no_foreign_content_or_secret_in_responses_receipts_or_logs(rig_wire, caplog):
    wire = rig_wire
    sentinel = 'placeholder-owner-private-design'
    created(await wire.edit(sentinel))
    response = await wire.edit('api_key=placeholder-never-store')
    assert response.status_code in (400, 422), response.text
    for user, tenant in ((USER_B, wire.stack.tenant), (USER_C, wire.stack.other_tenant)):
        assert sentinel not in json.dumps(await wire.rows(user, tenant))
        result = await wire.build(user=user, tenant=tenant)
        assert sentinel not in json.dumps(result)
    assert sentinel not in caplog.text and 'placeholder-never-store' not in caplog.text


def test_runtime_packaging_and_default_off_profiles(monkeypatch):
    require_runtime()
    monkeypatch.syspath_prepend(str(ROOT / 'agents/rig'))
    from gates_memory import memory_enabled
    from rig_brain_client import brain_enabled
    monkeypatch.delenv('RIG_MEMORY_ENABLED', raising=False)
    monkeypatch.delenv('RIG_BRAIN_ENABLED', raising=False)
    assert not memory_enabled() and not brain_enabled()
    services = yaml.safe_load((ROOT / 'agents/rig/docker-compose.yml').read_text())['services']
    for name in ('rig-brain', 'rig-sandbox'):
        assert 'brain' in services[name]['profiles']


@pytest.mark.asyncio
async def test_unset_settings_add_no_memory_work_or_rescheduling(rig_wire, monkeypatch):
    wire = rig_wire
    monkeypatch.delenv('RIG_MEMORY_ENABLED', raising=False)
    monkeypatch.delenv('RIG_BRAIN_ENABLED', raising=False)
    before, calls = await wire.persistent(), list(wire.stack.calls)
    answer = await wire.request('GET', '/v1/rig/search')
    assert answer.status_code == 200
    assert await wire.persistent() == before and wire.stack.calls == calls
    assert not wire.provider_calls
    assert not list(wire.root.rglob('submitted.json'))


@pytest.mark.asyncio
async def test_build_task_recall_execution_receipt_remember_and_exact_repeat(rig_wire):
    wire = rig_wire
    first = await wire.build()
    repeat = await wire.build()  # Fresh run identity, identical business input.
    changed = await wire.build('placeholder build a different display stand')
    assert first['status'] == repeat['status'] == changed['status'] == 'done'
    # Fixture costs must be observed at the provider edge and reconcile to Tank.
    assert len(wire.provider_calls) == 4
    for receipt, calls in ((first, 2), (repeat, 0), (changed, 2)):
        assert receipt['paid_calls'] == calls
        assert receipt['cost_usd'] == (0.05 * calls)
        assert receipt['tokens_in'] == (10 * calls)
        assert receipt['tokens_out'] == (3 * calls)
        assert receipt['tenant_id'] == wire.stack.tenant and receipt['user_id'] == USER_A
        assert receipt['would_have_cost']['cost_usd'] == 0.1
        assert receipt['tank_receipts']
    assert repeat['answered_from_memory'] is True
    rows = await wire.rows()
    assert any('placeholder' in row['text'] and row['meta'].get('outcome') for row in rows)
    # Each product memory category is written by a real owner control, then
    # positively recalled by the actual worker; unrelated invented output fields
    # are not evidence of a successful catalogue build.
    kinds = ('rig.build', 'rig.store_preference', 'rig.part', 'rig.fit', 'rig.quote', 'rig.rejected_design')
    evidence = []
    for kind in kinds:
        evidence.append(created(await wire.edit('placeholder ' + kind, kind=kind)))
    await wire.build('placeholder recall approved catalogue evidence')
    requests = [json.loads(p.read_text()) for p in wire.root.rglob('request.json')]
    assert any(set(evidence) <= {row['id'] for row in item['memories']} for item in requests)



@pytest.mark.asyncio
async def test_changed_owner_tenant_and_ineligible_action_never_reuses(rig_wire):
    wire = rig_wire
    first = await wire.build()
    for user, tenant in ((USER_B, wire.stack.tenant), (USER_C, wire.stack.other_tenant)):
        answer = await wire.build(user=user, tenant=tenant)
        assert answer['answered_from_memory'] is False
        assert answer['user_id'] == user and answer['tenant_id'] == tenant
        assert answer['task_id'] != first['task_id']
    from gates_memory import is_cache_eligible
    assert not is_cache_eligible('rig.forge.submit')
    assert not is_cache_eligible('rig.payment')
    assert len(wire.provider_calls) == 6


@pytest.mark.asyncio
async def test_correction_and_forget_invalidate_derived_repeats(rig_wire):
    wire = rig_wire
    await wire.build()
    correction = created(await wire.edit('correction=placeholder prefer low stand', kind='rig.correction'))
    corrected = await wire.build()
    assert 'placeholder prefer low stand' in json.dumps(corrected)
    peer = await wire.build(user=USER_B)
    assert 'placeholder prefer low stand' not in json.dumps(peer)
    response = await wire.request('POST', '/memory/forget', body={'memory_id': correction})
    assert response.status_code == 200
    assert not any((row.get('meta') or {}).get('outcome') for row in await wire.rows())
    after = await wire.build()
    assert 'placeholder prefer low stand' not in json.dumps(after)
    assert not after['answered_from_memory']


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['records', 'recall', 'remember'])
async def test_memory_network_outages_are_truthful_and_do_not_pay_twice(rig_wire, operation):
    wire = rig_wire
    paths = {'records': '/records', 'recall': '/recall', 'remember': '/memories'}

    wire.memory_failure = (paths[operation], 503)
    try:
        task_id = str(uuid4())
        first = await wire.build(task_id=task_id)
        second = await wire.build(task_id=task_id)
        assert first['memory_status'] == 'memory unavailable'
        assert second['task_id'] == first['task_id']
        assert len(wire.provider_calls) == 2
        assert first['cost_usd'] == second['cost_usd'] == 0.1
    finally:
        wire.memory_failure = None


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [401, 403])
async def test_auth_errors_never_return_private_cached_answers(rig_wire, status):
    wire = rig_wire
    await wire.build()
    before = len(wire.provider_calls)
    wire.memory_failure = (None, status)
    try:
        result = await wire.build()
        assert result['status'] != 'done'
        assert not result.get('answered_from_memory')
        assert result.get('memory_status') != 'memory unavailable'
        assert len(wire.provider_calls) == before
    finally:
        wire.memory_failure = None


@pytest.mark.asyncio
async def test_concurrent_task_identity_preserves_one_payment_and_receipt(rig_wire):
    wire = rig_wire
    identity = str(uuid4())
    results = await asyncio.gather(*(wire.build(task_id=identity) for _ in range(3)))
    assert all(row['task_id'] == identity and row['user_id'] == USER_A for row in results)
    assert len(wire.provider_calls) == 2
    assert len({json.dumps(row['tank_receipts'], sort_keys=True) for row in results}) == 1


def test_forge_one_command_offline_no_database_and_cli_contract():
    require_runtime()
    import os
    env = dict(os.environ)
    for name in ('DATABASE_URL', 'RIG_TEST_DATABASE_URL', 'POOL_SCHEMA_DATABASE_URL'):
        env.pop(name, None)
    env['PYTHONPATH'] = os.pathsep.join(str(ROOT / path) for path in ('agents/rig', 'agents/_chassis', ''))
    result = subprocess.run([sys.executable, '-m', 'rigbox.three_d.command', '--dry-run'],
                            cwd=ROOT, env=env, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'approved' in result.stdout.lower()
    # Keep the original offline-box requirement visible; its private demo class
    # cannot substitute for this shipped product command or authenticated path.
    assert (ROOT / 'tests/test_rig_offline_box_journey.py').is_file()


@pytest.mark.asyncio
async def test_tank_grants_deny_controls_and_build_without_product_access(rig_wire):
    wire = rig_wire
    await wire.pool.execute("DELETE FROM tank.tenant_squad WHERE tenant_id=$1::uuid AND agent='rig'", wire.stack.tenant)
    before = await wire.persistent()
    response = await wire.edit()
    assert response.status_code == 403
    response = await wire.request('POST', '/tasks', body={
        'task_id': str(uuid4()), 'home_region': 'us-east', 'question': 'placeholder denied build'})
    assert response.status_code == 403
    assert await wire.persistent() == before and not wire.provider_calls
    assert not list(wire.root.rglob('submitted.json'))


@pytest.mark.asyncio
async def test_worker_owner_survives_retry_restart_and_foreign_poll(rig_wire):
    wire = rig_wire
    task_id = str(uuid4())
    first = await wire.build(task_id=task_id)
    assert first['status'] == 'done'
    count = len(wire.provider_calls)
    foreign = await wire.ingress.get('/v1/rig/tasks/' + task_id,
        params={'tenant_id': wire.stack.tenant, 'home_region': 'us-east'}, headers=wire.headers(USER_B))
    assert foreign.status_code == 404
    import rig_brain.service as brain
    assert not brain.jobs
    retried = await wire.build(task_id=task_id)
    assert retried == first and len(wire.provider_calls) == count
    submitted = next(wire.root.rglob('submitted.json'))
    assert json.loads(submitted.read_text())['user_id'] == USER_A


@pytest.mark.asyncio
async def test_worker_failure_keeps_actual_bill_and_retry_never_fabricates_success(rig_wire):
    wire = rig_wire
    wire.provider_mode = 'malformed'
    identity = str(uuid4())
    first = await wire.build(task_id=identity)
    assert first['status'] == 'failed' and first['model_receipts']
    actual = sum(row['cost_usd'] for row in wire.provider_calls)
    assert actual > 0 and first['cost_usd'] == actual
    assert first['tokens_in'] == sum(row['tokens_in'] for row in wire.provider_calls)
    assert first['tokens_out'] == sum(row['tokens_out'] for row in wire.provider_calls)
    count = len(wire.provider_calls)
    wire.provider_mode = ''
    retry = await wire.build(task_id=identity)
    assert retry['status'] == 'failed' and retry['cost_usd'] == actual
    assert len(wire.provider_calls) == count
    assert not any((row.get('meta') or {}).get('outcome') for row in await wire.rows())


@pytest.mark.asyncio
async def test_observed_zero_worker_cost_is_not_replaced_with_a_fixture_price(rig_wire):
    wire = rig_wire
    wire.provider_cost = 0
    result = await wire.build()
    assert result['status'] == 'done' and len(wire.provider_calls) == 2
    assert result['cost_usd'] == 0 and result['would_have_cost']['cost_usd'] == 0
    assert all(row['cost_usd'] == 0 for row in result['model_receipts'])


@pytest.mark.asyncio
async def test_editing_owned_result_replaces_it_and_invalidates_reuse(rig_wire):
    wire = rig_wire
    first = await wire.build()
    assert first['status'] == 'done'
    row = next(row for row in await wire.rows() if (row.get('meta') or {}).get('outcome'))
    identity = created(await wire.edit('placeholder corrected result', kind='rig.correction', memory_id=row['id']))
    assert identity == row['id']
    rows = await wire.rows()
    assert any(item['id'] == identity and item['text'] == 'placeholder corrected result' for item in rows)
    assert not any((item.get('meta') or {}).get('outcome') for item in rows)
    corrected = await wire.build()
    assert corrected['summary'] == 'placeholder corrected result'
    assert len(wire.provider_calls) == 2
