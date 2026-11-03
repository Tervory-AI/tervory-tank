# Trigger CRM · current specification · 3 November

This replaces all previous canvas and repository CRM design guidance. Page `93:2`; canvas SPEC `101:8244`; branch `codex/crm-design`; existing PR #436. Original screen roots remain. Changed screens say **Changed after approval, awaiting founder**; unchanged component specimens say **Approved 3 Nov**. Founder visual acceptance of these changes is outstanding. No application code, model call, production data or deployment is part of this work.

## Navigation and character

CRM is Trigger. One 240px Trigger menu, approved Tervory logo and client switcher. Writing: Write, Voice. CRM: Leads, Clients, Contacts, Opportunities, Cases, Tasks. Sales: Quotes, Invoices. Marketing and Chat bot entries remain. Bottom: All products, Receipts, Billing, Account settings. Settings names the Chat bot area; it occurs once in the menu. Quotes is the display name for the existing Estimates API. Clients is the display name for the Accounts API. IDs, routes and API names stay internal.

Desktop is 1440×900 with a 1200px work area and 1136px content width. Mobile is 375×812, one matching drawer, two-line record cards linked to full details. Drawer content scrolls independently above a pinned 240px-wide bottom block with a top divider and 16px end clearance. No design-index strip appears inside screens. Existing Jost Light headings, Inter text, Trigger controls and bound colour tokens are reused.

## Fields, labels and record identity

One rendered field per idea. The linked account field is Clients; account name is its display value, not another field. Contact name resolves the linked Contact and is not duplicated. Invoice and quote client snapshots are distinct Bill-to name, Bill-to email, Bill-to phone and Bill-to address fields. Country is shown once; country_display formats country. Stage is shown once; stage_label formats stage. Created is shown once; created_on_arrow formats created_at. Fields omitted from lists remain on detail screens. Hidden redundant nodes preserve their IDs.

Reference (id), Board order (kanban_order/board_order), Organisation (org), Acceptance IP address (accepted_ip) are hidden on user screens, including confirmations. UUIDs remain internal navigation/API arguments. They never identify a record in confirmation copy. No data or API field is removed.

Detail titles use [Full name], [Client name], [Opportunity name], [Case name], [Task title], [Invoice number] or [Quote number], with a back link to the matching list and size/state. Mobile Lead and Contact cards use one [Full name], derived by joining non-empty first_name and last_name with one space, not separate visible slots. The detail fields retain First name and Last name.

## Lists and tables

Plain header row with a bottom border, no header card treatment, same cell padding and widths as data rows. Full-width row dividers. Invoice number is one line. Desktop column sets have at most eight columns; all other supported fields remain on detail. Filled brackets denote data slots, never sample records. Zero lists contain one proposed empty-state line.

- Leads: First name, Last name, Company, Email, Status, Source, Next follow-up, Assigned to.
- Clients: Name, Email, Phone, Industry, Assigned to.
- Contacts: First name, Last name, Email, Company, Phone, Do not call.
- Opportunities: Name, Clients, Stage, Amount, Currency, Probability, Closed, Assigned to.
- Cases: Name, Status, Priority, Clients, Assigned to, First reply due, Resolution due.
- Tasks: Title, Status, Priority, Due date, Assigned to, Clients.
- Invoices: Invoice number, Title, Clients, Status, Due date, Total, Amount due, Currency.
- Quotes: Quote number, Title, Clients, Status, Expiry date, Total, Currency.

Invoice Items and Payments are tables on detail screens. Items: Item, Quantity, Unit price, Subtotal, row Delete. Payments: Amount, Payment date, Payment method, Reference number, row Delete. At 375 these tables scroll horizontally within the detail viewport. Filled rows are bracketed field slots; Zero has No items yet. / No payments yet. Each row Delete opens the existing corresponding confirmation with invoice context and the selected row's identity and amounts. Delete payment and Delete line item are absent from the page-level action row. No invoice-record Delete endpoint is invented.

## Actions and confirmations

Action labels are centred. Confirm is primary. Delete actions are destructive and last after ordinary actions. Existing action order remains consistent within each record type; Invoice actions are Send, Mark paid, Record payment. All existing confirmation steps and frame IDs remain.

