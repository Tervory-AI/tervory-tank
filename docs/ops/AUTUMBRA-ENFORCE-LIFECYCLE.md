# Autumbra Enforce lifecycle — founder test-host acceptance

**Security revision status: blocked; do not configure or deploy this branch.**
The six lifecycle setting mappings have been removed from Watch. The isolated
`enforce-lifecycle` service is not implemented yet. Do not put a control-plane
write token on Watch. Only one instance of the eventual isolated service may
receive these settings; the lifecycle lock is per process.

The requested read/write-only token conflicts with the currently published
[Coolify delete endpoint](https://coolify.io/docs/api/endpoints/applications/delete-application-by-uuid),
which explicitly requires both write and deploy. The
[permissions reference](https://coolify.io/docs/api/permissions) defines read
as redacted inspection, write as resource mutation, and deploy as deployment
operations; it also requires the token owner to remain a team administrator or
owner for privileged calls. The requested token must have read/write only,
without deploy, root or read:sensitive. Compatibility must be established from
the installed version's API contract before the isolated service is implemented.
No installed Coolify version or corresponding API documentation is available in
this checkout or through a connected Coolify tool. No permission was broadened.


Gate 1 creates and removes a separate Git-backed Coolify application per tenant.
Creation never deploys it. Use the founder's own test tenant UUID, never a client.
No Workspace page or visible wording changes. All three commands propose the
existing Confirm cards in `/chats`; nothing executes until Confirm.

1. Create a dedicated Coolify team containing only Enforce resources. Create its
   token with **read and write**, **without deploy, root or read:sensitive**. Do not use
   the Watch inventory token. Keep this team's project and source access separate
   from other Tervory resources. The founder enters all values in Coolify; no
   value belongs in chat, Git, screenshots, logs or acceptance evidence.
2. Select the **Coolify test host**, never live Boston, as the server in that
   team. Create its project and environment. Connect the existing GitHub App
   source to `Tervory-AI/tervory-tank`, granting access to that repository. New
   applications use `main`, build pack `dockercompose` and compose location
   `/agents/ghost/docker-compose.enforce.yml`. Automatic and instant deployment
   are both disabled. The compose file is fetched from Git at deployment time;
   its existing egress and health services remain included.
3. After the compatibility blocker is resolved, fill these six names on the
   isolated **enforce-lifecycle** resource only (not yet implemented):

   - `AUTUMBRA_COOLIFY_URL`: Coolify HTTPS origin, optionally ending `/api/v1`.
   - `AUTUMBRA_COOLIFY_TOKEN`: the dedicated team's token.
   - `AUTUMBRA_COOLIFY_PROJECT_UUID`: that team's project.
   - `AUTUMBRA_COOLIFY_SERVER_UUID`: the test server.
   - `AUTUMBRA_COOLIFY_ENVIRONMENT`: the environment name.
   - `AUTUMBRA_COOLIFY_GITHUB_APP_UUID`: the connected GitHub App source.

   Deployment of the isolated service remains blocked as stated above. No builder opens the environment panel.
   Empty configuration retains the existing fixture execution behavior.
4. In `/chats`, enter `autumbra.enforce.create <your-test-tenant-uuid>` and confirm
   its card. Inspect the dedicated team in your own browser. The new application
   is named `autumbra-enforce-<your-test-tenant-uuid>`, is **not deployed**, and
   contains exactly these four plan-supplied setting values: `TENANT_ID`,
   `ENFORCE_DATA_VOLUME`, `THREAT_PAYLOAD_QUEUE_VOLUME`, `ENFORCE_NETWORK_NAME`.
   Record the receipt and resource UUID with settings values concealed.
5. The receipt's `founder_fills` is derived from the checked-in compose file.
   Fill those names on the **new Enforce resource** yourself. Today they are:
   `AUTUMBRA_EDGE_CREDENTIAL`, `AUTUMBRA_UNDO_TOKEN_SECRET`, `SITE_NAME`,
   `CLOUDFLARE_API_TOKEN_ENFORCE`, `AUTUMBRA_HEALTH_SECRET`. Never copy values into
   this document or chat. Run `autumbra.enforce.list` in `/chats`, confirm, and
   retain the resource's name, UUID, status and $0 code receipt.
6. Deploy the new Enforce application manually on the **test host**. Verify its
   healthy status, then on that host run the existing helpers against its
   Enforce container:

   ```sh
   bash ops/autumbra-enforce-memory-measure.sh <enforce-container-name>
   bash ops/autumbra-enforce-isolation-check.sh <enforce-container-name>
   ```

   Retain their complete output. Follow [memory measurement](AUTUMBRA-ENFORCE-MEMORY.md)
   and [isolation proof](AUTUMBRA-ENFORCE-ISOLATION.md). `DEFAULT_CONTAINER_CAP`
   remains `None`; only the founder sets it after measurement. Counts already
   come from the dedicated team's current Coolify applications.
7. In `/chats`, enter `autumbra.enforce.destroy <your-test-tenant-uuid>`, confirm,
   and verify that only that exact resource is removed, including its networks and configuration. **Volumes are kept for the founder
   to clean up separately**; lifecycle deletion never requests volume removal. Confirm `autumbra.enforce.list` again and verify
   its absence. An already-missing resource returns `absent`.

A timeout or server error after a mutation returns `unknown` and is never retried
automatically. Inspect the resource in the dedicated team before taking another
action. A create is refused while its exact name exists; it will not silently
replace or deploy a partially configured resource. A definite settings-write
refusal after creation returns `created_unconfigured` and its UUID; destroy
that resource (keeping volumes), then explicitly create again. No environment-list, logs,
start or deploy API is called by this lifecycle.

The founder's browser screenshots, command receipts, health and helper output
are required acceptance evidence. Offline tests alone do not establish live
acceptance. This branch does not claim that acceptance has occurred.

API contracts: [private GitHub App creation](https://coolify.io/docs/api/endpoints/applications/create-private-github-app-application),
[bulk environment write](https://coolify.io/docs/api/endpoints/applications/update-envs-by-application-uuid),
[application deletion flags](https://coolify.io/docs/api/endpoints/applications/delete-application-by-uuid).

## Gate 1 implementation and offline evidence

Branch: `codex/autumbra-w3`. Final code/test commit before this evidence-only
update: `9df5820e`. Work was performed only in `/workspace/codex-autumbra-w3`.
Every completed source file was committed and pushed to this branch. No push
failed. No PR was opened, labelled or merged; Claude owns that review step.

| File and starting line | Change |
| --- | --- |
| `agents/ghost/enforce_lifecycle.py:32`, `:282` | Six setting names; copied-client import with repo fallback; list, fresh-count planning, exact-name create/destroy, four settings, dynamic founder names and unknown receipts. Writes serialize in the existing single Watch worker. |
| `agents/tisan/promotion.py:138` | Shared client accepts setting-name arguments with unchanged Tisan defaults; opt-in list responses, ambiguous-write classification and discarded environment-write responses. Default Tisan call behavior remains unchanged. |
| `agents/ghost/Dockerfile:11` | Copies only Tisan's existing `promotion.py` as `/app/enforce_coolify.py`. |
| `agents/ghost/docker-compose.yml:35` | Empty-default mappings for the six founder-supplied names. |
| `.env.example:533` | Names and dedicated-team permission comment; no values. |
| `agents/ghost/app.py:1208` | Configured Coolify execution and authenticated list route; existing unconfigured fixture path/message retained. |
| `tank/ghost_routes.py:51`, `:127` | Optional corridor timeout, founder-only proxies and list's $0 `code_receipt`. |
| `tank/command.py:57`, `:490`, `:938`, `:1245`, `:1487`, `:1681`, `:1846` | Founder-only adapters, confirmed write dispatch and explicit commands planned in code into pending Confirm cards. |
| `tests/test_autumbra_coolify_lifecycle.py:1` | 18 offline cases; fake API, exact four values, duplicates/count/cap, tenant deletion flags, ambiguity/no retry, fixtures, compose isolation, packaging, founder access, configured routes, concurrency and DEBUG-log token exclusion. |
| `docs/ops/AUTUMBRA-ENFORCE-LIFECYCLE.md:1` | Founder setup, test-host acceptance steps and this evidence. |

Deploy-on-merge will select Ghost and Tisan, including their configured regional
copies, because their room sources changed. No live settings or resources were
changed. The Enforce compose file, default cap and founder cap decision text are
unchanged. No Workspace/UI files changed.

Exact successful validation commands (repository root unless stated otherwise):

```sh
PYTHONPATH=/workspace/codex-autumbra-w3/.test-deps /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_autumbra_coolify_lifecycle.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --basetemp=/workspace/codex-autumbra-w3/.pytest-focused --tb=short
```

**18 passed, 4 warnings in 4.21s** at the final code/test commit. The new suite
uses `httpx.MockTransport`; no real Coolify, model, Docker or external-network
call supplies its results. Existing room background probes are blocked by the
offline network restrictions.

```sh
PYTHONPATH=/workspace/codex-autumbra-w3/.test-deps /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_autumbra*.py tests/test_ghost*.py tests/test_tisan*.py tests/tisan_promotion --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --basetemp=/workspace/codex-autumbra-w3/.pytest-tmp --tb=short > /workspace/codex-autumbra-w3/.regression.log 2>&1
```

**775 passed, 22 skipped, 1 failed in 407.20s.** The sole failure was the
unchanged `test_seal_checks_enforce_observer_and_both_proxies[outward]`, whose
fake-Docker subprocess exceeded its existing 60-second timeout. This run
collected the then-current 16 lifecycle cases; the two subsequently added
concurrency/default-message cases are included in the final 18-case run above.
All existing Tisan tests passed unchanged. The timeout case was rerun exactly:

```sh
PYTHONPATH=/workspace/codex-autumbra-w3/.test-deps /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q 'tests/test_autumbra_cloudflare_live.py::test_seal_checks_enforce_observer_and_both_proxies[outward]' --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --basetemp=/workspace/codex-autumbra-w3/.pytest-recheck --tb=short
```

**1 passed in 3.53s.** The combined run is recorded as a timeout, not claimed green.

```sh
node --test tests/tisan_gold_actions.test.cjs
PYTHONPATH=/workspace/codex-autumbra-w3/.test-deps /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_secrets.py --basetemp=/workspace/codex-autumbra-w3/.pytest-secrets
/home/ammosync/trigger-crm-venv312/bin/ruff check agents/ghost/enforce_lifecycle.py agents/ghost/app.py agents/tisan/promotion.py tank/ghost_routes.py tank/command.py tests/test_autumbra_coolify_lifecycle.py --select E9,F
python3 -m py_compile agents/ghost/enforce_lifecycle.py agents/ghost/app.py agents/tisan/promotion.py tank/ghost_routes.py tank/command.py
git diff origin/main --check
```

Respectively: **1 Node test passed; 2 secret tests passed in 38.11s; all Ruff
checks passed; compilation passed; diff check passed**.

Test setup commands (dependencies installed in this checkout only):

```sh
/home/ammosync/trigger-crm-venv312/bin/python -m pip install --target /workspace/codex-autumbra-w3/.test-deps pytest-socket
/home/ammosync/trigger-crm-venv312/bin/python -m pip install --no-deps --target /workspace/codex-autumbra-w3/.test-deps selectolax==0.3.27 PyJWT==2.15.1 phonenumbers==9.0.42
/home/ammosync/trigger-crm-venv312/bin/python -m pip install --no-deps --target /workspace/codex-autumbra-w3/.test-deps redis==5.2.1 tiktoken==0.14.0 rapidfuzz==3.10.1 feedparser==6.0.14 feedparser-sgmllib==2.1.0
/home/ammosync/trigger-crm-venv312/bin/python -m pip install --target /workspace/codex-autumbra-w3/.test-deps cryptography==50.0.2
```

All succeeded. From `workspace/`:

```sh
npm ci --no-audit --no-fund --cache /workspace/codex-autumbra-w3/.npm-cache > /workspace/codex-autumbra-w3/.npm-ci.log 2>&1
```

Succeeded: **45 packages installed**. Before setup, the focused command without
`PYTHONPATH` failed on unrecognized pytest-socket flags. The first isolated
collection lacked `selectolax`; broad collection later lacked `cryptography`.
An intermediate focused run had test-harness failures for the omitted founder
allowlist and the room's expected 404 denial; these tests were corrected and
all 18 now pass. An earlier broad command omitted CI's
`--allow-hosts=127.0.0.1,localhost,::1`: **736 passed, 22 skipped, 39 failed**
(35 loopback-socket failures, three then-uncorrected founder-harness cases and
one missing JavaScript dependency). The corrected command and results are
recorded above. No outside network was enabled for those tests.

Acceptance remains pending: the founder must configure the six names, complete
the own-tenant test-host create/list/manual-deploy/health/memory/isolation/destroy
flow, and supply browser screenshots and command receipts with values concealed.
No founder screenshot, live health result or live isolation result exists from
this builder run. Final-head Tank and Workspace PR CI results are also pending
Claude opening the PR. Neither offline tests nor this document claim DONE.

## Security revision — partial fixes, blocked before gate 2

This section supersedes the initial gate 1 handoff. No merge or main update was
performed. Security revision source/test head before this evidence update:
`60635d38` on `codex/autumbra-w3`.

- `tank/ghost_routes.py:144`: create and destroy now resolve Command identity,
  require their founder tool and the bound confirmed card before any room call.
  Non-success outcomes return 409 with the review's exact reconciliation text;
  successful outcomes add a $0 code receipt.
- `agents/ghost/enforce_lifecycle.py:159`, `:301`, `:350`, `:369`, `:384`, `:394`:
  retain volumes; match complete resource names; create a tenant provenance
  marker; distinguish refused POST from created-but-unconfigured PATCH; require
  all source/provenance fields before deletion.
- `agents/ghost/app.py:1266`: list returns only names, UUIDs and status; missing
  configuration uses the requested message.
- `tank/command.py:1846`: check recognized tool names before authorization and
  use the review's usage error.
- `agents/ghost/docker-compose.yml:33`: lifecycle mappings removed from Watch;
  browser also receives none. This removes the unsafe write-token mapping
  without pretending a working isolated replacement exists.
- `.env.example:534`: setting names reserved for the isolated service only,
  read/write without deploy or sensitive-read permissions.
- `tests/test_autumbra_coolify_lifecycle.py:1`: Confirm bypass returns 409;
  correctly bound card succeeds; tenant admins are refused; retained volumes,
  missing/foreign provenance, definite POST/PATCH refusals, unknown outcomes,
  redirects and actual confirmed-dispatch routing are tested. Watch's six-name
  credential seal is asserted against its real compose file.
- `docs/ops/AUTUMBRA-ENFORCE-LIFECYCLE.md:3`: operational blocker, permission
  sources, retained-volume instructions and created-unconfigured recovery.

Commands and results for this revision:

```sh
PYTHONPATH=/workspace/codex-autumbra-w3/.test-deps /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_autumbra_coolify_lifecycle.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --basetemp=/workspace/codex-autumbra-w3/.pytest-focused --tb=short
```

Intermediate regression before the final seal/provenance/dispatch cases:
**25 passed, 4 warnings in 3.76s**.

```sh
PYTHONPATH=/workspace/codex-autumbra-w3/.test-deps /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_autumbra_coolify_lifecycle.py tests/test_autumbra_lifecycle_fixture.py tests/test_autumbra_tenant_isolation_routes.py tests/test_ghost_routes.py tests/tisan_promotion --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --basetemp=/workspace/codex-autumbra-w3/.pytest-focused --tb=short
/home/ammosync/trigger-crm-venv312/bin/ruff check agents/ghost/enforce_lifecycle.py agents/ghost/app.py tank/ghost_routes.py tank/command.py tests/test_autumbra_coolify_lifecycle.py --select E9,F
git diff --check
```

**82 passed, 3 skipped, 15 warnings in 25.18s; Ruff passed; diff check passed.**
No live network, Coolify resource, setting value, database or model was used.

Exact missing prerequisites and unfinished work:

1. **Gate 1, review items 6/9/10:** the installed Coolify version's API contract
   proving the requested application DELETE works with read/write **without
   deploy**. The current public DELETE reference requires deploy. The installed
   version is absent from the repository's operations documentation and no
   Coolify connector is available. The isolated service, its Tank corridor and
   internal API reachability are not implemented. Only the unsafe Watch
   mappings have been removed. Do not configure or deploy this branch.
2. **Gate 2:** not started, because the requested preceding gate 1 security
   revision is blocked.
3. **Gate 3:** read-only prerequisite inspection found the brief's explicit
   stop condition. `hermes/records.py:448` selects and deletes only client-tier
   records. `hermes/service.py:223` delegates `/memories/{memory_id}` to that
   method, then falls back to vector deletion; it does not delete a published
   platform-tier SQL record. `hermes/record_routes.py` has no platform-record
   DELETE endpoint. Missing: an existing authenticated, tenant/source-bound
   platform-record withdrawal path. No sharing or standing-block pipeline was
   added, and Hermes was not changed outside this brief.

No founder browser acceptance or final-head Tank/Workspace CI result is claimed.
