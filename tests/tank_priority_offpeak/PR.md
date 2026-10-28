# Make urgent requests immediate and offpeak requests durable

Branch: `codex/tank-priority-offpeak`, originally started from main `73a0e2f`.
Synchronized with current main `7a13687de256896c488a0f28e0906fbcbce5b046` in
`98e801ea606d394377b6e7356e916ae53db7c81e`; that source/test tree is now verified.
The only merge conflict was the end of `tank/schema.sql`: both the priority queue
and main's Skala/memory additions were retained. No implementation was rebuilt.
Claude opens the PR; the founder merges. No deployment, production SQL, secret
inspection, real model call or owner-laptop access was used. Read-only GitHub
metadata was used during this continuation to establish branch ownership.


Urgent requests bypass cache lookup, embedding-cache work, RouteLLM observation
and candidate shadows. Standard routing remains unchanged. An explicit offpeak
request that needs a model gets a durable tenant/region-scoped job and ledger
receipt. The existing worker dispatches it in the configured window, or promptly
when no window is configured. Supported providers use Tank's existing batch
submission, polling, reservations and fallback implementation.

A queued receipt has unknown cost, then records dispatch time and the delivered
answer's cost on the **same ledger id**. The existing savings columns consume
that cost. Deferred Command answers return to their original thread even after
the browser disconnects; existing text and controls are retained.

## What changed

