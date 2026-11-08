"""Trigger acceptance through real sign-in, product handlers and Hermes storage."""
import asyncio
import json
from uuid import UUID, uuid4
from decimal import Decimal

import pytest

from trigger_gate78_stack import trigger_stack as trigger_stack_fixture, control, write, rows, signed_request, headers, ROOT, USER_A, USER_B, COST, TOKENS

trigger_stack = trigger_stack_fixture


@pytest.mark.asyncio
async def test_owner_controls_use_real_hermes(trigger_stack):
    b = trigger_stack
    saved = await control(b, 'edit', body={'text': 'placeholder owner preference', 'kind': 'trigger.tone', 'source': 'urn:placeholder:owner'})
    assert saved.status_code == 200, saved.text
    row = saved.json()['memory']
    listed = await control(b)
    assert listed.status_code == 200 and row['id'] in {r['id'] for r in listed.json()['memories']}
    assert ('GET', '/records') in b.stack.calls and ('POST', '/memories') in b.stack.calls
    forgotten = await control(b, 'forget', body={'memory_id': row['id']})
    assert forgotten.status_code == 200, forgotten.text
    assert row['id'] not in {r['id'] for r in (await control(b)).json()['memories']}


@pytest.mark.asyncio
async def test_first_repeat_changed_input_receipts_and_provider_counts(trigger_stack):
    b = trigger_stack
    first = (await write(b))['result']
    first_calls = len(b.net.providers)
    repeated = (await write(b))['result']
    repeat_calls = len(b.net.providers) - first_calls
    changed = (await write(b, 'Describe the placeholder product in detail.'))['result']
    changed_calls = len(b.net.providers) - first_calls - repeat_calls
    (ROOT / '.tmp/trigger-gate78-fixture-costs.json').write_text(json.dumps({
        'fixture_only': True, 'runs': {name: {'cost_usd': item['cost_usd'], 'tokens_in': item['tokens_in'],
            'tokens_out': item['tokens_out']} for name, item in [('first', first), ('exact_repeat', repeated), ('changed_input', changed)]},
        'provider_calls_per_run': dict(first=first_calls, exact_repeat=repeat_calls, changed_input=changed_calls),
        'captured_provider_calls': len(b.net.providers)}, indent=2))
    assert first['cost_usd'] == changed['cost_usd'] == COST
    assert (first['tokens_in'], first['tokens_out']) == TOKENS
    assert repeated['cost_usd'] == repeated['tokens_in'] == repeated['tokens_out'] == 0, (first.get('memory_receipt'), repeated.get('memory_receipt'))
    assert repeated['memory_receipt']['would_have_cost']['cost_usd'] == COST
    assert len(b.net.providers) == 2
    assert (first_calls, repeat_calls, changed_calls) == (1, 0, 1)


@pytest.mark.asyncio
async def test_shared_fixture_preserves_product_agent_for_owner_recall(trigger_stack):
    b = trigger_stack
    saved = await control(b, 'edit', body={'text': 'placeholder exact owner recall', 'kind': 'trigger.tone', 'source': 'urn:placeholder:recall'})
    assert saved.status_code == 200, saved.text
    own = await b.stack.client(USER_A).recall(b.tenant, 'placeholder exact owner recall')
    assert saved.json()['memory']['id'] in {r['id'] for r in own}, {
        'rows': await rows(b), 'collections': [c.name for c in b.stack.records.index.client.get_collections().collections]}


