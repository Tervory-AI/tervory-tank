# Trigger CRM design

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

Status: founder 1 November 14:25 Trigger navigation revision applied; founder acceptance and draft group wording approval remain pending.
Branch: `codex/crm-marketing-chat-design`. Claude opens the PR. No application code or live data changed.

Figma: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=93-2
Page: **2 · CRM** (`93:2`), founder only. CRM SPEC frame: **`101:8244`**. Existing Case studies page: `42:2`; revision 3 SPEC: `63:10450`.

## Contract and design rules

Sources: `ops/trigger-crm/openapi-cd7c12a.yml` (BottleCRM cd7c12a), `docs/figma/crm/INVOICES-ESTIMATES.md`, `docs/figma/case-studies/SPEC.md` and `workspace/app/product-nav.ts`.

CRM and Sales areas use the single Trigger menu above. Quotes and Invoices remain separate despite their shared BottleCRM API prefix. Existing field/control components and typography are reused.

Desktop viewports are 1440 × 900. Mobile viewports are 375 × 812. Detail fields scroll vertically. Desktop lists scroll horizontally to retain exact schema labels. Mobile lists use the first five listed columns; the full record is available in detail. Zero lists have no rows or invented empty-state wording. Zero detail fields show the existing em-dash convention. Filled values such as `[first_name]` are schema-binding annotations in Figma, never sample client records or live data. They must be replaced with tenant-scoped API values at implementation time.

No public client routes or links. `public_token` and `public_url` are not displayed. `public_link_enabled` stays false and is not an editable control. `is_sample` is not displayed. Record money uses its own `currency`, without conversion. API metadata is documented here, not added as product copy.

## Screen register

64 entity screens are present (8 sections × list/detail × desktop/mobile × Zero/Filled), plus the 28 confirmation roots listed below: 92 CRM roots in this revision.

| Section | View | Size | State | Node ID |
|---|---|---|---|---|
| Leads | List | Desktop | Zero | 94:172 |
| Leads | List | Desktop | Filled | 94:417 |
| Leads | List | Mobile | Zero | 94:671 |
| Leads | List | Mobile | Filled | 94:682 |
| Leads | Detail | Desktop | Zero | 94:741 |
| Leads | Detail | Desktop | Filled | 94:1061 |
| Leads | Detail | Mobile | Zero | 94:1384 |
| Leads | Detail | Mobile | Filled | 94:1596 |
| Accounts | List | Desktop | Zero | 94:1811 |
| Accounts | List | Desktop | Filled | 94:1978 |
| Accounts | List | Mobile | Zero | 94:2193 |
| Accounts | List | Mobile | Filled | 94:2204 |
| Accounts | Detail | Desktop | Zero | 94:2263 |
| Accounts | Detail | Desktop | Filled | 94:2510 |
| Accounts | Detail | Mobile | Zero | 94:2760 |
| Accounts | Detail | Mobile | Filled | 94:2888 |
| Contacts | List | Desktop | Zero | 97:2074 |
| Contacts | List | Desktop | Filled | 97:2245 |
| Contacts | List | Mobile | Zero | 97:2473 |
| Contacts | List | Mobile | Filled | 97:2484 |
| Contacts | Detail | Desktop | Zero | 97:2543 |
| Contacts | Detail | Desktop | Filled | 97:2800 |
| Contacts | Detail | Mobile | Zero | 97:3060 |
| Contacts | Detail | Mobile | Filled | 97:3200 |
| Opportunities | List | Desktop | Zero | 97:3343 |
| Opportunities | List | Desktop | Filled | 97:3522 |
| Opportunities | List | Mobile | Zero | 97:3776 |
| Opportunities | List | Mobile | Filled | 97:3787 |
| Opportunities | Detail | Desktop | Zero | 97:3846 |
| Opportunities | Detail | Desktop | Filled | 97:4107 |
| Opportunities | Detail | Mobile | Zero | 97:4371 |
| Opportunities | Detail | Mobile | Filled | 97:4515 |
| Cases | List | Desktop | Zero | 97:4662 |
| Cases | List | Desktop | Filled | 97:4837 |
| Cases | List | Mobile | Zero | 97:5078 |
| Cases | List | Mobile | Filled | 97:5089 |
| Cases | Detail | Desktop | Zero | 97:5148 |
| Cases | Detail | Desktop | Filled | 97:5416 |
| Cases | Detail | Mobile | Zero | 97:5687 |
| Cases | Detail | Mobile | Filled | 97:5839 |
| Tasks | List | Desktop | Zero | 97:5994 |
| Tasks | List | Desktop | Filled | 97:6165 |
| Tasks | List | Mobile | Zero | 97:6393 |
| Tasks | List | Mobile | Filled | 97:6404 |
| Tasks | Detail | Desktop | Zero | 97:6463 |
| Tasks | Detail | Desktop | Filled | 97:6671 |
| Tasks | Detail | Mobile | Zero | 97:6882 |
| Tasks | Detail | Mobile | Filled | 97:6966 |
| Invoices | List | Desktop | Zero | 97:7053 |
| Invoices | List | Desktop | Filled | 97:7276 |
| Invoices | List | Mobile | Zero | 97:7673 |
| Invoices | List | Mobile | Filled | 97:7684 |
| Invoices | Detail | Desktop | Zero | 97:7743 |
| Invoices | Detail | Desktop | Filled | 97:8098 |
| Invoices | Detail | Mobile | Zero | 97:8464 |
| Invoices | Detail | Mobile | Filled | 97:8716 |
| Quotes | List | Desktop | Zero | 97:8979 |
| Quotes | List | Desktop | Filled | 97:9218 |
| Quotes | List | Mobile | Zero | 97:9667 |
| Quotes | List | Mobile | Filled | 97:9678 |
| Quotes | Detail | Desktop | Zero | 97:9737 |
| Quotes | Detail | Desktop | Filled | 97:10064 |
| Quotes | Detail | Mobile | Zero | 97:10398 |
| Quotes | Detail | Mobile | Filled | 97:10618 |

