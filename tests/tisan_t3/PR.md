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
| `tank/tisan_requests.py:12` | Four client tools; requested to changes_requested or accepted; changes_requested to itself only after a newer build and different commit, or to accepted; accepted terminal. |
| `tank/tisan_requests.py:41` | Fixed same-room preview read; validate and return only succeeded build, full commit and HTTPS staging origin. |
| `tank/tisan_requests.py:67` | Literal parameterized SQL, tenant-scoped transactions, row locking, immutable events and operation identity prevent cross-tenant or refused writes. Feedback binds text to the latest succeeded build; sign-off after feedback needs a newer build and different commit. |
| `tank/tisan_requests.py:128` | Explicit `tisan.request`/`preview`/`feedback`/`handover` commands propose existing cards with a code receipt, without calling a model. Request and feedback take JSON arguments; preview and handover also accept a plain slug. Preview, feedback and handover select the tenant’s newest open request for that slug. |
| `tank/tisan_requests.py:148` | Existing authenticated Actor/require_tool/confirmation pattern; three mutations require the exact executing Confirm-card binding. Preview is a $0 read. Each successful operation returns a real $0 code ledger receipt. |
| `tank/tisan_requests.py:188` | Existing long-build cards can read their owned room job's completed checks and memory ID. Foreign tenant/job results and receipt injection are rejected; no job is resubmitted. |
| `tank/command.py:28`, `:55`, `:120` | Expose the four client tools to the founder and verified tenant admins only, like Trigger. Ordinary members retain their current tools, and tisan.build remains founder-only. |
| `tank/command.py:401` | Hydrate completed build result data on the existing thread read. Existing card labels display build_id, url and status. request_id, commit, memory_id and checks remain hidden and each needs an approved Figma frame before it can appear. No UI changes. |
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

## Full-suite environment diagnostics and repaired main run

The first main rerun was interrupted explicitly to preserve its diagnostics
once environmental failures were identified. It returned exit 2 after 322.94s:
**25 failed, 3208 passed, 8 skipped, 8 collection errors, 114 warnings**. This was
an interrupted partial run, not a completed full-suite result. The 8 collection
errors were missing phonenumbers, jwt, trimesh or boto3 in the existing local
interpreter. The failed browser cases reported closed Chrome processes and
failed `/tmp/playwright_chromiumdev_profile-*` cache/login-database writes under
the existing quota. Tiger's migration diagnostics reported an already-existing
`agent_tiger` role in the reused disposable cluster. None is hidden or waived.

Focused diagnostic commands, on the original cluster and default temporary path:

```sh
PYTHONPATH=tank:.git/t3-deps POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32843/tisan_t3_test /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_tiger_competitors.py::test_room_migration_and_nonowner_tank_admin_after_role_ownership --disable-socket --allow-hosts=127.0.0.1,localhost --tb=short --basetemp=.git/t3-tiger-diagnostic-tmp
PYTHONPATH=tank:.git/t3-deps /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_read1_review.py::test_canvas_normalizes_modern_css_colours --disable-socket --allow-hosts=127.0.0.1,localhost --tb=short --basetemp=.git/t3-read1-diagnostic-tmp
```

Results: **2 failed in 2.90s** (duplicate role), and **3 failed** (Chrome profile
writes failed under `/tmp`). No Tiger or READ-1 source/assertion was changed.
Repaired only the owned test environment:

```sh
docker run --detach --rm --name codex-tisan-t3-diagnostic-postgres --publish 127.0.0.1::5432 --env POSTGRES_HOST_AUTH_METHOD=trust --tmpfs /var/lib/postgresql/data postgres:16.15
docker port codex-tisan-t3-diagnostic-postgres 5432
mkdir -p .git/t3-runtime-tmp
PYTHONPATH=tank:.git/t3-deps POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32851/postgres /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_tiger_competitors.py::test_room_migration_and_nonowner_tank_admin_after_role_ownership --disable-socket --allow-hosts=127.0.0.1,localhost --tb=short --basetemp=.git/t3-tiger-clean-tmp
TMPDIR=/workspace/codex-tisan-t3/.git/t3-runtime-tmp PYTHONPATH=tank:.git/t3-deps /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_read1_review.py::test_canvas_normalizes_modern_css_colours --disable-socket --allow-hosts=127.0.0.1,localhost --tb=short --basetemp=.git/t3-read1-clean-tmp
```

