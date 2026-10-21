"""Exact R2 host, independent limits and no direct egress from Radix."""
import asyncio
import importlib.util
from pathlib import Path
import secrets
import socket
import sys

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents' / '_chassis'))
from chassis.storage import Storage, StorageError  # noqa: E402

spec = importlib.util.spec_from_file_location('bucket1_egress', ROOT / 'agents/radix/egress.py')
egress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(egress)


@pytest.fixture
def r2_host(monkeypatch):
    account = secrets.token_hex(16)
    monkeypatch.setenv('R2_ACCOUNT_ID', account)
    return account + '.r2.cloudflarestorage.com'


def test_only_exact_account_allowed(r2_host):
    assert egress.parse_connect_target(r2_host + ':443', r2_host) == (r2_host, 443)
    for host in ('r2.cloudflarestorage.com', 'evil.r2.cloudflarestorage.com',
                 r2_host + '.evil.example', 'cloudflare.com', 'api.cloudflare.com',
                 'tervory-radix.' + r2_host, '127.0.0.1', '*.r2.cloudflarestorage.com'):
        assert egress.parse_connect_target(host + ':443', r2_host) is None
    assert egress.parse_connect_target(r2_host + ':80', r2_host) is None


def test_r2_lookup_is_pinned_and_private_dns_denied(monkeypatch, r2_host):
    calls = []
    def resolve(host, port, **kwargs):
        calls.append((host, port))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('1.1.1.1', 443))]
    monkeypatch.setattr(socket, 'getaddrinfo', resolve)
    assert egress.system_resolve(r2_host) == '1.1.1.1'
    assert calls == [(r2_host, 443)]
    with pytest.raises(egress.ProxyError):
        egress.system_resolve('wrong.r2.cloudflarestorage.com')
    assert len(calls) == 1
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.1', 443))])
    with pytest.raises(egress.ProxyError):
        egress.system_resolve(r2_host)


def test_independent_limits_preserve_lokd(r2_host):
    assert egress.BOUNDS == {'max_concurrent': 2, 'max_requests_per_minute': 6,
                             'max_response_bytes': 1_000_000, 'max_duration_seconds': 20}
    proxy = egress.Proxy(now=lambda: 0)
    for _ in range(6):
        assert proxy._admit()
        proxy._release()
    assert not proxy._admit()
    assert proxy._admit(True)
    assert proxy._admit(True)
    assert not proxy._admit(True)
    proxy._release(True)
    proxy._release(True)
    for _ in range(118):
        assert proxy._admit(True)
        proxy._release(True)
    assert not proxy._admit(True)


def test_invalid_account_refuses_policy_startup(monkeypatch):
    for account in ('', '*.example', 'x/../../', 'a' * 31, 'A' * 32):
        monkeypatch.setenv('R2_ACCOUNT_ID', account)
        with pytest.raises(egress.PolicyError):
            egress.load_policy(ROOT / 'agents/radix/egress-policy.json')


def test_storage_without_fixed_proxy_never_creates_http_client(monkeypatch, r2_host):
    env = {'R2_ACCOUNT_ID': r2_host.split('.')[0], 'R2_ACCESS_KEY_ID_RADIX': secrets.token_hex(16),
           'R2_SECRET_ACCESS_KEY_RADIX': secrets.token_hex(32)}
    def no_http(**kwargs):
        pytest.fail('A direct HTTP client was constructed')
    monkeypatch.setattr(httpx, 'AsyncClient', no_http)
    for proxy in ('', 'http://elsewhere:8080', 'https://egress-proxy:8080'):
        with pytest.raises(StorageError, match='proxy'):
            Storage('radix', environ={**env, 'RADIX_EGRESS_PROXY': proxy})


def test_storage_http_client_has_only_fixed_proxy(monkeypatch, r2_host):
    calls = []
    original = httpx.AsyncClient
    def client(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(httpx, 'AsyncClient', client)
    async def scenario():
        store = Storage('radix', environ={'R2_ACCOUNT_ID': r2_host.split('.')[0],
                        'R2_ACCESS_KEY_ID_RADIX': secrets.token_hex(16),
                        'R2_SECRET_ACCESS_KEY_RADIX': secrets.token_hex(32),
                        'RADIX_EGRESS_PROXY': 'http://egress-proxy:8080'})
        await store.close()
    asyncio.run(scenario())
    assert calls[0]['proxy'] == 'http://egress-proxy:8080'
    assert calls[0]['trust_env'] is False
    assert calls[0]['follow_redirects'] is False


def test_r2_tunnel_reaches_only_pinned_address(r2_host):
    calls = []
    def connect(address, port):
        calls.append((address, port))
        left, right = socket.socketpair()
        right.close()
        return left
    proxy = egress.Proxy(resolve=lambda host: '1.1.1.1' if host == r2_host else pytest.fail('wrong host'), connect=connect)
    server = egress.Server(proxy).start()
    try:
        with socket.create_connection(('127.0.0.1', server.port), timeout=2) as client:
            client.sendall(f'CONNECT {r2_host}:443 HTTP/1.1\r\n\r\n'.encode())
            assert client.recv(4096).startswith(b'HTTP/1.1 200')
    finally:
        server.close()
    assert calls == [('1.1.1.1', 443)]


def test_real_storage_transport_resolves_only_room_proxy(monkeypatch, r2_host):
    calls = []
    def resolve(host, *args, **kwargs):
        calls.append(host)
        assert host in ('egress-proxy', b'egress-proxy')
        raise OSError('test proxy unavailable')
    monkeypatch.setattr(socket, 'getaddrinfo', resolve)
    async def scenario():
        store = Storage('radix', environ={'R2_ACCOUNT_ID': r2_host.split('.')[0],
                        'R2_ACCESS_KEY_ID_RADIX': secrets.token_hex(16),
                        'R2_SECRET_ACCESS_KEY_RADIX': secrets.token_hex(32),
                        'RADIX_EGRESS_PROXY': 'http://egress-proxy:8080'})
        try:
            with pytest.raises(StorageError, match='unreachable'):
                await store.usage()
        finally:
            await store.close()
    asyncio.run(scenario())
    assert calls
