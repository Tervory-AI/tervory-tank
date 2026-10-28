# PR #410 — authoritative memory records and review fixes

The founder's explicit `Remember that <fact>` instruction now returns the stored
claim and its UUID in the existing chat answer. Opening
`/api/memory/records/<id>` returns the saved row through Workspace → Tank → Hermes.
All three checks require the existing founder identity. Clients and reviewers
cannot use the lookup. Unknown IDs return 404. No page, label or button was added.

Publication now refuses empty or unreviewed identity inventories and keeps the
policy OFF, including previously enabled invalid policies. Claims exceeding the
encoder's 512-token context are refused before SQL writes, using the existing 422
validation-detail array. The worker records `embed_failed` after five failed
upsert attempts and preserves that terminal job across replay, restart and scans.

Branch: `codex/d2-agent-memory-records`. Continued existing PR #410; no new branch
or PR was created. Main `241d802` was merged in commit `4b9d0b0`, preserving both
memory and Skala changes. No production SQL, deployment, model inference, paid
request, GitHub API call, or live client-data change was made. The founder merges.
**Live acceptance and founder screenshots are pending. Offline checks are not the
founder's acceptance.**

## Review fixes: file and line

| File and line | Change / proof |
| --- | --- |
| `hermes/records.py:90`, `:190` | Validate before saving; founder-only caller can inspect an ID across configured schemas, returning exactly the ten requested fields. An ambiguous ID across schemas is refused with 409. Ordinary tenant reads are unchanged. |
| `hermes/records.py:272`, `:314`, `:353` | Five attempts per row and encoder pin; terminal `memory_index_jobs.last_error='embed_failed'` remains durable so unchanged replay cannot reset the budget. A new pin can index again. Deletion tombstones continue retrying to remove vectors. |
| `hermes/record_routes.py:18`, `:115`, `:150` | Existing validation shape, founder-authenticated ID lookup, and 422 for overlong founder claims. Response fields: id, tenant_id, agent, claim, evidence, confidence, last_verified, embed_model, created_at, updated_at. |
| `hermes/service.py:24`, `:157` | Agent `/memories` writes use the same token validation and 422 shape for `body.text`. |
| `tank/memory_routes.py:42`, `:63`, `:70`, `:140` | Preserve upstream validation details; new GET uses `require_reviewer`, then `actor.founder`, otherwise 404. Old routes retain `require_admin`. Chat returns the claim, a blank line, and the raw UUID as data, with its existing zero-cost ledger row. |
| `workspace/lib/tank.ts:7` | Server-only fixed GET to Tank using existing credentials and trusted identity headers; no-store, no redirects. |
| `workspace/app/api/memory/records/[id]/route.ts:1` | New JSON route uses existing `goldIdentity("platform")`, explicitly requires role founder, validates UUID, and returns private/no-store JSON. Error responses add no wording. |
| `hermes/deidentify.py:44`, `:76` | Reuse inventory validation for publication and redaction. Review must be true; lists must be valid and contain at least one identity across the inventory. An empty tenant inventory is not made nonempty by the tenant UUID. |
| `hermes/publishing.py:13`, `:52` | Invalid enable attempts commit OFF before returning 422. Publishing rechecks saved inventories, revokes invalid legacy policy and records the refusal in the existing audit transaction. |
| `tank/semantic_encoder.py:22`, `:34`, `:45` | Shared pinned tokenizer validation, including subwords and special tokens, with truncation disabled. Validation loads no model. Embedding reuses the same check. Missing/wrong pin fails closed. |
| `tests/test_agent_memory_records.py:45`, `:547`, `:576` | Update stub contract and prove chat ID → founder Tank GET → Hermes → actual PostgreSQL row. |
| `tests/agent_memory/test_review.py:26`, `:80`, `:113`, `:144`, `:200` | Exact fields/404/auth/collision; existing Hermes credential plumbing; empty or unreviewed policy refusal; real tokenizer 512/513 boundary; terminal failures and deletion retries. |
| `tests/agent_memory/test_chat.py:22` | Full existing command SSE endpoint, real test SQL message/task/ledger, matching ID in streamed and saved answer, zero-cost receipt, founder inspection and two-client denial. Model route fails the test if called. |
| `tests/agent_memory/workspace.cjs:1` | Execute actual route, goldIdentity, founder/reviewer checks and Tank helper with offline Clerk/fetch stubs. Two clients, reviewer and forged headers refused; fixed GET, no-store, UUID validation and empty failure bodies checked. |
| `tests/agent_memory/proof-row.json:1` | Fresh, explicitly offline SQL row with returned ID, chat payload, browser path and PostgreSQL version. This is not a live screenshot. |
| `tests/agent_memory/PR.md:1` | Updated description, whole-PR file/line manifest, commands/results and founder acceptance steps. |
| `tank/main.py:4196`, `:4200`; `tank/schema.sql:2101`, `:2152` | Merge conflict resolution keeps the memory router and main's Skala revalidation installer/outbox/trigger. Generated memory DDL remains at EOF as its generator requires. |