## Field and API register

Every field below is an exact schema property. `[]` denotes an array element. Fields not selected as list columns remain available on the detail record where present. Envelope metadata and nested objects are retained as structured data; no inferred labels are substituted.

### Leads

List: GET `/api/leads/`, schema `Lead`, record path `open_leads.open_leads[]`.
Detail: GET `/api/leads/{id}/`, schema `Lead`, record path `lead_obj`.

| Field | List response path | Detail response path |
|---|---|---|
| `id` | `open_leads.open_leads[].id` | `lead_obj.id` |
| `title` | `open_leads.open_leads[].title` | `lead_obj.title` |
| `salutation` | `open_leads.open_leads[].salutation` | `lead_obj.salutation` |
| `first_name` | `open_leads.open_leads[].first_name` | `lead_obj.first_name` |
| `last_name` | `open_leads.open_leads[].last_name` | `lead_obj.last_name` |
| `email` | `open_leads.open_leads[].email` | `lead_obj.email` |
| `phone` | `open_leads.open_leads[].phone` | `lead_obj.phone` |
| `job_title` | `open_leads.open_leads[].job_title` | `lead_obj.job_title` |
| `website` | `open_leads.open_leads[].website` | `lead_obj.website` |
| `linkedin_url` | `open_leads.open_leads[].linkedin_url` | `lead_obj.linkedin_url` |
| `status` | `open_leads.open_leads[].status` | `lead_obj.status` |
| `source` | `open_leads.open_leads[].source` | `lead_obj.source` |
| `source_detail` | `open_leads.open_leads[].source_detail` | `lead_obj.source_detail` |
| `source_ref` | `open_leads.open_leads[].source_ref` | `lead_obj.source_ref` |
| `industry` | `open_leads.open_leads[].industry` | `lead_obj.industry` |
| `rating` | `open_leads.open_leads[].rating` | `lead_obj.rating` |
| `opportunity_amount` | `open_leads.open_leads[].opportunity_amount` | `lead_obj.opportunity_amount` |
| `currency` | `open_leads.open_leads[].currency` | `lead_obj.currency` |
| `probability` | `open_leads.open_leads[].probability` | `lead_obj.probability` |
| `close_date` | `open_leads.open_leads[].close_date` | `lead_obj.close_date` |
| `address_line` | `open_leads.open_leads[].address_line` | `lead_obj.address_line` |
| `city` | `open_leads.open_leads[].city` | `lead_obj.city` |
| `state` | `open_leads.open_leads[].state` | `lead_obj.state` |
| `postcode` | `open_leads.open_leads[].postcode` | `lead_obj.postcode` |
| `country` | `open_leads.open_leads[].country` | `lead_obj.country` |
| `assigned_to` | `open_leads.open_leads[].assigned_to` | `lead_obj.assigned_to` |
| `teams` | `open_leads.open_leads[].teams` | `lead_obj.teams` |
| `last_contacted` | `open_leads.open_leads[].last_contacted` | `lead_obj.last_contacted` |
| `next_follow_up` | `open_leads.open_leads[].next_follow_up` | `lead_obj.next_follow_up` |
| `description` | `open_leads.open_leads[].description` | `lead_obj.description` |
| `contacts` | `open_leads.open_leads[].contacts` | `lead_obj.contacts` |
| `tags` | `open_leads.open_leads[].tags` | `lead_obj.tags` |
| `created_by` | `open_leads.open_leads[].created_by` | `lead_obj.created_by` |
| `created_at` | `open_leads.open_leads[].created_at` | `lead_obj.created_at` |
| `updated_at` | `open_leads.open_leads[].updated_at` | `lead_obj.updated_at` |
| `is_active` | `open_leads.open_leads[].is_active` | `lead_obj.is_active` |
| `company_name` | `open_leads.open_leads[].company_name` | `lead_obj.company_name` |
| `stage` | `open_leads.open_leads[].stage` | `lead_obj.stage` |
| `kanban_order` | `open_leads.open_leads[].kanban_order` | `lead_obj.kanban_order` |
| `custom_fields` | `open_leads.open_leads[].custom_fields` | `lead_obj.custom_fields` |
| `phone_e164` | `open_leads.open_leads[].phone_e164` | `lead_obj.phone_e164` |
| `external_source` | `open_leads.open_leads[].external_source` | `lead_obj.external_source` |
| `external_id` | `open_leads.open_leads[].external_id` | `lead_obj.external_id` |
| `last_enquiry_at` | `open_leads.open_leads[].last_enquiry_at` | `lead_obj.last_enquiry_at` |
| `first_response_at` | `open_leads.open_leads[].first_response_at` | `lead_obj.first_response_at` |
| `first_response_by` | `open_leads.open_leads[].first_response_by` | `lead_obj.first_response_by` |
| `first_response_by_details` | `open_leads.open_leads[].first_response_by_details` | `lead_obj.first_response_by_details` |
| `last_outbound_at` | `open_leads.open_leads[].last_outbound_at` | `lead_obj.last_outbound_at` |
| `waiting_since` | `open_leads.open_leads[].waiting_since` | `lead_obj.waiting_since` |
| `is_unanswered` | `open_leads.open_leads[].is_unanswered` | `lead_obj.is_unanswered` |
| `is_sample` | — | `lead_obj.is_sample` (hidden; policy above) |

