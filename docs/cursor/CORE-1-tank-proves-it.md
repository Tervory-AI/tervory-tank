# CORE-1: Tank proves it is cheaper (bench, savings, proof page)

> Written 20 Oct 2026. Founder: "Going between models, show receipts and the benefits. Right now we have proven nothing." #210 gives Tank its live roster with prices (`_roster_models`, `/v1/models`). This lane turns that into evidence.

**Files you may change:**
- new `tank/bench.py` and `tank/proof.py`;
- `tank/main.py` (route registration and the ledger write for `baseline_cost_usd` only);
- `tank/graduate.py`;
- `tank/schema.sql` (additive);
- `workspace/app/tank/` (graduation table, the new `/tank/proof` page);
- `.env.example` (names only);
- tests.

Do not change room code.

1. **Real cost now.** "Now / call" on the graduation table comes from `tank.ledger` for the current model: the median over 30 days on this box. With no calls it says "no calls yet".
2. **Bench, with no live traffic needed.**
   - **When it runs:** nightly, and when the roster or prices change (`tank.search_state` fingerprints).
   - **What it runs:** each paid task's eval cases, plus held-out gold when present, on every roster model, cheapest first.
   - **What it records:** the score and cost per call, in `tank.route_evidence`.
   - **What it proposes:** the cheapest model scoring at least as well as the current one, as the task's `candidate_model`. It never switches the live model; the founder promotes.
   - **Cap:** daily bench spend is limited by `TANK_BENCH_MAX_USD` (default 5) and recorded on the ledger under the platform tenant.
3. **A savings line on every call.**
   - Every ledger row stores `baseline_model` and `baseline_cost_usd`: the same tokens priced on the task's baseline model. The baseline is a new policy column, defaulting to the most expensive model in the same family on the roster.
   - Saved = baseline minus actual.
   - Backfill existing rows from their tokens and the price book, and mark them `backfilled`.
4. **The proof page** at `/tank/proof` (founder only). For each task:
   - what was tested, with scores and the cost per call before and after;
   - shadow pairs: primary versus shadow model, the cost of each, the agreement score, the sample count, and "could have cost" totals;
   - promotions, with dates;
   - money saved to date;
   - the share of calls served by code with no model.

   Every number links to its evidence rows. CSV and PDF export.
5. **`auto_promote` is off by default.** Change the column default to false and set existing rows to false in the schema migration. The founder promotes.
6. Remove the old vault "Pipeline to …" boxes from the Tank page.

## Done when
CI green. Tests:
- the bench proposes the cheaper model only when its score is not lower;
- the spend cap stops the bench;
- saved is computed from baseline and actual;
- the backfill marks rows;
- proof page numbers match ledger rows;
- `auto_promote` defaults to false.
