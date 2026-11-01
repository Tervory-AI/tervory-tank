# Chat bot · design proposal

DRAFT — founder approval pending. Design only; no bot, live connection, lead or quote was created.

Figma file: [Tervory designs](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=148-10). Page **5 · Chat bot**, ID `148:10`. Branch `codex/crm-marketing-chat-design`.

## Authority, appearance and scope

Founder pasted brief, 1 November 2026; existing CRM page `93:2` and `origin/codex/crm-design:docs/figma/crm/SPEC.md`; `agents/trigger/README.md`; widget brand model from `agents/tisan/templates/next-site/app/tokens.css`. All newly drawn wording is draft wording for founder approval. Store-side screens are founder-only, like CRM; the website widget is the separate visitor-facing surface. No old rejected dashboard, client sidebar, signup or billing proposal is approved by this design job.

Store: exact CRM field/action/mobile components `93:6`, `93:4`, `93:9`, side menu item variants `43:409` / `43:421`, founder chrome, typography and CRM accent `VariableID:72:9823`. Desktop 1440×900 and mobile 375×812. Existing CRM entity screens are preserved. Leads and Estimates receive drafts; the Estimates menu has not been renamed.

Website widget: no Tervory logo, founder menu, CRM accent or internal development labels. Widget component set `152:3622` has 14 variants (7 views × Zero/Filled) and linked instances across 1440×900, 390×844 and additionally 375×812. Body uses Atkinson Hyperlegible and headings Literata, matching the existing Tisan template. Blank host area is not a fabricated client website. No client logo/name/content is invented.

## Store-side screen register

| Screen | Size | State | Figma ID |
|---|---|---|---|
| Conversations | Desktop | Zero | `149:13691` |
| Conversations | Desktop | Filled | `149:14042` |
| Conversations | Mobile | Zero | `149:14393` |
| Conversations | Mobile | Filled | `149:14641` |
| Conversation detail | Desktop | Zero | `149:14889` |
| Conversation detail | Desktop | Filled | `149:15281` |
| Conversation detail | Mobile | Zero | `149:15673` |
| Conversation detail | Mobile | Filled | `149:15962` |
| Hand-over | Desktop | Zero | `149:16251` |
| Hand-over | Desktop | Filled | `149:16604` |
| Hand-over | Mobile | Zero | `149:16957` |
| Hand-over | Mobile | Filled | `149:17207` |
| Lead draft | Desktop | Zero | `149:17457` |
| Lead draft | Desktop | Filled | `149:17814` |
| Lead draft | Mobile | Zero | `149:18171` |
| Lead draft | Mobile | Filled | `149:18425` |
| Quote draft | Desktop | Zero | `149:18679` |
| Quote draft | Desktop | Filled | `149:19033` |
| Quote draft | Mobile | Zero | `149:19387` |
| Quote draft | Mobile | Filled | `149:19638` |
| Bot settings | Desktop | Zero | `149:19889` |
| Bot settings | Desktop | Filled | `149:20253` |
| Bot settings | Mobile | Zero | `149:20617` |
| Bot settings | Mobile | Filled | `149:20878` |
| Confirm · Send reply | Desktop | Zero | `151:6994` |
| Confirm · Send reply | Desktop | Filled | `151:7330` |
| Confirm · Send reply | Mobile | Zero | `151:7666` |
| Confirm · Send reply | Mobile | Filled | `151:7899` |
| Confirm · Hand over | Desktop | Zero | `151:8132` |
| Confirm · Hand over | Desktop | Filled | `151:8468` |
| Confirm · Hand over | Mobile | Zero | `151:8804` |
| Confirm · Hand over | Mobile | Filled | `151:9037` |
| Confirm · Lead | Desktop | Zero | `151:9270` |
| Confirm · Lead | Desktop | Filled | `151:9612` |
| Confirm · Lead | Mobile | Zero | `151:9954` |
| Confirm · Lead | Mobile | Filled | `151:10193` |
| Confirm · Quote | Desktop | Zero | `151:10432` |
| Confirm · Quote | Desktop | Filled | `151:10771` |
| Confirm · Quote | Mobile | Zero | `151:11110` |
| Confirm · Quote | Mobile | Filled | `151:11346` |
| Confirm · Bot settings | Desktop | Zero | `151:11582` |
| Confirm · Bot settings | Desktop | Filled | `151:11924` |
| Confirm · Bot settings | Mobile | Zero | `151:12266` |
| Confirm · Bot settings | Mobile | Filled | `151:12505` |

