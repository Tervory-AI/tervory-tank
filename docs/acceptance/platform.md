# Workspace and Tank — founder testing sheet

Scope: Platform wave 4, based on `origin/main` at
`15432cb522a7922359ad9174aed3784480b34b50`, after #682 merged. There are
**26 acceptance rows**. Each named `tests/acceptance/test_platform.py::test_pNN_*`
case executes that row offline. The final mapping check rejects missing,
duplicate or extra cases. Fixture database rows, clocks, model transports and
SMTP replace external boundaries; these checks do not spend money, approve a
production skill, change production data, send email or deploy anything.

## Addresses, inputs and evidence

- Browser: **https://app.tervory.com/** (client dashboard), **/control** (founder
  dashboard), **/chats**, **/ledger**, **/tasks**, **/tank/proof** and the product
  pages reached through Squad. Use the existing signed-in founder organization;
  use a separate authorized member test session for refusal checks.
- Workspace `/api/...` URLs below are authenticated JSON APIs, not new screens.
  `http://tank:8000/v1/...` is an internal authorized operator API. Keep its
  existing Workspace key and server identity headers private; never paste a key
  into a URL, this sheet or chat. Workspace derives tenant/user from its session.
- `<TENANT>`, `<TASK>` and `<LEDGER>` mean actual returned, owned UUIDs. `<OLD>`
  and `<NEW>` are actual registered skill versions; `<DEADLINE>` is a future
  timezone-aware ISO timestamp. Offline `placeholder` text and `.test` mailboxes
  are fixture inputs, not values to publish or production recipients.
- A live acceptance mutation needs the founder's own disposable test tenant or
  package and the applicable approval. This sheet is a testing recipe, not
  authorization to edit production policies, onboard a customer, send mail,
  start paid work, retire a version or deploy.
- Setting names come from [FOUNDER-SETTINGS.md](../ops/FOUNDER-SETTINGS.md).
  “none” means no additional setting beyond the existing sign-in, founder role,
  organization and working Workspace/Tank connection. No values are recorded.
- For region rows, the existing connection uses `TANK_URL`, `TANK_API_KEY` and
  `TANK_REGION`. The other region requires `TANK_URL_ZA` /
  `TANK_CONTENT_API_KEY_ZA`, or `TANK_URL_US` / `TANK_CONTENT_API_KEY_US`.
  Restricted homes/feeds keys cannot authorize tenant content. A ZA Workspace
  needs its US directory connection. These are existing reserved names; this
  branch does not set them or change runtime configuration.
- Unknown cost is pending, not zero. Savings compare the same eligible receipts
  and frozen baseline; negative savings remain negative. A successful HTTP
  response alone is not evidence of delivery, production health or a promotion.

## Acceptance rows