Fresh cluster bound only `127.0.0.1:32851`. Results: **2 passed in 4.48s** and
**3 passed in 4.76s**. These include reapplying the actual Tank schema as its
non-superuser admin after room-role ownership, with the new Tisan DDL present.
No shared temporary directory was purged.

Installed only existing pinned suite dependencies into `.git/t3-deps`:

```sh
TMPDIR=/workspace/codex-tisan-t3/.git/t3-runtime-tmp /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pip install --no-cache-dir --no-deps --target .git/t3-deps phonenumbers==9.0.42 PyJWT==2.15.1 boto3==1.40.47 botocore==1.40.76 jmespath==1.1.0 s3transfer==0.14.0 trimesh==4.9.0 numpy==2.2.6
TMPDIR=/workspace/codex-tisan-t3/.git/t3-runtime-tmp /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pip install --no-cache-dir --target .git/t3-deps python-dateutil==2.9.0.post0
```

Both exited 0. The intermediate import check found missing dateutil; the second
command installed its existing Forge-lock pin and six. Final import check for
phonenumbers, jwt, trimesh, boto3, dateutil and urllib3 succeeded. No dependency
manifest or shared interpreter was changed; no model/weights were installed.

Created `tisan_t3_test`, `market_test` and `radix_passive_test` with `docker exec
codex-tisan-t3-diagnostic-postgres createdb -U postgres <name>` (all exit 0).
Stopped only this task's original disposable cluster after its tests finished:
`docker stop codex-tisan-t3-postgres` (exit 0; its `--rm` removed it). The clean
main run reuses the actual checked-in offline runner helpers with this exact
local helper, saved as `.git/t3-rerun-main.py`:

```python
import importlib.util
import os
from pathlib import Path

root = Path.cwd()
spec = importlib.util.spec_from_file_location('t3_offline_runner', root / '.github/scripts/offline_suite.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
env = runner.clean_env()
shared = 'postgresql://postgres@127.0.0.1:32851/tisan_t3_test'
for name in ('POOL_SCHEMA_DATABASE_URL', 'ZENAS_SCHEMA_DATABASE_URL', 'MEMORY_TEST_DATABASE_URL',
             'BASE_TEST_DATABASE_URL', 'RLS_TEST_DATABASE_URL', 'SKALA_B3_TEST_DATABASE_URL',
             'SKALA_INTAKE_TEST_DATABASE_URL', 'TIGER_MAIL_TEST_DATABASE_URL', 'RIG_TEST_DATABASE_URL',
             'TRAINING_SCHEMA_DATABASE_URL'):
    env[name] = shared
for name, database in [('RADIX_PASSIVE_TEST_DATABASE_URL', 'radix_passive_test'), ('DATABASE_URL', 'market_test')]:
    env[name] = 'postgresql://postgres@127.0.0.1:32851/' + database
env['GITHUB_ACTIONS'] = 'true'
env['TMPDIR'] = str(root / '.git/t3-runtime-tmp')
env['PYTHONPATH'] = str(root / 'tank') + ':' + str(root / '.git/t3-deps')
args = runner.pytest_args('3', '300')
args += ['--junitxml=' + str(root / '.git/t3-junit/main-clean.xml')]
args += ['--ignore=' + p for p in runner.ALONE + runner.ELSEWHERE]
raise SystemExit(runner.run(args, 2160, 'main-local-rerun', cwd=root, env=env))
```

Invoked with:

```sh
TMPDIR=/workspace/codex-tisan-t3/.git/t3-runtime-tmp /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python .git/t3-rerun-main.py
```

The clean main result is still pending at this checkpoint. Its final outcome
will be appended; neither earlier main attempt is being represented as green.


## Final full-suite result

