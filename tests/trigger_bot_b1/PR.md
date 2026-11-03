# Trigger B1: tenant-source bot engine, Command tools and public corridor

A store can approve its own sources, ask through existing Command cards, and receive a sourced answer or a hand-over state. Approved FAQ answers use code and a zero-cost ledger receipt. Other answers use one existing Tank writing-route call; code rejects unknown citations and unsupported numeric/date/currency tokens. Rig facts are read again at answer time. No page or widget is included.

Status: branch implementation and offline evidence only. **Not founder-browser acceptance and not done.** Claude opens the PR; founder alone merges.

## Reviewed inputs and heads

- Figma file `ZnphBOJU6657tohGLD3IzS`, page `148:10`, SPEC frame [`210:6156`](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=210-6156), read through the connected Figma session; matching native spec ID `154:4349`. Its UI remains draft. No Figma content was changed.
- Latest included main: `d6004c8d1f0110cc74fc7bbeaae4144277ca6758`.
- Combined 392-pass run and 17-pass Rig run: source head `91eb4b6f642668f615223acc60afa00337fd9fe2`.
- Final code/test head, including contact-only lead refusal: `0d40e841babf856edde821c65281df31a2ad4194`. The final 38-test socket-blocked B1 run and enabled 8-test CLI/CRM run use this head. Subsequent commits contain evidence only.
- Work directory `/workspace/codex-trigger-b1`; sole work branch `codex/trigger-b1-bot`. Main merged normally, no reset of shared work and no main push.

## What changed: file and line

| File and line | Change |
|---|---|
| `tank/trigger_bot_grounding.py:23`, `:64` | Tenant-bound passage contract, chunking, fixed thresholds, citation and number/date/currency refusal, exact record links, code rank fusion. |
| `tank/trigger_bot_sources.py:42`, `:77`, `:100` | HTTPS guarded robots-aware same-site crawl capped at 200 pages, weekly checks, per-page URL/time, pinned local encoder, Qdrant tenant/region/encoder filters and authoritative PostgreSQL hybrid retrieval. Latest approved correction supersedes an older identical FAQ question. |
| `tank/trigger_bot_engine.py:18` | Shared visitor/Command answer path; exact approved FAQ at $0, live Rig replacement, one evidence-only model call otherwise, no model judge or retry. |
| `tank/trigger_bot.py:22`, `:148`, `:194` | Tenant Rig entitlement, live catalogue facts, canonical voice, conversations/messages, typed lead drafts requiring an enquiry, claimed SMTP hand-over, weekly source maintenance. |
| `tank/trigger_bot_contract.py:13` | Strict payloads, 2,000-character message cap, no caller identity fields. |
| `tank/trigger_bot_api.py:46`, `:69`, `:115`, `:201`, `:234`, `:286` | Verified founder/admin tools, owned attachment references, digest-bound preview/Confirm, approved sources/FAQ, feedback/review/stats, lead/quote delegation and origin-bound public API. |
| `tank/trigger_bot_shared.py:23`, `:211`, `:228` | Reused Rig limiter, exact-origin issuer and SMTP sender; SQL tables are the only limiter namespace change. |
| `tank/schema.sql:2337` | Nine additive, idempotent tenant tables; conditional ENABLE/FORCE RLS and restrictive tenant boundary like personal_tokens. New trigger.bot.answer policy copies the existing trigger.write route, with cache disabled. |
| `tank/command.py:27`, `:474`, `:1141`, `:1178`, `:1255` | Register bot tools and adapters, code-only explicit command parsing and existing Confirm cards. No Trigger addition to SQUADS. |
| `tank/trigger_crm.py:95`, `:217` | Narrow create-only bot lead helper, exact confirmed digest and existing tenant binding/organization attestation. Generic CRM remains founder-only. |
| `tank/main.py:106`, `:805`, `:812`, `:4688` | Mount API; start maintenance after existing startup RLS checks; cancel it before pool shutdown. No run_route/queue/skill/cache changes. |
| `agents/rig/app.py:335`, `:446` | Internal source_record metadata preserves stored URL/SKU/decimal; room-key, tenant and region checked quote delegation to existing service.quote. |
| `workspace/app/v1/bot/messages/route.ts:1` | Public origin/key-only forwarder, bounded body, no identity/cookie forwarding, correct region with no fallback, strict upstream CORS match. No page/widget. |
| `.env.example:486` | Declare only TRIGGER_BOT_HANDOVER_ADDRESSES name; existing SMTP names reused. |
| `docker-compose.yml:240`, `docker-compose.za.yml:137` | Forward SMTP setting names and tenant recipient-map name into each Tank; no values supplied. |
| `tests/trigger_bot_b1/test_engine.py:1` | Offline evidence/refusal/FAQ/live-price/robots/origin/abuse/authority/Confirm tests; Rig primitive AST parity; contact-only lead refusal. |
| `tests/trigger_bot_b1/test_database.py:1` | Isolated PostgreSQL hybrid isolation, conditional native RLS, counters, attachment ownership, exact origin/region, startup guard, newest FAQ and zero receipt proof. |
| `tests/trigger_bot_b1/test_rig_bridge.py:1` | Actual Rig ASGI routes with fakes, exact decimal provenance, quote identity/tenant/region checks. |
| `tests/trigger_bot_b1/public_contract.cjs:1` | Actual Workspace route with fake upstream: region, origin, body limits, no identity forwarding and no fallback. |
| `tests/trigger_first_build/test_trigger.py:296` | Preserve all original first-build policy assertions by restricting that query to its original write/check tasks; B1 policy receives its own database assertion. |
| `tests/trigger_bot_b1/verification.txt:1` | Exact verification commands, captured output, setup and initial-failure record. |

