"""Tiger's original Gate 7/8 promises on the one canonical test platform."""
import asyncio
import json
import os
import time
from uuid import uuid4

import pytest
import yaml

from tiger_fixture import (KEY, ROOT, USER_A, USER_B, runtime_dependencies,
                           tiger_system as tiger_fixture)

tiger_system = tiger_fixture


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def facts():
    return {'sku': 'placeholder-sku', 'products': [{'sku': 'placeholder-sku', 'name': 'placeholder-product'}],
            'seen_prices': [{'url': 'https://placeholder.example/item', 'amount': 19.5, 'currency': 'USD'}],
            'suppliers': [{'name': 'placeholder-supplier', 'delivery_days': 3}],
            'margin_rules': [{'minimum': .2}], 'dismissed_alerts': [{'id': 'placeholder-alert', 'reason': 'placeholder-reviewed'}]}


def test_runtime_contract():
    runtime_dependencies()
    from chassis.memory import MemoryClient
    from chassis.user_assertion import sign_assertion
    assert callable(sign_assertion)
    client = MemoryClient(api_key=KEY, agent='tiger', user_id=USER_A)
    assert '/v1/memory' not in client._base


@pytest.mark.asyncio
async def test_owner_crud_and_meaningful_fields(tiger_system):
    s = tiger_system
    result = ok(await s.task(facts()))
    assert result['result']['supplier'] == 'placeholder-supplier-result'
    rows = await s.rows()
    for field, kind in [('products', 'product'), ('seen_prices', 'seen_price'), ('suppliers', 'supplier'),
                        ('margin_rules', 'margin_rule'), ('dismissed_alerts', 'dismissed_alert')]:
        row = next(row for row in rows if row['kind'] == 'tiger.' + kind)
        assert json.loads(row['claim']) == facts()[field]
        assert ok(await s.request('GET', '/memory/' + row['id']))['id'] == row['id']
    own = next(row for row in rows if row['kind'] == 'tiger.product')
    changed = ok(await s.request('PATCH', '/memory/' + own['id'], {'value': {'name': 'placeholder-edited'}}))
    assert (await s.request('GET', '/memory/' + own['id'])).status_code == 404
    assert 'placeholder-edited' in json.dumps(ok(await s.request('GET', '/memory/' + changed['id'])))
    ok(await s.request('DELETE', '/memory/' + changed['id']))
    assert (await s.request('GET', '/memory/' + changed['id'])).status_code == 404
    assert ('POST', '/memories') in s.memory.calls and ('POST', '/recall') in s.memory.calls


@pytest.mark.asyncio
@pytest.mark.parametrize('foreign', ['same-tenant', 'other-tenant'])
async def test_foreign_owner_read_mutate_publish(tiger_system, foreign):
    s = tiger_system
    ok(await s.task(facts()))
    row = next(r for r in await s.rows() if r['kind'] == 'tiger.product')
    user, tenant = (USER_B, s.memory.tenant) if foreign == 'same-tenant' else (USER_A, s.memory.other_tenant)
    before = await s.snapshot()
    assert await s.rows(user=user, tenant=tenant) == []
    for method, path, body in [('GET', '/memory/' + row['id'], None),
                               ('PATCH', '/memory/' + row['id'], {'value': 'placeholder-attack'}),
                               ('DELETE', '/memory/' + row['id'], None),
                               ('POST', '/memory/' + row['id'] + '/publish', {})]:
        response = await s.request(method, path, body, user=user, tenant=tenant)
        assert response.status_code in (403, 404), response.text
        assert 'placeholder-product' not in response.text
        assert await s.snapshot() == before
    assert len(s.sends) == 1


