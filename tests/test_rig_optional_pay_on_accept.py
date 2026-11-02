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
    refund = await payments.refund(adapter, charge, "order_failed", reference="rig:t:q1", env=TEST_ENV)
    assert refund == await payments.refund(adapter, charge, "order_failed", reference="rig:t:q1", env=TEST_ENV)
    assert adapter.calls[-1] == ("refund", "rig:t:q1:refund")
    assert kinds(adapter) == ["create_intent", "capture", "refund"]
    assert adapter.calls[0][1] == "rig:t:q1:intent" and adapter.calls[1][1] == "rig:t:q1:capture"


class LiveAdapter(payments.TestAdapter):
    """Claims success but cannot prove test mode."""

    async def create_intent(self, **kwargs):
        intent = await super().create_intent(**kwargs)
        return payments.Intent(intent.reference, intent.status, intent.amount, intent.currency, False)

    async def find_intent(self, **kwargs):
        intent = await super().find_intent(**kwargs)
        return intent and payments.Intent(intent.reference, intent.status, intent.amount, intent.currency, False)


@pytest.mark.asyncio
async def test_live_mode_is_refused_before_any_adapter_call(monkeypatch, tmp_path):
    for name, value in (("RIG_LOCATE_PAYMENTS_MODE", "live"), ("STRIPE_SECRET_KEY", "sk_live_example")):
        store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
        monkeypatch.setenv(name, value)
        with pytest.raises(RigError) as raised:
            await service.locate_accept(TENANT, body)
        assert raised.value.status == 503 and service.payments.calls == [] and store.locate_orders == {}
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=LiveAdapter())
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    # The adapter made an intent it can't prove is test-mode: never "not taken".
    # The quote stays payment_pending; reconcile never voids or refunds an
    # unproven intent, so it stays open (reconcile_error) for a person.
    assert raised.value.status == 502 and kinds(service.payments) == ["create_intent"] and store.locate_orders == {}
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "payment_pending" and state["note"] == "intent_unconfirmed"
    assert state["payment"]["intent_key"].endswith(":intent") and "intent" not in state["payment"]
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [] and kinds(service.payments) == ["create_intent", "find_intent"]
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "payment_pending" and state["reconcile_error"] is True


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
    saved = await store.locate_order(TENANT, result["request_id"])  # Rig's own order + PO, no ERP
    assert saved["order"]["state"] == "placed" and saved["order"]["price"] == result["price"]["amount"]
    assert saved["purchase_order"]["state"] == "sent"
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
    saved = await store.locate_order(TENANT, store.quotes[-1]["id"])
    assert (saved["order"]["state"], saved["purchase_order"]["state"]) == ("cancelled", "cancelled")


@pytest.mark.asyncio
async def test_order_failure_refunds_the_captured_payment(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)

    async def fail(**kwargs):
        raise DeliveryError("order_unavailable")
    service.fulfilment.place_located_order = fail
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "order_failed_refunded"
    assert kinds(service.payments) == ["create_intent", "capture", "refund"] and store.locate_orders == {}
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("token,calls", [("tok_decline", ["create_intent"]),
                                         ("tok_capture_fails", ["create_intent", "capture", "cancel_intent"])])
async def test_declined_or_failed_capture_places_no_order(monkeypatch, tmp_path, token, calls):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, {**body, "payment_token": token})
    assert raised.value.status == 402 and kinds(service.payments) == calls
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "payment_failed"
    assert store.locate_orders == {} and list(tmp_path.iterdir()) == []
    if token == "tok_capture_fails":  # the authorization is voided, not left to expire
        assert store.quotes[-1]["payload"]["locate_state"]["cancel"] == {"status": "canceled"}
        assert list(service.payments.canceled.values())[0].status == "canceled"