## Reuse and deployment

Tank's Dockerfile copies `tank/*.py`; its image contains no `agents/rig/rigbox` package. Direct import of Rig's key/limiter/mailer code would fail in the shipped image. `trigger_bot_shared.py` carries the existing implementations verbatim, changing only limiter table names. The offline AST parity test proves the issuer, SMTP class and limiter class bodies match their originals. It does not call SMTP or an external service.

Source pins at included main:

- `agents/rig/rigbox/quotes/keys.py`: SHA256 `ebb968c877a4a86e7d67f9c83e6a6710595b26c31aa1b354f4410bdeea18154c`.
- `agents/rig/rigbox/quotes/limits.py`: SHA256 `fd98fcfa39d545846a13349b7cfcf5af593425cc916b86312464a24ce183f0f7`.
- `agents/rig/rigbox/reserve.py`: SHA256 `850d4df7a83e75314860f9d5e537c194dafbbee9a8887675eef421109f8141c2`.

The founder's explicit one-branch brief takes precedence over AGENTS.md's usual separate runtime-config PR rule. This branch includes only required names-only SMTP forwarding. On founder merge, root Compose changes redeploy the main app and `tervory-tank-za`; the Rig app change redeploys the Rig room and regional copies under the existing deploy rules. No deployment was performed here.

Founder-supplied setting names only: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `TRIGGER_BOT_HANDOVER_ADDRESSES` (tenant UUID to recipient email map). Existing region/corridor and CRM tenant-binding settings remain prerequisites. Values were never inspected or supplied. Actual SMTP delivery, runtime bindings, local encoder/Qdrant availability and the store's approved source URLs are not certified by fake-based tests.

Founder decision, 3 November 2026: conversation retention is **12 calendar months after the last message**. Daily maintenance deletes expired conversations, messages and unconfirmed drafts in tenant-scoped batches. Confirmed lead/quote drafts and their CRM/Rig records remain. Rate-limit counters now reference the tenant's window with ON DELETE CASCADE, so deleting expired windows also deletes their counters; the legacy orphan cleanup and CHECK (hits>0) are idempotent. Ambiguous SMTP/CRM/quote execution is not automatically replayed. Privacy-notice wording remains the founder's unfilled slot.

## Verification and gaps

Exact commands and captured results: [verification.txt](verification.txt).

- Combined B1 + existing Trigger/Command: **392 passed, 6 skipped**. Five skipped client/CRM checks were subsequently enabled successfully; only the pre-existing real Trigger/LanguageTool-container check remains unrun.
- Final B1 suite with outside sockets blocked and only loopback/Unix sockets allowed: **38 passed**.
- Enabled actual CLI/Workspace/loopback Tank/fake CRM acceptance: **8 passed**, no skips, after installing existing locked CLI packages.
- Existing Rig room/public proxy regressions: **17 passed**.
- Pinned Django CRM WSGI regressions: **4 passed**.
- Actual public bot Workspace transport contract: **PASS**.
- TypeScript, targeted Ruff, diff whitespace and both Compose YAML/name-forwarding checks: **PASS**.

Initial failed runs and their corrections are recorded in verification.txt; none is presented as a pass. Tests used an isolated disposable Postgres container, synthetic inputs and fake model/index/mail/upstream paths. No production SQL, real customer write, actual model call, live fixture screen or founder-browser screenshot was used.

**Missing test dependency:** the isolated Trigger room plus its pinned internal LanguageTool container for `test_real_room_with_internal_languagetool` (`TRIGGER_INTERNAL_CHECKER_TEST=1`). That test is skipped, not passed.

**Missing founder acceptance and screenshots:** Custom Nation in the founder's own `/chats` browser: approve its website and Rig sources; ask 10 real customer questions with own-source links or hand-over; compare a price with live Rig; approve two corrected FAQs and repeat at $0; verify another tenant never appears; verify hand-over email and confirmed write corridor. No founder session or screenshots were supplied, and no completion claim is made. No new page or widget is necessary for this existing Command test path.


## PR #600 review addition 14: twelve-month conversation retention

Founder decision dated 3 November 2026; implemented on this same branch from
`c71d048d77f203923cbcb309a5e11689bf957458`, with `origin/main` merged before each
push. Own checkout: `/workspace/codex-trigger-b1-retention`. No deployment,
production SQL, real deletion or model call was used to verify this change.

- `tank/trigger_bot.py:104`: at most 100 expired conversations per transaction,
  measured from the latest actual message (creation time for an empty conversation).
  Delete messages and unconfirmed drafts; detach and preserve confirmed lead/quote
  drafts without changing CRM/Rig. Lock/recheck protects a concurrent message.
