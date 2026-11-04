# Wave 4b Workspace dashboards

Base: `origin/main` **981ac096**. Branch: `codex/dashboards-w4`. Sources: founder **10:115 / 20:44**, client **12:2 / 20:2**, and their checked-in export/spec folders. DATA values follow their real sources, not the example figures in a frame. The latest founder ruling replaces idle dashes with derived zero counts.

No founder session, sign-in, live credential or client preview is used. All evidence below is offline. The founder verifies live values after deploy using the testing sheet below.

## Founder control panel — completed

Fixed the renamed spend label, “Approve all ready” label, extra unframed Workers diagnostics card, idle squad dashes and the shared shell's 1184px width cap at 1440. Restored original status-dot assets from the export. Preserved approval confirmation and all founder-only routes. Missing/unpriced spend refuses the incomplete measurement; it is not relabelled as a partial total or shown as a dash/zero. A genuinely empty ledger still measures zero.

Every visible value has the following provenance. Line references refer to this branch.

| Value | Component / derivation | Loader | Tank route / query or provider source |
| --- | --- | --- | --- |
| Sign-ups total, +N this week, sparkline | `workspace/app/control/view.tsx:58`, `values.ts:26` | `workspace/app/control/sources.ts:19` | Clerk `users.getCount` and paginated `users.getUserList`: `sources.ts:21`, `sources.ts:31`, `sources.ts:51`. Direct server-side provider source specified by the frame; there is no Tank copy/table of Clerk's user population. |
| Paying clients total, +N this week, sparkline | `workspace/app/control/view.tsx:59` | `workspace/app/control/sources.ts:62` | Stripe live active subscriptions plus positive paid invoices: `sources.ts:66`, `sources.ts:69`, `sources.ts:75`, `sources.ts:89`. Direct server-side provider source specified by the frame; a price-book rate is not counted as payment. |
| Work done today, code share, work sparkline | `workspace/app/control/view.tsx:60`, `values.ts:32` | `workspace/lib/tank.ts:1139` | `/v1/dashboards/founder`, `tank/dashboards.py:73` → `measurements:34` → `tank.ledger`, delivered and code counts: `dashboards.py:37`. |
| Spent this month, spend sparkline | `workspace/app/control/view.tsx:61`, `values.ts:47` | `workspace/lib/tank.ts:1139` | Same route → `tank.ledger.cost_usd`, `cost_status`, `unpriced`: `tank/dashboards.py:40`. Incomplete price coverage is a source gap, never an invented total. |
| Needs you count | `workspace/app/control/widgets.tsx:47` | Derived from the three sources below | Count of visible action rows; hidden at zero. |
| Skills passed | `workspace/app/control/view.tsx:63`, `values.ts:21` | `workspace/lib/tank.ts:1139` | `/v1/dashboards/founder` → `tank.skills`, staging/present and score/threshold fields: `tank/dashboards.py:76`. |
| Proven task label, monthly saving | `workspace/app/control/widgets.tsx:60`, `values.ts:61` | `workspace/lib/tank.ts:1156` | `/v1/graduation`, `tank/main.py:2225` → `tank.policy`, `tank.shadow` costs/agreement, `tank.ledger` 30-day calls: `main.py:2243`, `main.py:2258`. Existing eligibility and cheaper-cost checks; monthly estimate = measured per-call difference × measured calls. |
| Daily check examples | `workspace/app/control/page.tsx:27` | `workspace/lib/tank.ts:990` | `/v1/gold/summary`, `tank/gold.py:125` → `tank.gold_examples`, candidate count: `gold.py:129`. |
| Squad running/queued counts and dots | `workspace/app/control/view.tsx:67` | `workspace/lib/tank.ts:1139` | `/v1/dashboards/founder` → `tank.tasks` grouped by agent/status: `tank/dashboards.py:80`. No matching rows means measured zero, grey dot. |
| Latest names, company, country, plan, age; All N | `workspace/app/control/view.tsx:80`, `values.ts:70` | `workspace/app/control/sources.ts:19` | Clerk user names, public metadata and creation timestamps: `sources.ts:40`. Missing metadata throws rather than supplying a placeholder. |
| Paid pause/resume state | `workspace/app/control/page.tsx:18`, `widgets.tsx:9` | `workspace/lib/tank.ts:1142` | `/v1/controls`, `tank/controls.py:101` → `tank.controls.value`, `controls.py:37`. |
| Workers pause/resume state | `workspace/app/control/page.tsx:19`, `widgets.tsx:21` | `workspace/app/control/workers.ts:20` | `/v1/controls/workers`, `tank/workers_status.py:140` → `tank.workers_controls`, `workers_status.py:153`. |

Control destinations are real: pause actions `workspace/app/control/actions.ts:14` → `workspace/lib/tank.ts:1145` → `tank/controls.py:110`; workers pause `actions.ts:24` → `workers.ts:23` → `tank/controls.py:133`; Switch `actions.ts:19` → `workspace/lib/tank.ts:1150` → `tank/main.py:2412`; Approve all retains `workspace/app/skala/approve-all.tsx:11` → `workspace/app/api/skala/route.ts:50` → the existing preview/confirm endpoints. Number links open `workspace/app/control/source/route.ts:10`. Start opens `/skala/gold`, Open the window `/chats`, Proof report `/tank/proof`, All N `/control/signups`.

Offline proof: `tests/dashboards_w4_routes.py` executes production FastAPI routes over isolated query rows with placeholder markers. Graduation loads the exact read-only function via AST to avoid booting unrelated model services; its SQL, auth decision, eligibility and arithmetic are unchanged. Price/research transports are empty doubles. `tests/dashboards-w4-render.cjs` uses the actual `workspace/lib/tank.ts` loaders over that route JSON, plus isolated Clerk/Stripe transport doubles, and renders the actual page. `tests/dashboards-w4-browser.mjs` verifies every displayed fixture value at 1440/375, assets, enabled approval control, text bounds and before/after screenshots. Neither database doubles nor provider doubles prove live data or execute production writes.

Passed: route fixture generation, route-to-screen render, 1440/375 browser checks, existing dashboard regressions, Workspace TypeScript checking and the full production build. Screenshots: `docs/screenshots/dashboards-w4/{main,current}-founder-{1440,375}.png`.

## No frame / source gaps

- No distinct 375px export exists for either dashboard in the supplied folders. Mobile captures prove wrapping and approved content, not identity to a nonexistent mobile frame.
- The extra Workers diagnostics card has no place in 10:115 and is removed from this screen; its reusable component remains available elsewhere.
- Bulk approval confirmation/progress/errors and generic source-failure pages have no frame in these two exports. Existing safety behavior is preserved; no replacement copy is invented.
- Ledger rows with missing prices cannot produce a complete monthly spend. Provider outages/missing signup metadata likewise cannot produce truthful provider values. These remain explicit source failures rather than sample values, partial totals or disabled pretend controls.
- Client dashboard comparison and provenance follow in the next screen commit.

## Founder testing sheet — after deploy

- [ ] Founder only: compare every KPI, week delta and sparkline with its linked source and Clerk/Stripe; confirm empty-ledger zero and refusal of incomplete prices.
- [ ] Confirm needs-you row count, tested skills, measured candidate savings and daily-check example count against their source links.
- [ ] Confirm per-squad running/queued/idle measurements and the latest five real signup metadata/timestamps.
- [ ] Exercise paid pause/resume, workers pause/resume, approval confirmation, Switch/Later and source/navigation links using the founder's own session.
- [ ] Founder visually accepts 1440px and 375px. Builder screenshots are offline fixture evidence only.
