# Radix I2 — founder-confirmed active scan

Source checkpoint: `202247642fee15dc7aae49612256c3355034fe5f`, branch `codex/radix-w4`, stacked on #634 at Claude's `ca662ce620b14c85e7de6a3d1de1c0fdea22c559`. `git fetch origin && git rebase origin/codex/radix-w3` succeeded before I2. Claude had already merged main; this builder did not merge or rebase on main. A read-only fetch now records main `55b2e224` for the wave 4 audit.

`radix.active.scan` accepts only `url`. The founder must Confirm. Both the tool catalogue and Tank corridor refuse other users, including tenant admins. Direct unconfirmed calls and mismatched confirmed URLs are refused. The tenant comes from the founder's authenticated workspace. The active target must be an exact HTTPS origin root in `active-domains.json`, currently only `tervory.com`; there is no request or environment override. The gateway checks the persisted tenant's TXT challenge again before opening any target tunnel. Its domain and active mode come from the stored row.

The existing gateway creates a separate active `Proxy` on its existing private link/port, under its existing lock and the same `passive_one_running` index. No compose, passive scanner command, egress implementation, egress policy or passive bound was changed. Active bounds: **2 concurrent, 120/minute, 2,000,000 response bytes, 30 seconds per tunnel, 1,800-second lease**. The outer scan deadline is **1,200 seconds**, including proof/launch time. ZAP's JVM is explicitly capped at 512 MiB; the room stays 1 GiB and .25 CPU.

The bounded policy enables bundled synchronous CRLF (40003), reflected XSS (40012) and SQL injection (40018) rules at **LOW/MEDIUM**. Other rules default OFF, so no callback/OAST rule can be enabled implicitly. Existing build-pinned ZAP 2.17.0 and bundled GraalJS are reused; existing update/download-disable flags remain. No add-on is installed at runtime. This is the stated selected-rule assessment, not a claim that every possible vulnerability was tested.

## Exact automation plan

The paths below stand for the per-run temporary directory; only paths vary at runtime.

```yaml
env:
  contexts:
  - name: verified-active
    urls:
    - https://tervory.com/
    includePaths:
    - ^https://tervory\.com/.*$
  parameters:
    failOnError: true
    failOnWarning: true
jobs:
- type: script
  parameters:
    action: add
    type: httpsender
    engine: 'ECMAScript : Graal.js'
    name: active-guard
    source: /tmp/placeholder-i2/guard.js
- type: requestor
  requests:
  - url: https://tervory.com/
    method: GET
    responseCode: 200
- type: spider
  parameters:
    context: verified-active
    url: https://tervory.com/
    maxDuration: 5
    maxDepth: 5
    maxChildren: 50
    threadCount: 2
    processForm: false
    postForm: false
    parseRobotsTxt: false
    parseSitemapXml: false
- type: activeScan
  parameters:
    context: verified-active
    maxScanDurationInMins: 14
    maxRuleDurationInMins: 2
    threadPerHost: 2
    handleAntiCSRFTokens: false
  policyDefinition:
    defaultStrength: LOW
    defaultThreshold: 'OFF'
    rules:
    - id: 40003
      strength: LOW
      threshold: MEDIUM
    - id: 40012
      strength: LOW
      threshold: MEDIUM
    - id: 40018
      strength: LOW
      threshold: MEDIUM
- type: passiveScan-wait
  parameters:
    maxDuration: 1
- type: report
  parameters:
    template: traditional-json
    reportDir: /tmp/placeholder-i2
    reportFile: zap.json
  sites:
  - https://tervory.com
```

The script runs before any request. It enforces a global maximum of 50 distinct spider URLs; ZAP's `maxChildren` alone is only a per-node bound. It refuses other schemes, hosts, userinfo and ports by routing them to a sentinel the exact-host proxy denies before DNS/dial. The proxy also checks TLS SNI. The active job uses the context, rather than the root's leaf node, so spidered paths are actually probed. ZAP adds a 2 requests/second rate limit; proxy limits remain independently enforced. Spider has a 5-minute bound, activeScan 14 minutes, each rule 2 minutes and 2 threads; the outer 20-minute deadline also covers startup and cleanup.

**Autumbra or Cloudflare may block the scan.** Non-200 root responses, blocked/challenge responses, missing reports, zero active responses, unmatched request/response counts, rule skips and deadlines are incomplete. An incomplete active run is persisted as an error with partial check coverage and can still retain parsed findings. Both `radix.findings` and `radix.changes` keep the existing failed state, including an empty report; they never present that as a clean scan. Incomplete runs cannot fix previous findings. Active and passive comparison baselines and promotion gates remain separate.

All report parsing uses `zap_findings`; only existing upstream description/remediation survives. Findings carry active metadata, and the existing Rule value displays the active tag. The existing card projection is reused; no page, component, label or explanatory prose was added. Confirmed dispatch writes a $0 code receipt and a repeated confirmation cannot run a second scan. The explicit command is planned by code, without a model.

## Verification

