"""Offline second-build contracts; fixtures never enter production."""
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'agents'), str(ROOT / 'agents/_chassis')]
spec = importlib.util.spec_from_file_location('zenas_scope', ROOT / 'agents/zenas/core/scope_rules.py')
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)
sys.modules['zenas_scope'] = scope
import command
import trigger_routes
import trigger_commands
from trigger.app import app as room_app
from trigger.voice_history import VoiceHistory
from trigger.voice_parser import parse_voice
from trigger.checkers import local_checks
from trigger.service import WriteIn, write

TENANT = UUID('00000000-0000-0000-0000-000000000011')
OTHER = UUID('00000000-0000-0000-0000-000000000012')
NOTES = '''Brand: Offline tenant
Rules:
- Keep claims precise.
Preferred words: reliable, clear
Banned words: revolutionary, effortless
On-voice:
- Built for everyday work.
Off-voice:
- Revolutionary magic!
'''


def test_parser_preserves_only_authored_values():
    parsed = parse_voice(NOTES, 1).model_dump(exclude_unset=True)
    assert parsed == {'brand': 'Offline tenant', 'status': 'live', 'revision': 1,
                     'guidelines': [{'rule': 'Keep claims precise.'}],
                     'preferredTerms': ['reliable', 'clear'], 'bannedTerms': ['revolutionary', 'effortless'],
                     'doAndDont': [{'do': 'Built for everyday work.'}, {'dont': 'Revolutionary magic!'}]}
    assert parse_voice('Keep it brief.', 2).brand == ''
    assert parse_voice('Keep it brief.', 2).guidelines == [{'rule': 'Keep it brief.'}]
    assert 'maxSentenceWords' not in parsed and 'registers' not in parsed
    assert parse_voice('Banned words: "one, two", three', 1).bannedTerms == ['one, two', 'three']


def test_house_style_only_without_tenant_voice():
    text = 'Simply click [here](https://example.com). It was completed by the team.'
    assert any(i['source'] == 'house-style' for i in local_checks(text, None)['issues'])
    assert not any(i['source'] == 'house-style' for i in local_checks(text, parse_voice('Use passive voice.', 1))['issues'])


@pytest_asyncio.fixture
async def env(monkeypatch):
    url = os.environ.get('POOL_SCHEMA_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated local Postgres')
    admin = await asyncpg.connect(url)
    name = 'trigger2_' + uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    parts = urlsplit(url)
    pool = await asyncpg.create_pool(urlunsplit((parts.scheme, parts.netloc, '/' + name, '', '')), min_size=1, max_size=8)
    schema = (ROOT / 'tank/schema.sql').read_text()
    await pool.execute(schema)
    await pool.execute(schema)
    await pool.execute('CREATE SCHEMA agent_trigger')
    await pool.execute((ROOT / 'agents/trigger/schema.sql').read_text())
    await pool.execute((ROOT / 'agents/trigger/schema.sql').read_text())
    app = FastAPI()
    app.include_router(command.router)
    app.include_router(trigger_routes.router)
    runtime = SimpleNamespace(pool=lambda: pool, box_region=lambda: 'us-east', app=app,
                              TANK_API_KEY='dummy-workspace-key', Message=lambda **k: k, RouteRequest=lambda **k: k,
                              run_route=AsyncMock(side_effect=AssertionError('No planner model allowed')))
    monkeypatch.setitem(sys.modules, 'main', runtime)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder')
    monkeypatch.setenv('TANK_KEY', 'dummy-room-key')
    monkeypatch.setattr(room_app.state, 'pool', pool, raising=False)
    lt = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={'matches': []})))
    monkeypatch.setattr(room_app.state, 'http', lt, raising=False)
    # No approved checker versions: the current client explicitly returns None.
    tank = SimpleNamespace(route=AsyncMock(return_value={'content': 'A reliable product.', 'ledger_id': str(uuid4()), 'cost_usd': 0.01}),
                           approved_skill=AsyncMock(return_value=None))
    monkeypatch.setattr(room_app.state, 'tank', tank, raising=False)
    bridge_calls = []
    async def bridge(operation, body):
        bridge_calls.append((operation, body))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room_app), base_url='http://room') as client:
            response = await client.post('/' + operation, json=body, headers={'X-Tank-Key': 'dummy-room-key'})
        if response.status_code >= 400:
            raise HTTPException(response.status_code, response.json())
        return response.json()
    monkeypatch.setattr(trigger_routes, 'room', bridge)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank', timeout=20) as client:
        yield SimpleNamespace(pool=pool, client=client, store=VoiceHistory(pool), model=tank.route,
                              planner=runtime.run_route, actor=command.Actor(TENANT, 'founder', True), bridge=bridge_calls,
                              checkers=tank.approved_skill)
    await lt.aclose()
    await pool.close()
    await admin.execute(f'DROP DATABASE "{name}"')
    await admin.close()


def headers(tenant=TENANT, user='founder', role=''):
    return {'X-Tank-Key': 'dummy-workspace-key', 'X-Tervory-Tenant': str(tenant), 'X-Tervory-User': user, 'X-Tervory-Role': role}


