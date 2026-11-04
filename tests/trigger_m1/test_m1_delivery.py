"""Offline HTTP phase boundaries: refreshing never publishes a post."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import trigger_google as module
from trigger_google import Google, GoogleFailure, TOKEN, V4


@pytest.mark.asyncio
@pytest.mark.parametrize('phase', ['refresh', 'publish'])
@pytest.mark.parametrize('failure', ['connect', 'connect_timeout', 'read_timeout', 'dropped', 'write', 'server', 'unreadable', 'oversized', 'rejection', 'rate_limit'])
async def test_refresh_and_post_failures_distinguish_unsent_from_uncertain(monkeypatch, phase, failure):
    calls = []
    def transport(request):
        calls.append(str(request.url))
        if (str(request.url) == TOKEN) == (phase == 'refresh'):
            errors = {'connect': httpx.ConnectError, 'connect_timeout': httpx.ConnectTimeout,
                      'read_timeout': httpx.ReadTimeout, 'dropped': httpx.RemoteProtocolError, 'write': httpx.WriteError}
            if failure in errors:
                raise errors[failure]('placeholder transport failure', request=request)
            if failure == 'unreadable':
                return httpx.Response(200, content=b'placeholder not JSON')
            if failure == 'oversized':
                return httpx.Response(200, content=b' ' * 2_000_001)
            status = {'server': 503, 'rejection': 400, 'rate_limit': 429}[failure]
            return httpx.Response(status, json={'error': {'message': 'placeholder Google failure'}})
        return httpx.Response(200, json={'access_token': 'placeholder transient'})
    original = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(transport), **kw))
    monkeypatch.setattr(module, 'settings', lambda: {'client_id': 'placeholder', 'client_secret': 'placeholder'})
    monkeypatch.setattr(module, 'open_seal', lambda *args: {'refresh_token': 'placeholder refresh'})
    pool = SimpleNamespace(fetchrow=AsyncMock(return_value={'generation': uuid4(), 'sealed': 'placeholder', 'status': 'connected'}))
    with pytest.raises(GoogleFailure) as caught:
        await Google(pool).request(uuid4(), 'POST', V4+'accounts/123/locations/456/localPosts', json={'summary': 'placeholder'})
    uncertain = phase == 'publish' and failure in {'read_timeout', 'dropped', 'write', 'server', 'unreadable', 'oversized'}
    assert caught.value.uncertain is uncertain
    assert caught.value.retryable is (not uncertain and failure != 'rejection')
    assert len(calls) == (1 if phase == 'refresh' else 2)
    assert calls[0] == TOKEN
