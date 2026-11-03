# CLI code mode — PR handoff, 3 November 2026

Branch: `codex/cli-code-mode`. Work is isolated at
`/workspace/codex-cli-code-mode`. Claude opened PR #598; the founder merges.
Main was merged into this branch as recorded below. No PR merge or deployment was performed.
**Offline verification is not founder acceptance.**

## PR #598 round 2 — current review result

Round 1 items 1–6 and 8 were verified by the review; the founder reports CI green
on `9610a5d9`. The older local full-suite failure record below is historical,
not a claim that CI on that revision is red. This round's pushes retrigger CI.

Main `305b833b` was merged at `77060457`, retaining both sides of all five
conflicted files. `cli/CHANGELOG.md` retains main's 0.1.2 entry and code mode's
0.2.0 entry; package.json and both lockfile version fields are 0.2.0.
The code policy remains at `tank/schema.sql:2286`, above the generated-memory
marker at line 2444. No PR merge or production migration was performed.

| Item | File and line | Fix and proof |
| --- | --- | --- |
| 1a | `cli/src/code-tools.mjs:233,247`; `cli/test/code-mode.test.mjs:371` | Candidate and canonical target must both be regular executable files. Directory runners, directory symlinks, nonexecutables and their symlinks refuse before approval. Node binds only its binary file, never bin or its parent. A valid Node runner works, cannot read neighboring .npmrc data and cannot overwrite the bound executable. |
| 1b | `cli/src/code-tools.mjs:252,293`; `cli/test/code-mode.test.mjs:394` | pip-user/uv launchers under .local/bin are refused. Dedicated Python installs bind only executable files, matching lib/pythonX.Y, pyvenv.cfg and matching libpython files. Their installation parent is never bound. User-data canaries in .local/share/python_keyring and .local/share/fish remain inaccessible. Actual worker venv test still passes with these specific mounts. |
| 2 | `tank/command.py:1801`; `tests/test_command_code.py:169,175` | Only requests keys or names equal to one of the six tools trigger strict proposal handling. Both requested my-app examples, ordinary arguments prose and fenced answers succeed. Tool envelopes, known tool names and malformed requests retain strict validation. |
| 3 | `cli/CHANGELOG.md:3`, `cli/package.json:4`, `cli/package-lock.json:3`, `cli/src/client.mjs:456`, `tank/schema.sql:2286` | Kept main's release/help/schema changes and code mode. Version guard explicitly passes 0.1.2 -> 0.2.0. |
| 4 | `tank/schema.sql:2286`; `tests/test_command_code.py:97,120`; `tests/test_perplexity_research.py:405,436` | Copied policy overrides only task_type and cache_scope='none'. Reapplication repairs an older tenant-cache code policy without replacing other fields. Full row comparison differs from command.turn only by task/cache scope. Real run_route tests in both regions, Auto and pin, use the seeded cache scope and assert zero command.code route_cache rows. run_route itself is unchanged. |

Exact current command output and build hashes: **results.txt**.

```sh
TMPDIR="$PWD/.task-tmp" npm test --prefix cli
# exit 0: 89 passed, 0 failed, 27.866 seconds

TMPDIR="$PWD/.task-tmp" node --test --test-name-pattern='external' cli/test/code-mode.test.mjs
# exit 0: 4 passed, including both reported mount exploits

TMPDIR="$PWD/.task-tmp" PYTHONPATH=.task-tmp/deps:.task-tmp/forge-deps:tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55468/pooltest /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_command_code.py tests/test_perplexity_research.py::test_schema_applies_twice_and_preserves_policy tests/test_schema.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
# exit 0: 23 passed, 32.05 seconds; actual HTTP/router/SQL, mocked upstream only

sh .github/scripts/cli_version_guard.sh origin/main
# exit 0: CLI changed and the version moved 0.1.2 -> 0.2.0 with a CHANGELOG entry.

/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# exit 0: All checks passed!

git diff --check origin/main
# exit 0

TMPDIR="$PWD/.task-tmp" node cli/scripts/build-release.mjs --out "$PWD/.task-tmp/round2-release"
# exit 0: all six artifacts built
```

