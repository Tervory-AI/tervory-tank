# Trigger M1: approved posts, GBP connection, publication and review replies

Posts use W1's saved draft, voice and checker results. The founder or verified
tenant admin approves a specific revision/profile and schedules it through the
existing `/chats` Confirm cards. A due GBP post gets a durable send claim and
retains Google's returned ID/link. Review replies require Confirm; identical
sent text is not sent twice, and an edit replaces the same reply resource.
Other channels remain scheduled-only. No page, widget or visible wording added.

**Branch implementation only; founder-browser acceptance is missing.** Claude
opens the PR; the founder merges. No live Google write or production SQL ran.

## Heads and dependency

- Branch: `codex/trigger-m1-marketing`; own folder `/workspace/codex-trigger-m1`.
- Current code/test head: `ca8cc947` (full hash in verification evidence).
- Included main: `b2fa83bdfca6d5788d12e11ce5230da1463a3621`.
- Refreshed W1 head `b9d9b363` was merged without resetting either side; W1
  subsequently landed on main in #595. Main was merged again, keeping its
  additions and one copy of the identical W1 provenance schema block.

## Founder-approved limit rule, checked 3 November 2026

The Marketing SPEC line **“Missing limits block scheduling” is superseded** by
the founder's 3 November answer. Figma thread: correct SPEC frame `210:2897`
(native root `151:3973`) in the next round. No Figma document was changed here.

An official numeric limit still requires W1's checker to report the text within
that limit. Where there is no official limit, a completely checked post may
schedule once approved. GBP retains `limit: none` in existing checker fields;
no new card wording or third-party 1,500-character limit is introduced.
Google's too-long rejection marks the post failed with Google's message and
does not automatically retry. Editing returns it to draft.

Official references checked on **3 November 2026**, also recorded beside GBP
in `agents/trigger/formats.py:26`:

- https://support.google.com/business/answer/7342169
- https://support.google.com/business/answer/7390603
- https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts

## What changed (file and line)

| File and line | Result |
|---|---|
| `agents/trigger/formats.py:26` | Founder rule, check date and three official references; GBP limit stays unset. |
| `agents/trigger/service.py:102` | Review text is separately labelled untrusted customer data, not the trusted task brief or dispatch instruction. |
| `tank/trigger_marketing_contract.py:1` | Typed existing-card tools, checker eligibility, explicit-offset/IANA scheduling validation. |
| `tank/schema.sql:2445` | Six additive/idempotent tenant tables above generated memory; conditional ENABLE/FORCE RLS follows existing rollout guard. |
| `tank/trigger_google.py:1` | Official OAuth/API endpoints, one-use tenant/user state, PKCE, scoped vault refresh storage, transient access tokens and sanitized failures. |
| `tank/trigger_marketing.py:1` | Owned W1 drafts, revision/profile-bound approval, editing, scheduling, calendar, review cursor and saved reply drafts. |
| `tank/trigger_publisher.py:1` | Committed claims, locked sends, bounded rate-limit backoff, terminal length failures, ambiguous-delivery refusal and confirmed reply PUT. |
| `tank/trigger_marketing_api.py:25` | Verified founder/admin authority and existing Confirm dispatch; no caller tenant override. |
| `tank/command.py:35` | Register M1 tools/adapters and prepare exact owned previews; existing SQUADS and permission logic unchanged. |
| `tank/trigger_routes.py:48` | Code parses explicit M1 commands before existing W1 planning. |
| `tank/main.py:106`, `:805`, `:4689` | Publisher starts after startup guards, cancels before pool shutdown; mount API. |
| `tank/case_study_sources.py:179` | Actual publication/reply counts as metadata on the existing draft figure; tenant, receipt region and date scoped. No new report labels. |
| `workspace/app/oauth/trigger-gbp/callback/route.ts:1` | Existing authenticated server transport completes OAuth, then returns to `/chats`; no new page or reflected exchange data. |
| `.env.example:505`, `docker-compose.yml:240`, `docker-compose.za.yml:137` | Names-only OAuth forwarding; exact setting locations listed in ops instructions. No values. |
| `docs/ops/TRIGGER-GBP.md:1` | Official access/client/scope/redirect instructions, existing-card workflow, recovery semantics and founder acceptance steps. |
| `tests/trigger_m1/test_marketing.py:1` | Offline state/length/concurrency/retry/DST/Confirm/reply/OAuth tests. |
| `tests/trigger_m1/test_m1_storage.py:1` | Actual W1 Confirm cards, customer-data prompt boundary, native RLS/startup guards and credential redaction. |
| `tests/trigger_m1/test_m1_queue.py:1` | Eligible-tenant queue, known manual retry and ambiguous cancellation refusal. |
| `tests/trigger_m1/test_m1_metrics.py:1` | Existing report keys and actual count provenance across tenant/region/date boundaries. |
| `tests/trigger_m1/callback_contract.cjs:1` | Actual Workspace callback tested with fake transport and outside fetch refused. |

## Validation and acceptance

Exact commands and captured results are in `verification.txt`. Current code/test
head: **25 M1 tests passed**, with outside sockets blocked. Actual callback
contract, TypeScript, Ruff and secret regressions passed.

The full repository command completed with **6,612 passed, 10 failed, 42 skipped**
and **1,799 subtests passed**; separate Tiger and Zenas runs passed **46** and
**40** tests. The ten failures all pass on focused retries after correcting
scratch/dependency setup. The original full command's exit 1 remains recorded;
it is not relabelled green. Earlier incomplete/timed-out runs and the corrected
case-study regression are also recorded. A final current-head Trigger/Command
run is finishing; its exact completion will be appended to the evidence.

**Founder test and screenshots: not performed or available.** The required test
is Custom Nation in its own browser: connect its actual profile, approve and
schedule three real GBP posts, inspect the calendar, see one post appear on
Google, and see a real review reply appear only after Confirm. Fake-Google
tests do not satisfy that acceptance.

## Deployment, settings and delivery boundary

See `docs/ops/TRIGGER-GBP.md` for Google's official prerequisites, API access
approval, client steps, exact redirect and `business.manage` scope references.
Founder fills names only: `TRIGGER_GOOGLE_OAUTH_CLIENT_ID`,
`TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET`; existing `TANK_VAULT_KEY` must be present in
the tenant's home region. Values were neither inspected nor supplied.

The founder's explicit one-branch brief takes precedence over AGENTS.md's usual
separate runtime-config PR rule. Root/ZA Compose changes redeploy the main app
and ZA Tank; `agents/trigger/` changes redeploy Trigger and its regional copies
under existing deploy rules. No deployment was performed by this thread.

Google has no documented create-post request-id/idempotency field. A transport
error, 5xx, malformed success or lost in-flight claim becomes failed/uncertain,
without automatic or ordinary manual POST replay. This prevents double posting
after an unrecorded success; it cannot promise atomic Google/Postgres delivery.
Uncertain deliveries require reconciliation against Google before any further
publication decision. A successful create response is offline evidence of API
acceptance only; actual public visibility still needs the founder's test.
