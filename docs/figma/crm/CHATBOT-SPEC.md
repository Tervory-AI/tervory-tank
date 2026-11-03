# Chat bot · current specification · 3 November

This replaces the previous Chat bot SPEC in full. Historical proposals and raw binding paths are removed. Changed frames are **Changed after approval, awaiting founder**; unchanged Closed widget previews are **Approved 3 Nov**. Existing original screen and component IDs are retained where possible.

## Client widget character and slots

Component set `152:3622` contains 26 variants: 13 views × Zero/Filled. The widget uses only the client's accent, ink, paper and line variables: `VariableID:152:3601`, `152:3603`, `152:3605`, `152:3607`. It has no Tervory logo, Trigger menu, CRM colour, model name or technical binding path. Atkinson Hyperlegible body and Literata headings remain. Frame captions outside the client surface are approval metadata only.

Every visitor slot uses plain words in brackets. These are design annotations, not actual client identities, messages, sources or records. Source chips repeat under each bot answer and contain a title and domain. Their link target is the returned Source link for that exact source record; a placeholder chip has no invented external URL and becomes a real link only when that source exists. The list must support any returned source count, not a fixed two sources. The two chips shown are repeated-slot specimens.

## Widget state graph

- Closed → Open → Conversation. Close is an × at the top right and returns to Closed.
- Conversation `152:3613` shows the visitor message as Pending, without an answer. Sending is a separate new pending-message state. A successful reply moves to Answer `152:3615` and displays the bot bubble with its repeatable source chips.
- Send on Answer goes to Sending with a New message pending, never back to the old Conversation state. Pending Send is disabled. Prototype delayed transitions demonstrate the next state; they do not call an answering service.
- With no eligible client evidence, show the configured No-source message, then hand over. No source never produces a bot answer or general-web fallback.
- Offline and Outside hours each have their own state; they do not show a fabricated answer or staff availability.
- Hand-over shows Connecting you to a person. A Person bubble contains the person's identity and reply and is visually distinct from the Bot and visitor bubbles.
- The lead form uses First name, Last name, Email, Phone and Notes. Its action is Send my details → Details sent. It no longer jumps to Hand-over.
- The quote form uses Title, Product, Quantity, Your request and Contact. Its action is Send request → Request sent. It no longer jumps to Hand-over.
- The lead form has a Privacy notice — awaiting founder decision slot. This is a design marker; it is not the privacy notice wording. The founder decides the notice before widget implementation.

Website preview widths remain 1440, 390 and 375. Open panels use a 343×640 client surface, with clipped vertical message/form scrolling and a separate composer/action footer. Bubbles preserve role distinctions; sources belong to bot answers only.

## Store flows and matching fields

One 240px Trigger menu and a wide desktop content area; one mobile drawer with a pinned account block, full-width divider and scroll clearance. The page/menu names are Inbox and Settings. Hand-over and Lead draft are consistent. Account settings names the account-level footer item so Settings occurs once in the menu.

- Filled desktop Inbox rows open Conversation detail; header/row columns share widths. Mobile uses a two-line summary linked to full detail.
- Conversation detail: visitor messages have Message only. Bot messages have Message, Who answered and Sources. Person messages have Message and a Person heading, not bot source/answer metadata.
- Hand-over → Hand-over screen → Confirm → Conversation detail. The screen is the review/confirmation step. Older separate confirmation specimens retain their IDs but are not inserted into this flow.
- Widget lead form, Lead draft and Confirm · Lead share First name, Last name and Notes, as well as Email and Phone. Submission is a draft until the store confirms it; visitor submission is not store consent.
- Quote draft and Confirm · Quote include Title. Requests remain drafts; no amount, price, invoice or payment is invented.
- Settings has one current-state On/Off toggle, Opening hours, Time zone, Greeting, Catalogue, FAQs, Documents, Hand-over rules, No-source message and Hand-over message. Confirm · Settings includes Time zone and both visitor-message fields, so those changes can be reviewed.
- Every outgoing reply, lead activation, quote activation and settings save retains the founder confirmation gate. Confirm/Cancel are prototype navigation, with no live effect.

## Shared controls

Action family `266:3038`: Primary `266:3032`, Secondary `266:3034`, Destructive `266:3036`. Labels are centred. Confirm uses Primary; Disconnect and Delete use Destructive. Store controls reuse the new scoped menu `266:3212`; client widget controls retain client-only colours. Native document `154:4349` and visible SPEC frame `210:6156` contain this same current document.

## Store screen and field register

