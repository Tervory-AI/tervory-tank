# MCP G1 review handoff

Branch: `codex/mcp-server`. This is the backend and public transport portion of the founder's Gate G1 brief. **Do not mark G1 done:** the approved Figma source and approval for page “7 · MCP”, frame 1 have not been supplied to this task. `/oauth/authorize` has Tank validation/decision handlers and a server-side Workspace approval helper, but no new Workspace consent page or page words were created. Founder connector/browser acceptance and its screenshots remain absent. Claude opens the PR; the founder merges.

## Changed code (current file and line)

| File | Change |
| --- | --- |
| `tank/mcp_oauth.py:83` | Bounded CIMD resolution through `access.public_get`, exact client/redirect validation and metadata cache. |
| `tank/mcp_oauth.py:143` | Both resource documents and authorization-server discovery. |
| `tank/mcp_oauth.py:161` | Public-client registration and transaction-serialized per-source limit. |
| `tank/mcp_oauth.py:221` | Signed-in request validation and single-use PKCE approval/denial; no invalid-client redirect. |
| `tank/mcp_oauth.py:260` | Resource-bound code exchange, shared CLI refresh rotation and revocation. |
| `tank/mcp_server.py:44` | Read classification computed from Command adapters. Existing `worker.build` has no HTTP adapter, so its existing `BuildArgs` special case remains non-read and pending Confirm. |
| `tank/mcp_server.py:74` | Per-session Command thread, durable proposals, automatic read Confirm, sixty-second wait and stored receipts; all other tools remain pending. |
| `tank/mcp_server.py:115` | Bearer-only identity, allowed Origins, Streamable HTTP initialization/session lifecycle and four G1 methods. |
| `tank/personal_tokens.py:142` | Shared hash lookup with a server-selected audience. CLI management still requires Workspace identity. |
| `tank/device_login.py:212` | Reuse existing format, expiry and atomic refresh rotation, now with audience/client binding. |
| `tank/schema.sql:2337` | Additive token columns, global public-client metadata and tenant-scoped codes/sessions. Conditional RLS matches `personal_tokens`; startup guard stays unchanged. |
| `tank/main.py:4679` | Mount the new routers beside CLI, with no route/worker/cache changes. |
| `workspace/lib/mcp.ts:47` | Bounded public proxy; six MCP request headers only, OAuth body/media type only, no cookies or service identity; fixed local Tank and us-east host. |
| `workspace/lib/mcp.ts:83` | Existing authenticated us-east approval corridor prepared for the approved page. |
| `workspace/middleware.ts:11` | Public discovery/protocol paths; consent stays private. Seven fixed route files under `workspace/app/mcp`, `workspace/app/oauth` and `workspace/app/.well-known` forward to that helper. |
| `tests/test_mcp_oauth.py:1` | CIMD/DCR, redirect/size/rate limits, PKCE, replay/expiry, tenant/client/resource binding, refresh, audience separation, revoke and ZA refusal. |
| `tests/test_mcp_server.py:1` | Actual Command proposals/Confirm/receipt storage, no-run paid proposals, role/session isolation and deferred reads. |
| `tests/test_mcp_schema.py:1` | Apply actual schema twice; evaluate `_startup`'s actual catalogue query; prove staged compatibility and enforced tenant policies with a non-bypass test role. |
| `tests/mcp_proxy.cjs:1`, `tests/test_mcp_proxy.py:1` | Real TypeScript proxy regression, including identity stripping and signed-in approval. |
| `docs/mcp/README.md:1` | Official-source connector setup, protocol boundaries, SDK compatibility decision and acceptance still required. |

No runtime configuration or new settings were added. Tank/Workspace changes deploy the main application and its regional copy under the existing deployment rules; the G1 routes answer 404 on ZA. No deployment or production change was performed here.

## Exact validation commands and results

Working directory for commands below: `/workspace/codex-mcp-server`.

