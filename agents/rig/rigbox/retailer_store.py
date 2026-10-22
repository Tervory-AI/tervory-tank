"""RIG-3 persistence. Private pricing never joins a public product query."""

import copy
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID
from typing import Any
from collections.abc import AsyncIterator


class ConnectionPool:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[Any]:
        yield self.conn


class RetailerMemoryStore:
    def _retailer_state(self) -> None:
        if not hasattr(self, "private_rules"):
            self.private_rules = {}
            self.private_rates = {}
            self.private_costs = {}
            self.feed_receipts = []

    @asynccontextmanager
    async def atomic(self, tenant_id: str) -> AsyncIterator[Any]:
        self._retailer_state()
        saved = copy.deepcopy(self.__dict__)
        try:
            yield self
        except BaseException:
            self.__dict__.clear()
            self.__dict__.update(saved)
            raise

    async def rule(self, tenant_id: str) -> dict[str, Any] | None:
        self._retailer_state()
        return self.private_rules.get(str(tenant_id))

    async def save_rule(self, tenant_id: str, rule: dict[str, Any]) -> None:
        self._retailer_state()
        self.private_rules[str(tenant_id)] = dict(rule)

    async def rate(self, tenant_id: str, currency: str) -> Any:
        self._retailer_state()
        return "1" if currency == "ZAR" else self.private_rates.get((str(tenant_id), currency))

    async def save_rate(self, tenant_id: str, currency: str, rate: Any) -> None:
        self._retailer_state()
        self.private_rates[(str(tenant_id), currency)] = str(rate)

    async def costs(self, tenant_id: str) -> list[dict[str, Any]]:
        self._retailer_state()
        return [dict(row) for (tenant, _), row in self.private_costs.items() if tenant == str(tenant_id)]

    async def save_cost(self, tenant_id: str, row: dict[str, Any]) -> None:
        self._retailer_state()
        self.private_costs[(str(tenant_id), row["sku"])] = dict(row)

    async def is_feed_product(self, tenant_id: str, sku: str) -> bool:
        self._retailer_state()
        return (str(tenant_id), sku) in self.private_costs

    async def save_feed_receipt(self, tenant_id: str, receipt: dict[str, Any]) -> None:
        self._retailer_state()
        self.feed_receipts.append({**receipt, "tenant_id": str(tenant_id), "created_at": datetime.now(timezone.utc).isoformat()})

    async def receipts(self, tenant_id: str) -> list[dict[str, Any]]:
        self._retailer_state()
        return [{k: v for k, v in row.items() if k != "tenant_id"} for row in reversed(self.feed_receipts) if row["tenant_id"] == str(tenant_id)][:30]

    async def missed_searches(self, tenant_id: str) -> list[dict[str, Any]]:
        counts = {}
        for row in self.searches:
            if row["tenant_id"] == str(tenant_id) and (not row.get("ids") or not row.get("exact_match", True)):
                counts[row["query"]] = counts.get(row["query"], 0) + 1
        return [{"query": q, "count": n} for q, n in sorted(counts.items(), key=lambda item: -item[1])[:50]]


class RetailerPgStore:
    @asynccontextmanager
    async def atomic(self, tenant_id: str) -> AsyncIterator[Any]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Serializes imports, rule changes and reviews for one tenant only.
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", "rig-retailer:" + str(tenant_id))
                yield type(self)(ConnectionPool(conn))

    async def rule(self, tenant_id: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            raw = await conn.fetchval("SELECT rule FROM agent_rig.price_rules WHERE tenant_id=$1", UUID(str(tenant_id)))
        return json.loads(raw) if isinstance(raw, str) else raw

    async def save_rule(self, tenant_id: str, rule: dict[str, Any]) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("""INSERT INTO agent_rig.price_rules(tenant_id,rule) VALUES($1,$2::jsonb)
                ON CONFLICT(tenant_id) DO UPDATE SET rule=EXCLUDED.rule,updated_at=now()""", UUID(str(tenant_id)), json.dumps(rule))

    async def rate(self, tenant_id: str, currency: str) -> Any:
        if currency == "ZAR":
            return "1"
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT rate FROM agent_rig.exchange_rates WHERE tenant_id=$1 AND currency=$2", UUID(str(tenant_id)), currency)

    async def save_rate(self, tenant_id: str, currency: str, rate: Any) -> None:
        from decimal import Decimal
        async with self.pool.acquire() as conn:
            await conn.execute("""INSERT INTO agent_rig.exchange_rates(tenant_id,currency,rate) VALUES($1,$2,$3)
                ON CONFLICT(tenant_id,currency) DO UPDATE SET rate=EXCLUDED.rate,updated_at=now()""", UUID(str(tenant_id)), currency, Decimal(str(rate)))

    async def costs(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT sku,cost,currency,provider,site FROM agent_rig.supplier_costs WHERE tenant_id=$1", UUID(str(tenant_id)))
        return [dict(row) for row in rows]

    async def save_cost(self, tenant_id: str, row: dict[str, Any]) -> None:
        from decimal import Decimal
        async with self.pool.acquire() as conn:
            await conn.execute("""INSERT INTO agent_rig.supplier_costs(tenant_id,sku,cost,currency,provider,site)
                VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(tenant_id,sku) DO UPDATE SET
                cost=EXCLUDED.cost,currency=EXCLUDED.currency,provider=EXCLUDED.provider,site=EXCLUDED.site,updated_at=now()""",
                UUID(str(tenant_id)), row["sku"], Decimal(str(row["cost"])), row["currency"], row["provider"], row["site"])

    async def is_feed_product(self, tenant_id: str, sku: str) -> bool:
        async with self.pool.acquire() as conn:
            return bool(await conn.fetchval("SELECT 1 FROM agent_rig.supplier_costs WHERE tenant_id=$1 AND sku=$2", UUID(str(tenant_id)), sku))

    async def save_feed_receipt(self, tenant_id: str, receipt: dict[str, Any]) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("""INSERT INTO agent_rig.feed_receipts(tenant_id,id,provider,site,added,updated,rejected)
                VALUES($1,$2,$3,$4,$5,$6,$7)""", UUID(str(tenant_id)), UUID(receipt["id"]), receipt["provider"], receipt["site"],
                receipt["added"], receipt["updated"], receipt["rejected"])

    async def receipts(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""SELECT id,provider,site,added,updated,rejected,created_at FROM agent_rig.feed_receipts
                WHERE tenant_id=$1 ORDER BY created_at DESC LIMIT 30""", UUID(str(tenant_id)))
        return [{**dict(row), "id": str(row["id"]), "created_at": row["created_at"].isoformat()} for row in rows]

    async def missed_searches(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""SELECT query,count(*)::int AS count FROM agent_rig.searches
                WHERE tenant_id=$1 AND (NOT exact_match OR ids='[]'::jsonb)
                AND created_at >= now()-interval '90 days' GROUP BY query ORDER BY count(*) DESC,query LIMIT 50""", UUID(str(tenant_id)))
        return [dict(row) for row in rows]