The original PR's SQL-first design remains: records and durable index jobs commit
before inference/vector writes, vectors contain IDs and indexing metadata,
recall hydrates scoped SQL, platform publication requires explicit founder opt-in,
and legacy vector collections are not migrated. The original additive generated
schemas, room memory client, same-box runtime and read-only Zenas law reference
remain part of this PR; the complete changed-file manifest follows below.

## Exact commands and observed results

All commands ran in the cloud checkout `/workspace/tervory-tank`, except TypeScript
which ran with working directory `/workspace/tervory-tank/workspace`. All database
URLs below point to disposable loopback PostgreSQL, with trust authentication and
no secret. No production connection was used.

### Continue and merge

```sh
git fetch origin && git checkout codex/d2-agent-memory-records && git merge origin/main
```

Fetch/checkout succeeded. Merge exited 1 with conflicts in `tank/main.py` and
`tank/schema.sql`. Both sides were retained as authorized. Existing named files
were checked; the new Workspace route was created as requested by the corrected
rule 13. The merge checks below passed before:

```sh
git diff --cached --check
git commit -m "Merge origin/main preserving memory records and Skala lifecycle additions"
git push origin HEAD
git ls-remote origin refs/heads/codex/d2-agent-memory-records
```

Commit `4b9d0b0086136e94188c9485854bc930b5de5e36`; remote branch confirmed that hash.
No push failed. All subsequent finished files were separately committed/pushed,
as recorded in the commit-command section below.

### Offline dependencies and PostgreSQL

```sh
uv --cache-dir /tmp/pr410-uv-cache pip install --python /tmp/command-repo-venv/bin/python qdrant-client==1.20.0
uv --cache-dir /tmp/pr410-uv-cache pip install --python /tmp/command-repo-venv/bin/python 'tokenizers>=0.15,<1.0'
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock run -d --rm --name pr410-postgres -p 127.0.0.1:55443:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16.15
```

Dependency installation and container startup succeeded. Qdrant 1.20.0 ran in
memory; tokenizer 0.23.3 loaded only a local test WordPiece fixture. PostgreSQL
16.15 ran natively in Docker. No weights were downloaded or evaluated. The
production tokenizer file remains the existing pinned encoder artifact; the
tokenizer test verifies the code path and boundary, not embedding quality.

### Merge validation

```sh
MEMORY_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/postgres SKALA_B3_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/postgres /tmp/command-repo-venv/bin/python -m pytest tests/test_agent_memory_records.py tests/skala_b3_b4/test_lifecycle.py tests/test_tank_health.py tests/test_tank_boots.py -q --disable-warnings
```

Result: **55 passed, 14 warnings in 13.89s**, no skips. An initial collection attempt
failed because qdrant-client was absent; it was installed before the successful
run. A preliminary run without `SKALA_B3_TEST_DATABASE_URL` had 41 passed/14 skipped;
the command above exercised those SQL cases too. Tank boot checks launch actual
`uvicorn main:app`, require startup completion and HTTP 200 `/health`, then repeat
on the same disposable database to check schema reapplication.

### Memory checks while implementing

