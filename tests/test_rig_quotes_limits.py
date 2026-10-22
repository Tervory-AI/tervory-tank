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
        assert (await limits.consume(TENANT, "192.0.2.1", "/v1/rig/search")).retry_after == 0
    assert (await limits.consume(TENANT, "192.0.2.1", "/v1/rig/search")).retry_after == 60
    assert (await limits.consume(TENANT, "192.0.2.2", "/v1/rig/search")).retry_after == 0
    assert (await limits.consume(TENANT, "192.0.2.1", "/v1/rig/graph/{product_id}")).retry_after == 0
    for _ in range(5):
        assert (await limits.consume(TENANT, "192.0.2.1", "/v1/rig/quote")).retry_after == 0
    assert (await limits.consume(TENANT, "192.0.2.1", "/v1/rig/link-quote")).retry_after == 60
    assert (await limits.consume(TENANT, "192.0.2.2", "/v1/rig/link-quote")).retry_after == 0
    assert "192.0.2" not in str(limits.windows)
    now[0] += 60
    assert (await limits.consume(TENANT, "192.0.2.1", "/v1/rig/quote")).retry_after == 0


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
        assert (await limits.consume(TENANT, "192.0.2.1", "/v1/rig/search")).retry_after == 0
    for _ in range(6000):
        assert (await limits.consume(TENANT, "192.0.2.1", "/v1/rig/search")).retry_after > 0
    # The abusive client has used just 60 of the tenant's 6000 accepted requests.
    for index in range(5940):
        assert (await limits.consume(TENANT, f"shopper-{index}", "/v1/rig/search")).retry_after == 0
    assert (await limits.consume(TENANT, "new-shopper", "/v1/rig/search")).retry_after > 0
    assert (await limits.consume(TENANT, "new-shopper", "/v1/rig/quote")).retry_after == 0
    assert (await limits.consume("other-tenant", "new-shopper", "/v1/rig/search")).retry_after == 0


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


@pytest.mark.asyncio
async def test_two_shoppers_behind_proxy_and_ipv6_rotation(monkeypatch):
    import httpx
    from fastapi import FastAPI
    from rigbox.api import mount
    from test_rig_quotes import service, CONTACT
    from rigbox.quotes.sample import KEY

    monkeypatch.setenv("RIG_TRUSTED_PROXY_CIDRS", "10.20.0.0/24")
    app = FastAPI()
    app.state.rig = await service()
    app.state.rig.public_limits = MemoryRateLimits(clock=lambda: 123)
    mount(app)
    headers = {"X-Rig-Key": KEY, "Origin": "http://127.0.0.1:8001"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("10.20.0.2", 123)), base_url="http://test") as client:
        for index in range(6):
            response = await client.post("/v1/rig/quote", headers={**headers, "X-Forwarded-For": f"2001:db8:1:1::{index + 1}"},
                                         json={"product_id": "CORE-1", "contact": CONTACT})
            assert response.status_code == (200 if index < 5 else 429)
        # A second shopper on another /64 behind the exact same proxy still works.
        other = await client.post("/v1/rig/quote", headers={**headers, "X-Forwarded-For": "2001:db8:1:2::1"},
                                  json={"product_id": "CORE-1", "contact": CONTACT})
        assert other.status_code == 200
        for origin in (None, "https://wrong.example"):
            invalid = {**headers, "X-Forwarded-For": "192.0.2.9"}
            if origin:
                invalid["Origin"] = origin
            else:
                invalid.pop("Origin")
            for route in ("quote", "link-quote"):
                assert (await client.post("/v1/rig/" + route, headers=invalid, json={})).status_code == 403
    assert len(app.state.rig.handoff.sent) == 6


