"""Offline reference source tests: local fixture HTTP server and local Postgres only."""
from contextlib import asynccontextmanager
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import socket
import threading
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest

from agents._brain import security
from agents.base.engines.ffl import reference, reference_source
from base_queries import reference_page
from base_product_fixtures import TENANT, raw
from base_reference_status import check_reference
from base_repository import BaseStore, PLATFORM
from test_base_atf_download import engine
from test_base_database import database as database

FIXTURES = Path(__file__).parent / 'base_reference_file'
FILE_URL = 'https://reference.example/0926-ffl-list.csv'
PUBLIC_IP = '93.184.216.34'


@pytest.fixture
def local_file(monkeypatch):
    calls = []

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append(self.path)
            super().do_GET()

    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(FIXTURES)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Only the test transport maps the validated, pinned public address onto
    # the local fixture server. Production has no private-address bypass.
    class Transport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.inner = httpx.AsyncHTTPTransport()

        async def handle_async_request(self, request):
            assert request.url.host == PUBLIC_IP
            assert request.headers['host'] == 'reference.example'
            assert request.extensions['sni_hostname'] == 'reference.example'
            assert 'x-tank-key' not in request.headers
            target = request.url.copy_with(scheme='http', host='127.0.0.1', port=server.server_port)
            return await self.inner.handle_async_request(httpx.Request(request.method, target, headers=request.headers))

        async def aclose(self):
            await self.inner.aclose()

    async def resolve(host, port, **kwargs):
        assert host == 'reference.example' and port == 443
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (PUBLIC_IP, port))]

    # Patch only the policy's async DNS resolver, not socket DNS used by the server.
    @asynccontextmanager
    async def files():
        import asyncio
        loop = asyncio.get_running_loop()
        original = loop.getaddrinfo
        async def dns(host, port, **kwargs):
            if host == 'reference.example':
                return await resolve(host, port, **kwargs)
            return await original(host, port, **kwargs)
        monkeypatch.setattr(loop, 'getaddrinfo', dns)
        async with httpx.AsyncClient(transport=Transport(), trust_env=False) as client:
            yield client

    monkeypatch.setattr(reference_source, 'file_client', files)
    monkeypatch.setenv('BASE_REFERENCE_FILE_URL', FILE_URL)
    monkeypatch.setattr(reference, '_blocked_files', set())
    monkeypatch.setattr(reference, '_last_read', 0)
    try:
        yield calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.asyncio
async def test_new_file_source_installs_after_legacy_atf_block_and_retains_stop(database, monkeypatch, local_file):  # noqa: F811 (pytest fixture parameter)
    conn, rt = database
    # Represent the old row exactly: the new additive column is still empty.
    await conn.execute("INSERT INTO tank.base_reference_checks(owner_id,checked_at,status,message) VALUES($1,now(),'blocked','ATF did not allow the read (HTTP 403). Automatic checks have stopped.')", PLATFORM)
    async with engine(rt, monkeypatch, lambda request: pytest.fail('No ATF fetch for configured file')) as store:
        monkeypatch.setattr(reference, '_blocked', True)
        await check_reference(store)
        await check_reference(BaseStore(rt))
        file = await store.latest_file()
        assert file['published_on'] == date(2026, 9, 1)
        assert file['row_count'] == 6 and file['source_url'] == FILE_URL and not file['adopted']
        assert file['sha256'] == hashlib.sha256((FIXTURES / '0926-ffl-list.csv').read_bytes()).hexdigest()
        assert await conn.fetchval('SELECT count(*) FROM tank.base_reference_files') == 1
        assert await conn.fetchval('SELECT count(*) FROM tank.base_reference_entries') == 6
        page = await reference_page(store, [], [], False, 0, 10)
        assert page['total_all'] == 6 and page['file']['published_on'] == date(2026, 9, 1)
        assert page['refresh']['status'] == 'updated' and page['refresh']['message'] is None
        sources = json.loads(await conn.fetchval('SELECT source_checks FROM tank.base_reference_checks WHERE owner_id=$1', PLATFORM))
        assert sources['atf']['status'] == 'blocked'
        assert FILE_URL not in json.dumps(sources)
        monkeypatch.delenv('BASE_REFERENCE_FILE_URL')
        assert not await BaseStore(rt).due_refresh()
        with pytest.raises(ValueError, match='automatic reads have stopped'):
            await BaseStore(rt).refresh()
    assert local_file == ['/0926-ffl-list.csv']