Initial setup was the brief's exact clone/fetch/checkout sequence. Named existing files were listed successfully. `plan/MCP-APPS-PLUGINS-PLAN-2026-11-01.md` is absent and explicitly optional. Before **every** push: `git fetch origin main`, `git merge origin/main`, then `git push` (first push used `git push -u origin codex/mcp-server`). The normal main merge had no conflicts; no force push or main push was used.

SDK compatibility (expected refusal, not a passing installation):

```sh
/home/ammosync/trigger-crm-venv312/bin/python -m pip install --dry-run 'mcp==2.3.0' 'pydantic==2.10.6'
```

Result: `ResolutionImpossible`: latest stable MCP requires `pydantic>=2.12.0`, conflicting with Tank's frozen pin. [Resolver output](evidence/sdk-compatibility.log). The brief's direct four-method fallback is used; no SDK or model dependency was added.

Dependencies and disposable database:

```sh
npm ci --prefix workspace --ignore-scripts --no-audit --no-fund
npm ci --prefix cli --ignore-scripts --no-audit --no-fund
/home/ammosync/trigger-crm-venv312/bin/python -m pip install --no-deps --target .git/mcp-evidence/deps pytest-socket
docker run -d --name codex-mcp-tests-pg -p 127.0.0.1::5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16.15
docker port codex-mcp-tests-pg
```

Results: dependency installs succeeded. Only disposable Postgres, trust-authenticated, published at `127.0.0.1:32794`; no production database or credentials were used. Reused the existing CI-compatible Python 3.12 environment and existing repository-pinned jsonschema dependency target read-only.

Final Python command:

```sh
TMPDIR="$PWD/.test-tmp" POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32794/postgres PYTHONPATH="$PWD/.git/mcp-evidence/deps:/workspace/radix-review-deps-dc616753" /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_mcp_*.py tests/test_personal_tokens.py tests/test_device_login.py tests/test_command*.py -q --disable-socket --allow-hosts=127.0.0.1,localhost --basetemp="$PWD/.test-tmp/full-final" --junitxml=.git/mcp-evidence/python-tests-final.xml
```

Result: **261 passed**, exit 0, 255.68 seconds, 14 existing warnings. This includes the legacy MCP connector tests as well as the existing personal-token, device and Command tests. [Log](evidence/python-tests-final.log), [JUnit test cases](evidence/python-tests-final.xml).

```sh
TMPDIR="$PWD/.test-tmp" npm test --prefix cli
node tests/mcp_proxy.cjs
npm run build --prefix workspace
./workspace/node_modules/.bin/tsc --project workspace/tsconfig.json --noEmit
/tmp/tervory-rls-python/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
git diff --check
```

Results: CLI **62/62 passed**, exit 0 ([log](evidence/cli-tests-isolated.log)); proxy assertions passed; production Workspace build passed ([log](evidence/workspace-build.log)); TypeScript, lint ([log](evidence/lint-final.log)) and whitespace checks passed, exit 0. No external provider or model was called. Socket-blocked Python tests and local Node transports use synthetic identities/records only.

Earlier attempts are not represented as passes: the initial reused Python environment lacked `redis` (212 passed, 48 setup errors), and `/tmp` quota caused CLI writes to fail (48/62 passed). Corrected the runtime/scratch directory without changing CLI source. The first corrected CLI run alongside other workloads passed 61/62, with the existing GC/header-deadline timing assertion failing; the complete isolated rerun above passed 62/62. Initial TypeScript body typing and test-import lint errors were fixed before final validation. Original attempt logs remain in `.git/mcp-evidence/` on this host.

## Remaining evidence / blocker

Missing: founder-approved **Figma page “7 · MCP”, frame 1**, including its exact consent/error/denied words and layout. The brief explicitly says to build and push everything else, then stop when this approval is unavailable; this handoff follows that exception. No replacement page, invented words or consent workaround was added.

No founder screenshots exist for connecting from claude.ai, verified FFL rows plus `/chats` receipt, Base waiting for Confirm, or revocation refusing the next call. No live sign-in, live MCP call, deployment or merge was attempted. The PR needs its own CI and independent review; these logs prove local checks only.
