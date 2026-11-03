# CLI W3 — implementation handoff, 3 November 2026

Branch: `codex/cli-w3`, in `/workspace/codex-cli-w3`.
Base: `a870ade14bce0b15fb1fb88fbf80d868029f253f`.
Validated code: `24f35f10e72428bc917a0fb235067d1224fb0e2e`.
Later commits record this evidence only. The founder merges; Claude opens the PR.

Code mode now proposes Tervory actions through the existing pending Confirm
cards, carries bounded project notes, and can use installed first-party plugins'
connected read tools. One approved patch can change twenty files; ten changes can
be undone in memory. macOS commands use system Seatbelt confinement.

**Implementation and offline verification are complete. Founder acceptance is
outstanding.** These records do not claim a live founder run, deployed behavior,
Mac execution, screenshots, or passing CI.

## Changes by file and line

| File and verified line | Change |
| --- | --- |
| `tank/command.py:57`, `:123`, `:1253`, `:1408`, `:1692` | Plugin catalogue/roles, existing-card adapters, readiness before proposal, and durable Confirm dispatch. Empty-grant members retain an empty catalogue. |
| `tank/command.py:1375`, `:1900`, `:1919`, `:1924`, `:1956`, `:2010` | Reused planner catalogue with code response format; `tervory` requests/results, six-request bound, actor validation, transient project notes, same-thread pending cards, and twenty-file/UTF-8 edit contract. |
| `cli/src/code-mode.mjs:1`, `:10`, `:25`, `:55` | Git-root AGENTS.md through CodeFolder read; bounded `project` history; existing Confirm/followThread and redacted card results; local `/undo`. |
| `cli/src/client.mjs:357` | Explicitly non-interactive Confirm cancels without prompting. |
| `cli/src/code-tools.mjs:35`, `:67`, `:147`, `:195`, `:200`, `:243`, `:268`, `:381`, `:436` | Restricted macOS temporary directory; byte-preserving reads; whole-set preflight/staging/rollback; ten undo snapshots; Darwin sandbox probe; hunk-aware twenty-file splitting, with Git still applying each patch. |
| `cli/src/seatbelt-base.sbpl:1` | Unmodified pinned upstream Seatbelt base. |
| `cli/src/seatbelt.LICENSE:1` | Upstream Apache-2.0 license. |
| `cli/src/seatbelt.mjs:1` | Read-only system and selected runtime paths, selected-folder writes, explicit secret/network denies, and required Apple git toolchain lookup. |
| `tank/plugins.py:1`, `:55`, `:73`, `:83`, `:100`, `:114`, `:130`, `:163` | Manifest validation; tenant install/list/remove; current approval/skill/connection state; code-only read filtering by full vault-and-connection identity. No credential fields are selected for list output. |
| `plugins:1` | Repository path points to the one manifest source at `tank/plugin_packages`, inside Tank's existing build context. |
| `tank/plugin_packages/github/1.0.0/plugin.yaml:1` | First-party GitHub manifest, also available at `plugins/github/1.0.0/plugin.yaml`; six official read tools, Radix, code mode enabled, no skill refs. |
| `tank/Dockerfile:20` | Copies bundled manifests into the image; existing module COPY already includes the new Python module. |
| `tank/schema.sql:2762` | Additive/idempotent plugin installs and both conditional RLS policies, matching personal_tokens, above the generated-memory block. |
| `.github/workflows/cli.yml:140` | macos-latest runs npm test and the same confinement checks. Existing release tests use GNU tar/coreutils/OpenSSL/wget on that runner. |
| `cli/README.md:50` | All three gates, existing confirmation path, notes/privacy, change sets/undo, runtime restrictions and Seatbelt attribution. |
| `cli/package.json:4`, `cli/package-lock.json:3`, `:9` | Gate 1 version 0.3.0, gate 3 final version 0.4.0, lockfile synchronized. |
| `cli/CHANGELOG.md:3`, `:10` | Entries for 0.4.0 and 0.3.0. |
| `docs/mcp/README.md:77` | Manifest format, packaging, `{name, version}` install arguments, tenant/admin/approval rules, GitHub source and Figma boundary. |
| `cli/test/code-mode.test.mjs:418`, `:455`, `:482`, `:494`, `:516`, `:527`, `:546`, `:563`, `:576`, `:596`, `:608`, `:618`, `:626` | Fake-Tank confirmations/cancellation/notes; atomicity and crash simulation; undo; real confinement with a reachable-host network control; missing sandbox/invalid profile; byte-exact BOM restore; non-interactive cancellation. |
| `tests/test_command_code.py:36`, `:193`, `:207`, `:240` | Updated catalogue, six-request and authorization refusal, real pending-card route/privacy/no dispatch, optional multi-file path and UTF-8 bounds. |
| `tests/test_plugins.py:23`, `:41`, `:81`, `:102`, `:136`, `:164`, `:182` | Manifest rejection, install/admin/Confirm/receipt checks, state and no-token output, install-gated reads, actual RLS, actual existing card projection, and colliding connection IDs in different vaults. |
| `tests/test_command.py:49`, `:956` | Existing enabled-product catalogue expectations include plugins.list; grant/revocation checks remain enforced. |
| `tests/test_personal_tokens.py:49` | Existing token-identity catalogue assertion includes plugins.list for its enabled Tiger product. |
| `tests/cli_code_mode/W3-RESULTS.txt:1` | Actual final command output, with only trailing whitespace normalized. |
| `tests/cli_code_mode/W3-EVIDENCE.md:1` | This handoff, remaining acceptance and source/license record. |

