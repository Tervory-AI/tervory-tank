# G5: Tiger alerts and the five review fixes

Tiger now records `new_product`, `below_cost` and `market_gap` in its existing
alert table and sends them through the existing #365 SMTP outbox and three-line
email layout. Per-watch API preferences suppress each type at detection and
again before queued mail is sent. Workspace filters these three kinds out until
their Figma design is approved; existing price/stock rows remain. No new page
wording, controls, colours or layout are introduced.

Branch: `codex/tiger-g5-alerts`, started from main at `585a900`.
Main `37ec348` was merged in `b7a63d1`, preserving both Tiger's playbook callback
and G5's tenant-scoped product callback. Final code/tests verified at `8111bfa`.
Claude opens the single draft PR. No GitHub API was used, and no merge or push
to main was performed.

## Behaviour

- `new_product`: a complete structured listing establishes a baseline; subsequent
  additions create alerts. Supports JSON-LD ItemList (including ListItem.item),
  Product arrays and products from the existing microdata extractor. Identity
  is its individual product URL, then GTIN/SKU, then name plus a confirmed price;
  the category URL is never used as an identity. Explicit ItemList supports
  empty/single lists; otherwise multiple products are needed to identify a
  category. Standalone product/price fallbacks do not establish catalogue
  baselines. Malformed, incomplete and blocked reads retain the baseline.
  Arbitrary unstructured links are not guessed to be products. Confirmed
  listings do not invoke OCR just because they have no single price.
- `below_cost`: existing tenant-owned `tank.access_feed_links` maps the watched
  URL to the client's SKU. Rig reads `agent_rig.supplier_costs.cost` joined on
  **tenant and SKU** through its private retailer listener. No link/product/cost
  row, or a currency mismatch, means no alert. Stock data is not required for a
  confirmed price comparison. Retail price never replaces cost.
- `market_gap`: uses those same explicit matches and Rig's existing
  `products.active` stock flag. Every enabled matched competitor watch must have
  a confirmed out-of-stock reading that is not overdue for its schedule. Muted
  competitors still count; the client's own page is excluded. Unknown, failed
  and overdue readings cannot establish a gap. Confirmed stock is retained even
  when a page has no price; stock-only checks do not invoke OCR for that reason.
- `alert_new_product`, `alert_below_cost`, `alert_market_gap` default to `true`,
  like price/stock. They are available through watch POST/PATCH/read. Newly
  created automatic Rig own-page watches explicitly mute the new types too.
- Cost and market conditions alert only on transitions, not repeated checks.
  Market gaps produce one event per tenant/product. Reading/listing baselines
  use watch ID **and URL**: changing the URL starts a fresh baseline and cannot
  reuse the previous page's stock. Muted checks advance state
  without replaying old events when re-enabled. Tenant-scoped state and ordinary
  alert/mail inserts commit atomically, serialized per tenant. Existing SMTP
  retries and uncertain-send handling remain in use.

Only these founder-approved email lines were added. Subject = line; body =
product name / line / watched URL, as in #365:

```text
New product listed: {product}
Competitor price {price} is below your cost {cost}
All watched competitors are out of stock. You are in stock.
```

## Files and lines

Implementation line numbers refer to `8111bfa`.

