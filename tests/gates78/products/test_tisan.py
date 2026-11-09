"""Tisan acceptance on the central platform, never a private Hermes overlay.
Runtime dependencies are ordinary failures, not skips/xfails or gate passes.
Fixture prices are labelled and must reconcile with observed network calls.
"""
import asyncio
import json
from pathlib import Path
import httpx
import pytest
import yaml
from tisan_assertions import assert_foreign_state, assert_rejected_assertion, assert_replay_wall, assert_owner_task, assert_fixture_spend
from tisan_fixture import (tisan as tisan, tisan_runtime as tisan_runtime, USER_A, USER_B, KEY,
                           FIXTURE_COST, FIXTURE_INPUT, FIXTURE_OUTPUT, corrected_plan)

@pytest.mark.asyncio
async def test_owner_task_recall_list_edit_forget(tisan):
    await assert_owner_task(tisan)

@pytest.mark.asyncio
@pytest.mark.parametrize('other_tenant', [False, True])
async def test_foreign_read_edit_forget_and_publish_leave_owner_state_unchanged(tisan, other_tenant):
    await assert_foreign_state(tisan, other_tenant)

@pytest.mark.asyncio
async def test_only_declared_brand_kind_is_shared_and_owned_brand_stays_personal(tisan):
    from hermes.user_scope import TENANT_WIDE_KINDS
    assert tisan.runtime.gates_memory.TENANT_WIDE <= TENANT_WIDE_KINDS['tisan']
    await tisan.plan()
    brand = [r for r in (await tisan.view(USER_B))['memories'] if r['kind'] == 'tisan.brand']
    assert brand and all(not r['meta'].get('user_id') for r in brand)
    # Infrastructure seeding uses the shipped signed client, after real owner
    # ingress above. The visibility/mutation proof still uses product controls.
    saved = await tisan.stack.client(USER_A).remember(tisan.stack.tenant,
        'placeholder personal brand', 'tisan.brand', 'placeholder-central-test', index=False,
        meta={'value': {'placeholder': 'personal brand'}}, user_id=USER_A)
    assert saved['id'] in {r['id'] for r in (await tisan.view())['memories']}
    assert saved['id'] not in {r['id'] for r in (await tisan.view(USER_B))['memories']}
    edited = await tisan.correct(saved['id'], {'placeholder': 'edited personal brand'})
    own = next(r for r in (await tisan.view())['memories'] if r['id'] == edited['id'])
    assert own['meta']['user_id'] == USER_A
    assert edited['id'] not in {r['id'] for r in (await tisan.view(USER_B))['memories']}
    assert (await tisan.control('DELETE', '/' + edited['id'])).status_code == 200
    assert edited['id'] not in {r['id'] for r in (await tisan.view())['memories']}
    with pytest.raises((ValueError, RuntimeError)):
        await tisan.stack.client(USER_A).remember(tisan.stack.tenant,
            'placeholder unowned personal row', 'tisan.result', 'placeholder-central-test',
            index=False, tenant_wide=True)

@pytest.mark.asyncio
async def test_verified_signin_and_product_assertion_not_body_or_raw_headers(tisan):
    await tisan.plan()
    assert tisan.provider.calls, 'Actual Trigger sign-in discovery/signature verification must run'
    states = [s.get('verified_product_user') for s in tisan.room.states if s.get('verified_product_user')]
    assert states and all(s.user_id == USER_A and s.tenant_id == tisan.stack.tenant for s in states)
    original = await tisan.records()
    forged = await tisan.control('POST', '/setting', body={'enabled': False,
        'user_id': USER_B, 'tenant_id': tisan.stack.other_tenant})
    assert forged.status_code in (400, 401, 403, 404, 422)
    assert await tisan.records() == original
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tisan.room), base_url='http://agent-tisan:8000') as raw:
        denied = await raw.get('/memory', headers={'X-Tank-Key': KEY, 'X-Tervory-User': USER_A},
            params={'tenant_id': tisan.stack.tenant, 'user_id': USER_A})
        assert denied.status_code in (401, 403, 404)

@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['missing', 'key', 'audience', 'tenant', 'method', 'target', 'body', 'expired', 'future'])
async def test_nonce_assertion_rejection_at_product_control(tisan, fault):
    await assert_rejected_assertion(tisan, fault)

@pytest.mark.asyncio
async def test_nonce_replay_is_atomic_across_restart_and_cannot_restore_forgotten_data(tisan):
    await assert_replay_wall(tisan)

