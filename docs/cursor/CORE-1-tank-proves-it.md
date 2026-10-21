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

## 7. Client savings are compulsory (founder, 21 Oct, 07:19 PT)
> "No one cares what we saved. They want what *they* saved."

The proof is per client. Every client has one **savings graph set**. The founder sees every client's set on `/tank/proof`. Each client sees the **same set, for their own account only**, live on their dashboard (`/`).

**The graph set (identical components in both places):**
1. **Spent against "would have cost"**, per day: two lines. Ranges: this month, the last 3 months, the last 12 months.
2. **Saved to date**: a cumulative line, with the total as the headline number.
3. **Saved this month**: in money and as a percentage of "would have cost".
4. **Done at no AI cost**: the share of work done by our own tools or cache, with no model call.
5. **Saved by team member**: a bar per agent (Base, Tiger, Market Lab and so on), using the agent names already shown in "Your team".

**Founder (`/tank/proof`):**
- An **all-clients** set at the top.
- Then **one set per client**, with a client picker. Tervory's own account is one entry in the picker, not the default.
- **Tervory's margin (founder only, never on a client screen).** What we save is money for us. For all clients, and per client, show:
  - what the client paid, from the price book and Stripe;
  - what the work actually cost us;
  - what it would have cost on the baseline;
  - our margin: paid minus actual cost, in money and as a percentage, per day and to date.

  Where a client's payments are not yet available, show "no billing data yet", never an estimate.
- Every number links to its ledger rows. CSV and PDF export per client, so a client's set can be sent as their case study.

**Client (`/`, their own dashboard):**
- The same five graphs, for their account only. A client can never see another client's numbers: Tank scopes by the signed-in organisation, server-side.
- **Live:** refreshes at least every 60 seconds, and when a job finishes.
- Plain words only. The banned words still apply: no model names, no Tank, ledger, shadow or rung.
- Tapping a number opens a drawer listing their own jobs, with what each cost, what it would have cost, and what they saved. No receipt IDs or model names.

**Only defensible numbers reach a client:**
- A row whose baseline is flagged (cheaper than actual, from a different family, or unknown) is left out of client totals.
- It is shown to the founder on `/tank/proof` to fix.
- A client total must always equal the sum of the rows behind it.

**Files:** this section adds `workspace/app/page.tsx` (the savings section only; leave the rest of DASH-1's layout as it is) and a shared graph component under `workspace/app/tank/proof/`, used by both pages.

**Tests:**
- A client sees only their own set.
- The founder sees all of them.
- The client totals equal their rows.
- Flagged rows are excluded from client totals but shown to the founder.
- No banned words on the client graphs.
- The margin view is founder-only and never appears on a client page.
- Screenshots at 375px and 1440px.

**Later (not this PR): a live ticker on tervory.com.** The founder wants the all-clients "saved to date" total on the public homepage. Build the totals so that a later lane can expose one aggregate-only figure:
- money saved for all clients to date, plus the jobs count;
- defensible rows only;
- no client names or per-client figures;
- cached, and safe to call publicly.

Do not build the public endpoint now.
