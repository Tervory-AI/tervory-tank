# Platform Wave 4

Base: origin/main at 55b2e224cf6dc41f0507f79b2d608ecb2134957f.
Branch: codex/platform-w4. Claude opens the implementation PR.
Runtime prerequisite: #645, commit 8360d7a6; merge and deploy it before the dependent backend lands.

## D6: morning report

Each regional Tank schedules one report at 07:00 America/Los_Angeles, including DST. The window is the preceding Pacific 07:00 to this 07:00. The report contains ledger totals, known savings, unknown-cost counts, failed jobs, current graduation candidates and deployment workflow outcomes. It is assembled by code. Missing GitHub access is reported as unavailable, not as no deploys.

Set FOUNDER_REPORT_TO, FOUNDER_REPORT_SMTP_HOST and FOUNDER_REPORT_SMTP_FROM to enable; optional SMTP_PORT (default 587), SMTP_USER and SMTP_PASSWORD use the existing approved SMTP service. STARTTLS is required. No live SMTP or provider calls were made during implementation. Founder GET /v1/platform/morning-report exposes configuration status and latest report. Durable claims prevent duplicate sends; failed, interrupted or uncertain deliveries require operator inspection before any manual resend. A stopped box catches up on its current day's report, not historical mail.

Validation: 3 focused tests passed on disposable PostgreSQL, including 23/25-hour DST windows, report assembly, daily deduplication and an uncertain SMTP failure. External sockets disabled; SMTP stubbed. CI remains the full-suite test of record. No retries added.

Missing frames: founder report status/preview and transport configuration help.

## B3/A31: roster validation before policy writes

A durable fingerprint binds the sanitized served roster, approved package bytes/cases, region, tenant policy ownership and evaluation settings. All approved, present, same-region skills run through the existing live Skala eval handler. Pure code packages run their cases without introducing model calls. Private packages use their owner's policy, or that owner's inherited default. Policy upserts, deletes, promotions and rollbacks queue proof before changing the serving policy and return 409 while pending/failed. The roster observer also installs a database barrier covering all policy writers, including automatic shadow/configuration writes. Startup establishes that barrier before serving. The idempotent schema/seed transaction has a transaction-local migration exemption; runtime writes do not.

Results append to skills.models_validated with their roster fingerprint. Failed batches remain failed; the same request never retries paid evals. A changed roster/package/configuration needs new proof. Preflight failures hold the policy without demoting the currently serving package. Existing legacy after-change jobs continue to drain. A matching successful preflight suppresses duplicate after-change evals.

Validation: real PostgreSQL tests cover two approved packages, pending/failed holds, unchanged policy before proof, successful change after proof, cached proof, and a direct SQL writer blocked on an observed roster change. External sockets disabled; eval fixtures execute real pure code.

Missing frame: founder roster-validation pending/failed status and evidence detail.

## B4: retirement requires live probation

The newer approved version needs a delivered live receipt, a clean 30-day interval measured from approval/first delivery/last failed eval/last rollback/last failed or rejected live receipt, and a delivered receipt after that interval. Preview receipts cannot count. Pending revalidations hold retirement. Retirement changes registry state only; version files and previous approval stay available to the existing confirmed rollback path.

Validation: real SQL covers an old approval with no live use, 29 days of live use, delivery after 30 clean days, and a late live failure resetting probation.

## C1/N1: tenant home authority

Founder-only PUT /v1/tenants/{uuid} records us-east or za once; repeat onboarding is idempotent and a different home is 409. GET returns only UUID/home metadata. Workspace's Tank transport resolves that record before sending tenant content and selects only existing configured regional URL/key pairs. Existing founder onboarding writes the immutable metadata to configured registries, US first when connected, then continues the existing Zenas onboarding. A partial mirror is reported as a failure and repeating the same request completes it. No automatic region migration or inferred geography is introduced. Existing tenants also need explicit founder onboarding before new routed work; missing authority fails closed.

Route, tasks, batch and direct skill execution check the tenant record before dispatch, including internal direct skill calls. Zenas content proxy calls cross-check any accepted tenant against the record. Global metadata, public founder-only regional pool operations and PAT/MCP token corridors keep their existing host contracts. Tenant-table access follows the existing RLS rollout.

