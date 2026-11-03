# CLI code mode — PR handoff, 3 November 2026

Branch: `codex/cli-code-mode`. Work is isolated at
`/workspace/codex-cli-code-mode`. Claude opens the PR; the founder merges.
No PR has been opened by this job. No merge or deployment was performed.
**Offline verification is not founder acceptance.**

## Result and file map

`tervory code [folder]` uses the existing keychain token and fixed regional
origin, then loops through Tank's code proposals and the six local tools.

| File and starting line | Change |
| --- | --- |
| `cli/src/client.mjs:438,464` | Help fragment and code-session dispatch; existing auth/region/receipt helpers reused. |
| `cli/bin/tervory.mjs:42` | Real stdin/stdout TTY state passed to the approval gate. |
| `cli/src/code-mode.mjs:3` | Interactive loop, bounded transient result context, redaction before sending, no turn retries. |
| `cli/src/code-tools.mjs:8,21,76` | Bounds, repository secret-pattern redaction, canonical path/secret-path checks. |
| `cli/src/code-tools.mjs:90,130,137,164` | Git-ignore-aware file list (2,000), text read (200,000 bytes), search (200 matches), git diff. Regex work is isolated in a timed worker. |
| `cli/src/code-tools.mjs:169` | Single-file unified diff; missing-file reads allow creation; exact context and read hash checked before and after approval. Only literal `y` applies. |
| `cli/src/code-tools.mjs:193,214` | Approved commands use the worker's existing Linux Bubblewrap, a restricted environment and isolated process/network namespace. Host folders and secret paths are unavailable; no unsandboxed fallback. Output is redacted and shown locally; deadline 120 seconds, retained stdout/stderr at most 65,536 bytes. |
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
# 76 passed, zero failed, zero skipped; 16.208 seconds
# Includes all 62 pre-existing CLI tests and 14 new code-mode cases.

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
