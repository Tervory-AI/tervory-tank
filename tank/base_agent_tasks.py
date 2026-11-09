"""Base's signed planning work through its existing paid policy and ledger."""
from uuid import UUID
from fastapi import HTTPException
from command_tools._user_assertion import PostgresNonces, signed_user
from product_identity import actor_scope


async def room_task(tank, body, request):
    from agent_skills import Chat, complete, local_region, room_key
    room_key('base', request.headers.get('authorization', ''), request.headers.get('x-tank-key', ''))
    region = local_region(tank, request.headers.get('x-home-region'), room='base')
    if region != 'us-east':
        raise HTTPException(403, 'Base planning region mismatch')
    actor = await signed_user(request, tenant_id=str(body.tenant_id), product='base', required=True,
                              nonces=PostgresNonces(tank.pool(), 'tank'))
    if actor.user_id != body.user_id:
        raise HTTPException(403, 'Base owner mismatch')
    with actor_scope(actor):
        return await complete(tank, Chat(messages=body.messages, paid_run_id=body.run_id),
                              body.tenant_id, UUID(str(body.run_id)), region, room='base')
