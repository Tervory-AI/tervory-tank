# Radix: proven-domain watches, regulation rechecks and bounded R6 measurements

Radix watches a tenant's proven domain daily or weekly, re-checks its TXT proof before every run, and stops the watch when that proof is removed or changed. A run performs the existing passive scan followed by bounded TLS/certificate, page-hash, malware, accessibility, notice and cookie measurements. Zenas regulation events queue notice/cookie-only runs for the same tenant's watched domains. Results and measured facts return through the existing `radix.changes` card; no page, chat tool, static labels, explanatory copy, email or model call was added.

**One PR: #634, branch `codex/radix-w3`, carrying R4 + I8 + R6.** R4's eight commits were inherited at `5359bf0a12c15371feb09a8810cd5526eaa485c3`. This PR includes that work directly; it no longer waits for another R4 merge. Main has not been merged. The founder merges; merge main only if Claude reports a conflict. The earlier I8 checkpoint and commands remain in `tests/radix_i8/PR.md`; its HTTP-only limitation is superseded by the browser observer delivered here.

## R4 audit: inherited versus added

| R4 item | Disposition | File and line |
| --- | --- | --- |
| Confirmed watch/unwatch, watches and changes; Radix squad/founder access | **already on R4** | `tank/command.py:46`, `:1266`, `:1368`, `:1520`; `tank/radix_watch.py:8` |
| TXT proof re-check; stop with missing/changed reason before any scan | **already on R4** | `agents/radix/passive_gateway.py:28`, `:67`; `agents/radix/passive_store.py:309` |
| Passive scan with an honest target sha256 artifact | **already on R4** | `agents/radix/passive_watch.py:47`; `agents/radix/passive_store.py:100` |
| Existing scheduler and globally one running scan | **already on R4** | `agents/radix/app.py:70`; `agents/radix/passive_watch.py:21`; `passive_store.py:74` |
| Tenant/domain comparison; severity changes are new; original rule text | **already on R4** | `agents/radix/passive_store.py:114`, `:230` |
| Room-owned watch table joins the existing tenant RLS rollout | **already on R4**, restricted-role catalog lookup **added here** | `agents/radix/passive_store.py:40`; avoids requiring access to Tank's schema |
| Explicit missing/changed TXT, due scheduling, severity and unwatch regressions | **added here** | `tests/radix_i8/test_events.py:310` |
| Comparison state and measured item appear in the existing Rule value | **added here** | `tank/command.py:1368`; raw comparison arrays and original rule IDs remain intact |
| A completing watch is independent of a newer law-change queue row | **added here** | `agents/radix/passive_routes.py:85`; `tests/radix_r6/test_checks.py:273` |

Tank's `_startup` at `tank/main.py:755` still applies its idempotent schema. No Tank table or Tank startup change was needed. There is no second scheduler. `WATCH_LOCK`, the existing gateway lease and `passive_one_running` remain the arbitration boundaries.

## R6 and I8 changes by file and line

