"""Local proof: actual room app; only R2's HTTP transport is replaced."""
import os
import socket
from pathlib import Path

import httpx

_original = httpx.AsyncHTTPTransport.handle_async_request


async def r2(self, request):
    if request.url.host != os.environ['R2_ACCOUNT_ID'] + '.r2.cloudflarestorage.com':
        return await _original(self, request)
    root = Path(os.environ['MARKET_DOCS_PROOF_BUCKET']).resolve()
    target = (root / request.url.path.lstrip('/')).resolve()
    expected = root / ('tervory-' + os.environ['AGENT_NAME'].replace('_', '-'))
    assert target.is_relative_to(expected)
    assert request.headers.get('authorization') and request.headers.get('x-amz-content-sha256')
    if request.method == 'PUT':
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(await request.aread())
        return httpx.Response(200)
    if request.method == 'DELETE':
        target.unlink(missing_ok=True)
        return httpx.Response(204)
    if request.method == 'GET' and target.is_file():
        return httpx.Response(200, content=target.read_bytes())
    return httpx.Response(404)


httpx.AsyncHTTPTransport.handle_async_request = r2

# The vault links route asks the room to subscribe https://example.com/reports, and
# the room's shared public-URL check resolves the host (#421). Answer that one name
# with a fixed public address so the proof needs no DNS; every other name and the
# public-address rule itself are unchanged.
_getaddrinfo = socket.getaddrinfo


def _resolve(host, *args, **kwargs):
    if host == 'example.com':
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]
    return _getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = _resolve
if os.environ['AGENT_NAME'] == 'market_lab':
    from app import app
else:
    # The shared production chassis, specifically for testing its storage API.
    from chassis.app import create_app
    app = create_app(agent=os.environ['AGENT_NAME'], handlers={})
