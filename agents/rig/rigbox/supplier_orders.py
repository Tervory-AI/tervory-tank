"""Optional auto-order: send the confirmed purchase order to the approved source.

Sandbox only. There is no live sender: the only transport is a local outbox
directory (one RFC 5322 .eml file per order), written with
RIG_LOCATE_ORDER_MODE=sandbox and RIG_LOCATE_OUTBOX_DIR set. Nothing here opens
a socket or sends mail. Going live needs a new transport and an explicit,
separately approved change; there is deliberately no mode switch for it.

Idempotent: one file per (tenant, quote), created with O_EXCL, so a retry
never sends the supplier a second order.
"""

from __future__ import annotations

import hashlib
import os
import re
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rigbox.quotes.senders import DeliveryError, sandbox_orders

OUTBOX_ENV = "RIG_LOCATE_OUTBOX_DIR"
EMAIL = re.compile(r"[^\s@<>,;\"]+@[^\s@<>,;\"]+\.[^\s@<>,;\"]+")
BLIND_TEXT = ("SHIP BLIND: this parcel goes straight to our customer. No supplier branding, prices, "
              "invoice or branded packing slip in the parcel. Use a plain packing slip or none.")


def supplier_ready(source: dict[str, Any]) -> bool:
    """An approved source can take auto-orders only with a real vendor and order inbox."""
    return bool(str(source.get("vendor_name") or "").strip()) and bool(
        EMAIL.fullmatch(str(source.get("order_email") or "")))


def outbox(env: dict[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    sandbox_orders(values)
    folder = values.get(OUTBOX_ENV, "")
    if not folder:
        raise DeliveryError("outbox_not_configured")
    path = Path(folder)
    if not path.is_dir():
        raise DeliveryError("outbox_not_configured")
    return path


def compose(*, tenant_id: str, quote_id: str, store_name: str, store_email: str | None,
            located: dict[str, Any], purchase: dict[str, Any], ship: dict[str, Any] | None) -> EmailMessage:
    """The supplier-facing order. Supplier identity belongs here, never in shopper text."""
    source, offer, live = located["source"], located["offer"], located["live"]
    if not supplier_ready(source):
        raise DeliveryError("supplier_not_configured")
    reference = f"rig:{tenant_id}:{quote_id}"
    message = EmailMessage()
    message["To"] = str(source["order_email"])
    message["From"] = f"{store_name or 'Rig'} <orders@rig.tervory.com>"
    if store_email and EMAIL.fullmatch(store_email):
        message["Reply-To"] = store_email
    message["Subject"] = f"Purchase order {purchase['name']} from {store_name or 'Rig'}"
    message["Message-ID"] = f"<po-{hashlib.sha256(reference.encode()).hexdigest()[:24]}@rig.tervory.com>"
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    message["X-Rig-Reference"] = reference
    lines = [
        f"Hello {source['vendor_name']},",
        "",
        f"Please supply the following on our purchase order {purchase['name']}.",
        "",
        f"  Your item: {offer.get('sku') or ''}",
        f"  Page: {offer.get('url') or ''}",
        "  Quantity: 1",
        f"  Agreed price: {live['price']} {live['currency']} (your live price when we checked)",
        "",
    ]
    if ship is not None:
        address = ship["address"]
        lines += ["Ship directly to:"] + [f"  {address[key]}" for key in
                  ("name", "street", "street2", "city", "state", "zip", "country", "phone") if address.get(key)] + [""]
        if source.get("neutral_slip_required") is True:
            lines += [BLIND_TEXT, ""]
    else:
        lines += [f"Ship to {store_name or 'us'} at the address on your account.", ""]
    lines += [f"Please reply with the tracking number and quote {purchase['name']}.", "", "Thank you."]
    message.set_content("\n".join(lines))
    return message


def write(message: EmailMessage, *, tenant_id: str, quote_id: str,
          env: dict[str, str] | None = None) -> dict[str, Any]:
    """Write once to the sandbox outbox. A second call for the same order is a no-op."""
    folder = outbox(env)
    name = hashlib.sha256(f"rig:{tenant_id}:{quote_id}".encode()).hexdigest()[:32] + ".eml"
    path = folder / name
    try:
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return {"channel": "email", "transport": "sandbox_outbox", "file": name, "duplicate": True}
    except OSError:
        raise DeliveryError("outbox_unavailable") from None
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(bytes(message))
    except OSError:
        path.unlink(missing_ok=True)
        raise DeliveryError("outbox_unavailable") from None
    return {"channel": "email", "transport": "sandbox_outbox", "file": name, "duplicate": False,
            "message_id": message["Message-ID"]}
