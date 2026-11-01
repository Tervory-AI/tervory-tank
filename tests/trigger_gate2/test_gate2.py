"""Gate 2: actual Command confirmation, room checks and disposable tenant data."""
from __future__ import annotations

import importlib.util
import re
import sys
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/trigger_second_build'))
from test_second import env as second_build_env, headers, confirm, TENANT, OTHER

# Reuse the real second-build disposable database and room fixture.
env = second_build_env
import command
from trigger import checkers
from trigger.service import CheckIn, WriteIn
from trigger.voice_parser import parse_voice


def scaffold_module():
    spec = importlib.util.spec_from_file_location('gate2_scaffold', ROOT / 'agents/tisan/scaffold.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def brief(pages):
    return {'name': 'Offline build', 'slug': 'offline-build', 'pages': pages,
            'brand': {'colours': {'ink': '#001840', 'paper': '#ffffff', 'accent': '#E80008', 'line': '#B8BFD0'},
                      'fonts': {'heading': 'Inter', 'body': 'Inter'}}}


async def card_for(env, tool, arguments, *, tenant=TENANT, user='admin', thread=None):
    actor = command.Actor(tenant, user, user == 'founder', tenant_admin=True)
    if thread is None:
        thread = UUID((await command.create_thread(command.NewThread(title='Offline Gate 2'), actor))['thread_id'])
    async with command.editing(UUID(str(thread)), actor) as (conn, row, state):
        action = command.validate_action(command.PlannedAction(tool=tool, arguments=arguments), actor)
        card = await command.propose_action(conn, row, state, action, actor)
    return thread, card


async def written(env, *, tenant=TENANT, user='admin', text='A reliable product.'):
    # A deterministic router substitute: it records its own local receipt and
    # returns fixed test text. No model, provider, or production data is used.
    receipt = await env.pool.fetchval("""INSERT INTO tank.ledger
        (tenant_id,region,agent,task_type,model,outcome,cost_usd)
        VALUES($1,'us-east','trigger','trigger.write','offline-stub','delivered',0) RETURNING id""", tenant)
    env.model.return_value = {'content': text, 'ledger_id': str(receipt), 'cost_usd': 0}
    thread, card = await card_for(env, 'trigger.write', {'text': 'Describe only the supplied product.'}, tenant=tenant, user=user)
    assert await env.pool.fetchval('SELECT count(*) FROM tank.trigger_writes WHERE tenant_id=$1', tenant) == 0
    result = await confirm(env, card, tenant=tenant, user=user, role='org:admin')
    assert result['status'] == 'confirmed', result
    return thread, result['result']


async def accepted(env, *, text='A reliable product.'):
    thread, result = await written(env, text=text)
    _, card = await card_for(env, 'trigger.feedback', {'write_id': result['write_id'], 'status': 'accepted', 'changes': ''}, thread=thread)
    assert (await confirm(env, card, user='admin', role='org:admin'))['status'] == 'confirmed'
    return thread, result


@pytest.mark.asyncio
async def test_verified_admin_write_check_feedback_stay_in_own_tenant(env):
    catalog = (await env.client.get('/v1/command/tools', headers=headers(user='admin', role='org:admin'))).json()
    assert set(command.TOOLS['trigger']) <= set(catalog)
    assert 'worker.build' not in catalog and 'tisan.scaffold' not in catalog
    assert not await env.pool.fetchval('SELECT count(*) FROM tank.tenant_squad WHERE tenant_id=$1', TENANT)
    thread, result = await written(env)
    _, check_card = await card_for(env, 'trigger.check', {'text': 'This is a test.'}, thread=thread)
    checked = await confirm(env, check_card, user='admin', role='org:admin')
    assert checked['status'] == 'confirmed' and checked['result']['model_calls'] == 0
    _, feedback_card = await card_for(env, 'trigger.feedback', {'write_id': result['write_id'], 'status': 'accepted', 'changes': ''}, thread=thread)
    assert (await confirm(env, feedback_card, user='admin', role='org:admin'))['status'] == 'confirmed'
    assert await env.pool.fetchval('SELECT feedback_status FROM tank.trigger_writes WHERE tenant_id=$1 AND id=$2', TENANT, UUID(result['write_id'])) == 'accepted'
    for tool, arguments in [('write', {'text': 'Write.'}), ('check', {'text': 'Check.'}),
                            ('feedback', {'write_id': result['write_id'], 'status': 'accepted', 'changes': ''})]:
        for bad_headers in [headers(user='member'), {**headers(user='admin', role='org:admin'), 'X-Tank-Key': 'forged', 'X-Tervory-Squad': 'trigger'}]:
            response = await env.client.post('/v1/trigger/' + tool, json=arguments, headers=bad_headers)
            assert response.status_code in {401, 403}
        response = await env.client.post('/v1/trigger/' + tool, json={**arguments, 'tenant_id': str(OTHER)}, headers=headers(user='admin', role='org:admin'))
        assert response.status_code == 403
        direct = await env.client.post('/v1/trigger/' + tool, json=arguments, headers=headers(user='admin', role='org:admin'))
        assert direct.status_code == 409  # A current admin still needs an executing Confirm card.
    _, foreign = await card_for(env, 'trigger.feedback', {'write_id': result['write_id'], 'status': 'accepted', 'changes': ''}, tenant=OTHER)
    assert (await confirm(env, foreign, tenant=OTHER, user='admin', role='org:admin'))['status'] == 'failed'
    assert await env.pool.fetchval('SELECT count(*) FROM tank.trigger_feedback WHERE tenant_id=$1', OTHER) == 0
    assert env.model.await_count == 1
    env.planner.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('tool,args', [('trigger.write', {'text': 'Write.'}), ('trigger.check', {'text': 'Check.'}),
                                     ('trigger.feedback', {'write_id': '00000000-0000-0000-0000-000000000013', 'status': 'accepted', 'changes': ''})])
async def test_stale_cancelled_and_foreign_confirmation_cards_are_refused(env, tool, args):
    _, card = await card_for(env, tool, args)
    url = '/v1/command/cards/' + card['card_id']
    assert (await env.client.post(url, json={'action': 'confirm'}, headers=headers(user='admin'))).status_code == 403
    for h in [headers(OTHER, 'admin', 'org:admin'), headers(TENANT, 'another-admin', 'org:admin')]:
        assert (await env.client.post(url, json={'action': 'confirm'}, headers=h)).status_code == 404
    assert (await env.client.post(url, json={'action': 'cancel'}, headers=headers(user='admin', role='org:admin'))).status_code == 200
    assert (await env.client.post(url, json={'action': 'confirm'}, headers=headers(user='admin', role='org:admin'))).status_code == 409
    env.model.assert_not_called()
    assert await env.pool.fetchval('SELECT count(*) FROM tank.trigger_writes') == 0
    assert await env.pool.fetchval('SELECT count(*) FROM tank.trigger_feedback') == 0


@pytest.mark.asyncio
async def test_long_attached_document_checked_once_with_whole_text_offsets(env):
    document = '# First\n' + ('plain words.\n' * 1350) + '\n# Second\n' + ('more words.\n' * 500) + 'revolutionary\n'
    assert 20000 < len(document) < 31000
    # Save a real fixture voice through its existing Confirm path.
    from test_second import proposal
    _, voice = await proposal(env, 'trigger.voice.set:\nBanned words: revolutionary', user='admin', role='org:admin')
    assert (await confirm(env, voice, user='admin', role='org:admin'))['status'] == 'confirmed'
    created = await env.client.post('/v1/command/threads', json={'title': 'Offline long check'}, headers=headers(user='admin', role='org:admin'))
    thread = created.json()['thread_id']
    response = await env.client.post(f'/v1/command/threads/{thread}/turn', json={'text': 'Trigger, check:',
        'attachments': [{'name': 'document.md', 'text': document}]}, headers=headers(user='admin', role='org:admin'))
    assert response.status_code == 200
    snapshot = (await env.client.get(f'/v1/command/threads/{thread}', headers=headers(user='admin', role='org:admin'))).json()
    card = next(c for c in snapshot['cards'] if c['status'] == 'pending')
    assert card['arguments'] == {'text': document}
    result = await confirm(env, card, user='admin', role='org:admin')
    assert result['status'] == 'confirmed', result
    report = result['result']['report']
    found = next(i for i in report['issues'] if i['rule'] == 'banned_term')
    assert found['offset'] == document.index('revolutionary')
    assert result['result']['text'] == document and report['model_calls'] == 0 and report['complete']
    chunk_calls = [call.args[2]['text'] for call in env.checkers.await_args_list if call.args[1] == 'trigger.languagetool']
    assert len(chunk_calls) > 1 and ''.join(chunk_calls) == document
    assert all(len(t) < 20000 for t in chunk_calls)
    assert sum(op == 'check' for op, _ in env.bridge) == 1
    env.model.assert_not_called()
    env.planner.assert_not_called()


@pytest.mark.asyncio
async def test_unicode_offsets_line_columns_and_aggregate_truncation(monkeypatch):
    document = '# A\n' + ('plain ' * 2800) + '\n\n# B\n😀 FLAG\n' + 'FLAG ' * 1500
    async def piece(text, voice, http, **kwargs):
        issues = []
        for m in re.finditer('FLAG', text):
            before = text[:m.start()]
            issues.append({'source': 'languagetool', 'rule': 'offline', 'message': 'offline',
                           'offset': len(before.encode('utf-16-le')) // 2, 'length': 4})
            issues.append({'source': 'proselint', 'rule': 'offline', 'message': 'offline',
                           'line': before.count('\n') + 1, 'column': len(before.rsplit('\n', 1)[-1]) + 1})
        return {'issues': issues, 'issue_count': len(issues), 'complete': not text.startswith('# B'),
                'checker_errors': [] if not text.startswith('# B') else ['offline incomplete'],
                'model_calls': 0, 'truncated': False}
    monkeypatch.setattr(checkers, '_check_piece', piece)
    report = await checkers.check(document, None, None)
    assert report['issue_count'] == 3002 and len(report['issues']) == 200 and report['truncated']
    for issue in report['issues']:
        assert document[issue['offset']:issue['offset'] + 4] == 'FLAG'
        if 'line' in issue:
            assert issue['line'] == document[:issue['offset']].count('\n') + 1
            assert issue['column'] == len(document[:issue['offset']].rsplit('\n', 1)[-1]) + 1
    assert report['complete'] is False and report['checker_errors'] == ['offline incomplete']


def test_chunk_boundaries_and_total_limits():
    examples = ['# A\n' + 'x' * 17000 + '\n\n# B\n' + 'y' * 10000,
                'x' * 15000 + '\n\n' + 'y' * 15000, 'word ' * 6000, 'x' * 32000]
    for document in examples:
        chunks = list(checkers.pieces(document))
        assert ''.join(part for _, part in chunks) == document
        assert all(0 < len(part) < 20000 and document[start:start + len(part)] == part for start, part in chunks)
    actor = command.Actor(TENANT, 'founder', True)
    command.validate_action(command.PlannedAction(tool='trigger.check', arguments={'text': 'x' * 31000}), actor)
    for text in ['x' * 32001, '😀' * 10000]:
        with pytest.raises(HTTPException):
            command.validate_action(command.PlannedAction(tool='trigger.check', arguments={'text': text}), actor)
    with pytest.raises(ValueError):
        CheckIn(tenant_id=TENANT, text='x' * 32001)
    with pytest.raises(ValueError):
        WriteIn(tenant_id=TENANT, text='x' * 20001)


@pytest.mark.asyncio
async def test_long_checks_do_not_invent_per_chunk_missing_terms_or_fences():
    document = '```\n' + ('plain ' * 2700) + '\n\n# End\n' + ('plain ' * 1000) + '\nrequired\n```'
    voice = parse_voice('Required words: required', 1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'matches': []}))) as http:
        report = await checkers.check(document, voice, http)
    assert not any(i['rule'] in {'required_term', 'F3'} for i in report['issues'])
    with pytest.raises(ValueError):
        await checkers.check('x' * 32001, voice, None)