- `149:13691` · conversations|Desktop|Zero · Changed after approval, awaiting founder · Fields: Visitor; Last message; Status; Assigned person; Updated at.
- `149:14042` · conversations|Desktop|Filled · Changed after approval, awaiting founder · Fields: Visitor; Last message; Status; Assigned person; Updated at.
- `149:14393` · conversations|Mobile|Zero · Changed after approval, awaiting founder · Fields: Last message; Visitor; Assigned person; Updated at; Status.
- `149:14641` · conversations|Mobile|Filled · Changed after approval, awaiting founder · Fields: Last message; Visitor; Assigned person; Updated at; Status.
- `149:14889` · conversation-detail|Desktop|Zero · Changed after approval, awaiting founder · Fields: Visitor; Status; Assigned person; Sources used; Reply; Message; Who answered; Sources.
- `149:15281` · conversation-detail|Desktop|Filled · Changed after approval, awaiting founder · Fields: Visitor; Status; Assigned person; Sources used; Reply; Message; Who answered; Sources.
- `149:15673` · conversation-detail|Mobile|Zero · Changed after approval, awaiting founder · Fields: Visitor; Status; Assigned person; Sources used; Reply; Message; Who answered; Sources.
- `149:15962` · conversation-detail|Mobile|Filled · Changed after approval, awaiting founder · Fields: Visitor; Status; Assigned person; Sources used; Reply; Message; Who answered; Sources.
- `149:16251` · handover|Desktop|Zero · Changed after approval, awaiting founder · Fields: Conversation; Person; Reason; Availability; Reply.
- `149:16604` · handover|Desktop|Filled · Changed after approval, awaiting founder · Fields: Conversation; Person; Reason; Availability; Reply.
- `149:16957` · handover|Mobile|Zero · Changed after approval, awaiting founder · Fields: Conversation; Person; Reason; Availability; Reply.
- `149:17207` · handover|Mobile|Filled · Changed after approval, awaiting founder · Fields: Conversation; Person; Reason; Availability; Reply.
- `149:17457` · lead-draft|Desktop|Zero · Changed after approval, awaiting founder · Fields: Draft status; First name; Last name; Email; Phone; Source conversation; Notes.
- `149:17814` · lead-draft|Desktop|Filled · Changed after approval, awaiting founder · Fields: Draft status; First name; Last name; Email; Phone; Source conversation; Notes.
- `149:18171` · lead-draft|Mobile|Zero · Changed after approval, awaiting founder · Fields: Draft status; First name; Last name; Email; Phone; Source conversation; Notes.
- `149:18425` · lead-draft|Mobile|Filled · Changed after approval, awaiting founder · Fields: Draft status; First name; Last name; Email; Phone; Source conversation; Notes.
- `149:18679` · quote-draft|Desktop|Zero · Changed after approval, awaiting founder · Fields: Draft status; Title; Contact; Request; Line items; Source conversation.
- `149:19033` · quote-draft|Desktop|Filled · Changed after approval, awaiting founder · Fields: Draft status; Title; Contact; Request; Line items; Source conversation.
- `149:19387` · quote-draft|Mobile|Zero · Changed after approval, awaiting founder · Fields: Draft status; Title; Contact; Request; Line items; Source conversation.
- `149:19638` · quote-draft|Mobile|Filled · Changed after approval, awaiting founder · Fields: Draft status; Title; Contact; Request; Line items; Source conversation.
- `149:19889` · bot-settings|Desktop|Zero · Changed after approval, awaiting founder · Fields: Bot; Opening hours; Time zone; Greeting; Catalogue; FAQs; Documents; Hand-over rules; No-source message; Hand-over message.
- `149:20253` · bot-settings|Desktop|Filled · Changed after approval, awaiting founder · Fields: Bot; Opening hours; Time zone; Greeting; Catalogue; FAQs; Documents; Hand-over rules; No-source message; Hand-over message.
- `149:20617` · bot-settings|Mobile|Zero · Changed after approval, awaiting founder · Fields: Bot; Opening hours; Time zone; Greeting; Catalogue; FAQs; Documents; Hand-over rules; No-source message; Hand-over message.
- `149:20878` · bot-settings|Mobile|Filled · Changed after approval, awaiting founder · Fields: Bot; Opening hours; Time zone; Greeting; Catalogue; FAQs; Documents; Hand-over rules; No-source message; Hand-over message.
- `151:6994` · confirm-send-reply|Desktop|Zero · Changed after approval, awaiting founder · Fields: Conversation; Recipient; Reply.
- `151:7330` · confirm-send-reply|Desktop|Filled · Changed after approval, awaiting founder · Fields: Conversation; Recipient; Reply.
- `151:7666` · confirm-send-reply|Mobile|Zero · Changed after approval, awaiting founder · Fields: Conversation; Recipient; Reply.
- `151:7899` · confirm-send-reply|Mobile|Filled · Changed after approval, awaiting founder · Fields: Conversation; Recipient; Reply.
- `151:8132` · confirm-handover|Desktop|Zero · Changed after approval, awaiting founder · Fields: Conversation; Person; Reason.
- `151:8468` · confirm-handover|Desktop|Filled · Changed after approval, awaiting founder · Fields: Conversation; Person; Reason.
- `151:8804` · confirm-handover|Mobile|Zero · Changed after approval, awaiting founder · Fields: Conversation; Person; Reason.
- `151:9037` · confirm-handover|Mobile|Filled · Changed after approval, awaiting founder · Fields: Conversation; Person; Reason.
- `151:9270` · confirm-lead|Desktop|Zero · Changed after approval, awaiting founder · Fields: Lead draft; Source conversation; First name; Email; Phone; Last name; Notes.
- `151:9612` · confirm-lead|Desktop|Filled · Changed after approval, awaiting founder · Fields: Lead draft; Source conversation; First name; Email; Phone; Last name; Notes.
- `151:9954` · confirm-lead|Mobile|Zero · Changed after approval, awaiting founder · Fields: Lead draft; Source conversation; First name; Email; Phone; Last name; Notes.
- `151:10193` · confirm-lead|Mobile|Filled · Changed after approval, awaiting founder · Fields: Lead draft; Source conversation; First name; Email; Phone; Last name; Notes.
- `151:10432` · confirm-quote|Desktop|Zero · Changed after approval, awaiting founder · Fields: Draft quote; Contact; Request; Line items; Title.
- `151:10771` · confirm-quote|Desktop|Filled · Changed after approval, awaiting founder · Fields: Draft quote; Contact; Request; Line items; Title.
- `151:11110` · confirm-quote|Mobile|Zero · Changed after approval, awaiting founder · Fields: Draft quote; Contact; Request; Line items; Title.
- `151:11346` · confirm-quote|Mobile|Filled · Changed after approval, awaiting founder · Fields: Draft quote; Contact; Request; Line items; Title.
- `151:11582` · confirm-settings|Desktop|Zero · Changed after approval, awaiting founder · Fields: Bot; Opening hours; Greeting; Sources; Hand-over rules; Time zone; No-source message; Hand-over message.
- `151:11924` · confirm-settings|Desktop|Filled · Changed after approval, awaiting founder · Fields: Bot; Opening hours; Greeting; Sources; Hand-over rules; Time zone; No-source message; Hand-over message.
- `151:12266` · confirm-settings|Mobile|Zero · Changed after approval, awaiting founder · Fields: Bot; Opening hours; Greeting; Sources; Hand-over rules; Time zone; No-source message; Hand-over message.
- `151:12505` · confirm-settings|Mobile|Filled · Changed after approval, awaiting founder · Fields: Bot; Opening hours; Greeting; Sources; Hand-over rules; Time zone; No-source message; Hand-over message.