class CancelFailsOnce(payments.TestAdapter):
    """The cancel call after a failed capture is lost once (provider outage)."""

    def __init__(self) -> None:
        super().__init__()
        self.cancel_failures = 1

    async def cancel_intent(self, *, intent, idempotency_key):
        if self.cancel_failures:
            self.cancel_failures -= 1
            raise ConnectionError("cancel response lost")
        return await super().cancel_intent(intent=intent, idempotency_key=idempotency_key)


def later(minutes=20):
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


@pytest.mark.asyncio
async def test_a_lost_capture_response_is_resolved_by_the_cancel_call(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    result = await service.locate_accept(TENANT, {**body, "payment_token": "tok_capture_lost"})
    # cancel reports "captured": the shopper was charged, so the order goes ahead (once).
    assert result["state"] == "ordered"
    assert kinds(service.payments) == ["create_intent", "capture", "cancel_intent"]
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "supplier_ordered"
    assert service.payments.refunds == {} and len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
async def test_capture_failure_with_a_lost_cancel_is_settled_by_reconcile(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=CancelFailsOnce())
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, {**body, "payment_token": "tok_capture_fails"})
    state = store.quotes[-1]["payload"]["locate_state"]
    assert raised.value.status == 502 and state["state"] == "payment_pending"
    assert state["note"] == "capture_unconfirmed" and store.locate_orders == {}
    assert (await service.reconcile_payments(TENANT))["reconciled"] == []  # too recent: maybe in flight
    fixed = await service.reconcile_payments(TENANT, now=later())
    assert fixed == {"checked": 1, "reconciled": [{"quote_id": store.quotes[-1]["id"], "from": "payment_pending",
                                                   "to": "payment_failed"}], "needs_review": []}
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["reconciled"] is True and state["cancel"] == {"status": "canceled"}
    assert service.payments.refunds == {} and store.locate_orders == {}
    assert await service.reconcile_payments(TENANT, now=later()) == {"checked": 0, "reconciled": [], "needs_review": []}


@pytest.mark.asyncio
async def test_reconcile_refunds_a_paid_quote_with_no_order_once(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)

    async def crash(**kwargs):
        raise RuntimeError("worker killed after capture")
    service.fulfilment.place_located_order = crash
    with pytest.raises(RuntimeError):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "paid"
    assert (await service.reconcile_payments(TENANT, now=later(5)))["reconciled"] == []
    both = await asyncio.gather(service.reconcile_payments(TENANT, now=later()),
                                service.reconcile_payments(TENANT, now=later()))
    assert sum(len(item["reconciled"]) for item in both) == 1  # claimed once
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "order_failed_refunded" and state["refund"] == {"status": "refunded"}
    assert kinds(service.payments) == ["create_intent", "capture", "refund"]
    assert [item["quote_id"] for result in both for item in result["reconciled"]] == [quote_id]
    assert store.locate_orders == {}


