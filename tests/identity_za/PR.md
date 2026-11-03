# Identity ZA: Step 1 review evidence

Branch: `codex/identity-za`. Claude opens the PR; founder merges.
This prepares the independent ZA Zitadel resource and optional ZA CLI sign-in.
**Not product completion:** no production deployment, setting values, DNS
mutation, real identity, founder screenshot or live ZA restore is claimed.
The founder's ordered deployment/acceptance steps are in
[IDENTITY-ZA.md](../../docs/ops/IDENTITY-ZA.md).

## Resulting behavior

With the issuer unset, the existing device approval and credential lifecycle
remain unchanged. Boston ignores the optional identity settings. With the ZA
issuer configured, **only** an explicit `approval: "zitadel"` request uses the fixed
Zitadel origin. `tervory login --region za --sign-in zitadel` sends that selection.
Plain/old CLI requests and explicit `approval: "workspace"` retain the Boston
approval path; its dedicated key still cannot approve founders. Verified ID tokens
map reserved organisation IDs to existing tenant UUIDs and mint the same Tank
access/refresh credentials.

Identity is only `zitadel:<sub>`. Founder rights are re-read from the explicit
ZA admin list; tenant_admin is captured only from the requesting app's reserved
project role claim, bound to the mapped organisation. Setup verifies the CLI
project is owned by the initial Tervory organisation. Other-project role claims,
user metadata, email, display name and request headers cannot grant those rights.
Roles are a sign-in snapshot; refresh/revoke use the existing credential row and
lifetimes. The existing revoke ends both access and refresh.

## What changed, file and line

- `ops/identity/docker-compose.yml:1`: separate identity-za resource, digest-pinned
  API/Login/Postgres, split init/setup/start, own volumes, existing proxy h2c labels,
  default branding, forced first password change, signup off and backup worker.
- `ops/identity/Dockerfile.setup:1`: digest-pinned configuration and existing
  encrypted-backup source build targets. Zitadel source is never patched/copied.
- `ops/identity/setup.py:37`: API-only idempotent project/app/role/policy setup;
  owner verification, preserved policy lifetimes, omitted protobuf defaults,
  explicit second factors/passkeys. Successful stdout is only the public client ID.
- `tank/identity_oidc.py:29`: optional ZA-only configuration gate.
- `tank/identity_oidc.py:72`: same-origin discovery cache and JWKS key refresh.
- `tank/identity_oidc.py:89`: RS256 signature, issuer, audience/azp, expiry/iat checks.
- `tank/identity_oidc.py:131`: reserved sub/organisation/current-project role mapping.
- `tank/identity_device.py:17`: provider device grant to hash-only local pending state.
- `tank/identity_device.py:45`: serialized single-use grant exchange into existing
  personal_tokens rows; no upstream token or raw device code is persisted.
- `tank/device_login.py:59`: optional explicit Zitadel approval selector.
- `tank/device_login.py:131`: optional identity start; token polling branches by
  the new wrapped provider code, leaving the old code/approval routes working.
- `tank/personal_tokens.py:150`: verified role snapshot read only after token-hash
  match; only ZA Zitadel identities can use it. Founder list behavior is unchanged.
- `tank/schema.sql:2339`: additive/idempotent role and provider columns, defaulting
  old rows to false/workspace; format and token lifetimes are unchanged.
- `tank/requirements.txt:49`: standard PyJWT verification added, using the existing
  cryptography backend rather than implementing JWT cryptography.
- `docker-compose.za.yml:157`: the three public identity settings reach ZA Tank only.
- `.env.example:487`: new setting names only, with no values.
- `cli/src/client.mjs:108`: fixed-origin Zitadel verification URL validation;
  old us-east/Workspace URL construction remains unchanged. Wrapped codes are
  also redacted across streamed chunk boundaries.
- `cli/package.json:4`, `cli/package-lock.json:3`, `cli/CHANGELOG.md:3`: CLI 0.1.2.
- `cli/README.md:26`: ZA founder setup and unchanged disabled-provider behavior.
- `jobs/train/backup.py:86`: own fixed identity database dump through the existing
  encrypted pipe/archive path; ZA Zenas scope only, identity archive label.
- `ops/restore_drill.py:99`: identity manifest selection and required-archive guard.
- `ops/restore_drill.py:179`: restore identity to a separate disposable database;
  no production SQL, no identity user rows in result JSON.
- `docs/ops/RESTORE-DRILL.md:124`: ZA identity drill steps and secret-volume limits.
- `tests/test_identity_za.py:1`, `tests/test_identity_stack.py:1`,
  `tests/test_identity_backup.py:1`, `tests/test_restore_drill.py:1`,
  `cli/test/identity-za.test.mjs:1`: synthetic-only tests described below.

No Workspace page, Clerk setting, brand copy, Boston compose or production data
was edited by this task. Incoming origin/main was merged before each push, as
required. Schema/ZA config/Tank and backup changes select existing deployment
pipelines on merge; founder must review that impact. No deploy was triggered here.