@pytest.mark.asyncio
async def test_accepted_copy_resolves_tenant_reference_and_escapes_generated_body(env, monkeypatch, tmp_path):
    _, result = await accepted(env, text='Supplied <script> & {content} from this tenant.')
    monkeypatch.setenv('TANK_KEY_TISAN', 'offline-tisan')
    monkeypatch.setenv('TANK_KEY', 'offline-tisan')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    cls = httpx.AsyncClient
    def local_client(*args, **kwargs):
        kwargs['transport'] = httpx.ASGITransport(app=env.client._transport.app)
        return cls(*args, **kwargs)
    monkeypatch.setattr(httpx, 'AsyncClient', local_client)
    scaffold = scaffold_module()
    async def checked(*args):
        return [{'name': name, 'ok': True} for name in ('npm ci', 'npm run lint', 'npm run build', 'npm test')], ''
    monkeypatch.setattr(scaffold, 'run_checks', checked)
    payload = brief(['home', 'about', {'name': 'products', 'copy': result['write_id']}])
    built = await scaffold.execute(payload, str(TENANT), data_root=tmp_path)
    assert built['ok']
    archive = tmp_path / built['archive']
    with tarfile.open(archive) as tar:
        name = next(n for n in tar.getnames() if n.endswith('app/products/page.tsx'))
        source = tar.extractfile(name).read().decode()
        assert scaffold._jsx_text(result['text']) in source and '<script>' not in source and '{content}' not in source
        about = next(n for n in tar.getnames() if n.endswith('app/about/page.tsx'))
        assert tar.extractfile(about).read() == (ROOT / 'agents/tisan/templates/next-site/app/about/page.tsx').read_bytes()
    with pytest.raises(scaffold.ScaffoldError, match='Writing record unavailable'):
        await scaffold.execute(payload, str(OTHER), data_root=tmp_path)
    assert not (tmp_path / 'builds' / str(OTHER)).exists()
    for forged in [{'name': 'products', 'copy': 'raw supplied copy'},
                   {'name': 'products', 'copy': {'write_id': result['write_id'], 'text': 'forged'}}]:
        with pytest.raises(scaffold.ScaffoldError):
            scaffold.validate(brief([forged]))


