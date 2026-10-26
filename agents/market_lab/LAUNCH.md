# Market Lab launch verification

Branch: `codex/market-lab-works`, based on `origin/main` at `65067a4`.
The local Postgres fixture job is complete. Every screenshot is labelled **local, fixture page**.
This proves the local question-to-stored-source flow. Grok owns live feed collection;
Claude owns signed-in proof in the founder's browser after the founder deploys.
Those checks are not claimed here. No test sign-in or credentials are required for this proof.

## The job, step by step, as a client does it

1. Sign in, choose a workspace, and open `/market-lab`.
2. Choose **Refresh feeds**. Collection runs for that workspace. The page shows progress and refreshes while collection is queued or running.
3. Check **On**: each counted feed has observations stored by its last collection. Missing keys say **Off, needs key** and are skipped. Blocked sites say **Off, blocked**. Linked pages never count as stored feeds.
4. Ask “What are the latest population figures for California?” The brief uses stored observations only; it supplies no figures when evidence is absent.
5. Open a linked statement. `/market-lab/sources/<document UUID>?row=<index>#point-<index>` opens its immutable stored document at that observation. Another workspace cannot read it.

## What changed

Paths below are relative to the repository root.

- `agents/market_lab/core/jobs.py:39` collects all 14 copyable feeds, preserves batch checks, and saves immutable source documents and per-feed results. `agents/market_lab/feeds/fetch.py` supports history, notice pagination and published table downloads.
- `agents/market_lab/schema.sql:137` adds idempotent, tenant-owned `feed_documents` and `feed_checks`. `agents/market_lab/core/evidence.py:105` computes On from the latest collection; `:126` answers deterministically with citations. Production reads exclude fixtures and answers exclude withdrawn batches.
- `agents/market_lab/feeds/collect.py:40` keeps publisher boundaries and download fingerprints, strips URL queries from stored provenance, and permits public pages without a robots gate. `agents/market_lab/feeds/live.py:82` uses one truthful Tervory user agent, a two-second per-host delay, and stops a host on access blocks, captchas or login/paywall pages. No retries or alternate paths after a block.
- `agents/market_lab/core/http.py:22` and `tank/market_lab_routes.py:18` provide authenticated, tenant-scoped overview, refresh, question and document operations. The previously approved `tank/main.py` registration and `tank/Dockerfile` entry are unchanged from `73be8e6`.
- `workspace/lib/tank.ts:1032` adds only the Market Lab server helper. `workspace/app/market-lab/load.ts:12` reads it; `view.tsx:128` asks a question and renders cited facts. The feed-page design is retained.
- `workspace/app/market-lab/source-view.tsx:4` shares the source renderer between the signed-in route and local proof. Long attribution URLs wrap and the table remains readable on mobile.
- `agents/market_lab/fixture_proof/run.py:25` mounts the actual page components in an isolated temporary Next app. `server.py:51` uses the real Tank proxy, evidence readers and local Postgres. `capture.mjs` checks each citation and captures both viewport widths. These tools are excluded from the deployed room image.

**Decisions I made**

- Use code to write the brief from stored rows. The new Ask flow makes no model call and adds no paid service, vendor or key.
- Retain immutable normalized observations and source fingerprints; these are extracted source records, not replicas of the publisher's file layout. Citation URLs survive later refreshes.
- Count feeds with observations retained by the last successful collection, including unchanged observations fetched again. A failed collection clears On without deleting earlier documents. Linked-only sources, including FRED, cannot support a stored-source brief.
- Follow the founder's public-pages rule: read only needed public data, identify truthfully, pace requests, and stop at access boundaries. A block records `blocked` and stops further requests to that host during the run. Missing named keys remain off.
- Keep fixture records marked `fixture = true`. The fixture selector is internal to the isolated proof; production route bodies do not accept it. No production authentication was changed. The proof uses a loopback database ending in `_test`, an ephemeral internal key and a fixed local fixture tenant.
- Reuse the existing room job and tenant lock for refresh. Add `/market-lab/ask` within this lane; the page no longer calls the older `/api/market-lab/chat` route.
- Keep the single PR draft and report local tests. No CI retry, production action or sign-in attempt is part of this proof.

## How it was tested

From the repository root, Python 3.12 with the existing feed requirements installed:

```bash
PYTHONPATH=tank /workspace/.venvs/rig/bin/python -m pytest -q tests/test_market*.py tests/test_feeds*.py
```

**144 passed, 1 skipped.** The optional Postgres test is run separately below. The suite includes every copyable feed, missing keys, tenant isolation, immutable citations, withdrawn observations, date/geography constraints, public-page reading, block stopping, truthful identity, pagination and the Tank proxy. It includes the 12 TypeScript model tests through the existing test loader. No public-network access is needed. Five existing FastAPI startup deprecation warnings remain.

