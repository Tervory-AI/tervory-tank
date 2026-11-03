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

## Gate 3 WhatsApp: blocked by current pricing

Checked **3 November 2026**, before implementing the WhatsApp corridor. The
brief explicitly requires stopping if an in-window free-form reply is charged.
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
fetches returned 200 and the current pricing text. No authenticated Meta request,
message send, live-data change or model call was performed. No WhatsApp route,
setting, schema or bot-engine change was implemented. No message counter, cap or
other workaround was added. Gate 3 remains blocked on the brief's free-only
condition, not on a missing secret value. Gate 2 is unchanged.
