# Radix I8 — regulation-triggered notice and cookie checks

**Stacked on R4:** branch `codex/radix-w3` starts at `codex/radix-r4-watch`, commit `5359bf0a12c15371feb09a8810cd5526eaa485c3`. Review this gate against that commit, not main. No merge from main was performed. Claude opens the PR; the founder merges. Merge main once only when Claude releases that step after R4 merges.

A tenant's `zenas.regulation.changed` event now atomically queues one passive run per active watched domain. Tenant identity comes from Radix's own watch rows. Duplicate delivery does not create duplicate runs. The consumer acknowledges only after the queue transaction commits; malformed facts and enqueue errors fail the delivery for the bus's existing retry/dead-letter policy.

The existing R4 tick drains these runs under `WATCH_LOCK`. Manual scans remain arbitrated by the existing gateway lease and `passive_one_running` index. Each queued run uses the existing gateway TXT re-check; removed TXT stops its watch before the notice scanner runs. Busy/unavailable runs retain their scan id and retry after a minute. A crash after scan completion is recovered without rescanning. The event id and original validated facts, including source/link when supplied, accompany the run through `radix.changes`. Legacy ZenasFact events have document/version hashes only; source/link are never invented.

## Scope and measured limitations

Gate 2 reuses the existing `scan_html` GDPR/POPIA notice rules and `live._cookie_findings` response-cookie flag rules. It fetches one HTTPS root response through `http://radix-passive-proxy:8082`, with redirects disabled and a 1 MB decoded-body bound. It persists findings with existing rule text, never page bodies or cookie values. No other scan runs for an event.

These are **HTTP-only checks**. They do not execute JavaScript or observe browser cookies; the run data explicitly records `browser_cookies_checked: false`. Gate 1/R6's browser cookie behaviour, accessibility, CCPA extension and other checks are not claimed here. There is no new page, chat tool, visible wording, email, model call, setting, provider or limit change. Notice-only and full-scan baselines are separated so a notice run cannot falsely fix TLS/header findings. Egress code and policy are unchanged.

## Changes by file and line

| File | Line | Change |
| --- | ---: | --- |
| `agents/radix/regulation_events.py` | 20 | Validate both exact bus fact shapes, including official-source link restrictions. |
| `agents/radix/regulation_events.py` | 48 | Discover own active-watch tenants; atomically deduplicate and queue scans for their domains. |
| `agents/radix/regulation_events.py` | 80 | Receive/settle loop using `chassis.events.request`, with commit-before-ack and fail-on-error. |
| `agents/radix/regulation_events.py` | 113 | Drain durable event work within R4's worker lock, retain run ids across retries, recover completed work, skip stopped watches. |
| `agents/radix/passive_notices.py` | 16 | Bounded proxied root response; reuse only notice and response-cookie rules and their wording. |
| `agents/radix/passive_watch.py` | 22 | Drain event runs through the existing tick, without adding a scheduler. |
| `agents/radix/passive_routes.py` | 55 | Execute a persisted queued scan id through the normal TXT lease; return that run's own completion. |
| `agents/radix/passive_store.py` | 58 | Idempotent event queue table bootstrap alongside the existing passive tables. |
| `agents/radix/passive_store.py` | 189 | Keep durable event runs eligible behind long-running scans without removing the TXT/watch checks. |
| `agents/radix/passive_store.py` | 232 | Compare completed scans with the same check scope. |
| `agents/radix/passive_store.py` | 291 | Return event facts and HTTP-only check coverage in `radix.changes`. |
| `agents/radix/schema.sql` | 27 | Add the room-owned dedupe/retry table above generated memory; join the existing RLS rollout with ENABLE/FORCE and both policies. Use catalog lookup without needing access to Tank's schema. |
| `agents/radix/app.py` | 118 | Start the consumer after table initialization and cancel it before chassis pools close. |
| `agents/radix/Dockerfile` | 69 | Package `regulation_events.py` alongside the existing passive modules. Deploy-on-merge will redeploy Radix and Tank for this code change; no compose/runtime settings change. |
| `tank/event_bus.py` | 249 | Permit both delivery event names; receive/settle at 275/285 allow only Rig/price and Radix/regulation pairs. |
| `tests/radix_i8/test_events.py` | 1 | Fake bus/page tests plus disposable Postgres queue, isolation, comparison, TXT removal, atomic rollback and HTTP authorization checks. |
| `tests/tenant_bus/test_radix_events.py` | 17 | Actual bus/Redis: malformed messages retry five times, dead-letter once and remain tenant-isolated. |
| `tests/test_radix_passive.py` | 64 | Clear R4 watches and I8 event state in the existing disposable fixture to satisfy its FK constraints. |
| `tests/radix_i8/PR.md` | 1 | Review handoff and verification evidence. |

