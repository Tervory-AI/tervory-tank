# C10 — Boxes for Radix, Tisan and Zenas (empty, ready to learn)

> **Room setup:** follow `docs/cursor/ROOMS.md` exactly (proven in C6b). It overrides anything below about networks, compose or database access.

**Scope update:** Radix and Tisan only (Zenas's room is built in Zenas Z1). Each per ROOMS.md: `tervory-gw-radix`, `tervory-gw-tisan`, logins `agent_radix`, `agent_tisan`. Radix additionally gets NO shared service other than tank+postgres+hermes on its corridor and an outbound allowlist.

**Goal:** the three later Squad members exist as running, isolated agents with memory and schedules, but no skills yet, so their development can start the day their first skill is approved. Depends on C6 and C7.

**Files you may change:** `agents/radix/`, `agents/tisan/`, `agents/zenas/` (new, from the template), `docker-compose.yml`.

- Each: chassis + `health`, a `ping` job, Hermes memory wired, own schema, own network, own volume, `mem_limit` 256m until it has work.
- **Radix:** its network allows NO connection to other Squad networks, only Tank and Hermes (Build Pack: a security auditor must be isolated). Outbound internet only through an allowlist env (`RADIX_ALLOWED_HOSTS`, empty by default).
- **Tisan / Zenas:** standard isolation.
- A one-page `agents/<name>/README.md` each: its job (from the Build Pack), the first three skills it should learn, what it may never do.

**Done when:** all three deploy healthy, each remembers and recalls a note in its own memory, and a test proves Radix cannot reach Tiger or Market Lab.