@pytest.mark.asyncio
@pytest.mark.parametrize('foreign', ['user', 'tenant'])
async def test_foreign_users_cannot_read_or_mutate_personal_records(trigger_stack, foreign, caplog):
    b = trigger_stack
    saved = await control(b, 'edit', body={'text': 'placeholder private owner content', 'kind': 'trigger.tone', 'source': 'urn:placeholder:private'})
    assert saved.status_code == 200
    ident = saved.json()['memory']['id']
    who = {'user': USER_B} if foreign == 'user' else {'tenant': b.other}
    before = await rows(b)
    listed = await control(b, **who)
    assert listed.status_code == 200 and listed.json()['memories'] == []
    for op, body in [('edit', {'memory_id': ident, 'kind': 'trigger.tone', 'text': 'placeholder tamper', 'source': 'urn:placeholder:tamper'}),
                     ('forget', {'memory_id': ident})]:
        response = await control(b, op, body=body, **who)
        assert response.status_code == 403 and await rows(b) == before
    spoofed = await control(b, 'edit', body={'kind': 'trigger.tone', 'text': 'placeholder tamper',
        'source': 'urn:placeholder:tamper', 'user_id': USER_A}, user=USER_B)
    assert spoofed.status_code == 403 and await rows(b) == before
    exposed = listed.text + caplog.text
    assert 'placeholder private owner content' not in exposed
    assert not b.net.providers


@pytest.mark.asyncio
async def test_no_tenant_wide_kind_or_unverified_owner_is_invented(trigger_stack):
    from hermes.user_scope import TENANT_WIDE_KINDS
    b = trigger_stack
    assert TENANT_WIDE_KINDS['trigger'] == frozenset()
    before = await rows(b)
    for kind in ('trigger.tone', 'trigger.receipt', 'heartbeat'):
        response = await b.stack.http.post('/memories', json={'tenant_id': b.tenant,
            'text': 'placeholder unowned', 'kind': kind, 'source': 'urn:placeholder:unowned', 'meta': {'scope': 'tenant'}},
            headers={'X-Tank-Key': b.key})
        assert response.status_code in {401, 422}, response.text
    response = await control(b, 'edit', body={'text': 'placeholder no widening', 'kind': 'trigger.tone',
        'source': 'urn:placeholder:unowned', 'meta': {'scope': 'tenant'}})
    assert response.status_code == 422 and await rows(b) == before


@pytest.mark.asyncio
async def test_signin_verification_refuses_body_and_header_impersonation(trigger_stack):
    b = trigger_stack
    good = headers(b)
    assert (await b.front.get('/v1/command/tools', headers=good)).status_code == 200
    assert b.provider.calls
    for updates in ({'X-Tervory-User': USER_B}, {'X-Tervory-Tenant': b.other},
                    {'x-trigger-signin-token': 'placeholder-invalid-token'}, {'X-Tervory-Role': 'founder'}):
        response = await b.front.get('/v1/command/tools', headers={**good, **updates})
        assert response.status_code in {401, 403}
    assert not b.net.forwarded and not b.net.providers and not await rows(b)


@pytest.mark.asyncio
@pytest.mark.parametrize('flaw', ['key', 'audience', 'tenant', 'method', 'target', 'body', 'expired', 'future', 'missing'])
async def test_product_assertions_reject_tampering_without_mutation(trigger_stack, flaw):
    import time
    import product_identity
    b = trigger_stack
    body = {'tenant_id': b.tenant, 'text': 'placeholder asserted owner', 'kind': 'trigger.tone', 'source': 'urn:placeholder:asserted'}
    changes = {'key': {'key': 'placeholder-wrong-key'}, 'audience': {'product': 'opli'},
        'tenant': {'user': product_identity.User(b.other, USER_A, 'member')}, 'method': {'method': 'DELETE'},
        'target': {'target': '/memory/switch'}, 'body': {'body': b'placeholder-tampered'},
        'expired': {'now': int(time.time()) - 61}, 'future': {'now': int(time.time()) + 61}, 'missing': {}}[flaw]
    request = await signed_request(b, 'POST', '/memory/edit', body=body, overrides=changes)
    if flaw == 'missing':
        del request.headers[product_identity.HEADER]
    response = await b.http.send(request)
    assert response.status_code == 401 and not await rows(b) and not b.net.providers


