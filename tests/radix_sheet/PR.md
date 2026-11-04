# Fixes found while auditing shipped Radix

1. Weekly infrastructure work could be cancelled by the room worker at 420 seconds even though its existing bounded scan permits 1,200 seconds. `agents/radix/app.py` gives watch_tick 1,260 seconds, including control/cleanup, still below the existing 1,800-second lease. The regression runs the actual scheduled handler through the actual worker boundary with a logical clock: it fails on main's 420-second timeout and passes with the fix. Scanner budgets, passive/active proxy limits and runtime configuration are unchanged.
2. The shared I8/R6 disposable fixture left weekly/consent rows behind. Running weekly checks followed by lost-TXT watch checks selected stale weekly work instead of the test's watch. The fixture now clears all its test-owned scheduling/consent rows; no production cleanup or behavior change.

Claude opens the PR. No PR is opened, labelled or merged by this task. No main merge, production scan/deploy, provider/key addition, visible UI wording or security-rule exception.

## Inventory on main

Audited `d5d3ea2eeb08c9b7a9061274504f0acf53bab2a6`, including merged #634 and #651 (GitHub confirms both merged). The following are shipped implementations, not assertions about an open PR's routes:

| Shipped feature | Code evidence | Offline path |
| --- | --- | --- |
| Five supplied-business-evidence skills: verification, entity links, account links, site risk, business risk; business-only input and tenant/region scope | agents/radix/verify/routes.py; tank/skills/radix.* | Real private ASGI intake, real code engines, fake external evidence and scoped store. |
| Handed-over source/static, secrets, dependency and IaC checks; tar/zip/git bundle; masked findings and saved jobs | agents/radix/scanlib; tank/radix_repo.py | Real Command upload/Confirm, archive extraction/scanners, fake external CLI/room boundaries, real local Git bundle. |
| Canonical-domain TXT challenges, passive ZAP/Nuclei checks, explicit completion, promotion gate | agents/radix/passive_routes.py; passive_gateway.py; passive_tools.py | Private ASGI + fresh fake DNS, real scoped persistence/gate, bounded fake pages/tool output. |
| Daily/weekly watches, unwatch, list, changes/new/fixed/unchanged; single running lease and tenant RLS | agents/radix/passive_store.py; passive_watch.py | Disposable Postgres scheduler/gateway and same-lock contention. |
| Certificates/TLS, page checksum differences, ClamAV, axe, notices and cookie metadata; honest partial/skipped coverage | agents/radix/passive_r6.py; browser/check.cjs | Fake HTTPS/pages/tool output, real parsers and persistence; existing native proof is not claimed as a new run. |
| Tenant Zenas regulation rechecks, two fact shapes, per-event/domain dedupe, retries/dead-letter | agents/radix/regulation_events.py; tank/event_bus.py | Fake event transport/pages plus actual disposable Redis retry/dead-letter and database queue. |
| Founder active ZAP, immutable own-domain policy, separate bounds; blocked/time-limited scans incomplete | agents/radix/active_policy.py; active_routes.py; active_tools.py | Real Confirm, fake site/scanner, real proof/lease/store; no live scan. |
| Client-admin written consent and withdrawal, domain/user/time audit, runtime recheck/revocation | tank/radix_passive_routes.py; passive_store.py; passive_gateway.py | Real Confirm/$0 receipts and scoped DB, fake proof/requests. Consent wording is the founder's section D1 text. |
| Nmap top-100 connect-only checks, scoped dnsx, separate bounded proxy | agents/radix/passive_infra_tools.py; passive_infra_proxy.py | Fake targets/dials/DNS and CLI output, real policy/collector/persistence; fixed host/port/type constraints. |
| Durable weekly passive/infra pair, restart dedupe and withdrawal | agents/radix/passive_weekly.py | Real worker/scheduler/queue/lease boundaries and fake scanners; worker timeout fixed above. |
| Own-main immutable repository provenance, per-app critical deploy gate, founder confirmed override, fail-open unreachable read | tank/radix_deploy.py; .github/scripts/deploy_changed.py | Real local bundle, fake fixed GitHub/room/Coolify, real Confirm/receipt, per-app isolation and standalone map parity. |
| Private code-template report and evidence links, optional installed PDF, $0 receipt | tank/radix_report.py; Workspace /chats/api/radix/reports | Real Command/private room/download corridor; code renderer and fake observations, no model or remote assets. |
| IaC candidate eval and private frozen gold-source/evidence checks | agents/radix/app.py; gold_sources.py | Real room-key ASGI checks and deterministic supplied fixtures, no automatic skill approval. |

HIBP remains conditional on free domain search and founder configuration. No paid lookup or new integration is added, and a key name alone is not counted as a shipped scan. Approved consent text comes from FOUNDER-SETTINGS D1; the sheet will ask for that text, never supply invented wording. Existing missing explanatory frames for measured hashes/cookie provenance/partial coverage remain listed in #634's evidence; no UI is built for them.

## Delivery steps

1. Inventory and bounded-worker fix, with all existing Radix offline checks and before/after regression.
2. Founder acceptance sheet and the required setting-name additions to FOUNDER-SETTINGS.
3. Exactly one offline case per acceptance row, plus exact row/case parity. `scripts/precheck.sh` runs before each push without skipping Gitleaks or Semgrep. Container runs use --rm, label tervory.test=1 and codex-radix-sheet-prefixed names; all test temporary files use this checkout's .tmp.
