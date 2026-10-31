"""Tenant-selected senders. Configuration and credentials never reach shoppers.

Odoo uses its documented external JSON-RPC API (common.authenticate and
object.execute_kw). Quote handoff creates draft sale.order records only: never
confirm, invoice, take payment or send mail. client_order_ref reconciles a
timed-out call.

The one exception is Locate order placement (place_located_order). It runs
only with RIG_LOCATE_ORDER_MODE=sandbox, against a sandbox Odoo, after a test
mode payment: it confirms that sale.order and creates one draft supplier
purchase.order. It never invoices, sends mail or confirms the purchase.

Blind ship (optional, per store): the sale.order gets the shopper's delivery
address, its line takes Odoo's Dropship route, and Odoo's own procurement
drafts the supplier purchase.order to that address (dest_address_id). Nothing
about the other store is written to customer-facing records.
"""

from __future__ import annotations

import json
from html import escape
import os
import re
from typing import Any
from urllib.parse import urlsplit


class DeliveryError(Exception):
    """Safe, fixed error code. Never include a remote response or credentials."""


def https_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise DeliveryError("configuration") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise DeliveryError("configuration")
    return value.rstrip("/")


ORDER_MODE_ENV = "RIG_LOCATE_ORDER_MODE"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def sandbox_orders(env: dict[str, str] | None = None) -> None:
    """Locate order placement is sandbox-only. Anything else refuses."""
    if (os.environ if env is None else env).get(ORDER_MODE_ENV, "") != "sandbox":
        raise DeliveryError("order_mode")


def odoo_url(value: str) -> str:
    """https, or plain http to a loopback sandbox only in sandbox order mode."""
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise DeliveryError("configuration") from None
    if (parsed.scheme == "http" and parsed.hostname in LOOPBACK
            and os.environ.get(ORDER_MODE_ENV, "") == "sandbox"
            and not (parsed.username or parsed.password or parsed.query or parsed.fragment)):
        return value.rstrip("/")
    return https_url(value)


def flow_for(tenant_id: str) -> dict[str, Any]:
    try:
        flows = json.loads(os.environ.get("RIG_QUOTE_FLOWS") or "{}")
        flow = flows.get(str(tenant_id), {})
        if not isinstance(flow, dict):
            raise ValueError
        return flow
    except (ValueError, AttributeError):
        raise DeliveryError("configuration") from None


# Printed on the supplier's purchase order (purchase.order.notes) when the
# approved source is flagged neutral_slip_required.
BLIND_INSTRUCTION = ("<p><strong>Ship blind.</strong> This parcel goes straight to our customer. "
                     "No supplier branding, prices, invoice or branded packing slip in the parcel. "
                     "Use a plain packing slip or none.</p>")