## Upstream release, image pins and proxy decision

Latest stable was verified through:

```sh
gh api repos/zitadel/zitadel/releases/latest --jq '{tag_name,published_at}'
docker buildx imagetools inspect ghcr.io/zitadel/zitadel:v4.20.0 --format '{{json .Manifest.Digest}}'
docker buildx imagetools inspect ghcr.io/zitadel/zitadel-login:v4.20.0 --format '{{json .Manifest.Digest}}'
docker buildx imagetools inspect postgres:16.15 --format '{{json .Manifest.Digest}}'
docker buildx imagetools inspect python:3.12-slim --format '{{json .Manifest.Digest}}'
```

Observed: **v4.20.0**, published **2026-10-22T10:18:58Z**.

| Image | Observed index digest |
| --- | --- |
| ghcr.io/zitadel/zitadel:v4.20.0 | sha256:9ea0e9ecfdc43115da871242e40a0320f2ece864c7cd8b5d41a863a7f4902499 |
| ghcr.io/zitadel/zitadel-login:v4.20.0 | sha256:f1abfdf3c5d16eda03cad3b584226207ecc640ca5c679d7c45abbbce7d1d63f0 |
| postgres:16.15 | sha256:5db6dac2ef5dcff512f4f00a009c3c332b9f2f28f24277175bf3e4a3d02ef83a |
| python:3.12-slim | sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 |

The guide selects **Proxied auth-za.tervory.com**, covered by the free
`*.tervory.com` Universal SSL certificate, with Network gRPC On, HTTP/2 to Origin
On, Full (strict), origin443 TLS/ALPN h2 and the existing Coolify API h2c route.
Origin certificates must use exactly the existing proxied ZA site's issuance and
renewal path, without changing the shared proxy or introducing a Cloudflare token.
The repo does not establish that live mechanism. The guide stops at explicit
read-only Coolify resource/router/resolver checks until it is established.
No DNS, proxy, credential or firewall changes were made by this PR.

## Commands and results

Working directory: `/workspace/codex-identity-za` unless a prefix specifies cli.
A new disposable Postgres container was used, never a production connection:

```sh
docker run --rm -d --name tervory-identity-za-offline-pg --label tervory.test=identity-za --memory=1g --cpus=1 -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1::5432 postgres:16.15
docker port tervory-identity-za-offline-pg 5432
```

The allocated host endpoint was `127.0.0.1:32795`. Fixtures create/drop their
own randomly named databases there, apply schema twice, and use only synthetic
identities. The fake OIDC provider is httpx MockTransport; outbound sockets/DNS
are blocked for Python identity/command tests. No model calls were used to test.
The restore test uses only its existing disposable internal Docker networks,
real age encryption and an in-memory fake archive store, never real R2.

Checkout-local dependencies (the shared Python environment was not modified):

```sh
/tmp/base-reliability-venv/bin/python -m pip install --no-deps --target /workspace/codex-identity-za/.proof/python PyJWT==2.15.1 pytest-socket==0.8.1
/tmp/base-reliability-venv/bin/python -m pip install --target /workspace/codex-identity-za/.proof/python jsonschema==4.26.0
/tmp/base-reliability-venv/bin/python -m pip install --no-deps --target /workspace/codex-identity-za/.proof/python ruff==0.17.2
npm ci --ignore-scripts --no-audit --no-fund  # in cli/
TMPDIR=/workspace/codex-identity-za/.proof/tmp npm_config_cache=/workspace/codex-identity-za/.proof/npm-cache npm ci --prefix workspace --ignore-scripts --no-audit --no-fund
```

All succeeded. The first CLI run used the quota-full shared /tmp and had 14
filesystem/release failures; using this checkout's TMPDIR resolved them. The
first backend run lacked jsonschema; the repository-pinned install resolved it.
A broader command run then had three missing-TypeScript failures (full output
below); installing the checked-in Workspace dependencies resolved all three.
No product/test code was weakened or skipped to resolve those environment errors.

Core existing device/login/command run:

```sh
PYTHONPATH=tank:.proof/python TMPDIR=/workspace/codex-identity-za/.proof/tmp POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32795/postgres /tmp/base-reliability-venv/bin/python -m pytest -q --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 tests/test_device_login.py tests/test_personal_tokens.py tests/test_command.py
```

Exit 0: **104 passed**, 14 existing warnings, 102.05 s.

Broader matrix (existing CI clean_env strips credentials, and all database
settings are replaced with the disposable local endpoint):