### Accounts

List: GET `/api/accounts/`, schema `Account`, record path `active_accounts.open_accounts[]`.
Detail: GET `/api/accounts/{id}/`, schema `AccountWithRelated`, record path `account_obj`.

| Field | List response path | Detail response path |
|---|---|---|
| `id` | `active_accounts.open_accounts[].id` | `account_obj.id` |
| `name` | `active_accounts.open_accounts[].name` | `account_obj.name` |
| `email` | `active_accounts.open_accounts[].email` | `account_obj.email` |
| `phone` | `active_accounts.open_accounts[].phone` | `account_obj.phone` |
| `website` | `active_accounts.open_accounts[].website` | `account_obj.website` |
| `industry` | `active_accounts.open_accounts[].industry` | `account_obj.industry` |
| `number_of_employees` | `active_accounts.open_accounts[].number_of_employees` | `account_obj.number_of_employees` |
| `annual_revenue` | `active_accounts.open_accounts[].annual_revenue` | `account_obj.annual_revenue` |
| `currency` | `active_accounts.open_accounts[].currency` | `account_obj.currency` |
| `address_line` | `active_accounts.open_accounts[].address_line` | `account_obj.address_line` |
| `city` | `active_accounts.open_accounts[].city` | `account_obj.city` |
| `state` | `active_accounts.open_accounts[].state` | `account_obj.state` |
| `postcode` | `active_accounts.open_accounts[].postcode` | `account_obj.postcode` |
| `country` | `active_accounts.open_accounts[].country` | `account_obj.country` |
| `country_display` | `active_accounts.open_accounts[].country_display` | `account_obj.country_display` |
| `assigned_to` | `active_accounts.open_accounts[].assigned_to` | `account_obj.assigned_to` |
| `teams` | `active_accounts.open_accounts[].teams` | `account_obj.teams` |
| `tags` | `active_accounts.open_accounts[].tags` | `account_obj.tags` |
| `description` | `active_accounts.open_accounts[].description` | `account_obj.description` |
| `rollups` | `active_accounts.open_accounts[].rollups` | `account_obj.rollups` |
| `created_by` | `active_accounts.open_accounts[].created_by` | `account_obj.created_by` |
| `created_at` | `active_accounts.open_accounts[].created_at` | `account_obj.created_at` |
| `is_active` | `active_accounts.open_accounts[].is_active` | `account_obj.is_active` |
| `org` | `active_accounts.open_accounts[].org` | `account_obj.org` |
| `custom_fields` | `active_accounts.open_accounts[].custom_fields` | `account_obj.custom_fields` |
| `contacts` | — | `account_obj.contacts` |
| `cases` | — | `account_obj.cases` |
| `tasks` | — | `account_obj.tasks` |
| `opportunities` | — | `account_obj.opportunities` |

### Contacts

List: GET `/api/contacts/`, schema `Contact`, record path `results[]`.
Detail: GET `/api/contacts/{id}/`, schema `Contact`, record path `contact_obj`.

| Field | List response path | Detail response path |
|---|---|---|
| `id` | `results[].id` | `contact_obj.id` |
| `first_name` | `results[].first_name` | `contact_obj.first_name` |
| `last_name` | `results[].last_name` | `contact_obj.last_name` |
| `email` | `results[].email` | `contact_obj.email` |
| `phone` | `results[].phone` | `contact_obj.phone` |
| `phone_e164` | `results[].phone_e164` | `contact_obj.phone_e164` |
| `source` | `results[].source` | `contact_obj.source` |
| `source_detail` | `results[].source_detail` | `contact_obj.source_detail` |
| `source_ref` | `results[].source_ref` | `contact_obj.source_ref` |
| `organization` | `results[].organization` | `contact_obj.organization` |
| `title` | `results[].title` | `contact_obj.title` |
| `department` | `results[].department` | `contact_obj.department` |
| `do_not_call` | `results[].do_not_call` | `contact_obj.do_not_call` |
| `linkedin_url` | `results[].linkedin_url` | `contact_obj.linkedin_url` |
| `address_line` | `results[].address_line` | `contact_obj.address_line` |
| `city` | `results[].city` | `contact_obj.city` |
| `state` | `results[].state` | `contact_obj.state` |
| `postcode` | `results[].postcode` | `contact_obj.postcode` |
| `country` | `results[].country` | `contact_obj.country` |
| `assigned_to` | `results[].assigned_to` | `contact_obj.assigned_to` |
| `teams` | `results[].teams` | `contact_obj.teams` |
| `tags` | `results[].tags` | `contact_obj.tags` |
| `description` | `results[].description` | `contact_obj.description` |
| `created_by` | `results[].created_by` | `contact_obj.created_by` |
| `created_at` | `results[].created_at` | `contact_obj.created_at` |
| `updated_at` | `results[].updated_at` | `contact_obj.updated_at` |
| `is_active` | `results[].is_active` | `contact_obj.is_active` |
| `org` | `results[].org` | `contact_obj.org` |
| `account` | `results[].account` | `contact_obj.account` |
| `account_detail` | `results[].account_detail` | `contact_obj.account_detail` |
| `linked_accounts` | `results[].linked_accounts` | `contact_obj.linked_accounts` |
| `custom_fields` | `results[].custom_fields` | `contact_obj.custom_fields` |

