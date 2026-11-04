# Trigger — founder testing sheet

Scope: all Trigger features shipped on main at `d5d3ea2e`, including writing/checks
and voice, #567 tenant-admin/long-document/accepted-copy work, #595 writing that
learns, #497/#498 CRM and #624 client organisations/Facebook/WhatsApp, #604 GBP,
#600 source-grounded bot, and #654 responsive console/embedded widget. Source
inventory: `agents/trigger/`, `tank/trigger_*.py`, `workspace/app/trigger/`,
`workspace/public/trigger/widget.js` and their existing offline fixtures. The old
CRM acceptance branch is not a source. There are **56 rows** with one offline
case per row in `tests/acceptance/test_trigger.py`.

## Addresses, inputs and evidence

- Repeat browser checks at **1440 and 375 px** (the founder’s phone). Trigger’s
  host maps `/` to `/trigger`; `/trigger/crm/...`, `/trigger/marketing/...` and
  `/trigger/bot/...` retain their prefixes on this host. `/chats` uses the existing Command cards. Sign in and select the
  actual client organisation first; ordinary members cannot perform admin work.
- Settings below are names copied from `docs/ops/FOUNDER-SETTINGS.md`; **none**
  means no additional setting beyond working sign-in/room routing. Values are
  entered privately by the founder. Never paste tokens into chats, this sheet or
  URLs. Google/Meta connection consent uses the existing callback routes.
- Replace every record/write/source/card ID with an actual returned ID. Use only
  the founder’s own test organisation, Page/Profile, approved store origin and
  actual source/product facts. Offline strings containing `placeholder` and the
  fixed clocks are fixtures, never live customer content.
- Meta/Google rejection, crash, cap, stale-state, foreign-tenant and retention
  probes run offline against fake providers and disposable data. Do not induce
  1000 live sends or failures on a customer account. Positive publication rows
  require the founder’s planned test post on his own connected account.
- For catalogue/quote checks, enable this tenant’s existing Rig entitlement and
  Confirm `trigger.bot.source.add` with `kind: "rig"` and the store’s actual
  catalogue. Live prices/availability come from its current Rig record, never
  an old page or FAQ. No additional environment setting is introduced.
- Every side effect uses the existing **Confirm** card. Verify its data before
  confirming; proposal, Cancel or a stale preview cannot authorize a write.
  Inspect actual returned status, link and receipt, not a specimen screenshot.
- Chat bot contact/quote capture requires the founder’s privacy notice and
  retention wording in **FOUNDER-SETTINGS D2**, saved as tenant settings
  `privacy_notice` and `notice_version` through the existing confirmed
  `trigger.bot.settings` tool. These are data fields, not new environment names.
- Embed the existing `/trigger/widget.js` with this store’s returned origin-bound
  public key. It is not a provider token. Source documents/FAQs belong to the
  store; unsupported facts hand over rather than fabricate an answer.

## Acceptance rows

