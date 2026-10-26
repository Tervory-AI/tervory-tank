# Market Lab launch verification

Branch: `codex/market-lab-works`, based on `origin/main` at `65067a4`.
Status: implementation and local checks complete; **live launch proof is pending**.
No PR has been opened. The attached builder rules require a real signed-in job before a PR.

## The job, step by step, as a client does it

1. Sign in, choose a workspace, and open `/market-lab`.
2. Choose **Refresh feeds**. Collection runs for that workspace. The page shows progress and refreshes while collection is queued or running.
3. Check **On**: each counted feed has observations stored by its last collection. Missing credentials say **Off, needs key**. Failed/empty fetches remain off. A linked source is never counted as a stored feed.
4. Ask a question that matches a stored feed, for example “What are the latest population figures for California?” when that feed has rows. No figures are supplied when evidence is absent.
5. Open a linked statement in the brief. `/market-lab/sources/<document UUID>?row=<index>#point-<index>` opens the immutable stored document at that observation. Notices link to their own stored entries. The page includes source downloads and attribution. Another workspace cannot read that document.

## What changed

- `core/jobs.py:39` collects every public feed in the engine's plan, retains existing batch checks, and saves source documents and per-feed results. `engines/ffl/engine.py` separates the 14 copyable feeds from linked-only pages.
- `feeds/collect.py:25` records download fingerprints and strips query strings from stored download URLs. Its HTTP wrapper checks robots policies and publisher boundaries, including redirects. Fixture processing never opens a network connection.
- `feeds/fetch.py` supports history collection, paginated notices, dated regulation snapshots, and published spreadsheet/table downloads. World Bank commodities use the publisher's historical monthly workbook. Existing credentials remain optional; no vendor or key was added.
- `schema.sql` adds tenant-owned `feed_documents` and `feed_checks`. `core/evidence.py` handles stored documents, latest-run status and deterministic cited statements. Fixture documents are excluded from all client reads. Withdrawn batches are excluded from answers.
- `core/http.py` and `tank/market_lab_routes.py` provide authenticated, tenant-scoped overview, refresh, question and document operations. `tank/main.py` adds only the registration; `tank/Dockerfile` adds only the module name to its COPY list.
- `workspace/lib/tank.ts` adds only Market Lab types and a server-side helper. `workspace/app/market-lab/` uses that helper for reads, collection and questions. The existing page design is retained; the additions are off-feed reasons, progress and a paged source document view.

**Decisions I made**

- Use deterministic statements from stored rows; the new Ask flow makes no model call.
- Store immutable normalized source documents with download fingerprints and attribution. They preserve extracted observations, not a claim to reproduce the publisher's original file layout. Historical collection remains in Postgres; citation URLs remain stable after another refresh.
- Keep the existing parser adapters and in-memory parsing store. Only Postgres is authoritative for the application. No Workspace SQLite fallback or direct public-feed fetching remains.
- Count observations retained by the last successful per-feed collection, including unchanged observations fetched again. A failed last collection clears its On status without deleting prior source documents.
- Separate linked-only feeds, including FRED, from copyable feeds. Their numbers cannot support a stored-source brief.
- Keep fixtures explicitly marked and inaccessible to the signed-in client flow. The fixture and mock transport tests below are never launch screenshots.
- Use existing room jobs for refresh, with a tenant lock and a refresh-specific time allowance for polite backfills. No queue-worker or routing-ladder changes.
- Add `/market-lab/ask` within the permitted directory. The old `/api/market-lab/chat` implementation is outside this brief's file ownership and is no longer called by the page.

## How it was tested

From the repository root, using Python 3.12 in `/workspace/.venvs/rig`:

```bash
PIP_CACHE_DIR=/workspace/.cache/pip /workspace/.venvs/rig/bin/python -m pip install -r agents/market_lab/feeds/requirements.txt
PYTHONPATH=tank /workspace/.venvs/rig/bin/python -m pytest -q tests/test_market*.py tests/test_feeds_*.py
```

