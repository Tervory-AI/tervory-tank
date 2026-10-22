# How an agent gets its room (proven in C6b, 13 Oct 2026: 21/21 isolation checks passed)

Every Squad member (Tiger, Market Lab, Zenas, RIG, Tisan, Radix) gets exactly this. Copy `agents/_template/`; do not invent a new pattern.

## The room
1. **Own Coolify resource.** `agents/<name>/docker-compose.yml`, deployed as its own Coolify "Docker Compose" resource: Base Directory `/agents/<name>`, Compose Location `/docker-compose.yml`, no domain (except RIG's public API), Predefined Network setting = "Isolated network only". Build context `..` (agents/) so the chassis is included. `mem_limit`/`cpus` set; healthcheck on `/health`; volume for `/data`.
2. **One private corridor.** The agent's only network is `tervory-gw-<name>` (`external: true` in the agent's compose). In the MAIN `docker-compose.yml`, declare it (see Deploy order) and add it to `tank`, `postgres`, and any shared service the agent needs (`hermes` after C7; Tiger's browser service for agents that browse). Nothing else joins it. Never put two agents on one corridor.
3. **Own database login.** Add `AGENT_DB_PASSWORD_<NAME>: ${AGENT_DB_PASSWORD_<NAME>:-}` to the `agent-roles` service env in the MAIN compose (roles are provisioned generically for every non-empty `AGENT_DB_PASSWORD_*`). The agent's compose builds `DATABASE_URL=postgresql://agent_<name>:${AGENT_DB_PASSWORD_<NAME>}@postgres:5432/${POSTGRES_DB:-tervory}`. Never give an agent `POSTGRES_USER`/`POSTGRES_PASSWORD`.
4. **Own Tank key.** `TANK_KEY_<NAME>` on Tank (main compose) and as `TANK_KEY` in the agent's compose.
4b. **Memory (Hermes, C7).** In the MAIN compose, add `tervory-gw-<name>` to the `hermes` service's networks and `TANK_KEY_<NAME>: ${TANK_KEY_<NAME>:-}` to its environment. Without both, Hermes cannot be reached or does not recognise the agent. The agent calls `http://hermes:8000` through the chassis `MemoryClient`; it never calls Qdrant.
5. **Proof.** `agents/check_isolation.sh <container>` must print all PASS on the server before the agent does real work. Add the agent's expected neighbours (e.g. hermes) to the script's allowed list if the brief adds a shared service.

## Deploy order (from 14 Oct 2026: one op, nothing by hand)
1. **Corridor:** in the MAIN `docker-compose.yml`, declare the new corridor as a compose-managed network with a fixed name, so deploying the main stack creates it. No server command:
   ```yaml
   tervory-gw-<name>:
     name: tervory-gw-<name>          # add `internal: true` for a room with no internet (Radix)
   ```
   (The agent's own compose still lists it as `external: true`.) Corridors created before this date stay `external: true`.
2. **Merge** the PR (Claude reviews first).
3. **Claude runs one op:** `coolify-ops` with `op=room-setup room=<name>` (plus any extra room-only secrets in `names`). It creates the Coolify app, generates `AGENT_DB_PASSWORD_<NAME>` and `TANK_KEY_<NAME>` inside GitHub Actions (masked, never seen by anyone), writes them to the main app and the room, then deploys the main app and the room.
4. **Claude runs the isolation check.** Only then does the agent take jobs.

The founder does nothing for a new room except merge. Public rooms (Rig) also need one DNS record.

## Rules
- Shared services (Tank, Postgres, Hermes, Tiger's browser) live in the MAIN stack and join every agent's corridor. Agents never live in the main stack.
- Hex passwords only (`openssl rand -hex 24`), never logged.
- Main-compose changes are additive: add networks/env lines; do not change existing services otherwise.

## Sealed rooms (SEAL-1, 21 Oct 2026)
A **sealed** service is one declared only on internal networks: Base's `base-sandbox` and `base-browser`, Tiger's `tiger-browser`, and `agent-radix`.
- **Why raw compose.** In its normal mode Coolify adds its own app network to every service without `network_mode`. That network is not internal, so a sealed service would reach the internet and every other service in the app. In **Raw Compose Deployment** mode Coolify deploys the file as written and adds only its labels.
- **The marker.** A compose file with a sealed service starts with `# coolify: raw compose`. Base, Tiger and Radix do. `tests/test_room_seal.py` simulates normal mode on every `agents/*/docker-compose*.yml` and fails if a sealed service would leak in a file without the marker, or if a service on an internal network declares `ports:`.
- **A raw file needs nothing from Coolify:** every variable comes through explicit `environment:` interpolation (no `env_file`), every service names its networks, no `ports:`, and existing volumes are `external` with their live names, so data survives the switch. Tiger's existing data volume is pinned to its live name (`fro6z8xlh579owlp1wwrjr8n_agent-tiger-data`), because Coolify rejects `${VAR:?…}` in external volume names; its new browser volume has the separate name `tervory-tiger-browser-data`.
- **Founder step, once per room:** Coolify > the app > **Advanced** > turn on **Raw Compose Deployment**, then redeploy. This setting is not available through Coolify's API.
- **Proof after every deploy of Base, Tiger or Radix:** on the host, `bash ops/seal-check.sh` (read-only). It prints one line per room and must say `sealed` for agent-base, agent-tiger and agent-radix and exit 0. `LEAK: <container> on <network>` and exit 1 mean a sealed container is on a non-internal network. `agent-base: NOT FOUND`, `agent-tiger: NOT FOUND` or `agent-radix: NOT FOUND` (exit 1) means an expected room is not running; it is never skipped. Rooms are found by the `coolify.applicationUuid` and `com.docker.compose.service` labels, so normal-mode names (`<service>-<uuid>-<timestamp>`) and Raw Compose names (`<uuid>-<service>-1`) both work. Declared corridors are allowed: agent-base, base-brain and base-browser-gateway on `tervory-gw-base`; tiger-browser-gateway on `tervory-gw-tiger`; egress-proxy on `egress`. `agent-tiger` joins only its corridor, so it gets no exception for joining the browser network. A Tiger browser or gateway on an extra outbound network is a leak; Tiger without an internal network is `NOT SEALED`.
- **Browsers hold no Tank key.** `base-browser` and `tiger-browser` run untrusted pages; each accepts work only from its own browser gateway's address, and only the gateway talks to Tank.

## Base brain pilot (AGENT-1)

Base retains its room, database login and corridor. Its Compose resource adds
`base-brain` (pinned Nous Hermes Agent), `base-sandbox` (an unprivileged WASI exec
service), `base-browser` (Chromium) and `base-browser-gateway`. Only Base's brain
joins the sandbox's internal network. Only the gateway joins the browser's
internal network. No host ports, host Docker socket, nested daemon, privileged
container, added capabilities or shared host PID/network namespace are allowed.

The executor has a read-only root and tmpfs. Only one run workspace is exposed
to its CPython/WASI command, with no sockets, credentials, native shell or other
run files. Outputs return to Base's own volume. Browser cookies/history are
separate per tenant. Four sites may run in parallel with a few seconds between
same-site pages. Public HTTP(S) sites and PDFs are permitted; private/internal
addresses are blocked and DNS/redirects are re-checked. The CONNECT proxy binds
only to the browser-network interface. Captchas/bot checks are **needs a person**;
only simple age-confirmation buttons outside forms may be clicked. The browser
checks URLs without outside DNS; gateway DNS checks pin HTTP/CONNECT addresses.
WebRTC cannot use non-proxied UDP. Browser memory is 2 GB; queue waits return
busy after 20 seconds.

Base's Skala context uses its own gateway. Tiger no longer joins
`tervory-gw-base`; Tank reaches Tiger through `tervory-gw-tiger`. Other room
deployments retain their existing browser pattern until their own migration.

Before taking real jobs, run
`python agents/base/check_brain_isolation.py ROOM BRAIN SANDBOX BROWSER GATEWAY`
on the authorized cloud host. It checks all five health states, exact network
membership, no host mounts/ports/provider keys, privilege/capability/PID/network
settings, Base's database role, denied egress, isolated scratch execution and
browser-only proxy reachability. The generic single-container gate stays
unchanged for other rooms. See [Base's runbook](../../agents/base/BRAIN.md).

Brain tasks and pipeline phases use authenticated start-then-poll endpoints.
When the brain fails before starting pipeline work, Base cancels it and runs
today's pipeline, retaining a fallback receipt. If it fails after the free pass,
Base stops the brain, waits for work, and runs paid continuation with a
`pipeline_continue_fallback` step. Work already started is retained.
`SANDBOX_KEY` belongs only to brain and executor, authenticates `/exec` and never
reaches scratch code. Confirm Coolify adds no outbound tool networks before
the live pilot.

Receipts are available to the work panel through the existing tenant-scoped
`GET /v1/base/batches?tenant_id=...` response: each batch has `brain_tasks`, with
task ID, status and full receipt. The receipt includes recall/remember, approved
skills, model ledger IDs with cost and baseline, and browser/sandbox actions.
The Base import screen hides unapproved preview; COMMAND-1 consumes this receipt contract.

## Ghost (GHOST-1 phase 1)

Ghost's corridor is `tervory-gw-ghost`. Only Tank and Postgres join it from
the main stack. The separate `agents/ghost/docker-compose.yml` resource has
`agent-ghost` and its own `ghost-browser`; neither shares a browser, volume,
model credential, Docker socket or control-plane credential with another room.
The founder explicitly limited main-stack changes to this corridor, the
`TANK_KEY_GHOST` variable on Tank, and `AGENT_DB_PASSWORD_GHOST` on agent-roles.
Shared Hermes is **not** attached to this corridor.

The Ghost DB role is reserved by room setup, but its password is not passed
to either Ghost container. Incident state and deterministic recall use SQLite
on Ghost's private `/data` volume. This is not the Hermes Agent brain: adoption
of the AGENT-1 adapter and Ghost's own memory service belongs to GHOST-2.
BUCKET-1 must supply its isolated `tervory-ghost` bucket integration in GHOST-2;
a volume is not presented as an R2 bucket.

Tank endpoints:
- Founder Workspace identity only: `GET /v1/ghost/incidents`,
  `POST /v1/ghost/look`, `/message`, `/alert`, and
  `/incidents/{id}/resolve`.
- Ghost key only: `POST /v1/ghost/check`, `POST /v1/ghost/actions`, and
  `GET`/`POST /v1/ghost/radix`. Ghost also uses the existing zero-cost vendor
  receipt endpoint. It has no policy, admin or Skala approval access.
- The action route permits only `rerun_failed_deploy` for the fixed Boston
  app list and `restart_crashed_room` for the fixed room list. ZA is excluded.
  It must observe failed/crashed state, pass the observed revision to the
  executor, record every call, and never retry pending or uncertain requests.

**Recovery disabled in phase 1:** `app.state.ghost_recovery_backend` has no production
implementation. Its contract is `observe(target) -> {state, revision}` and
`execute(action, target, revision, request_id) -> 'queued'`. The executor must
atomically compare the observed revision, enforce the same action/target
allowlist, and rerun the exact failed revision (not today's main). No backend,
Coolify credential or external service has been fabricated. Missing integration
returns 503 with a Tank ledger receipt and makes no production change.
`COOLIFY_TOKEN_GHOST_ACTIONS` is documented by name only for GHOST-2: a Coolify
token with read and deploy permissions, retained by Tank, never Ghost. It is
not wired into any service in phase 1.

GHOST-2 follows the AGENT-1, BUCKET-1 and COMMAND-1 C merges. It adds read-only Workspace/Tank log-pattern, deploy, main-CI and
Radix finding feeds; founder-approved worker dispatch; AGENT-1 brain/sandbox;
BUCKET-1 storage. These are visible as disconnected in `/admin/ghost`. The
current watcher covers fixed public-site health/latency/DNS/certificates/headers
and room health. It cannot claim full monitoring coverage until the feeds exist.

Private `ghost.incident` candidates join the shared training intake and founder
review list with the monthly `ghost:incident:YYYY-MM` family. They retain
`public=false`; intake does not approve them or export them to public training.

After the founder merges and the operator deploys phase 1: run the existing
`room-setup room=ghost`, check corridor isolation, and open `/admin/ghost` as the
founder. Press Look, verify step IDs against `tank.ledger` for `PLATFORM_TENANT`,
and inject a failing health fixture in a nonproduction room to inspect its brief.
Resolve only after the original probe passes and the founder confirms the cause
and fix. `GET /gold/candidates` on Ghost must then show the family
`ghost:incident:YYYY-MM`; another identical alert must recall that solution.
Recovery requests are scoped and deduplicated in `tank.ghost_recovery`. Do not
test recovery by restarting production during PR review.

## Rig brain pilot (RIG-2)

Rig uses Raw Compose with its existing public API on `agent-rig:8000` and the
`tervory-gw-rig` corridor. Only that service keeps the public domain. Its separate
`rig-brain`, internal-only `rig-sandbox`, internal-only `rig-browser`, and
`rig-browser-gateway` follow Base's isolated execution shape. They share no Base
or Tiger processes, volumes, keys or browser state. The brain uses only approved
Rig skills, its tenant's Hermes memory and Tank's `agent.rig.think` policy, with
the paid-work pause and task receipts. Existing Rig R2 storage stays on agent-rig.

Before merging, enable Raw Compose on agent-rig and set `RIG_DATA_VOLUME_NAME`
to the verified existing live `/data` volume, plus the Rig-only `SANDBOX_KEY_RIG`.
Do not guess the live volume name or let Compose replace it. Keep the proxy's
existing reachability to the Rig corridor. Run `ops/seal-check.sh` after deployment;
Rig is now an expected room and its public API is allowed only on its corridor.
See [Rig's box runbook](../../agents/rig/BOX.md) for the authenticated question,
receipt and public-health checks. Stand-in catalogue data only on Boston; live
ZA shopper data is not part of this pilot.

## Regions

South African clients and South African law stay in South Africa. United States clients stay in the United States. Same code, deployed twice. The region is `TANK_REGION`: `za` or `us-east`. It is not a fork.

`docker-compose.za.yml` is the whole South Africa stack: its own Postgres, Redis, Qdrant, Hermes, LiteLLM, Tank and backup volume. The Zenas room is its own Coolify resource on the SA server: `agents/zenas/docker-compose.za.yml`. Model keys reach only LiteLLM; the room gets only its Tank key and its `agent_zenas` login. Nothing in that file names a US host. There is no replication and no network shared with Boston. Coolify may list both servers; it keeps deploy settings, not client data.

Tank is the only public service, at `za.tervory.com`. The corridor `tervory-gw-zenas` is created by `docker-compose.za.yml`. The Zenas service joins only that corridor. Tank, Postgres and Hermes join it as well. The agent uses the `agent_zenas` login, not the Postgres superuser.

On `/v1/route`, `/v1/tasks` and `/v1/skala/*/run`, a missing home is this server's `TANK_REGION`, so the live Workspace and agent rooms keep working. An empty, unknown, or other-region home is refused and nothing is stored. `/v1/zenas/*` does not fill a missing home in. The home on that request is a cross-check. The authoritative home is `agent_zenas.tenants.home_region`. The founder sets it once, to `za` or `us-east`, from `/admin/homes`, and that call goes through this proxy to `POST /tenants`. The column is not added here. In `za`, a prompt that still contains a personal identifier is refused for every provider that is not running in South Africa. No such model is active yet. `za-local` is a commented slot in `litellm/config.za.yaml`.

The pool-loader service is not in this file. It is added on the ZA box only, and it uses this stack's database.