@pytest.mark.asyncio
async def test_reconcile_records_an_order_placed_before_the_crash_and_never_refunds_it(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    result = await service.locate_accept(TENANT, body)
    row = store.quotes[-1]
    row["payload"]["locate_state"] = {**row["payload"]["locate_state"], "state": "paid"}  # crash before "ordered"
    fixed = await service.reconcile_payments(TENANT, now=later())
    assert fixed["reconciled"] == [{"quote_id": result["request_id"], "from": "paid", "to": "ordered"}]
    state = row["payload"]["locate_state"]
    assert state["order"].startswith("RIG-") and state["purchase_order"].startswith("PO-")
    assert "refund" not in kinds(service.payments)


@pytest.mark.asyncio
async def test_reconcile_refunds_a_pending_intent_that_was_captured_before_the_crash(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    original = service.payments.capture_intent

    async def capture_then_crash(**kwargs):
        await original(**kwargs)
        raise SystemExit("worker killed after capture")  # not caught by Accept
    service.payments.capture_intent = capture_then_crash
    with pytest.raises(SystemExit):
        await service.locate_accept(TENANT, body)
    service.payments.capture_intent = original
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "payment_pending"
    fixed = await service.reconcile_payments(TENANT, now=later())
    assert fixed["reconciled"][0]["to"] == "order_failed_refunded"
    assert kinds(service.payments) == ["create_intent", "capture", "cancel_intent", "refund"]
    assert list(service.payments.refunds.values())[0].status == "refunded" and store.locate_orders == {}


class RefusesCapture(payments.TestAdapter):
    """Capture is refused before any money moves (probe D)."""

    async def capture_intent(self, *, intent, idempotency_key):
        self.calls.append(("capture", idempotency_key))
        raise payments.PaymentRefused("live_charge_refused")


class UnprovenCapture(payments.TestAdapter):
    """Capture takes the money but the charge can't be proven test-mode (probe K)."""

    async def capture_intent(self, **kwargs):
        charge = await super().capture_intent(**kwargs)
        return payments.Charge(charge.reference, charge.status, charge.amount, charge.currency, False)


@pytest.mark.asyncio
async def test_a_refused_capture_is_voided(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=RefusesCapture())
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 402
    assert kinds(service.payments) == ["create_intent", "capture", "cancel_intent"] and store.locate_orders == {}
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "payment_failed" and state["cancel"] == {"status": "canceled"}


@pytest.mark.asyncio
async def test_a_refusal_after_capture_is_refunded_by_reconcile(monkeypatch, tmp_path):
    """Money was captured but the charge can't be proven test-mode: the shopper
    is never told "not taken", the quote stays payment_pending, and the
    reconciler refunds that charge, once."""
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=UnprovenCapture())
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502 and "refunded" in raised.value.message
    assert kinds(service.payments) == ["create_intent", "capture", "cancel_intent"] and store.locate_orders == {}
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "payment_pending" and state["note"] == "capture_unproven"
    assert len(service.payments.charges) == 1 and service.payments.refunds == {}
    quote_id = store.quotes[-1]["id"]
    assert (await service.reconcile_payments(TENANT))["reconciled"] == []  # still in flight
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [{"quote_id": quote_id, "from": "payment_pending", "to": "order_failed_refunded"}]
    assert kinds(service.payments) == ["create_intent", "capture", "cancel_intent", "refund"]
    assert service.payments.calls[-1] == ("refund", f"rig:{TENANT}:{quote_id}:refund")
    assert list(service.payments.refunds.values())[0].status == "refunded" and store.locate_orders == {}
    assert (await service.reconcile_payments(TENANT, now=later(60)))["reconciled"] == []
    assert kinds(service.payments).count("refund") == 1


@pytest.mark.asyncio
async def test_a_lost_create_intent_response_is_voided_by_reconcile(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    body["payment_token"] = "tok_intent_lost"
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502 and store.locate_orders == {}
    state = store.quotes[-1]["payload"]["locate_state"]
    quote_id = store.quotes[-1]["id"]
    assert state["state"] == "payment_pending" and state["note"] == "intent_unconfirmed"
    assert state["payment"]["intent_key"] == f"rig:{TENANT}:{quote_id}:intent" and "intent" not in state["payment"]
    assert len(service.payments.intents) == 1  # authorized, response lost
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [{"quote_id": quote_id, "from": "payment_pending", "to": "payment_failed"}]
    assert kinds(service.payments) == ["create_intent", "find_intent", "cancel_intent"]
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["cancel"] == {"status": "canceled"} and state["payment"]["intent"].startswith("pi_test_")
    assert service.payments.charges == {} and service.payments.refunds == {}


@pytest.mark.asyncio
async def test_a_create_intent_that_never_reached_the_provider_settles_as_failed(monkeypatch, tmp_path):
    class Down(payments.TestAdapter):
        async def create_intent(self, **kwargs):
            raise ConnectionError("provider unreachable")
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=Down())
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "payment_pending"
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert [item["to"] for item in result["reconciled"]] == ["payment_failed"]
    assert store.quotes[-1]["payload"]["locate_state"]["note"] == "no_intent"
    assert kinds(service.payments) == ["find_intent"]


@pytest.mark.asyncio
async def test_a_crash_between_ordered_and_the_supplier_send_is_cancelled_and_refunded(monkeypatch, tmp_path):
    from rigbox.fulfilment import RigOrders

    class Crash(Exception):
        """Rig stops after recording "ordered", before the PO is sent."""

    async def killed(self, **kwargs):
        raise Crash()
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setattr(RigOrders, "send_supplier_order", killed)
    with pytest.raises(Crash):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "ordered"
    assert store.locate_orders[(TENANT, quote_id)]["purchase_order"]["state"] == "draft"
    assert list(tmp_path.iterdir()) == []
    assert (await service.reconcile_payments(TENANT))["reconciled"] == []  # too recent
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [{"quote_id": quote_id, "from": "ordered", "to": "supplier_order_failed_refunded"}]
    row = store.locate_orders[(TENANT, quote_id)]
    assert row["order"]["state"] == "cancelled" and row["purchase_order"]["state"] == "cancelled"
    assert kinds(service.payments) == ["create_intent", "capture", "refund"]
    assert service.payments.calls[-1] == ("refund", f"rig:{TENANT}:{quote_id}:refund")
    assert list(tmp_path.iterdir()) == []  # reconcile never sends
    assert (await service.reconcile_payments(TENANT, now=later(60)))["reconciled"] == []
    assert kinds(service.payments).count("refund") == 1


@pytest.mark.asyncio
async def test_a_stranded_po_the_supplier_has_is_not_refunded(monkeypatch, tmp_path):
    """The PO file was written but Rig stopped before recording anything after
    "ordered": reconcile marks the PO sent, moves the quote to supplier_ordered
    and never refunds."""
    from rigbox import supplier_orders
    from rigbox.fulfilment import RigOrders
    real = RigOrders.send_supplier_order

    class Crash(Exception):
        pass

    async def written_then_killed(self, **kwargs):
        await real(self, **kwargs)
        store.locate_orders[(TENANT, kwargs["quote_id"])]["purchase_order"].update(state="draft", sent=None)
        raise Crash()
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setattr(RigOrders, "send_supplier_order", written_then_killed)
    with pytest.raises(Crash):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    result = await service.reconcile_payments(TENANT, now=later(30))
    # RigOrders.reconcile finds the outbox file and marks the PO sent; nothing is stranded.
    assert result["reconciled"] == [{"quote_id": quote_id, "from": "ordered", "to": "supplier_ordered"}]
    assert "refund" not in kinds(service.payments)
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "supplier_ordered" and state["purchase_order_state"] == "sent"
    assert store.locate_orders[(TENANT, quote_id)]["purchase_order"]["state"] == "sent"
    assert len(list(tmp_path.iterdir())) == 1 and supplier_orders.sent_record(tenant_id=TENANT, quote_id=quote_id)


@pytest.mark.asyncio
async def test_an_unconfirmed_supplier_order_is_never_refunded_on_a_guess(monkeypatch, tmp_path):
    from rigbox import supplier_orders
    from rigbox.fulfilment import RigOrders

    async def send_fails(self, **kwargs):
        raise DeliveryError("order_unavailable")

    def unreadable(**kwargs):
        raise DeliveryError("outbox_unavailable")
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setattr(RigOrders, "send_supplier_order", send_fails)
    monkeypatch.setattr(supplier_orders, "sent_record", unreadable)
    assert (await service.locate_accept(TENANT, body))["state"] == "ordered"
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "supplier_order_unconfirmed"
    quote_id = store.quotes[-1]["id"]
    for minutes in (30, 60):
        result = await service.reconcile_payments(TENANT, now=later(minutes))
        # Reported for a person every run; never cancelled or refunded.
        assert result["reconciled"] == [] and result["needs_review"] == [quote_id]
    assert "refund" not in kinds(service.payments)
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "supplier_order_unconfirmed"
    assert state["reconcile_error"] is True and state["needs_review"] is True
    assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "placed"


class RefundFailsOnce(payments.TestAdapter):
    """The first refund call fails before reaching the provider."""

    def __init__(self) -> None:
        super().__init__()
        self.refund_failures = 1

    async def refund(self, **kwargs):
        if self.refund_failures:
            self.refund_failures -= 1
            raise ConnectionError("provider unreachable")
        return await super().refund(**kwargs)


class RefundResponseLost(payments.TestAdapter):
    """The first refund goes through at the provider but its response is lost."""

    def __init__(self) -> None:
        super().__init__()
        self.lost = 1

    async def refund(self, **kwargs):
        refunded = await super().refund(**kwargs)
        if self.lost:
            self.lost -= 1
            raise ConnectionError("refund response lost")
        return refunded


async def failing_accept(monkeypatch, tmp_path, adapter, where):
    from rigbox.fulfilment import RigOrders
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=adapter)
    if where == "supplier":
        async def send_refused(self, **kwargs):
            raise DeliveryError("order_mode")  # refused before writing: nothing was sent
        monkeypatch.setattr(RigOrders, "send_supplier_order", send_refused)
    else:
        async def place_fails(**kwargs):
            raise DeliveryError("order_unavailable")
        service.fulfilment.place_located_order = place_fails
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    return store, service, raised.value


