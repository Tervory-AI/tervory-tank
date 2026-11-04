# Trigger W3 gate 2: Facebook Page publishing

Branch `codex/trigger-w3`, same [PR #624](https://github.com/Tervory-AI/tervory-tank/pull/624).
Gate 1 remains reviewed/passed at `ec3b330d`. Gate 2 implementation/test head:
`ba96378f4990d5397b642a7ae28ad3effc228ab6`; this evidence is committed afterwards.
Gate 3 has not started. No main merge, new PR, label, merge or deployment.

Approved and scheduled Facebook text posts now use M1's durable publication
corridor with the tenant's selected Page and sealed grant. Existing cards expose
Facebook `status` and `url` through their existing labels; no page or visible
wording was added. No model call or paid service was added. Instagram requires
image/video media that posts do not have today, so Instagram, LinkedIn and X
remain scheduled-only and are never claimed.

## File and line manifest

| File and line | Change |
|---|---|
| `tank/trigger_meta.py:30`, `:60`, `:83`, `:104` | Meta v26.0, private bounded transport reused from Google, scrubbed errors, one-use tenant/user state and confidential code exchange. |
| `tank/trigger_meta.py:187`, `:208`, `:216`, `:233`, `:244`, `:276`, `:287` | Verified Page selection, tenant/generation vault context, Page-owned publishing/reconciliation, returned permalink, revocation and disconnect. Tokens are transient only while calling Meta; none is returned or logged. |
| `tank/schema.sql:2762` | Two additive/idempotent tenant tables above generated memory. Conditional ENABLE/FORCE RLS, permissive tenant access plus restrictive tenant boundary mirror GBP/personal_tokens. |
| `tank/trigger_marketing_contract.py:80`, `:105` | Page-selection payload and four Meta tools; existing admin/Confirm registration is reused. |
| `tank/trigger_marketing_api.py:34`, `:63`, `:84`, `:110`, `:215` | Code-only command planning, owned selection/generation previews, execution and authenticated callback with $0 receipts. |
| `tank/trigger_marketing.py:25`, `:115`, `:127`, `:155`, `:199`, `:224` | Page-bound approval/scheduling, confirmed reconciliation, bounded link-only recovery, existing Status/Result aliases and collection data, unsupported-channel due metadata. |
| `tank/trigger_publisher.py:35`, `:58`, `:71`, `:128` | Claim only GBP or eligible connected Facebook rows; preserve M1 lease, durable claim, row locks, three-attempt backoff, uncertain-delivery guard and code receipts. |
| `workspace/app/oauth/trigger-meta/callback/route.ts:1` | Exact GBP server-transport callback pattern; authenticated active tenant, bounded parameters, fixed `/chats` return, no reflected exchange data. |
| `.env.example:528`, `docker-compose.yml:249`, `docker-compose.za.yml:146` | Only the two requested setting names, beside Google's names. Founder supplies values. Explicit same-branch gate authorises this runtime wiring; merge deploys the main app and ZA Tank. |
| `docs/ops/TRIGGER-META.md:1` | Official sources/date, founder registration/settings/redirect, Page access/App Review/PKCE boundary, existing-card acceptance and delivery behaviour. |
| `docs/ops/TRIGGER-GBP.md:7` | Link to M2 and correct current scheduled-only channel boundary. |
| `tests/trigger_m2/test_meta.py:137` | Native SQL/vault/cards with fake Meta: state, tenant isolation, tokens, actual once-only publish, crash, retries, refusal, link recovery and disconnect. |
| `tests/trigger_m2/test_safety.py:25`, `:60`, `:106`, `:135`, `:162` | Native RLS and stale-state/binding refusals, complete/incomplete reconciliation, send-phase failures, malformed links, boolean revocation and safe pagination. |
| `tests/trigger_m2/callback_contract.cjs:1` | Actual Workspace callback and presentation modules with fake transport; existing Status/Result labels and no reflected code/token. |
| `tests/trigger_m1/test_marketing.py:192` | Update the obsolete Facebook scheduled-only assertion; retain it for Instagram, LinkedIn and X. |
| `tests/trigger_w3/GATE2.md:1` | Review evidence and outstanding founder/CI acceptance. |

`tank/main.py:755`, `:780`, `:782`, `:810` was inspected before pushing: startup
applies the schema after the existing guards and before the publisher starts.
It required no edit. `tank/Dockerfile:17` already copies `*.py`, so the new module
is included without changing Dockerfile. No other shared lines were reorganised.

## Official Meta sources

**Every URL below was checked on 3 November 2026**, directly from Meta.
The web reader returned HTTP 429. Direct public-document requests returned 200;
no authenticated Graph API request was made during research.

| Topic | Official URL | Verified boundary |
|---|---|---|
| Business login | https://developers.facebook.com/docs/facebook-login/facebook-login-for-business/ | Business-compatible app; manual user-token flow permits scopes without an obligatory configuration ID. |
| Manual code flow | https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/ | Exact redirect, state, server-side exchange; no PKCE advertised for this selected web flow. |
| Login security | https://developers.facebook.com/docs/facebook-login/security/ | Confidential server-side token use; no tokens delivered to the browser. |
| Current version | https://developers.facebook.com/docs/graph-api/changelog/ | Latest Graph API `v26.0`, released 29 July 2026. |
| Publish permissions/call | https://developers.facebook.com/docs/graph-api/reference/page/feed/ | Page token, CREATE_CONTENT, pages_show_list, pages_read_engagement, pages_manage_posts; POST /{page-id}/feed. |
| Publishing guide | https://developers.facebook.com/docs/pages-api/posts/ | Text message publication; Tank sends at its own due time rather than scheduling twice. |
| Page discovery | https://developers.facebook.com/docs/pages-api/getting-started/ | Discover the user's permitted Pages via /me/accounts. |
| Long-lived Page token | https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/ | Derive the Page token from a long-lived user token; invalidation remains possible. |
| Own Page before App Review | https://developers.facebook.com/docs/graph-api/overview/access-levels/ | Standard Access for app-role users; founder must have the Page task. Unrelated clients need Advanced Access/App Review and applicable Business Verification. |
| Revocation | https://developers.facebook.com/docs/facebook-login/guides/permissions/request-revoke/#revokelogin | DELETE /me/permissions; clear sealed state only after successful revocation, retain on failure. |
| Permalink | https://developers.facebook.com/docs/graph-api/reference/page-post/ | Read permalink_url from the returned post ID; never invent a link. |
| Reconciliation | https://developers.facebook.com/docs/graph-api/reference/page/published_posts/ | Bounded pagination of that Page's published posts; never follow credential-bearing next URLs. |
| Error handling | https://developers.facebook.com/docs/graph-api/guides/error-handling/ | Back off known transient refusals; keep possibly-sent failures uncertain without automatic replay. |
| Instagram | https://developers.facebook.com/docs/instagram-platform/content-publishing/ | Image/video media required, absent from current posts. |

## Exact verification commands and results

All commands ran in `/workspace/codex-trigger-w3`. Real values were never read
or supplied. Local tests used only placeholder credentials and a passwordless,
disposable loopback Postgres owned by this checkout.

Existing Gate 1 Python/Workspace dependencies were reused. Added only the
repository's test pins to an ignored local target:

```sh
TMPDIR=/workspace/codex-trigger-w3/.gate1-tmp .venv/bin/python -m pip install --no-deps --target .gate2-deps pytest-socket==0.8.1 pytest-timeout==2.4.0
TMPDIR=/workspace/codex-trigger-w3/.gate1-tmp .venv/bin/python -m pip install --upgrade --target .gate2-deps pytest==9.1.1 pytest-asyncio==1.4.1 pytest-xdist==3.8.0 pytest-timeout==2.4.0 pytest-socket==0.8.1
```

Both succeeded. The bundled `pgserver` binary created `.gate2-pg` with trust auth
and loopback-only listening. Initial port 55439 was occupied; no existing server
was touched. A dynamically selected free port, 57527, succeeded. Full
`tank/schema.sql` was applied **twice** with asyncpg successfully. Native tests
also verify conditional RLS twice with a non-bypass role and foreign-row denial.

```sh
TMPDIR=/workspace/codex-trigger-w3/.gate1-tmp POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:57527/postgres PYTHONPATH=.gate2-deps:tank .venv/bin/python -m pytest -q tests/trigger_m2 tests/trigger_m1 --disable-socket --allow-hosts=127.0.0.1,localhost --timeout=60 --tb=short
```

**101 passed**, no skips, 15 warnings, 197.26 seconds. This includes all M1 tests
and the initial 34 M2 cases with real disposable SQL and fake Meta transport.

```sh
TMPDIR=/workspace/codex-trigger-w3/.gate1-tmp POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:57527/postgres COMMAND_TEST_TOOLS=/workspace/codex-trigger-w3/workspace/node_modules PYTHONPATH=.gate2-deps:tank .venv/bin/python -m pytest -q -n 4 --dist loadfile tests/test_trigger*.py tests/test_command*.py tests/test_base_lists.py tests/trigger_first_build tests/trigger_second_build tests/trigger_gate2 tests/trigger_bot_b1 tests/trigger_m1 tests/trigger_m2 tests/test_secrets.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --timeout=120 --tb=short --durations=10
```

**837 passed, 2 skipped**, zero failures, 302 warnings, 310.87 seconds. Broad run
started on implementation head `4df6cb5b4f8733d966c8b7fb41e2ca4eb3544d8f`.
The later malformed-permalink guard and five added edge cases were verified by:

```sh
TMPDIR=/workspace/codex-trigger-w3/.gate1-tmp POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:57527/postgres PYTHONPATH=.gate2-deps:tank .venv/bin/python -m pytest -q tests/trigger_m2/test_safety.py -k 'bad_permalink or boolean_revocation or page_pagination' --disable-socket --allow-hosts=127.0.0.1,localhost --timeout=60 --tb=short
TMPDIR=/workspace/codex-trigger-w3/.gate1-tmp POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:57527/postgres PYTHONPATH=.gate2-deps:tank .venv/bin/python -m pytest -q -n 4 --dist loadfile tests/trigger_m2 tests/test_secrets.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --timeout=120 --tb=short
```

**5 passed, 17 deselected**, then **41 passed**, zero skips/failures, 16 warnings,
110.48 seconds. The final command ran on implementation/test head `ba96378f`.

```sh
COMMAND_TEST_TOOLS=/workspace/codex-trigger-w3/workspace/node_modules node tests/trigger_m2/callback_contract.cjs
node workspace/node_modules/typescript/bin/tsc --noEmit --incremental false --project workspace/tsconfig.json
/home/ammosync/trigger-crm-venv312/bin/ruff check tank/trigger_meta.py tank/trigger_marketing.py tank/trigger_publisher.py tank/trigger_marketing_api.py tank/trigger_marketing_contract.py tests/trigger_m2 --select E9,F --output-format concise
git diff --check
```

All passed. Callback test exercises the real callback and presentation modules,
not a fabricated browser screenshot. TypeScript exited 0 without diagnostics.
The final disposable Postgres was stopped successfully via `pgserver.pg_ctl`
with `-w -m fast stop`, targeting only `.gate2-pg`.

Earlier iterations are not passing evidence: one M1 test still expected Facebook
to stay scheduled-only (corrected); the initial Meta test run had a 33-byte
placeholder vault key (interrupted after twelve failures, corrected to 32 bytes);
seven safety-test fixture setup errors were corrected by explicit fixture
re-exports. The first standalone Node callback command lacked COMMAND_TEST_TOOLS
and was rerun with the exact successful command above. An initial Dockerfile
named-module assertion failed because COPY already uses a glob; no Dockerfile
edit was needed. An SQL template typo in the initial RLS commit was corrected
before schema application. All completed files were committed and pushed using
`git push origin codex/trigger-w3`; every push succeeded, with no main merge.

## Outstanding acceptance and CI

- Founder registers the Meta app and supplies `TRIGGER_META_APP_ID` and
  `TRIGGER_META_APP_SECRET` in Coolify. Existing `TANK_VAULT_KEY` is a prerequisite.
  Live setting presence/values were not inspected.
- Founder uses his own workspace and Page: Confirm connect, finish consent,
  Confirm Page selection, approve/schedule a real Facebook write, verify its
  actual appearance at the planned time and the existing card's status/link/
  receipt. **No founder browser evidence or screenshots are available.**
- Exact final-head hosted `tank` and `workspace` results remain unverified.
  The GitHub connector returned no PR-triggered workflow runs for the queried
  full implementation SHAs. No hosted-CI clearance is claimed.
- PR metadata reported `mergeable: false` at `ba96378f`. Main was left untouched
  under the explicit instruction. Any conflict-resolution work needs Claude's
  next block; this gate does not merge main or change the PR base.

Gate 2 implementation is ready for review; live completion is not claimed.
