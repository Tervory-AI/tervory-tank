# Trigger M1: approved posts, GBP connection, publication and review replies

Posts use W1's saved draft, voice and checker results. The founder or verified
tenant admin approves a specific revision/profile and schedules it through the
existing `/chats` Confirm cards. A due GBP post gets a durable send claim and
retains Google's returned ID/link. Review replies require Confirm; identical
sent text is not sent twice, and an edit replaces the same reply resource.
Other channels remain scheduled-only. No page, widget or visible wording added.

**PR #604; founder merges.** The founder browser test and real Trigger/internal
LanguageTool check follow after merge, as directed in the review. No live Google
write or production SQL ran.

## Heads and dependency

- Branch: `codex/trigger-m1-marketing`; own folder `/workspace/codex-trigger-m1`.
- Final head: [current #604 branch head](https://github.com/Tervory-AI/tervory-tank/commits/codex/trigger-m1-marketing).
  The exact final SHA and its CI `tank` result are pinned in the PR description
  after the last push, so recording the result does not change the tested head.
- Latest merged main: `ecef216bc16d17c6337242971d117b3fbd8db854`.
- Locally validated merged head: `0b1e3d6a4d4e8dec96893b8f471d9da33ab831aa`.
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
| `tank/trigger_publisher.py:1` | Committed claims, locked sends, bounded rate-limit backoff, terminal length failures, ambiguous-delivery handling, confirmed reconciliation and reply PUT. |
| `tank/trigger_marketing_api.py:25` | Verified founder/admin authority and existing Confirm dispatch; no caller tenant override. |
| `tank/command.py:35` | Register M1 tools/adapters and prepare exact owned previews; existing SQUADS and permission logic unchanged. |
| `tank/trigger_routes.py:48` | Code parses explicit M1 commands before existing W1 planning. |
| `tank/main.py:106`, `:805`, `:4684` | Publisher starts after startup guards, cancels before pool shutdown; mount API. |
| `tank/case_study_sources.py:179` | Actual publication/reply counts as metadata on the existing draft figure; tenant, receipt region and date scoped. No new report labels. |
| `workspace/app/oauth/trigger-gbp/callback/route.ts:1` | Existing authenticated server transport completes OAuth, then returns to `/chats`; no new page or reflected exchange data. |
| `.env.example:505`, `docker-compose.yml:240`, `docker-compose.za.yml:137` | Names-only OAuth forwarding; exact setting locations listed in ops instructions. No values. |
| `docs/ops/TRIGGER-GBP.md:1` | Official access/client/scope/redirect instructions, existing-card workflow, recovery semantics and founder acceptance steps. |
| `tests/trigger_m1/test_marketing.py:1` | Offline state/length/concurrency/retry/DST/Confirm/reply/OAuth tests. |
| `tests/trigger_m1/test_m1_storage.py:1` | Actual W1 Confirm cards, customer-data prompt boundary, native RLS/startup guards and credential redaction. |
| `tests/trigger_m1/test_m1_queue.py:1` | Eligible-tenant queue, known manual retry and confirmed cancellation of uncertain deliveries. |
| `tests/trigger_m1/test_m1_metrics.py:1` | Existing report keys and actual count provenance across tenant/region/date boundaries. |
| `tests/trigger_m1/callback_contract.cjs:1` | Actual Workspace callback tested with fake transport and outside fetch refused. |

## Review corrections 1–7

| Review | File and line | Verified change |
|---|---|---|
| 1 | `tank/trigger_google.py:43`, `:55`, `:142`; `tests/trigger_m1/test_m1_delivery.py:1` | Refresh failures and POST ConnectError/ConnectTimeout are unsent/retryable; only possibly sent publishing failures are uncertain. 20-case HTTP phase matrix; existing three-attempt/backoff test now covers 503 and 429. |
| 2 | `tank/schema.sql:2464`, `tank/trigger_publisher.py:44`, `tank/trigger_marketing.py:95`, `:146`; `tests/trigger_m1/test_m1_reconcile.py:1` | Persist claim time. Uncertain cancellation works. Confirmed retry paginates location posts: same summary created after claim adopts name/searchUrl without a POST; no match permits one retry. Failed/incomplete reads retain uncertainty. Six actual-Confirm recovery tests pass. |
| 3 | `tank/trigger_google.py:190`; `tests/trigger_m1/test_m1_oauth_review.py:1` | Revocation accepts 200 or explicit 400 invalid_token; other responses retain the sealed token and raise. |
| 4 | `tank/command.py:1250`; `tests/trigger_m1/test_m1_paid.py:1` | The two model-capable routes are paid_run and execute the existing paid guard before dispatch; code-only tools keep defaults. Three tests pass. |
| 5 | `tank/trigger_google.py:98`, `:134`; `tests/trigger_m1/test_m1_oauth_review.py:36` | Confirmed reconnect revokes the previous grant before new consent and clears the old ciphertext. Callback refuses to overwrite an installed token. Reconnect and revocation tests: eight passed. |
| 6 | `tests/trigger_m1/test_m1_dst.py:1` | Both 2026-11-01 01:30 offsets (-07:00 and -08:00) are on November 1 in the actual SQL calendar and date filter. Two tests pass. |
| 7 | This file; `review-verification.txt`; PR description | Current implementation head, exact commands/results, final-head CI record, and after-merge acceptance. |

Paid (`paid=True`, `kind="paid_run"`): `trigger.post.create`,
`trigger.gbp.reply.draft`. Post creation remains classified as model-capable even
when a particular request reuses an existing `write_id`.

Code-only (default `paid=False`, `kind="other"`): `trigger.post.edit`,
`trigger.post.approve`, `trigger.post.schedule`, `trigger.post.cancel`,
`trigger.post.retry`, `trigger.posts`, `trigger.calendar`, `trigger.gbp.connect`,
`trigger.gbp.locations`, `trigger.gbp.location.select`, `trigger.gbp.disconnect`,
`trigger.gbp.reviews`, `trigger.gbp.reply.edit`, `trigger.gbp.reply.send`.

## Validation and after-merge acceptance

**CI's `tank` job on the final PR head is the full-suite test of record.** The
exact final head, job link and result are recorded in the PR description after
its run completes; recording that result does not create another git head.
Local focused commands/results are in `review-verification.txt`. Historical
pre-review runs remain in `verification.txt` and are not the final CI record.

All **65 M1 tests passed** with external sockets blocked. The current broader
Trigger/Command selection passed **529 tests, with 2 skips** (separate CRM WSGI
runtime and the after-merge Trigger/LanguageTool check). Ruff passed. Exact
results are recorded in the review evidence.
Main advanced during the final required fetch and merged cleanly. The merged
head was checked with the full M1 selection and the new Zenas Command tests;
its captured result is in `review-verification.txt`. No actual model call was
used to test or check this work.

**After merge:** the founder runs Custom Nation in his own browser, connects its
actual profile, approves/schedules three real posts, sees one appear on Google,
and confirms a real review reply before it appears. The real Trigger/internal
LanguageTool check also follows after merge. Screenshots of that founder test
are not available before it runs; none is fabricated here.

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

Google's create-post endpoint has no documented request-id/idempotency field.
Possibly sent failures never automatically repeat a POST. A confirmed retry
first reconciles the location's complete paginated list by exact summary and
creation after the claim. A match is marked published with its returned ID/link;
a complete read without a match permits one retry. Cancellation works before
published; failed reads or changed profile binding do not authorize another POST.
[Official list reference](https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts/list)
and [LocalPost fields](https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts)
checked 3 November 2026. Actual public visibility is checked after merge.
