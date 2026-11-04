# Tisan — founder testing sheet

Scope: all shipped Tisan waves through merged #652, based on `origin/main` at
`475597ed`. Branch `codex/tisan-acceptance`. There are **48 acceptance rows**;
`tests/acceptance/test_tisan.py::test_tNN_*` is the offline proof for row TNN.
Only test/docs/CI preparation change here; no product UI or runtime setting is added.

Setting names below are copied from **docs/ops/FOUNDER-SETTINGS.md**, read from
`origin/claude/founder-settings` (#657). Existing founder sign-in, active founder
organization, room keys, region routing and founder allowlist must already work;
do not change sign-in or paste any credential into chat, a URL or this document.
“none” means no additional founder setting. `tisan.vault` is the existing Tank
vault switch, not a new environment variable. Leave it off except for T03–T06.
Only the founder handles private key/token inputs in those rows.

## Addresses, inputs and evidence

- Browser: **https://app.tervory.com/tisan** and **https://app.tervory.com/chats**.
- `http://agent-tisan:8000/...` is an **internal room operator API**, not a public
  browser page. Use the existing authorized operator session with `X-Tank-Key`
  and founder `X-Tervory-Admin` headers supplied privately by the deployment.
  Tank promotion calls use **http://tank:8000/v1/tisan/promotion/** with the
  existing Workspace key/founder guard. No key value is supplied in this sheet.
- Replace `<TENANT>` with the active founder organization's UUID, `<PAGE>` with
  a tenant-owned approved page ID, `<FILE>`/`<NODE>` with that page's actual Figma
  pair, `<REQUEST>` with the returned quote UUID, `<OP>` with a new operation UUID,
  `<SHA>` with the full 40-character staging commit and `<OLD>` with the journal's
  recorded previous production commit. Use stable `<OP>` when retrying one action.
  A site's build number, URL, UUID and SHA must be **the actual returned values**;
  the fixed `.test` origins/SHAs below identify offline fixtures only.
- Before positive pipeline tests, retain a complete saved page/frame pair at
  **375 and 1440 px**, review it, approve it as gold, pair its Figma file, and have
  accepted copy IDs for every required slot. The legacy landing recording is
  incomplete and is deliberately **not** a positive approval/pipeline fixture.
- Use only a founder-owned test site, its existing private repository and healthy,
  pinned staging/production Coolify applications with automatic deploy disabled.
  Register the site and authorize its staging domain through the existing Radix
  domain-proof workflow. Do not run negative mutations against a client site.
- **R** (request body): `{"name":"placeholder site","slug":"placeholder-site","locale":"en","brand":{},"request":"placeholder client request"}`.
  This is the exact offline input. For live acceptance use the founder's actual
  approved test-site name/slug/request instead; no fixture content is published.
- **P** (founder pipeline request): R plus `"page_id":"<PAGE>"` and, when needed,
  `"assembly":{"plan":<APPROVED_PLAN>,"copy":<ACCEPTED_SLOT_TO_WRITE_ID_MAP>,"media":<APPROVED_MEDIA_MAP>}`.
  The plan must use the shipped section manifest, not invented text or sections.
  Minimal offline plan: `{"nav":[{"href":"/"}],"ui":{},"pages":[{"name":"home","path":"/","sections":[{"id":"hero-1","type":"hero","props":{}}]}]}`.
  Fixtures supply every named transport/artifact locally; these are not live seed data.
- **Q** (quote creation body): `{"tenant_id":"<TENANT>","data":{"contact":{"name":"placeholder customer","email":"placeholder@example.invalid","phone":"+1 (234) 567-890","company":"placeholder company","reply_method":"phone"},"items":[{"item_id":"00000000-0000-0000-0000-000000000003","type":"product","description":"placeholder product","quantity":1,"notes":"placeholder product notes"},{"type":"service","description":"placeholder service","quantity":2,"notes":"placeholder service notes"}]}}`.
  The product reference is optional and belongs to the store. Live tests use the
  founder's own request and actual product reference, never a customer's data.
- **V** (quoted transition body): `{"tenant_id":"<TENANT>","state":"quoted","quote_amount":"12.34","quote_currency":"USD","valid_until":"<FUTURE_AWARE_ISO_TIME>","quote_message":"placeholder store quote"}`.
  Choose a timezone-aware future time, e.g. tomorrow at `12:00:00+00:00`; a fixed
  past date would invalidate the test. No payment/card field is supported.

## Acceptance rows

| Row / offline test | Where | Exact action | Expected result | Setting it needs |
| --- | --- | --- | --- | --- |
| T01 `test_t01_*` | https://app.tervory.com/tisan | Click **Builds**, **Design**, **Tests**, then **Overview**. Search `placeholder absent`; click **Start build**, enter `placeholder founder site`, click the dialog's **Start build**. | The three views/search say **No builds yet.** The dialog says **No saved page yet.** Submitting this shell queues **zero** jobs. Use `/chats` for real work; this page is not a live build-history view. | none |
| T02 `test_t02_*` | https://app.tervory.com/tisan | With `tisan.vault` off, click **Plugins**. | **Plugins are off** and **This vault is off. Turn it on in Tank.** No save/read action runs. | none |
| T03 `test_t03_*` | https://app.tervory.com/tisan → Plugins → API keys | With the existing vault on, enter the founder's chosen tool name and key privately, click **Save key**, inspect its row, then **Remove**. Offline inputs are `placeholder-tool` / `placeholder-key`. | **Saved. The key is hidden and will not be shown again.** Metadata shows `••••••••`; raw value is absent. Removal says **Removed.** Both actions bind to `tisan.vault`, squad `tisan`, active tenant/user. | none; existing `tisan.vault` switch on |
| T04 `test_t04_*` | https://app.tervory.com/tisan → Plugins → Files | Click **Choose files**, select the founder's CSV/XLSX/PDF, then **Remove** its row. Offline file is `placeholder.csv` containing `name` and one `placeholder` row. | **Saved.** and file metadata; then **Removed.** Upload/remove use only the active tenant's Tisan vault. | none; existing `tisan.vault` switch on |
| T05 `test_t05_*` | https://app.tervory.com/tisan → Plugins → Source links | Enter the founder's HTTPS source in **Link**, enter a label, leave **Daily**, click **Add link**, then **Remove**. Offline link/label: `https://placeholder.invalid/` / `placeholder source`. | **Saved.**, labelled host metadata; then **Removed.** No source is fetched by this save action. | none; existing `tisan.vault` switch on |
| T06 `test_t06_*` | https://app.tervory.com/tisan → Plugins → MCP connections | Enter the founder's **Name**, HTTPS **Server URL**, choose **Token**, enter it privately, click **Add connection**, then **Disconnect**. Offline values: `placeholder MCP`, `https://placeholder.invalid/mcp`, `placeholder-token`. | **Saved. A token is hidden and will not be shown again.**, `••••••••`, then **Removed.** Raw token is absent. | none; existing `tisan.vault` switch on |
| T07 `test_t07_*` | https://app.tervory.com/tisan | As founder click **Load pages for review**, inspect **Saved frame** and sandboxed **Built page**, then **Approve as gold** for the actual tenant page. | **Approved as gold. A changed page or frame will need approval again.** Room approval returns `approved: true`; current hashes produce two private candidates, `tisan.figma` and `tisan.scaffold`, with `founder-approved-page:YYYY-MM`. No synthetic approval is seeded. | none |
| T08 `test_t08_*` | https://app.tervory.com/tisan | Load a review, save a changed frame for that same founder test page, then click the old **Approve as gold** without reloading. | Approval is HTTP **409**; UI says **Approval failed. Reload the pages and review again.** Old candidates disappear; reload/review before reapproval. | none |
| T09 `test_t09_*` | https://app.tervory.com/tisan; internal `http://agent-tisan:8000/gold/approve` | In a non-founder fixture/session inspect the page and attempt the same approval with the member identity. Do not change the founder's account. | No founder review controls; room approval is HTTP **404** for a member, and a wrong key is refused. Zero approval write. | none |
| T10 `test_t10_*` | `http://agent-tisan:8000/evals/run` | POST `{"skill_id":"tisan.figma","version":"1.0.1","tenant_id":"<TENANT>","input":{"file_key":"<RECORDED_FIGMA_FILE_KEY>","node_id":"0:1"}}` through the authorized operator session. Replace `<RECORDED_FIGMA_FILE_KEY>` with the recorded file identifier from `agents/tisan/fixtures/tervory-landing.json`; this is a file reference, never `FIGMA_TOKEN`. | Recorded landing remains `source: "fixture"`, `ready: false`; named tokens/gaps are retained. Approved 1.0.1 never makes a live call, even with a configured token. Offline real Skala→room evaluation passes all **6** cases. | none |
| T11 `test_t11_*` | `http://agent-tisan:8000/evals/run` | With live-reader approval, POST the T10 body with `version: "1.1.0"` and the founder's paired `<FILE>` / `<NODE>`. Pipeline uses this same reader with trusted live dispatch. | `source: "figma"`; tokens match saved REST evidence, only node + local-variables GETs go through the fixed Figma proxy. Tenant reading is saved; no token/header in result or artifact. The actual design may still report gaps; live does not imply complete. | FIGMA_TOKEN, TISAN_FIGMA_FILES |
| T12 `test_t12_*` | `http://agent-tisan:8000/evals/run` | Repeat T11 for a file absent from that tenant's pairing (offline `placeholderUnpairedFile01`). | Eval returns `refused: true`; reader raises its fixed refusal **before** creating an HTTP client. No reading or outbound request. | FIGMA_TOKEN, TISAN_FIGMA_FILES |
| T13 `test_t13_*` | `http://agent-tisan:8000/evals/run` | Read the paired founder file using T11 with a Figma account whose Variables endpoint returns **403**; reproduce offline with that response fixture. | `collections_known: false`, empty token values and a `variables_unavailable` gap; no invented tokens. Node read is retained. | FIGMA_TOKEN, TISAN_FIGMA_FILES |
| T14 `test_t14_*` | https://app.tervory.com/chats; generated archive from `tisan.scaffold` | Send `tisan.scaffold {"name":"Founder acceptance","slug":"founder-acceptance","page_id":"<PAGE>","brand":{"colours":{"ink":"#001840","paper":"#F4F6FB","accent":"#E80008","line":"#B8BFD0"},"fonts":{"heading":"Jost","body":"Inter"}},"pages":["home","contact","privacy"]}`. Click **Confirm**; inspect the generated archive/manifest. Offline test changes the second brand accent to `#C4622D`. | `token_set.colours.accent` matches each supplied brand; archive is under that job tenant, includes `app/tokens.css`, contact and not-found routes, excludes `node_modules`/`.next`. Tenant A's archive is not tenant B's. This row checks generation; later rows prove checks/deployment. | FIGMA_TOKEN, TISAN_FIGMA_FILES |
| T15 `test_t15_*` | https://app.tervory.com/chats | Send P via `tisan.request <P JSON>` with the minimal approved plan and no accepted-copy IDs; click **Confirm**. Inspect the result's missing-slot list. | No archive/work is produced. `copy_needed` includes `home/hero-1/heading` with purpose **the section's heading**, `home/title`, and `site/nav/0/label`. Supply accepted Copy IDs; the builder never invents the text. | FIGMA_TOKEN, TISAN_FIGMA_FILES |
| T16 `test_t16_*` | https://app.tervory.com/chats | Repeat P with every accepted-copy slot, `logo: {}` in the approved plan, and no logo media mapping; **Confirm**. | `media_needed[0].key: "site/logo/src"`; no invented image or archive. | FIGMA_TOKEN, TISAN_FIGMA_FILES |
| T17 `test_t17_*` | https://app.tervory.com/chats | Send `tisan.request <P JSON>`. Inspect its pending card, click **Confirm**, then confirm/reload that same card again. | One durable room job only, `kind: "pipeline"`, initially `status: "queued"`, request UUID equals job UUID, server-owned founder actor, `max_attempts: 1`. The **original** card later shows measured `awaiting_promote`, staging URL and `radix.repo`. Proposal alone does not dispatch. | FIGMA_TOKEN, TISAN_FIGMA_FILES, TISAN_COOLIFY_URL, TISAN_COOLIFY_TOKEN, TISAN_SITES_REPO, TISAN_GITHUB_TOKEN |
| T18 `test_t18_*` | https://app.tervory.com/chats | For the open successful founder test request send `tisan.preview <actual-site-slug>` and **Confirm**. Offline command is `tisan.preview placeholder-site`. | `status: "requested"`, actual successful `build_id`, full `commit`, staging `url`. Fixture exact values: build **1**, commit **40 a characters**, `https://placeholder-stage.test/`. Failed/pending builds are not a successful preview. | TISAN_COOLIFY_URL, TISAN_COOLIFY_TOKEN |
| T19 `test_t19_*` | https://app.tervory.com/chats | Send `tisan.feedback {"slug":"<actual-site-slug>","text":"placeholder change request"}`; **Confirm**. Before rebuilding, send `tisan.handover <actual-site-slug>`; **Confirm**. | Feedback records `status: "changes_requested"`. Signing off the unchanged build is HTTP **409**, `status: "new_build_required"`. | TISAN_COOLIFY_URL, TISAN_COOLIFY_TOKEN |
| T20 `test_t20_*` | https://app.tervory.com/chats | After T19 stage a newer approved build with a different commit, then `tisan.handover <actual-site-slug>` → **Confirm**. | `status: "accepted"`, newer `build_id` and commit retained. Fixture: build **2**, **40 b characters**. This is request sign-off, not production promotion. | TISAN_COOLIFY_URL, TISAN_COOLIFY_TOKEN |
| T21 `test_t21_*` | https://app.tervory.com/chats | Send complete P with accepted content/media and unchanged live approved page; **Confirm**; reload its card until staging finishes. | Pipeline steps in order: `requested`, `figma`, `build`, `checks`, `staging`, `awaiting_promote`; aware timestamps. Checks include `accessibility`, `lighthouse`, `links`, `secrets`, `k6`, `radix.repo`. `ok: true`; production is untouched. Replaying the same request runs build/staging once. | FIGMA_TOKEN, TISAN_FIGMA_FILES, TISAN_COOLIFY_URL, TISAN_COOLIFY_TOKEN, TISAN_SITES_REPO, TISAN_GITHUB_TOKEN |
| T22 `test_t22_*` | https://app.tervory.com/chats | Submit P referencing a founder test page with no approval; **Confirm**. | `pipeline_status: "blocked"`, `ok: false`; **zero build and staging calls**. An offline missing-approval fixture proves the same gate; do not revoke a live client's approval. | none |
| T23 `test_t23_*` | https://app.tervory.com/chats | On the isolated founder test build, run the R5-critical fixture through the request's scan path; inspect the failed check/receipt. Never plant real secrets. | Check `name: "radix.repo"`, `critical: 1`, `ok: false`, tenant/scan UUID/archive SHA retained in sidecar. Publishing is refused; zero production deployment. | none |
| T24 `test_t24_*` | https://app.tervory.com/chats; https://app.tervory.com/skala | Ensure `scan.secrets` is approved/shared with Tisan. Run the canonical fake-key fixture on the isolated generated tree. Inspect checks on the existing card. | `secrets` fails with file/line/rule only, no key text. The original presenter retains failed quality rows; failure blocks the build. Missing skill approval must fail closed, not be bypassed. | none; existing `scan.secrets` Skala approval |
| T25 `test_t25_*` | https://app.tervory.com/chats | Build the clean approved founder site, then inspect **k6** on the card and build memory. | `name: "k6"`, `ok: true`; every manifest page has `status: 200`, `requests > 1`, numeric `p95_ms >= 0`. Only the local Next server receives requests; redirects are not followed. | FIGMA_TOKEN, TISAN_FIGMA_FILES |
| T26 `test_t26_*` | https://app.tervory.com/chats | In the isolated build fixture make one local manifest page return **500** and run the same check. Do not break a production route. | `k6` is false, build `ok: false`, failed manifest/card row retained, **no archive**. No outside request. | none |
| T27 `test_t27_*` | https://app.tervory.com/chats | Open the completed build's original card; inspect its returned `memory_id` and the founder's build-memory record. | One tenant-private measured build record includes the actual checks and `radix.repo` receipt; card carries that `memory_id`. A critical scan stays false in both record/result. No public training flag or source-secret text. | none |
| T28 `test_t28_*` | `http://agent-tisan:8000/publish/build` and /publish/status | Authorized founder POST `{"tenant_id":"<TENANT>","slug":"<actual-site-slug>","build":<BUILD>,"operation_id":"<OP>"}` to `/publish/build`, poll `/publish/status` with the same body. | `pending` then `succeeded`; commit/tree contains the exact scanned archive and unchanged CI workflow, branch update is non-force. Only staging is pinned/deployed; production untouched. Replay is read-only. | TISAN_COOLIFY_URL, TISAN_COOLIFY_TOKEN, TISAN_SITES_REPO, TISAN_GITHUB_TOKEN |
| T29 `test_t29_*` | `http://tank:8000/v1/tisan/promotion/sites`, /promote, /status | Register `{"tenant_id":"<TENANT>","site":"<SITE>","staging":"<STAGE_APP_UUID>","production":"<PROD_APP_UUID>","url":"<STAGING_HTTPS_ORIGIN>"}` once. POST `{"tenant_id":"<TENANT>","site":"<SITE>","operation_id":"<OP>","commit":"<SHA>"}` to `/promote`, poll `/status` with it. | Successful complete R5 receipt, fresh passive gate with zero high/critical findings and live stage checks are required. Result `pending` → `succeeded` only at exact deployed SHA. One PATCH pin + one deploy POST. Critical recheck refuses and records finding count before writes. No Docker socket. | TISAN_COOLIFY_URL, TISAN_COOLIFY_TOKEN |
| T30 `test_t30_*` | `http://tank:8000/v1/tisan/promotion/rollback` and /status; https://app.tervory.com/chats | After successful T29, POST its tenant/site with a **new** operation UUID and `commit: "<OLD>"` to `/rollback`; poll `/status`, reload the original request card. | Rollback `pending` → `succeeded`, exact recorded old SHA restored. Original card tracks `promoted` then `rolled_back`; status refresh adds **zero** deploys. Total promote+rollback: two PATCHes and two POSTs. | TISAN_COOLIFY_URL, TISAN_COOLIFY_TOKEN |
| T31 `test_t31_*` | `http://tank:8000/v1/tisan/promotion/promote` and /status | Reproduce a queued deployment and a lost acknowledgement in the offline Coolify fixture; retry the identical operation UUID. On a live unknown result, only inspect status/history. | Pending stays pending until attested. Lost acknowledgement records `unknown` and retains the site reservation; retry adds **zero** deployment writes. No automatic resend/force-unlock. | TISAN_COOLIFY_URL, TISAN_COOLIFY_TOKEN |
| T32 `test_t32_*` | `http://agent-tisan:8000/quotes`; /quotes/<REQUEST>?tenant_id=<TENANT> | Authorized founder POST Q; GET returned request. No public quote form exists yet. | HTTP **201**, `state: "submitted"`; contact and items, decoded from returned JSON strings, exactly retain name/email/phone/company/reply_method and both product/service rows, optional product reference and notes. Initial history starts `draft`. No payment fields. | none |
| T33 `test_t33_*` | `http://agent-tisan:8000/quotes` | Repeat Q separately with phone omitted while `reply_method: "phone"`, description length **253**, and a NUL in name. | Each is HTTP **422**, no 500 or request write. Limits remain 120 name/company, 40 phone, 240 description, 2,000 notes/message; email reply does not require phone. | none |
| T34 `test_t34_*` | `http://agent-tisan:8000/quotes/<REQUEST>/state` | POST `{"tenant_id":"<TENANT>","state":"acknowledged"}`, then V. Try V again with `quote_amount: "99.99"`; GET the request. | First quote HTTP **200**, `state: "quoted"`; repeat/change HTTP **409**. Stored `quote_amount: "12.34"`, `quote_currency: "USD"`, original expiry/message remain immutable. All four fields are required only on acknowledged→quoted. | none |
| T35 `test_t35_*` | `http://agent-tisan:8000/quotes/<REQUEST>/state`; /quotes/<REQUEST>?tenant_id=<TENANT> | Only after the founder receives the customer's own acceptance, record `{"tenant_id":"<TENANT>","state":"accepted"}`. Then try `declined`, GET history. Offline fixture supplies that customer decision. | Accept HTTP **200**, later decline **409**; final `accepted`. History exactly `draft`, `submitted`, `acknowledged`, `quoted`, `accepted`, each with aware time/actor. Tisan does not accept for the customer. | none |
| T36 `test_t36_*` | `http://agent-tisan:8000/quotes/<REQUEST>/state` | On another quoted request, only after the customer's own decline, record `state: "declined"`; then try `accepted`. | Decline HTTP **200**, later accept **409**; final `declined`. No automatic reversal. | none |
| T37 `test_t37_*` | `http://agent-tisan:8000/quotes/<REQUEST>/email?tenant_id=<TENANT>` | With no `QUOTE-EMAILS.md`, POST the email action on a submitted request. | HTTP **200**, exactly `{"mail":"wording_missing"}`; `approved_letter()` is `None`, **no mail sent**. Do not add wording or SMTP settings to bypass this gate. | none |
| T38 `test_t38_*` | `http://agent-tisan:8000/quotes/<REQUEST>?tenant_id=<OTHER_TENANT>`; /quotes?tenant_id=<OTHER_TENANT> | In offline tenant fixtures, read/list tenant A's request as tenant B, then attempt access with a non-founder actor. Do not use live customer identities. | Other-tenant detail **404**, list `[]`; member access **404**. No request data leaks. | none |
| T39 `test_t39_*` | `http://agent-tisan:8000/quotes/<LEGACY_REQUEST>?tenant_id=<TENANT>` | Read an existing stored request containing only old email/item_id/quantity fields. Use the legacy DB fixture offline, do not insert legacy rows into production. | HTTP **200**, old values preserved; absent name/reply_method/type/description/quote fields remain **absent**, never fabricated or null-filled into the old objects. | none |
| T40 `test_t40_*` | Founder test site's generated `npm run deploy` / `npm run test:visual` gates | Run the existing deploy gate on saved pages: privacy link + same-site script, missing privacy, external script/frame without cookie notice; validate frame pair versus a single 375px frame. | Privacy case passes; missing privacy/cookie notice is refused without fetching/deploying. Complete **375/1440** visual evidence is required; missing/390-only data gives **frame data incomplete**. | none |
| T41 `test_t41_*` | https://app.tervory.com/chats → build checks | Run the local clean and missing-alt generated-page fixtures through Q1 accessibility, then inspect the failed check. | Clean page has no axe violations at both widths; missing-alt page fails rule **image-alt** with its page/element retained. No staging after a failed check. | none |
| T42 `test_t42_*` | https://app.tervory.com/chats → build checks | Run the broken-link local page fixture and inspect **links**. | `/missing-test-link` reports **404**. External URLs are listed but **zero external requests** are made; clean page has no link failures. | none |
| T43 `test_t43_*` | https://app.tervory.com/chats → build checks | Run the slow local page fixture through the existing Lighthouse check; inspect its score/budget. | `lighthouse.ok: false`, performance score **< 0.90** recorded, build cannot continue. Current default budgets are performance **0.90**, accessibility **0.95**, best-practices **0.90**, SEO **0.90**; these are existing file budgets, not new Coolify settings. | none |
| T44 `test_t44_*` | Founder test site's `<STAGING_HTTPS_ORIGIN>/api/contact` | POST a contact form body with `name: "placeholder"`, `message: "placeholder message"` on the isolated fixture; live uses the founder's own text. | HTTP **202**, exactly `{"ok":true}`. This shipped handler only acknowledges: **nothing is stored or forwarded**, no email delivery is claimed. | none |
| T45 `test_t45_*` | Founder test site's generated `/`, `/one/two`, and an unknown route | Inspect the generated content-route fixture with no content, with the manifest's section types, and with nested approved content. | Missing home returns no default words; unknown/nested-missing route is not found. Supplied page metadata uses its accepted title. All current section renderers remain empty pending approved section frames; no invented visual UI is claimed. | none |
| T46 `test_t46_*` | https://app.tervory.com/chats | Inspect tools with founder, tenant-admin and ordinary-member identity fixtures. Try a request carrying top-level `tenant_id`, `plan`, `copy` or `media`. | Only founder gets `tisan.build`; tenant admins get request/preview/feedback/handover, ordinary members do not. Top-level authority/assembly overrides are refused by input validation; founder assembly belongs inside `assembly`. | none |
| T47 `test_t47_*` | https://app.tervory.com/chats → `tisan.request` approved-plan build path | In offline P set section type to `placeholder-invented`; separately try HTTP, credential-bearing HTTPS, `/media/../placeholder-private`, data-URL and protocol-relative media inputs. | Unknown section fails plan validation; all five unsafe media forms are refused before generated content is written. No invented section or private fetch. | none |
| T48 `test_t48_*` | Founder test site's existing `npm run test:visual` | Compare the approved frame's measured text/box/colour against rendered local fixture at 375px. Then change its text, painted colour and x position. | Exact match yields `score: 1`, `passed: true`; changed rendering yields `score < 1`, `passed: false`, identifying failed measurements. No external asset request. T40 separately proves both required frame widths. | none |

## Offline proof and limits

Each `test_tNN_*` executes its shipped UI, route, orchestration, scanner or
publisher path on existing fixtures. Imported scenario helpers retain their own
assertions; there is no copy of product logic in this sheet's tests. T01–T06 use
actual TSX, React and Chromium, with Trigger sign-in/Next/Tank server boundaries stubbed;
raw keys/tokens are placeholder fixture strings only. Browser requests are
blocked. Gold server actions are also executed with the existing identity fixture.
Request/quote routes use throwaway PostgreSQL, existing guards and tenant binding.
Figma uses local HTTPS through the real fixed proxy, not Figma's live API. The
pipeline's build/staging services and R5 scanner-job transport are fixtures;
separate rows run actual k6, Q1 browser checks, secret engine, publisher HTTP
client and Coolify promotion/rollback client. No model, provider, live setting,
production SQL, real customer decision, live promotion or mail is used.

The UI's start dialog and empty build history remain shells. Quote-request page
still needs the Figma thread's frame; no public quote URL is asserted. Live
Figma 1.1.0 still needs its existing Skala approval; the ordinary unversioned
Figma job cannot opt into live mode through caller input. These boundaries are
part of acceptance, not claims of completed live UI wiring.

CI preparation installs the **existing pinned** template npm dependencies and
Chromium before the offline suite. No package/lockfile or deployment setting is
changed. Run with the repo's Python test dependencies, Node 22, workspace npm
packages, template npm packages/browser and the pinned room k6 already installed.
`POOL_SCHEMA_DATABASE_URL` must identify a disposable loopback Postgres, never
production. CI already supplies it; each fixture creates/drops its own database.

```sh
PATH="$PWD/.venv/k6-v1.8.2-linux-amd64:$PATH" \
PLAYWRIGHT_BROWSERS_PATH="$PWD/.venv/j5-browser" \
TISAN_TEST_PLAYWRIGHT="$PWD/.venv/tisan-browser/node_modules/playwright" \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32885/postgres \
.venv/bin/python -m pytest tests/acceptance/test_tisan.py -q -n 2 --dist loadfile \
  --disable-socket --allow-hosts=127.0.0.1,localhost

.venv/bin/ruff check tank tests --select E9,F \
  --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"
git diff --check
```

Validation: **48 passed, 0 skipped**, 10 existing warnings in **127.55s**, using the exact acceptance command above with two xdist workers. `tests/test_secrets.py -q --disable-socket` also passed (**2 passed**). The 48 unique table IDs match the 48 test functions and the workflow YAML parses. Exact CI lint returned **All checks passed!**; `git diff --check` was clean. The pushed head is reported in the handoff. The founder still
runs the live positive cases after deployment in his own workspace; offline
fixtures do not establish that live acceptance occurred.