@pytest.mark.asyncio
async def test_concurrent_and_restarted_product_workers_reject_replay(trigger_stack):
    from chassis.user_assertion import PostgresNonces
    b = trigger_stack
    body = {'tenant_id': b.tenant, 'text': 'placeholder nonce record', 'kind': 'trigger.tone', 'source': 'urn:placeholder:nonce'}
    request = await signed_request(b, 'POST', '/memory/edit', body=body, overrides={'nonce': 'placeholder-trigger-replay-' + uuid4().hex})
    args = dict(method=request.method, url=str(request.url), headers=dict(request.headers), content=request.content)
    first, second = await asyncio.gather(b.http.request(**args), b.http.request(**args))
    assert sorted([first.status_code, second.status_code]) == [200, 401]
    assert len(await rows(b)) == 1
    b.room.app.state.product_nonce_stores = {'trigger': PostgresNonces(b.pool, 'trigger')}
    restarted = await b.http.request(**args)
    assert restarted.status_code == 401 and len(await rows(b)) == 1


@pytest.mark.asyncio
async def test_sql_owner_candidates_precede_vector_search_and_limit(trigger_stack, monkeypatch):
    b = trigger_stack
    for user, text in ((USER_A, 'placeholder own'), (USER_B, 'placeholder foreign one'), (USER_B, 'placeholder foreign two')):
        response = await control(b, 'edit', user=user, body={'text': text, 'kind': 'trigger.tone', 'source': 'urn:placeholder:sql'})
        assert response.status_code == 200
    own = (await control(b)).json()['memories']
    seen = []
    original = b.stack.records.index.search
    def observed(*args, **kwargs):
        seen.append(kwargs['allowed_ids'])
        assert set(kwargs['allowed_ids']) == {r['id'] for r in own}
        return original(*args, **kwargs)
    monkeypatch.setattr(b.stack.records.index, 'search', observed)
    await write(b)
    assert len(seen) == 1
    assert await b.stack.client('placeholder-empty-user').recall(b.tenant, 'placeholder own', limit=1) == []
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_restricted_database_role_uses_product_schema_and_ownership(trigger_stack):
    b = trigger_stack
    import asyncpg
    from contextlib import asynccontextmanager
    role = b.stack.records.schema('trigger')
    saved = await control(b, 'edit', body={'kind': 'trigger.tone', 'text': 'placeholder restricted owner', 'source': 'urn:placeholder:role'})
    assert saved.status_code == 200
    await b.pool.execute('CREATE ROLE ' + role + ' NOLOGIN NOSUPERUSER NOBYPASSRLS')
    await b.pool.execute('GRANT USAGE,CREATE ON SCHEMA ' + role + ' TO ' + role)
    await b.pool.execute('GRANT SELECT ON ALL TABLES IN SCHEMA ' + role + ' TO ' + role)
    await b.pool.execute('GRANT SELECT,INSERT,DELETE ON ' + role + '.user_assertion_nonces TO ' + role)
    observed = []
    class RestrictedPool:
        @asynccontextmanager
        async def acquire(self):
            async with b.pool.acquire() as conn, conn.transaction():
                await conn.execute('SET LOCAL ROLE ' + role)
                observed.append(await conn.fetchval('SELECT current_user'))
                assert not await conn.fetchval('SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user')
                yield conn
    original = b.stack.records.pool
    b.stack.records.pool = RestrictedPool()
    try:
        own = await control(b)
        assert own.status_code == 200 and saved.json()['memory']['id'] in {row['id'] for row in own.json()['memories']}
        foreign = await control(b, user=USER_B)
        assert foreign.status_code == 200 and foreign.json()['memories'] == []
        assert observed and set(observed) == {role}
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            async with b.stack.records.pool.acquire() as conn:
                await conn.fetch('SELECT * FROM tank.ledger')
    finally:
        b.stack.records.pool = original
        await b.pool.execute('DROP OWNED BY ' + role)
        await b.pool.execute('DROP ROLE ' + role)



