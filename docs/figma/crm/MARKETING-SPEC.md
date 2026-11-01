# Marketing · design proposal

## Trigger menu revision · founder 1 November 2026, 14:25

This revision supersedes the earlier Workspace/CRM submenu design and the pending Estimates rename. CRM is Trigger. Applied across all 180 founder/store screens: CRM 92 (64 entity screens plus 28 confirmations), Marketing 44 and Chat bot 44. Every original screen ID, field value node and confirmation step is retained.

One 240px left menu only. Top: the existing approved Tervory on-white logo, client switcher, then Trigger bound to `color/accent/trigger` (`VariableID:72:9815`). The source asset is `workspace/public/brand/tervory-logo-on-white.png`, image hash `f5ac182d72fee0efa7e44827420ee36fb292e8d9`; the white stamp is not used.

| Draft group | Areas in order |
|---|---|
| Writing | write, voice |
| CRM | Leads, Accounts, Contacts, Opportunities, Cases, Tasks |
| Sales | Quotes, Invoices |
| Marketing | Channels, Calendar, Composer, Google reviews |
| Chat bot | Inbox, Settings |

Bottom: All products (back to all products), Receipts, Billing, Settings. Group labels and the All products label remain draft wording for founder approval. The Workspace product list is removed from every Trigger screen. Quotes is the founder-authorized display name for BottleCRM Estimates; schema names, estimate bindings and confirmation fields remain unchanged.

Shared editable component set `180:8549`: desktop menu `180:8387`, mobile menu `180:8467`; mobile bar `180:8550`. At 1440, work area starts at x=240 and is 1200px wide, with 1136px usable content after 32px side padding: a 180px gain. Lists use full-width tables; wide schemas keep horizontal scrolling without deleting columns. Detail forms use two columns; Composer draft/check panels sit beside each other. At 375, content stacks below a 64px Trigger bar. One drawer contains the same 240px menu and groups; its 375px overlay includes a dismiss scrim. Groups scroll vertically on mobile, while top/bottom controls stay pinned.

Drawer roots retain their IDs: CRM `98:9181` / `98:9227`, Marketing `150:4047` / `150:4061`, Chat bot `153:4367` / `153:4381`. Navigation to designed areas is wired; cross-page actions are Figma file references. No new Writing or account destination screens were invented.

In-screen design-index strips are removed; the screen registers below are the design index on SPEC only. Existing page titles remain. Channels has one compact 64px row per channel: name, account, status and exactly one visible Connect or Disconnect button according to state. Disconnect retains its confirmation. Mobile Channels uses horizontal table scrolling.

The 42 client-site widget frames remain client-branded visitor surfaces without Trigger founder chrome. They are not Trigger store screens and retain their existing IDs and source fields.

### Revision validation

Structural reconciliation checks all 180 original root IDs and 2318 baseline field-value IDs/texts (CRM 1678, Marketing 380, Chat bot 260). No baseline field was removed or changed. The expanded hidden-layer audit also sees 164 pre-existing CRM table-header value internals omitted by the original visible-instance snapshot; these are header internals, not added records. All 64 confirmation roots remain. Every desktop root has exactly one 240px Trigger menu and a 1200px work area; every mobile root has the Trigger bar and one same-page drawer. No old Workspace product labels or in-screen design-index frame remains.

No application code or application tests changed. Figma structure checks and authoring screenshots are design evidence; founder acceptance remains pending.

DRAFT — founder approval pending. No application or live connection was created.

Figma file: [Tervory designs](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=148-9). Page **4 · Marketing**, ID `148:9`. Branch `codex/crm-marketing-chat-design`.

## Authority and scope

Source: founder's pasted Marketing and Chat bot design brief, 1 November 2026; existing CRM page `93:2` and `origin/codex/crm-design:docs/figma/crm/SPEC.md`; `agents/trigger/README.md`. The new design words are drafts, explicitly authorized for approval in this design job. Founder-only screens; this is not clearance to implement or publish client UI. Existing rejected client dashboards, signup/billing screens and sidebar proposals are not revived.

