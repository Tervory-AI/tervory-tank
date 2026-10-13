# C9 — Market Lab in its own box: feeds, opportunity and prediction layer

> **Room setup:** follow `docs/cursor/ROOMS.md` exactly (proven in C6b). It overrides anything below about networks, compose or database access.

**Lane update:** `agents/market_lab/` (own docker-compose.yml per ROOMS.md, corridor `tervory-gw-market_lab`, login `agent_market_lab`, key `TANK_KEY_MARKET_LAB`); imports the existing `agents/market_lab/feeds/` package without rewriting it (C12b may be changing feeds in parallel — coordinate only through its public functions). Main-compose changes: add `tervory-gw-market_lab` to tank, postgres, hermes; add `AGENT_DB_PASSWORD_MARKET_LAB` to agent-roles; `TANK_KEY_MARKET_LAB` to tank.

**Goal:** Market Lab tracks series, researches why they move, and writes dated predictions it later scores. Industry-neutral core; each engine decides which series matter. Depends on C6 (C7 for memory).

**Files you may change:** `agents/market_lab/` (new), `tank/skills/market.*` (new skills, 1.0.0 with evals), `docker-compose.yml`, `.env.example` (names only).

## Feeds (core skills)
The feed adapters and their history are built by C12 (`agents/market_lab/feeds/`); C9 imports that package and wraps it as skills. Do not rebuild adapters C12 already has.
- `market.series_fetch@1.0.0`: fetch a time series from a source adapter. Adapters now: FRED (commodities, rates; env `FRED_API_KEY`, free), CSV/XLSX upload, and "ATF monthly FFL lists" (count licences per state/type per month from the monthly list files). Output `{series_id, points:[{date, value}], source, fetched_at}`.
- `market.surge_detect@1.0.0` (pure code): flags moves against the series' own history (z-score over a rolling window, plus % change), returns events with size and date.
- Tables in `agent_market_lab`: `series (id, tenant_id, source, ref, unit, engine)`, `points (series_id, date, value, fetched_at)`, `events (series_id, date, kind, size)`.

## Research
- `market.research@1.0.0`: a question in, a short answer with citations out. Calls Tank with task type `market.research` (Tank routes it; Perplexity Sonar once its key is in, otherwise SearXNG + a model). Every claim keeps its source URL and date. Stored as a report row with its citations and remembered in Hermes.

## Opportunity layer (the core of Market Lab)
The question it answers: **where is demand outrunning supply, and is that gap opening or closing?** Marketing goes heavier where demand is high and supply is thin, not into hot spots where everyone already competes. Industry-neutral core; the engine says which series count as demand and which as supply.
- `market.gap_score@1.0.0` (pure code): per area (state, county, metro) and segment, combine engine-chosen **demand** series and **supply** series into: demand index, supply index (per capita where population applies), **gap** (demand vs supply), saturation (supply density and competitor activity), reachability (share of targets we can actually contact), and trend of the gap over 3/6/12 months. Output a ranked list with each component visible, never only a single score.
- `market.shift_detect@1.0.0` (pure code): flags areas where the gap changed sharply (a new bottleneck forming, or a market saturating), using `market.surge_detect` on the gap series.
- Table `opportunities (id, tenant_id, made_at, area, segment, demand_idx, supply_idx, gap, saturation, reachability, trend, rank, evidence jsonb)`, recomputed monthly (and when a feed updates), history kept.
- **Recommendation:** each run writes "increase / hold / reduce marketing" per area and segment, with the evidence behind it, and records each one as a prediction (e.g. "area X: response rate above Y% in 90 days") so the prediction ledger scores Market Lab's own calls.
- **Opportunity finder:** segments with a clear gap where Tervory has, or could build, a product (e.g. dealers with no website → Tisan; dealers with a web shop → RIG; licences expiring → Zenas). Ranked by size × reachability × gap × fit, written up monthly.

## Prediction ledger
- Table `predictions (id, tenant_id, made_at, statement, metric_series_id, comparator, target, resolve_by, rationale, sources jsonb, outcome, resolved_at, score)`.
- Job `resolve`: on `resolve_by`, read the series, set outcome hit/miss and score. Never edit a prediction after it is made (append-only; corrections are new rows).

## Engine for the case study (separate folder `agents/market_lab/engines/ffl/`)
Which series and what counts as a surge. **Supply:** active licences per area and type from the ATF monthly lists, per capita (Census population), dealers with a web presence (Base), stock and price signals (Tiger). **Demand:** the founder's per-state licence-application history (uploaded), monthly FBI NICS background-check counts per state (public; a demand proxy, not sales), population growth, client order data where the client allows it. **Costs:** copper, zinc and lead from FRED, freight indices. Saturation = supply density plus competitor activity. No firearms words outside this folder.

**Done when:** evals pass on fixture data; `gap_score` ranks a fixture where a high-demand, thin-supply area beats a high-supply hot spot, with every component visible; a FRED series and the ATF state counts load and update on schedule; a surge in fixture data raises an event; a prediction made today resolves correctly in a test with a fake clock.
