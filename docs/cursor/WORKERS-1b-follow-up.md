# WORKERS-1b: worker key on Tank, GitHub App key from settings, Workers panel

> Written 19 Oct 2026, 02:40 PT. Follow-up after #156 merged.

**Files you may change:** `docker-compose.yml` (tank service environment, one line), `docker-compose.workers.yml`, `workers/settings.py`, `workers/github_app.py`, `workspace/app/tank/`, `tank/main.py` (one new read-only route only), `.env.example` (names only), tests.

1. **Tank accepts the worker key.** Add `TANK_KEY_WORKERS: ${TANK_KEY_WORKERS:-}` to the tank service environment next to the other `TANK_KEY_*` lines. Test that every `TANK_KEY_*` used by any compose file is passed to Tank.
2. **GitHub App key from Coolify settings.** Workers read the key from `GITHUB_APP_PRIVATE_KEY` (multiline PEM) when `GITHUB_APP_PRIVATE_KEY_FILE` is not set. Remove the host-file volume from `docker-compose.workers.yml`; pass `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID` and `GITHUB_APP_PRIVATE_KEY` as environment. The key is never logged and never written outside the private per-task directory. Tests.
3. **Workers panel on the Tank page** (founder decision: allowed). Read-only list of recent worker tasks: status, PR link, minutes, model cost. One new read-only Tank route reads the workers service's `/workers` page. Nothing in the ledger changes.

## Done when
CI green; a worker key set on Tank is accepted (tested); the key is read from the setting (tested); the panel shows fixture tasks (tested).
