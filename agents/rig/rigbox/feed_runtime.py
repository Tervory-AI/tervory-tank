"""Bounded public reads for the room's existing registered catalogue feeds."""
import asyncio
import socket
from urllib.parse import urlsplit

import httpx
from chassis.public_urls import _blocked_address
from rigbox.feeds.catalogue import LIMIT


async def fetch(http, url: str) -> bytes:
    # Authenticated supplier connections continue through Tank ACCESS. This
    # older room registry holds public URLs only, never supplier credentials.
    parsed = urlsplit(url)
    if (len(url) > 2000 or parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.fragment
            or parsed.port not in (None, 443)):
        raise ValueError("feed unavailable")
    async with asyncio.timeout(25):
        answers = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
        if not addresses or any(_blocked_address(address) for address in addresses):
            raise ValueError("feed unavailable")
        # Pin the checked address while retaining the original TLS hostname.
        target = httpx.URL(url).copy_with(host=addresses[0])
        async with http.stream("GET", target, headers={"Host": parsed.hostname},
                               extensions={"sni_hostname": parsed.hostname},
                               timeout=25, follow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError("feed unavailable")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > LIMIT:
                    raise ValueError("feed unavailable")
                body.extend(chunk)
            return bytes(body)