```sh
MEMORY_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/postgres MEMORY_PROOF_PATH=/tmp/pr410-proof-row.json /tmp/command-repo-venv/bin/python -m pytest tests/test_agent_memory_records.py -q --disable-warnings > /tmp/pr410-record-tests.txt 2>&1
MEMORY_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/postgres /tmp/command-repo-venv/bin/python -m pytest tests/agent_memory/test_review.py -q --disable-warnings > /tmp/pr410-review-tests.txt 2>&1
node tests/agent_memory/workspace.cjs > /tmp/pr410-workspace-tests.txt 2>&1
```

Results: **24 passed, 1 warning in 3.55s**; **9 passed in 2.92s**; Node exit 0:

```text
PASS: founder-only memory JSON, two-client/reviewer refusal, trusted identity, fixed GET path, no-store, empty error bodies.
```

The first review-test run was 1 failed/8 passed: the test expected old admin denial
403, but the existing gate correctly returns 404. Corrected the assertion; no auth
behavior was changed for that failure. Ruff also caught an unused import and
fixture import shadowing in the new test file; both were corrected before push.

### Regression checks and corrected failure

```sh
MEMORY_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/postgres /tmp/command-repo-venv/bin/python -m pytest tests/test_agent_memory_records.py tests/agent_memory/test_review.py tests/test_hermes_memory.py tests/test_agent_roles.py tests/test_secrets.py tests/test_tank_one_door.py tests/test_tank_semantic_cache.py -q --disable-warnings > /tmp/pr410-regression-tests.txt 2>&1
```

Initial result: 1 failed, 81 passed, 27 skipped. The secret scanner rejected the
label used for a synthetic offline credential in the JS test. Changed that
fixture to the repository-recognized `dummy-offline` placeholder. No actual
credential was present. The skips were semantic-cache SQL cases lacking their
fixture environment; the final run below includes the database and has no skips.

```sh
node tests/agent_memory/workspace.cjs
/tmp/command-repo-venv/bin/python -m pytest tests/test_secrets.py -q --disable-warnings > /tmp/pr410-secret-tests.txt 2>&1
```

Results: Node PASS; **2 passed in 7.45s**.

### Final regression and chat acceptance checks

```sh
MEMORY_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/postgres MEMORY_PROOF_PATH=/tmp/pr410-proof-row.json /tmp/command-repo-venv/bin/python -m pytest tests/test_agent_memory_records.py tests/agent_memory/test_review.py tests/test_hermes_memory.py tests/test_agent_roles.py tests/test_secrets.py tests/test_tank_one_door.py tests/test_tank_semantic_cache.py tests/test_command.py tests/test_tank_health.py tests/test_tank_boots.py -q --disable-warnings > /tmp/pr410-final-tests.txt 2>&1
MEMORY_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/postgres /tmp/command-repo-venv/bin/python -m pytest tests/agent_memory/test_chat.py -q --disable-warnings > /tmp/pr410-chat-tests.txt 2>&1
```

```text
194 passed, 12 warnings in 81.22s (0:01:21)
1 passed, 1 warning in 3.96s
```

No skips or failures. The additional chat test exercises SSE, saved message,
real test ledger and inspection together, with no model calls. The broader run
covers existing command receipts/actions, tenant isolation, semantic cache,
Hermes legacy behavior, agent roles, secret/model boundaries and real Tank boot.

### Static checks, artifact and cleanup

Working directory `workspace`:

```sh
./node_modules/.bin/tsc --noEmit --incremental false > /tmp/pr410-tsc.txt 2>&1
```

Exit 0; no diagnostics. Python checks from repository root:

```sh
/tmp/command-repo-venv/bin/python -m py_compile tank/semantic_encoder.py
/tmp/command-repo-venv/bin/python -m py_compile hermes/records.py
/tmp/command-repo-venv/bin/python -m py_compile hermes/record_routes.py
/tmp/command-repo-venv/bin/python -m py_compile hermes/service.py
/tmp/command-repo-venv/bin/python -m py_compile tank/memory_routes.py
/tmp/command-repo-venv/bin/python -m py_compile hermes/deidentify.py
/tmp/command-repo-venv/bin/python -m py_compile hermes/publishing.py
/tmp/command-repo-venv/bin/python -m ruff check tests/agent_memory/test_review.py --select E9,F
/tmp/command-repo-venv/bin/python -m ruff check hermes/records.py hermes/record_routes.py hermes/service.py hermes/deidentify.py hermes/publishing.py tank/semantic_encoder.py tank/memory_routes.py tests/test_agent_memory_records.py tests/agent_memory/test_review.py --select E9,F
/tmp/command-repo-venv/bin/python -m ruff check tests/agent_memory/test_chat.py --select E9,F
cp /tmp/pr410-proof-row.json tests/agent_memory/proof-row.json
/tmp/command-repo-venv/bin/python -m json.tool tests/agent_memory/proof-row.json > /dev/null
git diff --check
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock stop pr410-postgres
```

