# Trigger M1 · Google Business Profile

Checked against Google's official documentation on **3 November 2026**.
This is the channel connection for a tenant's business profile. M1 adds no page
or widget: the founder/tenant admin uses the existing `/chats` Confirm cards.
Meta publishing is M2 and is absent. Facebook, Instagram, LinkedIn and X drafts
remain scheduled-only; the calendar marks them due without sending anything.

## Google project: founder steps

1. Use the founder's Google Cloud project, or create one in Cloud Console. The
   applicant must manage a verified Business Profile active for at least 60 days
   and have the business website on that profile. Request Business Profile API
   access through Google's contact form with that project's number. Wait for
   Google's approval; creating an OAuth client alone does not grant API access.
2. Enable the approved Business Profile APIs needed here: Google My Business API
   for v4 posts/reviews, Account Management API for accounts, Business Information
   API for locations. Confirm access/quota in that project after approval.
3. Configure the project's OAuth consent details and a **Web application** OAuth
   client. Use Google's normal OAuth app-verification process where required.
   During testing, authorize only the founder's intended test Google account.
4. Register this exact authorized redirect URI:
   `https://app.tervory.com/oauth/trigger-gbp/callback`.
5. In Coolify, the founder fills **names only**:
   `TRIGGER_GOOGLE_OAUTH_CLIENT_ID` and
   `TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET` on the main app. The existing
   `TANK_VAULT_KEY` must already be configured for scoped connection sealing.
   No value belongs in this document, a PR, a terminal transcript or a chat.
   A tenant's home-region Tank needs the same setting names configured there;
   the code never forwards a tenant's connection to another region as fallback.
6. The founder merges/deploys. Builders do not merge main or provision values.
   Root Compose changes redeploy the main app; ZA Compose changes redeploy
   `tervory-tank-za`; the format comment under `agents/trigger/` also matches the
   existing Trigger room deploy rule. No deployment is performed by this PR.

