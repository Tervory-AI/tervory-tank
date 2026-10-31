# Trigger CRM connector checkpoint

Updated **31 October 2026, 12:00 PDT / 19:00 UTC**. Earlier 11:29 checkpoint results are retained and superseded where noted below. Draft PR #498. This is implementation and offline evidence, not founder acceptance or a live deployment claim.

## What changed

| File and line | Change |
|---|---|
| `tank/trigger_crm.py:28` | Reuse JSON Schema validation against a strict pinned BottleCRM write subset. No arbitrary metadata or automatic project/billing/public-link side effects. |
| `tank/trigger_crm.py:48` | Recheck existing Command identity and actual persisted tenant Trigger entitlement; no default grant or cross-tenant founder fallback. Client integration was explicitly authorized after the initial founder-only checkpoint. Voice administration remains founder/tenant-admin only. |
| `tank/trigger_crm.py:56` | Explicit Tank tenant -> actual BottleCRM organization + connector token setting name mapping. Missing, duplicate organizations, setting names or credential values fail closed. Mapping is founder-supplied configuration. A matching authenticated CRM organization attestation is now required on every upstream read; writes additionally require attested read preflight and server-side expected-org check before the CRM view executes. |
| `tank/trigger_crm.py:91` | Fixed allowlisted BottleCRM paths, bounded response/timeout, no redirects/proxy environment, sanitized errors, no upstream user/token/org metadata projected to Workspace. |
| `tank/trigger_crm.py:132` | GET leads/contacts/estimates list. Public `page` translated to pinned DRF limit/offset (10 rows); leads have independently paged open/closed groups, combined only after strict shape checks. |
| `tank/trigger_crm.py:169` | GET one UUID record. |
| `tank/trigger_crm.py:177` | POST execution only with exact existing durable Command confirmed-card context; no boolean approval bypass, no automatic retry. Successful code mutation gets an actual zero-cost ledger row. |
| `tank/trigger_crm_schema.py:1` | Write contracts copied from `ops/trigger-crm/openapi-cd7c12a.yml`, pinned upstream `cd7c12a`. Countries/currencies and required fields preserved; arbitrary custom fields excluded. |
| `tank/command.py:44`, `:978`, `:1015` | Tenant Trigger-granted `trigger.crm.write` tool, strict arguments and existing Command adapter; existing durable card ownership, role recheck, cancellation and once-only dispatch reused. |
| `tank/main.py:4484` | Register CRM router. |
| `tank/requirements.txt:17` | Existing Researcher `jsonschema==4.26.0` pin reused; no model needed for validation. |
| `docker-compose.yml:261` | Names-only connector settings; Tank attached to existing CRM corridor. |
| `ops/trigger-crm/docker-compose.yml:92` | Unambiguous private backend DNS alias, default allowed host list updated. |
| `.env.example` | Setting names only; no token values. |
| `tests/test_trigger_crm.py:1` | Synthetic transport, real ASGI routes/identity, role/tenant/region denial, projections, invalid inputs, SSRF/redirect/error handling, exact payload-bound Confirm and existing executing-card owner predicates. |

## Workspace contract

- `GET /v1/trigger/crm/{leads|contacts|estimates}` -> `{resource,items,page,count}`. `count` is unknown/null if unavailable, never invented.
- Query: `page=1..10000`; contacts optionally `name`; leads optionally `title`, `status` (`assigned`, `closed`, `converted`, `in process`, `recycled`). No tenant, organization, URL or duplicate query parameters.
- `GET /v1/trigger/crm/{resource}/{uuid}` -> `{resource,item}`.
- CRM changes go through the existing Command action/card/confirm contract as `trigger.crm.write`: `{resource,record_id?,data}`. Do not expose a raw browser write proxy. PUT edits use pinned full-body requirements: contacts first_name/last_name; leads assigned_to/contacts/teams; estimates account_id/contact_id/title. No delete, send, convert, pay, order or automation action is implemented.
- Client backend integration is authorized under an actual persisted Trigger grant. No grant is created. Client dashboard layout/copy still needs approved Figma frames; API permission is not visual approval.

## Required runtime settings (names only)

`TRIGGER_CRM_URL`, `TRIGGER_CRM_TENANT_BINDINGS`, `TRIGGER_CRM_PAT_CONNECTOR`.

