# Trigger CRM: Invoices and Estimates

Written by Claude, 28 Oct 2026, from `ops/trigger-crm/openapi-cd7c12a.yml` (our pinned BottleCRM, commit cd7c12a). Founder decision, 28 Oct: **Invoices and Estimates are two separate items in Tervory's CRM**, each with its own menu item, list and detail screen.

BottleCRM files estimates under its invoices API (`/api/invoices/estimates/`). That is BottleCRM's URL layout only. Our users never see it: the Trigger CRM connector maps each screen to the right path.

## The two menu items

| Menu item | List | Detail | API base |
|---|---|---|---|
| Invoices | All invoices | One invoice | `/api/invoices/` |
| Estimates | All estimates | One estimate | `/api/invoices/estimates/` |

An estimate can become an invoice (`POST /api/invoices/estimates/{id}/convert/`). The converted estimate links to its invoice (`converted_to_invoice`), and the invoice opens from there.

## Invoices: list fields (`InvoiceList`)
`id`, `invoice_number`, `invoice_title`, `status`, `account`, `account_name`, `project`, `contact`, `contact_name`, `client_name`, `client_email`, `issue_date`, `due_date`, `total_amount`, `amount_due`, `amount_paid`, `currency`, `is_overdue`, `line_items_count`, `created_at`

## Invoices: detail fields (`Invoice`)
`id`, `invoice_number`, `invoice_title`, `status`, `account`, `contact`, `opportunity`, `project`, `client_name`, `client_email`, `client_phone`, `billing_address_line`, `billing_city`, `billing_state`, `billing_postcode`, `billing_country`, `client_address_line`, `client_city`, `client_state`, `client_postcode`, `client_country`, `subtotal`, `discount_type`, `discount_value`, `discount_amount`, `tax_rate`, `tax_amount`, `shipping_amount`, `total_amount`, `currency`, `amount_paid`, `amount_due`, `issue_date`, `due_date`, `payment_terms`, `sent_at`, `viewed_at`, `paid_at`, `reminder_enabled`, `reminder_days_before`, `reminder_days_after`, `reminder_frequency`, `last_reminder_sent`, `reminder_count`, `public_token`, `public_link_enabled`, `public_url`, `template`, `notes`, `terms`, `details`, `billing_period`, `po_number`, `custom_fields`, `line_items`, `payments`, `assigned_to`, `teams`, `is_overdue`, `created_at`, `updated_at`, `created_by`, `org`

## Estimates: list fields (`EstimateList`)
`id`, `estimate_number`, `title`, `status`, `account`, `account_name`, `contact`, `contact_name`, `opportunity`, `converted_to_invoice`, `client_name`, `issue_date`, `expiry_date`, `total_amount`, `currency`, `is_expired`, `introduction`, `deposit_percent`, `start_project`, `project_billing_type`, `project`, `deposit_invoice`, `deposit`, `created_at`

## Estimates: detail fields (`Estimate`)
`id`, `account`, `contact`, `opportunity`, `converted_to_invoice`, `project`, `deposit_invoice`, `line_items`, `created_by`, `assigned_to`, `teams`, `is_expired`, `public_url`, `created_at`, `updated_at`, `estimate_number`, `title`, `status`, `client_name`, `client_email`, `client_phone`, `client_address_line`, `client_city`, `client_state`, `client_postcode`, `client_country`, `subtotal`, `discount_type`, `discount_value`, `discount_amount`, `tax_rate`, `tax_amount`, `total_amount`, `currency`, `issue_date`, `expiry_date`, `sent_at`, `viewed_at`, `accepted_at`, `declined_at`, `accepted_by_name`, `accepted_by_email`, `accepted_ip`, `accepted_user_agent`, `introduction`, `deposit_percent`, `start_project`, `project_billing_type`, `public_token`, `public_link_enabled`, `notes`, `terms`, `custom_fields`, `updated_by`, `org`

