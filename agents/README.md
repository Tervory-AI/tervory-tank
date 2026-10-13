# Agent boxes

Each Squad member (Tiger, Market Lab, Radix, Tisan, Zenas, later Base) runs in its own box. The box has its own computer, files, schedule, and Tank key. `_chassis/` is the shared library. `_template/` is a working agent you copy.

The chassis knows no industry. Vocabulary, field names, and scoring stay in an engine. The engine passes them in.

## What a box has

- `GET /health` — the process is up and can reach the database.
- `POST /jobs` — enqueue `{tenant_id, kind, input, run_at?}`.
- `GET /jobs/{id}?tenant_id=` — that tenant's job only.
- A worker over `agent_<name>.jobs`. A running job older than its timeout goes back to queued. A failed attempt is tried again until `max_attempts` (3), then marked failed.
- A scheduler over `agent_<name>.schedules`. Five-field cron, inside the process. No system cron.
- Files under `/data/<tenant_id>/`. `..` is rejected.
- A Tank client that sends only this box's key. No model keys in the box.
- `remember` / `recall` / `forget` — empty until Hermes (C7).
- `render(url, session)` — empty until Tiger's browser pool (C8).

Logs are JSON lines on stdout: agent, tenant_id, job id. Keys are never logged.

## Make a new agent

About ten minutes, from this repo.

1. Copy `agents/_template/` to `agents/<name>/` (lowercase, digits, underscores — the schema will be `agent_<name>`).
2. In the new `app.py`, set the default `AGENT_NAME`, add job handlers, and add any schedules. Handlers receive a `JobContext` and return a dict. Do not put industry words in this code.
3. In `docker-compose.yml`, copy the `agent-template` service:
   - service name `agent-<name>`
   - `dockerfile: agents/<name>/Dockerfile` (or keep building from `agents/` and point `COPY` at the new folder)
   - `AGENT_NAME: <name>`
   - `TANK_KEY: ${TANK_KEY_<NAME>}` — this box receives only its own key
   - `mem_limit: 512m` and `cpus: 0.5`
   - its own volume at `/data`
   - its own network `net_<name>` only. Do not attach it to `default` or to another agent's network.
4. Attach `postgres`, `tank`, and `tiger` (the browser) to `net_<name>`. When Hermes exists, attach it too. Agents never share a network, so one box cannot call another.
5. Give Tank the same key: add `TANK_KEY_<NAME>: ${TANK_KEY_<NAME>:-}` under the `tank` service. Tank hashes it (SHA-256) into `tank.agent_keys`. The value is never written to a log.
6. Add `TANK_KEY_<NAME>=` to `.env.example` with a one-line comment, and put the real value in Coolify only.
7. Open a PR. Do not push to `main`.

The template's check is a `ping` job and a heartbeat every five minutes (`*/5 * * * *`) on the platform tenant. After deploy, `GET /health` on `agent-template` is ok, and a ping job reaches `done`. From inside that container, `http://tank:8000/health` answers. A name that lives only on the default network (for example `workspace`) does not resolve. A second agent on `net_<other>` is unreachable for the same reason.