Every confirmation shows a record name or number. Send includes Recipient email. Convert includes Quote number, Total and Currency. Delete payment includes Invoice number, Amount and Payment date; Delete line item includes Invoice number, Name, Quantity and Unit price. No internal Reference is shown.

Record payment and Mark paid show Invoice number, Amount due and Currency at the top, then inputs. Amount *, Payment date * and Payment method * are required by PaymentCreateRequest in the pinned BottleCRM OpenAPI. Amount is a decimal input bounded by outstanding balance; Payment date is a date control; Payment method is a choice control from the existing enum. Reference number and Notes are optional inputs. The asterisk marks required inputs. The design shows outlined editable-control specimens, not submitted values or live payment records. Confirm and Cancel remain pinned on mobile; the scroll viewport stops above them and content has footer-height plus 24px clearance. A real payment requires the founder's final confirmation.

No public client routes or links. Public-link fields are not exposed. Money uses its record currency without conversion. API operations and tenant scoping remain as specified below.

## Changed screen node register

- `94:172` · Leads / List / Desktop / Zero · Changed after approval, awaiting founder.
- `94:417` · Leads / List / Desktop / Filled · Changed after approval, awaiting founder.
- `94:671` · Leads / List / Mobile / Zero · Changed after approval, awaiting founder.
- `94:682` · Leads / List / Mobile / Filled · Changed after approval, awaiting founder.
- `94:741` · Leads / Detail / Desktop / Zero · Changed after approval, awaiting founder.
- `94:1061` · Leads / Detail / Desktop / Filled · Changed after approval, awaiting founder.
- `94:1384` · Leads / Detail / Mobile / Zero · Changed after approval, awaiting founder.
- `94:1596` · Leads / Detail / Mobile / Filled · Changed after approval, awaiting founder.
- `94:1811` · Clients / List / Desktop / Zero · Changed after approval, awaiting founder.
- `94:1978` · Clients / List / Desktop / Filled · Changed after approval, awaiting founder.
- `94:2193` · Clients / List / Mobile / Zero · Changed after approval, awaiting founder.
- `94:2204` · Clients / List / Mobile / Filled · Changed after approval, awaiting founder.
- `94:2263` · Clients / Detail / Desktop / Zero · Changed after approval, awaiting founder.
- `94:2510` · Clients / Detail / Desktop / Filled · Changed after approval, awaiting founder.
- `94:2760` · Clients / Detail / Mobile / Zero · Changed after approval, awaiting founder.
- `94:2888` · Clients / Detail / Mobile / Filled · Changed after approval, awaiting founder.
- `97:2074` · Contacts / List / Desktop / Zero · Changed after approval, awaiting founder.
- `97:2245` · Contacts / List / Desktop / Filled · Changed after approval, awaiting founder.
- `97:2473` · Contacts / List / Mobile / Zero · Changed after approval, awaiting founder.
- `97:2484` · Contacts / List / Mobile / Filled · Changed after approval, awaiting founder.
- `97:2543` · Contacts / Detail / Desktop / Zero · Changed after approval, awaiting founder.
- `97:2800` · Contacts / Detail / Desktop / Filled · Changed after approval, awaiting founder.
- `97:3060` · Contacts / Detail / Mobile / Zero · Changed after approval, awaiting founder.
- `97:3200` · Contacts / Detail / Mobile / Filled · Changed after approval, awaiting founder.
- `97:3343` · Opportunities / List / Desktop / Zero · Changed after approval, awaiting founder.
- `97:3522` · Opportunities / List / Desktop / Filled · Changed after approval, awaiting founder.
- `97:3776` · Opportunities / List / Mobile / Zero · Changed after approval, awaiting founder.
- `97:3787` · Opportunities / List / Mobile / Filled · Changed after approval, awaiting founder.
- `97:3846` · Opportunities / Detail / Desktop / Zero · Changed after approval, awaiting founder.
- `97:4107` · Opportunities / Detail / Desktop / Filled · Changed after approval, awaiting founder.
- `97:4371` · Opportunities / Detail / Mobile / Zero · Changed after approval, awaiting founder.
- `97:4515` · Opportunities / Detail / Mobile / Filled · Changed after approval, awaiting founder.
- `97:4662` · Cases / List / Desktop / Zero · Changed after approval, awaiting founder.
- `97:4837` · Cases / List / Desktop / Filled · Changed after approval, awaiting founder.
- `97:5078` · Cases / List / Mobile / Zero · Changed after approval, awaiting founder.
- `97:5089` · Cases / List / Mobile / Filled · Changed after approval, awaiting founder.
- `97:5148` · Cases / Detail / Desktop / Zero · Changed after approval, awaiting founder.
- `97:5416` · Cases / Detail / Desktop / Filled · Changed after approval, awaiting founder.
- `97:5687` · Cases / Detail / Mobile / Zero · Changed after approval, awaiting founder.
- `97:5839` · Cases / Detail / Mobile / Filled · Changed after approval, awaiting founder.
- `97:5994` · Tasks / List / Desktop / Zero · Changed after approval, awaiting founder.
- `97:6165` · Tasks / List / Desktop / Filled · Changed after approval, awaiting founder.
- `97:6393` · Tasks / List / Mobile / Zero · Changed after approval, awaiting founder.
- `97:6404` · Tasks / List / Mobile / Filled · Changed after approval, awaiting founder.
- `97:6463` · Tasks / Detail / Desktop / Zero · Changed after approval, awaiting founder.
- `97:6671` · Tasks / Detail / Desktop / Filled · Changed after approval, awaiting founder.
- `97:6882` · Tasks / Detail / Mobile / Zero · Changed after approval, awaiting founder.
- `97:6966` · Tasks / Detail / Mobile / Filled · Changed after approval, awaiting founder.
- `97:7053` · Invoices / List / Desktop / Zero · Changed after approval, awaiting founder.
- `97:7276` · Invoices / List / Desktop / Filled · Changed after approval, awaiting founder.
- `97:7673` · Invoices / List / Mobile / Zero · Changed after approval, awaiting founder.
- `97:7684` · Invoices / List / Mobile / Filled · Changed after approval, awaiting founder.
- `97:7743` · Invoices / Detail / Desktop / Zero · Changed after approval, awaiting founder.
- `97:8098` · Invoices / Detail / Desktop / Filled · Changed after approval, awaiting founder.
- `97:8464` · Invoices / Detail / Mobile / Zero · Changed after approval, awaiting founder.
- `97:8716` · Invoices / Detail / Mobile / Filled · Changed after approval, awaiting founder.
- `97:8979` · Quotes / List / Desktop / Zero · Changed after approval, awaiting founder.
- `97:9218` · Quotes / List / Desktop / Filled · Changed after approval, awaiting founder.
- `97:9667` · Quotes / List / Mobile / Zero · Changed after approval, awaiting founder.
- `97:9678` · Quotes / List / Mobile / Filled · Changed after approval, awaiting founder.
- `97:9737` · Quotes / Detail / Desktop / Zero · Changed after approval, awaiting founder.
- `97:10064` · Quotes / Detail / Desktop / Filled · Changed after approval, awaiting founder.
- `97:10398` · Quotes / Detail / Mobile / Zero · Changed after approval, awaiting founder.
- `97:10618` · Quotes / Detail / Mobile / Filled · Changed after approval, awaiting founder.
- `98:8589` · Leads / Confirm Delete / Desktop · Changed after approval, awaiting founder.
- `98:8605` · Leads / Confirm Delete / Mobile · Changed after approval, awaiting founder.
- `98:8621` · Clients / Confirm Delete / Desktop · Changed after approval, awaiting founder.
- `98:8637` · Clients / Confirm Delete / Mobile · Changed after approval, awaiting founder.
- `98:8653` · Contacts / Confirm Delete / Desktop · Changed after approval, awaiting founder.
- `98:8669` · Contacts / Confirm Delete / Mobile · Changed after approval, awaiting founder.
- `98:8685` · Opportunities / Confirm Delete / Desktop · Changed after approval, awaiting founder.
- `98:8701` · Opportunities / Confirm Delete / Mobile · Changed after approval, awaiting founder.
- `98:8717` · Cases / Confirm Delete / Desktop · Changed after approval, awaiting founder.
- `98:8733` · Cases / Confirm Delete / Mobile · Changed after approval, awaiting founder.
- `98:8749` · Tasks / Confirm Delete / Desktop · Changed after approval, awaiting founder.
- `98:8765` · Tasks / Confirm Delete / Mobile · Changed after approval, awaiting founder.
- `98:8781` · Invoices / Confirm Send / Desktop · Changed after approval, awaiting founder.
- `98:8800` · Invoices / Confirm Send / Mobile · Changed after approval, awaiting founder.
- `98:8819` · Invoices / Confirm Mark paid / Desktop · Changed after approval, awaiting founder.
- `98:8856` · Invoices / Confirm Mark paid / Mobile · Changed after approval, awaiting founder.
- `98:8893` · Quotes / Confirm Delete / Desktop · Changed after approval, awaiting founder.
- `98:8909` · Quotes / Confirm Delete / Mobile · Changed after approval, awaiting founder.
- `98:8925` · Quotes / Confirm Send / Desktop · Changed after approval, awaiting founder.
- `98:8944` · Quotes / Confirm Send / Mobile · Changed after approval, awaiting founder.
- `98:8963` · Quotes / Confirm Convert / Desktop · Changed after approval, awaiting founder.
- `98:8988` · Quotes / Confirm Convert / Mobile · Changed after approval, awaiting founder.
- `98:9013` · Invoices / Confirm Record payment / Desktop · Changed after approval, awaiting founder.
- `98:9050` · Invoices / Confirm Record payment / Mobile · Changed after approval, awaiting founder.
- `98:9087` · Invoices / Confirm Delete payment / Desktop · Changed after approval, awaiting founder.
- `98:9109` · Invoices / Confirm Delete payment / Mobile · Changed after approval, awaiting founder.
- `98:9131` · Invoices / Confirm Delete line item / Desktop · Changed after approval, awaiting founder.
- `98:9156` · Invoices / Confirm Delete line item / Mobile · Changed after approval, awaiting founder.
- `98:9181` · Trigger / Mobile drawer / Zero · Changed after approval, awaiting founder.
- `98:9227` · Trigger / Mobile drawer / Filled · Changed after approval, awaiting founder.

