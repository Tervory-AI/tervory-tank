"""Bundled plugin validation and Command/RLS tests; isolated SQL, no external calls."""
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
import asyncpg
from fastapi import HTTPException

import command
import plugins
from test_command import api, runtime, command_pool, TENANT, OTHER  # noqa: F401

PLUGIN = plugins.MANIFESTS['github', '1.0.0']
URL = PLUGIN.servers[0].url
ARGS = {'id': 'github', 'version': '1.0.0'}
IDENT = '12345678-abcd-4000-8000-000000000001'


def test_manifests_load_and_bad_manifest_fails(tmp_path):
    assert plugins.load_manifests() == plugins.MANIFESTS
    assert Path('plugins/github/1.0.0/plugin.yaml').resolve() == plugins.ROOT / 'github/1.0.0/plugin.yaml'
    assert set(PLUGIN.servers[0].tools.values()) == {'read'}
    target = tmp_path / 'github/1.0.0'
    target.mkdir(parents=True)
    for change in [{'products': ['placeholder']}, {'code_mode': 'true'}, {'skills': ['placeholder']}, {'servers': []}, {'version': '2.0.0'}]:
        value = {**PLUGIN.model_dump(), **change}
        (target / 'plugin.yaml').write_text(json.dumps(value))
        with pytest.raises(ValueError):
            plugins.load_manifests(tmp_path)


async def approve(pool, tools=None):
    await pool.execute('INSERT INTO tank.mcp_servers(url,name,allowed_tools,approved_by) VALUES($1,$2,$3::jsonb,$4) ON CONFLICT(url) DO UPDATE SET allowed_tools=$3::jsonb', URL, 'placeholder server', json.dumps(PLUGIN.servers[0].tools if tools is None else tools), 'placeholder-founder')


@pytest.mark.asyncio
async def test_list_install_remove_confirm_receipts_and_tenant_boundary(api, runtime):  # noqa: F811
    client, pool = api
    runtime.pool = lambda: pool
    actor = command.Actor(TENANT, 'founder', True)
    async with pool.acquire() as conn:
        before = await plugins.listing(conn, actor)
    assert before['plugins'][0]['status'] == 'not_ready'
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    path = f'/v1/command/threads/{thread}/actions'
    member_thread = (await client.post('/v1/command/threads', json={}, headers={'x-tervory-user': 'placeholder-member'})).json()['thread_id']
    for tool in ['plugins.install', 'plugins.remove']:
        member = await client.post(f'/v1/command/threads/{member_thread}/actions', json={'tool': tool, 'arguments': ARGS}, headers={'x-tervory-user': 'placeholder-member'})
        assert member.status_code == 403
    denied = await client.post(path, json={'tool': 'plugins.install', 'arguments': ARGS})
    assert denied.status_code == 422
    await approve(pool, {'list_issues': 'read'})
    assert (await client.post(path, json={'tool': 'plugins.install', 'arguments': ARGS})).status_code == 422
    await approve(pool)
    for tool in ['plugins.install', 'plugins.remove']:
        card = (await client.post(path, json={'tool': tool, 'arguments': ARGS})).json()
        assert card['status'] == 'pending'
        assert await pool.fetchval('SELECT count(*) FROM tank.plugin_installs WHERE tenant_id=$1', TENANT) == (0 if tool.endswith('install') else 1)
        confirmed = (await client.post(f"/v1/command/cards/{card['card_id']}", json={'action': 'confirm'})).json()
        assert confirmed['status'] == 'confirmed', confirmed
        receipt = await pool.fetchrow('SELECT model,cost_usd FROM tank.ledger WHERE tenant_id=$1 AND task_type=$2', TENANT, tool)
        assert receipt['model'] == 'code' and receipt['cost_usd'] == 0
        async with pool.acquire() as conn:
            own = await plugins.listing(conn, actor)
            foreign = await plugins.listing(conn, command.Actor(OTHER, 'founder', True))
        assert own['plugins'][0]['installed'] == tool.endswith('install')
        assert not foreign['plugins'][0]['installed']
    admin = command.Actor(TENANT, 'placeholder-admin', False, frozenset({'radix'}), True)
    member = command.Actor(TENANT, 'placeholder-member', False, frozenset({'radix'}))
    assert {'plugins.list', 'plugins.install', 'plugins.remove'} <= set(command.allowed_tools(admin))
    assert 'plugins.list' in command.allowed_tools(member) and 'plugins.install' not in command.allowed_tools(member)
    with pytest.raises(HTTPException):
        await plugins.dispatch(command.PlannedAction(tool='plugins.install', arguments=ARGS), admin)


@pytest.mark.asyncio
async def test_skill_and_connection_status_and_no_credentials(api, monkeypatch):  # noqa: F811
    _, pool = api
    manifest = PLUGIN.model_copy(update={'skills': ['placeholder@1.0.0']})
    monkeypatch.setattr(plugins, 'MANIFESTS', {('github', '1.0.0'): manifest})
    await approve(pool)
    actor = command.Actor(TENANT, 'founder', True)
    await pool.execute("INSERT INTO tank.vault_items(tenant_id,vault,kind,name,metadata,sealed,mcp_state) VALUES($1,'radix.vault','connections',$2,$3::jsonb,$4,'needs_sign_in')", TENANT, IDENT, json.dumps({'server_url': URL}), 'placeholder-never-returned')
    async with pool.acquire() as conn:
        listing = await plugins.listing(conn, actor)
        assert listing['plugins'][0]['servers'][0]['connections'][0]['mcp_state'] == 'needs_sign_in'
        assert listing['plugins'][0]['skills'] == [{'ref': 'placeholder@1.0.0', 'approved': False}]
        assert 'placeholder-never-returned' not in json.dumps(listing)
        with pytest.raises(HTTPException) as error:
            await plugins.prepare(command.PlannedAction(tool='plugins.install', arguments=ARGS), actor, conn)
        assert error.value.status_code == 422
        await conn.execute("INSERT INTO tank.skills(id,version,agent,state) VALUES('placeholder','1.0.0','placeholder','approved')")
        assert (await plugins.listing(conn, actor))['plugins'][0]['skills'][0]['approved']
        assert await plugins.prepare(command.PlannedAction(tool='plugins.install', arguments=ARGS), actor, conn)


