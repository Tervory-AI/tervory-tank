"""Tenant vault MCP catalogue, founder approvals, and zero-dollar receipts."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Literal

import jsonschema
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp_client import Client, Refused, SignInRequired, TOOL_NAME

VAULTS = {f'{room}.vault': room for room in ('base', 'tiger', 'rig', 'tisan', 'radix', 'zenas')}
VAULTS['lab.vault'] = 'market_lab'


def db():
    from command import db as command_db
    return command_db()


def unpack(value):
    return json.loads(value) if isinstance(value, str) else value


class ServerArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(max_length=2000)

    @field_validator('url')
    @classmethod
    def public(cls, value):
        from vault_routes import public_url
        return public_url(value)


class ApproveArgs(ServerArgs):
    name: str = Field(min_length=1, max_length=200)
    allowed_tools: dict[str, Literal['read', 'write']] = Field(min_length=1, max_length=1000)

    @field_validator('allowed_tools')
    @classmethod
    def names(cls, value):
        if any(not TOOL_NAME.fullmatch(name) for name in value):
            raise ValueError('Invalid tool name')
        return value


async def approved(url: str) -> dict:
    async with db().acquire() as conn:
        row = await conn.fetchrow('SELECT url,name,allowed_tools FROM tank.mcp_servers WHERE url=$1', url)
    if not row:
        raise Refused('MCP server not approved')
    return {**dict(row), 'allowed_tools': unpack(row['allowed_tools'])}


async def connection(actor, vault: str, ident: str) -> dict:
    if vault not in VAULTS or (not actor.founder and VAULTS[vault] not in actor.squads):
        raise HTTPException(403, 'This tool is not available to this user')
    try:
        ident = str(uuid.UUID(ident))
    except ValueError:
        raise HTTPException(404, 'Not Found') from None
    async with db().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tank.vault_items WHERE tenant_id=$1 AND vault=$2 AND kind='connections' AND name=$3", actor.tenant_id, vault, ident)
    if not row:
        raise HTTPException(404, 'Not Found')
    return {**dict(row), 'metadata': unpack(row['metadata']), 'mcp_tools': unpack(row['mcp_tools'])}


def context(row) -> str:
    return f"plugins:v1:{row['tenant_id']}:{row['vault']}:connection:{row['name']}"


def credentials(row) -> dict:
    from vault import open_seal
    return open_seal(row['sealed'], context(row)) if row.get('sealed') else {}


async def state(row, value: str):
    async with db().acquire() as conn:
        await conn.execute("UPDATE tank.vault_items SET mcp_state=$4 WHERE tenant_id=$1 AND vault=$2 AND kind='connections' AND name=$3", row['tenant_id'], row['vault'], row['name'], value)


async def store_credentials(row, value: dict, *, mcp_state: str):
    from vault import seal
    encrypted = seal(value, context(row))
    async with db().acquire() as conn:
        status = await conn.execute("UPDATE tank.vault_items SET sealed=$4,mcp_state=$5 WHERE tenant_id=$1 AND vault=$2 AND kind='connections' AND name=$3 AND sealed IS NOT DISTINCT FROM $6", row['tenant_id'], row['vault'], row['name'], encrypted, mcp_state, row.get('sealed'))
    if status != 'UPDATE 1':
        raise Refused('MCP connection changed')
    row['sealed'] = encrypted


async def bearer(row) -> tuple[str | None, list[str]]:
    mode = row['metadata']['auth_type']
    if mode == 'none':
        return None, []
    data = credentials(row)
    if mode == 'provider':
        from mcp_oauth import refresh
        data = await refresh(row, data)
        token = data.get('access_token')
    else:
        token = data.get('token')
    if not isinstance(token, str) or not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
        await state(row, 'needs_sign_in')
        raise SignInRequired()
    return token, [value for key, value in data.items() if key in {'token', 'access_token', 'refresh_token', 'client_secret'} and isinstance(value, str) and value]


async def discover(actor, vault: str, ident: str, *, force=False) -> list[dict]:
    row = await connection(actor, vault, ident)
    try:
        server = await approved(row['metadata']['server_url'])
    except Refused:
        await state(row, 'not_approved')
        return []
    cached_at = row.get('mcp_discovered_at')
    if not force and row['mcp_state'] == 'connected' and cached_at and (datetime.now(timezone.utc) - cached_at).total_seconds() < 3600:
        return [tool for tool in row['mcp_tools'] if tool['name'] in server['allowed_tools']]
    async def gate():
        await approved(server['url'])
    try:
        token, secrets = await bearer(row)
        client = Client(server['url'], gate, token)
        await client.initialize()
        tools = await client.tools(server['allowed_tools'])
        # A hostile endpoint cannot reflect an authentication value into planner data.
        tools = redact(tools, secrets)
    except SignInRequired:
        await state(row, 'needs_sign_in')
        return []
    except Refused:
        await state(row, 'sign_in_failed')
        return []
    async with db().acquire() as conn:
        await conn.execute("UPDATE tank.vault_items SET mcp_tools=$4::jsonb,mcp_discovered_at=now(),mcp_state='connected' WHERE tenant_id=$1 AND vault=$2 AND kind='connections' AND name=$3", actor.tenant_id, vault, ident, json.dumps(tools))
    return tools


def redact(value, secrets: list[str]):
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, '[redacted]')
        return value
    if isinstance(value, dict):
        return {redact(key, secrets): redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    return value


async def catalogue(actor, conn=None) -> dict[str, dict]:
    if conn is None:
        async with db().acquire() as connection:
            return await catalogue(actor, connection)
    # No cross-tenant lookup, including founders: the selected workspace owns the vault.
    rows = await conn.fetch("""SELECT v.vault,v.name,v.mcp_tools,s.allowed_tools FROM tank.vault_items v
        JOIN tank.mcp_servers s ON s.url=v.metadata->>'server_url'
        WHERE v.tenant_id=$1 AND v.kind='connections' AND v.mcp_state='connected'
        AND v.mcp_discovered_at > now()-interval '1 hour'""", actor.tenant_id)
    result, collisions = {}, set()
    for row in rows:
        vault = row['vault']
        if vault not in VAULTS or (not actor.founder and VAULTS[vault] not in actor.squads):
            continue
        allowed = unpack(row['allowed_tools'])
        for tool in unpack(row['mcp_tools']):
            if tool['name'] not in allowed:
                continue
            name = f"mcp.{uuid.UUID(row['name']).hex[:8]}.{tool['name']}"
            if name in result:
                collisions.add(name)
            result[name] = {**tool, 'vault': vault, 'connection_id': row['name'], 'access': allowed[tool['name']]}
    return {name: tool for name, tool in result.items() if name not in collisions}


def validate(tool: dict, arguments: dict):
    try:
        jsonschema.Draft202012Validator(tool['inputSchema']).validate(arguments)
    except (jsonschema.exceptions.ValidationError, jsonschema.exceptions.SchemaError, RecursionError):
        raise HTTPException(422, 'The action arguments are invalid') from None


async def receipt(actor, name: str) -> str:
    from main import box_region
    async with db().acquire() as conn:
        ident = await conn.fetchval("""INSERT INTO tank.ledger(tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out)
            VALUES($1,$2,'tank',$3,3,'code',0,0,0) RETURNING id""", actor.tenant_id, box_region(), name)
    return str(ident)


async def dispatch(action, actor) -> tuple[int, dict]:
    # Called only after Command's durable Confirm claim, never from a product room.
    name, args = action.tool, action.arguments
    if name.startswith('mcp.servers.'):
        from command import require_founder
        require_founder(actor)
        async with db().acquire() as conn:
            if name == 'mcp.servers.list':
                rows = await conn.fetch('SELECT url,name,allowed_tools,approved_by,approved_at FROM tank.mcp_servers ORDER BY url')
                result = {'servers': [{**dict(row), 'allowed_tools': unpack(row['allowed_tools']), 'approved_at': row['approved_at'].isoformat()} for row in rows]}
            elif name == 'mcp.servers.approve':
                body = ApproveArgs.model_validate(args)
                await conn.execute('''INSERT INTO tank.mcp_servers(url,name,allowed_tools,approved_by)
                    VALUES($1,$2,$3::jsonb,$4) ON CONFLICT(url) DO UPDATE SET name=$2,allowed_tools=$3::jsonb,approved_by=$4,approved_at=now()''', body.url, body.name, json.dumps(body.allowed_tools), actor.user_id)
                result = {'ok': True}
            elif name == 'mcp.servers.remove':
                body = ServerArgs.model_validate(args)
                await conn.execute('DELETE FROM tank.mcp_servers WHERE url=$1', body.url)
                result = {'ok': True}
            else:
                raise HTTPException(403, 'This tool is not available to this user')
        return 200, {**result, 'ledger_id': await receipt(actor, name)}
    tools = await catalogue(actor)
    tool = tools.get(name)
    if not tool:
        raise HTTPException(403, 'This tool is not available to this user')
    validate(tool, args)
    row = await connection(actor, tool['vault'], tool['connection_id'])
    server = await approved(row['metadata']['server_url'])
    async def gate():
        current = await approved(server['url'])
        if tool['name'] not in current['allowed_tools']:
            raise Refused('MCP tool refused')
    ledger_id = await receipt(actor, name)  # Persist even if the external call fails.
    try:
        token, secrets = await bearer(row)
        client = Client(server['url'], gate, token)
        await client.initialize()
        result = redact(await client.call(tool['name'], args), secrets)
        # Bound the result retained in the Confirm card, independently of transport size.
        if len(json.dumps(result).encode()) > 64_000:
            result = {'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)[:12000]}]}
        return 200, {'data': result, 'ledger_id': ledger_id}
    except SignInRequired:
        await state(row, 'needs_sign_in')
    except Refused:
        await state(row, 'sign_in_failed')
    return 409, {'ledger_id': ledger_id}
