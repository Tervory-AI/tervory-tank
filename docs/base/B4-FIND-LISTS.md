# Base B4 — PR #594 review proof

Branch: `codex/base-b4-find-lists`. PR: https://github.com/Tervory-AI/tervory-tank/pull/594.
The founder merges. No deployment, production SQL, live CRM writes or model calls were performed here.

## Final implementation and review fixes

- `tank/base_lists.py:15`: tenant-only typed filters over verified contact evidence, B1 quality, B2 site signals, reference identity and final verification tier. Unknown quality never satisfies a negative-quality filter.
- `tank/base_lists.py:132`: one literal, parameterized SQL cursor query pushes state, city, licence type, engine/category and checked-date prefilters into WHERE, using the same profile/reference paths as `project()`. SQL conservatively includes candidate sources; the existing Python verification/precedence checks remain authoritative. Non-ASCII values stay conservative to preserve Python casefold semantics. Read batches are bounded by `prefetch=200`.
- `tank/base_lists.py:175`: find retains the exact total and only 20 preview rows, not all tenant records.
- `tank/base_lists.py:184`: save scans a stable repeatable-read transaction, keeps at most 10,000 IDs and an exact total, and refuses larger lists with HTTP 422 and `detail.total` before inserting anything. Accepted snapshots stream in 200-row chunks to the existing saved-list JSON; the process never holds the whole snapshot. Both cursor passes see the same database snapshot. The existing `tenant_transaction` helper supplies that snapshot for both native asyncpg and production TenantPool connections; a regression verifies there is one correctly isolated transaction rather than an incompatible nested transaction.
- `tank/command.py` (`list_refusal_result`): the existing failed card retains only the safe integer total for this specific oversized-save refusal. Its existing error text and existing Total label are reused; no new page wording.
- `tank/base_lists.py` (`to_crm`): selected records are sent in saved-list order. Pool/tenant-lock acquisition is bounded to 30 seconds; queue expiry returns one failed result per selected record without sending anything.
- `tank/base_list_crm.py:8`: fixed concurrency 5, 45-second whole-operation write deadlines, 60-second duplicate discovery deadline, no ambiguous-write retries. Identities are reserved in list order before concurrent work, preventing within-card duplicate races. Results retain input/list order regardless of completion order.
- `tank/command.py:888`: the CRM card limit is **1,020 seconds (17 minutes)**: 60 seconds discovery + 20 waves × 45 seconds + 60 seconds margin. The margin includes the 30-second pool/tenant-lock wait and 30 seconds for cleanup/receipt handling. The former 4,200-second limit is removed.
- `workspace/app/base/download/route.ts:15`: forwards success status and unchanged CSV bytes. For 403/404/500 errors it forwards the upstream status/body and content type without CSV attachment headers.
- `workspace/lib/tank.ts:1218`: an explicit server-only `passThroughErrors` option preserves Tank responses for that fixed saved-list download path. Existing callers keep their existing sanitized error behavior.
- `tank/schema.sql`: saved lists follow the `personal_tokens` conditional RLS rollout, including FORCE RLS and a restrictive tenant boundary. Every saved-list read/write also has an explicit tenant predicate. No startup/runtime configuration changed. `_startup` and the router-before-tenant-binder registration order were checked.
- `tank/base_list_crm.py`: only verified company, website, phone, email, city and state are sent through the existing bound CRM corridor. The description records each sent value's original URL and date. Existing email/website duplicates are skipped, and missing binding sends nothing, reusing existing wording.

The existing Base CSV serializer and columns are unchanged. Base pages are unchanged; `/chats` reuses existing cards. Their existing first-five-item visual preview remains unchanged; structured find results contain the first 20 records.

## 50,000 synthetic records: measured local PostgreSQL test

Command (repo root):

```sh
PYTHONPATH=tank:tests:. .venv/bin/python tests/base_lists_scale.py
```

Exit 0. The script creates and deletes its own private local PostgreSQL cluster under this checkout's `.git/`, inserts **50,000 synthetic records**, and runs the actual SQL cursor, SQL prefilters and Python projection/verification. It uses no outside network, live tenant or credentials. State/city/licence/date filters all match this worst-case dataset, so all 50,000 candidates are scanned.

