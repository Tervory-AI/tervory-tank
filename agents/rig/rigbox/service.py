"""Shopper calls. The store is always read and written for one tenant."""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4
from urllib.parse import urlparse

from rigbox.catalogue import (
    check_fit_refs,
    families_from,
    load_folder,
    map_google_merchant,
    map_shopify,
    map_woocommerce,
    price_patch,
)
from rigbox.ground import ask as ground_ask
from rigbox.ground import ask_prompt
from rigbox.ground import explain as ground_explain
from rigbox.ground import explain_prompt
from rigbox.ground import fit_suggest
from rigbox.ground import in_catalogue
from rigbox.ground import suggest_prompt
from rigbox.logic import approved
from rigbox.logic import graph as build_graph
from rigbox.logic import options_for
from rigbox.logic import product_detail
from rigbox.logic import public_product
from rigbox.logic import reprice
from rigbox.logic import search as rank
from rigbox.logic import setups as build_setups
from rigbox.store import _fit_key

_KEY = re.compile(r"^rk_pub_[A-Za-z0-9][A-Za-z0-9_-]{0,80}$")
_MAPS = {
    "shopify": map_shopify,
    "woocommerce": map_woocommerce,
    "google": map_google_merchant,
}


class RigError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class RateLimiter:
    def __init__(self, limit: int = 60, window: float = 60) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}

    def allow(self, key_hash: str, now: float | None = None) -> bool:
        moment = time.monotonic() if now is None else now
        hits = [item for item in self._hits.get(key_hash, []) if moment - item < self.window]
        if len(hits) >= self.limit:
            self._hits[key_hash] = hits
            return False
        hits.append(moment)
        self._hits[key_hash] = hits
        return True


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RecordingHandoff:
    """Test double. It records the handoff and does not send mail."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(
        self,
        *,
        tenant_id: str,
        email: str | None,
        webhook: str | None,
        quote: dict[str, Any],
    ) -> None:
        self.sent.append(
            {"tenant_id": tenant_id, "email": email, "webhook": webhook, "quote": quote}
        )


class WebhookHandoff:
    """Posts the quote to the retailer's webhook. Email stays on the stored quote."""

    def __init__(self, http: Any) -> None:
        self.http = http

    async def send(
        self,
        *,
        tenant_id: str,
        email: str | None,
        webhook: str | None,
        quote: dict[str, Any],
    ) -> None:
        del email
        if not webhook or self.http is None:
            return
        await self.http.post(webhook, json={"tenant_id": tenant_id, "quote": quote})