Existing CRM field/action components `93:6` and `93:4`, local variables and typography are reused. Trigger chrome and responsive layout follow the controlling revision above. Jost Light headings and Inter body remain.

## Menu and approval items

The founder's 14:25 revision above replaces the old Workspace/CRM submenu. Quotes is now applied as the display name; the former approval-only rename decision is superseded.

## Screen register

| Screen | Size | State | Figma ID |
|---|---|---|---|
| Channels | Desktop | Zero | `149:2263` |
| Channels | Desktop | Filled | `149:2696` |
| Channels | Mobile | Zero | `149:3129` |
| Channels | Mobile | Filled | `149:3459` |
| Calendar · Month | Desktop | Zero | `149:3789` |
| Calendar · Month | Desktop | Filled | `149:4224` |
| Calendar · Month | Mobile | Zero | `149:4663` |
| Calendar · Month | Mobile | Filled | `149:4995` |
| Calendar · Week | Desktop | Zero | `149:5331` |
| Calendar · Week | Desktop | Filled | `149:5710` |
| Calendar · Week | Mobile | Zero | `149:6093` |
| Calendar · Week | Mobile | Filled | `149:6369` |
| Composer | Desktop | Zero | `149:6649` |
| Composer | Desktop | Filled | `149:7134` |
| Composer | Mobile | Zero | `149:7619` |
| Composer | Mobile | Filled | `149:8001` |
| Post detail | Desktop | Zero | `149:8383` |
| Post detail | Desktop | Filled | `149:8745` |
| Post detail | Mobile | Zero | `149:9107` |
| Post detail | Mobile | Filled | `149:9366` |
| Google Business Profile · Posts | Desktop | Zero | `149:9625` |
| Google Business Profile · Posts | Desktop | Filled | `149:9975` |
| Google Business Profile · Posts | Mobile | Zero | `149:10325` |
| Google Business Profile · Posts | Mobile | Filled | `149:10572` |
| Google Business Profile · Reviews | Desktop | Zero | `149:10819` |
| Google Business Profile · Reviews | Desktop | Filled | `149:11184` |
| Google Business Profile · Reviews | Mobile | Zero | `149:11549` |
| Google Business Profile · Reviews | Mobile | Filled | `149:11811` |
| Confirm · Approve | Desktop | Zero | `149:21139` |
| Confirm · Approve | Desktop | Filled | `149:21481` |
| Confirm · Approve | Mobile | Zero | `149:21823` |
| Confirm · Approve | Mobile | Filled | `149:22062` |
| Confirm · Schedule | Desktop | Zero | `149:22301` |
| Confirm · Schedule | Desktop | Filled | `149:22643` |
| Confirm · Schedule | Mobile | Zero | `149:22985` |
| Confirm · Schedule | Mobile | Filled | `149:23224` |
| Confirm · Send review reply | Desktop | Zero | `149:23463` |
| Confirm · Send review reply | Desktop | Filled | `149:23802` |
| Confirm · Send review reply | Mobile | Zero | `149:24141` |
| Confirm · Send review reply | Mobile | Filled | `149:24377` |
| Confirm · Disconnect | Desktop | Zero | `149:24613` |
| Confirm · Disconnect | Desktop | Filled | `149:24946` |
| Confirm · Disconnect | Mobile | Zero | `149:25279` |
| Confirm · Disconnect | Mobile | Filled | `149:25509` |

Entry flows: Channels desktop/mobile × Zero/Filled. Confirmation screens preserve viewport and state. Confirm and Cancel return to their originating view; Figma sends no request. Mobile CRM drawers are `150:4047`, `150:4061`. Cross-page Marketing/Chat bot links are Figma design references, not public product links.

## Proposed field register

