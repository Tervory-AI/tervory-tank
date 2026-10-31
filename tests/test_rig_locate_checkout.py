"""Locate switch, live confirm, holds, test-only payments and sandbox-only orders.

Offline. Checkers, payment providers and the order step are test doubles here only; the
product path wires the real checkers and no payment provider.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
from rigbox import payments
from rigbox.locate import SupplyStore, catalogue, enabled
from rigbox.locate_live import (Checkers, Holds, LiveResult, LocateRefused, SourceApiChecker, TigerChecker,
                                confirm, hold_token, read_token)
from rigbox.fulfilment import sandbox_orders
from rigbox.quotes.senders import DeliveryError
from rigbox.quotes.privacy import shopper_body
from rigbox.quotes.service import QuoteService
from rigbox.quotes.store import MemoryQuotes
from rigbox.retailer import Retailer
from rigbox.service import RigError, Service
from rigbox.store import MemoryStore

NOW = datetime.now(timezone.utc)
TENANT = "00000000-0000-0000-0000-000000000201"
OTHER = "00000000-0000-0000-0000-000000000202"
SECRET = b"t" * 40


class Live:
    """Test double checker."""

    def __init__(self, result):
        self.result, self.calls = result, []

    async def check(self, tenant, source, offer):
        self.calls.append((tenant, source["id"], offer["sku"]))
        return self.result


def available(price="42.00", currency="USD", checked=None, code=None):
    return LiveResult("available", Decimal(price), currency, checked or datetime.now(timezone.utc), code, "double")


async def shop(enabled_flag=True, tenant=TENANT):
    store = MemoryStore()
    product = dict(sku="part-1", id="part-1", gtin="847313003072", mpn="00307", name="Roller cam pin",
                   brand="POF-USA", category="Parts", price="3350", currency="ZAR",
                   image_url="https://example.com/part.png", active=True,
                   attributes={"stock": {"status": "out_of_stock"}})
    await store.upsert_product(tenant, product)
    await store.save_rule(tenant, {"freight": "5", "duty_percent": "0", "margin_percent": "20"})
    await store.put_retailer(tenant, "shop", "shop@example.com", None, "Shop", locate_enabled=enabled_flag)
    supply = SupplyStore(store)
    await supply.source(tenant, dict(id="other-store", approved=True, priority=1, max_offer_age_seconds=3600,
                                     provider="tiger", site="https://other.example"))
    store.supply_state[tenant]["offers"] = [dict(
        tenant_id=tenant, source_id="other-store", sku="RSR|POF00307", gtin="847313003072", brand="POF-USA",
        mpn="00307", quantity="1", status="available", eta="2026-11-12", ship_days=10, region="US",
        cost="40", currency="USD", seen_at=NOW, url="https://other.example/product/cam-pin/")]
    return store


async def rate_stub(store):
    async def rate(tenant, source, target):
        if (source, target) == ("USD", "ZAR"):
            return Decimal("18")
        if source == target:
            return Decimal("1")
        raise ValueError("no rate")
    store.rate = rate
    return store


# 1. Switch: off by default, refusal and skipped supply lookup.

@pytest.mark.asyncio
async def test_switch_is_off_by_default_and_persists_explicit_values():
    store = MemoryStore()
    await store.put_retailer(TENANT, "shop", None, None, "Shop")
    assert await enabled(store, TENANT) is False
    assert (await store.retailer(TENANT))["locate_enabled"] is False
    await store.put_retailer(TENANT, "shop", None, None, "Shop", locate_enabled=True)
    # Saving other settings without the field keeps the saved value.
    await store.put_retailer(TENANT, "shop", "a@example.com", None, "Shop")
    assert await enabled(store, TENANT) is True
    assert await enabled(MemoryStore(), OTHER) is False


@pytest.mark.asyncio
async def test_settings_toggle_requires_a_boolean_and_panel_reports_it():
    store = await rate_stub(await shop(False))
    retailer = Retailer(Service(store))
    base = {"name": "Shop", "email": "shop@example.com"}
    for bad in ("true", 1, None):
        with pytest.raises(ValueError):
            await retailer.set_settings(TENANT, {**base, "locate_enabled": bad})
    await retailer.set_settings(TENANT, {**base, "locate_enabled": True})
    assert (await retailer.panel(TENANT))["settings"]["locate_enabled"] is True
    await retailer.set_settings(TENANT, base)
    assert (await retailer.panel(TENANT))["settings"]["locate_enabled"] is True
    await retailer.set_settings(TENANT, {**base, "locate_enabled": False})
    assert (await retailer.panel(TENANT))["settings"]["locate_enabled"] is False


@pytest.mark.asyncio
async def test_off_refuses_locate_confirm_accept_and_skips_search_and_quote_lookup():
    store = await rate_stub(await shop(False))
    service = QuoteService(store, None, None, MemoryQuotes(store))
    service.locate_checker = Live(available())
    for call in (service.locate(TENANT, "part-1"), service.locate_confirm(TENANT, "part-1"),
                 service.locate_accept(TENANT, {"product_id": "part-1"})):
        with pytest.raises(RigError) as raised:
            await call
        assert raised.value.status == 403 and raised.value.code == "locate_disabled"
    rows = await catalogue(store, TENANT)
    assert "availability" not in rows[0]
    payload, _ = await service.quote_payload(TENANT, {"product_id": "part-1", "contact": {
        "name": "Shopper", "email": "shopper@example.com"}})
    assert "locate" not in payload
    assert service.locate_checker.calls == []


# 2. Confirm: live re-check, freshness, unknown never available.

@pytest.mark.asyncio
async def test_confirm_issues_hold_from_live_price_without_supplier_fields():
    store = await rate_stub(await shop())
    checker = Live(available("45.00"))
    product = (await store.products(TENANT))[0]
    result = await confirm(store, TENANT, product, checker, secret=SECRET)
    public = result["public"]
    assert public["status"] == "available_to_order"
    # (45 + 5) * 18 / 0.8 from the live price, not the imported 40.
    assert public["price"] == {"amount": "1125.00", "currency": "ZAR"}
    assert checker.calls == [(TENANT, "other-store", "RSR|POF00307")]
    assert set(shopper_body(public)) == {"status", "eta", "price", "expires_at", "hold"}
    assert "other-store" not in json.dumps(shopper_body(public)) and "RSR" not in json.dumps(public)
    assert read_token(SECRET, TENANT, public["hold"], datetime.now(timezone.utc)) == result["hold_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("live,expected", [
    (LiveResult.unknown("double", "blocked"), "check_with_store"),
    (LiveResult("unavailable", method="double"), "unavailable"),
    (LiveResult("available", None, "USD", NOW, None, "double"), "check_with_store"),
    ("stale-live", "check_with_store"),
    ("other-gtin", "check_with_store"),
])
async def test_confirm_never_shows_unknown_or_stale_stock_as_available(live, expected):
    store = await rate_stub(await shop())
    if live == "stale-live":
        live = available(checked=datetime.now(timezone.utc) - timedelta(hours=2))
    elif live == "other-gtin":
        live = available(code="00000000000000")
    result = await confirm(store, TENANT, (await store.products(TENANT))[0], Live(live), secret=SECRET)
    assert result["public"] == {"status": expected}
    assert not store.supply_state[TENANT].get("holds")


@pytest.mark.asyncio
async def test_confirm_rechecks_offer_freshness_before_any_live_call():
    store = await rate_stub(await shop())
    store.supply_state[TENANT]["offers"][0]["seen_at"] = NOW - timedelta(hours=3)
    checker = Live(available())
    result = await confirm(store, TENANT, (await store.products(TENANT))[0], checker, secret=SECRET)
    assert result["public"] == {"status": "check_with_store"} and checker.calls == []


@pytest.mark.asyncio
async def test_provider_without_live_checker_is_unknown():
    store = await rate_stub(await shop())
    checkers = Checkers({"api": Live(available())})
    result = await confirm(store, TENANT, (await store.products(TENANT))[0], checkers, secret=SECRET)
    assert result["public"] == {"status": "check_with_store"}


@pytest.mark.asyncio
async def test_service_confirm_needs_checker_and_hold_secret(monkeypatch):
    store = await rate_stub(await shop())
    service = Service(store)
    monkeypatch.delenv("RIG_LOCATE_HOLD_SECRET", raising=False)
    with pytest.raises(RigError) as raised:
        await service.locate_confirm(TENANT, "part-1")
    assert raised.value.status == 503
    service.locate_checker = Live(available())
    with pytest.raises(RigError) as raised:
        await service.locate_confirm(TENANT, "part-1")
    assert raised.value.status == 503
    monkeypatch.setenv("RIG_LOCATE_HOLD_SECRET", "s" * 40)
    assert (await service.locate_confirm(TENANT, "part-1"))["status"] == "available_to_order"


# 3. Holds: signed, short-lived, single-use and tenant scoped.

@pytest.mark.asyncio
async def test_hold_token_rejects_tamper_other_tenant_expiry_and_reuse():
    store = await rate_stub(await shop())
    result = await confirm(store, TENANT, (await store.products(TENANT))[0], Live(available()), secret=SECRET)
    token, now = result["public"]["hold"], datetime.now(timezone.utc)
    hold_id, expires, signature = token.split(".")
    for bad in (f"{hold_id}.{int(expires) + 600}.{signature}", f"{hold_id}.{expires}.{'0' * 64}", "x"):
        with pytest.raises(LocateRefused):
            read_token(SECRET, TENANT, bad, now)
    with pytest.raises(LocateRefused):
        read_token(SECRET, OTHER, token, now)
    with pytest.raises(LocateRefused, match="hold_expired"):
        read_token(SECRET, TENANT, token, now + timedelta(hours=1))
    assert await Holds(store).take(OTHER, hold_id, now) is None
    assert (await Holds(store).take(TENANT, hold_id, now))["product_id"] == "part-1"
    assert await Holds(store).take(TENANT, hold_id, now) is None
    stale = hold_token(SECRET, TENANT, hold_id, int(now.timestamp()) - 1)
    with pytest.raises(LocateRefused):
        read_token(SECRET, TENANT, stale, now)


# 4. Payments: test mode only, no live key.

class FakeProvider:
    """Test double. Never a concrete provider in the product path."""

    name = "test-double"

    def __init__(self, key="sk_test_double", test=True, status="captured"):
        self.key, self.test, self.status = key, test, status
        self.captured, self.refunded = [], []

    def keys(self):
        return [self.key]

    async def capture(self, *, amount, currency, token, reference, metadata):
        self.captured.append((amount, currency, reference))
        return payments.Charge("ch_test_1", self.status, amount, currency, self.test)

    async def refund(self, *, charge, reason):
        self.refunded.append(reason)
        return payments.Charge(charge.reference, "refunded", charge.amount, charge.currency, True)


@pytest.mark.asyncio
async def test_payments_refuse_without_test_mode_live_keys_and_unproven_test_charges():
    test_env = {"RIG_LOCATE_PAYMENTS_MODE": "test"}
    for env in ({}, {"RIG_LOCATE_PAYMENTS_MODE": "live"}, {"RIG_LOCATE_PAYMENTS_MODE": "TEST"}):
        with pytest.raises(payments.PaymentRefused, match="payments_mode"):
            payments.guard(FakeProvider(), env)
    with pytest.raises(payments.PaymentRefused, match="payments_not_configured"):
        payments.guard(None, test_env)
    for key in ("sk_live_x", "pk_live_x", "rk_live_x", "LIVE_secret", "key-live-1"):
        with pytest.raises(payments.PaymentRefused, match="live_key_refused"):
            payments.guard(FakeProvider(key), test_env)
    for name in ("STRIPE_SECRET_KEY", "PAYSTACK_SECRET_KEY"):
        with pytest.raises(payments.PaymentRefused, match="live_key_refused"):
            payments.guard(FakeProvider(), {**test_env, name: "sk_live_from_env"})
    with pytest.raises(payments.PaymentRefused) as raised:
        payments.guard(FakeProvider("sk_" + "live_" + "SECRETVALUE"), test_env)  # dummy, built so no key-shaped literal
    assert "SECRETVALUE" not in str(raised.value)
    with pytest.raises(payments.PaymentRefused, match="live_charge_refused"):
        await payments.capture(FakeProvider(test=False), amount="1", currency="ZAR", token="tok", reference="r",
                               metadata={}, env=test_env)
    charge = await payments.capture(FakeProvider(), amount="1", currency="ZAR", token="tok", reference="r",
                                    metadata={}, env=test_env)
    assert charge.test is True and charge.status == "captured"


# 5. Orders: sandbox only.

def test_order_placement_refuses_outside_sandbox():
    for value in ("", "live", "production", "SANDBOX"):
        with pytest.raises(DeliveryError, match="order_mode"):
            sandbox_orders({"RIG_LOCATE_ORDER_MODE": value})
    sandbox_orders({"RIG_LOCATE_ORDER_MODE": "sandbox"})


class SandboxOrders:
    """Test double for the retailer handoff and the order step (rigbox.fulfilment)."""

    def __init__(self, fail=False):
        self.sent, self.placed, self.fail = [], [], fail

    async def send(self, *, tenant_id, email, webhook, quote):
        self.sent.append((tenant_id, quote["id"]))

    async def place_located_order(self, *, tenant_id, quote_id, located, price=None, ship=None):
        sandbox_orders()
        if self.fail:
            raise DeliveryError("order_rejected")
        self.placed.append((tenant_id, quote_id, located["offer"]["sku"], located["live"]["price"]))
        return {"order": {"number": "S00001", "state": "placed"},
                "purchase_order": {"number": "P00001", "state": "draft"}}


async def checkout(monkeypatch, *, fail=False, provider=None):
    monkeypatch.setenv("RIG_LOCATE_HOLD_SECRET", "s" * 40)
    monkeypatch.setenv("RIG_LOCATE_ORDER_MODE", "sandbox")
    monkeypatch.setenv("RIG_LOCATE_PAYMENTS_MODE", "test")
    for name in ("STRIPE_SECRET_KEY", "PAYSTACK_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    store = await rate_stub(await shop())
    orders = SandboxOrders(fail)
    service = QuoteService(store, None, orders, MemoryQuotes(store))
    service.fulfilment = orders
    service.locate_checker = Live(available("45.00"))
    service.payments = provider or FakeProvider()
    held = await service.locate_confirm(TENANT, "part-1")
    body = {"product_id": "part-1", "hold": held["hold"], "payment_token": "tok_test_visa",
            "contact": {"name": "Shopper", "email": "shopper@example.com"}}
    return store, service, orders, held, body


@pytest.mark.asyncio
async def test_accept_pays_in_test_mode_then_orders_and_records_each_state(monkeypatch):
    store, service, orders, held, body = await checkout(monkeypatch)
    result = await service.locate_accept(TENANT, body)
    assert result["state"] == "ordered" and result["payment"]["test"] is True
    assert result["price"] == held["price"] == {"amount": "1125.00", "currency": "ZAR"}
    quote = next(q for q in store.quotes if q["id"] == result["request_id"])
    state = quote["payload"]["locate_state"]
    assert state["state"] == "ordered" and state["order"] == "S00001" and state["purchase_order"] == "P00001"
    assert state["payment"] == {"reference": "ch_test_1", "provider": "test-double", "test": True}
    assert quote["payload"]["product"]["price"] == held["price"]
    assert orders.placed == [(TENANT, result["request_id"], "RSR|POF00307", "45.00")]
    assert service.payments.captured == [(Decimal("1125.00"), "ZAR", f"rig:{TENANT}:{result['request_id']}")]
    # Single use: the same hold cannot pay twice.
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 410 and len(service.payments.captured) == 1


@pytest.mark.asyncio
async def test_accept_refunds_when_sandbox_order_fails(monkeypatch):
    store, service, orders, _, body = await checkout(monkeypatch, fail=True)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "order_failed_refunded" and service.payments.refunded == ["order_failed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    {"RIG_LOCATE_ORDER_MODE": "live"}, {"RIG_LOCATE_PAYMENTS_MODE": "live"},
    {"STRIPE_SECRET_KEY": "sk_live_present"}, {"RIG_LOCATE_HOLD_SECRET": "short"},
])
async def test_accept_refuses_before_taking_hold_or_payment(monkeypatch, change):
    store, service, orders, held, body = await checkout(monkeypatch)
    for name, value in change.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 503
    assert service.payments.captured == [] and orders.sent == [] and orders.placed == []
    hold_id = held["hold"].split(".")[0]
    assert store.supply_state[TENANT]["holds"][hold_id]["used_at"] is None


@pytest.mark.asyncio
async def test_accept_without_provider_refuses(monkeypatch):
    _, service, orders, _, body = await checkout(monkeypatch)
    service.payments = None
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 503 and orders.sent == []


@pytest.mark.asyncio
async def test_tenant_isolation_hold_offer_and_switch(monkeypatch):
    store, service, orders, held, body = await checkout(monkeypatch)
    # Another store cannot use this hold, even with Locate switched on and the same sku.
    product = (await store.products(TENANT))[0]
    await store.upsert_product(OTHER, dict(product))
    await store.save_rule(OTHER, {"freight": "5", "duty_percent": "0", "margin_percent": "20"})
    with pytest.raises(RigError) as raised:
        await service.locate_accept(OTHER, body)
    assert raised.value.code == "locate_disabled"
    await store.put_retailer(OTHER, "other", "o@example.com", None, "Other", locate_enabled=True)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(OTHER, body)
    assert raised.value.status == 422
    # The other store has no approved source or offer of its own.
    assert await service.locate_confirm(OTHER, "part-1") == {"status": "unavailable"}
    assert service.payments.captured == [] and orders.placed == []
    assert (await service.locate_accept(TENANT, body))["state"] == "ordered"


# 6. Product checkers: unknown unless explicitly configured and answered.

@pytest.mark.asyncio
async def test_product_checkers_fail_closed():
    source = {"id": "other-store", "provider": "tiger"}
    offer = {"sku": "x", "url": "https://other.example/p"}
    seen = []

    def answer(request):
        seen.append((str(request.url), dict(request.headers)))
        if request.url.path == "/rig/check-now":
            return httpx.Response(200, json={"status": "available", "price": "45.00", "currency": "USD",
                                             "checked_at": NOW.isoformat(), "gtin": "847313003072"})
        return httpx.Response(200, json={"status": "available"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as http:
        assert (await TigerChecker(http, {}).check(TENANT, source, offer)).status == "unknown"
        assert (await TigerChecker(http, {"RIG_TIGER_URL": "http://tiger", "RIG_TIGER_CHECK_KEY": "k"}).check(
            TENANT, source, {"sku": "x", "url": "http://other.example/p"})).status == "unknown"
        live = await TigerChecker(http, {"RIG_TIGER_URL": "http://tiger", "RIG_TIGER_CHECK_KEY": "k"}).check(
            TENANT, source, offer)
        assert live.status == "available" and live.price == Decimal("45.00") and live.gtin == "00847313003072"
        assert seen[-1][1]["x-rig-check-key"] == "k"
        api = {"id": "other-store", "provider": "api"}
        assert (await SourceApiChecker(http, {}).check(TENANT, api, offer)).status == "unknown"
        env = {"RIG_SUPPLY_API_URL_OTHER_STORE": "https://supplier.example/v1", "RIG_SUPPLY_API_KEY_OTHER_STORE": "k"}
        # Available without a stated price is unknown.
        assert (await SourceApiChecker(http, env).check(TENANT, api, offer)).status == "unknown"
        env["RIG_SUPPLY_API_URL_OTHER_STORE"] = "http://supplier.example/v1"
        assert (await SourceApiChecker(http, env).check(TENANT, api, offer)).status == "unknown"


# 7. Tiger check-now: a watched page, robots, explicit stock and price only.

class Watches:
    def __init__(self, url):
        self.url = url

    async def get_watch(self, tenant, url):
        return {"enabled": True} if url == self.url else None


@pytest.mark.asyncio
async def test_tiger_check_now_reads_only_explicit_stock_on_watched_pages():
    import asyncio
    sys.path.insert(0, str(ROOT / "agents" / "tiger"))
    from rig_watch import check_now
    url = "https://other.example/product/cam-pin/"

    async def robots(_):
        return "User-agent: *\nDisallow: /cart/"

    def page(availability, price="240.00"):
        async def render(_):
            return {"ok": True, "html": "<html></html>"}
        async def extract(html, _):
            return {"method": "jsonld", "items": [{"name": "Cam pin", "price": price, "currency": "USD",
                                                    "availability": availability, "gtin": "847313003072",
                                                    "method": "jsonld"}]}
        return render, extract

    render, extract = page("InStock")
    result = await check_now(Watches(url), TENANT, url, render, extract, robots)
    assert result["status"] == "available" and result["price"] == "240.00" and result["currency"] == "USD"
    render, extract = page("OutOfStock")
    assert (await check_now(Watches(url), TENANT, url, render, extract, robots))["status"] == "unavailable"
    render, extract = page("SomethingElse")
    assert (await check_now(Watches(url), TENANT, url, render, extract, robots))["status"] == "unknown"
    render, extract = page("InStock")
    assert (await check_now(Watches("https://elsewhere.example/"), TENANT, url, render, extract, robots)) == {
        "status": "unknown", "reason": "not_watched", "url": url}

    async def disallow(_):
        return "User-agent: *\nDisallow: /product/"
    assert (await check_now(Watches(url), TENANT, url, render, extract, disallow))["reason"] == "robots"

    async def challenge(_):
        return {"ok": True, "challenge": True, "html": "<html>Just a moment</html>"}
    assert (await check_now(Watches(url), TENANT, url, challenge, extract, robots))["reason"] == "blocked"

    async def slow(_):
        await asyncio.sleep(1)
    assert (await check_now(Watches(url), TENANT, url, slow, extract, robots, budget=0.05))["reason"] == "timeout"


def test_tiger_check_now_uses_the_45_second_budget():
    sys.path.insert(0, str(ROOT / "agents" / "tiger"))
    import rig_watch
    from rigbox import locate_live
    assert rig_watch.CHECK_NOW_BUDGET_S == locate_live.TIGER_BUDGET_SECONDS == 45
    source = (ROOT / "agents" / "tiger" / "app.py").read_text()
    assert '"request_timeout_ms": 45000' in source and '@app.post("/rig/check-now")' in source


# 8. Real Postgres: default false, holds tenant scoped and single use.

@pytest.mark.asyncio
async def test_real_postgres_switch_default_and_hold_isolation():
    import asyncpg
    from uuid import uuid4
    from test_rig_postgres import _admin_url, _database_url, _create_database, _drop_database
    from rigbox.store import PgStore
    admin = _admin_url()
    name = "rig_locate_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            store = PgStore(pool)
            await store.apply_schema()
            await store.apply_schema()
            await store.put_retailer(TENANT, "shop", None, None, "Shop")
            assert (await store.retailer(TENANT))["locate_enabled"] is False
            assert await enabled(store, TENANT) is False
            await store.put_retailer(TENANT, "shop", None, None, "Shop", locate_enabled=True)
            await store.put_retailer(TENANT, "shop", "a@example.com", None, "Shop")
            assert await enabled(store, TENANT) is True
            default = await pool.fetchval("""SELECT column_default FROM information_schema.columns
                WHERE table_schema='agent_rig' AND table_name='retailers' AND column_name='locate_enabled'""")
            assert default == "false"
            now = datetime.now(timezone.utc)
            holds = Holds(store)
            await holds.save(TENANT, "h_" + "a" * 32, "part-1", {"status": "available_to_order"},
                             {"offer": {"sku": "x"}}, now + timedelta(minutes=5))
            assert await holds.take(OTHER, "h_" + "a" * 32, now) is None
            assert (await holds.take(TENANT, "h_" + "a" * 32, now))["private"] == {"offer": {"sku": "x"}}
            assert await holds.take(TENANT, "h_" + "a" * 32, now) is None
            await holds.save(TENANT, "h_" + "b" * 32, "part-1", {}, {}, now - timedelta(seconds=1))
            assert await holds.take(TENANT, "h_" + "b" * 32, now) is None
            quote_id = "req_locate_state"
            await store.add_quote(TENANT, quote_id, {"kind": "product"}, {})
            await store.locate_state(OTHER, quote_id, {"state": "paid"})
            await store.locate_state(TENANT, quote_id, {"state": "ordered"})
            payload = json.loads(await pool.fetchval("SELECT payload FROM agent_rig.quotes WHERE id=$1", quote_id))
            assert payload["locate_state"] == {"state": "ordered"}
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


# Tiger page observations feed the same offer table, definite answers only.

@pytest.mark.asyncio
async def test_page_observation_records_only_definite_priced_reads():
    store = await rate_stub(await shop())
    store.supply_state[TENANT]["offers"] = []
    supply = SupplyStore(store)
    page = dict(url="https://other.example/product/cam-pin/", sku="RSR|POF00307", brand="POF-USA", mpn=None, region="us")
    for status in ("unknown", "blocked"):
        result = LiveResult(status, None, None, NOW, None, "double")
        assert (await supply.observe_page(TENANT, "other-store", live=result, **page))["imported"] == 0
    assert store.supply_state[TENANT]["offers"] == []
    product = (await store.products(TENANT))[0]
    assert (await catalogue_status(store, product)) == "unavailable"
    await supply.observe_page(TENANT, "other-store", live=available("240.00", code="847313003072"), **page)
    [offer] = store.supply_state[TENANT]["offers"]
    assert offer["quantity"] == 1 and offer["status"] == "available" and offer["region"] == "US"
    assert offer["eta"] is None and offer["cost"] == Decimal("240.00")
    assert (await catalogue_status(store, product)) == "available_to_order"
    await supply.observe_page(TENANT, "other-store", live=LiveResult(
        "unavailable", Decimal("240.00"), "USD", datetime.now(timezone.utc), "847313003072", "double"), **page)
    assert (await catalogue_status(store, product)) == "unavailable"
    with pytest.raises(ValueError):
        await supply.observe_page(TENANT, "other-store", live=available(), **{**page, "url": "http://other.example/x"})
    await supply.source(TENANT, dict(id="feed", approved=True, max_offer_age_seconds=60, provider="api"))
    with pytest.raises(ValueError):
        await supply.observe_page(TENANT, "feed", live=available(), **page)
    with pytest.raises(ValueError):
        await supply.observe_page(OTHER, "other-store", live=available(), **page)


async def catalogue_status(store, product):
    from rigbox.locate import locate
    return (await locate(store, TENANT, product))["public"]["status"]
