"""Authenticated Market Lab memory controls and durable research enqueue."""
from uuid import UUID
import json

from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field


class ResearchJob(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    kind: str = Field(pattern='^research$')
    input: dict


def install(router, tank):
    import command
    from ghost_routes import call_room
    from product_identity import actor_scope

    async def actor(identity=Depends(command.identity)):
        current = await command.authorized_actor(identity)
        command.require_tool(current, 'market_lab.research')
        return current

    @router.post('/v1/market-lab/jobs')
    async def job(body: ResearchJob, user=Depends(actor)):
        if body.tenant_id != user.tenant_id:
            raise HTTPException(403, 'This workspace is not available')
        with actor_scope(user):
            response = await call_room('POST', 'market_lab', '/jobs', body=body.model_dump(mode='json'),
                                       tenant=user.tenant_id, user=user.user_id)
        return Response(response.content, response.status_code, media_type='application/json',
                        headers={'Cache-Control': 'private, no-store'})

    @router.api_route('/v1/market-lab/memory', methods=['GET'])
    @router.api_route('/v1/market-lab/memory/{operation}', methods=['POST'])
    async def memory(request: Request, operation: str = '', user=Depends(actor)):
        if operation not in {'', 'control', 'edit', 'forget'}:
            raise HTTPException(404, 'Not found')
        body = None
        if request.method != 'GET':
            try:
                body = json.loads(await request.body())
            except ValueError:
                raise HTTPException(422, 'Invalid request') from None
        with actor_scope(user):
            response = await call_room(request.method, 'market_lab', '/v1/market-lab/memory' + ('/'+operation if operation else ''),
                body=body, params=list(request.query_params.multi_items()), tenant=user.tenant_id, user=user.user_id)
        return Response(response.content, response.status_code, media_type='application/json',
                        headers={'Cache-Control': 'private, no-store'})