async def proposal(env, text, *, tenant=TENANT, user='founder', role='', thread=None):
    h = headers(tenant, user, role)
    if thread is None:
        response = await env.client.post('/v1/command/threads', json={'title': 'Offline voice test'}, headers=h)
        assert response.status_code == 200, response.text
        thread = response.json()['thread_id']
    response = await env.client.post(f'/v1/command/threads/{thread}/turn', json={'text': text}, headers=h)
    assert response.status_code == 200
    snapshot = (await env.client.get(f'/v1/command/threads/{thread}', headers=h)).json()
    assert snapshot['cards'], response.text
    card = next(c for c in snapshot['cards'] if c['status'] == 'pending')
    return thread, card


async def confirm(env, card, **who):
    response = await env.client.post('/v1/command/cards/' + card['card_id'], json={'action': 'confirm'}, headers=headers(**who))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_preview_confirm_history_rollback_and_repeat(env):
    thread, card = await proposal(env, 'trigger.voice.set:\n' + NOTES)
    assert json.loads(card['arguments']['brief_markdown'])['guidelines'] == [{'rule': 'Keep claims precise.'}]
    assert await env.store.get(TENANT) is None
    pending = (await env.client.get(f'/v1/command/threads/{thread}', headers=headers())).json()
    result = await confirm(env, card)
    assert result['status'] == 'confirmed', result
    assert (await env.store.get(TENANT)).revision == 1
    await confirm(env, card)
    assert (await env.store.show(TENANT))['history_total'] == 1
    _, second = await proposal(env, 'trigger.voice.set:\nRules: Keep sentences short.', thread=thread)
    await confirm(env, second)
    _, rollback = await proposal(env, 'trigger.voice.rollback: 1', thread=thread)
    assert (await env.store.get(TENANT)).revision == 2  # Preview is read-only.
    result = await confirm(env, rollback)
    assert result['status'] == 'confirmed', result
    current = await env.store.get(TENANT)
    assert current.revision == 3 and current.guidelines == [{'rule': 'Keep claims precise.'}]
    _, show = await proposal(env, 'trigger.voice.show', thread=thread)
    shown = await confirm(env, show)
    assert shown['result']['history_total'] == 3
    assert shown['result']['history'][0]['restored_from'] == 1
    evidence = os.environ.get('TRIGGER_SECOND_EVIDENCE')
    if evidence:
        saved = (await env.client.get(f'/v1/command/threads/{thread}', headers=headers())).json()
        Path(evidence).write_text(json.dumps({'pending': pending, 'saved': saved}, indent=2) + '\n')
    env.model.assert_not_called()
    env.planner.assert_not_called()


@pytest.mark.asyncio
async def test_tenant_admin_scope_revocation_and_no_confirmation_bypass(env):
    thread, card = await proposal(env, 'trigger.voice.set:\n' + NOTES, user='admin', role='org:admin')
    direct = await env.client.post('/v1/trigger/voice.set', json={**card['arguments'], 'tenant_id': str(TENANT)}, headers=headers(user='admin', role='org:admin'))
    assert direct.status_code == 409
    assert await env.store.get(TENANT) is None
    denied = await env.client.post('/v1/command/cards/' + card['card_id'], json={'action': 'confirm'}, headers=headers(user='admin'))
    assert denied.status_code == 403
    assert (await confirm(env, card, user='admin', role='org:admin'))['status'] == 'confirmed'
    other = await env.client.post('/v1/trigger/voice.show', json={}, headers=headers(OTHER, 'admin', 'org:admin'))
    assert other.status_code == 200 and other.json()['voice'] is None
    forged = await env.client.post('/v1/trigger/voice.show', json={'tenant_id': str(TENANT)}, headers=headers(OTHER, 'admin', 'org:admin'))
    assert forged.status_code == 403
    for h in [headers(user='member'), {**headers(user='admin', role='org:admin'), 'X-Tank-Key': 'wrong'}]:
        assert (await env.client.post('/v1/trigger/voice.show', json={}, headers=h)).status_code in {401, 403}
    catalog = (await env.client.get('/v1/command/tools', headers=headers(user='admin', role='org:admin'))).json()
    assert 'trigger.voice.set' in catalog and 'worker.build' not in catalog and 'trigger.write' not in catalog
    env.model.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_and_stale_preview_never_overwrite(env):
    _, one = await proposal(env, 'trigger.voice.set:\nRules: First.')
    _, stale = await proposal(env, 'trigger.voice.set:\nRules: Second.')
    await env.client.post('/v1/command/cards/' + one['card_id'], json={'action': 'cancel'}, headers=headers())
    assert await env.store.get(TENANT) is None
    _, live = await proposal(env, 'trigger.voice.set:\nRules: Third.')
    await confirm(env, live)
    result = await confirm(env, stale)
    assert result['status'] == 'failed'
    assert (await env.store.get(TENANT)).guidelines == [{'rule': 'Third.'}]
    assert (await env.store.show(TENANT))['history_total'] == 1


