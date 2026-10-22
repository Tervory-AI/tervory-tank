"""RIG-4 additions isolated from catalogue, feed and ranking work."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from rigbox.logic import fitting_parts
from rigbox.service import RigError, Service, _contact

from .senders import DeliveryError


class QuoteService(Service):
    def __init__(self, store: Any, models: Any, handoff: Any, quotes: Any) -> None:
        super().__init__(store, models, handoff)
        self.quote_store = quotes

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

    async def quote(self, tenant_id: str, body: dict[str, Any]) -> dict[str, Any]:
        if isinstance(body.get("setup"), dict):
            await self.validate_setup(tenant_id, body["setup"])
        return await super().quote(tenant_id, body)

    async def link_quote(self, tenant_id: str, url: str, note: str,
                         contact: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            parsed = urlsplit(url.strip())
        except ValueError:
            raise RigError("invalid", "That link is not a web address.", 422) from None
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or len(url) > 2048 or len(note) > 4000):
            raise RigError("invalid", "That link is not a web address.", 422)
        return await self._store_quote(tenant_id,
            {"kind": "link", "url": parsed.geturl(), "note": note.strip()},
            _contact(contact) if contact else {})

    async def _store_quote(self, tenant_id: str, payload: dict[str, Any],
                           contact: dict[str, Any]) -> dict[str, Any]:
        quote_id = "req_" + uuid4().hex
        await self.quote_store.create(tenant_id, {"id": quote_id, "payload": payload, "contact": contact})
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
