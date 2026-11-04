"""HTTP contract; no provider, network, paid step or real credential."""
import asyncio
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tank'))
import window_complete as route
from command import Actor, identity

TENANT = uuid.uuid4()
LEDGER = uuid.uuid4()


@pytest.fixture
def setup(monkeypatch):
    class Conn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, sql, receipt_id, tenant, region, error):
            assert tenant == TENANT and "'not_set'" in sql and 'unknown' in error

        async def fetch(self, sql, tenant, ids):
            assert 'tenant_id=$1' in sql and tenant == TENANT and ids == [LEDGER]
            return [dict(id=LEDGER, model='private-model', tokens_in=10, tokens_out=3,
                         cost_usd=.001, baseline_cost_usd=.01, baseline_model='private-baseline')]

    run = AsyncMock(return_value=SimpleNamespace(content='return 1\n', ledger_id=LEDGER, escalation=[]))
    runtime = SimpleNamespace(run_route=run, RouteRequest=lambda **kw: SimpleNamespace(**kw),
                              Message=lambda **kw: kw, box_region=lambda: 'us-east',
                              pool=lambda: SimpleNamespace(acquire=Conn))
    monkeypatch.setitem(sys.modules, 'main', runtime)
    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[identity] = lambda: Actor(TENANT, 'user', False)
    return app, run


@pytest.mark.asyncio
async def test_ask_cannot_dispatch(setup):
    app, run = setup
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
        result = await client.post('/v1/command/complete', json={'prefix': 'abc'})
    assert result.json() == {'status': 'ask', 'text': '', 'receipts': []}
    run.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['complete', 'edit'])
async def test_fim_rules_receipts_and_existing_policy(setup, mode):
    app, run = setup
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
        result = await client.post('/v1/command/complete', json={
            'mode': mode, 'paid_mode': 'auto', 'prefix': 'before', 'suffix': 'after',
            'rules': 'use tabs', 'selection': 'old', 'instruction': 'replace',
            'tabs': [{'path': 'near.py', 'text': 'nearby'}]})
    assert result.status_code == 200, result.text
    answer = result.json()
    assert answer['text'] == 'return 1\n'
    assert answer['receipts'][0]['saved_usd'] == pytest.approx(.009)
    assert 'private-model' not in result.text and 'private-baseline' not in result.text
    req = run.call_args.args[0]
    assert req.task_type == 'command.code' and req.tenant_id == TENANT
    assert 'use tabs' in req.messages[1]['content'] and 'nearby' in req.messages[1]['content']
    assert run.call_count == 1 and not run.call_args.kwargs


@pytest.mark.asyncio
async def test_disconnect_cancels_provider_without_retry(setup, monkeypatch):
    _, run = setup
    cancelled = asyncio.Event()

    async def slow(*args, **kwargs):
        try:
            await asyncio.sleep(30)
        finally:
            cancelled.set()

    run.side_effect = slow
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
    with pytest.raises(route.HTTPException) as error:
        await route.complete(route.Complete(paid_mode='auto'), request, Actor(TENANT, 'user', False))
    assert error.value.status_code == 499
    assert cancelled.is_set() and run.call_count == 1


@pytest.mark.asyncio
async def test_timeout_is_short_and_never_retries(setup):
    _, run = setup
    run.side_effect = lambda *a, **k: None

    async def slow(*args, **kwargs):
        await asyncio.sleep(30)

    run.side_effect = slow
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    with pytest.raises(route.HTTPException) as error:
        await route.complete(route.Complete(paid_mode='auto'), request, Actor(TENANT, 'user', False))
    assert error.value.status_code == 504 and run.call_count == 1


@pytest.mark.asyncio
async def test_invalid_edit_and_tenant_spoof_refused(setup):
    app, run = setup
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
        for payload in [{'mode': 'edit'}, {'tenant_id': str(uuid.uuid4())}, {'paid_mode': 'yes'}]:
            assert (await client.post('/v1/command/complete', json=payload)).status_code == 422
    run.assert_not_awaited()


def test_personal_token_corridor_is_post_only():
    from personal_tokens import cli_route
    from starlette.requests import Request
    assert cli_route(Request({'type': 'http', 'method': 'POST', 'path': '/v1/command/complete', 'headers': []}))
    for method, path in [('GET', '/v1/command/complete'), ('POST', '/v1/command/complete/admin'),
                         ('POST', '/v1/route')]:
        assert not cli_route(Request({'type': 'http', 'method': method, 'path': path, 'headers': []}))