| File and line | Change |
| --- | --- |
| [tank/main.py:599](../../tank/main.py#L599), [1067](../../tank/main.py#L1067) | Priority values; urgent bypass; preflight, cap checks and durable offpeak handoff; dispatch timestamps and usage-based offpeak receipts. |
| [tank/main.py:2421](../../tank/main.py#L2421), [2443](../../tank/main.py#L2443) | `/v1/route` job reply and tenant-scoped `/v1/route/jobs/{id}` polling. |
| [tank/main.py:2538](../../tank/main.py#L2538), [2653](../../tank/main.py#L2653), [2788](../../tank/main.py#L2788) | Reuse batch preparation/reservations, retain requested priority and receipt id, run queue maintenance in the existing worker. |
| [tank/priority_queue.py:48](../../tank/priority_queue.py#L48), [100](../../tank/priority_queue.py#L100), [150](../../tank/priority_queue.py#L150) | Frozen-clock-compatible windows, provider usage pricing, enqueue/dispatch/recovery. Advisory claims prevent duplicate sends; per-process serialization avoids pool exhaustion. |
| [tank/priority_queue.py:238](../../tank/priority_queue.py#L238) | Durable, idempotent Command completion notifications. |
| [tank/schema.sql:2099](../../tank/schema.sql#L2099) | Additive queue schema plus ledger `sent_at` and `offpeak_job_id`; existing `priority` records the requested value. |
| [litellm/config.yaml:107](../../litellm/config.yaml#L107), [128](../../litellm/config.yaml#L128) | Plain per-model DeepSeek windows and price multipliers, available through LiteLLM model metadata. No environment settings or keys. |
| [tank/command.py:132](../../tank/command.py#L132), [383](../../tank/command.py#L383), [414](../../tank/command.py#L414) | Optional priority; persist deferred thread context; reuse existing answer/receipt/event path. |
| [workspace/app/chats/api/[...path]/route.ts:86](../../workspace/app/chats/api/%5B...path%5D/route.ts#L86) | Pass an explicitly supplied priority through the existing proxy. No new page text or controls. |
| [tests/test_tank_priority_offpeak.py:1](../test_tank_priority_offpeak.py#L1) | 34 offline priority tests, including real SQL, HTTP contracts, existing savings projections and Command completion. |

## Decisions I made

- Free code/cache results can finish immediately. Urgent skips cache reuse and all
  shadow work; an approved code policy remains an approved code policy. This does
  not substitute a new paid model for a skill.
- Explicit `priority=offpeak` is consent to wait, including when `interactive` was
  left at its default. It can use a provider batch below `TANK_BATCH_MIN`.
  **Standard batch eligibility and minimums are unchanged.** OpenAI, Vertex and
  Anthropic reuse the existing adapters and their existing batch rates. Discounts
  are not stacked with time-of-day pricing.
- Submit offpeak requests through `/v1/route` or the existing Command turn API.
  `/v1/route/batch` rejects offpeak items with the correct route in its response,
  rather than falsely reporting a queued item as completed. Urgent items submitted
  through `/v1/route/batch` still run immediately and never enter a batch.
- The existing MoA foreground-only restriction is preserved: `/v1/route` rejects
  offpeak on a MoA-enabled policy. Standard MoA requests retain their existing path.
- The new queue uses the existing ten-second maintenance loop, with an immediate
  wake-up on acceptance. No separate service, cron job, key or setting is needed.
  Policy changes cancel unsent work. An interrupted dispatch is marked uncertain
  and is never automatically purchased again. Window boundaries are checked again
  immediately before a normal dispatch.
- DeepSeek configuration contains the verified recurring UTC offpeak periods:
  weekdays 00:00–01:00, 04:00–06:00 and 10:00–24:00; all weekend hours. Endpoints are
  start-inclusive/end-exclusive. The multiplier is 0.5. The provider also offers
  public-holiday offpeak pricing; no holiday calendar is guessed or downloaded.
  Verified additional dates can be listed in the plain model settings. Until then,
  holiday requests use these guaranteed recurring periods.
- LiteLLM's static peak-price header cannot establish a time-of-day discount.
  DeepSeek receipts use reported input/output/cache-hit tokens and the configured
  published rates at dispatch. Missing usage evidence, or an unexpected answering
  model, leaves cost unknown. No missing receipt is presented as free work.
- Windows are carried through sanitized `/model/info` roster metadata, since Tank's
  production image does not contain the LiteLLM config file. The pinned LiteLLM
  `1.106.4` source (`ea7ca16dbc3904d9e59a9505f379a2ca3091821f`,
  `litellm/types/router.py:239–321`) permits extra ModelInfo fields. No upgrade.

Pricing source checked during this work:
[DeepSeek official pricing](https://api-docs.deepseek.com/quick_start/pricing/).
Existing peak cache-miss rates remain unchanged; the config adds the published
cache-hit rates and offpeak multiplier.

## Commands and results

All execution was on the managed cloud workspace. PostgreSQL below is a disposable
local test server. Model responses and usage are stubbed; no model was downloaded
or called. Full captured output: [verification.txt](verification.txt).

```sh
git fetch origin main
git switch -c codex/tank-priority-offpeak origin/main
# exit 0; starting main 73a0e2f

git push -u origin codex/tank-priority-offpeak
# exit 0; every finished file was committed and pushed, with subsequent git push commands.
# No push failed. The branch history preserves each step.

POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_tank_priority_offpeak.py tests/test_tank_ladder.py tests/test_tank_batch_providers.py tests/test_tank_semantic_cache.py tests/test_tank_routellm.py tests/test_tank_shadow_coexistence.py tests/test_command.py tests/test_command_streaming.py tests/test_tank_one_door.py tests/test_secrets.py tests/test_tank_boots.py --tb=short
# exit 0: 250 passed, 6 warnings in 135.63s.
# Includes all 34 new priority tests and a real Tank boot twice on the same database.

/workspace/worker-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# exit 0: All checks passed!

git diff --check origin/main
# exit 0; no output.

# cwd: /workspace/tervory-tank/workspace
./node_modules/.bin/tsc --noEmit --incremental false
# exit 0; no output.

# cwd: /workspace/tervory-tank
PATH=/tmp/priority-security-bin:$PATH /workspace/worker-venv/bin/python -m unittest discover -s tests/ci_security -p test_security.py -q
# exit 0: Ran 34 tests; OK.

PATH=/tmp/priority-security-bin:$PATH /workspace/worker-venv/bin/python .github/scripts/security_scan.py gitleaks --base 73a0e2f --output /tmp/priority-security-results
# exit 0: gitleaks: clean; sanitized findings [].
```

Earlier checks are not hidden: invoking the `pytest` executable directly gave
211 passes and two `ModuleNotFoundError: agents` failures. Using CI's
`python -m pytest` invocation resolved the import path without changing the tests.
The first security-policy run had three errors because Gitleaks was absent. The
repo-pinned free Gitleaks 8.30.1 release was downloaded from github.com and its
SHA-256 verified against `.github/scripts/install-security-tools.sh`:
`551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`.
The rerun and redacted branch scan passed. No GitHub API was used.

GitHub CI itself, Semgrep, OSV and the Workspace production build are not claimed
as run. The recorded checks above are local cloud checks.

## Founder-browser proof — pending

**Not done under the founder's definition yet.** No deployment or founder-browser
session was performed, and no screenshots are available or fabricated.

After founder review/merge/deployment, use a real request in the existing `/chats`
thread with a selected DeepSeek model, outside the configured window. Supply
`"priority":"offpeak"` in the existing turn request body. There is no new UI
selector: the existing browser request can be resent with that one field added.
Use an uncached real question so the free ladder does not answer immediately.

Capture the existing ledger showing that job as `queued` with unknown cost, then
its dispatch/delivered state and price when the window opens. Capture the answer
and receipt in the same thread. The `sent_at` field and tenant-scoped job endpoint
provide the dispatch timestamp; savings use the existing columns. Attach those
founder screenshots to this PR before calling the acceptance condition complete.

## Current-main continuation: exact commands and results

Execution directory: `/tmp/tervory-priority-resume` on Boston. This is an isolated
checkout, not the production tree. No existing branch was reset. The existing
remote branch had no PR and was continued in place.

```sh
gh api repos/Tervory-AI/tervory-tank/commits/main --jq .sha
gh pr list -R Tervory-AI/tervory-tank --state open --limit 100 --json number,title,headRefName,url
gh api repos/Tervory-AI/tervory-tank/branches --paginate --jq '.[].name'
gh api repos/Tervory-AI/tervory-tank/compare/main...codex/tank-priority-offpeak --jq '{status,ahead_by,behind_by,commits:[.commits[]|{sha,message:.commit.message}],files:[.files[].filename]}'
gh pr list -R Tervory-AI/tervory-tank --state all --head codex/tank-priority-offpeak --json number,state,title,url
# Main 7a13687; existing branch ef0fb502, 25 ahead/18 behind; no matching PR.

git clone --filter=blob:none --no-checkout https://github.com/Tervory-AI/tervory-tank.git /tmp/tervory-priority-resume
git -C /tmp/tervory-priority-resume checkout codex/tank-priority-offpeak
git config user.name 'Codex'
git config user.email 'codex@users.noreply.github.com'
git merge origin/main
# Preserved both appended schema blocks; all other files merged automatically.
# Initial merge exited 128 for missing local committer identity; resolved above.
# Merge then exited 1 for schema conflict; resolved as documented.

python3 -m venv /tmp/tervory-priority-python
/tmp/tervory-priority-python/bin/pip -q install uv
/tmp/tervory-priority-python/bin/uv python install 3.12
/tmp/tervory-priority-python/bin/uv venv --python 3.12 /tmp/tervory-priority-312
/tmp/tervory-priority-python/bin/uv pip install --python /tmp/tervory-priority-312/bin/python -r tank/requirements.txt pytest==9.1.1 pytest-asyncio==1.4.1 ruff==0.17.2
sudo -n docker run --detach --rm --name tervory-priority-test-pg --publish 127.0.0.1:55461:5432 --env POSTGRES_HOST_AUTH_METHOD=trust postgres:16.15
# Setup exits 0; Python 3.12.16. Disposable local test data only.

POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55461/postgres /tmp/tervory-priority-312/bin/python -m pytest -q tests/test_tank_priority_offpeak.py tests/test_tank_one_door.py tests/test_tank_boots.py --tb=short > /tmp/priority-merge-tests.txt 2>&1
# Exit 0: 62 passed, 12 warnings in 66.75s.
git commit -m 'Merge current main while preserving priority queue and memory schemas'
git push origin codex/tank-priority-offpeak
# Exit 0: 98e801ea606d394377b6e7356e916ae53db7c81e published.

POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55461/postgres /tmp/tervory-priority-312/bin/python -m pytest -q tests/test_tank_priority_offpeak.py tests/test_tank_ladder.py tests/test_tank_batch_providers.py tests/test_tank_semantic_cache.py tests/test_tank_routellm.py tests/test_tank_shadow_coexistence.py tests/test_command.py tests/test_command_streaming.py tests/test_tank_one_door.py tests/test_secrets.py tests/test_tank_boots.py --tb=short > /tmp/priority-resume-regression.txt 2>&1
# Exit 0: 250 passed, 12 deprecation warnings in 316.25s.
/tmp/tervory-priority-312/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# Exit 0: All checks passed!
git diff --check origin/main
# Exit 0, no output.
```

Full current output is appended in `verification.txt`, separately from the original
cloud proof. `git diff --check --cached` during the merge reported whitespace in
incoming main's untouched feed fixture and Tiger skill; these are outside this
branch's diff against main and were preserved. Final branch whitespace check is clean.
The supplied PUSH brief filename was not present on this branch (Contents API
404); the complete assigned job supplied directly in chat was used instead.

The official DeepSeek pricing page was rechecked on October 28: recurring UTC
windows and the 0.5 multiplier still match the implementation. No API contract,
model weight, key or provider was changed during this continuation.

Independent reviewer inspected synchronized `98e801ea` read-only and reported no
actionable correctness finding so far. Final PR/head/check review remains pending
Claude creating the PR. No founder screenshots exist for this continuation; the
queued-to-sent ledger, same-thread answer/receipt and actual paid amount remain
explicit founder-browser acceptance requirements, not offline-test claims.

## Checkpoint — 2026-10-28 16:42:06 PDT (UTC-07:00) / 2026-10-28 23:42:06 UTC

- Branch: `codex/tank-priority-offpeak`; local and remote head at checkpoint:
  `8e38c4c7d327b848fe02427de0e3e378dcec40cc`. This entry is append-only; earlier evidence remains intact.
- Tested source SHA: `98e801ea606d394377b6e7356e916ae53db7c81e`.
  Subsequent changes through the checkpoint head affect only this report and
  `verification.txt`. Independent reviewer confirmed that exact documentation-only
  diff and reported no outstanding actionable code finding.
- Settled checks: focused selection **62 passed**, 12 deprecation warnings,
  66.75s; full affected selection **250 passed**, 12 deprecation warnings,
  316.25s. Ruff and branch whitespace checks passed. Exact commands and captured
  results are above and in `verification.txt`; these tests were not repeated.
- Fresh commands: `git status --short` exited 0 with no output;
  `git rev-parse HEAD` and
  `git ls-remote origin refs/heads/codex/tank-priority-offpeak` exited 0 and
  agreed on the checkpoint head;
  `gh pr list -R Tervory-AI/tervory-tank --state all --head codex/tank-priority-offpeak --json number,state,url,headRefOid`
  exited 0 and returned `[]`.
- Publication: implementation and proof are pushed on the existing branch.
  No PR exists at this checkpoint; Claude must open it using this report.
  Exact PR-head hosted checks and final PR review remain pending. Founder merges.
- Open code findings: none from independent branch review. Test gaps: hosted
  PR checks and founder-browser acceptance; no new offline failure is outstanding.
- Founder acceptance remains pending: outside the configured window submit a real
  offpeak turn, observe queued then sent ledger evidence, actual dispatch time
  and paid amount, and the answer/receipt in the same chat. No model calls,
  deployment, production migration, live scan or founder screenshots were made
  during this reporting checkpoint. Offline checks are not live acceptance.

This report update is committed and pushed separately after the recorded head;
its resulting SHA is supplied to the independent reviewer in the handoff.

## Publication checkpoint — 2026-10-28 16:47:20 PDT (UTC-07:00) / 2026-10-28 23:47:20 UTC

Draft PR [#424](https://github.com/Tervory-AI/tervory-tank/pull/424) now exists,
opened by the coordinator at `0f7d7da732e7ce9094879b455860f10f54c7dae4` on
`codex/tank-priority-offpeak`. This supersedes the earlier pending Claude handoff;
those historical entries remain intact. Founder merges. The PR is attached to
this chat.

Fresh command: `gh pr view 424 -R Tervory-AI/tervory-tank --json headRefOid,isDraft,state,statusCheckRollup,url`
exited 0: OPEN, draft, expected head. CI security/Tank/Workspace and CodeQL are
running; changes passed, runner/savings skipped. No completed failure was reported.
The publication report commit will advance the head and require its own hosted
check status; earlier running checks are not claimed as final-head results.

Independent reviewer confirmed the previous append-only report head `0f7d7da7`
and reported no new code finding. Tested source remains `98e801ea`; settled
62/250 offline results are unchanged. No tests or implementation changes were
repeated for publication. Actual founder queued-to-sent ledger and same-thread
answer/receipt evidence remain missing; no live acceptance is claimed.

This checkpoint is committed/pushed, then the PR description is updated from this
file with `gh pr edit 424 -R Tervory-AI/tervory-tank --body-file tests/tank_priority_offpeak/PR.md`.
The resulting report-only head is sent to the independent reviewer.

## Publication transport correction — 2026-10-28 16:47:52 PDT (UTC-07:00) / 2026-10-28 23:47:52 UTC

Published report head: `24c176ec3c1579a1f1d395bae7f71e42fb0086d4`.
The planned `gh pr edit --body-file` command failed with GraphQL's deprecated
`repository.pullRequest.projectCards` field. It did not update the description.
Recovery succeeded with `gh api --method PATCH repos/Tervory-AI/tervory-tank/pulls/424 --input - --jq '{number,html_url,head:.head.sha}'`,
passing structured JSON `body` read from this report on stdin. Response: PR424,
expected URL and head24c176ec. No credentials or shell-interpolated body involved.
This report-only correction is pushed separately and the REST update is repeated
with its current content. No implementation changes or tests repeated.
Hosted checks and founder-browser evidence remain pending as above.