Founder supplies the actual tenant UUID and BottleCRM organization UUID. The bindings object is keyed by the actual tenant UUID and has `organization_id` and `token_env` fields. `token_env` names `TRIGGER_CRM_PAT_CONNECTOR` in the current compose. The founder supplies its PAT value in Coolify; builders never create/read/print it. Additional tenant connector credentials require separately forwarded setting names, never reuse this founder organization token for clients.

Private URL defaults to `http://trigger-crm-backend:8000`, on the existing `tervory-gw-trigger-crm` network. If Coolify already explicitly sets `ALLOWED_HOSTS`, the founder must include the new private alias. The public alternative `https://crm.tervory.com` remains Access-gated and redirects are deliberately rejected, not bypassed. No runtime setting was inspected or changed here.

## Commands and results

All commands ran in isolated `/home/ammosync/tervory-trigger-crm-backend-20261031`, Python 3.12 environment `/home/ammosync/trigger-crm-venv312`, with `TMPDIR=/home/ammosync/trigger-crm-tmp`. Default `/tmp` ensurepip initially failed with disk quota; rerun used an owned directory on the larger filesystem. No other checkout/cache/source was deleted.

1. `git clone https://github.com/Tervory-AI/tervory-tank.git /home/ammosync/tervory-trigger-crm-backend-20261031`; `git fetch origin main`; `git checkout -b codex/trigger-crm-backend-20261031 origin/main`; named `ls` checks: **passed**. First commit needed repository-local Git author identity; no push failed. Every finished file committed and pushed.
2. `TMPDIR=/home/ammosync/trigger-crm-tmp python3.12 -m venv /home/ammosync/trigger-crm-venv312`: **passed**. Dependencies installed at repository pins plus pytest/pytest-asyncio/Ruff for local testing. Missing test-runtime openai/jiter imports were resolved using the existing Tank pins; no test failures were hidden.
3. `TMPDIR=/home/ammosync/trigger-crm-tmp PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_trigger_crm.py tests/test_secrets.py --tb=short`: **31 passed, 1 existing Pydantic warning, 10.07s** at runtime/test head `9000cb6f`. This is 29 CRM cases plus 2 existing secret-scan cases, not 31 independent CRM cases. Initial test fixture authority setup was corrected before this final run.
4. `/home/ammosync/trigger-crm-venv312/bin/ruff check tank/trigger_crm.py tank/trigger_crm_schema.py tests/test_trigger_crm.py`: **All checks passed**.
5. `git diff --check`: **passed**.
6. Read-only `gh api repos/Django-CRM/Django-CRM/contents/backend/contacts/views.py?ref=cd7c12a607df1719518fcdaf289864f6ba7d0bcd` (and `backend/leads/views/lead_views.py`, `backend/invoices/api_views.py`): confirmed pinned `LimitOffsetPagination`, native wrappers and create response IDs. No live CRM API was contacted.

The initial `94782b9d` checkpoint passed all 10 applicable hosted checks. Subsequent security/client/schema changes invalidate that old clearance; exact NEW-head CI, independent review and combined Workspace -> Tank integration remain pending. Full heavyweight Tank boot suite was not run locally. No screenshots are required for this server-only change; founder browser screenshots remain unverified and must be added after approved UI/deployment.

## Capability audit for new design proposals

Evidence: pinned repository OpenAPI, not a live capability claim.

