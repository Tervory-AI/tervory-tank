# Trigger W3 gate 3: WhatsApp through the shared bot engine

Branch `codex/trigger-w3`, same [PR #624](https://github.com/Tervory-AI/tervory-tank/pull/624).
Final code/test head: `d5b888773a4f8b180beedc1df8ca246f58ae06a1`.
The combined run began at `b329e0eaa7499b2627586842c2f6c8dd9d1de149`;
the final B3 run also covers the subsequent strict raw-character-cap fix.
The evidence commit follows that head. Gate 1 remains reviewed/passed. No main
merge, PR creation, label, deployment, production SQL or live message send.

The founder superseded the initial pricing stop with a hard 1,000-attempt cap,
then corrected the calendar boundary to the founder-supplied account timezone.
Each binding has `tenant_id`, `token_env`, and `timezone`; Python `zoneinfo`
validates the IANA name. There is no timezone default. Missing/invalid zones,
missing tokens, exhausted budgets and closed/invalid service windows hand over
through the existing email, without a WhatsApp response or answer-model call.

## Official sources checked 3 November 2026

| Topic | Official URL | Decision |
|---|---|---|
| Free tier and account month | https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing#free-tier-of-monthly-service-messages | Per business phone, 1,000 free delivered service messages monthly; charging starts at 1,001. Reset is midnight in the Messaging account timezone. Attempts are conservatively counted before sending and never refunded. |
| Customer-service window | https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing#customer-service-window-csw | Only free-form text inside the 24-hour window opened/reset by a customer message. No templates. |
| Verification and signature | https://developers.facebook.com/docs/graph-api/webhooks/getting-started/ | Constant-time verify-token comparison and matching GET challenge; raw-body HMAC-SHA256 before JSON parsing. |
| Incoming messages | https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components/ | Read the signed metadata phone_number_id and text messages only; ignore contacts, statuses and unknown numbers. |
| Text send | https://developers.facebook.com/docs/whatsapp/cloud-api/messages/text-messages/ | POST /{phone-number-id}/messages, bearer token, type=text. Official example names Graph v26.0; that version is used. |
| Send reference | https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages/ | Fixed Graph endpoint and text payload, no template or retry path. |

The web reader returned a login screen for pricing; public direct HTTP fetches
returned 200 and the pricing content, including the account-timezone reset.
Full operational instructions and source findings are in `docs/ops/TRIGGER-META.md:111`.

## File and line manifest

| File and line | Change |
|---|---|
| `tank/trigger_whatsapp.py:35`, `:69` | Founder bindings and validated account-local month, never a UTC/regional fallback. |
| `tank/trigger_whatsapp.py:87`, `:104` | Current-month totals and atomic conditional allowance reservation, capped at 1,000 and committed before HTTP. No refunds. |
| `tank/trigger_whatsapp.py:145`, `:219` | Keyed opaque visitor, tenant/conversation-sealed sender, durable inbound/send claim, shared engine, bounded linked text, window/month recheck and existing hand-over email. Failures never replay sends or expose provider data. |
| `tank/trigger_whatsapp.py:256`, `:268` | Constant-time GET challenge; raw signature check before parsing; unknown numbers store nothing; explicit tenant scope from the binding only. |
| `tank/trigger_bot.py:156`, `:186` | Optional forced hand-over and transactional reply gate; web callers retain their defaults and the same grounding, receipt, lead-draft and email behavior. |
| `tank/trigger_bot_api.py:206`, `:338` | Monthly reply total under the existing `count` label; mount the signature-authenticated public router. Weekly stats include WhatsApp messages. |
| `tank/schema.sql:2807`, `:2818`, `:2826`, `:2832` | Widen the web-only channel CHECK to web/whatsapp; add a sealed sender column, monthly budget and cascading event claims above generated memory; conditional ENABLE/FORCE RLS, permissive tenant_access plus restrictive tenant_boundary exactly as personal_tokens. Unique phone/month budget prevents replenishment by tenant rebinding. |
| `workspace/app/v1/bot/whatsapp/route.ts:1` | Explicit regional target with no fallback, raw bounded POST forwarding, private GET verification transport, empty failure/POST responses and no identity forwarding. No page. |
| `workspace/middleware.ts:23` | Public-path registration for this independently signature-authenticated webhook, following the existing public bot door. |
| `.env.example:531`, `:538` | Names-only app secret, verify token, binding map and connector token slot, documenting the timezone key. |
| `docker-compose.yml:251`, `docker-compose.za.yml:148` | Forward only the authorized WhatsApp setting names to each regional Tank. |
| `docs/ops/TRIGGER-META.md:111` | Supersede pricing stop with authorized cap/timezone behavior, source URLs/check date, setup and real-device acceptance instructions. |
| `tests/trigger_bot_b3/test_whatsapp.py:1` | Actual shared engine and native disposable SQL/vault with httpx.MockTransport: HMAC-before-parse, challenge, unknown IDs, source/FAQ/foreign-source handling, cap/concurrency, local-month boundaries, failure/crash replay, email, lead drafts, retention, native RLS, rebinding and abuse/window refusal. |
| `tests/trigger_bot_b3/public_contract.cjs:1` | Actual Workspace route and existing Count card with fake fetch: raw bytes, both regions, limits, challenge, no identity forwarding, no reflected private data. |
| `tests/trigger_bot_b3/test_whatsapp_workspace.py:1` | Run that actual TypeScript transport/card contract under the offline CI test suite. |
| `tests/trigger_w3/GATE3.md:1` | This gate's implementation, source, file/line and verification evidence. |

The schema **widens the existing channel constraint and removes no table,
column or row**. Its idempotent block replaces only the old web-only CHECK.
The generated memory block remains last. `tank/main.py:_startup` at lines
755–810 was read before schema pushes: guards and schema application precede
the bot retention and publisher loops. Existing 12-calendar-month retention
deletes the conversation's sealed sender and cascading claims; aggregate
account counters remain, so customer deletion cannot replenish the cap.

## Verification

All commands below ran in `/workspace/codex-trigger-w3`, using only placeholder
credentials, fake model/SMTP/Meta services and an owned, passwordless disposable
Postgres on loopback port 47097. Outside sockets and DNS were blocked by the
repository's offline test harness. Node contract tests use fake fetch.

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:47097/postgres PYTHONPATH=.gate2-deps:tank .venv/bin/python -m pytest -q -n 4 tests/trigger_bot_b3/test_whatsapp.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --timeout=120 --tb=short
```

**10 passed**, 12 warnings, 19.22 seconds. Tests include replies 999 and 1,000,
no send for 1,001, two simultaneous HTTP webhooks contending for the last slot,
committed counter/send state observed by fake Meta before send, no refund or
replay after crash/failure, and the same capped sender replying again at the
account-local month boundary in Johannesburg and Los Angeles. Missing/invalid
timezones hand over and never retrieve/generate/send.

```sh
PYTHONPATH=.gate2-deps:tank .venv/bin/python -m pytest -q tests/trigger_bot_b3/test_whatsapp_workspace.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --timeout=120 --tb=short
```

**1 passed**, 1.14 seconds.

After the full raw-character-cap edge case was added, the final focused run was:

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:47097/postgres PYTHONPATH=.gate2-deps:tank .venv/bin/python -m pytest -q -n 4 tests/trigger_bot_b3 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --timeout=120 --tb=short
```

**11 passed**, 12 warnings, 36.72 seconds. This includes the real Workspace
transport and rejects overlong raw text even when the excess is padding spaces.

```sh
TMPDIR=/workspace/codex-trigger-w3/.gate1-tmp POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:47097/postgres COMMAND_TEST_TOOLS=/workspace/codex-trigger-w3/workspace/node_modules PYTHONPATH=.gate2-deps:tank .venv/bin/python -m pytest -q -n 4 --dist load tests/test_trigger*.py tests/test_command*.py tests/test_base_lists.py tests/trigger_first_build tests/trigger_second_build tests/trigger_gate2 tests/trigger_bot_b1 tests/trigger_m1 tests/trigger_m2 tests/trigger_bot_b3 tests/test_secrets.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --timeout=120 --tb=short --durations=10
```

**845 passed, 2 skipped**, 302 warnings, 448.19 seconds, with one existing
hand-over limiter assertion failure and one missing-dependency collection error.
The limiter test makes six calls against a live minute clock; its last call
being sent is consistent with a minute-boundary rollover under parallel load.
That clock diagnosis is an inference; the unchanged test passed in isolation. The collected Zenas
module required the cleaned local `docxtpl` dependency. Neither was a B3 or
M1/M2 failure. The following isolated rerun restored the dependency and cleared
both, without changing production limiter behavior or existing test assertions:

```sh
.venv/bin/pip install --disable-pip-version-check docxtpl==0.20.2 Mako==1.4.2
TMPDIR=/workspace/codex-trigger-w3/.gate1-tmp POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:47097/postgres COMMAND_TEST_TOOLS=/workspace/codex-trigger-w3/workspace/node_modules PYTHONPATH=.gate2-deps:tank:tests/trigger_bot_b1 .venv/bin/python -m pytest -q tests/trigger_bot_b1/test_b1_review.py::test_mail_visitor_and_tenant_hold_keeps_handover_without_send tests/test_command_zenas_z3.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --timeout=120 --tb=short
```

**8 passed**, 14 warnings, 35.49 seconds, at final code/test head. Every collected
existing Trigger/B1/M1/M2 case passed across these runs; the combined invocation
itself is not represented as a single clean run. Two cases were skipped; full hosted-CI coverage is not claimed. The eleven final B3 cases separately pass above.

```sh
node workspace/node_modules/typescript/bin/tsc --noEmit --incremental false --project workspace/tsconfig.json
COMMAND_TEST_TOOLS=/workspace/codex-trigger-w3/workspace/node_modules node tests/trigger_bot_b3/public_contract.cjs
COMMAND_TEST_TOOLS=/workspace/codex-trigger-w3/workspace/node_modules node tests/trigger_bot_b1/public_contract.cjs
COMMAND_TEST_TOOLS=/workspace/codex-trigger-w3/workspace/node_modules node tests/trigger_m2/callback_contract.cjs
/home/ammosync/trigger-crm-venv312/bin/ruff check tank/trigger_whatsapp.py tank/trigger_bot.py tank/trigger_bot_api.py tests/trigger_bot_b3 --select E9,F --output-format concise
git diff --check
```

All passed. No TypeScript output/errors. The three actual Workspace contracts
printed PASS; Ruff printed `All checks passed!`. Full schema was also applied
twice successfully, and B3's native RLS test applies it twice after rollout,
uses a non-bypass role and checks foreign-row refusal even with an extra
permissive policy.

### Local setup and initial failures

Shared dependency paths from the earlier gates had been cleaned. Restored local
dependencies only, without editing repository requirements:

```sh
.venv/bin/pip install --disable-pip-version-check selectolax==0.3.27 rapidfuzz==3.10.1
# First pgserver restoration used --ignore-installed --no-deps; the next command restored its dependencies.
.venv/bin/pip install --ignore-installed --no-deps pgserver
.venv/bin/pip install --disable-pip-version-check pgserver
.venv/bin/pip install --disable-pip-version-check cryptography==50.0.2
.venv/bin/pip install --disable-pip-version-check -r agents/trigger/requirements.txt
.venv/bin/pip install --disable-pip-version-check redis==5.2.1 tiktoken==0.14.0
# In workspace/, replace the stale shared node_modules symlink, then:
npm ci --ignore-scripts --no-audit --no-fund
```

All succeeded. The owned Postgres was restarted against its restored local
binary. Initial B3 runs failed because the running shared PostgreSQL library
path was removed, a placeholder vault fixture was 31 bytes instead of 32, and
the vault dependency was absent. After repairing local setup and correcting
the fixture, all focused cases passed. The first combined run before all
restoration finished reported 609 passed, 1 failed, 1 skipped and 88 errors;
the failure/setup/collection errors were missing proselint/redis imports.
The standalone repaired M2 run passed all 17 test_meta.py cases (125.81 seconds).
The repaired combined run and isolated follow-up above supersede those setup
failures; the original attempt is not claimed as a passing run.

Every completed file was committed and pushed to `origin codex/trigger-w3`.
Every push succeeded. No main merge or force push.

## Hosted CI and real-device acceptance

GitHub returned no PR-triggered workflow runs for full implementation head
`b329e0eaa7499b2627586842c2f6c8dd9d1de149`; exact evidence-head results are to be
recorded in the PR after this evidence is pushed. Hosted Tank/Workspace success
is not claimed. PR metadata still reports draft/open and mergeable:false;
main/base/labels/merge state were left untouched.

The founder supplies values for the names above, an existing vault key and
handover-email configuration, registers the app/number and copies its actual
account timezone. The free-only allowance requires the number's entire service
budget to be available to this corridor in one regional deployment; sends
elsewhere are not visible to its local counter. Do not activate it mid-month
on a number whose allowance was already consumed elsewhere.

Real acceptance is the founder's own phone/test number and tenant: receive an
own-source reply with links, ask an unsupported question and receive the existing
handover email, then view WhatsApp-inclusive weekly stats and the existing
monthly Count in `/chats`. **No founder screenshots or live acceptance evidence
exist from this build.** No secret value, live model request, SMTP delivery,
customer data or production schema was accessed for verification.
