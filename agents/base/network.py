"""Bound external work by elapsed time, including response-body reads.

Only reads are retried. Writes reconcile through their existing durable IDs;
a lost acknowledgement must never purchase the same work twice.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import httpx


class BoundedHTTP:
    _base_bounded = True

    def __init__(self, http):
        # The room image imports flat modules; shared callers use the package.
        # Both names must share the same retry budget when wrapped together.
        self.http = http.http if getattr(http, '_base_bounded', False) is True else http

    async def _call(self, method, *args, **kwargs):
        timeout = kwargs.setdefault('timeout', 30)
        seconds = timeout if isinstance(timeout, (int, float)) else 30
        safe_read = method in ('get', 'head') or (method == 'request' and str(args[0]).lower() in ('get', 'head'))
        for attempt in range(2 if safe_read else 1):
            try:
                async with asyncio.timeout(seconds):
                    response = await getattr(self.http, method)(*args, **kwargs)
                if safe_read and response.status_code in (502, 503, 504) and attempt == 0:
                    continue
                return response
            except (TimeoutError, httpx.TransportError):
                if safe_read and attempt == 0:
                    continue
                raise httpx.TimeoutException('Base could not complete this request.') from None

    async def get(self, *args, **kwargs):
        return await self._call('get', *args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._call('post', *args, **kwargs)

    async def delete(self, *args, **kwargs):
        return await self._call('delete', *args, **kwargs)

    async def request(self, method, *args, **kwargs):
        return await self._call('request', method, *args, **kwargs)

    def __getattr__(self, name):
        if name in ('put', 'patch', 'head', 'options'):
            async def call(*args, **kwargs):
                return await self._call(name, *args, **kwargs)
            return call
        return getattr(self.http, name)

    @asynccontextmanager
    async def stream(self, *args, **kwargs):
        # Streaming reads have no replay after bytes have been consumed.
        seconds = kwargs.setdefault('timeout', 60)
        try:
            async with asyncio.timeout(seconds):
                async with self.http.stream(*args, **kwargs) as response:
                    yield response
        except (TimeoutError, httpx.TransportError):
            raise httpx.TimeoutException('Base could not complete this request.') from None


async def admitted(operation, seconds=300):
    """Paid approval polling has one total deadline and is never replayed here."""
    try:
        async with asyncio.timeout(seconds):
            return await operation
    except TimeoutError:
        raise httpx.TimeoutException('Base could not complete this request.') from None


class _AdmissionHTTP(BoundedHTTP):
    def __init__(self, http):
        super().__init__(http)
        self.posts = self.polls = 0

    async def post(self, *args, **kwargs):
        self.posts += 1
        if self.posts > 2:
            raise httpx.TimeoutException('Base could not complete this request.')
        return await super().post(*args, **kwargs)

    async def get(self, *args, **kwargs):
        self.polls += 1
        if self.polls > 60:
            raise httpx.TimeoutException('Base could not complete this request.')
        return await super().get(*args, **kwargs)


async def paid_post(http, *args, **kwargs):
    # Reuse chassis approval/tenant checks, but cap both polling and the
    # approval-authorized replay. A misbehaving approval service cannot loop.
    from chassis.paid_steps import post
    return await admitted(post(_AdmissionHTTP(http), *args, **kwargs))
