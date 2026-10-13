# C4 — Tests and CI on every pull request

**Goal:** every PR proves itself before a human looks at it.

**Files you may change:** `tests/`, `.github/workflows/ci.yml` (new), `tank/requirements-dev.txt` (new), `workspace/package.json` (scripts only).

**Do:**
- `tank/requirements-dev.txt`: `pytest`, `pytest-asyncio`, `ruff`.
- `tests/test_skills_offline.py`: discover every `tank/skills/*/*/skill.yaml`; for each skill with `rung: 3` run its `evals/cases.jsonl` through `run.py` with a stub context (no network: `ctx.http` raises, `ctx.model` raises, `ctx.env = {}`) and the same scoring as `tank/skala.py::score_case`. Cases that need the network must be skipped automatically: mark a case as network-bound if the run raises from the stub `http`. Report per-skill pass counts. Fail the test if an offline-capable case fails.
- `tests/test_schema.py`: assert every statement in `tank/schema.sql` is idempotent-shaped (`CREATE … IF NOT EXISTS`, `ALTER … ADD COLUMN IF NOT EXISTS`, `INSERT … ON CONFLICT`, `UPDATE`), no `DROP`, no `RENAME`.
- `tests/test_tenant_scoping.py`: parse `tank/main.py` with `ast`; every function decorated with an `@app.get/post/put` route whose path starts `/v1/` and takes a `tenant_id` parameter must reference `tenant_id` inside every SQL string it passes to `conn.fetch*`/`execute`. (A cheap guard, not a proof.)
- Keep `tests/test_smoke.py` passing.
- `.github/workflows/ci.yml` on `pull_request`: job `tank` (Python 3.12, install `tank/requirements.txt` + dev, `ruff check tank tests --select E9,F`, `pytest -q`); job `workspace` (Node 22, `npm ci`, `npx next build` with dummy env `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXk` and `CLERK_SECRET_KEY=sk_test_dummy`).

**Done when:** the workflow runs green on its own PR, and the PR description lists the per-skill offline pass counts.
