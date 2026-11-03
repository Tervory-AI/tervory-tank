# Tiger T1: match the store catalogue to saved competitor sites

Tiger could watch manually supplied pages and Rig supplier URLs, but could not find competitors for the store's own catalogue. This change discovers pages on the tenant's saved Tiger Source origins, records identifier evidence, creates ordinary watches for confirmed matches, and returns price position through the existing `/chats` cards.

Branch: `codex/tiger-competitors`. Tested implementation: `556809f8`, including main `d6004c8d` through merge `fe1f605c`. Subsequent commits add evidence only. Claude opens the PR; the founder merges. Nothing was merged into main or deployed by this build.

**Acceptance is incomplete: founder-browser evidence and screenshots are missing.** Offline tests are not live acceptance.

## Changes, with file and line

| File | Change |
| --- | --- |
| [retailer_store.py:33](../../agents/rig/rigbox/retailer_store.py#L33), [Postgres:138](../../agents/rig/rigbox/retailer_store.py#L138) | Add GTIN, MPN, brand, price and currency to watch-products. The optional `catalogue=True` includes feed-backed products and products without supplier URLs. The default retains existing watch eligibility and deletion exclusions. |
| [retailer_api.py:50](../../agents/rig/rigbox/retailer_api.py#L50) | Forward the opt-in catalogue flag through the existing private operation. Tank's existing [products pass-through:992](../../tank/access.py#L992) already forwards the added fields without filtering them. |
| [rig_watch.py:290](../../agents/tiger/rig_watch.py#L290) | Durable host accounting: a PostgreSQL advisory lock serializes all workers/tenants for that public origin, requests are spaced by at least three seconds, and the UTC daily cap is 500 attempts. Reservations commit before transport, including failed attempts. Public counters contain no tenant data. |
| [rig_watch.py:366](../../agents/tiger/rig_watch.py#L366) | Discover robots-listed/default sitemaps and nested sitemap indexes, then GTIN searches through Shopify, WooCommerce and existing GET search forms. Enforce robots restrictions, same-origin HTTPS and human-check stops. No external search or model. |
| [app.py:63](../../agents/tiger/app.py#L63), [text fetch:89](../../agents/tiger/app.py#L89), [job:205](../../agents/tiger/app.py#L205) | Use existing fetch/render functions and the existing durable Tiger queue. Discovery text fetches are bounded and redirects are checked individually. The job has an explicit 24-hour maximum. |
| [browser.py:119](../../agents/_brain/browser.py#L119), [guard:446](../../agents/_brain/browser.py#L446) | Discovery uses one exact anonymous document GET per reservation. Assets, frames, redirects, POSTs and subsequent navigation are blocked. It does not reuse authenticated/held sessions, click age checks, or retain a challenge for solving. Existing `human_check` detects challenges. Ordinary browser callers retain their existing behavior. |
| [access.py:1175](../../tank/access.py#L1175), [matching:1185](../../tank/access.py#L1185), [reader:1202](../../tank/access.py#L1202) | Validate GTIN check digits and normalize to GTIN-14. Reuse the existing published structured price reader unchanged. Read JSON-LD/microdata Product identifiers with their own product scope; titles and competitor SKUs are never matching evidence. Refuse conflicting identifiers and ambiguous assignments of one URL to multiple own SKUs. |
| [access.py:1297](../../tank/access.py#L1297), [publication:1320](../../tank/access.py#L1320) | Save tenant/SKU/URL, method, identifiers seen, source page, timestamp and state. Exact GTIN matches confirm automatically. Brand+MPN without a page barcode stays suggested. Confirmed matches atomically bind `access_feed_links` and use the existing watch create path: new watches are enabled, every 6h, all five alerts on. Existing URL bindings are not overwritten; existing watches are reused. Human checks create a tenant access-queue record and stop that site. |
| [access.py:1382](../../tank/access.py#L1382), [decisions:1417](../../tank/access.py#L1417), [position:1482](../../tank/access.py#L1482), [card:1499](../../tank/access.py#L1499) | Tenant-scoped start/confirm/reject and GET position routes. Start/decisions require the existing durable Confirm binding. Recheck catalogue identifiers and Source entitlement before confirming a suggestion. Poll the durable job into the existing chat result; bounded match output includes the total and `has_more`. Position reads existing observations, never fetches a competitor page or invokes a model. |
| [command.py:37](../../tank/command.py#L37), [adapters:1160](../../tank/command.py#L1160), [planner:1642](../../tank/command.py#L1642) | Tiger-only tool catalogue and adapters for all four commands. Explicit commands are planned in code before the memory/model planner. All are unpaid; `tiger.position` is GET. Confirm actions reuse the existing confirmation dispatcher. Existing cards and result fields render the data; no Workspace/UI file changes. |
| [app.py:148](../../agents/tiger/app.py#L148) | Subsequent checks for a confirmed catalogue match use `tiger.price_structured` and disable the screenshot/model fallback. Existing supplier/ordinary watch behavior remains on its original path. |
| [schema.sql:2337](../../tank/schema.sql#L2337) | Additive/idempotent `agent_tiger.matches`, `match_runs`, and public host counters. Tenant tables use the same legacy-safe RLS activation sentinel and permissive/restrictive policies as `tank.personal_tokens`. Checked [Tank startup:753](../../tank/main.py#L753): schema runs through the existing admin-or-legacy connection and existing role validation. No startup, queue worker, policy lifecycle or cache edits. |
| [trigger_routes.py:20](../../tank/trigger_routes.py#L20) | Approved shared-helper change: optional keyword `agent='trigger'`, passed as `$5` in literal SQL. Existing callers keep their signature and attribution. Tiger uses `agent='tiger'`; receipts have the same zero-token/code/$0 ledger shape as `trigger.check`. |
| [test_tiger_competitors.py:1](../test_tiger_competitors.py#L1), [legacy corridor:59](test_prices.py#L59), [opt-in test:105](test_prices.py#L105), [wiring:491](../test_tiger.py#L491), [runner:1](run_t1_offline.py#L1) | Synthetic tests for receipt attribution, GTIN validation, evidence refusal, suggested/confirmed/rejected states, tenant isolation, position arithmetic, robots, human checks, search forms, host limits, anonymous browser requests, durable chat results and RLS. Update the handler contract for the added job. Run database tests on an existing free PostgreSQL image with `pg_trgm`. |

Position uses competition ranking: `1 + competitors priced below the store`. Difference is own price minus the cheapest matched competitor in the same currency. Other currencies, missing prices and unreadable pages remain in the source data but are excluded from arithmetic. No currency conversion is invented. Each competitor includes its URL, latest price, stock and observation time.

The 500-request allowance conservatively includes robots/sitemap requests, not only product pages. Discovery blocks external scripts/assets so those requests cannot escape the budget. Sites requiring those resources may remain unreadable; there is no paid/model fallback or challenge bypass.

## Exact validation commands and results

Working directory: `/workspace/codex-tiger-t1`.

```sh
.venv/bin/python tests/rig_tiger_prices/run_t1_offline.py
```

**245 passed, 6 failed, no skips; exit 1.** The six failures are the identical test IDs reproduced on clean current main, below. All 14 Rig/Tiger PostgreSQL cycle tests and the optional Tiger mail persistence test ran. The runner invokes every `tests/test_tiger*.py` and `tests/rig_tiger_prices` test, limits network access to loopback/Unix sockets, starts a disposable trust-authenticated PostgreSQL container, and removes that container afterward. It does not read a production DSN or a password. [Full raw output](evidence/tiger_t1_tests.txt).

```sh
.venv/bin/python -m pytest tests/test_tiger_competitors.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
```

**37 passed; exit 0.** Includes the requested default-Trigger and explicit-Tiger receipt tests. [Focused output](evidence/tiger_t1_focused_and_static.txt).

```sh
git diff --check
git diff origin/main --check
.venv/bin/ruff check --select F821,F822,F823 tank/access.py tank/command.py tank/trigger_routes.py agents/rig/rigbox/retailer_api.py agents/rig/rigbox/retailer_store.py agents/tiger/app.py agents/tiger/rig_watch.py agents/_brain/browser.py tests/test_tiger_competitors.py tests/rig_tiger_prices/run_t1_offline.py
```

**All exit 0.** [Static output and exact commands](evidence/tiger_t1_focused_and_static.txt).

Captured output files retain the test/error content; trailing whitespace was trimmed for repository checks.

## Clean-main comparison of the six failures

The separate checkout `/workspace/codex-tiger-t1-main-baseline` was fetched and detached at clean `origin/main` **`d6004c8d1f0110cc74fc7bbeaae4144277ca6758`**. `git status --porcelain` was empty. It contains none of this branch's changes.

Commands in that checkout:

```sh
git fetch origin main && git checkout --detach origin/main && git status --short
/workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_tiger_alert_email.py::test_email_copy_matches_actual_workspace_formatter 'tests/test_tiger_public_policy.py::test_real_browser_document_and_asset_refusals[200]' 'tests/test_tiger_public_policy.py::test_real_browser_document_and_asset_refusals[403]' 'tests/test_tiger_public_policy.py::test_real_browser_document_and_asset_refusals[429]' tests/test_tiger_works.py::test_workspace_actions_and_safe_unread_display tests/test_tiger_works.py::test_real_chromium_markup_stores_history_and_one_price_alert -q --tb=short
```

**All six also fail on main; exit 1.** They were left unchanged as instructed. [Complete baseline trace and error lines](evidence/tiger_t1_main_baseline.txt).

| Failing test | Main error line |
| --- | --- |
| `test_tiger_alert_email.py::test_email_copy_matches_actual_workspace_formatter` | `tests/test_tiger_alert_email.py:399`: `CalledProcessError: Command '['node', 'tests/tiger_alert_email/page_copy.cjs']' returned non-zero exit status 1.` |
| `test_tiger_public_policy.py::test_real_browser_document_and_asset_refusals[200]` | `tests/test_tiger_public_policy.py:282`: `TargetClosedError: BrowserContext.storage_state: Target page, context or browser has been closed` |
| `test_tiger_public_policy.py::test_real_browser_document_and_asset_refusals[403]` | Same test line and `BrowserContext.storage_state` error. |
| `test_tiger_public_policy.py::test_real_browser_document_and_asset_refusals[429]` | Same test line and `BrowserContext.storage_state` error. |
| `test_tiger_works.py::test_workspace_actions_and_safe_unread_display` | `tests/test_tiger_works.py:222`: `MODULE_NOT_FOUND`, `Cannot find module '/workspace/codex-tiger-t1-main-baseline/workspace/node_modules/typescript'` |
| `test_tiger_works.py::test_real_chromium_markup_stores_history_and_one_price_alert` | `tests/test_tiger_works.py:237`: `TargetClosedError: Page.evaluate: Target page, context or browser has been closed` |

## Checkout and environment commands

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-tiger-t1 && cd /workspace/codex-tiger-t1 && git fetch origin main && git checkout -B codex/tiger-competitors origin/main
git config user.name 'Codex' && git config user.email 'codex@users.noreply.github.com'
/home/ammosync/.local/bin/python3.12 -m venv .venv
.venv/bin/pip install -r tank/requirements.txt -r tank/requirements-dev.txt
docker image inspect postgres:16 --format '{{.Id}}'
```

All succeeded. The PostgreSQL image already existed (`sha256:1beaa3084eee2676f20a9cd9928f0bf2c5bf674f8e49f81017912183d377c61c`); no paid service was added. Earlier setup attempts found no `python` alias/no system `pytest` and an unset Git author; the configured Python 3.12 environment and the founder-supplied Git identity resolved those setup issues. These are test/build settings, not application credential changes.

Each finished file was committed and pushed on `codex/tiger-competitors`, with `git merge origin/main` before the push. Later evidence pushes also fetch main first. Main advanced during the build; `git fetch origin main` and `git merge origin/main` produced `fe1f605c`, without conflicts, and the full suite was rerun afterward. No push failed. Commit history and the branch diff are the source-change record.

## Deployment and founder-browser proof — missing

No new Coolify setting names or values are required. Existing deploy-on-merge selection includes the main/ZA stack and Rig/Tiger room stacks and their regional copies. The Tiger stack already builds its browser sidecar from `agents/base/Dockerfile.browser`, which copies `agents/_brain`; its browser image must be rebuilt with the agent. No runtime configuration file was changed.

Missing acceptance evidence is exactly:

1. Founder screenshots of Custom Nation's two or three chosen public HTTPS Source links saved in Tiger Plugins.
2. In the founder's own `/chats`, `tiger.match`, its Confirm card/$0 receipt, then returned confirmed matches showing source pages and barcodes. A brand+MPN suggestion must remain suggested until `tiger.match.confirm <match-id>` is confirmed; rejection uses `tiger.match.reject <match-id>` and its own Confirm card.
3. After ordinary watch checks, the founder's `tiger.position` result with own price, competitor prices/stock/source links/check times, rank and difference.
4. A second tenant's browser showing none of Custom Nation's matches/readings.

**No founder-browser screenshots exist for this build. None are replaced with synthetic screenshots, and live acceptance is not claimed.** The Tiger page view remains deferred to approved Figma page “9 · Tiger price position”; no page, button, UI copy, empty state or error wording was added.
