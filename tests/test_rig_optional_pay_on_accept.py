"""Optional pay on Accept: provider-agnostic PaymentAdapter, test mode only.

create_intent on Accept, capture, refund, and HMAC-SHA256 webhook verification,
all behind payments.guard (RIG_LOCATE_PAYMENTS_MODE=test, no live-looking key).
The built-in TestAdapter runs Accept -> pay -> auto-order -> refund-on-failure
end to end. No provider SDK, no keys, no live mode.
"""
import asyncio
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "tests"))
from rigbox import payments
from rigbox.api import mount
from rigbox.quotes.privacy import shopper_body
from rigbox.quotes.senders import DeliveryError
from rigbox.service import RigError
from test_rig_locate_checkout import TENANT
from test_rig_optional_auto_order import auto_shop, no_network_mail  # noqa: F401  (autouse SMTP refusal)

TEST_ENV = {"RIG_LOCATE_PAYMENTS_MODE": "test"}


async def paid_shop(monkeypatch, outbox, adapter=None, **options):
    store, service, orders, held, body = await auto_shop(monkeypatch, outbox, **options)
    service.payments = adapter or payments.TestAdapter()
    return store, service, orders, held, body


def kinds(adapter):
    return [kind for kind, _key in adapter.calls]


# 1. Webhook signature verification.

def test_webhook_signature_accepts_only_a_fresh_exact_hmac():
    adapter = payments.TestAdapter()
    body, header = adapter.event("evt_1", "charge.refunded", f"rig:{TENANT}:req_{'a' * 32}")
    assert payments.verify_webhook(adapter, body, header, env=TEST_ENV)["id"] == "evt_1"
    stamp = int(header.split(",")[0][2:])
    rotated = f"t={stamp},v1={'0' * 64},v1={header.split('v1=')[1]}"  # any valid v1 passes (secret rotation)
    assert payments.verify_webhook(adapter, body, rotated, env=TEST_ENV)["type"] == "charge.refunded"
    other = payments.TestAdapter()
    bad = [
        (body.replace(b"evt_1", b"evt_2"), header, "webhook_signature"),          # tampered body
        (body, other.event("evt_1", "charge.refunded", "x")[1], "webhook_signature"),  # wrong secret
        (body, "", "webhook_signature"),
        (body, "v1=" + header.split("v1=")[1], "webhook_signature"),             # no timestamp
        (body, f"t={stamp}", "webhook_signature"),                               # no signature
        (body, header.replace(f"t={stamp}", f"t={stamp + 1}"), "webhook_signature"),
        (b"x" * (payments.WEBHOOK_MAX_BYTES + 1), header, "webhook_signature"),
    ]
    for raw, sig, code in bad:
        with pytest.raises(payments.PaymentRefused, match=code):
            payments.verify_webhook(adapter, raw, sig, env=TEST_ENV)
    old_body, old = adapter.event("evt_old", "charge.refunded", "x", timestamp=int(time.time()) - 301)
    future_body, future = adapter.event("evt_new", "charge.refunded", "x", timestamp=int(time.time()) + 301)
    for raw, sig in ((old_body, old), (future_body, future)):
        with pytest.raises(payments.PaymentRefused, match="webhook_stale"):
            payments.verify_webhook(adapter, raw, sig, env=TEST_ENV)
    unsigned = b'{"type":"charge.refunded","data":{}}'
    with pytest.raises(payments.PaymentRefused, match="webhook_payload"):
        payments.verify_webhook(adapter, unsigned, payments.sign(adapter.webhook_secret(), unsigned, int(time.time())),
                                env=TEST_ENV)


def test_webhook_verification_sits_behind_the_test_mode_guard():
    adapter = payments.TestAdapter()
    body, header = adapter.event("evt_1", "charge.refunded", "x")
    for env in ({}, {"RIG_LOCATE_PAYMENTS_MODE": "live"}):
        with pytest.raises(payments.PaymentRefused, match="payments_mode"):
            payments.verify_webhook(adapter, body, header, env=env)
    with pytest.raises(payments.PaymentRefused, match="payments_not_configured"):
        payments.verify_webhook(None, body, header, env=TEST_ENV)
    live = payments.TestAdapter(secret="whsec_live_example")
    with pytest.raises(payments.PaymentRefused, match="live_key_refused"):
        payments.verify_webhook(live, *live.event("evt_1", "charge.refunded", "x"), env=TEST_ENV)
    with pytest.raises(payments.PaymentRefused, match="live_key_refused"):
        payments.verify_webhook(adapter, body, header, env={**TEST_ENV, "STRIPE_SECRET_KEY": "sk_live_example"})


