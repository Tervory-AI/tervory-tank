# Tiger T1: catalogue competitor matching and price position

Tiger discovers public product pages on the tenant's saved Tiger Source sites, matches catalogue identifiers, creates ordinary watches for confirmed matches, and returns price position in existing `/chats` cards. Exact validated GTIN confirms automatically; brand plus MPN without a barcode stays suggested until a bound Confirm card is accepted. Titles and competitor SKUs never establish identity. Every command records the existing code/$0 receipt shape.

PR #599, branch `codex/tiger-competitors`. Includes Claude's schema-order fix `cea1a0cf` and main `cf95a07e`. The founder merges. No production SQL, runtime setting changes, model calls, paid search, new UI or deployment was performed.

**Founder-browser acceptance and screenshots remain missing. Tests are not live acceptance.**

## Review fixes, with file and line

| Review | Final behavior and source |
| --- | --- |
| 1 | [rig_watch.py:456](../../agents/tiger/rig_watch.py#L456) advances one network operation or one catalogue position per slice. The JSON cursor persists site, robots, sitemap/candidate queues, visited URLs, confirmed SKUs, forms and search index. [app.py:200](../../agents/tiger/app.py#L200) atomically saves the slice result and inserts a deterministic continuation in the existing jobs table. Continuations wait one second so queued checks can run first; timeout is 45 seconds, not 24 hours. A real chassis `claim_next`/`run_claimed` test executes a check between discovery slices. |
| 2 | [browser.py:436](../../agents/_brain/browser.py#L436) starts an empty context; [cleanup:591](../../agents/_brain/browser.py#L591) passes `save=False` for catalogue visits. Existing saved cookie bytes survive unchanged. |
| 3 | [access.py:1347](../../tank/access.py#L1347) records discovery captcha items with `ON CONFLICT DO NOTHING`. Existing waiting/handling items retain handles, handler, timestamps and status. |
| 4 | [browser.py:383](../../agents/_brain/browser.py#L383) returns `unsupported`, not a challenge, for private policies/PDFs. [syntactic filtering:411](../../agents/tiger/rig_watch.py#L411) skips PDF candidates before reservation. Only the existing human-check detector or HTTP 401/403/429 marks the host blocked. |
| 5 | [rig_watch.py:402](../../agents/tiger/rig_watch.py#L402) adds discovery-local path-plus-query robots matching with `*`, `$`, longest match and Allow ties. Existing watch robots callers are unchanged. Both `/?s=` and `/*?s=` refusals are tested. Public rules are compiled once per body/user-agent, with a bounded cache; URL filtering does not reparse robots.txt for every sitemap location. |
| 6 | [rig_watch.py:536](../../agents/tiger/rig_watch.py#L536) skips unavailable, redirected or soft-404 HTML sitemaps and continues to search. Only challenge-looking HTML receives a separately reserved browser probe. |
| 7 | [app.py:91](../../agents/tiger/app.py#L91) bounds sitemap reads at 4 MB and robots at 100 KB, exposing truncation. [iterparse:430](../../agents/tiger/rig_watch.py#L430) bounds locations at 10,000 and records cuts/parse truncation. Traversal queues are also bounded. |
| 8 | [access.py:1521](../../tank/access.py#L1521) returns only catalogue SKUs with confirmed matches, at most 100 SKUs, retaining every competitor for each returned SKU, with `total` and `has_more`. [card bound:1546](../../tank/access.py#L1546) measures the entire serialized result, including repeated text, against 240 KB. Tests cover 1,000 unmatched SKUs and escaped text. |
| 9 | [app.py:137](../../agents/tiger/app.py#L137) keeps ordinary watches on the original `price_extract` and OCR paths. The per-check matches/to_regclass query and reader switch are removed. Reused hand-made watches retain their existing settings; new watches use the existing six-hour/all-alert defaults. |
| 10 | [access.py:1336](../../tank/access.py#L1336) validates the publishing job's tenant/root binding and stores a sighting with the actual slice job ID, stable root job ID and evidence snapshot. [card loading:1555](../../tank/access.py#L1555) selects that run's sightings, never a timestamp window. |
| 11 | [access.py:1189](../../tank/access.py#L1189) rejects normalized all-zero GTIN placeholders as well as bad check digits. |
| 12 | [rig_watch.py:411](../../agents/tiger/rig_watch.py#L411) filters links by parsed HTTPS host/port only. Public-DNS validation happens at transport admission, off the event loop. |
| 13 | [test_tiger_competitors.py](../test_tiger_competitors.py) removes unused imports/fixture redefinition warnings. [test_command.py:49](../test_command.py#L49), [squad grant:956](../test_command.py#L956), and [test_personal_tokens.py:49](../test_personal_tokens.py#L49) expect all six Tiger tools. [runner:30](run_t1_offline.py#L30) includes both entire suites as well as every Tiger/Rig-price test. Full CI Ruff command is recorded below. |
| 14 | [schema.sql:2308](../../tank/schema.sql#L2308) adds run progress and tenant-scoped sightings; [grants:2345](../../tank/schema.sql#L2345) grants existing roles the required privileges. Fresh-role ownership and existing-role migration orders are exercised using a disposable NOLOGIN role. [access.py:1555](../../tank/access.py#L1555) preserves a saved card if enrichment fails, so one error cannot break a thread. |
| 15 | [browser.py:442](../../agents/_brain/browser.py#L442) uses the existing browser service's anonymous request context with `max_redirects=0`; it never starts page navigation, scripts or assets. This explicitly refuses redirects rather than relying on Playwright page routing. A same-origin WooCommerce search redirect becomes a new product candidate and receives its own robots check and reservation. Sitemap redirects are skipped. |
| 16 | [rig_watch.py:564](../../agents/tiger/rig_watch.py#L564) publishes only product candidates. Search/home HTML is used solely to find forms/links. [access.py:1361](../../tank/access.py#L1361) also refuses known search URLs as product evidence. Tests put matching Product markup on search/home pages and prove no binding/watch is made. |

Rig's [store projection:33](../../agents/rig/rigbox/retailer_store.py#L33) and [API:50](../../agents/rig/rigbox/retailer_api.py#L50) add GTIN/brand/MPN/price/currency through the existing opt-in catalogue operation; default callers retain their eligibility rules. [command.py:37](../../tank/command.py#L37) exposes the six Tiger-only tools and unpaid adapters through existing cards. [trigger_routes.py:20](../../tank/trigger_routes.py#L20) has the approved optional `agent='trigger'` parameter, passed as `$5` in literal SQL; Tiger explicitly passes `agent='tiger'`. Both receipt attributions are tested.

Position uses competition rank `1 + cheaper comparable competitors` and difference `own price - cheapest comparable competitor`, using latest tenant observations. Missing prices and different currencies are excluded from arithmetic; no conversion is invented. Confirmed matches bind tenant/URL/SKU through the existing feed-link/watch path. No existing URL binding is overwritten.

The shared host gate reserves before transport, including failures, spaces attempts by three seconds and limits each public origin to 500 attempts per UTC day across tenants/workers. Robots, sitemap and product/search requests all count. Isolated catalogue reads use returned HTML structured data and do not run client scripts or bypass challenges; some sites may yield no match.

## Deployment order and privileges

[Tank startup:753](../../tank/main.py#L753) applies idempotent schema through the existing admin-or-legacy connection. Tenant tables join the existing personal-token RLS rollout only when the command-thread sentinel is enabled; they use both permissive and restrictive tenant policies.

[docker-compose.yml:363](../../docker-compose.yml#L363) explicitly says Tank does not wait for the one-shot `agent-roles` service. [provision_agent_roles.py:29](../../agents/_chassis/provision_agent_roles.py#L29) calls `apply_roles`; [roles.py:63](../../agents/_chassis/chassis/roles.py#L63) transfers ownership of every existing table/sequence in the agent schema, and its caller grants schema USAGE/CREATE. Therefore migration-before-role is covered by the existing ownership pass; role-before-migration is covered by the new conditional schema/table grants. Tests assert SELECT, INSERT and UPDATE privileges on all four T1 tables and execute writes as the NOLOGIN role. No password is created or read by these tests.

[deploy_changed.py:254](../../.github/scripts/deploy_changed.py#L254) deploys/waits for main and ZA before room stacks. Changed Tank, Rig, Tiger and shared browser sources require their normal stack/image rebuilds after merge. No runtime configuration file or setting was changed.

## Validation

Working directory `/workspace/codex-tiger-t1`; Python 3.12 virtual environment. The runner uses a disposable existing `postgres:16` image with trust authentication on loopback, blocks external test sockets, and removes its container afterward. No production DSN is used.

**Full required suites: 365 passed, 6 failed, no skips; exit 1.** The six failures have the same errors on clean main and are listed below. This run includes all Tiger/Rig-price tests plus the entire command (83 cases) and personal-token (8 cases) suites. Tested implementation `5b6625f9`; the subsequent policy-compilation change `406fe08e` was validated with the entire focused T1 suite. [Full output and targeted timeout rerun](evidence/tiger_t1_tests.txt).

**Final focused T1 suite: 66 passed; shared browser fixture suite: 9 passed; both exit 0.** These cover the final implementation, including compiled robots policy, preserved cookies/handoffs, job/run isolation, deployment-order grants, check execution between slices, large sitemap/card bounds and the twenty-first competitor. **Both Ruff commands and both whitespace checks pass.** [Commands and raw focused/static/browser/benchmark output](evidence/tiger_t1_focused_and_static.txt).

Commands:

```sh
.venv/bin/python tests/rig_tiger_prices/run_t1_offline.py
.venv/bin/python -m pytest tests/test_tiger_competitors.py -q --tb=short --timeout=300 --disable-socket --allow-unix-socket
.venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
.venv/bin/ruff check agents/tiger/app.py agents/tiger/rig_watch.py agents/_brain/browser.py --select E9,F
git diff --check
git diff origin/main --check
.venv/bin/python -m pytest tests/test_agent1_browser.py -q --tb=short --timeout=300 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
.venv/bin/python tests/rig_tiger_prices/run_t1_offline.py tests/test_command.py::test_pinned_turn_receipt_uses_actual_model_and_pending_auto
```

An initial full run was interrupted to inspect three PostgreSQL fixture setup timeouts and a stale wiring assertion for 86400 seconds. That assertion was corrected to 45 seconds before the final validation. A second run was stopped when main advanced, so the merged branch could be validated afresh. Final outputs below supersede those incomplete runs. A completed 90-second run had 363 passes and seven failures: the six main failures plus a fixture-inclusive timeout in `test_pinned_turn_receipt_uses_actual_model_and_pending_auto`. That test passed in an isolated rerun (1 passed, 12.29 seconds). The runner now uses the normal [CI 300-second test limit](../../.github/scripts/offline_suite.py#L103); the discovery job limit remains 45 seconds. The final full run includes the position case whose cheapest competitor appears beyond the twentieth source. A final compiled-policy optimization is covered by the complete focused T1 suite and the offline benchmark below.

Offline policy benchmark (no requests): 10,000 URLs against 1,000 rules for both user agents completed in **5.364 seconds**. Before compilation was shared, only 100 URLs for one user agent took 2.631 seconds. The complete command and output are in the focused/static evidence.

## Clean-main comparison: six pre-existing failures

Separate clean checkout: `/workspace/codex-tiger-t1-main-baseline`, detached at fetched `origin/main` `cf95a07e`; `git status --short` empty.

```sh
git fetch origin main
git checkout --detach origin/main
git status --short
/workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_tiger_alert_email.py::test_email_copy_matches_actual_workspace_formatter tests/test_tiger_public_policy.py::test_real_browser_document_and_asset_refusals tests/test_tiger_works.py::test_workspace_actions_and_safe_unread_display tests/test_tiger_works.py::test_real_chromium_markup_stores_history_and_one_price_alert -q --tb=short --timeout=90 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
```

**6 failed; exit 1**, also on main. Left unchanged as instructed. [Full main trace](evidence/tiger_t1_main_baseline.txt).

| Test | Error line on clean main |
| --- | --- |
| `test_tiger_alert_email.py::test_email_copy_matches_actual_workspace_formatter` | `tests/test_tiger_alert_email.py:399`: `CalledProcessError: Command '['node', 'tests/tiger_alert_email/page_copy.cjs']' returned non-zero exit status 1.` |
| `test_tiger_public_policy.py::test_real_browser_document_and_asset_refusals[200]` | `tests/test_tiger_public_policy.py:282`: `TargetClosedError: BrowserContext.storage_state: Target page, context or browser has been closed` |
| `test_tiger_public_policy.py::test_real_browser_document_and_asset_refusals[403]` | `tests/test_tiger_public_policy.py:282`: same `BrowserContext.storage_state` error. |
| `test_tiger_public_policy.py::test_real_browser_document_and_asset_refusals[429]` | `tests/test_tiger_public_policy.py:282`: same `BrowserContext.storage_state` error. |
| `test_tiger_works.py::test_workspace_actions_and_safe_unread_display` | `tests/test_tiger_works.py:222`: `MODULE_NOT_FOUND`, `Cannot find module '/workspace/codex-tiger-t1-main-baseline/workspace/node_modules/typescript'` |
| `test_tiger_works.py::test_real_chromium_markup_stores_history_and_one_price_alert` | `tests/test_tiger_works.py:237`: `TargetClosedError: Page.evaluate: Target page, context or browser has been closed` |

## Founder-browser proof still required

No founder screenshots exist. Missing: Custom Nation's chosen two or three Source links saved in Tiger Plugins; `tiger.match` Confirm/$0 receipt and returned page/barcode evidence in `/chats`; `tiger.position` after ordinary checks with prices, stock, sources, check times, rank and difference; another tenant seeing none of those rows. No synthetic screenshot substitutes for that proof. The Tiger page remains deferred to approved Figma page “9 · Tiger price position”.
