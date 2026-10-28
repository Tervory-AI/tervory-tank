"""Offline Trigger contracts. All fixture brands stay in tests, never runtime seeds."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import yaml
from fastapi import FastAPI
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'agents'))
sys.path.insert(0, str(ROOT / 'agents/_chassis'))
spec = importlib.util.spec_from_file_location('zenas_scope', ROOT / 'agents/zenas/core/scope_rules.py')
zenas_scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zenas_scope)
sys.modules['zenas_scope'] = zenas_scope

import command
import trigger_routes
from trigger.checkers import ROOT as ROOM, SKIPPED, check, local_checks
from trigger.service import CheckIn, WriteIn, check_text, legal_request, write
from trigger.voice import BOOKS, Voice, VoiceStore

TENANT = UUID('00000000-0000-0000-0000-000000000011')
OTHER = UUID('00000000-0000-0000-0000-000000000012')


def voice(**kw):
    return Voice(brand='Offline test brand', status='live', revision=1, **kw)


class VoiceDB:
    def __init__(self):
        self.rows = {}

    async def fetchval(self, sql, tenant, *values):
        if sql.startswith('SELECT'):
            assert 'WHERE tenant_id=$1' in sql
            return self.rows.get(tenant)
        assert 'ON CONFLICT(tenant_id)' in sql
        raw, revision = values
        old = json.loads(self.rows.get(tenant, '{"revision":0}'))
        if revision <= old['revision']:
            return None
        self.rows[tenant] = raw
        return revision


def lt_client(payload=None, status=200):
    def respond(request):
        assert str(request.url) == 'http://trigger-languagetool:8081/v2/check'
        assert request.method == 'POST'
        assert b'language=en-US' in request.content
        return httpx.Response(status, json=payload if payload is not None else {'matches': []})
    return httpx.AsyncClient(transport=httpx.MockTransport(respond), trust_env=False)


def test_real_free_checkers_find_issues():
    result = local_checks('This is very unique. It was completed by the team.\n```\nunclosed', None)
    rules = {(i['source'], i['rule']) for i in result['issues']}
    assert any(source == 'proselint' for source, _ in rules)
    assert ('readability', 'passive_voice') in rules
    assert ('practical-prose', 'F3') in rules
    assert 'RULE-04' in SKIPPED
    assert not any(rule in SKIPPED for source, rule in rules if source == 'agent-style')


def test_voice_changes_code_rules_and_respects_word_boundaries():
    text = 'The catapult was built with care. The cat is very quiet today.'
    result = local_checks(text, voice(bannedTerms=['cat'], requiredTerms=['Reliable'], maxSentenceWords=5))
    banned = [i for i in result['issues'] if i['rule'] == 'banned_term']
    assert len(banned) == 1 and text[banned[0]['offset']:][:3] == 'cat'
    assert any(i['rule'] == 'required_term' for i in result['issues'])
    assert any(i['rule'] == 'sentence_length' for i in result['issues'])
    other = local_checks(text, voice(requiredTerms=['with care']))
    assert not any(i['source'] == 'voice' for i in other['issues'])


def test_voice_has_no_example_defaults_and_rejects_unsafe_format():
    assert voice().bannedTerms == []
    assert len(BOOKS) == 11
    for payload in ({'brand': 'Test', 'status': 'sample', 'revision': 1},
                    {'brand': 'Test', 'status': 'live', 'revision': 1, 'stylebook': '../../escape'},
                    {'brand': 'Test', 'status': 'live', 'revision': 1, 'bannedTerms': [''], 'requiredTerms': []}):
        with pytest.raises(ValidationError):
            Voice.model_validate(payload)
    with pytest.raises(ValidationError):
        voice(bannedTerms=['No'], requiredTerms=['no'])


@pytest.mark.asyncio
async def test_tenant_voice_isolation_and_stale_update():
    store = VoiceStore(VoiceDB())
    await store.put(TENANT, voice(bannedTerms=['wrong']))
    assert await store.get(OTHER) is None
    await store.put(OTHER, voice(requiredTerms=['right']))
    assert (await store.get(TENANT)).requiredTerms == []
    assert (await store.get(OTHER)).bannedTerms == []
    with pytest.raises(ValueError, match='increase'):
        await store.put(TENANT, voice())


@pytest.mark.asyncio
async def test_check_calls_only_internal_checker_and_preserves_text():
    store = VoiceStore(VoiceDB())
    await store.put(TENANT, voice(bannedTerms=['wrong']))
    async with lt_client({'matches': [{'rule': {'id': 'THIS_NNS'}, 'message': 'Known issue', 'offset': 0, 'length': 4}]}) as http:
        text = 'This are wrong.'
        result = await check_text(CheckIn(tenant_id=TENANT, text=text), store, http)
        assert result['text'] == text
        assert result['model_calls'] == result['report']['model_calls'] == 0
        assert result['report']['voice_revision'] == 1
        assert 'THIS_NNS' in result['summary'] and 'Banned term: wrong' in result['summary']
        other = await check_text(CheckIn(tenant_id=OTHER, text=text), store, http)
        assert other['report']['voice_revision'] is None
        assert not any(i['source'] == 'voice' for i in other['report']['issues'])


@pytest.mark.asyncio
@pytest.mark.parametrize('payload,status', [({}, 503), ({'matches': None}, 200),
    ({'matches': [], 'warnings': {'incompleteResults': True}}, 200)])
async def test_checker_failure_is_explicit(payload, status):
    async with lt_client(payload, status) as http:
        result = await check('This is very unique.', None, http)
    assert result['complete'] is False and result['checker_errors']
    assert result['issues']  # Local checks are still returned.


@pytest.mark.asyncio
async def test_write_routes_once_through_tank_with_own_voice_and_receipt():
    store = VoiceStore(VoiceDB())
    await store.put(OTHER, voice(requiredTerms=['OTHER_PRIVATE_TERM']))
    tank = SimpleNamespace(route=AsyncMock(return_value={'content': 'A very unique product.',
                            'ledger_id': str(uuid4()), 'cost_usd': 0.01, 'model': 'offline-router'}))
    body = WriteIn(tenant_id=TENANT, text='Describe this product.', voice=voice(requiredTerms=['reliable']))
    async with lt_client() as http:
        result = await write(body, store, tank, http)
        assert tank.route.await_count == 1
        tenant, task, messages = tank.route.call_args.args
        assert tenant == str(TENANT) and task == 'trigger.write'
        assert 'reliable' in messages[0]['content'] and 'OTHER_PRIVATE_TERM' not in json.dumps(messages)
        assert result['ledger_id'] == tank.route.return_value['ledger_id']
        assert result['report']['model_calls'] == 0 and result['report']['complete']
        assert any(i['rule'] == 'required_term' for i in result['report']['issues'])
        with pytest.raises(ValueError, match='required'):
            await write(WriteIn(tenant_id=uuid4(), text='Describe this product.'), store, tank, http)
        assert tank.route.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['Draft a nondisclosure agreement.', 'Draft a criminal defence pleading.', 'Write a last will.'])
async def test_legal_requests_delegate_without_drafting_or_checking(text):
    tank = SimpleNamespace(route=AsyncMock(side_effect=AssertionError('No model')))
    http = SimpleNamespace(post=AsyncMock(side_effect=AssertionError('No check')))
    result = await write(WriteIn(tenant_id=TENANT, text=text), VoiceStore(VoiceDB()), tank, http)
    assert result == {'delegate': 'zenas.draft'}
    tank.route.assert_not_called()
    http.post.assert_not_called()


def test_future_tense_copy_is_not_a_will():
    assert not legal_request(WriteIn(tenant_id=TENANT, text='This tool will help you write a short description.'))
    assert zenas_scope.classify('Draft a criminal defence pleading.', 'us')['criminal'] is True


@pytest.mark.asyncio
async def test_code_plan_keeps_confirmation_without_model(monkeypatch):
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder')
    receipt = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(trigger_routes, 'code_receipt', receipt)
    runtime = SimpleNamespace(Message=lambda **k: k, RouteRequest=lambda **k: k,
                              box_region=lambda: 'us-east', run_route=AsyncMock(side_effect=AssertionError('No model')))
    monkeypatch.setitem(sys.modules, 'main', runtime)
    actor = command.Actor(TENANT, 'founder', True)
    result = await command.route_turn(actor, [{'role': 'user', 'content': 'Trigger, check: This are a test.'}])
    plan = command.parse_plan(result.content, actor)
    assert plan.actions[0].tool == 'trigger.check'
    assert plan.actions[0].arguments == {'text': 'This are a test.'}
    runtime.run_route.assert_not_called()
    receipt.assert_awaited_once()
    assert await trigger_routes.code_plan(actor, [{'role': 'user', 'content': 'ordinary question'}], None) is None
    assert 'trigger.check' not in command.allowed_tools(command.Actor(TENANT, 'client', False))


@pytest.mark.asyncio
async def test_adapter_http_tenant_ownership_and_zero_receipt(monkeypatch):
    app = FastAPI()
    app.include_router(trigger_routes.router)
    actor = command.Actor(TENANT, 'founder', True)
    app.dependency_overrides[command.identity] = lambda: actor
    room = AsyncMock(return_value={'text': 'This are a test.', 'summary': 'Grammar issue', 'report': {}})
    receipt = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(trigger_routes, 'room', room)
    monkeypatch.setattr(trigger_routes, 'code_receipt', receipt)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank') as http:
        response = await http.post('/v1/trigger/check', json={'text': 'This are a test.'})
        assert response.status_code == 200
        assert response.json()['cost_usd'] == response.json()['model_calls'] == 0
        assert room.call_args.args[1]['tenant_id'] == str(TENANT)
        assert receipt.call_args.args == (TENANT, 'trigger.check')
        for payload, status in [({'text': 'text', 'tenant_id': str(OTHER)}, 403),
                                ({'text': 'text', 'url': 'https://example.com'}, 422),
                                ({'text': 'x' * 20001}, 422)]:
            response = await http.post('/v1/trigger/check', json=payload)
            assert response.status_code == status
        actor = command.Actor(TENANT, 'client', False)
        response = await http.post('/v1/trigger/check', json={'text': 'text'})
        assert response.status_code == 403
        assert room.await_count == 1


@pytest.mark.asyncio
async def test_zenas_handoff_keeps_result_notice_and_scope(monkeypatch):
    app = FastAPI()
    seen = []
    @app.post('/v1/zenas/drafts', status_code=201)
    async def draft(body: dict):
        seen.append(body)
        return {'text': 'Civil draft from Zenas', 'model_calls': 0, 'notice': 'legal information, not legal advice'}
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(app=app, TANK_API_KEY='dummy-workspace-key', box_region=lambda: 'us-east'))
    result = await trigger_routes.zenas_draft({'template': 'nda', 'jurisdiction': 'us', 'text': 'Draft an NDA.'}, command.Actor(TENANT, 'founder', True))
    assert result.status_code == 201
    body = json.loads(result.body)
    assert body['text'] == 'Civil draft from Zenas' and body['summary'] == body['notice']
    assert seen[0]['tenant_id'] == str(TENANT) and seen[0]['home_region'] == 'us-east'
    assert 'provider' not in seen[0]


def test_sources_match_pins_and_internal_room_limits():
    for filename, digest in json.loads((ROOM / 'sources/checksums.json').read_text()).items():
        assert hashlib.sha256((ROOM / filename).read_bytes()).hexdigest() == digest, filename
    compose = yaml.safe_load((ROOM / 'docker-compose.yml').read_text())
    server = compose['services']['trigger-languagetool']
    assert '@sha256:' in server['image'] and server['mem_limit'] == '2g'
    assert server['networks'] == ['checkers'] and not server.get('ports')
    assert compose['networks']['checkers']['internal'] is True
    assert server['entrypoint'][0] == 'java'  # No entrypoint downloading optional models.
    root = yaml.safe_load((ROOT / 'docker-compose.yml').read_text())
    corridor = [name for name, service in root['services'].items() if 'tervory-gw-trigger' in service.get('networks', [])]
    assert set(corridor) == {'tank', 'postgres'}
    assert 'external' not in root['networks']['tervory-gw-trigger']


def test_stylebook_changes_checks_without_semantic_scorer():
    from trigger.checkers import BOOK_TERMS
    for book, terms in BOOK_TERMS.items():
        guide = (ROOM / 'sources/stylebooks' / book / 'SKILL.md').read_text()
        avoid = guide.split('## Avoid')[1].split('## ')[0]
        assert all(f'`{term}`' in avoid for term in terms)
    selected = local_checks('Please simply continue.', voice(stylebook='govuk'))
    assert len([i for i in selected['issues'] if i['rule'] == 'avoid_candidate']) == 2
    default = local_checks('Please simply continue.', voice())
    assert not any(i['source'] == 'stylebook' for i in default['issues'])


def test_voice_length_setting_overrides_upstream_default():
    text = ' '.join(['word'] * 35) + '.'
    assert any(i['rule'] == 'RULE-12' for i in local_checks(text, None)['issues'])
    assert not any(i['rule'] in {'RULE-12', 'sentence_length'} for i in local_checks(text, voice(maxSentenceWords=40))['issues'])
