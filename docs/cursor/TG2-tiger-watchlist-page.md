# TG-2 — Tiger in the Workspace: watchlist, prices, alerts

**Goal:** a client manages what Tiger watches and sees prices and alerts in the app.

**Files you may change:** `tank/main.py` (new proxy endpoints only, listed below), `workspace/app/prices/*` (new), `workspace/lib/tank.ts`, new tests.

- **Tank proxy (Tank is on Tiger's corridor; the Workspace is not):** `GET/POST /v1/tiger/watchlist`, `DELETE /v1/tiger/watchlist/{id}`, `GET /v1/tiger/observations?url=`, `GET /v1/tiger/alerts`. Each forwards to `http://agent-tiger:8000` with the caller's `tenant_id`; Tank's existing auth and tenant scoping apply (AGENTS rule 3). No other Tank code changes.
- **Workspace page "Prices":** add a URL to watch (label, how often, alert threshold %), list of watches with last price and change, a price-history chart per URL, and an alerts list. Plain English, brand rules from AGENTS.md. Server components; calls go through `workspace/lib/tank.ts` only.
- Respect Tiger's rules: it records `blocked` for sites that refuse it, and the page says so plainly ("This site blocks automated checks").

**Done when:** CI green; tests prove one tenant cannot read or delete another tenant's watches through the proxy; after deploy, adding a public test-shop URL shows its first observation within one check cycle.