| Capability | Existing contract | Connector status |
|---|---|---|
| Leads, contacts, estimates | `/api/leads/`, `/api/contacts/`, `/api/invoices/estimates/` with list/detail/create/update | Implemented core slice, tenant mapping/runtime setup pending |
| Invoice data, send, PDF, payments | `/api/invoices/`, `/{id}/send/`, `/{id}/pdf/`, `/{invoice_id}/payments/` | Not exposed; payments/Stripe/platform billing are outside this job |
| Estimate email/send and PDF | `/api/invoices/estimates/{id}/send/`, `/{id}/pdf/` | Not exposed; requires explicit send action/confirmation and real mail configuration |
| Automation | `/api/automation/catalogue/`, `/rules/`, `/rules/{id}/runs/`, `/rules/{id}/try/`, `/rules/reorder/` | Existing upstream APIs; current connector PAT deliberately excludes automation scopes |
| Inbound email | `/api/cases/inbound/email/` | Existing specialized case ingestion, not a general mailbox/chat/messages API |
| General chat/messages | No named general chat/messages endpoints in the pinned OpenAPI | Existing Tank Chats must be reused, not duplicated |
| Reminders | InvoiceBodyRequest: reminder_enabled, reminder_days_before/after, reminder_frequency; Invoice: last_reminder_sent/reminder_count; OrgSettings: lead_reminder_minutes. Tasks + notifications exist. | Existing upstream reminder features, not yet exposed by this connector; no generic daily-reminder capability is claimed |
| Other historical CRM modules | `/api/accounts/`, `/api/opportunities/`, `/api/cases/`, `/api/tasks/`, `/api/invoices/` | Five of the historical eight CRM modules are not yet wired through this connector; no whole-CRM completion claim. Additional module scopes require founder-supplied narrow PAT configuration; existing scopes are not silently broadened |

## Still incomplete

Approved client dashboard frame/copy and explicit client-access authority; real connector mapping/PAT setting values (founder only); actual store/customer account/contact/estimate source records; live private connectivity; independent review; final hosted CI; approved UI integration; founder walkthrough LAST. No synthetic data was inserted into a live system, no SQL/migration was run on production, and no messages/emails/provider/model calls were sent.


## Security/client follow-up (supersedes founder-only checkpoint)

- Corrected a generated-contract defect: schema normalization stripped actual property names `title` and `description` as though they were schema annotations. Added exact property-set comparison against the pinned source and valid lead/contact/estimate payload regressions.
- Added `trigger` to the existing generic tenant squad authority and the CRM tool to Trigger tools. Preserve voice administration as founder/tenant-admin only; clients cannot acquire founder tools. Actual grant removal is rechecked on execution, including after the CRM preflight.
- Fixed the independent review finding that configured organization uniqueness alone does not prove which organization a PAT authenticates. A small read-only Compose-config WSGI wrapper appends an organization-binding middleware to the **existing pinned application**. It uses only the PAT and organization already resolved by upstream middleware. Expected-org mismatch returns 403 **before** view execution. Successful authenticated responses attest `X-Tervory-CRM-Organization`.
- Tank sends the expected organization, validates the attested organization before reading any response body, and requires an attested GET preflight before every write. An old/unmodified server therefore fails before POST/PUT, rather than detecting an issue only after a side effect. No new endpoint, credential type, profile scope, organization override or upstream fork is introduced.
- Backend and connector overlay must be deployed together; missing attestation is an intentional 502 and must not be bypassed. The existing CRM database migrations/initial-admin command is unchanged; no production deployment or SQL was run.
- Additional files: `ops/trigger-crm/tervory_crm_middleware.py`, `tervory_connector_wsgi.py`, two read-only Compose config mounts, `tests/test_trigger_crm_wsgi.py`.

Follow-up commands/results:

1. `TMPDIR=/home/ammosync/trigger-crm-tmp PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_trigger_crm.py tests/test_secrets.py --tb=short`: **40 passed, one existing warning, 18.01s** at `d65ca60b` (38 CRM + 2 existing secret checks).
2. Installed **Django==6.1.2**, the exact upstream `backend/uv.lock` pin, in the isolated test environment only. `TMPDIR=/home/ammosync/trigger-crm-tmp PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_trigger_crm_wsgi.py --tb=short`: **4 passed, 1.04s**. Uses real Django WSGI/response machinery with synthetic settings/auth and zero database; it is not a full deployed BottleCRM integration claim. The WSGI tests explicitly skip if the optional CRM-only Django runtime is absent from a Tank-only environment.
3. Ruff on the connector, schema, new tests and both WSGI files: **passed**. Full-file Ruff on existing `command.py` reports preexisting findings; accidental automatic cleanup was reverted before committing, preserving only the required CRM hunks.
4. Read-only YAML assertions for config source existence, read-only mounts and WSGI command: **passed**.
5. Broader `tests/test_command.py` attempt: **17 passed, 26 skipped, 32 setup errors** because this narrow local environment lacks Redis and the remaining heavy Tank runtime dependencies. This is not a passing broad suite; hosted actual new-head CI remains required.
