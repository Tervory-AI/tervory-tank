# Chat bot · design proposal

## Founder review corrections · 1 November 2026, 17:20

This section controls the current canvas and supersedes earlier raw-label, mobile-table and on-page-history descriptions. Every visible field label uses plain wording. All wording in the mapping below is **draft for founder approval**. API field names and paths remain documentation only; no API property or endpoint was renamed. Every original screen ID, field node and confirmation step remains.

The visible navigation labels are **Write** and **Voice**. The client switcher uses the draft placeholder **Client**. Zero values use the existing em dash. Filled values are plain-word design annotations such as **[Invoice number]**, **[Client]** and **[Status]**, never raw API paths or invented client records. They show which data belongs in each slot; they are not live facts. This replaces the former raw bracketed API annotations throughout all 180 Trigger founder/store screens.

At 375px, each CRM record is one 76px two-line card. The first line contains the identifier and party; the second contains an amount/date and status. The original card click opens the corresponding full detail screen. Additional list fields remain preserved in hidden card layers; full fields remain visible on detail screens. Missing summary slots are linked copies of existing detail field components, never fabricated data fields. Zero lists remain empty.

| Area | Line 1: identifier; party | Line 2: amount/date; status |
|---|---|---|
| Leads | First name + Last name; Company | Next follow-up; Status |
| Accounts | Reference; Name | Created; Active |
| Contacts | First name + Last name; Company | Created; Do not call |
| Opportunities | Name; Client | Amount; Stage |
| Cases | Name; Client | First reply due; Status |
| Tasks | Title; Client | Due date; Status |
| Invoices | Invoice number; Client | Total; Status |
| Quotes | Quote number; Client | Total; Status |
| Google Business Profile posts | Post; Profile | Published at; Status |
| Chat bot inbox | Visitor; Assigned person | Updated at; Status |

Contacts use their existing Do not call flag as the contact state; no unsupported generic status was invented. Mobile posts and inbox use the same two-line card layout, with their retained fields on Post detail / Conversation detail. Channels use an 88px two-line connection card on mobile: channel/account, then status and the one state-dependent button.

Channels no longer has the Connected / Needs reconnecting / Off legend below the title. Desktop rows remain 64px high. Account is narrowed to 390px; Status is widened to 362px. The same one-button state rule and disconnect confirmation remain.

Visible canvas SPEC frames: CRM `101:8244`, Marketing `210:2897`, Chat bot `210:6156`. Marketing and Chat bot are actual FRAME nodes, each with an editable, complete canvas rendering of the matching Markdown and its preserved native SPEC document (`151:3973` / `154:4349`). CRM native SPEC remains `192:10312`. The canvas rendering is generated from the native Markdown source, not maintained as a separate document. These documentation frames are outside product viewports; screen indexes and API names occur here only.

The two old Workspace menu specimens `93:14` and `99:8146` were moved, with IDs preserved, from CRM to **Archive · Trigger design history**, page `208:11727`. They are no longer hidden clutter on page `93:2`.

### Complete new draft label mapping

All new labels below await founder wording approval. Entries with the same label retain distinct underlying API fields; the API identity belongs in this SPEC only.

