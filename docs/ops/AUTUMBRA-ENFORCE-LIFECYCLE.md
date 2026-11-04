# Autumbra Enforce lifecycle — founder acceptance

Only the single `enforce-lifecycle` service holds the six lifecycle settings.
Watch and its browser hold none of them. The service runs one Uvicorn worker;
its count/check/write lock is per process. Do not scale or duplicate that service.
It has no ingress, published port, host mount or Docker socket, runs read-only
with ALL capabilities dropped and no-new-privileges, and has CPU/memory limits.
It mounts no data volume. It does not run Watch's lifespan or background probes.

## Founder setup on the test host

1. Use the **Coolify test host, never live Boston**, and the founder's own test
   tenant UUID, never a client. Create a dedicated Coolify team containing only
   Enforce resources and a project/environment in that team. Create a token
   with **read, write and deploy**, **without root or read:sensitive**. Deploy
   permission is required by Coolify's application DELETE endpoint, even though
   this implementation never calls deploy/start/restart. The token owner must
   remain a team administrator/owner. Values are entered by the founder only.
2. Keep the Ghost compose in normal mode. Lifecycle joins only the external
   `tervory-gw-ghost` network, shared with Watch, browser and Tank. It is not a
   sealed service. No volumes are renamed or pinned and no ingress is added.
   Give `AUTUMBRA_LIFECYCLE_KEY` only to Tank and enforce-lifecycle. Watch and
   browser receive neither this key nor the six lifecycle Coolify settings.
   Tank signs the timestamp, HTTP method, path and exact body with HMAC-SHA256.
   Lifecycle rejects missing signatures, Watch-key signatures and timestamps
   outside 60 seconds with 401. This separate key enforces the air gap on the
   shared network; it never falls back to Watch's `TANK_KEY_GHOST`.
3. Connect the GitHub App source to `Tervory-AI/tervory-tank`. On the isolated
   **enforce-lifecycle service only**, fill these six setting names:

   - `AUTUMBRA_COOLIFY_URL`
   - `AUTUMBRA_COOLIFY_TOKEN`
   - `AUTUMBRA_COOLIFY_PROJECT_UUID`
   - `AUTUMBRA_COOLIFY_SERVER_UUID` (test host)
   - `AUTUMBRA_COOLIFY_ENVIRONMENT` (environment name)
   - `AUTUMBRA_COOLIFY_GITHUB_APP_UUID`

   Never paste values into chat, Git, logs, screenshots or this document.
4. In `/chats`, enter `autumbra.enforce.create <your-test-tenant-uuid>` and
   confirm the existing card. Verify in your own browser that the dedicated
   team's named application exists and is **not deployed**. Its four supplied
   values are `TENANT_ID`, `ENFORCE_DATA_VOLUME`, `THREAT_PAYLOAD_QUEUE_VOLUME`,
   `ENFORCE_NETWORK_NAME`. Automatic and instant deployment are disabled.
5. Fill the receipt's `founder_fills` on the new Enforce application yourself.
   This list is parsed from the real compose file. Today: `AUTUMBRA_EDGE_CREDENTIAL`,
   `AUTUMBRA_UNDO_TOKEN_SECRET`, `SITE_NAME`, `CLOUDFLARE_API_TOKEN_ENFORCE`,
   `AUTUMBRA_HEALTH_SECRET`. Confirm `autumbra.enforce.list` and retain its $0
   receipt and the application's name, UUID and status.
6. Manually deploy the new application on the test host and verify healthy
   status. It fetches `main` and `/agents/ghost/docker-compose.enforce.yml`,
   including the existing egress and both health services. Run on that host:

   ```sh
   bash ops/autumbra-enforce-memory-measure.sh <enforce-container-name>
   bash ops/autumbra-enforce-isolation-check.sh <enforce-container-name>
   ```

   Retain full output. `DEFAULT_CONTAINER_CAP` stays None until the founder
   decides it after measurement. The current count comes from Coolify.