| Operation | Time | Peak traced Python allocation | Peak client RSS |
| --- | ---: | ---: | ---: |
| Find: exact total 50,000, 20 previews | 63.383 s | 1.140 MiB | 92.703 MiB |
| Save refused: exact total 50,000, no insertion | 46.652 s | 2.121 MiB | 93.762 MiB |

Times include `tracemalloc` instrumentation. RSS is the Python client process's absolute high-water mark (including imports), not the separate PostgreSQL server's memory. The test asserts the count, 20-row result bound and oversized-save refusal. An earlier traced run measured 51.360 s / 1.131 MiB for find and 44.594 s / 2.121 MiB for refusal; the table uses the final RSS-instrumented run, rather than selecting the faster run.

`test_fifty_thousand_matches_keep_twenty_previews_and_refuse_save` also gates 50,000-match aggregation/cap behavior in the normal offline suite with a generated cursor stream. It asserts that no list was inserted.

## Exact regression commands and results

Working directory `/workspace/codex-base-b4` unless specified.

```sh
.venv/bin/python -m pytest -q -ra tests/test_base_* tests/test_command.py tests/test_trigger_crm.py tests/test_skills_offline.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

**406 passed, 101 skipped, 15 warnings in 74.75 seconds; exit 0.** Includes every existing Base test, the Command/CRM tests and all offline skill evals. The 101 skips require explicit local Postgres fixtures (`BASE_TEST_DATABASE_URL` / `POOL_SCHEMA_DATABASE_URL`), not production settings. Their existing per-module breakdown is 10 ATF, 14 audit, 6 Base database, 1 new saved-list RLS test, 14 reference adoption, 7 reference file, 3 source reliability and 46 Command tests. Warnings are existing framework/Pydantic warnings. CI's isolated Postgres jobs provide the remaining integration coverage; use the current PR checks, not this local skip result, as CI proof.

```sh
node tests/base_lists_download.cjs
cd workspace && npx tsc --noEmit
.venv/bin/ruff check tank/base_lists.py tank/base_list_crm.py tests/base_lists_scale.py tests/test_base_lists.py
git diff --check
```

Each exits 0 (the TypeScript command runs from repo root; subsequent commands run from repo root again). Download tests verify byte equality, tenant identity forwarding, original batch redirect, and unmodified upstream 403/404/500 bodies/statuses without CSV headers. Concurrency tests reach exactly 5 active writes, preserve ordered results and assert the 1,020-second budget. Refusal tests retain the count while rejecting arbitrary failed-provider details. No new interface labels or error wording are introduced.

## SQL / Semgrep proof

All SQL newly introduced by B4/review is a **literal string**. Runtime tenant IDs, filter strings/dates, ID arrays and JSON snapshots are passed separately as `$1`…`$7` parameters. There is no interpolated table name, SQL f-string, concatenated request value or generated WHERE clause.

`test_new_sql_is_literal_with_bound_runtime_arguments` walks the AST of the production list module, PostgreSQL benchmark and B4 tests. It requires SQL call arguments to be string constants and runtime arguments to have `$1` binding. The only excluded call is the pre-existing fixture bootstrap reading the fixed repository `tank/schema.sql`, not newly generated SQL. Fixture roles now use static literal identifiers instead of f-strings. Static setup DDL has no runtime values to bind.

The PR body records final CI links/status after the final push, including the security job that runs Semgrep. No claim is based on canceled or superseded-head runs.

## Founder / Figma acceptance

**Base page: find, lists and send to CRM — awaiting an approved Figma frame.** No Base page view was built.

**Founder-browser screenshots remain pending.** This review work did not create live leads or place synthetic fixtures on a live screen. Product acceptance still requires the founder, in `/chats`, to find DC dealers with verified websites and syntax-valid non-disposable emails, save/download the list, confirm 10 selected records into the bound CRM, and see the leads at crm.tervory.com. Passing tests and CI do not substitute for that browser test.

Every completed file was committed on this same branch, followed by `git fetch origin main`, `git merge --no-edit origin/main`, and `git push -u origin codex/base-b4-find-lists`. All pushes succeeded. No PR merge or main push was performed.
