"""Finite outbound calls; only idempotent reads may be repeated."""
from __future__ import annotations

import asyncio
import httpx

READ_ATTEMPTS = 2
WRITE_ATTEMPTS = 1
TRANSIENT = {429, 502, 503, 504}


class Unavailable(ValueError):
    """Safe to return without copying an upstream URL, response or credential."""


async def _bounded(send, *, read, timeout):
    attempts = READ_ATTEMPTS if read else WRITE_ATTEMPTS
    for attempt in range(attempts):
        try:
            async with asyncio.timeout(timeout):
                response = await send()
            if read and response.status_code in TRANSIENT and attempt + 1 < attempts:
                await response.aclose()
                continue
            return response
        except (httpx.HTTPError, TimeoutError):
            if attempt + 1 == attempts:
                raise Unavailable('External service unavailable') from None
    raise AssertionError('unreachable')


async def request(client, method, url, *, timeout=30, **kwargs):
    kwargs['follow_redirects'] = False
    return await _bounded(lambda: client.request(method, url, timeout=timeout, **kwargs),
                          read=method.upper() in {'GET', 'HEAD'}, timeout=timeout)


async def get(client, url, *, timeout=30, **kwargs):
    kwargs['follow_redirects'] = False
    return await _bounded(lambda: client.get(url, timeout=timeout, **kwargs), read=True, timeout=timeout)


async def post(client, url, *, timeout=30, **kwargs):
    kwargs['follow_redirects'] = False
    return await _bounded(lambda: client.post(url, timeout=timeout, **kwargs), read=False, timeout=timeout)
