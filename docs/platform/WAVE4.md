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
