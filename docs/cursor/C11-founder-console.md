# C11 — Founder console: independence, revenue and margin

**Goal:** one founder-only page in the Tervory backend that shows, live and over time, how much of our work runs without a paid model, what we earn per outcome, what it costs us, and the margin — with every graduation (a task moving down the ladder) marked on the graph. This is the business's core growth metric. Clients never see it.

**Files you may change:** `tank/admin.py` (new module, mounted in `tank/main.py` with ONE `include_router` line), `tank/schema.sql` (additive), `workspace/app/admin/*` (new), `workspace/lib/admin.ts` (new — do not edit `workspace/lib/tank.ts`), `tests/`.

## Who can see it
- Tank: every `/v1/admin/*` endpoint requires the Workspace key AND header `X-Tervory-Admin: <clerk user id>` matching env `TERVORY_ADMIN_USER_IDS` (comma-separated). Otherwise 404 (not 403: the page should not be discoverable).
- Workspace: `/admin` renders only for those user ids; everyone else gets the normal 404.

## Data (Tank, additive)
- `tank.price_book (id, tenant_id NULL=default, outcome_type, unit_price, currency, effective_from, effective_to, note)` — what we charge per outcome (e.g. `base.record_enriched`, `rig.setup_quoted`, `zenas.document_released`, `tier0.answer_accepted`). Until billing (Stripe) exists, revenue is **booked value** = outcomes × price_book, and the page says so.
- `tank.outcomes (id, ts, tenant_id, agent, outcome_type, quantity, ref, ledger_ids uuid[])` — one row per billable outcome, written by the agent/worker when the outcome happens. For Base, add a backfill: one `base.record_enriched` per `base.records` row with `status='done'`, dated by `updated_at`.
- `tank.econ_daily (day, tenant_id, agent, task_type, rung, calls, cost_usd, outcomes, booked_usd, cache_hits)` — a nightly rollup (idempotent upsert for yesterday and today, plus a one-off backfill from the first ledger row). History survives ledger pruning.
- Graduation events already live in `tank.policy_log` (promote/rollback). Read them; do not change that table.

## Endpoints (read-only, in `tank/admin.py`)
- `GET /v1/admin/counters` → lifetime and 30-day: calls, model spend, outcomes, booked revenue, margin %, **independence %** (share of calls at rungs 2–4: owned model, code, cache), cost per outcome.
- `GET /v1/admin/series?days=90&group=agent|task_type|tenant` → per day: calls by rung, spend, outcomes, booked revenue, margin, independence %.
- `GET /v1/admin/graduations?days=90` → each promote/rollback with task type, from-model, to-model, saving %.
- `GET /v1/admin/focus?days=30` → **the paid-work focus list**: every task type that still uses a paid model (rung 1), ranked by spend, with: paid model, calls, spend, share of all paid spend, cache-hit rate, whether a shadow candidate is set, its agreement score and sample size (from `tank.shadow` / the graduation view), and a status: `no candidate` / `testing` / `ready to promote` / `promoted`.
- `GET /v1/admin/price_book` and `PUT /v1/admin/price_book` (founder edits prices; every change is a new row, never an update in place).

## The page (`/admin`)
- **Counter strip** (big numbers): independence %, margin %, booked revenue (30 days and lifetime), model spend, cost per outcome. Each with its change vs the previous 30 days.
- **Main graph:** daily independence % (line) over stacked calls by rung, with a marker on every graduation event (hover shows the task and saving). Range 30 / 90 / 365 days.
- **Economics graph:** daily booked revenue vs model spend, margin shaded between them.
- **Focus list (top of the page, under the counters):** "Where our paid spend goes" — the `/focus` rows as a ranked bar list (spend per task type and model), each with its status chip and a one-line next step ("set a shadow candidate", "keep testing: 40 of 200 samples", "ready to promote"). This is the to-do list for moving work down the ladder.
- **Tables:** by agent and by task type — calls, independence %, spend, outcomes, cost per outcome, margin; sortable. Click a task type → its own graph and its graduation history.
- **Price book** editor.
- Light and dark, brand tokens (navy #001840, red #E80008 sparingly, JetBrains Mono for numbers).

**Done when:** the focus list ranks a fixture ledger correctly and shows the right status for a task with no candidate, one testing and one eligible; tests prove a non-admin gets 404 on every admin endpoint; the rollup is idempotent (running it twice changes nothing); independence % and margin are computed correctly on a fixture ledger; the Base backfill produces one outcome per done record; PR with screenshots using real data, then stop for Claude's review.
