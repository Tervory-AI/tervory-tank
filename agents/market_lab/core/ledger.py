"""Tenant-scoped rows for one Market Lab box.

FRED points are refused. Predictions are insert-only: a resolution or a
correction is a new row, and nothing here updates an existing prediction.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

SCHEMA = "agent_market_lab"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema.sql"


def schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


class MemoryLedger:
    """In-memory stand-in used by tests. Same rules as the database ledger."""

    def __init__(self) -> None:
        self.series: list[dict[str, Any]] = []
        self.points: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.opportunities: list[dict[str, Any]] = []
        self.predictions: list[dict[str, Any]] = []
        self.reports: list[dict[str, Any]] = []
        self.refused: list[str] = []

    def save_series(self, row: dict[str, Any]) -> None:
        self._require_tenant(row["tenant_id"])
        if any(item["id"] == row["id"] for item in self.series):
            return
        self.series.append(dict(row))

    def save_points(self, series_id: str, tenant_id: str, points: list[dict[str, Any]], *, stored: bool, source: str) -> int:
        self._require_tenant(tenant_id)
        if not stored or source == "fred":
            self.refused.append(series_id)
            return 0
        if not any(item["id"] == series_id and item["tenant_id"] == str(tenant_id) for item in self.series):
            raise RuntimeError("series is not in this tenant")
        added = 0
        for point in points:
            key = (series_id, str(point["date"])[:10])
            if any((item["series_id"], item["date"]) == key for item in self.points):
                continue
            self.points.append(
                {
                    "series_id": series_id,
                    "tenant_id": str(tenant_id),
                    "date": key[1],
                    "value": point["value"],
                    "fetched_at": point.get("fetched_at") or "",
                }
            )
            added += 1
        return added

    def save_event(self, series_id: str, tenant_id: str, event: dict[str, Any]) -> bool:
        self._require_tenant(tenant_id)
        key = (series_id, event["date"], event["kind"])
        if any((item["series_id"], item["date"], item["kind"]) == key for item in self.events):
            return False
        self.events.append(
            {
                "series_id": series_id,
                "tenant_id": str(tenant_id),
                "date": event["date"],
                "kind": event["kind"],
                "size": event["size"],
            }
        )
        return True

    def save_opportunity(self, row: dict[str, Any]) -> None:
        self._require_tenant(row["tenant_id"])
        self.opportunities.append(dict(row))

    def save_prediction(self, row: dict[str, Any]) -> None:
        self._require_tenant(row["tenant_id"])
        if any(item["id"] == row["id"] for item in self.predictions):
            raise RuntimeError("predictions are append-only")
        self.predictions.append(dict(row))

    def save_report(self, row: dict[str, Any]) -> None:
        self._require_tenant(row["tenant_id"])
        self.reports.append(dict(row))

    def series_for(self, tenant_id: str) -> list[dict[str, Any]]:
        self._require_tenant(tenant_id)
        return [dict(item) for item in self.series if item["tenant_id"] == str(tenant_id)]

    def points_for(self, tenant_id: str, series_id: str | None = None) -> list[dict[str, Any]]:
        self._require_tenant(tenant_id)
        rows = [item for item in self.points if item["tenant_id"] == str(tenant_id)]
        if series_id is not None:
            rows = [item for item in rows if item["series_id"] == series_id]
        return [dict(item) for item in rows]

    def predictions_for(self, tenant_id: str) -> list[dict[str, Any]]:
        self._require_tenant(tenant_id)
        return [dict(item) for item in self.predictions if item["tenant_id"] == str(tenant_id)]

    def _require_tenant(self, tenant_id: str) -> None:
        text = str(tenant_id)
        if not text:
            raise RuntimeError("tenant_id is required")


class PostgresLedger:
    """asyncpg ledger. Every statement filters by tenant_id."""

    def __init__(self, conn: Any) -> None:
        self.conn = conn

    async def apply_schema(self) -> None:
        for statement in _statements(schema_sql()):
            try:
                await self.conn.execute(statement)
            except Exception:
                if statement.upper().startswith("CREATE SCHEMA"):
                    present = await self.conn.fetchval(
                        "SELECT 1 FROM pg_namespace WHERE nspname = $1",
                        SCHEMA,
                    )
                    if present == 1:
                        continue
                raise

    async def save_series(self, row: dict[str, Any]) -> None:
        await self.conn.execute(
            f"""
            INSERT INTO {SCHEMA}.series (id, tenant_id, source, ref, unit, engine)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO NOTHING
            """,
            row["id"],
            uuid.UUID(str(row["tenant_id"])),
            row["source"],
            row["ref"],
            row["unit"],
            row["engine"],
        )

    async def save_points(
        self,
        series_id: str,
        tenant_id: str,
        points: list[dict[str, Any]],
        *,
        stored: bool,
        source: str,
    ) -> int:
        if not stored or source == "fred":
            return 0
        owned = await self.conn.fetchval(
            f"SELECT 1 FROM {SCHEMA}.series WHERE id = $1 AND tenant_id = $2",
            series_id,
            uuid.UUID(str(tenant_id)),
        )
        if owned != 1:
            raise RuntimeError("series is not in this tenant")
        added = 0
        for point in points:
            result = await self.conn.execute(
                f"""
                INSERT INTO {SCHEMA}.points (series_id, date, value, fetched_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (series_id, date) DO NOTHING
                """,
                series_id,
                str(point["date"])[:10],
                point["value"],
                str(point.get("fetched_at") or ""),
            )
            if result.endswith(" 1"):
                added += 1
        return added

    async def save_event(self, series_id: str, tenant_id: str, event: dict[str, Any]) -> bool:
        owned = await self.conn.fetchval(
            f"SELECT 1 FROM {SCHEMA}.series WHERE id = $1 AND tenant_id = $2",
            series_id,
            uuid.UUID(str(tenant_id)),
        )
        if owned != 1:
            raise RuntimeError("series is not in this tenant")
        result = await self.conn.execute(
            f"""
            INSERT INTO {SCHEMA}.events (series_id, date, kind, size)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (series_id, date, kind) DO NOTHING
            """,
            series_id,
            event["date"],
            event["kind"],
            event["size"],
        )
        return result.endswith(" 1")

    async def save_opportunity(self, row: dict[str, Any]) -> None:
        await self.conn.execute(
            f"""
            INSERT INTO {SCHEMA}.opportunities (
                id, tenant_id, made_at, area, segment, demand_idx, supply_idx,
                gap, saturation, reachability, trend, rank, evidence
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13::jsonb
            )
            """,
            uuid.UUID(str(row["id"])),
            uuid.UUID(str(row["tenant_id"])),
            row["made_at"],
            row["area"],
            row["segment"],
            row["demand_idx"],
            row["supply_idx"],
            row["gap"],
            row["saturation"],
            row["reachability"],
            json.dumps(row["trend"]),
            row["rank"],
            json.dumps(row["evidence"]),
        )

    async def save_prediction(self, row: dict[str, Any]) -> None:
        await self.conn.execute(
            f"""
            INSERT INTO {SCHEMA}.predictions (
                id, tenant_id, made_at, statement, metric_series_id, comparator,
                target, resolve_by, rationale, sources, outcome, resolved_at, score
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12, $13
            )
            """,
            uuid.UUID(str(row["id"])),
            uuid.UUID(str(row["tenant_id"])),
            row["made_at"],
            row["statement"],
            row["metric_series_id"],
            row["comparator"],
            row["target"],
            row["resolve_by"],
            row["rationale"],
            json.dumps(row["sources"]),
            row.get("outcome"),
            row.get("resolved_at"),
            row.get("score"),
        )

    async def save_report(self, row: dict[str, Any]) -> None:
        await self.conn.execute(
            f"""
            INSERT INTO {SCHEMA}.reports (id, tenant_id, made_at, question, answer, citations)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            uuid.UUID(str(row["id"])),
            uuid.UUID(str(row["tenant_id"])),
            row["made_at"],
            row["question"],
            row["answer"],
            json.dumps(row["citations"]),
        )

    async def series_for(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = await self.conn.fetch(
            f"""
            SELECT id, tenant_id, source, ref, unit, engine
            FROM {SCHEMA}.series
            WHERE tenant_id = $1
            ORDER BY id
            """,
            uuid.UUID(str(tenant_id)),
        )
        return [_record(row) for row in rows]

    async def points_for(self, tenant_id: str, series_id: str | None = None) -> list[dict[str, Any]]:
        if series_id is None:
            rows = await self.conn.fetch(
                f"""
                SELECT p.series_id, p.date, p.value, p.fetched_at
                FROM {SCHEMA}.points p
                JOIN {SCHEMA}.series s ON s.id = p.series_id
                WHERE s.tenant_id = $1
                ORDER BY p.series_id, p.date
                """,
                uuid.UUID(str(tenant_id)),
            )
        else:
            rows = await self.conn.fetch(
                f"""
                SELECT p.series_id, p.date, p.value, p.fetched_at
                FROM {SCHEMA}.points p
                JOIN {SCHEMA}.series s ON s.id = p.series_id
                WHERE s.tenant_id = $1 AND p.series_id = $2
                ORDER BY p.date
                """,
                uuid.UUID(str(tenant_id)),
                series_id,
            )
        return [_record(row) for row in rows]

    async def predictions_for(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = await self.conn.fetch(
            f"""
            SELECT id, tenant_id, made_at, statement, metric_series_id, comparator,
                   target, resolve_by, rationale, sources, outcome, resolved_at, score
            FROM {SCHEMA}.predictions
            WHERE tenant_id = $1
            ORDER BY made_at, id
            """,
            uuid.UUID(str(tenant_id)),
        )
        return [_record(row) for row in rows]


def _statements(script: str) -> list[str]:
    found: list[str] = []
    for raw in script.split(";"):
        lines = [line for line in raw.splitlines() if not line.strip().startswith("--")]
        text = "\n".join(lines).strip()
        if text:
            found.append(text)
    return found


def _record(row: Any) -> dict[str, Any]:
    data = dict(row)
    for key, value in list(data.items()):
        if hasattr(value, "hex") and key in {"id", "tenant_id"}:
            data[key] = str(value)
        elif isinstance(value, str) and key in {"sources", "trend", "evidence", "citations"}:
            data[key] = json.loads(value)
    return data
