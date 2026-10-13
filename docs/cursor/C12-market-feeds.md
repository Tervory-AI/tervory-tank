# C12 — Market Lab baseline feeds (start the data flowing now)

**Goal:** begin collecting the history Market Lab will reason over, today, before its box exists. Every feed lands as a dated, sourced time series or a dated event, so Market Lab starts from a baseline with months of history behind it. Industry-neutral package; the FFL/ammunition choices live in `engines/ffl/`.

**Files you may change:** `agents/market_lab/feeds/` (new standalone Python 3.12 package with its own `schema.sql`, CREATE … IF NOT EXISTS only), new tests under `tests/`, `.env.example` (names only). Nothing else: C9 (the Market Lab box) will import this package later, and C6 is changing compose in parallel.

## Data model
- `feed_sources (id, name, kind, url, licence, terms_checked_at, cadence, enabled)` — **record the licence/terms before ingesting; unknown or no-bulk terms → not ingested, linked only.**
- `series (id, source_id, ref, title, unit, geo_level national|state|county|port|metro, geo, frequency)` and `points (series_id, date, value, fetched_at, revision)` — keep revisions (agencies revise numbers; keep every vintage).
- `events (id, source_id, kind, geo, date, title, body, url, fetched_at)` — legislation, rule changes, carrier policy changes, severe weather, port disruptions.
- `fetch_runs (source_id, started, finished, rows, error)`; one CLI `feeds run [--source X] [--backfill]` and a `feeds status` report.

## First wave of adapters (each with saved fixtures for tests; no live network in tests)
**Baseline — the market's skeleton**
- ATF monthly FFL listings: counts per state, county (from ZIP), licence type, new and dropped licences month on month. Backfill as far back as ATF publishes.
- FBI NICS monthly background checks per state and type (public; a demand proxy, not sales).
- Census population by state/county (ACS API).

**Rules — what can be sold, shipped and delivered where**
- Legislation: LegiScan API (all 50 states; env `LEGISCAN_API_KEY`) filtered by the engine's topics; each bill status change is an event. Federal Register (ATF and DOT/PHMSA rules).
- Delivery rules: the engine's watch list of carrier policy pages and state shipping restrictions; Tiger (or a plain fetch until C8 lands) checks them weekly and records a changed page as an event with a diff. Hazmat basis: 49 CFR (eCFR API).

**Market feeds — where nobody is looking**
- Trade: Census international trade API (env `CENSUS_API_KEY`) monthly imports/exports by HS code, partner country and port; the engine lists the codes (e.g. ammunition, propellant powders, primers, components).
- Freight and fuel: FRED (env `FRED_API_KEY`) freight and shipping series; EIA diesel prices (env `EIA_API_KEY`); port container volumes where ports publish them.
- Commodities: copper, zinc, lead, cotton (FRED / World Bank monthly).
- Weather: NOAA (env `NOAA_TOKEN` for NCEI; NWS alerts need none) — severe-weather alerts as events per state, monthly temperature/precipitation per state; hunting-season calendars per state from the engine's list of state wildlife agency pages (events).
- Hunting participation: USFWS licence data per state (annual).

## Engine (`agents/market_lab/feeds/engines/ffl/`)
Lists only: HS codes, LegiScan topics, carrier/state pages to watch, FRED/EIA series ids, wildlife agency pages. No firearms words outside this folder.

**Done when:** every adapter has fixtures and tests; `feeds run --backfill` against fixtures fills points and events; re-running adds nothing duplicate and keeps revisions; `feeds status` lists each source with its licence, last run and row counts. PR lists every source, its licence and what could not be ingested and why, plus the free API keys the founder must create. Then stop for Claude's review.
