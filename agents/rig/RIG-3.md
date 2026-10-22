# RIG-3 retailer feeds

`/rig/admin` is available to the active tenant's Clerk organization administrator or a listed founder. Every operation resolves that identity server-side, goes through Tank, and uses a separate Tank-to-Rig retailer credential. The browser never receives a room key, stored supplier credentials, source amounts, saved price rules or exchange rates.

## Import and refresh

Use `/v1/access/rig/admin/import`, `/connect` and `/refresh` through the authenticated retailer admin. These call ACCESS-1's existing feed parsing, connection vault, refresh and receipt functions. The general `/v1/access/feeds/*` routes retain Tiger authorization before body parsing and refuse a Rig target; the general Workspace Access proxy also rejects `target`. The distributor field accepts `shopify`, `woocommerce`, `google`, `zanders`, `sports_south`, `rsr` and `jerrys`. Shopify and WooCommerce use JSON, Google Merchant uses XML, and distributors use CSV, TSV or JSON catalogue exports. Inventory-only EDI lacks product labels and is refused for catalogue creation. Map nonstandard columns in the admin; the existing distributor price/quantity adapters remain in use.

Connections use the existing ACCESS vault and same-site, pinned HTTPS fetcher. Public, bearer, Shopify header and HTTP Basic/WooCommerce credentials are supported. Credentials are entered only in the authenticated connection form and stored encrypted. Configure a read-only export URL or the first Shopify/WooCommerce REST page, without a query or embedded credentials. Pagination follows Shopify's next-page link or WooCommerce's total-page count, stays on the same host and path, and accepts only pagination query fields. All pages are collected before import, with a combined 8 MB / 100-page limit. Other sources supply complete files. File imports need no vault or supplier credentials.

ACCESS owns the refresh schedule: 03:00 UTC, plus **Refresh now**. Its `rig_feed_loop` runs in Tank's existing ACCESS lifespan because Tank alone owns the encrypted feed credentials, pinned supplier fetcher and durable schedule rows. Rig never receives those credentials. The loop starts and stops with ACCESS, claims only due `rig:` rows with `FOR UPDATE SKIP LOCKED`, and leaves Tiger's refresh behavior unchanged. The connection name has a `rig:` prefix so Tiger's existing connections are retained. A failed fetch is recorded as `feed_refresh_failed` for nightly runs. It does not replace catalogue data. A completed file produces `{added, updated, rejected}` in `agent_rig.feed_receipts`, mirrored in `tank.access_feed_batches.rig_summary` and the existing ACCESS receipt stream. Rig stores the import and its receipt in the same transaction. If Tank loses its connection after a commit, check import history before retrying; the UI does not claim that the import was rolled back.

All rows, families, fit references and template defaults are validated before the transaction commits. A bad row rejects the whole file. Re-importing a valid file updates its SKUs. Feed-supplied fits enter the review queue as `source='suggested'`, with evidence, and remain invisible until approved. Refreshes and later suggestions preserve human approvals/rejections. When a feed supplies no fits, the existing `rig.fit_suggest` route is used; unavailability is reported separately from a successful import. No new paid provider or route is added.

## Private prices

The retailer replaces its private rule by entering all three fields. Freight is per item in supplier currency; duty and gross margin are percentages. The founder sets a per-tenant source-currency-to-ZAR rate. ZAR itself is always 1. Prices use decimal arithmetic and round once to cents:

`((supplier cost + freight) × (1 + duty / 100) × ZAR rate) / (1 - gross margin / 100)`

Feed amounts are treated as supplier costs. They live in `agent_rig.supplier_costs`, separate from public products. Only the calculated indicative ZAR amount is written to `agent_rig.products`. Saving a rule or rate reprices the tenant's imported products in one transaction. The admin receives only a configured flag, never the stored rule or inputs. Missing rules/rates reject imports rather than inventing a price.

Tiger can call `POST /v1/access/rig/tiger` with its own existing key and the tenant, SKU, price, currency and/or availability. Tank forwards that narrow update to Rig. A product belonging to a feed is refused; fitment is never updated by this path.

## Configuration and deployment

Configure a new, distinct `RIG_RETAILER_KEY` in Coolify on **Tank and agent-rig only**. The empty name is declared in `.env.example`; no value is committed. Do not give it to rig-brain, a browser gateway, Hermes or Workspace. Tank calls `http://agent-rig:8003/internal/retailer/*` with this key and derives tenant/founder status from its own authenticated actor. The private listener shares the catalogue service and application lifespan. Traefik routes only port 8000, where retailer control paths do not exist; port 8003 is never published on the host. With the key absent, the listener stays off and Tank refuses retailer operations. Reuse `TANK_VAULT_KEY` on Tank and `TERVORY_ADMIN_USER_IDS` on Tank/Workspace. Sample file imports need no live supplier credentials.

Deploy Tank, agent-rig and Workspace after review. Both schemas are additive and idempotent. This lane changes no room networks, quote flow, widget bundle or 3D code. The compose additions pass the dedicated retailer key to its two owners only. Live Custom Nation shopper data still belongs on the future ZA host; the following checks use synthetic office products only.

## Prove it after deploy

1. Check that a POST to `https://rig.tervory.com/internal/retailer/panel` returns 404, including with the existing room key. From Tank's corridor, the private port must reject the room key and accept only `RIG_RETAILER_KEY`; never place either value in commands, logs or URLs. Sign in as the sample tenant's organization admin and open `/rig/admin`. Set a private price rule. As founder, set that tenant's USD-to-ZAR rate.
2. Import `catalogues/samples/shopify.json` as Shopify, USD, using a sample supplier website. Check that two rows were added and that the receipt is visible. Import `distributor.csv` as Zanders and confirm one added row. The WooCommerce and Google files exercise the other mappings.
3. Check the sample shade in the fit queue. Before approval it must be absent from the shopper's approved combinations. Approve it, verify it appears, then refresh/re-import and confirm the decision remains intact. Reject it and confirm it is removed.
4. Inspect the browser's product/admin responses: one indicative price only; no stored cost, freight, duty, margin, FX or credential values. Change the private rule and verify the product price changes.
5. Connect a controlled read-only sample endpoint, press **Refresh now**, and verify `tank.access_feed_connections.rig_refresh_at`. After the scheduled run check the tenant's `tank.access_receipts` and `agent_rig.feed_receipts` rows. An unavailable supplier must leave the prior catalogue intact.
6. Search for an absent sample product; check the admin's unmatched searches. A second tenant must see none of the first tenant's products, review queue, templates, connections or receipts.

## Validation artifacts

The Python tests also prove public control paths return 404, brain keys cannot control retailers, Tank supplies founder status, XML declarations are rejected before parsing, and Tiger's feed formats/permissions remain unchanged. They cover the sample providers, all four distributor adapters, tenant boundaries, private pricing, review visibility, refreshes, real PostgreSQL rollback and schema reapplication. `tests/rig_feeds_admin_browser.mjs` exercises the production component against synthetic responses and writes the 375px/1440px screenshots to a temporary directory (`RIG_SCREENSHOT_DIR` can override it). The Rig-only review workflow uploads `rig-admin-screenshots` as a PR check artifact; PNGs are not tracked in the repository. These are component fixtures, not authenticated production screenshots. Its dependencies can be supplied using `RIG_ESBUILD_PATH`, `RIG_PLAYWRIGHT_PATH` and `READ1_CHROMIUM_EXECUTABLE`.