## Widget screen register

- `152:3879` · widget-closed|1440|Zero · Approved 3 Nov.
- `152:3882` · widget-closed|1440|Filled · Approved 3 Nov.
- `152:3885` · widget-closed|390|Zero · Approved 3 Nov.
- `152:3888` · widget-closed|390|Filled · Approved 3 Nov.
- `152:3891` · widget-closed|375|Zero · Approved 3 Nov.
- `152:3894` · widget-closed|375|Filled · Approved 3 Nov.
- `152:3897` · widget-open|1440|Zero · Changed after approval, awaiting founder.
- `152:3913` · widget-open|1440|Filled · Changed after approval, awaiting founder.
- `152:3929` · widget-open|390|Zero · Changed after approval, awaiting founder.
- `152:3945` · widget-open|390|Filled · Changed after approval, awaiting founder.
- `152:3961` · widget-open|375|Zero · Changed after approval, awaiting founder.
- `152:3977` · widget-open|375|Filled · Changed after approval, awaiting founder.
- `152:3993` · widget-conversation|1440|Zero · Changed after approval, awaiting founder.
- `152:4019` · widget-conversation|1440|Filled · Changed after approval, awaiting founder.
- `152:4046` · widget-conversation|390|Zero · Changed after approval, awaiting founder.
- `152:4072` · widget-conversation|390|Filled · Changed after approval, awaiting founder.
- `152:4099` · widget-conversation|375|Zero · Changed after approval, awaiting founder.
- `152:4125` · widget-conversation|375|Filled · Changed after approval, awaiting founder.
- `152:4152` · widget-answer|1440|Zero · Changed after approval, awaiting founder.
- `152:4178` · widget-answer|1440|Filled · Changed after approval, awaiting founder.
- `152:4205` · widget-answer|390|Zero · Changed after approval, awaiting founder.
- `152:4231` · widget-answer|390|Filled · Changed after approval, awaiting founder.
- `152:4258` · widget-answer|375|Zero · Changed after approval, awaiting founder.
- `152:4284` · widget-answer|375|Filled · Changed after approval, awaiting founder.
- `152:4311` · widget-hand-over|1440|Zero · Changed after approval, awaiting founder.
- `152:4328` · widget-hand-over|1440|Filled · Changed after approval, awaiting founder.
- `152:4345` · widget-hand-over|390|Zero · Changed after approval, awaiting founder.
- `152:4362` · widget-hand-over|390|Filled · Changed after approval, awaiting founder.
- `152:4379` · widget-hand-over|375|Zero · Changed after approval, awaiting founder.
- `152:4396` · widget-hand-over|375|Filled · Changed after approval, awaiting founder.
- `152:4413` · widget-lead|1440|Zero · Changed after approval, awaiting founder.
- `152:4438` · widget-lead|1440|Filled · Changed after approval, awaiting founder.
- `152:4463` · widget-lead|390|Zero · Changed after approval, awaiting founder.
- `152:4488` · widget-lead|390|Filled · Changed after approval, awaiting founder.
- `152:4513` · widget-lead|375|Zero · Changed after approval, awaiting founder.
- `152:4538` · widget-lead|375|Filled · Changed after approval, awaiting founder.
- `152:4563` · widget-quote|1440|Zero · Changed after approval, awaiting founder.
- `152:4591` · widget-quote|1440|Filled · Changed after approval, awaiting founder.
- `152:4619` · widget-quote|390|Zero · Changed after approval, awaiting founder.
- `152:4647` · widget-quote|390|Filled · Changed after approval, awaiting founder.
- `152:4675` · widget-quote|375|Zero · Changed after approval, awaiting founder.
- `152:4703` · widget-quote|375|Filled · Changed after approval, awaiting founder.
- `274:24240` · widget-sending|1440|Zero · Changed after approval, awaiting founder.
- `274:24257` · widget-sending|390|Zero · Changed after approval, awaiting founder.
- `274:24274` · widget-sending|375|Zero · Changed after approval, awaiting founder.
- `274:24291` · widget-sending|1440|Filled · Changed after approval, awaiting founder.
- `274:24308` · widget-sending|390|Filled · Changed after approval, awaiting founder.
- `274:24325` · widget-sending|375|Filled · Changed after approval, awaiting founder.
- `274:24342` · widget-no-source|1440|Zero · Changed after approval, awaiting founder.
- `274:24359` · widget-no-source|390|Zero · Changed after approval, awaiting founder.
- `274:24376` · widget-no-source|375|Zero · Changed after approval, awaiting founder.
- `274:24393` · widget-no-source|1440|Filled · Changed after approval, awaiting founder.
- `274:24410` · widget-no-source|390|Filled · Changed after approval, awaiting founder.
- `274:24427` · widget-no-source|375|Filled · Changed after approval, awaiting founder.
- `274:24444` · widget-offline|1440|Zero · Changed after approval, awaiting founder.
- `274:24461` · widget-offline|390|Zero · Changed after approval, awaiting founder.
- `274:24478` · widget-offline|375|Zero · Changed after approval, awaiting founder.
- `274:24495` · widget-offline|1440|Filled · Changed after approval, awaiting founder.
- `274:24512` · widget-offline|390|Filled · Changed after approval, awaiting founder.
- `274:24529` · widget-offline|375|Filled · Changed after approval, awaiting founder.
- `274:24546` · widget-outside-hours|1440|Zero · Changed after approval, awaiting founder.
- `274:24563` · widget-outside-hours|390|Zero · Changed after approval, awaiting founder.
- `274:24580` · widget-outside-hours|375|Zero · Changed after approval, awaiting founder.
- `274:24597` · widget-outside-hours|1440|Filled · Changed after approval, awaiting founder.
- `274:24614` · widget-outside-hours|390|Filled · Changed after approval, awaiting founder.
- `274:24631` · widget-outside-hours|375|Filled · Changed after approval, awaiting founder.
- `274:24648` · widget-details-sent|1440|Zero · Changed after approval, awaiting founder.
- `274:24665` · widget-details-sent|390|Zero · Changed after approval, awaiting founder.
- `274:24682` · widget-details-sent|375|Zero · Changed after approval, awaiting founder.
- `274:24699` · widget-details-sent|1440|Filled · Changed after approval, awaiting founder.
- `274:24716` · widget-details-sent|390|Filled · Changed after approval, awaiting founder.
- `274:24733` · widget-details-sent|375|Filled · Changed after approval, awaiting founder.
- `274:24750` · widget-request-sent|1440|Zero · Changed after approval, awaiting founder.
- `274:24767` · widget-request-sent|390|Zero · Changed after approval, awaiting founder.
- `274:24784` · widget-request-sent|375|Zero · Changed after approval, awaiting founder.
- `274:24801` · widget-request-sent|1440|Filled · Changed after approval, awaiting founder.
- `274:24818` · widget-request-sent|390|Filled · Changed after approval, awaiting founder.
- `274:24835` · widget-request-sent|375|Filled · Changed after approval, awaiting founder.

