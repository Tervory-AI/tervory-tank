# G5: Tiger product, cost and market alerts

Tiger now records `new_product`, `below_cost` and `market_gap` in its existing
alert table and sends them through the existing #365 SMTP outbox and three-line
email layout. Per-watch API preferences suppress each type at detection and
again before queued mail is sent. No page, control, or Workspace copy changes.

Branch: `codex/tiger-g5-alerts`, started from main at `585a900`.
Implementation commits: `b880581`, `8fecf31`; initial proof checkpoint `56305a6`.
Claude opens the single draft PR. No GitHub API was used, and no merge or push
to main was performed.

## Behaviour

- `new_product`: a complete structured listing establishes a baseline; subsequent
  additions create alerts. Supports JSON-LD ItemList (including ListItem.item),
  Product arrays and products from the existing microdata extractor. Identity
  is a product URL, GTIN or SKU; names alone are never a match. An explicitly
  empty ItemList is a baseline. Malformed, incomplete and blocked reads retain
  it. Arbitrary unstructured links are not guessed to be products. Confirmed
  listings do not invoke OCR just because they have no single price.
- `below_cost`: existing tenant-owned `tank.access_feed_links` maps the watched
  URL to the client's SKU. Rig reads `agent_rig.supplier_costs.cost` joined on
  **tenant and SKU** through its private retailer listener. No link/product/cost
  row, or a currency mismatch, means no alert. Retail price never replaces cost.
- `market_gap`: uses those same explicit matches and Rig's existing
  `products.active` stock flag. Every enabled matched competitor watch must have
  a confirmed out-of-stock reading that is not overdue for its schedule. Muted
  competitors still count; the client's own page is excluded. Unknown, failed
  and overdue readings cannot establish a gap.
- `alert_new_product`, `alert_below_cost`, `alert_market_gap` default to `true`,
  like price/stock. They are available through watch POST/PATCH/read. Newly
  created automatic Rig own-page watches explicitly mute the new types too.
- Cost and market conditions alert only on transitions, not repeated checks.
  Market gaps produce one event per tenant/product. Muted checks advance state
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

Implementation line numbers refer to `8fecf31`.

| File:line | Change |
| --- | --- |
| `agents/tiger/g5_alerts.py:22,83,169,242,262` | Validated room search path, listing membership, tenant-scoped transitions, atomic SQL persistence and memory equivalent. |
| `agents/tiger/schema.sql:1` | Additive, idempotent preferences and alert-state table. No production migration was run. |
| `agents/tiger/watch.py:26,33,42,61,663,679,735,773,846,884,925,950,1139` | Store preferences, fixed parameterized PATCH, reuse alert/mail transaction, send-time switches and integration around existing reader/site limiter. |
| `agents/tiger/alert_email.py:97,118` | Reject multiline subject data; add the three approved email lines. |
| `agents/tiger/app.py:126,154,206,221,254` | Private product context for competitor checks; accept preferences. |
| `agents/tiger/rig_watch.py:102,142` | Reuse Tank client for context; mute newly created automatic own-page watches. |
| `agents/tiger/Dockerfile:11` | Ship detector and schema with Tiger. |
| `agents/rig/rigbox/retailer_store.py:22,124` | Read-only tenant/SKU cost and own-stock lookup, excluding deleted products. |
| `agents/rig/rigbox/retailer_api.py:15,48` | Private watch-context operation, existing authentication and tenant validation. |
| `tank/access.py:1005` | Tiger-only URL/product match and private Rig relay; both queries filter tenant. |
| `tank/main.py:3697,3704` | Preferences and PATCH in existing authenticated Tiger watch relay. |
| `tests/test_tiger_works.py:194` | Migration stand-in now covers transaction/search path and all preference defaults. |
| `tests/tiger_g5/conftest.py:1` | Disposable loopback SQL fixtures; memory/SQL parametrization. |
| `tests/tiger_g5/fixtures/category.html:1` | Offline-only listing fixture. |
| `tests/tiger_g5/test_alerts.py:68,102,119,134,149,174,197` | Two tenants, exact emails, no repeat/disabled mail, incomplete readings, cost/stock rules, concurrency, rollback and repeated migration. |
| `tests/tiger_g5/test_integration.py:51,77,111` | Real Tank/Rig routes, actual agent jobs to local SMTP, tenant-safe API switches. |
| `tests/tiger_g5/PR.md:1`, `tests/tiger_g5/proof/pytest.txt:1`, `tests/tiger_g5/proof/semgrep.txt:1` | Description and captured proof. |

