# Tisan Wave 4: one tracked request through scanned staging and founder promotion

A founder-confirmed `tisan.request` now queues one durable room pipeline using the request ID as its job ID. The pipeline reuses the stored page approval, J2 live Figma reader, existing builder, Q1/k6 checks, R5 repo scanner through Tank, existing Git/staging publisher and existing founder-only Coolify promotion API. It never promotes automatically.

Branch: `codex/tisan-w4`, in `/workspace/codex-tisan-w3`. The founder's exact stash/fetch/new-branch/rebase/stash-pop sequence completed without conflicts. Base after rebase: `c4e1395e`. The rebased initial R5 refactor is `f924b432`. The finished W3 branch and merged #627 were not updated.

Pushed gate heads: repo scan/promotion enforcement `110c9a8c`; tracked request/staging and promotion tests `02c0f367`. The final handoff reports the subsequent validation/evidence head.

## Behavior and authority

- Existing tenant-admin requests still record requests and use the existing preview/feedback/handover flow. Only a current founder can submit pipeline page/assembly parameters or dispatch a build pipeline.
- A founder request carries `page_id`, referring to an existing tenant-owned approval, plus optional `assembly` containing the existing `plan`, accepted-copy IDs and media inputs. Top-level client `plan`/`copy`/`media`, tenant overrides and approval flags remain forbidden. A missing page reference is tracked as blocked; no build starts.
- The room loads the approval and its original frame/page artifact hashes. J2 reads the stored file/frame pair live using that tenant's existing pairing. Missing/incomplete/changed/fixture readings fail closed. Approval is rechecked after the live read and after the build, before staging. No approval record is created by the pipeline.
- The existing queue gets a deterministic request/job ID, a bounded pipeline timeout and one attempt. Replay checks the stored immutable input and returns the recorded result. It does not repeat a build or a deployment after an uncertain acknowledgement.
- R5 receives the exact generated archive through Tank. The receipt binds tenant, scan ID and SHA-256, requires a complete scan and zero critical findings, and is retained in the build checks, sidecar and existing build memory. A critical or incomplete result blocks staging/promotion. Only counts and identifiers enter the build result, not finding source/secret text.
- Publishing verifies the receipt against the actual archive. Promotion resolves the successfully published build for the exact staging commit and rechecks its R5 receipt through Tank. The existing fresh passive site scan, staging/production revision checks and founder authorization remain required. Refused critical receipts are retained in the promotion audit.
- The same request card refresh reads the durable pipeline and acknowledged deployment status. It follows founder promotion and rollback through the existing operation journal, including terminal failure/refusal/unknown states. Status reads only inspect deployment status; they cannot submit a deployment. Existing card summary/result fields are reused; no Workspace layout or copy is changed.
- The API still pins/deploys through Coolify HTTPS. The room has no Docker socket mount. Rollback restores the recorded prior commit; uncertain deployments remain quarantined as before.

## Source changes by file and line

| File | Change |
| --- | --- |
| `tank/radix_repo.py:33` | Share existing R5 archive submission; retain the existing ref and leak flag in scoped scan results. The public repo command still requires its original confirmation. |
| `tank/tisan_pipeline.py:20` | Narrow Tisan-room-key, tenant and region corridor to R5; validate archive size/signature/hash; reuse the existing scanner jobs and findings route. |
| `agents/tisan/repo_scan.py:44` | Bounded R5 submit/poll, strict receipt validation, measured sidecar/check rows and exact-archive publication/promotion gates. |
| `agents/tisan/builder.py:282` | Scan successful runtime builds before the existing memory/ready-event path. |
| `agents/tisan/scaffold.py:459` | Include the repo result in existing card result rows. |
| `agents/tisan/publish.py:49` | Reject missing, critical, incomplete, foreign or changed-archive receipts before Git/staging mutations. |
| `agents/tisan/promotion.py:219` | Require and retain the repo receipt before existing live/passive checks and production mutation; validate identity/completeness/counts. |
| `agents/tisan/promotion_api.py:101` | Supply the actual archive-bound repo gate to the existing founder API. |
| `agents/tisan/pipeline.py:32` | Tenant/request SQLite journal on the existing data volume; approved live gate, build/check/staging orchestration, read-only production/rollback reconciliation and idempotent room job start. |
| `agents/tisan/app.py:71` | Require approved live pages for runtime build/scaffold handlers; register pipeline job/routes and bounded timeouts; refuse a substituted Figma source. Approved-version reader fixture behavior stays unchanged. |
| `tank/command.py:407` | Reuse card hydration for requests; add optional page references and founder-only nested assembly inputs without changing the original client field guards. |
| `tank/tisan_requests.py:168` | Dispatch confirmed founder requests with server-owned actor/tenant identity and hydrate the same card through staging, promotion and rollback. |
| `agents/tisan/Dockerfile:11` | Copy the two new room modules. No new dependency, environment variable, volume, network or Docker client. |
| `tests/test_tisan_wave4_repo.py:1` | Actual Tank/R5 corridor with isolated scanner-job transport: archive/tenant/region binding, critical and unavailable results, sidecar, publication and memory. |
| `tests/test_tisan_wave4_pipeline.py:1` | Actual Command Confirm/request/job/card flow with disposable Postgres; tenant-bound approval artifacts/live reader arguments, approval races, quality failures, replay and read-only staging reconciliation. Build/staging services in orchestration-only tests are test doubles. |
| `tests/test_tisan_wave4_promotion.py:1` | One scanned test site's promotion/rollback using the real Coolify client and fake HTTP API, exact production writes and original-request tracking; no Docker socket. |
| `tests/test_tisan_requests.py:47` | Keep the pre-existing memory test isolated from the separately tested repo transport. |
| `tests/test_tisan_publish.py:59` | Existing publish fixtures now carry a matching synthetic receipt for their archive. |
| `tests/tisan_promotion/test_promotion.py:90`, `tests/tisan_promotion/test_tisan_promotion_api.py:52` | Existing passive/API tests explicitly supply their isolated valid repo gate. |
| `tests/test_c10_rooms.py:222` | Expect the added pipeline handler and bounded scan/staging allowances; heartbeat and other room assertions remain unchanged. |
| `tests/tisan_wave4/verify_runtime.py:1` | Reproducible current-source import/OpenAPI check in an existing pinned room runtime, read-only and network-disabled, without a Docker socket. This is not a claim that a new image was deployed. |

