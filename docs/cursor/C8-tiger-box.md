# C8 — Tiger in its own box: browser pool + price mining

**Goal:** Tiger becomes a full Squad member: it watches pages on a schedule and mines prices into a history, for any industry. Depends on C6 (C7 for memory). Core skills only: no product, brand or industry words in Tiger's code; the targets come from each tenant's watchlist.

**Files you may change:** `tiger/` (the existing browser service), `agents/tiger/` (new agent from the template), `tank/skills/tiger.*` (new skills, version 1.0.0 each with evals and CHANGELOG), `docker-compose.yml`.

## Browser pool (`tiger/`)
- Keep `POST /render` working exactly as today (find_site and scrape_site use it).
- Add `session` (string): one isolated browser context per session key, cookies/storage persisted to a volume as `/data/sessions/<agent>/<tenant>/<session>.json`. Contexts never mix across agents or tenants. Idle contexts close after 10 minutes.
- Same rules as today: waits for self-clearing checks, reports `challenge: true` for interactive ones, never clicks or solves them, honest user agent, images/fonts blocked unless `screenshot: true`.
- `screenshot: true` returns a PNG (for OCR and for evidence).

## Skills (Skala, agent `tiger`)
- `tiger.price_extract@1.0.0` (pure code): from HTML return `{items:[{name, sku, gtin, price, currency, availability, url}], method}` using, in order: JSON-LD Product/Offer/AggregateOffer, microdata, OpenGraph/product meta, then a currency-pattern fallback near the product title. Never guesses a price it cannot point to; each item carries `method`.
- `tiger.price_ocr@1.0.0`: price from a screenshot when the price is an image (Tesseract in the Tiger box). Returns the same shape with `method: "ocr"` and lower confidence.
- Evals: saved HTML fixtures in `evals/` (no network), at least 8 cases incl. a sale price, out of stock, multiple offers, no price.

## The agent (`agents/tiger/`)
- Tables in `agent_tiger`: `watchlist (tenant_id, url, label, engine, every, enabled)`, `observations (tenant_id, url, ts, price, currency, availability, method, evidence)`, `alerts (tenant_id, url, ts, kind, before, after)`.
- Job `check(url)`: render via pool (session per tenant), run `tiger.price_extract` (OCR fallback), store an observation, raise an alert when the price moves more than the watch's threshold or stock changes.
- Schedules from the watchlist. Respect robots.txt and a per-domain rate limit (default 1 request / 10 s).
- Endpoints for the Workspace: watchlist CRUD, observations for a URL, alerts (all tenant-scoped).

**Done when:** evals pass; a watch on a public test shop records observations on schedule, a simulated price change raises an alert, two tenants watching the same URL get separate sessions and separate rows.
