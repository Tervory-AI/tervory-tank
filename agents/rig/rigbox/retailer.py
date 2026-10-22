"""Retailer operations behind Tank's authenticated, tenant-scoped corridor."""

import json
import re
from uuid import uuid4
from typing import Any

from rigbox.catalogue import _product_row, check_fit_refs, families_from
from rigbox.feeds import pull
from rigbox.pricing import indicative_price, number, price_rule
from rigbox.service import RigError, Service


def templates(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict) or len(value) > 30:
        raise ValueError("Choose at most 30 category templates.")
    result = {}
    for category, roles in value.items():
        if not isinstance(category, str) or not category.strip() or len(category) > 80 or not isinstance(roles, dict) or len(roles) > 12:
            raise ValueError("Check the category and its roles.")
        if any(not isinstance(k, str) or not isinstance(v, str) or not k.strip() or not v.strip() or max(len(k), len(v)) > 80 for k, v in roles.items()):
            raise ValueError("Every role needs a product category.")
        result[category.strip()] = {k.strip(): v.strip() for k, v in roles.items()}
    return result


def map_import(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if data.get("parse_error"):
        raise ValueError("The source file could not be read.")
    provider = data["provider"]
    metadata = {}
    if provider in {"shopify", "woocommerce", "google"}:
        raw = data["contents"]
        mapped = pull({"format": provider, "currency": data.get("currency", "")}, raw)
        if provider != "google":
            loaded = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(loaded, dict):
                metadata = loaded.get("rig") or {}
    else:
        rows = []
        rejected = []
        for index, row in enumerate(data.get("rows", []), 1):
            try:
                # ACCESS-1 already validated supplier amounts and identifiers.
                values = {key: str(row.get(key) or "") for key in ("sku", "name", "brand", "category", "image_url", "url", "family")}
                values.update(price=str(row.get("price", "")), currency=data.get("currency", "USD"),
                              gtin=str(row.get("upc") or ""), active="true" if number(row.get("quantity") or 0) > 0 else "false")
                rows.append(_product_row(values, index))
            except ValueError:
                rejected.append({"row": index, "reason": "Check the product columns and supplier amount."})
        mapped = {"rows": rows if not rejected else [], "rejected": rejected}
        metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("Feed metadata must be an object.")
    if not mapped["rows"] and not mapped["rejected"]:
        raise ValueError("The file has no products.")
    return mapped, metadata


class Retailer:
    def __init__(self, service: Service) -> None:
        self.service = service
        self.store = service.store

    async def panel(self, tenant: str) -> dict[str, Any]:
        return {
            "price_configured": bool(await self.store.rule(tenant)),
            "currency": "ZAR",
            "templates": await self.store.templates_for(tenant),
            "fits": (await self.service.suggested_fits(tenant))["fits"],
            "missed_searches": await self.store.missed_searches(tenant),
            "receipts": await self.store.receipts(tenant),
            "products": len(await self.store.products(tenant)),
        }

    async def reprice(self, store: Any, tenant: str) -> None:
        rule = await store.rule(tenant)
        for row in await store.costs(tenant):
            amount = indicative_price(row["cost"], rule or {}, await store.rate(tenant, row["currency"]))
            await store.update_price(tenant, row["sku"], {"price": amount, "currency": "ZAR"})

    async def set_rule(self, tenant: str, data: dict[str, Any]) -> dict[str, bool]:
        rule = price_rule(data)
        async with self.store.atomic(tenant) as store:
            await store.save_rule(tenant, rule)
            await self.reprice(store, tenant)
        return {"saved": True, "price_configured": True}

    async def set_rate(self, tenant: str, data: dict[str, Any], founder: bool = False) -> dict[str, bool]:
        if not founder:
            raise RigError("forbidden", "Only the founder can set an exchange rate.", 403)
        code = str(data.get("currency", "")).upper()
        rate = number(data.get("rate"), maximum="1000000")
        if not re.fullmatch("[A-Z]{3}", code) or not rate or (code == "ZAR" and rate != 1):
            raise ValueError("Use a currency code and a positive rate to ZAR.")
        async with self.store.atomic(tenant) as store:
            await store.save_rate(tenant, code, rate)
            await self.reprice(store, tenant)
        return {"saved": True}

    async def set_templates(self, tenant: str, data: dict[str, Any]) -> dict[str, bool]:
        values = templates(data)
        async with self.store.atomic(tenant) as store:
            for category, roles in values.items():
                await store.set_template(tenant, category, roles)
        return {"saved": True}

    async def import_file(self, tenant: str, data: dict[str, Any]) -> dict[str, Any]:
        receipt = {"id": str(uuid4()), "provider": data["provider"], "site": data["site"], "added": 0, "updated": 0, "rejected": 0}
        problems = []
        try:
            mapped, metadata = map_import(data)
            problems = mapped["rejected"]
            if problems:
                raise ValueError("The file contains invalid products.")
            defaults = templates(metadata.get("setup_templates", {}))
            async with self.store.atomic(tenant) as store:
                rule = await store.rule(tenant)
                if rule is None:
                    raise ValueError("Set the private price rule before importing.")
                existing = {row["sku"]: row for row in await store.products(tenant)}
                combined = {**existing, **{row["sku"]: row for row in mapped["rows"]}}
                families = metadata.get("families", {})
                if not isinstance(families, dict) or len(families) > 5000:
                    raise ValueError("Check the feed's families.")
                for family, members in families.items():
                    if not isinstance(family, str) or not family or len(family) > 120 or not isinstance(members, list) or any(sku not in combined for sku in members):
                        raise ValueError("Every family member must be in this catalogue.")
                    for sku in members:
                        combined[sku] = {**combined[sku], "family": family}
                fits = metadata.get("fits", [])
                if not isinstance(fits, list) or len(fits) > 50000:
                    raise ValueError("Check the supplied fits.")
                checked = []
                for row in fits:
                    if not isinstance(row, dict) or not row.get("part_sku") or bool(row.get("fits_sku")) == bool(row.get("fits_family")):
                        raise ValueError("Each fit needs a part and exactly one target.")
                    note = str(row.get("note", "")).strip()
                    if not note or len(note) > 2000:
                        raise ValueError("Each supplied fit needs evidence for review.")
                    checked.append({"part_sku": row["part_sku"], "fits_sku": row.get("fits_sku"), "fits_family": row.get("fits_family"),
                                    "note": note, "source": "suggested", "approved": False, "confidence": None, "rule": {}, "row": 0})
                if check_fit_refs(checked, set(combined), set(families_from(list(combined.values())))):
                    raise ValueError("A supplied fit refers to an unknown product or family.")
                for row in mapped["rows"]:
                    sku = row["sku"]
                    # Source amounts exist only in the private cost table.
                    cost = {"sku": sku, "cost": row["price"], "currency": row["currency"], "provider": data["provider"], "site": data["site"]}
                    amount = indicative_price(cost["cost"], rule, await store.rate(tenant, cost["currency"]))
                    public = {**combined[sku], "price": amount, "currency": "ZAR", "attributes": {}}
                    action = await store.upsert_product(tenant, public)
                    receipt[action] += 1
                    await store.save_cost(tenant, cost)
                imported_skus = {row["sku"] for row in mapped["rows"]}
                for sku, row in combined.items():
                    if sku not in imported_skus and sku in existing and existing[sku].get("family") != row.get("family"):
                        await store.upsert_product(tenant, row)
                next_families = families_from(list(combined.values()))
                for family in set(families_from(list(existing.values()))) | set(next_families):
                    await store.set_family(tenant, family, next_families.get(family, []))
                current_templates = await store.templates_for(tenant)
                for category, roles in defaults.items():
                    if category not in current_templates:
                        await store.set_template(tenant, category, roles)
                # A refresh must not overwrite a human approval or rejection.
                reviewed = {(r["part_sku"], r.get("fits_sku") or "", r.get("fits_family") or "") for r in await store.fits(tenant)
                            if r.get("approved") or r.get("source") == "rejected"}
                for row in checked:
                    if (row["part_sku"], row.get("fits_sku") or "", row.get("fits_family") or "") not in reviewed:
                        await store.upsert_fit(tenant, row)
                await store.save_feed_receipt(tenant, receipt)
        except (ValueError, TypeError, KeyError):
            receipt.update(added=0, updated=0, rejected=max(1, len(problems)))
            await self.store.save_feed_receipt(tenant, receipt)
            return {"receipt": receipt, "ok": False, "message": "Nothing was imported. Check the file, private price rule and founder-set exchange rate."}
        result = {"receipt": receipt, "ok": True}
        if not metadata.get("fits"):
            if self.service.models is None:
                result["suggestions"] = "unavailable"
            else:
                try:
                    await self.service.suggest(tenant)
                    result["suggestions"] = "awaiting_review"
                except Exception:
                    # The import is committed and receipted. A model outage is
                    # reported separately and never changes approval status.
                    result["suggestions"] = "unavailable"
        return result
