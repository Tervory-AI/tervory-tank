# Base B4 — find, lists and CRM review handoff

Branch: `codex/base-b4-find-lists`. Claude opens the PR; the founder merges. No main push, deployment, production SQL, live lead creation, provider/model call, or live credential inspection was performed.

## What changed (file and line)

- `tank/base_lists.py:14`: strictly validated find filters for state, city, licence type/category, verified contact presence, B1 quality, B2 passive signals, final verification tier and original checked dates. Unknown quality does not satisfy a negative-quality filter. Uploaded identity is not promoted into verified identity; identity may come from the recorded platform reference and its original source/date.
- `tank/base_lists.py:127`: reads `agent_base.records` with an explicit tenant predicate; completed and partial failed attempts can contribute independently verified evidence. Saved lists store the exact IDs, filters and full evidence snapshots. Later enrichment cannot silently change membership or exported values.
- `tank/base_lists.py:168`: count plus the first 20 rows, retaining field values/source URLs/check dates in the existing generic card result. No new card renderer or interface copy. Existing cards keep their existing first-five-item visual preview; the structured result includes all 20 rows.
- `tank/base_lists.py:180`: authenticated find/list/show/export routes, a $0 Base code receipt, and the existing byte-for-byte `export_records` CSV serializer. Save/send endpoints require the durable, exact Command confirmation binding. CRM sends are limited to at most 100 selected snapshot records and serialized per tenant.
- `tank/base_list_crm.py:23`: builds a lead only from verified values, with source `Base` and a description recording each sent field's URL/date. Requires verified company identity; unverified phone/email/address values are omitted.
- `tank/base_list_crm.py:78`: uses the existing `trigger_crm.binding` and attested fixed-endpoint `upstream` corridor. Checks existing open/closed leads across every page before writes, skips matching email or normalized website, and skips duplicate identities within the card. Incomplete duplicate reads fail closed. Missing binding sends nothing and reuses the existing corridor's wording. Every selected record receives a result; ambiguous writes are not retried.
- `tank/command.py:37` and `:1152`: Base-only tool catalogue and unpaid adapters for `base.find`, `base.list.save`, `base.lists`, `base.list.show`, `base.list.export`, `base.list.to_crm`. Reads use GET. Save/send reuse the existing durable confirmed-card dispatcher; identity remains in authenticated server headers, outside tool arguments. The bounded 100-record CRM action has its own longer timeout; other action limits are unchanged.
- `tank/trigger_crm.py:57`: a Base client may use the corridor only while executing its own confirmed `base.list.to_crm` card. Existing Trigger CRM actions remain founder-only.
- `tank/main.py:4194`: mounts the router before the existing tenant-endpoint binder (`:4711`). `_startup` (`:753`) was inspected before pushing: schema applies through the existing admin/raw bootstrap path, with existing RLS role checks. No startup logic or runtime configuration changed.
- `tank/schema.sql:2337`: additive/idempotent saved-list table. Follows `personal_tokens` exactly: join an existing `command_threads` RLS rollout, enable and force RLS, install tenant access and restrictive boundary policies with matching USING/WITH CHECK. Never starts RLS on a legacy installation.
- `workspace/app/base/download/route.ts:12`: accepts a saved-list ID through the existing authenticated download route and server-only Command corridor. Preserves CSV bytes; batch downloads retain their existing redirect. No Base page render code changed.
- `tests/test_base_lists.py`, `tests/base_lists_download.cjs`: offline filters, verification guards, tenant predicates and ownership, immutable snapshots, byte equality, no-binding behavior, duplicates, 100-record bound, confirmation/authority, receipt/read method and actual Workspace download-route tests. An additional real-Postgres fixture test verifies snapshot persistence plus restrictive tenant RLS; it remains skipped here until the local test service is configured.

## Figma and browser acceptance