@pytest.mark.asyncio
@pytest.mark.parametrize("where, reason, final", [
    ("supplier", "supplier_order_failed", "supplier_order_failed_refunded"),
    ("order", "order_failed", "order_failed_refunded")])
async def test_a_refund_that_fails_at_accept_is_retried_by_reconcile(monkeypatch, tmp_path, where, reason, final):
    store, service, error = await failing_accept(monkeypatch, tmp_path, RefundFailsOnce(), where)
    assert error.status == 502 and error.message == "The order could not be placed. The payment will be refunded."
    quote_id = store.quotes[-1]["id"]
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "refund_due" and state["refund_reason"] == reason
    assert service.payments.refunds == {}
    assert (await service.reconcile_payments(TENANT))["reconciled"] == []  # too recent: Accept may be in flight
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [{"quote_id": quote_id, "from": "refund_due", "to": final}]
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["refund"] == {"status": "refunded"} and state["reconciled"] is True
    assert service.payments.calls[-1] == ("refund", f"rig:{TENANT}:{quote_id}:refund")
    assert service.payments.refund_causes == [reason]
    assert "find_intent" not in kinds(service.payments)  # never the paid branch's order lookup path
    if where == "supplier":
        assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "cancelled"
    else:
        assert store.locate_orders == {}
    assert (await service.reconcile_payments(TENANT, now=later(60)))["reconciled"] == []
    assert kinds(service.payments).count("refund") == 1