@pytest.mark.asyncio
async def test_code_mode_requires_install_and_never_offers_another_tenants_tools(api, monkeypatch):  # noqa: F811
    client, pool = api
    await approve(pool)
    tools = [{'name': 'list_pull_requests', 'description': 'placeholder read', 'inputSchema': {'type': 'object'}}]
    for tenant, ident in [(TENANT, IDENT), (OTHER, str(uuid.UUID(int=456)))]:
        await pool.execute("INSERT INTO tank.vault_items(tenant_id,vault,kind,name,metadata,mcp_tools,mcp_discovered_at,mcp_state) VALUES($1,'radix.vault','connections',$2,$3::jsonb,$4::jsonb,now(),'connected')", tenant, ident, json.dumps({'server_url': URL}), json.dumps(tools))
    actor = command.Actor(TENANT, 'founder', True)
    async with pool.acquire() as conn:
        authorized = await command.authorized_actor(actor, conn, include_mcp=True)
        assert len(authorized.mcp_tools) == 1
        assert not (await plugins.code_actor(authorized, conn)).mcp_tools
        assert (await plugins.listing(conn, actor))['plugins'][0]['status'] == 'ready'
        await conn.execute('INSERT INTO tank.plugin_installs(tenant_id,plugin_id,version,installed_by) VALUES($1,$2,$3,$4)', TENANT, 'github', '1.0.0', 'placeholder-founder')
        enabled = await plugins.code_actor(authorized, conn)
        assert list(enabled.mcp_tools) == ['mcp.12345678.list_pull_requests']
        writes = command.replace(authorized, mcp_tools={name: {**tool, 'access': 'write'} for name, tool in authorized.mcp_tools.items()})
        assert not (await plugins.code_actor(writes, conn)).mcp_tools
    ledger = uuid.uuid4()
    await pool.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd) VALUES($1,$2,'orchestrator','command.code','code',0)", ledger, TENANT)
    route = AsyncMock(return_value=SimpleNamespace(ledger_id=ledger, content=json.dumps({'requests': [{'name': 'tervory', 'arguments': {'tool': 'mcp.12345678.list_pull_requests', 'arguments': {}}}]})))
    monkeypatch.setattr(command, 'route_code', route)
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    response = await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': 'placeholder read PRs'})
    assert response.status_code == 200, response.text
    assert response.json()['cards'][0]['status'] == 'pending'
    assert 'mcp.12345678.list_pull_requests' in route.call_args.args[1][0]['content']
    await pool.execute('DELETE FROM tank.plugin_installs WHERE tenant_id=$1', TENANT)
    route.return_value.ledger_id = uuid.uuid4()
    await pool.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd) VALUES($1,$2,'orchestrator','command.code','code',0)", route.return_value.ledger_id, TENANT)
    response = await client.post(f'/v1/command/threads/{thread}/code-turn', json={'text': 'placeholder read PRs again'})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_plugin_rls_follows_staged_and_enforced_rollout(command_pool):  # noqa: F811
    async with command_pool.acquire() as conn:
        assert not await conn.fetchval("SELECT relrowsecurity FROM pg_class WHERE oid='tank.plugin_installs'::regclass")
        await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
        schema = Path('tank/schema.sql').read_text()
        await conn.execute(schema)
        await conn.execute(schema)
        assert await conn.fetchval("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='tank.plugin_installs'::regclass")
        await conn.execute('CREATE ROLE placeholder_plugin_role NOLOGIN NOSUPERUSER NOBYPASSRLS')
        try:
            await conn.execute('GRANT USAGE ON SCHEMA tank TO placeholder_plugin_role')
            await conn.execute('GRANT SELECT,INSERT ON tank.plugin_installs TO placeholder_plugin_role')
            await conn.execute("INSERT INTO tank.plugin_installs(tenant_id,plugin_id,version,installed_by) VALUES($1,'github','1.0.0','placeholder-founder'),($2,'github','1.0.0','placeholder-founder')", TENANT, OTHER)
            async with conn.transaction():
                await conn.execute('SET LOCAL ROLE placeholder_plugin_role')
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(TENANT))
                rows = await conn.fetch('SELECT tenant_id FROM tank.plugin_installs')
                assert [row['tenant_id'] for row in rows] == [TENANT]
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute('SET LOCAL ROLE placeholder_plugin_role')
                    await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(TENANT))
                    await conn.execute("INSERT INTO tank.plugin_installs(tenant_id,plugin_id,version,installed_by) VALUES($1,'placeholder','1.0.0','placeholder-founder')", OTHER)
        finally:
            await conn.execute('DROP OWNED BY placeholder_plugin_role')
            await conn.execute('DROP ROLE placeholder_plugin_role')
