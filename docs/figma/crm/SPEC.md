# Trigger CRM design

Status: design in progress; founder acceptance not yet performed.
Branch: `codex/crm-design`. Claude opens the PR. No application code or live data changed.

Figma: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=93-2
Page: **2 · CRM** (`93:2`), founder only. Existing Case studies page: `42:2`; revision 3 SPEC: `63:10450`.

## Contract and design rules

Sources: `ops/trigger-crm/openapi-cd7c12a.yml` (BottleCRM cd7c12a), `docs/figma/crm/INVOICES-ESTIMATES.md`, `docs/figma/case-studies/SPEC.md` and `workspace/app/product-nav.ts`.

The eight independent menu items are Leads, Accounts, Contacts, Opportunities, Cases, Tasks, Invoices, Estimates. Invoices and Estimates remain separate despite their shared API prefix. Case-study founder menus, typography, controls and variables are reused. CRM accent is `color/accent/crm` (`VariableID:72:9823`, #0369A1, 5.93:1 on white).

Desktop viewports are 1440 × 900. Mobile viewports are 375 × 812. Detail fields scroll vertically. Desktop lists scroll horizontally to retain exact schema labels. Mobile lists use the first five listed columns; the full record is available in detail. Zero lists have no rows or invented empty-state wording. Zero detail fields show the existing em-dash convention. Filled values such as `[first_name]` are schema-binding annotations in Figma, never sample client records or live data. They must be replaced with tenant-scoped API values at implementation time.

No public client routes or links. `public_token` and `public_url` are not displayed. `public_link_enabled` stays false and is not an editable control. `is_sample` is not displayed. Record money uses its own `currency`, without conversion. API metadata is documented here, not added as product copy.

## Screen register

Target: 64 screens (8 sections × list/detail × desktop/mobile × Zero/Filled). IDs below are existing created nodes; remaining variants are still being composed.

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

### Estimates

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
| Estimates | Delete | DELETE | `/api/invoices/estimates/{id}/` |
| Estimates | Send | POST | `/api/invoices/estimates/{id}/send/` |
| Estimates | Convert | POST | `/api/invoices/estimates/{id}/convert/` |
| Invoices | Record payment | POST | `/api/invoices/{invoice_id}/payments/` |
| Invoices | Delete payment | DELETE | `/api/invoices/{invoice_id}/payments/{id}/` |
| Invoices | Delete line item | DELETE | `/api/invoices/{invoice_id}/line-items/{id}/` |

All other DELETE operations, including comments and attachments, inherit the same confirmation gate if exposed. There is no invoice-record DELETE endpoint; do not invent one. Converted estimates open the invoice through `converted_to_invoice`. Cases may return `CaseMergedRedirectResponse`; resolve the canonical case rather than rendering a fictitious record. Leads' closed lists use `close_leads.close_leads[]`; Accounts' closed lists use `closed_accounts.close_accounts[]` with the same record schema.

## Evidence and remaining acceptance

- Fetch and checkout from `origin/main` succeeded; starting commit `35cb373`.
- All 44 case-study screen IDs resolved after revision 3 edits.
- Figma screenshot inspection: accent comparison `89:10434`, Tiger Filled `49:3211`, Leads list `94:417`, Leads mobile detail `94:1596`. Initial CRM inspection found submenu contrast and mobile header sizing issues; shared components corrected, final screenshots pending.
- Founder browser test and approval screenshots are not supplied. They remain required for acceptance; no claim of founder approval is made.

