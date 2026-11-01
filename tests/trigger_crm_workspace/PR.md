## Actual CLI fake-tank CI repair — 1 November 2026

Reproduced failure from run 41358882569 / job 125004751849 at reviewed head
0de9c23f. `cli/test/public-edge.test.mjs:6,13` now uses the existing real
Workspace module loader with CLI's installed TypeScript, rather than a VM
without require. Real Tank and regionTank load. No production code changes.
Every byte from `function request` through all six test bodies is unchanged.

Commands in `/workspace/codex-trigger-crm`:

- `node --expose-gc --test cli/test/public-edge.test.mjs`: before fix **0 passed, 6 failed**, reproduced `require is not defined`.
- `npm test --prefix cli`: after fix all six public-edge cases pass; full run **48 passed, 14 failed** because host `/tmp` quota prevents CSV/release/version-guard temporary writes. Not a passing run.
- `TMPDIR=/home/ammosync/trigger-crm-tmp npm test --prefix cli`: **62 passed, 0 failed, 0 skipped**, 18.46s; this is the same npm test script as the actual CLI workflow, with only local temp placement changed.
- `node --check cli/bin/tervory.mjs && node --check cli/src/client.mjs`: PASS.
- `node --check cli/test/public-edge.test.mjs`: PASS.
- `sh .github/scripts/cli_version_guard.sh origin/main`: PASS, no shipped CLI file changed; no version bump needed.
- `npm pack --dry-run` from `cli/`: PASS, seven packaged files. Initial root-directory `npm pack --dry-run --prefix cli` was not accepted by npm and failed ENOENT; correct cwd passed.
- Python source comparison against HEAD: all six public-edge test bodies/assertions identical. `git diff --check`: PASS.

Code and this required evidence committed together, one normal final push to
avoid optional status commits. Fresh exact-head CI required; previous green
results do not apply. #499 will include this corrected candidate by normal merge.
No live CRM, settings, secrets, production SQL/writes or model calls.

## Normal main merge after #498 — 1 November 2026

Main `858dbffa9ffcaeb6fb643dcab679cd593a773349` merged normally into this same
branch at `4aaf549d`. No rebase, force push or reset. Source/test head: `120815383f71c27cc04ec9a31e2bc8d3ad01e7a0`.
The sole conflict was the appended CRM helper in `workspace/lib/tank.ts:1449`.
It is retained; the diff against main is only that helper. Main's ZA regionTank
import/public reader, PAT/device/CLI functions and Trigger authority are intact.

Integration fixes preserve actual production-module loading:

- `tests/trigger_gate2/admin_contract.cjs:8`: resolve @/ aliases to real Workspace modules, including Zenas regionTank; no auth stub.
- `tests/command_acceptance_20261031/public_edge.cjs:5,12`: reuse existing workspace_loader for actual Tank and regionTank instead of a VM without require. All PAT/cancellation/ownership assertions remain.

Exact checks in `/workspace/codex-trigger-crm`:

