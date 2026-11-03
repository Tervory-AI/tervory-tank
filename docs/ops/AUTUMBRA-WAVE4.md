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