@pytest.mark.asyncio
async def test_a_refund_whose_response_was_lost_is_replayed_with_one_adapter_call(monkeypatch, tmp_path):
    store, service, error = await failing_accept(monkeypatch, tmp_path, RefundResponseLost(), "supplier")
    assert error.status == 502 and "will be refunded" in error.message
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "refund_due"
    assert len(service.payments.refund_keys) == 1  # the money already went back
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert [item["to"] for item in result["reconciled"]] == ["supplier_order_failed_refunded"]
    assert kinds(service.payments).count("refund") == 1 and len(service.payments.refunds) == 1


@pytest.mark.asyncio
async def test_a_stranded_po_whose_refund_fails_is_left_refund_due_and_retried(monkeypatch, tmp_path):
    from rigbox.fulfilment import RigOrders

    class Crash(Exception):
        pass

    async def killed(self, **kwargs):
        raise Crash()
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=RefundFailsOnce())
    monkeypatch.setattr(RigOrders, "send_supplier_order", killed)
    with pytest.raises(Crash):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    first = await service.reconcile_payments(TENANT, now=later(30))
    assert first["reconciled"] == [] and first["needs_review"] == []
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "refund_due" and state["refund_reason"] == "supplier_order_unsent"
    assert state["reconcile_error"] is True
    assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "cancelled"
    assert service.payments.refunds == {}
    second = await service.reconcile_payments(TENANT, now=later(60))
    assert second["reconciled"] == [{"quote_id": quote_id, "from": "refund_due",
                                     "to": "supplier_order_failed_refunded"}]
    assert kinds(service.payments) == ["create_intent", "capture", "refund"]
    assert service.payments.refund_causes == ["supplier_order_unsent"]
    assert (await service.reconcile_payments(TENANT, now=later(90)))["reconciled"] == []


