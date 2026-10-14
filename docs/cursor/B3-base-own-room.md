# B-3 — Base in its own room (out of Tank)

**Do this first** (founder, 14 Oct: no agent runs outside its own room).

**Goal:** Base becomes a Squad member like the others: its own room, its own database login, its own memory. Tank goes back to being only the router and skills library. Same results, same API for the Workspace.

**Lane:** this brief allows moving the Base worker, batch runner and `/v1/base/*` handlers out of `tank/main.py`, and changes to `agents/base/` (new, from `agents/_template/`), `docker-compose.yml` (additive per ROOMS.md: compose-managed corridor `tervory-gw-base`, `TANK_KEY_BASE` on tank and hermes, `AGENT_DB_PASSWORD_BASE` on agent-roles), `tank/schema.sql` (additive), and tests.

- **Tables:** `base.records` moves to `agent_base.records` with a one-time, logged copy (additive: the old table is left in place, read-only, until Claude retires it). Keep every column.
- **Skills stay in Skala** (`tank/skills/base.*`). Base runs them through the chassis, and model rungs go through Tank like every other agent.
- **Tank keeps `/v1/base/*` as a thin proxy** to `http://agent-base:8000`, so the Workspace does not change.
- Base's room needs internet (it reads websites through Tiger's browser and SearXNG): join it to Tiger's browser and SearXNG on its corridor, and add both to `check_isolation.sh`'s allowed neighbours for `tervory-gw-base` only.

**Done when:** CI green; a sample batch gives identical records before and after the move (fixture test); after Claude deploys, the Data page shows the same records and a new batch runs end to end in the Base room.
