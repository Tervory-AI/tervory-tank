"""Internal Moot media API. Only a trusted server may forward actor identity.

Run separately from Zenas. Browser access must use the authenticated Workspace/
Tank boundary; this application never trusts browser-supplied organization roles.
"""
import asyncio
import hmac
from contextlib import asynccontextmanager, suppress
from uuid import UUID
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from .contracts import Scope, MediaError


class GrantInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    seat: str


def create_app(*, bridge, rooms, journal, internal_key, region, mux=None):
    leases = {}  # Revalidation is required again on process restart/new connection.

    async def check_leases():
        while True:
            await asyncio.sleep(0.5)
            for key, lease in list(leases.items()):
                scope, user, seat, epoch, identity = lease
                try:
                    state = await bridge.projection(scope, user, seat)
                    if seat not in state.get('my_seats', []) or state['seats'][seat]['epoch'] != epoch:
                        raise MediaError('seat_revoked')
                except Exception:
                    try:
                        await rooms.revoke(scope, identity)
                    except Exception:
                        continue  # retry revocation; never issue a replacement grant.
                    leases.pop(key, None)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(check_leases())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(lifespan=lifespan)

    def actor(tenant, user, key):
        if not internal_key or not hmac.compare_digest(key.encode(), internal_key.encode()):
            raise HTTPException(401, 'internal_auth_required')
        try:
            UUID(tenant)
            if not user or len(user) > 200:
                raise ValueError()
        except ValueError:
            raise HTTPException(401, 'actor_required') from None
        return tenant, user

    @app.get('/healthz')
    async def health():
        return {'product': 'moot', 'region': region, 'speech': 'unavailable'}

    @app.post('/internal/hearings/{hearing}/grants')
    async def grant(hearing: UUID, body: GrantInput, x_moot_key: str = Header(default=''),
        x_moot_tenant: str = Header(default=''), x_moot_actor: str = Header(default='')):
        tenant, user = actor(x_moot_tenant, x_moot_actor, x_moot_key)
        scope = Scope(tenant, region, str(hearing))
        try:
            state = await bridge.projection(scope, user, body.seat)
            result = rooms.grant(scope, user, body.seat, state)
            # Explicit room creation keeps LiveKit auto_create disabled.
            await rooms.create(scope)
            fresh = await bridge.projection(scope, user, body.seat)
            if fresh['seats'][body.seat]['epoch'] != result['epoch']:
                raise MediaError('seat_revoked')
            leases[(scope.room, result['identity'])] = (scope, user, body.seat, result['epoch'], result['identity'])
            return result
        except MediaError as exc:
            raise HTTPException(403, str(exc)) from None
        except Exception:
            raise HTTPException(503, 'media_unavailable') from None

    @app.get('/internal/hearings/{hearing}/resume')
    async def resume(hearing: UUID, seat: str, after: int = 0, x_moot_key: str = Header(default=''),
        x_moot_tenant: str = Header(default=''), x_moot_actor: str = Header(default='')):
        tenant, user = actor(x_moot_tenant, x_moot_actor, x_moot_key)
        scope = Scope(tenant, region, str(hearing))
        if after < 0:
            raise HTTPException(422, 'invalid_cursor')
        try:
            projection = await bridge.projection(scope, user, seat)
            # The role-specific legacy projection remains authoritative. Never read
            # its raw SQL state or expose a judge projection to another seat.
            return {'hearing': projection, 'events': journal.events(scope, after), 'speech': 'unavailable'}
        except MediaError:
            raise HTTPException(403, 'not_found') from None

    @app.post('/webhooks/mux')
    async def mux_webhook(request: __import__('fastapi').Request,
                          mux_signature: str = Header(default='')):
        if mux is None:
            raise HTTPException(503, 'mux_unavailable')
        if int(request.headers.get('content-length', '0')) > 1024 * 1024:
            raise HTTPException(413, 'webhook_too_large')
        raw = await request.body()
        try:
            accepted = mux.webhook(raw, mux_signature)
            return {'accepted': accepted}
        except MediaError:
            raise HTTPException(400, 'invalid_webhook') from None

    return app
