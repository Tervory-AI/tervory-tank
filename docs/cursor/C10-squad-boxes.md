# C10 — Rooms for Radix and Tisan (empty, ready to learn)

> **Room setup:** follow `docs/cursor/ROOMS.md` exactly (proven in C6b, used for Tiger and Market Lab). It overrides anything below about networks, compose or database access.

**Scope:** Radix and Tisan only. Zenas's room is built in Zenas Z1 (`Z-zenas-plan.md`), not here.

**Goal:** the two Squad members exist as running, isolated agents with memory and a schedule, but no skills yet, so their development can start the day their first skill is approved. Depends on C6 and C7 (both live).

**Files you may change:** `agents/radix/` and `agents/tisan/` (new, copied from `agents/_template/`), `docker-compose.yml` (additive only), `.env.example` (names only), `agents/check_isolation.sh` (the Radix no-internet check below), `agents/README.md` (one row each), new tests under `tests/`.

## Both rooms (ROOMS.md, no changes to the pattern)
- Corridors `tervory-gw-radix` and `tervory-gw-tisan`; logins `agent_radix`, `agent_tisan`; keys `TANK_KEY_RADIX`, `TANK_KEY_TISAN`.
- Main compose, additive: each corridor on `tank`, `postgres` and `hermes`; each `TANK_KEY_<NAME>` on `tank` **and** `hermes` (ROOMS.md step 4b); each `AGENT_DB_PASSWORD_<NAME>` on `agent-roles`; both networks in the top-level `networks:` as `external: true`.
- Each agent: chassis + `/health`, the template's `ping` job (writes a heartbeat to Hermes), own schema, own volume, `mem_limit: 256m`, `cpus: 0.25` until it has work.
- A one-page `agents/<name>/README.md` each: its job (below), the first three skills it should learn, what it may never do.

## Radix: the security auditor (stricter room)
- **No internet.** Its corridor is created on the server as an **internal** network (`docker network create --internal tervory-gw-radix`), so Radix can reach Tank, Postgres and Hermes and nothing else. Say this in the compose comment and in Radix's README.
- `RADIX_ALLOWED_HOSTS` (env, empty by default) is read by Radix's own outbound client (`agents/radix/net.py`, the only way Radix code makes HTTP calls outside Tank/Hermes), which refuses any host not on the list. When the first scanning skill needs the internet, Claude adds an egress proxy that enforces the same list; until then the list stays empty.
- **Never does:** scans a target the tenant has not registered **and** proven it owns (DNS TXT or file token; this check is Radix's first skill); runs exploits or anything beyond detection; stores secrets it finds (it records type, file and line, never the value); reaches another Squad member's corridor.
- First three skills to learn (from the Build Pack): `scan.secrets` (Gitleaks), `scan.dependencies` (npm audit + pip audit), `scan.static_analysis` (Semgrep). All run on code handed to it, so none need the internet.
- `agents/check_isolation.sh`: when the container is on `tervory-gw-radix`, add one check, "internet is unreachable", that tries a TCP connect to `1.1.1.1:443` with a 5-second timeout and passes only if it fails. Every other corridor keeps today's checks unchanged. (If Coolify's own per-resource network gives Radix a way out, this check fails and Claude fixes it at deploy; do not work around it in code.)

## Tisan: the developer + designer
- Standard isolation (same as the template).
- **Never does:** deploys anything to production without a Radix scan result of "no critical findings"; holds model keys (all model calls go through Tank); pushes to a client's repo without that tenant's approval recorded.
- First three skills to learn (from the Build Pack): the project scaffold (Next.js + Tailwind + TypeScript), the Figma token reader (style contract), and the Playwright test runner.

## Tests
- Compose test: each agent compose has only its own external corridor, a `mem_limit`, a healthcheck and no `POSTGRES_USER`/`POSTGRES_PASSWORD`; the main compose has both corridors on tank, postgres and hermes and both keys on tank and hermes.
- Radix's HTTP client refuses a host that is not on `RADIX_ALLOWED_HOSTS` (empty list refuses everything).
- `check_isolation.sh` runs the internet check only for `tervory-gw-radix` (shellcheck-clean).

**Done when:** CI is green; after Claude deploys, both rooms pass `check_isolation.sh` (Radix including "internet is unreachable"), each remembers a heartbeat in its own Hermes memory, and neither can resolve `tiger` or another agent.
