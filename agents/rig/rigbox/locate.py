"""Approved supplier lookup. Private offers are never shopper products.

All persistence is tenant scoped. Matching and ranking use code only. An import
is a supplied catalogue snapshot, never a fetch, purchase or supplier order.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from rigbox.feeds.catalogue import map_catalogue
from rigbox.pricing import indicative_price, number, resolved_rule


def stamp(value: Any) -> datetime:
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Offer observation requires a timezone.")
    return result.astimezone(timezone.utc)


def norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def gtin(value: Any) -> str:
    value = str(value or "").strip()
    return value.zfill(14) if value.isdigit() and len(value) in (8, 12, 13, 14) else ""


def needs_supply(product: dict) -> bool:
    stock = (product.get("attributes") or {}).get("stock") or {}
    if product.get("active") is False:
        return product.get("supply_eligible") is True
    return stock.get("status") == "out_of_stock"


class SupplyStore:
    def __init__(self, store: Any):
        self.store = store
        self.pool = getattr(store, "pool", None)
        if self.pool is None and not hasattr(store, "supply_state"):
            store.supply_state = {}

    async def snapshot(self, tenant: str) -> tuple[list[dict], list[dict], list[dict]]:
        if self.pool is None:
            state = self.store.supply_state.get(str(tenant), {})
            return tuple(copy.deepcopy(state.get(key, [])) for key in ("sources", "offers", "maps"))
        async with self.pool.acquire() as conn:
            sources = await conn.fetch("SELECT * FROM agent_rig.supply_sources WHERE tenant_id=$1", UUID(str(tenant)))
            offers = await conn.fetch("SELECT * FROM agent_rig.supply_offers WHERE tenant_id=$1", UUID(str(tenant)))
            maps = await conn.fetch("SELECT * FROM agent_rig.supply_sku_map WHERE tenant_id=$1", UUID(str(tenant)))
        return [dict(row) for row in sources], [dict(row) for row in offers], [dict(row) for row in maps]

    async def source(self, tenant: str, source: dict) -> None:
        identity = str(source["id"]).strip()
        age = int(source["max_offer_age_seconds"])
        if not identity or age <= 0 or not isinstance(source.get("approved"), bool):
            raise ValueError("A source, explicit approval and maximum age are required.")
        row = {"id": identity, "approved": source["approved"], "priority": int(source.get("priority", 0)),
               "max_offer_age_seconds": age, "tenant_id": str(tenant)}
        if self.pool is None:
            state = self.store.supply_state.setdefault(str(tenant), {})
            state["sources"] = [s for s in state.get("sources", []) if s["id"] != identity] + [row]
            return
        async with self.pool.acquire() as conn:
            await conn.execute("""INSERT INTO agent_rig.supply_sources
                (tenant_id,id,approved,priority,max_offer_age_seconds) VALUES($1,$2,$3,$4,$5)
                ON CONFLICT(tenant_id,id) DO UPDATE SET approved=$3,priority=$4,max_offer_age_seconds=$5""",
                UUID(str(tenant)), identity, row["approved"], row["priority"], age)

    async def import_catalogue(self, tenant: str, source_id: str, record: dict, contents: str | bytes,
                               seen_at: Any) -> dict:
        sources, _, _ = await self.snapshot(tenant)
        if not any(s["id"] == source_id for s in sources):
            raise ValueError("Register this store's supplier first.")
        when = stamp(seen_at)
        if when > datetime.now(timezone.utc):
            raise ValueError("Observation cannot be in the future.")
        parsed = map_catalogue(record, contents)
        if parsed["rejected"]:
            return {"imported": 0, "rejected": parsed["rejected"]}
        offers = []
        for product in parsed["rows"]:
            qty = None if product["quantity"] is None else number(product["quantity"])
            offers.append({"tenant_id": str(tenant), "source_id": source_id, "sku": product["sku"],
                "gtin": product.get("gtin"), "brand": product["brand"], "mpn": product.get("mpn"),
                "quantity": qty, "status": "available" if product["active"] and qty is not None and qty > 0
                    else "unavailable" if qty == 0 or not product["active"] else "unknown",
                "eta": product["eta"], "ship_days": product["ship_days"], "region": product["region"],
                "cost": number(product["price"]), "currency": product["currency"], "seen_at": when})
        if self.pool is None:
            state = self.store.supply_state.setdefault(str(tenant), {})
            # Keep older rows as stale evidence, never invent absence observations.
            by_key = {(o["source_id"], o["sku"]): o for o in state.get("offers", [])}
            for row in offers:
                previous = by_key.get((source_id, row["sku"]))
                if previous is None or stamp(previous["seen_at"]) <= when:
                    by_key[(source_id, row["sku"])] = row
            state["offers"] = list(by_key.values())
        else:
            async with self.pool.acquire() as conn, conn.transaction():
                for o in offers:
                    await conn.execute("""INSERT INTO agent_rig.supply_offers
                        (tenant_id,source_id,sku,gtin,brand,mpn,quantity,status,eta,ship_days,region,cost,currency,seen_at)
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                        ON CONFLICT(tenant_id,source_id,sku) DO UPDATE SET
                        gtin=$4,brand=$5,mpn=$6,quantity=$7,status=$8,eta=$9,ship_days=$10,region=$11,cost=$12,currency=$13,seen_at=$14
                        WHERE agent_rig.supply_offers.seen_at <= EXCLUDED.seen_at""",
                        UUID(str(tenant)), *[o[k] for k in ("source_id", "sku", "gtin", "brand", "mpn", "quantity",
                            "status", "eta", "ship_days", "region", "cost", "currency", "seen_at")])
        return {"imported": len(offers), "rejected": []}

    async def map_sku(self, tenant: str, product_sku: str, source_id: str, offer_sku: str) -> None:
        _, offers, _ = await self.snapshot(tenant)
        if not any(o["source_id"] == source_id and o["sku"] == offer_sku for o in offers):
            raise ValueError("No such offer in this store.")
        if not any(p["sku"] == product_sku for p in await self.store.products(tenant)):
            raise ValueError("No such store product.")
        row = dict(tenant_id=str(tenant), product_sku=product_sku, source_id=source_id, offer_sku=offer_sku)
        if self.pool is None:
            rows = self.store.supply_state.setdefault(str(tenant), {}).setdefault("maps", [])
            if row not in rows:
                rows.append(row)
            return
        async with self.pool.acquire() as conn:
            await conn.execute("""INSERT INTO agent_rig.supply_sku_map(tenant_id,product_sku,source_id,offer_sku)
                VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING""", UUID(str(tenant)), product_sku, source_id, offer_sku)


async def locate(store: Any, tenant: str, product: dict, *, now: datetime | None = None,
                 snapshot: tuple | None = None) -> dict:
    """Return separate public and store-only projections; no supplier data in public."""
    sources, offers, maps = snapshot if snapshot is not None else await SupplyStore(store).snapshot(tenant)
    approved = {s["id"]: s for s in sources if s.get("approved") is True and str(s.get("tenant_id")) == str(tenant)}
    offers = [o for o in offers if str(o.get("tenant_id")) == str(tenant) and o["source_id"] in approved]
    match = []
    code = gtin(product.get("gtin"))
    if code:
        match = [o for o in offers if gtin(o.get("gtin")) == code]
    if not match and norm(product.get("brand")) and norm(product.get("mpn")):
        match = [o for o in offers if norm(o.get("brand")) == norm(product["brand"])
                 and norm(o.get("mpn")) == norm(product["mpn"])]
    if not match:
        mapped = {(m["source_id"], m["offer_sku"]) for m in maps
                  if str(m.get("tenant_id")) == str(tenant) and m["product_sku"] == product["sku"]}
        match = [o for o in offers if (o["source_id"], o["sku"]) in mapped]
    moment = now or datetime.now(timezone.utc)
    ranked, stale = [], False
    settings = await store.rule(tenant) if match else None
    for offer in match:
        age = (moment - stamp(offer["seen_at"])).total_seconds()
        if age < 0 or age > approved[offer["source_id"]]["max_offer_age_seconds"]:
            stale = True
            continue
        if offer["status"] != "available" or offer.get("quantity") is None or number(offer["quantity"]) < 1:
            continue
        # No guessed FX or pricing. Reuse the store's confirmed price rule.
        try:
            rule = resolved_rule(settings, {"provider": offer["source_id"], "site": "", "country": offer["region"]})
            rate = await store.rate(tenant, offer["currency"], product["currency"])
            amount = indicative_price(offer["cost"], rule, rate)
            landed = indicative_price(offer["cost"], {**rule, "margin_percent": 0}, rate)
        except (ValueError, TypeError):
            continue
        ranked.append(((landed, offer["ship_days"] if offer["ship_days"] is not None else Decimal("Infinity"),
                        approved[offer["source_id"]]["priority"], offer["source_id"], offer["sku"]), offer, amount))
    if not ranked:
        return {"public": {"status": "check_with_store" if stale else "unavailable"}}
    _, offer, amount = min(ranked, key=lambda item: item[0])
    public = {"status": "available_to_order", "eta": offer.get("eta"),
              "price": {"amount": str(amount), "currency": product["currency"]}}
    private = {key: (value.isoformat() if isinstance(value, datetime) else str(value) if isinstance(value, Decimal) else value)
               for key, value in offer.items() if key != "tenant_id"}
    return {"public": public, "store": private}


async def catalogue(store: Any, tenant: str) -> list[dict]:
    """Resolve only unavailable store products; preserve store identity and fit rules."""
    products = await store.products(tenant)
    snapshot = await SupplyStore(store).snapshot(tenant)
    if not snapshot[0]:
        return products
    resolved = []
    for original in products:
        row = copy.deepcopy(original)
        if needs_supply(row):
            result = await locate(store, tenant, row, snapshot=snapshot)
            row["availability"] = result["public"]
            if result["public"]["status"] == "available_to_order":
                row["active"] = True
                row["price"] = result["public"]["price"]["amount"]
                # The status remains distinct from stock held by the store.
                row.setdefault("attributes", {})["stock"] = {"status": "available_to_order"}
        resolved.append(row)
    return resolved