| ID | Live address | What he does | What he should see | Setting names |
| --- | --- | --- | --- | --- |
| R01 | https://trigger.tervory.com | At 1440 and 375 px open CRM lists/details, Channels, Calendar, Composer, Google reviews, Inbox and Settings; open/close the phone menu. | Own data and registered labels; no horizontal page overflow or runtime error; disabled controls remain disabled. Host routes to /trigger. The embedded widget fits both widths. | none |
| R02 | https://trigger.tervory.com/chats | Send `trigger.check: placeholder text` and Confirm; inspect findings and receipt. | Original text and offsets retained; all free checker results or explicit unavailable status; zero-cost code receipt. | none |
| R03 | https://trigger.tervory.com/chats | Ask Trigger to write from the supplied facts, review its card and Confirm. | One draft using this tenant’s voice, checks, write ID and actual receipt. Proposal alone does not write. | none |
| R04 | https://trigger.tervory.com/chats | Attach a long owned document and request a check; Confirm. | Whole-document offsets and bounded findings, without losing boundary findings or checking the wrong attachment. | none |
| R05 | https://trigger.tervory.com/chats | Request a will or other legal document. | Delegated to Zenas, with the hand-off result and scope; Trigger does not draft legal text. | none |
| R06 | https://trigger.tervory.com/chats | Upload/paste authored voice rules; preview, Confirm, inspect history, then roll back to an actual prior revision. | Only authored rules; versioned tenant voice, history and a new rollback revision; repeat confirmation is safe. | none |
| R07 | https://trigger.tervory.com/chats | Preview a voice change, cancel it, then attempt an outdated preview after another save. | Cancel does not overwrite; stale preview is refused; another organisation cannot read or change this voice. | none |
| R08 | https://trigger.tervory.com/chats | Write a draft; use changes, reject, then accept feedback and Confirm each. | Feedback is attached to that write; only accepted copy activates its private tenant training pair; receipt remains visible. | none |
| R09 | https://trigger.tervory.com/chats | Accept a write, then reference that write in an approved Tisan build. | Only accepted, confirmed, tenant-owned copy resolves; unaccepted/foreign references fail before building. | none |
| R10 | https://trigger.tervory.com/chats | At 1440 and 375 px inspect a checker card, voice preview and voice history. | Findings, confirmation and voice history use the shipped layouts with no page overflow. | none |
| R11 | https://trigger.tervory.com/trigger/crm/leads | Open Leads; page through the client’s own records and open an actual record. | BottleCRM records from this client’s bound organisation only; projected fields, tenant receipt, no credential/public invoice token fields. | TRIGGER_CRM_URL, TRIGGER_CRM_PAT_CONNECTOR, TRIGGER_CRM_TENANT_BINDINGS |
| R12 | https://trigger.tervory.com/trigger/crm/contacts | Open Contacts; page through the client’s own records and open an actual record. | BottleCRM records from this client’s bound organisation only; projected fields, tenant receipt, no credential/public invoice token fields. | TRIGGER_CRM_URL, TRIGGER_CRM_PAT_CONNECTOR, TRIGGER_CRM_TENANT_BINDINGS |
| R13 | https://trigger.tervory.com/trigger/crm/estimates | Open Quotes; page through the client’s own records and open an actual record. | BottleCRM records from this client’s bound organisation only; projected fields, tenant receipt, no credential/public invoice token fields. | TRIGGER_CRM_URL, TRIGGER_CRM_PAT_CONNECTOR, TRIGGER_CRM_TENANT_BINDINGS |
| R14 | https://trigger.tervory.com/trigger/crm/invoices | Open Invoices; page through the client’s own records and open an actual record. | BottleCRM records from this client’s bound organisation only; projected fields, tenant receipt, no credential/public invoice token fields. | TRIGGER_CRM_URL, TRIGGER_CRM_PAT_CONNECTOR, TRIGGER_CRM_TENANT_BINDINGS |
| R15 | https://trigger.tervory.com/chats | As tenant admin propose `trigger.crm.write` for an owned contact; inspect and Confirm the exact payload. | One native BottleCRM write under the tenant’s own organisation. An unconfirmed or mismatched payload is refused. | TRIGGER_CRM_URL, TRIGGER_CRM_PAT_CONNECTOR, TRIGGER_CRM_TENANT_BINDINGS |
| R16 | https://trigger.tervory.com/trigger/crm/leads | In an isolated second-organisation test session try a first-organisation record and a connector response with wrong organisation attestation. | No foreign record or write; wrong/missing organisation attestation fails closed. Do not modify a customer account. | TRIGGER_CRM_URL, TRIGGER_CRM_PAT_CONNECTOR, TRIGGER_CRM_TENANT_BINDINGS |
| R17 | https://trigger.tervory.com/trigger/marketing/channels | Connect Google, complete consent in the same workspace, list locations with `gbp.locations`, select the owned location and Confirm. | Single-use tenant/user-bound PKCE state; only refresh token sealed; selected Business Profile connected. | TRIGGER_GOOGLE_OAUTH_CLIENT_ID, TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET |
| R18 | https://trigger.tervory.com/trigger/marketing/channels | Connect Facebook, complete consent, then run `meta.pages` in chats. | Single-use tenant/user-bound state; available owned Pages, no Page/user token in card, logs or URL. | TRIGGER_META_APP_ID, TRIGGER_META_APP_SECRET |
| R19 | https://trigger.tervory.com/trigger/marketing/channels | Select the owned Page using `meta.page.select` and Confirm; retry a stale selection in the isolated fixture. | Owned Page and connection generation bound; stale/foreign Page refused; Page token remains sealed. | TRIGGER_META_APP_ID, TRIGGER_META_APP_SECRET |
| R20 | https://trigger.tervory.com/trigger/marketing/channels | Disconnect the owned Google connection and Confirm. | Provider grant revoked and sealed token cleared; a revocation failure keeps the connection recoverable. | TRIGGER_GOOGLE_OAUTH_CLIENT_ID, TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET |
| R21 | https://trigger.tervory.com/trigger/marketing/channels | Disconnect the owned Facebook Page and Confirm. | Meta grant revoked, sealed token cleared; refusal does not silently erase the recoverable connection. | TRIGGER_META_APP_ID, TRIGGER_META_APP_SECRET |
| R22 | https://trigger.tervory.com/trigger/marketing/composer | Draft from supplied facts, inspect the checked text, Approve and Confirm, then Schedule and Confirm an explicit future local time and IANA zone. | Separate durable draft/approval/schedule cards; only the reviewed revision is scheduled, with its receipt. | TRIGGER_GOOGLE_OAUTH_CLIENT_ID, TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET |
| R23 | https://trigger.tervory.com/trigger/marketing/composer | Edit an approved draft; try scheduling before reviewing and approving the new revision. | Edit returns to draft; stale approval cannot schedule; channel length/checker status is respected. | none |
| R24 | https://trigger.tervory.com/trigger/marketing/calendar | Approve and schedule a GBP test post on the founder’s own profile; inspect it after the planned time. | Published once; actual Google post ID, link, status and zero-cost publishing receipt on its card. | TRIGGER_GOOGLE_OAUTH_CLIENT_ID, TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET |
| R25 | https://trigger.tervory.com/trigger/marketing/calendar | Approve and schedule a Facebook test post on the founder’s own Page; inspect it after the planned time. | Published once; actual Meta post ID, permalink, status and zero-cost publishing receipt on its card. | TRIGGER_META_APP_ID, TRIGGER_META_APP_SECRET |
| R26 | https://trigger.tervory.com/chats | Using an isolated transport-loss fixture, inspect an uncertain delivery; Confirm reconciliation/retry. | Durable claim prevents duplicate delivery after crash. A matching provider post is reconciled instead of sent again. | TRIGGER_GOOGLE_OAUTH_CLIENT_ID, TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET, TRIGGER_META_APP_ID, TRIGGER_META_APP_SECRET |
| R27 | https://trigger.tervory.com/trigger/marketing/calendar | Use an isolated provider-refusal fixture for a scheduled post. | Failed status with sanitised provider message; no automatic retry of a terminal refusal. | TRIGGER_META_APP_ID, TRIGGER_META_APP_SECRET |
| R28 | https://trigger.tervory.com/trigger/marketing/calendar | Use isolated 429/5xx provider fixtures and inspect retry status. | Bounded backoff and attempt limit; no retry storm or duplicate successful send. | TRIGGER_META_APP_ID, TRIGGER_META_APP_SECRET |
| R29 | https://trigger.tervory.com/trigger/marketing/composer | Approve and schedule Instagram, LinkedIn and X text drafts; inspect their calendar status. | Scheduled-only; publisher never claims these channels. Instagram requires media that text posts do not have. | none |
| R30 | https://trigger.tervory.com/trigger/marketing/calendar | Switch Month/Week and use an explicit local zone; try nonexistent/repeated DST wall times in the fixture. | Correct local dates; ambiguous/nonexistent wall times refused without guessing an offset. | none |
| R31 | https://trigger.tervory.com/chats | Cancel a scheduled post and Confirm; inspect `trigger.posts`, calendar and `trigger.scorecard`. | Cancelled post is not delivered; own post states/counts and receipts remain available. | TRIGGER_GOOGLE_OAUTH_CLIENT_ID, TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET |
| R32 | https://trigger.tervory.com/trigger/marketing/reviews | Refresh Google reviews; draft/edit a reply from the review, inspect checks, Send reply and Confirm; refresh again. | Actual review text, rating and checked reply; one PUT for identical text, sent state and receipt. This is GBP review replying; Facebook supports posts. | TRIGGER_GOOGLE_OAUTH_CLIENT_ID, TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET |
| R33 | https://trigger.tervory.com/chats | Attach an owned source document; propose `trigger.bot.source.add` with kind document, inspect and Confirm. | Only that user/thread’s actual attachment is indexed; model-supplied text cannot replace it. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R34 | https://trigger.tervory.com/chats | List `trigger.bot.sources`; remove an approved source and Confirm; ask about its old content in the fixture. | Removed and foreign passages cannot ground an answer; another tenant’s index remains intact. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R35 | https://trigger.tervory.com/chats | Add an approved question/answer with `trigger.bot.faq.add`, Confirm, then ask the matching question. | Exact approved FAQ answer with source and zero-model, zero-cost receipt. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R36 | https://trigger.tervory.com → approved store embed | Open Chat → Start chat on the store origin; ask a question supported by an approved source. | Sourced answer and real source links; public response excludes internal passages/credentials; pending Send cannot submit twice. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R37 | https://trigger.tervory.com → approved store embed | Ask an unsupported question or open outside configured hours; use Talk to a person. | No invented answer; hand-over status and existing hand-over email to the configured recipient. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM |
| R38 | https://trigger.tervory.com/trigger/bot/settings | Set On/Off, actual store greeting, explicit hours and IANA zone; Save settings, inspect and Confirm. | Proposal alone writes nothing; only confirmed tenant-bound captured settings save; replay writes once. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R39 | https://trigger.tervory.com → approved store embed | Before supplying the real notice, inspect Leave details and Request a quote; in the isolated fixture submit an old notice version. | Capture stays disabled without a notice/version; missing or changed notice is refused before writing contact data. Requires founder privacy wording: FOUNDER-SETTINGS D2. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R40 | https://trigger.tervory.com → approved store embed | With founder privacy notice/version (D2), Leave details; enter actual first/last name and contact, then Send my details. | Names and contact preserved as a lead draft, with source conversation; no automatic CRM write. Requires D2. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R41 | https://trigger.tervory.com → approved store embed | With the approved Rig catalogue, ask the current product price, then Request a quote under the founder privacy notice/version (D2); supply actual product, quantity, title/request and contact. | Price answer uses the current Rig record and exact source link; no stale-page price without live Rig. Quote draft preserves request metadata with no invented price, invoice or automatic send. Requires D2. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R42 | https://trigger.tervory.com/trigger/bot/inbox | Open the conversation, hand over, inspect transcript/sources, enter a human reply and Confirm. | Saved human reply reaches only that web conversation/visitor; another visitor cannot poll it; no WhatsApp send bypass. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R43 | https://trigger.tervory.com/chats | Add the founder-owned HTTPS website source and Confirm; embed its returned public key only on that origin. | Origin/region-bound hashed public key; guarded same-site crawl respects robots; removing source revokes its key. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R44 | https://trigger.tervory.com/v1/bot/whatsapp | Register the existing Meta verification callback privately; use signed provider fixtures for invalid signature/unknown number. | Correct verification challenge; invalid signature refused before parsing; unknown number never replies. | TRIGGER_WHATSAPP_APP_SECRET, TRIGGER_WHATSAPP_VERIFY_TOKEN, TRIGGER_WHATSAPP_TOKEN_CONNECTOR, TRIGGER_WHATSAPP_BINDINGS |
| R45 | https://trigger.tervory.com/chats; founder WhatsApp number | Send the matching FAQ question to the bound number, replay its webhook fixture, then read `trigger.bot.stats`. | One free-form reply with source; sealed sender identity; no duplicate send; stats count includes this month’s replies. | TRIGGER_WHATSAPP_APP_SECRET, TRIGGER_WHATSAPP_VERIFY_TOKEN, TRIGGER_WHATSAPP_TOKEN_CONNECTOR, TRIGGER_WHATSAPP_BINDINGS, TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R46 | https://trigger.tervory.com/chats; founder WhatsApp number | In isolated fixtures exercise replies 999, 1000 and 1001 concurrently, then cross month-end in Johannesburg and Los Angeles. | 999 and 1000 send; next hands over without sending. Count reserves before send and resets at midnight on day 1 in the binding’s account timezone. | TRIGGER_WHATSAPP_APP_SECRET, TRIGGER_WHATSAPP_VERIFY_TOKEN, TRIGGER_WHATSAPP_TOKEN_CONNECTOR, TRIGGER_WHATSAPP_BINDINGS, TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM |
| R47 | https://trigger.tervory.com/chats; founder WhatsApp number | In isolated fixtures omit/invalidly set binding timezone, close the 24-hour window, then fail or crash a send. | Hand-over without reply outside the window or without a valid zone; failed sends never refund reserved count or replay after crash. | TRIGGER_WHATSAPP_APP_SECRET, TRIGGER_WHATSAPP_VERIFY_TOKEN, TRIGGER_WHATSAPP_TOKEN_CONNECTOR, TRIGGER_WHATSAPP_BINDINGS, TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM |
| R48 | https://trigger.tervory.com/trigger/bot/inbox | In an isolated aged-conversation fixture run retention and inspect another tenant plus confirmed CRM/quote records. | Only expired tenant conversations and unconfirmed drafts are removed; fresh conversations and confirmed records survive. Founder retention wording: D2. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R49 | https://trigger.tervory.com/chats | Draft each supported writing format and inspect its length/check report, including weighted X text. | Nine shipped formats, correct channel counting and explicit no-limit fields; text is not silently truncated. | none |
| R50 | https://trigger.tervory.com/chats | Accept an email example, draft another email, then switch format/organisation in the fixture. | Only accepted examples of the same tenant and format are ranked and used; withdrawal removes eligibility. | none |
| R51 | https://trigger.tervory.com/chats | Use `trigger.revise` for an owned write, inspect and Confirm. | New checked child write with parent ID; original brief/text snapshot retained and foreign writes refused. | none |
| R52 | https://trigger.tervory.com/chats | Use `trigger.voice.learn` from changes, inspect literal rule preview, cancel then Confirm a fresh preview. | Only supplied changes become voice rules; existing fields retained; stale/cancelled preview cannot save. | none |
| R53 | https://trigger.tervory.com/chats | Attach a catalogue CSV (up to 25 products), ask `trigger.write.batch: attachment <actual filename>`, inspect and Confirm. | One product draft/check/receipt per actual CSV row; each uses only its own facts; no publication or invented product data. | none |
| R54 | https://trigger.tervory.com/chats | Read `trigger.scorecard` after writing/feedback and compare formats/periods. | Tenant-only last-30-day and weekly counts, acceptance/example rates and zero-cost read receipt; no invented missing metrics. | none |
| R55 | https://trigger.tervory.com/chats | Give `trigger.bot.feedback` for an actual message with a correction; read `trigger.bot.review` and `trigger.bot.stats`. | Feedback belongs to that tenant/message; correction is a reviewable FAQ draft, never silently approved. | TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |
| R56 | https://trigger.tervory.com/trigger/bot/inbox; https://trigger.tervory.com/chats | Review the visitor’s actual lead/quote draft; Confirm the existing lead/quote action after privacy notice (D2). | Only unchanged tenant-owned draft activates once through the existing CRM/Rig corridor; no unconfirmed side effect. Requires D2. | TRIGGER_CRM_URL, TRIGGER_CRM_PAT_CONNECTOR, TRIGGER_CRM_TENANT_BINDINGS, TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS |

## Frame and capability boundaries

No new visible wording or UI is introduced by this acceptance work. The approved
FIXED/DATA register and existing missing variants remain listed in
`docs/ops/TRIGGER-WAVE4.md`: connection/cancellation confirmations, platform
errors/receipt placement, missing-source-link chips and navigation placements.
Founder privacy wording is D2; no invented notice is used. Disabled CRM
send/payment/delete/convert controls and unframed shared-menu destinations do not
become features through this sheet. Google review replies are shipped; Facebook
post publication does not imply Facebook review replies. Instagram, LinkedIn and
X remain scheduled-only. TikTok/YouTube connections remain disabled.

Offline proof exercises actual handlers/SQL/React with fake provider, model,
mail and index boundaries; it makes no paid/model/provider request. This sheet
is the live founder checklist, not a claim that production acceptance has run.