The owned PostgreSQL container uses loopback port 55468, trust authentication and
only disposable test data. No SQL was run against production. No live model was
called to check work, and no real credential was read or created.

The real CLI worker proof was rerun with the existing venv after the mount fix:
**worker-test.txt** records the exact entrypoint command, real TTY inputs,
specific bound paths shown before y, **2 passed in 0.19s**, and CLI exit 0.
Keychain/HTTP are explicitly offline stubs. This does not claim a live founder
receipt, /chats browser acceptance or screenshot; those are still missing.
No page/UI/copy was added; no new terminal wording was introduced in round 2.
`cli/README.md` documents the narrower mounts and the no-cache policy, retaining
the founder's existing transcript masking/tenant/region storage clarification.

## PR #598 review fixes — 3 November 2026

The existing PR is <https://github.com/Tervory-AI/tervory-tank/pull/598>.
Main was merged at `e8ac46fd` (both schema additions retained), then refreshed
and merged at `dc7cd7c0` (`origin/main` = `cf95a07e`). No push to main.
The implementation notes below this review section describe earlier runs;
they are not a claim that founder acceptance has happened.

| Review | File and verified line | Result |
| --- | --- | --- |
| 1 | `cli/src/code-tools.mjs:33,78,112,340`; `cli/test/code-mode.test.mjs:201` | Every Git subprocess uses global literal pathspec mode, including scratch application. Ignored tracked names come from `ls-files`, because `check-ignore` rejects global literal mode. Tracked `.e*` cannot include tracked `.env` in a diff. |
| 2 | `cli/src/code-tools.mjs:314`; `cli/test/code-mode.test.mjs:236` | Status uses `--ignore-submodules=all`. Registered/committed submodule has a distinct clean driver and a same-size edit: removing the flag was independently verified to execute its marker command. Fixed status and diff leave both markers absent. |
| 3 | `cli/src/code-tools.mjs:27,94,196`; `cli/test/code-mode.test.mjs:266` | Missing-file canonical parent plus basename is checked both when resolving and immediately before rename. `.git` is case-insensitive. Tests cover direct `lnk -> .git` creation, approval-time ancestor swaps, and `.GIT`. |
| 4 | `cli/src/code-tools.mjs:65,78`; `cli/test/code-mode.test.mjs:285` | Repository Git directory and work tree are pinned after discovery. An approved command creates a nested repository; subsequent list/status/diff still use the original one. Scratch Git has its own explicit directory/work-tree pair. |
| 5a | `cli/src/code-tools.mjs:33` | Removed the shell option; spawn uses literal `shell: false`. |
| 5b | `.github/workflows/cli.yml:51`; `cli/src/code-tools.mjs:218` | Ephemeral Ubuntu runner enables unprivileged namespaces when its AppArmor knob exists, then requires a successful Bubblewrap probe. External hosted Node installation is bound read-only and named before approval. PR fake-tank passed (links below). |
| 5c | `tests/test_perplexity_research.py:414,431` | Added command.code to the additive seed set and compared every copied policy field with command.turn. Targeted test and the merged-tree Command group pass. The full offline script was run and failed outside this lane; complete output and unrun count are recorded below. |
| 6 | `cli/test/code-mode.test.mjs:150` | Confinement command must return 0 and print `sandbox-ok`, as well as hide canaries. A failed sandbox cannot pass. |
| 7 | `cli/src/code-tools.mjs:218,287`; `cli/README.md:50`; `tests/cli_code_mode/worker-proof.mjs:1` | Leading external Node/Python/pytest runner resolves to only its own read-only runtime directories. Venv base Python is included; intermediate links are recreated without mounting their host parent. No HOME/config/SSH/keychain directory is mounted. Actual worker terminal record runs the existing schema test file after y: 2 passed. |
| 8 | `cli/src/code-mode.mjs:9,22,32`; `tank/command.py:1720,1791`; `tests/test_command_code.py:128` | Prompt UUID plus continuation flag stores the user message once. Bounded redacted history (40 entries / 200,000 UTF-8 bytes) includes earlier prompts, answers, names/arguments as DATA. Backend tests prove three rounds store one user message/three receipts and no history in state/events/tasks. CLI test exercises eviction across 60 offline prompts. |
| 9 | `tank/command.py:1752`; `tests/test_command_code.py:169,180` | Prose is an answer with no tool requests; fenced JSON is decoded. Structured or malformed tool proposals retain strict tool/argument validation. A real route test accepts prose and retains paid ledger receipts. |

