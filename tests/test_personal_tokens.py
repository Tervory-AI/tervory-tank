"""CLI-1 offline authentication tests: synthetic tokens, no live credentials."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
import sys
import uuid

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request
from starlette.responses import Response

import command
import personal_tokens as pat
from tenant_db import _tenant

TENANT = uuid.UUID('00000000-0000-0000-0000-000000000011')
TOKEN = f'tv1.us-east.{TENANT.hex}.' + 'x' * 43


def request(token=TOKEN, **headers):
    if token is not None:
        headers['authorization'] = 'Bearer ' + token
    return Request({'type': 'http', 'headers': [(k.encode(), v.encode()) for k, v in headers.items()]})


@pytest.fixture
def runtime(monkeypatch):
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value={'user_id': 'client'}),
                           fetch=AsyncMock(return_value=[{'agent': 'tiger'}]))
    @asynccontextmanager
    async def acquire():
        assert _tenant.get() == str(TENANT)
        yield conn
    monkeypatch.setattr(command, 'db', lambda: SimpleNamespace(acquire=acquire))
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(box_region=lambda: 'us-east', TANK_API_KEY='dummy-workspace'))
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder')
    return conn


@pytest.mark.asyncio
async def test_token_identity_ignores_all_assertion_headers(runtime):
    actor = await pat.identity(request(**{'x-tervory-user': 'founder', 'x-tervory-tenant': str(uuid.uuid4()),
                                        'x-tervory-role': 'org:admin', 'x-tervory-squad': 'base'}))
    assert actor.user_id == 'client' and actor.tenant_id == TENANT
    assert not actor.founder and not actor.tenant_admin
    assert command.allowed_tools(actor) == ['tiger.read', 'tiger.watch']
    args = runtime.fetchrow.call_args.args
    assert args[1:] == (TENANT, 'us-east', pat.digest(TOKEN))
    assert TOKEN not in repr(args)


@pytest.mark.asyncio
async def test_revoked_and_unknown_tokens_are_refused(runtime):
    runtime.fetchrow.return_value = None
    with pytest.raises(HTTPException) as error:
        await pat.identity(request())
    assert error.value.status_code == 401
    assert 'revoked_at IS NULL' in runtime.fetchrow.call_args.args[0]


@pytest.mark.asyncio
async def test_foreign_region_never_queries_local_database(runtime):
    with pytest.raises(HTTPException) as error:
        await pat.identity(request(TOKEN.replace('us-east', 'za')))
    assert error.value.status_code == 403
    runtime.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_malformed_bearer_cannot_fall_back_to_workspace(runtime):
    with pytest.raises(HTTPException) as error:
        await pat.identity(request('invalid', **{'x-tank-key': 'dummy-workspace'}))
    assert error.value.status_code == 401
    runtime.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_pat_cannot_mint_or_list_tokens(runtime):
    with pytest.raises(HTTPException):
        await pat.workspace_actor(request())
    runtime.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_creation_persists_hash_only_and_disables_caching(runtime, monkeypatch):
    monkeypatch.setattr(pat.secrets, 'token_urlsafe', lambda size: 'x' * 43)
    runtime.fetchrow.return_value = {'token_id': uuid.uuid4(), 'region': 'us-east', 'name': 'CLI', 'created_at': None}
    response = Response()
    result = await pat.create_token(pat.NewToken(name='CLI'), response, command.Actor(TENANT, 'client', False))
    assert result['token'] == TOKEN
    assert response.headers['cache-control'] == 'no-store'
    query, *values = runtime.fetchrow.call_args.args
    assert TOKEN not in values and pat.digest(TOKEN) in values
    assert values[:3] == [TENANT, 'client', 'us-east']


@pytest.mark.asyncio
async def test_revoke_scoped_to_token_owner(runtime):
    token_id = uuid.uuid4()
    result = await pat.revoke_token(token_id, command.Actor(TENANT, 'client', False))
    assert result.status_code == 204
    assert runtime.fetchrow.call_args.args[1:] == (TENANT, 'client', token_id)
    assert 'tenant_id=$1 AND user_id=$2 AND token_id=$3' in runtime.fetchrow.call_args.args[0]


def test_register_reuses_command_identity_without_global_service_key_override():
    app = FastAPI()
    pat.register(app)
    assert app.dependency_overrides == {command.identity: pat.identity}
