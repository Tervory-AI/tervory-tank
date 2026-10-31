# Prompt2 supplier locate evidence

2026-10-31 02:06 PDT / 09:06 UTC. Source checkpoint: ff096536 (production code identical to independently reviewed 282e28de). Draft Tank PR https://github.com/Tervory-AI/tervory-tank/pull/463; companion widget draft https://github.com/Tervory-AI/tervory-rig/pull/9 at 8c220d6. Founder alone merges. This is backend implementation evidence, not complete browser acceptance.

## Changes and wiring

| File and line | Behavior |
| --- | --- |
| agents/rig/schema.sql:408 | Additive/idempotent store-scoped approved sources, offers, explicit SKU maps, MPN and stock-depletion provenance; located counters and receipt ledger. No production application. |
| agents/rig/rigbox/feeds/catalogue.py:271 | Retains quantity, ETA, ship days, region, MPN; distinguishes zero stock from explicitly disabled items. |
| agents/rig/rigbox/catalogue.py:194 | Direct store imports retain MPN. |
| agents/rig/rigbox/store.py:627 | Persists product MPN and supply eligibility. |
| agents/rig/rigbox/locate.py:41 | Admin-provided bounded snapshots reuse the existing parser, reject bad rows atomically, and refuse older observations overwriting newer ones. |
| agents/rig/rigbox/locate.py:135 | Approved tenant network only. GTIN, then brand+MPN, then store-maintained SKU mapping. Fresh available quantity first, then landed cost, ship days, supplier priority, stable identity. Reuses confirmed pricing/FX and supplier/region scopes. No model call. |
| agents/rig/rigbox/locate.py:184 | Generic catalogue resolution keeps store identity/fit rules, never revives deliberately disabled products. Historical inactive rows without stock provenance require a confirmed feed refresh. |
| agents/rig/rigbox/service.py:315 | Both existing search paths use resolved catalogue rows; recall version includes resolved availability, so stale supplier results are not reused. Product/setup pricing also uses resolved rows. |
| agents/rig/rigbox/service.py:655 | Server-built quote locate block keeps public and store projections separate. No client-supplied supplier or price evidence. |
| agents/rig/rigbox/cn.py:301 | Preserves resolved availability through existing stock presentation/filtering. |
| agents/rig/rigbox/logic.py:25 | Public product projection includes only status and actual ETA from availability. |
| agents/rig/rigbox/quotes/privacy.py:6 | Recursively removes supplier, cost, ship-from, region and private store evidence from shopper serialization. |
| agents/rig/rigbox/api.py:205 | Authenticated POST /v1/rig/locate; public product ID only. |
| agents/rig/rigbox/api.py:349 | Admin-only approved source configuration, catalogue snapshot import and explicit SKU map endpoints. Existing feed pricing identity supported. |
| agents/rig/rigbox/quotes/senders.py:86 | Odoo internal chatter mail.mt_note; supplier evidence is absent from customer-facing order notes/lines. Reconciles lost note responses. No confirm, payment, invoice or supplier order. |
| agents/rig/rigbox/quotes/store.py:170 | Located count is persisted supplier-backed quote requests, once at creation, separate from delivery retries. Unavailable/stale-only requests do not count as located. |
| agents/rig/rigbox/supply_accounting.py:16 | Idempotent admin-reported receipt ledger with tenant, quote/product reference, signed net amount, original currency, source reference and timestamp; concurrent retries count once. Does not verify an external accounting system or take payment. |
| agents/rig/rigbox/quotes/api.py:22 | Admin analytics expose located-count provenance and revenue grouped by original currency. No receipt means null revenue, never quoted-value estimates. |
| agents/rig/rigbox/quotes/api.py:112 | Admin-only sale-receipt recording. Refunds can be separate signed receipts; no currency conversion. |
| tervory-rig widget/src/api/client.ts:54 | Public locate contract only. Offline mode returns unavailable and fabricates no supplier observation. |

The brief's shorthand agents/rig/feeds and agents/rig/quotes resolve to the existing agents/rig/rigbox/feeds and agents/rig/rigbox/quotes. Coordinator explicitly confirmed this correction. No directories moved. Existing #366/#454 and historical dirty widget checkout were untouched. Isolated checkouts: /tmp/tervory-prompt2-supply-20261031 and /tmp/tervory-rig-prompt2-supply-20261031 on Boston.

## Exact verification commands and results