```sh
PYTHONPATH=tank:.proof/python TMPDIR=/workspace/codex-identity-za/.proof/tmp /tmp/base-reliability-venv/bin/python - <<'PY'
import os
from pathlib import Path
import runpy
import subprocess
import sys

env = runpy.run_path('.github/scripts/offline_suite.py')['clean_env']()
for key in list(env):
    if 'DATABASE' in key.upper():
        del env[key]
env['POOL_SCHEMA_DATABASE_URL'] = 'postgresql://postgres@127.0.0.1:32795/postgres'
paths = ['tests/test_device_login.py', 'tests/test_personal_tokens.py',
         'tests/test_identity_za.py', 'tests/test_identity_stack.py', 'tests/test_identity_backup.py',
         *sorted(str(path) for path in Path('tests').glob('test_command*.py'))]
args = [sys.executable, '-m', 'pytest', '-q', '--disable-socket', '--allow-unix-socket',
        '--allow-hosts=127.0.0.1,localhost,::1', *paths]
with open('.proof/final-python.txt', 'w') as output:
    result = subprocess.run(args, env=env, stdout=output, stderr=subprocess.STDOUT)
print(Path('.proof/final-python.txt').read_text())
raise SystemExit(result.returncode)
PY
```

That run returned 1: **224 passed, 3 failed, 1 skipped**, 14 warnings, 198.93 s.
All three failures were the absent Workspace TypeScript dependency, not identity
assertions. After installing Workspace dependencies, the exact affected file:

```sh
PYTHONPATH=tank:.proof/python TMPDIR=/workspace/codex-identity-za/.proof/tmp /tmp/base-reliability-venv/bin/python -m pytest -q --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 tests/test_command_1b_workspace.py
```

returned 0: **3 passed in 1.98 s**. Thus every executed non-skipped case in that
matrix passed across the original run and focused environment-corrected rerun.
The one skip is retained below rather than claimed as coverage.

New identity tests and the later setup-defaults regression:

```sh
PYTHONPATH=tank:.proof/python TMPDIR=/workspace/codex-identity-za/.proof/tmp POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32795/postgres /tmp/base-reliability-venv/bin/python -m pytest -q --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 tests/test_identity_za.py
PYTHONPATH=tank:.proof/python TMPDIR=/workspace/codex-identity-za/.proof/tmp /tmp/base-reliability-venv/bin/python -m pytest -q --disable-socket --allow-unix-socket tests/test_identity_stack.py
PYTHONPATH=tank:.proof/python TMPDIR=/workspace/codex-identity-za/.proof/tmp /tmp/base-reliability-venv/bin/python -m pytest -q --disable-socket --allow-unix-socket tests/test_identity_backup.py
```

Exit 0 each: **12 passed** (OIDC), **3 passed** (setup/stack, including omitted
protobuf defaults), **2 passed** (backup scope). Tests cover bad signatures,
wrong issuer/audience/azp, expiry, unknown kid and rotation, unmapped orgs,
metadata/other-project roles, founder list lookup, legacy approval alongside
Zitadel, issuer unset/Boston unchanged, refresh/revoke, setup idempotency and
project ownership, private bootstrap volume and pinned deployment boundaries.

```sh
TMPDIR=/workspace/codex-identity-za/.proof/tmp npm test --prefix cli
```

Exit 0: **65 passed**, no skips/failures, 18.55 s. Includes fixed-origin refusal,
legacy/us-east behavior, credential rotation/revoke, wrapped-code redaction,
release reproducibility/install checks and version/lockfile/changelog consistency.

```sh
PYTHONPATH=tank:.proof/python TMPDIR=/workspace/codex-identity-za/.proof/tmp RESTORE_DRILL_E2E=1 /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_restore_drill.py
```

Exit 0: **4 passed in 39.70 s**. Real age-encrypted synthetic Tank/Qdrant/identity
archives are restored in disposable containers. The ZA test verifies an actual
identity row before container teardown, not only schema presence. Missing
identity archives fail when required; identity cannot substitute for Qdrant.
No live ZA/Boston archive or private restore identity was accessed.

```sh
PYTHONPATH=.proof/python /tmp/base-reliability-venv/bin/python -m ruff check tank/identity_oidc.py tank/identity_device.py tank/device_login.py tank/personal_tokens.py ops/identity/setup.py ops/restore_drill.py jobs/train/backup.py tests/test_identity_za.py tests/test_identity_stack.py tests/test_identity_backup.py tests/test_restore_drill.py --select E9,F
docker compose -f ops/identity/docker-compose.yml config --no-interpolate --quiet
git diff --check
docker build --target configure -f ops/identity/Dockerfile.setup -t tervory-identity-za-config:review .
docker build --target backup -f ops/identity/Dockerfile.setup -t tervory-identity-za-backup:review .
```

All exit 0. Both custom targets built locally; no image was published. A full
Docker Compose schema check of the existing ZA compose file rejects its
preexisting Coolify `services.agent-roles.exclude_from_hc` extension; the identity
compose passes, and a separate YAML check confirmed all three new settings are
on ZA Tank. The Coolify extension was not removed to manufacture a pass.

## Acceptance and deployment still required

