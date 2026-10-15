# Z4 — Zenas on the ladder: pair each request with work already done

> Written 14 Oct 2026, 17:55 PT. Replaces the Z4 section of `docs/cursor/Z-zenas-plan.md`. Depends on Z2 (pool, merged), Z2b (US library) for real content, and T6 (graduation) for automatic promotion. Can be built on fixtures before Z2b and T6 land.

**The idea (founder, 14 Oct 2026):** a legal answer is **law applied to facts**. The law does not change without a reason we can see (a new version of a statute or rule, a new judgment). Facts are never the same twice, so Zenas **pairs each new request with the matters already done**: it finds the closest worked matters, reuses what carries over, and works out only what is different. Every finished matter makes the next one cheaper, and the growing set of worked matters is what our own model is built on. This is the Tank ladder applied to legal work.

**Files you may change:** `agents/zenas/` (new `core/rules.py`, `core/apply.py`, `core/compose.py`, schema additions in `agents/zenas/schema.sql`), `tank/skills/zenas.*` (new skills at 1.0.0, each with evals + CHANGELOG), policy rows appended to `tank/schema.sql` (additive, `ON CONFLICT DO NOTHING`), new tests under `tests/`.

## The three layers

### 1. Law layer: rule cards (shared, keyed by law version)
- A **rule card** is the law for one legal question, broken into its parts: `{id, jurisdiction, question, elements[] (each a test with its source citation), exceptions[], defences[], remedies[], sources[] (doc id + version), as_at, status draft|lawyer_approved|stale, approved_by, model_used, cost_usd}`.
- Built by `zenas.rule_card@1.0.0` (model via Tank, top tier, task type `zenas.rule_card`) from passages retrieved from the pool. Every element cites a pool document; `zenas.cite_check` must pass.
- Stored in `agent_zenas.rule_cards`, shared across all tenants **of the same region**. A rule card contains law only, never client facts.
- A lawyer approves the card once (review queue). After that, **every client question on that law reuses it at no model cost** (ladder rung 4, cache), until the law changes.

### 2. Matter matching: pair the request with work already done
- Every finished, lawyer-released matter is stored as a **worked matter**: `{id, region, jurisdiction, area, rule_card_ids, fact_pattern (structured features + embedding), element_findings[] (per element: finding, the facts it rested on, the reasoning), outcome, lawyer_edits, as_at}`. Personal identifiers are replaced by placeholders (`zenas.pii`) before it is stored.
- `zenas.match@1.0.0` (code): for a new request, finds the closest worked matters by rule card + structured fact features first, then meaning (embeddings), and returns them ranked with a per-element **fact difference**: which facts are the same as a worked matter's and which differ.
- Sharing scope is a founder setting, `ZENAS_MATTER_SHARING=region|tenant` (default `region`: worked matters from every client in the same region are matched, identifiers removed). Never across regions.

### 3. Facts layer: applying the card (per matter)
- `zenas.apply@1.0.0`: takes the client's facts, a rule card and the matches, and decides, element by element: met / not met / unclear, with the fact that supports it and what is missing. Output is structured, never free prose.
- Ladder for apply, cheapest first:
  - **Reuse (rung 4):** where an element's relevant facts match a worked matter's, reuse that matter's lawyer-approved finding and reasoning, cited to it. $0.
  - **Code (rung 3):** when a card's elements are checkable from structured facts (dates, amounts, yes/no, party types, jurisdictions), the card carries a decision table and apply runs as pure code. Court deadlines (Z6) are already like this.
  - **Cheap model (rung 1, cheapest available):** one small call per unclear element, never a long open-ended prompt.
  - Graduation (T6): shadow runs compare cheap model vs code vs the top model, element by element; when code or a cheaper model agrees at the bar, Tank switches by itself and rolls back by itself on a drop.
- Only elements whose facts differ from every close worked matter go to code or a model.

### 5. Building our own model on the worked matters
- Every released matter is saved as a training pair: request (identifiers removed) → the lawyer-approved element findings and memo, with the lawyer's edits. Stored in `agent_zenas.training_pairs`, per region.
- These pairs are the training set for our own legal model (T7, ladder rung 2) and the golden cases T6 uses to test cheaper routes.

### 4. Writing layer
- `zenas.compose@1.0.0`: builds the memo (IRAC) from the card + the apply result with templates (code). A cheap model only smooths the wording; it cannot add law. `zenas.plain_language` as in the plan.

## When the law changes (what keeps the cache honest)
- Every rule card records the exact source versions it relied on.
- The nightly pool update (Z2/Z2b) and the citation graph (eyecite) emit "changed" events: new statute or rule version, a case reversed, overruled, or newly citing.
- Any card that relied on a changed source is marked **stale**: it stops being served, is rebuilt by `zenas.rule_card`, and goes back to a lawyer. Matters keep their "as at" date, so an old answer can always be reproduced as it was.

## Skills (all 1.0.0, evals with each)
`zenas.retrieve` (code: citation + full text + meaning, filtered by jurisdiction and as-at date), `zenas.cite_check` (code), `zenas.rule_card` (model), `zenas.match` (code), `zenas.apply` (code first, model per element), `zenas.compose` (code + cheap model), `zenas.plain_language` (cheap model). Every request still passes `zenas.scope` first. Policy rows: `zenas.rule_card` top tier; `zenas.apply` and `zenas.compose` cheapest available; cache_scope `region` for rule cards, `tenant` for apply.

## Measured (founder console)
Per legal question: first-answer cost, cost per later matter, share of elements reused from worked matters, share decided by code, worked matters and training pairs collected, cards stale vs approved, lawyer edits per card. This is the evidence for the invention record.

## Done when
CI green on fixtures; a second client asking the same legal question reuses the approved card with $0 model cost on the law layer (tested); a new matter with mostly the same facts as a worked matter reuses those elements' findings at $0 and sends only the differing elements on (tested); a released matter produces a training pair with no identifiers (tested); a statute version change marks the cards that relied on it stale (tested); a card with a planted fake citation is never approved (tested); apply runs as pure code for a fixture card with a decision table; nothing from one tenant's facts appears in a rule card or another tenant's results (tested).

## From the founder
Lawyer accounts to approve rule cards; the 20 test questions per country (these become the first rule cards).
