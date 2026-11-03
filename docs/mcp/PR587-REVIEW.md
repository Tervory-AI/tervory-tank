# PR #587 review fixes

Branch: `codex/mcp-server`. Review baseline: `968de1f5b5d9053e844ce86168775aba49a95fe9`. Merged `origin/main` (`9313fd6e`) normally, preserving both sides. No deployment, production SQL, setting changes, model calls or merge of this PR occurred.

## Changes and regression coverage

| Review | Current file and line | Change and proof |
| --- | --- | --- |
| 1 | `tank/device_login.py:212`, `tank/mcp_oauth.py:187`, `tank/mcp_oauth.py:272`, `tank/mcp_oauth.py:319`, `tank/mcp_oauth.py:363`, `tank/personal_tokens.py:142` | Literal SQL with positional parameters throughout these authentication modules. Expiry calculations are computed before the calls, removing the audit rule's matches on arithmetic in bound values as well. AST regression checks every execute/fetch query (`tests/test_mcp_review_587.py:150`). No security rule suppression. |
| 2 | `workspace/lib/mcp.ts:64`, `tank/mcp_oauth.py:205`, `docs/mcp/README.md:65` | Registration alone authenticates Workspace's validated Traefik `X-Real-IP` assertion using existing service authentication. Incoming private headers/authentication are overwritten. Tank ignores untrusted forwarding assertions and uses its socket peer. Independent 50/hour source buckets and spoof refusal tested (`tests/test_mcp_review_587.py:64`, `tests/mcp_proxy.cjs:24`). |
| 3 | `tank/mcp_oauth.py:214`, `tank/mcp_oauth.py:244` | Ignore unknown authorization parameters; refuse duplicates. Tests include scope, prompt and nonce (`tests/test_mcp_review_587.py:19`). |
| 4 | `tank/mcp_server.py:188` | tools/list accepts and ignores cursor and _meta (`tests/test_mcp_review_587.py:34`). |
| 5 | `tank/mcp_oauth.py:169`, `tank/mcp_oauth.py:200` | Validate requested grant/response types as supported sets; order and duplicates do not matter. Authorization-code-only passes; unsupported/malformed lists fail (`tests/test_mcp_review_587.py:48`). |
| 6 | `tank/mcp_oauth.py:283`, `tank/mcp_oauth.py:334` | Token exchanges look up stored code/refresh rows and compare client_id. No metadata resolution/fetch at token time; tests forbid both resolver and network fetch even after clearing CIMD cache (`tests/test_mcp_review_587.py:98`). |
| 7 | `tank/mcp_oauth.py:229` | Metadata HTTP errors, recursive JSON, value/OS errors become invalid_client. Failure cases are tested (`tests/test_mcp_review_587.py:88`). |
| 8 | `tank/schema.sql:2317`, `tank/mcp_oauth.py:318` | Code row retains issued token_id. Correctly bound replay revokes that grant, including access/refresh after rotation; unrelated client/verifier cannot revoke it (`tests/test_mcp_review_587.py:120`). |
| 9 | `workspace/lib/mcp.ts:19`, `tests/mcp_proxy.cjs:70` | 90-second proxy deadline gives Tank's 60-second wait 30 seconds of slack. Virtual-time 70-second read returns its running thread link. |
| 10 | `docs/mcp/README.md:41`, `tests/test_mcp_review_587.py:159` | [Official Cursor docs](https://cursor.com/docs/mcp) currently specify HTTPS Web/Agents and localhost desktop callbacks. Both existing rules accept them. No private-use scheme is specified, so the conditional scheme expansion does not apply. Unsafe redirect schemes remain refused. |
| 11 | `docs/mcp/README.md:60`, `tests/test_mcp_review_587.py:143` | Retain claude.ai, chatgpt.com and cursor.com Origins for browser connector requests; document that Origin never replaces bearer authentication. |
| Additional CI failure | `tank/schema.sql:2286` | Original tank CI also failed generator-tail tests. MCP schema now precedes the existing generated Hermes block, leaving that generated block byte-identical at EOF. Both actual generator regressions are included in the validation command below. |

## Validation

Working directory: `/workspace/codex-mcp-server`. Python tests use only the disposable local Postgres below, synthetic records and disabled external sockets. Existing CI-compatible dependencies were reused. No live connector or production database was contacted.

```sh
docker run -d --name codex-mcp-review-tests-pg -p 127.0.0.1::5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16.15
docker port codex-mcp-review-tests-pg
```

Result: disposable database available at `127.0.0.1:32799`.

```sh
TMPDIR="$PWD/.test-tmp" POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32799/postgres PYTHONPATH="$PWD/.git/mcp-evidence/deps:/workspace/radix-review-deps-dc616753" /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_mcp_*.py tests/test_personal_tokens.py tests/test_device_login.py tests/test_command*.py tests/test_agent_memory_records.py tests/test_tisan_builder_interfaces.py -q --disable-socket --allow-hosts=127.0.0.1,localhost --basetemp="$PWD/.test-tmp/review587-full" --junitxml=.git/mcp-review-587/full.xml
node tests/mcp_proxy.cjs
/tmp/tervory-rls-python/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
./workspace/node_modules/.bin/tsc --project workspace/tsconfig.json --noEmit
npm run build --prefix workspace
git diff --check
```

Results: **322 passed, 12 skipped**, exit 0, 351.33 seconds (14 warnings). The 24 new review regressions pass. Eleven unrelated agent-memory integration tests require their separate `MEMORY_TEST_DATABASE_URL`; one Tisan real-build test requires its explicit opt-in. Both generator-tail regressions passed. Node proxy, Ruff, TypeScript, Workspace production build and `git diff --check` all passed, exit 0.

The original failing logs were read with:

```sh
TMPDIR="$PWD/.test-tmp" gh run view 41596851126 --job 125786112980 --log
TMPDIR="$PWD/.test-tmp" gh run view 41596851126 --job 125786196467 --log
```

They show the five Semgrep findings from the review and the two additional schema-generator failures. An initial local test selection used a nonexistent test filename and collected no tests; the corrected full command above includes the actual generator test files.

Read-only proxy verification commands:

```sh
docker ps --format '{{.Names}} {{.Image}}' --filter name=coolify-proxy
docker inspect --format '{{range .Config.Cmd}}{{println .}}{{end}}' coolify-proxy | rg -i 'entrypoints|forwardedheaders|providers.file|providers.docker|proxyprotocol'
docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' coolify-proxy | rg '^TRAEFIK_ENTRYPOINTS_.*(FORWARDEDHEADERS|PROXYPROTOCOL)' || true
rg -n -i 'x-real-ip|forwardedheaders' /data/coolify/proxy/dynamic 2>/dev/null || true
docker ps --filter name=workspace --format '{{.Names}} {{.Ports}}'
```

Result: `traefik:v3.7.16`; HTTP/HTTPS entrypoints without forwarded-header trust/insecure or PROXY-protocol overrides; no dynamic X-Real-IP override; Workspace exposes internal `3000/tcp` without a host-published port. Header behavior and primary-source links are in [the trust-boundary documentation](README.md#registration-source-trust-boundary). No secret values were requested or printed.

Each finished file was committed and pushed on this branch; before every push:

```sh
git fetch origin main
git merge origin/main
git push
```

All fetches, merges and pushes succeeded. The PR's current checks provide the remote CI results; local output is recorded below. No founder browser screenshots exist. Approved Figma page “7 · MCP”, frame 1 and founder connector/browser acceptance remain outstanding from G1; this review adds no UI or page wording.

## Recorded local output

This recorded run precedes the final expiry-calculation cleanup. Run `41603260531` passed security but still annotated two WARNINGs for datetime additions in bound values; those calculations now happen before SQL calls. The PR body records the follow-up local run and final-head CI, without rewriting this earlier output.

### Python regressions

```text
........................................................................ [ 21%]
........................................................................ [ 43%]
........................................................................ [ 64%]
........................................................................ [ 86%]
...............................ssssssss.sss..s                           [100%]
=============================== warnings summary ===============================
../../home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "copy" in "ScaffoldPage" shadows an attribute in parent "Body"
    warnings.warn(

../../home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "copy" in "TisanBuildArgs" shadows an attribute in parent "Body"
    warnings.warn(

../../home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "register" in "TriggerWriteArgs" shadows an attribute in parent "TriggerCheckArgs"
    warnings.warn(

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-mcp-server/tank/main.py:752: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/lib/python3.12/site-packages/fastapi/applications.py:4723: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)  # ty: ignore[deprecated]

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-mcp-server/tank/main.py:806: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("shutdown")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-mcp-server/tank/agent_skills.py:531: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @router.on_event("startup")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-mcp-server/tank/skala_intake.py:71: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-mcp-server/tank/skala_intake.py:77: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("shutdown")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-mcp-server/tank/skala_revalidation.py:192: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
322 passed, 12 skipped, 14 warnings in 351.33s (0:05:51)
```

### Node proxy

```text
MCP proxy: allowlisted headers, body-only OAuth, discovery, ZA refusal, body limit, empty DELETE and signed-in approval passed
```

### Ruff

```text
All checks passed!
```

### Workspace production build

```text

> tervory-workspace@0.1.0 build
> next build

   ▲ Next.js 15.5.28

   Creating an optimized production build ...
 ✓ Compiled successfully in 15.1s
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/38) ...
   Generating static pages (9/38) 
   Generating static pages (18/38) 
   Generating static pages (28/38) 
 ✓ Generating static pages (38/38)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                       Size  First Load JS
┌ ƒ /                                            466 B         108 kB
├ ƒ /_not-found                                  995 B         104 kB
├ ƒ /.well-known/oauth-authorization-server      294 B         103 kB
├ ƒ /.well-known/oauth-protected-resource        294 B         103 kB
├ ƒ /.well-known/oauth-protected-resource/mcp    294 B         103 kB
├ ƒ /access                                     4.2 kB         107 kB
├ ƒ /access/api/[...path]                        294 B         103 kB
├ ƒ /access/live/[id]                          1.46 kB         104 kB
├ ƒ /admin                                     6.33 kB         113 kB
├ ƒ /admin/autumbra                            4.37 kB         111 kB
├ ƒ /admin/feeds                               1.07 kB         107 kB
├ ƒ /admin/ghost                                 294 B         103 kB
├ ƒ /admin/homes                               1.02 kB         107 kB
├ ƒ /admin/unpriced                              294 B         103 kB
├ ƒ /api/autumbra/receipts/weekly/[tenant]       294 B         103 kB
├ ƒ /api/autumbra/undo                           294 B         103 kB
├ ƒ /api/base                                    294 B         103 kB
├ ƒ /api/base/context-trial                      294 B         103 kB
├ ƒ /api/base/export                             294 B         103 kB
├ ƒ /api/billing/webhook                         294 B         103 kB
├ ƒ /api/case-studies/[[...path]]                294 B         103 kB
├ ƒ /api/chat                                    294 B         103 kB
├ ƒ /api/feedback                                294 B         103 kB
├ ƒ /api/health                                  294 B         103 kB
├ ƒ /api/ledger                                  294 B         103 kB
├ ƒ /api/memory/records/[id]                     294 B         103 kB
├ ƒ /api/skala                                   294 B         103 kB
├ ƒ /api/skala/gold                              294 B         103 kB
├ ƒ /api/tank                                    294 B         103 kB
├ ƒ /api/tank/chat                               294 B         103 kB
├ ƒ /api/tasks                                   294 B         103 kB
├ ƒ /api/trigger-crm/[...path]                   294 B         103 kB
├ ƒ /api/zenas/answers                           294 B         103 kB
├ ƒ /api/zenas/documents/[id]/reviews            294 B         103 kB
├ ƒ /api/zenas/feeds                             294 B         103 kB
├ ƒ /api/zenas/feeds/load                        294 B         103 kB
├ ƒ /api/zenas/feeds/region                      294 B         103 kB
├ ƒ /api/zenas/feeds/region/convert              294 B         103 kB
├ ƒ /api/zenas/feeds/region/load                 294 B         103 kB
├ ƒ /api/zenas/matters                           294 B         103 kB
├ ƒ /api/zenas/matters/[id]/documents            294 B         103 kB
├ ƒ /api/zenas/matters/[id]/release              294 B         103 kB
├ ƒ /api/zenas/moot/[[...segments]]              294 B         103 kB
├ ƒ /api/zenas/review                            294 B         103 kB
├ ƒ /api/zenas/review-switch                     294 B         103 kB
├ ƒ /api/zenas/selftest                          294 B         103 kB
├ ƒ /api/zenas/tenants                           294 B         103 kB
├ ƒ /autumbra                                    172 B         103 kB
├ ƒ /autumbra/receipts/weekly/[tenant]           294 B         103 kB
├ ƒ /autumbra/undo/[id]                        1.13 kB         104 kB
├ ƒ /base                                      19.5 kB         123 kB
├ ƒ /base/download                               294 B         103 kB
├ ƒ /base/product/[...path]                      294 B         103 kB
├ ƒ /billing                                     369 B         103 kB
├ ƒ /chats                                     11.9 kB         115 kB
├ ƒ /chats/api/[...path]                         294 B         103 kB
├ ƒ /chats/evidence/[thread]                     174 B         103 kB
├ ƒ /chats/evidence/[thread]/[row]               174 B         103 kB
├ ƒ /cli/device                                  294 B         103 kB
├ ƒ /cli/sign-ins                                173 B         103 kB
├ ƒ /control                                   2.49 kB         106 kB
├ ƒ /control/signups                             171 B         103 kB
├ ƒ /control/source                              294 B         103 kB
├ ƒ /data                                      3.58 kB         107 kB
├ ƒ /ledger                                      294 B         103 kB
├ ƒ /market-lab                                10.9 kB         114 kB
├ ƒ /market-lab/ask                              294 B         103 kB
├ ƒ /market-lab/files                            294 B         103 kB
├ ƒ /market-lab/sources/[id]                     171 B         103 kB
├ ƒ /market-lab/warnings/feedback                294 B         103 kB
├ ƒ /matters                                   1.27 kB         104 kB
├ ƒ /mcp                                         294 B         103 kB
├ ƒ /moot                                        182 B         107 kB
├ ƒ /moot/[match]                                171 B         103 kB
├ ƒ /moot/status                                 294 B         103 kB
├ ƒ /oauth/register                              294 B         103 kB
├ ƒ /oauth/revoke                                294 B         103 kB
├ ƒ /oauth/token                                 294 B         103 kB
├ ƒ /onboarding                                6.05 kB         152 kB
├ ƒ /onboarding/status                           294 B         103 kB
├ ƒ /prices                                      323 B         103 kB
├ ƒ /radix                                     10.3 kB         156 kB
├ ƒ /radix/plugins/files                         294 B         103 kB
├ ƒ /radix/requests                              294 B         103 kB
├ ƒ /review                                    2.88 kB         109 kB
├ ƒ /rig                                       9.98 kB         113 kB
├ ƒ /rig/admin                                 6.48 kB         110 kB
├ ƒ /rig/admin/api                               294 B         103 kB
├ ƒ /rig/admin/three-d                         1.08 kB         104 kB
├ ƒ /rig/admin/three-d/file/[...path]            294 B         103 kB
├ ƒ /rig/api/rig                                 294 B         103 kB
├ ƒ /rig/price-history                           294 B         103 kB
├ ƒ /sign-in/[[...sign-in]]                      336 B         150 kB
├ ƒ /sign-up/[[...sign-up]]                      336 B         150 kB
├ ƒ /skala                                      8.5 kB         112 kB
├ ƒ /skala/gold                                3.41 kB         106 kB
├ ƒ /tank                                      5.37 kB         108 kB
├ ƒ /tank/moa                                    171 B         103 kB
├ ƒ /tank/proof                                1.86 kB         109 kB
├ ƒ /tank/proof/export                           294 B         103 kB
├ ƒ /tank/proof/savings-export                   294 B         103 kB
├ ƒ /tasks                                     2.06 kB         105 kB
├ ƒ /tiger                                     6.72 kB         110 kB
├ ƒ /tisan                                     11.6 kB         115 kB
├ ƒ /v1/command/[...path]                        294 B         103 kB
├ ƒ /zenas                                     16.9 kB         123 kB
└ ƒ /zenas/feeds                               2.31 kB         109 kB
+ First Load JS shared by all                   103 kB
  ├ chunks/1255-dc3ddf72a1dc71a7.js            46.6 kB
  ├ chunks/4bd1b696-f785427dddbba9fb.js        54.2 kB
  └ other shared chunks (total)                 2.2 kB


ƒ Middleware                                     93 kB

ƒ  (Dynamic)  server-rendered on demand
```

TypeScript and whitespace checks produced no output and exited 0.