@pytest.mark.asyncio
async def test_a_manual_order_is_never_refunded_after_the_store_turns_auto_order_on(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, auto=False)
    assert (await service.locate_accept(TENANT, body))["state"] == "ordered"
    quote_id = store.quotes[-1]["id"]
    assert "auto_order" not in store.quotes[-1]["payload"]["locate_state"]
    await store.put_retailer(TENANT, "shop", "shop@example.com", None, "Shop", blind_ship=True, auto_order=True)
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [] and result["needs_review"] == []
    assert "refund" not in kinds(service.payments)
    row = store.locate_orders[(TENANT, quote_id)]
    assert row["order"]["state"] == "placed" and row["purchase_order"]["state"] == "draft"
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "ordered"


@pytest.mark.asyncio
async def test_a_crashed_auto_order_is_settled_after_the_store_turns_auto_order_off(monkeypatch, tmp_path):
    from rigbox.fulfilment import RigOrders

    class Crash(Exception):
        pass

    async def killed(self, **kwargs):
        raise Crash()
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setattr(RigOrders, "send_supplier_order", killed)
    with pytest.raises(Crash):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    assert store.quotes[-1]["payload"]["locate_state"]["auto_order"] is True
    await store.put_retailer(TENANT, "shop", "shop@example.com", None, "Shop", blind_ship=True, auto_order=False)
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [{"quote_id": quote_id, "from": "ordered", "to": "supplier_order_failed_refunded"}]
    assert kinds(service.payments).count("refund") == 1
    assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "cancelled"


@pytest.mark.asyncio
async def test_a_failed_refund_due_write_after_accept_cancels_is_refunded_by_reconcile(monkeypatch, tmp_path):
    """The cancel commits, then the refund_due write fails: the quote is left at
    "cancelling", and the next reconcile reads the cancelled order and refunds
    exactly once."""
    from rigbox.fulfilment import RigOrders

    async def send_refused(self, **kwargs):
        raise DeliveryError("order_mode")
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setattr(RigOrders, "send_supplier_order", send_refused)
    real, failures = store.locate_state, [1]

    async def blip(tenant_id, quote_id, state):
        if state.get("state") == "refund_due" and failures[0]:
            failures[0] -= 1
            raise ConnectionError("database blip")
        return await real(tenant_id, quote_id, state)
    monkeypatch.setattr(store, "locate_state", blip)
    with pytest.raises(ConnectionError):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "cancelling" and state["cancel_reason"] == "supplier_order_failed"
    assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "cancelled"
    assert service.payments.refunds == {}
    assert (await service.reconcile_payments(TENANT))["reconciled"] == []  # too recent
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [{"quote_id": quote_id, "from": "cancelling",
                                     "to": "supplier_order_failed_refunded"}]
    assert service.payments.refund_causes == ["supplier_order_failed"]
    assert (await service.reconcile_payments(TENANT, now=later(60)))["reconciled"] == []
    assert kinds(service.payments).count("refund") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["raises", "returns_false"])
