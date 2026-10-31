# COMMAND-1 / CLI-1 acceptance audit — 31 October 2026

Evidence captured 2026-10-31 01:59 PDT / 08:59 UTC. PASS below means the stated offline assertion passed, never founder acceptance. GAP means an unmet requirement in the pinned source; UNVERIFIED means required proof was not executed or supplied. No live model calls, live worker operations, production SQL, ZA operations, UI additions or implementation edits were performed.

## Exact source provenance

- Main baseline: `d8277ded0a698bb103f41a9ca84db5254ae1ecb6`.
- Backend PR465: `894ef4a0a75b1bf02e91626b230c1a6af890a28d`.
- Workspace PR466: `82711d435318546d371adfaac56670e848b0bb57`.
- CLI/PAT PR464: `8ca19a990c707b651a976a5d392eaaadedd35c2d`.
- Acceptance PR467: `6474280b` (test source; this document added afterward).
- Local combined test checkout: `/tmp/tervory-command-assembled-20261031`, detached integration commit `d2f986141b0c4433861036aaaa3a563b7b7d4443`. Clean Git merges of those lane heads; no conflict resolution or implementation edits.
- Broad suite collected before later harness additions, at integration `2c840c0bd23ef7d55ec8721eebc2ce44bf2a6f02`, acceptance source `b67c7a8f`. Later focused run uses acceptance `6474280b` and actual B/CLI modules.

## Every Done when item

| Requirement / specification line | Status | Executed evidence and limitation |
|---|---|---|
| COMMAND CI green, COMMAND-1:55 | UNVERIFIED | PR467 checks pending at audit capture; draft stays draft. Green smoke CI alone does not execute this matrix. |
| Threads persist and stream, :56 | PASS offline | `tests/test_command.py:158`, `tests/test_command_streaming.py:178`; real local SQL and HTTP, fake upstream stream. Saved ownership, partial tokens before finish and durable answer tested. |
| Tool uses Tank and ledger, :57 | PASS offline | `tests/test_command.py:363`, `:444`, `:564`; real native route dispatch within test app, explicit ledger evidence, failure receipt and idempotence. No real provider cost claimed. |
| Approve/paid action waits for Confirm, :58 | PASS offline | `tests/test_command.py:400`, `:425`; `tests/test_command_streaming.py:334`; no dispatch before approval or after cancel, failure/retry barrier. |
| Client cannot see founder tools, :59 | PASS offline | `tests/test_command.py:38`, `:936`; acceptance `test_cross_lane.py:102` authenticates persisted synthetic PAT, ignores forged founder/tenant headers, rejects build, tools empty, revocation enforced. |
| Build reaches workers without issue; PR in thread, :60 | PASS contract / UNVERIFIED real execution | Acceptance `test_cross_lane.py:20` and `:36`: proposal not claimable before Confirm, fake worker claims via HTTP, reports progress and repository PR link. No real worker is launched or investigated. |
| Every turn model/cost/baseline/saved matches ledger, :61–62 | PASS offline / GAP actual Auto comparison | Streaming ledger tests at `test_command_streaming.py:178`, `:212`; command receipts at `test_command.py:612`, `:706`, `:744`. Unknown evidence remains null. Actual Auto comparison ledger provenance is absent; legacy price projections are hidden by `test_command.py:1222` and client bridge. No second model call to manufacture comparison. |
| Panel updates as steps change, :63 | PASS offline | Acceptance `test_cross_lane.py:36`: 504 HTTP worker reports exceed 500-event SQL page; ordered replay drains fully, cursor exhaustion, final durable panel/PR/checks/review match. `consume_replay.cjs:20` consumes same bytes through actual B and CLI decoders. Actual rendered component replay behavior remains B lane's separate browser proof. |
| 375px and 1440px screenshots in PR, :64 | UNVERIFIED | B owner reports offline screenshot work. No founder-browser screenshots supplied to this audit; no fabricated acceptance screenshots. |
| CLI CI green, CLI-1:32 | UNVERIFIED | PR464 checks and independent clearance not verified here. |
| Login stores keychain / never prints token, :33 | UNVERIFIED | Pinned implementation uses OS keyring; pinned head lacks executable CLI test suite. Source inspection is not keychain proof. No real secret used. |
| Chat streams tokens/steps/receipts, :34 | PASS decoder / UNVERIFIED interactive terminal | Actual CLI `events` consumes the real 504-event Tank replay byte-for-byte with B decoder; full interactive chat recording/test pending CLI owner. |
| Confirm card does nothing on N, :35 | UNVERIFIED CLI / PASS server barrier | Backend cancellation proof passes; CLI y/N fake-Tank test not supplied at pinned head. |
| Client token cannot see founder tools, :36 | PASS offline | Persisted PAT hash + actual command HTTP dependency override in acceptance `test_cross_lane.py:102`; client headers cannot escalate, cannot read another user's thread, wrong box refused. |
| Pinned model shows Auto comparison, :37 | GAP | Actual historical Auto ledger comparison not available. Do not substitute price-book projection. Backend pin/ledger proof passes; unavailable comparison stays explicit. |
| Revoked token refused, :38 | PASS offline | Actual local persisted PAT revoked and subsequent command HTTP returns 401, acceptance `test_cross_lane.py:129`; fake-DB PAT unit tests also pass. |
| Terminal recording with receipt, :40 | UNVERIFIED | CLI owner owns recording; no artifact supplied at capture. |
| Founder sees product work in own browser | UNVERIFIED | Required last after build/review. This audit cannot supply founder acceptance. |