These are proposed design binding paths, not claimed existing scheduler API endpoints. Filled values are bracketed bindings; Zero data values are em dashes, calendars have no post records, and no client facts/results are fabricated.

### Channels

| Draft label | Binding |
|---|---|
| Account | `channel.account_name` |
| Status | `channel.status` |

Actions: Connect, Disconnect.

### Calendar · Month

| Draft label | Binding |
|---|---|
| Period | `calendar.period` |
| Time zone | `calendar.time_zone` |
| Channel | `post.channel` |
| Status | `post.status` |

Actions: view / navigation only.

### Calendar · Week

| Draft label | Binding |
|---|---|
| Period | `calendar.period` |
| Time zone | `calendar.time_zone` |
| Channel | `post.channel` |
| Status | `post.status` |

Actions: view / navigation only.

### Composer

| Draft label | Binding |
|---|---|
| Brief | `post.brief` |
| Saved voice | `voice.revision` |
| Draft text | `post.text` |
| Media | `post.media` |
| Channels | `post.channels` |
| Findings | `checks.findings` |
| Checker status | `checks.complete` |
| Rule | `checks.rule` |
| Location | `checks.location` |
| Scheduled for | `post.scheduled_at` |
| Time zone | `post.time_zone` |
| Preview | `post.previews[channel].text` |
| Length limit | `channel_limits[channel].limit` |
| Counted as | `channel_limits[channel].unit` |
| Length used | `post.previews[channel].length` |

Actions: Approve, Schedule.

### Post detail

| Draft label | Binding |
|---|---|
| Channel | `post.channel` |
| Status | `post.status` |
| Text | `post.text` |
| Media | `post.media` |
| Status history | `post.history` |
| Reported at | `post.metrics.reported_at` |
| Reach | `post.metrics.reach` |
| Clicks | `post.metrics.clicks` |
| Comments | `post.metrics.comments` |

Actions: view / navigation only.

### Google Business Profile · Posts

| Draft label | Binding |
|---|---|
| Profile | `gbp.profile_name` |
| Post | `gbp.post.text` |
| Status | `gbp.post.status` |
| Published at | `gbp.post.published_at` |

Actions: New post.

### Google Business Profile · Reviews

| Draft label | Binding |
|---|---|
| Profile | `gbp.profile_name` |
| Review | `review.text` |
| Rating | `review.rating` |
| Received at | `review.created_at` |
| Reply brief | `reply.brief` |
| Draft reply | `reply.text` |
| Saved voice | `voice.revision` |
| Checker findings | `reply.checks` |
| Reply status | `reply.status` |

Actions: Send reply.

### Confirm · Approve

| Draft label | Binding |
|---|---|
| Post | `post.id` |
| Text | `post.text` |
| Channels | `post.channels` |
| Voice revision | `voice.revision` |
| Checker findings | `checks.findings` |

Actions: Confirm, Cancel.

### Confirm · Schedule

| Draft label | Binding |
|---|---|
| Post | `post.id` |
| Approved revision | `post.approved_revision` |
| Channels | `post.channels` |
| Scheduled for | `post.scheduled_at` |
| Time zone | `post.time_zone` |

Actions: Confirm, Cancel.

### Confirm · Send review reply

| Draft label | Binding |
|---|---|
| Profile | `gbp.profile_name` |
| Review | `review.id` |
| Reply | `reply.text` |
| Checker findings | `reply.checks` |

Actions: Confirm, Cancel.

### Confirm · Disconnect

| Draft label | Binding |
|---|---|
| Channel | `channel.name` |
| Account | `channel.account_name` |

Actions: Confirm, Cancel.

## Channel coverage and limits

All seven channels have compact connection rows and per-channel preview panels: Facebook, Instagram, LinkedIn, X, TikTok, YouTube, Google Business Profile. Connection states: Connected, Needs reconnecting, Off. Post states: Draft, Awaiting approval, Scheduled, Published, Failed. Calendar rows/cards retain channel and status. Google posts reuse the same Composer; Google reviews show a saved-voice reply draft and checker findings before confirmation.