@pytest.mark.asyncio
async def test_scope_is_filtered_before_vector_search_limit_and_empty_user_scope(tisan, monkeypatch):
    await tisan.plan(user=USER_A)
    await tisan.view(USER_B)
    observed = []
    index = tisan.stack.records.index
    original = index.search
    def observe(*args, **kwargs):
        observed.append((args, kwargs))
        return original(*args, **kwargs)
    monkeypatch.setattr(index, 'search', observe)
    hits = await tisan.stack.client(USER_B).recall(tisan.stack.tenant, 'placeholder private owner',
        user_id=USER_B, kind='tisan.result', limit=1)
    assert hits == [] and observed == []

@pytest.mark.asyncio
async def test_product_controls_use_restricted_role_and_staged_rls(tisan):
    await tisan.view()
    pool = tisan.runtime.app.app.state.pool
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute('SET LOCAL ROLE agent_tisan')
            roles = await conn.fetchrow('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
            assert not roles['rolsuper'] and not roles['rolbypassrls']
            assert not await conn.fetchval("SELECT has_schema_privilege(current_user,'tank','USAGE')")
    # Actual runtime pool must use that role, not merely demonstrate a role exists.
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT current_user') == 'agent_tisan'

@pytest.mark.asyncio
async def test_controls_view_edit_forget_off_and_unsigned_plain_task(tisan):
    from tisan_worker_fixture import assert_unsigned_task
    await tisan.plan()
    await assert_unsigned_task(tisan)
    response = await tisan.control('POST', '/setting', body={'enabled': False})
    assert response.status_code == 200
    assert (await tisan.view())['enabled'] is False
    before = await tisan.records()
    await tisan.plan('placeholder memory off input')
    assert await tisan.records() == before
    assert (await tisan.view(USER_B))['enabled'] is True

@pytest.mark.asyncio
async def test_no_foreign_content_in_answers_receipts_or_logs(tisan, caplog):
    await tisan.plan('placeholder private user a brief')
    other = await tisan.plan('placeholder user b brief', user=USER_B)
    text = json.dumps(other) + json.dumps(await tisan.view(USER_B)) + caplog.text
    assert 'placeholder private user a brief' not in text
    assert KEY not in text

@pytest.mark.asyncio
async def test_real_runtime_client_and_packaging(tisan):
    from chassis.memory import MemoryClient
    assert isinstance(tisan.runtime.app.app.state.memory, MemoryClient)
    await tisan.plan()
    assert any(path == '/records' for _, path in tisan.stack.calls)
    assert any(path == '/memories' for _, path in tisan.stack.calls)
    docker = (Path(tisan.runtime.builder.__file__).with_name('Dockerfile')).read_text()
    assert 'gates_memory.py' in docker and 'memory_api.py' in docker and 'brain_service.py' in docker
    from tisan_adapter_assertions import assert_task_boundary
    await assert_task_boundary(tisan)

@pytest.mark.asyncio
async def test_default_off_keeps_profiles_and_introduces_no_memory_work(tisan, monkeypatch):
    monkeypatch.delenv('TISAN_BRAIN_ENABLED', raising=False)
    assert tisan.runtime.gates_memory.brain_enabled() is False
    compose = yaml.safe_load(Path(tisan.runtime.builder.__file__).with_name('docker-compose.yml').read_text())
    assert compose['services']['agent-tisan']['environment']['TISAN_BRAIN_ENABLED'].endswith(':-false}')
    for service in ('tisan-brain', 'tisan-sandbox', 'tisan-browser', 'tisan-browser-gateway'):
        assert compose['services'][service]['profiles'] == ['brain']
    before = list(tisan.stack.calls)
    await tisan.plan(plan={'nav': [{'href': '/'}], 'ui': {}, 'pages': [{'name': 'home', 'path': '/', 'sections': []}]})
    assert tisan.stack.calls == before

@pytest.mark.asyncio
async def test_recall_then_actual_builder_brain_tank_receipt_then_remember(tisan):
    first = await tisan.plan()
    receipt = first['brain_receipt']
    assert receipt['ledger_ids'] and receipt['memory_id']
    assert receipt['paid_calls'] == len(tisan.provider_calls) == 1
    assert receipt['cost_usd'] == FIXTURE_COST
    assert receipt['tokens_in'] == FIXTURE_INPUT and receipt['tokens_out'] == FIXTURE_OUTPUT
    rows = await tisan.records()
    assert any(r['kind'] == 'tisan.result' and r['meta']['result'] and r['meta']['receipt']['ledger_ids'] for r in rows)
    assert any(r['kind'] == 'tisan.brand' and r['meta']['value']['fonts']['heading'] == 'Jost' for r in rows)

@pytest.mark.asyncio
async def test_code_free_steps_precede_brain_and_no_provider_for_structured_plan(tisan):
    plan = {'nav': [{'href': '/'}], 'ui': {}, 'pages': [{'name': 'home', 'path': '/', 'sections': []}]}
    await tisan.plan(plan=plan)
    assert tisan.provider_calls == []

@pytest.mark.asyncio
async def test_first_exact_repeat_and_changed_input_reconcile_actual_fixture_spend(tisan, record_property):
    await assert_fixture_spend(tisan, record_property)

@pytest.mark.asyncio
async def test_another_user_and_tenant_miss_without_receiving_owner_cached_answer(tisan):
    await tisan.plan()
    for tenant, user in ((tisan.stack.tenant, USER_B), (tisan.stack.other_tenant, USER_A)):
        before = len(tisan.provider_calls)
        result = await tisan.plan(user=user, tenant=tenant)
        assert not result['brain_receipt'].get('answered_from_memory')
        assert len(tisan.provider_calls) == before + 1

@pytest.mark.asyncio
async def test_correction_invalidates_old_exact_answer_without_another_provider_call(tisan):
    await tisan.plan()
    row = next(r for r in (await tisan.view())['memories'] if r['kind'] == 'tisan.result')
    corrected = corrected_plan(row['meta']['result'])
    await tisan.correct(row['id'], corrected)
    before = len(tisan.provider_calls)
    result = await tisan.plan()
    assert len(tisan.provider_calls) == before
    assert result['brain_receipt']['source'] == 'correction'
    assert result['brain_receipt']['paid_calls'] == 0
    assert row['id'] not in {r['id'] for r in await tisan.records()}

@pytest.mark.asyncio
async def test_forget_invalidates_reusable_plan(tisan):
    await tisan.plan()
    row = next(r for r in (await tisan.view())['memories'] if r['kind'] == 'tisan.result')
    response = await tisan.control('DELETE', '/' + row['id'])
    assert response.status_code == 200
    before = len(tisan.provider_calls)
    result = await tisan.plan()
    assert len(tisan.provider_calls) == before + 1
    assert not result['brain_receipt'].get('answered_from_memory')

@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['recall', 'list', 'remember'])
async def test_memory_outage_is_truthful_and_post_payment_remember_never_pays_twice(tisan, stage):
    tisan.transport_outage = stage
    result = await tisan.plan('placeholder outage task')
    assert result['brain_receipt']['memory'] == 'memory unavailable'
    assert len(tisan.provider_calls) == 1
    assert result['brain_receipt']['paid_calls'] == 1
    assert result['brain_receipt']['cost_usd'] == FIXTURE_COST