Tank `_startup` at `tank/main.py:755` was read before schema work. Its existing
conditional RLS startup guard and schema-on-start path are unchanged. The schema
was applied twice to disposable test databases, both staged and RLS-enforced.
The file still ends with the generated block.

## Exact final verification commands and results

Working directory for every command below: `/workspace/codex-cli-w3`.
Full captured output and exact commands: `W3-RESULTS.txt`.

```sh
TMPDIR=/workspace/codex-cli-w3/.tmp PYTHONPATH=.tmp/deps:tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55473/pooltest /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -n 4 -q tests/test_command*.py tests/test_mcp*.py tests/test_personal_tokens.py tests/test_pat_route_corridor.py tests/test_plugins.py tests/test_schema.py tests/test_secrets.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
# exit 0: 427 passed, 331 warnings in 237.32s

TMPDIR=/workspace/codex-cli-w3/.tmp npm test --prefix cli
# exit 0: 101 passed, 0 failed, 1 skipped, 40.070s
# The skipped test intentionally loads an invalid Seatbelt profile on macOS.
# This worker is Linux; the macOS job runs that test.

TMPDIR=/workspace/codex-cli-w3/.tmp /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/ruff check tank/command.py tank/plugins.py tests/test_plugins.py tests/test_command_code.py tests/test_command.py tests/test_personal_tokens.py --select E9,F
# exit 0: All checks passed!

TMPDIR=/workspace/codex-cli-w3/.tmp sh .github/scripts/cli_version_guard.sh origin/main
# exit 0: 0.2.0 -> 0.4.0, matching CHANGELOG entry

git diff --check origin/main
# exit 0, no output

cmp cli/src/seatbelt-base.sbpl .tmp/seatbelt_base_policy.sbpl
# exit 0: unchanged upstream base
```

Additional final-version release check:

```sh
TMPDIR=/workspace/codex-cli-w3/.tmp node --test cli/test/release.test.mjs
# exit 0: 7 passed, 0 failed, 33.830s
```

The first combined serial Python run had 422 passed and three catalogue
assertion failures. The empty-grant regression was fixed and enabled-product
expectations were updated. The final 427-test parallel run above supersedes
that run. Earlier malformed findings fixtures were corrected to provide the
existing required scan_id. Initial dependency collection needed the repo-pinned
jsonschema package. No implementation was changed to skip a failing Linux test.

## Worker setup and temporary files

The prescribed clone/fetch/branch/config commands succeeded. Each finished file
was committed and `git push origin codex/cli-w3` succeeded; all pushes were to
this branch. The initial interpreter attempt used unavailable `python`; subsequent
edit scripts used `python3`. No file changed in that failed attempt.

The original `/tmp` test failed with disk quota errors. On resumption,
`ls -ld /tmp/code-mode-PDifUB` reported the recorded test directory absent; the
harness had already removed it. No other thread's temporary directory was deleted.