Store entry flows start at Conversations desktop/mobile × Zero/Filled. Same-page CRM mobile drawers: `153:4367`, `153:4381`. Every side-effect button leads to its full-screen confirmation or draft first; no prototype interaction calls an API. Confirm and Cancel return to the originating view, not an asserted success state.

## Website widget screen register

| Widget view | Width | Data state | Figma ID |
|---|---|---|---|
| Widget · Closed | 1440 | Zero | `152:3879` |
| Widget · Closed | 1440 | Filled | `152:3882` |
| Widget · Closed | 390 | Zero | `152:3885` |
| Widget · Closed | 390 | Filled | `152:3888` |
| Widget · Closed | 375 | Zero | `152:3891` |
| Widget · Closed | 375 | Filled | `152:3894` |
| Widget · Open | 1440 | Zero | `152:3897` |
| Widget · Open | 1440 | Filled | `152:3913` |
| Widget · Open | 390 | Zero | `152:3929` |
| Widget · Open | 390 | Filled | `152:3945` |
| Widget · Open | 375 | Zero | `152:3961` |
| Widget · Open | 375 | Filled | `152:3977` |
| Widget · Conversation | 1440 | Zero | `152:3993` |
| Widget · Conversation | 1440 | Filled | `152:4019` |
| Widget · Conversation | 390 | Zero | `152:4046` |
| Widget · Conversation | 390 | Filled | `152:4072` |
| Widget · Conversation | 375 | Zero | `152:4099` |
| Widget · Conversation | 375 | Filled | `152:4125` |
| Widget · Answer | 1440 | Zero | `152:4152` |
| Widget · Answer | 1440 | Filled | `152:4178` |
| Widget · Answer | 390 | Zero | `152:4205` |
| Widget · Answer | 390 | Filled | `152:4231` |
| Widget · Answer | 375 | Zero | `152:4258` |
| Widget · Answer | 375 | Filled | `152:4284` |
| Widget · Hand-over | 1440 | Zero | `152:4311` |
| Widget · Hand-over | 1440 | Filled | `152:4328` |
| Widget · Hand-over | 390 | Zero | `152:4345` |
| Widget · Hand-over | 390 | Filled | `152:4362` |
| Widget · Hand-over | 375 | Zero | `152:4379` |
| Widget · Hand-over | 375 | Filled | `152:4396` |
| Widget · Lead | 1440 | Zero | `152:4413` |
| Widget · Lead | 1440 | Filled | `152:4438` |
| Widget · Lead | 390 | Zero | `152:4463` |
| Widget · Lead | 390 | Filled | `152:4488` |
| Widget · Lead | 375 | Zero | `152:4513` |
| Widget · Lead | 375 | Filled | `152:4538` |
| Widget · Quote | 1440 | Zero | `152:4563` |
| Widget · Quote | 1440 | Filled | `152:4591` |
| Widget · Quote | 390 | Zero | `152:4619` |
| Widget · Quote | 390 | Filled | `152:4647` |
| Widget · Quote | 375 | Zero | `152:4675` |
| Widget · Quote | 375 | Filled | `152:4703` |

Closed bubble opens chat; Start chat enters a conversation; Send advances the design to the answer state; Talk to a person opens Hand-over; Leave details and Request a quote open draft forms. Save draft controls represent future draft submission and person review only, not a confirmed lead, invoice or quote. This is not a working chat or data-write test. Both Zero and Filled remain explicitly design states.

## Proposed store-side field and action register

Binding paths below are a proposed interface contract, not claimed existing Chatwoot endpoints. Brackets are source bindings and never sample conversation data.

### Conversations

| Draft label | Binding |
|---|---|
| Visitor | `conversation.visitor` |
| Last message | `conversation.last_message` |
| Status | `conversation.status` |
| Assigned person | `conversation.assignee` |
| Updated at | `conversation.updated_at` |

Actions: Open conversation.

### Conversation detail

| Draft label | Binding |
|---|---|
| Visitor | `conversation.visitor` |
| Status | `conversation.status` |
| Assigned person | `conversation.assignee` |
| Sources used | `conversation.sources` |
| Reply | `reply.text` |

Actions: Hand over, Send reply, Draft lead, Draft quote.

### Hand-over

| Draft label | Binding |
|---|---|
| Conversation | `handover.conversation` |
| Person | `handover.assignee` |
| Reason | `handover.reason` |
| Availability | `handover.availability` |
| Reply | `reply.text` |