### Opportunities

List: GET `/api/opportunities/`, schema `OpportunityList`, record path `opportunities[]`.
Detail: GET `/api/opportunities/{id}/`, schema `Opportunity`, record path `opportunity_obj`.

| Field | List response path | Detail response path |
|---|---|---|
| `id` | `opportunities[].id` | `opportunity_obj.id` |
| `name` | `opportunities[].name` | `opportunity_obj.name` |
| `account` | `opportunities[].account` | `opportunity_obj.account` |
| `pipeline` | `opportunities[].pipeline` | `opportunity_obj.pipeline` |
| `stage` | `opportunities[].stage` | `opportunity_obj.stage` |
| `stage_label` | `opportunities[].stage_label` | `opportunity_obj.stage_label` |
| `stage_kind` | `opportunities[].stage_kind` | `opportunity_obj.stage_kind` |
| `opportunity_type` | `opportunities[].opportunity_type` | `opportunity_obj.opportunity_type` |
| `currency` | `opportunities[].currency` | `opportunity_obj.currency` |
| `amount` | `opportunities[].amount` | `opportunity_obj.amount` |
| `amount_source` | `opportunities[].amount_source` | `opportunity_obj.amount_source` |
| `probability` | `opportunities[].probability` | `opportunity_obj.probability` |
| `closed_on` | `opportunities[].closed_on` | `opportunity_obj.closed_on` |
| `lead_source` | `opportunities[].lead_source` | `opportunity_obj.lead_source` |
| `source_detail` | `opportunities[].source_detail` | `opportunity_obj.source_detail` |
| `source_ref` | `opportunities[].source_ref` | `opportunity_obj.source_ref` |
| `contacts` | `opportunities[].contacts` | `opportunity_obj.contacts` |
| `line_items` | `opportunities[].line_items` | `opportunity_obj.line_items` |
| `line_items_total` | `opportunities[].line_items_total` | `opportunity_obj.line_items_total` |
| `assigned_to` | `opportunities[].assigned_to` | `opportunity_obj.assigned_to` |
| `teams` | `opportunities[].teams` | `opportunity_obj.teams` |
| `closed_by` | `opportunities[].closed_by` | `opportunity_obj.closed_by` |
| `tags` | `opportunities[].tags` | `opportunity_obj.tags` |
| `description` | `opportunities[].description` | `opportunity_obj.description` |
| `created_by` | `opportunities[].created_by` | `opportunity_obj.created_by` |
| `created_at` | `opportunities[].created_at` | `opportunity_obj.created_at` |
| `is_active` | `opportunities[].is_active` | `opportunity_obj.is_active` |
| `org` | `opportunities[].org` | `opportunity_obj.org` |
| `created_on_arrow` | `opportunities[].created_on_arrow` | `opportunity_obj.created_on_arrow` |
| `stage_changed_at` | `opportunities[].stage_changed_at` | `opportunity_obj.stage_changed_at` |
| `days_in_stage` | `opportunities[].days_in_stage` | `opportunity_obj.days_in_stage` |
| `aging_status` | `opportunities[].aging_status` | `opportunity_obj.aging_status` |
| `custom_fields` | `opportunities[].custom_fields` | `opportunity_obj.custom_fields` |
| `next_activity` | `opportunities[].next_activity` | — |

### Cases

List: GET `/api/cases/`, schema `Case`, record path `cases[]`.
Detail: GET `/api/cases/{id}/`, schema `Case`, record path `cases_obj`.