async def test_a_failed_refund_due_swap_in_the_stranded_branch_is_refunded_next_run(monkeypatch, tmp_path, failure):
    from rigbox.fulfilment import RigOrders

    class Crash(Exception):
        pass

    async def killed(self, **kwargs):
        raise Crash()
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setattr(RigOrders, "send_supplier_order", killed)
    with pytest.raises(Crash):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    real, failures = store.swap_locate_state, [1]

    async def flaky(tenant_id, quote, old, new):
        if new.get("state") == "refund_due" and failures[0]:
            failures[0] -= 1
            if failure == "raises":
                raise ConnectionError("database blip")
            return False
        return await real(tenant_id, quote, old, new)
    monkeypatch.setattr(store, "swap_locate_state", flaky)
    first = await service.reconcile_payments(TENANT, now=later(30))
    assert first["reconciled"] == [] and first["needs_review"] == []
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "cancelling" and state["cancel_reason"] == "supplier_order_unsent"
    assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "cancelled"
    assert service.payments.refunds == {}
    second = await service.reconcile_payments(TENANT, now=later(60))
    assert second["reconciled"] == [{"quote_id": quote_id, "from": "cancelling",
                                     "to": "supplier_order_failed_refunded"}]
    assert service.payments.refund_causes == ["supplier_order_unsent"]
    assert (await service.reconcile_payments(TENANT, now=later(90)))["reconciled"] == []
    assert kinds(service.payments).count("refund") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["po_sent", "po_unsent", "order_vanished"])
async def test_a_quote_left_cancelling_is_settled_from_the_order(monkeypatch, tmp_path, case):
    """Rig stops inside the cancel, after writing "cancelling". The reconciler
    reads the order: a PO the supplier has ends supplier_ordered with 0
    refunds; an unsent one is cancelled and refunded once; no order at all is
    listed for a person."""
    from rigbox.fulfilment import RigOrders
    real_send, real_cancel = RigOrders.send_supplier_order, RigOrders.cancel

    class Killed(Exception):
        pass

    async def send_fails(self, **kwargs):
        if case == "po_sent":
            await real_send(self, **kwargs)  # the file reaches the outbox...
            store.locate_orders[(TENANT, kwargs["quote_id"])]["purchase_order"].update(state="draft", sent=None)
        raise DeliveryError("smtp_down")  # ...but Rig records a failure

    async def killed(self, *args, **kwargs):
        raise Killed()
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setattr(RigOrders, "send_supplier_order", send_fails)
    monkeypatch.setattr(RigOrders, "cancel", killed)
    with pytest.raises(Killed):
        await service.locate_accept(TENANT, body)
    monkeypatch.setattr(RigOrders, "cancel", real_cancel)
    quote_id = store.quotes[-1]["id"]
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "cancelling"
    assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "placed"
    if case == "order_vanished":
        del store.locate_orders[(TENANT, quote_id)]
    result = await service.reconcile_payments(TENANT, now=later(30))
    state = store.quotes[-1]["payload"]["locate_state"]
    if case == "po_sent":
        assert result["reconciled"] == [{"quote_id": quote_id, "from": "cancelling", "to": "supplier_ordered"}]
        assert state["purchase_order_state"] == "sent" and "refund" not in kinds(service.payments)
        assert store.locate_orders[(TENANT, quote_id)]["purchase_order"]["state"] == "sent"
    elif case == "po_unsent":
        assert result["reconciled"] == [{"quote_id": quote_id, "from": "cancelling",
                                         "to": "supplier_order_failed_refunded"}]
        assert kinds(service.payments).count("refund") == 1
        assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "cancelled"
    else:
        assert result["reconciled"] == [] and result["needs_review"] == [quote_id]
        assert state["state"] == "cancelling" and state["needs_review"] is True
        assert "refund" not in kinds(service.payments)
    assert (await service.reconcile_payments(TENANT, now=later(60)))["reconciled"] == []