| API field / previous wording | Draft visible label |
|---|---|
| `accepted_at` | Accepted |
| `accepted_by_email` | Acceptance email |
| `accepted_by_name` | Accepted by |
| `accepted_ip` | Acceptance IP address |
| `accepted_user_agent` | Acceptance browser |
| `account` | Client |
| `account_detail` | Client details |
| `account_name` | Client |
| `address_line` | Address line |
| `aging_status` | Age status |
| `amount` | Amount |
| `amount_due` | Amount due |
| `amount_paid` | Amount paid |
| `amount_source` | Amount source |
| `annual_revenue` | Annual revenue |
| `assigned_to` | Assigned to |
| `billing_address_line` | Billing address line |
| `billing_city` | Billing city |
| `billing_country` | Billing country |
| `billing_period` | Billing period |
| `billing_postcode` | Billing postcode |
| `billing_state` | Billing state or region |
| `case` | Case |
| `case_type` | Case type |
| `cases` | Cases |
| `child_count` | Related case count |
| `city` | City |
| `client_address_line` | Client address line |
| `client_city` | Client city |
| `client_country` | Client country |
| `client_email` | Client email |
| `client_name` | Client |
| `client_phone` | Client phone |
| `client_postcode` | Client postcode |
| `client_state` | Client state or region |
| `close_date` | Close date |
| `closed_by` | Closed by |
| `closed_on` | Closed |
| `company_name` | Company |
| `contact` | Contact |
| `contact_name` | Contact |
| `contacts` | Contacts |
| `converted_to_invoice` | Converted invoice |
| `country` | Country |
| `country_display` | Country |
| `created_at` | Created |
| `created_by` | Created by |
| `created_on_arrow` | Created |
| `currency` | Currency |
| `custom_fields` | Additional fields |
| `days_in_stage` | Days in stage |
| `declined_at` | Declined |
| `department` | Department |
| `deposit` | Deposit |
| `deposit_invoice` | Deposit invoice |
| `deposit_percent` | Deposit percentage |
| `description` | Description |
| `details` | Details |
| `discount_amount` | Discount amount |
| `discount_type` | Discount type |
| `discount_value` | Discount value |
| `do_not_call` | Do not call |
| `Draft estimate` | Draft quote |
| `due_date` | Due date |
| `email` | Email |
| `escalation_count` | Escalations |
| `estimate_number` | Quote number |
| `expiry_date` | Expiry date |
| `external_id` | External reference |
| `external_source` | External source |
| `first_name` | First name |
| `first_response_at` | First reply |
| `first_response_by` | First replied by |
| `first_response_by_details` | First responder details |
| `first_response_sla_deadline` | First reply due |
| `id` | Reference |
| `industry` | Industry |
| `introduction` | Introduction |
| `invoice_number` | Invoice number |
| `invoice_title` | Title |
| `is_active` | Active |
| `is_expired` | Expired |
| `is_overdue` | Overdue |
| `is_problem` | Problem |
| `is_sla_first_response_at_risk` | First reply at risk |
| `is_sla_first_response_breached` | First reply overdue |
| `is_sla_resolution_at_risk` | Resolution at risk |
| `is_sla_resolution_breached` | Resolution overdue |
| `is_unanswered` | Awaiting reply |
| `issue_date` | Issue date |
| `job_title` | Job title |
| `kanban_order` | Board order |
| `last_contacted` | Last contacted |
| `last_enquiry_at` | Last enquiry |
| `last_escalation_fired_at` | Last escalated |
| `last_name` | Last name |
| `last_outbound_at` | Last message sent |
| `last_reminder_sent` | Last reminder |
| `lead` | Lead |
| `lead_source` | Lead source |
| `line_items` | Items |
| `line_items_count` | Item count |
| `line_items_total` | Items total |
| `linked_accounts` | Linked clients |
| `linkedin_url` | LinkedIn profile |
| `name` | Name |
| `next_follow_up` | Next follow-up |
| `notes` | Notes |
| `number_of_employees` | Employee count |
| `opportunities` | Opportunities |
| `opportunity` | Opportunity |
| `opportunity_amount` | Potential value |
| `opportunity_type` | Opportunity type |
| `org` | Organisation |
| `organization` | Company |
| `paid_at` | Paid |
| `parent` | Parent case |
| `parent_summary` | Parent case summary |
| `payment_date` | Payment date |
| `payment_method` | Payment method |
| `payment_terms` | Payment terms |
| `payments` | Payments |
| `phone` | Phone |
| `phone_e164` | International phone number |
| `pipeline` | Pipeline |
| `po_number` | Purchase order number |
| `postcode` | Postcode |
| `priority` | Priority |
| `probability` | Probability |
| `project` | Project |
| `project_billing_type` | Project billing |
| `quantity` | Quantity |
| `rating` | Rating |
| `reference_number` | Reference number |
| `reminder_count` | Reminder count |
| `reminder_days_after` | Remind days after due |
| `reminder_days_before` | Remind days before due |
| `reminder_enabled` | Reminders on |
| `reminder_frequency` | Reminder interval |
| `resolution_sla_deadline` | Resolution due |
| `resolved_at` | Resolved |
| `rollups` | Related totals |
| `salutation` | Salutation |
| `sent_at` | Sent |
| `shipping_amount` | Shipping amount |
| `sla_first_response_hours` | First reply target in hours |
| `sla_paused_at` | Response target paused |
| `sla_resolution_hours` | Resolution target in hours |
| `source` | Source |
| `source_detail` | Source details |
| `source_ref` | Source reference |
| `stage` | Stage |
| `stage_changed_at` | Stage changed |
| `stage_kind` | Stage type |
| `stage_label` | Stage |
| `start_project` | Start project |
| `state` | State or region |
| `status` | Status |
| `subtotal` | Subtotal |
| `tags` | Tags |
| `tasks` | Tasks |
| `tax_amount` | Tax amount |
| `tax_rate` | Tax rate |
| `teams` | Teams |
| `template` | Template |
| `terms` | Terms |
| `time_summary` | Time summary |
| `title` | Title |
| `total_amount` | Total |
| `unit_price` | Unit price |
| `updated_at` | Last updated |
| `updated_by` | Updated by |
| `viewed_at` | Viewed |
| `voice` | Voice |
| `waiting_since` | Waiting since |
| `website` | Website |
| `write` | Write |