### Commands and observed results for the review

All commands ran in `/workspace/codex-cli-code-mode` unless a working directory
is explicitly stated. `.task-tmp` is ignored and contains only local test
artifacts/dependencies. PostgreSQL is the owned disposable `cli-code-mode-tests`
container on loopback port 55468; no production data was queried or changed.

- `git fetch origin && git checkout codex/cli-code-mode && git merge origin/main`:
  schema conflict resolved retaining both additions; schema tests 2 passed.
- `git fetch origin && git merge origin/main`: clean later merge of MCP work,
  `dc7cd7c0`; every push was preceded by `git merge origin/main`.
- `TMPDIR="$PWD/.task-tmp" node --test cli/test/code-mode.test.mjs`:
  19 passed before the extra runtime-link case; its targeted run then passed.
- `TMPDIR="$PWD/.task-tmp" npm test --prefix cli`: under concurrent host load,
  79/81 passed, two deadline failures (regex worker and existing redirect test).
- `TMPDIR="$PWD/.task-tmp" node --expose-gc --test --test-concurrency=1 cli/test/*.test.mjs`:
  **82 passed, 0 failed**, 87.839 seconds. Later strengthened submodule/history
  tests each passed separately with the exact commands below.
- `TMPDIR="$PWD/.task-tmp" node --test --test-name-pattern='clean/process' cli/test/code-mode.test.mjs`:
  1 passed; same-size submodule edit, distinct driver, registered submodule.
- `TMPDIR="$PWD/.task-tmp" node --test --test-name-pattern='session history' cli/test/code-mode.test.mjs`:
  1 passed, including 60 prompts and byte/entry limits.
- `TMPDIR="$PWD/.task-tmp" node --test --test-name-pattern='external|missing files|Git reads|confinement|approved command' cli/test/code-mode.test.mjs`:
  5 passed (read-only runtime, intermediate links, pinned repository, hook escape,
  command confinement).
- `TMPDIR="$PWD/.task-tmp" PYTHONPATH=.task-tmp/deps:tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55468/pooltest /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_command_code.py`:
  **15 passed**, 46.38 seconds, including real mocked-upstream router/ledger tests.
- Same environment/interpreter with `-m pytest -q tests/test_perplexity_research.py::test_schema_applies_twice_and_preserves_policy`:
  **1 passed**, 9.03 seconds.
- `/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'`: passed.
- `sh .github/scripts/cli_version_guard.sh origin/main`: passed, 0.1.1 → 0.2.0.
- `git diff --check`: passed. AST source extraction of `run_route` versus
  `git show origin/main:tank/main.py`: byte-identical.

