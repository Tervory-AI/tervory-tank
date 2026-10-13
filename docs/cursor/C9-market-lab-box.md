# C9 — Market Lab in its own box: feeds, research, prediction ledger

**Goal:** Market Lab tracks series, researches why they move, and writes dated predictions it later scores. Industry-neutral core; each engine decides which series matter. Depends on C6 (C7 for memory).

**Files you may change:** `agents/market_lab/` (new), `tank/skills/market.*` (new skills, 1.0.0 with evals), `docker-compose.yml`, `.env.example` (names only).

## Feeds (core skills)
- `market.series_fetch@1.0.0`: fetch a time series from a source adapter. Adapters now: FRED (commodities, rates; env `FRED_API_KEY`, free), CSV/XLSX upload, and "ATF monthly FFL lists" (count licences per state/type per month from the monthly list files). Output `{series_id, points:[{date, value}], source, fetched_at}`.
- `market.surge_detect@1.0.0` (pure code): flags moves against the series' own history (z-score over a rolling window, plus % change), returns events with size and date.
- Tables in `agent_market_lab`: `series (id, tenant_id, source, ref, unit, engine)`, `points (series_id, date, value, fetched_at)`, `events (series_id, date, kind, size)`.

## Research
- `market.research@1.0.0`: a question in, a short answer with citations out. Calls Tank with task type `market.research` (Tank routes it; Perplexity Sonar once its key is in, otherwise SearXNG + a model). Every claim keeps its source URL and date. Stored as a report row with its citations and remembered in Hermes.

## Prediction ledger
- Table `predictions (id, tenant_id, made_at, statement, metric_series_id, comparator, target, resolve_by, rationale, sources jsonb, outcome, resolved_at, score)`.
- Job `resolve`: on `resolve_by`, read the series, set outcome hit/miss and score. Never edit a prediction after it is made (append-only; corrections are new rows).

## Engine for the case study (separate folder `agents/market_lab/engines/ffl/`)
Which series (licence counts per state from ATF monthly lists, the founder's per-state application history once uploaded, copper/zinc/lead from FRED) and what counts as a surge. No firearms words outside this folder.

**Done when:** evals pass on fixture data; a FRED series and the ATF state counts load and update on schedule; a surge in fixture data raises an event; a prediction made today resolves correctly in a test with a fake clock.
