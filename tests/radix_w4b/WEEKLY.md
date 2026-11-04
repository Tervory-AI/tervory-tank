# Wave 4b item 3 — durable weekly passive + infrastructure monitoring

Audit: main `981ac096` has R4's daily/weekly passive watch scheduler but no infrastructure pair. This change reuses that room scheduler and its transaction-scoped global WATCH_LOCK, ahead of ordinary watches and behind queued regulation work. No additional scheduler service, model, provider, email or page.

Each enrolled tenant/domain has a persisted due time and the same TXT challenge. Written client consent enrolls the domain if its proof row exists; issuing its proof afterward also enrolls it. Founder enrollment uses a trusted Tank-derived founder header and the unchanged own-domain list, when proving or watching a domain, or after a successful own active/infra lease. An old proof/watch with no persisted founder authorization is not guessed to be a founder workspace: the founder can re-confirm its existing prove/watch command to record that scope. The initial automatic due time is seven days after enrollment. Enrollment is idempotent and does not reset an existing due time.

For each due period, one transaction inserts **one passive run and one infrastructure run**, records both ids under unique `(tenant, domain, period, kind)` keys beside the runs, then advances the next due time seven days. This is a sequential pair of existing run types, not two overlapping scans. Pending rows survive restart, and ordinary manual work owning the global lease leaves the same pair queued. The worker re-enters the persisted owner's tenant scope. A gateway busy race requeues the same row; a scan/proof failure is recorded as incomplete rather than inserting another run for the week. A later week gets its own independent pair.

The passive phase uses its original HTTPS proxy bounds and R6 watch checks. The infrastructure phase uses the separate bounded TCP/DNS proxy, with consent and TXT rechecked before each phase. Stored weekly challenge ownership permits the scheduled check after the original one-day manual proof expiry, exactly as the existing persistent watch does; it never bypasses runtime TXT verification. Withdrawal disables client weekly enrollment and invalidates pending/running consent-bound leases. TXT disappearance disables monitoring before any scanner starts. An explicit weekly watch's future due time is aligned to the paired passive run to avoid duplicate weekly work; explicit daily watches retain their schedule.

Findings remain available through each recorded run's existing radix.findings/radix.report path and radix.changes. The pair's ids, domain, tenant and scheduled period are persisted in weekly_runs. There is no new visible wording. The approved consent wording remains the missing frame listed in CONSENT.md.

## Changes by file/line

- `agents/radix/passive_weekly.py:8`: atomic period deduplication and pair queue; `:43` scoped sequential execution and restart/busy behavior.
- `agents/radix/passive_watch.py:26`: call weekly work while holding the existing worker lock.
- `agents/radix/passive_store.py:102`: weekly domain/run tables; `:232` stable TXT challenge renewal; `:251` tenant-domain enrollment and weekly watch alignment; `:323` admit persisted weekly proofs, with runtime verification still mandatory; withdrawal/TXT loss disable monitoring.
- `agents/radix/schema.sql:112`: additive/idempotent weekly tables and tenant RLS policies above generated memory.
- `agents/radix/active_routes.py:15`: reuse a queued infra run id and enroll freshly verified founder scope.
- `agents/radix/passive_gateway.py:76`: consent validation also protects a weekly passive phase; founder weekly phase still checks the own-domain policy before DNS.
- `agents/radix/passive_routes.py:119`: trusted founder proof enrollment; existing watch route enrolls founder scope after proof validation.
- `tank/radix_passive_routes.py:81`: derive the room's founder flag from authenticated server-side identity, never a browser-provided flag.
- `agents/radix/passive_infra_proxy.py:66`: final transport hardening: Nmap ends after connect, with no forwarded application payload/banner; DNS coverage records both name and record type.
- `agents/radix/passive_infra_tools.py:91`: require A and AAAA coverage for every candidate before declaring a complete check.
- `tests/test_radix_weekly.py:24`: real worker/global locks, pair deduplication, restart, expiry, withdrawal, tenant scope, TXT loss and manual-scan contention.
- `tests/test_radix_infra.py:97`: exact DNS question coverage fixture; `tests/test_radix_passive.py:64`: clear new disposable fixture tables between tests.

## Verification

Full Radix/Command, event-bus, R4/I8/R6/I2, deployment and repository-tool selection: **590 passed, 256 warnings, 437 subtests passed in 118.63s**. After the final DNS coverage and proof-renewal changes, the final focused selection passed **9 tests in 1.71s**; WEEKLY-PROOF.txt records its result. Real Nmap/proxychains/dnsx rechecked with final source, --network none, fake upstreams: 100 TCP connects, six DNS queries, four findings, both checks complete. All offline, using disposable loopback Postgres/Redis; no production scan, deployment or configuration change. Exact CI lint, changed room lint and whitespace checks passed; secret checks passed **2 tests in 15.60s**. Hosted CI/live cadence follow review and merge.
