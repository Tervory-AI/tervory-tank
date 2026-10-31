# COMMAND-1 / CLI-1 acceptance audit — 31 October 2026

Initial evidence captured 2026-10-31 01:59 PDT / 08:59 UTC; final combined evidence 02:10 PDT / 09:10 UTC. PASS below means the stated offline assertion passed, never founder acceptance. GAP means an unmet requirement in the pinned source; UNVERIFIED means required proof was not executed or supplied. No live model calls, live worker operations, production SQL, ZA operations, UI additions or implementation edits were performed.

## Final frozen assembly (supersedes initial lane availability below)

- Backend PR465: `50b123c994488171fe7283a0823a271245d910a3`.
- Workspace PR466: `70a94d824f12a8144533767d24beac8dc33c1152`.
- CLI/PAT PR464: `bcaf0f27f84439e1ef5a885ff0b8141b228c3979` (owner frozen).
- Acceptance PR467 test source: `3b77006564ded67511f301f99691069f6037c572` (initial final test run); review tightening `6ac6a1cf`.
- Exact combined detached checkout: `9af496fba5ab4d496846ecdfc9324fef9f9b86d3`. Clean merges, no implementation changes.
- **4 cross-lane tests passed, zero skips, 10.78s**: real local HTTP/SQL through actual CLI, actual Workspace PAT adapter and actual full Tank, including cancellation N producing zero build rows and zero provider requests. Also 504 actual events consumed by browser and CLI, ownership/region denial, real persisted PAT revocation, foreign receipt rollback.
- **30 CLI tests passed, zero skips, 716.399ms** including streamed token redaction boundaries, replacement/sequence handling, confirm/job-follow and public adapter tests.
- B contract and page checks both passed again on this assembly.
- PR467 hosted checks at source `3b770065`: Tank, Workspace, security, CodeQL and all Analyze jobs PASS; runner/savings jobs skipped by workflow. It remains draft pending independent review; subsequent evidence-only commit checks must be checked again.
- Verified B artifacts are **375×812** and **1440×1120**, explicitly offline fixtures. Verified CLI asciinema v2 header is **120×28**, explicitly scripted OFFLINE fake-Tank output. These satisfy offline artifact coverage; they are not founder acceptance or native OS-keychain proof.
- Still missing: actual historical Auto-comparison ledger evidence; founder browser acceptance; approved Settings Access tokens frame and exact copy on Client `5:114` / Founder `5:115`. Existing Chats frames `3:2`, `4:84`, `4:114` were rejected per B owner; current approved Chats frame/text is also missing. No UI was invented.

Final commands (working directory `/tmp/tervory-command-assembled-20261031`):

```sh
npm ci --ignore-scripts --no-audit --no-fund --prefix cli
COMMAND_TEST_TOOLS=/tmp/tervory-command-workspace-20261031/workspace/node_modules COMMAND_ACCEPTANCE_CLIENTS=1 PYTHONPATH=tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/postgres /tmp/base-reliability-venv/bin/python -m pytest -q -s tests/command_acceptance_20261031/test_cross_lane.py
npm test --prefix cli
node tests/command_1b_contract.cjs
node tests/command_1b_pages.cjs
```

Logs: `/tmp/command-acceptance-final-crosslane.log`, `/tmp/command-acceptance-final-cli.log`. New public-edge assertions are `test_cross_lane.py:141` and `public_edge.cjs:29`; all foreign-region test traffic stays on the guarded loopback Tank. No ZA endpoint is contacted.

Final broad database command (same frozen A/B/CLI source, assembled `9af496fb`):

```sh
PYTHONPATH=tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/postgres /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_command.py tests/test_command_streaming.py tests/test_command_repo_tools.py tests/test_personal_tokens.py
```

**193 passed, zero skips, 12 warnings, 100.38s**; log `/tmp/command-acceptance-final-db.log`. Together with the four separate cross-lane tests, this is 197 passing Python tests; do not add the historical 194 result again.

Independent review requested a stricter assertion that the foreign-region request actually reaches the local Tank. Fixed in acceptance source `6ac6a1cf`: require exactly one additional upstream call and capture its actual 403 status. Combined checkout after this harness-only merge: `8b7d88d6fe5db2a52b72411317c4a40ac722ad73`. Affected-test command:

```sh
COMMAND_TEST_TOOLS=/tmp/tervory-command-workspace-20261031/workspace/node_modules COMMAND_ACCEPTANCE_CLIENTS=1 PYTHONPATH=tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/postgres /tmp/base-reliability-venv/bin/python -m pytest -q -s tests/command_acceptance_20261031/test_cross_lane.py::test_cli_public_adapter_reaches_real_tank_with_cancel_barrier
```

**1 passed, 12 warnings, 4.59s**, log `/tmp/command-acceptance-final-edge-tightened.log`. Other tests were not repeated because no other source changed. Initial weak assertion is not retained as final proof.

