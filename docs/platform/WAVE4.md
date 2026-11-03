# Platform Wave 4

Base: origin/main at 55b2e224cf6dc41f0507f79b2d608ecb2134957f.
Branch: codex/platform-w4. Claude opens the implementation PR.
Runtime prerequisite: #645, commit 8360d7a6; merge and deploy it before the dependent backend lands.

## D6: morning report

Each regional Tank schedules one report at 07:00 America/Los_Angeles, including DST. The window is the preceding Pacific 07:00 to this 07:00. The report contains ledger totals, known savings, unknown-cost counts, failed jobs, current graduation candidates and deployment workflow outcomes. It is assembled by code. Missing GitHub access is reported as unavailable, not as no deploys.

Set FOUNDER_REPORT_TO, FOUNDER_REPORT_SMTP_HOST and FOUNDER_REPORT_SMTP_FROM to enable; optional SMTP_PORT (default 587), SMTP_USER and SMTP_PASSWORD use the existing approved SMTP service. STARTTLS is required. No live SMTP or provider calls were made during implementation. Founder GET /v1/platform/morning-report exposes configuration status and latest report. Durable claims prevent duplicate sends; failed, interrupted or uncertain deliveries require operator inspection before any manual resend. A stopped box catches up on its current day's report, not historical mail.

Validation: 3 focused tests passed on disposable PostgreSQL, including 23/25-hour DST windows, report assembly, daily deduplication and an uncertain SMTP failure. External sockets disabled; SMTP stubbed. CI remains the full-suite test of record. No retries added.

Missing frames: founder report status/preview and transport configuration help.