### Review correction validation

Passed: all 180 original screen roots and all 2318 original field-value node IDs remain; all 64 confirmation screens retain wired Confirm and Cancel controls. Zero visible technical field syntax or lowercase Write/Voice errors was found. The 24 CRM Filled list cards and the two Filled post/inbox summaries have exactly two lines and a detail destination; Zero lists remain empty. Complete canvas SPEC text matches native Markdown. Screenshots checked: Invoices mobile list `97:7684`, Invoices desktop detail `97:8098`, Channels desktop `149:2696`, Channels mobile `149:3459`, mobile inbox `149:14641`, and the visible Marketing/Chat bot SPEC headings and body. Value wording intentionally changes to plain annotations; field identities and API contracts remain.

Authoring screenshots are design evidence, not founder acceptance screenshots. No application code, live data, model API, secrets, connection setup or deployment is part of this correction. The founder's own visual acceptance remains pending.

Commands for this review: `git fetch origin main codex/crm-marketing-chat-design`, `git diff --check`, followed separately for each finished SPEC file by `git add <file>`, `git commit` and `git push origin codex/crm-marketing-chat-design`. Fetch passed. Push results and final audit totals are recorded after the checks. Claude opens the PR; the founder merges.

## Trigger menu revision · founder 1 November 2026, 14:25

This revision supersedes the earlier Workspace/CRM submenu design and the pending Estimates rename. CRM is Trigger. Applied across all 180 founder/store screens: CRM 92 (64 entity screens plus 28 confirmations), Marketing 44 and Chat bot 44. Every original screen ID, field value node and confirmation step is retained.

One 240px left menu only. Top: the existing approved Tervory on-white logo, client switcher, then Trigger bound to `color/accent/trigger` (`VariableID:72:9815`). The source asset is `workspace/public/brand/tervory-logo-on-white.png`, image hash `f5ac182d72fee0efa7e44827420ee36fb292e8d9`; the white stamp is not used.

| Draft group | Areas in order |
|---|---|
| Writing | Write, Voice |
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

### Execution proof for the 14:25 revision

Final Figma structural audit: **180 screens, 90 desktop, 90 mobile, 64 confirmation roots, zero errors**. All 2318 baseline field-value IDs/texts survive. Confirm and Cancel remain wired on every confirmation. Original desktop confirmation roots were expanded from their former 560px dialogs to full 1440px Trigger screens; mobile remains 375px. An intermediate width-based classification was corrected to use the explicit Desktop/Mobile screen names, then the complete audit was repeated.

Native SPEC readbacks: CRM `192:10312` inside existing frame `101:8244`; Marketing `151:3973`; Chat bot `154:4349`. Markdown content matches the repository specifications, allowing native normalization of paragraph whitespace. Authoring screenshots reviewed: CRM desktop detail `94:1061`, Channels Filled `149:2696`, mobile drawer `153:4367`; earlier revision checks also covered lists, Composer and calendars. Founder test screenshots have not been supplied and are not claimed.