Actions: Confirm hand-over, Send reply.

### Lead draft

| Draft label | Binding |
|---|---|
| Draft status | `lead.status` |
| Name | `lead.first_name` |
| Last name | `lead.last_name` |
| Email | `lead.email` |
| Phone | `lead.phone` |
| Source conversation | `lead.source_ref` |
| Notes | `lead.description` |

Actions: Confirm lead.

### Quote draft

| Draft label | Binding |
|---|---|
| Draft status | `estimate.status` |
| Title | `estimate.title` |
| Contact | `estimate.contact` |
| Request | `estimate.notes` |
| Line items | `estimate.line_items` |
| Source conversation | `estimate.custom_fields.source_conversation` |

Actions: Confirm quote.

### Bot settings

| Draft label | Binding |
|---|---|
| Bot | `bot.enabled` |
| Opening hours | `bot.opening_hours` |
| Time zone | `bot.time_zone` |
| Greeting | `bot.greeting` |
| Catalogue | `bot.sources.catalogue` |
| FAQs | `bot.sources.faqs` |
| Documents | `bot.sources.documents` |
| Hand-over rules | `bot.handover_rules` |

Actions: On, Off, Save settings.

### Confirm · Send reply

| Draft label | Binding |
|---|---|
| Conversation | `conversation.id` |
| Recipient | `conversation.visitor` |
| Reply | `reply.text` |

Actions: Confirm, Cancel.

### Confirm · Hand over

| Draft label | Binding |
|---|---|
| Conversation | `conversation.id` |
| Person | `handover.assignee` |
| Reason | `handover.reason` |

Actions: Confirm, Cancel.

### Confirm · Lead

| Draft label | Binding |
|---|---|
| Draft lead | `lead.id` |
| Source conversation | `lead.source_ref` |
| Name | `lead.first_name` |
| Email | `lead.email` |
| Phone | `lead.phone` |

Actions: Confirm, Cancel.

### Confirm · Quote

| Draft label | Binding |
|---|---|
| Draft estimate | `estimate.id` |
| Contact | `estimate.contact` |
| Request | `estimate.notes` |
| Line items | `estimate.line_items` |

Actions: Confirm, Cancel.

### Confirm · Bot settings

| Draft label | Binding |
|---|---|
| Bot | `bot.enabled` |
| Opening hours | `bot.opening_hours` |
| Greeting | `bot.greeting` |
| Sources | `bot.sources` |
| Hand-over rules | `bot.handover_rules` |

Actions: Confirm, Cancel.

## Transcript fields

For each message: `conversation.messages[].text`, `.author`, `.role`, `.created_at`, `.sources[]`; source entries carry `.id`, `.title`, `.url`, `.client_id`, `.document_id` and `.page` where applicable. The store detail groups Visitor, Bot and Person with message, who answered and sources. Only relevant returned fields render; no source is invented for human/visitor messages. The source group is mandatory for every bot answer.

## Widget field register

| View | Every source field |
|---|---|
| Closed | Configuration: `bot.enabled`, client colour tokens; no visitor record |
| Open | `client.name`, `bot.greeting`, `bot.enabled` |
| Conversation / Answer | `visitor.message`, `client_data.answer`, `source.title`, `source.url`, `message.text` |
| Hand-over | `client.name`, `handover.status`, `person.display_name`, `person.reply`, `message.text` |
| Lead | `lead.name`, `lead.email`, `lead.phone`, `client.name`, source conversation identity |
| Quote | `quote.product`, `quote.quantity`, `quote.request`, `quote.contact`, `client.name`, source conversation identity |

Each answer is restricted to the active client's allowed catalogue, FAQs and documents. Its source link is taken from that exact source record. The Figma source button and `[source.url]` are source slots, not made-up URLs. With no eligible evidence, the future runtime must not produce an unsourced answer: use the configured hand-over route. No default claims, general-web answers, cross-client retrieval, model name or model-debug data is shown. Missing-source/blocked-answer wording remains a founder copy decision; none is presented as approved.

## Client brand token contract

Figma collection **Chat bot / Client brand · unconfigured**, mode **Awaiting client tokens**, uses only semantic client colour variables: accent `VariableID:152:3601`, ink `VariableID:152:3603`, paper `VariableID:152:3605`, line `VariableID:152:3607`. Their WEB names are `var(--colour-accent)`, `var(--colour-ink)`, `var(--colour-paper)`, `var(--colour-line)` from the Tisan template. Every solid widget fill is variable-bound. Neutral unconfigured grayscale is a design placeholder, not an invented client palette; before implementation the selected client's actual brand tokens must supply the values. No CRM colour is used inside the visitor widget. No client brand approval is claimed.

