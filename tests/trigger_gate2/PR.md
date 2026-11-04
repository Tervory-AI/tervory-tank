# Trigger Gate 2: tenant admins, long checks and accepted page copy

Branch: `codex/trigger-gate2`. Isolated checkout: `/workspace/codex-trigger-gate2`.
Original Gate 2 validated code head: `4d953ff00833f6ce2ce395f7a7ef1330cf45eacb`, incorporating
main `7a5132fadf30f1cb10e5c55c1d3cc216524dd64b`. The review correction and its validation are recorded below. Claude opens the PR; founder reviews and merges.

**Offline implementation and the requested tests pass. Live founder acceptance
and its screenshots are pending.** The existing Command-to-Tisan runtime
integration limitation below must be resolved before claiming the full live
Chats-to-generated-site journey works.

## Changes

| File and line | Result |
| --- | --- |
| `tank/command.py:102` | Reuse `Actor.tenant_admin`, already derived by the existing Clerk user/org/tenant binding, to expose all Trigger tools to that tenant's verified admin. No new squad or grant. Ordinary members retain their existing restrictions. |
| `tank/command.py:900` | Optional page objects carry a page name and a `copy` write UUID. Existing page-name strings remain valid. No raw body copy is accepted in that field. |
| `tank/command.py:937`, `agents/trigger/service.py:16` | Long checks fit the existing 32,000-byte Command action envelope. The room additionally bounds the whole document at 32,000 characters; writing stays at 20,000. UTF-8/JSON envelope size remains enforced by `validate_action`. |
| `agents/trigger/checkers.py:164` | Lossless splitting at headings, then paragraphs, then word boundaries, with a hard fallback for an uninterrupted word. Every piece is less than 20,000 characters. No model splits or checks text. |
| `agents/trigger/checkers.py:180` | Translate piece offsets and line/column locations into whole-document positions, including LanguageTool's UTF-16 offsets around supplementary Unicode characters. Findings that refer to the whole document, such as an absent required term, retain their document-level meaning rather than acquiring an invented position. |
| `agents/trigger/checkers.py:206` | Aggregate completeness, errors, issue totals and checker receipts. Keep the first 200 findings and explicit truncation; missing-term and fence checks do not become false findings just because a document was split. Existing report wording remains unchanged. |
| `agents/trigger/service.py:22`, `agents/trigger/app.py:63` | Preserve the separate 20,000-character private LanguageTool input bound and writing bound. Only the whole-document check input grows. |
| `tank/trigger_routes.py:42` | The existing attachment flow can check a document over the composer's 20,000-character message limit in one action. With an empty `Trigger, check:` prefix and one text attachment, retrieve that owned turn's actual attachment, without including its transport label in the checked document. The existing action envelope still applies; arbitrary 200,000-character attachments do not bypass it. |
| `tank/trigger_routes.py:110` | A fixed, authenticated Tisan-to-Tank read corridor returns only that job tenant's currently accepted write whose original Command write card is confirmed. Validate room authentication, tenant and home box. Return private/no-store data. |
| `tank/trigger_routes.py:168` | Write and check dispatch require the existing executing Confirm-card binding to tenant, user, tool and exact arguments. Voice and feedback retain that same binding. Revoked authority is rechecked by the existing Command confirmation flow. |
| `agents/tisan/scaffold.py:78`, `:253`, `:314`, `:510` | Normalize per-page write references, resolve them through the fixed Tank corridor before creating build files, and escape the accepted body with the existing `_jsx_text`. Extra pages without references render their heading with no body paragraph; pages with references render only the escaped accepted body. Standard template pages without references remain unchanged. Preserve the existing contact form. Missing, foreign, unaccepted, malformed or unavailable copy fails closed; the brief cannot supply its own resolved text. |
| `tank/trigger_learning.py:43` | Record confirmed acceptance/change/rejection in the existing receipt feedback fields consumed by `case_study_sources.trigger()`. The write ID, confirmed card, tenant, receipt ID, task and region must match. Existing private training-pair behavior is retained. |
| `tests/trigger_gate2/test_gate2.py:73`, `:104` | Real disposable-Postgres and HTTP confirmation tests: admin write/check/feedback in own tenant, no squad grant, denied ordinary member, forged credential, stale/cancelled card, revoked admin role, foreign tenant/user/card and cross-tenant feedback. Direct unconfirmed dispatch is refused. |
| `tests/trigger_gate2/test_gate2.py:118`, `:148`, `:172`, `:191`, `:339` | One confirmed long-document request, source offsets, UTF-16/line/column locations, byte/character bounds, lossless pieces, aggregate 200-finding truncation, partial results, whole-document required terms/fences and the private checker input bound. |
| `tests/trigger_gate2/test_gate2.py:202`, `:236`, `:274`, `:303`, `:321` | Actual accepted-write lookup through the authenticated route into a generated archive; escaping, tenant isolation, preserved default pages, retained form, duplicate/raw-copy refusal and fail-closed lookup failures before build creation. |
| `tests/trigger_gate2/test_gate2.py:256` | A write is generated through a deterministic test substitute, confirmed and accepted through the real flow. Its draft, acceptance and checker figures appear for that tenant/region only. |
| `tests/trigger_gate2/admin_contract.cjs:1` | Exercise the unchanged real Clerk binding and Workspace header writer: user, org and mapped tenant must match; injected role/user/tenant/squad headers cannot supply admin authority. |

The earlier first/second-build tests now use confirmed writing/checking where
required and expect the requested admin entitlement. Their existing isolation,
revocation, receipt and learning assertions remain. Approved skill packages,
Workspace components/copy, provider routes, schema, worker, pricing, sign-in,
settings and runtime configuration files were not changed.