| File | Line | Result |
| --- | ---: | --- |
| `agents/radix/passive_r6.py` | 23 | A deadline budget inside the existing 420-second lease; bounded tool processes, cleanup on timeout/cancellation and keyless child environments. |
| `agents/radix/passive_r6.py` | 36 | ClamAV uses the existing room memory cgroup; its child is selected first for OOM termination so the app can record a skip and continue. No capability or memory-limit change. |
| `agents/radix/passive_r6.py` | 96 | Raw page sha256 differences: URL plus old/new hash, including new/changed/gone. Previous sampled pages are prioritized to avoid false gone results when links reorder. A linked 404 is gone; a 500 or incomplete fetch does not replace the snapshot. |
| `agents/radix/passive_r6.py` | 103 | Retain complete testssl JSON objects if a bounded run is cut short; incomplete checks remain partial/skipped. |
| `agents/radix/passive_r6.py` | 132 | Proxied HTTPS root and at most ten linked same-host HTML pages. Malware fetches close HTML responses before reading their bodies. Page/file discovery caps list skipped URLs and reasons. |
| `agents/radix/passive_r6.py` | 250 | Reuse `tls_findings` for expiry and negotiated protocol; testssl runs protocol/certificate checks only, with `--ip=proxy --nodns=none` and the fixed passive proxy. No phone-out option. |
| `agents/radix/passive_r6.py` | 285 | Scan linked files only, each bounded to 1,000,000 bytes, with baked ClamAV signatures. Findings retain URL, signature and signature database date; OOM/unavailable/budget cases do not pass. |
| `agents/radix/passive_r6.py` | 332 | Axe findings keep serious/critical tool severity, page, rule, element, help and helpUrl. Cookie observations keep requested metadata and provenance, without values or essential/non-essential labels. |
| `agents/radix/browser/check.cjs` | 7 | Fresh browser context, no clicks or consent. Proxy-only networking, no implicit loopback bypass, no direct QUIC/non-proxied WebRTC, no service workers and refused WebSockets. Count proxy-refused third-party requests separately from client refusals. |
| `agents/radix/browser/check.cjs` | 14 | Capture Set-Cookie headers, script-set events across frames, Cookie Store changes and the final browser cookie store. Whitelist exported fields; preserve no cookie values. Provenance distinguishes observed set attempts from cookies actually in the browser store. |
| `agents/radix/live.py` | 316 | Extend the existing certificate helper with the verified host; use the existing Python DNS-name matcher for wildcard SANs. Existing fixed-host callers retain their default. |
| `agents/radix/passive_routes.py` | 55 | Run R6 after the passive scan under the same TXT-authorized lease; persist completion and snapshots atomically. Outer watch deadline is 410 seconds, with a 400-second elapsed-time measurement budget; the lease stays 420 seconds. |
| `agents/radix/passive_store.py` | 29 | Store check coverage and complete page snapshots beside scans. |
| `agents/radix/passive_store.py` | 136 | Reuse original tool text and retain measured facts; omit unavailable prose for new measurements. |
| `agents/radix/passive_store.py` | 230 | A skipped check cannot fix an earlier finding or replace a complete comparison baseline. Preserve the tool's severity in findings; fit the unchanged bus vocabulary with `unknown` when necessary. |
| `agents/radix/passive_store.py` | 315 | Return coverage, event metadata and findings through `radix.changes`; `:341` reads only tenant/domain-scoped complete page snapshots. |
| `agents/radix/app.py` | 118 | Start and stop the regulation event consumer with the room lifecycle. |
| `agents/radix/passive_watch.py` | 22 | Drain event work under the existing watch lock before scheduled work. |
| `agents/radix/regulation_events.py` | 20 | Accept exactly both bus fact shapes; discover tenants from own active watches, atomically dedupe per domain/event, acknowledge only after queue commit and fail on errors. |
| `tank/event_bus.py` | 249 | HTTP delivery and settlement allow only Rig/price and Radix/regulation room/event pairs. |
| `tests/tenant_bus/test_radix_events.py` | 17 | Actual Redis retry/dead-letter and isolation checks for malformed regulation messages. |
| `tests/test_radix_passive.py` | 64 | Reset watch/event rows in the existing disposable fixture before scans. |
| `agents/radix/regulation_events.py` | 118 | Upgrade I8 to the same browser cookie observer with accessibility/TLS/hash/malware work disabled for regulation runs. Existing atomic dedupe, ack-after-queue and fail/retry remain. |
| `agents/radix/scanlib/comply.py` | 27 | Accept CCPA/CPRA notice aliases through the existing saved-page checker, alongside GDPR/POPIA. Existing tool id and wording remain. This is notice presence, not a claim of legal compliance. |
| `agents/radix/schema.sql` | 55 | Add page snapshots above generated memory, with ENABLE/FORCE and both policies when the existing tenant RLS rollout is active. Literal parameterized SQL throughout. |
| `agents/radix/install-watch-tools.sh` | 1 | Pin testssl 3.2.4 and archive SHA256 `98528f8a0ac07f1e226efaa8ead438247df8efcb8fee4e056a937ab82a305490`, verified before extraction. |
| `agents/radix/browser/package.json` | 1 | Exact `@axe-core/playwright` 4.14.0 and Playwright 1.64.1; `package-lock.json:1` locks integrity and transitive versions. |
| `agents/radix/Dockerfile` | 15 | Debian ClamAV signature build stage; install pinned testssl/browser tools and their dependencies at build time only. No runtime updater. |
| `tests/radix_i8/test_events.py` | 172 | Reset snapshots in disposable fixtures; align I8 checks with the shared browser collector; add R4 takeover tests. |
| `tests/radix_r6/test_checks.py` | 1 | Offline expiry, wildcard, hash stability, removed-page, EICAR/tool-output, axe/cookie, skip, RLS, baseline and queue-race tests; CCPA/CPRA alias cases. |
| `tests/radix_r6/image_smoke.py` | 1 | Network-disabled real-image proof with synthetic HTTPS, the real proxy's test seams, unchanged bounds and the actual room CPU/memory settings. |
| `tank/command.py` | 1368 | Project new/fixed/unchanged and item locations into the existing card Rule value; preserve original rule IDs and raw comparison arrays. |
| `tests/radix_r6/PROOF.txt` | 1 | Exact commands, outputs, source checkpoints and image metrics. |