```bash
DATABASE_URL=postgresql://postgres@127.0.0.1:54329/market_lab_test PYTHONPATH=tank /workspace/.venvs/rig/bin/python -m pytest -q tests/test_market_lab_postgres.py
```

**1 passed.** A local test database only: schema applied twice, all 14 fixture feeds stored, answers read back, another tenant denied, production readers excluded fixtures, and earlier source documents preserved. Test writes roll back.

```bash
node --experimental-strip-types --import ./tests/market_lab_register.mjs --test workspace/app/market-lab/model.test.ts
```

**12 passed, 0 failed** (also covered by pytest).

```bash
cd workspace
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy npx next build
```

**Passed:** compilation, type checking and all 35 static pages generated. Dependencies were installed with the brief's `npm install --no-package-lock --no-audit --no-fund`. The dummy values above are for build validation only; no sign-in was attempted.

**Reproduce the local page proof**

With Workspace dependencies, Python feed requirements plus asyncpg/FastAPI/uvicorn, a local empty Postgres test database, Chromium and an installed Playwright module, start:

```bash
DATABASE_URL=postgresql://postgres@127.0.0.1:54329/market_lab_test /workspace/.venvs/rig/bin/python agents/market_lab/fixture_proof/run.py
```

Open `http://127.0.0.1:3046/market-lab`. In a second cloud terminal:

```bash
node agents/market_lab/fixture_proof/capture.mjs --playwright /workspace/tervory-rig/node_modules/@playwright/test/index.js
```

The module path above reuses an already-installed cloud dependency; another installed Playwright path can be supplied. `--browser` accepts another local Chromium executable. No changes to that repository are needed.

Output: **Local fixture page: 8 screenshots, 2 exact citations, no external browser requests or errors.** The browser rejects nonlocal requests. The local API seeds all fixtures into Postgres, then the page uses the production server-side helper and Tank proxy to read them. Stop the runner with Ctrl-C; it stops its two local services. Saved fixture rows remain in the local test database.

## Proof

All images are **local, fixture page**, at 375px and 1440px. They are not live or signed-in screenshots.

| Step | 375px | 1440px |
| --- | --- | --- |
| Feeds with 14 stored feeds On | [Feed page](evidence/feeds-375.png) | [Feed page](evidence/feeds-1440.png) |
| Entered question | [Question](evidence/question-375.png) | [Question](evidence/question-1440.png) |
| Brief with every number linked | [Brief](evidence/brief-375.png) | [Brief](evidence/brief-1440.png) |
| Stored source opened at cited row | [Source](evidence/source-375.png) | [Source](evidence/source-1440.png) |

[Browser receipt](evidence/browser-proof.json) records the question, both exact citation links, stored row cells, viewports, filenames and empty error/external-request lists. It asserts that removing the citation links leaves no number in the answer. Every citation opens and its title, date, value and unit match the rendered stored row.

Local fixture tenant: `00000000-0000-0000-0000-000000000905`.
Stored document: `d753f1e5-d187-45f8-9997-f4b3b99639ff`, source `census_population`, zero-based rows 1 and 4.
The fixture values (110 and 50 persons) are deliberately small saved test inputs, not population claims. They exist in `agent_market_lab.feed_documents.content` in local Postgres with `fixture = true`.

## Founder must decide

No new decision, service or credential is needed for this draft. Live source availability and the real signed-in journey remain assigned to Grok and Claude respectively.

**Grok's one-command live collection**

Inside the Market Lab room with its existing environment bindings:

```bash
python -m feeds run --engine ffl --tenant '<the signed-in workspace tenant UUID>' --live --backfill
```

Use the UUID derived by `workspace/lib/tenant.ts` for that Clerk organization, not the platform UUID. The command reads the existing database and named feed keys from its environment; do not pass secret values as arguments. Outside the room, run from the repository root with `PYTHONPATH=agents/market_lab` and the same environment bindings.

The report contains source status, row counts and document identifiers. Missing keys are skipped. Copyable-feed errors, blocks, or a run with no copyable observations return exit code 1; other hosts continue and each finished feed is committed. Backfill can take hours with per-host pacing. Existing source windows include configured listing history, Census population from 2009, trade from January 2013, NCEI from 2016, notice pages/version dates and published history files. These live endpoints have not been verified by this local fixture proof.

After the founder deploys, Claude verifies `/market-lab` in the founder's signed-in browser: refresh, ask a question, and open `/market-lab/sources/<UUID>?row=<index>#point-<index>`. `POST /v1/market-lab/overview` must match the page's On count and that tenant's latest `agent_market_lab.feed_checks` rows. Check `agent_market_lab.feed_documents` with `fixture = false`: the document's tenant, date, value and unit must match each linked statement. Switching workspace must deny access to the same document.
