"""Offline revocation and reconnect lifecycle; only placeholder credentials."""
from unittest.mock import AsyncMock

import httpx
import pytest
import trigger_google as module
from test_marketing import env as env  # noqa: PLC0414 -- pytest fixture re-export
from test_marketing import m1 as m1  # noqa: PLC0414 -- pytest fixture re-export
from test_second import TENANT
from trigger_google import Google, GoogleFailure, REVOKE


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
