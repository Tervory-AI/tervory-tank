# BASE-CTX-3: let Context.dev run inside Base, and learn from every record

> Written 20 Oct 2026. The founder has 50,000 Context.dev credits. Founder: let Base run with Context.dev **provided the learning is in place**. Every Context.dev answer must leave a receipt and a lesson, not just a filled field. The #195 trial compares Context.dev with ATF truth; this lane makes it a rung on Base's ladder.

**Files you may change:**
- `agents/base/` (pipeline, sources, gold_sources.py, app.py);
- `tank/` (route registration only; vendor ledger reads);
- `workspace/app/base/` (receipt and lessons view);
- tests.

1. **Context.dev as a rung, after our own code.** It runs only for records our code skills could not finish (no site, no contact, no category), never first.
   - Paid: it pauses for the founder's approval unless the rung is set to auto, with a per-batch credit cap (`BASE_CTX_MAX_CREDITS`, default 500).
   - Every call is written to Tank's vendor ledger (`/v1/ledger/vendor`): credits, the USD equivalent, record id, batch id.
2. **Learn from every result.** For each record Context.dev touches, store three things side by side:
   - what our code found;
   - what Context.dev returned;
   - the ATF or official truth, where it exists.
   - Where Context.dev is right and our code missed, the record becomes a **gold candidate** for the code skill that missed, with label family `context-dev:{skill}:{YYYY-MM}`, so the code skill learns from it.
   - Where it disagrees with the official truth, it is flagged and never used.
3. **Show what each step cost and what it earned.** Each batch's receipt shows per step: code (free), Context.dev (credits and USD), and how many records each step completed. The "lessons" count shows the new gold candidates created.
4. **Region:** only public business data, and only on the box the batch runs on.

## Done when
CI green. Tests:
- Context.dev never runs before the code skills;
- it stops at the credit cap;
- it pauses for approval when not on auto;
- every call has a vendor ledger row;
- a record where Context.dev beats our code becomes a gold candidate with the right family;
- a disagreement with ATF truth is flagged and not used.
