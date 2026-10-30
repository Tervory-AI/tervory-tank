# Automatically keep unfed Rig products current through Tiger

Rig already accepts Tiger price updates, but nothing sends them. This change
discovers each tenant's eligible products, creates ordinary Tiger watches, and
sends confirmed price/stock readings through Tank's existing
`POST /v1/access/rig/tiger` receiver. It implements the founder's automatic-watch
decision of 28 Oct 04:10 PT, with no page, control or copy changes.

Branch: `codex/rig-tiger-prices`. Started from main
`bde4578cfbfbdcdd2ba5fa76cd91d4bc54669df5`. Tested implementation: `5e57e5d`.
Claude opens the PR. Nothing has been merged or deployed.

Verification: 250 relevant tests pass. The one-door guard has an identical
pre-existing failure on starting main; evidence is below. Founder browser
proof remains pending deployment.

## Behaviour

- The existing scheduler discovers Rig tenants every minute. Each tenant's
  existing dispatch job reconciles products with page URLs and no supplier
  feed or deletion tombstone. New watches use Tiger's existing six-hour
  default, with an initial queued check. A watch starts disabled until its
  tenant/SKU binding and managed flag commit together.
- A tenant's SKUs sharing a page share one watch. Matching existing watches
  retain their interval and alert preferences. New automatic watches have
  email alerts off; their purpose is to update Rig. Unrelated watches remain
  under their existing settings.
- Every managed check revalidates eligibility before reading. Gaining a feed,
  losing/changing the URL, or deletion removes obsolete bindings and pending
  deliveries, disables unused managed watches and cancels their queued checks.
  A shared watch continues only while another eligible SKU uses it. An
  out-of-stock product remains watched so it can return to stock.
- The existing URL validation, browser scope boundary, domain limiter,
  extraction and schedule code perform the reads. No new model/provider path,
  key, setting or service is introduced. Existing deployment bindings are
  reused by name: Tiger's `TANK_URL`/`TANK_KEY`, Tank's `TANK_KEY_TIGER` and the
  existing private Rig relay settings.
- Complete readings seed the initial price/stock and queue subsequent changes.
  Observation and pending delivery commit in one transaction. A failed send
  survives restart and retries on dispatch after 60 seconds, doubling to a
  one-hour ceiling. An unchanged reading retains that retry; a newer changed
  reading replaces the pending value. Delivery attempts are bounded to 20
  per dispatch/check. Acknowledgement cannot discard a newer pending value.
- Rig rechecks tenant, SKU, current URL, feed ownership and deletion under its
  existing tenant lock. Timestamp receipts make retries idempotent and prevent
  older readings from replacing newer prices. No pricing or fitment formula
  changes.
- Legacy feed imports did not retain product provenance. The additive source
  index records it atomically with imports. A tenant with an unindexed legacy
  feed is held out of Tiger until a complete successful feed refresh; partial
  or failed refreshes cannot declare its products unfed. Supplier-cost-backed
  products are always excluded. No production backfill/SQL was run.

## What changed (file and line)

