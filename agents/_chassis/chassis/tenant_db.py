"""Transaction-local tenant context for asyncpg; authentication stays upstream."""

from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import signature
from typing import Any
from uuid import UUID

_tenant: ContextVar[str] = ContextVar("chassis_database_tenant", default="")
_administrative: ContextVar[bool] = ContextVar("chassis_database_admin", default=False)


@contextmanager
def tenant_scope(tenant_id: Any, *, administrative: bool = False):
    value = "" if tenant_id is None or tenant_id == "" else str(UUID(str(tenant_id)))
    token = _tenant.set(value)
    admin_token = _administrative.set(administrative)
    try:
        yield
    finally:
        _administrative.reset(admin_token)
        _tenant.reset(token)


def administrative() -> bool:
    return _administrative.get()


def activate_tenant(tenant_id):
    """Called only with the tenant an existing authentication path accepted."""
    _tenant.set(str(UUID(str(tenant_id))))
    _administrative.set(False)


class TenantContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        with tenant_scope(None):
            await self.app(scope, receive, send)


def bind_tenant_endpoints(app):
    """Scope accepted endpoint arguments after FastAPI resolves authentication.

    Read no raw request body or authentication header. The tenant is exactly
    the existing validated endpoint argument or its authenticated Actor value.
    This also covers routers registered by other Tank modules.
    """
    from fastapi.routing import APIRoute

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        original = route.dependant.call
        parameters = signature(original)
        authenticated_actor = any(d.name == "actor" for d in route.dependant.dependencies)
        founder_only = any(d.call.__module__ == "admin" and d.call.__name__ == "require_admin"
                           for d in route.dependant.dependencies if d.call is not None)

        def wrap(function, parameters, authenticated_actor, founder_only):
            @wraps(function)
            async def scoped(**kwargs):
                bound = parameters.bind_partial(**kwargs).arguments
                tenant = bound.get("tenant_id", bound.get("tenant"))
                actor = bound.get("actor") if authenticated_actor else None
                for name in ("actor", "body", "req", "payload"):
                    if name == "actor" and not authenticated_actor:
                        continue
                    if name != "actor" and tenant is not None:
                        break
                    value = bound.get(name)
                    if hasattr(value, "tenant_id"):
                        tenant = value.tenant_id
                        break
                    if name == "actor" and hasattr(value, "tenant"):
                        tenant = value.tenant
                        break
                admin = founder_only or bool(actor and getattr(actor, "founder", False))
                with tenant_scope(tenant, administrative=admin):
                    response = await function(**kwargs)
                # StreamingResponse runs after endpoint return; preserve its scope.
                if hasattr(response, "body_iterator"):
                    iterator = response.body_iterator

                    async def stream():
                        with tenant_scope(tenant, administrative=admin):
                            async for chunk in iterator:
                                yield chunk

                    response.body_iterator = stream()
                return response
            return scoped

        route.dependant.call = wrap(original, parameters, authenticated_actor, founder_only)


def tenant_path(parameter: str):
    """Pass an already accepted path value, without changing execution order."""
    def decorate(function):
        parameters = signature(function, eval_str=True)

        @wraps(function)
        async def scoped(*args, **kwargs):
            accepted = parameters.bind(*args, **kwargs).arguments[parameter]
            tenant_id = getattr(accepted, "tenant_id", accepted)
            with tenant_scope(tenant_id):
                return await function(*args, **kwargs)

        scoped.__signature__ = parameters
        return scoped
    return decorate


class TenantPool:
    """Each checkout owns a short transaction; no transaction spans a model call.

    set_config(..., true) is the parameterized equivalent of SET LOCAL. Closing
    or rolling back this transaction restores the previous connection state.
    Unscoped work explicitly sets the empty value and therefore sees no tenants.
    """

    def __init__(self, pool: Any, admin_pool: Any = None):
        self.raw = pool
        self.admin_pool = admin_pool

    @asynccontextmanager
    async def acquire(self, *, isolation=None, readonly=False, deferrable=False, **kwargs):
        source = self.admin_pool if administrative() and self.admin_pool is not None else self.raw
        async with source.acquire(**kwargs) as conn:
            async with conn.transaction(isolation=isolation, readonly=readonly, deferrable=deferrable):
                await conn.execute("SELECT set_config('app.tenant_id', $1, true)", _tenant.get())
                yield conn

    async def fetch(self, query, *args, **kwargs):
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, **kwargs)

    async def fetchrow(self, query, *args, **kwargs):
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, **kwargs)

    async def fetchval(self, query, *args, **kwargs):
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, **kwargs)

    async def execute(self, query, *args, **kwargs):
        async with self.acquire() as conn:
            return await conn.execute(query, *args, **kwargs)

    async def close(self):
        await self.raw.close()


@asynccontextmanager
async def tenant_transaction(pool, **options):
    """Keep native asyncpg callers and scoped checkouts on the same snapshot."""
    if isinstance(pool, TenantPool):
        async with pool.acquire(**options) as conn:
            yield conn
    else:
        async with pool.acquire() as conn, conn.transaction(**options):
            yield conn
