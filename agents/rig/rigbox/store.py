"""Tenant-scoped catalogue store. Every read and write takes a tenant_id."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from rigbox.logic import public_product

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema.sql"

_PRODUCTS = """
SELECT sku, gtin, name, brand, category, price, currency, image_url, url, family,
       attributes, active
FROM agent_rig.products
WHERE tenant_id = $1
"""

_SEARCH = """
SELECT sku, gtin, name, brand, category, price, currency, image_url, url, family,
       attributes, active
FROM agent_rig.products
WHERE tenant_id = $1
  AND active = true
  AND (
    to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(brand, '') || ' ' || coalesce(sku, '') || ' ' || coalesce(attributes::text, ''))
      @@ plainto_tsquery('simple', $2)
    OR similarity(coalesce(name, ''), $2) > 0.2
    OR similarity(coalesce(brand, ''), $2) > 0.2
    OR similarity(coalesce(sku, ''), $2) > 0.2
  )
ORDER BY ts_rank(
    to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(brand, '') || ' ' || coalesce(sku, '') || ' ' || coalesce(attributes::text, '')),
    plainto_tsquery('simple', $2)
  ) DESC,
  similarity(coalesce(name, ''), $2) DESC,
  sku ASC
LIMIT $3
"""

_SEARCH_FTS = """
SELECT sku, gtin, name, brand, category, price, currency, image_url, url, family,
       attributes, active
FROM agent_rig.products
WHERE tenant_id = $1
  AND active = true
  AND to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(brand, '') || ' ' || coalesce(sku, '') || ' ' || coalesce(attributes::text, ''))
      @@ plainto_tsquery('simple', $2)
ORDER BY ts_rank(
    to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(brand, '') || ' ' || coalesce(sku, '') || ' ' || coalesce(attributes::text, '')),
    plainto_tsquery('simple', $2)
  ) DESC,
  sku ASC