**Base page: find, lists and send to CRM — awaiting approved Figma frame.** No Base page view was implemented. `/chats` reuses its existing cards and rendering limits. The tool names in the card summaries are the exact names specified in the brief.

**Founder-browser screenshots are pending, not fabricated.** Offline fixtures were never placed on a live screen. Acceptance still requires the founder's tenant in `/chats`: find DC dealers with a verified website and syntax-valid, non-disposable email; save and download that list; confirm 10 selected snapshot records into the bound BottleCRM organization; see those leads at crm.tervory.com. No browser/CRM acceptance is claimed by these tests.

## Exact commands and results

Working directory: `/workspace/codex-base-b4` unless stated otherwise.

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-base-b4
cd /workspace/codex-base-b4
git fetch origin main
git checkout -B codex/base-b4-find-lists origin/main
ls tank/command.py tank/base_evidence.py workspace/app/base/download/route.ts tank/base_metrics.py tank/trigger_crm.py tank/schema.sql tank/main.py
```

All exited 0; every named existing file was present. Read applicable `AGENTS.md`. Set `user.name=Codex` and `user.email=codex@users.noreply.github.com` in this checkout only.

```sh
/home/ammosync/.local/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -r tank/requirements.txt -r tank/requirements-dev.txt
```

Exit 0. Existing pinned dependencies only; no dependency or lockfile change.

```sh
.venv/bin/python -m pytest -q -ra tests/test_base_* tests/test_command.py tests/test_trigger_crm.py tests/test_skills_offline.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Exit 0: **400 passed, 101 skipped, 15 warnings in 66.66s**. Includes every existing Base test plus Command, existing Trigger CRM and all offline skill evaluations. Warnings concern existing framework deprecations / Pydantic field names. The earlier focused run found two real test-harness mistakes (runtime settings imported unnecessarily; database helper mocked too late); both were fixed. No remaining real test failure is claimed away as a missing service.

```sh
.venv/bin/python -m pytest -q tests/test_base_lists.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
node tests/base_lists_download.cjs
```

The final focused result is recorded below after the Workspace route regression. Node exited 0:

```text
Saved-list CSV bytes preserved; tenant identity forwarded; existing batch download unchanged.
```

The full suite ran before the final additional Workspace wrapper test and preview compaction; the final focused run covers those changes. The server serializer itself is reused and unchanged.

```sh
npm ci --ignore-scripts --no-audit --no-fund
npx tsc --noEmit
```

Run in `/workspace/codex-base-b4/workspace`. Each exited 0; TypeScript emitted no diagnostics. No Workspace package/lockfile change.

```sh
.venv/bin/ruff check tank/base_lists.py tank/base_list_crm.py tests/test_base_lists.py
git diff --check
```

Exit 0; `All checks passed!` and no whitespace errors.

## Local Postgres gaps

All 101 full-run skips explicitly need the isolated local PostgreSQL test service, not a production connection. Configuration names only: `BASE_TEST_DATABASE_URL`; audit/source-reliability also accept `POOL_SCHEMA_DATABASE_URL`; Command uses `POOL_SCHEMA_DATABASE_URL`.

| Module | Skips |
| --- | ---: |
| test_base_atf_download.py | 10 |
| test_base_audit.py | 14 |
| test_base_database.py | 6 |
| test_base_lists.py (new real snapshot/RLS check) | 1 |
| test_base_reference_adopt.py | 14 |
| test_base_reference_file.py | 7 |
| test_base_source_reliability.py | 3 |
| test_command.py | 46 |

CI/PR checks and founder-browser screenshots are not yet observed. Passing these offline tests is not the product's definition of done.

## Push discipline

Every finished file was committed, then `git fetch origin main`, `git merge --no-edit origin/main`, and `git push -u origin codex/base-b4-find-lists`. Every push succeeded. One branch only. No PR was opened because the brief assigns that to Claude.
56 passed, 1 skipped, 3 warnings in 1.97s
