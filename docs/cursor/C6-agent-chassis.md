# C6 — Agent chassis: one box per Squad member

**Goal:** every Squad member (Tiger, Market Lab, Radix, Tisan, Zenas, later Base) runs in its own sealed box with its own computer, files, schedule and identity. Build the chassis once as a template; C8–C10 copy it per agent. Read `AGENTS.md` first (rule 9: core skills know no industry).

**Files you may change:** `agents/` (new), `docker-compose.yml` (add services/networks/volumes only), `tank/schema.sql` (additive), and in `tank/main.py` ONLY `require_key` and `run_one_skill` as described below. Do not touch `run_route`, the cache, shadow/graduation or the Base worker.

## The chassis (`agents/_chassis/`)
Python 3.12, FastAPI, asyncpg, httpx. A small library + a runnable template:
- `GET /health`, `POST /jobs` (enqueue `{tenant_id, kind, input, run_at?}`), `GET /jobs/{id}`.
- **Jobs:** a resumable worker over table `agent_<name>.jobs` (status queued/running/done/failed, attempts, error, result jsonb). Restart-safe: a running job older than its timeout returns to queued.
- **Schedule:** table `agent_<name>.schedules` (cron expression, tenant_id, kind, input, enabled, last_run). A scheduler loop enqueues due jobs. No external cron.
- **Files:** a named volume mounted at `/data`; helpers `save_file(tenant_id, name, bytes)` / `read_file` that always write under `/data/<tenant_id>/`.
- **Tank client:** `route(tenant_id, task_type, messages)` and `run_skill(tenant_id, skill_id, input)` over HTTP to Tank with the agent's own key. The box holds no model or provider keys, ever.
- **Memory client:** stub interface `remember / recall / forget` that C7 fills in (Hermes).
- **Browser client:** stub `render(url, session)` that C8 fills in (Tiger's browser pool).
- Logs to stdout as JSON lines with agent, tenant_id, job id.

## Identity and isolation
- **Per-agent Tank keys.** New table `tank.agent_keys (agent text PK, key_hash text, created_at)`. `require_key` accepts the existing `TANK_API_KEY` (Workspace, unchanged) OR an agent key (compare SHA-256), and exposes which agent is calling. Keys come from env `TANK_KEY_<AGENT>` and are hashed into the table on start; never logged.
- **Skills only through Skala, only your own.** In `run_one_skill`: when the caller is an agent, refuse (403) a skill whose `agent` field is a different agent, unless the skill's yaml lists the caller in a new optional `shared_with: [..]`. Ledger rows from that call carry the calling agent.
- **Network:** each agent gets its own compose network `net_<agent>`; Tank, Hermes and the browser join every agent network; agents never share one. An agent cannot reach another agent (test it).
- **Database:** each agent its own schema `agent_<name>`, created by the chassis on start (idempotent). Every query filtered by `tenant_id`.
- **Resources:** `mem_limit` and `cpus` per agent service (start 512m / 0.5).

## Deliverables
1. `agents/_chassis/` library + `agents/_template/` (a minimal agent using it: a `ping` job kind and a 5-minute heartbeat schedule).
2. Compose: the template running as `agent-template` on its own network, to prove isolation.
3. `agents/README.md`: how to make a new agent from the template in under 10 minutes.
4. Tests (`tests/`, no network, no DB needed for unit tests): cron due-time, job retry/timeout, tenant path safety in `save_file` (no `..`), agent-key check, skill gate (own skill ok, other agent's skill 403, shared_with ok).

**Done when:** PR merged-ready with tests green; `agent-template` deploys, `/health` ok, a ping job runs, its ledger row (if any) shows agent `template`, and from inside `agent-template` Tank answers but another agent network is unreachable. Write in the PR what the founder must add in Coolify (the new `TANK_KEY_*` names).
