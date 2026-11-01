"""Actual room app/worker; only publisher I/O is replayed from saved responses.

This entry point refuses any database except an explicitly selected local test
database. It is never imported by production code or copied into the room image.
"""
import io
import socket
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from fixture_proof.server import database_url

database_url()
ROOT = Path(__file__).resolve().parents[2]
REPLAYS = {
    "https://www.federalreserve.gov/feeds/press_all.xml": ROOT / "tests/market_lab_keyless_feeds/fixtures/feed.xml",
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.atom": ROOT / "tests/market_lab_keyless_feeds/fixtures/atom.xml",
}
_dns = socket.getaddrinfo


def public_dns(host, *args, **kwargs):
    if host in {urlsplit(url).hostname for url in REPLAYS}:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    if host in {"localhost", "127.0.0.1", "::1"}:
        return _dns(host, *args, **kwargs)
    raise AssertionError("offline proof refused an unrecorded hostname")


def replay(self, request, *args, **kwargs):
    url = request.full_url if isinstance(request, urllib.request.Request) else request
    if url not in REPLAYS:
        raise AssertionError("offline proof refused an unrecorded publisher request")
    response = io.BytesIO(REPLAYS[url].read_bytes())
    response.status = 200
    return response


socket.getaddrinfo = public_dns
urllib.request.OpenerDirector.open = replay

from app import app as app
