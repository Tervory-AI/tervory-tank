import httpx
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

from trigger import checkers


@pytest.fixture(autouse=True)
def deterministic_local(monkeypatch):
    monkeypatch.setattr(checkers, 'local_checks', lambda *args: {
        'issues': [], 'limitations': 'Mechanical findings only.'})


@pytest.mark.asyncio
@pytest.mark.parametrize('prefix', ['', 'A sentence.\n' * 2000])
async def test_unicode_grammar_points_to_original_text(prefix):
    text = prefix + '😀 teh word.'
    def response(request):
        from urllib.parse import parse_qs
        part = parse_qs(request.content.decode())['text'][0]
        matches = []
        if 'teh' in part:
            offset = len(part[:part.index('teh')].encode('utf-16-le')) // 2
            matches = [{'rule': {'id': 'SPELLING'}, 'message': 'Check spelling.', 'offset': offset, 'length': 3}]
        return httpx.Response(200, json={'matches': matches})
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        report = await checkers.check(text, None, http)
    assert report['complete'] is True
    assert report['model_calls'] == 0
    assert report['issue_count'] == 1
    item = report['issues'][0]
    assert text[item['offset']:item['offset'] + item['length']] == 'teh'


@pytest.mark.asyncio
@pytest.mark.parametrize('match', [None, [], {'rule': None},
    {'rule': {'id': 'X'}, 'message': 'Check.', 'offset': -1, 'length': 1},
    {'rule': {'id': 'X'}, 'message': 'Check.', 'offset': True, 'length': 1},
    {'rule': {'id': 'X'}, 'message': 'Check.', 'offset': 0, 'length': 100}])
async def test_invalid_provider_findings_are_explicitly_incomplete(match):
    valid = {'rule': {'id': 'X'}, 'message': 'Check.', 'offset': 0, 'length': 1}
    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={'matches': [valid, match]}))) as http:
        report = await checkers.check('word', None, http)
    assert report['complete'] is False
    assert report['checker_errors']
    assert report['issues'] == []


@pytest.mark.asyncio
async def test_nonboolean_provider_completeness_is_not_accepted():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200,
            json={'matches': [], 'warnings': {'incompleteResults': 'false'}}))) as http:
        report = await checkers.check('word', None, http)
    assert report['complete'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [RuntimeError, httpx.ConnectError, ValueError])
async def test_failed_approved_grammar_never_calls_legacy_service(failure):
    async def approved(tenant, skill, payload):
        if skill == 'trigger.languagetool':
            raise failure('placeholder unavailable')
        return None
    http = SimpleNamespace(post=AsyncMock())
    report = await checkers.check('word', None, http,
        tank=SimpleNamespace(approved_skill=approved), tenant_id=UUID(int=11))
    assert report['complete'] is False
    assert report['checker_errors']
    assert report['model_calls'] == 0
    assert 'skills' not in report
    http.post.assert_not_awaited()
