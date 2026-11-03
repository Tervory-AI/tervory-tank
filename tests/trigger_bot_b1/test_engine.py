"""Offline B1 contracts. No real model, encoder inference, mail or outside HTTP."""
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import command
import httpx
import pytest
import trigger_bot_api as api
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from trigger_bot_contract import ConfirmDraft, PublicMessage, SourceAdd
from trigger_bot_engine import respond
from trigger_bot_grounding import Passage, eligible, fuse, grounded
from trigger_bot_shared import MemoryRateLimits, RigError, issue_embed_key
from trigger_bot_sources import crawl
from trigger_commands import CONFIRMED

A, B, SOURCE, POINT, CARD = [UUID(int=n) for n in (11, 12, 13, 14, 15)]


def passage(**kwargs):
    return replace(Passage(POINT, A, SOURCE, 'Delivery takes 3 days.', 'https://store.invalid/delivery',
                           'Delivery', 'website', 1.0), **kwargs)


async def answer(question='When is delivery?', passages=None, output=None):
    route = AsyncMock(return_value=SimpleNamespace(content=json.dumps(output or {
        'answer': 'Delivery takes 3 days.', 'passage_ids': [str(POINT)]}), ledger_id=CARD))
    receipts = AsyncMock(return_value=CARD)
    rig = AsyncMock(side_effect=lambda tenant, p: p)
    voice = AsyncMock(return_value={})
    result = await respond(A, question, retrieve=AsyncMock(return_value=passages if passages is not None else [passage()]),
                           route=route, live_rig=rig, receipt=receipts, voice=voice)
    return result, route, receipts, rig


@pytest.mark.asyncio
async def test_sources_are_tenant_bound_in_both_indexes_and_at_answer():
    assert eligible(A, [passage(tenant_id=B)]) == []
    assert fuse(A, [], [{'id': POINT, 'tenant_id': B, 'score': 1.0}]) == []
    result, route, _, _ = await answer(passages=[passage(tenant_id=B)])
    assert result['answer'] is None and result['sources'] == [] and result['state'] == 'handed_over'
    route.assert_not_awaited()


@pytest.mark.parametrize('output', [
    {'answer': 'No source.', 'passage_ids': []},
    {'answer': 'Delivery takes 99 days.', 'passage_ids': [str(POINT)]},
    {'answer': 'Delivery on Monday.', 'passage_ids': [str(POINT)]},
    {'answer': 'Visit https://invented.invalid', 'passage_ids': [str(POINT)]},
    {'answer': 'Delivery takes 3 days.', 'passage_ids': [str(uuid4())]},
    {'answer': 'Delivery takes 3 days.', 'passage_ids': [str(POINT)], 'model': 'hidden'},
])
@pytest.mark.asyncio
async def test_unsourced_novel_number_date_url_and_unknown_citations_handover(output):
    result, route, receipts, _ = await answer(output=output)
    assert result['state'] == 'handed_over' and result['answer'] is None and result['sources'] == []
    assert result['retrieved'] == [str(POINT)] and result['cited'] == []
    assert route.await_count == 1
    receipts.assert_not_awaited()  # Keep the real attempted route's receipt, never claim it was free.


@pytest.mark.asyncio
async def test_approved_faq_has_zero_model_calls_and_code_receipt():
    result, route, receipts, _ = await answer('When is delivery?', [passage(
        kind='faq', text='When is delivery?', approved_answer='Delivery takes 3 days.')])
    assert result['answer'] == 'Delivery takes 3 days.' and result['outcome'] == 'faq'
    assert result['sources'][0]['url'] == 'https://store.invalid/delivery'
    route.assert_not_awaited()
    receipts.assert_awaited_once_with(A, 'trigger.bot.answer')


@pytest.mark.asyncio
async def test_changed_faq_quantity_or_negation_is_not_a_free_approved_match():
    result, route, _, _ = await answer('Do not deliver 9 items?', [passage(
        kind='faq', text='Do deliver 3 items?', approved_answer='Delivery is supported.')])
    assert result['outcome'] != 'faq' and route.await_count == 1


