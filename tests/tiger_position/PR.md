# Tiger TG2: approved price-position views

Branch `codex/tiger-w4`, started from main `c4e1395ec00831561e26227c602a22dfea7ad915`.
Design register read from `codex/tiger-figma` at
`115cae58d4ac219a40989f69902c182d94ecf471`, Approved 3 Nov 15:20 PT.
No PR creation, main merge, deployment or live tenant changes by this task.

## Gate 1: Tank review API

`GET /v1/access/tiger/matches` returns only the authenticated tenant's suggested
and rejected matches with their evidence, newest first, bounded to 100. It uses
the existing Tiger entitlement check and writes a $0 Tiger receipt.

Undo uses the same durable confirmation binding as reject. Only that tenant's
rejected row can move to suggested; confirmed remains final. Reject/undo use a
conditional UPDATE so a concurrent decision cannot overwrite another state.
Both new tools are registered; only Undo enters confirmed dispatch. Explicit
commands remain code-only. Existing personal-token tool expectations are updated.

Validation: the competitors, personal-token and Command suites passed 135 tests
with 48 existing Command database cases initially skipped. All 86 Command tests
then passed against an isolated local pgserver, including those database cases.
The explicit planner regression and Ruff E9/F also pass.

## Unframed states

No additional visible copy will be invented for loading, failed reads, failed
decisions or unavailable site-check metadata. These states need approved frames.
The rest of the approved views continue independently. Read failure must not be
presented as an empty account or a successful mutation.

## Gate 2: Workspace views

The Watch list now offers Price position, Matches to review and Competitor sites.
Open `/tiger?tab=watch&view=position` (or `matches` / `sites`). The existing
Overview, Alerts and History remain available. The new views reuse the panel,
side menu, table, PageLink, AttemptTime and Pill; the approved light shell and
mobile cards apply to these views. Warning text and borders use `--warn`.

Reads stay server-side in the Tank library. Catalogue names and identifier
evidence populate review rows. Confirm, Reject and Undo create and confirm a
durable code-only Tank card, whose dispatch calls the existing decision route.
The browser updates only from its successful response. A failed or unknown
decision retains its row and disables repeat submission; its wording needs a frame.

Position uses confirmed matches, saved sites, matching currencies, known watch
intervals and current readings. Paused, missing, future-dated and overdue readings
cannot claim a rank; overdue values remain visible with the framed warning.
Equal prices share a rank, your store participates, and a zero denominator never
produces an invented percentage. This implements the frame's exact "Proposed rule"
copy. The existing /chats position response remains compatible.

Competitor sites comes from the same tenant's Tiger vault links used by Plugins.
Its link opens the existing panel directly on Source links. Counts use immutable
match sightings from the latest recorded discovery run; page counts and outcomes
come from that run's existing summaries. A site's timestamp is the first completed
slice that records it, so later slices for other sites cannot refresh its age.
Unsaved sites and other tenants' runs are excluded. Unknown counts remain absent,
rather than becoming zero. Catalogue outages preserve stored review evidence.

No frame example is imported by production. All examples live in this test folder.
All ten PNG exports are retained in `frames/`; screenshot fixtures and the approved
FIXED-copy manifest are separate from the Workspace.

Validation at the Workspace gate:

- All ten Playwright screenshots passed the approved FIXED-copy checks and a
  pixel comparison with fewer than 5% changed pixels (channel delta above 32).
  The 89px Figma approval/illustrative-data bar is excluded from the app region.
  Browser/Figma antialiasing is allowed; this is not a claim of identical pixels.
- Mobile card heights and every frame's footer position match Figma geometry
  (footer tolerance 1px). Visible static asset files load at their exact sizes.
- Playwright exercises Reject → Undo → Confirm at both widths, unavailable reads,
  failed decisions without a false success, and opening Plugins on Source links.
- Workspace typecheck and production build passed using CI's dummy Clerk values.
  No Clerk session, live tenant data or model/provider was used for verification.
- All 66 existing Workspace TypeScript tests and 19 existing Tiger Node tests passed.
  New model, loader, action and confirmation-transport tests pass as well.
- The real Tank card/decision flow, catalogue outage and tenant-scoped site counts
  passed against isolated Postgres. A focused timestamp regression also passed.
- Final regression results and the disposable-environment rerun are recorded below.

Evidence is in `evidence/`, with actual screenshots in `evidence/screenshots/`.
The browser fixture uses the actual React components and production styles with
server boundaries mocked; the separate Tank test uses real durable cards/routes.

## Gate 3: final regression evidence

All 502 collected Tiger cases are accounted for: 501 passed across the broad run
and the focused rerun; one existing gold-set case remains skipped because its
human-checked expected data is absent. No test was removed or loosened.

The broad run covered every `test_tiger*` / `test_tg2*` module and every
`tiger_*` test directory, including tenant-bus history, real Chromium reading,
brain profiles, alerts and watch commands. It passed 470 cases. Its remaining
31 cases initially failed because the embedded PostgreSQL lacked `pg_trgm`, or
parallel workers shared cluster-wide role names. Those exact 31 cases then passed
serially on disposable PostgreSQL 16.15 with its extensions. Both logs are retained.
The PostgreSQL/Redis processes were isolated to this task; no deployment database,
existing volume or live tenant was used.

