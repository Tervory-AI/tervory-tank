"""Model skills on /skala take their price from this box's platform ledger."""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import pytest

import skill_costs

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Conn:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[tuple] = []

    async def fetch(self, sql: str, *args: object) -> list[dict]:
        self.calls.append((sql, args))
        return self.rows


def test_the_query_is_platform_tenant_and_this_region_only() -> None:
    sql = skill_costs.CALL_COST_SQL
    assert "tenant_id = $1" in sql
    assert "region = $2" in sql
    assert "interval '30 days'" in sql
    assert "avg(cost_usd)" in sql
    assert " OR " not in sql
    body = (ROOT / "tank" / "main.py").read_text(encoding="utf-8")
    fn = body.split("async def list_skills", 1)[1].split("\nclass ", 1)[0]
    assert "fetch_call_costs(conn, PLATFORM_TENANT, box_region())" in fn


@pytest.mark.asyncio
async def test_each_version_gets_its_own_30_day_average() -> None:
    conn = Conn([
        {"skill": "market.research@1.1.0", "calls_30d": 8, "avg_cost_usd": Decimal("0.0031")},
        {"skill": "base.find_site@1.7.0", "calls_30d": 2, "avg_cost_usd": Decimal("0")},
        {"skill": None, "calls_30d": 5, "avg_cost_usd": Decimal("1")},
    ])
    costs = await skill_costs.fetch_call_costs(conn, PLATFORM, "za")
    assert conn.calls[0][1] == (PLATFORM, "za")
    skills = skill_costs.attach_call_costs([
        {"id": "market.research", "version": "1.1.0"},
        {"id": "market.research", "version": "1.0.0"},
        {"id": "base.find_site", "version": "1.7.0"},
    ], costs)
    assert skills[0]["calls_30d"] == 8
    assert skills[0]["avg_cost_usd"] == pytest.approx(0.0031)
    assert skills[1] == {"id": "market.research", "version": "1.0.0", "calls_30d": 0, "avg_cost_usd": None}
    assert skills[2]["calls_30d"] == 2
    assert skills[2]["avg_cost_usd"] == 0.0