Every preview includes `post.previews[channel].text`, `.length`, `channel_limits[channel].limit` and `.unit`. Limits are data and must be read from the chosen adapter and current post format/account capabilities; never invent a single universal character count. The draft shows each limit slot explicitly, with a bracketed binding until the adapter is chosen. Read-only official references checked for future adapter mapping: [LinkedIn](https://learn.microsoft.com/en-us/linkedin/compliance/integrations/shares/ugc-post-api) documents 3,000 characters; [X](https://docs.x.com/fundamentals/counting-characters) documents a 280 weighted-character standard post and twitter-text counting; [TikTok direct video](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post) documents 2,200 UTF-16 runes for caption; [YouTube](https://developers.google.com/youtube/data/reference/rest/v3/videos) documents description max 5,000 bytes, not characters. Facebook, Instagram and Google Business Profile numeric constraints require verification against the selected adapter/official endpoint before implementation. A missing limit blocks scheduling; approval wording for that validation is still draft. No platform API was called or credential accessed.

Post detail reports only returned reach, clicks and comments with a reporting timestamp. Unsupported/unreturned metrics remain absent/em dash, never fabricated zero; no claim all platforms expose all three metrics.

## Founder confirmations and behavior

- Approve: exact post revision, channel selection, saved-voice revision and checker findings reviewed before confirmation. Editing text/media/channels invalidates previous approval.
- Schedule: approved revision, channels, date/time and time zone shown before confirmation. Changed schedule or changed post requires a new confirmation; validation is code-only.
- Send review reply: exact profile, review and checked reply shown before confirmation. No reply is sent by the prototype.
- Disconnect: selected channel/account shown before confirmation. Connect is a draft action only; no sign-in, account setup, settings or secret workflow was designed.
- Zero screens cannot authorize external operations without a real record; their controls demonstrate draft layout only. Connect/disconnect, approval, scheduling and sending are future scoped operations, not existing integrations.

## Engine decisions for the founder — not selected or installed

| Feature | Existing/free engine to reuse or evaluate | Decision |
|---|---|---|
| Channels, calendars, scheduling, previews | Open-source social scheduler; [Postiz upstream](https://github.com/gitroomhq/postiz-app) is a candidate for evaluation, not the selected engine | Founder chooses scheduler and confirms adapter coverage; do not recode one |
| Composer and review replies | Existing Trigger saved-voice drafting and existing code checkers | Reuse Trigger; drafting subject to later implementation brief, no drafting model was called for this design |
| Platform status/results | Chosen scheduler adapters and each platform's returned data | Verify fields, capabilities and limits; no invented API contract |
| Confirmation gates | Existing CRM/Tervory confirmation pattern | Exact fields above; prototype has no side effects |

No ads spend, budgets, pricing, payment, billing, credits or keys are included in the new content. Existing founder chrome is reused as the brief directs; old chrome labels are not new feature work.

## Every new draft wording string awaiting approval

All view names, labels, actions, statuses and day abbreviations below await founder approval. Dynamic bracketed paths are annotations, not proposed client copy. Existing reused CRM/founder chrome text is not newly approved by this task.

- Account
- Approve
- Approved revision
- Brief
- Calendar · Month
- Calendar · Week
- Cancel
- Channel
- Channels
- Checker findings
- Checker status
- Clicks
- Comments
- Composer
- Confirm
- Confirm · Approve
- Confirm · Disconnect
- Confirm · Schedule
- Confirm · Send review reply
- Connect
- Connected · Needs reconnecting · Off
- Counted as
- Disconnect
- Draft reply
- Draft text
- Draft · Awaiting approval · Scheduled · Published · Failed
- Facebook
- Facebook preview
- Findings
- Fri
- Google Business Profile
- Google Business Profile preview
- Google Business Profile · Posts
- Google Business Profile · Reviews
- Instagram
- Instagram preview
- Length limit
- Length used
- LinkedIn
- LinkedIn preview
- Location
- Media
- Mon
- Month
- New post
- Nothing runs until you confirm.
- Period
- Post
- Post detail
- Preview
- Profile
- Published at
- Rating
- Reach
- Received at
- Reply
- Reply brief
- Reply status
- Reported at
- Review
- Rule
- Sat
- Saved voice
- Schedule
- Scheduled for
- Send reply
- Status
- Status history
- Sun
- Text
- Thu
- TikTok
- TikTok preview
- Time zone
- Trigger checks
- Tue
- Voice revision
- Wed
- Week
- X
- X preview
- YouTube
- YouTube preview

## Validation and proof

Initial creation audit (before the 14:25 reflow): Current deterministic audit: 44 screens; 380 field-value instances; viewport errors 0. Editable descendant types: FRAME=564, TEXT=1460, INSTANCE=704. No complete-UI raster was used. Source components and native logo instances remain linked. Visual checks identified and repaired horizontal container sizing and button wrapping. Final visual checks and source/field reconciliation are recorded before handoff; Figma authoring screenshots are not founder acceptance screenshots. No live application test or founder approval is claimed. Current geometry and preservation evidence is recorded in the controlling revision above; descendant counts here are historical.

## Final handoff proof · 1 November 2026

Native Figma SPEC: `151:3973`. Draft close-control wording: **Close**; this also awaits approval. The controlling 14:25 revision above supersedes the earlier submenu and rename proof. Existing screen registers and confirmation IDs remain valid.

Mobile drawers now use the shared Trigger menu and a dismiss scrim within the same preserved root IDs. Content spacing uses existing space variables; original entity field nodes and values remain.

Final rendered-binding audit: 82 distinct label/binding pairs, zero wrong heading/body font families. Exact rendered field paths follow below. The arrays/dictionary paths in the conceptual field register describe the same proposed data contract; none is an assertion of an existing scheduler or Chatwoot API.

Commands run in `/workspace/codex-crm-marketing-chat-design` unless absolute paths are shown:

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-crm-marketing-chat-design
git fetch origin main codex/crm-design
git checkout -B codex/crm-marketing-chat-design origin/main
ls agents/trigger/README.md
git --no-pager show origin/codex/crm-design:docs/figma/crm/SPEC.md
git diff --check
git add docs/figma/crm/MARKETING-SPEC.md
git commit -m 'Document Marketing Figma screens, draft copy and confirmation contract'
git push -u origin codex/crm-marketing-chat-design
```

Results: clone/fetch/checkout/required source-file read succeeded; whitespace check passed; commits `e4f441ba` (Marketing) and `b285cce9` (Chat bot) pushed successfully. The first commit attempt lacked a local author identity and failed; the existing Codex identity from the prior CRM checkout was reused locally, then commit/push passed. A temporary helper write under `/tmp` failed with `Disk quota exceeded`; the authorized private checkout and its `.git` scratch area remained writable. No required source file, fetch or push failed. Figma API validation rejected intermediate type/scroll/reaction operations; the canvas was inspected after each failure, then targeted corrections were applied. No failed operation is counted as a completed screen. No application tests were run because no application code changed. No secrets or production data were read.

Figma authoring screenshots reviewed: Composer desktop `149:7134`, calendar mobile `149:4995`, mobile drawer `150:4047`. These are design-review evidence, not founder acceptance screenshots. Separate reviewer chat was notified; review is not claimed complete. Claude opens the PR from this branch; the founder alone merges. Founder approval and his own Figma/browser review remain pending.

## Exact rendered binding register

| Draft field label | Rendered binding |
|---|---|
| Account | `[channels.Facebook.account_name]` |
| Status | `[channels.Facebook.status]` |
| Account | `[channels.Instagram.account_name]` |
| Status | `[channels.Instagram.status]` |
| Account | `[channels.LinkedIn.account_name]` |
| Status | `[channels.LinkedIn.status]` |
| Account | `[channels.X.account_name]` |
| Status | `[channels.X.status]` |
| Account | `[channels.TikTok.account_name]` |
| Status | `[channels.TikTok.status]` |
| Account | `[channels.YouTube.account_name]` |
| Status | `[channels.YouTube.status]` |
| Account | `[channels.Google Business Profile.account_name]` |
| Status | `[channels.Google Business Profile.status]` |
| Period | `[calendar.period]` |
| Time zone | `[calendar.time_zone]` |
| Brief | `[post.brief]` |
| Saved voice | `[voice.revision]` |
| Draft text | `[post.text]` |
| Media | `[post.media]` |
| Channels | `[post.channels]` |
| Findings | `[checks.findings]` |
| Checker status | `[checks.complete]` |
| Rule | `[checks.rule]` |
| Location | `[checks.location]` |
| Scheduled for | `[post.scheduled_at]` |
| Time zone | `[post.time_zone]` |
| Preview | `[post.previews.Facebook.text]` |
| Length limit | `[channel_limits.Facebook.limit]` |
| Counted as | `[channel_limits.Facebook.unit]` |
| Length used | `[post.previews.Facebook.length]` |
| Preview | `[post.previews.Instagram.text]` |
| Length limit | `[channel_limits.Instagram.limit]` |
| Counted as | `[channel_limits.Instagram.unit]` |
| Length used | `[post.previews.Instagram.length]` |
| Preview | `[post.previews.LinkedIn.text]` |
| Length limit | `[channel_limits.LinkedIn.limit]` |
| Counted as | `[channel_limits.LinkedIn.unit]` |
| Length used | `[post.previews.LinkedIn.length]` |
| Preview | `[post.previews.X.text]` |
| Length limit | `[channel_limits.X.limit]` |
| Counted as | `[channel_limits.X.unit]` |
| Length used | `[post.previews.X.length]` |
| Preview | `[post.previews.TikTok.text]` |
| Length limit | `[channel_limits.TikTok.limit]` |
| Counted as | `[channel_limits.TikTok.unit]` |
| Length used | `[post.previews.TikTok.length]` |
| Preview | `[post.previews.YouTube.text]` |
| Length limit | `[channel_limits.YouTube.limit]` |
| Counted as | `[channel_limits.YouTube.unit]` |
| Length used | `[post.previews.YouTube.length]` |
| Preview | `[post.previews.Google Business Profile.text]` |
| Length limit | `[channel_limits.Google Business Profile.limit]` |
| Counted as | `[channel_limits.Google Business Profile.unit]` |
| Length used | `[post.previews.Google Business Profile.length]` |
| Channel | `[post.channel]` |
| Status | `[post.status]` |
| Text | `[post.text]` |
| Status history | `[post.history]` |
| Reported at | `[post.metrics.reported_at]` |
| Reach | `[post.metrics.reach]` |
| Clicks | `[post.metrics.clicks]` |
| Comments | `[post.metrics.comments]` |
| Profile | `[gbp.profile_name]` |
| Post | `[gbp.post.text]` |
| Status | `[gbp.post.status]` |
| Published at | `[gbp.post.published_at]` |
| Review | `[review.text]` |
| Rating | `[review.rating]` |
| Received at | `[review.created_at]` |
| Reply brief | `[reply.brief]` |
| Draft reply | `[reply.text]` |
| Checker findings | `[reply.checks]` |
| Reply status | `[reply.status]` |
| Post | `[post.id]` |
| Voice revision | `[voice.revision]` |
| Checker findings | `[checks.findings]` |
| Approved revision | `[post.approved_revision]` |
| Review | `[review.id]` |
| Reply | `[reply.text]` |
| Channel | `[channel.name]` |
| Account | `[channel.account_name]` |