| Field | List response path | Detail response path |
|---|---|---|
| `id` | `cases[].id` | `cases_obj.id` |
| `name` | `cases[].name` | `cases_obj.name` |
| `status` | `cases[].status` | `cases_obj.status` |
| `priority` | `cases[].priority` | `cases_obj.priority` |
| `case_type` | `cases[].case_type` | `cases_obj.case_type` |
| `closed_on` | `cases[].closed_on` | `cases_obj.closed_on` |
| `description` | `cases[].description` | `cases_obj.description` |
| `created_by` | `cases[].created_by` | `cases_obj.created_by` |
| `created_at` | `cases[].created_at` | `cases_obj.created_at` |
| `is_active` | `cases[].is_active` | `cases_obj.is_active` |
| `account` | `cases[].account` | `cases_obj.account` |
| `contacts` | `cases[].contacts` | `cases_obj.contacts` |
| `teams` | `cases[].teams` | `cases_obj.teams` |
| `assigned_to` | `cases[].assigned_to` | `cases_obj.assigned_to` |
| `tags` | `cases[].tags` | `cases_obj.tags` |
| `org` | `cases[].org` | `cases_obj.org` |
| `custom_fields` | `cases[].custom_fields` | `cases_obj.custom_fields` |
| `escalation_count` | `cases[].escalation_count` | `cases_obj.escalation_count` |
| `last_escalation_fired_at` | `cases[].last_escalation_fired_at` | `cases_obj.last_escalation_fired_at` |
| `sla_first_response_hours` | `cases[].sla_first_response_hours` | `cases_obj.sla_first_response_hours` |
| `sla_resolution_hours` | `cases[].sla_resolution_hours` | `cases_obj.sla_resolution_hours` |
| `first_response_at` | `cases[].first_response_at` | `cases_obj.first_response_at` |
| `resolved_at` | `cases[].resolved_at` | `cases_obj.resolved_at` |
| `sla_paused_at` | `cases[].sla_paused_at` | `cases_obj.sla_paused_at` |
| `first_response_sla_deadline` | `cases[].first_response_sla_deadline` | `cases_obj.first_response_sla_deadline` |
| `resolution_sla_deadline` | `cases[].resolution_sla_deadline` | `cases_obj.resolution_sla_deadline` |
| `is_sla_first_response_breached` | `cases[].is_sla_first_response_breached` | `cases_obj.is_sla_first_response_breached` |
| `is_sla_resolution_breached` | `cases[].is_sla_resolution_breached` | `cases_obj.is_sla_resolution_breached` |
| `is_sla_first_response_at_risk` | `cases[].is_sla_first_response_at_risk` | `cases_obj.is_sla_first_response_at_risk` |
| `is_sla_resolution_at_risk` | `cases[].is_sla_resolution_at_risk` | `cases_obj.is_sla_resolution_at_risk` |
| `parent` | `cases[].parent` | `cases_obj.parent` |
| `is_problem` | `cases[].is_problem` | `cases_obj.is_problem` |
| `parent_summary` | `cases[].parent_summary` | `cases_obj.parent_summary` |
| `child_count` | `cases[].child_count` | `cases_obj.child_count` |
| `time_summary` | `cases[].time_summary` | `cases_obj.time_summary` |

### Tasks

List: GET `/api/tasks/`, schema `TaskList`, record path `tasks[]`.
Detail: GET `/api/tasks/{id}/`, schema `Task`, record path `task_obj`.

| Field | List response path | Detail response path |
|---|---|---|
| `id` | `tasks[].id` | `task_obj.id` |
| `title` | `tasks[].title` | `task_obj.title` |
| `status` | `tasks[].status` | `task_obj.status` |
| `priority` | `tasks[].priority` | `task_obj.priority` |
| `due_date` | `tasks[].due_date` | `task_obj.due_date` |
| `account` | `tasks[].account` | `task_obj.account` |
| `opportunity` | `tasks[].opportunity` | `task_obj.opportunity` |
| `case` | `tasks[].case` | `task_obj.case` |
| `lead` | `tasks[].lead` | `task_obj.lead` |
| `project` | `tasks[].project` | `task_obj.project` |
| `assigned_to` | `tasks[].assigned_to` | `task_obj.assigned_to` |
| `tags` | `tasks[].tags` | `task_obj.tags` |
| `created_at` | `tasks[].created_at` | `task_obj.created_at` |
| `description` | — | `task_obj.description` |
| `created_by` | — | `task_obj.created_by` |
| `contacts` | — | `task_obj.contacts` |
| `teams` | — | `task_obj.teams` |
| `custom_fields` | — | `task_obj.custom_fields` |

### Invoices

List: GET `/api/invoices/`, schema `InvoiceList`, record path `results[]`.
Detail: GET `/api/invoices/{id}/`, schema `Invoice`, record path `invoice`.