## Commands and results

All SQL below targets a new disposable localhost-only PostgreSQL container. Existing test fixture creates and drops a unique database per test. No production database is read or written. Provider HTTP is fake; PAT bearer is deliberately fixed, non-random test data.

```sh
docker run -d --name command-acceptance-pg-20261031 -p 127.0.0.1:55439:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16.15
```

Initial main-only proof:

```sh
PYTHONPATH=tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/postgres /tmp/tervory-rls-python/bin/python -m pytest -q tests/command_acceptance_20261031/test_cross_lane.py
```

Result: **2 passed, 14 warnings, 5.93s** on `b67c7a8f`. A broader baseline run with this reused Python 3.14 environment produced **133 passed, 48 setup errors** in 65.94s because its selectolax 1.x removed `selectolax.parser`. These are setup errors, not passing or product-failure assertions. No application workaround was introduced.

Compatible existing Python 3.12 environment, assembled lane source:

```sh
PYTHONPATH=tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/postgres /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_command.py tests/test_command_streaming.py tests/test_command_repo_tools.py tests/test_personal_tokens.py tests/command_acceptance_20261031/test_cross_lane.py
```

Result: **194 passed, 12 warnings, 98.87s**. Log `/tmp/command-acceptance-assembled-pytest.log`. Acceptance source for that collection was `b67c7a8f` (two tests).

```sh
npm ci --ignore-scripts --no-audit --no-fund --prefix cli
COMMAND_TEST_TOOLS=/tmp/tervory-command-workspace-20261031/workspace/node_modules COMMAND_ACCEPTANCE_CLIENTS=1 PYTHONPATH=tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/postgres /tmp/base-reliability-venv/bin/python -m pytest -q -s tests/command_acceptance_20261031/test_cross_lane.py
```

Result: **3 passed, 1 warning, 8.24s**, zero skips. Log `/tmp/command-acceptance-clients-pat.log`, including `PASS: 504 actual Tank events drained by browser and CLI; durable panel matches; pending and legacy Auto stay unproven`. Run with `COMMAND_ACCEPTANCE_CLIENTS=1` in assembled source to require both actual decoders; ordinary main-only run does not claim that coverage and skips PAT when its lane is absent.

```sh
ln -s /tmp/tervory-command-workspace-20261031/workspace/node_modules workspace/node_modules
node tests/command_1b_contract.cjs
node tests/command_1b_pages.cjs
```

Both PASS. Server-side Workspace identity, CSRF, stream/projection, model choice, attachments, failure behavior, catalogue and page-boundary assertions passed. These are offline contract tests, not visual or founder acceptance.

## Review handoff

PR467 remains draft. Independent review authority: chat `01a18da9-bec9-7291-a09e-23bbb838df8d`. Implementation owners must fix implementation findings on their own PRs. New implementation commits after the hashes above require a new exact-head evidence entry; none are silently covered by these results. The new backend task-receipt route in later head `50b123c9` is not covered by this entry.
