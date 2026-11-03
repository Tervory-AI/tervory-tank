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

No conversation/message deletion is scheduled. **Retention is a founder decision.** Rate-limit counters have Rig's existing short-lived windows; this does not delete conversation history. Ambiguous SMTP/CRM/quote execution is not automatically replayed.

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