@pytest.mark.asyncio
async def test_plain_write_runs_without_identity_but_memory_controls_refuse(trigger_stack):
    b = trigger_stack
    before = len(b.net.providers)
    response = await b.http.post('http://agent-trigger:8000/write', headers={'X-Tank-Key': b.key},
                                 json={'tenant_id': b.tenant, 'user_id': 'placeholder-spoofed-user', 'text': 'Describe a placeholder product.'})
    assert response.status_code == 200, response.text
    assert len(b.net.providers) == before + 1 and not await rows(b)
    for path, method in (('/memory/records?tenant_id=' + b.tenant, 'GET'), ('/memory/edit', 'POST'),
                         ('/memory/forget', 'POST'), ('/memory/switch', 'POST')):
        response = await b.http.request(method, 'http://agent-trigger:8000' + path,
            headers={'X-Tank-Key': b.key}, json={'tenant_id': b.tenant, 'memory_id': str(uuid4()), 'enabled': False,
                'text': 'placeholder rejected', 'kind': 'trigger.tone', 'source': 'urn:placeholder:unsigned'})
        assert response.status_code == 401 and not await rows(b)


@pytest.mark.asyncio
async def test_default_off_preserves_original_write_and_opt_in_profiles(trigger_stack, monkeypatch):
    import yaml
    from trigger import gates_memory, trigger_brain
    b = trigger_stack
    for name in ('TRIGGER_MEMORY_ENABLED', 'TRIGGER_BRAIN_ENABLED', 'TRIGGER_BRAIN_URL'):
        monkeypatch.delenv(name, raising=False)
    assert not gates_memory.memory_enabled() and not trigger_brain.brain_enabled()
    first = (await write(b))['result']
    assert first['cost_usd'] == COST and not await rows(b)
    assert not [item for item in b.net.calls if item[0] == 'hermes']
    services = yaml.safe_load((ROOT / 'agents/trigger/docker-compose.yml').read_text())['services']
    for name, service in services.items():
        if 'brain' in name:
            assert service.get('profiles')


@pytest.mark.asyncio
async def test_paid_write_recall_execute_receipt_remember_order_and_meaningful_fields(trigger_stack):
    b = trigger_stack
    result = (await write(b))['result']
    assert result['cost_usd'] == COST and (result['tokens_in'], result['tokens_out']) == TOKENS
    calls = b.net.calls
    recall = next(i for i, item in enumerate(calls) if item[:2] == ('hermes', 'POST') and item[2] == '/recall')
    provider = next(i for i, item in enumerate(calls) if item[0] == 'placeholder-gateway' and item[2] == '/v1/chat/completions')
    remember = next(i for i, item in enumerate(calls) if item == ('hermes', 'POST', '/memories'))
    assert recall < provider < remember
    saved = (await control(b)).json()['memories']
    assert len(saved) == 1 and saved[0]['meta']['user_id'] == USER_A
    assert saved[0]['meta']['outcome']['conversation_context']
    assert 'Describe the placeholder product.' in saved[0]['meta']['outcome']['conversation_context']
    receipt = await b.pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2', UUID(result['ledger_id']), UUID(b.tenant))
    assert receipt['cost_usd'] == Decimal(str(COST)) and (receipt['tokens_in'], receipt['tokens_out']) == TOKENS
    assert b.net.forwarded and b.net.forwarded[0].headers.get('X-Tervory-User-Assertion')
    import base64
    encoded = b.net.forwarded[0].headers['X-Tervory-User-Assertion'].split('.')[0]
    bound = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
    assert (bound['aud'], bound['tenant_id'], bound['user_id'], bound['role'], bound['method'], bound['target']) == (
        'trigger', b.tenant, USER_A, 'founder', 'POST', '/write')


@pytest.mark.asyncio
async def test_other_user_tenant_and_changed_input_miss_real_provider_cache(trigger_stack):
    b = trigger_stack
    for changes in ({}, {'user': USER_B}, {'tenant': b.other}, {'text': 'A changed placeholder request.'}):
        result = (await write(b, **changes))['result']
        assert result['cost_usd'] == COST
    assert len(b.net.providers) == 4
    assert [r['meta']['user_id'] for r in await rows(b)].count(USER_A) == 3