@pytest.mark.asyncio
async def test_copy_endpoint_refuses_pending_unconfirmed_wrong_room_or_region(env, monkeypatch):
    thread, result = await written(env)
    monkeypatch.setenv('TANK_KEY_TISAN', 'offline-tisan')
    url = '/v1/trigger/copy/' + result['write_id']
    h = {'X-Tank-Key': 'offline-tisan', 'X-Tervory-Tenant': str(TENANT), 'X-Tervory-Home-Region': 'us-east'}
    assert (await env.client.get(url, params={'tenant_id': str(TENANT)}, headers=h)).status_code == 404
    _, card = await card_for(env, 'trigger.feedback', {'write_id': result['write_id'], 'status': 'accepted', 'changes': ''}, thread=thread)
    await confirm(env, card, user='admin', role='org:admin')
    assert (await env.client.get(url, params={'tenant_id': str(TENANT)}, headers=h)).status_code == 200
    for patch, tenant, code in [({'X-Tank-Key': 'wrong'}, TENANT, 401), ({'X-Tervory-Home-Region': 'za'}, TENANT, 403),
                                ({}, OTHER, 403), ({'X-Tervory-Tenant': str(OTHER)}, OTHER, 404)]:
        assert (await env.client.get(url, params={'tenant_id': str(tenant)}, headers={**h, **patch})).status_code == code
    async with command.editing(thread, command.Actor(TENANT, 'admin', False, tenant_admin=True)) as (_, _, state):
        for card in state['cards'].values():
            if card['tool'] == 'trigger.write':
                card['status'] = 'cancelled'
    assert (await env.client.get(url, params={'tenant_id': str(TENANT)}, headers=h)).status_code == 404