## Invoice endpoints
| Method | Path | What it does |
|---|---|---|
| `GET` | `/api/invoices/` | invoices_list |
| `POST` | `/api/invoices/` | invoices_create |
| `POST` | `/api/invoices/{invoice_id}/attachments/` | attachments_create |
| `POST` | `/api/invoices/{invoice_id}/comments/` | comments_create |
| `GET` | `/api/invoices/{invoice_id}/line-items/` | line_items_list |
| `POST` | `/api/invoices/{invoice_id}/line-items/` | line_items_create |
| `PUT` | `/api/invoices/{invoice_id}/line-items/{id}/` | line_items_update |
| `DELETE` | `/api/invoices/{invoice_id}/line-items/{id}/` | line_items_destroy |
| `GET` | `/api/invoices/{invoice_id}/payments/` | payments_list |
| `POST` | `/api/invoices/{invoice_id}/payments/` | payments_create |
| `DELETE` | `/api/invoices/{invoice_id}/payments/{id}/` | payments_destroy |
| `GET` | `/api/invoices/{id}/` | invoices_retrieve |
| `PUT` | `/api/invoices/{id}/` | invoices_update |
| `POST` | `/api/invoices/{id}/cancel/` | invoices_cancel |
| `POST` | `/api/invoices/{id}/duplicate/` | invoices_duplicate |
| `POST` | `/api/invoices/{id}/mark-paid/` | invoices_mark_paid |
| `GET` | `/api/invoices/{id}/pdf/` | invoices_pdf |
| `POST` | `/api/invoices/{id}/send/` | invoices_send |
| `DELETE` | `/api/invoices/attachments/{id}/` | attachments_destroy |
| `PUT` | `/api/invoices/comments/{id}/` | comments_update |
| `DELETE` | `/api/invoices/comments/{id}/` | comments_destroy |
| `GET` | `/api/invoices/export/` | invoices_export_retrieve |
| `POST` | `/api/invoices/from-opportunity/{opportunity_id}/` | invoice_from_opportunity |
| `POST` | `/api/invoices/from-time-entries/` | invoices_from_time_entries_create |
| `GET` | `/api/invoices/products/` | products_list |
| `POST` | `/api/invoices/products/` | products_create |
| `GET` | `/api/invoices/products/{id}/` | products_retrieve |
| `PUT` | `/api/invoices/products/{id}/` | products_update |
| `DELETE` | `/api/invoices/products/{id}/` | products_destroy |
| `GET` | `/api/invoices/recurring/` | recurring_list |
| `POST` | `/api/invoices/recurring/` | recurring_create |
| `GET` | `/api/invoices/recurring/{id}/` | recurring_retrieve |
| `PUT` | `/api/invoices/recurring/{id}/` | recurring_update |
| `DELETE` | `/api/invoices/recurring/{id}/` | recurring_destroy |
| `POST` | `/api/invoices/recurring/{id}/toggle/` | recurring_toggle |
| `GET` | `/api/invoices/reports/aging/` | aging_report |
| `GET` | `/api/invoices/reports/dashboard/` | dashboard |
| `GET` | `/api/invoices/reports/revenue/` | revenue_report |
| `GET` | `/api/invoices/statements/{account_id}/` | account_statement |
| `GET` | `/api/invoices/statements/{account_id}/pdf/` | account_statement_pdf |
| `GET` | `/api/invoices/templates/` | templates_list |
| `POST` | `/api/invoices/templates/` | templates_create |
| `GET` | `/api/invoices/templates/{id}/` | templates_retrieve |
| `PUT` | `/api/invoices/templates/{id}/` | templates_update |
| `DELETE` | `/api/invoices/templates/{id}/` | templates_destroy |
| `GET` | `/api/invoices/templates/{id}/editor/` | templates_editor_retrieve |

## Estimate endpoints
| Method | Path | What it does |
|---|---|---|
| `GET` | `/api/invoices/estimates/` | estimates_list |
| `POST` | `/api/invoices/estimates/` | estimates_create |
| `GET` | `/api/invoices/estimates/{id}/` | estimates_retrieve |
| `PUT` | `/api/invoices/estimates/{id}/` | estimates_update |
| `DELETE` | `/api/invoices/estimates/{id}/` | estimates_destroy |
| `POST` | `/api/invoices/estimates/{id}/convert/` | estimates_convert |
| `GET` | `/api/invoices/estimates/{id}/pdf/` | estimates_pdf |
| `POST` | `/api/invoices/estimates/{id}/send/` | estimates_send |

## Rules for the design and the connector
- **Sends and deletes need the founder's confirmation in Tervory first.** BottleCRM's API sends email, records payments and deletes with no confirmation of its own: every `.../send/`, `.../mark-paid/`, `.../payments/` POST, `.../convert/` and every `DELETE`.
- **Public links stay off** (`public_link_enabled`, `/api/public/...`). The CRM is for the founder only until its own design is approved. There is no client-facing accept/decline page.
- **Money is shown in the record's own `currency`,** with no conversion.
- **No sample data on the live screens.** An empty list stays empty.