@pytest.mark.asyncio
async def test_live_rig_price_wins_and_exact_record_link_is_returned():
    old = passage(kind='rig', text='Price ZAR 999', sku='sku-1')
    fresh = replace(old, text='Price ZAR 129', url='https://store.invalid/products/real-record')
    live = AsyncMock(return_value=fresh)
    async def route(tenant, messages):
        assert tenant == A and '999' not in messages[-1]['content']
        assert '129' in messages[-1]['content']
        return SimpleNamespace(content=json.dumps({'answer': 'Price ZAR 129', 'passage_ids': [str(POINT)]}), ledger_id=CARD)
    result = await respond(A, 'What is the price?', retrieve=AsyncMock(return_value=[old, passage(text='Price ZAR 999', id=UUID(int=17))]),
        route=route, live_rig=live, receipt=AsyncMock(return_value=CARD), voice=AsyncMock(return_value={}))
    assert result['answer'] == 'Price ZAR 129'
    assert result['sources'][0]['url'] == fresh.url and result['sources'][0]['sku'] == 'sku-1'
    live.assert_awaited_once_with(A, old)
    assert grounded({'answer': 'Price USD 129', 'passage_ids': [str(POINT)]}, [fresh]) is None


@pytest.mark.asyncio
async def test_no_live_rig_means_no_price_answer_from_old_page_or_faq():
    result, route, _, _ = await answer('What is the price?', [passage(text='Price ZAR 999')])
    assert result['state'] == 'handed_over'
    route.assert_not_awaited()


@pytest.mark.asyncio
async def test_robots_disallow_same_site_only_and_per_page_limit():
    fetched = []
    async def get(url, **kwargs):
        fetched.append(url)
        if url.endswith('/robots.txt'):
            return b'User-agent: *\nDisallow: /private\n', {}
        return (b'<p>Owned page</p><a href="/private">private</a><a href="https://other.invalid">other</a>'
                b'<a href="/next">next</a>'), {'content-type': 'text/html'}
    pages = await crawl('https://store.invalid/', get)
    assert len(pages) == 2
    assert all('checked_at' in p for p in pages)
    assert 'https://store.invalid/private' not in fetched and not any('other.invalid' in p for p in fetched)


@pytest.mark.parametrize('origins', [['http://store.invalid'], ['https://store.invalid/path'], ['https://*.invalid'], ['https://user@store.invalid'], []])
@pytest.mark.asyncio
async def test_embed_issuer_reuses_exact_https_origin_validation(origins):
    store = SimpleNamespace(put_key=AsyncMock())
    with pytest.raises(RigError):
        await issue_embed_key(store, str(A), origins)
    store.put_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_abuse_limits_bound_clients_without_joinable_raw_addresses():
    limits = MemoryRateLimits(clock=lambda: 123)
    for _ in range(10):
        assert (await limits.consume(str(A), '192.0.2.1', '/v1/rig/ask')).retry_after == 0
    assert (await limits.consume(str(A), '192.0.2.1', '/v1/rig/ask')).retry_after > 0
    assert (await limits.consume(str(B), '192.0.2.1', '/v1/rig/ask')).retry_after == 0
    assert '192.0.2.1' not in repr(limits.windows)


@pytest.mark.parametrize('user,admin', [('member', False), ('admin', True)])
def test_members_never_gain_bot_and_admins_never_gain_generic_crm(user, admin):
    tools = command.allowed_tools(command.Actor(A, user, False, frozenset(command.SQUADS), admin))
    assert ('trigger.bot.ask' in tools) == admin
    assert 'trigger.crm.write' not in tools


@pytest.mark.parametrize('text', ['', 'x' * 2001])
def test_public_message_limits_and_identity_injection(text):
    with pytest.raises(ValidationError):
        PublicMessage(text=text)
    with pytest.raises(ValidationError):
        PublicMessage(text='A question', tenant_id=str(B))
    with pytest.raises(ValidationError):
        SourceAdd(kind='document', title='Document', attachment_name='a.txt', content='not an attachment')