| Field | List response path | Detail response path |
|---|---|---|
| `id` | `results[].id` | `invoice.id` |
| `invoice_number` | `results[].invoice_number` | `invoice.invoice_number` |
| `invoice_title` | `results[].invoice_title` | `invoice.invoice_title` |
| `status` | `results[].status` | `invoice.status` |
| `account` | `results[].account` | `invoice.account` |
| `account_name` | `results[].account_name` | — |
| `project` | `results[].project` | `invoice.project` |
| `contact` | `results[].contact` | `invoice.contact` |
| `contact_name` | `results[].contact_name` | — |
| `client_name` | `results[].client_name` | `invoice.client_name` |
| `client_email` | `results[].client_email` | `invoice.client_email` |
| `issue_date` | `results[].issue_date` | `invoice.issue_date` |
| `due_date` | `results[].due_date` | `invoice.due_date` |
| `total_amount` | `results[].total_amount` | `invoice.total_amount` |
| `amount_due` | `results[].amount_due` | `invoice.amount_due` |
| `amount_paid` | `results[].amount_paid` | `invoice.amount_paid` |
| `currency` | `results[].currency` | `invoice.currency` |
| `is_overdue` | `results[].is_overdue` | `invoice.is_overdue` |
| `line_items_count` | `results[].line_items_count` | — |
| `created_at` | `results[].created_at` | `invoice.created_at` |
| `opportunity` | — | `invoice.opportunity` |
| `client_phone` | — | `invoice.client_phone` |
| `billing_address_line` | — | `invoice.billing_address_line` |
| `billing_city` | — | `invoice.billing_city` |
| `billing_state` | — | `invoice.billing_state` |
| `billing_postcode` | — | `invoice.billing_postcode` |
| `billing_country` | — | `invoice.billing_country` |
| `client_address_line` | — | `invoice.client_address_line` |
| `client_city` | — | `invoice.client_city` |
| `client_state` | — | `invoice.client_state` |
| `client_postcode` | — | `invoice.client_postcode` |
| `client_country` | — | `invoice.client_country` |
| `subtotal` | — | `invoice.subtotal` |
| `discount_type` | — | `invoice.discount_type` |
| `discount_value` | — | `invoice.discount_value` |
| `discount_amount` | — | `invoice.discount_amount` |
| `tax_rate` | — | `invoice.tax_rate` |
| `tax_amount` | — | `invoice.tax_amount` |
| `shipping_amount` | — | `invoice.shipping_amount` |
| `payment_terms` | — | `invoice.payment_terms` |
| `sent_at` | — | `invoice.sent_at` |
| `viewed_at` | — | `invoice.viewed_at` |
| `paid_at` | — | `invoice.paid_at` |
| `reminder_enabled` | — | `invoice.reminder_enabled` |
| `reminder_days_before` | — | `invoice.reminder_days_before` |
| `reminder_days_after` | — | `invoice.reminder_days_after` |
| `reminder_frequency` | — | `invoice.reminder_frequency` |
| `last_reminder_sent` | — | `invoice.last_reminder_sent` |
| `reminder_count` | — | `invoice.reminder_count` |
| `template` | — | `invoice.template` |
| `notes` | — | `invoice.notes` |
| `terms` | — | `invoice.terms` |
| `details` | — | `invoice.details` |
| `billing_period` | — | `invoice.billing_period` |
| `po_number` | — | `invoice.po_number` |
| `custom_fields` | — | `invoice.custom_fields` |
| `line_items` | — | `invoice.line_items` |
| `payments` | — | `invoice.payments` |
| `assigned_to` | — | `invoice.assigned_to` |
| `teams` | — | `invoice.teams` |
| `updated_at` | — | `invoice.updated_at` |
| `created_by` | — | `invoice.created_by` |
| `org` | — | `invoice.org` |
| `public_token` | — | `invoice.public_token` (hidden; policy above) |
| `public_link_enabled` | — | `invoice.public_link_enabled` (hidden; policy above) |
| `public_url` | — | `invoice.public_url` (hidden; policy above) |

### Quotes (BottleCRM Estimates)

List: GET `/api/invoices/estimates/`, schema `EstimateList`, record path `results[]`.
Detail: GET `/api/invoices/estimates/{id}/`, schema `Estimate`, record path `estimate`.

| Field | List response path | Detail response path |
|---|---|---|
| `id` | `results[].id` | `estimate.id` |
| `estimate_number` | `results[].estimate_number` | `estimate.estimate_number` |
| `title` | `results[].title` | `estimate.title` |
| `status` | `results[].status` | `estimate.status` |
| `account` | `results[].account` | `estimate.account` |
| `account_name` | `results[].account_name` | — |
| `contact` | `results[].contact` | `estimate.contact` |
| `contact_name` | `results[].contact_name` | — |
| `opportunity` | `results[].opportunity` | `estimate.opportunity` |
| `converted_to_invoice` | `results[].converted_to_invoice` | `estimate.converted_to_invoice` |
| `client_name` | `results[].client_name` | `estimate.client_name` |
| `issue_date` | `results[].issue_date` | `estimate.issue_date` |
| `expiry_date` | `results[].expiry_date` | `estimate.expiry_date` |
| `total_amount` | `results[].total_amount` | `estimate.total_amount` |
| `currency` | `results[].currency` | `estimate.currency` |
| `is_expired` | `results[].is_expired` | `estimate.is_expired` |
| `introduction` | `results[].introduction` | `estimate.introduction` |
| `deposit_percent` | `results[].deposit_percent` | `estimate.deposit_percent` |
| `start_project` | `results[].start_project` | `estimate.start_project` |
| `project_billing_type` | `results[].project_billing_type` | `estimate.project_billing_type` |
| `project` | `results[].project` | `estimate.project` |
| `deposit_invoice` | `results[].deposit_invoice` | `estimate.deposit_invoice` |
| `deposit` | `results[].deposit` | — |
| `created_at` | `results[].created_at` | `estimate.created_at` |
| `line_items` | — | `estimate.line_items` |
| `created_by` | — | `estimate.created_by` |
| `assigned_to` | — | `estimate.assigned_to` |
| `teams` | — | `estimate.teams` |
| `updated_at` | — | `estimate.updated_at` |
| `client_email` | — | `estimate.client_email` |
| `client_phone` | — | `estimate.client_phone` |
| `client_address_line` | — | `estimate.client_address_line` |
| `client_city` | — | `estimate.client_city` |
| `client_state` | — | `estimate.client_state` |
| `client_postcode` | — | `estimate.client_postcode` |
| `client_country` | — | `estimate.client_country` |
| `subtotal` | — | `estimate.subtotal` |
| `discount_type` | — | `estimate.discount_type` |
| `discount_value` | — | `estimate.discount_value` |
| `discount_amount` | — | `estimate.discount_amount` |
| `tax_rate` | — | `estimate.tax_rate` |
| `tax_amount` | — | `estimate.tax_amount` |
| `sent_at` | — | `estimate.sent_at` |
| `viewed_at` | — | `estimate.viewed_at` |
| `accepted_at` | — | `estimate.accepted_at` |
| `declined_at` | — | `estimate.declined_at` |
| `accepted_by_name` | — | `estimate.accepted_by_name` |
| `accepted_by_email` | — | `estimate.accepted_by_email` |
| `accepted_ip` | — | `estimate.accepted_ip` |
| `accepted_user_agent` | — | `estimate.accepted_user_agent` |
| `notes` | — | `estimate.notes` |
| `terms` | — | `estimate.terms` |
| `custom_fields` | — | `estimate.custom_fields` |
| `updated_by` | — | `estimate.updated_by` |
| `org` | — | `estimate.org` |
| `public_url` | — | `estimate.public_url` (hidden; policy above) |
| `public_token` | — | `estimate.public_token` (hidden; policy above) |
| `public_link_enabled` | — | `estimate.public_link_enabled` (hidden; policy above) |