@pytest.mark.asyncio
async def test_tenant_ceiling_holds_and_alerts_without_blocking_shoppers(caplog):
    import httpx
    from fastapi import FastAPI
    from rigbox.api import mount
    from rigbox.quotes.api import mount as mount_admin
    from test_rig_quotes import service, CONTACT, OTHER
    from rigbox.quotes.sample import KEY
    from rigbox.service import hash_key

    app = FastAPI()
    rig = app.state.rig = await service()
    rig.public_limits = MemoryRateLimits(clock=lambda: 120)
    for index in range(600):
        decision = await rig.public_limits.consume(TENANT, f"shopper-{index}", "/v1/rig/quote")
        assert not decision.hold and decision.retry_after == 0
    mount(app)
    mount_admin(app)
    admin = "RIG_ADMIN_KEY"
    await rig.store.put_key(TENANT, hash_key(admin), "admin", [])
    await rig.store.put_key(OTHER, hash_key("OTHER_RIG_ADMIN_KEY"), "admin", [])
    headers = {"X-Rig-Key": KEY, "Origin": "http://127.0.0.1:8001"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("192.0.2.9", 123)), base_url="http://test") as client:
        response = await client.post("/v1/rig/quote", headers=headers, json={"product_id": "CORE-1", "contact": CONTACT})
        assert response.status_code == 200 and response.json()["delivery"] == "needs_person"
        quote_id = response.json()["request_id"]
        linked = await client.post("/v1/rig/link-quote", headers=headers,
                                   json={"url": "https://example.com/item", "contact": CONTACT})
        assert linked.status_code == 200 and linked.json()["delivery"] == "needs_person"
        assert "rig_quote_held" in caplog.text and quote_id in caplog.text
        assert CONTACT["email"] not in caplog.text and "192.0.2.9" not in caplog.text
        assert await rig.retry_pending(TENANT) == 0 and not rig.handoff.sent
        queue = await client.get("/v1/rig/admin/quotes/attention", headers={"X-Rig-Key": admin})
        assert len(queue.json()["requests"]) == 2
        assert queue.json()["requests"][0]["error"] == "tenant_quote_limit"
        assert (await client.get("/v1/rig/admin/quotes/attention", headers=headers)).status_code == 403
        assert (await client.get("/v1/rig/admin/quotes/attention", headers={"X-Rig-Key": "OTHER_RIG_ADMIN_KEY"})).json()["requests"] == []
        await client.post(f"/v1/rig/admin/quotes/{quote_id}/retry", headers={"X-Rig-Key": admin})
        assert not rig.handoff.sent
        released = await client.post(f"/v1/rig/admin/quotes/{quote_id}/resume", headers={"X-Rig-Key": admin})
        assert released.json()["status"] == "sent" and len(rig.handoff.sent) == 1
        for _ in range(3):
            assert (await client.post("/v1/rig/quote", headers=headers, json={"product_id": "CORE-1", "contact": CONTACT})).status_code == 200
        assert (await client.post("/v1/rig/quote", headers=headers, json={"product_id": "CORE-1", "contact": CONTACT})).status_code == 429
        assert (await client.get("/v1/rig/search?q=Core", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_failed_key_lookups_are_bounded_before_database_access(monkeypatch):
    import asyncio
    from rigbox.quotes.limits import FailedKeyLimits
    from rigbox.quotes.sample import KEY
    from rigbox.service import RigError
    from test_rig_quotes import service

    rig = await service()
    now = [120]
    rig.failed_keys = FailedKeyLimits(limit=2, clock=lambda: now[0])
    lookup = rig.store.key
    looked_up = []
    async def spy(digest):
        looked_up.append(digest)
        await asyncio.sleep(0)
        return await lookup(digest)
    monkeypatch.setattr(rig.store, "key", spy)
    # Successful browsing does not consume the failed-lookup budget.
    for _ in range(5):
        assert await rig.authenticate(KEY, "192.0.2.1")
    looked_up.clear()
    results = await asyncio.gather(*(rig.authenticate(f"rk_pub_unknown_{i}", f"2001:db8:1:1::{i+1}")
                                    for i in range(10)), return_exceptions=True)
    assert len(looked_up) == 2
    assert sorted(result.status for result in results) == [401, 401] + [429] * 8
    assert all(isinstance(result, RigError) for result in results)
    assert await rig.authenticate(KEY, "2001:db8:2:2::1")
    now[0] += 60
    assert await rig.authenticate(KEY, "2001:db8:1:1::1")
    assert "2001:db8" not in str(rig.failed_keys.counts)


@pytest.mark.asyncio
async def test_failed_key_flood_from_10000_ipv6_subnets_does_not_lock_out_stores():
    from rigbox.quotes.limits import FailedKeyLimits
    from rigbox.quotes.sample import KEY
    from rigbox.service import RigError, hash_key
    from test_rig_quotes import service, OTHER

    rig = await service()
    rig.failed_keys = FailedKeyLimits(clock=lambda: 120)
    await rig.store.put_key(OTHER, hash_key("rk_pub_OTHER_RIG_PUBLISHABLE_KEY"), "publishable", [])
    for index in range(10000):
        # The review reproduction: 10,000 different /64s within one /48.
        with pytest.raises(RigError) as error:
            await rig.authenticate("rk_pub_INVALID_RIG_PUBLISHABLE_KEY", f"2001:db8:1:{index:x}::1")
        assert error.value.status == (401 if index < 60 else 429)
    assert len(rig.failed_keys.counts) == 1
    assert (await rig.authenticate(KEY, "2001:db8:2::1"))["tenant_id"] == TENANT
    assert (await rig.authenticate("rk_pub_OTHER_RIG_PUBLISHABLE_KEY", "192.0.2.1"))["tenant_id"] == OTHER


@pytest.mark.asyncio
async def test_full_failed_key_table_evicts_oldest_and_only_that_guard_fails_open():
    from ipaddress import IPv4Address
    from rigbox.quotes.limits import FailedKeyLimits
    from rigbox.quotes.sample import KEY
    from rigbox.service import RigError
    from test_rig_quotes import service

    rig = await service()
    limits = rig.failed_keys = FailedKeyLimits(limit=1, clock=lambda: 120)
    for index in range(10000):
        assert limits.reserve(str(IPv4Address(0xC6120000 + index))) is not None
    oldest = next(iter(limits.counts))
    assert await rig.authenticate(KEY, "192.0.2.1")  # Full table cannot reject a new shopper.
    assert oldest not in limits.counts and len(limits.counts) == 9999
    assert limits.reserve("192.0.2.2") is not None
    assert len(limits.counts) == 10000
    with pytest.raises(RigError) as error:
        await rig.authenticate("rk_pub_INVALID_RIG_PUBLISHABLE_KEY", "192.0.2.3")
    assert error.value.status == 401  # Fail-open never accepts an invalid key.
    assert len(limits.counts) == 9999
    assert limits.reserve("192.0.2.2") is None  # Tracked clients still have their failed-key cap.
    for _ in range(5):
        assert (await rig.public_limits.consume(TENANT, "192.0.2.1", "/v1/rig/quote")).retry_after == 0
    assert (await rig.public_limits.consume(TENANT, "192.0.2.1", "/v1/rig/quote")).retry_after > 0
