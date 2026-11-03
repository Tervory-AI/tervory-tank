"""Offline review regressions: real proxy limits, pinned ownership and health."""
import socket

import httpx
import pytest

from agents.ghost import cloudflare_edge as cf
from agents.ghost.client_settings import ApplyMode
from agents.ghost.enforce_apply import apply_from_payload, approve_pending, undo_from_payload
from agents.radix.egress import Proxy, Server, BOUNDS
from test_autumbra_cloudflare_hand import FakeCloudflare, settings, payload, undo_payload, OTHER


def test_health_probes_and_propose_approve_undo_at_six_tunnels(monkeypatch, tmp_path):
    connect_original = socket.create_connection
    upstreams = []
    def upstream(ip, port):
        one, two = socket.socketpair()
        two.close()
        upstreams.append((ip, port))
        return one
    proxy = Proxy(verified_host="api.cloudflare.com", allow_storage=False,
                  resolve=lambda host: "1.1.1.1", connect=upstream)
    assert BOUNDS["max_requests_per_minute"] == 6
    server = Server(proxy).start()
    def proxy_connect(address, *args, **kwargs):
        assert address == ("egress-proxy", 8080)
        return connect_original(("127.0.0.1", server.port), *args, **kwargs)
    monkeypatch.setattr(cf.socket, "create_connection", proxy_connect)
    api = FakeCloudflare()
    class OfflineTransport(cf.CloudflareProxyTransport):
        failed = False
        def handle_request(self, request):
            if self.failed:
                raise httpx.ConnectError("offline")
            # Deliberately force a new tunnel for every API request: five calls
            # for apply+Undo, rather than relying on HTTP keepalive to pass.
            with connect_original(("127.0.0.1", server.port), timeout=2) as conn:
                conn.sendall(b"CONNECT api.cloudflare.com:443 HTTP/1.1\r\n\r\n")
                assert b"200 Connection Established" in conn.recv(4096)
            return api(request)
    transport = OfflineTransport()
    edge = cf.CloudflareEdgeControl(tenant_id=settings().tenant_id, site="tervory.com",
                                   transport=transport, health_probe=lambda: True)
    monkeypatch.setenv(cf.TOKEN_ENV, "offline-test-marker")
    monkeypatch.setattr('agents.ghost.site_health.health_configured', lambda *args: True)
    try:
        for _ in range(20):
            assert cf.proxy_answers()
        assert len(proxy._times) == 0
        proposal = apply_from_payload(payload(), settings=settings(ApplyMode.approve_each),
                                      control=edge, data_dir=tmp_path)
        # A failed probe must never change an existing proposal's control.
        monkeypatch.setattr(cf, 'proxy_answers', lambda: False)
        approval = payload(action="approve_shield", prior_receipt_id=proposal['id'])
        approved = approve_pending(approval, settings=settings(), control=edge, data_dir=tmp_path)
        assert approved['applied'] and approved['control'] == 'cloudflare'
        transport.failed = True
        with pytest.raises(cf.CloudflareEdgeError, match='Cloudflare request failed.'):
            undo_from_payload(undo_payload(approved), settings=settings(), control=edge, data_dir=tmp_path)
        assert len(edge.blocked) == 1
        transport.failed = False
        result = undo_from_payload(undo_payload(approved), settings=settings(), control=edge, data_dir=tmp_path)
        assert result['outcome'] == 'undone' and not edge.blocked
        assert [r['id'] for r in api.rules] == [OTHER]
        assert len(proxy._times) == len(upstreams) == 5
    finally:
        edge.close()
        server.close()


def test_failed_approval_is_requeued_with_same_control(monkeypatch, tmp_path):
    from agents.ghost.threat_queue import ThreatPayloadQueue, enforce_drain_once
    from test_autumbra_cloudflare_hand import edge
    api = FakeCloudflare()
    control = edge(api)
    proposal = apply_from_payload(payload(), settings=settings(ApplyMode.approve_each),
                                  control=control, data_dir=tmp_path)
    queue = ThreatPayloadQueue(tmp_path/'queue')
    queue.put(payload(action='approve_shield', prior_receipt_id=proposal['id']))
    original = control._request
    def fail(*args, **kwargs):
        raise cf.CloudflareEdgeError('Cloudflare request failed.')
    monkeypatch.setattr(control, '_request', fail)
    with pytest.raises(cf.CloudflareEdgeError):
        enforce_drain_once(queue, settings=settings(), control=control, data_dir=tmp_path)
    assert len(list((queue.root/'inbox').glob('*.json'))) == 1
    monkeypatch.setattr(control, '_request', original)
    approved = enforce_drain_once(queue, settings=settings(), control=control, data_dir=tmp_path)
    assert approved['applied'] and approved['control'] == 'cloudflare'
    queue.put(undo_payload(approved))
    monkeypatch.setattr(control, '_request', fail)
    with pytest.raises(cf.CloudflareEdgeError):
        enforce_drain_once(queue, settings=settings(), control=control, data_dir=tmp_path)
    monkeypatch.setattr(control, '_request', original)
    assert enforce_drain_once(queue, settings=settings(), control=control, data_dir=tmp_path)['outcome'] == 'undone'
    assert not control.blocked


