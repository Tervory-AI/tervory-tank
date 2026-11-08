"""Signed live Tiger memory controls and opt-in brain on the shared chassis.

Identity comes ONLY from Tank's signed-in producer; query/body scopes are targets,
never identity. A mismatch is refused before obtaining the memory client.
"""
import os
from uuid import UUID, uuid4
import httpx
from fastapi import HTTPException, Request
from gates_memory import Memory, ScopeError, Unavailable


def install(app):
    async def identity(request, tenant, user):
        try:
            from chassis.user_assertion import signed_user
        except ImportError:
            raise HTTPException(503, 'Signed-user chassis integration pending') from None
        actor = await signed_user(request, tenant_id=str(tenant), product='tiger', required=True)
        if actor.tenant_id != str(tenant) or actor.user_id != user:
            raise HTTPException(403, 'Memory owner mismatch')
        return actor

    def client():
        from chassis.memory import MemoryClient
        # Compose maps TANK_KEY_TIGER to TANK_KEY for this room only.
        return MemoryClient(api_key=os.environ.get('TANK_KEY_TIGER') or os.environ.get('TANK_KEY', ''), agent='tiger', http=app.state.http)

    async def invoke(call):
        try:
            return await call()
        except (ScopeError, ValueError):
            raise HTTPException(403, 'Memory scope refused') from None
        except Unavailable:
            raise HTTPException(503, 'memory unavailable') from None
        except httpx.HTTPStatusError as exc:
            raise HTTPException(exc.response.status_code, 'Tiger task unavailable') from None
        except httpx.HTTPError:
            raise HTTPException(503, 'Tiger task unavailable') from None

    async def body_for(request, actor):
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(422, 'JSON object required') from None
        if not isinstance(body, dict):
            raise HTTPException(422, 'JSON object required')
        if (body.get('tenant_id', actor.tenant_id) != actor.tenant_id
                or body.get('user_id', actor.user_id) != actor.user_id
                or body.get('role', actor.role) != actor.role):
            raise HTTPException(403, 'Memory owner mismatch')
        return body

    @app.get('/memory')
    async def view(request: Request, tenant_id: UUID, user_id: str):
        actor = await identity(request, tenant_id, user_id)
        memory = Memory(client(), actor.tenant_id, actor.user_id)
        return await invoke(memory.rows)

    @app.get('/memory/{record_id}')
    async def get_record(record_id: UUID, request: Request, tenant_id: UUID, user_id: str):
        actor = await identity(request, tenant_id, user_id)
        memory = Memory(client(), actor.tenant_id, actor.user_id)
        rows = await invoke(memory.rows)
        row = next((row for row in rows if row['id'] == str(record_id)), None)
        if row is None:
            raise HTTPException(404, 'No owned record')
        return row

    @app.patch('/memory/{record_id}')
    async def edit(record_id: UUID, request: Request, tenant_id: UUID, user_id: str):
        actor = await identity(request, tenant_id, user_id)
        body = await body_for(request, actor)
        if 'value' not in body:
            raise HTTPException(422, 'value required')
        memory = Memory(client(), actor.tenant_id, actor.user_id)
        return await invoke(lambda: memory.edit(str(record_id), body['value']))

    @app.delete('/memory/{record_id}')
    async def forget(record_id: UUID, request: Request, tenant_id: UUID, user_id: str):
        actor = await identity(request, tenant_id, user_id)
        memory = Memory(client(), actor.tenant_id, actor.user_id)
        await invoke(lambda: memory.forget(str(record_id)))
        return {'forgotten': True}

    @app.post('/memory/setting')
    async def setting(request: Request, tenant_id: UUID, user_id: str):
        actor = await identity(request, tenant_id, user_id)
        body = await body_for(request, actor)
        if type(body.get('enabled')) is not bool:
            raise HTTPException(422, 'Boolean enabled required')
        memory = Memory(client(), actor.tenant_id, actor.user_id)
        return await invoke(lambda: memory.setting(body['enabled']))

    @app.post('/memory/correction')
    async def correction(request: Request, tenant_id: UUID, user_id: str):
        actor = await identity(request, tenant_id, user_id)
        body = await body_for(request, actor)
        if not isinstance(body.get('task_key'), str) or not isinstance(body.get('input'), dict) or 'result' not in body:
            raise HTTPException(422, 'task_key, input and result required')
        memory = Memory(client(), actor.tenant_id, actor.user_id)
        return await invoke(lambda: memory.correct(body['task_key'], body['input'], body['result']))

    @app.post('/brain/tasks')
    async def task(request: Request, tenant_id: UUID, user_id: str):
        actor = await identity(request, tenant_id, user_id)
        from gates_brain import run, brain_service
        body = await body_for(request, actor)
        if not isinstance(body.get('task_key'), str) or not isinstance(body.get('input'), dict):
            raise HTTPException(422, 'task_key and input required')
        try:
            run_id = str(UUID(str(body.get('run_id') or uuid4())))
        except ValueError:
            raise HTTPException(422, 'Valid run_id required') from None
        async def paid(task, payload, recall):
            return await brain_service(app.state.http, actor, task, payload, recall, run_id=run_id)
        result = await invoke(lambda: run(client(), actor, body['task_key'], body['input'], paid))
        return {**result, 'run_id': run_id}
