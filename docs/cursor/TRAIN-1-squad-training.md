# TRAIN-1 — Squad training infrastructure (gold sets, re-tests, training pairs)

> Written 18 Oct 2026, 17:05 PT. Shared infrastructure for every agent, so the squad can be tested and trained the same way. Implements "Tests every agent gets" from the Agent tests page and the Build plan. One PR; it touches shared files (`tank/`), so it goes to the final review before deploy.

**Files you may change:** `tank/gold.py`, `tank/training.py` (new), `tank/main.py` (mount the two new routers only), `tank/schema.sql` (additive only), `workspace/app/skala/gold/` (new page), `workspace/app/api/skala/` (new routes only), `.github/workflows/retest.yml` (new), `.env.example` (names only), new tests under `tests/`.

## 1. Gold sets (one store for every agent)
- Table `tank.gold_examples (id, skill_id, agent, input jsonb, expected jsonb, status candidate|checked|rejected, holdout bool, source, checked_by, checked_at, note)`.
- On start, import every skill's existing `evals/cases.jsonl` as `candidate` rows (idempotent; never duplicate).
- Candidates also come from live work: ledger rows a client accepted, approved Rig fits, lawyer-released Zenas findings, Tiger reads a person confirmed. Never from rejected work.
- When an example is checked, 20% are marked `holdout` automatically (stable hash), used only for the final check before a switch.

## 2. The checking page (`/skala/gold`, founders and reviewers only)
- Pick an agent and skill. One example at a time: the input, the expected answer, buttons **Right**, **Wrong** (with a correction box), **Skip**. Keyboard shortcuts.
- Shows per skill: checked / target (100), holdout count.

## 3. Weekly re-test
- `.github/workflows/retest.yml`, weekly, plus run on demand: calls a Tank endpoint that runs every approved skill against its checked gold set (not holdout), stores `tank.gold_scores (skill_id, version, score, n, ran_at)`, and opens a GitHub issue "Score drop: <skill>" when a score falls more than 2 points from the last run.
- Uses the ladder as normal; pure-code skills cost $0.

## 4. Training pairs (what our own models learn from)
- Table `tank.training_pairs (id, agent, task_type, region, input jsonb, output jsonb, approved_by, source, created_at)`: every checked gold example, every client-accepted answer, every lawyer-released Zenas matter, every decided case converted by Zenas. Region is kept; ZA pairs stay in the ZA region's database.
- Nightly export to a private Hugging Face dataset per agent when `HF_TOKEN` and `HF_ORG` are set (JSONL, versioned by date); skipped cleanly when not set. Never export a row with a detected personal identifier from a client matter.

## 5. Squad training view (on the Tank page)
Per agent: gold examples checked / target, last re-test score and trend, training pairs collected, holdout size.

## Rules
- Schema changes additive and tested on an empty database, re-applied, and on a database with the current main schema and agent roles (the 14 Oct outage).
- Every read and write scoped by tenant where client data is involved. No model call added beyond the re-test using existing skills. No secrets in code, URLs, logs or tests.

## Done when
CI green; existing evals appear as candidates; marking an example Right makes it checked and 1 in 5 become holdout (tested); the re-test stores scores and opens an issue on a planted 3-point drop (tested); training pairs fill from an accepted ledger row and a released matter (tested); export is skipped without `HF_TOKEN` (tested).

## Founder
Create a Hugging Face organisation and a write token; add `HF_TOKEN` and `HF_ORG` to Tank in Coolify. Then check examples on `/skala/gold` (lawyers check Zenas).
