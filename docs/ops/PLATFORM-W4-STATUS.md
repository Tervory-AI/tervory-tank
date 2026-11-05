# Platform wave 4 completion

Baseline: `15432cb522a7922359ad9174aed3784480b34b50`, after #682 merged.
No live settings, data, approvals or deployments are changed by this branch.

## Gate 1

- B4 — already on main: `tank/skala_probation.py:10` calculates 30 clean days
  after approval, failed evaluation or rollback; pending revalidations block
  retirement. `tank/skala.py:667` retires state only and retains the package;
  `tank/skala.py:654` permits explicit rollback to a previously approved version.
- A22 — already on main: `litellm/config.yaml:830` and
  `litellm/config.za.yaml:864` select LiteLLM cost-based routing. Multiple
  deployments share their model group; `tank/routing_data.py:16` retains all
  group members. Existing host/privacy restrictions can pin the permitted
  deployment; load balancing must never bypass those restrictions.
- A8 — added deadline-aware scheduling to the existing off-peak queue.
  `RouteRequest.deadline` is an optional timezone-aware timestamp. The selected
  model's published off-peak windows and existing provider batch discount are
  compared with its current price. The cheapest feasible option wins; equal
  prices prefer earlier completion. Foreground work reserves 120 seconds and
  provider batches require their existing 24-hour completion window. No new
  provider, model, paid route or rate is introduced. Requests without a deadline
  retain the existing explicit off-peak behavior. Polls recheck current prices,
  policy and the deadline; an expired job fails without dispatch. Waiting and
  foreground execution are bounded, but provider completion is not guaranteed.
  Receipts preserve actual measured costs; predicted discounts are not savings.
  The protected `run_route` snapshot changes only its authorized dispatch-window
  predicate; cache and task execution snapshots remain intact.

## Gate 2

- C1/N1 — added `tank/tenant_regions.py` and `tank.tenants`. The founder assigns
  a new tenant's `us-east` or `za` home through
  `PUT /api/tenants/<tenant UUID>/home`. The US Tank is the directory. Assignment
  is idempotent; a changed home requires a separate migration. An assignment to
  ZA refuses existing US tenant data, including conversations and product tables.
  Workspace's tenant-aware clients resolve the record before transporting
  content; Zenas uses the same directory. Missing legacy records retain the
  existing box contract. Invalid/unavailable metadata fails before content is
  sent. Other-region content requires its full content key; homes/feeds keys
  retain their existing scope. Direct route/task/skill and command authorization
  checks reject a different recorded home.
- C3/C6 — `tank/workspace_board.py` exposes tenant-owned tasks and results.
  Delivery comes from the ledger; a legacy `done` without delivery proof is
  Unverified. Queued tasks retain their receipt and finish through the existing
  queue. Results contain recorded content, measured cost or an explicit unknown,
  and no fixture download URLs. Useful, Not useful and Wrong feedback keep the
  originating task/ledger identity and an optional 1,000-character note. The
  existing feedback writer still produces the learning evidence.
- B3/A31 — already on main: `tank/schema.sql:2194` queues policy-model changes;
  `tank/skala_revalidation.py:170` drains durable evals, and
  `tank/routes_registry.py:57` installs it. Added live membership observation,
  including current tenant overrides and held proposals. Price/key rotations and
  generated deployment IDs do not fabricate a membership change. Private cases
  use their owner's model permissions. First observation records the baseline.
  Later changes run every approved package's evals and append the fingerprint to
  `models_validated`. Routine writes/promotions wait for roster work; a held
  proposal is rechecked before release. Completed paid evals are not replayed.
  The existing target-model gate and explicit rollback path remain in use.
- D6 — `tank/morning_report.py` builds a regional midnight–07:00 Pacific digest
  from ledger activity, canonical comparable savings, failed jobs, deployment
  observations and candidate comparisons. Deferred work uses its dispatch night;
  evaluation failures count once across their receipts. The scheduled email uses
  existing SMTP setting names and a durable daily claim. Uncertain SMTP delivery
  is not retried. Optional GitHub deployment history is marked incomplete when
  unavailable/truncated; it is not an application-health attestation. No model,
  promotion, deployment or production-data operation builds this report.
