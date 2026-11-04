# Trigger M2: Facebook Page publishing

Official documentation checked **3 November 2026**. Graph API **v26.0** is the
latest version named by Meta's changelog, released 29 July 2026. No version is
inferred from a third-party guide. These public pages were read directly from
Meta; the web reader returned 429, but direct HTTP fetches succeeded.

## Official sources and decisions

All URLs below were checked on 3 November 2026:

- [Facebook Login for Business](https://developers.facebook.com/docs/facebook-login/facebook-login-for-business/):
  business-compatible app, user-token authorization-code flow. The manual flow
  describes `config_id` as optional and permits scopes. This implementation uses
  explicit scopes and needs no third configuration setting. Client businesses
  outside the app's role users require Advanced Access/App Review.
- [Manual login flow](https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/)
  and [login security](https://developers.facebook.com/docs/facebook-login/security/):
  confidential server-side code exchange, exact redirect, unpredictable state.
  These documents do not advertise PKCE for this Facebook Login for Business
  manual web flow; no PKCE support is claimed and no challenge/verifier is sent.
  This differs from Google's documented S256 support. Tokens stay server-side.
- [Graph API changelog](https://developers.facebook.com/docs/graph-api/changelog/):
  latest Graph API is `v26.0`; use it for dialog, exchange and Page requests.
- [Page feed reference](https://developers.facebook.com/docs/graph-api/reference/page/feed/):
  `POST /{page-id}/feed`, `message`, a Page access token, `CREATE_CONTENT` task,
  `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`. Request only
  those three permissions. The combined posts guide covers extra operations;
  their engagement/video permissions are unnecessary for a text-only feed post.
- [Pages posts guide](https://developers.facebook.com/docs/pages-api/posts/)
  and [Pages getting started](https://developers.facebook.com/docs/pages-api/getting-started/):
  Page discovery through `/me/accounts`; Page publishing returns a post ID.
  Tank sends immediately when its existing durable scheduler reaches the due time;
  it does not create a second schedule inside Meta.
- [Long-lived tokens](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/):
  exchange the short-lived user token server-side, then derive the selected
  Page's token from `/me/accounts`. A Page token derived this way has no fixed
  expiry but can still be invalidated. No permanent-access guarantee is made.
- [Access levels](https://developers.facebook.com/docs/graph-api/overview/access-levels/):
  Standard Access is available to app-role users before App Review. The founder
  must have an app role and `CREATE_CONTENT` on his own Page. This does not
  authorise onboarding unrelated clients without the required Advanced Access,
  Business Verification and App Review.
- [Revocation](https://developers.facebook.com/docs/facebook-login/guides/permissions/request-revoke/#revokelogin):
  `DELETE /me/permissions` invalidates the user's app authorisation. Disconnect
  clears ciphertext only after confirmed revocation. Failed revocation retains
  the sealed grant for recovery. This revocation applies to that Facebook user's app grant, so other
  connections using the same user grant may also become invalid.
- [Graph error handling](https://developers.facebook.com/docs/graph-api/guides/error-handling/):
  structured transient refusals use M1's three-attempt exponential backoff. A
  timeout, malformed response or unstructured server failure after a send stays
  uncertain, without automatic replay.
- [Page-owned published posts](https://developers.facebook.com/docs/graph-api/reference/page/published_posts/):
  confirmed reconciliation scans this Page's posts with bounded cursor pagination
  and the claim time, rather than following token-bearing pagination URLs.
- [Page post reference](https://developers.facebook.com/docs/graph-api/reference/page-post/):
  read the returned ID's `permalink_url`; do not invent a Page/post URL.
- [Instagram content publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/):
  Instagram's publishing flow requires image/video media. Trigger posts have
  text only today, so Instagram remains scheduled-only, as do LinkedIn and X.

## Founder setup and existing-card workflow

The founder registers a Meta app supporting Facebook Login for Business and
configures the exact redirect:
`https://app.tervory.com/oauth/trigger-meta/callback`.
Use the documented user-token authorization-code flow with the three permissions
above. For the first test, the founder has an app role and uses his own Page.

The founder fills **names only** in Coolify: `TRIGGER_META_APP_ID` and
`TRIGGER_META_APP_SECRET`. Existing `TANK_VAULT_KEY` must be configured in the
same tenant home-region Tank. Builders never inspect or supply values. The root
and ZA Compose files forward these names next to Google's OAuth names. This
explicit same-branch gate authorises that runtime wiring; it redeploys the main
app and ZA Tank under the existing deployment rules when the founder merges.
No deployment or main merge is performed by this gate.

In the founder's own workspace, use the existing `/chats` cards:

1. `trigger.meta.connect` and Confirm; follow its existing result URL and finish
   consent. The server callback returns to `/chats` without reflecting exchange
   data. State is single-use, expires in ten minutes and belongs to the tenant/user.
2. `trigger.meta.pages` and Confirm the read card. Only permitted Page IDs/names
   are returned, never tokens. The read records the existing $0 code receipt.
3. `trigger.meta.page.select:` with the selected `page_id` in JSON. The preview
   and Confirm bind the active connection generation and selected Page. The
   Page is verified against Meta's `/me/accounts` for this tenant's sealed grant.
4. Reuse an existing Facebook-format write through `trigger.post.create`, then
   `trigger.post.approve` and `trigger.post.schedule` with the real intended time
   and IANA time zone. This gate adds no model call. Approval binds the Page and
   connection generation. Changing the selection cannot redirect an old approval.
5. At the planned time, verify the actual post on the founder's Page. Inspect
   its existing post status/link and receipt fields in `/chats`.
6. `trigger.meta.disconnect` requires Confirm. It serializes against sends,
   revokes the grant and clears sealed tokens and pending consent states.

No page, label, button or visible wording is introduced. Missing settings,
invalid state and stale connection use the existing HTTP/card failure handling.
Provider refusal messages are bounded and scrubbed of credentials; raw Meta
bodies, access tokens and app secrets never reach cards or logs.

Delivery uses M1's durable claim, lease, bounded retries and uncertain-send
handling. A crashed or possibly sent attempt is never replayed automatically.
Explicit retry reconciles Page-owned posts from Meta before permitting another
send. A returned post ID is retained even if permalink lookup must be retried;
permalink lookup cannot trigger a second publish.

Founder browser evidence, screenshots and final-head hosted CI results must be
recorded on the PR after they exist. Offline tests alone do not prove completion.

## Gate 3 WhatsApp: capped service replies in the account timezone

Checked **3 November 2026**, before implementing the WhatsApp corridor. The
original brief required stopping if an in-window free-form reply was charged.
The founder subsequently authorized a strict 1,000-attempt cap and explicitly
corrected the calendar boundary to the account's own timezone.
Meta's current pricing does charge service replies beyond a limited free tier:
as of **1 October 2026**, each business phone number has 1,000 free service
messages per month, and charging begins with the 1,001st. The customer-service
window is 24 hours after the user's most recent message; being inside that
window does not make every service reply free. Meta classifies non-template
replies powered by third-party AI solutions as service messages.

Official sources read directly from Meta, all checked **3 November 2026**:

| Topic | Official URL | Finding |
|---|---|---|
| Pricing and free tier | https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing#free-tier-of-monthly-service-messages | Since 1 October 2026, only the first 1,000 service messages per phone number each month are free; subsequent service replies are charged. |
| Customer-service window | https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing#customer-service-window-csw | 24 hours, reset by the user's messages; non-template messages require an open window. This is not an unlimited free-reply guarantee. |
| Webhook verification and signature | https://developers.facebook.com/docs/graph-api/webhooks/getting-started/ | GET challenge with a matching verify token; X-Hub-Signature-256 authenticates the raw payload with the app secret. |
| Message webhook shape | https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components/ | Incoming text is in entry/changes/value/messages; metadata supplies phone_number_id. |
| Text send call | https://developers.facebook.com/docs/whatsapp/cloud-api/messages/text-messages/ | POST /{phone-number-id}/messages with type=text and bearer authorization; links can be included in the text. |
| Send API reference | https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages/ | Versioned Graph message endpoint and bearer authentication. |

The web reader returned a login page for pricing; direct public-document HTTP
fetches returned 200 and the current pricing text. The pricing page states that
the monthly free tier resets at midnight in the Messaging account timezone,
not at UTC midnight. The timezone is copied by the founder from Meta Business
settings; it is never inferred from the phone, tenant region, browser or server.
The official text-message example names Graph **v26.0**, reused here.

### Names-only configuration and registration

The founder registers the WhatsApp number on the Meta app and supplies
`TRIGGER_WHATSAPP_APP_SECRET`, `TRIGGER_WHATSAPP_VERIFY_TOKEN`, and
`TRIGGER_WHATSAPP_BINDINGS` in the number's own regional Tank. Each entry maps
one `phone_number_id` to exactly the founder-selected `tenant_id`, `token_env`
and `timezone`. `token_env` names a server-only setting matching
`TRIGGER_WHATSAPP_TOKEN_<NAME>`; `timezone` is an IANA name validated with Python
`zoneinfo`, for example `Africa/Johannesburg` or `America/Los_Angeles`.
`TRIGGER_WHATSAPP_TOKEN_CONNECTOR` is the supplied names-only Compose slot.
Additional token setting names require corresponding server environment
passthroughs; do not put token values in the bindings JSON or repository.

**A missing or invalid timezone never permits a WhatsApp reply. Every new
conversation is handed over through the existing hand-over email.** A missing
token, closed/invalid customer-service window or exhausted monthly cap also
hands over without replying or invoking the answer model. There is no UTC or
regional default for an account timezone.

Register the public callback URL with an explicit region:
`https://app.tervory.com/v1/bot/whatsapp?region=us-east` or
`https://app.tervory.com/v1/bot/whatsapp?region=za`. The regional target must be
configured; there is no cross-region fallback. Workspace forwards the untouched
POST bytes and signature. For GET verification it moves the verify token from
Meta's query to a private Tank header, keeping it out of the internal access-log
URL. Only the matching numeric challenge is returned. No browser identity,
cookie, embed key or caller-supplied tenant is accepted by this corridor.

Subscribe to the messages webhook. Tank verifies HMAC-SHA256 over the raw bytes
before parsing JSON. Unknown numbers, status updates and non-text messages are
acknowledged without storing customer data. Messages over 2,000 characters are
ignored. The existing per-tenant/per-sender bot rate limits apply. Contacts and
profile metadata are ignored. The sender identifier is a keyed opaque visitor
UUID, and the raw identifier is sealed under a tenant/conversation vault context
for sending only. Existing retention deletes that sealed value and cascading
webhook claims 12 calendar months after the conversation's last message.

Conversation delivery is recorded in the additive `transport` column: `web`
by default, or `whatsapp` for this corridor. The legacy `channel` column keeps
its original web-only check. No existing constraint is removed or relaxed.

### Free-tier claim and hand-over behavior

`tank.trigger_whatsapp_months` holds the tenant, business phone number, local
calendar month, validated timezone and attempted reply count. A unique phone/month budget and conditional SQL
UPDATE reserve the next slot only below 1,000, inside the same transaction as
the bot message and durable send state. That transaction commits before the HTTP
send. Failed, interrupted and uncertain sends never refund the slot or retry.
Webhook claims commit before the engine runs; replaying a claimed event cannot
run another model or send again. A phone/month unique index also prevents tenant rebinding from replenishing
the allowance. Counter rows survive customer retention so
removing an expired conversation cannot replenish an account's allowance.

Replies 999 and 1,000 may send; the next incoming conversation hands over by the
existing email with no WhatsApp response. The account-local month starts at
00:00 on the 1st. A new month creates a fresh WhatsApp session, allowing a sender
handed over at last month's cap to use the new allowance. A timezone change that
conflicts with an existing month's stored timezone fails closed for that month.
`trigger.bot.stats` returns the current local-month total across this tenant's
bound numbers through the existing `count` field and retains its weekly results.

Only a free-form `type=text` POST to `/{phone-number-id}/messages` exists; there
is no template path. The signed inbound timestamp must be inside 24 hours and
not in the future. The window and account month are rechecked before sending.
The shared web engine still owns source/tenant/citation/number validation,
live Rig reads, code-only FAQs and receipts. The reply includes the verified
source links; an answer plus links over 2,000 characters hands over. Existing
lead drafts and claimed hand-over email keep their existing behavior.

This cap controls this corridor's attempts. To preserve the free-only account
budget, the founder must bind a number whose entire service-message allowance
is available to this corridor, in one regional deployment only. Sends by other
applications or operators are not visible to the local counter. Do not enable
it mid-month on a number whose allowance has already been consumed elsewhere.
No token values, model requests, live WhatsApp sends, SMTP delivery or production
SQL were used to build or verify this gate.

Founder acceptance remains a real-device check after configuration: ask from
his own phone, verify a sourced reply with links, verify an unsupported question
hands over and its email arrives, then inspect `trigger.bot.stats` in `/chats`.
Record actual screenshots and hosted Tank/Workspace CI results on the PR when
they exist; offline proof must not be presented as founder acceptance.