## Exact verification commands and results

Run in `/workspace/tiger-g5-alerts`. PostgreSQL and SMTP were loopback fixtures;
no deployment values were inspected or created.

```bash
source /workspace/tervory-env/activate.sh
TIGER_MAIL_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/pooltest python -m pytest -q tests/tiger_g5 tests/test_tiger.py tests/test_tiger_alert_email.py tests/test_tg2_tiger_watchlist.py tests/test_tiger_works.py tests/test_tiger_missing_name.py tests/test_tiger_price_structured.py tests/test_tiger_public_policy.py tests/tiger_playbooks tests/rig_tiger_prices tests/test_tank_one_door.py --tb=short > /tmp/tiger-g5-all-final.log 2>&1
```

Exit 0; [captured output](proof/pytest.txt):

```text
270 passed, 6 warnings in 114.92s (0:01:54)
```

Includes all 31 G5 cases, existing Tiger/Rig regressions, browser/scope/site-limit
checks and the one-door guard. Warnings are the existing Pydantic field-shadowing
and FastAPI startup/shutdown deprecations.

```bash
SEMGREP_SETTINGS_FILE=/tmp/tiger-g5-semgrep-settings.yml SEMGREP_LOG_FILE=/tmp/tiger-g5-semgrep-runtime.log /tmp/tiger-playbooks-semgrep-env/bin/semgrep scan --config auto --metrics auto --disable-version-check --disable-nosem --no-git-ignore --baseline-commit 585a900 --error --json --output /tmp/tiger-g5-semgrep-final.json agents/tiger agents/rig/rigbox/retailer_api.py agents/rig/rigbox/retailer_store.py tank/access.py tank/main.py > /tmp/tiger-g5-semgrep-final.log 2>&1
```

Exit 0; [captured output](proof/semgrep.txt):

```text
Ran 332 rules on 29 files: 0 findings.
```

JSON report: zero errors. Scan covers the supplied source targets against the
starting main commit, with suppressions disabled. It is not a remote CI result
or a claim about unrelated repository findings. Scanner reports one size-excluded
file in the target tree.

`git diff --check` — exit 0, no output.

Earlier checks caught missing local node_modules, an outdated migration double,
and a Semgrep flag on concatenation in a bound argument. Test dependencies were
linked locally, the double now covers the transaction, and the lock prefix uses
fixed SQL with a `$1` value. The final run includes these corrections; no
suppression was added.

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

The environment briefly disconnected during final checks. Local changes were
intact after reconnection and tests were rerun.

## Founder browser/inbox proof — pending

**The live done condition has not been demonstrated. No founder screenshot is
claimed.** This branch has not been merged or deployed. No live page, catalogue,
database row, SMTP setting or recipient mapping was changed.

After founder merge/deployment, use an existing watch on a controlled listing
page with confirmed product identities. Establish a baseline, add a product,
and run another check. The founder must receive `New product listed: {product}`
in the configured inbox; a repeated check must not send another copy. Capture
the controlled page and received email as the founder's proof.

The existing path uses `TIGER_SMTP_HOST`, `TIGER_SMTP_PORT`, `TIGER_SMTP_USER`,
`TIGER_SMTP_PASSWORD`, `TIGER_SMTP_FROM`, and `TIGER_SMTP_ALERT_ADDRESSES`.
No new setting or key is introduced. Values remain founder-managed; live
configuration and inbox receipt were not inspected. No production migration
or live send is claimed by the offline tests.