LIMIT $3
"""


def schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def schema_statements() -> list[str]:
    return [part.strip() for part in schema_sql().split(";") if part.strip()]


def _uuid(value: str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {})


def _fit_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("part_sku") or ""),
        str(row.get("fits_sku") or ""),
        str(row.get("fits_family") or ""),
    )


class MemoryStore:
    """In-memory stand-in. Tests never open a database."""

    def __init__(self) -> None:
        self._products: dict[tuple[str, str], dict[str, Any]] = {}
        self._fits: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self.families: dict[tuple[str, str], list[str]] = {}
        self.templates: dict[tuple[str, str], Any] = {}
        self.keys: dict[str, dict[str, Any]] = {}
        self.quotes: list[dict[str, Any]] = []
        self.retailers: dict[str, dict[str, Any]] = {}
        self.feeds: dict[tuple[str, str], dict[str, Any]] = {}

    async def product_exists(self, tenant_id: str, sku: str) -> bool:
        return (str(tenant_id), sku) in self._products

    async def upsert_product(self, tenant_id: str, row: dict[str, Any]) -> str:
        key = (str(tenant_id), str(row["sku"]))
        action = "updated" if key in self._products else "added"
        self._products[key] = {**row, "tenant_id": str(tenant_id), "sku": str(row["sku"])}
        return action

    async def products(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = [row for (tenant, _sku), row in self._products.items() if tenant == str(tenant_id)]
        return sorted(rows, key=lambda row: str(row.get("sku")))

    async def upsert_fit(self, tenant_id: str, row: dict[str, Any]) -> None:
        part, fits_sku, fits_family = _fit_key(row)
        self._fits[(str(tenant_id), part, fits_sku, fits_family)] = {
            **row,
            "tenant_id": str(tenant_id),
            "fits_sku": fits_sku or None,
            "fits_family": fits_family or None,
        }

    async def fits(self, tenant_id: str) -> list[dict[str, Any]]:
        return [row for key, row in self._fits.items() if key[0] == str(tenant_id)]

    async def set_family(self, tenant_id: str, family: str, members: list[str]) -> None:
        self.families[(str(tenant_id), family)] = list(members)

    async def set_template(self, tenant_id: str, category: str, roles: Any) -> None:
        self.templates[(str(tenant_id), category)] = roles

    async def templates_for(self, tenant_id: str) -> dict[str, Any]:
        return {category: roles for (tenant, category), roles in self.templates.items() if tenant == str(tenant_id)}

    async def put_key(self, tenant_id: str, key_hash: str, kind: str, origins: list[str]) -> None:
        self.keys[key_hash] = {
            "tenant_id": str(tenant_id),
            "kind": kind,
            "origins": list(origins),
        }

    async def key(self, key_hash: str) -> dict[str, Any] | None:
        row = self.keys.get(key_hash)
        return dict(row) if row else None

    async def put_retailer(self, tenant_id: str, slug: str, email: str | None, webhook: str | None) -> None:
        self.retailers[str(tenant_id)] = {"slug": slug, "email": email, "webhook": webhook}

    async def retailer(self, tenant_id: str) -> dict[str, Any] | None:
        row = self.retailers.get(str(tenant_id))
        return dict(row) if row else None

    async def put_feed(self, tenant_id: str, fmt: str, url: str, currency: str) -> None:
        self.feeds[(str(tenant_id), url)] = {"format": fmt, "url": url, "currency": currency}

    async def feeds_for(self, tenant_id: str) -> list[dict[str, Any]]:
        return [dict(row) for (tenant, _url), row in self.feeds.items() if tenant == str(tenant_id)]

    async def tenant_ids(self) -> list[str]:
        found = {tenant for tenant, _sku in self._products}
        found.update(self.retailers)
        return sorted(found)

    async def add_quote(self, tenant_id: str, quote_id: str, payload: dict[str, Any], contact: dict[str, Any]) -> None:
        self.quotes.append(
            {"tenant_id": str(tenant_id), "id": quote_id, "payload": payload, "contact": contact, "sent_at": None}
        )

    async def mark_sent(self, tenant_id: str, quote_id: str) -> None:
        for row in self.quotes:
            if row["tenant_id"] == str(tenant_id) and row["id"] == quote_id:
                row["sent_at"] = "sent"

    async def quotes_for(self, tenant_id: str) -> list[dict[str, Any]]:
        return [row for row in self.quotes if row["tenant_id"] == str(tenant_id)]

    async def approve_fit(self, tenant_id: str, part_sku: str, fits_sku: str | None, fits_family: str | None) -> bool:
        key = (str(tenant_id), part_sku, fits_sku or "", fits_family or "")
        row = self._fits.get(key)
        if row is None:
            return False
        row["approved"] = True
        return True

    async def update_price(self, tenant_id: str, sku: str, patch: dict[str, Any]) -> bool:
        row = self._products.get((str(tenant_id), sku))
        if row is None:
            return False
        if "price" in patch:
            row["price"] = patch["price"]
        if "currency" in patch:
            row["currency"] = patch["currency"]
        if "active" in patch:
            row["active"] = patch["active"]
        return True


def _record_product(row: Any) -> dict[str, Any]:
    attributes = row["attributes"]
    if isinstance(attributes, str):
        attributes = json.loads(attributes)
    return {
        "sku": row["sku"],
        "id": row["sku"],
        "gtin": row["gtin"],
        "name": row["name"],
        "brand": row["brand"],
        "category": row["category"],
        "price": row["price"],
        "currency": row["currency"],
        "image_url": row["image_url"],
        "url": row["url"],
        "family": row["family"] or "",
        "attributes": attributes or {},
        "active": row["active"],
    }


class PgStore:
    """Postgres for the live room. Search is full text plus trigram, always by tenant."""

    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def apply_schema(self) -> None:
        async with self.pool.acquire() as conn:
            for statement in schema_statements():
                optional = statement.upper().startswith("CREATE EXTENSION") or "GIN_TRGM_OPS" in statement.upper()
                try:
                    await conn.execute(statement)
                except Exception:
                    if not optional:
                        if statement.upper().startswith("CREATE SCHEMA"):
                            present = await conn.fetchval(
                                "SELECT 1 FROM pg_namespace WHERE nspname = 'agent_rig'"
                            )
                            if present == 1:
                                continue
                        raise

    async def product_exists(self, tenant_id: str, sku: str) -> bool:
        async with self.pool.acquire() as conn:
            found = await conn.fetchval(
                "SELECT 1 FROM agent_rig.products WHERE tenant_id = $1 AND sku = $2",
                _uuid(tenant_id),
                sku,
            )
        return found == 1

    async def upsert_product(self, tenant_id: str, row: dict[str, Any]) -> str:
        existed = await self.product_exists(tenant_id, str(row["sku"]))
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_rig.products
                    (tenant_id, id, sku, gtin, name, brand, category, price, currency,
                     image_url, url, family, attributes, active, updated_at)
                VALUES ($1, $2, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13, now())
                ON CONFLICT (tenant_id, sku) DO UPDATE SET
                    gtin = EXCLUDED.gtin,
                    name = EXCLUDED.name,
                    brand = EXCLUDED.brand,
                    category = EXCLUDED.category,
                    price = EXCLUDED.price,
                    currency = EXCLUDED.currency,
                    image_url = EXCLUDED.image_url,
                    url = EXCLUDED.url,
                    family = EXCLUDED.family,
                    attributes = EXCLUDED.attributes,
                    active = EXCLUDED.active,
                    updated_at = now()
                """,
                _uuid(tenant_id),
                str(row["sku"]),
                row.get("gtin"),
                row["name"],
                row["brand"],
                row["category"],
                row["price"],
                row["currency"],
                row.get("image_url"),
                row.get("url") or "",
                row.get("family") or "",
                _json(row.get("attributes") or {}),
                bool(row.get("active", True)),
            )
        return "updated" if existed else "added"

    async def products(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(_PRODUCTS + " ORDER BY sku", _uuid(tenant_id))
        return [_record_product(row) | {"tenant_id": str(tenant_id)} for row in rows]

    async def search_rows(self, tenant_id: str, query: str, limit: int) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            try:
                rows = await conn.fetch(_SEARCH, _uuid(tenant_id), query, limit)
            except Exception as exc:
                if "similarity" not in str(exc).lower() and "pg_trgm" not in str(exc).lower():
                    raise
                rows = await conn.fetch(_SEARCH_FTS, _uuid(tenant_id), query, limit)
        return [_record_product(row) | {"tenant_id": str(tenant_id)} for row in rows]

    async def upsert_fit(self, tenant_id: str, row: dict[str, Any]) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_rig.fits
                    (tenant_id, part_sku, fits_sku, fits_family, rule, source, confidence, approved, note)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9)
                ON CONFLICT (tenant_id, part_sku, fits_sku, fits_family) DO UPDATE SET
                    rule = EXCLUDED.rule,
                    source = EXCLUDED.source,
                    confidence = EXCLUDED.confidence,
                    approved = EXCLUDED.approved,
                    note = EXCLUDED.note
                """,
                _uuid(tenant_id),
                str(row["part_sku"]),
                str(row.get("fits_sku") or ""),
                str(row.get("fits_family") or ""),
                _json(row.get("rule") or {}),
                str(row.get("source") or "import"),
                row.get("confidence"),
                bool(row.get("approved")),
                str(row.get("note") or ""),
            )

    async def fits(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT part_sku, fits_sku, fits_family, rule, source, confidence, approved, note
                FROM agent_rig.fits WHERE tenant_id = $1
                """,
                _uuid(tenant_id),
            )
        out: list[dict[str, Any]] = []
        for row in rows:
            rule = row["rule"]
            if isinstance(rule, str):
                rule = json.loads(rule)
            out.append(
                {
                    "tenant_id": str(tenant_id),
                    "part_sku": row["part_sku"],
                    "fits_sku": row["fits_sku"] or None,
                    "fits_family": row["fits_family"] or None,
                    "rule": rule or {},
                    "source": row["source"],
                    "confidence": row["confidence"],
                    "approved": row["approved"],
                    "note": row["note"],
                }
            )
        return out

    async def set_family(self, tenant_id: str, family: str, members: list[str]) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_rig.families (tenant_id, family, member_skus)
                VALUES ($1, $2, $3)
                ON CONFLICT (tenant_id, family) DO UPDATE SET member_skus = EXCLUDED.member_skus
                """,
                _uuid(tenant_id),
                family,
                members,
            )

    async def set_template(self, tenant_id: str, category: str, roles: Any) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_rig.setup_templates (tenant_id, category, roles)
                VALUES ($1, $2, $3::jsonb)
                ON CONFLICT (tenant_id, category) DO UPDATE SET roles = EXCLUDED.roles
                """,
                _uuid(tenant_id),
                category,
                _json(roles),
            )

    async def templates_for(self, tenant_id: str) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT category, roles FROM agent_rig.setup_templates WHERE tenant_id = $1",
                _uuid(tenant_id),
            )
        found: dict[str, Any] = {}
        for row in rows:
            roles = row["roles"]
            if isinstance(roles, str):
                roles = json.loads(roles)
            found[row["category"]] = roles
        return found

    async def put_key(self, tenant_id: str, key_hash: str, kind: str, origins: list[str]) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_rig.keys (tenant_id, key_hash, kind, origins)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (key_hash) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    kind = EXCLUDED.kind,
                    origins = EXCLUDED.origins
                """,
                _uuid(tenant_id),
                key_hash,
                kind,
                origins,
            )

    async def key(self, key_hash: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT tenant_id, kind, origins FROM agent_rig.keys WHERE key_hash = $1",
                key_hash,
            )
        if row is None:
            return None
        return {"tenant_id": str(row["tenant_id"]), "kind": row["kind"], "origins": list(row["origins"] or [])}

    async def put_retailer(self, tenant_id: str, slug: str, email: str | None, webhook: str | None) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_rig.retailers (tenant_id, slug, email, webhook)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (tenant_id) DO UPDATE SET slug = EXCLUDED.slug, email = EXCLUDED.email, webhook = EXCLUDED.webhook
                """,
                _uuid(tenant_id),
                slug,
                email,
                webhook,
            )

    async def retailer(self, tenant_id: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT slug, email, webhook FROM agent_rig.retailers WHERE tenant_id = $1",
                _uuid(tenant_id),
            )
        if row is None:
            return None
        return {"slug": row["slug"], "email": row["email"], "webhook": row["webhook"]}

    async def put_feed(self, tenant_id: str, fmt: str, url: str, currency: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_rig.feeds (tenant_id, format, url, currency)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (tenant_id, url) DO UPDATE SET format = EXCLUDED.format, currency = EXCLUDED.currency
                """,
                _uuid(tenant_id),
                fmt,
                url,
                currency,
            )

    async def feeds_for(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT format, url, currency FROM agent_rig.feeds WHERE tenant_id = $1",
                _uuid(tenant_id),
            )
        return [{"format": row["format"], "url": row["url"], "currency": row["currency"]} for row in rows]

    async def tenant_ids(self) -> list[str]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT tenant_id FROM agent_rig.retailers")
        return [str(row["tenant_id"]) for row in rows]

    async def add_quote(self, tenant_id: str, quote_id: str, payload: dict[str, Any], contact: dict[str, Any]) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_rig.quotes (tenant_id, id, payload, contact)
                VALUES ($1, $2, $3::jsonb, $4::jsonb)
                """,
                _uuid(tenant_id),
                quote_id,
                _json(payload),
                _json(contact),
            )

    async def mark_sent(self, tenant_id: str, quote_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE agent_rig.quotes SET sent_at = now() WHERE tenant_id = $1 AND id = $2",
                _uuid(tenant_id),
                quote_id,
            )

    async def quotes_for(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, payload, contact FROM agent_rig.quotes WHERE tenant_id = $1",
                _uuid(tenant_id),
            )
        out = []
        for row in rows:
            payload = row["payload"]
            contact = row["contact"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            if isinstance(contact, str):
                contact = json.loads(contact)
            out.append({"id": row["id"], "tenant_id": str(tenant_id), "payload": payload, "contact": contact})
        return out

    async def approve_fit(self, tenant_id: str, part_sku: str, fits_sku: str | None, fits_family: str | None) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE agent_rig.fits SET approved = true
                WHERE tenant_id = $1 AND part_sku = $2 AND fits_sku = $3 AND fits_family = $4
                """,
                _uuid(tenant_id),
                part_sku,
                fits_sku or "",
                fits_family or "",
            )
        return result.endswith("1")

    async def update_price(self, tenant_id: str, sku: str, patch: dict[str, Any]) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE agent_rig.products SET
                    price = COALESCE($3, price),
                    currency = COALESCE($4, currency),
                    active = COALESCE($5, active),
                    updated_at = now()
                WHERE tenant_id = $1 AND sku = $2
                """,
                _uuid(tenant_id),
                sku,
                patch.get("price"),
                patch.get("currency"),
                patch.get("active"),
            )
        return result.endswith("1")


def as_public_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [public_product(row) for row in rows]