All Postgres commands below used a newly created disposable test container, not production. No credentials were required or exposed. Tests create/drop only uniquely named databases there.

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /tmp/tervory-prompt2-supply-20261031
git fetch origin main
git checkout -b codex/prompt2-supply-locate-20261031 origin/main
ls agents/rig/rigbox/feeds/catalogue.py agents/rig/rigbox/quotes/senders.py
```

Succeeded. Original shorthand `ls agents/rig/feeds agents/rig/quotes` failed; corrected paths authorized. Local git author initially unset; configured repository-local Codex identity, then commit succeeded. Every finished source/test file committed and branch pushed; no push failed. One commit sequence hit disk quota; deleting only this job's generated widget node_modules restored capacity. No unrelated checkout reset or cleanup.

```sh
docker run --detach --rm --name rig-prompt2-offline-postgres --env POSTGRES_HOST_AUTH_METHOD=trust --publish 127.0.0.1::5432 postgres:16.15
docker port rig-prompt2-offline-postgres 5432
```

Succeeded; assigned 127.0.0.1:32772. An earlier explicit port 55439 was allocated, so the failed container start was replaced with Docker-assigned loopback port. No existing container was changed.

```sh
PYTHONPATH=agents/rig:agents/_chassis /tmp/tervory-job8-python/bin/python -m pytest tests/test_rig_feeds_catalogues.py tests/test_rig_recall.py tests/test_rig_quotes_postgres.py -q
```

Initial regression: 33 passed, 7 skipped (no test DB configured yet), 2 warnings, 1.78s; /tmp/prompt2-initial-tests.log.

```sh
RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32772/postgres PYTHONPATH=agents/rig:agents/_chassis /tmp/tervory-job8-python/bin/python -m pytest tests/test_rig_supply_locate.py -q
```

Final focused: 19 passed, 1 warning, 1.46s; /tmp/prompt2-supply-tests6.log. Reviewer independently ran the same 19 against the disposable instance: 19 passed, 1.06s. Includes schema applied twice, MPN/import/map roundtrip, freshness, disabled-item protection, pricing scopes/priority, API admin/public boundary, redaction, receipt atomicity/retries/currency separation, Odoo internal note lost-response reconciliation, and all four new tables under existing opt-in RLS policies with a non-superuser. API route test uses explicit auth stand-ins; it does not claim to test cryptography.

An intermediate focused run failed 2 tests: missing test contact fields and a semicolon in a new SQL comment confusing the existing schema splitter. Both fixed before final results. Earlier 9/12/14/15-test checkpoints are superseded by 19.

```sh
RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32772/postgres PYTHONPATH=agents/rig:agents/_chassis /tmp/tervory-job8-python/bin/python -m pytest tests/test_rig_supply_locate.py tests/test_rig_feeds_catalogues.py tests/test_rig_feeds_mapping.py tests/test_rig_feeds_pricing.py tests/test_rig_quotes.py tests/test_rig_quotes_postgres.py tests/test_rig_recall.py tests/test_rig_cn_archon.py tests/test_rig_postgres.py tests/test_rig_isolation.py -q
```

260 passed, 2 existing warnings, 15.98s; /tmp/prompt2-final-regression.log. A smaller earlier regression passed 251 tests in 13.13s. Samples, including catalogues/samples/distributor.csv, were used offline only and never placed on a live screen. Sample's short non-standard UPC requires explicit SKU mapping; no GTIN or ETA was invented.

```sh
/tmp/tervory-job8-python/bin/python -m ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
git diff --check
```

Both passed; /tmp/prompt2-ruff.log. Hosted Tank job 124495720271 first failed F401 for an unused test import; removed only that import in ff096536. New hosted checks pending. This is a diagnosed source fix, not a blind rerun.

Widget checkout:

```sh
npm ci --ignore-scripts
npm run lint
npm run build
npx vitest run
```

All exit 0. 23 unit tests across 3 files passed in 522ms, including 2 new locate client tests. Build includes TypeScript checking, ES/UMD builds and existing no-sample-data bundle check. Logs: /tmp/prompt2-widget-install2.log, /tmp/prompt2-widget-lint.log, /tmp/prompt2-widget-build2.log, /tmp/prompt2-widget-vitest.log. No browser rendering change or browser acceptance claimed. Widget hosted job 124495790419 had no steps/runner and did not start: GitHub annotation reports failed account payments or spending limit. No billing/settings changes or CI workaround performed.

## Review and remaining boundaries

Independent review thread 01a18da9-bec9-7291-a09e-23bbb838df8d cleared Tank production code at 282e28de and widget code at 8c220d6. Refresh requested after test-only import removal ff096536. Both PRs remain drafts while checks/approval remain incomplete. No merge, main push, deployment or live configuration change.

New tables receive explicit tenant predicates everywhere. Existing db/migrations/tenant_rls/agent_rig.sql discovers all tenant tables, but is opt-in and must be re-applied through the founder-approved migration workflow after new tables exist if DB-level RLS is required. Startup does not silently activate that policy. This boundary was tested only in the disposable DB; no production migration run.

Figma file uRpPy3Hns0WxWZYTPwZ2ni, actual page 0:1, session ff9f9b7f-acad-40c5-9055-f4e4bafad92c inspected via metadata. Existing result frames 2:41 and 7:41, and full page, contain neither “Available to order” nor exact “Request” button. Missing: an approved availability-chip/Request frame with exact founder copy “Available to order, ETA x”, its real ETA formatting, and approved admin presentation for new metrics. render.ts and /rig/admin visual presentation unchanged. Backend/client work continued independently. No Figma modifications, invented UI copy or fake ETA.

Store inputs required: approved supplier account/source identity (names only; founder fills secret values), confirmed catalogue format/product-list path/field map/currency, supplied quantity/status and real ETA/ship days/region, observation timestamps, maximum offer age, supplier priority, existing confirmed price rule and FX where currencies differ, and explicit SKU maps when GTIN or brand+MPN are absent. Revenue additionally requires actual store-reported accounting receipt IDs/references, net amounts, original currency and timestamps. No source account/feed or real sale receipt was fabricated.

Founder browser acceptance and screenshots are LAST and pending. No screenshot is presented as founder proof. No model call or model-based checking, no production SQL, no live fixture data, no secrets read/created, no ZA/worker investigation, no payment/auto-ordering. Optional sale_rules were not implemented.