@pytest.mark.asyncio
async def test_owner_correction_changes_next_answer_only_for_owner(trigger_stack):
    b = trigger_stack
    correction = await control(b, 'edit', body={'kind': 'trigger.correction', 'text': 'correction=Use the placeholder corrected answer.',
        'source': 'urn:placeholder:correction'})
    assert correction.status_code == 200
    corrected = (await write(b))['result']
    assert 'placeholder corrected answer' in corrected['text'] and corrected['cost_usd'] == 0
    foreign = (await write(b, user=USER_B))['result']
    assert 'placeholder corrected answer' not in foreign['text'] and foreign['cost_usd'] == COST


@pytest.mark.asyncio
async def test_forget_invalidates_reusable_outcome_and_replay_cannot_restore(trigger_stack):
    b = trigger_stack
    first = (await write(b))['result']
    stored = (await control(b)).json()['memories']
    assert len(stored) == 1
    forgotten = await control(b, 'forget', body={'memory_id': stored[0]['id']})
    assert forgotten.status_code == 200 and not await rows(b)
    repeated = (await write(b))['result']
    assert repeated['cost_usd'] == first['cost_usd'] == COST and len(b.net.providers) == 2


@pytest.mark.asyncio
async def test_memory_switch_is_per_owner_and_reenable_deletes_only_own_switch(trigger_stack):
    b = trigger_stack
    disabled = await control(b, 'switch', body={'enabled': False})
    assert disabled.status_code == 200
    before = len(await rows(b))
    start = len(b.net.calls)
    result = (await write(b))['result']
    assert result['cost_usd'] == COST and len(await rows(b)) == before
    assert not [call for call in b.net.calls[start:] if call[0] == 'hermes' and call[1] == 'POST']
    assert (await control(b)).json()['memory_enabled'] is False
    other = (await write(b, user=USER_B))['result']
    assert other['memory_receipt']['memory_enabled'] is True
    response = await control(b, 'switch', body={'enabled': True})
    assert response.status_code == 200 and (await control(b)).json()['memory_enabled'] is True


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [('GET', '/records'), ('POST', '/recall'), ('POST', '/memories')])
async def test_outages_are_truthful_and_never_repeat_paid_writing(trigger_stack, failure):
    b = trigger_stack
    b.net.failure = failure
    card = await write(b)
    result = card['result']
    assert result['cost_usd'] == COST and result.get('memory_unavailable', result.get('memory_receipt', {}).get('memory_unavailable'))
    assert len(b.net.providers) == 1
    retried = await write(b, retry=card['card_id'])
    assert retried['result'] == result and len(b.net.providers) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [401, 403])
async def test_memory_auth_failures_are_not_storage_outages(trigger_stack, status):
    b = trigger_stack
    b.net.failure, b.net.body_status = ('GET', '/records'), status
    card = await write(b, allow_failure=True)
    assert card['status'] == 'failed', 'Authentication refusal must fail closed before paid work'
    assert not b.net.providers and not await rows(b)
    assert 'placeholder private' not in json.dumps(card)



@pytest.mark.asyncio
async def test_retry_concurrency_and_foreign_card_preserve_single_payment(trigger_stack):
    b = trigger_stack
    card = await write(b)
    results = await asyncio.gather(write(b, retry=card['card_id']), write(b, retry=card['card_id']))
    assert all(item['result'] == card['result'] for item in results) and len(b.net.providers) == 1
    foreign = await b.front.post('/v1/command/cards/' + card['card_id'], headers=headers(b, USER_B), json={'action': 'confirm'})
    assert foreign.status_code == 404 and len(b.net.providers) == 1


@pytest.mark.asyncio
async def test_free_check_and_voice_and_language_paths_make_no_provider_calls(trigger_stack):
    b = trigger_stack
    for path, payload in (('/check', {'text': 'A placeholder clear sentence.'}),
                          ('/voice/show', {}), ('/skala/languagetool', {'text': 'A placeholder sentence.'})):
        response = await b.http.post('http://agent-trigger:8000' + path, headers={'X-Tank-Key': b.key},
                                     json={'tenant_id': b.tenant, **payload})
        assert response.status_code == 200, response.text
    assert not b.net.providers and not await rows(b)


