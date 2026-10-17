# RX-2 — controlled egress preparation

Source: [Radix build spec](https://app.notion.com/p/1ffc59366e944b94be881146ab25a981)
and [Build plan](https://app.notion.com/p/3fbba7f3966281bab72ade2463c93665).

Status: **preparation only; RX-2 is not complete**. C10 and RX-1 are already on
main. The service remains sealed. RX-3 and RX-4 have not started.

## Host decision

The sources do not name an approved external scan target or provide a client's
ownership proof. Do not infer permission from a domain mentioned in the spec.

| Destination | Proposed access now | Reason |
| --- | --- | --- |
| External client targets | None; exact staging hostname still needed | Owner and tenant must be identified, with DNS TXT or file-token proof |
| External APIs, package registries, scanner telemetry and template downloads | None | RX-1 uses image-baked tools and advisory data |
| Tank, Postgres and Hermes | Existing corridor only | Keep the current C10 configuration |

The effective external list remains empty. No wildcard, suffix permission,
IP literal, arbitrary port or implicit redirect destination is proposed.
Each future row must name the exact ASCII hostname, scheme/port, tenant, purpose,
ownership-proof reference, expiry/revocation conditions and approval reference.
Do not put credentials or ownership token values in this document.

## Prepared in this change

The existing application HTTP guard now rejects malformed allowlist entries,
userinfo, ambiguous URL authority syntax, IP literals, non-default ports and
Host-header overrides. It disables automatic redirects, environment proxies,
authentication handlers that could send extra requests, and transport extensions
that could override TLS server names. An injected HTTP client is trusted test
infrastructure, not an isolation boundary.

An empty host list still refuses every request before DNS or transport. Offline
scan jobs still do not call this client. There is no new live-scan job, dependency,
environment variable, proxy, network, compose edit or schema edit.

Tests live under `agents/radix/tests/` so all changes stay inside Radix. The
repository's existing `pytest -q` CI command discovers them without a workflow
change. They use HTTPX mock transport and refuse real socket connections.

## Work after the host list is approved

1. Record the approved exact target rows and verified ownership scope.
2. Prepare an egress proxy and its network wiring for the plan's final review.
   Keep direct outbound sockets blocked; an application allowlist alone is not
   sufficient. The proxy must enforce the same destinations, validate all DNS
   answers, reject non-public addresses and pin the validated address for each
   connection. Test DNS rebinding and mixed public/private answers. Preserve
   hostname verification and TLS SNI. Never trust a job-provided proxy or resolver.
3. Bound request rate, concurrency, response size and total scan duration.
   Redirects require a separately checked, approved destination.
4. Prove in an isolated test deployment that approved traffic succeeds only
   through the proxy, while unlisted hosts, alternate ports, internal services,
   metadata addresses, IPv4/IPv6 literals and direct socket bypasses fail.
   Missing policy, invalid policy, revoked ownership and a stopped proxy must
   fail closed.
5. Re-run the existing isolation check on every deploy. General/direct internet
   remains blocked; any approved exception needs its own evidence. Shared
   compose or schema changes wait for final review.
6. Only after RX-2 passes, start RX-3 live-site scans; RX-4 follows RX-3.

## Evidence still required before deployment

Application guard unit tests do not demonstrate deployed network isolation.
The Radix scan gates remain: at least 95% of planted problems found, under 5%
false alarms, and blocked general internet on every deploy. Also retain all seven
agent checks from the build plan: human-reviewed gold sets with a 20% holdout,
trap cases, shadow runs before model switches, weekly regression checks, room and
tenant isolation, cost/speed targets, and feedback becoming new gold examples.

This preparation does not claim those release gates have passed. Build and test
in GitHub Actions or an authorized cloud worker, never on the founder's laptop.
