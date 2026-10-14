# How an agent gets its room (proven in C6b, 13 Oct 2026: 21/21 isolation checks passed)

Every Squad member (Tiger, Market Lab, Zenas, RIG, Tisan, Radix) gets exactly this. Copy `agents/_template/`; do not invent a new pattern.

## The room
1. **Own Coolify resource.** `agents/<name>/docker-compose.yml`, deployed as its own Coolify "Docker Compose" resource: Base Directory `/agents/<name>`, Compose Location `/docker-compose.yml`, no domain (except RIG's public API), Predefined Network setting = "Isolated network only". Build context `..` (agents/) so the chassis is included. `mem_limit`/`cpus` set; healthcheck on `/health`; volume for `/data`.
2. **One private corridor.** The agent's only network is the external `tervory-gw-<name>` (`external: true`). In the MAIN `docker-compose.yml`, add `tervory-gw-<name>` (external) to `tank`, `postgres`, and any shared service the agent needs (`hermes` after C7; Tiger's browser service for agents that browse). Nothing else joins it. Never put two agents on one corridor.
3. **Own database login.** Add `AGENT_DB_PASSWORD_<NAME>: ${AGENT_DB_PASSWORD_<NAME>:-}` to the `agent-roles` service env in the MAIN compose (roles are provisioned generically for every non-empty `AGENT_DB_PASSWORD_*`). The agent's compose builds `DATABASE_URL=postgresql://agent_<name>:${AGENT_DB_PASSWORD_<NAME>}@postgres:5432/${POSTGRES_DB:-tervory}`. Never give an agent `POSTGRES_USER`/`POSTGRES_PASSWORD`.
4. **Own Tank key.** `TANK_KEY_<NAME>` on Tank (main compose) and as `TANK_KEY` in the agent's compose.
4b. **Memory (Hermes, C7).** In the MAIN compose, add `tervory-gw-<name>` to the `hermes` service's networks and `TANK_KEY_<NAME>: ${TANK_KEY_<NAME>:-}` to its environment. Without both, Hermes cannot be reached or does not recognise the agent. The agent calls `http://hermes:8000` through the chassis `MemoryClient`; it never calls Qdrant.
5. **Proof.** `agents/check_isolation.sh <container>` must print all PASS on the server before the agent does real work. Add the agent's expected neighbours (e.g. hermes) to the script's allowed list if the brief adds a shared service.

## Deploy order (Claude runs this; never merge before step 1)
1. Server: `docker network create tervory-gw-<name>` (a main-compose deploy fails if the network is missing).
2. Founder: one password per agent, pasted once into a Coolify **Project shared variable** `AGENT_DB_PASSWORD_<NAME>` (Project → Shared variables); both the main resource and the agent resource reference it as `{{project.AGENT_DB_PASSWORD_<NAME>}}`. Same for `TANK_KEY_<NAME>`. (Radix's corridor is created with `--internal`; see C10.)
3. Merge the PR → main stack redeploys → `agent-roles` creates the login.
4. Create the agent's Coolify resource (settings above), deploy.
5. Run `check_isolation.sh`; only then does the agent take jobs.

## Rules
- Shared services (Tank, Postgres, Hermes, Tiger's browser) live in the MAIN stack and join every agent's corridor. Agents never live in the main stack.
- Hex passwords only (`openssl rand -hex 24`), never logged.
- Main-compose changes are additive: add networks/env lines; do not change existing services otherwise.
