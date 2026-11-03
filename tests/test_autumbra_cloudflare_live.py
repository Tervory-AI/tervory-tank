"""Offline A3 gates, signed health and fixed proxy contracts."""
import hashlib
import hmac
import itertools
import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import yaml

from agents.ghost import cloudflare_edge as cf, site_health as health
from agents.ghost.client_settings import ClientAutumbraSettings
from agents.ghost.enforce_apply import select_control
from agents.ghost.fixture_edge import FixtureEdgeControl
from agents.radix.egress import Proxy, Server

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ROOT = Path(__file__).resolve().parents[1]


def signed_result(monkeypatch, tmp_path, **changes):
    # A public offline marker with no credential capability.
    monkeypatch.setenv(health.SECRET_ENV, "offline-test-marker")
    monkeypatch.setattr(health, "HEALTH_DIR", tmp_path)
    result = dict(site="tervory.com", url="https://tervory.com/", ok=True,
                  status=200, ms=2, checked_at=time.time())
    result.update(changes)
    signature = hmac.new(b"offline-test-marker", health.canonical(result), hashlib.sha256).hexdigest()
    path = tmp_path / "tervory.com.json"
    path.write_text(json.dumps(dict(result=result, signature=signature)))
    return path


@pytest.mark.parametrize("changes,expected", [({}, True), ({"ok": False}, False),
    ({"status": 500}, False), ({"checked_at": 0}, False),
    ({"checked_at": time.time()+1000}, False), ({"url": "https://example.com/"}, False),
    ({"site": "other.tervory.com"}, False), ({"ms": -1}, False)])
def test_signed_health(monkeypatch, tmp_path, changes, expected):
    signed_result(monkeypatch, tmp_path, **changes)
    assert health.read_health("tervory.com") is expected


@pytest.mark.parametrize("mutation", ["unsigned", "tampered", "missing", "corrupt", "oversize"])
def test_bad_health_fails_closed(monkeypatch, tmp_path, mutation):
    path = signed_result(monkeypatch, tmp_path)
    data = json.loads(path.read_text())
    if mutation == "unsigned":
        del data["signature"]
    if mutation == "tampered":
        data["result"]["status"] = 201
    path.write_text(json.dumps(data))
    if mutation == "missing":
        path.unlink()
    if mutation == "corrupt":
        path.write_text("{")
    if mutation == "oversize":
        path.write_text(" " * 4097)
    assert health.read_health("tervory.com") is False


@pytest.mark.parametrize("token,allowed,proxy,observer", itertools.product([False, True], repeat=4))
def test_all_four_gates(monkeypatch, token, allowed, proxy, observer):
    monkeypatch.setenv(cf.TOKEN_ENV, "offline-test-marker" if token else "")
    monkeypatch.setattr(cf, "proxy_answers", lambda: proxy)
    monkeypatch.setattr(health, "health_configured", lambda: observer)
    monkeypatch.setattr(cf, "CloudflareProxyTransport", lambda: httpx.MockTransport(lambda r: pytest.fail("API called")))
    fixture = FixtureEdgeControl(tenant_id=TENANT)
    edge = select_control(site="tervory.com" if allowed else "example.com",
                          settings=ClientAutumbraSettings(tenant_id=TENANT), control=fixture)
    assert isinstance(edge, cf.CloudflareEdgeControl) is (token and allowed and proxy and observer)
    if edge is not fixture:
        edge.close()


def test_proxy_probe_dials_only_fixed_proxy(monkeypatch):
    calls = []
    def fail(address, **kwargs):
        calls.append(address)
        raise OSError
    monkeypatch.setattr(cf.socket, "create_connection", fail)
    assert cf.proxy_answers() is False
    assert calls == [("egress-proxy", 8080)]


def test_live_transport_has_no_direct_fallback(monkeypatch):
    calls = []
    def fail(address, **kwargs):
        calls.append(address)
        raise OSError("offline")
    monkeypatch.setattr(socket, "create_connection", fail)
    with httpx.Client(transport=cf.CloudflareProxyTransport(), trust_env=False) as client:
        with pytest.raises(httpx.ConnectError):
            client.get(cf.API_ROOT)
    assert calls == [("egress-proxy", 8080)]


@pytest.mark.parametrize("host", ["api.cloudflare.com", "tervory.com"])
def test_real_local_proxy_refuses_every_other_destination(host):
    connected = []
    def connect(ip, port):
        connected.append((ip, port))
        upstream, sink = socket.socketpair()
        sink.close()
        return upstream
    proxy = Proxy(verified_host=host, allow_storage=False,
                  resolve=lambda h: "1.1.1.1", connect=connect, max_requests_per_minute=120)
    server = Server(proxy).start()
    try:
        for target in [host+":443", "evil.example:443", "tank:443", "health-observer:443",
                       "other-client:443", "127.0.0.1:443", "169.254.169.254:443",
                       host+":80", "x."+host+":443", host+"@evil.example:443"]:
            with socket.create_connection(("127.0.0.1", server.port), timeout=2) as conn:
                conn.sendall(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
                reply = conn.recv(1024)
                assert (b"200 Connection Established" in reply) is (target == host+":443")
        assert connected == [("1.1.1.1", 443)]
    finally:
        server.close()


def test_observer_get_only_no_cookies_body_redirects():
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, headers={"set-cookie": "untrusted=1"}, content=b"discard")
    with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=False, trust_env=False) as client:
        for _ in range(2):
            assert health.observe_once(client, "tervory.com")["ok"] is True
    assert all(r.method == "GET" and str(r.url) == "https://tervory.com/"
               and r.content == b"" and not r.headers.get("cookie") for r in requests)


def test_compose_one_way_health_and_separate_networks():
    data = yaml.safe_load((ROOT / "agents/ghost/docker-compose.enforce.yml").read_text())
    services = data["services"]
    assert services["enforce"]["networks"] == ["enforce_internal"]
    assert services["health-observer"]["networks"] == ["health_internal"]
    assert services["health-observer"]["volumes"] == ["health_results:/data"]
    assert "health_results:/health:ro" in services["enforce"]["volumes"]
    for name in ("egress-proxy", "health-egress-proxy", "health-observer"):
        assert "ports" not in services[name]
        assert cf.TOKEN_ENV not in services[name]["environment"]
    assert set(services["egress-proxy"]["networks"]) == {"enforce_internal", "egress"}
    assert set(services["health-egress-proxy"]["networks"]) == {"health_internal", "health_egress"}
