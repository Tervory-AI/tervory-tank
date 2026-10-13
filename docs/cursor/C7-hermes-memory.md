# C7 — Hermes: memory for every Squad member

> **Room setup:** follow `docs/cursor/ROOMS.md` exactly (proven in C6b). It overrides anything below about networks, compose or database access.

**Hermes is a shared service, not an agent:** it lives in the MAIN docker-compose.yml (next to qdrant), on `default` plus every existing `tervory-gw-*` network (today: `tervory-gw-template`), and its README tells future agent tasks to add their corridor to Hermes. Auth: agent keys are the env-held `TANK_KEY_<AGENT>` values (hash compare, same as Tank's `require_key`), not a DB lookup. Update `agents/check_isolation.sh` so `hermes` is an allowed neighbour on the corridor (and still everything else is blocked). Lane: `hermes/` (new), main `docker-compose.yml` (add the hermes service only), `agents/_chassis/chassis/memory.py`, `agents/check_isolation.sh`, tests.

**Goal:** each agent remembers what it learns, per client, and can recall it by meaning. Memory is private to one agent and one tenant. Depends on C6.

**Files you may change:** `hermes/` (new service), `docker-compose.yml` (add the service), `agents/_chassis/` (fill in the memory client).

## Service (`hermes/`)
Python 3.12, FastAPI, qdrant-client, **fastembed** (open-weight embedding model, e.g. BAAI/bge-small-en-v1.5, runs on CPU inside the container: no provider key, client text never leaves our server). Internal only (no public domain).
- Auth: the same per-agent keys as Tank (`tank.agent_keys`, read-only), so Hermes knows which agent is calling. Workspace key may read (for a future "what does Tiger know" page), never write.
- `POST /memories {tenant_id, text, kind, source, meta}` → embeds and stores. `source` is required (URL, ledger id, file, or "human").
- `POST /recall {tenant_id, query, kind?, limit}` → nearest memories with score, source, created_at.
- `DELETE /memories/{id}` and `DELETE /tenants/{tenant_id}` (forget a client entirely).
- One Qdrant collection per agent (`mem_<agent>`); every point carries `tenant_id`; every query is filtered by the caller's agent collection AND `tenant_id`. An agent can never name another agent's collection.
- Dedupe: a new memory with cosine ≥ 0.97 to an existing one in the same tenant updates it (bump `seen`, keep sources).
- Later (not this PR): Mem0-style extraction of facts from long texts through Tank.

## Chassis
`remember(tenant_id, text, kind, source)`, `recall(tenant_id, query)`, `forget(id)` call Hermes with the agent's key.

**Done when:** tests prove (a) agent A cannot recall agent B's memories, (b) tenant X cannot see tenant Y's, (c) dedupe works, (d) delete-tenant removes everything; the template agent from C6 remembers its heartbeat count and recalls it after a restart.
