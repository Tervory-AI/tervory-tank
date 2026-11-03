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
2. Deploy the reviewed main-stack mapping that creates
   `tervory-enforce-control` with `internal: true` and attaches Tank. The Ghost
   compose joins this network as external; only its lifecycle service joins it,
   not Watch or the browser. Provision the existing Coolify HTTPS API endpoint
   on that internal network, with DNS/alias and a trusted certificate matching
   the origin in `AUTUMBRA_COOLIFY_URL`. An internal network has no public
   internet route: a public-only API origin will remain unreachable. Do not
   weaken the network or attach Watch to it. Only Tank holds the HMAC key on the
   caller side; the existing require_tank check protects all lifecycle routes.
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