Additional completed checks:

- 34 existing Workspace Python checks passed.
- All 66 Workspace TypeScript, 19 legacy Tiger Node and 10 new TG2 tests passed.
- All 29 one-door and secret guards passed. The new transport test's environment
  restoration was expanded to avoid a secret-scanner false positive; its key and
  host remain explicit placeholders, with no allowlist change.
- The existing Chats contract, header and stall scripts, Next-fetch guard and CLI
  sign-in script passed. Production build, TypeScript and all ten visual checks
  passed as recorded above.
- The exact CI Ruff E9/F command printed `All checks passed!` before each push.

`evidence/README.md` maps the logs and explains the rerun. Hosted CI and production
acceptance remain for Claude's PR and deployment; no PR was opened by this thread.

## Remaining frame gaps and live acceptance

The approved empty states are exactly "No matches to review." and "No saved sites.".
Unframed states needing follow-up are initial loading, read/decision failures or
unknown outcomes, a price-position collection with no products, absent check
metadata/partial readings, queued or failed discovery outcomes, and GTIN suggestions
(the review frame describes brand/part-number suggestions). They do not receive
new copy. An unavailable read never becomes a successful empty account; an unknown
site outcome never receives a successful-check label. GTIN suggestions remain in
the API and do not receive the frame's false "No barcode match" explanation.

No live deployment or founder phone/account check was performed. After Claude's
merge/deploy, validate actual confirmed prices and the decision flow on
tiger.tervory.com at 1440 and 375. Workspace/Tank code triggers the main deployment
and its configured ZA counterpart; no Tiger room deployment configuration changed.
No provider, paid route or approved skill was added or edited.

## File and line inventory

| File | Change |
| --- | --- |
| `tank/access.py:1504,1548,1573,1652` | Guarded Undo, bounded review read, site summaries and product names. |
| `tank/command.py:43,1462,1965,2149` | Tools, adapters, confirmation dispatch and explicit code planning. |
| `workspace/lib/tank.ts:684` | Typed reads and durable decision helper. |
| `workspace/app/tiger/position-load.ts:7` | Independent tenant-bound server reads. |
| `workspace/app/tiger/position-model.ts:6,68,104` | View/data model, freshness/rank and real site metadata. |
| `workspace/app/tiger/position-actions.ts:7` | Session-owned decision action and revalidation. |
| `workspace/app/tiger/position-views.tsx:21,61,117,155` | The three responsive views and framed empty states. |
| `workspace/app/tiger/parts.tsx:3` | Shared Pill, PageLink, AttemptTime and table. |
| `workspace/app/tiger/view.tsx:76,142` | Existing Tiger shell/Watch list integration. |
| `workspace/app/tiger/page.tsx:17` | Server load and initial view. |
| `workspace/app/tiger/plugins.tsx:25` | Optional initial Source links tab. |
| `workspace/app/tiger/tiger.css:685` | Approved desktop/mobile styling. |
| `workspace/public/tiger/*.svg:1` | Four original Figma search/status assets; existing white logo reused. |
| `tests/test_tiger_competitors.py:185,231,242,264` | Tenant/receipt/Undo, outages, real cards and site metadata regressions. |
| `tests/test_command.py:49` and `tests/test_personal_tokens.py:49` | Tool-list expectations. |
| `tests/test_tiger_app_page.py:57` | Approved TG2 entry replaces the old unavailable-control assertion. |
| `tests/tiger_works/workspace.test.cjs:7,152` | Shared TSX helper support and isolated legacy-view regression. |
| `tests/tiger_position/workspace.test.cjs:1` | Code/data and server-transport tests. |
| `tests/tiger_position/browser.cjs:1` | Offline ten-frame visual/interaction checks. |
| `tests/tiger_position/fixture.ts:1`, `frames/*`, `evidence/*` | Test-only examples, approved references and proof. |

## Reproduction

Install Workspace dependencies with its lockfile. For the offline screenshot
harness, install test-only tools in an isolated prefix:

```sh
npm install --prefix .tmp/browser --no-audit --no-fund playwright@1.64.1 esbuild pngjs
PLAYWRIGHT_BROWSERS_PATH="$PWD/.tmp/browsers" .tmp/browser/node_modules/.bin/playwright install chromium
PLAYWRIGHT_BROWSERS_PATH="$PWD/.tmp/browsers" node tests/tiger_position/browser.cjs
node --test tests/tiger_position/workspace.test.cjs tests/tiger_works/workspace.test.cjs
```

The cloud executor needed standard fallback fonts for arrow glyphs; those were
provided only to its test browser, not added as application assets. Existing local
Inter/Jost files are used, with Inter's variable weight range matching Next's setup.
Python tests use Python 3.12, isolated Postgres/Redis, system Chromium and Compose,
with socket access restricted to loopback/unix. Containers use `--rm`, the
`tervory.test=1` label and the `codex-tiger-w4` prefix; TMPDIR is this checkout's `.tmp`.