The clean main run completed: **22 failed, 6886 passed, 39 skipped, 174 warnings, 12 errors, 1827 subtests passed in 1413.82s**. It is not green. Separate runner groups completed with **46 passed** (tiger_g5) and **40 passed** (zenas_regulation_alerts), as recorded above. No failure is waived.

The external temporary-directory diagnostic ran the complete RX1 and base-engine files: **33 passed in 1.62s**. The worker diagnostic still failed because `workers/task/__main__.py:159` writes `/tmp/worker-message.txt`, which returns `[Errno 122] Disk quota exceeded`. No shared temporary files were removed and no unrelated worker code was changed. Other final errors include missing `manifold3d`, browser/pytest worker crashes, local service startup failures, Moot setup assertions, and a Node timeout; these remain unresolved.

Exact diagnostic commands:

```sh
TMPDIR=/workspace/codex-tisan-t3-runtime PYTHONPATH=/workspace/codex-tisan-t3/tank:/workspace/codex-tisan-t3/.git/t3-deps /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_base_engine_terms_approved.py tests/test_rx1_scans.py --disable-socket --allow-hosts=127.0.0.1,localhost --tb=short --basetemp=/workspace/codex-tisan-t3-runtime/pytest-proof
```

Final main JUnit failures/errors (each entry is an observed result, not an attribution to T3):

