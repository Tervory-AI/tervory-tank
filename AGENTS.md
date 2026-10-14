# Working on Tervory (read this first)

This file is for any coding agent working in this repo (Cursor, Claude, others). It is short on purpose.

## What this repo is
One Docker Compose stack, deployed by Coolify on a Boston VPS:

| Service | Path | What it does |
| --- | --- | --- |
| Tank | `tank/` (Python 3.12, FastAPI, asyncpg) | The only path to any AI model. Policy table, ledger, cache, shadow/graduation, skills registry (Skala), Base pipeline, queue worker. |
| Workspace | `workspace/` (Next.js 15, App Router, Clerk) | The client app at app.tervory.com. Clerk organizations = tenants. |
| LiteLLM | `litellm/` | Holds every model key. Only Tank talks to it. |
| SearXNG | `searxng/` | Self-hosted search, internal only. |
| Postgres / Redis / Qdrant | images | Shared stores. |

Spec: Build Pack v2 (Claude Doc) and `README.md`.

## Rules that are not negotiable
1. **Never push to `main`.** A push to `main` deploys to production within two minutes. Work on a branch named `cursor/<task-id>-<slug>`, open a pull request, and stop. The founder or Claude reviews and merges.
2. **No secrets in code, ever.** Keys live in Coolify's environment panel. If you need a new variable, add its NAME to `.env.example` with a comment and say so in the PR.
3. **Every Tank read or write is scoped by `tenant_id`.** No endpoint may return another tenant's rows. Platform work uses `PLATFORM_TENANT`.
4. **The Workspace never calls a model or LiteLLM.** It calls Tank, server-side only, through `workspace/lib/tank.ts`. `TANK_API_KEY` never reaches the browser.
5. **Schema changes are additive and idempotent** (`CREATE … IF NOT EXISTS`, `ALTER … ADD COLUMN IF NOT EXISTS`). Tank applies `tank/schema.sql` on every start. Never drop or rename.
6. **Stay in your lane.** Each task brief lists the files you may change. Do not touch `run_route`, the queue worker, Skala's lifecycle or the cache in `tank/main.py` unless the brief says so. If the task needs it, say so in the PR instead.
7. **Skills are versioned packages.** Never edit an approved skill version in place; copy to a new version folder (`1.0.0` → `1.1.0`), update its `CHANGELOG.md`, add eval cases.
8. **Nothing installed on the founder's laptop.** Work as a cloud/background agent. The founder's laptop is a window only.
9. **Core skills know no industry.** `base.*`, Tiger and Tank learn general skills (find a site, read a page, mine prices, track a series). Industry knowledge (vocabulary, field mappings, targets, scoring) lives only in an engine (`ffl.*` today). A new industry is a new engine plugged into the same core skills, never a fork of them. If a core skill needs industry words, the engine passes them in.

10. **The ladder: free rungs run automatically, paid rungs wait for admin approval.** Every step of a run is a rung. Free rungs (code, our own search, our own browser) always run. A paid rung (Brave search, a model pass in a batch, a data vendor) pauses the run and waits for an admin to approve it, unless that rung is set to auto in `tank.paid_routes`. When a paid rung runs, the model gateway uses the cheapest model that has funds (`litellm/config.yaml`). No code may skip the pause: a skill only receives a paid key when its rung may run.

## Conventions
- Plain English in the UI. No jargon, no hype words.
- Brand: navy `#001840` (text, dark bands), red `#E80008` (the dot, one primary action, the accepted chip only), lines `#B8BFD0`, tint `#F4F6FB`. Headings Jost Light, body Inter, cost/meta lines JetBrains Mono. Logo files in `workspace/public/brand/` — use them as-is, never redraw the logo.
- Python: type hints, `async` all the way, no new heavy dependencies without saying why.
- TypeScript: strict, server components by default, client components only where interaction needs it.
- Every PR description: what changed, how you tested it, screenshots for UI, anything the founder must decide.

## How to check your work without a laptop
- `tests/` holds pytest tests that run without a database or network. Add to them.
- CI (GitHub Actions, task C4) runs the tests and `next build` on every PR.
- Production checks after merge are done by Claude through Coolify.