| File:line | Change |
| --- | --- |
| `agents/tiger/g5_alerts.py:22,83,179,187,194,198,257,277` | Validated room search path, individual listing identities, watch/URL baselines, independent price/stock checks, atomic SQL persistence and memory equivalent. |
| `agents/tiger/schema.sql:1` | Additive, idempotent preferences and alert-state table. No production migration was run. |
| `agents/tiger/watch.py:26,33,42,61,396,663,679,735,773,846,884,925,950,1139` | Preferences, parameterized PATCH, existing alert/mail transaction and site limiter, independent stock reading and no unnecessary stock-only OCR; forward the merged playbook callback. |
| `agents/tiger/alert_email.py:97,118` | Reject multiline subject data; add the three approved email lines. |
| `agents/tiger/app.py:129,157,210,225,258` | Private product context for competitor checks; accept preferences and preserve main's playbook callback. |
| `agents/tiger/rig_watch.py:101,142` | Reuse Tank client for context; mute newly created automatic own-page watches. |
| `agents/tiger/Dockerfile:11` | Ship detector and schema with Tiger. |
| `agents/rig/rigbox/retailer_store.py:22,124` | Read-only tenant/SKU cost and own-stock lookup, excluding deleted products. |
| `agents/rig/rigbox/retailer_api.py:15,48` | Private watch-context operation, existing authentication and tenant validation. |
| `tank/access.py:1005` | Tiger-only URL/product match and private Rig relay; both queries filter tenant. |
| `tank/main.py:3705,3714` | Preferences and PATCH in existing authenticated Tiger watch relay. |
| `workspace/app/tiger/model.ts:268` | Filter only the three G5 kinds from the existing alert list pending Figma; no new words. |
| `tests/test_tiger_works.py:194` | Migration stand-in now covers transaction/search path and all preference defaults. |
| `tests/tiger_g5/conftest.py:1` | Disposable loopback SQL fixtures; memory/SQL parametrization. |
| `tests/tiger_g5/fixtures/category.html:1` | Offline-only listing fixture. |
| `tests/tiger_g5/test_alerts.py:68,102,119,134,149,174,197` | Two tenants, exact emails, no repeat/disabled mail, incomplete readings, cost/stock rules, concurrency, rollback and repeated migration. |
| `tests/tiger_g5/test_integration.py:24,52,78,120` | Real Tank/Rig routes, actual agent jobs to local SMTP, tenant-safe API switches, merged playbook execution. |
| `tests/tiger_g5/test_review.py:44,60,71,95,111` | All five findings, two tenants, memory/SQL stores, URL/SKU/GTIN/name+price identities, local SMTP and Workspace formatter. |
| `tests/rig_tiger_prices/test_cycle.py:23,89,102` | Test client implements main's approved-playbook interface using the real code-only skill. |
| `tests/tiger_price_read/test_shadow_reused.py:16` | Correct pre-existing stale assertions to the founder's 200-sample/99% defaults; no graduation implementation or policy change. |
| `tests/tiger_g5/PR.md:1`, `tests/tiger_g5/proof/review.txt:1` | Current description, exact commands and captured review proof. |
| `tests/tiger_g5/proof/pytest.txt:1`, `tests/tiger_g5/proof/semgrep.txt:1` | Retained historical proof from the original implementation, before this review. |

## Five review tests

All are in `tests/tiger_g5/test_review.py`. They expand to 15 cases; memory/SQL
cases exercise two tenants. The initial reproduction was **13 failed, 2 passed**
on merged code `b7a63d1` with tests subsequently committed as `4368131`.
The completed five groups pass; exact before/after output is in
[review.txt](proof/review.txt).

| Finding | Test |
| --- | --- |
| Third microdata product sends exactly one email; each identity fallback works | `test_microdata_third_product_sends_one_new_product_email` |
| $10 versus $15 alerts without stock; another tenant's $5 cost does not | `test_below_cost_ten_against_fifteen_needs_no_stock` |
| All competitors out without prices, own store in stock; no repeat or OCR | `test_market_gap_all_competitors_out_without_prices` |
| Changed URL starts fresh; old stock cannot stand in for the new page | `test_watch_url_change_starts_new_baseline_and_peer_reading` |
| G5 rows omitted; existing price and stock rows retained | `test_workspace_omits_g5_rows_until_figma_and_keeps_existing_alerts` |

## Exact verification commands and results

Run in `/workspace/tiger-g5-alerts`. PostgreSQL and SMTP were loopback fixtures;
no deployment values were inspected or created.

```bash
source /workspace/tervory-env/activate.sh
TIGER_MAIL_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/pooltest python -m pytest -q tests/test_tiger*.py tests/test_tg2_tiger_watchlist.py tests/tiger_g5 tests/tiger_playbooks tests/tiger_alert_page tests/tiger_before_deploy tests/tiger_price_read tests/rig_tiger_prices tests/test_tank_one_door.py --tb=short -rs > /tmp/tiger-g5-review-suite-final.txt 2>&1
```

Exit 0; [captured output](proof/review.txt):

```text
349 passed, 1 skipped, 12 warnings in 133.28s (0:02:13)
```

Includes the five new regression groups, existing Tiger/Rig regressions,
browser/scope/site-limit checks and the one-door guard. The skip is
`test_filled_gold_pages_match_exactly`: its 100-page gold set still needs human
labelling. No missing gold evidence was invented. Warnings are existing Pydantic
field-shadowing and FastAPI startup/shutdown deprecations.

`node --test tests/tiger_works/workspace.test.cjs` — exit 0, 19 passed.

