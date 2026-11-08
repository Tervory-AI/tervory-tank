"""Keep a price job's database changes and saved result in one transaction."""
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import wraps
import json
from uuid import UUID

_pool = ContextVar('tiger_job_pool', default=None)


def job_pool(default):
    return _pool.get() or default


class ConnectionPool:
    def __init__(self, conn):
        self.conn = conn

    @asynccontextmanager
    async def acquire(self, **kwargs):
        yield self.conn


def once_check(pool):
    def decorate(handler):
        @wraps(handler)
        async def run(ctx):
            async with pool().acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow('''SELECT result FROM agent_tiger.jobs
                        WHERE tenant_id=$1 AND id=$2 AND kind='check' FOR UPDATE''',
                        UUID(str(ctx.tenant_id)), UUID(str(ctx.job_id)))
                    if row is not None:
                        if row['result'] is not None:
                            return json.loads(row['result']) if isinstance(row['result'], str) else row['result']
                        token = _pool.set(ConnectionPool(conn))
                        try:
                            result = await handler(ctx)
                            parts = getattr(ctx.tank, 'parts', []) if hasattr(ctx, 'tank') else []
                            if parts:
                                result['_savings_parts'] = list(dict.fromkeys(parts))
                            await conn.execute('''UPDATE agent_tiger.jobs SET result=$3::jsonb
                                WHERE tenant_id=$1 AND id=$2 AND kind='check' ''',
                                UUID(str(ctx.tenant_id)), UUID(str(ctx.job_id)), json.dumps(result))
                            return result
                        finally:
                            _pool.reset(token)
            # Internal one-off calls without a persisted job still use the
            # same handler; durable worker calls always have their owned row.
            return await handler(ctx)
        return run
    return decorate
