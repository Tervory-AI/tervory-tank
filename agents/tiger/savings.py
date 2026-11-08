"""Use Tank's routing and accounting; never estimate provider charges in a room."""
import asyncio
from dataclasses import replace
from functools import wraps
from uuid import UUID, uuid5


class MeteredTank:
    def __init__(self, tank):
        self.tank = tank
        self.parts = []

    def __getattr__(self, name):
        return getattr(self.tank, name)

    def remember(self, value):
        if isinstance(value, dict) and value.get('_savings'):
            self.parts.append(value['_savings']['id'])
        return value

    async def run_skill(self, *args, **kwargs):
        return self.remember(await self.tank.run_skill(*args, **kwargs))

    async def approved_skill(self, *args, **kwargs):
        return self.remember(await self.tank.approved_skill(*args, **kwargs))


def receipted(handler):
    @wraps(handler)
    async def run(ctx):
        # A dry run does not create live receipts or contact accounting.
        if ctx.input.get('dry_run') is True:
            return await handler(ctx)
        meter = MeteredTank(ctx.tank)
        child = replace(ctx, tank=meter)
        try:
            result = await handler(child)
        except (Exception, asyncio.CancelledError):
            # Worker retries are distinct attempts, but accounting retries use
            # the same id. Only safe status text leaves the failed handler.
            await publish(ctx, meter.parts, {'status': 'failed'}, failed=True)
            raise
        parts = list(dict.fromkeys([*result.get('_savings_parts', []), *meter.parts]))
        receipt = await publish(ctx, parts, result)
        return {**result, '_savings_parts': parts, 'savings': receipt}
    return run


async def publish(ctx, parts, result, *, failed=False):
    ident = UUID(str(ctx.job_id))
    if failed:
        ident = uuid5(ident, 'failed:' + ':'.join(sorted(parts)))
    # Existing Tank client supplies room auth, tenant and paid-run identity.
    # Retries belong to the worker; this request never replays an action.
    async with asyncio.timeout(10):
        return await ctx.tank._post('/v1/tiger/savings', {
            'tenant_id': str(ctx.tenant_id), 'id': str(ident),
            'action': 'tiger.' + ctx.kind, 'input': ctx.input,
            'output': {k: v for k, v in result.items() if k not in {'savings', '_savings_parts'}},
            'parts': parts, 'failed': failed,
        })