def client_hello(host, version=None):
    import ssl
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    if version is not None:
        context.maximum_version = version
    outgoing = ssl.MemoryBIO()
    client = context.wrap_bio(ssl.MemoryBIO(), outgoing, server_hostname=host)
    try:
        client.do_handshake()
    except ssl.SSLWantReadError:
        pass
    return outgoing.read()


@pytest.mark.parametrize('host', ['api.cloudflare.com', 'tervory.com'])
@pytest.mark.parametrize('case', ['matching', 'mismatch', 'missing', 'plaintext', 'truncated', 'case', 'trailing_dot'])
def test_opt_in_sni_refuses_before_upstream(host, case):
    hello = (b'GET / HTTP/1.1\r\n\r\n' if case == 'plaintext' else
             client_hello(None if case == 'missing' else
                          'example.com' if case == 'mismatch' else
                          host.upper() if case == 'case' else
                          host+'.' if case == 'trailing_dot' else host))
    if case == 'truncated':
        hello = hello[:10]
    connected = []
    received = []
    threads = []
    def upstream(ip, port):
        import threading
        one, two = socket.socketpair()
        connected.append((ip, port))
        def collect():
            with two:
                raw = b''
                while len(raw) < len(hello):
                    chunk = two.recv(65536)
                    if not chunk:
                        break
                    raw += chunk
                received.append(raw)
                two.sendall(b'accepted')
        thread = threading.Thread(target=collect)
        thread.start()
        threads.append(thread)
        return one
    server = Server(Proxy(verified_host=host, allow_storage=False, require_sni=True,
                          resolve=lambda name: '1.1.1.1', connect=upstream)).start()
    try:
        with socket.create_connection(('127.0.0.1', server.port), timeout=2) as conn:
            conn.sendall(f'CONNECT {host}:443 HTTP/1.1\r\n\r\n'.encode())
            assert b'200 Connection Established' in conn.recv(4096)
            # Exercise partial TCP delivery of the ClientHello.
            conn.sendall(hello[:7])
            conn.sendall(hello[7:])
            if case == 'truncated':
                conn.shutdown(socket.SHUT_WR)
            reply = conn.recv(4096)
            assert (reply == b'accepted') is (case == 'matching')
        assert len(connected) == (1 if case == 'matching' else 0)
        if case == 'matching':
            assert received == [hello]
    finally:
        server.close()
        for thread in threads:
            thread.join(2)


def test_radix_sni_default_off_preserves_plaintext_relay():
    # Existing Radix contract allows opaque bytes; opt-in must not alter it.
    original = Proxy()
    assert original._require_sni is False


def test_project_site_is_a_founder_setting():
    from pathlib import Path
    import yaml
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load((root/'agents/ghost/docker-compose.enforce.yml').read_text())
    assert compose['services']['enforce']['environment']['SITE_NAME'] == '${SITE_NAME:-}'
    assert '`SITE_NAME`' in (root/'docs/ops/AUTUMBRA-CLOUDFLARE-LIVE.md').read_text()


class ObserverStopped(Exception):
    pass


@pytest.mark.parametrize('secret,site', [('', 'tervory.com'), ('   ', 'tervory.com'),
    ('offline-test-marker', ''), ('offline-test-marker', 'example.com')])
def test_unconfigured_observer_sleeps_without_requests(monkeypatch, capsys, tmp_path, secret, site):
    from agents.ghost import site_health as health
    monkeypatch.setenv(health.SECRET_ENV, secret)
    monkeypatch.setenv('SITE_NAME', site)
    monkeypatch.setattr(health, 'HEALTH_DIR', tmp_path)
    assert not health.health_configured('tervory.com')
    sleeps = []
    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise ObserverStopped
    monkeypatch.setattr(health.time, 'sleep', sleep)
    monkeypatch.setattr(health.httpx, 'HTTPTransport', lambda **kwargs: pytest.fail('request transport created'))
    with pytest.raises(ObserverStopped):
        health.main()
    assert sleeps == [15, 15, 15]
    assert capsys.readouterr().out == 'Health observer is not configured.\n'


def test_observer_only_fetches_this_projects_site(monkeypatch, tmp_path):
    from agents.ghost import site_health as health
    monkeypatch.setenv(health.SECRET_ENV, 'offline-test-marker')
    monkeypatch.setenv('SITE_NAME', 'tervory.com')
    monkeypatch.setattr(health, 'OUTPUT_DIR', tmp_path)
    monkeypatch.setitem(health.HEALTH_URLS, 'other.example', 'https://other.example/')
    seen = []
    def respond(request):
        seen.append(str(request.url))
        return httpx.Response(200)
    def transport(**kwargs):
        assert kwargs == {'proxy': 'http://health-egress-proxy:8080'}
        return httpx.MockTransport(respond)
    monkeypatch.setattr(health.httpx, 'HTTPTransport', transport)
    def stop(seconds):
        raise ObserverStopped
    monkeypatch.setattr(health.time, 'sleep', stop)
    with pytest.raises(ObserverStopped):
        health.main()
    assert seen == ['https://tervory.com/']
    assert sorted(p.name for p in tmp_path.iterdir()) == ['tervory.com.json']