@pytest.mark.asyncio
async def test_scope_error_is_refusal_not_a_memory_outage_or_private_cache_fallback(tisan):
    await tisan.plan()
    tisan.transport_outage = 'auth'
    before = len(tisan.provider_calls)
    with pytest.raises((PermissionError, RuntimeError, AssertionError)):
        await tisan.plan()
    assert len(tisan.provider_calls) == before

@pytest.mark.asyncio
async def test_retries_and_concurrent_exact_tasks_do_not_double_pay(tisan):
    run_id = str(__import__('uuid').uuid4())
    results = await asyncio.gather(tisan.plan(run_id=run_id), tisan.plan(run_id=run_id))
    assert len(tisan.provider_calls) == 1
    assert results[0] == results[1]
    assert results[0]['brain_receipt']['cost_usd'] == FIXTURE_COST
    assert all(r['brain_receipt']['memory_id'] for r in results)
    from tisan_worker_fixture import assert_checkpoint_replay
    await assert_checkpoint_replay(tisan)

def test_original_gate_requirements_and_browser_cli_worker_tests_remain_present(tisan_runtime):
    root = Path(tisan_runtime.builder.__file__).resolve().parents[2]
    manifest = json.loads(Path(__file__).with_name('tisan.json').read_text())
    for node in manifest['legacy_tests']:
        path, name = node.split('::', 1)
        assert (root / path).is_file(), 'Missing original requirement file: ' + path
        assert 'def ' + name + '(' in (root / path).read_text(), node
    for path in ('tests/test_tisan_gate5_browser.py', 'tests/test_tisan_k6.py',
                 'tests/test_tisan_wave4_pipeline.py'):
        assert (root / path).is_file(), path