- Setting names and conditional regional connections are documented in
  `docs/ops/FOUNDER-SETTINGS.md`; runtime configuration is unchanged.
- The frozen registry extension preserves every tool, adapter, visibility set,
  dispatch branch and existing route order. It adds six routes, the report task
  and SQL inside the existing platform block; the freeze origin is unchanged.

Missing frames: C6 Feedback (desktop/mobile and empty/loading/error states) and
founder Paid steps settings (per-step Ask/Auto plus global pause/resume). These
are listed as uncreated in `docs/figma/workspace/REGISTER.md`. The backend is
available through authenticated APIs while those frames are pending.

## Review locations

Gate 1 (`ea9b7cfd7f6a1fd23ea0860921036ba514e739a5`):
`tank/main.py:681` accepts the aware deadline and `tank/main.py:1445` changes
only the off-peak dispatch predicate; `tank/offpeak_schedule.py:9` selects
known feasible prices; `tank/priority_queue.py:103` plans/waits/bounds dispatch;
`tests/test_offpeak_deadline.py:1` exercises deadlines, receipt cost and DST;
`tests/tenant_rls/run_route.pinned:207` and
`tests/test_platform_routellm_serving.py:150` preserve the protected route body.
`docs/ops/PLATFORM-W4-STATUS.md:6` records the already-main B4/A22 evidence.

Gate 2 source commit: `be88402d9c61bfebee2ec4f9c34fd16ea4b09c9d`.
Fixture follow-ups are `ab7641d6` (Rig import order) and `bfc92b6a`
(explicit legacy-home results for existing routing tests), followed by
`82b0594a` (remaining auth/lifecycle fixtures and an inert placeholder marker).
These locations identify each changed file; additional hooks in a file are
listed where they are needed to review the behavior.

| File:line | Change |
| --- | --- |
| `tank/tenant_regions.py:1` | Strict founder onboarding, immutable home, directory and route guards. |
| `tank/workspace_board.py:1` | Owned task/results projections, delivery truth and Wrong + note. |
| `tank/roster_validation.py:1` | Live roster fingerprint, durable all-approved eval jobs and policy gate. |
| `tank/morning_report.py:1` | Regional 07:00 Pacific report, actual metrics, read-only deploy feed and durable SMTP claim. |
| `tank/main.py:752` | Feedback verdict; policy checks at 956/2090; region checks at 2692/2803/3149/3524; queued task at 3122; feedback learning scope at 3882. |
| `tank/command.py:1685` | Recorded-home guard before conversation access. |
| `tank/priority_queue.py:185` | Deferred result finishes its originating task on the same receipt. |
| `tank/skala_revalidation.py:87` | Link eval receipts to jobs, record fingerprint, hold proposals until all roster evals finish; observer at 248. |
| `tank/routes_registry.py:58` | Six API endpoints via three product routers; report lifecycle hook at 84. |
| `tank/schema.sql:3126` | Additive home/report/roster/feedback SQL in the original platform block. |
| `workspace/lib/tank.ts:217` | Private callers use tenant routing; directory and content helpers at 1481. |
| `workspace/app/api/zenas/tank.ts:12` | Private tenant calls use the same directory and full regional key. |
| `workspace/app/api/tenants/[tenantId]/home/route.ts:1` | Founder-only, same-origin home assignment API. |
| `workspace/app/api/workspace/tasks/route.ts:1` | Session-derived task read API. |
| `workspace/app/api/workspace/results/route.ts:1` | Session-derived results read API. |
| `workspace/app/api/workspace/tasks/[taskId]/feedback/route.ts:1` | Same-origin feedback API with strict verdict/note. |
| `tests/test_platform_workspace.py:1` | Real SQL/ASGI home, task, feedback, queue and client transport regressions. |
| `tests/test_platform_roster.py:1` | Real eval handler, owner permissions, held proposals and worker wiring. |
| `tests/test_platform_morning.py:1` | Frozen clock, SQL accounting, duplicate claims, TLS and deployment feed checks. |
| `tests/platform_region_contract.cjs:1` | Real Workspace modules, identity/credentials, private clients and metadata failure/prototype cases. |
| `tests/tenant_directory_fixture.cjs:1` | Legacy content-contract harness supplies only the explicit missing-home metadata response. |
| `tests/command_1b_contract.cjs:1` | Keep existing streaming/content assertions with the new metadata fixture. |
| `tests/command_tools_contract.cjs:1` | Keep catalogue/name/identity assertions with the metadata fixture. |
| `tests/test_command.py:43` | Explicit legacy missing-home response in the identity fixture. |
| `tests/test_command_repo_tools.py:109` | Explicit tenant-bound missing-home response in the read-only repository fixture. |
| `tests/test_personal_tokens.py:31` | Explicit legacy home in token identity tests; asserted token tenant/region remain unchanged. |
| `tests/test_registry_extensions.py:48` | Start/cancel the appended report task while retaining the original task order. |
| `tests/test_rig_cart_admin.py:13` | Load its existing Rig path fixture before importing rigbox, so precheck can collect the selected file independently. |
| `tests/test_agent_chassis.py:40` | Explicit missing-home fixture for its database-free caller/skill tests. |
| `tests/test_moa_integration.py:23` | Explicit legacy home fixture while preserving MoA route, budget and privacy assertions. |
| `tests/test_za_region.py:436` | Fake connections return no onboarding record for their existing legacy region scenarios. |
| `tests/test_platform_routellm_serving.py:192` | Eval job UUID and concrete RouteLLM receipt assertions. |
| `tests/skala_b3_b4/test_lifecycle.py:67` | Clear observer state in its disposable database fixture. |
| `tests/test_tenant_rls.py:266` | Preserve full routing/task-body pins around the authorized queue arm. |
| `tests/tenant_rls/run_task.pinned:1` | Full task body after the authorized queued-result handling. |
| `tests/registry_frozen.golden:7987` | Explicit six-route/lifecycle/platform-SQL extension; all existing contracts preserved. |
| `docs/ops/FOUNDER-SETTINGS.md:9` | Report and regional connection names; no values/configuration changes. |
| `docs/ops/PLATFORM-W4-STATUS.md:30` | Main evidence, implementation scope and frame gaps. |