Ubuntu CI proof before the final merge/docs refresh:
[fake-tank passed](https://github.com/Tervory-AI/tervory-tank/actions/runs/41618528889/job/125857964762).
The prior security run including Semgrep also
[passed](https://github.com/Tervory-AI/tervory-tank/actions/runs/41616631339/job/125852066593).
These links identify the tested revisions; current-head CI remains separately visible on the PR.

### Final merged-tree results and exact full-suite blockers

`TMPDIR="$PWD/.task-tmp" npm test --prefix cli` now passes with the standard
parallel invocation: **82 passed, 0 failed**, 33.346 seconds. This supersedes the
earlier host-load deadline failures without changing their timeouts.

The following merged-tree check passed **235 tests**, including all code-mode
routes, all Command tests, the policy-copy regression, schema and secret checks:

```sh
TMPDIR="$PWD/.task-tmp" PYTHONPATH=.task-tmp/deps:.task-tmp/forge-deps:tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55468/pooltest /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_command*.py tests/test_pat_route_corridor.py tests/test_perplexity_research.py::test_schema_applies_twice_and_preserves_policy tests/test_schema.py tests/test_secrets.py --timeout=150 --timeout-method=thread --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Result: exit 0, 235 passed in 500.52 seconds. Complete stdout is in `results.txt`.
`TMPDIR="$PWD/.task-tmp" node cli/scripts/build-release.mjs --out "$PWD/.task-tmp/review-release"`
also exited 0 and built all six release artifacts; hashes/sizes are in that file.
`run_route` was rechecked after the MCP merge and remains byte-identical to main.

The existing `.github/scripts/offline_suite.py` was run with all CI database
opt-ins, loopback-only sockets, the pinned Forge requirements, existing Chromium,
four workers, and the script's documented budget scale of 2 for this worker.
Exact wrapper, preparation commands and full stdout/stderr: **`full-suite.txt`**.
It completed normally with **exit 1 in 1182 seconds**:

- Main pass: 2,088 passed, 4 failed, 4 skipped. Worker loss left **4,432 of 6,524
  collected tests unrun**; this is explicitly not a passing full-suite claim.
- Tiger separate pass: 46 passed, exit 0.
- Zenas separate pass: 40 passed, exit 0.

Exact main failures (these files are unchanged from origin/main):

1. `tests/test_read1_review.py:367`,
   `test_raw_text_containers_are_removed_before_serializing[noframes]`:
   `Page.set_content: Timeout 30000ms exceeded`, waiting for load.
2. `tests/test_moa_integration.py:245`,
   `test_all_seven_bench_shapes_use_routed_receipts_and_never_enable`:
   `assert (1 == 7)`; one failed shape returned instead of seven complete shapes.
3. `tests/test_tiger_public_policy.py:230`,
   `test_real_browser_document_and_asset_refusals[429]`: worker gw2 crashed after
   the per-test timeout; the suite reports `Not properly terminated`.
4. `tests/test_read1_review.py:428`,
   `test_cumulative_opacity_below_point_one_is_hidden` (opacity 0.01): worker gw3
   crashed after the per-test timeout, also `Not properly terminated`.

A focused READ-1 browser diagnosis passed one case then stalled; it was
interrupted after 295.86 seconds. No READ-1, MoA or Tiger implementation was
changed to hide these failures. Earlier incomplete attempts and missing Forge
setup are not counted as successful suite runs.

PR CI on the code revision passed fake-tank, security/Semgrep, Command acceptance,
Workspace, CodeQL, isolation, nonroot-services and rig-admin. Subsequent evidence
commits retrigger CI; current-head status is available on the PR. No current-head
Tank success is claimed without a completed job.

### Real worker terminal proof and acceptance boundary

Exact recorded command (real stdin/stdout TTY):

```sh
script -qefc 'env TERVORY_NO_UPDATE_CHECK=1 CODE_PROOF_PYTHON=/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python node --import ./tests/cli_code_mode/worker-proof.mjs cli/bin/tervory.mjs code /workspace/codex-cli-code-mode' .task-tmp/worker-proof.typescript
```

Inputs: `Run the repository's schema test file.`, then literal `y`, then `/exit`.
The full entrypoint transcript is committed as `worker-test.txt`: the complete
Python command and both runtime directories appear before the approval;
`tests/test_schema.py` reports **2 passed in 0.23s**, CLI exit 0.
This is the real CLI entrypoint and actual Bubblewrap/test execution on the
worker. Only keychain/HTTP are offline stubs. There was no live token read,
provider request, invented charge or production thread. `Receipt pending`
is the actual offline display, not proof of a real receipt.

The founder's live worker question, `/chats` receipt and screenshots are still
missing. No offline test or rendered log is claimed as that founder test.
No browser screenshot has been fabricated. No PR merge/deployment was performed.
Additional terminal wording introduced by the review: `Read-only runner: {path}`.
The requested directory names are displayed before the existing Run prompt.

## Result and file map

`tervory code [folder]` uses the existing keychain token and fixed regional
origin, then loops through Tank's code proposals and the six local tools.

| File and starting line | Change |
| --- | --- |
| `cli/src/client.mjs:438,464` | Help fragment and code-session dispatch; existing auth/region/receipt helpers reused. |
| `cli/bin/tervory.mjs:42` | Real stdin/stdout TTY state passed to the approval gate. |
| `cli/src/code-mode.mjs:3` | Interactive loop, bounded transient result context, redaction before sending, no turn retries. |
| `cli/src/code-tools.mjs:8,21,88` | Bounds, repository secret-pattern redaction, canonical path/secret-path checks. |
| `cli/src/code-tools.mjs:102,142,149,176` | Git-ignore-aware file list (2,000), text read (200,000 bytes), search (200 matches), git diff. Regex work is isolated in a timed worker. Git clean/process filters are disabled so read tools cannot execute repository commands without approval. |
| `cli/src/code-tools.mjs:181` | Single-file unified diff using Git's existing applicator in an isolated scratch repository; only one neutral text target is permitted. Missing-file reads allow creation; read hash is checked before and after approval. Only literal `y` applies. |
| `cli/src/code-tools.mjs:205,226` | Approved commands use the worker's existing Linux Bubblewrap, a restricted environment and isolated process/network namespace. Host folders and secret paths are unavailable; no unsandboxed fallback. Output is redacted and shown locally; deadline 120 seconds, retained stdout/stderr at most 65,536 bytes. |
| `tank/command.py:1623,1697,1709` | Typed six-tool catalogue, `command.code` via existing `run_route`, metadata-only thread/task/event persistence, actual ledger receipts, founder-only pins. Tank does not execute any of the six tools. |
| `tank/main.py:1006` | Add `command.code` to the existing model-override task allowlist **outside `run_route`**. The function itself is byte-identical to main. |
| `tank/schema.sql:2286` | Additive/idempotent initial `command.code` policy copied from existing chat policies, including tenant-specific rows. Existing policies are not overwritten. No fixed new model/provider is selected. |
| `tank/personal_tokens.py:121`, `workspace/lib/tank.ts:162` | Add only `code-turn` to the existing personal-token corridors (direct ZA and fixed-local Workspace proxy). |
| `cli/package.json:4`, `cli/package-lock.json:3`, `cli/CHANGELOG.md:3` | Version 0.2.0; historical changelog entries retained. |
| `cli/README.md:50` | Code-mode use, command sandbox/platform limits and the founder's clarified storage rule. |
| `cli/test/code-mode.test.mjs:1`, `tests/test_command_code.py:1` | Offline safety, edit/command confirmation, limits, complete read-edit-test loop, route/receipt/storage/region/pin regressions. |
| `tests/test_pat_route_corridor.py:34,94` | New route included in the existing explicit corridor boundary audit. |
| `.github/workflows/cli.yml:51` | Ensure Bubblewrap exists on the ephemeral CI runner for local command tests; no production runtime configuration changed. |

`/chats` uses existing user-message and step/receipt components. No page UI,
button, empty state or new page wording was added. Existing “Preparing answer”,
“Answer ready” and “Answer failed” labels are reused. Assistant code replies are
returned privately to the CLI; the saved assistant message is the existing
“Answer ready” status, so model-quoted source or patch bodies cannot enter `/chats`.
Tool requests and results retain only name and UTF-8 byte size there. Cancelling
at command approval stops execution and any subsequent code-model request.

## Storage clarification from the founder

The no-file-contents requirement applies to the Command thread, events, task input
and `/chats`. File/result/patch bodies do not enter those records. The model call's
transcript follows Tank's existing handling for every chat turn: masked by
`_preflight_mask` and `_storage_mask`, tenant-scoped, and retained on that region's
own box. Local secret redaction runs before any tool data or typed input leaves
the machine. This distinction is also in `cli/README.md`.

There is no new sign-in, token argument/environment credential, URL override,
provider, model client, paid-service configuration or price calculation. Existing
receipt amounts are displayed unchanged. The new task begins with a copy of the
existing chat policy; subsequent code-policy choices remain founder-controlled.

## New CLI strings for founder approval

These are terminal strings, not page copy. The existing `> `, `Thread {id}`,
receipt rendering and generic transport errors are reused.

```text
code [folder]                        (added fragment in existing help)
Apply [y/N]                          (prompt ends with one space)
Run [y/N]                            (prompt ends with one space)
Code mode requires an interactive terminal.
Code mode requires a git repository.
Code tool refused.
Code tool limit reached; nothing was retried.
Code tool result exceeds the limit.
```

The diff, full command, redacted process output and model answer are data displayed
in the terminal, not invented fixed UI copy. Approval prompts accept only `y`
(case-insensitive, surrounding whitespace ignored); `yes`, N, EOF and non-TTY
sessions cannot apply an edit or run a command.

## Exact local validation commands and results

Working directory for all commands: `/workspace/codex-cli-code-mode`.
No test used a live model, live sign-in, production SQL or live fixture screen.

```sh
npm ci --ignore-scripts --no-audit --no-fund --prefix cli
# installed CLI dependencies successfully

# The reused Python test runtime lacked a dependency now required by main.
# Install the already pinned repo dependency into this checkout's ignored directory.
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pip install --target .task-tmp/deps 'jsonschema==4.26.0'
# installed; no shared runtime was modified

docker run -d --name cli-code-mode-tests -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=pooltest -p 127.0.0.1:55468:5432 postgres:16
# disposable loopback test service only, no production connection

TMPDIR="$PWD/.task-tmp" npm test --prefix cli
# 77 passed, zero failed, zero skipped; see final CLI log for elapsed time
# Includes all 62 pre-existing CLI tests and 15 new code-mode cases.

TMPDIR="$PWD/.task-tmp" PYTHONPATH=.task-tmp/deps:tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55468/pooltest /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_command.py tests/test_command_streaming.py tests/test_command_repo_tools.py tests/test_personal_tokens.py tests/test_pat_route_corridor.py tests/test_command_code.py
# 205 passed, zero skipped; 14 deprecation/field warnings; 140.01 seconds

TMPDIR="$PWD/.task-tmp" PYTHONPATH=.task-tmp/deps:tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55468/pooltest /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_schema.py tests/test_secrets.py
# 4 passed, 23.14 seconds

/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# All checks passed!

sh .github/scripts/cli_version_guard.sh origin/main
# CLI changed and the version moved 0.1.1 -> 0.2.0 with a CHANGELOG entry.

git diff --check
# exit 0
```

The read-edit-test CLI case uses a fake Tank, an existing synthetic token,
a disposable git directory and a real sandboxed `node --test small.test.mjs`.
It verifies missing-file read, the exact diff, separate edit/run approvals, a saved
test file and `# pass 1` from the real local test process. The route tests use actual
Tank HTTP/SQL and the existing router with a stubbed upstream, check both regions
and Auto/founder pins, and correlate the Command receipt to the ledger. A canary
in tool data and a patch returned by the model are absent from thread state,
events, task input/result and `/chats` reads; masked transcripts follow existing
handling, separately verified. These are offline proofs, not founder screenshots.

Initial test setup issues are not hidden: a non-git-folder test initially used a
temporary directory inside this checkout (which correctly is inside a git repo),
so its fixture was corrected to explicitly mark an invalid git directory. The
first full-router setup lacked `jsonschema`; installing the repo-pinned package
into `.task-tmp/deps` resolved it. Neither failure was a live product test.

## Deployment and remaining founder acceptance

Merge would deploy the changed Tank/Workspace source through the existing flow.
The schema seed is additive; it was applied only to disposable test databases here.
No production setting was changed and no secret value was inspected. The worker
already has Bubblewrap; another worker without it will refuse commands instead of
running them without confinement. The command runner is Linux-only. Command tests
run in the selected folder mounted at `/work`, with system executables read-only,
secret paths hidden, and temporary output at isolated `/tmp`; dependencies outside
that folder and commands requiring network access are intentionally unavailable.

After the founder controls merge/deployment and the existing CLI update to 0.2.0,
use the existing worker-box keychain session in a clone of tervory-tank:

1. Run `tervory code`.
2. Ask it to add one small test.
3. Verify its reads, displayed diff and explicit edit `y`.
4. Verify the full displayed test command, separate run `y`, and actual test output.
5. Open the same session in `/chats`; verify the receipts and absence of source/patch contents.

**Founder run and screenshots are missing.** No offline capture is substituted.
This branch is ready for Claude's PR and separate review, not marked done.