| Row / offline test | Where | Exact action | Expected result | Setting it needs |
| --- | --- | --- | --- | --- |
| P01 `test_p01_shell` | Workspace shared shell, e.g. /ledger | Open Squad; use Arrow keys and Escape; inspect founder and member menus. | Dashboard, Projects, Chats and Squad retain their order. Squad is a pop-out; Escape closes it. Skala and Tank remain founder-only. Offline proof covers navigation logic and wiring, not a new browser screenshot. | none |
| P02 `test_p02_dashboard_render` | / and /control | Open each dashboard with recorded data, then an unavailable measurement. Follow the source links. | Actual components render scoped measurements and source links. An unavailable source produces an error; fixture numbers are never product defaults. Founder details do not appear in the client view. | none |
| P03 `test_p03_founder_controls` | Internal /v1/controls/paid-paused and /v1/dashboards/founder | From the member fixture session attempt to read founder data and write `{"paused":true}`. | HTTP 404; no control or audit write. Founder identity is checked independently of the shared transport key. | none |
| P04 `test_p04_chats_auto` | /chats | Send `Hello` with Auto selected; repeat with the paid-work refusal fixture. | The existing `command.turn` route receives the active tenant, home and messages without a model override. A refusal is preserved; no second route is attempted. | none |
| P05 `test_p05_conversation_ownership` | /chats | Create a fixture conversation, search it and replay its saved turn; try the ID from another tenant. | Own content persists and can be searched/replayed; the other tenant cannot read it. Saved replay does not execute a new action. | none |
| P06 `test_p06_receipt_unknowns` | /chats receipt | Inspect a response without a measured baseline/cost, and one with explicit ledger evidence. | Missing baseline/cost remains unknown; an explicit receipt ID is retained. The receipt never invents a baseline or treats an unknown charge as free. | none |
| P07 `test_p07_ledger_scope` | /ledger; internal GET /v1/ledger/summary?tenant_id=<TENANT> | Read the owner with one measured $0.10 delivered receipt and one unpriced unverified receipt; read an empty tenant. | Owner totals: 2 calls, 1 delivered, $0.10 known spend, 1 unpriced. Foreign $999 receipt is absent; empty tenant has 0 calls. | none |
| P08 `test_p08_savings_reconcile` | Dashboard savings and /tank/proof | Open the same snapshot's graphs and all detail pages; change tenant, member and date range. | Graph totals equal all 206 eligible fixture receipts and the 100/100/6 detail pages. Savings retain precise values and reconcile to $41.20; foreign/region/excluded rows stay out of the client population. | none |
| P09 `test_p09_code_ladder` | Internal /v1/route and /v1/skills/.../run | Run the approved code fixture through the normal ladder and directly. | Existing code rung produces its recorded result, ledger and transcript. No paid model call replaces a successful code path. | none |
| P10 `test_p10_actual_execution_receipt` | Tank route receipt | Run the escalation fixture, then the cache path. | The receipt records the actual execution and binds the call to its tenant. Cache evidence remains distinct from model execution evidence. | none |
| P11 `test_p11_price_window_and_deadline` | Internal POST /v1/route | Submit batch-eligible off-peak work with a deadline; compare known feasible price windows. For the receipt fixture the deadline is one hour away and the discount starts two hours away. | Cheapest feasible published window wins; infeasible discount does not postpone work beyond its deadline. The fixture delivers once at the ordinary measured $0.00008412, on the same receipt. Forecast discounts are not booked as savings. | none |
| P12 `test_p12_expired_work` | Existing off-peak job status | Advance the fixture clock beyond its accepted deadline before dispatch. | Job fails with deadline evidence; no paid dispatch occurs. No retry or alternate paid route is added. | none |
| P13 `test_p13_retirement_and_rollback` | Internal Skala version lifecycle | In an isolated package, attempt to retire OLD after NEW has 29 clean days, then after 30; request rollback. | Day 29 refuses; day 30 permits retirement only with the existing clean evidence. OLD files remain and rollback works. A new approval alone never retires OLD. | none |
| P14 `test_p14_roster_before_policy` | Existing policy/model roster workflow | Change the fixture deployment membership, then propose a model policy change. Complete the real approved-package eval handler. | Policy is held while every approved package is evaluated; `tank.skills.models_validated` records the roster fingerprint. The proposal still passes its separate target-model gate before serving. Completed evals are not replayed. | none |
| P15 `test_p15_founder_onboarding` | PUT /api/tenants/<TENANT>/home; internal /v1/tenants/<TENANT>/home | For a new isolated tenant submit `{"home_region":"za"}` as founder; repeat, change it to us-east, and try as member. | Internal founder assignment and same-home repeat succeed. Changed home requires migration (409); the internal API gives a member 403 (the Workspace founder guard hides its proxy with 404). Invalid home gives 422. US direct route/task/batch reject that ZA tenant; existing US data prevents silent ZA assignment. | regional connection names above |
| P16 `test_p16_regional_content_transport` | Workspace server calls, including /chats and Zenas | Resolve a ZA tenant through the US directory, then send private content; repeat with unavailable, malformed, redirected or mismatched metadata. | Directory request contains only the tenant UUID; content and full regional key go only to the recorded destination. Server identity is preserved. Unsafe metadata fails before content; no restricted-key fallback. | regional connection names above |
| P17 `test_p17_task_board` | GET /api/workspace/tasks | Read the tenant's delivered and unverified tasks, plus a foreign task fixture. | Ledger evidence determines Delivered/Unverified; foreign task is absent. Unknown cost is null with `cost_pending=true`. This is the backend contract, not a replacement of the existing /tasks screen. | none |
| P18 `test_p18_wrong_with_note` | POST /api/workspace/tasks/<TASK>/feedback | On a delivered owned task submit `{"verdict":"wrong","note":"placeholder correction"}`; try a 1,001-character note and another tenant's task. | Correct ledger stores rejected + wrong + note + session user; learning writer is retained. Long note gives 422; foreign task gives 404. Unverified work cannot be rated as delivered. | none |
| P19 `test_p19_recorded_results` | GET /api/workspace/results | Read an owned delivered task whose actual answer is stored in its transcript. | Result includes that actual content and original ledger ID; foreign result is absent. No sample download URL is invented. Product artifacts must come from the real product output. | none |
| P20 `test_p20_morning_ledger` | Founder GET internal /v1/platform/morning-report | Preview the frozen night's report with deferred calls, comparable savings and multiple failed eval receipts. | Dispatch-night spend and canonical savings are used. Failed evals count once per job, including no-call failure. Unknown charges stay separate; no customer content or notes enter the digest. | none; TANK_GITHUB_READ_TOKEN is optional for read-only deployment workflow history |
| P21 `test_p21_morning_smtp_claim` | Founder report email | Allow the authorized schedule for the same region/day to run twice, including a restart. Offline SMTP is a stub mailbox. | A durable daily claim produces one email to the configured founder only. A repeated claim does not resend; the durable record survives the restart. | FOUNDER_REPORT_TO; SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM; optional FOUNDER_REPORT_SMTP_HOST, FOUNDER_REPORT_SMTP_PORT, FOUNDER_REPORT_SMTP_USER, FOUNDER_REPORT_SMTP_PASSWORD, FOUNDER_REPORT_SMTP_FROM |
| P22 `test_p22_seven_pacific` | Tank report scheduler | Start the fixture at 06:59:59 Pacific and advance one second. | No early send; one 07:00 America/Los_Angeles send, then the existing poll. Pacific DST uses its real time zone. | same report settings as P21 |
| P23 `test_p23_product_registries` | /chats product tool catalogue and Tank router registry | Inspect member, tenant-admin and founder catalogues and registered API/lifecycle entries against the reviewed freeze. | Every tool, argument schema, adapter, first dispatch arm, role visibility, route order and lifecycle slot matches the explicit golden. No tool is executed by this inspection. | none |
| P24 `test_p24_global_paid_pause` | Founder paid-work control; Tank cache/paid boundary | Pause paid work, then run a cache hit and a paid cache miss in the fixture. | Cached result can return. Paid miss stops before transport. The global pause remains the overriding control; this row does not claim a new per-step settings screen. | none |
| P25 `test_p25_founder_promotion_bar` | Tank graduation candidates | Inspect RouteLLM evidence with policy threshold .95 and minimum 30: compare 200 samples at .98 and .99 agreement. | .98 holds; .99 can meet the evidence bar. Existing founder review is still required; this case does not perform a production promotion. | none |
| P26 `test_p26_multiple_deployments` | Existing US and ZA LiteLLM model roster | Inspect a same-model group with several deployments and the configured routing strategy. | Both existing rosters use cost-based routing and preserve every group member. Host/privacy restrictions remain authoritative. Offline proof checks configuration and catalogue preservation, not live provider traffic. | none |