The obsolete initial `passive_notices.py` was removed for CodeQL alert 175; I8 now exercises the shared bounded collector. The synthetic HTTPS fixture explicitly permits only TLS 1.2–1.3 for alert 176. No security rule was suppressed.

I8's original room table, consumer, app lifespan, Docker copy and bus HTTP pair restriction are detailed by file/line in `tests/radix_i8/PR.md`. No changes to `agents/radix/egress.py`, `egress-policy.json`, compose files, proxy bounds, runtime setting names, sign-in, payment, model routing or approved skill-version folders. No production SQL, live scan, deploy or merge was performed. Deploy-on-merge will redeploy Tank and Radix because their code changes; no separate runtime configuration is included.

## Verification

Source/test checkpoint: `be777521d0f43dc1b9526e6f5aed2a760b25a5d7`. All work was in `/workspace/codex-radix-w3`. Finished files were committed and pushed individually, serially, to `codex/radix-w3`; completed pushes succeeded. Main was never merged. Exact setup and earlier I8 commands are preserved in the I8 report; R4 takeover checked the inherited code before adding missing tests and the catalog fix.

Final broad offline command (only loopback sockets permitted):

```sh
TMPDIR=/workspace/codex-radix-w3/.test-data/tmp RADIX_OSV_REAL=/workspace/codex-radix-w3/.test-data/osv.sqlite RADIX_PASSIVE_TEST_DATABASE_URL=postgresql://placeholder@127.0.0.1:56483/radix_passive_test RADIX_I8_TEST_DATABASE_URL=postgresql://placeholder@127.0.0.1:56483/radix_passive_test POOL_SCHEMA_DATABASE_URL=postgresql://placeholder@127.0.0.1:56483/postgres TENANT_BUS_REDIS_URL=redis://127.0.0.1:56484/0 DATABASE_URL=postgresql://placeholder@127.0.0.1:56483/postgres LITELLM_MASTER_KEY=placeholder TANK_API_KEY=placeholder PYTHONPATH=agents/_chassis /workspace/codex-radix-r4-py312/bin/python -m pytest -q --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 tests/test_radix_*.py tests/test_rx1_scans.py tests/test_rx4_compliance.py tests/test_command_radix.py tests/test_command_radix_repo.py tests/test_bucket1_radix.py tests/test_skala_radix_region_evals.py agents/radix/tests/ tests/tenant_bus/ tests/radix_i8/ tests/radix_r6/
```

**413 passed, 245 warnings, 437 subtests passed in 99.17 seconds; no skips**. The real OSV data came from the built image; no external network or model was used by tests. The original broad selections passed 298, then 310, 375, 377 and 380 tests as coverage expanded; these are overlapping runs, not additive totals. The focused notice/R6 selection passed 50 tests. Forced-RLS tests use a non-login restricted role against disposable loopback Postgres; malformed-event retries/dead-lettering use the actual local Redis bus.

Native tool commands:

```sh
DOCKER_HOST=unix:///var/run/docker.sock docker build --pull=false --progress=plain -f agents/radix/Dockerfile -t codex-radix-w3:final agents
docker --host=unix:///var/run/docker.sock run --rm --network none --memory 1g --cpus .25 --cap-drop ALL --security-opt no-new-privileges:true --add-host radix-passive-proxy:127.0.0.1 -v /workspace/codex-radix-w3/tests/radix_r6/image_smoke.py:/tmp/placeholder-image-smoke.py:ro codex-radix-w3:final python /tmp/placeholder-image-smoke.py
docker --host=unix:///var/run/docker.sock run --rm --network none --memory 1g --cpus .25 --cap-drop ALL --security-opt no-new-privileges:true --add-host radix-passive-proxy:127.0.0.1 -v /workspace/codex-radix-w3/tests/radix_r6/image_smoke.py:/tmp/placeholder-image-smoke.py:ro codex-radix-w3:final python /tmp/placeholder-image-smoke.py --browser-only
```

