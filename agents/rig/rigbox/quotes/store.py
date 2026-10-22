"""Durable delivery state and counts. No visitor IDs, search text or IPs."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

EVENTS = frozenset({"searches", "setups_opened", "swaps", "quotes", "no_results"})


class MemoryQuotes:
    def __init__(self, store: Any) -> None:
        self.store = store
        self.states: dict[tuple[str, str], dict[str, Any]] = {}
        self.counts: Counter = Counter()
        self.lock = asyncio.Lock()

    async def create(self, tenant: str, quote: dict[str, Any]) -> None:
        await self.store.add_quote(tenant, quote["id"], quote["payload"], quote["contact"])
        self.states[(tenant, quote["id"])] = {"status": "pending", "error": None}
        await self.count(tenant, "quotes")

    async def count(self, tenant: str, event: str) -> None:
        if event not in EVENTS:
            raise ValueError("Unknown event")
        self.counts[(tenant, datetime.now(timezone.utc).date(), event)] += 1

    async def analytics(self, tenant: str, since: date) -> dict[str, int]:
        return {event: sum(n for (t, day, e), n in self.counts.items()
                           if t == tenant and day >= since and e == event) for event in sorted(EVENTS)}

    async def claim(self, tenant: str, quote_id: str) -> dict[str, Any] | None:
        async with self.lock:
            state = self.states.get((tenant, quote_id))
            if not state or state["status"] != "pending":
                return None
            state["status"] = "sending"
            return next(row for row in await self.store.quotes_for(tenant) if row["id"] == quote_id)

    async def finish(self, tenant: str, quote_id: str, error: str | None) -> None:
        self.states[(tenant, quote_id)] = {"status": "pending" if error else "sent", "error": error}
        if not error:
            await self.store.mark_sent(tenant, quote_id)

    async def pending(self, tenant: str) -> list[str]:
        return [q for (t, q), state in self.states.items() if t == tenant and state["status"] == "pending"][:25]

    async def status(self, tenant: str, quote_id: str) -> dict[str, Any] | None:
        return self.states.get((tenant, quote_id))


class PgQuotes:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def create(self, tenant: str, quote: dict[str, Any]) -> None:
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("""INSERT INTO agent_rig.quotes (tenant_id, id, payload, contact)
                VALUES ($1, $2, $3::jsonb, $4::jsonb)""", UUID(tenant), quote["id"],
                json.dumps(quote["payload"]), json.dumps(quote["contact"]))
            await conn.execute("""INSERT INTO agent_rig.quote_handoffs (tenant_id, quote_id)
                VALUES ($1, $2)""", UUID(tenant), quote["id"])
            await self._count(conn, tenant, "quotes")

    async def _count(self, conn: Any, tenant: str, event: str) -> None:
        if event not in EVENTS:
            raise ValueError("Unknown event")
        await conn.execute("""INSERT INTO agent_rig.widget_counts (tenant_id, day, event, count)
            VALUES ($1, (now() AT TIME ZONE 'UTC')::date, $2, 1)
            ON CONFLICT (tenant_id, day, event) DO UPDATE
            SET count = agent_rig.widget_counts.count + 1""", UUID(tenant), event)

    async def count(self, tenant: str, event: str) -> None:
        async with self.pool.acquire() as conn:
            await self._count(conn, tenant, event)

    async def analytics(self, tenant: str, since: date) -> dict[str, int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""SELECT event, sum(count) AS count FROM agent_rig.widget_counts
                WHERE tenant_id = $1 AND day >= $2 GROUP BY event""", UUID(tenant), since)
        totals = {event: 0 for event in sorted(EVENTS)}
        totals.update({row["event"]: int(row["count"]) for row in rows})
        return totals

    async def claim(self, tenant: str, quote_id: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn, conn.transaction():
            claimed = await conn.fetchval("""UPDATE agent_rig.quote_handoffs
                SET status = 'sending', updated_at = now(), attempts = attempts + 1
                WHERE tenant_id = $1 AND quote_id = $2 AND
                (status = 'pending' OR (status = 'sending' AND updated_at < now() - interval '5 minutes'))
                RETURNING quote_id""", UUID(tenant), quote_id)
            if not claimed:
                return None
            row = await conn.fetchrow("""SELECT id, payload, contact FROM agent_rig.quotes
                WHERE tenant_id = $1 AND id = $2""", UUID(tenant), quote_id)
        return {"id": row["id"], **{key: json.loads(row[key]) if isinstance(row[key], str) else row[key]
                                  for key in ("payload", "contact")}}

    async def finish(self, tenant: str, quote_id: str, error: str | None) -> None:
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("""UPDATE agent_rig.quote_handoffs
                SET status = $3, error = $4, updated_at = now()
                WHERE tenant_id = $1 AND quote_id = $2""", UUID(tenant), quote_id,
                "pending" if error else "sent", error)
            if not error:
                await conn.execute("""UPDATE agent_rig.quotes SET sent_at = now()
                    WHERE tenant_id = $1 AND id = $2""", UUID(tenant), quote_id)

    async def pending(self, tenant: str) -> list[str]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""SELECT quote_id FROM agent_rig.quote_handoffs
                WHERE tenant_id = $1 AND (status = 'pending' OR
                    (status = 'sending' AND updated_at < now() - interval '5 minutes'))
                ORDER BY updated_at LIMIT 25""", UUID(tenant))
        return [row["quote_id"] for row in rows]

    async def status(self, tenant: str, quote_id: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""SELECT status, error FROM agent_rig.quote_handoffs
                WHERE tenant_id = $1 AND quote_id = $2""", UUID(tenant), quote_id)
        return dict(row) if row else None