@pytest.mark.asyncio
async def test_unconfirmed_bot_action_never_reaches_execution(monkeypatch):
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder')
    actor = command.Actor(A, 'founder', True)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[command.identity] = lambda: actor
    execute = AsyncMock()
    monkeypatch.setattr(api, 'execute', execute)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://local.invalid') as client:
        result = await client.post('/v1/trigger/bot/lead.confirm', json={'draft_id': str(SOURCE), 'approved': True})
        assert result.status_code == 422
        result = await client.post('/v1/trigger/bot/lead.confirm', json={'draft_id': str(SOURCE)})
        assert result.status_code == 409
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_crm_binding_fails_before_draft_claim_or_upstream(monkeypatch):
    monkeypatch.setenv('TRIGGER_CRM_TENANT_BINDINGS', '{}')
    actor = command.Actor(A, 'admin', False, tenant_admin=True)
    pool = SimpleNamespace(fetchrow=AsyncMock())
    bot = SimpleNamespace(pool=pool)
    args = ConfirmDraft(draft_id=SOURCE)
    bound = CONFIRMED.set((A, 'admin', CARD, 'trigger.bot.lead.confirm', args.model_dump(mode='json', exclude_none=True)))
    try:
        with pytest.raises(HTTPException) as error:
            await api.confirm_draft(bot, actor, 'lead.confirm', args, CARD)
        assert error.value.status_code == 503
        pool.fetchrow.assert_not_awaited()
    finally:
        CONFIRMED.reset(bound)


@pytest.mark.parametrize('currency', ['USD', 'R', 'CAD'])
def test_currency_attached_to_existing_amount_cannot_change_its_unit(currency):
    evidence = passage(text='Price ZAR3', kind='rig')
    assert grounded({'answer': f'Price {currency}3', 'passage_ids': [str(POINT)]}, [evidence]) is None
    assert grounded({'answer': 'Price ZAR3', 'passage_ids': [str(POINT)]}, [evidence]) is not None


def test_reused_rig_security_and_smtp_implementations_keep_original_behavior():
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    shared = ast.parse((root / 'tank/trigger_bot_shared.py').read_text().replace('tank.trigger_bot_windows', 'agent_rig.rate_windows').replace('tank.trigger_bot_limits', 'agent_rig.rate_counts'))
    def definition(tree, name):
        return ast.dump(next(node for node in tree.body if getattr(node, 'name', None) == name), include_attributes=False)
    for original, names in [
        ('agents/rig/rigbox/quotes/limits.py', ['FailedKeyLimits', 'MemoryRateLimits', 'PgRateLimits']),
        ('agents/rig/rigbox/quotes/keys.py', ['issue_embed_key']),
        ('agents/rig/rigbox/reserve.py', ['SmtpMailer']),
    ]:
        source = ast.parse((root / original).read_text())
        for name in names:
            assert definition(shared, name) == definition(source, name), name


@pytest.mark.asyncio
async def test_contact_details_without_an_enquiry_do_not_create_a_lead():
    from trigger_bot import Bot
    pool = SimpleNamespace(execute=AsyncMock())
    bot = Bot(SimpleNamespace(pool=lambda: pool, box_region=lambda: 'us-east'))
    contact_only = 'Name: Typed name\nEmail: typed@offline.invalid\n'
    assert await bot.lead_draft(A, SOURCE, contact_only, None) is None
    pool.execute.assert_not_awaited()
    draft = await bot.lead_draft(A, SOURCE, contact_only + 'Please quote the item.', None)
    assert isinstance(draft, UUID)
    stored = json.loads(pool.execute.await_args.args[-1])
    assert stored['first_name'] == 'Typed name' and stored['email'] == 'typed@offline.invalid'
    assert stored['description'] == contact_only + 'Please quote the item.'