- Full offline Radix, compliance, command, event-bus, I8, R6 and I2 selection: **431 passed, 245 warnings, 437 subtests passed in 92.09 seconds**, no skips. An additional explicit active-command planner test passed separately after collection; it changes tests only. Focused selection: 39 passed before that additional case.
- Real image, external networking disabled, 1 GiB/.25 CPU: **23 requests/23 responses, including 19 active probes/19 active responses**, two spider URLs, six parsed findings; all 23 target dials went through the exact-host active proxy. Another host and port 80 were refused before any dial.
- Same final runtime image against HTTP 403: one request, blocked=true, zero active responses, persisted collector coverage partial. No clean claim.
- Separate earlier native spider-cap proof: exactly 50 spider URLs, capped=true, 16 refusals, incomplete. This used the same cap logic before final response counters/context selection; it is not described as the final complete-scan proof.
- Nine final runtime file hashes match the native-proof image, `sha256:cfb936ca413f02fbd65e2930d2789fe4a8674111c9dec71ba1a2f83459c5f227`.
- Ruff with repository CI rules (`E9,F`), JavaScript syntax and whitespace pass. Exact commands, results, source hashes, room/secret checks and initial diagnostic corrections are in `PROOF.txt`.

The first root-only native plan sent no active probes despite ZAP exit zero. It was retained as incomplete, then corrected to scan the exact-host context. Response counters and rule-timeout log checks prevent attempted requests or a zero exit code from establishing completion. No test assertion or proxy limit was weakened.

## Changes by file and line

| File | Line | Change |
| --- | ---: | --- |
| `agents/radix/active-domains.json` | 1 | Reviewed owner-domain allowlist. |
| `agents/radix/active_policy.py` | 7 | Separate active bounds, lease/deadline and exact-root validation. |
| `agents/radix/active_guard.js` | 1 | Same-host request guard, global spider cap, response/block counters; no traffic values exported. |
| `agents/radix/active_tools.py` | 17 | Separate automation plan, synchronous rules, fixed proxy and bounded parser/coverage checks. |
| `agents/radix/active_routes.py` | 15 | Runtime proof lease, shared run table, completion/failure and release. |
| `agents/radix/passive_gateway.py` | 64 | Active-mode/allowlist check and separate 30-minute proxy instance under existing lock. |
| `agents/radix/passive_store.py` | 29 | Additive mode column; tenant-scoped creation, lease, isolated baselines and partial persistence (`:176`, `:207`, `:234`). |
| `agents/radix/passive_store.py` | 323 | Active changes and read status (`:369`) preserve incomplete results. |
| `agents/radix/passive_routes.py` | 137 | Preserve active failed state on findings reads; trusted active execution at `:145`. |
| `agents/radix/schema.sql` | 80 | Idempotent column above generated memory; existing row policies remain authoritative. |
| `agents/radix/Dockerfile` | 82 | Package code; read-only policy assets at `:91`. No new dependency or service. |
| `tank/command.py` | 47 | Tool catalogue/founder filter, URL schema, adapter (`:1381`), existing projection (`:1513`), receipt (`:1672`) and confirmed dispatch (`:1855`). |
| `tank/radix_passive_routes.py` | 47 | Founder and exact confirmed-payload authorization, trusted room header and timeout. |
| `tank/radix_watch.py` | 10 | Explicit active command code planner. |
| `tests/radix_i2/test_active.py` | 1 | Offline authorization, bounds, shared lock, tenant isolation, partial persistence and read-state regressions. |
| `tests/radix_i2/image_smoke.py` | 1 | Actual ZAP, synthetic TLS and real proxy with existing test-only DNS/dial seams. |
| `tests/test_command_radix_active.py` | 1 | Founder-only Confirm, receipt, duplicate refusal and code planner. |
| `tests/radix_i2/PR.md` | 1 | Handoff and exact plan. |
| `tests/radix_i2/PROOF.txt` | 1 | Commands and captured results. |

## Publication and live acceptance

The first I2 allowlist commit on w3 could not be pushed: GH006, #634 was locked in the merge queue. No queue change or alternate push was attempted. The founder then authorized moving I2 to w4. The exact requested checkout/add/commit/push succeeded at `20224764`; both the allowlist commit and the remaining implementation are preserved. This report/evidence checkpoint follows on w4. Claude opens the PR once #634 lands; no PR was opened or modified by this gate.

No live scan, production SQL, deploy, merge or founder screenshot is claimed. After merge/deploy the founder proves `tervory.com` in his workspace, confirms `radix.active.scan https://tervory.com/`, then reads the returned scan with `radix.findings` or `radix.changes`. An unlisted domain must be refused. Hosted CI/founder live acceptance remain pending. Official contracts used: [activeScan](https://www.zaproxy.org/docs/desktop/addons/automation-framework/job-ascan/), [spider](https://www.zaproxy.org/docs/desktop/addons/spider/automation/), [scripts](https://www.zaproxy.org/docs/desktop/addons/script-console/automation/).