Official prerequisite and access-request instructions:
[Business Profile API prerequisites](https://developers.google.com/my-business/content/prereqs),
[OAuth for Business Profile](https://developers.google.com/my-business/content/implement-oauth),
[Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server).
GBP API approval and OAuth consent/app verification are separate prerequisites.

## APIs and connection boundary

- Local posts use Google My Business v4:
  `POST https://mybusiness.googleapis.com/v4/accounts/{account}/locations/{location}/localPosts`.
  The returned resource name and `searchUrl` are retained, without constructing
  a profile link. [Official create reference](https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts/create).
- Reviews use the same v4 location's `reviews` collection. Replies use
  `PUT .../reviews/{review}/reply`, which creates or replaces that one owner's
  reply; it does not append a second reply. The location must be verified.
  [Official review list](https://developers.google.com/my-business/reference/rest/v4/accounts.locations.reviews/list),
  [official updateReply](https://developers.google.com/my-business/reference/rest/v4/accounts.locations.reviews/updateReply).
- Requested scope is only `https://www.googleapis.com/auth/business.manage`.
  It is documented for both operations above; no profile/email sign-in scopes
  are added. Account/location discovery uses
  [Account Management accounts.list](https://developers.google.com/my-business/reference/accountmanagement/rest/v1/accounts/list)
  and [Business Information locations.list](https://developers.google.com/my-business/reference/businessinformation/rest/v1/accounts.locations/list).
- Consent uses Google's authorization/token endpoints with offline access and
  PKCE S256. Google's [published discovery metadata](https://accounts.google.com/.well-known/openid-configuration)
  advertises S256 and the confidential-client token methods; its
  [PKCE description](https://developers.google.com/identity/protocols/oauth2/native-app)
  documents the challenge/verifier pair. The server also supplies the web
  client's secret during exchange.
- State is one-use, expires after ten minutes and is bound to the active tenant
  and user. Its hash and sealed verifier are stored server-side. The authenticated
  Workspace callback forwards only the exchange data to Tank, then redirects to
  `/chats` with no code/token in its response. A denied, expired, foreign-user or
  replayed exchange cannot install a connection.
- Only the refresh token is stored, using the existing vault's tenant/generation
  encryption context. Access tokens exist transiently during requests. Neither
  credentials nor their response bodies are projected into cards, model prompts
  or log messages. Only approved public API fields and sanitized Google messages
  are returned.
- Disconnect is confirmed, generation-bound and locked against publication.
  It posts the refresh token to Google's revocation endpoint in the request
  body, then removes the local ciphertext and pending states on success. An
  explicit HTTP 400 `invalid_token` is already revoked; other failures preserve
  local state. Reconnecting revokes the old grant at confirmed connect, before
  new consent. The callback refuses to overwrite a still-installed token.
  [Official revocation documentation](https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke).

## Existing-card workflow

Explicit commands are parsed in code. Arguments use the existing card's Brief;
no new button, label, empty-state copy or settings page is introduced.
`trigger.post.create` and `trigger.gbp.reply.draft` are model-capable paid-run
cards, using the existing paid guard at Confirm. Other M1 tools use code only. Tools
require the founder or the active tenant's verified admin. Every mutation and
paid draft is behind the existing durable Confirm dispatcher.

- `trigger.gbp.connect` → Confirm → the consent URL. Complete consent as the
  store's own Google account. The callback returns to `/chats`.
- `trigger.gbp.locations` → Confirm read → the actual account/location names.
  `trigger.gbp.location.select:` with `{"location":"accounts/<account>/locations/<location>"}`
  → preview/Confirm chooses a location verified against that connection.
  The bracketed identifiers above describe syntax, not a live record.
- `trigger.post.create:` with a channel and either `text` (the brief) or an
  existing `write_id`. Channels are `gbp`, `facebook`, `instagram`, `linkedin`,
  `x`. Confirming a brief uses W1 and the existing `trigger.write` route once;
  an existing write is read without a model. The format must match the channel.
- `trigger.post.approve:` with `post_id` previews the actual revision, text,
  checks and selected profile. Confirm approves that revision. A changed Google
  connection/selection cannot silently reuse the approval.
- `trigger.post.schedule:` with `post_id`, `planned_at` and `time_zone` previews
  the approval plus the chosen time. The timestamp must have the real UTC offset
  for that IANA zone; a nonexistent DST time or mismatched offset is refused.
  A repeated DST hour is distinguished by its explicit offset.
- `trigger.post.edit:` with `post_id` and edited `text` runs W1's free checkers
  and returns it to draft. No model checks. `trigger.post.cancel` cancels a post
  before publication; locks serialize a racing send and cancellation.
- `trigger.posts` filters by state/channel/local date range. `trigger.calendar`
  takes `start` and `period` (`week` or `month`) and groups each post in its own
  zone. Both use $0 code receipts. Publish attempts and review sends also have
  code receipts; actual draft calls retain their existing paid write receipts.
- `trigger.gbp.reviews` returns actual review text/rating updated since the
  tenant/location cursor. `trigger.gbp.reply.draft` takes `review_id`; its brief
  labels the review customer text, guidance only, never instructions. W1 drafts
  in the saved voice and runs its free checkers. `trigger.gbp.reply.edit` edits
  and checks the reply without a model. `trigger.gbp.reply.send` requires a new
  Confirm. Identical sent text is not sent again; changed text replaces the
  same Google reply resource. `trigger.gbp.disconnect` requires Confirm.

## Founder-approved limit rule: supersedes the Marketing SPEC line

On **3 November 2026** the founder superseded “Missing limits block scheduling”
in Marketing SPEC frame `210:2897` (native root `151:3973`). The Figma thread must
correct that line in its next round. This PR does not edit the Figma document.

W1's verified official limits still apply: the checker must report the post
within its limit before scheduling. When no official numeric limit is published,
an approved, completely checked post is schedulable with the existing field
`limit: none`. No new explanatory wording is added to the card.

GBP's summary/event-title/offer-terms numeric limits remain unset. The founder
and this thread checked these official references; no third-party 1,500 figure
is substituted:

- https://support.google.com/business/answer/7342169
- https://support.google.com/business/answer/7390603 (currently redirects to the prior help page)
- https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts

Google's response is authoritative for an unverified limit. A too-long rejection
is failed with Google's message, with no automatic retry of that text. Editing
returns it to draft, requiring approval and scheduling again. The rule is also
recorded beside the GBP format in `agents/trigger/formats.py`.

## Delivery and recovery semantics

Due GBP posts are selected under tenant scope with `FOR UPDATE SKIP LOCKED`.
Each attempt gets a durable committed claim before any Google POST; a second
worker cannot send the same claim. Publication and disconnect/cancel are
serialized by row locks. Returned platform IDs/URLs are stored with the code
receipt. Non-GBP channels never enter the send queue in M1.

A rate-limit rejection, failed token refresh (transport/5xx), or a connection
failure before the publishing POST uses bounded code backoff (three attempts;
60 then 120 seconds before the next attempts). After that it stops; a confirmed
`trigger.post.retry` can explicitly reset a known failure after a fresh Confirm;
uncertain delivery first follows the reconciliation below. Length errors are terminal for automatic
retry and do not enter backoff. Editing still returns the post to draft.

Google's create endpoint has no documented request-id/idempotency field. A
publishing POST's read timeout, dropped response, 5xx or unreadable body may
have reached Google; it becomes failed/uncertain without automatic POST replay.
Token-refresh failures and POST connection failures are not uncertain: no post
was sent. Google rejections other than 429 do not automatically retry.

An uncertain post may be cancelled before it is marked published. A confirmed
`trigger.post.retry` first lists all pages of the selected location's local
posts. An exact summary match created after the durable claim is adopted as
published with its returned name and search URL, without a second POST. A
complete read with no match allows the confirmed retry. Failed/incomplete reads
or a changed connection/profile leave the post uncertain. The claim timestamp
is stored explicitly; pre-review claims retain their original five-minute
lease timestamp as a compatibility fallback.
[Official list reference](https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts/list),
[official LocalPost fields](https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts)
were checked on 3 November 2026 for pagination, summary and createTime.

The case study counts actual published posts and distinct replied-to reviews,
scoped by tenant, receipt region and first publication/send date. It reads no
post/review text for those figures.

## After-merge acceptance

After merge and the founder configures the project/access/settings, Custom Nation's own
`/chats` test must connect its account/location, create and approve three real
GBP posts, schedule them and inspect the calendar; one must appear on Google
at its time with its returned link. A draft reply to a real review must appear
on Google only after Confirm. Founder screenshots and live delivery proof are
required. Offline fake-Google tests are not that acceptance, and no live Google
write is made by those tests.

The real Trigger room/internal LanguageTool check also follows after merge,
as directed in the founder review. CI's `tank` job on the final PR head is the
full-suite test of record; local focused tests do not replace it.
