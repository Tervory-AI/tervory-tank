"""Offline revocation and reconnect lifecycle; only placeholder credentials."""
import json
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import trigger_google as module
from test_marketing import env as env  # noqa: PLC0414 -- pytest fixture re-export
from test_marketing import m1 as m1  # noqa: PLC0414 -- pytest fixture re-export
from test_second import TENANT
from trigger_google import Google, GoogleFailure, REVOKE, TOKEN


@pytest.mark.asyncio
@pytest.mark.parametrize('status,body,revoked', [
    (200, {}, True), (400, {'error': 'invalid_token'}, True),
    (400, {'error': 'invalid_client'}, False), (503, {}, False), (204, {}, False),
])
async def test_disconnect_erases_only_successful_or_already_revoked_token(m1, monkeypatch, status, body, revoked):
    await m1.env.pool.execute("UPDATE tank.trigger_gbp_connections SET sealed='placeholder sealed' WHERE tenant_id=$1", TENANT)
    monkeypatch.setattr(module, 'open_seal', lambda *args: {'refresh_token': 'placeholder refresh'})
    google = Google(m1.env.pool)
    google.http = AsyncMock(return_value=httpx.Response(status, json=body))
    if revoked:
        assert (await google.disconnect(TENANT, m1.generation))['status'] == 'disconnected'
    else:
        with pytest.raises(GoogleFailure):
            await google.disconnect(TENANT, m1.generation)
    row = await m1.env.pool.fetchrow('SELECT sealed,status FROM tank.trigger_gbp_connections WHERE tenant_id=$1', TENANT)
    assert row['sealed'] == (None if revoked else 'placeholder sealed')
    assert row['status'] == ('disconnected' if revoked else 'connected')
    google.http.assert_awaited_once_with('POST', REVOKE, data={'token': 'placeholder refresh'})


@pytest.mark.asyncio
@pytest.mark.parametrize('status,error', [(200, None), (400, 'invalid_token'), (400, 'invalid_client')])
async def test_reconnect_revokes_old_grant_before_new_consent_and_storage(m1, monkeypatch, status, error):
    old = json.dumps({'refresh_token': 'placeholder old refresh'})
    await m1.env.pool.execute('UPDATE tank.trigger_gbp_connections SET sealed=$2 WHERE tenant_id=$1', TENANT, old)
    monkeypatch.setattr(module, 'settings', lambda: {'client_id': 'placeholder', 'client_secret': 'placeholder'})
    monkeypatch.setattr(module, 'seal', lambda data, context: json.dumps(data))
    monkeypatch.setattr(module, 'open_seal', lambda value, context: json.loads(value))
    google = Google(m1.env.pool)
    calls = []
    async def http(method, url, **kwargs):
        calls.append(url)
        if url == REVOKE:
            assert kwargs['data'] == {'token': 'placeholder old refresh'}
            return httpx.Response(status, json={'error': error} if error else {})
        assert url == TOKEN and calls == [REVOKE, TOKEN]
        assert await m1.env.pool.fetchval('SELECT sealed FROM tank.trigger_gbp_connections WHERE tenant_id=$1', TENANT) is None
        return httpx.Response(200, json={'refresh_token': 'placeholder new refresh', 'scope': module.SCOPE})
    google.http = AsyncMock(side_effect=http)
    if error == 'invalid_client':
        with pytest.raises(GoogleFailure):
            await google.connect(m1.actor)
        assert calls == [REVOKE]
        assert await m1.env.pool.fetchval('SELECT sealed FROM tank.trigger_gbp_connections WHERE tenant_id=$1', TENANT) == old
        assert not await m1.env.pool.fetchval('SELECT 1 FROM tank.trigger_gbp_states WHERE tenant_id=$1', TENANT)
        return
    link = await google.connect(m1.actor)
    assert calls == [REVOKE]
    state = parse_qs(urlsplit(link['url']).query)['state'][0]
    await google.callback(m1.actor, state, 'placeholder code')
    row = await m1.env.pool.fetchrow('SELECT sealed,generation,status FROM tank.trigger_gbp_connections WHERE tenant_id=$1', TENANT)
    assert json.loads(row['sealed']) == {'refresh_token': 'placeholder new refresh'}
    assert row['generation'] != m1.generation and row['status'] == 'connected'