## Founder confirmation

The following operations require a confirmation screen before the connector may call BottleCRM. Reuse `Confirm`, `Cancel` and `Nothing runs until you confirm.` from `workspace/app/chats/window.tsx:244`. Action labels come from the founder brief. No new explanatory body copy is invented. Any action-specific warning, success, failure or empty-state wording requires founder approval before implementation.

| Section | Action | Method | API path |
|---|---|---|---|
| Leads | Delete | DELETE | `/api/leads/{id}/` |
| Accounts | Delete | DELETE | `/api/accounts/{id}/` |
| Contacts | Delete | DELETE | `/api/contacts/{id}/` |
| Opportunities | Delete | DELETE | `/api/opportunities/{id}/` |
| Cases | Delete | DELETE | `/api/cases/{id}/` |
| Tasks | Delete | DELETE | `/api/tasks/{id}/` |
| Invoices | Send | POST | `/api/invoices/{id}/send/` |
| Invoices | Mark paid | POST | `/api/invoices/{id}/mark-paid/` |
| Quotes | Delete | DELETE | `/api/invoices/estimates/{id}/` |
| Quotes | Send | POST | `/api/invoices/estimates/{id}/send/` |
| Quotes | Convert | POST | `/api/invoices/estimates/{id}/convert/` |
| Invoices | Record payment | POST | `/api/invoices/{invoice_id}/payments/` |
| Invoices | Delete payment | DELETE | `/api/invoices/{invoice_id}/payments/{id}/` |
| Invoices | Delete line item | DELETE | `/api/invoices/{invoice_id}/line-items/{id}/` |

All other DELETE operations, including comments and attachments, inherit the same confirmation gate if exposed. There is no invoice-record DELETE endpoint; do not invent one. Converted estimates open the invoice through `converted_to_invoice`. Cases may return `CaseMergedRedirectResponse`; resolve the canonical case rather than rendering a fictitious record. Leads' closed lists use `close_leads.close_leads[]`; Accounts' closed lists use `closed_accounts.close_accounts[]` with the same record schema.

## Evidence and remaining acceptance

- Fetch and checkout from `origin/main` succeeded; starting commit `35cb373`.
- All 44 case-study screen IDs resolved after revision 3 edits.
- Figma screenshot inspection: accent comparison `89:10434`, Tiger Filled `49:3211`, Leads list `94:417`, Leads mobile detail `94:1596`. Initial CRM inspection found submenu contrast and mobile header sizing issues; shared components were corrected. Final screenshots checked: Invoices desktop detail `97:8098`, Estimates mobile list `97:9678`, Leads desktop list `94:417`, mobile payment confirmation `98:9050`.
- Founder browser test and approval screenshots are not supplied. They remain required for acceptance; no claim of founder approval is made.

## Confirmation screen register

These are Figma prototypes: Confirm and Cancel dismiss the overlay. No request is sent by Figma. Implementation must gate the recorded API operation behind Confirm, and must not treat opening an overlay as authorization. Missing action-specific warnings and result wording remain approval items; none is invented here.

| Section | Action | Desktop | Mobile |
|---|---|---|---|
| Leads | Delete | 98:8589 | 98:8605 |
| Accounts | Delete | 98:8621 | 98:8637 |
| Contacts | Delete | 98:8653 | 98:8669 |
| Opportunities | Delete | 98:8685 | 98:8701 |
| Cases | Delete | 98:8717 | 98:8733 |
| Tasks | Delete | 98:8749 | 98:8765 |
| Invoices | Send | 98:8781 | 98:8800 |
| Invoices | Mark paid | 98:8819 | 98:8856 |
| Quotes | Delete | 98:8893 | 98:8909 |
| Quotes | Send | 98:8925 | 98:8944 |
| Quotes | Convert | 98:8963 | 98:8988 |
| Invoices | Record payment | 98:9013 | 98:9050 |
| Invoices | Delete payment | 98:9087 | 98:9109 |
| Invoices | Delete line item | 98:9131 | 98:9156 |