Commands run for this revision in the private checkout:

```sh
git fetch origin main codex/crm-marketing-chat-design codex/crm-design
git show origin/codex/crm-design:docs/figma/crm/SPEC.md
git diff --check
git add docs/figma/crm/MARKETING-SPEC.md
git commit -m 'Apply founder single Trigger menu and Marketing reflow specification'
git push origin codex/crm-marketing-chat-design
git add docs/figma/crm/CHATBOT-SPEC.md
git commit -m 'Document shared Trigger navigation and Chat bot reflow'
git push origin codex/crm-marketing-chat-design
git add docs/figma/crm/SPEC.md
git commit -m 'Carry forward CRM schema and IDs with founder Trigger menu revision'
git push origin codex/crm-marketing-chat-design
```

Results: fetch/source read/whitespace check passed; commits `5d21bb16`, `684b13bf`, `c2bb1c5d` pushed successfully. Figma structural checks used deterministic node traversal and native SPEC readback, without model API calls. Intermediate authoring API errors (unsupported native SPEC geometry/visibility and code-size limits) were corrected before readback; no failed operation is counted as completed. Local temporary-file quota errors were handled in private checkout scratch storage. No fetch, push or required-source read failed. Final proof updates are committed and pushed separately for each specification. Claude opens the PR; founder review and merging remain with the founder.

DRAFT — founder approval pending. Design only; no bot, live connection, lead or quote was created.

Figma file: [Tervory designs](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=148-10). Page **5 · Chat bot**, ID `148:10`. Branch `codex/crm-marketing-chat-design`.

## Authority, appearance and scope

Founder pasted brief, 1 November 2026; existing CRM page `93:2` and `origin/codex/crm-design:docs/figma/crm/SPEC.md`; `agents/trigger/README.md`; widget brand model from `agents/tisan/templates/next-site/app/tokens.css`. All newly drawn wording is draft wording for founder approval. Store-side screens are founder-only, like CRM; the website widget is the separate visitor-facing surface. No old rejected dashboard, client sidebar, signup or billing proposal is approved by this design job.

Store: existing CRM field/action components `93:6` and `93:4`, local variables and typography are reused. Trigger chrome and responsive layout follow the controlling revision above. Leads and Quotes receive drafts; underlying Estimate bindings remain unchanged.

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
- Quote request creates a **draft** in Quotes (BottleCRM Estimates) with contact, request, requested items and source conversation. Store confirmation is required before any quote is issued; no amount, price, payment, currency or invoice is invented. This design does not add payment or billing flows.
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
| Leads / Quotes (BottleCRM Estimates) draft records and confirmation | Existing BottleCRM and Tervory confirmation components | Verify adapter mapping and draft lifecycle; no new CRM implementation |
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

Initial creation audit (before the 14:25 reflow): Deterministic audit: 44 store screens, 42 widget screens, 260 store field-value instances; viewport errors 0, unbound solid widget fills 0, wrong widget font families 0. Store editable descendant types: FRAME=192, TEXT=832, INSTANCE=492. Visual composition checks include mobile sourced answer, mobile quote draft and desktop store transcript. Save draft actions were pinned in the footer so they remain visible while form content scrolls. No complete-UI raster was used; Figma authoring proof is not founder browser acceptance. Founder approval and final review remain pending. Current geometry and preservation evidence is recorded in the controlling revision above; descendant counts here are historical.

## Final handoff proof · 1 November 2026

Native Figma SPEC: `154:4349`. Draft close-control wording: **Close**; this also awaits approval. The controlling 14:25 revision above supersedes the earlier submenu and rename proof. Existing screen registers and confirmation IDs remain valid.

Mobile drawers now use the shared Trigger menu and a dismiss scrim within the same preserved root IDs. Content spacing uses existing space variables; original entity field nodes and values remain.

