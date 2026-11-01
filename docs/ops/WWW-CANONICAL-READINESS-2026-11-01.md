# Marketing www alias readiness

The intended canonical marketing host remains `https://tervory.com`.
The existing `www.tervory.com` alias is documented in PRODUCT-HOSTS.md.
This change implements the origin's canonical response; it does not create DNS,
attach hosting domains, or establish a working public alias.

## Observed state

Read-only checks on 2026-11-01 at approximately 08:47–08:54 UTC:

- Both authoritative nameservers, `hadlee.ns.cloudflare.com` and
  `lamar.ns.cloudflare.com`, returned authoritative `NOERROR` with zero answers
  for www A, AAAA and CNAME. This is NODATA, not a proven NXDOMAIN response.
- Apex HTTPS returned 200 through Cloudflare. The live `site` container in the
  Boston main stack has apex-only HTTP/HTTPS Traefik Host rules on port 3000.
- A diagnostic request forcing www to an apex Cloudflare edge address passed
  normal hostname/certificate verification but returned HTTP 530. Its valid edge
  certificate does not establish working DNS, origin routing, or alias acceptance.
- Existing local Wrangler OAuth access can read the active zone and its empty
  Worker-route list. Requests for www DNS records and edge certificate packs
  returned HTTP 403. Its advertised scopes contain no DNS scope. No token value
  was printed, requested, changed or copied. No external mutation was attempted.
- Available connected tools include no general Cloudflare DNS or browser-control
  capability. Sites is unrelated and is not a hosting migration path for this fix.

Durable read-only evidence is in
`/home/ammosync/.codex/tervory-lane6-evidence/www-observations.json` on Boston.

## Origin change and regression checks

`site/server.mjs` returns 308 only for the actual www Host header, with a fixed
`https://tervory.com` origin and the original escaped request path and query.
It ignores forwarded-host input. Apex, localhost health probes, exported pages
and the release signup handler retain their behavior. POST uses 308 so a client
can resubmit the same request at the canonical host; the alias does not write a
signup before redirecting.

The offline regression starts the real server on a unique OS-selected port with
isolated temporary pages and signup storage. It checks GET, HEAD, escaped paths,
queries, repeated parameters, exact-host matching, a single hop to apex, health
probes, 404/405 behavior, and a real isolated signup write after the redirect.
No model call, provider dependency, live signup, or production data is used.

## Exact external proposal for the existing owner

Before mutation, the DNS owner must read the authoritative record inventory and
retain record IDs/settings for rollback. NODATA alone cannot exclude a record
of a different type. Do not replace any existing www record without reconciling
that inventory. Do not change apex, mail, unrelated records, or nameservers.

Proposed DNS delta in the existing tervory.com Cloudflare zone:

| Setting | Current observed | Proposed |
| --- | --- | --- |
| www A / AAAA / CNAME answers | none | CNAME `www` to `tervory.com`, proxied, TTL Auto |

No IP target is invented. Use ONE of the following routing options:

1. **Existing Cloudflare edge Single Redirect (preferred if the owner can edit it).**
   Match only `http.host eq "www.tervory.com"`, including both incoming schemes.
   Set dynamic target `concat("https://tervory.com", http.request.uri.path)`,
   status 308, and Preserve query string enabled. Review existing redirect rules
   and their ordering first; add this one rule without replacing the ruleset.
   The edge response removes the need for a www origin route. No Worker is needed.
2. **Existing site origin.** After this server change is reviewed, merged and
   deployed through normal integration, append `https://www.tervory.com` to the
   existing main-stack `site` domain list, keeping `https://tervory.com` and all
   other current entries. Retain port 3000. Let normal hosting issue/verify its
   certificate and route www to this same server. Do not attach it to Workspace
   or an agent, create a new app, or change the apex domain.

The Cloudflare proposal follows its documented
[domain redirect](https://developers.cloudflare.com/fundamentals/manage-domains/redirect-domain/)
and [Single Redirect settings](https://developers.cloudflare.com/rules/url-forwarding/single-redirects/settings/).
Traffic must be proxied for the edge rule to run. Check interactions with existing
HTTPS redirects so HTTP www reaches HTTPS apex in one hop, rather than first
redirecting to HTTPS www.

**Blocker:** the inspected existing OAuth connection cannot read/write DNS records
(HTTP 403), and no authorized DNS-edit connection is exposed to this task. An
existing account owner must apply the coordinated delta or expose an already
approved DNS-edit session; no new provider, key or secret paste is requested.
The origin PR remains independently reviewable while this access is unavailable.

## Public acceptance after the coordinated change

Use normal DNS and TLS verification, without --resolve or insecure TLS flags:

- Both authoritative nameservers and public recursive DNS resolve www. Check A,
  AAAA and CNAME behavior (proxied CNAMEs may be flattened to address answers).
- GET/HEAD `https://www.tervory.com/` return 308 directly to HTTPS apex, followed
  by 200. HTTP www also reaches HTTPS apex in one redirect.
- Test a real existing path with query parameters and an escaped path. The first
  Location must preserve the path/query exactly, with no redirect loop. A final
  404 on an intentionally nonexistent path is expected; it must not become `/`.
- Apex still returns its original content/status; its health and release signup
  behavior remain healthy. Use isolated acceptance fixtures for signup writes,
  not production signup records.

Deployment scope of `site/` changes is the main app and `tervory-tank-za` under
`deploy_changed.py` MAIN_PREFIXES. This task performs no merge or deployment.
Rollback removes only the new www DNS record and chosen www-only redirect/domain
addition, restoring the owner's captured pre-change settings; revert the origin
PR if needed. Leave apex and existing records/domain entries intact.