@pytest.mark.asyncio
async def test_an_order_saved_before_place_raised_is_never_refunded(monkeypatch, tmp_path):
    """place_located_order can raise after its row is saved (order_mismatch).
    Accept doesn't refund; the reconciler lists the quote in needs_review."""
    from rigbox.fulfilment import RigOrders
    real_place = RigOrders.place_located_order

    async def saved_then_raises(self, **kwargs):
        await real_place(self, **kwargs)
        raise DeliveryError("order_mismatch")
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setattr(RigOrders, "place_located_order", saved_then_raises)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502 and "will be refunded" in raised.value.message
    quote_id = store.quotes[-1]["id"]
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "refund_due" and state["refund_reason"] == "order_failed"
    for minutes in (30, 60):
        result = await service.reconcile_payments(TENANT, now=later(minutes))
        assert result["reconciled"] == [] and result["needs_review"] == [quote_id]
    assert "refund" not in kinds(service.payments)
    assert store.quotes[-1]["payload"]["locate_state"]["needs_review"] is True
    assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "placed"


@pytest.mark.asyncio
async def test_reconcile_is_test_mode_only(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setenv("RIG_LOCATE_PAYMENTS_MODE", "live")
    with pytest.raises(payments.PaymentRefused):
        await service.reconcile_payments(TENANT, now=later())
    assert service.payments.calls == []


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


@pytest.mark.asyncio
async def test_real_postgres_reconcile_claims_each_stuck_quote_once(monkeypatch, tmp_path):
    import asyncpg
    from uuid import uuid4
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    from rigbox.store import PgStore
    from chassis.tenant_db import tenant_scope
    _, service, _, _, _ = await paid_shop(monkeypatch, tmp_path)
    admin = _admin_url()
    name = "rig_payrec_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            store = PgStore(pool)
            await store.apply_schema()
            service.store = store
            price = {"amount": "1125.00", "currency": "ZAR"}
            paid, pending, done = ("req_" + uuid4().hex for _ in range(3))
            with tenant_scope(TENANT):
                for quote_id, state in ((paid, {"state": "paid", "paid_at": "2026-10-31T00:00:00+00:00",
                                                 "price": price, "payment": {"reference": "ch_test_pg"}}),
                                        (pending, {"state": "payment_pending", "pending_at": later(-1).isoformat(),
                                                   "price": price, "payment": {"intent": "pi_test_pg"}}),
                                        (done, {"state": "supplier_ordered", "price": price})):
                    await store.add_quote(TENANT, quote_id, {"kind": "product", "locate_state": state}, {"name": "T"})
                listed = await store.open_locate_payments(TENANT)
                assert [quote_id for quote_id, _ in listed] == [paid, pending]
                assert await store.open_locate_payments(str(uuid4())) == []
                states = dict(await store.locate_states(TENANT, [done, pending, "req_missing"]))
                assert set(states) == {done, pending} and states[done]["state"] == "supplier_ordered"
                assert await store.locate_states(str(uuid4()), [done]) == []
                old = listed[0][1]
                swaps = await asyncio.gather(*(store.swap_locate_state(TENANT, paid, old, {**old, "n": i})
                                               for i in range(5)))
                assert sorted(swaps) == [False, False, False, False, True]
                await store.swap_locate_state(TENANT, paid, (await store.open_locate_payments(TENANT))[0][1], old)
                both = await asyncio.gather(service.reconcile_payments(TENANT), service.reconcile_payments(TENANT))
                settled = await pool.fetch("SELECT id, payload->'locate_state'->>'state' AS state"
                                           " FROM agent_rig.quotes ORDER BY created_at")
            assert [item for result in both for item in result["reconciled"]] == [
                {"quote_id": paid, "from": "paid", "to": "order_failed_refunded"}]  # pending is too recent
            assert {row["id"]: row["state"] for row in settled} == {
                paid: "order_failed_refunded", pending: "payment_pending", done: "supplier_ordered"}
            assert kinds(service.payments) == ["refund"]
            print("RIG_PAY_RECONCILE_PG", json.dumps(both, sort_keys=True))
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)