Result: **129 passed, 1 skipped**. The skipped test is the optional local Postgres check, run separately below. PDF parsing tests ran after installing the existing feed requirements. The suite covers every copyable feed, failed fetches, missing keys, tenant isolation, source citations, immutable snapshots, withdrawn observations, geography/date constraints, robots denial, pagination, and the Tank-to-room path. No test needs public-network access.

A separate local database, `market_lab_test`, uses the existing cloud-only Postgres server on loopback; it contains no production data or credentials:

```bash
DATABASE_URL=postgresql://postgres@127.0.0.1:54329/market_lab_test PYTHONPATH=tank /workspace/.venvs/rig/bin/python -m pytest -q tests/test_market_lab_postgres.py
```

Result: **1 passed**. Applies the schema twice, stores all 14 fixture feeds in actual Postgres, answers from those rows, checks cross-tenant denials and preserves earlier source documents. Test writes roll back.

The CLI fixture round trip also completed against that local database:

```bash
PYTHONPATH=agents/market_lab DATABASE_URL=postgresql://postgres@127.0.0.1:54329/market_lab_test /workspace/.venvs/rig/bin/python -m feeds run --engine ffl --tenant 00000000-0000-0000-0000-000000000001 --fixtures tests/fixtures/feeds --backfill
```

Workspace build:

```bash
cd workspace
npm_config_cache=/workspace/.cache/npm npm install --no-package-lock --no-audit --no-fund
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy npx next build
```

Result: **passed**, including compilation, type checking and route generation. The dummy credentials are build-only. No CI workflow was triggered or retried.

**One-command live collection for Grok**

Inside the Market Lab room, where its existing `DATABASE_URL` and any existing feed credentials are injected, run:

```bash
python -m feeds run --engine ffl --tenant '<the signed-in workspace tenant UUID>' --live --backfill
```

Use the UUID derived by `workspace/lib/tenant.ts` for that Clerk organization; do not use the platform UUID for a client proof. Do not pass the database URL or secret values as CLI arguments. The CLI reads its existing environment. Outside the room, run from the repository root with `PYTHONPATH=agents/market_lab` and the same environment bindings.

The report contains only source status, row counts and document identifiers. Missing keys are off, not fabricated. Read/parse errors in copyable feeds or a run with no copyable observations return exit code 1. Each completed feed is committed, so other feeds continue after an individual failure. Backfill may take hours under the per-host delay. Existing source windows include the configured listing start year, Census population from 2009, trade from January 2013, NCEI from 2016, available notice pages/version dates, and all rows in published history files. Source availability and published formats still need the live check; this document does not claim those endpoints have been verified from this branch.

## Proof

**Pending.** There are no real signed-in screenshots yet.

On this cloud machine, public feed probes returned `URLError: Tunnel connection failed: 403 Forbidden` from the managed network proxy. The environment has no real Clerk session configured. A saved cloud-configuration draft adds the feed hosts and the existing PDF dependency; saving that draft has not applied or published it. Proxy/TLS safeguards were left enabled.

After live access and a real signed-in session are available, capture at 375px and 1440px:

1. The feeds page with actual stored counts and Off reasons.
2. A client-entered question about an On feed.
3. The resulting brief, with each numeric statement linked.
4. One linked statement opened at its exact stored observation.

Also switch workspace and verify the same document cannot be read. Record the tenant UUID, feed check timestamp, document UUID and actual commands/results with the screenshots. Only then open the single draft PR using the five sections in the builder rules.

## Founder must decide

- Apply the saved feed-host network configuration in environment settings and publish the environment, or have Grok run the live command in its already authorized cloud environment.
- Provide an existing authorized signed-in session in the test environment for the screenshots. No authentication bypass or substitute sign-in has been added, and no secret should be pasted into chat.
- Review any feed that still fails after real access is available. Missing listed credentials can remain off; do not add a paid provider to fill a gap.

Runtime proof uses `/market-lab`, a cited `/market-lab/sources/<UUID>` page, and the same tenant's `agent_market_lab.feed_checks` / `agent_market_lab.feed_documents` rows with `fixture = false`. `POST /v1/market-lab/overview` must agree with the page's On count. The source document's tenant, date, value and unit must match the linked statement.