7. Confirm `autumbra.enforce.destroy <your-test-tenant-uuid>`. Verify removal of
   that application, its network and configuration, then confirm list again.
   **Volumes are retained for the founder to clean up separately.** A missing
   application returns absent. A foreign application's matching name is refused
   unless its tenant marker and all source fields match Autumbra's creation.

Every command requires a founder. Writes also require the bound confirmed card.
Successful reads/writes carry $0 code receipts. Unknown/refused/unconfigured
results become failed cards (409), never success. A definite POST refusal returns
refused; a definite PATCH refusal after creation returns created_unconfigured
with its UUID: destroy it, retaining volumes, then explicitly create again.
A timeout or 5xx after a mutation returns unknown with no automatic retry.
Inspect Coolify before repeating anything. Existing names block another create.
No environment-list or log endpoint is used; write responses are discarded.

## API contract checked 3 November 2026

The founder confirms these fields against his installed version at acceptance:

- [Private GitHub App creation](https://coolify.io/docs/api/endpoints/applications/create-private-github-app-application):
  project_uuid, server_uuid, environment_name, github_app_uuid, git_repository
  (repository URL), git_branch, build_pack=dockercompose, name, description,
  docker_compose_location, instant_deploy=false, is_auto_deploy_enabled=false.
  ports_exposes is optional in current docs; this compose application supplies
  no exposed/public port, so it is omitted. Confirm that omission on the host.
- [Bulk environment update](https://coolify.io/docs/api/endpoints/applications/update-envs-by-application-uuid):
  PATCH /applications/{uuid}/envs/bulk with data rows containing key, value,
  is_preview, is_buildtime, is_runtime and is_literal. Confirm the booleans use
  is_buildtime/is_runtime, not is_build_time, on the installed API.
- [Application DELETE](https://coolify.io/docs/api/endpoints/applications/delete-application-by-uuid):
  delete_configurations=true, delete_volumes=false,
  delete_connected_networks=true, docker_cleanup=false; the endpoint requires
  write and deploy permissions.
- [Permissions](https://coolify.io/docs/api/permissions): team scope, redacted read
  responses without read:sensitive, and token-owner role requirements.

No installed-version compatibility or live acceptance is claimed by offline
checks. Final evidence must include founder browser screenshots with setting
values concealed, create/list/destroy receipts, healthy status and both helper
outputs. Claude owns PR #622 and final-head Tank/Workspace CI evidence; this
builder never merges or enables deployment.

## M12 — founder approval of code fixes

Code-fix settings accept only approve_each and never. A legacy automatic value
is read as approve_each in both saved and mirrored settings, without rewriting
stored data. Shield mode retains all three choices. The automatic-fix email
paragraph is removed; no replacement wording or page was added.

Confirm `autumbra.fixes` in the founder's `/chats`. It reads the watcher's current
open matches and lists only valid dogfood fix plans in items. Existing card
Name/Summary/Status fields show the package, versions, advisory, severity and
match ID. Confirm `autumbra.fix.approve <match-id>` to approve one stored match.
The room resolves that ID; the card cannot supply repository or patch facts.
A non-dogfood repository gets the existing burned-brief response.

With `GHOST_PATCH_PR_ENABLED` off, the existing dry-run plan is returned. With
it on and the **existing**, repo-scoped `GHOST_GITHUB_TOKEN` configured by the
founder, the existing draft PR implementation runs and its pr_url appears under
the card's existing Review label. No token is created or inspected by this
builder. These setting names are passed to Watch's existing patch path only;
all six Coolify lifecycle names remain exclusive to enforce-lifecycle.
No code marks a PR ready, merges it or deploys it. Rules select the plan; no
model supplies a second opinion.

Founder evidence still required: current fixes in his browser, a confirmed
approval, and the actual resulting draft PR URL. Offline fake GitHub URLs do
not count as a created live PR or founder acceptance.

## M26 — standing blocks, explicit sharing and undo

Use two test tenant UUIDs belonging to the founder's own sites, never clients.
Watch's minute loop scans its existing per-tenant queue boxes. After an applied
block_ip receipt stands for 24 hours without an undo marker, the existing room
MemoryClient writes one stable client-tier blocked_address record through
Tank's same-box Ghost memory corridor. It contains only the address, receipt
ID, applied time and public source URLs from the receipt. Raw logs, site names
and customer data are excluded. Protected/own addresses are never recorded.
Stable IDs prevent duplicate records across restarts. Writes use index=false,
and listings read SQL records directly; neither path invokes embeddings or a
model. No new table or paid feed is introduced.

1. After the founder's own test block has stood for 24 hours, confirm
   `autumbra.blocks <tenant-A-uuid>`. Its items show standing records, record IDs,
   last_verified and private/published/expired state through existing card fields.
2. Enable tenant A's existing ghost publication policy through the existing
   founder memory controls (`POST /v1/memory/publish-policy`) with the reviewed
   identity inventory. No setting values or identity inventory belong in this
   document or chat. Policy remains off by default.
3. Confirm `autumbra.blocks.share <tenant-A-uuid> <record-id> [record-id ...]`.
   Every selected ID is checked against that tenant's current standing records,
   then submitted through **POST /v1/memory/publish**. Policy off returns disabled
   and logs it; policy on de-identifies, publishes and logs it. Publication retains
   only the generic code-only indexing flag, never customer metadata. Explicit
   public IP facts survive telephone-number scrubbing only after identity-inventory
   substitutions; the source's own CIDRs were already rejected by Watch.
4. Send a signed event for the same address on tenant B using the existing test
   event procedure. The address must occur in B's own raw log and pass B's own
   never-block/CIDR checks first. Only unexpired platform records contribute a
   count under source_data["autumbra.shared_blocks"]. This is evidence only:
   B's shield_mode and existing checks still decide whether anything happens.
   Seven days after last_verified, the shared record contributes nothing.
5. Undo A's source block through its existing signed/validated undo flow. Watch
   deletes the client source before rechecking the platform copy, preventing a
   concurrent publish from escaping cleanup. Any platform copy is withdrawn
   through Tank's existing founder memory corridor. The relay derives the
   original, still-authorized founder from the immutable publication log; the
   room cannot choose an actor or another agent. A single-record Hermes founder
   route verifies the source tenant and publication audit, deletes only that
   platform-tier row, and records withdrawn in the publish log. Client-tier or
   unpublished records cannot be deleted by this route. Pending cleanup pointers
   use existing room state and survive retries; failures are counted/logged without
   tenant or credential data. A withdrawn source cannot be republished.

Hermes startup widens the existing publish-log result constraint to include
withdrawn, in the same schema-setup transaction. No live SQL was run by this
builder; no generated memory block, tenant row or RLS policy was rewritten.
Withdrawal also queues existing index tombstones when needed. The new block
path itself never creates an index job. All memory traffic stays on the same
Tank/Hermes box, without cross-region proxying.

The new source_data is kept in receipt data. The existing weekly receipt page
and owner email select their existing fields and do not print it. No Figma
wording, label, page or renderer was added. Founder evidence remains pending:
24-hour record, explicit policy/share and publish log, B's signed event receipt
with the shared count, B's mode result, expiry and source-undo withdrawal.

## Verification and handoff

Branch: codex/autumbra-w3. Final source/test revision before this documentation
update: 1677c17aa30bb0e247258b85dd6fd4b8f139d5ab. Each completed file was committed
and pushed to this branch. No push failed; origin/main was never merged.
PR #622 remains a draft; no label, ready-state or merge action was performed.

Exact commands, run from /workspace/codex-autumbra-w3:

```sh
PYTHONPATH=/workspace/codex-autumbra-w3/.test-deps /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_autumbra*.py tests/test_ghost*.py tests/test_tisan*.py tests/tisan_promotion --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --basetemp=/workspace/codex-autumbra-w3/.pytest-tmp --tb=short > /workspace/codex-autumbra-w3/.regression-final.log 2>&1
```

**806 passed, 22 skipped, 27 warnings in 96.24s.** All existing Tisan tests in
this selection pass. An earlier broad run had 791 passed, 22 skipped and five
failures: old automatic-fix/network expectations and a no-lifespan test lacking
its settings store. Those tests were updated for the requested behavior; the
focused affected-file rerun passed all 77 tests before the green broad run.
Subsequent timestamp, card-field and canonical-name/cap refinements were checked
with the final focused command below.

```sh
PYTHONPATH=/workspace/codex-autumbra-w3/.test-deps /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_autumbra_coolify_lifecycle.py tests/test_autumbra_w3_fixes.py tests/test_autumbra_w3_blocks.py tests/test_ghost_patch_connect.py tests/test_ghost_routes.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --basetemp=/workspace/codex-autumbra-w3/.pytest-cards-final --tb=short > /workspace/codex-autumbra-w3/.cards-final.log 2>&1
```

**74 passed, 15 warnings in 11.08s** at the final source/test revision. Includes
36 lifecycle cases, fake GitHub approval, fake SQL/Hermes/Tank publication and
withdrawal, live-format epoch times, 24-hour hold/early undo/own CIDRs, deduplication,
expiry, retry after deleting the client source, zero-encoder writes, complete
record pagination, and signed cross-tenant evidence obeying its own mode.

```sh
PYTHONPATH=/workspace/codex-autumbra-w3/.test-deps /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_agent_memory_records.py tests/test_hermes_memory.py tests/test_agent_chassis.py tests/agent_memory/test_chat.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --basetemp=/workspace/codex-autumbra-w3/.pytest-memory --tb=short
```

**47 passed, 12 skipped, 15 warnings in 8.55s**. The skipped integration cases
require a disposable database. A later combined focused/core/secret run was
**105 passed, 12 skipped in 38.30s**. No model, external API or live database was
used to check this work.

```sh
node tests/autumbra_w3_cards.cjs
/home/ammosync/trigger-crm-venv312/bin/ruff check agents/ghost agents/_chassis/chassis/memory.py hermes/records.py hermes/publishing.py hermes/record_routes.py hermes/service.py hermes/deidentify.py tank/ghost_routes.py tank/memory_routes.py tank/command.py tests/test_autumbra_w3_blocks.py tests/test_autumbra_w3_fixes.py --select E9,F --output-format concise
python3 -m compileall -q agents/ghost agents/_chassis/chassis/memory.py hermes tank/ghost_routes.py tank/memory_routes.py tank/command.py
git diff --check
```

Four actual existing-card projections passed; Ruff, compilation and diff checks
passed. These are data-projection checks, not browser screenshots. The missing
Qdrant client initially prevented existing Hermes tests from collecting; it was
installed only into this checkout, preserving the existing Pydantic pin:

```sh
/home/ammosync/trigger-crm-venv312/bin/python -m pip install --target /workspace/codex-autumbra-w3/.test-deps qdrant-client==1.20.0 pydantic==2.10.6 httpx==0.28.1 > /workspace/codex-autumbra-w3/.memory-deps.log 2>&1
```

Install succeeded. Earlier isolated test dependencies and workspace npm
installation remain local to this checkout; no dependency pin was changed.

CI is the full-suite test of record. The final-head Tank and Workspace jobs have
not appeared in GitHub's check rollup/run list; they are recorded as **not run /
not available**, never green. PR #622's previous ci run at 09c38641 is not proof
for this revision. Current exact-head CI status is recorded in the PR body.
Live founder browser screenshots and all acceptance steps above remain pending.

Deploy-on-merge impact: both main stacks (Tank/Workspace/Hermes configuration),
Ghost and Tisan room sources, and **all rooms selected by the shared chassis
change**, including registered regional copies. No deployment was triggered by
this builder. Founder merge and the existing deployment workflow remain required.

## Source locations

Every changed file; line is the first changed location relative to the starting main.

| File and line | Change |
| --- | --- |
| `.env.example:532` | Setting names only: isolated Coolify permissions and existing draft-PR settings. |
| `agents/_chassis/chassis/memory.py:33` | Backward-compatible stable/code-only writes and paged literal reads. |
| `agents/ghost/Dockerfile:10` | Package the existing Tisan Coolify client only. |
| `agents/ghost/app.py:8` | Reuse lifecycle routes; stored-match approval; standing-record loop, undo reconciliation and signed evidence. |
| `agents/ghost/client_settings.py:12` | Two code-fix modes and legacy read normalization; three shield modes unchanged. |
| `agents/ghost/docker-compose.yml:35` | Hardened lifecycle service on Ghost gateway; Watch has no lifecycle names or lifecycle key. |
| `agents/ghost/enforce_api.py:1` | Shared lifecycle registration and a standalone service without Watch lifespan. |
| `agents/ghost/enforce_apply.py:158` | Retain source_data in receipts without affecting apply decisions. |
| `agents/ghost/enforce_lifecycle.py:16` | Coolify lifecycle, real cap count, provenance, volume retention and precise outcomes. |
| `agents/ghost/fix_approval.py:1` | Eligible dogfood plans over the existing watcher store. |
| `agents/ghost/owner_email.py:110` | Remove the automatic-code-fix paragraph without replacement copy. |
| `agents/ghost/shared_blocks.py:1` | 24-hour deduplicated facts, expiry and durable source-undo withdrawal. |
| `agents/ghost/tenant_queue.py:82` | Normalize legacy mirrored fix mode without losing shield settings. |
| `agents/ghost/threat_payload.py:266` | Bound the single shared-evidence key and positive count. |
| `agents/ghost/threat_queue.py:246` | Carry server-derived evidence through the existing queue. |
| `agents/tisan/promotion.py:138` | Reusable client settings and opt-in lifecycle response handling; Tisan defaults retained. |
| `docker-compose.yml:319` | Tank-only lifecycle HMAC key; no separate control network. |
| `docs/ops/AUTUMBRA-ENFORCE-LIFECYCLE.md:1` | Setup, API citations, three acceptance gates and exact evidence. |
| `hermes/deidentify.py:8` | Preserve explicit public IP facts after identity inventory scrubbing. |
| `hermes/publishing.py:82` | Audit-proven single platform withdrawal, withdrawn-source guard and code-only publication. |
| `hermes/record_routes.py:8` | Founder-only withdrawal and bounded record pagination. |
| `hermes/records.py:83` | Code-only records, paged reads and idempotent audit-result constraint widening. |
| `hermes/service.py:46` | Explicit no-index writes, with no legacy model fallback. |
| `tank/command.py:57` | Founder tool schemas, Confirm dispatch and deterministic command planning. |
| `tank/ghost_routes.py:28` | Founder tools, isolated routing, scoped memory corridor and audit-bound undo relay. |
| `tank/main.py:643` | Narrow Ghost route authorization, including validated single-record client deletes. |
| `tank/memory_routes.py:45` | Existing founder corridor withdrawal and preserved disabled-policy result. |
| `tests/autumbra_w3_cards.cjs:1` | Offline regression proof for the requested modes, isolation, authentication and factual card projection. |
| `tests/test_autumbra_a2.py:479` | Offline regression proof for the requested modes, isolation, authentication and factual card projection. |
| `tests/test_autumbra_client_settings_email.py:72` | Offline regression proof for the requested modes, isolation, authentication and factual card projection. |
| `tests/test_autumbra_coolify_lifecycle.py:1` | Offline regression proof for the requested modes, isolation, authentication and factual card projection. |
| `tests/test_autumbra_enforce_process.py:156` | Offline regression proof for the requested modes, isolation, authentication and factual card projection. |
| `tests/test_autumbra_fifth_review_security.py:245` | Offline regression proof for the requested modes, isolation, authentication and factual card projection. |
| `tests/test_autumbra_w3_blocks.py:1` | Offline regression proof for the requested modes, isolation, authentication and factual card projection. |
| `tests/test_autumbra_w3_fixes.py:1` | Offline regression proof for the requested modes, isolation, authentication and factual card projection. |
| `tests/test_ghost_inventory.py:205` | Offline regression proof for the requested modes, isolation, authentication and factual card projection. |
| `tests/test_ghost_routes.py:169` | Offline regression proof for the requested modes, isolation, authentication and factual card projection. |