The integrated room-limit proof found EICAR, found missing alt text, captured HTTP/JavaScript cookies before interaction, counted refused third-party requests and found the 10-day certificate. Notice and page measurements completed. **testssl was partial**, recorded as incomplete rather than clean. Bounds stayed 2 concurrent tunnels, 6/minute, 1,000,000 response bytes and 20 seconds per tunnel, under the same lease. The final browser proof additionally checks loopback routing, WebSocket refusal, frame/transient/Cookie Store cookies, domain case handling and rejection of unwanted value fields: **25 metadata observations (including repeated provenance), two third-party refusals, loopback-used-proxy and WebSocket-refused assertions passed**.

These are synthetic fixtures, not live scans. The HTTPS fixture uses temporary self-signed test material that is never logged or committed. The real proxy's existing test-only DNS/dial injection maps a pinned public placeholder address to the loopback fixture; external networking is disabled. Separate tool proofs reset only their test lease between phases, never limits. The integrated collector retains the real limits and honestly reports partial/skipped checks.

Build/proof fixes retained in evidence: the first image lacked testssl's required `hexdump`; Debian `bsdextrautils` fixes it. An initial 768 MiB virtual-memory guard rejected a scan that fit the real room limit; it was replaced with child OOM priority while preserving the 1 GiB cgroup. Direct EICAR proof peaked at 987,088 KiB RSS. Quarter-core signature loading needed more than the helper's original 40 seconds; ClamAV now gets up to 90 seconds from the existing overall deadline. Wildcard tests caught the removed SSL API before it was replaced with the runtime's DNS-name matcher. Early test-only setup/bind/path errors were corrected, without dropping assertions or weakening bounds.

Other checks: **Ruff with the repository CI rules (`--select E9,F`), JavaScript syntax, installer shell syntax, whitespace and unchanged-egress checks passed; secret scan: 2 passed in 12.08 seconds**. `PROOF.txt` contains exact outputs and the checkpoints exercised by the native proofs. This report and proof commits change documentation only after the tested source checkpoint.

## Image size

Exact pre-R6 checkpoint `55337dfb` was archived into this checkout and rebuilt with the same builder. After unpack completed, Docker image `.Size` was **2,390,444,664 bytes** before and **4,750,496,720 bytes** after: **+2,360,052,056 bytes (2.198 GiB)**. Final image: `sha256:524bcba33050d07199d7a6154e8a82216f2701a9ee4c3005c941c85c81291349`. The increase includes the browser, Debian dependencies and baked signature database; no memory/CPU setting was raised. Exact build/inspect commands and both identities are in `PROOF.txt`.

## Missing prose for Figma

These findings intentionally have no invented explanatory or remediation sentence. The existing card displays state, rule, item/location and available tool text. Full structured measurements remain in the API; new metadata labels await approved prose:

| Measurement | Missing approved sentence |
| --- | --- |
| `sha256` new/changed/gone | Explanation of old/new hashes and the bounded linked-page observation scope. |
| Chromium cookie metadata | Explanation of each metadata/provenance field; no essential/non-essential classification. |
| Skipped/partial checks and discovery URLs | Explanation of coverage/budget/tool/memory limitations. |
| CCPA-specific remediation | Existing generic tool wording is retained; no new jurisdiction-specific prose was added. |

Existing notice rules, TLS helper text, testssl text, ClamAV signature names and axe help/helpUrl supply their own text. Approved Radix presentation remains [Figma 205:6112](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=205-6112). Tool source: [testssl 3.2.4 release](https://github.com/testssl/testssl.sh/releases/tag/v3.2.4); the checksum is pinned from the official tag archive, not claimed as a separately published upstream checksum.

## Hosted CI and founder proof

Hosted checks are asynchronous. CodeQL actions, JavaScript/TypeScript and Python analyses passed at source checkpoint `be777521`; both review alerts (175 and 176) are now marked fixed on the PR ref. Final documentation-head checks and full hosted Tank/Workspace results are not claimed here. The local offline suite and native tool proofs above passed with the stated partial-TLS limitation.

No founder browser screenshot or live acceptance is claimed. After founder merge/deploy, prove and watch `tervory.com` in his own workspace; inspect `radix.changes` after a run, after a page deploy, after a Zenas change and after removing TXT. The real founder test/screenshots remain pending. This handoff finishes the requested implementation/review gate and stops without merging or deploying.