@pytest.mark.asyncio
async def test_configured_refresh_uses_filename_date_and_same_parser(monkeypatch, local_file):
    http = AsyncMock()
    value = await reference.refresh(http, date(2026, 8, 1), date(2026, 10, 28))
    assert value['changed'] and len(value['files']) == 1 and len(value['rows']) == 6
    assert value['published_on'] == '2026-09-01'
    current = await reference.refresh(http, date(2026, 9, 1), date(2026, 10, 28))
    assert current['changed'] is False and len(local_file) == 1
    http.stream.assert_not_called()


@pytest.mark.asyncio
async def test_each_blocked_source_gets_one_try_survives_restart_and_does_not_clear_atf(database, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    conn, rt = database
    seen = []
    monkeypatch.setenv('BASE_REFERENCE_FILE_URL', FILE_URL)
    monkeypatch.setattr(reference, '_blocked_files', set())
    monkeypatch.setattr(reference_source, 'destination', AsyncMock(return_value=(httpx.URL('https://' + PUBLIC_IP + '/0926-ffl-list.csv'), 'reference.example')))
    def blocked(request):
        seen.append(request)
        return httpx.Response(403)
    monkeypatch.setattr(reference_source, 'file_client', lambda: httpx.AsyncClient(transport=httpx.MockTransport(blocked)))
    async with engine(rt, monkeypatch, lambda request: pytest.fail('ATF must not be read')) as store:
        await check_reference(store)
        monkeypatch.setattr(reference, '_blocked_files', set())
        await check_reference(BaseStore(rt))
        assert len(seen) == 1
        assert (await store.reference_state())['status'] == 'blocked'
        monkeypatch.setenv('BASE_REFERENCE_FILE_URL', FILE_URL.replace('/0926', '/other/0926'))
        monkeypatch.setattr(reference, '_last_read', 0)
        await check_reference(BaseStore(rt))
        await check_reference(BaseStore(rt))
        assert len(seen) == 2
        monkeypatch.setenv('BASE_REFERENCE_FILE_URL', FILE_URL)
        assert not await BaseStore(rt).due_refresh()
        assert await store.latest_file() is None


@pytest.mark.asyncio
@pytest.mark.parametrize('url', [
    'https://127.0.0.1/0926-ffl-list.csv', 'https://[::1]/0926-ffl-list.csv',
    'https://169.254.169.254/0926-ffl-list.csv', 'https://10.0.0.1/0926-ffl-list.csv',
    'https://localhost/0926-ffl-list.csv', 'https://service.internal/0926-ffl-list.csv',
    'https://user:password@reference.example/0926-ffl-list.csv', 'file:///0926-ffl-list.csv',
    'http://reference.example/0926-ffl-list.csv', 'https://reference.example:8443/0926-ffl-list.csv',
])
async def test_private_and_non_https_configured_sources_never_fetch(monkeypatch, url):
    monkeypatch.setenv('BASE_REFERENCE_FILE_URL', url)
    client = AsyncMock()
    monkeypatch.setattr(reference_source, 'file_client', client)
    with pytest.raises(ValueError):
        await reference.refresh(None, None, date(2026, 10, 28))
    client.assert_not_called()


@pytest.mark.asyncio
async def test_dns_mixed_answers_and_redirects_to_private_addresses_are_refused(monkeypatch):
    import asyncio
    loop = asyncio.get_running_loop()
    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (PUBLIC_IP, 443)),
               (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.1', 443))]
    monkeypatch.setattr(loop, 'getaddrinfo', AsyncMock(return_value=answers))
    with pytest.raises(ValueError, match='Private'):
        await reference_source.destination(FILE_URL)
    monkeypatch.setattr(loop, 'getaddrinfo', AsyncMock(return_value=answers[:1]))
    seen = []
    def redirect(request):
        seen.append(request)
        return httpx.Response(302, headers={'location': 'https://127.0.0.1/0926-ffl-list.csv'})
    monkeypatch.setattr(reference, '_last_read', 0)
    monkeypatch.setattr(reference, '_blocked_files', set())
    async with httpx.AsyncClient(transport=httpx.MockTransport(redirect)) as client:
        with pytest.raises(ValueError, match='Private'):
            await reference.read_public(client, FILE_URL, configured=True)
    assert len(seen) == 1 and seen[0].url.host == PUBLIC_IP
    assert seen[0].headers['host'] == 'reference.example'


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [b'', b'not,a,licence\n1,2,3\n', b'<html>captcha</html>'])
async def test_bad_file_does_not_install_or_fall_back_to_atf(database, monkeypatch, body):  # noqa: F811 (pytest fixture parameter)
    conn, rt = database
    monkeypatch.setenv('BASE_REFERENCE_FILE_URL', FILE_URL)
    monkeypatch.setattr(reference, '_blocked_files', set())
    monkeypatch.setattr(reference_source, 'destination', AsyncMock(return_value=(httpx.URL('https://' + PUBLIC_IP + '/0926-ffl-list.csv'), 'reference.example')))
    seen = []
    def get(request):
        seen.append(request)
        return httpx.Response(200, content=body)
    monkeypatch.setattr(reference_source, 'file_client', lambda: httpx.AsyncClient(transport=httpx.MockTransport(get)))
    async with engine(rt, monkeypatch, lambda request: pytest.fail('No fallback to ATF')) as store:
        await check_reference(store)
        await check_reference(BaseStore(rt))
        assert await store.latest_file() is None
        assert await conn.fetchval('SELECT count(*) FROM tank.base_reference_entries') == 0
        assert len(seen) == 1