@pytest.mark.asyncio
async def test_declared_heartbeat_only_and_personal_owner(tiger_system):
    from hermes.user_scope import TENANT_WIDE_KINDS
    s = tiger_system
    assert TENANT_WIDE_KINDS['tiger'] == frozenset({'heartbeat'})
    # These are service/adversarial seeds, not signed-in-user proof. Visibility
    # and denied mutations enter the actual authenticated product routes below.
    client = s.memory.client(USER_A)
    shared = await client.remember(s.memory.tenant, 'placeholder-heartbeat', 'heartbeat',
                                   'placeholder-fixture', tenant_wide=True)
    personal = await client.remember(s.memory.tenant, 'placeholder-personal-heartbeat',
                                     'heartbeat', 'placeholder-fixture')
    assert {r['id'] for r in await s.rows()} == {shared['id'], personal['id']}
    assert {r['id'] for r in await s.rows(USER_B)} == {shared['id']}
    assert await s.rows(tenant=s.memory.other_tenant) == []
    before = await s.snapshot()
    assert (await s.request('DELETE', '/memory/' + shared['id'])).status_code == 403
    assert await s.snapshot() == before
    with pytest.raises(ValueError):
        await client.remember(s.memory.tenant, 'placeholder-unowned', 'tiger.product',
                              'placeholder-fixture', tenant_wide=True, user_id=USER_A)
    response = await s.memory.http.post('/memories', headers={'X-Tank-Key': KEY}, json={
        'tenant_id': s.memory.tenant, 'kind': 'tiger.product', 'text': 'placeholder-unowned',
        'source': 'placeholder-fixture', 'meta': {'tenant_wide': True}})
    assert response.status_code in (400, 401, 422)
    assert await s.snapshot() == before


@pytest.mark.asyncio
async def test_signed_actor_and_body_impersonation(tiger_system):
    s = tiger_system
    ok(await s.task())
    assert s.issuer.calls, 'OIDC discovery/JWK signature verification must run'
    before = await s.snapshot()
    for field, value in [('user_id', USER_B), ('tenant_id', s.memory.other_tenant), ('role', 'founder')]:
        response = await s.request('POST', '/brain/tasks', {
            'task_key': 'tiger.supplier', 'input': facts(), field: value})
        assert response.status_code == 403
        assert await s.snapshot() == before
    headers = s.headers()
    headers['X-Tervory-User'] = USER_B
    assert (await s.request('GET', '/memory', headers=headers)).status_code == 403
    headers = s.headers()
    headers['X-Tervory-Tenant'] = s.memory.other_tenant
    assert (await s.request('GET', '/memory', headers=headers)).status_code == 403
    headers = s.headers()
    headers.pop('x-trigger-signin-token')
    assert (await s.request('GET', '/memory', headers=headers)).status_code in (401, 403)
    assert await s.snapshot() == before and len(s.sends) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['missing', 'key', 'audience', 'tenant', 'method', 'target', 'body', 'expired', 'future'])
async def test_assertion_rejection(tiger_system, fault):
    from chassis.user_assertion import SignedUser, sign_assertion
    s = tiger_system
    target = '/memory/setting?tenant_id=' + s.memory.tenant + '&user_id=' + USER_A
    body = b'{"enabled":false}'
    actor = SignedUser(s.memory.other_tenant if fault == 'tenant' else s.memory.tenant, USER_A, 'member')
    token = sign_assertion('base' if fault == 'audience' else 'tiger', actor,
        'GET' if fault == 'method' else 'POST', target + '&placeholder=1' if fault == 'target' else target,
        b'{}' if fault == 'body' else body, key='placeholder-wrong-key' if fault == 'key' else KEY,
        now=int(time.time()) + (120 if fault == 'future' else -120 if fault == 'expired' else 0))
    before = await s.snapshot()
    calls = len(s.memory.calls)
    response = await s.direct.post(target, content=body,
        headers={'X-Tervory-User-Assertion': '' if fault == 'missing' else token})
    assert response.status_code == 401, response.text
    assert await s.snapshot() == before and len(s.memory.calls) == calls and not s.sends


@pytest.mark.asyncio
async def test_nonce_replay_concurrent_restart_and_forget(tiger_system):
    from chassis.user_assertion import SignedUser, sign_assertion
    s = tiger_system
    ok(await s.task())
    request = next(r for r in s.assertions if r.url.path == '/brain/tasks')
    row = next(r for r in await s.rows() if r['kind'] == 'tiger.outcome')
    ok(await s.request('DELETE', '/memory/' + row['id']))
    before = await s.snapshot()
    s.restart_nonces()  # New worker instances, same durable Postgres nonce store.
    async def replay():
        return await s.direct.request(request.method, str(request.url), content=request.content,
                                      headers=dict(request.headers))
    responses = await asyncio.gather(replay(), replay())
    assert [r.status_code for r in responses] == [401, 401]
    assert await s.snapshot() == before and len(s.sends) == 1
    target = '/memory?tenant_id=' + s.memory.tenant + '&user_id=' + USER_A
    token = sign_assertion('tiger', SignedUser(s.memory.tenant, USER_A, 'member'),
                           'GET', target, b'', key=KEY)
    async def first_use():
        return await s.direct.get(target, headers={'X-Tervory-User-Assertion': token})
    assert sorted(r.status_code for r in await asyncio.gather(first_use(), first_use())) == [200, 401]
    s.restart_nonces()
    assert (await first_use()).status_code == 401


