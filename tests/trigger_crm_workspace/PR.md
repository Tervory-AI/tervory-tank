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
