"""Public-web robots policy, checked before page/PDF navigation, cached for 24h."""
from __future__ import annotations

import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from brain.security import public_url

CACHE_SECONDS = 86400
MAX_ROBOTS_BYTES = 256_000
cache: dict[str, tuple[float, RobotFileParser]] = {}


class RobotsDenied(ValueError):
    pass


async def allowed(context, url: str, timeout: int = 10000) -> bool:
    public_url(url)
    parsed = urlsplit(url)
    origin = f'{parsed.scheme}://{parsed.netloc}'
    saved = cache.get(origin)
    if saved and time.monotonic() - saved[0] < CACHE_SECONDS:
        return saved[1].can_fetch('TervoryBase', url)
    policy = RobotFileParser()
    target = origin + '/robots.txt'
    try:
        for _ in range(8):
            public_url(target)
            response = await context.request.get(target, timeout=timeout, max_redirects=0)
            if response.status in {301, 302, 303, 307, 308}:
                target = urljoin(target, response.headers.get('location', ''))
                continue
            if response.status == 404:
                policy.parse(['User-agent: *', 'Allow: /'])
            elif response.status == 200:
                if int(response.headers.get('content-length', '0')) > MAX_ROBOTS_BYTES:
                    return False
                payload = await response.body()
                if len(payload) > MAX_ROBOTS_BYTES:
                    return False
                policy.parse(payload.decode('utf-8', errors='replace').splitlines())
            else:
                # Includes forbidden robots and unavailable policy. Do not guess
                # that a site consents when its policy cannot be fetched.
                policy.parse(['User-agent: *', 'Disallow: /'])
            if len(cache) >= 1024:
                cache.pop(min(cache, key=lambda host: cache[host][0]))
            cache[origin] = (time.monotonic(), policy)
            return policy.can_fetch('TervoryBase', url)
    except Exception:
        return False
    return False


async def require_allowed(context, url: str, timeout: int = 10000) -> None:
    if not await allowed(context, url, timeout):
        raise RobotsDenied('robots.txt')
