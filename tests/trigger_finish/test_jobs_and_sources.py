import asyncio
from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace
from uuid import UUID
from uuid import uuid4
import json
from pathlib import Path
import sys
from unittest.mock import AsyncMock

import httpx
import pytest

import trigger_bot
import trigger_bot_sources
import trigger_publisher
from patch_runtime import patched

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'trigger_bot_b1'))
import test_database as database_proofs

database = database_proofs.database
Index = database_proofs.Index


@pytest.mark.asyncio
async def test_long_approved_faq_can_answer_without_model(database):
    question = ' '.join(f'term{i:03}' for i in range(180))
    assert len(question) <= 2000 and len(question.split()) > 160
    await approved_faq(database, question)


@pytest.mark.asyncio
async def test_stopword_only_approved_faq_uses_code(database):
    await approved_faq(database, 'How are you?')


async def approved_faq(database, question):
    from trigger_bot_engine import respond
    namespace = patched(trigger_bot_sources, ['Sources'])
    index = Index()
    index.query = AsyncMock(side_effect=AssertionError('Exact FAQ needs no vector inference'))
    service = namespace['Sources'](database, 'us-east', index)
    tenant, other = UUID(int=11), UUID(int=12)
    for owner, answer in [(tenant, 'placeholder approved answer'), (other, 'placeholder foreign answer')]:
        source = await service.add(owner, uuid4(), 'faq', 'placeholder FAQ',
            content=json.dumps({'question': question, 'answer': answer}))
        await service.refresh(owner, source)
    route, live, voice = AsyncMock(), AsyncMock(), AsyncMock()
    receipt = AsyncMock(return_value=UUID(int=99))
    result = await respond(tenant, question, retrieve=service.search, route=route,
        live_rig=live, receipt=receipt, voice=voice)
    assert result['outcome'] == 'faq'
    assert result['answer'] == 'placeholder approved answer'
    assert result['ledger_id'] == str(UUID(int=99))
    receipt.assert_awaited_once_with(tenant, 'trigger.bot.answer')
    route.assert_not_awaited()
    live.assert_not_awaited()
    voice.assert_not_awaited()
    index.query.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['publication', 'retention'])
@pytest.mark.parametrize('cancel', [False, True])
async def test_scheduled_batches_isolate_failures_and_preserve_cancellation(kind, cancel, caplog):
    original = trigger_publisher if kind == 'publication' else trigger_bot
    name = 'publish_due' if kind == 'publication' else 'retention_due'
    namespace = patched(original, [name])
    first, second = UUID(int=11), UUID(int=12)
    active, attempted, receipts = [], [], []
    @contextmanager
    def scope(tenant, administrative=False):
        active.append((tenant, administrative))
        try:
            yield
        finally:
            active.pop()
    async def fetch(sql):
        assert active == [(None, True)]
        return [{'tenant_id': first}, {'tenant_id': second}]
    async def action(tenant):
        assert active == [(tenant, False)]
        attempted.append(tenant)
        if tenant == first:
            if cancel:
                raise asyncio.CancelledError()
            raise RuntimeError('placeholder private provider body')
        receipts.append(tenant)
    pool = SimpleNamespace(fetch=fetch)
    runtime = SimpleNamespace(admin_pool=lambda: pool, _admin_pool=pool, pool=lambda: pool)
    namespace['tenant_scope'] = scope
    if kind == 'publication':
        namespace['Publisher'] = lambda service: SimpleNamespace(once=action)
    else:
        namespace['Bot'] = lambda runtime: SimpleNamespace(retain_conversations=action)
    if cancel:
        with pytest.raises(asyncio.CancelledError):
            await namespace[name](runtime)
        assert attempted == [first] and receipts == []
    else:
        await namespace[name](runtime)
        assert attempted == [first, second] and receipts == [second]
        assert 'RuntimeError' in caplog.text
        assert 'placeholder private provider body' not in caplog.text
    assert active == []


@pytest.mark.asyncio
@pytest.mark.parametrize('status,allowed', [(200, True), (404, True), (429, False), (503, False)])
async def test_recorded_robots_status_controls_crawl(status, allowed):
    namespace = patched(trigger_bot_sources, ['robots_text', 'crawl', 'Page'])
    @asynccontextmanager
    async def stream(url, **kwargs):
        assert url == 'https://store.invalid/robots.txt'
        yield httpx.Response(status, content=b'User-agent: *\nAllow: /', request=httpx.Request('GET', url))
    seen = []
    async def get(url, **kwargs):
        assert url == 'https://store.invalid/'
        seen.append(url)
        return b'<title>Store policy</title><p>Returns within 30 days.</p>', {'content-type': 'text/html'}
    namespace.update(public_stream=stream, public_get=get)
    pages = await namespace['crawl']('https://store.invalid/', get=get)
    assert bool(pages) is allowed
    assert bool(seen) is allowed
    if pages:
        assert pages[0]['title'] == 'Store policy'
        assert pages[0]['url'] == seen[0]
        assert '30 days' in pages[0]['text']


@pytest.mark.asyncio
async def test_source_uses_real_title_and_ignores_hidden_links():
    namespace = patched(trigger_bot_sources, ['robots_text', 'crawl', 'Page'])
    seen = []
    async def get(url, **kwargs):
        seen.append(url)
        if url.endswith('/robots.txt'):
            return b'User-agent: *\nAllow: /', {}
        assert url == 'https://store.invalid/'
        return (b'<title>Returns &amp; shipping</title><noscript><a href="/hidden">placeholder hidden</a>'
                b'</noscript><p>Actual policy text.</p>', {'content-type': 'text/html'})
    pages = await namespace['crawl']('https://store.invalid/', get=get)
    assert len(pages) == 1
    assert pages[0]['title'] == 'Returns & shipping'
    assert 'placeholder hidden' not in pages[0]['text']
    assert seen == ['https://store.invalid/robots.txt', 'https://store.invalid/']
