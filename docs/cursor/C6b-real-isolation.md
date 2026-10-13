# C6b — Real isolation under Coolify (before any real agent moves in)

**Why:** after C6 deployed, a check from inside `agent-template` showed Coolify attaches every service in the tervory-tank stack to its own shared network (`xnmc0jkz8j9i5jh1jwanbsfv`). The box could resolve tank, postgres, tiger AND workspace, redis, qdrant, litellm, searxng. `net_template` alone does not isolate anything under Coolify. The box also holds the main Postgres superuser credentials.

**Goal:** an agent box can reach Tank (and its own database login) and nothing else, verified on the server.

**Files you may change:** `agents/` (incl. a new `agents/_template/docker-compose.yml`), `docker-compose.yml` (remove the `agent-template` service and `net_template`; let tank join the external agent networks), `tank/schema.sql` (additive), `agents/README.md`, `.env.example`, tests.

## Design
1. **Each agent is its own Coolify resource**, deployed from its own compose file in this repo (`agents/<name>/docker-compose.yml`, Coolify "Docker Compose" resource pointing at that path). Coolify then gives it its own resource network, separate from Tank's stack.
2. **One external bridge network per agent**, `tervory-gw-<agent>` (created once on the server: `docker network create tervory-gw-<agent>`; document this as a one-time step Claude runs). Tank joins every `tervory-gw-*` network as an external network; the agent joins only its own. Nothing else joins. So the agent reaches Tank, Tank reaches the agent, and agents never reach each other or the rest of the stack.
3. **Database access through its own role, not the superuser.** Option A (preferred, lean): the agent's DB traffic goes through Tank's network path to Postgres using a dedicated role `agent_<name>` with `USAGE, CREATE` on schema `agent_<name>` only, no access to `tank.*`, `base.*`, other agents' schemas or `public`. Postgres joins `tervory-gw-<agent>` as well; the role is the boundary. Tank creates the roles at start from env `AGENT_DB_PASSWORD_<AGENT>` (idempotent; never logs the password); `REVOKE ALL ON SCHEMA tank, base, public FROM agent_<name>`. Option B (if you find A unsound, say why in the PR): a small per-agent Postgres inside the agent's own stack.
4. **Hermes and Tiger's browser** (later) also join each `tervory-gw-*` network, nothing else.
5. **Template:** `agents/_template/docker-compose.yml` shows the pattern (external network, mem/cpu limits, healthcheck, env names only).

## Proof (write it as a script Claude runs on the server: `agents/check_isolation.sh <agent-container>`)
From inside the agent container: `tank` and `postgres` resolve and answer; `workspace`, `redis`, `qdrant`, `litellm`, `searxng`, `tiger` (until C8 wires it) and any other agent do NOT resolve. As the agent's DB role: can create/read in `agent_<name>`, gets permission denied on `tank.ledger`, `base.records` and another agent's schema. Script prints PASS/FAIL per check, read-only except a temp table in its own schema that it drops.

**Done when:** tests for the role/grant SQL (idempotent, no superuser leak) pass; PR documents the exact Coolify steps (new resource, compose path, env vars) and the one-time network commands; then stop for Claude's review. Claude deploys, runs the proof script, and only then do C7/C8/C9 proceed.