Confirmation data paths:

- Record identity: the detail response's `id` field in the field register above; for line-item/payment deletion use `Invoice.line_items[].id` / `Invoice.payments[].id` instead of the invoice id.
- Send recipient: `GET /api/invoices/{id}/ → invoice.client_email` or `GET /api/invoices/estimates/{id}/ → estimate.client_email`.
- Mark paid: `POST /api/invoices/{id}/mark-paid/`, request `PatchedPaymentCreateRequest`: `amount`, `payment_date`, `payment_method`, `reference_number`, `notes`.
- Record payment: `POST /api/invoices/{invoice_id}/payments/`, request `PaymentCreateRequest`: `amount`, `payment_date`, `payment_method`, `reference_number`, `notes`. The first three are required. Both payment paths use BottleCRM's existing status and outstanding-balance validation; no client-side substitute or price conversion is specified.
- Payment confirmation context: `GET /api/invoices/{id}/ → invoice.currency`, `invoice.amount_due`.
- Delete payment context: `GET /api/invoices/{id}/ → invoice.payments[].amount`, `.payment_date`, schema `Payment`.
- Delete line item context: `GET /api/invoices/{id}/ → invoice.line_items[].name`, `.quantity`, `.unit_price`, schema `InvoiceLineItem`.
- Convert context: `GET /api/invoices/estimates/{id}/ → estimate.estimate_number`, `.total_amount`, `.currency`; after conversion, `converted_to_invoice` opens the corresponding invoice detail.

## Displayed list columns and mobile cards

Every list column is a property of that section's list schema above. Desktop supports horizontal scrolling. Mobile card fields are the first five desktop fields. All detail fields in the register are present, except the explicitly hidden fields.

- Leads: `first_name`, `last_name`, `company_name`, `email`, `status`, `source`, `next_follow_up`, `assigned_to`.
- Accounts: `name`, `email`, `phone`, `industry`, `assigned_to`.
- Contacts: `first_name`, `last_name`, `email`, `organization`, `phone`, `do_not_call`.
- Opportunities: `name`, `account`, `stage`, `amount`, `currency`, `probability`, `closed_on`, `assigned_to`.
- Cases: `name`, `status`, `priority`, `account`, `assigned_to`, `first_response_sla_deadline`, `resolution_sla_deadline`.
- Tasks: `title`, `status`, `priority`, `due_date`, `assigned_to`, `account`.
- Invoices: `invoice_number`, `invoice_title`, `status`, `account`, `account_name`, `project`, `contact`, `contact_name`, `client_name`, `client_email`, `issue_date`, `due_date`, `total_amount`, `amount_due`, `amount_paid`, `currency`, `is_overdue`, `line_items_count`, `created_at`.
- Quotes (BottleCRM Estimates): `estimate_number`, `title`, `status`, `account`, `account_name`, `contact`, `contact_name`, `opportunity`, `converted_to_invoice`, `client_name`, `issue_date`, `expiry_date`, `total_amount`, `currency`, `is_expired`, `introduction`, `deposit_percent`, `start_project`, `project_billing_type`, `project`, `deposit_invoice`, `deposit`, `created_at`.

## Components, navigation and validation

- Reused: Table header `43:389`, Table row `43:405`, Export control `43:31`, existing approved logo and local variable collections. Workspace menus are superseded by Trigger component set `180:8549`.
- CRM field/action components: Action `93:4`, Field `93:6`; gallery `93:3`. Trigger menu `180:8549` and mobile bar `180:8550` replace the old CRM chrome. All remain editable linked components.
- Mobile Trigger drawers: Zero `98:9181`, Filled `98:9227`. Old merged Workspace specimens `99:8146` and `93:14` are hidden as superseded history; no Trigger screen uses them.
- Four prototype entry flows start at Leads list: desktop/mobile × Zero/Filled. Trigger navigation preserves size/state where the target exists. Filled rows/cards open detail. Action controls open the matching confirmation overlay. Converted-estimate links open Invoices.
- Historical creation audit, before the 14:25 revision: **64 screens, 1,602 field bindings, 28 confirmation overlays, 0 displayed public-link fields, 0 reported errors**. Case-study revision 3 preserves all 44 IDs.
- Figma screenshots are authoring evidence only. Founder test screenshots have not been supplied; founder acceptance remains pending.

## Source and revision proof

The complete CRM schema and ID registers were carried forward from `origin/codex/crm-design:docs/figma/crm/SPEC.md`; no API path or field binding was renamed by the Quotes display change. Native SPEC is embedded in the existing frame `101:8244`. Original canvas chapter nodes are preserved as hidden history.

Validation commands: `git diff --check`, structural Figma node/field reconciliation, native SPEC readback, and screenshot review. No application build was needed for this design-only change. Marketing and Chat bot registers remain in the adjacent specifications. Group wording remains draft; Claude opens the PR and the founder merges.