The founder supplies all actual values through Coolify (guide section 3), then
follows the DNS/resource/deployment/sign-in/passkey/SMTP/org/client-ID/admin-sub
steps in order. Zitadel/default Login were not started with real values here.
After the ZA box and settings are available, record the founder's own sign-in,
passkey, device approval, ZA founder chat, post-revoke refusal screenshots and
real ZA identity restore JSON. None exists from this preparation; no screenshot
is fabricated or substituted with a fixture screen. No new branded page or copy
is introduced pending approved Figma.

`gh run list --repo Tervory-AI/tervory-tank --branch codex/identity-za --limit 3 --json status,conclusion,headSha,url`
returned `[]` at the evidence check: Claude has not opened the PR, so no green PR
CI is claimed. Local tests and builds are preparation, not the done-when result.

## Broader command run including environment failures

```text
........................................................................ [ 31%]
................................................FFF..................... [ 63%]
..............................................................s......... [ 94%]
............                                                             [100%]
=================================== FAILURES ===================================
_________________________ test_command_window_contract _________________________

    def test_command_window_contract():
        result = subprocess.run(
            ["node", str(ROOT / "tests/command_1b_contract.cjs")],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
>       assert result.returncode == 0, result.stdout + result.stderr
E       AssertionError: node:internal/modules/cjs/loader:1433
E           throw err;
E           ^
E
E         Error: Cannot find module '/workspace/codex-identity-za/workspace/node_modules/typescript'
E         Require stack:
E         - /workspace/codex-identity-za/tests/command_1b_contract.cjs
E             at Function._resolveFilename (node:internal/modules/cjs/loader:1430:15)
E             at defaultResolveImpl (node:internal/modules/cjs/loader:1040:19)
E             at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1045:22)
E             at Function._load (node:internal/modules/cjs/loader:1216:25)
E             at wrapModuleLoad (node:internal/modules/cjs/loader:254:19)
E             at Module.require (node:internal/modules/cjs/loader:1527:12)
E             at require (node:internal/modules/helpers:147:16)
E             at Object.<anonymous> (/workspace/codex-identity-za/tests/command_1b_contract.cjs:6:12)
E             at Module._compile (node:internal/modules/cjs/loader:1781:14)
E             at Object..js (node:internal/modules/cjs/loader:1913:10) {
E           code: 'MODULE_NOT_FOUND',
E           requireStack: [ '/workspace/codex-identity-za/tests/command_1b_contract.cjs' ]
E         }
E
E         Node.js v22.23.4
E
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['node', '/workspace/codex-identity-za/tests/command_1b_contract.cjs'], returncode=1, stdout='',...OT_FOUND',\n  requireStack: [ '/workspace/codex-identity-za/tests/command_1b_contract.cjs' ]\n}\n\nNode.js v22.23.4\n").returncode

tests/test_command_1b_workspace.py:13: AssertionError
_________________________ test_command_page_boundaries _________________________

    def test_command_page_boundaries():
        result = subprocess.run(
            ["node", str(ROOT / "tests/command_1b_pages.cjs")],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
>       assert result.returncode == 0, result.stdout + result.stderr
E       AssertionError: node:internal/modules/cjs/loader:1433
E           throw err;
E           ^
E
E         Error: Cannot find module '/workspace/codex-identity-za/workspace/node_modules/typescript'
E         Require stack:
E         - /workspace/codex-identity-za/tests/command_1b_pages.cjs
E             at Function._resolveFilename (node:internal/modules/cjs/loader:1430:15)
E             at defaultResolveImpl (node:internal/modules/cjs/loader:1040:19)
E             at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1045:22)
E             at Function._load (node:internal/modules/cjs/loader:1216:25)
E             at wrapModuleLoad (node:internal/modules/cjs/loader:254:19)
E             at Module.require (node:internal/modules/cjs/loader:1527:12)
E             at require (node:internal/modules/helpers:147:16)
E             at Object.<anonymous> (/workspace/codex-identity-za/tests/command_1b_pages.cjs:7:10)
E             at Module._compile (node:internal/modules/cjs/loader:1781:14)
E             at Object..js (node:internal/modules/cjs/loader:1913:10) {
E           code: 'MODULE_NOT_FOUND',
E           requireStack: [ '/workspace/codex-identity-za/tests/command_1b_pages.cjs' ]
E         }
E
E         Node.js v22.23.4
E
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['node', '/workspace/codex-identity-za/tests/command_1b_pages.cjs'], returncode=1, stdout='', st...E_NOT_FOUND',\n  requireStack: [ '/workspace/codex-identity-za/tests/command_1b_pages.cjs' ]\n}\n\nNode.js v22.23.4\n").returncode

tests/test_command_1b_workspace.py:21: AssertionError
_______ test_command_window_header_hides_totals_without_a_selected_chat ________

    def test_command_window_header_hides_totals_without_a_selected_chat():
        result = subprocess.run(
            ["node", str(ROOT / "tests/command_window_header.cjs")],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
>       assert result.returncode == 0, result.stdout + result.stderr
E       AssertionError: node:internal/modules/cjs/loader:1433
E           throw err;
E           ^
E
E         Error: Cannot find module '/workspace/codex-identity-za/workspace/node_modules/typescript'
E         Require stack:
E         - /workspace/codex-identity-za/tests/command_window_header.cjs
E             at Function._resolveFilename (node:internal/modules/cjs/loader:1430:15)
E             at defaultResolveImpl (node:internal/modules/cjs/loader:1040:19)
E             at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1045:22)
E             at Function._load (node:internal/modules/cjs/loader:1216:25)
E             at wrapModuleLoad (node:internal/modules/cjs/loader:254:19)
E             at Module.require (node:internal/modules/cjs/loader:1527:12)
E             at require (node:internal/modules/helpers:147:16)
E             at Object.<anonymous> (/workspace/codex-identity-za/tests/command_window_header.cjs:8:12)
E             at Module._compile (node:internal/modules/cjs/loader:1781:14)
E             at Object..js (node:internal/modules/cjs/loader:1913:10) {
E           code: 'MODULE_NOT_FOUND',
E           requireStack: [ '/workspace/codex-identity-za/tests/command_window_header.cjs' ]
E         }
E
E         Node.js v22.23.4
E
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['node', '/workspace/codex-identity-za/tests/command_window_header.cjs'], returncode=1, stdout='..._FOUND',\n  requireStack: [ '/workspace/codex-identity-za/tests/command_window_header.cjs' ]\n}\n\nNode.js v22.23.4\n").returncode

tests/test_command_1b_workspace.py:29: AssertionError
=============================== warnings summary ===============================
../../tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "copy" in "ScaffoldPage" shadows an attribute in parent "Body"
    warnings.warn(

../../tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "copy" in "TisanBuildArgs" shadows an attribute in parent "Body"
    warnings.warn(

../../tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "register" in "TriggerWriteArgs" shadows an attribute in parent "TriggerCheckArgs"
    warnings.warn(

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/main.py:752: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @app.on_event("startup")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /tmp/base-reliability-venv/lib/python3.12/site-packages/fastapi/applications.py:4723: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    return self.router.on_event(event_type)  # ty: ignore[deprecated]

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/main.py:806: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @app.on_event("shutdown")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/agent_skills.py:531: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @router.on_event("startup")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/skala_intake.py:71: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @app.on_event("startup")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/skala_intake.py:77: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @app.on_event("shutdown")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/skala_revalidation.py:192: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @app.on_event("startup")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_command_1b_workspace.py::test_command_window_contract - Ass...
FAILED tests/test_command_1b_workspace.py::test_command_page_boundaries - Ass...
FAILED tests/test_command_1b_workspace.py::test_command_window_header_hides_totals_without_a_selected_chat
3 failed, 224 passed, 1 skipped, 14 warnings in 198.93s (0:03:18)
```