## Founder confirmation and draft lifecycle

- Lead capture creates a **draft** in Leads with source-conversation identity. Store confirmation reviews name/contact/details before activation. Do not treat visitor submission or a prototype click as store consent.
- Quote request creates a **draft** in Estimates with contact, request, requested items and source conversation. Store confirmation is required before any quote is issued; no amount, price, payment, currency or invoice is invented. This design does not add payment or billing flows.
- Send reply: review the exact conversation, recipient and outgoing text before confirmation; no reply is sent here.
- Hand over: review conversation/person/reason before confirmation. No fabricated staff roster or availability is supplied.
- Bot settings: review enabled state, opening hours/time zone, greeting, allowed source sets and hand-over rules before confirmation. On/Off/Save settings are draft controls only.
- Zero states cannot authorize operations without a real record. Confirmation controls have no live side effects. Request field/API mapping, draft persistence and activation semantics need the later implementation brief; no new CRM backend was built.

The current BottleCRM Lead/Estimate schema is reused for named CRM fields where present; conversation linkage/draft-review metadata is proposed and is not falsely represented as an already deployed connector. No public accept/decline link or client CRM portal is added.

## Engine decisions for the founder — not a selection made here

| Feature | Existing/free engine | Founder decision |
|---|---|---|
| Website widget, conversation list/detail, human inbox/handover | Chatwoot, already on Boston per the founder brief | Reuse existing deployment; exact supported widget/inbox API and branding contract need verification before implementation; this design did not inspect secrets or deploy it |
| Catalogue/FAQ/document source restriction and source links | Existing client-scoped data/retrieval and Chatwoot message metadata | Verify actual source mapping; never recode an available engine or let Chatwoot itself imply retrieval exists |
| Leads / Estimates draft records and confirmation | Existing BottleCRM and Tervory confirmation components | Verify adapter mapping and draft lifecycle; no new CRM implementation |
| Settings | Existing widget/inbox configuration where supported | Reuse supported settings; no settings were changed |

No model calls were used for drafting or checking this design. Future answering must follow the existing product architecture; it is not implemented or enabled by these frames.

## Every new store-side wording string awaiting approval

- Assigned person
- Availability
- Bot
- Bot settings
- Cancel
- Catalogue
- Confirm
- Confirm hand-over
- Confirm lead
- Confirm quote
- Confirm · Bot settings
- Confirm · Hand over
- Confirm · Lead
- Confirm · Quote
- Confirm · Send reply
- Contact
- Conversation
- Conversation detail
- Conversations
- Documents
- Draft estimate
- Draft lead
- Draft quote
- Draft status
- Email
- FAQs
- Greeting
- Hand over
- Hand-over
- Hand-over rules
- Last message
- Last name
- Lead draft
- Line items
- Message
- Name
- Notes
- Nothing runs until you confirm.
- Off
- On
- Open conversation
- Opening hours
- Person
- Phone
- Quote draft
- Reason
- Recipient
- Reply
- Request
- Save settings
- Send reply
- Source conversation
- Sources
- Sources used
- Status
- Time zone
- Title
- Transcript
- Updated at
- Visitor
- Who answered

## Every new visitor wording string awaiting approval

- Answer
- Chat
- Close
- Contact
- Email
- Hand-over
- Leave details
- Leave your details
- Message
- Name
- Phone
- Product
- Quantity
- Request a quote
- Save lead draft
- Save quote draft
- Send
- Sources
- Start chat
- Talk to a person
- You
- Your request

All greetings, client identities, visitor/bot/person messages, review states, source titles and record values remain dynamic bindings. No canned answer, fake client story, example lead or fabricated product is present. Existing founder chrome wording is reused as requested and is not a new client-menu approval.

## Validation and evidence

Deterministic audit: 44 store screens, 42 widget screens, 260 store field-value instances; viewport errors 0, unbound solid widget fills 0, wrong widget font families 0. Store editable descendant types: FRAME=192, TEXT=832, INSTANCE=492. Visual composition checks include mobile sourced answer, mobile quote draft and desktop store transcript. Save draft actions were pinned in the footer so they remain visible while form content scrolls. No complete-UI raster was used; Figma authoring proof is not founder browser acceptance. Founder approval and final review remain pending.