@pytest.mark.asyncio
async def test_foreign_content_and_secrets_do_not_enter_receipts_or_logs(trigger_stack, caplog):
    b = trigger_stack
    private = 'placeholder private foreign content'
    response = await control(b, 'edit', user=USER_B, body={'kind': 'trigger.tone', 'text': private, 'source': 'urn:placeholder:private'})
    assert response.status_code == 200
    own = (await write(b))['result']
    assert private not in json.dumps(own) + json.dumps(b.net.providers) + caplog.text
    response = await control(b, 'edit', body={'kind': 'trigger.tone', 'text': 'password=placeholder-secret', 'source': 'urn:placeholder:secret'})
    assert response.status_code == 422
    assert 'password=placeholder-secret' not in json.dumps(await rows(b))


@pytest.mark.asyncio
async def test_remembered_contact_categories_are_meaningful_and_recall_is_bounded(trigger_stack):
    b = trigger_stack
    text = 'deal=placeholder deal;context=placeholder conversation;objections=placeholder objection;tone=placeholder calm;handover=placeholder follow-up'
    saved = await control(b, 'edit', body={'kind': 'trigger.tone', 'text': text, 'source': 'urn:placeholder:categories'})
    assert saved.status_code == 200
    result = (await write(b))['result']
    receipt = result['memory_receipt']
    recall = next(step for step in receipt['steps'] if step['action'] == 'recall')
    assert recall['count'] >= 1
    capped = next(step for step in receipt['steps'] if step['action'] == 'recall_cap')
    assert 0 < capped['memory_context_tokens'] <= capped['budget'] and not capped['billed']
    remembered_id = next(step['memory_id'] for step in receipt['steps'] if step['action'] == 'remember')
    remembered = next(row for row in (await control(b)).json()['memories'] if row['id'] == remembered_id)
    outcome = remembered['meta']['outcome']
    for name in ('deal_history', 'conversation_context', 'objections', 'tone', 'handover_notes'):
        assert outcome[name], name
    assert len(b.net.providers) == 1


@pytest.mark.asyncio
async def test_forgetting_original_invalidates_any_derived_repeat(trigger_stack):
    b = trigger_stack
    original = (await write(b))['result']
    first_id = next(step['memory_id'] for step in original['memory_receipt']['steps'] if step['action'] == 'remember')
    repeat = (await write(b))['result']
    assert repeat['cost_usd'] == 0 and len(b.net.providers) == 1
    assert {row['id'] for row in await rows(b)} == {first_id}
    response = await control(b, 'forget', body={'memory_id': first_id})
    assert response.status_code == 200
    fresh = (await write(b))['result']
    assert fresh['cost_usd'] == COST and len(b.net.providers) == 2


@pytest.mark.asyncio
async def test_paid_endpoints_and_original_product_flows_remain_real(trigger_stack):
    b = trigger_stack
    paths = {route.path for route in b.room.app.routes}
    assert {'/write', '/check', '/voice/{operation}', '/skala/languagetool',
            '/memory/records', '/memory/edit', '/memory/forget', '/memory/switch'} <= paths
    # Invalid format is refused before a provider; legal work keeps the Zenas corridor.
    invalid = await b.http.post('http://agent-trigger:8000/write', headers={'X-Tank-Key': b.key},
        json={'tenant_id': b.tenant, 'text': 'placeholder request', 'format': 'placeholder invalid format'})
    assert invalid.status_code == 422 and not b.net.providers
    legal = await b.http.post('http://agent-trigger:8000/write', headers={'X-Tank-Key': b.key},
        json={'tenant_id': b.tenant, 'text': 'placeholder legal agreement', 'document_type': 'legal'})
    assert legal.status_code == 200 and legal.json()['delegate'] == 'zenas.draft' and not b.net.providers


