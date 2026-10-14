# B3b — Wire the code-only Base skills into the Base room, and point the founder console at it

> Written 14 Oct 2026, 15:40 PT. Start only after **B3 (#46) and C13 (#45) are both merged**.

**Why:** C13 made passes 2c and 5 pure code (base.extract 2.0.0, base.business_data 2.0.0), but the live pipeline still sends them only plain text: no page HTML and no engine id. So they cannot read JSON-LD, and size and NAICS stay empty. B3 moved Base into its own room, but the founder console still reads the old `base.records` table, so it misses every row written after the move.

**Files you may change:** `agents/base/pipeline.py`, `tank/skills/base.scrape_site/1.2.0/` (new version; never edit 1.1.0), `tank/admin.py` (only the SQL that reads Base rows), new tests under `tests/`.

## 1. Page HTML from pass 2b
- New `base.scrape_site@1.2.0`: same as 1.1.0, plus `html` in the output: the home page and the about/contact pages it already fetched, joined, capped at 400 KB. Evals: 1.1.0 cases plus 3 cases checking `html` is present and capped.

## 2. Pass 2c and pass 5 get what they need
- In `agents/base/pipeline.py`, call `base.extract` with `{name, text, html, engine}` and `base.business_data` with its current fields plus `html` and `engine`. `engine` is the record's engine id (e.g. `ffl`), so the skill loads its own vocabulary and thresholds from the engine data files.
- When the answer came from code (no `_cost_usd`, or the skill ref is 2.x), label profile sources `site:code`, not `site:model`.
- Keep working with 1.0.0 too (it ignores the extra fields), so whichever version is approved, nothing breaks.
- No model call is added anywhere.

## 3. Founder console reads Base's own table
- In `tank/admin.py`, every query that reads `base.records` (including `BASE_BACKFILL_SQL`) reads `agent_base.records` instead. Read-only. Same columns.

## Done when
CI green; a fixture record with JSON-LD on its page comes out of the pipeline with categories, size band and NAICS filled, sources `site:code`, and $0 cost; the founder console counts rows written to `agent_base.records`; 1.0.0 and 2.0.0 both run through the pipeline in tests without errors.

## After merge (founder)
1. Approve `base.scrape_site 1.2.0`, `base.extract 2.0.0` and `base.business_data 2.0.0` on https://app.tervory.com/skills.
2. Data page → the batch → **Re-run** "model skipped". It costs $0.
