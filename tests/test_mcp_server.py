"""Real MCP to Command proposals, Confirm, ownership and durable receipts."""
import asyncio
import json
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends

import command
import mcp_server as mcp
from test_command import seed_ledger, TENANT, OTHER, runtime, command_pool  # noqa: F401
from test_mcp_oauth import mcp_api, issued, WORKSPACE  # noqa: F401

ACCEPT = 'application/json, text/event-stream'


async def initialize(client, grant):
    response = await client.post('/mcp', headers={'authorization': 'Bearer ' + grant['access_token'], 'accept': ACCEPT},
        json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': mcp.PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'Offline test', 'version': '1'}}})
    assert response.status_code == 200, response.text
    assert response.json()['result']['protocolVersion'] == mcp.PROTOCOL
    headers = {'authorization': 'Bearer ' + grant['access_token'], 'accept': ACCEPT,
               'mcp-session-id': response.headers['mcp-session-id'], 'mcp-protocol-version': mcp.PROTOCOL}
    ready = await client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    assert ready.status_code == 202 and not ready.content
    return headers


async def rpc(client, headers, method, params=None):
    return await client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 2, 'method': method, 'params': params or {}})


async def enable(pool, tenant=TENANT):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'base','offline-test') ON CONFLICT DO NOTHING", tenant)


@pytest.mark.asyncio
async def test_tools_match_command_and_founder_tools_stay_private(mcp_api):
    client, pool, _, _ = mcp_api
    await enable(pool)
    _, grant = await issued(client)
    headers = await initialize(client, grant)
    result = (await rpc(client, headers, 'tools/list')).json()['result']
    names = {t['name'] for t in result['tools']}
    actor = command.Actor(TENANT, 'client', False, frozenset({'base'}))
    assert names == set(command.allowed_tools(actor))
    assert not names.intersection(command.FOUNDER_TOOLS)
    for tool in result['tools']:
        adapter = command.ADAPTERS[tool['name']]
        assert tool['inputSchema'] == adapter.arguments.model_json_schema()
        assert tool['annotations']['readOnlyHint'] == (adapter.method == 'GET' and not adapter.paid)
    founder_args, founder = await issued(client, headers={**WORKSPACE, 'x-tervory-user': 'founder'})
    founder_headers = await initialize(client, founder)
    listed = (await rpc(client, founder_headers, 'tools/list')).json()['result']['tools']
    assert 'worker.build' in {t['name'] for t in listed}
    assert {t['name'] for t in listed} == set(command.allowed_tools(command.Actor(TENANT, 'founder', True)))


@pytest.mark.asyncio
async def test_read_returns_rows_and_real_receipt_in_same_command_thread(mcp_api):
    client, pool, rt, _ = mcp_api
    await enable(pool)
    ledger = await seed_ledger(pool)
    calls = []
    @rt.app.get('/v1/base/records')
    async def records(tenant_id: uuid.UUID, actor: command.Actor = Depends(command.identity)):
        assert tenant_id == actor.tenant_id == TENANT and actor.user_id == 'client'
        command.require_tool(actor, 'base.search')
        calls.append(tenant_id)
        return {'rows': [{'name': 'Synthetic verified dealer', 'verified': True}], 'ledger_id': str(ledger)}
    _, grant = await issued(client)
    headers = await initialize(client, grant)
    response = await rpc(client, {**headers, 'x-tervory-user': 'founder', 'x-tervory-tenant': str(OTHER)}, 'tools/call', {'name': 'base.search', 'arguments': {}})
    assert response.status_code == 200, response.text
    result = response.json()['result']
    assert result['isError'] is False, result
    output = json.loads(result['content'][0]['text'])
    assert output['result']['rows'][0]['verified'] is True
    assert output['receipts'][0]['ledger_id'] == str(ledger)
    assert output['receipts'][0]['cost_usd'] == 0.02
    assert output['totals']['cost_usd'] == 0.02 and calls == [TENANT]
    thread = output['thread_url'].split('=')[-1]
    snapshot = (await client.get('/v1/command/threads/' + thread, headers=WORKSPACE)).json()
    assert snapshot['thread']['title'] == 'Offline client'
    assert snapshot['cards'][0]['status'] == 'confirmed'
    assert snapshot['receipts'][0]['ledger_id'] == str(ledger)
    assert any(step['actor'] == 'base' for step in snapshot['steps'])


