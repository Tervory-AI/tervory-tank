"""Public pages: truthful identity, pacing, and no workarounds for a block."""
import io
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from feeds.collect import EvidenceClient, collect
from feeds.live import BlockedSite, PoliteClient, USER_AGENT
from feeds.catalog import sources


class Response:
    status = 200
    def __init__(self, body=b"<html>Public information</html>"): self.body = body
    def read(self): return self.body
    def __iter__(self): yield self.body
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def close(self): pass


@pytest.mark.parametrize("status", [401, 402, 403, 429])
@pytest.mark.parametrize("stream", [False, True])
def test_denied_site_is_latched_without_retrying_or_changing_path(status, stream):
    calls = []
    def denied(request, **kwargs):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, "blocked", {}, None)
    client = PoliteClient(opener=denied, delay=0)
    def read(url): return list(client.iter_lines(url)) if stream else client.get(url)
    with pytest.raises(BlockedSite): read("https://site.test/data")
    with pytest.raises(BlockedSite): read("https://site.test/another-path")
    assert calls == ["https://site.test/data"]


@pytest.mark.parametrize("body", [b'<div class="g-recaptcha"></div>', b"Verify you are human", b'<input type="password">', b"Subscribe to continue"])
def test_challenge_or_login_page_stops_the_site(body):
    calls = []
    def opener(request, **kwargs):
        calls.append(request.full_url)
        return Response(body)
    client = PoliteClient(opener=opener, delay=0)
    with pytest.raises(BlockedSite): client.get("https://site.test/data")
    with pytest.raises(BlockedSite): list(client.iter_lines("https://site.test/data.csv"))
    assert len(calls) == 1


def test_proxy_denial_and_challenge_503_are_not_transport_retries():
    for error in [urllib.error.URLError("Tunnel connection failed: 403 Forbidden"),
                  urllib.error.HTTPError("https://site.test/data", 503, "challenge", {}, io.BytesIO(b"Verify you are human"))]:
        calls = []
        def opener(request, **kwargs):
            calls.append(request.full_url)
            raise error
        with pytest.raises(BlockedSite): PoliteClient(opener=opener, delay=0).get("https://site.test/data")
        assert len(calls) == 1


def test_login_path_is_not_requested_and_redirect_block_stops_both_hosts():
    calls = []
    def opener(request, **kwargs):
        calls.append(request.full_url)
        raise urllib.error.HTTPError("https://download.test/data", 403, "blocked", {}, None)
    client = PoliteClient(opener=opener, delay=0)
    with pytest.raises(BlockedSite): client.get("https://private.test/login")
    assert calls == []
    with pytest.raises(BlockedSite): client.get("https://publisher.test/data")
    with pytest.raises(BlockedSite): client.get("https://download.test/other")
    with pytest.raises(BlockedSite): client.get("https://publisher.test/other")
    assert calls == ["https://publisher.test/data"]


def test_collector_records_blocked_and_continues_with_other_sites():
    calls = []
    def opener(request, **kwargs):
        calls.append(request)
        if "weather.gov" in request.full_url:
            raise urllib.error.HTTPError(request.full_url, 403, "blocked", {}, None)
        return Response(b"<html>Public information</html>")
    client = EvidenceClient(PoliteClient(opener=opener, delay=0))
    source = next(row for row in sources("ffl") if row.id == "noaa_alerts")
    for _ in range(2):
        result = collect(source, fixtures=None, backfill=False, client=client)
        assert result["note"] == "Off, blocked"
        assert not result["points"] and not result["events"]
    assert len(calls) == 1
    assert client.get("https://another.test/public")
    assert len(calls) == 2
    assert all(request.get_header("User-agent") == USER_AGENT for request in calls)