@pytest.mark.asyncio
async def test_owner_get_single_record_and_foreign_guessed_ids(trigger_stack):
    b = trigger_stack
    saved = await control(b, 'edit', body={'kind': 'trigger.tone', 'text': 'placeholder selected record', 'source': 'urn:placeholder:get'})
    assert saved.status_code == 200
    ident = saved.json()['memory']['id']
    target = '/memory/records/' + ident + '?tenant_id=' + b.tenant
    response = await b.http.send(await signed_request(b, 'GET', target))
    assert response.status_code == 200, 'Product must support an owned selected-record read'
    for user, tenant in ((USER_B, b.tenant), (USER_A, b.other)):
        foreign_target = '/memory/records/' + ident + '?tenant_id=' + tenant
        foreign = await b.http.send(await signed_request(b, 'GET', foreign_target, user=user, tenant=tenant))
        assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_foreign_records_cannot_be_published_or_shared(trigger_stack):
    b = trigger_stack
    saved = await control(b, 'edit', body={'kind': 'trigger.tone', 'text': 'placeholder private publishing refusal', 'source': 'urn:placeholder:publish'})
    assert saved.status_code == 200
    before = await rows(b)
    for user, tenant in ((USER_B, b.tenant), (USER_A, b.other)):
        body = {'tenant_id': tenant, 'memory_id': saved.json()['memory']['id'], 'scope': 'tenant'}
        response = await b.http.send(await signed_request(b, 'POST', '/memory/publish', user=user, tenant=tenant, body=body))
        assert response.status_code in {403, 404} and await rows(b) == before


@pytest.mark.asyncio
async def test_shared_workspace_key_cannot_write_hermes(trigger_stack):
    b = trigger_stack
    response = await b.stack.http.post('/memories', headers={'X-Tank-Key': 'placeholder-workspace-key'},
        json={'tenant_id': b.tenant, 'user_id': USER_A, 'kind': 'trigger.tone', 'text': 'placeholder denied',
              'source': 'urn:placeholder:shared-key', 'meta': {'user_id': USER_A}})
    assert response.status_code in {401, 403} and not await rows(b)


@pytest.mark.asyncio
async def test_forbidden_tank_memory_base_is_never_used(trigger_stack, monkeypatch):
    b = trigger_stack
    monkeypatch.setenv('HERMES_URL', 'http://tank:8000/v1/memory')
    with pytest.raises(RuntimeError, match='must call Hermes directly'):
        async with b.room.lifespan(b.room.app):
            pytest.fail('Invalid memory base must fail during real product startup')
    assert not b.net.providers


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['Trigger.Deal', 'trigger-deal', '1trigger', 'trigger deal', 't' * 81, ''],
                         ids=['upper', 'dash', 'digit-first', 'space', 'too-long', 'empty'])
async def test_bad_kind_refused_through_product_and_real_hermes(trigger_stack, kind):
    from trigger_gate78_stack import actor
    b = trigger_stack
    await actor(b)
    response = await control(b, 'edit', body={'kind': kind, 'text': 'placeholder invalid kind', 'source': 'urn:placeholder:kind'})
    assert response.status_code == 422
    with pytest.raises(RuntimeError, match='hermes answered 422'):
        await b.stack.client(USER_A).remember(b.tenant, 'placeholder invalid kind', kind, 'urn:placeholder:kind')
    assert not await rows(b)


@pytest.mark.asyncio
async def test_trigger_key_cannot_select_another_agents_collection(trigger_stack):
    from chassis.user_assertion import bind_personal_headers
    from trigger_gate78_stack import actor
    b = trigger_stack
    await actor(b)
    body = {'tenant_id': b.tenant, 'user_id': USER_A, 'agent': 'tiger', 'kind': 'trigger.tone',
            'text': 'placeholder cross-agent refusal', 'source': 'urn:placeholder:agent', 'meta': {'user_id': USER_A}}
    raw = json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
    h = bind_personal_headers(b.key, 'POST', '/memories', tenant=b.tenant, user=USER_A, body=raw)
    response = await b.stack.http.post('/memories', content=raw, headers={**h, 'X-Tank-Key': b.key, 'Content-Type': 'application/json'})
    assert response.status_code == 403 and not await rows(b)