@pytest.mark.asyncio
async def test_mutated_user_source_cannot_be_proposed(env):
    action = command.validate_action(command.PlannedAction(tool='trigger.voice.set', arguments={'text': 'Invent a rule.'}), env.actor)
    with pytest.raises(HTTPException):
        await trigger_commands.prepare(action, env.actor, {'messages': [{'role': 'user', 'content': 'trigger.voice.set: Keep it clear.'}]})
    assert await env.store.get(TENANT) is None


@pytest.mark.asyncio
async def test_house_write_records_private_pending_pair_then_feedback(env):
    response = await env.client.post('/v1/trigger/write', json={'text': 'Describe the supplied product.'}, headers=headers())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['report']['style_source'] == 'house'
    assert [call.args for call in env.checkers.await_args_list] == [
        (str(TENANT), 'trigger.' + component, {'text': result['text']})
        for component in ('proselint', 'agent_style', 'readability', 'voice_check', 'house_style', 'languagetool')
    ]
    write_id = result['write_id']
    pair = await env.pool.fetchrow("SELECT * FROM tank.training_pairs WHERE tenant_id=$1 AND source='trigger.write' AND source_ref=$2", TENANT, write_id)
    assert not pair['active'] and not pair['public'] and pair['client_matter']
    assert json.loads(pair['input'])['brief'] == 'Describe the supplied product.'
    assert json.loads(pair['output'])['draft'] == result['text']
    assert 'checker_results' in json.loads(pair['output'])
    assert 'house_style' in env.model.call_args.args[2][0]['content']
    from trigger_learning import feedback
    with pytest.raises(HTTPException):
        await feedback(command.Actor(OTHER, 'founder', True), UUID(write_id), 'accepted', '', uuid4())
    # Insert the real completed tool result in an owned conversation for latest-draft feedback.
    thread = UUID((await command.create_thread(command.NewThread(title='Offline learning'), env.actor))['thread_id'])
    async with command.editing(thread, env.actor) as (_conn, _row, state):
        state['cards']['written'] = {'tool': 'trigger.write', 'status': 'confirmed', 'started_at': '2026-10-28T12:00:00+00:00', 'result': result}
    for prefix, status, changes in [('changes', 'changes_requested', 'Use fewer adjectives.'), ('reject', 'rejected', 'Wrong emphasis.'), ('accept', 'accepted', '')]:
        _, card = await proposal(env, f'trigger, {prefix}: {changes}', thread=str(thread))
        saved = await confirm(env, card)
        assert saved['status'] == 'confirmed', saved
        pair = await env.pool.fetchrow("SELECT * FROM tank.training_pairs WHERE tenant_id=$1 AND source='trigger.write' AND source_ref=$2", TENANT, write_id)
        assert json.loads(pair['output'])['feedback'] == {'status': status, 'changes': changes}
        assert pair['active'] == (status == 'accepted') and not pair['public'] and pair['client_matter']
    assert await env.pool.fetchval('SELECT count(*) FROM tank.trigger_feedback WHERE tenant_id=$1 AND write_id=$2', TENANT, UUID(write_id)) == 3
    assert await env.pool.fetchval('SELECT count(*) FROM tank.training_pairs WHERE tenant_id=$1', OTHER) == 0
    assert env.model.await_count == 1
    env.planner.assert_not_called()


@pytest.mark.asyncio
async def test_saved_voice_disables_house_prompt_and_checks(env):
    preview = await env.store.preview(TENANT, 'Banned words: reliable')
    await env.store.commit(TENANT, text='Banned words: reliable', expected_revision=0, digest=preview['preview_hash'], operation_id=uuid4())
    response = await write(WriteIn(tenant_id=TENANT, text='Describe a product.'), env.store, room_app.state.tank, room_app.state.http)
    assert response['report']['style_source'] == 'tenant'
    assert any(i['rule'] == 'banned_term' for i in response['report']['issues'])
    assert not any(i['source'] == 'house-style' for i in response['report']['issues'])
    assert '"house_style": null' in env.model.call_args.args[2][0]['content']


@pytest.mark.asyncio
async def test_history_read_and_concurrent_confirm(env):
    import asyncio
    one = await env.store.preview(TENANT, 'Rules: One.')
    two = await env.store.preview(TENANT, 'Rules: Two.')
    results = await asyncio.gather(*[
        env.store.commit(TENANT, text=text, expected_revision=0, digest=preview['preview_hash'], operation_id=uuid4())
        for text, preview in [('Rules: One.', one), ('Rules: Two.', two)]
    ], return_exceptions=True)
    assert sum(isinstance(r, ValueError) for r in results) == 1
    assert (await env.store.show(TENANT, target=1))['selected_voice']['revision'] == 1
    with pytest.raises(ValueError):
        await env.store.show(OTHER, target=1)
    with pytest.raises(ValueError):
        await env.store.preview(OTHER, target=1)


def test_bad_quotes_fail_visibly_and_all_house_sources_are_pinned():
    from trigger.house_style import RULES
    from trigger.voice import BOOKS
    with pytest.raises(ValueError, match='quotes'):
        parse_voice('Banned words: "unfinished', 1)
    assert {source for rule in RULES for source in rule['sources']} == BOOKS