@pytest.mark.asyncio
async def test_paid_tool_proposes_only_then_real_human_confirm_runs_it(mcp_api, monkeypatch):
    client, pool, _, _ = mcp_api
    await enable(pool)
    dispatch = AsyncMock(return_value=(200, {'batch': 'synthetic-batch'}))
    pause = AsyncMock()
    monkeypatch.setattr(command, 'dispatch_action', dispatch)
    monkeypatch.setattr(__import__('controls'), 'refuse_paid', pause)
    _, grant = await issued(client)
    headers = await initialize(client, grant)
    result = (await rpc(client, headers, 'tools/call', {'name': 'base.batch', 'arguments': {'batch': 'synthetic-batch', 'records': [{'name': 'Synthetic dealer'}]}})).json()['result']
    payload = json.loads(result['content'][0]['text'])
    assert payload['status'] == 'pending' and 'Confirm' in payload['message']
    dispatch.assert_not_awaited(); pause.assert_not_awaited()
    confirmed = await client.post('/v1/command/cards/' + payload['card_id'], json={'action': 'confirm'}, headers=WORKSPACE)
    assert confirmed.status_code == 200 and confirmed.json()['status'] == 'confirmed'
    dispatch.assert_awaited_once(); pause.assert_awaited_once()


@pytest.mark.asyncio
async def test_origin_versions_accept_and_session_lifecycle(mcp_api):
    client, _, _, _ = mcp_api
    _, grant = await issued(client)
    headers = await initialize(client, grant)
    assert (await rpc(client, {**headers, 'origin': 'https://evil.example'}, 'ping')).status_code == 403
    assert (await rpc(client, {**headers, 'origin': 'https://claude.ai'}, 'ping')).json()['result'] == {}
    assert (await rpc(client, {**headers, 'mcp-protocol-version': '2024-11-05'}, 'ping')).status_code == 400
    assert (await rpc(client, {**headers, 'accept': 'application/json'}, 'ping')).status_code == 406
    assert (await client.get('/mcp', headers=headers)).status_code == 405
    assert (await rpc(client, headers, 'resources/list')).json()['error']['code'] == -32601
    assert (await client.post('/mcp', headers={**headers, 'content-type': 'application/json'}, content='[]')).json()['error']['code'] == -32600
    assert (await client.post('/mcp', headers={**headers, 'content-type': 'application/json'}, content='{')).json()['error']['code'] == -32700
    assert (await client.delete('/mcp', headers=headers)).status_code == 204
    assert (await rpc(client, headers, 'ping')).status_code == 404


@pytest.mark.asyncio
async def test_foreign_tenant_and_other_grant_cannot_use_session_or_choose_tenant(mcp_api):
    client, pool, _, _ = mcp_api
    await enable(pool)
    _, grant = await issued(client)
    headers = await initialize(client, grant)
    _, foreign = await issued(client, headers={**WORKSPACE, 'x-tervory-tenant': str(OTHER)})
    denied = await rpc(client, {**headers, 'authorization': 'Bearer ' + foreign['access_token']}, 'ping')
    assert denied.status_code == 404
    _, another = await issued(client)
    assert (await rpc(client, {**headers, 'authorization': 'Bearer ' + another['access_token']}, 'ping')).status_code == 404
    response = await rpc(client, headers, 'tools/call', {'name': 'base.search', 'arguments': {'tenant_id': str(OTHER)}})
    assert response.json()['result']['isError'] is True
    response = await rpc(client, headers, 'tools/call', {'name': 'skala.list', 'arguments': {}})
    assert response.json()['result']['isError'] is True


@pytest.mark.asyncio
async def test_live_session_checks_revocation_and_role_changes_every_time(mcp_api, monkeypatch):
    client, pool, _, _ = mcp_api
    await enable(pool)
    _, grant = await issued(client)
    headers = await initialize(client, grant)
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM tank.tenant_squad WHERE tenant_id=$1 AND agent='base'", TENANT)
    assert (await rpc(client, headers, 'tools/list')).json()['result']['tools'] == []
    assert (await rpc(client, headers, 'tools/call', {'name': 'base.search'})).json()['result']['isError'] is True
    await client.delete('/v1/personal-tokens/' + grant['credential_id'], headers=WORKSPACE)
    assert (await rpc(client, headers, 'ping')).status_code == 401


@pytest.mark.asyncio
async def test_slow_read_continues_durably_after_sixty_second_wait(mcp_api, monkeypatch):
    client, pool, _, _ = mcp_api
    await enable(pool)
    _, grant = await issued(client)
    headers = await initialize(client, grant)
    started, finish = asyncio.Event(), asyncio.Event()
    original = command.card_action
    async def delayed(*args, **kwargs):
        started.set()
        await finish.wait()
        return await original(*args, **kwargs)
    monkeypatch.setattr(command, 'card_action', delayed)
    assert mcp.READ_WAIT_SECONDS == 60
    monkeypatch.setattr(mcp, 'READ_WAIT_SECONDS', 0.01)
    response = await rpc(client, headers, 'tools/call', {'name': 'base.search'})
    payload = json.loads(response.json()['result']['content'][0]['text'])
    assert payload['status'] == 'running' and len(mcp._background) == 1
    finish.set()
    await asyncio.gather(*mcp._background)
