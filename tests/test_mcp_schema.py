"""Apply the real schema and startup-guard SQL to staged and enforced copies."""
import ast
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from test_command import runtime, command_pool, TENANT, OTHER  # noqa: F401
from test_mcp_oauth import mcp_api, issued, WORKSPACE  # noqa: F401
from test_mcp_server import initialize

ROOT = Path(__file__).resolve().parents[1]


def startup_guard_query():
    tree = ast.parse((ROOT / 'tank/main.py').read_text())
    startup = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == '_startup')
    return next(node.value for node in ast.walk(startup) if isinstance(node, ast.Constant)
                and isinstance(node.value, str) and node.value.startswith('SELECT EXISTS') and 'relrowsecurity' in node.value)


@pytest.mark.asyncio
async def test_mcp_schema_idempotent_and_does_not_trip_staged_startup_guard(command_pool):  # noqa: F811
    async with command_pool.acquire() as conn:
        # command_pool applied the complete schema twice, exactly as Tank does.
        assert not await conn.fetchval(startup_guard_query())
        rows = await conn.fetch("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='tank' AND relname=ANY($1::text[])", ['oauth_codes', 'mcp_sessions', 'personal_tokens'])
        assert len(rows) == 3 and all(not row['relrowsecurity'] for row in rows)
        assert not await conn.fetchval("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='tank' AND table_name='oauth_clients' AND column_name='tenant_id')")
        default = await conn.fetchval("SELECT column_default FROM information_schema.columns WHERE table_schema='tank' AND table_name='personal_tokens' AND column_name='audience'")
        assert 'cli' in default


@pytest.mark.asyncio
async def test_mcp_tables_follow_enforced_rollout_and_restrict_foreign_tenants(mcp_api):
    client, pool, _, _ = mcp_api
    _, grant = await issued(client)
    await initialize(client, grant)
    _, foreign = await issued(client, headers={**WORKSPACE, 'x-tervory-tenant': str(OTHER)})
    await initialize(client, foreign)
    role = 'mcp_test_' + uuid4().hex
    async with pool.acquire() as conn:
        await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
        schema = (ROOT / 'tank/schema.sql').read_text()
        await conn.execute(schema)
        await conn.execute(schema)
        assert await conn.fetchval(startup_guard_query())
        # The actual startup guard now requires a non-bypass role + admin pool.
        rows = await conn.fetch("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='tank' AND relname=ANY($1::text[])", ['oauth_codes', 'mcp_sessions', 'personal_tokens'])
        assert all(row['relrowsecurity'] and row['relforcerowsecurity'] for row in rows)
        for table in ['oauth_codes', 'mcp_sessions']:
            policies = await conn.fetch("SELECT policyname,permissive FROM pg_policies WHERE schemaname='tank' AND tablename=$1", table)
            assert {(p['policyname'], p['permissive']) for p in policies} == {('tenant_access', 'PERMISSIVE'), ('tenant_boundary', 'RESTRICTIVE')}
        await conn.execute(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        try:
            await conn.execute(f'GRANT USAGE ON SCHEMA tank TO "{role}"')
            await conn.execute(f'GRANT SELECT,INSERT ON tank.oauth_codes,tank.mcp_sessions TO "{role}"')
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE "{role}"')
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(TENANT))
                for table in ['oauth_codes', 'mcp_sessions']:
                    owners = await conn.fetch(f'SELECT tenant_id FROM tank.{table}')
                    assert len(owners) == 1 and owners[0]['tenant_id'] == TENANT
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute(f'SET LOCAL ROLE "{role}"')
                    await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(TENANT))
                    await conn.execute("INSERT INTO tank.oauth_codes(code_hash,tenant_id,user_id,region,client_id,client_name,redirect_uri,challenge,resource,expires_at) VALUES($1,$2,'client','us-east','offline','Offline','https://client.example/cb','offline','https://app.tervory.com/mcp',now())", 'e' * 64, OTHER)
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE "{role}"')
                await conn.execute("SELECT set_config('app.tenant_id','',true)")
                assert await conn.fetchval('SELECT count(*) FROM tank.oauth_codes') == 0
                assert await conn.fetchval('SELECT count(*) FROM tank.mcp_sessions') == 0
        finally:
            await conn.execute(f'DROP OWNED BY "{role}"')
            await conn.execute(f'DROP ROLE "{role}"')