# 2. Adapter idempotency and live refusal.

@pytest.mark.asyncio
async def test_test_adapter_moves_money_at_most_once_per_key():
    adapter = payments.TestAdapter()
    first = await payments.create_intent(adapter, amount="1125.00", currency="ZAR", token="tok_test_visa",
                                         reference="rig:t:q1", metadata={}, env=TEST_ENV)
    again = await payments.create_intent(adapter, amount="1125.00", currency="ZAR", token="tok_test_visa",
                                         reference="rig:t:q1", metadata={}, env=TEST_ENV)
    assert first == again and first.status == "requires_capture" and first.amount == Decimal("1125.00")
    charge = await payments.capture_intent(adapter, first, reference="rig:t:q1", env=TEST_ENV)
    assert charge == await payments.capture_intent(adapter, first, reference="rig:t:q1", env=TEST_ENV) and charge.status == "captured"
    refund = await payments.refund(adapter, charge, "order_failed", env=TEST_ENV)
    assert refund == await payments.refund(adapter, charge, "order_failed", env=TEST_ENV)
    assert kinds(adapter) == ["create_intent", "capture", "refund"]
    assert adapter.calls[0][1] == "rig:t:q1:intent" and adapter.calls[1][1] == "rig:t:q1:capture"


class LiveAdapter(payments.TestAdapter):
    """Claims success but cannot prove test mode."""

    async def create_intent(self, **kwargs):
        intent = await super().create_intent(**kwargs)
        return payments.Intent(intent.reference, intent.status, intent.amount, intent.currency, False)


@pytest.mark.asyncio
async def test_live_mode_is_refused_before_any_adapter_call(monkeypatch, tmp_path):
    for name, value in (("RIG_LOCATE_PAYMENTS_MODE", "live"), ("STRIPE_SECRET_KEY", "sk_live_example")):
        store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
        monkeypatch.setenv(name, value)
        with pytest.raises(RigError) as raised:
            await service.locate_accept(TENANT, body)
        assert raised.value.status == 503 and service.payments.calls == [] and orders.placed == []
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=LiveAdapter())
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 402 and kinds(service.payments) == ["create_intent"] and orders.placed == []
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "payment_refused"


def test_the_test_adapter_is_not_wired_into_the_app_and_there_is_no_live_mode():
    sources = [path.read_text() for path in (ROOT / "agents" / "rig").rglob("*.py") if path.name != "payments.py"]
    assert not any("TestAdapter" in text for text in sources)
    code = (ROOT / "agents" / "rig" / "rigbox" / "payments.py").read_text()
    for word in ("import stripe", "import paystack", "httpx", "requests", 'MODE_ENV, "") == "live"', "live_mode"):
        assert word not in code, word


# 3. Accept -> pay -> auto-order -> refund on failure, end to end.

@pytest.mark.asyncio
async def test_accept_pays_then_auto_orders_once(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    result = await service.locate_accept(TENANT, body)
    state = store.quotes[-1]["payload"]["locate_state"]
    assert result["state"] == "ordered" and result["payment"]["test"] is True
    assert result["payment"]["reference"].startswith("ch_test_")
    assert state["state"] == "supplier_ordered" and state["payment"]["provider"] == "test-adapter"
    assert kinds(service.payments) == ["create_intent", "capture"] and len(list(tmp_path.iterdir())) == 1
    charged = service.payments.charges[f"rig:{TENANT}:{result['request_id']}:capture"]
    assert charged.amount == Decimal(result["price"]["amount"]) and charged.currency == result["price"]["currency"]
    text = json.dumps(shopper_body(result))
    for marker in ("pi_test_", "test-adapter", "other.example", "Other Store", "orders@", "45.00"):
        assert marker not in text
    with pytest.raises(RigError) as raised:  # replayed Accept: hold is single use, nothing charged again
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 410 and kinds(service.payments) == ["create_intent", "capture"]
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
async def test_supplier_order_failure_refunds_the_captured_payment(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, fail_supplier=True)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    state = store.quotes[-1]["payload"]["locate_state"]
    assert raised.value.status == 502 and state["state"] == "supplier_order_failed_refunded"
    assert kinds(service.payments) == ["create_intent", "capture", "refund"] and list(tmp_path.iterdir()) == []
    assert list(service.payments.refunds.values())[0].status == "refunded"


@pytest.mark.asyncio
async def test_order_failure_refunds_the_captured_payment(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)

    async def fail(**kwargs):
        raise DeliveryError("odoo_rejected")
    orders.place_located_order = fail
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "order_failed_refunded"
    assert kinds(service.payments) == ["create_intent", "capture", "refund"] and orders.supplied == []


@pytest.mark.asyncio
@pytest.mark.parametrize("token,calls", [("tok_decline", ["create_intent"]),
                                         ("tok_capture_fails", ["create_intent", "capture"])])
async def test_declined_or_failed_capture_places_no_order(monkeypatch, tmp_path, token, calls):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, {**body, "payment_token": token})
    assert raised.value.status == 402 and kinds(service.payments) == calls
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "payment_failed"
    assert orders.placed == [] and list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_one_shot_providers_still_work(monkeypatch, tmp_path):
    store, service, orders, _, body = await auto_shop(monkeypatch, tmp_path)  # #463 FakeProvider, no intents
    assert not payments.intents(service.payments)
    assert (await service.locate_accept(TENANT, body))["state"] == "ordered"
    assert len(service.payments.captured) == 1