## Exact checks

All commands ran on Boston in `/workspace/codex-trigger-gate2`, with an existing
Python 3.12 test environment and a read-only link to existing Node dependencies.
The only PostgreSQL container created for this task was `codex-trigger-gate2-pg`,
published on loopback port 32782 with disposable trust authentication. No
production SQL, production fixture data, actual secret access, model/provider
call or deployment was used. The writer's model route is a deterministic test
substitute. The accepted-copy archive test substitutes npm check results; it
proves lookup and generated source, not a real npm build or live browser result.

```bash
node tests/trigger_second_build/admin_contract.cjs
# PASS: existing Clerk session user/org/tenant binding and forged-header refusal.
node tests/trigger_gate2/admin_contract.cjs
# PASS: verified Clerk user/org/tenant admin binding; forged role/user/tenant/squad headers cannot grant Trigger authority.

TMPDIR=/home/ammosync/.codex/trigger-gate2/tmp \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32782/trigger_gate2 \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest \
  tests/trigger_first_build tests/trigger_second_build tests/trigger_gate2 \
  tests/test_tisan_*.py -q --tb=short --disable-warnings \
  --disable-socket --allow-hosts=127.0.0.1,localhost
# 109 passed, 1 skipped, 14 warnings in 42.68s.

TMPDIR=/home/ammosync/.codex/trigger-gate2/tmp \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32782/trigger_gate2 \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest \
  tests/test_command.py tests/test_case_study_reports.py \
  -q --tb=short --disable-warnings --disable-socket \
  --allow-hosts=127.0.0.1,localhost
# 96 passed, 13 warnings in 61.14s.

/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m ruff check \
  tank/command.py tank/trigger_routes.py tank/trigger_learning.py \
  agents/trigger/app.py agents/trigger/checkers.py agents/trigger/service.py \
  agents/tisan/scaffold.py tests/trigger_gate2 \
  tests/trigger_first_build/test_trigger.py \
  tests/trigger_second_build/test_second.py --select E9,F
# All checks passed.
git diff --check
# PASS.
```

The one skip is
`tests/trigger_first_build/test_trigger.py::test_real_room_with_internal_languagetool`:
its opt-in `TRIGGER_INTERNAL_CHECKER_TEST=1` environment and isolated LanguageTool
container were not supplied. Database-backed Gate 2 tests ran; they were not
skipped. Existing Pydantic/FastAPI deprecation/name warnings are non-fatal.
Hosted CI has not been claimed: the founder's workflow leaves PR creation to
Claude. Full command output is also retained locally in
`/home/ammosync/.codex/trigger-gate2/focused-final.log` and
`/home/ammosync/.codex/trigger-gate2/command-case-study.log`.

## Deployment and live acceptance boundary

Merge would deploy Tank (Boston and ZA), Trigger and Tisan because their source
paths changed. There is no compose/settings/schema change, new credential name,
new paid route or new model fallback. Revert code to roll back; existing tenant
voices, writes, feedback and history remain in their existing stores.

**Existing runtime integration requiring review:** Command's Tisan adapter is
`/v1/skala/tisan.scaffold/run` (`tank/command.py`). The existing approved-version
wrappers in `tank/skills/tisan.scaffold/*/run.py` load `agents/tisan/scaffold.py`
from a repository layout or `/app/scaffold.py`. The repository's Tank image
(`tank/Dockerfile`) does not copy either location. `tank/main.py` sends Tisan
evals to its room (`run_room_eval`), while ordinary skill execution uses the
local skill runner. This task did not change protected runtime routing,
Tank packaging or immutable approved wrappers to work around that boundary.
The accepted-copy implementation is exercised through Tisan's existing room
`scaffold.execute` path. Passing its source/archive tests does not establish
that the current live Command adapter can run that room-local builder. A
reviewed runtime integration is required for that entry point unless an
existing deployment supplies it outside the repository image definition.

The founder's live test remains: save Custom Nation's real notes with Confirm,
write in that voice, accept the write, attach and check a bounded document over
20,000 characters in one action, and render the accepted write by ID in a Tisan
page. Repeat with the actual tenant admin and check another tenant is denied.
Live founder screenshots and that browser acceptance are pending. All test
voices, draft text and generated archives stayed in the disposable test scope.


## Founder review correction: no default page sentence

Reviewed code head: `675bc1afc3363a8aa704bcb489ae905be0fed898`.
`agents/tisan/scaffold.py:253` now emits no body paragraph when copy is absent.
With accepted copy it emits only that escaped text in the existing paragraph.
`tests/trigger_gate2/test_gate2.py:303` writes actual generated page files in both
cases and asserts the default sentence is absent; the no-copy case has no
paragraph, and the accepted-copy case has exactly the expected escaped body.
The earlier default-rendering test now requires heading-only output.

```bash
TMPDIR=/home/ammosync/.codex/trigger-gate2/tmp \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest \
  tests/test_tisan_scaffold.py \
  tests/trigger_gate2/test_gate2.py::test_copy_defaults_legacy_rendering_and_standard_page_content \
  tests/trigger_gate2/test_gate2.py::test_extra_pages_never_write_default_sentence \
  -q --tb=short --disable-warnings --disable-socket --allow-unix-socket
# 14 passed, 3 warnings in 1.86s.
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m ruff check \
  agents/tisan/scaffold.py tests/trigger_gate2/test_gate2.py --select E9,F
# All checks passed.
git diff --check
# PASS.
```

Unix sockets are permitted only for asyncio's local event-loop self-pipe;
network sockets remain blocked. No database, model or live site was used for
this review correction. The source code head above is followed only by this
report update.