@pytest.mark.asyncio
async def test_one_accepted_write_enters_only_its_tenant_case_study(env):
    from test_second import proposal
    from case_study_sources import trigger
    from case_study_templates import empty_figures
    _, voice = await proposal(env, 'trigger.voice.set:\nBanned words: reliable', user='admin', role='org:admin')
    await confirm(env, voice, user='admin', role='org:admin')
    _, result = await accepted(env)
    now = datetime.now(timezone.utc)
    for tenant, region, expected in [(TENANT, 'us-east', 1), (OTHER, 'us-east', 0), (TENANT, 'za', 0)]:
        figures = empty_figures('trigger', now.date(), (now + timedelta(days=1)).date())
        async with env.pool.acquire() as conn:
            await trigger(conn, tenant, region, now - timedelta(hours=1), now + timedelta(hours=1), figures)
        assert figures['trigger.drafts']['value'] == expected
        assert figures['trigger.acceptance_rate']['value'] == (100 if expected else 0)
        assert figures['trigger.checker_issues_per_draft']['value'] == (result['report']['issue_count'] if expected else 0)
        assert figures['trigger.voice_rule_hits']['value'] == expected


def test_copy_defaults_legacy_rendering_and_standard_page_content(tmp_path):
    scaffold = scaffold_module()
    # Explicit None had the same meaning as an omitted pages list before Gate 2.
    normal = scaffold.validate(brief(None))
    assert normal['pages'] == ['home', 'about', 'contact', 'privacy'] and 'copies' not in normal
    injected = brief(['home', 'products'])
    injected['resolved_copy'] = {'products': 'unverified'}
    clean = scaffold.validate(injected)
    assert 'resolved_copy' not in clean
    old = scaffold.render_extra_page('Products')
    assert 'This page is ready for content.' not in old
    assert '<p' not in old
    assert '<h1 className="font-heading text-3xl">Products</h1>' in old
    assert scaffold.render_extra_page('Products', None) == old
    for page in ['home', 'about', 'contact', 'privacy']:
        normalized = scaffold.validate(brief([{'name': page, 'copy': str(uuid4())}]))
        normalized['resolved_copy'] = {page: 'Tenant <copy> & {literal}.'}
        target = tmp_path / page
        scaffold.write_project(normalized, target)
        source = (target / 'app' / ('page.tsx' if page == 'home' else page + '/page.tsx')).read_text()
        assert scaffold._jsx_text(normalized['resolved_copy'][page]) in source
        if page == 'contact':
            assert '<form action="/api/contact"' in source
    duplicate = str(uuid4())
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.validate(brief([{'name': 'products', 'copy': duplicate}, {'name': 'products', 'copy': str(uuid4())}]))


