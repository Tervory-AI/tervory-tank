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