class OdooHandoff:
    def __init__(self, http: Any, *, url: str, database: str, user: str, api_key: str) -> None:
        if not all((url, database, user, api_key)):
            raise DeliveryError("not_configured")
        self.http = http
        self.url = odoo_url(url) + "/jsonrpc"
        self.database, self.user, self.api_key = database, user, api_key

    async def _rpc(self, service: str, method: str, args: list[Any]) -> Any:
        try:
            response = await self.http.post(self.url, json={
                "jsonrpc": "2.0", "method": "call", "id": 1,
                "params": {"service": service, "method": method, "args": args},
            }, timeout=20, follow_redirects=False)
            response.raise_for_status()
            body = response.json()
            if body.get("error") or "result" not in body:
                raise DeliveryError("odoo_rejected")
            return body["result"]
        except DeliveryError:
            raise
        except Exception:
            raise DeliveryError("odoo_unavailable") from None

    async def _session(self) -> Any:
        version = await self._rpc("common", "version", [])
        info = version.get("server_version_info") if isinstance(version, dict) else None
        if not isinstance(info, list) or not info or info[0] not in (16, 17, 18):
            raise DeliveryError("odoo_version_unsupported")
        uid = await self._rpc("common", "authenticate", [self.database, self.user, self.api_key, {}])
        if not isinstance(uid, int) or isinstance(uid, bool) or uid <= 0:
            raise DeliveryError("odoo_authentication")

        async def execute(model: str, method: str, args: list[Any], **kwargs: Any) -> Any:
            return await self._rpc("object", "execute_kw", [
                self.database, uid, self.api_key, model, method, args, kwargs,
            ])
        return execute

    async def place_located_order(self, *, tenant_id: str, quote_id: str, located: dict[str, Any],
                                  env: dict[str, str] | None = None,
                                  ship: dict[str, Any] | None = None) -> dict[str, Any]:
        """Sandbox only: confirm the quote's sale.order, then draft one supplier PO.

        Idempotent by client_order_ref (sale) and origin (purchase).
        located holds the hold's private snapshot: source, offer and live cost.
        ship (blind ship only) holds the shopper's delivery address.
        """
        sandbox_orders(env)
        execute = await self._session()
        reference = f"rig:{tenant_id}:{quote_id}"
        orders = await execute("sale.order", "search_read", [[["client_order_ref", "=", reference]]],
                               fields=["id", "state", "order_line"], limit=2)
        if len(orders) != 1:
            raise DeliveryError("odoo_order_missing")
        order = orders[0]
        if ship is not None:
            # Blind ship confirms only after the address and Dropship route are set.
            return await self._blind_order(execute, tenant_id=tenant_id, reference=reference, order=order,
                                           located=located, ship=ship)
        if order["state"] in ("draft", "sent"):
            await execute("sale.order", "action_confirm", [[order["id"]]])
        elif order["state"] != "sale":
            raise DeliveryError("odoo_order_state")
        source, offer, live = located["source"], located["offer"], located["live"]
        purchases = await execute("purchase.order", "search", [[["origin", "=", reference]]], limit=2)
        if len(purchases) > 1:
            raise DeliveryError("odoo_purchase_mapping")
        if purchases:
            purchase_id = purchases[0]
        else:
            vendor_id = await self._vendor(execute, tenant_id, source)
            currencies = await execute("res.currency", "search", [[["name", "=", live["currency"]]]],
                                       limit=1, context={"active_test": False})
            if not currencies:
                raise DeliveryError("odoo_currency")
            products = await execute("product.product", "search", [[["default_code", "=", located["product_sku"]]]],
                                     limit=2)
            if len(products) != 1:
                raise DeliveryError("odoo_product_mapping")
            purchase_id = await execute("purchase.order", "create", [{
                "partner_id": vendor_id, "origin": reference, "currency_id": currencies[0],
                "partner_ref": str(offer.get("sku") or ""),
                "order_line": [[0, 0, {"product_id": products[0], "product_qty": 1,
                    "name": f"Rig Locate {located['product_sku']} from {source['id']} ({offer.get('url') or ''})",
                    "price_unit": float(live["price"]), "taxes_id": [[6, 0, []]]}]]}])
        if not isinstance(purchase_id, int) or isinstance(purchase_id, bool) or purchase_id <= 0:
            raise DeliveryError("odoo_rejected")
        sale = await execute("sale.order", "read", [[order["id"]]], fields=["name", "state"])
        purchase = await execute("purchase.order", "read", [[purchase_id]], fields=["name", "state"])
        return {"sale_order": {"id": order["id"], "name": sale[0]["name"], "state": sale[0]["state"]},
                "purchase_order": {"id": purchase_id, "name": purchase[0]["name"], "state": purchase[0]["state"]}}

    async def _vendor(self, execute: Any, tenant_id: str, source: dict[str, Any]) -> int:
        vendor_ref = f"rig-supply:{tenant_id}:{source['id']}"
        vendors = await execute("res.partner", "search", [[["ref", "=", vendor_ref]]], limit=2,
                                context={"active_test": False})
        if len(vendors) > 1:
            raise DeliveryError("odoo_partner_mapping")
        vendor_id = vendors[0] if vendors else await execute("res.partner", "create", [{
            "name": str(source.get("site") or source["id"]), "ref": vendor_ref, "is_company": True,
            "supplier_rank": 1, "comment": "Rig Locate approved source"}])
        if not isinstance(vendor_id, int) or isinstance(vendor_id, bool) or vendor_id <= 0:
            raise DeliveryError("odoo_partner_mapping")
        return vendor_id

    async def _blind_order(self, execute: Any, *, tenant_id: str, reference: str, order: dict[str, Any],
                           located: dict[str, Any], ship: dict[str, Any]) -> dict[str, Any]:
        """Dropship to the shopper: delivery address, Dropship route, Odoo drafts the PO.

        Idempotent: the delivery partner is keyed by ref, the supplier price by
        vendor and product, and the purchase.order is found through its link to
        this sale.order's line. Customer-facing records (sale.order, its lines
        and the delivery address) never name the other store.
        """
        source, offer, live = located["source"], located["offer"], located["live"]
        address = ship["address"]
        sale = (await execute("sale.order", "read", [[order["id"]]],
                              fields=["name", "state", "partner_id", "partner_shipping_id"]))[0]
        customer = sale["partner_id"][0] if sale.get("partner_id") else None
        if not isinstance(customer, int):
            raise DeliveryError("odoo_partner_mapping")
        countries = await execute("res.country", "search", [[["code", "=", address["country"]]]], limit=1)
        if not countries:
            raise DeliveryError("odoo_country")
        values: dict[str, Any] = {"type": "delivery", "parent_id": customer, "ref": reference + ":ship",
            "country_id": countries[0], "comment": "from Rig, not verified",
            **{key: address[key] for key in ("name", "street", "street2", "city", "zip", "phone") if address.get(key)}}
        if address.get("state"):
            states = await execute("res.country.state", "search", [[["country_id", "=", countries[0]], "|",
                ["code", "=ilike", address["state"]], ["name", "=ilike", address["state"]]]], limit=1)
            if states:
                values["state_id"] = states[0]
        found = await execute("res.partner", "search", [[["ref", "=", values["ref"]]]], limit=2,
                              context={"active_test": False})
        if len(found) > 1:
            raise DeliveryError("odoo_partner_mapping")
        ship_id = found[0] if found else await execute("res.partner", "create", [values])
        if not isinstance(ship_id, int) or isinstance(ship_id, bool) or ship_id <= 0:
            raise DeliveryError("odoo_partner_mapping")
        routes = await execute("ir.model.data", "search_read", [[["module", "=", "stock_dropshipping"],
            ["name", "=", "route_drop_shipping"], ["model", "=", "stock.route"]]], fields=["res_id"], limit=1)
        if not routes:
            raise DeliveryError("odoo_dropship_missing")
        products = await execute("product.product", "search_read", [[["default_code", "=", located["product_sku"]]]],
                                 fields=["id", "product_tmpl_id"], limit=2)
        if len(products) != 1:
            raise DeliveryError("odoo_product_mapping")
        product = products[0]
        lines = await execute("sale.order.line", "search", [[["order_id", "=", order["id"]],
                                                           ["product_id", "=", product["id"]]]], limit=2)
        if len(lines) != 1:
            raise DeliveryError("odoo_product_mapping")
        vendor_id = await self._vendor(execute, tenant_id, source)
        if sale["state"] in ("draft", "sent"):
            currencies = await execute("res.currency", "search", [[["name", "=", live["currency"]]]],
                                       limit=1, context={"active_test": False})
            if not currencies:
                raise DeliveryError("odoo_currency")
            # Odoo's Dropship procurement drafts the PO from this vendor price.
            seller = {"partner_id": vendor_id, "product_tmpl_id": product["product_tmpl_id"][0],
                      "product_id": product["id"], "price": float(live["price"]), "currency_id": currencies[0],
                      "min_qty": 1, "product_code": str(offer.get("sku") or "")}
            sellers = await execute("product.supplierinfo", "search", [[["partner_id", "=", vendor_id],
                                                                       ["product_id", "=", product["id"]]]], limit=1)
            if sellers:
                await execute("product.supplierinfo", "write", [sellers, seller])
            else:
                await execute("product.supplierinfo", "create", [seller])
            await execute("sale.order", "write", [[order["id"]], {"partner_shipping_id": ship_id}])
            await execute("sale.order.line", "write", [lines, {"route_id": routes[0]["res_id"]}])
            await execute("sale.order", "action_confirm", [[order["id"]]])
        elif sale["state"] != "sale":
            raise DeliveryError("odoo_order_state")
        links = await execute("purchase.order.line", "search_read", [[["sale_line_id", "in", lines]]],
                              fields=["order_id"], limit=10)
        purchase_ids = sorted({link["order_id"][0] for link in links if link.get("order_id")})
        if len(purchase_ids) != 1:
            raise DeliveryError("odoo_purchase_mapping")
        purchase_id = purchase_ids[0]
        purchase = (await execute("purchase.order", "read", [[purchase_id]],
                                  fields=["name", "state", "partner_id", "dest_address_id"]))[0]
        if (not purchase.get("dest_address_id") or purchase["dest_address_id"][0] != ship_id
                or purchase["partner_id"][0] != vendor_id):
            raise DeliveryError("odoo_dropship_mapping")
        if purchase["state"] in ("draft", "sent"):
            update: dict[str, Any] = {"partner_ref": str(offer.get("sku") or "")}
            if source.get("neutral_slip_required") is True:
                update["notes"] = BLIND_INSTRUCTION
            await execute("purchase.order", "write", [[purchase_id], update])
        sale = (await execute("sale.order", "read", [[order["id"]]], fields=["name", "state"]))[0]
        return {"sale_order": {"id": order["id"], "name": sale["name"], "state": sale["state"]},
                "purchase_order": {"id": purchase_id, "name": purchase["name"], "state": purchase["state"],
                                   "dropship": True}}

    async def send(self, *, tenant_id: str, email: str | None, webhook: str | None,
                   quote: dict[str, Any]) -> None:
        del email, webhook
        execute = await self._session()

        reference = f"rig:{tenant_id}:{quote['id']}"
        existing = await execute("sale.order", "search", [[['client_order_ref', '=', reference]]], limit=1)
        async def supplier_note(order_id: int) -> None:
            located = quote["payload"].get("locate") or []
            if not located:
                return
            # sale.order.note and line_note are customer-visible. Use an internal
            # chatter note, never a sale line, supplier order or confirmation.
            marker = "rig-supply:" + reference
            messages = await execute("mail.message", "search", [[
                ["model", "=", "sale.order"], ["res_id", "=", order_id],
                ["body", "ilike", marker]]], limit=1)
            if messages:
                return
            body = "<pre>" + escape(marker + "\n" + json.dumps(located, sort_keys=True)) + "</pre>"
            await execute("sale.order", "message_post", [[order_id]], body=body,
                          message_type="comment", subtype_xmlid="mail.mt_note")

        if existing:
            await supplier_note(existing[0])
            return
        contact, payload = quote["contact"], quote["payload"]
        # Link requests may have no contact in older clients. Do not fabricate a
        # customer or turn an unpriced product URL into a priced quotation.
        if not contact.get("email"):
            raise DeliveryError("contact_required")
        values: dict[str, Any] = {"client_order_ref": reference}
        if payload["kind"] == "link":
            values["order_line"] = [[0, 0, {"display_type": "line_note", "name":
                "Product to source: " + payload["url"] + "\n" + payload["note"]}]]
        else:
            products = ([part["product"] for part in payload["setup"]["parts"]]
                        if payload["kind"] == "setup" else [payload["product"]])
            currency = products[0]["price"]["currency"]
            currencies = await execute("res.currency", "search", [[['name', '=', currency]]], limit=1)
            if not currencies:
                raise DeliveryError("odoo_currency")
            pricelists = await execute("product.pricelist", "search", [
                [['currency_id', '=', currencies[0]]]], limit=1)
            if not pricelists:
                raise DeliveryError("odoo_pricelist")
            values["pricelist_id"] = pricelists[0]
            lines = []
            for product in products:
                ids = await execute("product.product", "search", [
                    [['default_code', '=', product['id']]]], limit=2)
                if len(ids) != 1:
                    raise DeliveryError("odoo_product_mapping")
                lines.append([0, 0, {"product_id": ids[0], "name": product["name"],
                    "product_uom_qty": 1, "price_unit": product["price"]["amount"],
                    "tax_id": [[6, 0, []]]}])
            values["order_line"] = lines
            values["note"] = "Indicative quote from Rig. Retailer review required."
        # Validate all product/currency mappings before creating a partner.
        # Typed email proves no identity: reuse only this tenant/request's
        # unverified partner, including after a lost partner-create response.
        # Do not match the HTML notes field: Odoo may normalize its markup.
        partners = await execute("res.partner", "search", [[["ref", "=", reference]]],
                                 limit=2, context={"active_test": False})
        if len(partners) > 1:
            raise DeliveryError("odoo_partner_mapping")
        partner_id = partners[0] if partners else await execute("res.partner", "create", [{
            "name": contact["name"], "email": contact["email"], "ref": reference,
            "comment": "from Rig, not verified",
            **({"phone": contact["phone"]} if contact.get("phone") else {}),
        }])
        if not isinstance(partner_id, int) or isinstance(partner_id, bool) or partner_id <= 0:
            raise DeliveryError("odoo_partner_mapping")
        values["partner_id"] = partner_id
        order_id = await execute("sale.order", "create", [values])
        if not isinstance(order_id, int) or isinstance(order_id, bool) or order_id <= 0:
            raise DeliveryError("odoo_rejected")
        await supplier_note(order_id)