```sh
mkdir -p .tmp && printf '\n.tmp/\n' >> .git/info/exclude
npm ci --ignore-scripts --no-audit --no-fund --prefix cli
TMPDIR=/workspace/codex-cli-w3/.tmp npm ci --ignore-scripts --no-audit --no-fund --prefix workspace
TMPDIR=/workspace/codex-cli-w3/.tmp /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pip install --target .tmp/deps 'jsonschema==4.26.0'
docker run -d --name cli-w3-tests -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=pooltest -p 127.0.0.1:55473:5432 postgres:16
```

All setup commands exited 0. The existing test interpreter was reused read-only;
missing pinned Python dependencies were installed only under this checkout's
ignored `.tmp/deps`. Test SQL used only the owned loopback PostgreSQL container.
Every resumed test command set TMPDIR to this checkout's `.tmp`; `.gitignore`
was not changed. No production SQL or model/provider check was performed.

## Official sources and license

GitHub's official server address and exact read tool names were verified on
**3 November 2026** from
[GitHub's official MCP server documentation](https://github.com/github/github-mcp-server#tools):
`list_issues`, `issue_read`, `list_pull_requests`, `pull_request_read`,
`actions_list`, `actions_get`. Server: `https://api.githubcopilot.com/mcp/`.
No workflow-trigger/write tool is bundled.

Seatbelt base source:
[openai/codex at 6b2a2757de696c2506ee460c49c66a8e2bed65e0](https://github.com/openai/codex/blob/6b2a2757de696c2506ee460c49c66a8e2bed65e0/codex-rs/sandboxing/src/seatbelt_base_policy.sbpl).
License: Apache-2.0, copied verbatim to `cli/src/seatbelt.LICENSE`.
Base SHA-256: `5103332ddb8885ee5e1926de6c0ef23a61f4e55e31297506ae05fa4e0b24ba74`.
The base file has zero changes. Tervory's separate adapter adds folder-only writes,
read-only system/runtime paths, Apple toolchain lookup, required ancestor metadata,
standard device descriptors, and explicit secret-path/network denies. The broad
upstream platform-default policy is excluded. No unsandboxed fallback was added.

## New terminal wording and Figma boundary

The only new fixed CLI string is `Undo [y/N] ` (one trailing space), matching the
existing Apply and Run prompts. It awaits founder wording approval in review.
All other terminal prompts/errors reuse existing strings.

No page, button, empty state, resultFields entry or error wording was added.
Plugin IDs map to `name`, states to `status`, and the count to `count`; `items`
uses the existing collection projection. Dedicated result labels for version,
installed flag, server approval, connection state and skill approval remain
waiting for an approved Figma frame. The Plugins install screen remains waiting
for approved page “7 · MCP”, #586; installation here uses existing /chats cards.

## CI and founder acceptance still outstanding

Read-only `gh pr list --repo Tervory-AI/tervory-tank --head codex/cli-w3 --json number,url,state`
returned `[]`. Claude has not opened this branch's PR. CI runs on PRs, so the
final-head Tank, Workspace, Linux CLI and macOS CLI CI results are **pending**.
This handoff does not substitute local checks for those required CI results.
No PR was opened, labeled or merged by this builder.

No founder screenshots exist for this work. The following founder runs remain
unverified, in his existing workspace:

1. Worker `tervory code`: request the repository's open Radix findings, confirm
   with y, verify the answer and same-thread $0 receipt in /chats, then ask about
   branch naming and verify AGENTS.md conventions.
2. Approve the GitHub server/read tools, connect the founder's account through
   the existing Radix Plugins panel, check plugins.list ready, confirm
   plugins.install with `{name: "github", version: "1.0.0"}`, check installed,
   then request/confirm open PRs in code mode and verify the $0 receipt.
3. Worker: one helper rename across three files, one Apply y, a Run y for its
   test, then /undo with y restoring all three. Mac: run a test after y and verify
   that reading ~/.ssh is refused. Verify /chats retains receipts and tool
   metadata without local file contents.

The implementation requires no new Coolify setting names. The outstanding
acceptance artifacts are the founder's live worker/browser/Mac results and
screenshots, plus final-head CI after Claude opens the PR.