Final rendered-binding audit: 46 distinct label/binding pairs, zero wrong heading/body font families. Exact rendered field paths follow below. The arrays/dictionary paths in the conceptual field register describe the same proposed data contract; none is an assertion of an existing scheduler or Chatwoot API.

Commands run in `/workspace/codex-crm-marketing-chat-design` unless absolute paths are shown:

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-crm-marketing-chat-design
git fetch origin main codex/crm-design
git checkout -B codex/crm-marketing-chat-design origin/main
ls agents/trigger/README.md
git --no-pager show origin/codex/crm-design:docs/figma/crm/SPEC.md
git diff --check
git add docs/figma/crm/CHATBOT-SPEC.md
git commit -m 'Document Chat bot widget and store screens with draft approval gates'
git push origin codex/crm-marketing-chat-design
```

Results: clone/fetch/checkout/required source-file read succeeded; whitespace check passed; commits `e4f441ba` (Marketing) and `b285cce9` (Chat bot) pushed successfully. The first commit attempt lacked a local author identity and failed; the existing Codex identity from the prior CRM checkout was reused locally, then commit/push passed. A temporary helper write under `/tmp` failed with `Disk quota exceeded`; the authorized private checkout and its `.git` scratch area remained writable. No required source file, fetch or push failed. Figma API validation rejected intermediate type/scroll/reaction operations; the canvas was inspected after each failure, then targeted corrections were applied. No failed operation is counted as a completed screen. No application tests were run because no application code changed. No secrets or production data were read.

Figma authoring screenshots reviewed: sourced-answer widget `152:4231`, quote widget `152:4647`, conversation desktop `149:15281`, mobile drawer `153:4367`. These are design-review evidence, not founder acceptance screenshots. Separate reviewer chat was notified; review is not claimed complete. Claude opens the PR from this branch; the founder alone merges. Founder approval and his own Figma/browser review remain pending.

## Exact rendered binding register

| Draft field label | Rendered binding |
|---|---|
| Visitor | `[conversation.visitor]` |
| Last message | `[conversation.last_message]` |
| Status | `[conversation.status]` |
| Assigned person | `[conversation.assignee]` |
| Updated at | `[conversation.updated_at]` |
| Sources used | `[conversation.sources]` |
| Reply | `[reply.text]` |
| Message | `[conversation.messages.Visitor.text]` |
| Who answered | `[conversation.messages.Visitor.author]` |
| Sources | `[conversation.messages.Visitor.sources]` |
| Message | `[conversation.messages.Bot.text]` |
| Who answered | `[conversation.messages.Bot.author]` |
| Sources | `[conversation.messages.Bot.sources]` |
| Message | `[conversation.messages.Person.text]` |
| Who answered | `[conversation.messages.Person.author]` |
| Sources | `[conversation.messages.Person.sources]` |
| Conversation | `[handover.conversation]` |
| Person | `[handover.assignee]` |
| Reason | `[handover.reason]` |
| Availability | `[handover.availability]` |
| Draft status | `[lead.status]` |
| Name | `[lead.first_name]` |
| Last name | `[lead.last_name]` |
| Email | `[lead.email]` |
| Phone | `[lead.phone]` |
| Source conversation | `[lead.source_ref]` |
| Notes | `[lead.description]` |
| Draft status | `[estimate.status]` |
| Title | `[estimate.title]` |
| Contact | `[estimate.contact]` |
| Request | `[estimate.notes]` |
| Line items | `[estimate.line_items]` |
| Source conversation | `[estimate.custom_fields.source_conversation]` |
| Bot | `[bot.enabled]` |
| Opening hours | `[bot.opening_hours]` |
| Time zone | `[bot.time_zone]` |
| Greeting | `[bot.greeting]` |
| Catalogue | `[bot.sources.catalogue]` |
| FAQs | `[bot.sources.faqs]` |
| Documents | `[bot.sources.documents]` |
| Hand-over rules | `[bot.handover_rules]` |
| Conversation | `[conversation.id]` |
| Recipient | `[conversation.visitor]` |
| Draft lead | `[lead.id]` |
| Draft estimate | `[estimate.id]` |
| Sources | `[bot.sources]` |