Deploy-on-merge affects Tank/main and regional stacks through the Tank changes, and Tisan plus its regional copies through `agents/tisan/`. No live deployment, production SQL, model call or paid service was used in this work. Existing schemas, generated memory blocks, scanner engines, approved skill versions and Compose topology are unchanged. The only new durable table is the additive/idempotent SQLite pipeline journal on the existing room data volume.

## Offline validation

Commands ran from `/workspace/codex-tisan-w3`, using this task's ignored Python/runtime dependencies and a separately named disposable trust-auth Postgres on loopback port 32884 with tmpfs storage. No production database setting was used.

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32884/postgres .venv/bin/python -m pytest tests/test_tisan_wave4_pipeline.py tests/test_tisan_wave4_repo.py tests/test_tisan_wave4_promotion.py tests/test_tisan_requests.py tests/test_tisan_publish.py tests/tisan_promotion/test_promotion.py tests/tisan_promotion/test_tisan_promotion_api.py tests/test_command_radix_repo.py -q --disable-socket --allow-hosts=127.0.0.1,localhost --maxfail=2
# Earlier combined integration pass: 122 passed in 36.39s.

.venv/bin/python -m pytest tests/test_tisan_wave4_promotion.py -q --disable-socket --allow-hosts=127.0.0.1,localhost --maxfail=2
# 6 passed in 1.18s; actual HTTP client, in-process Coolify API, no live site.

mkdir -p /tmp/codex-tisan-w4-tests
PATH="$PWD/.venv/k6-v1.8.2-linux-amd64:$PATH" TMPDIR=/tmp/codex-tisan-w4-tests J4_TEST_POSTGRES_PORT=32884 POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32884/postgres TISAN_TEST_PLAYWRIGHT="$PWD/.venv/tisan-browser/node_modules/playwright" PLAYWRIGHT_BROWSERS_PATH="$PWD/.venv/j5-browser" .venv/bin/python -m pytest tests/test_tisan_*.py tests/tisan_promotion/ tests/test_command_radix_repo.py tests/test_c10_rooms.py tests/test_secrets.py -q -rs --disable-socket --allow-hosts=127.0.0.1,localhost --maxfail=3
# 553 passed, 3 opt-in build skips, 247 warnings in 217.83s.

.venv/bin/python tests/tisan_wave4/verify_runtime.py --image codex-tisan-w3-j5:final
# Exit 0: current room routes imported in the existing pinned runtime;
# networking disabled, read-only source mounts, no Docker socket or startup SQL.

ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"
# All checks passed! Exact CI lint is required before every subsequent push.
git diff --check
# Exit 0.
```

An initial broad run used TMPDIR under `.venv`; the Radix engine intentionally skips any absolute path containing that segment, so its dirty-fixture findings were omitted in that local test configuration. The corrected run uses the task's dedicated `/tmp` directory. An existing C10 exact handler/timeout assertion was also updated for the new job. Scanner rules and expected findings were not weakened.

## Acceptance boundary

The founder still needs the merged/deployed code and a registered test site, an approved tenant page snapshot, configured paired live-reader settings, Q1's existing scan.secrets approval and the existing accepted-copy inputs. One founder request in `/chats` must then reach staging with its R5 scan recorded. Local tests use disposable data and isolated HTTP transports; they do not claim that live founder acceptance, a live promotion or a deployment occurred.

J4's quote-request page remains with the Figma thread for its frame. No quote page, visible form wording or email was built here. Claude opens the new PR; the founder merges.