## New words and slots awaiting founder approval

- Changed after approval, awaiting founder
- Approved 3 Nov
- Clients
- Account settings
- Bill-to name
- Bill-to email
- Bill-to phone
- Bill-to address line
- Bill-to city
- Bill-to state or region
- Bill-to postcode
- Bill-to country
- Full name
- Client name
- Opportunity name
- Case name
- Task title
- Recipient email
- Amount *
- Payment date *
- Payment method *
- No leads yet.
- No clients yet.
- No contacts yet.
- No opportunities yet.
- No cases yet.
- No tasks yet.
- No invoices yet.
- No quotes yet.
- No items yet.
- No payments yet.
- ← Leads
- ← Clients
- ← Contacts
- ← Opportunities
- ← Cases
- ← Tasks
- ← Invoices
- ← Quotes
- Item

Contextual bracket slots use the same plain labels, including [Full name], [Client name], [Opportunity name], [Case name], [Task title], [Invoice number], [Quote number], [Recipient email], [Clients] and each Bill-to field label. Amount, Payment date, Payment method, Reference number, Notes, Item, Quantity, Unit price and Subtotal use their existing words in bracketed table/input slots. The choice control uses the existing ⌄ glyph. These slots are annotations, not fake live records.

## API register

The existing pinned API names and response paths below are retained only as implementation mapping. Accounts and Estimates in API/schema names mean Clients and Quotes in the UI. The raw API register is not a display-label authority.


Every field below is an exact schema property. [] denotes an array element. Plain labels above control display; the API register retains internal metadata and all supported fields.

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



## Authoring verification and acceptance

The requested branch was cloned into /workspace/codex-crm-design. Fetch succeeded. The first merge attempt stopped because the local committer identity was absent; the requested local Codex name/email were configured, then git merge origin/main passed and the merge was pushed. Only docs/figma/crm/SPEC.md is edited for this design revision.

Commands: git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-crm-design; git fetch origin codex/crm-design; git checkout codex/crm-design; git config user.name Codex; git config user.email codex@users.noreply.github.com; git merge origin/main; git diff --check; git push origin codex/crm-design.

Figma structural checks cover duplicate detail labels, hidden internals, column counts, confirmation context, required payment inputs, drawer clearance and canvas text. Screenshots are authoring evidence, not a founder browser acceptance test. Founder acceptance remains outstanding. No tests or screenshots are claimed as founder approval. Claude handles PR review and the founder merges.
