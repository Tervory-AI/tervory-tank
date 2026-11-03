# Autumbra Wave 4 acceptance

Code and offline evidence only. The founder deploys and runs the dogfood check.
No model second opinion is used. Code changes require a human approval tap.
Changes under `agents/ghost` redeploy Ghost on merge; the per-client Enforce
compose needs its own reviewed deployment. No live verification is claimed here.

## M13 — provider verification

Checked 2026-11-03 against the official documentation:

- [Cloudflare generic webhooks](https://developers.cloudflare.com/notifications/get-started/configure-webhooks/):
  require the configured secret in `cf-webhook-auth`, compared in constant time.
  This is a shared header, not an HMAC signature. Duplicate bodies are suppressed.
  [Payload schema](https://developers.cloudflare.com/notifications/reference/webhook-payload-schema/)
  describes alert notifications; an alert does not establish a tenant or prove
  a source IP should be blocked. The unbound route records only verified metadata.
- [Authenticated Pub/Sub push](https://docs.cloud.google.com/pubsub/docs/authenticate-push-subscriptions):
  verify RS256 using Google's public keys, issuer, expiration, exact audience,
  verified email and configured push service account. Tank alone fetches keys.
  Tokens can be reused; deduplicate subscription/message ID, not the token.
- [Workspace Alert Center notifications](https://developers.google.com/workspace/admin/alertcenter/guides/notifications):
  configure a topic and grant `alerts-api-push-notifications@system.gserviceaccount.com`
  publisher permission. Set the topic in Alert Center notification settings and
  create an authenticated Pub/Sub push subscription. Decode its base64 JSON only
  after authentication. Require ALERT/JSON attributes and a supported resource
  status. Match the subscription and decoded customer ID to the saved binding.

Provider URLs never accept `X-Autumbra-Signature` as a fallback. Internal `edge`,
`mailbox` and `host_firewall` relay URLs retain the timestamp/nonce/body HMAC and
also require Watch's existing Tank corridor key before acting. Never give that
key or the internal relay secret to Cloudflare or Google.

The connected Google URL includes an opaque connection UUID. It derives tenant
identity from server-side configuration, ignores body tenant claims, and retains
only bounded receipt metadata and hashes of alert identifiers/types. Raw alert
objects, email addresses, provider tokens and mailbox content are not stored.
Alerts never become source-IP blocks by guessing an address from their contents.

## M9 — health after every shield

Per-client Enforce keeps the existing one-way observer and approved health
proxy. `AUTUMBRA_HEALTH_URL` selects an HTTPS path on the already approved
`SITE_NAME` host (currently the reviewed dogfood host `tervory.com`); it cannot
introduce another host, port, credentials, query or fragment. This does not
open arbitrary client egress. New hosts still require a reviewed proxy/zone
allowlist change. Give this setting only to Enforce and its health observer.

The observer makes a streaming HTTPS GET through `health-egress-proxy`, discards
the body and cookies, follows no redirects and accepts only 2xx. It samples
once per second and signs only site, URL, status, elapsed time, outcome and probe
start time. Enforce requires a signed result whose GET started after the
confirmed Cloudflare write, waits at most 30 seconds, and records that result
as `health_probe`. Stale/missing/invalid results and all failed GETs trigger
owned-rule Undo. There is no switch to disable this after live apply or approval.
Fixture health booleans are never used by the Cloudflare adapter. Test transports
remain offline; only the founder's later run establishes live health evidence.

## M17 — connect backend and missing frames

Both connect mutations live under the existing vault contract, use the signed-in
Workspace service authentication, require this tenant's workspace administrator
or founder role, and reject a mismatched tenant/home region. Autumbra has no
`tenant_squad` grant on current main, so this is an explicit administrator opt-in;
it does not add a squad grant or grant command tools.
They return names and status only. Do not submit secret values in chat or logs.

`POST /v1/vaults/ghost.vault/autumbra/connect/cloudflare` accepts `tenant_id`,
`name` (an uppercase setting name), `token` (secret input), `zone_name`, `zone_id`,
`permissions: ["Zone Read", "Zone WAF Edit"]`, and `specific_zone_only: true`.
It verifies active token status and that the token's zone listing exposes exactly
that one zone, then saves the encrypted value under the tenant/name in
`ghost.vault`, using the existing vault key and tenant/name authenticated data.
It does not send the token to Watch, a browser response, a receipt or a queue.

[Cloudflare permissions](https://developers.cloudflare.com/fundamentals/api/reference/permissions/)
and [token verification](https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/verify/)
were checked 2026-11-03. Token verification does not expose its policy. The client
must confirm the exact Zone Read / Zone WAF Edit permissions and specific-zone
resource selection; the backend proves active status and visible single-zone
scope, not absence of every other permission. It performs no write to test a
credential and requests no token-management privilege. Do not use a global key.

A save returns `awaiting_enforce_binding`. The founder binds that named vault
secret to the existing `CLOUDFLARE_API_TOKEN_ENFORCE` setting on this client's
Enforce service only, in the deployment secret panel; no secret resolver is
added to Watch. A vault save alone does not mean the live edge is connected.
The current reviewed live hand remains `tervory.com`; another zone requires the
existing allowlist/egress review before a shield can be applied.

`POST /v1/vaults/ghost.vault/autumbra/connect/google_workspace` accepts
`tenant_id`, `audience` (public HTTPS push URL/audience), `service_account`
(the push identity), `subscription` (full projects/.../subscriptions/... name),
and `customer_id` (Workspace customer). It saves the named binding in the client
vault and installs only this non-secret configuration on Watch, returning a
stable `connection_id`, `push_path`, and `awaiting_verified_push` status. Use the
returned path on the existing HTTPS ingress; this change does not deploy ingress.

The customer configures the topic, publisher permission, Alert Center settings,
and authenticated push subscription in Google, with the exact configured
audience. Only a valid matching push lights up the mailbox connection.
`GET /v1/vaults/ghost.vault/autumbra/alerts?tenant_id=...` returns this tenant's
bounded intake receipts through the same authorization contract. Legitimate
Pub/Sub redeliveries are acknowledged without adding a second receipt or action.
No Google mailbox-reading credential is requested or held by Watch.

Missing Figma frames (backend built; no new screens implemented):

- Autumbra optional-connections chooser and current connection states.
- Cloudflare specific-zone permission guide, masked named-token entry,
  verification errors, saved state and awaiting-Enforce-binding state.
- Google Workspace Alert Center topic/subscription guide, audience and push
  identity fields, customer binding, waiting-for-push and verified states.
- Connection replacement/disconnect confirmation and expired/revoked states.

## M21 — measured receipt budgets

Every persisted queue receipt has `speed_budget_summary`, including refusals,
quarantine and approvals that did not run an edge stage. Each stage is explicitly
passed, exceeded or not_run; absent stages never count as measured success.
The existing limits remain decision 2s, confirmed shield write 10s, health 30s,
Undo end-to-end 60s, queue transit 5s and event-to-shield 15s. Exceeded stages are
retained as failures rather than clamped or omitted.

The Watch decision elapsed time crosses the typed queue door as a bounded timing
field. The Enforce receipt adds that to its decision and confirmed-shield time,
plus measured queue transit. `timing_origin` says whether that producer timing
exists; manually queued acceptance probes start at the queue. Approval timing
starts with the approval event, excluding the human's waiting time. A failed
post-shield health check does not inflate the already-confirmed shield timing.
Undo is measured as Undo, not as a new shield.

Cloudflare receipts contain `edge_requests`: measured elapsed time, method and
status for the actual adapter requests, including zone lookup, rule lookup/write
and owned-rule Undo. They contain no token, raw provider body or URL query.
`health_probe` records the verified real GET's duration and post-write start time.
`measurement_path` distinguishes real_edge, fixture and no_edge. MockTransport
tests exercise the adapter but are not deployed-edge measurements. After deploy,
record actual receipt JSON and edge evidence as described in the dogfood runbook;
no live budget success is claimed by this build.

## M24 — founder run after deploy

Use [the Wave 4 dogfood runbook](AUTUMBRA-DOGFOOD-W4.md) for the controlled
tervory.com test source, actual edge block, fresh health result, emailed receipt
and one-tap Undo. It distinguishes API-only probes from real-traffic proof and
records the exact deployed head and actual timings. It does not authorize this
builder to deploy, send live traffic or send an email. Those live acceptance
results remain unmeasured until the founder runs the procedure.

Legacy automatic code-fix settings normalize to approval on read/validation;
new receipts and owner emails never claim automatic patching. Fixes may be
prepared as draft PRs but are never merged or deployed by Autumbra. No AI
second-opinion step is required. Existing human approval and CI remain mandatory.