## Commands and results

All source work ran in `/workspace/codex-radix-w3`. Existing Python 3.12 test tools were used read-only. Test PostgreSQL/Redis state lives under this checkout's ignored `.test-data/`, bound to loopback only. No production database, external test socket, live source fetch or model was used.

Setup:

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-radix-w3 && cd /workspace/codex-radix-w3 && git fetch origin main && git checkout -B codex/radix-w3 origin/main && git config user.name 'Codex' && git config user.email 'codex@users.noreply.github.com'
ls AGENTS.md docs/cursor/CONTEXT.md tank/event_bus.py agents/rig/rigbox/price_events.py agents/zenas/core/regulations.py agents/radix/app.py agents/rig/app.py agents/radix/schema.sql tests/tenant_bus
git fetch origin codex/radix-r4-watch && git checkout -B codex/radix-w3 origin/codex/radix-r4-watch
```

Each command exited 0; all named files were present. Initial main was `8636a506f6361459a84fb63da16ce163df4e9cba`. The founder then explicitly authorized the R4 stack above. Every completed source/test file was committed and pushed serially with `git add <file>`, a file-specific `git commit -m ...`, and `git push origin HEAD:codex/radix-w3`; all completed pushes succeeded. An interrupted packaging command left that file staged; the subsequent commit/push completed, and `git ls-remote origin refs/heads/codex/radix-w3` confirmed the remote head.

Disposable runtime setup:

```sh
mkdir -p .test-data
/workspace/codex-radix-r4-py312/lib/python3.12/site-packages/pgserver/pginstall/bin/initdb -D .test-data/postgres -A trust -U placeholder > .test-data/initdb.log
mkdir -p .test-data/tmp
/workspace/codex-radix-r4-py312/lib/python3.12/site-packages/pgserver/pginstall/bin/pg_ctl -D .test-data/postgres -l .test-data/postgres.log -o '-h 127.0.0.1 -p 56483 -k /workspace/codex-radix-w3/.test-data/tmp' start
/workspace/codex-radix-r4-py312/lib/python3.12/site-packages/pgserver/pginstall/bin/createdb -h 127.0.0.1 -p 56483 -U placeholder radix_passive_test
TMPDIR=/workspace/codex-radix-w3/.test-data/tmp /workspace/codex-radix-r4-py312/bin/python -m pip install --target .test-data/redis-runtime redislite --no-cache-dir --disable-pip-version-check
.test-data/redis-runtime/redislite/bin/redis-server --bind 127.0.0.1 --port 56484 --save '' --appendonly no --daemonize yes --dir /workspace/codex-radix-w3/.test-data --pidfile /workspace/codex-radix-w3/.test-data/redis.pid --logfile /workspace/codex-radix-w3/.test-data/redis.log
```

These commands exited 0. Redislite 6.2.912183 supplied the disposable test Redis binary only; it is not an application dependency. Earlier PostgreSQL startup probes failed on port 55439 (`Address already in use`) and then on a `/tmp` socket lock (`Disk quota exceeded`). Moving the socket to this checkout resolved that. An attempted local venv bootstrap also failed at ensurepip; the existing read-only Python runtime was used instead. A Docker image-list probe stalled and was not used to run the tests.

Workspace test dependency setup, from `workspace/`:

```sh
TMPDIR=/workspace/codex-radix-w3/.test-data/tmp npm ci --no-audit --no-fund
```

Exit 0: 45 packages installed. Lockfiles and application packages were unchanged.

Full required local regression on source head `6897185167f8db36debbcb68c50ef701edf37b01`:

```sh
TMPDIR=/workspace/codex-radix-w3/.test-data/tmp RADIX_PASSIVE_TEST_DATABASE_URL=postgresql://placeholder@127.0.0.1:56483/radix_passive_test RADIX_I8_TEST_DATABASE_URL=postgresql://placeholder@127.0.0.1:56483/radix_passive_test POOL_SCHEMA_DATABASE_URL=postgresql://placeholder@127.0.0.1:56483/postgres TENANT_BUS_REDIS_URL=redis://127.0.0.1:56484/0 DATABASE_URL=postgresql://placeholder@127.0.0.1:56483/postgres LITELLM_MASTER_KEY=placeholder TANK_API_KEY=placeholder PYTHONPATH=agents/_chassis /workspace/codex-radix-r4-py312/bin/python -m pytest -q --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 tests/test_radix_*.py tests/test_rx1_scans.py tests/test_command_radix.py agents/radix/tests/ tests/tenant_bus/ tests/radix_i8/ > .test-data/regression-final.txt 2>&1
```

**Exit 0: 298 passed, 1 skipped, 14 existing framework warnings, 437 subtests passed in 52.09s.** The sole skip is the pre-existing OSV real-data test: `no baked real OSV osv.sqlite on this machine`. All I8 tests and the bus/database tests ran. No acceptance threshold or existing assertion was removed.

Earlier runs, retained here rather than hidden:

- Existing passive/report selection before database setup: 41 passed, 7 database cases skipped.
- New I8 selection: 21 passed, then 22 passed after comparison coverage. One new gateway test initially used the wrong injection parameter (`lookup` rather than `check`); correcting the test produced 24 passed.
- Actual malformed-event bus test: 1 passed.
- First broad regression: 2 failed, 287 passed, 1 skipped, 7 errors, 437 subtests passed. One failure exposed the new schema's insufficient-privilege catalog check; fixed in `77d438cd`. One needed installed TypeScript test dependencies. Seven errors exposed R4's fixture truncation missing `passive_watches`; the fixture now clears watches and event state explicitly. The complete rerun above passed.

Other final checks:

```sh
TMPDIR=/workspace/codex-radix-w3/.test-data/tmp /workspace/codex-radix-r4-py312/bin/python -m pytest -q tests/test_secrets.py > .test-data/secrets.txt 2>&1
/workspace/codex-radix-r4-py312/bin/ruff check agents/radix/regulation_events.py agents/radix/passive_notices.py agents/radix/passive_watch.py agents/radix/passive_routes.py agents/radix/passive_store.py agents/radix/app.py tests/radix_i8 tests/tenant_bus/test_radix_events.py tank/event_bus.py --select E9,F
git diff --check origin/codex/radix-r4-watch...HEAD
```

Secret scan: **2 passed in 14.97s**, exit 0. Ruff: **All checks passed**, exit 0. Whitespace: exit 0. Ruff initially found one unused test import; removed before the passing run.

## CI and founder browser proof — pending

Claude has not yet opened this stacked PR, so there is no final-head Tank/Workspace CI result to claim. CI remains the full-suite test of record. This report's final commit changes documentation only; the tested source checkpoint is pinned above.

No live founder workspace test or screenshot has been captured. After the founder merges/deploys the dependency and this gate, the acceptance proof is: a real Zenas change for his tenant queues a notice/cookie run for watched `tervory.com`; confirming `radix.changes tervory.com` displays its existing Radix card; the run response names the Zenas event and its supplied source/link. Removing TXT must stop the watch before checks. Those live steps and screenshots remain outstanding, and this handoff does not claim product acceptance.