Validation: 2 focused tests passed (real PostgreSQL + offline Node transport), including founder authorization, immutable/idempotent onboarding, missing authority, wrong-box refusal without a ledger write, ZA routing with the ZA key, and no content call when authority lookup fails. TypeScript noEmit passed. A broader serial ladder run was interrupted after its first case passed because repeated schema setup was taking minutes on this host; it is not counted as a complete test run.

B3 follow-up: promotion/rollback release their pool checkout before queueing validation, then reacquire a row lock and verify the policy snapshot before writing. The prospective proof is transaction-local; a passing replacement can resolve a failed current-policy roster check without weakening the barrier for other writers.

Missing frames: founder tenant onboarding/home-region selection, unavailable-region state, and immutable-home/migration conflict state.

## A8: deadline-bounded price scheduling

Unattended, batch-eligible requests (interactive=false) use the durable queue unless standard/urgent was explicitly requested. Interactive calls keep their immediate response. Each request may name an absolute timezone-aware deadline_at, at most seven days out; omitted deadlines default to 48 hours. The scheduler compares configured offpeak windows/dates (including per-window charge_multiplier when supplied) with the already-authorized provider batch discount. It chooses the earliest cheapest feasible start for the selected policy model, including DST gaps/folds. Provider batches reserve their existing 24-hour completion window plus maintenance margin; batch and time discounts are never assumed to stack.

The job persists not_before, deadline_at, mode and estimated charge multiplier. Maintenance rechecks current prices, the policy snapshot, tenant home and cost cap before dispatch. If no discounted window fits, direct execution may use the cheapest feasible known rate. Expired queued work fails without dispatch. Direct dispatch is bounded by the remaining deadline; interrupted or uncertain work is not replayed. Existing provider status/cancellation behavior remains; a provider completion window cannot guarantee remote availability. No new provider, alias, retry or price is invented. Expired batch items do not submit or use the existing fallback retry.

Missing frames: deadline entry, scheduled start/price explanation, queued/expired status.

A8 validation: 4 tests passed in 177.18s on this host: cheapest versus first window, deadline fallback, provider completion budget, DST gap/fold, persisted waiting, exactly one dispatch and expiry without dispatch. Price and provider boundaries were stubbed; SQL was real. A missing native-provider field in the initial test double was corrected before this passing run. No test retries or production retries were added.

## A22: multiple deployments per alias

Both LiteLLM router configurations explicitly select simple-shuffle, so multiple deployments under one approved model_name are balanced by LiteLLM. No alias, provider, key, fallback or replica was added. Both model lists exactly match base 55b2e224; currently neither file has replicated aliases, so no multi-deployment production traffic was claimed. Runtime-only change: commit 8360d7a6, PR #645, pushed before the standing no-PR rule. It redeploys the main stack and tervory-tank-za and must land before this dependent backend.

Verification: both YAML files parse, strategy is explicit and model_list is unchanged. The routing contract is documented in the official LiteLLM routing guide: https://docs.litellm.ai/docs/routing . No provider calls were made.

## C3/C6: task board and feedback backend

GET /v1/task-board returns receipt-derived status values: queued, running, delivered, unverified or failed. Existing /v1/tasks CRUD retains its execution status for compatibility and adds board_state plus receipt outcome/feedback metadata. A completed task without an owning delivered receipt is unverified. A wrong verdict, an uncertain receipt, or a failed task with a sent/delivered receipt also remains unverified. Ledger joins and every task mutation include the owning tenant.

POST /v1/tasks/{id}/feedback accepts accepted or wrong. Wrong requires a nonblank note (at most 1000 characters). Actor/tenant come from the existing authenticated Workspace headers; body overrides have no authority. Wrong maps to the existing rejected training verdict. Feedback, the tenant transcript's eval verdict, training collection and cache invalidation commit together. An unverified answer may be marked wrong, but cannot be turned into a delivered answer by an accepted verdict. Workspace has server-only /api/task-board and /api/tasks/{id}/feedback proxies; no screens were invented.

Tasks accept deadline/priority, run unattended eligible work through the scheduler, remain queued while waiting, and finish only with the durable job. Job/receipt/task completion is transactional. This also fixes treating QueuedResponse as a completed answer.

Validation: real SQL covers delivered/unverified states, wrong+note validation, a foreign task and foreign receipt reference, atomic feedback rollback, and deferred task completion. The offline Node proxy proof checks forged identity fields, required note, recorded-home selection and the correct regional key. TypeScript noEmit passed.