| File:line | Change |
| --- | --- |
| `agents/rig/rigbox/retailer_api.py:15`, `:46` | Private tenant discovery and per-tenant eligible-product operations; tenant discovery requires the platform identity. |
| `agents/rig/rigbox/retailer_store.py:22`, `:79`, `:113`, `:185` | Memory/Postgres eligibility, delivery receipts and modern/legacy feed provenance. |
| `agents/rig/rigbox/service.py:750`, `:849` | Recheck delivery eligibility and timestamp under the tenant lock; record legacy feed membership with imported products. |
| `agents/rig/rigbox/store.py:258`, `:369`, `:890`, `:906` | Memory deletion cleanup, invalidate legacy feed indexing on registration, discover tenants with products even without a retailer row. |
| `agents/rig/schema.sql:59`, `:158` | Additive, idempotent delivery receipts, legacy-feed indexing flag and feed-product membership table. |
| `agents/tiger/Dockerfile:11` | Include the reconciliation module in the existing Tiger image. |
| `agents/tiger/app.py:18`, `:125`, `:154`, `:164`, `:172`, `:183` | Reconcile before managed reads, deliver after checks/on dispatch, add platform discovery through the existing scheduler. |
| `agents/tiger/rig_watch.py:20`, `:31`, `:47`, `:63`, `:102` | Additive Tiger state, validate confirmed readings, transactional delivery queue, Tank relay client, automatic reconciliation and retry. |
| `agents/tiger/watch.py:641`, `:779` | Apply additive watch state and save observation/delivery state atomically. |
| `tank/access.py:974`, `:984`, `:989`, `:1002` | Reuse Tiger authentication for discovery; accept URL/timestamp on the existing update route. |
| `tests/rig_tiger_prices/test_prices.py:33`, `:59` | Real Tank/Rig ASGI route tests for authentication, two tenants, eligibility and stale retries. |
| `tests/rig_tiger_prices/test_cycle.py:26`, `:54`, `:107` | Disposable Postgres stores, real Tiger handlers, offline saved pages and lifecycle/failure tests. |
| `tests/test_tiger.py:491` | Existing app/image wiring assertions include discovery and the new module. |
| `tests/test_tiger_alert_email.py:417` | Existing SMTP dispatch test stubs Rig delivery and verifies reconciliation receives the same tenant. |
| `tests/rig_tiger_prices/PR.md:1` | This description and command/results record. |
| `tests/rig_tiger_prices/evidence/{receiver,cycle-and-feeds,review-fixes,regression,main-guard,branch-guard,guard-comparison,lint}.txt:1` | Saved offline command outputs. |

## Required offline cases

The tests use two tenants with the same SKU and URL. No live product, page or
provider is used. Postgres fixtures create/drop unique databases on loopback;
both additive schemas are applied twice. Existing extraction code reads saved
HTML; any attempt to use the paid/OCR fallback fails the fixture.

| Requirement | Test |
| --- | --- |
| Price and stock reach Rig in the checking cycle; other tenant untouched | `test_one_cycle_price_stock_and_tenant_isolation` |
| Gaining a feed stops the next queued read; feed product untouched | `test_product_becoming_ineligible_stops_before_next_read[feed]` |
| Losing the URL stops watching | `test_product_becoming_ineligible_stops_before_next_read[no_url]` |
| Deleted product never discovered/reimported/watched | `test_deleted_product_is_never_discovered_even_if_reimport_attempted`; `test_product_becoming_ineligible_stops_before_next_read[deleted]` |
| Failed send persists and retries without reading again or crossing tenants | `test_failed_send_is_durable_retries_without_rereading_and_keeps_tenant` |
| A pending update is removed after feed assignment/deletion | `test_shared_watch_pending_removed_when_products_become_ineligible[feed/deleted]` |
| Shared URL uses one read for both SKUs | `test_shared_url_updates_each_sku_once_with_one_read` |
| Scope limits and incomplete/blocked readings | `test_scope_blocks_private_urls_and_challenges_never_publish`; `test_incomplete_observations_never_queue` plus existing Tiger public-policy/limiter tests |
| Legacy feed products are protected | `test_legacy_feed_provenance_never_becomes_a_page_watch` |
| Changed URL cancels old reads and starts the new page | `test_url_change_cancels_old_read_and_rebinds_to_new_page` |
| No observation saved without durable pending state | `test_observation_and_delivery_state_rollback_together` |
| No premature scheduling before ownership is committed | `test_new_watch_cannot_dispatch_before_rig_binding_commits` |
| Authenticated routes, late ineligible delivery, ordered/idempotent receipts | All tests in `test_prices.py` |

## Commands and results

Run in `/workspace/rig-tiger-prices` after
`source /workspace/tervory-env/activate.sh`. The local environment uses Python
3.12 and disposable Postgres on loopback. Its missing SMTP test dependency was
installed from the existing pin in `tank/requirements-dev.txt` with:

```sh
uv --cache-dir /tmp/rig-tiger-uv-cache pip install --python /workspace/tervory-env/venv/bin/python aiosmtpd==1.4.6
```

Final relevant regression run (exit 0):

```sh
TIGER_MAIL_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/pooltest python -m pytest -q tests/test_tiger.py tests/test_tiger_public_policy.py tests/test_tiger_works.py tests/test_tiger_alert_email.py tests/test_tg2_tiger_watchlist.py tests/rig_tiger_prices tests/test_rig_feeds.py tests/test_rig_feeds_retailer.py tests/test_rig_delete_products.py tests/test_rig_isolation.py tests/test_access1_review.py
```

