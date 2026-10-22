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


@pytest.mark.asyncio
async def test_tenant_ceiling_and_rejected_client_do_not_drain_other_shoppers():
    limits = MemoryRateLimits(clock=lambda: 120)
    for _ in range(60):
        assert await limits.consume(TENANT, "192.0.2.1", "/v1/rig/search") == 0
    for _ in range(6000):
        assert await limits.consume(TENANT, "192.0.2.1", "/v1/rig/search") > 0
    # The abusive client has used just 60 of the tenant's 6000 accepted requests.
    for index in range(5940):
        assert await limits.consume(TENANT, f"shopper-{index}", "/v1/rig/search") == 0
    assert await limits.consume(TENANT, "new-shopper", "/v1/rig/search") > 0
    assert await limits.consume(TENANT, "new-shopper", "/v1/rig/quote") == 0
    assert await limits.consume("other-tenant", "new-shopper", "/v1/rig/search") == 0


@pytest.mark.asyncio
async def test_http_separate_budgets_cors_and_spoofed_forwarding():
    import httpx
    from fastapi import FastAPI
    from rigbox.api import mount
    from test_rig_quotes import service, CONTACT
    from rigbox.quotes.sample import KEY

    app = FastAPI()
    app.state.rig = await service()
    app.state.rig.public_limits = MemoryRateLimits(read_limit=2, clock=lambda: 123)
    mount(app)
    headers = {"X-Rig-Key": KEY, "Origin": "http://127.0.0.1:8001"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("192.0.2.1", 1234)), base_url="http://test") as client:
        for _ in range(2):
            assert (await client.get("/v1/rig/search?q=Core", headers=headers)).status_code == 200
        blocked = await client.get("/v1/rig/search?q=Core", headers={**headers, "X-Forwarded-For": "198.51.100.1"})
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "57"
        assert blocked.headers["access-control-allow-origin"] == headers["Origin"]
        assert blocked.headers["access-control-expose-headers"] == "Retry-After"
        for _ in range(5):
            assert (await client.post("/v1/rig/quote", headers=headers,
                               json={"product_id": "CORE-1", "contact": CONTACT})).status_code == 200
        assert (await client.post("/v1/rig/link-quote", headers=headers,
                           json={"url": "https://example.com/item", "contact": CONTACT})).status_code == 429
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("192.0.2.2", 1234)), base_url="http://test") as other:
        assert (await other.get("/v1/rig/search?q=Core", headers=headers)).status_code == 200
