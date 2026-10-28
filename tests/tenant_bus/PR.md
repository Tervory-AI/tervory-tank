# Tenant-scoped job contract and Redis event bus

Branch `codex/e1-e3-tenant-bus`, from `origin/main` at `73a0e2f`.

Scope: shared job contract without room-table changes; tenant/event Redis Streams,
agent groups, acknowledgements, five-attempt dead letters, bounded retention;
six completion producers and one Rig price-history consumer reusing #386.
Redis failure must not fail product work. Event payloads contain IDs and facts only.
No page or model changes. Offline evidence and exact assessor steps will be recorded here.

## Blocked before implementation

Fetched main is `73a0e2f` (28 October). #386 is present, but its destination is
the current catalogue price, not a retained product price history:

- `agents/rig/rigbox/service.py:752` (`apply_watch`) validates the tenant, SKU,
  source URL and timestamp, then calls `update_price`.
- `agents/rig/rigbox/store.py:988` (`PgStore.update_price`) overwrites
  `agent_rig.products.price/currency/active/updated_at`. It inserts no history.
- `agents/rig/schema.sql:59` (`tiger_receipts`) has primary key
  `(tenant_id,sku,url)` and only one `observed_at`; the writer at
  `agents/rig/rigbox/retailer_store.py:129` overwrites that timestamp.
- `agents/rig/schema.sql:182` (`market_prices`) stores other sellers' prices
  keyed by `(tenant_id,sku,source)`, not changes to this product over time.
- `agents/rig/rigbox/cn.py:308` only passes through an imported
  `attributes.price_history` object. No Tiger or Rig completion path writes it.
- No price-history reader/page was found under `workspace/app/rig`.

Verification commands (read-only; no GitHub API):

```sh
git fetch origin main
git log -1 --oneline origin/main
rg -n -i --max-columns 180 'price.?history|historical.?price|previous.?price|old.?price' agents/rig/rigbox workspace/app/rig --glob '*.py' --glob '*.ts' --glob '*.tsx' --glob '!*.umd.js'
sed -n '752,783p' agents/rig/rigbox/service.py
sed -n '988,1010p' agents/rig/rigbox/store.py
sed -n '59,68p' agents/rig/schema.sql
sed -n '180,194p' agents/rig/schema.sql
```

Search result: only `cn.py:308-309`, the imported-attribute pass-through.
The stated acceptance check requires a real history destination and existing
display path. Substituting the current-price field or creating a new history
store/page would change the brief. Rule 9 requires stopping and reporting this
missing component rather than guessing or working around it.

This branch contains this documentation only. No E1/E2/E3 implementation,
schema change, test execution, deployment or live acceptance is claimed.
No PR has been opened.