@pytest.mark.asyncio
async def test_sql_candidates_before_vector_and_limit(tiger_system, monkeypatch):
    s = tiger_system
    mine = await s.memory.client(USER_A).remember(s.memory.tenant, 'placeholder-mine', 'tiger.product', 'placeholder-seed')
    foreign = []
    for user, tenant in [(USER_B, s.memory.tenant), (USER_A, s.memory.other_tenant)]:
        foreign.append(await s.memory.client(user).remember(tenant, 'placeholder-foreign', 'tiger.product', 'placeholder-seed'))
    original = s.memory.records.index.search
    calls = []
    def observed(*args, **kwargs):
        calls.append(kwargs['allowed_ids'])
        assert not {r['id'] for r in foreign} & set(kwargs['allowed_ids'])
        return original(*args, **kwargs)
    monkeypatch.setattr(s.memory.records.index, 'search', observed)
    ok(await s.task())
    assert calls and any(mine['id'] in ids for ids in calls)
    assert 'placeholder-foreign' not in s.sends[0].content.decode()
    searched = len(calls)
    ok(await s.task(user='placeholder-empty-user'))
    assert len(calls) == searched, 'An empty SQL scope must not search global vectors'
    assert 'placeholder-foreign' not in s.sends[-1].content.decode()
    assert 'placeholder-mine' not in s.sends[-1].content.decode()