- `tank/trigger_bot.py:247`, `:264`: run from the existing maintenance loop with
  tenant scope. An incomplete queue continues next tick; a completed tenant waits
  24 hours. A transaction advisory lock serializes multiple instances.
- `tank/trigger_routes.py:20`: reuse the existing $0 code receipt on the deletion
  transaction's connection. `tank.agent_receipts` stores counts only, tied to
  that tenant's ledger receipt; deletion and receipt commit or roll back together.
- `tank/schema.sql:2444`, `:2488`: record the approved rule and add idempotent
  indexes on existing message, draft and receipt stores. No new table/setting.
- `tests/trigger_bot_b1/test_retention.py:1`: one-day-under/over calendar-month
  boundary, actual last-message age, tenant isolation, confirmed lead/quote
  preservation, daily restart/batches, concurrency and receipt rollback.

Exact commands, heads and captured results are in `retention-verification.txt`.
Privacy-notice wording is unchanged and remains for the founder's own words.
No new UI, copy or screenshot is fabricated. Founder-browser acceptance and
screenshots remain missing as stated above.

Review-addition verification at code/test head
`cd5cc92191ea4eaf928d5a7e2879c7b6c20d0613`: **576 passed, 2 skipped** in the
current combined Trigger/Command/B1 run. All seven retention tests are included.
The skipped CRM WSGI module passed **4 tests** in its separate pinned Django
runtime. The real Trigger room/LanguageTool-container check remains unrun.
Earlier failing setup runs and their corrections remain in
`retention-verification.txt`; no skipped or failed run is relabelled a pass.


## PR #600 second review at c4b2201c

Own isolated checkout: `/workspace/codex-trigger-b1-rereview`, same branch
`codex/trigger-b1-bot`. Fetched and merged `origin/main` first and before every
one-file push. No production SQL, deployment or model calls.

| File and line | Review fix |
|---|---|
| `tank/trigger_bot_grounding.py:19`, `:47` | Extract digit runs beside letters from answers and cited evidence. Monetary amounts retain the existing separate decimal/currency validation. |
| `tank/trigger_bot_grounding.py:18`, `:22` | Explicit ZAR/USD/EUR/GBP/NAD/BWP/AUD/CAD codes, case-insensitive, with existing symbols and currency words. Ordinary phrases reach the answer path; lowercase prices require live Rig. |
| `tank/trigger_bot_grounding.py:27`, `:30`, `:143` | May requires an adjacent day/year in either order; remove now/soon/later. Normalize May date order while still verifying the digits. |
| `tank/trigger_bot.py:138` | Return deleted message ledger IDs; delete only that tenant's matching transcripts in the same transaction; add transcript count to the counts-only $0 receipt. |
| `tank/schema.sql:2507` | Delete legacy orphan counters, add table-scoped idempotent window FK with cascade and positive-hit check before the generated-memory block. |
| `tests/trigger_bot_b1/test_rereview.py:13`, `:68` | Each requested number form with and without support, ordinary phrases, all eight codes in both orders/cases, actual May dates and ordinary words, twice-applied constraints/orphan cleanup/cascade/other-tenant protection. |
| `tests/trigger_bot_b1/test_retention.py:24`, `:37`, `:109` | Expired transcripts removed, fresh and foreign transcripts retained, receipt contents and rollback proved with real disposable PostgreSQL. |

Exact commands, harness source and outcomes: [rereview-verification.txt](rereview-verification.txt).

- `.venv/bin/python .git/run-rereview.py`: **153 passed, zero skipped**,
  14 warnings in 61.65s. Includes the full B1 directory and both generator tests.
- `tests/test_tisan_builder_interfaces.py::test_policy_survives_actual_schema_generator`:
  **PASS** in that run; actual generator leaves `tank/schema.sql` byte-identical.
- `tests/test_agent_memory_records.py::test_all_agent_schema_files_use_one_generator`:
  **PASS** in that run.
- `.venv/bin/python .git/run-rls.py` invokes `tests/test_tenant_rls.py` with
  disposable local PostgreSQL: **4 passed, 11 setup errors, interrupted** because
  bundled pgserver lacks `pg_trgm`. No application assertion failed; the remaining
  cases were not completed locally. CI's Postgres is the test of record for this module.
- Targeted Ruff and `git diff --check`: **PASS**. Initial missing Node dependencies
  and the pre-existing broader runtime import-order lint are recorded without
  presenting either as a passing check.

**Final-head CI Tank result (full-suite test of record):**
[the current-head `tank` result on PR #600](https://github.com/Tervory-AI/tervory-tank/pull/600/checks).
This link follows the final head, rather than an earlier green run. The final
Tank counts and immutable job permalink are also recorded in the PR review
evidence after that head finishes. CI includes `tests/test_tenant_rls.py` with
Postgres and the tisan schema-generator test above.

**Founder-browser test follows after merge**, in the founder's own Custom Nation
`/chats` session. Founder alone merges. No browser acceptance or screenshots are
claimed here; the acceptance steps already listed above remain outstanding.