## Affected Workspace contracts after dependency installation

```text
...                                                                      [100%]
3 passed in 1.98s
```

## OIDC checks

```text
............                                                             [100%]
=============================== warnings summary ===============================
../../tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "copy" in "ScaffoldPage" shadows an attribute in parent "Body"
    warnings.warn(

../../tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "copy" in "TisanBuildArgs" shadows an attribute in parent "Body"
    warnings.warn(

../../tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "register" in "TriggerWriteArgs" shadows an attribute in parent "TriggerCheckArgs"
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 3 warnings in 5.61s
```

## Final setup and stack checks

```text
...                                                                      [100%]
3 passed in 0.24s
```

## Identity backup scope checks

```text
..                                                                       [100%]
2 passed in 0.12s
```

## CLI final result (TAP summary)

```text
  duration_ms: 194.641839
  type: 'test'
  ...
1..65
# tests 65
# suites 0
# pass 65
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 18546.604966
```

## Real encrypted synthetic restore result

```text
....                                                                     [100%]
4 passed in 39.70s
```

## Lint

```text
All checks passed!
```

## Configuration image build result

```text
#9 exporting to image
#9 exporting layers
#9 exporting layers 1.4s done
#9 exporting manifest sha256:05f06357c10eaf088768fe8ee5a1602913371827817bfb8fb7daff6b869a7fbd 0.0s done
#9 exporting config sha256:ee8aa4dc9db82cde57c8d0afd59d40626b99e54fcdab97f2451a84fc7715fabc 0.0s done
#9 exporting attestation manifest sha256:e5acdae75ed707df29fe840ab8671e5447579101523fb05c6ce0e4c74113101b 0.0s done
#9 exporting manifest list sha256:67cd9f2d477fce1f8f70aef0ba8bac8a1f02f18b421a07aa7418cce662df248e 0.0s done
#9 naming to docker.io/library/tervory-identity-za-config:review
#9 naming to docker.io/library/tervory-identity-za-config:review done
#9 unpacking to docker.io/library/tervory-identity-za-config:review
#9 unpacking to docker.io/library/tervory-identity-za-config:review 0.6s done
#9 DONE 2.1s
```

