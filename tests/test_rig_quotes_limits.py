"""Clients and route budgets cannot exhaust another shopper's quote allowance."""

from pathlib import Path
import sys

import pytest
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "rig"))
from rigbox.quotes.limits import MemoryRateLimits, client_address  # noqa: E402

TENANT = "44444444-4444-4444-8444-444444444444"


@pytest.mark.asyncio
async def test_clients_routes_quote_budget_and_window_expiry():
    now = [120.0]
    limits = MemoryRateLimits(read_limit=2, clock=lambda: now[0])
    for _ in range(2):
        assert await limits.consume(TENANT, "192.0.2.1", "/v1/rig/search") == 0
    assert await limits.consume(TENANT, "192.0.2.1", "/v1/rig/search") == 60
    assert await limits.consume(TENANT, "192.0.2.2", "/v1/rig/search") == 0
    assert await limits.consume(TENANT, "192.0.2.1", "/v1/rig/graph/{product_id}") == 0
    for _ in range(5):
        assert await limits.consume(TENANT, "192.0.2.1", "/v1/rig/quote") == 0
    assert await limits.consume(TENANT, "192.0.2.1", "/v1/rig/link-quote") == 60
    assert await limits.consume(TENANT, "192.0.2.2", "/v1/rig/link-quote") == 0
    assert "192.0.2" not in str(limits.windows)
    now[0] += 60
    assert await limits.consume(TENANT, "192.0.2.1", "/v1/rig/quote") == 0


def test_forwarded_addresses_require_a_known_proxy(monkeypatch):
    def request(peer, forwarded):
        return Request({"type": "http", "client": (peer, 123),
                        "headers": [(b"x-forwarded-for", forwarded.encode())]})
    monkeypatch.delenv("RIG_TRUSTED_PROXY_CIDRS", raising=False)
    assert client_address(request("192.0.2.1", "198.51.100.1")) == "192.0.2.1"
    monkeypatch.setenv("RIG_TRUSTED_PROXY_CIDRS", "10.20.0.0/24")
    assert client_address(request("10.20.0.2", "198.51.100.1, 192.0.2.1")) == "192.0.2.1"
    assert client_address(request("10.20.0.2", "not-an-address")) == "10.20.0.2"