- failure: `tests.test_rx1_scans::test_planted_key_vulnerable_dependency_and_injection_are_found` — `assert False is True`
- failure: `tests.test_rx1_scans::test_scan_makes_no_network_call` — `assert 0 >= 1`
- failure: `tests.test_rx1_scans::test_file_source_stays_inside_the_tenant` — `assert False is True`
- failure: `tests.test_rx1_scans::test_rows_and_logs_do_not_contain_the_secret` — `assert []`
- failure: `tests.test_rx1_scans::test_failing_gitleaks_falls_back_without_leaking_stderr` — `IndexError: list index out of range`
- failure: `tests.test_rx1_scans::test_git_bundle_is_scanned_without_fetching` — `assert False + where False = any(<generator object test_git_bundle_is_scanned_without_fetching.<locals>.<genexpr> at 0x77fc7a7b2e90>)`
- failure: `tests.test_base_engine_terms_approved::test_flat_app_layout_without_skills_dir_boots_empty` — `AssertionError: assert {'a': {'gener..._locals': []}} == {'a': {'gener..._locals': []}} Omitting 2 identical items, use -vv to show Differing items: {'b': {'generic_words': ['firearms', 'firearm', 'guns', 'gun', 'arms', `
- failure: `tests.test_workers_command::test_task_runner_reuses_local_branch_and_pr_for_followup` — `AssertionError: assert 1 == 0 + where 1 = <function main at 0x77fc6a10ed40>() + where <function main at 0x77fc6a10ed40> = <module 'workers.task.__main__' from '/workspace/codex-tisan-t3/workers/task/__main__.py'>.main`
- error: `tests.moot_hearing.test_store::test_duplicate_human_turn_survives_restart_and_only_one_event` — `failed on setup with "assert False"`
- error: `tests.moot_hearing.test_store::test_handover_and_turn_compete_one_revision_wins` — `failed on setup with "assert False"`
- error: `tests.moot_hearing.test_store::test_replay_projects_current_roles_never_old_judge_authority` — `failed on setup with "assert False"`
- error: `tests.moot_hearing.test_store::test_founder_publish_roundtrip_uses_existing_public_reader_without_private_state` — `failed on setup with "assert False"`
- error: `tests.moot_hearing.test_store::test_closed_reasoning_becomes_pending_review_never_automatic_gold` — `failed on setup with "assert False"`
- error: `tests.moot_hearing.test_store::test_pair_creation_is_atomic_retryable_and_region_tenant_private` — `failed on setup with "assert False"`
- error: `tests.moot_hearing.test_store::test_paired_publish_is_atomic_and_opposite_requests_do_not_deadlock` — `failed on setup with "assert False"`
- failure: `tests.test_radix_osv_real::test_dockerfiles_are_collected_from_a_tree` — `AssertionError: assert [] == ['svc/Dockerf...b.dockerfile'] Right contains 2 more items, first extra item: 'svc/Dockerfile' Use -v to get more diff`
- error: `tests.moot_hearing.test_api::test_room_identity_is_key_bound_tenant_scoped_and_never_json_asserted` — `failed on setup with "assert False"`
- error: `tests.moot_hearing.test_api::test_actual_room_turn_retry_is_idempotent_and_privacy_is_projected` — `failed on setup with "assert False"`
- error: `tests.moot_hearing.test_api::test_ai_counsel_start_creates_swapped_pair_atomically` — `failed on setup with "assert False"`
- error: `tests.moot_hearing.test_api::test_actual_workspace_transport_accepts_create_commands_and_preserves_region_guard` — `failed on setup with "assert False"`
- error: `tests.moot_hearing.test_api::test_paired_human_judge_reveal_waits_for_both_durable_closures_on_reads_and_retries` — `failed on setup with "assert False"`
- failure: `tests.test_rig_forge_geometry::test_scan_roundtrip_glb_is_draft_and_uses_metres` — `ModuleNotFoundError: No module named 'manifold3d'`
- failure: `tests.test_rig_forge_geometry::test_bad_scans_are_rejected_with_a_reason[inside_out-outward]` — `ModuleNotFoundError: No module named 'manifold3d'`
- failure: `tests.test_rig_forge_geometry::test_bad_scans_are_rejected_with_a_reason[hole-watertight]` — `ModuleNotFoundError: No module named 'manifold3d'`
- failure: `tests.test_rig_forge_geometry::test_bad_scans_are_rejected_with_a_reason[small_inverted_part-outward]` — `ModuleNotFoundError: No module named 'manifold3d'`
- failure: `tests.test_rig_forge_geometry::test_scale_and_size_budget_are_enforced` — `ModuleNotFoundError: No module named 'manifold3d'`
- failure: `tests.test_skills_offline::test_rung3_offline_cases` — `AssertionError: base.business_data@2.0.0: 15 passed, 0 network-skipped, 0 failed (15 cases) base.business_data@2.0.1: 17 passed, 0 network-skipped, 0 failed (17 cases) base.contacts@1.0.0: 4 passed, 0 network-skipped, 0 `
- failure: `tests.autumbra_public_bugs.test_page::test_public_host_and_direct_page_have_no_shell_admin_keeps_gate` — `AssertionError: Locator expected to be visible Actual value: None Error: Target crashed Call log: - Expect "to_be_visible" locator(".autumbra-public") with timeout 5000ms - waiting for locator(".autumbra-public")`
- error: `tests.test_agent1_public_render::test_example_com_through_render_with_internal_browser` — `failed on setup with "worker 'gw2' crashed while running 'tests/test_agent1_public_render.py::test_example_com_through_render_with_internal_browser'"`
- failure: `tests.test_market_lab_documents_real_tank::test_uploaded_documents_on_real_tank` — `RuntimeError: A local service exited during startup; inspect its local log`
- failure: `tests.test_market_lab_real_tank::test_real_tank_routes_to_real_room_and_postgres` — `RuntimeError: A local service exited during startup; inspect its local log`
- failure: `tests.test_market_lab_warning_real_tank::test_warning_job_on_real_tank` — `RuntimeError: A local service exited during startup; inspect its local log`
- failure: `tests.test_moot_published_states::test_moot_published_states` — `subprocess.TimeoutExpired: Command '['node', '--test', 'tests/live_page_sources.test.cjs']' timed out after 45 seconds`
- error: `tests.test_rig_3d_deployment::test_docker_cmd_preserves_public_api_health_and_private_brain` — `failed on setup with "worker 'gw0' crashed while running 'tests/test_rig_3d_deployment.py::test_docker_cmd_preserves_public_api_health_and_private_brain'"`

The final Tisan/Command regression result remains **333 passed, 11 skipped**; the opt-in disposable Postgres quote checks separately passed **6 tests**. Q1 checks were absent from main, so item 3 (k6) was skipped as instructed. No Docker image-size change is claimed.

