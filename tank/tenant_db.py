"""Transaction-local tenant context for asyncpg; authentication stays upstream."""

from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import signature
from typing import Any
from uuid import UUID

_tenant: ContextVar[str] = ContextVar("tank_database_tenant", default="")


@contextmanager
def tenant_scope(tenant_id: Any):
    value = "" if tenant_id is None or tenant_id == "" else str(UUID(str(tenant_id)))
    token = _tenant.set(value)
    try:
        yield
    finally:
        _tenant.reset(token)


def tenant_path(parameter: str):
    """Pass an already accepted path value, without changing execution order."""
    def decorate(function):
        parameters = signature(function)

        @wraps(function)
        async def scoped(*args, **kwargs):
            accepted = parameters.bind(*args, **kwargs).arguments[parameter]
            tenant_id = getattr(accepted, "tenant_id", accepted)
            with tenant_scope(tenant_id):
                return await function(*args, **kwargs)

        return scoped
    return decorate


class TenantPool:
    """Each checkout owns a short transaction; no transaction spans a model call.

    set_config(..., true) is the parameterized equivalent of SET LOCAL. Closing
    or rolling back this transaction restores the previous connection state.
    Unscoped work explicitly sets the empty value and therefore sees no tenants.
    """

    def __init__(self, pool: Any):
        self.raw = pool

    @asynccontextmanager
    async def acquire(self, **kwargs):
        async with self.raw.acquire(**kwargs) as conn:
            async with conn.transaction():
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