## New component variants

- `274:14621` · Sending · Zero.
- `274:14647` · Sending · Filled.
- `274:14673` · No source · Zero.
- `274:14699` · No source · Filled.
- `274:14725` · Offline · Zero.
- `274:14751` · Offline · Filled.
- `274:14777` · Outside hours · Zero.
- `274:14803` · Outside hours · Filled.
- `274:14829` · Details sent · Zero.
- `274:14855` · Details sent · Filled.
- `274:14881` · Request sent · Zero.
- `274:14907` · Request sent · Filled.

## Wording awaiting founder approval

The three visitor-facing proposals explicitly requested are Connecting you to a person, Send my details and Send request. New or changed store labels: Account settings; No-source message; Hand-over message; Inbox; Settings; Hand-over; Lead draft; First name; Last name; Notes; Title; Time zone. These standard field words may already occur elsewhere; their newly added use still awaits approval. Approval metadata: Changed after approval, awaiting founder; Approved 3 Nov.

The complete visible widget wording/slot inventory below includes retained words as well, so no new visitor wording is omitted:

- Bot
- Chat is offline.
- Connecting you to a person
- Contact
- Details sent
- Email
- First name
- Last name
- Leave details
- Leave your details
- Message
- Notes
- Outside opening hours
- Pending
- Person
- Phone
- Privacy notice — awaiting founder decision
- Product
- Quantity
- Request a quote
- Request sent
- Send
- Send my details
- Send request
- Sources
- Start chat
- Talk to a person
- Title
- You
- Your request
- [Answer]
- [Client name]
- [Contact]
- [Email]
- [First name]
- [Greeting]
- [Last name]
- [Message]
- [New message]
- [No-source message]
- [Notes]
- [Person name] · [Person reply]
- [Phone]
- [Product]
- [Quantity]
- [Source domain]
- [Source title]
- [Title]
- [Visitor message]
- [Your request]
- ×
- —