# 4. Webhook route: signed events recorded once on their quote.

def test_webhook_route_records_signed_events_once(monkeypatch, tmp_path):
    store, service, orders, _, body = asyncio.run(paid_shop(monkeypatch, tmp_path))
    quote_id = asyncio.run(service.locate_accept(TENANT, body))["request_id"]
    adapter = service.payments
    app = FastAPI()
    app.state.rig = service
    mount(app)
    route = "/v1/rig/locate/payments/webhook"
    raw, signature = adapter.event("evt_refund_1", "charge.refunded", f"rig:{TENANT}:{quote_id}")
    headers = {payments.SIGNATURE_HEADER: signature, "content-type": "application/json"}
    with TestClient(app) as client:
        first = client.post(route, content=raw, headers=headers)
        again = client.post(route, content=raw, headers=headers)
        forged = client.post(route, content=raw.replace(b"refunded", b"captured"), headers=headers)
        unsigned = client.post(route, content=raw)
        unknown = client.post(route, content=adapter.event("evt_2", "charge.refunded", "rig:nope")[0],
                              headers={payments.SIGNATURE_HEADER: adapter.event("evt_2", "charge.refunded",
                                                                                 "rig:nope")[1]})
        monkeypatch.setenv("RIG_LOCATE_PAYMENTS_MODE", "live")
        refused = client.post(route, content=raw, headers=headers)
    assert first.status_code == 200 and first.json() == {"received": True, "recorded": True}
    assert again.json() == {"received": True, "recorded": False}
    assert forged.status_code == 400 and unsigned.status_code == 400 and refused.status_code == 503
    assert unknown.json() == {"received": True, "recorded": False}
    events = store.quotes[-1]["payload"]["payment_events"]
    assert [event["id"] for event in events] == ["evt_refund_1"] and events[0]["type"] == "charge.refunded"
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "supplier_ordered"  # audit only


@pytest.mark.asyncio
async def test_real_postgres_payment_events_are_deduplicated_atomically():
    import asyncpg
    from uuid import uuid4
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    from rigbox.store import PgStore
    from chassis.tenant_db import tenant_scope
    admin = _admin_url()
    name = "rig_pay_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            store = PgStore(pool)
            await store.apply_schema()
            quote_id = "req_" + uuid4().hex
            with tenant_scope(TENANT):
                await store.add_quote(TENANT, quote_id, {"kind": "product"}, {"name": "T"})
                event = {"id": "evt_1", "type": "charge.refunded", "received_at": "2026-10-31T00:00:00+00:00"}
                results = await asyncio.gather(*(store.payment_event(TENANT, quote_id, event) for _ in range(5)))
                second = await store.payment_event(TENANT, quote_id, {**event, "id": "evt_2"})
                other = await store.payment_event(str(uuid4()), quote_id, {**event, "id": "evt_3"})
                saved = await pool.fetchval("SELECT payload->'payment_events' FROM agent_rig.quotes WHERE id = $1",
                                            quote_id)
            assert sorted(results) == [False, False, False, False, True] and second is True and other is False
            assert [item["id"] for item in json.loads(saved)] == ["evt_1", "evt_2"]
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)
