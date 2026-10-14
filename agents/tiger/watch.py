"""Tiger's watchlist, price history, and alerts.

No product, brand, or industry words. A watch stores the caller's label and
engine string and does not interpret them. `threshold` is a fraction of the
previous price: 0 alerts on any change, 0.05 alerts above a 5% move.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import asyncpg

from chassis.cron import is_due
from chassis.db import schema_for

SCHEMA = schema_for("tiger")
ROBOTS_TOKEN = "tervorytiger"
_INTERVAL = re.compile(r"^(\d+)(s|m|h|d)$")
_SKIP_METHODS = {"blocked", "robots", "error", "none"}

SQL_LIST_WATCHES = """
SELECT id, tenant_id, url, label, engine, every, enabled, threshold
FROM {schema}.watchlist
WHERE tenant_id = $1
ORDER BY url
"""
SQL_GET_WATCH = """
SELECT id, tenant_id, url, label, engine, every, enabled, threshold
FROM {schema}.watchlist
WHERE tenant_id = $1 AND url = $2
"""
SQL_GET_WATCH_ID = """
SELECT id, tenant_id, url, label, engine, every, enabled, threshold
FROM {schema}.watchlist
WHERE tenant_id = $1 AND id = $2
"""
SQL_INSERT_WATCH = """
INSERT INTO {schema}.watchlist (tenant_id, url, label, engine, every, enabled, threshold)
VALUES ($1, $2, $3, $4, $5, $6, $7)
RETURNING id, tenant_id, url, label, engine, every, enabled, threshold
"""
SQL_DELETE_WATCH = """
DELETE FROM {schema}.watchlist
WHERE tenant_id = $1 AND id = $2
"""
SQL_INSERT_OBS = """
INSERT INTO {schema}.observations (tenant_id, url, ts, price, currency, availability, method, evidence)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
RETURNING id, tenant_id, url, ts, price, currency, availability, method, evidence
"""
SQL_LIST_OBS = """
SELECT id, tenant_id, url, ts, price, currency, availability, method, evidence
FROM {schema}.observations
WHERE tenant_id = $1 AND url = $2
ORDER BY ts DESC
LIMIT 200
"""
SQL_LATEST_OBS = """
SELECT id, tenant_id, url, ts, price, currency, availability, method, evidence
FROM {schema}.observations
WHERE tenant_id = $1 AND url = $2
ORDER BY ts DESC
LIMIT 1
"""
SQL_PREVIOUS_OBS = """
SELECT id, tenant_id, url, ts, price, currency, availability, method, evidence
FROM {schema}.observations
WHERE tenant_id = $1 AND url = $2 AND id <> $3
  AND method <> ALL($4::text[])
ORDER BY ts DESC
LIMIT 1
"""
SQL_INSERT_ALERT = """
INSERT INTO {schema}.alerts (tenant_id, url, ts, kind, before, after)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING id, tenant_id, url, ts, kind, before, after
"""
SQL_LIST_ALERTS = """
SELECT id, tenant_id, url, ts, kind, before, after
FROM {schema}.alerts
WHERE tenant_id = $1 AND ($2::text IS NULL OR url = $2)
ORDER BY ts DESC
LIMIT 200
"""
SQL_CHECK_OPEN = """
SELECT 1
FROM {schema}.jobs
WHERE tenant_id = $1 AND kind = 'check' AND status IN ('queued', 'running')
  AND input->>'url' = $2