Privacy notice wording is intentionally absent. The visible awaiting founder decision marker identifies that unresolved slot.

## Data and engine contract

Answers may use only the active client's allowed catalogue, FAQs and documents, and each source must belong to that same client. No-source messages lead to the configured hand-over route. Do not infer sources for visitor or human messages. The proposed plain slots map to the existing lead/quote fields; they are not claimed deployed chat API paths.

Chatwoot is the existing/free inbox and widget engine from the brief, subject to the founder's adapter/branding decision. This design adds no backend, data write, deployment or model API call. Structure and authoring screenshot checks validate the proposal; the founder's visual acceptance is required before build.


## Authoring verification · 3 November

Menu destinations were checked on both pages, including both mobile drawers and the new Google posts and Post detail entries. Same-page destinations navigate in the prototype; cross-page entries link to the corresponding Figma frame. Schedule confirmation returns to the approved Composer. Drawer scroll content ends with 16px clearance above the 240px-wide pinned block when scrolled to the end.

Commands run in `/workspace/codex-crm-marketing-chat-design`: `git fetch origin` (passed); `git diff --check` (passed); `git status --short` (only these two SPEC documents); `git push origin codex/crm-marketing-chat-design` (passed after each documentation commit). Figma checks inspected frame bounds, field sets, prototype destinations and mirrored SPEC text. Authoring screenshots covered Channels 375, Google posts 1440, calendar 1440, review detail 1440, approved Composer 375, lead form 375, Answer and Sending. These are authoring checks, not screenshots of a founder acceptance test. Founder browser acceptance remains outstanding.

Shared changed controls: action family `266:3038` (primary `266:3032`, secondary `266:3034`, destructive `266:3036`); navigation family `266:3212` (desktop `266:3039`, mobile `266:3125`). Component variant words Primary, Secondary and Destructive are design metadata. The complete changed screen node register is above; original root IDs are retained. Approval captions are outside product screens.