## Missing frames and limits

[Workspace REGISTER.md](../figma/workspace/REGISTER.md) records the approved
Results and Task board frames. Gate 2 supplies their backend contracts; the
existing `/tasks` UI is not presented here as the new delivered/unverified frame.
Feedback desktop/mobile and empty/loading/error frames are still missing, as is
the founder **Paid steps settings** frame (each step Ask/Auto plus global pause).
No layout has been invented for them. Feedback is available through the strict
authenticated API meanwhile. Per-step confirmation/settings work is tracked
separately in [#710](https://github.com/Tervory-AI/tervory-tank/pull/710);
this sheet does not duplicate or claim its runtime proof. P24 proves the global
override only.

The morning report is regional: it covers midnight through 07:00 Pacific for
that Tank. Optional deployment workflow history is labelled incomplete when its
feed is unavailable or truncated; a workflow success or process-start SHA does
not attest room health. Candidate comparisons are prompts for founder review,
not approval or promotion. SMTP is verified TLS and uses only configured names.

Run the offline file with the normal CI disposable Postgres and installed
Workspace dependencies. Hosted CI on the final head is the release evidence.
Local precheck uses `PRECHECK_SKIP_SEMGREP=1 scripts/precheck.sh` by founder
instruction; local Semgrep is neither run nor claimed green.
The final documentation gate reuses the completed local scan evidence under
Root's subsequent no-additional-local-scans instruction. Fresh security evidence
for the final head comes from hosted CI.