In `workspace/`:

```bash
source /workspace/tervory-env/activate.sh && npx tsc --noEmit > /tmp/tiger-g5-review-tsc.txt 2>&1
```

Exit 0, no output. The Workspace filter was unchanged after this check.

```bash
SEMGREP_SETTINGS_FILE=/tmp/tiger-g5-semgrep-settings.yml SEMGREP_LOG_FILE=/tmp/tiger-g5-semgrep-runtime.log /tmp/tiger-playbooks-semgrep-env/bin/semgrep scan --config auto --metrics auto --disable-version-check --disable-nosem --no-git-ignore --baseline-commit 37ec348 --error --json --output /tmp/tiger-g5-review-semgrep-final.json agents/tiger agents/rig/rigbox/retailer_api.py agents/rig/rigbox/retailer_store.py tank/access.py tank/main.py workspace/app/tiger/model.ts > /tmp/tiger-g5-review-semgrep-final.txt 2>&1
```

Exit 0; [captured output](proof/review.txt):

```text
Ran 494 rules on 32 files: 0 findings.
```

JSON report: zero errors. Scan covers the supplied source targets against the
merged main commit, with suppressions disabled. It is not a remote CI result
or a claim about unrelated repository findings. Scanner reports one size-excluded
file in the target tree.

`git diff --check origin/main` — exit 0, no output.

The expanded suite exposed two false catalogue alerts on changed standalone
product pages; requiring explicit ItemList or multiple products resolved them.
It also exposed the stale 30/97% graduation-default assertions. A detached
checkout of untouched main `37ec348` reproduced that failure while passing the
two reader checks. The assertions now match the founder's existing decision.
Both diagnosis and corrected runs are captured in the proof; no production
code outside this lane was changed to make the tests pass.

Git checkpoints (all commits and pushes succeeded):

```bash
git fetch origin main
git worktree add -b codex/tiger-g5-alerts /workspace/tiger-g5-alerts origin/main
git commit -m 'docs: record Tiger G5 scope and proof checkpoint'
git push -u origin codex/tiger-g5-alerts
git commit -m 'feat(tiger): detect product cost and market alerts with durable deduplication'
git push origin codex/tiger-g5-alerts
git commit -m 'test(tiger): prove G5 through Tank Rig and local SMTP'
git push origin HEAD:refs/heads/codex/tiger-g5-alerts
```

Review continuation began with:

```bash
git fetch origin && git checkout codex/tiger-g5-alerts && git merge origin/main
ls agents/tiger/g5_alerts.py agents/tiger/watch.py agents/tiger/alert_email.py agents/tiger/schema.sql agents/rig/schema.sql workspace/app/tiger/model.ts
```

Fetch succeeded, all named files exist, and the single conflict in
`agents/tiger/app.py` was resolved by retaining both callbacks and forwarding
the playbook argument through `run_check`. The merge was committed as `b7a63d1`.
Every completed review file was committed and pushed using
`git push origin HEAD:refs/heads/codex/tiger-g5-alerts` (all pushes succeeded):
`4368131`, `43fb7a6`, `09587d0`, `4db0954`, `9468a58`, `5de6c7f`, `9c0f818`,
`0d9fdaa`, `8111bfa`, `6e64fe0`. No push to main or GitHub API call was made.

## Founder browser/inbox proof — pending

**The live done condition has not been demonstrated. No founder screenshot is
claimed.** This branch has not been merged or deployed. No live page, catalogue,
database row, SMTP setting or recipient mapping was changed.

After founder merge/deployment, use an existing watch on a controlled listing
page with confirmed product identities. Establish a baseline, add a product,
and run another check. The founder must receive `New product listed: {product}`
in the configured inbox; a repeated check must not send another copy. The
Workspace Tiger alert list must show none of the three G5 kinds and no wrong
“Not checked” rows for them. Capture the controlled page, received email and
Workspace list as the founder's proof. These live screenshots are still missing.

The existing path uses `TIGER_SMTP_HOST`, `TIGER_SMTP_PORT`, `TIGER_SMTP_USER`,
`TIGER_SMTP_PASSWORD`, `TIGER_SMTP_FROM`, and `TIGER_SMTP_ALERT_ADDRESSES`.
No new setting or key is introduced. Values remain founder-managed; live
configuration and inbox receipt were not inspected. No production migration
or live send is claimed by the offline tests.