## Initial source provenance (historical proof, not final heads)

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
| COMMAND CI green, COMMAND-1:56 | PASS hosted / review pending | PR467 checks PASS at final source capture; draft stays draft. Green smoke CI alone does not execute this matrix. |
| Threads persist and stream, :57 | PASS offline | `tests/test_command.py:158`, `tests/test_command_streaming.py:178`; real local SQL and HTTP, fake upstream stream. Saved ownership, partial tokens before finish and durable answer tested. |
| Tool uses Tank and ledger, :58 | PASS offline | `tests/test_command.py:363`, `:444`, `:564`; real native route dispatch within test app, explicit ledger evidence, failure receipt and idempotence. No real provider cost claimed. |
| Approve/paid action waits for Confirm, :59 | PASS offline | `tests/test_command.py:400`, `:425`; `tests/test_command_streaming.py:334`; no dispatch before approval or after cancel, failure/retry barrier. |
| Client cannot see founder tools, :60 | PASS offline | `tests/test_command.py:38`, `:936`; acceptance `test_cross_lane.py:104` authenticates persisted synthetic PAT, ignores forged founder/tenant headers, rejects build, tools empty, revocation enforced. |
| Build reaches workers without issue; PR in thread, :61 | PASS contract / UNVERIFIED real execution | Acceptance `test_cross_lane.py:22` and `:37`: proposal not claimable before Confirm, fake worker claims via HTTP, reports progress and repository PR link. No real worker is launched or investigated. |
| Every turn model/cost/baseline/saved matches ledger, :62 | PASS offline | Streaming ledger tests at `test_command_streaming.py:178`, `:212`; command receipts at `test_command.py:612`, `:706`, `:744`. Unknown evidence remains null. Pinned turns carry COMMAND-1's (#224) Auto comparison restored on #496: same recorded tokens priced at the `command.turn` policy model's `tank.proof_prices` rate, frozen at turn acceptance (`test_command.py` `test_auto_comparison_prices_same_tokens_with_frozen_tenant_policy`). No second model call is made to manufacture it. |
| Panel updates as steps change, :63 | PASS offline | Acceptance `test_cross_lane.py:37`: 504 HTTP worker reports exceed 500-event SQL page; ordered replay drains fully, cursor exhaustion, final durable panel/PR/checks/review match. `consume_replay.cjs:20` consumes same bytes through actual B and CLI decoders. Actual rendered component replay behavior remains B lane's separate browser proof. |
| 375px and 1440px screenshots in PR, :64 | PASS offline / UNVERIFIED founder | B committed offline-375.png (375×812) and offline-1440.png (1440×1120), verified from file headers; founder-browser screenshots absent. |
| CLI CI green, CLI-1:32 | UNVERIFIED hosted / PASS source review | Independent reviewer cleared CLI source bcaf0f27 after 30 Node and 8 PAT checks. This audit does not substitute source review for hosted CI. |
| Login stores keychain / never prints token, :33 | PASS interface / UNVERIFIED native | Final CLI client.test.mjs:50 verifies mocked keychain interface and no terminal disclosure. Actual native OS-keychain roundtrip is unverified. No real secret used. |
| Chat streams tokens/steps/receipts, :34 | PASS offline | Actual CLI decoder consumes 504 real local Tank events; CLI client.test.mjs:65 verifies streamed tokens, steps and receipts. Scripted offline cast supplied; not a founder terminal session. |
| Confirm card does nothing on N, :35 | PASS offline actual path | Final public-edge cross-lane test runs CLI build N through actual Workspace adapter and full Tank: card cancelled, zero builds and zero provider calls. CLI client.test.mjs:65/:117 also pass. |
| Client token cannot see founder tools, :36 | PASS offline | Persisted PAT hash + actual command HTTP dependency override in acceptance `test_cross_lane.py:104`; client headers cannot escalate, cannot read another user's thread, wrong box refused. |
| Pinned model shows Auto comparison, :37 | PASS offline | Restored on #496 from main (#224): `auto_price_snapshot` freezes the policy model and its price-book row at acceptance; `record_receipts` prices the pinned turn's recorded tokens with Decimal and labels it "What Auto would have cost (same tokens at policy model prices)", basis "not a separate model run". Snapshot and replay return it unchanged. Workspace totals it only when every row is priced (`command_1b_contract.cjs`); the CLI prints Tank's amount and never computes money (`cli/test/client.test.mjs`). It stays `pending` when the policy model has no active price row. |
| Revoked token refused, :38 | PASS offline | Actual local persisted PAT revoked and subsequent command HTTP returns 401, acceptance `test_cross_lane.py:131`; fake-DB PAT unit tests also pass. |
| Terminal recording with receipt, :40 | PASS offline | Final CLI tests/cli_1_20261031/fake-tank-chat.cast supplied, 120×28, scripted OFFLINE fake-Tank/synthetic ledger/N. Not native keychain, model or founder proof. |
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

PR467 remains draft. Independent review authority: chat `01a18da9-bec9-7291-a09e-23bbb838df8d`. Implementation owners must fix implementation findings on their own PRs. New implementation commits after the hashes above require a new exact-head evidence entry; none are silently covered by these results. The initial entry did not cover the later task-receipt route; final assembly includes `50b123c9`. Final broad DB results are recorded separately above: 193 passed, zero skips.


Harness checks and corrected failures: `node --check tests/command_acceptance_20261031/public_edge.cjs` and `consume_replay.cjs` PASS; `/tmp/base-reliability-venv/bin/ruff check --no-cache tests/command_acceptance_20261031 --select E9,F` PASS. Initial harness CI failed `tests/test_secrets.py` because a deliberately fake service placeholder was not recognized. Replaced only that literal with repository-standard `dummy-workspace-key`; `PYTHONPATH=tank /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_secrets.py` → **2 passed, 9.03s**; subsequent hosted Tank PASS. `gh pr edit` failed on deprecated projectCards GraphQL fields; body updated using `gh api .../pulls/467 -X PATCH -F body=@...`. A local commit hit disk quota; sparse-checkout excluded only this lane's existing test artifacts, then commit/push succeeded. No push failed.