All final checks exit 0; Ruff: `All checks passed!`; cleanup: `pr410-postgres`.
Each Python production file was compiled before its individual commit, and
`git diff --check` preceded each commit. The full Next production build and live
browser acceptance were not run; TypeScript and the actual route contract passed.
The original task's earlier test history is in previous versions of this PR file;
results here describe the merged branch and current fixes.

## Limits and founder evidence

No screenshot is claimed or supplied by the builder. The founder supplies the
chat answer and JSON-row screenshots after deployment. The offline row is an
isolated fixture only and must not be presented on a live client page. The
inventory must still cover the client's real identities; nonempty and reviewed
is a necessary gate, not proof that arbitrary prose contains no unknown name.
Client publication stays OFF until the founder deliberately enables it.

No new settings or credential values are required by these review fixes. The
existing Workspace/Tank/Hermes credential and founder allowlist are reused. No
change was made to the main branch or to a live database.

## Whole-PR file and line manifest

Compared with merged main `241d802`; line numbers are the starts of changed hunks.
Earlier PR files below are retained, not rebuilt by this review fix.

| File | Changed line starts |
| --- | --- |
| `.env.example` | 147 |
| `agents/_chassis/chassis/memory.py` | 32, 42, 57, 59, 62, 78 |
| `agents/_template/schema.sql` | 1 |
| `agents/base/schema.sql` | 1 |
| `agents/ghost/schema.sql` | 1 |
| `agents/market_lab/schema.sql` | 195 |
| `agents/radix/schema.sql` | 26 |
| `agents/rig/schema.sql` | 354 |
| `agents/tiger/schema.sql` | 1 |
| `agents/tisan/schema.sql` | 1 |
| `agents/trigger/schema.sql` | 22 |
| `agents/zenas/schema.sql` | 553 |
| `docker-compose.yml` | 75, 80, 97 |
| `docker-compose.za.yml` | 68, 73, 83 |
| `hermes/Dockerfile` | 8, 16, 22 |
| `hermes/deidentify.py` | 1 |
| `hermes/publishing.py` | 1 |
| `hermes/qdrant_store.py` | 129, 136 |
| `hermes/record_index.py` | 1 |
| `hermes/record_routes.py` | 1 |
| `hermes/record_runtime.py` | 1 |
| `hermes/record_schema.py` | 1 |
| `hermes/records.py` | 1 |
| `hermes/references.py` | 1 |
| `hermes/requirements.txt` | 10 |
| `hermes/runtime.py` | 4, 5, 7, 12, 18, 29, 33 |
| `hermes/service.py` | 1, 3, 16, 24, 35, 42, 55, 62, 64, 69, 78, 91, 137, 150, 191, 224, 227, 254, 272 |
| `hermes/store.py` | 88, 144, 149 |
| `tank/command.py` | 385 |
| `tank/main.py` | 4196 |
| `tank/memory_routes.py` | 1 |
| `tank/schema.sql` | 2099, 2150 |
| `tank/semantic_encoder.py` | 22, 45, 49, 54 |
| `tests/agent_memory/PR.md` | 1 |
| `tests/agent_memory/proof-row.json` | 1 |
| `tests/agent_memory/test_chat.py` | 1 |
| `tests/agent_memory/test_review.py` | 1 |
| `tests/agent_memory/workspace.cjs` | 1 |
| `tests/test_agent_memory_records.py` | 1 |
| `tests/test_hermes_memory.py` | 413, 443, 466 |
| `tests/zenas_za_meaning_search/test_hermes_law.py` | 119 |
| `workspace/app/api/memory/records/[id]/route.ts` | 1 |
| `workspace/lib/tank.ts` | 7 |

