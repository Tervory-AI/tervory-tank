"""Market Lab: series, gaps, and a prediction ledger. Industry words stay in an engine."""

from __future__ import annotations

import logging
import os

from fastapi import Header, Query

from chassis.app import create_app
from chassis.jobs import JobContext

from core.jobs import (
    perform_opportunities,
    perform_refresh,
    perform_research,
    perform_resolve,
)
from core.ledger import PostgresLedger
from engines.ffl.engine import schedules as case_schedules

AGENT = os.environ.get("AGENT_NAME", "market_lab")
HEARTBEAT_TENANT = "00000000-0000-0000-0000-000000000001"

log = logging.getLogger("agent")


async def ping(ctx: JobContext) -> dict:
    result: dict = {"pong": True, "agent": ctx.agent}
    if ctx.input.get("heartbeat"):
        try:
            saved = await ctx.memory.remember(
                ctx.tenant_id,
                f"{ctx.agent} heartbeat",
                "heartbeat",
                "schedule:*/5",
            )
            result["heartbeats_seen"] = saved.get("seen")
        except Exception as exc:  # noqa: BLE001 — class name only, never the message
            log.warning("heartbeat memory failed (%s)", type(exc).__name__)
            result["memory"] = "unreachable"
    return result


async def refresh(ctx: JobContext) -> dict:
    fixtures = ctx.input.get("fixtures") or os.environ.get("FEEDS_FIXTURES") or None
    async with _ledger() as ledger:
        return await perform_refresh(
            tenant_id=ctx.tenant_id,
            engine=str(ctx.input.get("engine") or ""),
            ledger=ledger,
            fixtures=None if not fixtures else str(fixtures),
            live=not fixtures,
        )


async def opportunities(ctx: JobContext) -> dict:
    async with _ledger() as ledger:
        result = await perform_opportunities(
            tenant_id=ctx.tenant_id,
            engine=str(ctx.input.get("engine") or ""),
            ledger=ledger,
            areas=ctx.input.get("areas"),
            signals=ctx.input.get("signals"),
            memory=_SafeMemory(ctx.memory),
        )
    return {"top_area": result["top_area"], "top_recommendation": result["top_recommendation"]}


async def resolve(ctx: JobContext) -> dict:
    async with _ledger() as ledger:
        return await perform_resolve(tenant_id=ctx.tenant_id, ledger=ledger)


def _has_source_passages(value: object) -> bool:
    return isinstance(value, list) and len(value) > 0


async def research(ctx: JobContext) -> dict:
    question = str(ctx.input.get("question") or "").strip()
    passages = ctx.input.get("passages")
    if not _has_source_passages(passages):
        return {"answer": "no sources yet", "citations": [], "cost_usd": 0}
    async with _ledger() as ledger:
        answer = await perform_research(
            tenant_id=ctx.tenant_id,
            ledger=ledger,
            question=question,
            passages=passages,
            model_text=None,
            memory=_SafeMemory(ctx.memory),
        )
    return {"answer": answer["answer"], "citations": answer["citations"]}


class _SafeMemory:
    def __init__(self, inner: object) -> None:
        self.inner = inner

    async def remember(self, tenant_id: str, text: str, kind: str, source: str) -> dict:
        try:
            saved = await self.inner.remember(tenant_id, text, kind, source)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 — class name only, never the message
            log.warning("memory failed (%s)", type(exc).__name__)
            return {"seen": None}
        return saved if isinstance(saved, dict) else {}


class _ledger:
    def __init__(self) -> None:
        self.conn = None
        self.ledger: PostgresLedger | None = None

    async def __aenter__(self) -> PostgresLedger:
        import asyncpg

        url = os.environ.get("DATABASE_URL", "")
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        self.conn = await asyncpg.connect(url)
        self.ledger = PostgresLedger(self.conn)
        await self.ledger.apply_schema()
        return self.ledger

    async def __aexit__(self, *_exc: object) -> None:
        if self.conn is not None:
            await self.conn.close()


def _schedules() -> list[dict]:
    rows = [
        {
            "tenant_id": HEARTBEAT_TENANT,
            "cron": "*/5 * * * *",
            "kind": "ping",
            "input": {"heartbeat": True},
        }
    ]
    rows.extend(case_schedules())
    return rows


app = create_app(
    agent=AGENT,
    handlers={
        "ping": ping,
        "refresh": refresh,
        "opportunities": opportunities,
        "resolve": resolve,
        "research": research,
    },
    schedules=_schedules(),
)


@app.get("/gold/candidates")
async def gold_candidates(
    limit: int = Query(200, ge=1, le=200),
    x_tank_key: str | None = Header(None),
) -> list[dict]:
    import hmac
    from fastapi import HTTPException
    from gold_sources import candidates

    key = os.environ.get("TANK_KEY", "")
    if not key or not x_tank_key or not hmac.compare_digest(key, x_tank_key):
        raise HTTPException(status_code=401, detail="Room key required")
    async with _ledger() as ledger:
        series = await ledger.series_for(HEARTBEAT_TENANT)
        points = await ledger.points_for(HEARTBEAT_TENANT)
    return candidates(series, points, region=os.environ.get("TANK_REGION", "us-east"), limit=limit)