## Gate 3

`docs/acceptance/platform.md:1` covers the Workspace shell, dashboards, chats,
ledger/savings, Tank ladder and receipts, scheduling/lifecycle, tenant homes,
task/results/feedback APIs, morning report and product registries in 26 rows.
`tests/acceptance/test_platform.py:1` provides one executable offline case per
row and an exact identity/name mapping check. Existing production approval,
paid-work and region guards remain applicable to any live acceptance run.

## Local validation record

- Gate 1: 25 targeted cases passed in 125.30 seconds. Required precheck passed:
  871 passed, 3 skipped in 2497.80 seconds; lint, Gitleaks and OSV passed.
- Gate 2: TypeScript completed with no errors. Both existing Command Node
  contracts and the new real-module regional HTTP contract passed.
- The final Gate 2 precheck selection completed at `bfc92b6a`: 2,003 passed,
  8 skipped, 7 failed in 2651.32 seconds. Its failures were five legacy fake
  connections without the new home query, one lifecycle mock without the report
  task, and an inert credential marker without the recognized placeholder prefix.
  `82b0594a` corrects all seven. The affected repository/token/registry files then
  passed 96 cases in 37.10 seconds, and the regional Node contract passed again.
  Earlier affected chassis/MoA/ZA/receipt checks passed 96 in 68.78 seconds.
- All 26 Platform acceptance cases and their exact mapping check passed inside
  that precheck selection. Its eight opt-in skips cover assembled CLI dependencies
  (four), the managed-cloud pilot, real Traefik proof, real build/loopback and
  isolated room/LanguageTool checks. None of the Platform acceptance rows skipped.
- The precheck process at `bfc92b6a` is not claimed green. Corrected regressions
  have focused proof; final-head hosted CI is the release record. Root's latest
  no-additional-local-scans instruction supersedes fresh local scan runs.
  Local Semgrep is not a pass; its launcher was removed so application fixtures
  cannot select it. No scan policy, suppression or exception was changed.
