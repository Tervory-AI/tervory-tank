"""A total deadline as well as the transport's per-read timeout. No retries.

Mutations keep their durable idempotency keys and explicit recovery paths;
an ambiguous response must never trigger a second write automatically.
"""
import asyncio
from functools import wraps


def bounded(seconds, failure):
    def decorate(call):
        @wraps(call)
        async def run(*args, **kwargs):
            try:
                async with asyncio.timeout(seconds):
                    return await call(*args, **kwargs)
            except TimeoutError:
                raise failure() from None
        return run
    return decorate