**250 passed, 6 warnings in 91.07s (0:01:31)** — [regression output](evidence/regression.txt).
Warnings are the existing Starlette/FastAPI deprecations. The SMTP Postgres
test ran; it was not skipped.

Earlier committed checkpoints, each pushed with git:

| Command | Result / output |
| --- | --- |
| `python -m pytest -q tests/rig_tiger_prices/test_prices.py tests/test_rig_feeds_retailer.py` | 31 passed, 1 warning in 1.55s; [receiver](evidence/receiver.txt), commit `3093777`. |
| `python -m pytest -q tests/rig_tiger_prices tests/test_rig_feeds.py tests/test_rig_feeds_retailer.py tests/test_rig_delete_products.py` | 77 passed, 1 warning in 8.19s; [cycle/feed](evidence/cycle-and-feeds.txt), commit `e40e604`. |
| `python -m pytest -q tests/rig_tiger_prices tests/test_tiger_alert_email.py::test_dispatch_job_runs_delivery` | 27 passed in 5.72s; [race/wiring fixes](evidence/review-fixes.txt), commit `5e57e5d`. |

Lint (exit 0, [output](evidence/lint.txt)):

```sh
ruff check --select E9,F agents/tiger/rig_watch.py agents/tiger/app.py agents/tiger/watch.py agents/rig/rigbox/retailer_store.py agents/rig/rigbox/service.py agents/rig/rigbox/store.py agents/rig/rigbox/retailer_api.py tank/access.py tests/rig_tiger_prices tests/test_tiger.py tests/test_tiger_alert_email.py
git diff --check
```

Result: `All checks passed!`; diff whitespace check produced no output.

Scope check (exit 0, no output):

```sh
git diff --exit-code bde4578 -- workspace agents/_chassis tank/main.py tests/test_tank_one_door.py tests/tank_batch_providers
```

### Existing one-door failure, reproduced on starting main

The guard is **not green**. Both checkouts report the same two unaudited
findings at the unchanged `tests/tank_batch_providers/verify_passthrough.py:87`
(`assembled endpoint` / `model/paid endpoint`). No exception was added and no
guard or batch-provider code was changed by this branch.

```sh
git clone --no-hardlinks --no-checkout /workspace/rig-tiger-prices /tmp/rig-tiger-main-proof-20261028
git -C /tmp/rig-tiger-main-proof-20261028 checkout --detach bde4578cfbfbdcdd2ba5fa76cd91d4bc54669df5
cd /tmp/rig-tiger-main-proof-20261028
source /workspace/tervory-env/activate.sh
python -m pytest -q tests/test_tank_one_door.py
cd /workspace/rig-tiger-prices
python -m pytest -q tests/test_tank_one_door.py
```

Fresh main: **1 failed, 26 passed in 11.85s**, exit 1 — [output](evidence/main-guard.txt).
Branch: **1 failed, 26 passed in 11.76s**, exit 1 — [output](evidence/branch-guard.txt).
Comparing the complete scanner findings (including occurrence counts) confirms
they are identical, with zero new findings; exit 0 — [output](evidence/guard-comparison.txt):

```sh
python - <<'PY'
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0, 'tests')
import test_tank_one_door as guard
base = Path('/tmp/rig-tiger-main-proof-20261028')
branch = Path.cwd()
original = Counter(item.identity for item in guard.scan(base))
current = Counter(item.identity for item in guard.scan(branch))
print('Starting main:', 'bde4578cfbfbdcdd2ba5fa76cd91d4bc54669df5')
print('Branch findings identical to starting main:', current == original)
print('New finding occurrences:', sum((current - original).values()))
assert current == original
PY
```

## Founder browser proof — pending

The offline cycle is demonstrated. The live DONE condition and screenshots
are **not demonstrated**: this branch has not been deployed and the founder's
browser session is unavailable. No production data was changed to simulate it.

After founder merge/deployment, the remaining proof is a real, unfed Rig
product with its public product-page URL: the next successful Tiger check
must appear in Rig with that page's confirmed price/stock. The founder's
before/after screenshots, tenant/SKU and observation time must be attached
here. Feed assignment and deletion must stop subsequent watches.