## Backup image build result

```text

#10 exporting to image
#10 exporting layers
#10 exporting layers 3.1s done
#10 exporting manifest sha256:c7f781464718d1c0bf4078f8f25976e27daec67a8d2504cb2bea78b66dbdfab5 0.0s done
#10 exporting config sha256:5d25a13959260530d7fc647afc7f33d18378b828ab767632de98f21299b5fd39 done
#10 exporting attestation manifest sha256:72373ff048bcebb78781591ad860ca03515cf73d3e5f37bf18b0e0975c5aae9d 0.0s done
#10 exporting manifest list sha256:a1bb29d36a64fc617c119fe847d80dbe719add3b5c6f39af62dce8d3698fbbc3 0.0s done
#10 naming to docker.io/library/tervory-identity-za-backup:review done
#10 unpacking to docker.io/library/tervory-identity-za-backup:review
#10 unpacking to docker.io/library/tervory-identity-za-backup:review 0.9s done
#10 DONE 4.1s
```



## PR #589 rule-10 review fixes (3 Nov 2026)

These replace the earlier default-Zitadel and DNS-only instructions. Token
signature/issuer/audience/expiry checks, principal rules, image digests and the
`Configure.run` API setup contract remain intact. `origin/main` was merged at
`33c7b87c` (main `9313fd6e`); its phone-validation dependency and this branch's
PyJWT dependency were both kept. The five setup/backup tests passed before the
merge commit. Every finished file was committed and pushed on `codex/identity-za`;
each push used `git fetch origin main && git merge origin/main && git push origin
codex/identity-za`. Founder still merges the PR.

### Changed lines and review coverage

1. `tank/identity_device.py:56`: short row-lock transaction reserves
   `last_polled_at`, releases the connection, then calls provider poll/verify.
   `tank/identity_device.py:77`: second short transaction conditionally consumes
   the pending/unexpired row with its verified tenant/user and `RETURNING *`;
   inserts exactly one credential only for the winner, in that transaction.
   The original consumed-row identity check remains satisfied; insertion failure
   rolls the consumption back. `tests/test_identity_za.py:224` stalls both provider
   calls/verification with events, asserts **all** pool connections are idle,
   successfully executes an independent database read, then lets two overlapping
   polls finish and proves one credential/one consumed row.
2. `tank/device_login.py:59`, `tank/device_login.py:134`: Zitadel requires explicit
   `approval: "zitadel"`. `cli/src/client.mjs:181`, `cli/src/client.mjs:473`:
   ZA-only `--sign-in zitadel`; default request body still has only device_name.
   `tests/test_identity_za.py:193` tests both an old request and explicit Workspace
   approval end-to-end while the issuer is set, followed by explicit Zitadel start.
   `cli/test/identity-za.test.mjs:28`, `:66`, `:85` test the opt-in request, old
   default/Workspace origin and rejected wrong-region/command/selection flags.
   `cli/README.md:24` and `cli/CHANGELOG.md:5` describe the actual selection.
3. `ops/identity/docker-compose.yml:157` passes the expiry name to setup;
   `ops/identity/docker-compose.yml:185` gates backups on healthy Postgres only.
   `ops/identity/setup.py:108` checks the public completion record after expiry,
   exits 0 with a clear stderr line and prints the saved public client ID without
   reading/signing the machine key or contacting the API. A partial/missing record
   fails. This trusts the previous completed setup, not a live drift audit.
   `tests/test_identity_stack.py:122` proves both outcomes without a machine key.
4. `docs/ops/IDENTITY-ZA.md:10`: proxied gRPC on the corrected single-level
   hostname with free wildcard coverage, existing ZA certificate issuance only,
   read-only Coolify checks and a stop before deployment if that mechanism is
   unverified; official source links retained. No shared proxy change or token.
5. `tank/identity_oidc.py:100`: an unknown-kid refresh is reserved under the short
   cache lock at most once per 60 seconds, including failed refreshes. Discovery
   and JWKS HTTP fetches occur outside the shared lock. Existing known keys remain
   usable during a slow refresh. `tests/test_identity_za.py:283` tests a burst of
   unknown IDs, the 60-second boundary and concurrent known-key verification.
6. `docs/ops/IDENTITY-ZA.md:181`: Tervory is the organisation Zitadel creates at
   first start. `docs/ops/IDENTITY-ZA.md:206`: map that org to the exact existing
   Tervory tenant UUID returned by the already implemented authenticated
   `https://app.tervory.com/api/case-studies` GET (no tenant query), after positively
   selecting the existing Tervory Clerk organisation. No SQL, fabricated UUID or
   new UI. The guide explicitly stops this deployment step if that verified
   tenant UUID cannot be obtained. Its live value is not asserted here.
   `docs/ops/IDENTITY-ZA.md:268`: removed Zitadel roles persist in an existing Tank
   sign-in through refresh until revoke/expiry; `tervory logout` on every affected
   CLI revokes its Tank credential and refresh token before a fresh login. The
   Clerk sign-in list does not list the separate `zitadel:<sub>` identities.