@pytest.mark.parametrize('copy', [None, 'Accepted <tenant> & {literal} text.'])
def test_extra_pages_never_write_default_sentence(copy, tmp_path):
    scaffold = scaffold_module()
    normalized = scaffold.validate(brief(['home', 'products']))
    if copy is not None:
        normalized['resolved_copy'] = {'products': copy}
    scaffold.write_project(normalized, tmp_path / 'project')
    source = (tmp_path / 'project/app/products/page.tsx').read_text()
    assert 'This page is ready for content.' not in source
    if copy is None:
        assert '<p' not in source
    else:
        assert source.count('<p') == 1
        assert f'<p className="mt-3">{scaffold._jsx_text(copy)}</p>' in source
        assert '<tenant>' not in source and '{literal}' not in source


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['auth', 'redirect', 'unavailable', 'tenant', 'write', 'text', 'size'])
async def test_copy_resolution_fails_closed_without_building(failure, monkeypatch, tmp_path):
    scaffold = scaffold_module()
    reference = str(uuid4())
    monkeypatch.setenv('TANK_KEY', 'offline-tisan')
    data = {'tenant_id': str(TENANT), 'write_id': reference, 'text': 'Accepted.'}
    status = {'auth': 401, 'redirect': 302, 'unavailable': 503}.get(failure, 200)
    if failure == 'tenant': data['tenant_id'] = str(OTHER)
    if failure == 'write': data['write_id'] = str(uuid4())
    if failure == 'text': data['text'] = {'unverified': 'copy'}
    if failure == 'size': data['text'] = 'x' * 20001
    cls = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: cls(**kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(status, json=data))))
    with pytest.raises(scaffold.ScaffoldError, match='Writing record unavailable'):
        await scaffold.execute(brief([{'name': 'products', 'copy': reference}]), str(TENANT), data_root=tmp_path)
    assert not (tmp_path / 'builds').exists()


@pytest.mark.asyncio
async def test_private_languagetool_transport_keeps_original_input_cap(env):
    from test_second import room_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room_app), base_url='http://room') as client:
        for size, status in [(20000, 200), (20001, 422)]:
            response = await client.post('/skala/languagetool', json={'tenant_id': str(TENANT), 'text': 'x' * size},
                                         headers={'X-Tank-Key': 'dummy-room-key'})
            assert response.status_code == status
    env.model.assert_not_called()