1. `git fetch origin && git checkout codex/trigger-crm-workspace-20261031 && git merge origin/main`: conflict above resolved preserving both sides; merge committed and pushed normally.
2. `node tests/trigger_crm_workspace/contract.cjs`: PASS (twice, including integrated candidate).
3. `workspace/node_modules/.bin/tsc --noEmit --incremental false -p workspace/tsconfig.json`: PASS, exit 0 (twice).
4. `docker run --rm -d --name codex-crm-497-refresh-20261101 --memory 512m --cpus 1 -e POSTGRES_HOST_AUTH_METHOD=trust --tmpfs /var/lib/postgresql/data -p 127.0.0.1::5432 postgres:16.15`: PASS; `docker port codex-crm-497-refresh-20261101 5432` gave 127.0.0.1:32786. Synthetic disposable DB only.
5. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tank:tests:.crm-testdeps POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32786/postgres COMMAND_ACCEPTANCE_CLIENTS=1 COMMAND_TEST_TOOLS=/workspace/codex-trigger-crm/workspace/node_modules /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q -p no:cacheprovider tests/test_trigger_crm.py tests/test_trigger_crm_wsgi.py tests/test_command.py tests/test_command_streaming.py tests/test_personal_tokens.py tests/test_device_login.py tests/test_pat_route_corridor.py tests/trigger_gate2/test_gate2.py tests/command_acceptance_20261031/test_cross_lane.py tests/test_acceptance_identity_matrix.py --tb=short`: initial combined attempt **221 passed, 9 failed**, 83.55s. Four WSGI subprocesses could not see checkout-local Django; five cross-lane failures were missing local csv-parse (existing CLI dependencies reused) and the real-region-module loader gap fixed above. These failures are not represented as a green broad run.
6. Same environment/pytest flags with `tests/command_acceptance_20261031/test_cross_lane.py` alone after fixes: **7 passed**, zero skips, 18.29s; actual CLI/public adapter, US and ZA device-login, durable cancel/confirm, replay and receipts exercised.
7. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q -p no:cacheprovider tests/test_trigger_crm_wsgi.py --tb=short`: **4 passed**, 1.74s; existing CRM environment makes Django available to subprocesses.
8. Copy existing #499 `combined.cjs` and `test_combined.py` unchanged into ignored `.crm-refresh-harness`, then `CRM_ASSEMBLED_ROOT=/workspace/codex-trigger-crm PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q -s -p no:cacheprovider .crm-refresh-harness/test_combined.py --tb=short`: **1 passed**, zero skips, 4.80s; actual candidate loaded, no auth stub.
9. `node --test tests/live_page_sources.test.cjs`: **15 passed**, including ZA reads, no Boston fallback, missing regional config, cancellation and bounded errors.
10. `node --expose-gc tests/device_login_next_fetch.cjs`: PASS, real Next dedupe fetch and stalled-body/GC bounds. `node tests/cli_sign_ins.cjs`: PASS. `node tests/trigger_gate2/admin_contract.cjs`: PASS after alias fix. `node tests/trigger_second_build/admin_contract.cjs`: PASS. `node tests/acceptance_identity_matrix.cjs`: PASS.
11. `git diff --check`: PASS. `node --check tests/command_acceptance_20261031/public_edge.cjs`: PASS.
12. `docker stop codex-crm-497-refresh-20261101`: PASS; own --rm test DB removed. Per-file commits and normal `git push origin codex/trigger-crm-workspace-20261031`: PASS.

The first audit collection lacked jsonschema. Existing pins jsonschema 4.26.0
and Django 6.1.2 installed only under ignored `.crm-testdeps`; no other task's
venv changed. Existing CLI and Workspace dependencies are untracked symlinks.
No live CRM request, setting values, production SQL/write, model call or deploy.
Fresh exact-head CI and independent review pending. #499 awaits its normal main
refresh after #497 merges. No founder browser completion/screenshots claimed.

## Review dependency refresh — 1 November 2026

Rebased onto corrected backend `551979986876ea0795c0c2dee5eef2f67f606554`,
which contains main `7a5132fa`. Workspace source head `5ab5816089f3be80ae322e51141d6d590c578695`.
No new Workspace implementation changes. CRM remains founder-only.

Commands in `/workspace/codex-trigger-crm`:

- `git checkout codex/trigger-crm-workspace-20261031 && git rebase codex/trigger-crm-backend-20261031`: PASS, no conflicts.
- `git push --force-with-lease=refs/heads/codex/trigger-crm-workspace-20261031:be137cb4146dee721125427c11a29810f9249ee0 origin codex/trigger-crm-workspace-20261031`: PASS, founder-authorized rebase.
- `node tests/trigger_crm_workspace/contract.cjs`: PASS.
- `workspace/node_modules/.bin/tsc --noEmit --incremental false -p workspace/tsconfig.json`: PASS, exit 0.
- `git diff --check`: PASS.