def test_only_one_new_setting_and_no_private_network_bypass():
    root = Path(__file__).resolve().parents[1]
    assert (root / '.env.example').read_text().count('BASE_REFERENCE_FILE_URL=') == 1
    for name in ('docker-compose.yml', 'agents/base/docker-compose.yml'):
        assert 'BASE_REFERENCE_FILE_URL: ${BASE_REFERENCE_FILE_URL:-}' in (root / name).read_text()
    assert 'COPY agents/_brain/security.py /app/reference_security.py' in (root / 'agents/base/Dockerfile').read_text()
    assert reference_source.public_destination is security.public_destination


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['/ffl.csv', '/1326-ffl-list.csv', '/1299-ffl-list.csv'])
async def test_missing_invalid_or_future_file_date_is_not_invented(monkeypatch, path):
    monkeypatch.setenv('BASE_REFERENCE_FILE_URL', 'https://reference.example' + path)
    client = AsyncMock()
    monkeypatch.setattr(reference_source, 'file_client', client)
    with pytest.raises(ValueError, match='No dated complete'):
        await reference.refresh(None, None, date(2026, 10, 28))
    client.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('counts,expected', [
    ({'CA': 3, 'TX': 2, 'WY': 1}, ['WY', 'TX', 'CA']),
    ({'TX': 1, 'CA': 1, 'WY': 2}, ['CA', 'TX', 'WY']),
])
async def test_campaign_persists_fewest_reference_licences_first_then_name(database, counts, expected):  # noqa: F811 (pytest fixture parameter)
    _, rt = database
    store = BaseStore(rt)
    rows = [reference.project(raw(i + 1, state)) for i, state in enumerate(
        state for state, count in counts.items() for _ in range(count))]
    file = await store.install({'published_on': '2026-09-01', 'source_url': FILE_URL,
        'checked_at': '2026-10-28T00:00:00+00:00', 'sha256': 'offline-state-counts', 'rows': rows}, initial=True)
    groups = {state: [row for row in rows if row['state'] == state] for state in counts}
    request_id = uuid.uuid4()
    campaign = await store.create_campaign(TENANT, request_id, 'Offline state test', 'fixture', file['id'], {}, groups)
    plan = await store.campaigns(TENANT)
    assert [row['state'] for row in plan] == expected
    assert [row['records_count'] for row in plan] == [counts[state] for state in expected]
    assert [row['ordinal'] for row in plan] == [0, 1, 2]
    assert all(row['id'] == campaign for row in plan)
    # Repeated confirmation keeps the original campaign and its persisted order.
    assert await store.create_campaign(TENANT, request_id, 'Offline state test', 'fixture', file['id'], {}, {}) == campaign
    assert [row['state'] for row in await store.campaigns(TENANT)] == expected
