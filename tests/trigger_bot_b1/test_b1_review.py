"""PR600 regressions: all upstreams are fakes; database is disposable."""
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request
import trigger_bot_api as api
import trigger_bot_sources as ingestion
from trigger_bot import Bot
from trigger_bot_contract import SourceAdd, SourceRemove
from trigger_bot_grounding import grounded, normalized_origin
from trigger_bot_shared import FailedKeyLimits, MemoryRateLimits, LimitDecision, client_address
import test_database
from test_database import Index, A

database = test_database.database
from test_engine import answer, passage, POINT


@pytest.mark.parametrize('text', ['R1,299', 'ZAR 1299', '1299 ZAR', '1299 rand',
    '12 dollars', '12 euros', '12 pounds', 'USD 12', '12 USD', 'Sold out, back soon',
    'out of stock', 'back order', 'in stock', 'low stock'])
@pytest.mark.asyncio
async def test_page_and_candidate_price_stock_are_refused(text):
    result, route, _, _ = await answer(passages=[passage(text=text)])
    assert result['state'] == 'handed_over'
    route.assert_not_awaited()
    result, _, _, _ = await answer(passages=[passage(text='There are 1299 targets and 12 targets.')],
        output={'answer': text, 'passage_ids': [str(POINT)]})
    assert result['answer'] is None


@pytest.mark.parametrize('token', ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun',
    'Jan', 'Feb', 'Mar', 'Apr', 'May 5', 'Jun', 'Jul', 'Aug', 'Sep', 'Sept',
    'Oct', 'Nov', 'Dec', 'weekend', 'tonight', 'next week', 'next month'])
def test_novel_dates_refused(token):
    assert grounded({'answer': token, 'passage_ids': [str(POINT)]}, [passage(text='Hours 9 to 5.')]) is None


@pytest.mark.parametrize('text', ['12 rand', 'R12', 'USD 12', '12 euros'])
def test_currency_is_not_just_a_supported_quantity(text):
    assert grounded({'answer': text, 'passage_ids': [str(POINT)]}, [passage(text='12 targets')]) is None


@pytest.mark.parametrize('text', ['R1,299', 'R1299.00', 'R 1299.00', 'ZAR 1299.00'])
def test_live_rig_decimal_currency_normalization(text):
    p = passage(kind='rig', text=json.dumps({'price': '1299.00', 'currency': 'ZAR'}))
    assert grounded({'answer': text, 'passage_ids': [str(POINT)]}, [p])
    assert not grounded({'answer': text, 'passage_ids': [str(POINT)]},
        [passage(kind='rig', text=json.dumps({'price': '1299.00', 'currency': 'USD'}))])


@pytest.mark.parametrize('question,approved', [
    ('Do you ship to Namibia?', 'Yes, we ship to Namibia.'),
    ('How much is shipping?', 'Shipping is 12 rand.')])
@pytest.mark.asyncio
async def test_approved_shipping_faq_never_calls_model(question, approved):
    result, route, _, _ = await answer(question, [passage(kind='faq', text=question, approved_answer=approved)])
    assert result['answer'] == approved
    route.assert_not_awaited()


def request(key='bad', address='198.51.100.1', origin='https://store.invalid'):
    return Request({'type': 'http', 'method': 'POST', 'path': '/v1/bot/messages',
        'client': ('10.1.1.1', 123), 'headers': [(b'x-forwarded-for', address.encode()),
        (b'x-bot-key', key.encode()), (b'origin', origin.encode())]})


@pytest.mark.asyncio
async def test_two_visitors_behind_one_proxy_have_separate_limits(monkeypatch):
    monkeypatch.setenv('TRIGGER_BOT_TRUSTED_PROXY_CIDRS', '10.0.0.0/8')
    one, two = client_address(request()), client_address(request(address='198.51.100.2'))
    assert one != two
    limits = MemoryRateLimits()
    for _ in range(10):
        assert not (await limits.consume(str(A), one, '/v1/rig/ask')).retry_after
    assert (await limits.consume(str(A), one, '/v1/rig/ask')).retry_after
    assert not (await limits.consume(str(A), two, '/v1/rig/ask')).retry_after
    monkeypatch.setattr(api, 'failed_keys', FailedKeyLimits(limit=2))
    monkeypatch.setattr(api, 'runtime', lambda: SimpleNamespace(box_region=lambda: 'us-east'))
    for _ in range(2):
        with pytest.raises(HTTPException) as error:
            await api.authenticate(request())
        assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        await api.authenticate(request())
    assert error.value.status_code == 429
    with pytest.raises(HTTPException) as error:
        await api.authenticate(request(address='198.51.100.2'))
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_lookup_failure_releases_failed_key_slot(monkeypatch):
    monkeypatch.setattr(api, 'failed_keys', FailedKeyLimits(limit=1))
    monkeypatch.setattr(api, 'runtime', lambda: SimpleNamespace(box_region=lambda: 'us-east',
        pool=lambda: SimpleNamespace(fetchrow=AsyncMock(side_effect=RuntimeError('offline')))))
    key = 'tb1.us-east.' + A.hex + '.rk_pub_' + 'a' * 48
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await api.authenticate(request(key))