@pytest.mark.asyncio
async def test_restricted_database_role_and_nonce_rls(tiger_system):
    import asyncpg
    from urllib.parse import urlsplit
    from chassis.user_assertion import PostgresNonces
    s = tiger_system
    schema = s.memory.records.schema('tiger')
    role = 'placeholder_tiger_' + uuid4().hex[:12]
    pool = s.memory.records.pool
    async with pool.acquire() as conn:
        await conn.execute(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS')
        await conn.execute(f'GRANT USAGE, CREATE ON SCHEMA {schema} TO {role}')
        await conn.execute(f'GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO {role}')
        # Exercise the existing staged RLS guard, not a new rollout decision.
        await conn.execute(f'CREATE TABLE {schema}.jobs(id uuid); ALTER TABLE {schema}.jobs ENABLE ROW LEVEL SECURITY')
    store = PostgresNonces(pool, 'tiger')
    store.schema = schema
    await store.setup()
    async with pool.acquire() as conn:
        await conn.execute(f'ALTER TABLE {schema}.user_assertion_nonces OWNER TO {role}')
        dsn = conn._params
        # Existing loopback fixture connection parameters, no credentials printed.
        assert dsn.database and urlsplit(__import__('os').environ['MEMORY_TEST_DATABASE_URL']).hostname in ('127.0.0.1', 'localhost', '::1')
    restricted = await asyncpg.create_pool(__import__('os').environ['MEMORY_TEST_DATABASE_URL'],
        min_size=1, max_size=2, server_settings={'role': role})
    old = s.memory.records.pool
    try:
        s.memory.records.pool = restricted
        for app in (s.room, s.brain):
            app.state.pool = restricted
        s.restart_nonces()
        async with restricted.acquire() as conn:
            info = await conn.fetchrow('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
            assert not info['rolsuper'] and not info['rolbypassrls']
            assert await conn.fetchval('SELECT relrowsecurity FROM pg_class WHERE oid=$1::regclass', schema + '.user_assertion_nonces')
        ok(await s.task())
        assert await s.rows() and await s.rows(USER_B) == []
    finally:
        s.memory.records.pool = old
        await restricted.close()
        async with pool.acquire() as conn:
            await conn.execute(f'ALTER TABLE {schema}.user_assertion_nonces OWNER TO CURRENT_USER')
            await conn.execute(f'DROP OWNED BY {role}; DROP ROLE {role}')


@pytest.mark.asyncio
async def test_default_off_and_unauthenticated_plain_free_path(tiger_system, monkeypatch):
    s = tiger_system
    monkeypatch.delenv('TIGER_BRAIN_ENABLED')
    before = await s.snapshot()
    schedules = list(s.room.state.schedules)
    calls = len(s.memory.calls)
    result = ok(await s.task({'price': 20, 'cost': 15}, task='tiger.margin'))
    assert result['result'] == {'margin': .25}
    assert result['paid_calls'] == 0 and result['receipt']['memory'] == 'off'
    assert len(s.memory.calls) == calls and await s.snapshot() == before and not s.sends
    assert (await s.direct.get('/memory', params={'tenant_id': s.memory.tenant, 'user_id': USER_A})).status_code == 401
    # Existing service-authorised pure-code action still runs without a human
    # assertion, while personal memory above is refused.
    assert (await s.direct.get('/gold/candidates', params={'limit': 1},
                               headers={'X-Tank-Key': KEY})).status_code == 200
    assert list(s.room.state.schedules) == schedules
    assert len(s.memory.calls) == calls and not s.sends
    config = yaml.safe_load((ROOT / 'agents/tiger/docker-compose.yml').read_text())['services']
    assert config['agent-tiger']['environment']['TIGER_BRAIN_ENABLED'] == '${TIGER_BRAIN_ENABLED:-false}'
    assert config['tiger-brain']['profiles'] == config['tiger-sandbox']['profiles'] == ['brain']


@pytest.mark.asyncio
async def test_task_path_receipts_exact_repeat_and_misses(tiger_system):
    s = tiger_system
    first = ok(await s.task(facts()))
    repeat = ok(await s.task(facts()))  # Fresh request + run ID; business exact hit.
    changed = ok(await s.task({**facts(), 'sku': 'placeholder-new-sku'}))
    assert [(r['cost_usd'], r['tokens_in'], r['tokens_out'], r['paid_calls']) for r in (first, repeat, changed)] == [(.01, 10, 5, 1), (0., 0, 0, 0), (.01, 10, 5, 1)]
    assert repeat['answered_from_memory'] and repeat['receipt']['would_have_cost'] == .01
    assert repeat['receipt']['source_receipt'] == first['receipt']['ledger_id']
    assert len(s.sends) == 2
    ok(await s.task(facts(), user=USER_B))
    ok(await s.task(facts(), tenant=s.memory.other_tenant))
    assert len(s.sends) == 4
    rows = await s.ledger()
    assert len(rows) == 4 and sum(float(r['cost_usd']) for r in rows) == .04
    assert sum(r['tokens_in'] for r in rows) == 40 and sum(r['tokens_out'] for r in rows) == 20
    events = s.events
    recall = next(i for i, e in enumerate(events) if e == ('POST', 'hermes', '/recall'))
    brain = next(i for i, e in enumerate(events) if e[1:] == ('tiger-brain', '/tasks'))
    tank = next(i for i, e in enumerate(events) if e[2] == s.chat_path)
    provider = next(i for i, e in enumerate(events) if e[1] == 'placeholder-model')
    remember = next(i for i, e in enumerate(events) if e == ('POST', 'hermes', '/memories'))
    assert recall < brain < tank < provider < remember
    print('FIXTURE first: cost=0.01 tokens=10/5 provider_calls=1; exact-repeat: cost=0 tokens=0/0 provider_calls=0; changed-input: cost=0.01 tokens=10/5 provider_calls=1')


@pytest.mark.asyncio
async def test_code_first_and_ineligible_task_reuse(tiger_system):
    s = tiger_system
    result = ok(await s.task({'price': 20, 'cost': 15}, task='tiger.margin'))
    assert result['result'] == {'margin': .25} and not s.sends
    for _ in range(2):
        result = ok(await s.task({'url': 'https://placeholder.example/live'}, task='tiger.live_price'))
        assert not result['answered_from_memory'], 'Live prices must never reuse a remembered answer'
    assert len(s.sends) == 2


@pytest.mark.asyncio
async def test_correction_and_forget_invalidate_derived_answers(tiger_system):
    s = tiger_system
    payload = facts()
    ok(await s.task(payload))
    correction = ok(await s.request('POST', '/memory/correction', {'task_key': 'tiger.supplier', 'input': payload,
                                                                 'result': {'supplier': 'placeholder-corrected'}}))
    assert ok(await s.task(payload))['result'] == {'supplier': 'placeholder-corrected'}
    assert not ok(await s.task(payload, user=USER_B))['answered_from_memory']
    ok(await s.request('DELETE', '/memory/' + correction['id']))
    assert not ok(await s.task(payload))['answered_from_memory']
    row = next(r for r in await s.rows() if r['kind'] == 'tiger.product')
    ok(await s.request('DELETE', '/memory/' + row['id']))
    assert not ok(await s.task(payload))['answered_from_memory'], 'Forgetting a source fact must invalidate derived answers'


@pytest.mark.asyncio
async def test_memory_off_is_per_owner(tiger_system):
    s = tiger_system
    ok(await s.task())
    ok(await s.task(user=USER_B))
    ok(await s.request('POST', '/memory/setting', {'enabled': False}))
    before = await s.snapshot()
    calls = len(s.memory.calls)
    result = ok(await s.task())
    assert not result['answered_from_memory'] and result['paid_calls'] == 1
    assert await s.snapshot() != before  # One new actual Tank receipt, no new memory.
    assert (await s.snapshot())[0] == before[0]
    assert ('POST', '/recall') not in s.memory.calls[calls:]
    assert ('POST', '/memories') not in s.memory.calls[calls:]
    assert ok(await s.task(user=USER_B))['answered_from_memory']


@pytest.mark.asyncio
@pytest.mark.parametrize('boundary', ['list', 'recall', 'remember'])
async def test_outage_truth_and_no_repayment(tiger_system, boundary):
    s = tiger_system
    target = {'list': ('GET', '/records'), 'recall': ('POST', '/recall'), 'remember': ('POST', '/memories')}[boundary]
    s.outage = lambda request: 503 if (request.method, request.url.path) == target else None
    run = str(uuid4())
    first = ok(await s.task(run_id=run))
    assert first['receipt']['memory'] == 'memory unavailable' and len(s.sends) == 1
    s.restart_nonces()
    s.outage = None
    retry = await s.task(run_id=run)
    assert retry.status_code in (200, 409), retry.text
    assert len(s.sends) == 1, 'Remember/storage failure must not repeat a paid dispatch'
    assert len(await s.ledger()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [401, 403])
async def test_scope_errors_never_become_outage(tiger_system, status):
    s = tiger_system
    ok(await s.task())
    before = await s.snapshot()
    s.outage = lambda request: status
    response = await s.task()
    assert response.status_code == 403
    assert len(s.sends) == 1 and await s.snapshot() == before
    assert 'placeholder-supplier-result' not in response.text


@pytest.mark.asyncio
async def test_retry_concurrency_and_no_content_leak(tiger_system, caplog):
    s = tiger_system
    run = str(uuid4())
    responses = await asyncio.gather(s.task(run_id=run), s.task(run_id=run))
    assert all(r.status_code in (200, 409) for r in responses)
    assert any(r.status_code == 200 for r in responses)
    assert len(s.sends) == 1 and len(await s.ledger()) == 1
    own = await s.snapshot()
    other = ok(await s.task({'sku': 'placeholder-other-owner-sku'}, user=USER_B))
    assert other['receipt']['tenant_id'] == s.memory.tenant
    assert len(s.sends) == 2
    assert 'placeholder-product' not in json.dumps(other)
    assert KEY not in caplog.text and 'placeholder-model-key' not in caplog.text
    # Secrets are refused before memory or paid HTTP, and never echoed.
    response = await s.task({'api_key': 'placeholder-secret-value'})
    assert response.status_code in (403, 422)
    assert len(s.sends) == 2
    assert 'placeholder-secret-value' not in response.text + caplog.text
    assert own[0]


def test_original_reader_ocr_and_brain_regressions(gate78_database):
    import subprocess
    import sys
    # Run the original shipped tests unmodified. Their failures/skips remain
    # failures here; this wrapper does not replace browser/OCR/room coverage.
    targets = ['tests/tiger_brain/test_tg3.py', 'tests/tiger_price_read', 'tests/test_tiger_works.py',
               'tests/test_tiger_price_structured.py', 'tests/tiger_playbooks']
    env = dict(os.environ, POOL_SCHEMA_DATABASE_URL=gate78_database,
               TIGER_MAIL_TEST_DATABASE_URL=gate78_database)
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-rs', '--disable-socket',
        '--allow-unix-socket', '--allow-hosts=127.0.0.1,localhost,::1', '--timeout=90', *targets],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=150)
    print(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ' skipped' not in result.stdout and ' xfailed' not in result.stdout
