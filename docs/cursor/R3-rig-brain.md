# R3 — Rig's brain: its own room, the public API, and the catalogue feed

> **Room setup:** follow `docs/cursor/ROOMS.md` exactly. Rig is the one agent with a public address.

**Goal:** the widget (`Tervory-AI/tervory-rig`) stops using sample data and talks to a live Rig API, loaded with the catalogues of the brands we already work with, so we can test with real products before any retailer integrates. Depends on C6/C7 (live). Read `tervory-rig/AGENTS.md` and `tervory-rig/docs/api.md` first: the API contract there is fixed; build to it exactly.

**Files you may change:** `agents/rig/` (new, from `agents/_template/`), `tank/skills/rig.*` (1.0.0 each, evals + CHANGELOG), `docker-compose.yml` (additive: declare corridor `tervory-gw-rig` as a compose-managed network per ROOMS.md Deploy order step 1, and join it to tank/postgres/hermes; `TANK_KEY_RIG` on tank **and** hermes; `AGENT_DB_PASSWORD_RIG` on agent-roles), `.env.example` (names only), `agents/README.md` (one row), new tests under `tests/`.

## The room
- Corridor `tervory-gw-rig`, login `agent_rig`, key `TANK_KEY_RIG`. Public domain `rig.tervory.com` (the only agent with one; Claude sets it in Coolify). `mem_limit 512m`.
- Every request carries a retailer's **publishable key** in `X-Rig-Key` (`rk_pub_…`). Each key belongs to one tenant (retailer) and has an allowed-origins list; requests from other origins are refused (CORS + server check). Rate limit per key (default 60/min). Publishable keys are not secrets but are stored hashed.

## Tables (`agent_rig`, all tenant-scoped)
- `products (tenant_id, id, sku, gtin, name, brand, category, price, currency, image_url, url, attributes jsonb, active, updated_at)`
- `fits (tenant_id, part_sku, fits_sku, fits_family, rule jsonb, source, confidence)`: one row per "this part fits that". `rule` holds attribute rules, e.g. `{"thread": "1/2x28"}`, `{"rail": "picatinny"}`, `{"length_mm": [400, 520]}`.
- `families (tenant_id, family, member_skus[])`: models that share fitment (e.g. every model on one platform).
- `setup_templates (tenant_id, category, roles jsonb)`: which roles a setup has for a centre product (e.g. optic, mount, sling, case), and the tier labels.
- `keys (tenant_id, key_hash, kind publishable|admin, origins[], created_at)`, `quotes (tenant_id, id, payload, contact, created_at, sent_at)`.

## Feeding the data (the exact way: `docs/rig/catalogue-feed.md`)
Three routes into the same tables, in this order of preference:
1. **Spreadsheet import (start here, for the brands we already have).** Two CSV files per brand: `products` and `fits`, columns exactly as `docs/rig/templates/products.csv` and `fits.csv` (guide: `docs/rig/catalogue-feed.md`). They live in the repo at `agents/rig/catalogues/<tenant-slug>/products.csv` and `fits.csv` (Claude adds them by pull request; no keys involved). On start, Rig imports every catalogue folder: validates every row, upserts by `(tenant, sku)`, never half-imports a file, and logs `{added, updated, rejected: [{row, reason}]}`. Ship one fixture brand in `agents/rig/catalogues/example/` for tests. (An admin upload endpoint comes later, behind `RIG_ADMIN_KEY`.)
2. **Feed URL.** Shopify `products.json`, WooCommerce REST, or a Google Merchant XML feed: register once, pulled nightly, mapped to the same columns. Map one per format; add others later.
3. **Tiger.** For a brand with no feed, Tiger's price-mining watchlist supplies price/availability updates only (never fitment).

Fitment is the valuable part. If a brand has no fitment data, the `fits` sheet can be partly filled by `rig.fit_suggest` (below), but suggested rows are stored with `source = 'suggested'` and **never shown to a shopper until a person approves them** (`confidence` + an approve call).

## Skills (Skala, agent `rig`)
- `rig.search@1.0.0` (pure code): Postgres full-text + trigram on name/brand/sku/attributes, tenant-scoped. (Meilisearch is a later swap behind the same skill.)
- `rig.setups@1.0.0` (pure code): from `fits` + `families` + `setup_templates` build the tiers. **Only parts with an approved fit row may appear.** Prices from `products` only; one indicative total, never a breakdown (widget rule 3).
- `rig.explain@1.0.0` (model via Tank, task type `rig.explain`): writes the `why` lines from the fit rows it is given; it cannot add parts.
- `rig.ask@1.0.0` (model via Tank, task type `rig.ask`): answers only from the catalogue and fit rows passed in, citing product ids; "I don't know" otherwise.
- `rig.fit_suggest@1.0.0` (model via Tank): proposes fit rows from product attributes; output is always `source='suggested'`, unapproved.
- Policy rows for the three model task types (`rig.explain`, `rig.ask`, `rig.fit_suggest`): append them to `tank/schema.sql` (additive, `ON CONFLICT DO NOTHING`, model `luna`, cache_scope `tenant`). This brief allows that one change to `tank/schema.sql`. Tests mock Tank.

## API
Implement every call in `tervory-rig/docs/api.md` with the exact shapes. `quote` and `link-quote` store the request and notify the retailer by email/webhook configured per tenant (stub the sender behind an interface; no real email in tests).

## Done when
CI green; an import of a sample brand (fixtures, not real data) loads products and fits; `setups` returns only approved-fit parts with one total; `ask` refuses to answer outside the catalogue; a key from one tenant never sees another tenant's products (tested); after Claude deploys, the widget pointed at `https://rig.tervory.com` shows real search results for one test brand.