Founder `/chats` acceptance and its screenshots are pending. No live test tenant data was created, no staging publish was performed, and no browser acceptance is claimed. Claude opens the PR; the founder merges. This branch is ready for review with the full-suite and acceptance blockers explicitly outstanding.


## Review fixes for #612

The six review items are implemented on the same branch, after merging `origin/main` (`8299ff94`). The dispatch conflict retained both Tisan Confirm tools and main's `radix.repo.scan`.

| File and line | Review correction |
| --- | --- |
| `tank/tisan_requests.py:19`, `:93`, `:188` | Preview, feedback and handover take validated slug, select the tenant's newest open request, and return existing 404 when none is open. Tenant and slug filtering are both enforced. |
| `tank/tisan_requests.py:133`, `:230` | Successful results expose only existing display aliases build_id, url and status; status is the request state. Completed build data also has build_id. No resultFields changes or new UI labels. |
| `agents/tisan/builder.py:279` | Only a result-provided slug enters memory; raw input slug is never substituted. |
| `agents/tisan/builder.py:273`, `:291` | A crash attempts exactly one memory write and then re-raises the same exception, even if memory is down, preserving chassis job failure. |
| `tank/tisan_requests.py:161` | JSON arguments must be objects; arrays, null, strings and numbers return existing 422. |
| `tank/tisan_requests.py:15`, `:32` | Repeat changes_requested is allowed only for a newer published build with a different commit. Same-build feedback writes nothing; accepted remains final. |
| `tests/test_tisan_requests.py:44` | Regression tests cover refused/crashed slug omission, re-raise with memory outage, object validation, multiple feedback rounds, newest open request, tenant isolation and build_id hydration. |
| `tests/tisan_t3/card_contract.cjs:1` | Executes the real presentation module for founder and client views: existing Site, Build, Result and Status labels appear; hidden fields do not. |

**Hidden fields requiring approved Figma frames:** request_id, commit, memory_id and checks. They remain in result data. The earlier statement that memory_id would appear on the card without UI changes was incorrect and is corrected above. No founder-browser screenshot or live acceptance is claimed.

Commands and observed results for the review changes:

```sh
git fetch origin && git merge origin/main
# One command.py conflict resolved retaining both sides; merge committed b95caaab.
# Before each sequential push:
git fetch origin main && git merge origin/main && git push origin codex/tisan-t3-requests
# Every push succeeded.

PYTHONPATH=tank:.git/t3-deps /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_tisan_requests.py --disable-socket --allow-hosts=127.0.0.1,localhost --basetemp=/workspace/codex-tisan-t3-runtime/review-unit
# 12 passed, 6 skipped (no database URL), 3 warnings in 4.78s.

docker run --rm -d --name codex-tisan-t3-review-postgres -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1::5432 --tmpfs /var/lib/postgresql/data postgres:16.15
# Disposable loopback-only Postgres on port 32861; no production SQL.

TMPDIR=/workspace/codex-tisan-t3-runtime PYTHONPATH=tank:.git/t3-deps POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32861/postgres /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_tisan_*.py tests/tisan_j4/ tests/tisan_promotion/ tests/test_command.py --disable-socket --allow-hosts=127.0.0.1,localhost --basetemp=/workspace/codex-tisan-t3-runtime/review-regression
# 338 passed, 11 skipped, 25 warnings in 62.07s.

TMPDIR=/workspace/codex-tisan-t3-runtime PYTHONPATH=tank:.git/t3-deps POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32861/postgres /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_tisan_requests.py --disable-socket --allow-hosts=127.0.0.1,localhost --basetemp=/workspace/codex-tisan-t3-runtime/review-final
# 20 passed, 3 warnings in 9.54s (includes newest-open and slug-plan tests added after regression collection).

node tests/tisan_t3/card_contract.cjs
# 6 existing-card projections passed; hidden fields excluded.

/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# All checks passed.
git diff --check
# Passed.
```

Q1 remains absent from main's run_checks; k6 is still skipped. Final-head CI Tank result is recorded in this PR's final verification update, so recording it does not create another untested head.
