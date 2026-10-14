# OPS-4 — Uptime watchdog (free, no new server software)

**Goal:** know within 10 minutes when anything is down, without installing anything on the server.

**Files you may change:** `.github/workflows/watchdog.yml` (new), `.github/scripts/watchdog.py` (new), `docs/ops/watchdog.md` (new).

- A GitHub Actions workflow on a 10-minute schedule (plus manual run). It checks:
  - `https://app.tervory.com` (HTTP 200), `https://coolify.tervory.com/api/health` (200), and later `https://rig.tervory.com/health` and `https://tervory.com` (skipped while they return a DNS error, reported as "not live yet").
  - Every Coolify application's status through the Coolify API (`GET /api/v1/applications`, secret `COOLIFY_TOKEN`); anything not `running:healthy` (the main app reports `running:unknown`, which is fine) is a failure.
  - The TLS certificate expiry of each live domain: warn at 14 days, fail at 7.
- **On failure:** open (or comment on) a single GitHub issue titled `Down: <thing>` with the label `incident`. GitHub emails the founder. When it recovers, comment "recovered" and close the issue. Never open duplicates.
- **Never print** the Coolify token or any response body that could contain secrets; print status codes and names only.

**Done when:** a manual run passes on the live system; a run with one URL deliberately wrong opens exactly one issue, and the next good run closes it.
