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

## Regions

South African clients and South African law stay in South Africa. United States clients stay in the United States. Same code, deployed twice. The region is `TANK_REGION`: `za` or `us-east`. It is not a fork.

`docker-compose.za.yml` is the whole South Africa stack: its own Postgres, Redis, Qdrant, Hermes, LiteLLM, Tank, Zenas room, file volume and backup volume. Nothing in that file names a US host. There is no replication and no network shared with Boston. Coolify may list both servers; it keeps deploy settings, not client data.

Tank is the only public service, at `za-api.tervory.com`. The corridor `tervory-gw-zenas` is created by that compose file. The Zenas service joins only that corridor. Tank, Postgres and Hermes join it as well. The agent uses the `agent_zenas` login, not the Postgres superuser.

A Tank refuses a tenant whose home is the other region and does not store that tenant's text. In `za`, a prompt that still contains a personal identifier is refused for every provider that is not running in South Africa. No such model is active yet. `za-local` is a commented slot in `litellm/config.za.yaml`.

The pool-loader service is not in this file. It is added on the ZA box only, and it uses this stack's database.
