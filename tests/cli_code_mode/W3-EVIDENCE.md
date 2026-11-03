# CLI W3 — security review of PR #632

Branch: `codex/cli-w3`, workspace `/workspace/codex-cli-w3`.
Review baseline: `0b7a7e38ed734a6a772c76f8820f52719a8f157f`.
The one authorized main merge is `4192f8a9`; its conflict resolution is
`346b52f8`. Both permission filters were preserved. No second main merge,
rebase, force push, main push, production data change or model request was made.

The table below maps every review item to source and regression evidence.
The exact final head and final-head CI run/job links are recorded in PR #632
and the final handoff after this evidence commit, avoiding a self-referential SHA.
GitHub reported new conflicts after the authorized merge when the Tiger lane
expanded catalogue assertions in `tests/test_command.py` and
`tests/test_personal_tokens.py`. Manual head runs use the same CI jobs without
merging main again; these verify the branch head, not a new merge result.

## Security review changes by file and line

| Review | Source and regression evidence | Result |
| --- | --- | --- |
| 1(a) | `cli/src/code-tools.mjs:54`; `cli/test/code-mode.test.mjs:743` | Kill the process group at exit and again at close, including descendants holding pipes open. Darwin tests both inherited and redirected output. |
| 1(b) | `cli/src/code-tools.mjs:141`; `cli/test/code-mode.test.mjs:657` | On non-Linux, recheck canonical containment, secret paths, device and inode after reading the opened descriptor. A vanished opened file refuses. |
| 1(c), 7 | `cli/src/code-tools.mjs:209`; `cli/test/code-mode.test.mjs:678`, `:694` | Pin canonical parents and temp identity, build temp/target from that parent, verify before/after rename, then attempt every safe rollback independently and throw the existing refusal. |
| 1(d) | `cli/README.md:101`; `cli/test/code-mode.test.mjs:743` | Disclose that a child calling setsid() can escape macOS process-group cleanup while retaining its sandbox. |
| 2 | `.github/workflows/cli.yml:141` | macOS validates the actual profile and runs the complete CLI suite. Final-head CI is mandatory; see PR for final status and links. |
| 3 | `cli/src/code-mode.mjs:62`; `cli/test/code-mode.test.mjs:421` | Print sanitized/redacted raw tool/arguments JSON before the existing Confirm. |
| 4, 12 | `cli/src/seatbelt.mjs:50`, `:53`, `:39`, `:22` | Deny /usr/local/etc and /usr/local/var, including mapping and execution. Replace inherited broad execution with selected folder, system/runtime and Apple git paths. Only the literal root directory is readable for dyld startup; its descendants gain no permission. |
| 5 | `cli/src/code-tools.mjs:142`; `cli/test/code-mode.test.mjs:650`, `:735` | Refuse multi-link reads; actual Darwin outside-file hard-link creation must fail. |
| 6, 13 | `cli/src/code-tools.mjs:28`, `:439`; `cli/test/code-mode.test.mjs:709` | Mask/refuse SSH, keychains and keyrings. Deny home/.ssh/Keychains directory listing, .git/config and outside-file reads, and a host Unix socket inside the selected folder. Linux masks pathname sockets because bind mounts can otherwise expose them across network namespaces. |
| 8 | `cli/src/client.mjs:360`; `cli/test/code-mode.test.mjs:637`; `cli/test/client.test.mjs:17` | Only interactive === true can prompt. Missing, false or non-boolean flags cancel without reading a yes. The interactive harness declares its intent. |
| 9 | `tank/command.py:2104`; `tests/test_command_code.py:228` | Exact requested Repository project notes DATA label, including not-instructions and forbidden authority categories. |
| 10 | `cli/src/code-mode.mjs:11`; `cli/test/code-mode.test.mjs:459` | Skip symlinked, oversized or non-UTF-8 notes with one notice and continue without sending project notes. |
| 11 | `tank/command.py:777`, `:1453`, `:2121`; `tests/test_plugins.py:103` | Store origin=code before card events. Re-narrow the actor with current installed plugins at Confirm. A real plugins.remove Confirm revokes the earlier code card while ordinary chat retains its catalogue. |
| 14 | `tank/plugins.py:56`, `:76`; `tests/test_plugins.py:220` | SafeLoader subclass rejects root/nested duplicate keys and merged duplicates; unsafe YAML objects remain rejected. |
| 15 | `tests/test_plugins.py:20`, `:45`, `:87`, `:111`; `tests/test_command_code.py:18`, `:102`; `cli/test/code-mode.test.mjs:126`, `:320` | Explicit placeholder fixture values, including synthetic token suffixes and a placeholder-derived UUID. The runtime test compares SHA-256 before/after instead of broad error text. |
| 16 | `cli/src/seatbelt.NOTICE:1`; `cli/README.md:108` | Ship the pinned upstream NOTICE beside seatbelt.LICENSE; both are included by the existing src/ package rule. |
| 17 | `cli/src/code-tools.mjs:19`, `:22`; `cli/test/code-mode.test.mjs:753` | Redact AWS secret assignments, including quoted JSON keys, and entire private-key PEM blocks, including truncated blocks, before results leave. |
| CI fixes | `tank/plugin_args.py:1`; `tank/command.py:1259`; `tank/plugins.py:13`; `tank/schema.sql:2842` | Separate lightweight card arguments from manifest initialization to remove the access-first import cycle; preserve the canonical schema-generator boundary. Existing Docker COPY *.py includes the new module. |
| Head verification | `.github/workflows/cli.yml:3`; `.github/workflows/ci.yml:5`; `tests/test_ci_minutes_workflows.py:40` | Manual full-head CI while a newly conflicting PR cannot start pull_request jobs. Security compares against origin/main; no check is disabled. |

## Current local verification

All tests used `TMPDIR=/workspace/codex-cli-w3/.tmp`. The folder is excluded only
in `.git/info/exclude`. No shared /tmp folder was deleted; no old code-mode
folders were present when checked. No quota blockage remained.

- Full Command/MCP/plugin/schema/secrets Python regression suite: **431 passed**.
- Full CLI suite: **107 passed, 3 Darwin-only skips** on Linux.
- Preflight macOS CI at `3bd51ca2`: **110 passed, no skips**; final-head links follow in the PR.
- Dedicated actual-plugin-removal and YAML suite: **11 passed**.
- Workflow scope and manual-head tests: **67 passed**.
- Schema-generator identity regression: **1 passed**.
- Access-first module import, Ruff E9/F, node syntax, version guard and diff whitespace checks passed.
- The owned disposable Postgres container was removed after tests.

The CLI version guard accepts 0.2.0 -> 0.4.0. The upstream base stays byte-for-byte
unchanged: SHA-256 `5103332ddb8885ee5e1926de6c0ef23a61f4e55e31297506ae05fa4e0b24ba74`.
License and NOTICE come from openai/codex commit
`6b2a2757de696c2506ee460c49c66a8e2bed65e0`.

## Terminal wording for the founder

New in this review: `AGENTS.md skipped: Code tool refused.` followed by newline.
The original implementation also introduced `Undo [y/N] ` (one trailing space).
Confirm arguments are raw JSON data, not new fixed copy. There are no new
Workspace screens, labels or presentation components.

## Original implementation evidence (historical)

The following record predates this security review. Its old SHA, line references,
Mac/CI limitations and original local counts are historical, superseded above and
by the final-head CI links in PR #632.

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