Earlier hosted results apply to older heads; current hosted checks pending.
No founder browser acceptance/screenshots, production changes or new UI claimed.

## Founder-only correction — 1 November 2026

Supersedes the client integration follow-up below. The route uses existing
`isFounder` from `workspace/lib/admin.ts` before any Tank transport. A granted
client, tenant admin and member are each refused on list and detail reads.
Writes remain unavailable through this route; Tank separately enforces founder
access and durable Command Confirm.

Changed `workspace/app/api/trigger-crm/[...path]/route.ts:1,16,21` and
`tests/trigger_crm_workspace/contract.cjs:77`. Source/test head:
`c655fe021bb8c1d9461c5a573cf581ab460be573`; main merged at `71858c13`.

Commands in `/workspace/codex-trigger-crm`:

- `git checkout codex/trigger-crm-workspace-20261031 && git merge origin/main`: passed, no conflicts.
- `node tests/trigger_crm_workspace/contract.cjs`: PASS, founder-only corridor and granted client/admin/member refusal before transport, existing tenant/query/envelope protections.
- `workspace/node_modules/.bin/tsc --noEmit --incremental false -p workspace/tsconfig.json`: PASS, exit 0.
- `git diff --check`: PASS.
- Per-file commit and `git push origin codex/trigger-crm-workspace-20261031`: passed.

Dependencies reused through an untracked node_modules symlink; never committed.
No page, text, live records, model calls, production SQL or deployment changed.
Hosted exact-head checks, founder browser acceptance and screenshots remain
unverified. This is not founder completion evidence.

# Trigger CRM Workspace read corridor

Updated 31 October 2026, 11:23 PDT / 18:23 UTC. Draft; not deployed or founder accepted.

## Scope and source authority

Current `main` has a running BottleCRM deployment scaffold and pinned OpenAPI but no Workspace CRM read route. This branch adds a read-only corridor to the separately implemented Tank connector. It does not replace BottleCRM or introduce a second CRM database.

Live Figma SPEC `101:8244`, file `ZnphBOJU6657tohGLD3IzS`, was read with screenshot in session `4e97f011-3475-43d0-a07c-bfe2464efdc9`. It says founder acceptance and accent approval are pending, and the historical page is founder-only. New client designs are assigned to the separate Figma lane. No new screen, navigation, copy, confirmation UI or error wording is introduced here; there is no changed view to screenshot. Founder browser proof remains pending until the full build.

## File and line manifest

| File | Line | Change |
|---|---:|---|
| `workspace/lib/trigger-crm.ts` | 2 | Only leads, contacts and estimates are readable. |
| `workspace/lib/trigger-crm.ts` | 4 | Only list or UUID detail paths; no arbitrary URL/path. |
| `workspace/lib/trigger-crm.ts` | 10 | Only one positive page <=10000 on lists; no detail query or caller identity. |
| `workspace/lib/tank.ts` | 1156 | Fixed same-box server-only Tank GET, server-derived identity; no CRM token in Workspace. |
| `workspace/app/api/trigger-crm/[...path]/route.ts` | 13 | Founder and active session org required, alias-aware tenant derivation. |
| `workspace/app/api/trigger-crm/[...path]/route.ts` | 23 | Empty non-cacheable error responses; no upstream exception bodies reflected. |
| `workspace/app/api/trigger-crm/[...path]/route.ts` | 24 | Resource/envelope sanity check; only GET exported. |
| `tests/trigger_crm_workspace/contract.cjs` | 1 | Offline actual route/helper identity and request boundary proof. |

Contract: `GET /api/trigger-crm/{leads|contacts|estimates}[/{UUID}]` calls `GET /v1/trigger/crm/{resource}[/{UUID}]`. List response is `{resource,items,page,count}`; detail `{resource,item}`. Tank remains authoritative for explicit tenant-to-CRM organization binding, permitted fields and connector errors. Nonfounders do not receive access through this route. Other modules are deliberately not inferred from upstream API existence. Mutations must use the separately implemented Command Confirm flow, never this proxy.