@pytest.mark.parametrize('setting', ['', 'invalid', '0.0.0.0/0'])
@pytest.mark.asyncio
async def test_public_endpoint_fails_closed_without_proxy_config(monkeypatch, setting):
    monkeypatch.setenv('TRIGGER_BOT_TRUSTED_PROXY_CIDRS', setting)
    with pytest.raises(HTTPException) as error:
        await api.public_message(request())
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_public_response_allowlist(monkeypatch):
    monkeypatch.setenv('TRIGGER_BOT_TRUSTED_PROXY_CIDRS', '10.0.0.0/8')
    monkeypatch.setattr(api, 'authenticate', AsyncMock(return_value=(A, 'https://store.invalid', '198.51.100.1')))
    monkeypatch.setattr(api, 'runtime', lambda: SimpleNamespace(pool=lambda: None))
    monkeypatch.setattr(api, 'make_bot', lambda: None)
    monkeypatch.setattr(api, 'PgRateLimits', lambda _: SimpleNamespace(consume=AsyncMock(return_value=LimitDecision())))
    public = dict(state='bot', answer='Approved', sources=[], message_id='m', conversation_id='c', visitor_id='v')
    mocked = AsyncMock(return_value={**public, 'ledger_id': 'internal', 'lead_draft_id': 'internal',
        'quote_draft_id': 'internal', 'future_private': 'internal'})
    monkeypatch.setattr(api, 'ask', mocked)
    app = FastAPI()
    app.include_router(api.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
        response = await client.post('/v1/bot/messages', json={'text': 'Delivery?'})
    assert response.json() == public
    assert mocked.call_args.kwargs['address'] == '198.51.100.1'


@pytest.mark.asyncio
async def test_keys_rotate_origin_normalizes_and_remove_revokes(database, monkeypatch):
    runtime = SimpleNamespace(pool=lambda: database, box_region=lambda: 'us-east')
    bot = Bot(runtime)
    monkeypatch.setattr(api, 'make_bot', lambda: bot)
    monkeypatch.setattr(api, 'runtime', lambda: runtime)
    args = SourceAdd(kind='website', title='Store', url='https://STORE.invalid:443/')
    first = await api.execute('source.add', args, SimpleNamespace(tenant_id=A), uuid4())
    second = await api.execute('source.add', args, SimpleNamespace(tenant_id=A), uuid4())
    assert first['status'] == second['status'] == 'queued'
    assert normalized_origin('https://STORE.invalid:443') == 'https://store.invalid'
    assert (await api.authenticate(request(second['embed_key'])))[0] == A
    with pytest.raises(HTTPException) as error:
        await api.authenticate(request(first['embed_key']))
    assert error.value.status_code == 403
    await api.execute('source.remove', SourceRemove(source_id=second['source_id']),
                      SimpleNamespace(tenant_id=A), uuid4())
    with pytest.raises(HTTPException) as error:
        await api.authenticate(request(second['embed_key']))
    assert error.value.status_code == 403
    assert json.loads(await database.fetchval('SELECT origins FROM tank.trigger_bot_config WHERE tenant_id=$1', A)) == []


@pytest.mark.asyncio
async def test_symmetric_faq_score_in_lexical_and_vector_paths(database):
    index = Index()
    service = ingestion.Sources(database, 'us-east', index)
    question = 'Can I return a custom engraved item?'
    source = await service.add(A, uuid4(), 'faq', question,
        content=json.dumps({'question': question, 'answer': 'Custom engraving cannot be returned.'}))
    await service.refresh(A, source)
    point = await database.fetchval('SELECT id FROM tank.trigger_bot_passages WHERE tenant_id=$1', A)
    index.points = [(point, 1.0)]
    rows = await service.search(A, 'can I return item')
    assert rows and rows[0].score < .92
    result, _, _, _ = await answer('can I return item', rows)
    assert result['outcome'] != 'faq'


@pytest.mark.parametrize('status,allowed', [(404, True), (403, True), (503, False), (301, False)])
@pytest.mark.asyncio
async def test_robots_status_uses_guarded_stream(monkeypatch, status, allowed):
    @asynccontextmanager
    async def stream(url, **kwargs):
        assert url == 'https://store.invalid/robots.txt'
        yield httpx.Response(status, content=b'', request=httpx.Request('GET', url))
    monkeypatch.setattr(ingestion, 'public_stream', stream)
    # Retain the real crawl default while replacing its page getter by identity.
    async def page(url, **kwargs):
        assert not url.endswith('robots.txt')
        return b'<p>Store policy</p>', {'content-type': 'text/html'}
    monkeypatch.setattr(ingestion, 'public_get', page)
    pages = await ingestion.crawl('https://store.invalid/', get=page)
    assert bool(pages) == allowed


@pytest.mark.asyncio
async def test_mail_visitor_and_tenant_hold_keeps_handover_without_send(database, monkeypatch):
    runtime = SimpleNamespace(pool=lambda: database, box_region=lambda: 'us-east')
    bot = Bot(runtime)
    bot.retrieve = AsyncMock(return_value=[])
    bot.receipt = AsyncMock(return_value=uuid4())
    sender = SimpleNamespace(send=AsyncMock())
    monkeypatch.setattr('trigger_bot.SmtpMailer.from_env', lambda: sender)
    await database.execute("INSERT INTO tank.trigger_bot_config(tenant_id,enabled,handover_email) VALUES($1,true,'store@example.invalid')", A)
    for _ in range(6):
        result = await bot.ask(A, 'Help', address='198.51.100.1')
    assert result['state'] == 'handed_over' and result['notification'] == 'held'
    assert sender.send.await_count == 5
    result = await bot.ask(A, 'Help', address='198.51.100.2')
    assert result['notification'] == 'sent'
    # Seed the real tenant ceiling, including the next window to avoid minute-boundary flakes.
    async with database.acquire() as conn, conn.transaction():
        window = await conn.fetchval("SELECT floor(extract(epoch FROM clock_timestamp())/60)::bigint")
        for current in (window, window + 1):
            await conn.execute('''INSERT INTO tank.trigger_bot_windows(tenant_id,window_id,salt)
                VALUES($1,$2,$3) ON CONFLICT DO NOTHING''', A, current, b'offline-test-salt')
            await conn.execute('''INSERT INTO tank.trigger_bot_limits(tenant_id,window_id,route,client_hash,hits)
                VALUES($1,$2,'quotes',$3,600) ON CONFLICT(tenant_id,window_id,route,client_hash)
                DO UPDATE SET hits=600''', A, current, b'')
    result = await bot.ask(A, 'Help', address='198.51.100.3')
    assert result['state'] == 'handed_over' and result['notification'] == 'held'
    assert sender.send.await_count == 6


@pytest.mark.asyncio
async def test_queue_states_lease_and_removal_win(database, monkeypatch):
    service = ingestion.Sources(database, 'us-east', Index())
    identity = await service.add(A, uuid4(), 'website', 'Store', 'https://store.invalid/')
    status = lambda: database.fetchval('SELECT status FROM tank.trigger_bot_sources WHERE tenant_id=$1 AND id=$2', A, identity)
    assert await status() == 'queued'
    async def crawl(url):
        assert await status() == 'indexing'
        # A second worker cannot acquire a still-live indexing lease.
        await service.refresh(A, identity)
        return [{'text': 'Store policy', 'url': url}]
    monkeypatch.setattr(ingestion, 'crawl', crawl)
    await service.refresh(A, identity)
    assert await status() == 'ready'
    monkeypatch.setattr(ingestion, 'crawl', AsyncMock(side_effect=ValueError('offline')))
    with pytest.raises(ValueError):
        await service.refresh(A, identity)
    assert await status() == 'failed'
    async def remove(url):
        await database.execute("UPDATE tank.trigger_bot_sources SET status='removed' WHERE tenant_id=$1 AND id=$2", A, identity)
        return [{'text': 'Removed text', 'url': url}]
    monkeypatch.setattr(ingestion, 'crawl', remove)
    await service.refresh(A, identity)
    assert await status() == 'removed'
    assert not await service.search(A, 'Removed text')


@pytest.mark.asyncio
async def test_bot_confirm_card_uses_main_adapter_and_bot_prepare(database, monkeypatch):
    import command
    actor = command.Actor(A, 'review-admin', True)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', actor.user_id)
    action = command.PlannedAction(tool='trigger.bot.source.add', arguments={
        'kind': 'website', 'title': 'Store', 'url': 'https://store.invalid/'})
    row = {'tenant_id': A, 'user_id': actor.user_id, 'thread_id': uuid4()}
    state = {'cards': {}, 'messages': []}
    monkeypatch.setattr(command, 'event', AsyncMock())
    monkeypatch.setattr(command, 'step', AsyncMock())
    # Generic Trigger preparation must never swallow a bot action after the merge.
    monkeypatch.setattr('trigger_commands.prepare', AsyncMock(side_effect=AssertionError('wrong adapter')))
    async with database.acquire() as conn:
        card = await command.propose_action(conn, row, state, action, actor)
    assert card['tool'] == action.tool and card['status'] == 'pending'
    assert card['kind'] == command.action_adapter(action, actor).kind
    assert command.public_card(card)['arguments']['url'] == 'https://store.invalid/'
    command.event.assert_awaited_once()