B3/A22 follow-up: validation observes every deployment, including replica replacement, while ordinary model pickers still see one alias. Only a hash of deployment identity/endpoint metadata is retained; provider keys never enter that snapshot. An unavailable served roster holds changes. A durable eval-start claim turns an interrupted preflight into failed proof without replaying possibly charged cases.

B4 follow-up: live policy-selected code receipts also count when their skill column is absent but model names the exact version. Preview receipts are explicitly marked #preview and excluded.

## Missing frames

- Task board with delivered/unverified states and receipt detail.
- Wrong-answer feedback sheet with required note, validation and saved/error states.
- Founder report preview/status and SMTP configuration help.
- Roster-validation pending/failed state and evidence detail.
- Founder Tank onboarding, unavailable-region state and immutable-home conflict.
- Deadline input, scheduled start/price explanation and expiry state.

## Reproducing the focused checks

Use disposable PostgreSQL via POOL_SCHEMA_DATABASE_URL (never a deployed database), PYTHONPATH=tank:agents/_chassis and Python 3.12. Run the six tests/test_platform_*.py modules serially with pytest -q --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1. They stub SMTP, repository reads and provider boundaries. The cloud harness creates a private localhost cluster, strips provider credentials from the environment and cleans it up; later runs set synchronous_commit=off and fsync=off only in that disposable cluster to avoid host disk waits. These checks prove SQL behavior and dispatch ownership, not power-loss durability.

Affected Workspace/region contracts: test_tenant_registration_workspace.py, test_command_1b_workspace.py, test_homes_region.py and test_za_region.py: 41 passed in 20.39s. Their existing fixture tenants are explicitly onboarded to their test box; the new region tests exercise missing, conflicting and foreign authority. Registry lookups use the same hard deadline as content requests and preserve existing transport header types. No live mail or paid provider was contacted.

Before every subsequent push, CI's exact lint is required:

    ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"

Full suite is CI's record; no parallel offline suite or 50-run loop was run for this wave.


Final connection boundary: TANK_API_KEY_ZA retains its existing homes/feeds scope. Foreign tenant content and mirrored Tank onboarding use opt-in TANK_CONTENT_API_KEY_ZA/US settings, reusing an already-approved destination Workspace key only when the founder enables that connection in Coolify. Empty content credentials refuse the route before sending tenant content. The runtime-only follow-up is in #645; no key was generated or copied by the builder. PAT, MCP/OAuth and device corridors retain their fixed token host; untrusted body fields never choose their region. Both Workspace and bearer identities check their tenant's recorded home before Command tools can execute.

The combined Wave 4 plus legacy lifecycle checks passed 40 tests in 300.73s; Command, personal-token and recorded-home checks passed 97 tests in 50.67s. Legacy committed-swap tests now set up legacy SQL swaps directly; the Wave 4 API tests require preflight. Retirement fixtures include actual live deliveries. An unavailable live roster holds policy writes and eval dispatch while free paths remain available; validation bypasses the model-picker cache and file fallback.


