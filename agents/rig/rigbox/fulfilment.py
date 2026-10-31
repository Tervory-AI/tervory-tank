"""Rig's own Locate fulfilment: orders and supplier purchase orders in Rig's Postgres.

Tervory no longer uses Odoo, so a paid Locate Accept is recorded here, not in
an ERP. One accepted quote makes exactly one row in agent_rig.locate_orders
(what the shopper bought, at the held price) and one draft row in
agent_rig.supplier_purchase_orders (what the store buys from the approved
source, at the source's live price). Both are keyed by (tenant, quote), so a
retry or a concurrent second Accept returns the same order and PO numbers and
never makes a second row.

Blind ship (per store, off by default): the PO carries the shopper's delivery
address, and when the source is flagged neutral_slip_required it carries the
neutral-slip instruction. The order and PO are private store records: nothing
here is returned to the shopper except through QuoteService.locate_accept's
own response, which names neither the source nor its price.

Sandbox only, like the rest of Locate ordering (RIG_LOCATE_ORDER_MODE=sandbox).
Nothing here opens a socket or sends mail.

The interface (Fulfilment) is what QuoteService calls. RigOrders is the only
implementation in this stack. #463's Odoo adapter (OdooHandoff /
RetailerHandoff.place_located_order) is left in place but is no longer called.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from rigbox.quotes.senders import DeliveryError, sandbox_orders

# Printed on the supplier PO when the order ships blind and the approved source
# is flagged neutral_slip_required.
NEUTRAL_SLIP = ("SHIP BLIND: this parcel goes straight to our customer. No supplier branding, prices, "
                "invoice or branded packing slip in the parcel. Use a plain packing slip or none.")

_CURRENCY = re.compile(r"[A-Z]{3}")


class Fulfilment(Protocol):
    """What QuoteService.locate_accept needs after a captured payment."""

    async def place_located_order(self, *, tenant_id: str, quote_id: str, located: dict[str, Any],
                                  price: dict[str, Any], ship: dict[str, Any] | None = None) -> dict[str, Any]:
        """Record the order and its draft supplier PO. Idempotent per (tenant, quote)."""
        ...


def numbers(tenant_id: str, quote_id: str) -> tuple[str, str]:
    """Stable order and PO numbers for a quote: the same on every retry."""
    digest = hashlib.sha256(f"rig:{tenant_id}:{quote_id}".encode()).hexdigest()[:10].upper()
    return f"RIG-{digest}", f"PO-{digest}"


def _amount(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise DeliveryError("order_rejected") from None
    if not amount.is_finite() or amount <= 0:
        raise DeliveryError("order_rejected")
    return str(amount.quantize(Decimal("0.01")))


def _currency(value: Any) -> str:
    currency = str(value or "").upper()
    if not _CURRENCY.fullmatch(currency):
        raise DeliveryError("order_rejected")
    return currency


def _public(order: dict[str, Any], purchase: dict[str, Any]) -> dict[str, Any]:
    """The caller's view: numbers and states only (kept in locate_state)."""
    return {"order": {"number": order["number"], "state": order["state"]},
            "purchase_order": {"number": purchase["number"], "state": purchase["state"],
                               "ship_direct": purchase["ship_to"] is not None,
                               "neutral_slip": purchase["neutral_slip"]}}


class RigOrders:
    """Fulfilment in Rig's own database (MemoryStore or PgStore)."""

    def __init__(self, store: Any) -> None:
        self.store = store

    async def place_located_order(self, *, tenant_id: str, quote_id: str, located: dict[str, Any],
                                  price: dict[str, Any], ship: dict[str, Any] | None = None,
                                  env: dict[str, str] | None = None) -> dict[str, Any]:
        sandbox_orders(env)
        try:
            source, offer, live = located["source"], located["offer"], located["live"]
            product_id, source_id = str(located["product_sku"]), str(source["id"])
        except (KeyError, TypeError):
            raise DeliveryError("order_rejected") from None
        if not product_id or not source_id:
            raise DeliveryError("order_rejected")
        address = dict(ship["address"]) if ship is not None else None
        neutral = address is not None and source.get("neutral_slip_required") is True
        order_number, po_number = numbers(tenant_id, quote_id)
        order = {"quote_id": quote_id, "number": order_number, "state": "placed", "product_id": product_id,
                 "price": _amount(price.get("amount")), "currency": _currency(price.get("currency")),
                 "ship_to": address}
        purchase = {"quote_id": quote_id, "number": po_number, "state": "draft", "source_id": source_id,
                    "vendor_name": str(source.get("vendor_name") or "").strip(),
                    "order_email": str(source.get("order_email") or "").strip(),
                    "item_sku": str(offer.get("sku") or ""), "item_url": str(offer.get("url") or ""),
                    "quantity": 1, "unit_cost": _amount(live.get("price")),
                    "currency": _currency(live.get("currency")), "ship_to": address,
                    "neutral_slip": neutral, "instructions": NEUTRAL_SLIP if neutral else ""}
        try:
            saved = await self.store.place_locate_order(tenant_id, order, purchase)
        except DeliveryError:
            raise
        except Exception:
            raise DeliveryError("order_unavailable") from None
        if saved["purchase_order"]["source_id"] != source_id:
            raise DeliveryError("order_mismatch")
        return _public(saved["order"], saved["purchase_order"])
