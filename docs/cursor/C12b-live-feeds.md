# C12b — Market Lab feeds go live (real fetching, history backfill)

> Builds on C12 (`agents/market_lab/feeds/`, merged). Read C12's review comment on PR #22 for the non-blocking list; this task is that list.

**Lane:** `agents/market_lab/feeds/` and new tests only. Do not touch `agents/market_lab/` outside `feeds/` (C9 is building the box in parallel), docker-compose, tank/.

**Do**
1. **Live fetching** with politeness: per-domain delay (default 2 s), retries with backoff (3×), a clear User-Agent naming Tervory with a contact URL, timeouts. Keys from env only; never put a URL that contains a key into a log or error message.
2. **ATF monthly lists:** stream each month (row by row), keep only the previous month's licence-id set in memory; backfill as far back as ATF publishes; renewal-safe identity (already fixed).
3. **Real formats:** FBI NICS (the published PDF tables → per-state monthly counts; pdfplumber is fine), NCEI monthly climate (real GSOM response shape), LegiScan `getSearch` real field names (`last_action`, `last_action_date`), NWS alerts mapped to states correctly (ignore marine zones).
4. **Page-change detection without copying text:** for linked-only pages (carrier rules, state shipping pages, hunting seasons), store a content hash + a dated "changed" event with the link; never the page text.
5. **Engines supply their own sources:** core reads `engine.sources()`; remove the hard import of `ffl` from `catalog.py` and the `--engine ffl` default (engine required on the CLI).
6. **Revisions:** record a return to an earlier value (A→B→A) as a new vintage.
7. `feeds run --live --source X` for a single real source; `feeds status` shows last success, rows, error per source.

**Tests:** fixtures only (no network in tests), including a NICS PDF fixture, a streamed ATF month, the hash-only change event, and A→B→A.

**Done when:** tests pass; PR lists each source's live status ("ready to run live" / "needs key X" / "blocked by terms"), and the free keys the founder must create. Stop for Claude's review.
