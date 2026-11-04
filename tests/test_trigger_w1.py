"""W1 offline contracts: real disposable DB, fake Tank, no outside sockets."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests/trigger_gate2'))
from test_gate2 import env as second_build_env, card_for

env = second_build_env
from test_second import TENANT, OTHER, confirm, headers, proposal
import command
import trigger_learning
from trigger.formats import FORMATS, instruction, check_limit, length
from trigger.service import WriteIn
from trigger.voice_parser import parse_voice
from trigger.voice_history import learned_voice
from trigger_batch import csv_products


def test_formats_and_exact_counts_preserve_truncation():
    assert len(FORMATS) == 9
    assert FORMATS['page meta description'].limit is None
    assert FORMATS['Google Business Profile post'].limit is None
    assert FORMATS['LinkedIn post'].limit == 3000
    assert all(f.checked == '2026-11-03' and f.source for f in FORMATS.values() if f.limit)
    assert length('日本語 👨‍👩‍👧‍👦 https://example.com/long/path', 'X post') == 33
    assert length('e\u0301', 'X post') == 1
    base = {'issues': [], 'issue_count': 0, 'truncated': False}
    assert check_limit(base, 'a' * 3000, 'LinkedIn post')['issue_count'] == 0
    report = check_limit(base, 'a' * 3001, 'LinkedIn post')
    assert report['issues'][0]['rule'] == 'over_limit' and report['issues'][0]['count'] == 3001
    full = {'issues': [{}] * 200, 'issue_count': 250, 'truncated': True}
    report = check_limit(full, 'a' * 281, 'X post')
    assert len(report['issues']) == 200 and report['issue_count'] == 251 and report['truncated']
    assert 'subject and body' in instruction('email')
    with pytest.raises(ValueError):
        WriteIn(tenant_id=TENANT, text='Facts', format='unknown')


def test_instagram_caption_official_character_limit():
    spec = FORMATS['Instagram caption']
    source = 'https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/error-codes'
    assert spec.limit == 2200 and spec.source == source and spec.checked == '2026-11-03'
    base = {'issues': [], 'issue_count': 0, 'truncated': False}
    assert check_limit(base, 'a' * 2200, 'Instagram caption')['issue_count'] == 0
    report = check_limit(base, 'a' * 2201, 'Instagram caption')
    assert report['issue_count'] == 1
    assert report['issues'][0]['rule'] == 'over_limit'
    assert report['issues'][0]['count'] == 2201 and report['issues'][0]['limit'] == 2200
    assert report['length']['source'] == source
    # This change enforces characters only, not separate hashtag/mention limits.
    assert check_limit(base, '#a ' * 31 + '@a ' * 21, 'Instagram caption')['issue_count'] == 0


async def seed(env, tenant=TENANT, *, draft='Own facts.', status='pending', format='product description', age=0):
    write_id = uuid4()
    await env.pool.execute('''INSERT INTO tank.trigger_writes
        (id,tenant_id,user_id,brief,draft,checker_results,feedback_status,format,created_at)
        VALUES($1,$2,'admin','Own supplied facts',$3,'{"issue_count":2}',$4,$5,now()-$6::interval)''',
        write_id, tenant, draft, status, format, timedelta(days=age))
    return write_id


async def fake_drafts(env):
    calls = []
    async def route(tenant, task, messages):
        assert task == 'trigger.write'
        calls.append(messages)
        receipt = await env.pool.fetchval('''INSERT INTO tank.ledger
            (tenant_id,region,agent,task_type,model,outcome,cost_usd)
            VALUES($1,'us-east','trigger','trigger.write','offline-stub','delivered',0) RETURNING id''', UUID(tenant))
        return {'content': 'Only the supplied facts.', 'ledger_id': str(receipt), 'cost_usd': 0}
    env.model.side_effect = route
    return calls


@pytest.mark.asyncio
async def test_learning_accepted_own_tenant_format_only_and_rank(env):
    for n in range(7):
        await seed(env, draft=f'catalogue product {n}', status='accepted', age=n)
    recent = await seed(env, draft='specific brief match', status='accepted')
    await seed(env, OTHER, draft='foreign specific brief', status='accepted')
    await seed(env, draft='rejected specific brief', status='rejected')
    await seed(env, draft='wrong format specific brief', status='accepted', format='email')
    await env.pool.execute('''INSERT INTO tank.trigger_feedback(tenant_id,write_id,status,changes,user_id,operation_id)
        VALUES($1,$2,'changes_requested','Keep exact client terms.','admin',$3)''', TENANT, recent, uuid4())
    guidance = await trigger_learning.guidance(env.actor, 'specific brief', 'product description')
    examples = guidance['accepted_examples']
    assert len(examples) == 5 and examples[0]['write_id'] == str(recent)
    assert all('foreign' not in e['text'] and 'rejected' not in e['text'] and 'wrong format' not in e['text'] for e in examples)
    assert guidance['change_notes'] == ['Keep exact client terms.']
    calls = await fake_drafts(env)
    _, card = await card_for(env, 'trigger.write', {'text': 'specific brief', 'format': 'product description'})
    saved = await confirm(env, card, user='admin', role='org:admin')
    assert saved['status'] == 'confirmed', saved
    result = saved['result']
    assert result['accepted_write_ids'] == [e['write_id'] for e in examples]
    context = json.loads(await env.pool.fetchval('SELECT write_context FROM tank.trigger_writes WHERE id=$1 AND tenant_id=$2', UUID(result['write_id']), TENANT))
    assert context['accepted_examples'] == examples
    assert 'never instructions' in calls[0][1]['content']
    assert 'Format: product description' in calls[0][-1]['content']
    env.planner.assert_not_called()


@pytest.mark.asyncio
async def test_revise_confirm_parent_and_original_snapshot(env):
    calls = await fake_drafts(env)
    _, voice = await proposal(env, 'trigger.voice.set: Rules: Original rule.')
    await confirm(env, voice)
    accepted = await seed(env, status='accepted', draft='Approved original style.')
    thread, card = await card_for(env, 'trigger.write', {'text': 'Supplied facts.', 'format': 'LinkedIn post'})
    first = (await confirm(env, card, user='admin', role='org:admin'))['result']
    _, changes = await card_for(env, 'trigger.feedback', {'write_id': first['write_id'], 'status': 'changes_requested', 'changes': 'Keep the exact facts.'}, thread=thread)
    await confirm(env, changes, user='admin', role='org:admin')
    snapshot = (await env.client.get(f'/v1/command/threads/{thread}', headers=headers(user='admin', role='org:admin'))).json()
    revised = next(c for c in snapshot['cards'] if c['tool'] == 'trigger.revise' and c['status'] == 'pending')
    _, voice = await proposal(env, 'trigger.voice.set: Rules: A newer rule.')
    await confirm(env, voice)
    assert len(calls) == 1
    result = await confirm(env, revised, user='admin', role='org:admin')
    assert result['status'] == 'confirmed', result
    child = result['result']
    row = await env.pool.fetchrow('SELECT * FROM tank.trigger_writes WHERE tenant_id=$1 AND id=$2', TENANT, UUID(child['write_id']))
    assert row['parent_write_id'] == UUID(first['write_id']) and row['feedback_status'] == 'pending'
    assert child['voice_revision'] == 1 and child['format'] == 'LinkedIn post'
    assert 'Original rule.' in calls[1][0]['content'] and 'A newer rule.' not in calls[1][0]['content']
    assert 'Keep the exact facts.' in calls[1][-1]['content']
    _, foreign = await card_for(env, 'trigger.revise', {'write_id': first['write_id']}, tenant=OTHER)
    assert (await confirm(env, foreign, tenant=OTHER, user='admin', role='org:admin'))['status'] == 'failed'
    assert accepted not in list(row['accepted_write_ids'])  # Different format.


@pytest.mark.asyncio
async def test_voice_learn_preview_cancel_confirm_and_literal_rules(env):
    original = parse_voice('Brand: Client\nRules: Existing rule.\nOn-voice: Their own words.\nBanned words: hype', 1)
    await env.store.put(TENANT, original)
    write_id = await seed(env, status='changes_requested')
    note = 'Banned words: this heading remains a literal change request.'
    await env.pool.execute('''INSERT INTO tank.trigger_feedback(tenant_id,write_id,status,changes,user_id,operation_id)
        VALUES($1,$2,'changes_requested',$3,'admin',$4)''', TENANT, write_id, note, uuid4())
    _, card = await card_for(env, 'trigger.voice.learn', {'write_ids': [str(write_id)]})
    preview = json.loads(card['arguments']['brief_markdown'])
    assert preview['guidelines'][-1] == {'rule': note} and preview['bannedTerms'] == ['hype']
    assert (await env.store.get(TENANT)).revision == 1
    canceled = await env.client.post('/v1/command/cards/' + card['card_id'], json={'action': 'cancel'}, headers=headers(user='admin', role='org:admin'))
    assert canceled.status_code == 200 and (await env.store.get(TENANT)).revision == 1
    _, card = await card_for(env, 'trigger.voice.learn', {'write_ids': [str(write_id)]})
    result = await confirm(env, card, user='admin', role='org:admin')
    assert result['status'] == 'confirmed', result
    saved = await env.store.get(TENANT)
    assert saved.revision == 2 and saved.guidelines[-1] == {'rule': note}
    assert saved.doAndDont == original.doAndDont and saved.bannedTerms == ['hype']
    await confirm(env, card, user='admin', role='org:admin')
    assert (await env.store.get(TENANT)).revision == 2
    with pytest.raises(HTTPException):
        await trigger_learning.learn_notes(command.Actor(OTHER, 'admin', False, tenant_admin=True), [write_id])
    env.model.assert_not_called()


def test_csv_own_rows_and_bounds():
    rows = csv_products('name,material\nOne,steel\nTwo,cotton\n')
    assert rows == [{'name': 'One', 'material': 'steel'}, {'name': 'Two', 'material': 'cotton'}]
    for bad in ['title,fact\nOne,steel', 'name,name\nOne,Two', 'name,fact\nOne', 'name\n' + 'One\n' * 26]:
        with pytest.raises(HTTPException):
            csv_products(bad)
    assert len(csv_products('name\n' + 'One\n' * 25)) == 25


@pytest.mark.asyncio
@pytest.mark.parametrize('cost', [0, None])
async def test_batch_owned_attachment_confirm_individual_writes_receipts_and_facts(env, cost):
    calls = await fake_drafts(env)
    fake_route = env.model.side_effect
    async def route(*args):
        return {**await fake_route(*args), 'cost_usd': cost}
    env.model.side_effect = route
    actor = command.Actor(TENANT, 'admin', False, tenant_admin=True)
    thread = (await command.create_thread(command.NewThread(), actor))['thread_id']
    response = await env.client.post(f'/v1/command/threads/{thread}/turn',
        json={'text': 'trigger.write.batch: attachment products.csv', 'attachments': [
            {'name': 'products.csv', 'text': 'name,material\nOne,steel\nTwo,cotton\n'}]},
        headers=headers(user='admin', role='org:admin'))
    assert response.status_code == 200, response.text
    snapshot = (await env.client.get(f'/v1/command/threads/{thread}', headers=headers(user='admin', role='org:admin'))).json()
    card = snapshot['cards'][0]
    assert json.loads(card['arguments']['brief_markdown'])['item_count'] == 2
    assert not calls
    result = await confirm(env, card, user='admin', role='org:admin')
    assert result['status'] == 'confirmed', result
    assert result['result']['cost_usd'] == cost
    items = result['result']['items']
    assert len(items) == len({i['write_id'] for i in items}) == len({i['ledger_id'] for i in items}) == 2
    assert 'steel' in json.dumps(calls[0]) and 'cotton' not in json.dumps(calls[0])
    assert 'cotton' in json.dumps(calls[1]) and 'steel' not in json.dumps(calls[1])
    assert all('only this product' in m[-1]['content'] for m in calls)
    assert await env.pool.fetchval("SELECT count(*) FROM tank.trigger_writes WHERE tenant_id=$1 AND feedback_status='pending'", TENANT) == 2
    assert all(i['report'] and i['format'] == 'product description' for i in items)
    env.planner.assert_not_called()


def test_scorecard_period_boundaries_and_rates():
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    rows = []
    for days, status, examples in [(0, 'accepted', []), (1, 'accepted', [uuid4()]), (2, 'changes_requested', []),
                                   (3, 'rejected', []), (30, 'pending', []), (31, 'accepted', [])]:
        rows.append({'format': 'email', 'created_at': now - timedelta(days=days), 'feedback_status': status,
                     'draft': 'two words', 'checker_results': {'issue_count': 1}, 'accepted_write_ids': examples})
    score = trigger_learning.score_rows(rows, now)
    last = score['last_30_days']['email']
    assert last['drafts'] == 4  # now excluded, day 30 included.
    assert last['accepted_rate'] == last['changes_requested_rate'] == last['rejected_rate'] == .25
    assert last['findings_per_1000_words'] == 500 and last['drafts_using_accepted_examples'] == 1
    assert score['prior_30_days']['email']['drafts'] == 1


@pytest.mark.asyncio
async def test_scorecard_get_zero_receipt_and_tenant_permissions(env):
    await seed(env, status='accepted', format='email')
    await seed(env, OTHER, status='rejected', format='email')
    response = await env.client.get('/v1/trigger/scorecard', params={'tenant_id': str(TENANT)}, headers=headers(user='admin', role='org:admin'))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['last_30_days']['email']['drafts'] == 1 and data['cost_usd'] == data['model_calls'] == 0
    receipt = await env.pool.fetchrow('SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2', UUID(data['ledger_id']), TENANT)
    assert receipt['cost_usd'] == 0 and receipt['model'] == 'code'
    method, _, params, body = command.adapter_request(command.PlannedAction(tool='trigger.scorecard', arguments={}), env.actor)
    assert method == 'GET' and body is None and params['tenant_id'] == str(TENANT)
    for tenant, role in [(OTHER, 'org:admin'), (TENANT, '')]:
        denied = await env.client.get('/v1/trigger/scorecard', params={'tenant_id': str(tenant)}, headers=headers(user='admin', role=role))
        assert denied.status_code == 403
    env.model.assert_not_called()


def test_learn_preserves_all_existing_voice_fields():
    current = parse_voice('Rules: Precise.\nTone: calm\nOn-voice: Original copy.', 2)
    learned = learned_voice(current, ['Exact request.'], 3)
    assert learned.tone == current.tone and learned.doAndDont == current.doAndDont
    assert learned.guidelines == [*current.guidelines, {'rule': 'Exact request.'}]


@pytest.mark.asyncio
async def test_rig_entitlement_existing_get_and_only_current_record(env):
    from fastapi import Request
    from trigger_batch import products
    actor = command.Actor(TENANT, 'admin', False, tenant_admin=True)
    args = {'skus': ['one', 'two']}
    with pytest.raises(HTTPException) as denied:
        await products(actor, args, {})
    assert denied.value.status_code == 403
    await env.pool.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'rig','offline')", TENANT)
    requested = []
    @env.client._transport.app.get('/v1/rig/products/{sku}')
    async def rig_record(sku: str, request: Request):
        assert request.query_params['tenant_id'] == str(TENANT)
        assert request.headers['x-tank-key'] == 'dummy-workspace-key'
        requested.append(sku)
        return {'id': sku, 'name': sku, 'attributes': {'material': 'steel' if sku == 'one' else 'cotton'},
                'categories_that_fit': [{'foreign_product': 'must not enter prompt'}]}
    rows = await products(actor, args, {})
    assert requested == ['one', 'two']
    assert rows == [{'id': 'one', 'name': 'one', 'attributes': {'material': 'steel'}},
                    {'id': 'two', 'name': 'two', 'attributes': {'material': 'cotton'}}]
    with pytest.raises(ValueError):
        command.TriggerBatchArgs(skus=['a'] * 26)
    with pytest.raises(ValueError):
        command.TriggerBatchArgs(skus=['a'], attachment='rows.csv')


@pytest.mark.asyncio
async def test_batch_25_receipts_feedback_and_case_study_provenance(env, monkeypatch):
    from case_study_sources import trigger
    await seed(env, status='accepted')
    calls = await fake_drafts(env)
    actor = command.Actor(TENANT, 'admin', False, tenant_admin=True)
    thread = UUID((await command.create_thread(command.NewThread(), actor))['thread_id'])
    async with command.editing(thread, actor) as (conn, row, state):
        state['messages'].append({'role': 'user', 'content': 'trigger.write.batch: attachment rows.csv',
                                  'attachments': [{'name': 'rows.csv', 'text': 'name,fact\n' + ''.join(f'item{i},fact{i}\n' for i in range(25))}]})
        action = command.validate_action(command.PlannedAction(tool='trigger.write.batch', arguments={'attachment': 'rows.csv'}), actor)
        card = await command.propose_action(conn, row, state, action, actor)
    result = await confirm(env, card, user='admin', role='org:admin')
    assert result['status'] == 'confirmed', result
    items = result['result']['items']
    assert len(items) == len(calls) == len({i['ledger_id'] for i in items}) == 25
    assert all(len(i['accepted_write_ids']) == 1 for i in items)
    _, accepted = await card_for(env, 'trigger.feedback', {'write_id': items[0]['write_id'], 'status': 'accepted'}, thread=thread)
    assert (await confirm(env, accepted, user='admin', role='org:admin'))['status'] == 'confirmed'
    assert await env.pool.fetchval('SELECT feedback FROM tank.ledger WHERE tenant_id=$1 AND id=$2', TENANT, UUID(items[0]['ledger_id'])) == 'accepted'
    figures = {name: {} for name in ('trigger.drafts', 'trigger.acceptance_rate', 'trigger.checker_issues_per_draft', 'trigger.voice_rule_hits')}
    now = datetime.now(timezone.utc)
    async with env.pool.acquire() as conn:
        await trigger(conn, TENANT, 'us-east', now-timedelta(days=1), now+timedelta(days=1), figures)
    assert figures['trigger.drafts']['drafts_using_accepted_examples'] == 25
    assert figures['trigger.drafts']['value'] == 25 and figures['trigger.acceptance_rate']['value'] == 100
    monkeypatch.setenv('TANK_KEY_TISAN', 'offline-tisan')
    copy = await env.client.get('/v1/trigger/copy/' + items[0]['write_id'], params={'tenant_id': str(TENANT)},
        headers={'X-Tank-Key': 'offline-tisan', 'X-Tervory-Tenant': str(TENANT), 'X-Tervory-Home-Region': 'us-east'})
    assert copy.status_code == 200 and copy.json()['text'] == items[0]['text']
    from trigger_commands import plan
    turn_id = uuid4()
    async with command.editing(thread, actor) as (conn, row, state):
        state['active_turn'] = str(turn_id)
    planned = await plan(actor, 'trigger, changes: ' + items[1]['write_id'] + ': Exact client request.', turn_id)
    assert planned['actions'][0]['arguments']['write_id'] == items[1]['write_id']
    with pytest.raises(HTTPException):
        await plan(actor, 'trigger, changes: Ambiguous batch item.', turn_id)
    async with command.editing(thread, actor) as (conn, row, state):
        state['active_turn'] = None
        state['messages'].append({'role': 'user', 'content': 'trigger.write.batch: attachment next.csv',
            'attachments': [{'name': 'next.csv', 'text': 'name,fact\nNext,Own facts\n'}]})
    _, next_card = await card_for(env, 'trigger.write.batch', {'attachment': 'next.csv'}, thread=thread)
    next_result = await confirm(env, next_card, user='admin', role='org:admin')
    assert next_result['status'] == 'confirmed', next_result
    assert items[0]['write_id'] in next_result['result']['items'][0]['accepted_write_ids']


@pytest.mark.asyncio
async def test_voice_learn_stale_preview_and_unconfirmed_routes_fail(env):
    write_id = await seed(env, status='changes_requested')
    await env.pool.execute('''INSERT INTO tank.trigger_feedback(tenant_id,write_id,status,changes,user_id,operation_id)
        VALUES($1,$2,'changes_requested','Exact note.','admin',$3)''', TENANT, write_id, uuid4())
    _, stale = await card_for(env, 'trigger.voice.learn', {'write_ids': [str(write_id)]})
    _, changed = await proposal(env, 'trigger.voice.set: Rules: New rule.')
    await confirm(env, changed)
    assert (await confirm(env, stale, user='admin', role='org:admin'))['status'] == 'failed'
    assert (await env.store.get(TENANT)).guidelines == [{'rule': 'New rule.'}]
    for op, args in [('revise', {'write_id': str(write_id)}), ('voice.learn', {'write_ids': [str(write_id)]}),
                     ('write.batch', {'skus': ['one']})]:
        direct = await env.client.post('/v1/trigger/' + op, json=args, headers=headers(user='admin', role='org:admin'))
        assert direct.status_code == 409
        member = await env.client.post('/v1/trigger/' + op, json=args, headers=headers(user='member'))
        assert member.status_code == 403
    env.model.assert_not_called()


@pytest.mark.asyncio
async def test_schema_follows_existing_rls_rollout_and_startup_admin_application(env):
    # Only this fixture's disposable database; never a production connection.
    assert not await env.pool.fetchval("SELECT relrowsecurity FROM pg_class WHERE oid='tank.trigger_writes'::regclass")
    await env.pool.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
    await env.pool.execute((ROOT / 'tank/schema.sql').read_text())
    flags = await env.pool.fetchrow("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='tank.trigger_writes'::regclass")
    assert flags['relrowsecurity'] and flags['relforcerowsecurity']
    policies = await env.pool.fetch("SELECT polname,polpermissive,pg_get_expr(polqual,polrelid) AS using,pg_get_expr(polwithcheck,polrelid) AS check FROM pg_policy WHERE polrelid='tank.trigger_writes'::regclass")
    assert {p['polname'] for p in policies} == {'tenant_access', 'tenant_boundary'}
    assert any(not p['polpermissive'] for p in policies)
    assert all('app.tenant_id' in p['using'] and 'app.tenant_id' in p['check'] for p in policies)
    startup = (ROOT / 'tank/main.py').read_text().split('async def _startup()', 1)[1].split('@app.on_event("shutdown")', 1)[0]
    assert '(_admin_pool or raw_pool).acquire()' in startup and 'await conn.execute(ddl)' in startup


@pytest.mark.asyncio
async def test_actual_write_format_report_and_withdrawn_example_refusal(env):
    calls = await fake_drafts(env)
    async def long_draft(*args):
        value = await fake_route(*args)
        return {**value, 'content': 'a' * 3001}
    fake_route = env.model.side_effect
    env.model.side_effect = long_draft
    approved = await seed(env, status='accepted', format='LinkedIn post')
    thread, card = await card_for(env, 'trigger.write', {'text': 'Supplied facts.', 'format': 'LinkedIn post'})
    saved = (await confirm(env, card, user='admin', role='org:admin'))['result']
    finding = next(i for i in saved['report']['issues'] if i['rule'] == 'over_limit')
    assert finding['count'] == 3001 and finding['limit'] == 3000
    assert saved['accepted_write_ids'] == [str(approved)]
    _, changes = await card_for(env, 'trigger.feedback', {'write_id': saved['write_id'], 'status': 'changes_requested', 'changes': 'Shorten it.'}, thread=thread)
    await confirm(env, changes, user='admin', role='org:admin')
    await env.pool.execute("UPDATE tank.trigger_writes SET feedback_status='rejected' WHERE tenant_id=$1 AND id=$2", TENANT, approved)
    with pytest.raises(HTTPException) as stale:
        await trigger_learning.revision(env.actor, UUID(saved['write_id']))
    assert stale.value.status_code == 409 and len(calls) == 1
