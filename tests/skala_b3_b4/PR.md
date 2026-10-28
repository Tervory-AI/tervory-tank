# Skala B3/B4: revalidate model changes and delay retirement

A policy model change now queues the evals of exactly the approved skills using
that task type. The same handler used by `/v1/skala/{id}/{version}/evals` runs the
cases against the captured new model, records `models_validated`, and moves a
failing approval to staging. Passing never approves or restores a version.

Approval now leaves the previous version in staging. Retirement requires a newer
approved version with 30 clean days; files remain available for confirmed rollback.

Branch: `codex/skala-b3-b4`, based on main `585a900`. Cloud workspace only.
Claude opens the PR. No GitHub API, main push, merge, deployment or production SQL.
Every finished repository file was committed and pushed separately.

## What changed (file and line)

- `tank/schema.sql:2099`: additive, idempotent model-change outbox, eval/model
  links and transactional policy trigger. The registry's task type is synced from
  `skill.yaml`; the worker also verifies the package's actual task type.
- `tank/skala_revalidation.py:25`: bind eval calls to the captured policy/model,
  reuse Tank's model/code helpers, retain platform receipts and suppress raw
  transport errors. No router/cache/shadow/judge calls.
- `tank/skala_revalidation.py:86`: record model evidence, eval result, demotion
  and job completion in one transaction. A single advisory-locked worker calls
  the existing eval handler; completed jobs do not run again. Start/stop hooks
  cancel the worker before Tank closes its resources.
- `tank/main.py:2990` and `:4190`: small eval-context/result and lifecycle hooks.
  An approved skill also moves to staging if its ordinary manual eval fails.
- `tank/skala.py:163` and `:322`: B3 bypasses saved model fixture answers so the
  new model is actually tested. Normal offline eval behavior stays available.
- `tank/skala.py:505` and `:559`: superseded approvals enter staging; state-only
  retirement consults the probation gate. Confirmed rollback accepts a present,
  previously approved version in staging or retired.
- `tank/skala_probation.py:10`: UTC 30-day window based on approval, failed evals
  and founder rollback history; pending revalidation also blocks retirement.
- `workspace/app/skala/library.ts:159`, `workspace/app/skala/view.tsx:349`:
  existing list follows the staging transition and exposes its existing rollback
  confirmation during probation. No new wording, page, layout or control.
- `tests/skala_b3_b4/test_lifecycle.py:1`: 21 offline lifecycle cases using real
  disposable Postgres and stubbed model transport. Existing approval/list tests
  were updated to expect probation rather than immediate retirement.
- `tests/skala_b3_b4/browser.mjs:1`: existing Skala UI rendered from the actual
  offline database export, with local assets and external requests blocked.

The existing `COPY *.py` in `tank/Dockerfile` includes both new modules. No
approved skill package, dependency, provider, secret or environment setting changed.
All new SQL is static with bound values; no SQL is constructed from strings.

## Decisions I made

- Use a transactional outbox trigger so both policy upserts and existing
  graduation/rollback writes are covered without rewriting routing or graduation.
  A rolled-back policy transaction creates no eval job. An unchanged model and
  initial policy creation without an effective previous model create none.
- Capture the full policy and affected approvals at swap time. Two quick swaps
  each validate their own model even if another model is already current. A later
  passing result leaves a previously demoted version in staging.
- Tenant override swaps record `policy_tenant_id`; eval inputs remain package
  fixtures and eval spend belongs to `PLATFORM_TENANT`. Nothing is sent cross-box.
- Use the existing Tank helper with provider fallback disabled and model identity
  checked. Code-skill graduations reuse the existing approved code executor and
  make no model call. Only calls requested by the evals run; no paid judging.
- Interpret B4 as a continuous 30 x 24-hour clean window. Any failed case resets
  that window, even if the aggregate met its pass mark. A founder rollback resets
  it for that skill. No newer approved version, no approval timestamp, or pending
  model validation means retirement is refused.
- Superseded versions retain their approval history in staging and remain
  restorable through the existing confirmed rollback action. Retirement changes
  state only; it never removes a directory.
- Registry/eval writes serialize with existing approval transactions. The worker
  prevents duplicate concurrent processing and atomically completes its result.
  A process crash before that commit can rerun an unfinished suite after restart;
  this is durable at-least-once processing, not a claim of crash-proof exactly-once
  provider billing.

## Commands and results

Disposable setup (internal Docker network, no published ports, no credentials):

```sh
docker network create --internal skala-b3-test
docker run -d --name skala-b3-pg --network skala-b3-test -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16
```

Lifecycle suite (schema applied twice by every database fixture):

```sh
docker run --rm --network skala-b3-test \
  -v /workspace/tervory-tank:/workspace/tervory-tank \
  -v /tmp/trigger-venv/lib/python3.12/site-packages:/test-packages:ro \
  -v /tmp/skala-b3-proof:/proof -w /workspace/tervory-tank \
  -e PYTHONPATH=/test-packages:/workspace/tervory-tank/tank:/workspace/tervory-tank \
  -e SKALA_B3_TEST_DATABASE_URL=postgresql://postgres@skala-b3-pg/postgres \
  -e SKALA_B3_PROOF_DIR=/proof --user 0 trigger-first-build:test \
  python -m pytest -q tests/skala_b3_b4/test_lifecycle.py --tb=short --disable-warnings
```

