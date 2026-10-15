# Z4 — Zenas on the ladder: law worked out once, facts applied cheaply

> Written 14 Oct 2026, 17:55 PT. Replaces the Z4 section of `docs/cursor/Z-zenas-plan.md`. Depends on Z2 (pool, merged), Z2b (US library) for real content, and T6 (graduation) for automatic promotion. Can be built on fixtures before Z2b and T6 land.

**The idea (founder, 14 Oct 2026):** a legal answer is **law applied to facts**. Facts change with every client; the law does not change without a reason we can see (a new version of a statute or rule, a new judgment). So the law part is worked out **once per law version**, checked, stored and reused for every client, and only the facts part runs per matter, as cheaply as possible. The more questions Zenas answers, the cheaper each one gets. This is the Tank ladder applied to legal work.

**Files you may change:** `agents/zenas/` (new `core/rules.py`, `core/apply.py`, `core/compose.py`, schema additions in `agents/zenas/schema.sql`), `tank/skills/zenas.*` (new skills at 1.0.0, each with evals + CHANGELOG), policy rows appended to `tank/schema.sql` (additive, `ON CONFLICT DO NOTHING`), new tests under `tests/`.

## The three layers

### 1. Law layer: rule cards (shared, keyed by law version)
- A **rule card** is the law for one legal question, broken into its parts: `{id, jurisdiction, question, elements[] (each a test with its source citation), exceptions[], defences[], remedies[], sources[] (doc id + version), as_at, status draft|lawyer_approved|stale, approved_by, model_used, cost_usd}`.
- Built by `zenas.rule_card@1.0.0` (model via Tank, top tier, task type `zenas.rule_card`) from passages retrieved from the pool. Every element cites a pool document; `zenas.cite_check` must pass.
- Stored in `agent_zenas.rule_cards`, shared across all tenants **of the same region**. A rule card contains law only, never client facts.
- A lawyer approves the card once (review queue). After that, **every client question on that law reuses it at no model cost** (ladder rung 4, cache), until the law changes.

### 2. Facts layer: applying the card (per tenant, private)
- `zenas.apply@1.0.0`: takes the client's facts and a rule card and decides, element by element: met / not met / unclear, with the fact that supports it and what is missing. Output is structured, never free prose.
- Ladder for apply, cheapest first:
  - **Code (rung 3):** when a card's elements are checkable from structured facts (dates, amounts, yes/no, party types, jurisdictions), the card carries a decision table and apply runs as pure code. Court deadlines (Z6) are already like this.
  - **Cheap model (rung 1, cheapest available):** one small call per unclear element, never a long open-ended prompt.
  - Graduation (T6): shadow runs compare cheap model vs code vs the top model, element by element; when code or a cheaper model agrees at the bar, Tank switches by itself and rolls back by itself on a drop.
- Facts and their results are cached per tenant and matter only.

### 3. Writing layer
- `zenas.compose@1.0.0`: builds the memo (IRAC) from the card + the apply result with templates (code). A cheap model only smooths the wording; it cannot add law. `zenas.plain_language` as in the plan.

## When the law changes (what keeps the cache honest)
- Every rule card records the exact source versions it relied on.
- The nightly pool update (Z2/Z2b) and the citation graph (eyecite) emit "changed" events: new statute or rule version, a case reversed, overruled, or newly citing.
- Any card that relied on a changed source is marked **stale**: it stops being served, is rebuilt by `zenas.rule_card`, and goes back to a lawyer. Matters keep their "as at" date, so an old answer can always be reproduced as it was.

## Skills (all 1.0.0, evals with each)
`zenas.retrieve` (code: citation + full text + meaning, filtered by jurisdiction and as-at date), `zenas.cite_check` (code), `zenas.rule_card` (model), `zenas.apply` (code first, model per element), `zenas.compose` (code + cheap model), `zenas.plain_language` (cheap model). Every request still passes `zenas.scope` first. Policy rows: `zenas.rule_card` top tier; `zenas.apply` and `zenas.compose` cheapest available; cache_scope `region` for rule cards, `tenant` for apply.

## Measured (founder console)
Per legal question: first-answer cost, repeat-answer cost, share of elements decided by code, cards stale vs approved, lawyer edits per card. This is the evidence for the invention record.

## Done when
CI green on fixtures; a second client asking the same legal question reuses the approved card with $0 model cost on the law layer (tested); a statute version change marks the cards that relied on it stale (tested); a card with a planted fake citation is never approved (tested); apply runs as pure code for a fixture card with a decision table; nothing from one tenant's facts appears in a rule card or another tenant's results (tested).

## From the founder
Lawyer accounts to approve rule cards; the 20 test questions per country (these become the first rule cards).