Final transport checks passed serially: recorded-home routing (including no homes-key fallback and opaque token/device host preservation), task feedback, founder memory, tenant bus, Base workflow, Trigger CRM and squad UI contracts; TypeScript noEmit passed. The runtime prerequisite head is 4f611af5 on codex/platform-wave4-runtime (#645), including only setting names and explicit replica balancing. Backend uses those settings only after that config is deployed. No new PR was opened after the standing instruction.

CI integration follow-up: legacy disposable tenants now have explicit home records (including ZA identity/watch fixtures); repository and route unit transports supply known home metadata. Routing refusal assertions remain. The Tank schema retains its historical prefix and its generated memory footer, with the migration exemption installed only by the startup transaction. Package/policy/served-roster proof is reused across prospective batches; derived jobs reference the original eval and cannot dispatch again. Workspace transports preserve their injected fetch boundary and recognize the existing Moot tenant header.

Serial integration checks after these corrections: 76 passed in 30.72s; 155 passed in 42.36s with one additional case unavailable locally because this disposable PostgreSQL lacks pg_trgm; 241 passed, 2 optional skips, 1 long fixture deselected in 90.48s; 16 affected Workspace/schema-source checks passed in 25.12s. The 200-run graduation fixture is left to CI. Full-suite results are reported against the pushed head, without adding retries.

Roster transitions carry a durable epoch: returning from roster B to a previously validated roster A reruns every approved skill. Proof reuse applies only within the same observed roster epoch.

CLI sign-in listing/revocation keep the issuing Tank and its dedicated approval credential, allowing users to revoke old tokens in either region. New token creation and content requests still require recorded-home routing.

CI follow-up: a perfect rerun of an already-approved legacy suite is valid preflight proof even when that saved suite predates new-approval eligibility rules. This never approves a version or relaxes source-review/approval gates. A short regression exercises the real legacy package suites without the 200-run fixture. Moot capability authentication precedes registry access. Chrome skips first-run setup, retains port=0/DevToolsActivePort, has a bounded 30-second startup budget and captures bounded startup stderr on failure; no launch retry is added.

## Item 8: founder Ask/Auto for every paid step

Founder decision 27 Oct takes precedence over decision-list item 22 and AGENTS.md rule 10. Missing settings mean **Ask**, including existing installations. The global paid-work pause still blocks Ask confirmations and Auto dispatches. No setting can lift it. Free code, exact/semantic cache and existing free search/browser work do not ask for paid permission.

Founder tools are available in `/chats` without a paid planner: `/paid-steps` proposes `platform.paid_steps`; `/paid-step <step_id> ask|auto` proposes `platform.paid_step.set`. Confirm the ordinary action card to read/change the setting. `platform.paid_step.approve` confirms one waiting operation. Other users cannot see or execute these tools; founder membership is checked again at confirmation. The HTTP controls are GET/PUT `/v1/controls/paid-steps`, GET `/pending` and POST `/approve`. Settings and changes are stored under the platform tenant with actor/time audit. Each regional Tank owns its settings and approval inbox; use its existing founder corridor. No new cross-region credential or transport was introduced.

Catalog: `vendor.brave`, `vendor.google_places`, `vendor.apollo`, `vendor.context_dev`, the research bundle's `vendor.perplexity.search_web` and `vendor.perplexity.fetch_url`, `hf.jobs.photogrammetry`, `hf.jobs.trellis2`, `hf.jobs.training`, and `model.rung1.<served alias>` / `model.rung2.<served alias>` for each served model. New aliases automatically default to Ask. Apollo is catalogued for its existing import/vendor boundary; this branch introduces no Apollo outbound request. Native research performs searches/fetches inside one provider request, so those two permissions cover that exact research request's native tool bundle, followed by its model permission.

Ask stores an owning tenant/run/step/input digest, then suspends the exact existing coroutine before dispatch. No prompt, credential or vendor body is saved in the approval row. A founder confirm card appears in the current founder chat or the founder-only Paid step approvals inbox (refreshed when listing threads). Cancel, expiry, changed inputs and the global pause prevent dispatch. Approval is claimed atomically once. Switching just that step to Auto also releases its waiting calls, subject to the global pause. Original request/work deadlines remain absolute. Active execution timeouts exclude human waits; concurrent seat budgets remain independent. Routing rechecks cancellation, policy revision and tenant home after a wait. Gateway fallbacks and retries are disabled for paid model dispatch so one approval cannot silently buy a different alias or a second attempt. No retry was added.

JSON callers receive 202 with `paid_run_id` and poll the authenticated `/v1/paid-runs/{id}?tenant_id=...` result. `/chats` saves waiting state and resumes its original turn/card. Room OpenAI completion requests send heartbeat comments/whitespace during the wait, then their original completion. Worker claims keep another worker from repeating a parked dispatch; Tank SQL pool connections are released during human waits. Base's existing trial worker retains its own trial lock and writes results through its existing result path. Base requests a bound Tank authorization before each Context.dev credit reservation; Rig obtains approval before its once-only HF claim/charged receipt. Their client prerequisite is separately pushed at 8c0362fc on `codex/platform-w4-paid-runtime`; deploy it before this backend. Earlier Wave 4 runtime prerequisite #645 still applies. Claude opens PRs; none was opened for item 8.

A process restart cannot restore a Python continuation. Worker leases mark its run/approvals interrupted, with no automatic replay; inspect that run before starting replacement work. Ask waits expire after 24 hours or the work deadline, whichever comes first. Existing external SDK/proxy lifetime limits still apply; a disconnected SDK request is cancelled before any unapproved dispatch. Backend status, receipts and existing saved chat events provide recovery evidence.

Missing frame: **Founder paid-step settings** with one Ask/Auto control per vendor/model rung/HF job, Ask as the default, the global-pause override, audit/save/error states and regional ownership. Also missing: the founder pending-approval/run-detail view, and client waiting-for-founder/cancelled/expired/interrupted states. No settings screen was invented.

Serial local proof: 13 paid-step/client/real Context.dev SQL checks passed in 9.95 seconds; the runtime transport proof passed 3 tests in 0.16 seconds. The broader serial protocol check was interrupted after progress without a final pytest result and is not claimed as a pass. CI is the full-suite test of record. No live paid provider, HF job or SMTP delivery was called, no parallel full offline suite or 50-run loop was run.

Final focused extension: 24 tests passed in 12.77 seconds, covering default Ask, independent model rungs, global pause after approval, founder chat tools/cards, continuation without repeated POST, real HF claim/receipt boundaries, expiry/cancellation, room JSON/SSE completion, RLS schema reapplication, worker leases, existing roster validation and price scheduling. SQL used the disposable localhost cluster; external sockets were disabled.

Follow-up proof: 28 targeted approval, revocation/cancel, timeout-isolation, MoA shadow and pinned/Auto routing checks passed in 14.60 seconds. Cancelling a waiting chat now finishes its queued task as failed without dispatch. Legacy transport fixtures explicitly select Auto for their synthetic aliases; production defaults are unchanged. Heartbeat maintenance recovers from a failed SQL tick without retrying paid work.

Additional serial protocol checks: 91 research and regional routing tests passed in 9.31 seconds. The research migration test explicitly authorizes its fixture bundle after switching to its new disposable pool. The new inbound room completion test is recorded in the existing static boundary audit; no provider exception was added.


Direct-client coverage also includes Base's existing SkillClient, Ghost, the retained Market Lab native research path, the isolated researcher and worker proxy. Seven offline transport tests passed in the backend checkout (1.03s) and the standalone runtime branch (1.23s). Runtime prerequisite head is 8c0362fc978428455b40cac36a6aa8772df71d91; all of its changes are included in this dependent branch so the diff disappears after Claude lands the prerequisite. No PR was opened or main merged.

Final continuation/batch extension: 54 checks passed serially in 72.44 seconds. [The complete file/line change index](PAID_STEP_CHANGES.md) includes runtime prerequisites, backend gates and explicit fixture changes.

CI integration repairs: the worker-alive function keeps a fixed search path and returns only a platform heartbeat boolean, using the schema owner's existing BYPASSRLS authority; it no longer requires SET privilege on app.tenant_id. Role/migration and routing checks passed 35 tests in 13.95s on a fresh disposable cluster. The full room-schema RLS probe is left to CI because this host's bundled PostgreSQL lacks pg_trgm. Isolated literal-SQL/Tiger fixtures now select their fake runtime explicitly; RouteLLM and batch-cache fixtures authorize their synthetic aliases before dispatch. Three formerly affected cache/shadow/Auto checks passed in 13.39s. The single previously failing Rig capture and cart checks passed 11 tests in 6.34s; CSS motion is disabled for the whole frozen-clock/font-ready comparison, with exact equality preserved and no retry/loop.

A founder workspace card may launch a platform-owned eval. The source tenant/card is recorded separately from paid-run ownership, so the same executing card is returned while waiting and cannot be replayed or marked stale during an approved continuation. Only an already-owned exact source card can inspect that waiting metadata. Approval/chat tests cover this path and foreign source-card denial: 22 focused checks passed in 15.31s.

The existing manual HF LoRA launcher also honors `hf.jobs.training` (default Ask). Its CLI waits in the same founder inbox, binds the private repository, snapshot day, runtime/cost bound and script digest, and rechecks the global pause immediately before `run_uv_job`. Existing reservation/provenance/billing reconciliation remains. No training job was launched by the builder. The real SQL approval and legacy fake-HF checks passed 38 tests in 7.61s.

CI's remaining teardown error exposed completed implicit runs that could outlive an event loop. Ownership is now removed synchronously on completion; free/Auto calls create no cleanup task, a completed/foreign-loop context cannot be reused, and shutdown only cancels active runs on its own loop. The closed-loop regression plus approval/RouteLLM coexistence checks passed 21 tests in 17.92s. No test skip or retry was introduced.
