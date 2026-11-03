# Autumbra Enforce lifecycle — founder test-host acceptance

Gate 1 creates and removes a separate Git-backed Coolify application per tenant.
Creation never deploys it. Use the founder's own test tenant UUID, never a client.
No Workspace page or visible wording changes. All three commands propose the
existing Confirm cards in `/chats`; nothing executes until Confirm.

1. Create a dedicated Coolify team containing only Enforce resources. Create its
   token with **read, write and deploy**, **without read:sensitive**. Do not use
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
3. On the **Autumbra Watch** resource, fill these six names:

   - `AUTUMBRA_COOLIFY_URL`: Coolify HTTPS origin, optionally ending `/api/v1`.
   - `AUTUMBRA_COOLIFY_TOKEN`: the dedicated team's token.
   - `AUTUMBRA_COOLIFY_PROJECT_UUID`: that team's project.
   - `AUTUMBRA_COOLIFY_SERVER_UUID`: the test server.
   - `AUTUMBRA_COOLIFY_ENVIRONMENT`: the environment name.
   - `AUTUMBRA_COOLIFY_GITHUB_APP_UUID`: the connected GitHub App source.

   Deploy the reviewed Watch image and setting mappings through the normal
   founder-controlled merge/deploy flow. No builder opens the environment panel.
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
   and verify that only that exact resource is removed, including its volumes,
   networks and configuration. Confirm `autumbra.enforce.list` again and verify
   its absence. An already-missing resource returns `absent`.

A timeout or server error after a mutation returns `unknown` and is never retried
automatically. Inspect the resource in the dedicated team before taking another
action. A create is refused while its exact name exists; it will not silently
replace or deploy a partially configured resource. No environment-list, logs,
start or deploy API is called by this lifecycle.

The founder's browser screenshots, command receipts, health and helper output
are required acceptance evidence. Offline tests alone do not establish live
acceptance. This branch does not claim that acceptance has occurred.

API contracts: [private GitHub App creation](https://coolify.io/docs/api/endpoints/applications/create-private-github-app-application),
[bulk environment write](https://coolify.io/docs/api/endpoints/applications/update-envs-by-application-uuid),
[application deletion flags](https://coolify.io/docs/api/endpoints/applications/delete-application-by-uuid).