class Service:
    def __init__(
        self,
        store: Any,
        models: Any | None = None,
        handoff: Any | None = None,
        *,
        rate_limit: int = 60,
    ) -> None:
        self.store = store
        self.models = models
        self.handoff = handoff or RecordingHandoff()
        self.limiter = RateLimiter(limit=rate_limit)

    async def authenticate(self, raw_key: str) -> dict[str, Any]:
        presented = raw_key or ""
        digest = hash_key(presented)
        if not self.limiter.allow(digest):
            raise RigError("rate_limit", "Too many requests. Try again in a minute.", 429)
        if _KEY.fullmatch(presented) is None:
            raise RigError("unauthorized", "That key is not valid.", 401)
        row = await self.store.key(digest)
        if row is None or row.get("kind") != "publishable":
            raise RigError("unauthorized", "That key is not valid.", 401)
        return row

    async def search(self, tenant_id: str, query: str, limit: int | None) -> dict[str, Any]:
        text = (query or "").strip()
        if not text:
            return {"results": []}
        finder = getattr(self.store, "search_rows", None)
        if finder is not None:
            rows = await finder(tenant_id, text, _limit(limit))
            return {"results": [public_product(row) for row in rows]}
        ranked = rank(
            {
                "tenant_id": tenant_id,
                "q": text,
                "limit": limit,
                "products": await self.store.products(tenant_id),
            }
        )
        return {"results": ranked["results"]}

    async def product(self, tenant_id: str, product_id: str) -> dict[str, Any]:
        detail = product_detail(await self._bundle(tenant_id, product_id))
        if detail is None:
            raise RigError("not_found", "No such product.", 404)
        return detail

    async def setups(self, tenant_id: str, product_id: str) -> dict[str, Any]:
        bundle = await self._bundle(tenant_id, product_id)
        if product_detail(bundle) is None:
            raise RigError("not_found", "No such product.", 404)
        built = build_setups(bundle)
        for setup in built["setups"]:
            setup["why"] = await self._explain(tenant_id, setup)
        return {"setups": built["setups"]}

    async def swap(self, tenant_id: str, setup: dict[str, Any], role: str) -> dict[str, Any]:
        products = await self._active(tenant_id)
        fits = await self._approved_fits(tenant_id)
        try:
            priced = reprice(setup, products)
        except KeyError:
            raise RigError("invalid", "That setup is not in this catalogue.", 422) from None
        return {
            "options": options_for({"role": role, "setup": priced, "products": products, "fits": fits}),
            "setup": priced,
        }

    async def graph(self, tenant_id: str, product_id: str) -> dict[str, Any]:
        built = build_graph(await self._bundle(tenant_id, product_id))
        if built is None:
            raise RigError("not_found", "No such product.", 404)
        return built

    async def ask(
        self,
        tenant_id: str,
        product_id: str,
        question: str,
        setup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not str(question or "").strip():
            raise RigError("invalid", "Ask a question about this catalogue.", 422)
        if product_detail(await self._bundle(tenant_id, product_id)) is None:
            raise RigError("not_found", "No such product.", 404)
        products = [public_product(row) for row in await self._active(tenant_id)]
        fits = await self._approved_fits(tenant_id)
        payload = {"question": question, "products": products, "fits": fits, "product_id": product_id, "setup": setup}
        if not in_catalogue(question, products, fits):
            return {"answer": "I don't know", "cites": []}
        if self.models is None:
            return {"answer": "I don't know", "cites": []}
        text = await self.models.complete(
            tenant_id,
            "rig.ask",
            [{"role": "user", "content": ask_prompt(payload)}],
        )
        return ground_ask(payload, text)

    async def link_quote(self, tenant_id: str, url: str, note: str) -> dict[str, str]:
        parsed = urlparse(str(url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RigError("invalid", "That link is not a web address.", 422)
        return await self._store_quote(
            tenant_id,
            {"kind": "link", "url": parsed.geturl(), "note": str(note or "").strip()},
            {},
        )

    async def quote(self, tenant_id: str, body: dict[str, Any]) -> dict[str, str]:
        contact = _contact(body.get("contact") or {})
        if isinstance(body.get("setup"), dict):
            products = await self._active(tenant_id)
            try:
                priced = reprice(body["setup"], products)
            except KeyError:
                raise RigError("invalid", "That setup is not in this catalogue.", 422) from None
            payload: dict[str, Any] = {"kind": "setup", "setup": priced}
        elif body.get("product_id"):
            payload = {"kind": "product", "product": await self.product(tenant_id, str(body["product_id"]))}
        else:
            raise RigError("invalid", "A setup or a product is required.", 422)
        return await self._store_quote(tenant_id, payload, contact)

    async def suggest(self, tenant_id: str) -> dict[str, Any]:
        if self.models is None:
            return {"fits": []}
        slim = [
            {
                "id": row["sku"],
                "sku": row["sku"],
                "name": row["name"],
                "family": row.get("family") or "",
                "attributes": row.get("attributes") or {},
            }
            for row in await self._active(tenant_id)
        ]
        text = await self.models.complete(
            tenant_id,
            "rig.fit_suggest",
            [{"role": "user", "content": suggest_prompt({"products": slim})}],
        )
        suggested = fit_suggest({"products": slim}, text)
        for row in suggested["fits"]:
            await self.store.upsert_fit(tenant_id, row)
        return suggested

    async def approve(self, tenant_id: str, part_sku: str, fits_sku: str | None, fits_family: str | None) -> bool:
        return await self.store.approve_fit(tenant_id, part_sku, fits_sku, fits_family)

    async def apply_watch(self, tenant_id: str, sku: str, update: dict[str, Any]) -> bool:
        patch = price_patch(update)
        if not patch:
            return False
        return await self.store.update_price(tenant_id, sku, patch)

    async def load_catalogues(self, root: Path) -> list[dict[str, Any]]:
        if not root.is_dir():
            return []
        reports = []
        for folder in sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")):
            reports.append(await self.load_folder(folder))
        return reports

    async def load_folder(self, folder: Path) -> dict[str, Any]:
        loaded = load_folder(folder)
        tenant = loaded["tenant_id"]
        report: dict[str, Any] = {"slug": loaded["slug"], "tenant_id": tenant, "products": {}, "fits": {}}
        if not tenant:
            reason = loaded["publish_error"] or "no tenant"
            report["products"] = {"added": 0, "updated": 0, "rejected": [{"row": 0, "reason": reason}]}
            report["fits"] = {"added": 0, "updated": 0, "rejected": []}
            return report
        products = loaded["products"]
        if products["rejected"]:
            report["products"] = {"added": 0, "updated": 0, "rejected": products["rejected"]}
        else:
            added = updated = 0
            for row in products["rows"]:
                action = await self.store.upsert_product(tenant, row)
                if action == "added":
                    added += 1
                else:
                    updated += 1
            report["products"] = {"added": added, "updated": updated, "rejected": []}
            for family, members in families_from(await self.store.products(tenant)).items():
                await self.store.set_family(tenant, family, members)
        if not loaded["publish_error"]:
            await self._apply_publish(tenant, loaded["slug"], loaded["publish"], report)
        fits = loaded["fits"]
        if fits["rejected"]:
            report["fits"] = {"added": 0, "updated": 0, "rejected": fits["rejected"]}
            return report
        known = {str(row["sku"]) for row in await self.store.products(tenant)}
        family_names = set(families_from(await self.store.products(tenant)))
        ref_errors = check_fit_refs(fits["rows"], known, family_names)
        if ref_errors:
            report["fits"] = {"added": 0, "updated": 0, "rejected": ref_errors}
            return report
        existing = {_fit_key(row) for row in await self.store.fits(tenant)}
        added = updated = 0
        for row in fits["rows"]:
            if _fit_key(row) in existing:
                updated += 1
            else:
                added += 1
            await self.store.upsert_fit(tenant, row)
        report["fits"] = {"added": added, "updated": updated, "rejected": []}
        return report

    async def pull_feeds(self, tenant_id: str, fetch: Any) -> list[dict[str, Any]]:
        reports = []
        for feed in await self.store.feeds_for(tenant_id):
            fmt = str(feed.get("format") or "")
            mapper = _MAPS.get(fmt)
            if mapper is None:
                reports.append(
                    {"format": fmt, "added": 0, "updated": 0, "rejected": [{"row": 0, "reason": "unknown feed format"}]}
                )
                continue
            body = await fetch(str(feed["url"]))
            if fmt == "google":
                mapped = mapper(body if isinstance(body, str) else str(body))
            else:
                mapped = mapper(body, str(feed.get("currency") or ""))
            if any(item.get("row") == 0 for item in mapped["rejected"]):
                reports.append({"format": fmt, "added": 0, "updated": 0, "rejected": mapped["rejected"]})
                continue
            added = updated = 0
            for row in mapped["rows"]:
                action = await self.store.upsert_product(tenant_id, row)
                if action == "added":
                    added += 1
                else:
                    updated += 1
            reports.append({"format": fmt, "added": added, "updated": updated, "rejected": mapped["rejected"]})
        return reports

    async def _bundle(self, tenant_id: str, product_id: str) -> dict[str, Any]:
        return {
            "tenant_id": tenant_id,
            "product_id": product_id,
            "products": await self._active(tenant_id),
            "fits": await self._approved_fits(tenant_id),
            "templates": await self.store.templates_for(tenant_id),
        }

    async def _active(self, tenant_id: str) -> list[dict[str, Any]]:
        return [row for row in await self.store.products(tenant_id) if row.get("active", True)]

    async def _approved_fits(self, tenant_id: str) -> list[dict[str, Any]]:
        return [row for row in await self.store.fits(tenant_id) if approved(row)]

    async def _explain(self, tenant_id: str, setup: dict[str, Any]) -> list[str]:
        fallback = list(setup.get("why") or [])
        if self.models is None:
            return fallback
        material = [
            {"role": part["role"], "id": part["product"]["id"], "name": part["product"]["name"]}
            for part in setup.get("parts") or []
        ]
        try:
            text = await self.models.complete(
                tenant_id,
                "rig.explain",
                [{"role": "user", "content": explain_prompt({"material": material})}],
            )
        except Exception:  # noqa: BLE001 — a model outage keeps the rule lines
            return fallback
        why = ground_explain({"fallback_why": fallback}, text)["why"]
        return why or fallback

    async def _apply_publish(self, tenant_id: str, slug: str, publish: dict[str, Any], report: dict[str, Any]) -> None:
        keys = publish.get("keys") if isinstance(publish.get("keys"), list) else []
        parsed: list[tuple[str, list[str]]] = []
        rejected: list[dict[str, Any]] = []
        for index, item in enumerate(keys, start=1):
            if not isinstance(item, dict):
                rejected.append({"row": index, "reason": "key must start with rk_pub_ and list origins"})
                continue
            raw = str(item.get("key") or "")
            origins = item.get("origins")
            if _KEY.fullmatch(raw) is None or not isinstance(origins, list) or not origins:
                rejected.append({"row": index, "reason": "key must start with rk_pub_ and list origins"})
                continue
            parsed.append((raw, [str(origin) for origin in origins]))
        if rejected:
            report["keys_rejected"] = rejected
        else:
            for raw, origins in parsed:
                await self.store.put_key(tenant_id, hash_key(raw), "publishable", origins)
            report["keys"] = len(parsed)
        email = publish.get("email")
        webhook = publish.get("webhook")
        await self.store.put_retailer(
            tenant_id,
            slug,
            str(email) if email else None,
            str(webhook) if webhook else None,
        )
        templates = publish.get("setup_templates")
        if isinstance(templates, dict):
            for category, roles in templates.items():
                await self.store.set_template(tenant_id, str(category), roles)
        feed = publish.get("feed")
        if isinstance(feed, dict) and feed.get("url") and feed.get("format"):
            await self.store.put_feed(
                tenant_id,
                str(feed["format"]),
                str(feed["url"]),
                str(feed.get("currency") or ""),
            )

    async def _store_quote(self, tenant_id: str, payload: dict[str, Any], contact: dict[str, Any]) -> dict[str, str]:
        quote_id = "req_" + uuid4().hex
        await self.store.add_quote(tenant_id, quote_id, payload, contact)
        retailer = await self.store.retailer(tenant_id) or {}
        try:
            await self.handoff.send(
                tenant_id=tenant_id,
                email=retailer.get("email"),
                webhook=retailer.get("webhook"),
                quote={"id": quote_id, "payload": payload, "contact": contact},
            )
        except Exception:  # noqa: BLE001 — the quote is stored even if the handoff fails
            return {"request_id": quote_id}
        await self.store.mark_sent(tenant_id, quote_id)
        return {"request_id": quote_id}


def _contact(contact: dict[str, Any]) -> dict[str, str]:
    name = str(contact.get("name") or "").strip()
    email = str(contact.get("email") or "").strip()
    domain = email.split("@")[-1] if "@" in email else ""
    if not name or "@" not in email or "." not in domain:
        raise RigError("invalid", "A name and email are required.", 422)
    out = {"name": name, "email": email}
    phone = str(contact.get("phone") or "").strip()
    if phone:
        out["phone"] = phone
    return out


def _limit(value: int | None) -> int:
    try:
        number = int(value if value is not None else 12)
    except (TypeError, ValueError):
        number = 12
    return max(1, min(number, 50))

