# Wave 4b item 2 — proven-domain infrastructure checks

Main audit: `981ac096` and #651 had no Nmap/dnsx run. This item adds confirmed $0 `radix.infra.scan <https://domain/>`, founder on the unchanged own-domain list or a Radix-enabled client admin with current written consent. It binds consent to the run and rechecks consent and TXT before target traffic, using the existing one-running index/lease. The result uses the existing findings card; reports also read these persisted findings. Infra and ZAP baselines are separated so one cannot retire the other's findings.

Nmap uses `--unprivileged -sT -Pn -n --disable-arp-ping --max-parallelism 2 --max-retries 0 --host-timeout 600s`, with exactly 100 explicit TCP ports from the immutable Nmap 7.95 service-frequency snapshot in infra-ports.json. No scripts, version detection, raw scan, UDP scan, ping or caller port list. [Nmap documents](https://nmap.org/book/man-bypass-firewalls-ids.html) that its --proxies option does not cover port scanning. Therefore proxychains4 intercepts connect calls with a fixed HTTP peer; remote DNS maps only to the exact proven hostname. The peer independently checks the hostname, port policy and public pinned address before dialing.

Pinned dnsx 1.2.2 uses only the local TCP DNS bridge as its resolver, with 2 workers, 2 queries/second, one attempt and update checks disabled. It checks A/AAAA for `www`, `api` and `mail` subdomains of the proven root, not an unbounded wordlist or discovered IP scan. The bridge and peer independently reject apex/out-of-suffix names and other record types before upstream DNS. Resolver lookup happens on the egress peer using its existing system DNS configuration; scanner-side DNS requests go through the same bounded peer as Nmap. Returned addresses never become port-scan targets. No runtime add-on or binary download.

The separate InfraProxy shares the existing Proxy admission counters, with **2 concurrent operations, 120/minute, 2,000,000 bytes each direction, 30 seconds per operation** and the **30-minute lease**. Nmap and DNS share these counters. Refused, missing or failed coverage makes the run incomplete even when a CLI exits zero; existing findings are retained. No clean inference from a blocked port/query. The sealed room still has no direct internet route. The existing egress.py, passive bounds and HTTPS active proxy remain unchanged.

## File/line changes

- `agents/radix/passive_infra_proxy.py:17`: immutable top-100 policy; `:66` separate scoped TCP/DNS proxy, public address pinning, shared admission/bounds and coverage.
- `agents/radix/passive_infra_tools.py:17`: no-script connect command and proxychains configuration; `:23` dnsx command; `:28` local DNS bridge, parsers, persisted tool facts and incomplete coverage handling.
- `agents/radix/infra-ports.json:1`: Nmap 7.95 top-100 TCP snapshot, official source URL and source SHA-256.
- `agents/radix/install-infra-tools.sh:1`: build-time Nmap/proxychains packages and checksum-pinned dnsx release; `agents/radix/Dockerfile:65` installs them and copies the read-only policy. Tank/Workspace and Radix (including its egress peer, same image) redeploy through existing mapping; no Compose/limit/provider configuration change.
- `agents/radix/passive_store.py:29`: persisted infra mode; `:229` mode-bound runs, `:253` gateway read, separate baseline comparison.
- `agents/radix/schema.sql:111`: additive mode column above generated memory.
- `agents/radix/active_routes.py:15`: shared authorized execution and infra lease endpoint.
- `agents/radix/passive_gateway.py:66`: enforce stored mode and use a separate InfraProxy under the same lock.
- `agents/radix/passive_routes.py:175`: private infrastructure dispatch.
- `tank/command.py:47`: tool, admin visibility, adapter, Confirm, timeout, existing card projection and $0 receipt.
- `tank/radix_passive_routes.py:48`: exact Confirm/tenant/admin enforcement for infra; `tank/radix_watch.py:10`: code planner.
- `tests/test_radix_infra.py:1`: fake proxy scope, public-address refusal, DNS scope, concurrency, consent, cross-tenant refusal, lock contention and partial coverage.
- `tests/test_radix_active_consent.py:79`: real confirmed infrastructure dispatch and $0 receipt.
- `tests/radix_w4b/infra_native.py:1`: actual CLI transport check against fake targets with --network none.

## Verification

74 passed, 3 warnings in 8.10s (infrastructure, consent and existing active/passive checks). Native Nmap 7.95/proxychains/dnsx 1.2.2: 100 proxied TCP dials, six scoped DNS queries, four findings; both checks complete, all targets fake, network none. The fixture was fixed to serialize absolute DNS answer names; actual dnsx's resolver grammar is `tcp:host:port`. A small test image built the real binaries; no production image/deploy/live scan was run. INFRA-PROOF.txt preserves evidence. Exact CI lint runs before push; hosted CI follows review.