LIMIT 1
"""
SQL_ENQUEUE_CHECK = """
INSERT INTO {schema}.jobs (tenant_id, kind, input, status, run_at)
VALUES ($1, 'check', $2::jsonb, 'queued', now())
"""
SQL_ENSURE_DISPATCH = """
INSERT INTO {schema}.schedules (tenant_id, cron, kind, input, enabled)
VALUES ($1, '* * * * *', 'dispatch', '{{}}'::jsonb, true)
ON CONFLICT (tenant_id, kind, cron) DO NOTHING
"""


class DuplicateWatch(Exception):
    """This tenant already watches that URL."""


class BadWatch(ValueError):
    """The watch fields are not usable."""


def session_for_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def robots_url_for(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def is_public_url(url: str) -> bool:
    """Same rule as tiger/pool.py. This box does not import the browser package.

    http(s) only. A name must contain a dot, so `tank` and `litellm` are not
    hosts. `localhost` is refused. Resolve the host and refuse if any address
    is private, loopback, link-local, multicast, reserved, or unspecified,
    including an IPv4 address written as IPv6.
    """
    if not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or host == "localhost":
        return False
    if not _is_ip(host) and "." not in host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            address = info[4][0]
        except (IndexError, TypeError):
            return False
        if _blocked_address(address):
            return False
    return True


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _blocked_address(address: str) -> bool:
    text = address.split("%", 1)[0]
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return True
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def check_url(url: str) -> str:
    text = url.strip()
    if len(text) > 2000:
        raise BadWatch("url is too long")
    if not is_public_url(text):
        raise BadWatch("url not allowed")
    return text


def check_every(every: str) -> str:
    text = every.strip()
    if _INTERVAL.fullmatch(text) or text.isdigit():
        if every_seconds(text) <= 0:
            raise BadWatch("every must be a positive interval")
        return text
    try:
        is_due(text, datetime.now(timezone.utc), None)
    except (ValueError, TypeError) as exc:
        raise BadWatch("every must be a cron expression or an interval such as 1h") from exc
    return text


def check_threshold(value: Any) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BadWatch("threshold must be a number") from exc
    if number < 0:
        raise BadWatch("threshold must be zero or more")
    return _plain(number)


def check_text(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        raise BadWatch("a field is too long")
    return text


def every_seconds(every: str) -> int | None:
    text = every.strip()
    if text.isdigit():
        return int(text)
    match = _INTERVAL.fullmatch(text)
    if match is None:
        return None
    amount = int(match.group(1))
    unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
    return amount * unit


def watch_is_due(every: str, now: datetime, last: datetime | None) -> bool:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    seconds = every_seconds(every)
    if seconds is None:
        return is_due(every.strip(), now, last)
    if seconds <= 0:
        return False
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last).total_seconds() >= seconds


def robots_allows(body: str, url: str, token: str = ROBOTS_TOKEN) -> bool:
    """True when robots.txt does not disallow this URL for Tiger."""
    if not body.strip():
        return True
    groups = _robot_groups(body)
    rules = _rules_for(groups, token)
    if rules is None:
        for agents, group_rules in groups:
            if any(agent.strip() == "*" for agent in agents):
                rules = group_rules
                break
    if not rules:
        return True
    path = urlparse(url).path or "/"
    allow_len = -1
    disallow_len = -1
    for kind, prefix in rules:
        if not prefix:
            continue
        if path.startswith(prefix):
            if kind == "allow" and len(prefix) > allow_len:
                allow_len = len(prefix)
            elif kind == "disallow" and len(prefix) > disallow_len:
                disallow_len = len(prefix)
    if disallow_len < 0:
        return True
    return allow_len >= disallow_len


def _robot_groups(body: str) -> list[tuple[list[str], list[tuple[str, str]]]]:
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []

    def flush() -> None:
        nonlocal agents, rules
        if agents or rules:
            groups.append((agents, rules))
        agents, rules = [], []

    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if rules:
                flush()
            agents.append(value)
        elif key in {"allow", "disallow"} and agents:
            rules.append((key, value))
    flush()
    return groups


def _rules_for(groups: list[tuple[list[str], list[tuple[str, str]]]], token: str) -> list[tuple[str, str]] | None:
    for agents, rules in groups:
        if any(token in agent.lower() for agent in agents):
            return rules
    return None


def price_moved(before: Any, after: Any, threshold: Any) -> bool:
    if before is None or after is None:
        return False
    old = Decimal(str(before))
    new = Decimal(str(after))
    if old == new:
        return False
    if old == 0:
        return True
    return abs(new - old) / abs(old) > Decimal(str(threshold))


def alerts_for(previous: dict | None, current: dict, threshold: Any) -> list[dict[str, str]]:
    if not _comparable(previous) or not _comparable(current):
        return []
    assert previous is not None
    found: list[dict[str, str]] = []
    if price_moved(previous.get("price"), current.get("price"), threshold):
        found.append({
            "kind": "price",
            "before": str(previous.get("price")),
            "after": str(current.get("price")),
        })
    before_stock = previous.get("availability")
    after_stock = current.get("availability")
    if before_stock and after_stock and before_stock != after_stock:
        found.append({"kind": "stock", "before": str(before_stock), "after": str(after_stock)})
    return found


def _comparable(row: dict | None) -> bool:
    if not row:
        return False
    return str(row.get("method") or "") not in _SKIP_METHODS


class DomainLimiter:
    """One request per domain per interval. Default 10 seconds."""

    def __init__(self, interval_s: float = 10, clock=None, sleep=None) -> None:
        self.interval_s = interval_s
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._next: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, host: str) -> float:
        async with self._lock:
            now = float(self._clock())
            ready = self._next.get(host, now)
            delay = max(0.0, ready - now)
            self._next[host] = max(ready, now) + self.interval_s
        if delay:
            await self._sleep(delay)
        return delay


def _plain(number: Decimal) -> str:
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _money(value: Any) -> str | None:
    if value is None:
        return None
    return f"{Decimal(str(value)).quantize(Decimal('0.01'))}"


def _stamp(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _obs(
    tenant_id: str,
    url: str,
    ts: datetime,
    price: str | None,
    currency: str | None,
    availability: str | None,
    method: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "tenant_id": str(tenant_id),
        "url": url,
        "ts": ts,
        "price": price,
        "currency": currency,
        "availability": availability,
        "method": method,
        "evidence": evidence[:2000],
    }


def _evidence(method: str | None, price: str | None, saved: str | None) -> str:
    return json.dumps({"method": method, "price": price, "file": saved}, default=str)[:2000]


async def ensure_tables(conn: Any, schema: str = SCHEMA) -> None:
    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.watchlist (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            url text NOT NULL,
            label text NOT NULL DEFAULT '',
            engine text NOT NULL DEFAULT '',
            every text NOT NULL,
            enabled boolean NOT NULL DEFAULT true,
            threshold numeric NOT NULL DEFAULT 0,
            UNIQUE (tenant_id, url)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.observations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            url text NOT NULL,
            ts timestamptz NOT NULL DEFAULT now(),
            price numeric,
            currency text,
            availability text,
            method text,
            evidence text
        )
        """,
        f"CREATE INDEX IF NOT EXISTS observations_tenant_url_ts ON {schema}.observations (tenant_id, url, ts DESC)",
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.alerts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            url text NOT NULL,
            ts timestamptz NOT NULL DEFAULT now(),
            kind text NOT NULL,
            before text,
            after text
        )
        """,
        f"CREATE INDEX IF NOT EXISTS alerts_tenant_url_ts ON {schema}.alerts (tenant_id, url, ts DESC)",
    ]
    for statement in statements:
        await conn.execute(statement)


def _watch_out(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "url": row["url"],
        "label": row["label"] or "",
        "engine": row["engine"] or "",
        "every": row["every"],
        "enabled": bool(row["enabled"]),
        "threshold": _plain(Decimal(str(row["threshold"]))),
    }


def _obs_out(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "url": row["url"],
        "ts": _stamp(row["ts"]),
        "price": _money(row["price"]),
        "currency": row["currency"],
        "availability": row["availability"],
        "method": row["method"],
        "evidence": row["evidence"],
    }


def _alert_out(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "url": row["url"],
        "ts": _stamp(row["ts"]),
        "kind": row["kind"],
        "before": row["before"],
        "after": row["after"],
    }


class PgStore:
    def __init__(self, pool: Any, schema: str = SCHEMA) -> None:
        self.pool = pool
        self.schema = schema

    def _sql(self, statement: str) -> str:
        return statement.format(schema=self.schema)

    async def create_watch(self, row: dict[str, Any]) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            try:
                saved = await conn.fetchrow(
                    self._sql(SQL_INSERT_WATCH),
                    uuid.UUID(str(row["tenant_id"])),
                    row["url"],
                    row["label"],
                    row["engine"],
                    row["every"],
                    bool(row["enabled"]),
                    Decimal(str(row["threshold"])),
                )
            except asyncpg.UniqueViolationError as exc:
                raise DuplicateWatch(row["url"]) from exc
            await conn.execute(self._sql(SQL_ENSURE_DISPATCH), uuid.UUID(str(row["tenant_id"])))
        return _watch_out(saved)

    async def list_watches(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            rows = await conn.fetch(self._sql(SQL_LIST_WATCHES), uuid.UUID(str(tenant_id)))
        return [_watch_out(row) for row in rows]

    async def get_watch(self, tenant_id: str, url: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            row = await conn.fetchrow(self._sql(SQL_GET_WATCH), uuid.UUID(str(tenant_id)), url)
        return _watch_out(row) if row else None

    async def get_watch_by_id(self, tenant_id: str, watch_id: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            row = await conn.fetchrow(
                self._sql(SQL_GET_WATCH_ID),
                uuid.UUID(str(tenant_id)),
                uuid.UUID(str(watch_id)),
            )
        return _watch_out(row) if row else None

    async def update_watch(self, tenant_id: str, watch_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        current = await self.get_watch_by_id(tenant_id, watch_id)
        if current is None:
            return None
        merged = dict(current)
        merged.update(fields)
        assignments = []
        values: list[Any] = [uuid.UUID(str(tenant_id)), uuid.UUID(str(watch_id))]
        for column in ("url", "label", "engine", "every", "enabled", "threshold"):
            if column not in fields:
                continue
            values.append(Decimal(str(merged[column])) if column == "threshold" else merged[column])
            assignments.append(f"{column} = ${len(values)}")
        if not assignments:
            return current
        sql = (
            f"UPDATE {self.schema}.watchlist SET " + ", ".join(assignments)
            + " WHERE tenant_id = $1 AND id = $2"
            + " RETURNING id, tenant_id, url, label, engine, every, enabled, threshold"
        )
        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(sql, *values)
            except asyncpg.UniqueViolationError as exc:
                raise DuplicateWatch(str(merged.get("url"))) from exc
        return _watch_out(row) if row else None

    async def delete_watch(self, tenant_id: str, watch_id: str) -> bool:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            result = await conn.execute(
                self._sql(SQL_DELETE_WATCH),
                uuid.UUID(str(tenant_id)),
                uuid.UUID(str(watch_id)),
            )
        return result.endswith(" 1")

    async def enabled_watches(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = await self.list_watches(tenant_id)
        return [row for row in rows if row["enabled"]]

    async def add_observation(self, row: dict[str, Any]) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            saved = await conn.fetchrow(
                self._sql(SQL_INSERT_OBS),
                uuid.UUID(str(row["tenant_id"])),
                row["url"],
                row["ts"],
                Decimal(str(row["price"])) if row.get("price") is not None else None,
                row.get("currency"),
                row.get("availability"),
                row.get("method"),
                row.get("evidence"),
            )
        return _obs_out(saved)

    async def list_observations(self, tenant_id: str, url: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            rows = await conn.fetch(self._sql(SQL_LIST_OBS), uuid.UUID(str(tenant_id)), url)
        return [_obs_out(row) for row in rows]

    async def latest_observation(self, tenant_id: str, url: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            row = await conn.fetchrow(self._sql(SQL_LATEST_OBS), uuid.UUID(str(tenant_id)), url)
        return _obs_out(row) if row else None

    async def previous_observation(self, tenant_id: str, url: str, current_id: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            row = await conn.fetchrow(
                self._sql(SQL_PREVIOUS_OBS),
                uuid.UUID(str(tenant_id)),
                url,
                uuid.UUID(str(current_id)),
                list(_SKIP_METHODS),
            )
        return _obs_out(row) if row else None

    async def add_alert(self, row: dict[str, Any]) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            saved = await conn.fetchrow(
                self._sql(SQL_INSERT_ALERT),
                uuid.UUID(str(row["tenant_id"])),
                row["url"],
                row["ts"],
                row["kind"],
                row.get("before"),
                row.get("after"),
            )
        return _alert_out(saved)

    async def list_alerts(self, tenant_id: str, url: str | None) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            await ensure_tables(conn, self.schema)
            rows = await conn.fetch(self._sql(SQL_LIST_ALERTS), uuid.UUID(str(tenant_id)), url)
        return [_alert_out(row) for row in rows]

    async def check_open(self, tenant_id: str, url: str) -> bool:
        async with self.pool.acquire() as conn:
            found = await conn.fetchval(self._sql(SQL_CHECK_OPEN), uuid.UUID(str(tenant_id)), url)
        return found is not None

    async def enqueue_check(self, tenant_id: str, url: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                self._sql(SQL_ENQUEUE_CHECK),
                uuid.UUID(str(tenant_id)),
                json.dumps({"url": url}),
            )


class MemoryStore:
    """In-memory stand-in used by tests. Same tenant filter as the SQL."""

    def __init__(self) -> None:
        self.watches: list[dict[str, Any]] = []
        self.observations: list[dict[str, Any]] = []
        self.alerts: list[dict[str, Any]] = []
        self.jobs: list[dict[str, Any]] = []
        self.schedules: list[dict[str, Any]] = []

    async def create_watch(self, row: dict[str, Any]) -> dict[str, Any]:
        if any(item["tenant_id"] == str(row["tenant_id"]) and item["url"] == row["url"] for item in self.watches):
            raise DuplicateWatch(row["url"])
        saved = {
            "id": str(uuid.uuid4()),
            "tenant_id": str(row["tenant_id"]),
            "url": row["url"],
            "label": row["label"],
            "engine": row["engine"],
            "every": row["every"],
            "enabled": bool(row["enabled"]),
            "threshold": _plain(Decimal(str(row["threshold"]))),
        }
        self.watches.append(saved)
        await self._ensure_dispatch(saved["tenant_id"])
        return dict(saved)

    async def _ensure_dispatch(self, tenant_id: str) -> None:
        key = (tenant_id, "dispatch", "* * * * *")
        if key not in {(item["tenant_id"], item["kind"], item["cron"]) for item in self.schedules}:
            self.schedules.append({"tenant_id": tenant_id, "kind": "dispatch", "cron": "* * * * *"})

    async def list_watches(self, tenant_id: str) -> list[dict[str, Any]]:
        return [dict(item) for item in self.watches if item["tenant_id"] == str(tenant_id)]

    async def get_watch(self, tenant_id: str, url: str) -> dict[str, Any] | None:
        for item in self.watches:
            if item["tenant_id"] == str(tenant_id) and item["url"] == url:
                return dict(item)
        return None

    async def get_watch_by_id(self, tenant_id: str, watch_id: str) -> dict[str, Any] | None:
        for item in self.watches:
            if item["tenant_id"] == str(tenant_id) and item["id"] == str(watch_id):
                return dict(item)
        return None

    async def update_watch(self, tenant_id: str, watch_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        for item in self.watches:
            if item["tenant_id"] == str(tenant_id) and item["id"] == str(watch_id):
                item.update(fields)
                if "threshold" in fields:
                    item["threshold"] = _plain(Decimal(str(fields["threshold"])))
                return dict(item)
        return None

    async def delete_watch(self, tenant_id: str, watch_id: str) -> bool:
        before = len(self.watches)
        self.watches = [
            item for item in self.watches
            if not (item["tenant_id"] == str(tenant_id) and item["id"] == str(watch_id))
        ]
        return len(self.watches) != before

    async def enabled_watches(self, tenant_id: str) -> list[dict[str, Any]]:
        return [item for item in await self.list_watches(tenant_id) if item["enabled"]]

    async def add_observation(self, row: dict[str, Any]) -> dict[str, Any]:
        saved = {
            "id": str(uuid.uuid4()),
            "tenant_id": str(row["tenant_id"]),
            "url": row["url"],
            "ts": _stamp(row["ts"]),
            "price": _money(row.get("price")),
            "currency": row.get("currency"),
            "availability": row.get("availability"),
            "method": row.get("method"),
            "evidence": row.get("evidence"),
        }
        self.observations.append(saved)
        return dict(saved)

    def _obs_for(self, tenant_id: str, url: str) -> list[dict[str, Any]]:
        rows = [
            item for item in self.observations
            if item["tenant_id"] == str(tenant_id) and item["url"] == url
        ]
        return sorted(rows, key=lambda item: item["ts"], reverse=True)

    async def list_observations(self, tenant_id: str, url: str) -> list[dict[str, Any]]:
        return [dict(item) for item in self._obs_for(tenant_id, url)]

    async def latest_observation(self, tenant_id: str, url: str) -> dict[str, Any] | None:
        rows = self._obs_for(tenant_id, url)
        return dict(rows[0]) if rows else None

    async def previous_observation(self, tenant_id: str, url: str, current_id: str) -> dict[str, Any] | None:
        for item in self._obs_for(tenant_id, url):
            if item["id"] == str(current_id):
                continue
            if item.get("method") in _SKIP_METHODS:
                continue
            return dict(item)
        return None

    async def add_alert(self, row: dict[str, Any]) -> dict[str, Any]:
        saved = {
            "id": str(uuid.uuid4()),
            "tenant_id": str(row["tenant_id"]),
            "url": row["url"],
            "ts": _stamp(row["ts"]),
            "kind": row["kind"],
            "before": row.get("before"),
            "after": row.get("after"),
        }
        self.alerts.append(saved)
        return dict(saved)

    async def list_alerts(self, tenant_id: str, url: str | None) -> list[dict[str, Any]]:
        rows = [item for item in self.alerts if item["tenant_id"] == str(tenant_id)]
        if url is not None:
            rows = [item for item in rows if item["url"] == url]
        return [dict(item) for item in rows]

    async def check_open(self, tenant_id: str, url: str) -> bool:
        return any(
            item["tenant_id"] == str(tenant_id)
            and item["url"] == url
            and item["status"] in {"queued", "running"}
            for item in self.jobs
        )

    async def enqueue_check(self, tenant_id: str, url: str) -> None:
        self.jobs.append({
            "tenant_id": str(tenant_id),
            "url": url,
            "kind": "check",
            "status": "queued",
        })


def _save_png(files: Any, tenant_id: str, png_base64: str | None, stamp: datetime) -> str | None:
    if not png_base64 or files is None:
        return None
    import base64
    try:
        raw = base64.b64decode(png_base64)
    except Exception:  # noqa: BLE001
        return None
    if not raw.startswith(b"\x89PNG") or len(raw) > 1_500_000:
        return None
    name = f"price-{int(stamp.timestamp())}.png"
    return str(files.save_file(tenant_id, name, raw))


async def run_check(
    store: Any,
    tenant_id: str,
    watch: dict[str, Any],
    agent: str,
    render: Any,
    extract: Any,
    ocr: Any,
    fetch_text: Any,
    limiter: DomainLimiter,
    files: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    clock = now or (lambda: datetime.now(timezone.utc))
    url = watch["url"]
    if str(watch.get("tenant_id")) != str(tenant_id):
        return {"status": "skipped", "url": url, "alerts": []}
    host = host_of(url)
    await limiter.wait(host)
    try:
        robots = await fetch_text(robots_url_for(url))
    except Exception:  # noqa: BLE001 — a missing robots file does not block the page
        robots = ""
    if robots and not robots_allows(str(robots), url):
        row = await store.add_observation(_obs(tenant_id, url, clock(), None, None, None, "robots", "robots"))
        return {"status": "robots", "url": url, "alerts": [], "observation": row}

    await limiter.wait(host)
    page = await render(url, session_for_url(url), agent, str(tenant_id))
    if page.get("challenge"):
        row = await store.add_observation(_obs(tenant_id, url, clock(), None, None, None, "blocked", "blocked"))
        return {"status": "blocked", "url": url, "alerts": [], "observation": row}
    html = page.get("html") or ""
    if not page.get("ok") or not html:
        detail = str(page.get("error") or "unread")[:300]
        row = await store.add_observation(_obs(tenant_id, url, clock(), None, None, None, "error", detail))
        return {"status": "error", "url": url, "alerts": [], "observation": row}

    extracted = await extract(html, url)
    items = list(extracted.get("items") or [])
    chosen = next((item for item in items if item.get("price")), None)
    method = extracted.get("method")
    png = page.get("png_base64")
    if chosen is None and png:
        read = await ocr(png, url)
        priced = [item for item in (read.get("items") or []) if item.get("price")]
        if priced:
            chosen = priced[0]
            method = "ocr"
    if chosen is None and items:
        chosen = items[0]
        method = chosen.get("method") or method
    price = chosen.get("price") if chosen else None
    currency = chosen.get("currency") if chosen else None
    availability = chosen.get("availability") if chosen else None
    method = method or "none"
    saved_file = _save_png(files, str(tenant_id), png if isinstance(png, str) else None, clock())
    current = await store.add_observation(_obs(
        tenant_id, url, clock(), price, currency, availability, method, _evidence(method, price, saved_file),
    ))
    previous = await store.previous_observation(tenant_id, url, current["id"])
    found = alerts_for(previous, current, watch.get("threshold") or 0)
    saved_alerts = []
    for alert in found:
        saved_alerts.append(await store.add_alert({
            "tenant_id": tenant_id,
            "url": url,
            "ts": clock(),
            "kind": alert["kind"],
            "before": alert["before"],
            "after": alert["after"],
        }))
    return {
        "status": "observed",
        "url": url,
        "method": method,
        "price": price,
        "alerts": saved_alerts,
        "observation": current,
    }


async def dispatch_tenant(store: Any, tenant_id: str, now: datetime) -> dict[str, Any]:
    queued: list[str] = []
    for watch in await store.enabled_watches(tenant_id):
        last = await store.latest_observation(tenant_id, watch["url"])
        last_ts = _parse_ts(last.get("ts")) if last else None
        if not watch_is_due(str(watch["every"]), now, last_ts):
            continue
        if await store.check_open(tenant_id, watch["url"]):
            continue
        await store.enqueue_check(tenant_id, watch["url"])
        queued.append(watch["url"])
    return {"queued": queued}