All 21 distinct lifecycle cases have passed across the full and focused runs.
The original 16-case suite passed. Adding five cases produced 19 passes and two
fixture errors (required eval details and FastAPI lifespan API). After fixing
those, the same Docker command with `-k 'database_probation or background_worker'`
passed both stored-history cases and exposed a Decimal/float assertion mismatch.
With that assertion corrected, `-k background_worker` passed. No completed test
was rerun solely for status. These fixture fixes are retained in the test file.

Coverage: exact task selection, no-op upserts, concurrent worker exclusion,
model snapshots, real handler reuse, demotion, no auto-approval, graduation,
policy rollback, transaction rollback, tenant override scope, code-only
execution, missing package, sanitized failure receipts, background start/stop,
day 29/day 30, failed-eval/rollback history, pending-validation refusal, and
rollback with package files unchanged after retirement.

Existing backend regression command used the same Docker runner/mounts, with
`POOL_SCHEMA_DATABASE_URL=postgresql://postgres@skala-b3-pg/postgres`:

```sh
python -m pytest -q tests/test_skala_eval_contract.py tests/test_skala_approval_safety.py --tb=short --disable-warnings
```

98 passed. The sole remaining test needed Node, absent in this Python container.
It passed in the cloud workspace with the existing graduation tests:

```sh
PYTHONPATH=tank:. /tmp/trigger-venv/bin/pytest -q tests/test_skala_approval_safety.py::test_founder_api_confirmation_and_origin_checks tests/test_t6_graduate.py --tb=short --disable-warnings
```

22 passed (the missing frontend test plus 21 graduation tests).

```sh
PYTHONPATH=tank:. /tmp/trigger-venv/bin/pytest -q tests/test_skala_page.py tests/test_chat_graduation.py --tb=short --disable-warnings
node --experimental-strip-types --test tests/skala_library.test.ts tests/skala_eval_record.test.ts
```

12 passed / 2 database-dependent chat tests skipped in the first command; all
12 Node cases passed in the second.

CI smoke command used the same Docker runner with `POOL_SCHEMA_DATABASE_URL`:

```sh
python -m pytest -q tests/test_secrets.py tests/test_tank_boots.py tests/test_tank_one_door.py --tb=short --disable-warnings
```

Tank's actual startup-twice test passed. 27 checks passed; three needed Git,
which the Python container lacks. The complete non-boot guards then passed in
the cloud workspace (29 passed):

```sh
PYTHONPATH=tank:. /tmp/trigger-venv/bin/pytest -q tests/test_secrets.py tests/test_tank_one_door.py --tb=short --disable-warnings
/tmp/trigger-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
(cd workspace && ./node_modules/.bin/tsc --noEmit --incremental false)
git diff --check 585a900
```

All passed. No paid model or provider request was made by these checks.

Browser command:

```sh
SKALA_ESBUILD_PATH=/tmp/trigger-browser-tools/node_modules/esbuild \
SKALA_PLAYWRIGHT_PATH=/tmp/trigger-browser-tools/node_modules/playwright \
SKALA_B3_PROOF_DIR=/tmp/skala-b3-proof node tests/skala_b3_b4/browser.mjs
```

Passed: failing score visible at 20% in staging, probation rollback requires
Confirm, 1440/375px, no horizontal overflow or browser errors. Reproduce against
saved rows by setting `SKALA_B3_PROOF_DIR=tests/skala_b3_b4/proof`.

Security commands (pinned existing CLIs):

```sh
PATH=/tmp/skala-intake-security/security-bin:$PATH python .github/scripts/security_scan.py gitleaks --base 585a900 --output /tmp/skala-b3-security
PATH=/tmp/skala-intake-security/security-bin:$PATH RUNNER_TEMP=/tmp/skala-intake-security GITHUB_WORKSPACE=/workspace/tervory-tank python .github/scripts/security_scan.py semgrep --base 585a900 --output /tmp/skala-intake-security/b3-results
PATH=/tmp/skala-intake-security/security-bin:$PATH python .github/scripts/security_scan.py osv --base 585a900 --output /tmp/skala-intake-security/b3-results
RUNNER_TEMP=/tmp/skala-intake-security GITHUB_WORKSPACE=/workspace/tervory-tank /tmp/skala-intake-security/security-bin/semgrep scan --config agents/radix/scanlib/semgrep.yml --metrics off --disable-version-check --baseline-commit 585a900 --json --output /tmp/skala-intake-security/b3-offline-semgrep.json tank/main.py tank/skala.py tank/skala_revalidation.py tank/skala_probation.py tests/skala_b3_b4/test_lifecycle.py
```

Gitleaks clean. Full Semgrep incomplete (exit 2, no JSON report); OSV incomplete
(RuntimeError from scanner). Bundled offline Semgrep rules passed: zero findings,
zero errors across all five listed Python files. This limited offline scan does
not replace the full CI security job. Hosted CI is pending Claude opening the PR;
no green-CI claim is made.

## Founder acceptance still required

No production changes were made. The founder must change a test task's model in
the control panel, then open/reload the existing Skala list and inspect its new
eval score/state. Verify a failing model leaves staging, and that only explicit
founder approval restores it. This live browser step is not claimed complete.

## Screenshots and evidence

These are **offline cloud browser screenshots**, not the founder's live browser.
They use database rows produced by the lifecycle test; no fixture is published.

- [1440px](proof/screenshots/skala-b3-b4-1440.png)
- [375px, scrolled to the changed versions](proof/screenshots/skala-b3-b4-375.png)
- [Actual offline Skala list export](proof/skills.json)
- [Failed then passing model evidence, still staging](proof/model-results.json)
