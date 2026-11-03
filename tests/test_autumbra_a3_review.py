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
    monkeypatch.setattr('agents.ghost.site_health.health_configured', lambda: True)
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
