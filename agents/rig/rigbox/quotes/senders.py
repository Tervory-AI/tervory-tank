"""Tenant-selected senders. Configuration and credentials never reach shoppers.

Odoo uses its documented external JSON-RPC API (common.authenticate and
object.execute_kw). Only draft sale.order records are created: never confirm,
invoice, take payment or send mail. client_order_ref reconciles a timed-out call.
"""

from __future__ import annotations

import json
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


def flow_for(tenant_id: str) -> dict[str, Any]:
    try:
        flows = json.loads(os.environ.get("RIG_QUOTE_FLOWS") or "{}")
        flow = flows.get(str(tenant_id), {})
        if not isinstance(flow, dict):
            raise ValueError
        return flow
    except (ValueError, AttributeError):
        raise DeliveryError("configuration") from None


class OdooHandoff:
    def __init__(self, http: Any, *, url: str, database: str, user: str, api_key: str) -> None:
        if not all((url, database, user, api_key)):
            raise DeliveryError("not_configured")
        self.http = http
        self.url = https_url(url) + "/jsonrpc"
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

    async def send(self, *, tenant_id: str, email: str | None, webhook: str | None,
                   quote: dict[str, Any]) -> None:
        del email, webhook
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

        reference = f"rig:{tenant_id}:{quote['id']}"
        existing = await execute("sale.order", "search", [[['client_order_ref', '=', reference]]], limit=1)
        if existing:
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

    def portal(self, tenant_id: str) -> str | None:
        url = flow_for(tenant_id).get("portal_url")
        return https_url(url) if isinstance(url, str) and url else None