@pytest.mark.asyncio
@pytest.mark.parametrize('key', ['', 'placeholder-wrong-key'])
async def test_missing_and_wrong_hermes_keys_refuse_without_persistence(trigger_stack, key):
    from chassis.memory import MemoryClient
    from trigger_gate78_stack import actor
    b = trigger_stack
    await actor(b)
    memory = MemoryClient('http://hermes', key, 'trigger', b.http, user_id=USER_A)
    with pytest.raises(RuntimeError, match='tank key is not set' if not key else 'hermes answered 401'):
        await memory.remember(b.tenant, 'placeholder key refusal', 'trigger.tone', 'urn:placeholder:key')
    assert not await rows(b) and not b.net.providers


@pytest.mark.asyncio
async def test_other_products_valid_kind_is_refused_by_trigger(trigger_stack):
    b = trigger_stack
    response = await control(b, 'edit', body={'kind': 'base.receipt', 'text': 'placeholder cross-kind refusal', 'source': 'urn:placeholder:kind'})
    assert response.status_code == 422 and not await rows(b)


@pytest.mark.asyncio
async def test_edit_roundtrip_reads_the_authored_current_version(trigger_stack):
    b = trigger_stack
    original = await control(b, 'edit', body={'kind': 'trigger.tone', 'text': 'placeholder original tone', 'source': 'urn:placeholder:edit'})
    assert original.status_code == 200
    edited = await control(b, 'edit', body={'memory_id': original.json()['memory']['id'],
        'kind': 'trigger.tone', 'text': 'placeholder revised tone', 'source': 'urn:placeholder:edit'})
    assert edited.status_code == 200
    ident = edited.json()['memory']['id']
    request = await signed_request(b, 'GET', '/memory/records/' + ident + '?tenant_id=' + b.tenant)
    result = await b.http.send(request)
    assert result.status_code == 200
    selected = result.json()['memory']
    assert selected['id'] == ident and selected['claim'] == 'placeholder revised tone'
    assert selected['meta']['user_id'] == USER_A


@pytest.mark.asyncio
async def test_replayed_create_cannot_restore_a_forgotten_personal_record(trigger_stack):
    from chassis.user_assertion import PostgresNonces
    b = trigger_stack
    body = {'tenant_id': b.tenant, 'kind': 'trigger.tone', 'text': 'placeholder forgotten claim', 'source': 'urn:placeholder:forgotten'}
    request = await signed_request(b, 'POST', '/memory/edit', body=body)
    saved_request = {'method': request.method, 'url': str(request.url), 'headers': dict(request.headers), 'content': request.content}
    created = await b.http.send(request)
    assert created.status_code == 200
    forgotten = await control(b, 'forget', body={'memory_id': created.json()['memory']['id']})
    assert forgotten.status_code == 200 and not await rows(b)
    b.room.app.state.product_nonce_stores = {'trigger': PostgresNonces(b.pool, 'trigger')}
    replay = await b.http.request(**saved_request)
    assert replay.status_code == 401 and not await rows(b) and not b.net.providers


@pytest.mark.asyncio
async def test_superseding_an_approved_source_invalidates_cached_derivatives(trigger_stack):
    b = trigger_stack
    original = (await write(b))['result']
    source_id = next(step['memory_id'] for step in original['memory_receipt']['steps'] if step['action'] == 'remember')
    assert (await write(b))['result']['cost_usd'] == 0 and len(b.net.providers) == 1
    edited = await control(b, 'edit', body={'memory_id': source_id, 'kind': 'trigger.receipt',
        'text': 'placeholder explicitly superseded receipt', 'source': 'urn:placeholder:superseded'})
    assert edited.status_code == 200
    assert source_id not in {row['id'] for row in await rows(b)}
    fresh = (await write(b))['result']
    assert fresh['cost_usd'] == COST and len(b.net.providers) == 2
