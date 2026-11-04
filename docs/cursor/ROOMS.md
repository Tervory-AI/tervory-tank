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

Keep Raw Compose enabled and provision the Rig-only `SANDBOX_KEY_RIG`.
The existing `/data` volume remains pinned external to
`59f8cnpelzwsyte1atyjc4fv_agent-rig-data`, preserving main's deployment fix.
Only agent-rig joins the existing proxy network `59f8cnpelzwsyte1atyjc4fv` as
well as its corridor; its explicit Traefik labels retain the public HTTPS route.
Run `ops/seal-check.sh` after deployment. Rig is now an expected room; any extra
attachment, including the proxy network on a private service, fails the check.
See [Rig's box runbook](../../agents/rig/BOX.md) for the authenticated question,
receipt and public-health checks. Stand-in catalogue data only on Boston; live
ZA shopper data is not part of this pilot.

## Tiger brain provision (TG3, 3 Nov 2026)

Tiger's optional Hermes image reuses `agents/rig/Dockerfile.brain` and its pinned
upstream build. The shared standby entrypoint exposes Tiger health only; it has
no task API. No caller or escalation is added: `tiger.price_extract`,
`tiger.price_structured` and `tiger.price_ocr` are code skills.

Both `tiger-brain` (2 GiB limit) and `tiger-sandbox` (512 MiB limit) carry the
Compose `brain` profile. Normal deployments exclude both. The separate
`TIGER_BRAIN_ENABLED` setting defaults to false and remains reserved for a future
caller. The brain joins only the Tiger corridor and its own sandbox network;
the executor joins only that internal sandbox network, with a read-only root,
tmpfs workspaces, dropped capabilities and no volume or Tank key. Only brain and
executor receive `SANDBOX_KEY_TIGER`; use the existing `coolify-ops` room-setup
with that extra name, without exposing its value.

**Capacity update, 3 Nov 2026:** the dated Boston `ops/box-memory.sh` snapshot is
recorded in the Zenas section below, with raw per-container usage and limits.
Keep Tiger's profile disabled until the founder enables it. The snapshot and
requested limits are not capacity approval.

After an authorized normal deploy, run `bash ops/seal-check.sh` on Boston and
require `agent-tiger ... sealed` with no Tiger brain/sandbox running. Recheck the
founder's existing Tiger /chats tools. If the optional profile is later enabled,
both services must be present and pass the exact-network checks; use
`agents/base/check_brain_isolation.py` with Tiger's five container names.

## Regions

South African clients and South African law stay in South Africa. United States clients stay in the United States. Same code, deployed twice. The region is `TANK_REGION`: `za` or `us-east`. It is not a fork.

`docker-compose.za.yml` is the whole South Africa stack: its own Postgres, Redis, Qdrant, Hermes, LiteLLM, Tank and backup volume. The Zenas room is its own Coolify resource on the SA server: `agents/zenas/docker-compose.za.yml`. Model keys reach only LiteLLM; the room gets only its Tank key and its `agent_zenas` login. Nothing in that file names a US host. There is no replication and no network shared with Boston. Coolify may list both servers; it keeps deploy settings, not client data.

Tank is the only public service, at `za.tervory.com`. The corridor `tervory-gw-zenas` is created by `docker-compose.za.yml`. The Zenas service joins only that corridor. Tank, Postgres and Hermes join it as well. The agent uses the `agent_zenas` login, not the Postgres superuser.

On `/v1/route`, `/v1/tasks` and `/v1/skala/*/run`, a missing home is this server's `TANK_REGION`, so the live Workspace and agent rooms keep working. An empty, unknown, or other-region home is refused and nothing is stored. `/v1/zenas/*` does not fill a missing home in. The home on that request is a cross-check. The authoritative home is `agent_zenas.tenants.home_region`. The founder sets it once, to `za` or `us-east`, from `/admin/homes`, and that call goes through this proxy to `POST /tenants`. The column is not added here. In `za`, a prompt that still contains a personal identifier is refused for every provider that is not running in South Africa. No such model is active yet. `za-local` is a commented slot in `litellm/config.za.yaml`.

The pool-loader service is not in this file. It is added on the ZA box only, and it uses this stack's database.

## Zenas standby brain, both boxes (3 Nov 2026)

`zenas-brain` and `zenas-sandbox` reuse the pinned Rig Hermes image, shared
health-only standby and Base WASI sandbox. No task API or caller is added.
Both services use the `brain` profile; `ZENAS_BRAIN_ENABLED` defaults to false.
The brain has a 2 GiB / 1 CPU limit, the sandbox 512 MiB / 0.5 CPU: planned
additional limits of 2.5 GiB and 1.5 CPU per box. Both roots are read-only;
workspaces are tmpfs, capabilities dropped and privileges/PIDs bounded. Each
brain has its own regional data volume; the sandbox has no persistent volume,
Tank key, provider key or bucket. All service URLs resolve inside that box.
The room's existing bucket and data remain regional.

Tank enables only the owning Zenas room key. Requests require a matching local
home region; ZA never forwards to Boston. Before model policy or gateway work,
the existing approved `zenas.scope` rules run in code, including criminal
refusal; ambiguous/out-of-scope prompts cannot fall back to a model here.
Only the room's existing approved skills export; candidate submission remains
Base-only. No model policy or provider is added.

Boston measurement, **3 Nov 2026, 14:20 PST (22:20 UTC)**, run read-only with
`ops/box-memory.sh` on `ammosync-us-boston`, before this task's test containers:

| Measure | Bytes / count |
| --- | ---: |
| Total memory | 33,648,410,624 |
| Used memory | 10,821,517,312 |
| Available memory | 22,826,893,312 |
| All container memory limits | 32,078,036,992 |
| Running container memory limits | 32,078,036,992 |
| Containers / running | 64 / 61 |
| Containers with no memory limit | 29 |

Per-running-container usage and limits are retained in
[the raw Boston snapshot](../../tests/zenas_brain/evidence/boston-memory.txt).
Available memory is a snapshot, not an allocation; the plan's limits are not
measured usage and do not authorize enabling either brain.

**ZA: pending, read after deploy with ops/box-memory.sh**. Planned additional
limits remain 2.5 GiB / 1.5 CPU; no ZA SSH target or credentials are available to
builders, and none are requested. Keep both disabled defaults until the founder
turns the brain on. No larger box is requested.

Both room files use Raw Compose. Existing room volume declarations and mounts
remain unchanged from main on both boxes. The brain mounts only its own new
`zenas_brain_data`; it never mounts room data. Any future room-data access must
use the room's existing tools through Tank.
After an authorized profile deployment, run `ops/seal-check.sh` on each host and
require Zenas brain and sandbox sealed. The isolation checker takes three Zenas
container names; Base/Tiger retain five. Hosted CI and both postdeploy host
proofs remain separate from local offline verification.

## Remaining squad standby brains (3 Nov 2026)

Each room below is provisioned independently, using the pinned Rig Hermes build,
`agents/_brain/standby.py` health-only entrypoint and Base's WASI sandbox. No model
caller, escalation, paid route, approved skill or candidate-submission permission
is added. Owning keys use Tank's existing policy, paid-work pause, model refusal,
tenant accounting and receipts. A room value outside the fixed allowlist is
refused before SQL. These new rooms remain in the existing US-only brain region
boundary; no ZA deployment or forwarding is introduced.

| Room | Flag (default false) | New optional limits |
| --- | --- | --- |
| Market Lab | `MARKET_LAB_BRAIN_ENABLED` | brain 2 GiB / 1 CPU; sandbox 512 MiB / 0.5 CPU; browser 2 GiB / 0.5 CPU; gateway 128 MiB / 0.25 CPU |

All added services carry profile `brain`. A normal Compose deployment starts
none of them. The flag is reserved for a future caller: enabling a profile or
setting a flag does not itself add model work. Founder enablement and capacity
approval remain required. Existing volumes and their mounts are unchanged from
main `de113044`; each brain mounts only its new brain volume, each new browser
only its new browser volume, and sandboxes/gateways have no persistent volume.
Private sandbox and browser networks are per project, internal and disjoint.
Brain/gateway corridor attachments are the owning room's existing Tank corridor,
as in Tiger; no other room's corridor or keys are supplied. Public browsing uses
the existing checked proxy. Vault/login access is not provisioned for new rooms.

Boston snapshot: **3 Nov 2026 16:35 PST (4 Nov 00:35 UTC)**, read-only
`ops/box-memory.sh`, before this task's test containers:

| Measurement | Bytes |
| --- | ---: |
| Total | 33,648,410,624 |
| Used | 11,334,434,816 |
| Available | 22,313,975,808 |
| All container limits | 32,212,254,720 |
| Running container limits | 32,212,254,720 |

65 containers, 62 running; 29 have no memory limit. See the complete per-container
[snapshot](../../tests/room_brains/evidence/boston-memory.txt). Available memory is
a snapshot, not an allocation; summed limits and unlimited containers require
fresh host checks before enabling any profile. No larger box is requested.

This is deployment configuration. Each room compose change redeploys that room;
Tank changes also redeploy the main stack and its configured ZA counterpart.
Raw Compose Deployment must be enabled in Coolify for the files carrying its
marker. Preserve the existing Compose project identity when switching modes so
unchanged room volumes retain their current identity. No volume migration or
replacement is part of this work. After deployment, run `ops/seal-check.sh` and,
if the optional profile is authorized, the isolation checker with the room's
container names. Offline fixtures do not replace that host check.