class EmailHandoff:
    """Use the stack's existing SMTP transport; delivery state belongs to PgQuotes."""

    async def send(self, email: str | None, quote: dict[str, Any]) -> None:
        from rigbox.reserve import SmtpMailer, reservation_letter

        try:
            mailer = SmtpMailer.from_env()
            if not mailer or not email:
                raise DeliveryError("not_configured")
            reference = quote["id"]
            letter = reservation_letter(reference, quote["payload"], quote.get("contact", {}), {"email": email})
            letter["subject"] = f"Quote request: {reference}"
            letter["text"] = "\n".join(f"Subject: {letter['subject']}" if line.startswith("Subject: ") else line
                                       for line in letter["text"].splitlines())
            # Link quotes have no product/setup yet. Keep the shopper's request.
            if quote["payload"].get("kind") == "link":
                letter["text"] += f"\nLink: {quote['payload']['url']}\nNote: {quote['payload'].get('note', '')}"
            letter["message_id"] = f"<{reference}@rig.tervory.com>"
            await mailer.send(letter)
        except DeliveryError:
            raise
        except Exception:
            # SMTP exceptions can contain recipients, credentials or remote text.
            raise DeliveryError("email_unavailable") from None


class RetailerHandoff:
    """Implements Service's existing sender interface, selected by exact tenant."""

    def __init__(self, http: Any) -> None:
        self.http = http

    async def send(self, *, tenant_id: str, email: str | None, webhook: str | None,
                   quote: dict[str, Any]) -> None:
        flow = flow_for(tenant_id)
        sender = flow.get("sender", "email" if email and not webhook else "webhook")
        if sender == "email":
            await EmailHandoff().send(email, quote)
            return
        if sender not in {"webhook", "odoo", "odoo+webhook"}:
            raise DeliveryError("configuration")
        if sender in {"odoo", "odoo+webhook"}:
            prefix = flow.get("env_prefix", "RIG_ODOO")
            if not isinstance(prefix, str) or not re.fullmatch(r"RIG_ODOO(?:_[A-Z0-9]+)*", prefix):
                raise DeliveryError("configuration")
            adapter = OdooHandoff(self.http, **{
                name: os.environ.get(prefix + suffix, "") for name, suffix in
                (("url", "_URL"), ("database", "_DATABASE"), ("user", "_USER"), ("api_key", "_API_KEY"))
            })
            await adapter.send(tenant_id=tenant_id, email=email, webhook=webhook, quote=quote)
        if sender in {"webhook", "odoo+webhook"}:
            if not webhook:
                raise DeliveryError("not_configured")
            try:
                response = await self.http.post(https_url(webhook),
                    json={"tenant_id": tenant_id, "quote": quote},
                    headers={"Idempotency-Key": f"rig:{tenant_id}:{quote['id']}"},
                    timeout=20, follow_redirects=False)
                response.raise_for_status()
            except DeliveryError:
                raise
            except Exception:
                raise DeliveryError("retailer_unavailable") from None

    def _odoo(self, tenant_id: str) -> OdooHandoff:
        flow = flow_for(tenant_id)
        if flow.get("sender") not in {"odoo", "odoo+webhook"}:
            raise DeliveryError("not_configured")
        prefix = flow.get("env_prefix", "RIG_ODOO")
        if not isinstance(prefix, str) or not re.fullmatch(r"RIG_ODOO(?:_[A-Z0-9]+)*", prefix):
            raise DeliveryError("configuration")
        return OdooHandoff(self.http, **{
            name: os.environ.get(prefix + suffix, "") for name, suffix in
            (("url", "_URL"), ("database", "_DATABASE"), ("user", "_USER"), ("api_key", "_API_KEY"))
        })

    async def place_located_order(self, *, tenant_id: str, quote_id: str, located: dict[str, Any],
                                  ship: dict[str, Any] | None = None) -> dict[str, Any]:
        sandbox_orders()
        return await self._odoo(tenant_id).place_located_order(tenant_id=tenant_id, quote_id=quote_id,
                                                               located=located, ship=ship)

    def portal(self, tenant_id: str) -> str | None:
        url = flow_for(tenant_id).get("portal_url")
        return https_url(url) if isinstance(url, str) and url else None
