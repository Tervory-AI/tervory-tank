# Tisan T3: private build memory and client request/sign-off cards

Branch: `codex/tisan-t3-requests`; isolated checkout `/workspace/codex-tisan-t3`.
Base: `1ad2c794f9d9db7999a33c639d62ae156e638622` (main includes #599, #604 and
#603). Claude opens the PR and the founder merges. None of those prior PRs is
reimplemented. No page, component, visible wording, email or approved skill
package was changed. The existing generic /chats cards carry the results.

## What changed

| File and line | Behavior |
| --- | --- |
| `agents/tisan/builder.py:256` | Retain the known slug and allocated build number when checks fail; no failed archive is fabricated. |
| `agents/tisan/builder.py:269` | After a passed, failed or refused build, attempt one `ctx.memory.remember` call with kind `build`, measured checks/details and confidence 1.0. Evidence contains the job ID and actual archive filename when present. The returned record ID is `memory_id`. An outage logs its exception class only and preserves the build outcome. |
| `agents/tisan/publish.py:150` | Room-key-only, tenant-and-slug-bound `/publish/latest` reads the existing promotion journal, selecting only succeeded publish operations. No success returns a status with no URL or sentence. No Coolify/GitHub call is made. |
| `tank/tisan_requests.py:12` | Four client tools and a strict forward transition table: requested to changes_requested or accepted; changes_requested to accepted; accepted terminal. |
| `tank/tisan_requests.py:41` | Fixed same-room preview read; validate and return only succeeded build, full commit and HTTPS staging origin. |
| `tank/tisan_requests.py:67` | Literal parameterized SQL, tenant-scoped transactions, row locking, immutable events and operation identity prevent cross-tenant or refused writes. Feedback binds text to the latest succeeded build; sign-off after feedback needs a newer build and different commit. |
| `tank/tisan_requests.py:128` | Explicit `tisan.request`/`preview`/`feedback`/`handover` commands propose existing cards with a code receipt, without calling a model. Request and feedback take JSON arguments; preview and handover also accept a plain request UUID. |
| `tank/tisan_requests.py:148` | Existing authenticated Actor/require_tool/confirmation pattern; three mutations require the exact executing Confirm-card binding. Preview is a $0 read. Each successful operation returns a real $0 code ledger receipt. |
| `tank/tisan_requests.py:188` | Existing long-build cards can read their owned room job's completed checks and memory ID. Foreign tenant/job results and receipt injection are rejected; no job is resubmitted. |
| `tank/command.py:28`, `:55`, `:120` | Expose the four client tools to the founder and verified tenant admins only, like Trigger. Ordinary members retain their current tools, and tisan.build remains founder-only. |
| `tank/command.py:401` | Hydrate a confirmed founder build card on the existing thread read; the existing browser polling picks up completed measurements and memory_id. No UI changes. |
| `tank/command.py:488`, `:1047`, `:1227`, `:1456`, `:1650` | Deterministic planning, request arguments derived from the existing TisanBuildArgs fields, ADAPTERS, actor-supplied identity and confirmed dispatch. Clients cannot inject tenant/user/region, plan/copy/media or approval fields into a request. |
| `tank/main.py:4197` | Mount the client router. `_startup:753` is unchanged and still applies the complete additive schema through its existing admin/raw pool selection. |
| `tank/schema.sql:2595` | Add requests and request events before the generated memory block. Follow personal_tokens exactly: only join existing RLS, FORCE it and install both tenant policies; leave legacy installations staged. |
| `tests/test_tisan_requests.py:44` | Fake-Hermes outcome/outage tests, real Confirm dispatch, actual disposable Postgres/RLS enforcement, journal preview filtering, forward-state/event and receipt checks, tenant isolation, and long-build card hydration. |
| `tests/test_tisan_builder.py:180` | Update the existing failed-build assertion for its now-retained measured identity; checks and no-archive assertions remain. |

Build memory remains in Hermes's existing client tier, `agent_tisan.memory_records`.
There is no platform publication. A refusal before allocation records a null
build number; an outcome with no archive supplies no invented filename. Original
check details are retained, including the result's overall failure detail.
A memory outage may leave no memory_id, but never turns a completed build into
a failure. Runtime execution errors record their class rather than raw messages.

A request stores exactly name, slug, locale, brand and request. The existing
founder build can use this returned input with accepted copy/media as before.
Nothing builds automatically. Feedback is the change request; handover records
client acceptance only. Neither path promotes, deploys, transfers a repository
or sends anything. There are no backward or repeated state transitions.

## Q1 dependency and k6

Item 3 is **skipped as explicitly instructed**: `scaffold.run_checks` on main
`1ad2c794` contains only its existing npm checks, with no Q1 quality-server checks.
No scaffold run_checks, template quality file, Dockerfile, k6 pin or image was
changed. There is no k6/image-size result to claim. Q1 must be merged before that
separate gated item can run.

## Exact commands and observed results

All commands ran in this task's own checkout. Git was configured locally with
the authorized Codex identity. Every finished file was committed and normally
pushed on this branch after fetching and merging origin/main. No force push,
merge to main, rebase, previous-work deletion, live setting change or deployment
was performed. All pushes succeeded.

Initial setup used the founder's exact clone/fetch/checkout/config command.
Every existing file named in the brief was checked with `ls`; all existed.
The earlier CLI attempt failed before filesystem operations with the temporary
sandbox quota error already reported; this retry succeeded.

The initial local test interpreter lacked jsonschema. The installed CRM test
environment had jsonschema but lacked selectolax. The repository-pinned missing
jsonschema was therefore installed only into this checkout's ignored `.git`:

```sh
mkdir -p .git/t3-tmp
TMPDIR=/workspace/codex-tisan-t3/.git/t3-tmp /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pip install --no-cache-dir --target .git/t3-deps jsonschema==4.26.0
```

Exit 0. No global/shared Python environment or dependency lock was changed.

```sh
docker run --detach --rm --name codex-tisan-t3-postgres --publish 127.0.0.1::5432 --env POSTGRES_HOST_AUTH_METHOD=trust --tmpfs /var/lib/postgresql/data postgres:16.15
docker exec codex-tisan-t3-postgres createdb -U postgres tisan_t3_test
docker port codex-tisan-t3-postgres 5432
```

Exit 0; owned disposable Postgres bound only `127.0.0.1:32843`. All test DB URLs
below use this server with trust authentication, not credentials or production.
The existing Command fixture creates/drops its own random databases there and
applies the real Tank schema twice, testing empty startup and idempotency.

```sh
PYTHONPATH=tank:.git/t3-deps POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_tisan_requests.py --disable-socket --allow-hosts=127.0.0.1,localhost --basetemp=.git/t3-test-tmp
```

Initial focused result: **9 passed in 4.95s**. Adding the actual Confirm-card
and enforced-RLS proofs gave **11 passed in 10.41s**. The final variant including
long-build card isolation and strict forward transitions, with basetemp
`.git/t3-final-tmp`, gave **13 passed in 14.09s**, three existing Pydantic warnings.

```sh
PYTHONPATH=tank:.git/t3-deps POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_tisan_*.py tests/tisan_j4/ tests/tisan_promotion/ tests/test_command.py --disable-socket --allow-hosts=127.0.0.1,localhost --basetemp=.git/t3-regression-tmp
```

Initial result: **2 failed, 329 passed, 11 skipped in 79.37s**. The first failure
was the existing assertion that lacked the new failed-build slug/build fields;
that assertion now verifies the retained identity. The second was a missing
local Workspace TypeScript installation for the unchanged Node gold-action test.
From `workspace/`, installed only the repository's lockfile packages:

```sh
npm ci --no-audit --no-fund --cache /workspace/codex-tisan-t3/.git/t3-npm-cache
```

Exit 0, 45 packages. Repeated the exact focused regression command:
**331 passed, 11 skipped, 25 warnings in 86.38s**. Opt-in real npm/browser/quote
Postgres cases account for the skips; they are not claimed as passes.

After adding long-build hydration, ran the actual card/Command regressions:

```sh
PYTHONPATH=tank:.git/t3-deps POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_tisan_requests.py tests/test_command.py --disable-socket --allow-hosts=127.0.0.1,localhost --basetemp=.git/t3-cards-tmp
```

**96 passed, 14 warnings in 59.17s**.

```sh
PYTHONPATH=tank:.git/t3-deps /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
PYTHONPATH=tank:.git/t3-deps /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_secrets.py tests/test_agent_memory_records.py::test_all_agent_schema_files_use_one_generator --disable-socket --allow-hosts=127.0.0.1,localhost
git diff --check
```

Ruff **All checks passed**; **3 passed in 38.61s**; diff check empty. Earlier
changed-file lint identified one old unused publish import and one unused new
test import; both were removed before these passing checks. Individual touched
Python files also passed `python3 -m py_compile` before their commits.

## Founder acceptance still required

No founder test-tenant flow, staging URL opening or screenshots have been
performed by this branch. No actual client request, preview, change request or
sign-off was written to production, and no live build, model call, publish,
Coolify mutation or email was made. Offline measurements are not live acceptance.

After founder merge, with existing skill approval, accepted Trigger copy and
configured staging resources, the founder must use his test tenant in /chats:
request and Confirm; use its input for the existing founder build/publish; inspect
the preview link in his browser; Confirm feedback; rebuild/republish and inspect
the new preview; then Confirm handover. Retain the actual build memory IDs and
checks, staging build numbers/SHAs, immutable events and real browser screenshots.
Verify a second tenant cannot read the requests, previews, cards or memories.
No invented screenshots are supplied. Hosted PR CI and separate review remain
required; Claude opens the PR and the founder merges.

Deploy-on-merge: Tank's source/schema changes deploy the main Tank stacks and
changes under `agents/tisan/` deploy Tisan and its regional copies under the
existing changed-path rules. No runtime configuration file or setting was changed.

## Final focused proof and full-suite attempt

Repeated the complete Tisan/Command command after all source changes, with
basetemp `.git/t3-proof-tmp`: **333 passed, 11 skipped, 25 warnings in 103.97s**.
Also explicitly enabled the existing opt-in quote Postgres tests:

```sh
PYTHONPATH=tank:.git/t3-deps J4_TEST_POSTGRES_PORT=32843 /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_tisan_quotes_postgres.py --disable-socket --allow-hosts=127.0.0.1,localhost --basetemp=.git/t3-j4-tmp
```

**6 passed in 2.54s** on the owned disposable cluster.

Prepared the other CI test databases with:

```sh
docker exec codex-tisan-t3-postgres createdb -U postgres market_test
docker exec codex-tisan-t3-postgres createdb -U postgres radix_passive_test
```

Both exited 0. Invoked the checked-in full runner with the same disposable
server for every CI database setting:

```sh
PYTHONPATH=/workspace/codex-tisan-t3/tank:/workspace/codex-tisan-t3/.git/t3-deps \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test \
ZENAS_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test \
MEMORY_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test \
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test \
RLS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test \
SKALA_B3_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test \
SKALA_INTAKE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test \
TIGER_MAIL_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test \
RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test \
TRAINING_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test \
RADIX_PASSIVE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/radix_passive_test \
DATABASE_URL=postgresql://postgres@127.0.0.1:32843/market_test \
SUITE_WORKERS=3 SUITE_JUNIT_DIR=/workspace/codex-tisan-t3/.git/t3-junit \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python .github/scripts/offline_suite.py
```

The runner's default main budget expired at **1080s**, near 98% progress, and
returned **124**. It printed failing-test progress, but aborted before a final
main summary/JUnit file, so no main pass count is claimed. Its separate runs
finished: **Tiger G5 46 passed, 42 warnings in 28.41s**, and **Zenas regulation
alerts 40 passed, 14 warnings in 25.43s**. Overall runner exit 1, 1143s.

The main portion is being rerun using the same checked-in runner's
`clean_env`, `pytest_args` and `run` helpers with three workers and a 2160-second
local budget, with `GITHUB_ACTIONS=true` for per-failure source locations.
This is a pending diagnostic, **not a green full-suite claim**. Its complete
outcome and exact helper invocation will be appended before final handoff.
