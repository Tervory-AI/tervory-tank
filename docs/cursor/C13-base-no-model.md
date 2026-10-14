# C13 — Base without a model: passes 2c and 5 as pure code

**Founder direction (14 Oct 2026): the goal is not using models less, it is not needing one at all.** Base already finds sites, reads pages, pulls contacts and socials, and verifies, all in plain code. Only two passes call a model: 2c (`base.extract`) and 5 (`base.business_data`). Rebuild both as pure code so a full Base run costs nothing in model credit. Models may be used **offline** to help write and check the rules, never at run time.

Read `AGENTS.md` (rule 9: core skills know no industry; vocabulary and mappings live in an engine) and the two 1.0.0 skills in `tank/skills/`.

**Files you may change:** `tank/skills/base.extract/2.0.0/`, `tank/skills/base.business_data/2.0.0/` (new versions; never edit 1.0.0), `tank/skills/ffl.*` engine data files for the FFL vocabulary (new files only), new tests under `tests/`. No change to `tank/main.py`.

## `base.extract@2.0.0` (no `task_type`; pure code)
Same input and output as 1.0.0, plus `method` and `confidence` per field. In this order, first hit wins per field:
1. **Structured data on the page:** JSON-LD / microdata (`Organization`, `LocalBusiness`, `Store`, `Person`, `hasOfferCatalog`, `makesOffer`, `openingHours`), OpenGraph and meta description.
2. **Page structure:** navigation menu labels, headings, and the "about"/"services"/"team" sections. People come from `Name – Role` patterns and team cards.
3. **Engine vocabulary:** the engine passes `{term → category}` and `{term → service}` dictionaries (FFL: the existing ffl engine supplies them). Core code only matches; it holds no industry words.
- `description` = meta/OG description, else the first sentence of the about section, trimmed to one line.
- Nothing is invented: an empty field stays empty.

## `base.business_data@2.0.0` (pure code)
Same output as 1.0.0, still labelled as estimates, confidence capped at 60.
- **Size band** from a points score over signals Base already has: number of locations, people found, breadth of services, online store present, social reach, years trading ("since 19xx", © year span), licence type (engine). The score thresholds are data in the engine, not code.
- **Revenue band** from size band via an engine table.
- **Business model** by rules: online store → retail + ecommerce; "wholesale/distributor/trade only" → B2B; and so on.
- **NAICS** from an engine `category → NAICS` table.

## Proof
- Both skills pass the existing 1.0.0 eval cases at the same thresholds (≥ 0.8), plus at least 10 new cases each from saved HTML fixtures (no network).
- An agreement report against 1.0.0's model answers where those exist (Tank's learning corpus), printed in the PR: per field, % agreement.
- Unit tests prove no model call is possible from 2.0.0 (no `task_type`, no `ctx.model` use).

**Done when:** CI green; Claude approves 2.0.0 in Skala; the ~8,000 records with skipped model passes are re-run on 2.0.0 at zero model cost.
