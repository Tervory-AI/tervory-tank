"""Equal raw subjects from independent issuers are not the same private owner."""
import uuid

import pytest
from fastapi import HTTPException
from starlette.responses import Response

import command
import personal_tokens
import trigger_signin_config as registry
import test_command as command_proofs

command_pool = command_proofs.command_pool
runtime = command_proofs.runtime
api = command_proofs.api


@pytest.mark.asyncio
async def test_thread_owner_is_bound_to_native_issuer_and_raw_subject(api):
    client, pool = api
    context = registry._issuer.set(registry.ISSUERS['us-east'])
    try:
        created = await client.post('/v1/command/threads', json={'title': 'Issuer-private thread'})
        assert created.status_code == 200
        thread_id = created.json()['thread_id']
        assert (await client.get('/v1/command/threads/' + thread_id)).status_code == 200
        async with pool.acquire() as connection:
            row = await connection.fetchrow('SELECT user_id,trigger_signin_issuer FROM tank.command_threads WHERE thread_id=$1', uuid.UUID(thread_id))
        assert row['user_id'] == 'founder'
        assert row['trigger_signin_issuer'] == registry.ISSUERS['us-east']
        registry._issuer.set(registry.ISSUERS['za'])
        assert (await client.get('/v1/command/threads/' + thread_id)).status_code == 404
        assert (await client.get('/v1/command/threads')).json() == []
        registry._issuer.set(registry.ISSUERS['us-east'])
        assert (await client.get('/v1/command/threads/' + thread_id)).status_code == 200
    finally:
        registry._issuer.reset(context)


@pytest.mark.asyncio
async def test_session_list_and_revoke_do_not_link_issuer_collisions(command_pool, runtime, monkeypatch):
    monkeypatch.setattr(command, 'db', lambda: command_pool)
    actor = command.Actor(command_proofs.TENANT, '20001', False)
    context = registry._issuer.set(registry.ISSUERS['za'])
    try:
        created = await personal_tokens.create_token(personal_tokens.NewToken(name='ZA native subject'), Response(), actor)
        identifier = created['token_id']
        assert len(await personal_tokens.list_tokens(Response(), actor)) == 1
        registry._issuer.set(registry.ISSUERS['us-east'])
        assert await personal_tokens.list_tokens(Response(), actor) == []
        with pytest.raises(HTTPException) as refused:
            await personal_tokens.revoke_token(identifier, actor)
        assert refused.value.status_code == 404
        registry._issuer.set(registry.ISSUERS['za'])
        assert (await personal_tokens.revoke_token(identifier, actor)).status_code == 204
    finally:
        registry._issuer.reset(context)