## Per-file commit and push commands

Each listed command sequence succeeded and pushed only the existing branch.
Commit subjects and files are taken from git history after merge `4b9d0b0`.

```sh
# Result: 2b08e90; commit and push succeeded
git add tank/semantic_encoder.py
git commit -m 'Validate memory input with the pinned encoder tokenizer without inference'
git push origin HEAD
# Result: ad84cec; commit and push succeeded
git add hermes/records.py
git commit -m 'Add founder record lookup and cap unchanged embedding jobs at five failures'
git push origin HEAD
# Result: 1765952; commit and push succeeded
git add hermes/record_routes.py
git commit -m 'Expose founder memory rows by ID and reject oversized claims with validation errors'
git push origin HEAD
# Result: 3c1ed80; commit and push succeeded
git add hermes/service.py
git commit -m 'Apply tokenizer validation errors to agent memory writes'
git push origin HEAD
# Result: 6815570; commit and push succeeded
git add tank/memory_routes.py
git commit -m 'Add founder-authenticated Tank record lookup and include memory ID in chat data'
git push origin HEAD
# Result: 30f8f71; commit and push succeeded
git add workspace/lib/tank.ts
git commit -m 'Route founder memory inspection through the existing server-side Tank helper'
git push origin HEAD
# Result: fbc8112; commit and push succeeded
git add 'workspace/app/api/memory/records/[id]/route.ts'
git commit -m 'Add founder-only browser JSON route for a saved memory ID'
git push origin HEAD
# Result: 6d15193; commit and push succeeded
git add hermes/deidentify.py
git commit -m 'Require a nonempty reviewed identity inventory before publication redaction'
git push origin HEAD
# Result: d83f4bb; commit and push succeeded
git add hermes/publishing.py
git commit -m 'Keep invalid publication policies off and refuse legacy empty inventories'
git push origin HEAD
# Result: ff7d11e; commit and push succeeded
git add tests/test_agent_memory_records.py
git commit -m 'Prove founder chat returns an ID that reads back through Tank and Hermes'
git push origin HEAD
# Result: 4a897fc; commit and push succeeded
git add tests/agent_memory/test_review.py
git commit -m 'Cover founder-only memory lookup, empty inventory refusal, token limits and terminal retries'
git push origin HEAD
# Result: 2c40ecb; commit and push succeeded
git add tests/agent_memory/workspace.cjs
git commit -m 'Verify the browser memory route and existing founder identity plumbing offline'
git push origin HEAD
# Result: b3a291c; commit and push succeeded
git add tests/agent_memory/workspace.cjs
git commit -m 'Use the repository-recognized dummy credential in the offline Workspace test'
git push origin HEAD
# Result: 1efc578; commit and push succeeded
git add tests/agent_memory/test_chat.py
git commit -m 'Prove the chat SSE response persists the memory ID and actual zero-cost receipt'
git push origin HEAD
# Result: 8b46576; commit and push succeeded
git add tests/agent_memory/proof-row.json
git commit -m 'Refresh offline memory proof with the returned ID and founder JSON readback'
git push origin HEAD
git diff --check
git add tests/agent_memory/PR.md
git commit -m 'Document PR 410 review fixes, exact checks and founder acceptance'
git push origin HEAD
```

## Founder browser acceptance — still required

1. After the founder merges and the deployment completes, open
   **https://app.tervory.com/chats** using the founder's existing session.
2. In the existing chat composer, type `Remember that ` followed by one real fact
   the founder wants stored, then use the existing send control. The answer must
   show that fact and its UUID, with the existing receipt. No fixture fact is
   prescribed for a live screen.
3. Copy that UUID and open
   **https://app.tervory.com/api/memory/records/<id>**, replacing `<id>` with it.
   Verify the JSON has the same id and claim, the correct tenant and agent, and
   all ten specified fields.
4. Add screenshots of the actual chat answer/receipt and JSON row to PR #410.
   This browser proof is pending; the builder has not claimed the job done.