7. `docs/ops/IDENTITY-ZA.md:293`: the existing `r2-backup-za` worker is only on
   `tervory-za` (`docker-compose.za.yml:230`), while identity Postgres is private
   to this separate resource, with no published port. It cannot reach identity
   Postgres as configured. Keeping the identity worker avoids broadening database
   network access. It reuses the existing backup code, same ZA-only R2 setting
   names/bucket/public age recipient, and its own database credential. Coolify
   resources do not inherit environment values; founder enters the existing R2
   values in the second resource. No new storage credentials/account/bucket were
   created or inspected. `tests/test_identity_stack.py:112` checks network isolation
   and the backup's independent Postgres health dependency.

### Exact review validation commands and results

All data/identities are synthetic. Docker Postgres uses loopback and disposable
random per-test databases; no production data or provider is reached.

```sh
docker run --rm -d --name tervory-identity-za-review-pg --label tervory.test=identity-za-review --memory=1g --cpus=1 -e POSTGRES_HOST_AUTH_METHOD=trust -p127.0.0.1::5432 postgres:16.15
docker port tervory-identity-za-review-pg 5432
```

Result: container started; `127.0.0.1:32797`.

The first new identity run (`TMPDIR=/workspace/codex-identity-za/.proof/tmp
PYTHONPATH=.proof/python:tank
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32797/postgres
/tmp/base-reliability-venv/bin/python -m pytest tests/test_identity_za.py -q`)
reported `2 failed, 13 passed, 3 warnings in 12.00s`: the atomic consumed UPDATE
needed tenant_id/user_id to satisfy the unchanged row constraint. Corrected the
UPDATE to include the verified identity; rerunning that exact command passed
`15 passed, 3 warnings in 8.24s`.

```sh
TMPDIR=/workspace/codex-identity-za/.proof/tmp PYTHONPATH=.proof/python:tank /tmp/base-reliability-venv/bin/python -m pytest tests/test_identity_stack.py tests/test_identity_backup.py -q
```

Result: `6 passed in 0.40s`.

```sh
TMPDIR=/workspace/codex-identity-za/.proof/tmp PYTHONPATH=.proof/python:tank POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32797/postgres /tmp/base-reliability-venv/bin/python -m pytest tests/test_identity_za.py tests/test_identity_stack.py tests/test_identity_backup.py tests/test_device_login.py tests/test_personal_tokens.py tests/test_command.py --disable-socket --allow-hosts=127.0.0.1,localhost -q
```

Full final output (trailing whitespace removed):

```text
........................................................................ [ 57%]
.....................................................                    [100%]
=============================== warnings summary ===============================
../../tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "copy" in "ScaffoldPage" shadows an attribute in parent "Body"
    warnings.warn(

../../tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "copy" in "TisanBuildArgs" shadows an attribute in parent "Body"
    warnings.warn(

../../tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192
  /tmp/base-reliability-venv/lib/python3.12/site-packages/pydantic/_internal/_fields.py:192: UserWarning: Field name "register" in "TriggerWriteArgs" shadows an attribute in parent "TriggerCheckArgs"
    warnings.warn(

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/main.py:752: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @app.on_event("startup")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /tmp/base-reliability-venv/lib/python3.12/site-packages/fastapi/applications.py:4723: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    return self.router.on_event(event_type)  # ty: ignore[deprecated]

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/main.py:806: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @app.on_event("shutdown")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/agent_skills.py:531: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @router.on_event("startup")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/skala_intake.py:71: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @app.on_event("startup")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/skala_intake.py:77: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @app.on_event("shutdown")

tests/test_command.py::test_shared_pin_keeps_policy_limits_and_records_actual_ledger
  /workspace/codex-identity-za/tank/skala_revalidation.py:192: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.

          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).

    @app.on_event("startup")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
125 passed, 14 warnings in 101.00s (0:01:40)
```

The initial `npm test --prefix cli` reported 52 passed / 15 failed: one old
region-refusal wording assertion, a `/tmp` quota error and 13 release-hook
failures from that temporary-directory issue. Kept the old refusal wording while
adding the new flag guidance; the final run uses the task's own temp/cache paths:

```sh
TMPDIR=/workspace/codex-identity-za/.proof/tmp npm_config_cache=/workspace/codex-identity-za/.proof/npm-cache npm test --prefix cli
```

Final TAP summary:

```text
1..67
# tests 67
# suites 0
# pass 67
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 23548.48591
```