## Commands and results

Commands ran in `/home/ammosync/.codex/trigger-crm-workspace-20261031` unless noted.

- `git clone --filter=blob:none https://github.com/Tervory-AI/tervory-tank.git /home/ammosync/.codex/trigger-crm-workspace-20261031`: PASS.
- `git fetch origin main` and `git checkout -b codex/trigger-crm-workspace-20261031 origin/main`: PASS.
- `git fetch origin codex/crm-design`: PASS, inspected design docs read-only; no branch merge.
- `node tests/trigger_crm_workspace/contract.cjs`: PASS. Actual route, helper and tenant alias derivation run with fake Clerk and fake Tank transport. Covers unsigned/client/no-org founder denial, malformed paths, unknown/injected/duplicate pagination, detail query denial, real allowed empty list/detail envelopes, fixed target/method/cache/redirect policy, headers derived from server session only, no mutation exports, empty sanitized upstream errors, network failure, malformed/wrong-resource envelopes, helper validation before fetch.
- `workspace/node_modules/.bin/tsc --noEmit -p workspace/tsconfig.json`: PASS, exit 0.
- `git diff --check origin/main`: PASS.
- `git status --short`: only untracked `workspace/node_modules` dependency symlink, never committed. Dependencies reused from `/tmp/tervory-command-workspace-20261031/workspace/node_modules`; no install on founder laptop.
- Per-file `git add <file>`, `git commit -m <description>`, `git push`: PASS for source/test commits. Initial local command used unavailable `python`; retried with `python3`. Initial commit required local Git author configuration; configured repository-only Codex identity before first successful commit. No push failed.
- `gh pr checks 497 --json name,state`: CLI compatibility failure (`unknown flag: --json`); no check-result claim based on that invocation.
- `gh pr view 497 --json headRefOid,statusCheckRollup --jq '{head:.headRefOid,checks:[.statusCheckRollup[]|{name,status,conclusion}]}'`: returned actual source head and four running checks at 11:24 PDT. Hosted checks still pending; not green evidence.

No real CRM records, secrets, model/provider calls, production SQL, live mutations, auth configuration changes, Zenas ZA work or worker investigation were used for this proof.

## Remaining completion gates

- Merge coordination and combined proof with the separately reviewed Tank connector, including configured organization mapping and actual permitted-field projection. Unit mocks are not live integration proof.
- Independent source review of this PR and all applicable exact-head hosted checks.
- Founder-approved current client CRM frames and exact copy before implementing the newly requested screens. No historical pending approval is treated as approval.
- Configured token and organization mapping are founder-owned by setting name only; no token values are requested or handled here.
- Full-build founder browser walkthrough and acceptance, last.


## Client integration follow-up — 2026-10-31T12:20:53.035623-07:00 / 2026-10-31T19:20:53.035623+00:00

Supersedes founder-only Workspace restriction: authenticated users with an active Clerk organization are forwarded using server-derived user/tenant identity. Tank remains authoritative for persisted Trigger entitlement, revocation and attested CRM organization binding. No default grant, new UI, direct write route or browser credential is added.

Changed `workspace/app/api/trigger-crm/[...path]/route.ts`: removed founder-only prefilter while preserving authentication, active organization, path/query allowlist and sanitized failures. `tests/trigger_crm_workspace/contract.cjs` verifies signed-in client forwarding and Tank permission-denial propagation alongside existing boundaries.

Exact commands: `node tests/trigger_crm_workspace/contract.cjs` — PASS; `git diff --check` — PASS. Commits `378fb6e` and `36d4224` pushed successfully. Initial commit failed because this fresh checkout lacked a Git author; configured repository-local identity matching existing Codex commits, then committed normally. No production requests or data changes. Fresh combined client integration, independent review and hosted CI remain required.
