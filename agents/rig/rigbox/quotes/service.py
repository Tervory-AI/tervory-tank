"""RIG-4 additions isolated from catalogue, feed and ranking work."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from rigbox.logic import fitting_parts
from rigbox.service import RigError, Service, _clean_text, _contact

from .senders import DeliveryError
from .notice import notice, receipt



_ADDRESS = {"name": 120, "street": 200, "street2": 200, "city": 120, "zip": 20, "state": 120,
            "country": 2, "phone": 40}
_ADDRESS_REQUIRED = ("name", "street", "city", "zip", "country")


def ship_address(value: Any) -> dict[str, str]:
    """Blind-ship delivery address from the shopper. Strict: known keys, sane lengths."""
    if not isinstance(value, dict) or set(value) - set(_ADDRESS):
        raise RigError("invalid", "A delivery address is required.", 422)
    address: dict[str, str] = {}
    for key, limit in _ADDRESS.items():
        item = value.get(key)
        if item is None or item == "":
            continue
        if not isinstance(item, str) or len(item.strip()) > limit or any(ch in item for ch in "\r\n\x00"):
            raise RigError("invalid", "A delivery address is required.", 422)
        address[key] = item.strip()
    if any(not address.get(key) for key in _ADDRESS_REQUIRED) or not re.fullmatch(r"[A-Za-z]{2}", address["country"]):
        raise RigError("invalid", "A delivery address is required.", 422)
    address["country"] = address["country"].upper()
    return address


class QuoteService(Service):
    def __init__(self, store: Any, models: Any, handoff: Any, quotes: Any) -> None:
        super().__init__(store, models, handoff)
        self.quote_store = quotes
        # Locate orders and supplier POs live in Rig's own database (no Odoo).
        from rigbox.fulfilment import RigOrders
        self.fulfilment: Any = RigOrders(store)

    async def validate_setup(self, tenant: str, setup: dict[str, Any]) -> None:
        parts = setup.get("parts")
        if not isinstance(parts, list) or not parts or len(parts) > 50:
            raise RigError("invalid", "Choose a setup from this catalogue.", 422)
        try:
            ids = [part["product"]["id"] for part in parts]
            roles = [part["role"] for part in parts]
            if not all(isinstance(value, str) and value for value in ids + roles):
                raise ValueError
            if len(set(ids)) != len(ids) or len(set(roles)) != len(roles):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise RigError("invalid", "Choose a setup from this catalogue.", 422) from None
        products = await self._active(tenant)
        centre = next((p for p in products if p["sku"] == ids[0]), None)
        if not centre:
            raise RigError("invalid", "That setup is not in this catalogue.", 422)
        fits = await self._approved_fits(tenant)
        allowed = {p["sku"] for p, _ in fitting_parts(centre, products, fits)}
        if any(sku not in allowed for sku in ids[1:]):
            raise RigError("fit", "A part no longer has an approved fit. Choose the setup again.", 422)

    async def swap(self, tenant_id: str, setup: dict[str, Any], role: str) -> dict[str, Any]:
        await self.validate_setup(tenant_id, setup)
        return await super().swap(tenant_id, setup, role)

    async def quote(self, tenant_id: str, body: dict[str, Any], *, hold: bool = False) -> dict[str, Any]:
        self._quote_fields(body.get("contact"))
        if isinstance(body.get("setup"), dict):
            await self.validate_setup(tenant_id, body["setup"])
        payload, contact = await self.quote_payload(tenant_id, body)
        evidence = await self._notice_receipt(tenant_id, body.get("notice_version"))
        if evidence:
            payload["notice_receipt"] = evidence
        return await self._store_quote(tenant_id, payload, contact, hold=hold)

    async def link_quote(self, tenant_id: str, url: str, note: str,
                         contact: dict[str, Any] | None = None, *, hold: bool = False,
                         notice_version: str | None = None) -> dict[str, Any]:
        self._quote_fields(contact)
        note = _clean_text(note, 4000)
        try:
            parsed = urlsplit(url.strip())
        except ValueError:
            raise RigError("invalid", "That link is not a web address.", 422) from None
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or len(url) > 2048 or len(note) > 4000):
            raise RigError("invalid", "That link is not a web address.", 422)
        payload = {"kind": "link", "url": parsed.geturl(), "note": note.strip()}
        evidence = await self._notice_receipt(tenant_id, notice_version)
        if evidence:
            payload["notice_receipt"] = evidence
        return await self._store_quote(tenant_id, payload,
            _contact(contact) if contact else {}, hold=hold)

    @staticmethod
    def _quote_fields(contact: Any) -> None:
        if contact is not None and (not isinstance(contact, dict)
                                   or set(contact) - {"name", "email", "phone"}):
            raise RigError("invalid", "The request is not valid.", 422)

    async def privacy_notice(self, tenant: str) -> dict[str, str] | None:
        retailer = await self.store.retailer(tenant) or {}
        return notice(retailer.get("quote_notice"))

    async def _notice_receipt(self, tenant: str, shown_version: str | None) -> dict[str, str] | None:
        return receipt(await self.privacy_notice(tenant), shown_version)

    async def _store_quote(self, tenant_id: str, payload: dict[str, Any],
                           contact: dict[str, Any], *, hold: bool = False) -> dict[str, Any]:
        quote_id = "req_" + uuid4().hex
        await self.quote_store.create(tenant_id, {"id": quote_id, "payload": payload, "contact": contact}, hold=hold)
        if hold:
            logging.getLogger("agent").warning("rig_quote_held tenant_id=%s request_id=%s reason=tenant_quote_limit",
                                               tenant_id, quote_id)
        else:
            await self.deliver(tenant_id, quote_id)
        state = await self.quote_store.status(tenant_id, quote_id)
        body: dict[str, Any] = {"request_id": quote_id, "delivery": state["status"]}
        if state["status"] != "sent":
            body["message"] = ("Your request is saved. The retailer needs to check its delivery."
                               if state["status"] == "needs_person" else
                               "Your request is saved. Delivery to the retailer is pending.")
        if hasattr(self.handoff, "portal"):
            try:
                portal = self.handoff.portal(tenant_id)
                if portal:
                    body["portal_url"] = portal
            except DeliveryError:
                pass  # Delivery state remains visible; never expose invalid URLs.
        return body

    async def locate_accept(self, tenant_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Shopper Accept on a held Locate price. Backend only, sandbox only.

        hold -> stored quote (sent to the retailer) -> test-mode capture ->
        Rig-owned order and draft supplier PO (rigbox.fulfilment, Rig's own
        Postgres; Tervory no longer uses Odoo). A failed order is refunded.
        Each step is recorded in the quote's payload as locate_state.
        """
        from datetime import datetime, timezone

        from rigbox import payments
        from rigbox.locate_live import Holds, LocateRefused, hold_secret, read_token
        from rigbox.fulfilment import sandbox_orders

        row = await self._locate_row(tenant_id, str(body.get("product_id") or ""))
        try:
            sandbox_orders()
            secret = hold_secret()
            provider = payments.guard(self.payments)
        except (DeliveryError, LocateRefused, payments.PaymentRefused):
            raise RigError("unavailable", "Ordering from other stores is not available.", 503) from None
        if self.fulfilment is None:
            raise RigError("unavailable", "Ordering from other stores is not available.", 503)
        self._quote_fields(body.get("contact"))
        token = str(body.get("payment_token") or "")
        if not token or len(token) > 200:
            raise RigError("invalid", "A payment is required.", 422)
        # Blind ship (per store, off by default): validate the address before
        # the hold is taken, so a bad address never burns the held price.
        retailer = await self.store.retailer(tenant_id) or {}
        blind = retailer.get("blind_ship") is True
        ship_to = ship_address(body.get("delivery")) if blind else None
        # Optional auto-order (per store, off by default): sandbox outbox only.
        auto = retailer.get("auto_order") is True
        if auto:
            from rigbox import supplier_orders
            try:
                supplier_orders.outbox()
            except DeliveryError:
                raise RigError("unavailable", "Ordering from other stores is not available.", 503) from None
            if not (hasattr(self.fulfilment, "send_supplier_order") and hasattr(self.fulfilment, "cancel")):
                raise RigError("unavailable", "Ordering from other stores is not available.", 503)
        now = datetime.now(timezone.utc)
        try:
            hold_id = read_token(secret, tenant_id, str(body.get("hold") or ""), now)
        except LocateRefused as exc:
            raise RigError("hold", "That price has expired. Check availability again.", 410
                           if str(exc) == "hold_expired" else 422) from None
        holds = Holds(self.store)
        if auto:
            # No real vendor or order inbox for this source: refuse before the
            # hold is taken (so the shopper's held price is not burned) and
            # before any payment.
            peeked = await holds.peek(tenant_id, hold_id, now)
            if peeked is not None and not supplier_orders.supplier_ready(peeked["private"]["source"]):
                raise RigError("unavailable", "Ordering from other stores is not available.", 503)
        held = await holds.take(tenant_id, hold_id, now)
        if held is None or held["product_id"] != row["sku"]:
            raise RigError("hold", "That price has expired. Check availability again.", 410)
        if auto and not supplier_orders.supplier_ready(held["private"]["source"]):
            raise RigError("unavailable", "Ordering from other stores is not available.", 503)
        price = held["public"]["price"]
        product = dict(await self.product(tenant_id, row["sku"]))
        product["price"] = dict(price)
        state: dict[str, Any] = {"state": "confirmed", "hold_id": hold_id,
                                 "located_at": held["private"]["offer"].get("seen_at"),
                                 "confirmed_at": held["private"]["live"]["checked_at"],
                                 "price": price}
        payload = {"kind": "product", "product": product, "locate_state": state,
                   "locate": [{"product_id": row["sku"], "public": held["public"], "store": held["private"]}]}
        if ship_to is not None:
            state["blind_ship"] = True
            payload["ship_to"] = ship_to
        evidence = await self._notice_receipt(tenant_id, body.get("notice_version"))
        if evidence:
            payload["notice_receipt"] = evidence
        stored = await self._store_quote(tenant_id, payload, _contact(body.get("contact") or {}))
        quote_id = stored["request_id"]

        async def record(**changes: Any) -> None:
            state.update(changes)
            await self.store.locate_state(tenant_id, quote_id, dict(state))

        if stored.get("delivery") != "sent":
            await record(state="confirmed", note="retailer_not_reached")
            return {"request_id": quote_id, "state": "confirmed", "price": price,
                    "message": "Your request is saved. No payment was taken."}
        reference = f"rig:{tenant_id}:{quote_id}"
        metadata = {"quote_id": quote_id, "product_id": row["sku"]}
        try:
            if payments.intents(provider):
                # Pay on Accept: an intent for the held price, then capture. Both
                # are keyed by the quote reference, so a retry never charges twice.
                intent = await payments.create_intent(provider, amount=price["amount"], currency=price["currency"],
                                                      token=token, reference=reference, metadata=metadata)
                await record(state="payment_pending",
                             payment={"intent": intent.reference, "provider": provider.name, "test": intent.test})
                if intent.status != "requires_capture":
                    await record(state="payment_failed")
                    raise RigError("payment", "The payment was not taken.", 402)
                charge = await payments.capture_intent(provider, intent, reference=reference)
            else:
                charge = await payments.capture(provider, amount=price["amount"], currency=price["currency"],
                                                token=token, reference=reference, metadata=metadata)
        except payments.PaymentRefused:
            await record(state="payment_refused")
            raise RigError("payment", "The payment was not taken.", 402) from None
        if charge.status != "captured":
            await record(state="payment_failed")
            raise RigError("payment", "The payment was not taken.", 402)
        await record(state="paid", paid_at=datetime.now(timezone.utc).isoformat(),
                     payment={"reference": charge.reference, "provider": provider.name, "test": charge.test})
        try:
            order = await self.fulfilment.place_located_order(
                tenant_id=tenant_id, quote_id=quote_id, located=held["private"], price=price,
                ship={"address": ship_to} if ship_to else None)
        except DeliveryError as exc:
            refunded = await payments.refund(provider, charge, "order_failed")
            await record(state="order_failed_refunded", error=str(exc), refund={"status": refunded.status})
            raise RigError("order", "The order could not be placed. The payment was refunded.", 502) from None
        await record(state="ordered", ordered_at=datetime.now(timezone.utc).isoformat(),
                     order=order["order"]["number"], purchase_order=order["purchase_order"]["number"])
        if auto:
            try:
                supplied = await self.fulfilment.send_supplier_order(
                    tenant_id=tenant_id, quote_id=quote_id, store_name=retailer.get("name") or "",
                    store_email=retailer.get("email"))
            except DeliveryError as exc:
                # Cancel Rig's order and unsent PO, then refund. cancel refuses
                # (returns "sent") when the supplier already has the PO: then
                # the order stands and nothing is refunded.
                cancelled = await self.fulfilment.cancel(tenant_id, quote_id, f"supplier_order_failed:{exc}")
                if cancelled != "sent":
                    refunded = await payments.refund(provider, charge, "supplier_order_failed")
                    await record(state="supplier_order_failed_refunded", error=str(exc),
                                 refund={"status": refunded.status})
                    raise RigError("order", "The order could not be placed. The payment was refunded.", 502) from None
                supplied = {"purchase_order": {"state": "sent"},
                            "supplier_order": {"channel": "email", "transport": "sandbox_outbox",
                                               "duplicate": True, "reconciled": True}}
            sent = supplied["supplier_order"]
            await record(state="supplier_ordered", supplier_ordered_at=datetime.now(timezone.utc).isoformat(),
                         purchase_order_state=supplied["purchase_order"]["state"],
                         supplier_order={key: sent.get(key) for key in ("channel", "transport", "file", "duplicate")})
        body = {"request_id": quote_id, "state": "ordered", "price": price,
                "payment": {"reference": charge.reference, "test": True}}
        if ship_to is not None:
            body["ships_direct"] = True
        return body

    async def payment_webhook(self, body: bytes, signature: str) -> dict[str, Any]:
        """Verified provider webhook. Records the event on its quote, once.

        No shopper key: the HMAC signature is the authentication. Refused
        (503) unless payments are in test mode with an adapter configured.
        Events are an audit trail only; they never move an order forward.
        """
        import re
        from datetime import datetime, timezone
        from uuid import UUID

        from chassis.tenant_db import tenant_scope

        from rigbox import payments

        try:
            event = payments.verify_webhook(self.payments, body, signature)
        except payments.PaymentRefused as exc:
            if str(exc) in {"webhook_signature", "webhook_stale", "webhook_payload"}:
                raise RigError("signature", "The webhook could not be verified.", 400) from None
            raise RigError("unavailable", "Payments are not available.", 503) from None
        match = re.fullmatch(r"rig:([0-9a-fA-F-]{36}):(req_[0-9a-f]{32})", str(event["data"].get("reference") or ""))
        try:
            tenant = str(UUID(match.group(1))) if match else ""
        except ValueError:
            tenant = ""
        if not tenant:
            return {"received": True, "recorded": False}
        # The signed reference is the authentication; scope the write to its tenant.
        with tenant_scope(tenant):
            recorded = await self.store.payment_event(tenant, match.group(2), {
                "id": event["id"], "type": event["type"][:64],
                "received_at": datetime.now(timezone.utc).isoformat()})
        return {"received": True, "recorded": recorded}

    async def deliver(self, tenant: str, quote_id: str) -> None:
        quote = await self.quote_store.claim(tenant, quote_id)
        if quote is None:
            return
        attempt = quote.pop("_attempt")
        error = None
        try:
            # Shorter than the five-minute claim lease, including multi-line Odoo orders.
            async with asyncio.timeout(60):
                retailer = await self.store.retailer(tenant) or {}
                await self.handoff.send(tenant_id=tenant, email=retailer.get("email"),
                                        webhook=retailer.get("webhook"), quote=quote)
        except DeliveryError as exc:
            error = str(exc)
        except Exception:
            error = "retailer_unavailable"
        await self.quote_store.finish(tenant, quote_id, error, attempt)

    async def retry_pending(self, tenant: str) -> int:
        ids = await self.quote_store.pending(tenant)
        for quote_id in ids:
            await self.deliver(tenant, quote_id)
        return len(ids)