```sh
PYTHONPATH=.proof/python /tmp/base-reliability-venv/bin/python -m ruff check --select E9,F tank/identity_device.py tank/identity_oidc.py tank/device_login.py ops/identity/setup.py tests/test_identity_za.py tests/test_identity_stack.py
docker compose -f ops/identity/docker-compose.yml config --no-interpolate --quiet
git diff --check
```

Results: `All checks passed!`; compose exit 0 with no output; diff check exit 0.
No environment values were rendered. CodeQL/restore GitHub checks were still
running while this evidence was prepared; no green CI claim is made here.

No founder browser screenshots, live sign-in, DNS/certificate changes, production
deployment, live credential revocation or ZA restore result are claimed. Founder
settings, exact tenant UUID from the existing read, valid edge/origin certificates
and founder acceptance remain deployment prerequisites in the guide.


## PR #589 second review: fixed hostname and existing certificate path

All fixed identity origins now use **https://auth-za.tervory.com**. Earlier
rule-10 fixes (pool release/single issuance, opt-in selection, independent backups,
expired completed setup, bounded JWKS refresh, principal/role rules and tenant
mapping) are kept. No image pin or certificate-resolver label was changed.

Changed file/line references:

- `ops/identity/docker-compose.yml:21,33,34,35,36`: external domain and all Login URLs.
  `:110,137,145`: all Traefik Host rules. `:127`: custom upstream Host header.
- `ops/identity/setup.py:14,140`: fixed assertion audience/issuer and API Host header.
- `tank/identity_oidc.py:15,46`: fixed issuer and same-origin endpoint guard.
- `cli/src/client.mjs:117`: fixed verification origin for both URLs.
- `cli/test/identity-za.test.mjs:7,8,15` and `tests/test_identity_za.py:47,129`:
  fake provider/CLI verification URLs and negative origin tests use the corrected host.
- `cli/README.md:24,26`, `cli/CHANGELOG.md:5`: new hostname in all instructions.
- `docs/ops/IDENTITY-ZA.md:12`: proxied A record and Cloudflare settings.
  `:26`: reuse existing ZA certificate issuance/renewal, no shared proxy changes
  and no new Cloudflare token. The repo's ZA compose has only Coolify's domain
  attachment comment and Tank port 8000; it contains no generated TLS labels or
  proxy certificate challenge configuration. `:40` gives exact read-only Coolify
  checks. `:61` stops deployment until the running resource's TLS router/resolver
  and existing issuance/renewal method are established. No certificate method is
  guessed. Certificates for the new hostname are verified during deployment.

All files were committed and pushed individually; each push fetched and merged
`origin/main`, which was already up to date. No shared proxy settings, DNS records,
firewall rules, new token or live settings were changed.

Exact validation commands:

```sh
docker run --rm -d --name tervory-identity-za-host-pg --label tervory.test=identity-za-host --memory=1g --cpus=1 -e POSTGRES_HOST_AUTH_METHOD=trust -p127.0.0.1::5432 postgres:16.15
docker port tervory-identity-za-host-pg 5432
TMPDIR=/workspace/codex-identity-za/.proof/tmp PYTHONPATH=.proof/python:tank POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32801/postgres /tmp/base-reliability-venv/bin/python -m pytest tests/test_identity_za.py tests/test_identity_stack.py tests/test_identity_backup.py tests/test_device_login.py tests/test_personal_tokens.py tests/test_command.py --disable-socket --allow-hosts=127.0.0.1,localhost -q
TMPDIR=/workspace/codex-identity-za/.proof/tmp npm_config_cache=/workspace/codex-identity-za/.proof/npm-cache npm test --prefix cli
docker compose -f ops/identity/docker-compose.yml config --no-interpolate --quiet
PYTHONPATH=.proof/python /tmp/base-reliability-venv/bin/python -m ruff check --select E9,F tank/identity_oidc.py ops/identity/setup.py tests/test_identity_za.py tests/test_identity_stack.py
git grep -n -E 'auth[.]za[.]tervory[.]com' -- .
git grep -n -E 'DNS[-]01|CF_DNS_API[_]TOKEN|dnschallenge' -- docs/ops/IDENTITY-ZA.md
git diff --check
docker stop tervory-identity-za-host-pg
```

Results: disposable Postgres mapped to `127.0.0.1:32801`; compose exit 0/no output;
Ruff `All checks passed!`; both grep searches exit 1/no matches (expected);
diff check exit 0. The container was stopped and automatically removed. Python
warnings are the same existing Pydantic/FastAPI warnings recorded above.

Python final summary:

```text
125 passed, 14 warnings in 82.35s (0:01:22)
```

CLI final TAP summary:

```text
1..67
# tests 67
# suites 0
# pass 67
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 19973.547646
```

No founder browser screenshots or deployment are claimed. The missing live
certificate issuance/renewal evidence is explicitly a read-only founder prerequisite
in step 1, along with the existing founder tenant/settings prerequisites later in
the guide. Tests are synthetic/offline, with only loopback database access allowed.
