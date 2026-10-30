# Add SEC EDGAR and New York port feeds with source-cited answers

Branch: `codex/market-lab-official-feeds`, started from `origin/main` at `4e74b42`.
Claude opens one draft PR from this branch. No GitHub API, PR creation, merge, deployment, production SQL or production data changes were performed.

SEC company submissions and New York port counts can now be collected through their free official JSON APIs. Stored evidence retains its publisher link, observation date and fetch time. The existing Market Lab answer path cites the exact saved row. USPTO remains blocked by authorization and unavailable API documentation; this is not a completed USPTO implementation or founder acceptance.

## What changed

| File and line | Change |
| --- | --- |
| `agents/market_lab/feeds/adapters.py:691` | Parse monthly category counts; reject invalid months, categories and non-finite/negative counts. |
| `agents/market_lab/feeds/adapters.py:714` | Parse SEC recent submissions; validate filer, aligned columns, dates and accession identifiers before constructing official filing-index links. |
| `agents/market_lab/feeds/fetch.py:409` | Official SODA pagination in stable row order, 1,000 rows/page, bounded completion and publisher validation. |
| `agents/market_lab/feeds/fetch.py:427` | Fetch the engine's configured SEC filers; reject mismatched returned identities. No filing-page scraping or historical archive crawl. |
| `agents/market_lab/feeds/live.py:24` and `:141` | Shared SEC limit of five requests/second within a worker across SEC hosts/clients, even with delay=0. Existing default two-second host delay and truthful User-Agent remain. |
| `agents/market_lab/feeds/engines/ffl/lists.py:11` | Verified SEC identifiers for Ruger and Smith & Wesson, kept in the industry engine. |
| `agents/market_lab/feeds/engines/ffl/sources.py:45`, `:287`, `:322` | Register SEC, enable New York, and retain publisher attribution, source links and the port's two-state coverage. |
| `agents/market_lab/feeds/licences.py:11`, `:119` | Record SEC and OPEN-NY reuse/access terms, checked 28 October. |
| `agents/market_lab/core/evidence.py:242` | Honor engine-declared state coverage when answering about a port spanning two states; retain the combined-port label and date. |
| `workspace/app/market-lab/catalog.ts:50`, `:58`, `:205` | Register SEC in the existing card using the source name from the brief; move New York from linked to stored. Empty summaries introduce no descriptive copy. Remove the now-false linked-group sentence naming New York. No new controls/layout/empty-state/error wording. |
| `tests/market_lab_feeds/test_official_feeds.py:46` | Recorded-response ingestion, deduplication, exact citations/fetch time, malformed input, rate limit, access boundaries, pagination, rollback, answer dates, tenant and fixture isolation. |
| `tests/fixtures/feeds/sec_edgar/ruger.json:1`, `tests/fixtures/feeds/sec_edgar/swbi.json:1`; `tests/fixtures/feeds/ports/nynj.json:1` | Recorded official responses; source URLs, HTTP status and SHA-256 in `tests/market_lab_feeds/evidence/recordings.json:1`. Used only by explicit offline fixture runs. |
| `workspace/app/market-lab/model.test.ts:28`, `:38`, `:87`, `:91` | Update stored-feed counts and prove both new cards open saved documents. |
| `tests/test_feeds_backfill.py:53`, `:105`, `:128` | Update totals for the added 384 points and 2,000 events; New York is no longer a linked-only source. All other no-copy assertions remain. |
| `tests/test_market_lab_postgres.py:35`; `tests/test_market_lab_real_tank.py:46`; `agents/market_lab/fixture_proof/capture.mjs:41` | Update expected stored-feed count from 14 to 16. These optional server/browser checks were not claimed as run. |
| `tests/market_lab_feeds/prove_live.py:24` | Repeatable real-fetch proof through the existing refresh/answer path into disposable local memory. No fixtures, credentials, models or production connection. |

## Catalogue audit

At this base, `feeds/catalog.py` delegates to `feeds/engines/ffl/sources.py`. The engine contains **34 entries**, all statically enabled. Five existing structured fetchers plus seven FRED links are gated by named key settings: **12 entries are off when those settings are absent**. Production setting values were not inspected. Fourteen catalogue entries already have live ingestion handlers; the premise that only FRED/Federal Register have fetchers does not match this main revision.

The table includes every key-gated entry and every link-only entry. Eleven link entries have page-hash watchers, so they are explicitly distinguished from missing fetchers. SEC EDGAR, USPTO, MarineTraffic, Freightos and LME were absent at the base. This branch adds SEC and enables New York: **35 entries, 16 stored-feed handlers and 19 linked entries**.

| Feed ID | Reason/status at base |
| --- | --- |
| `census_population` | Existing live fetcher; off when CENSUS_API_KEY is absent. No new fetcher is needed. Registration/settings belong to the founder. |
| `legiscan` | Existing live fetcher; off when LEGISCAN_API_KEY is absent. No new fetcher is needed. Registration/settings belong to the founder. |
| `census_trade` | Existing live fetcher; off when CENSUS_API_KEY is absent. No new fetcher is needed. Registration/settings belong to the founder. |
| `eia_diesel` | Existing live fetcher; off when EIA_API_KEY is absent. No new fetcher is needed. Registration/settings belong to the founder. |
| `noaa_climate` | Existing live fetcher; off when NOAA_TOKEN is absent. No new fetcher is needed. Registration/settings belong to the founder. |
| `port_long_beach` | Link-only. Existing catalogue records no verified permission to bulk-copy this dataset; no structured fetcher is enabled. |
| `port_nynj` | Link-only at base; now enabled through the official SODA API after checking OPEN-NY reuse terms. Recorded response has 384 rows covering 2000–2015; these are historical observations, not current port traffic. |
| `fred_tsifrght` | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_tsifrghtc` | Linked-only, gated by FRED_API_KEY. The generic live FRED reader exists, but this series is not selected in the engine cost plan. No ingestion adapter: existing FRED terms prohibit a database copy. |
| `fred_pcoppusdm` | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pzincusdm` | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pleadusdm` | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pcottindusdm` | Linked-only, gated by FRED_API_KEY. The generic live FRED reader exists, but this series is not selected in the engine cost plan. No ingestion adapter: existing FRED terms prohibit a database copy. |
| `fred_gasdesw` | Linked-only, gated by FRED_API_KEY. The generic live FRED reader exists, but this series is not selected in the engine cost plan. No ingestion adapter: existing FRED terms prohibit a database copy. |
| `ups_hazmat` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `fedex_hazmat` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `usps_pub52` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `ups_firearms` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `ca_oag_firearms` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `atf_state_ordinances` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `season_ca` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `season_tx` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `season_fl` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `season_pa` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `season_ny` | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |

## Sources named in the job

- SEC EDGAR: official JSON APIs require no authentication or API key. SEC publishes a 10 requests/second maximum and requires a declared User-Agent. Implemented for recent Ruger and Smith & Wesson submissions (the API recent window; not a complete historical archive). Recorded responses contain 1,000 filings per company. Shared per-worker SEC ceiling: five requests/second, in addition to the normal two-second host delay; declared Tervory User-Agent. No filing HTML is fetched.
- USPTO: stopped at the access boundary under rule 9. One unauthenticated GET to `https://api.uspto.gov/api/v1/patent/applications/search` returned HTTP **401**, body `{"message":"Unauthorized"}`. The official current PatentsView page links the Open Data Portal; its API/transition pages returned an application shell and Chromium showed only “Feedback”, without a readable contract or rate policy. No key was requested/created/seen, no sign-in was attempted, and no adapter/schema or paid-key requirement was guessed. Required before this source can be built and verified: current official endpoint/schema/rate documentation and authorized API access supplied through founder-managed settings. No USPTO rows are claimed.
- MarineTraffic, Freightos, LME: absent from this catalogue; paid/proprietary or scraping routes are excluded by the brief. No adapter will be built for them in this task; the founder must decide any future licensed integration.

Official documentation read: [SEC access/fair-access policy](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data), [SEC JSON APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [SEC developer FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions#developers). Documentation research is not a successful feed fetch.


## Official access and scope

- SEC documentation: no API key; maximum ten requests/second; declared User-Agent required. Requests identify as `Tervory Market Lab feeds (+https://app.tervory.com)`. The code applies a more conservative five/second ceiling shared within the worker, in addition to normal host pacing. It is not a distributed limiter across deployments. The engine fetches two named companies and only the API's recent window (1,000 filings each in this run); it does not claim all EDGAR companies or their complete history.
- OPEN-NY's [published terms](https://data.ny.gov/dataset/OPEN-NY-Terms-Of-Use/77gx-ii52) permit free download and lawful reuse, including private-sector projects. The dataset metadata attributes the records to the Port Authority and says counts are self-reported. Its posting frequency is annual. [SODA documentation](https://dev.socrata.com/docs/app-tokens.html) allows tokenless queries, with shared-IP throttling and HTTP 429. No fixed unauthenticated quota is published there; normal two-second host pacing stays, and 429 stops the run without retry. The returned dataset covers **2000–2015**, not current port traffic.
- Each SEC event stores its exact filing URL and `fetched_at`. Each port point retains `source_id`/`fetched_at`; its stored source record and immutable citation document retain the official dataset URL. Download URL/SHA-256 is retained in the citation document. No schema change is needed.
- The fourteen existing handlers and eleven page-hash watchers are not replaced or extended with scraping. The source audit distinguishes registered-key gates from missing adapters and terms restrictions.

## Exact validation commands and results

Commands ran in `/workspace/tervory-tank` unless noted. Python is the environment's existing virtualenv; `PYTHONPATH=tank` is set for pytest. No CI was retriggered.

```sh
/workspace/.tervory-cloud/venv/bin/pip install -r agents/market_lab/feeds/requirements.txt
# Exit 0; installs the repo's existing PDF dependency, no requirements edit.

PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/market_lab_feeds/test_official_feeds.py
# SEC checkpoint: 13 passed.

PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/market_lab_feeds/test_official_feeds.py tests/test_feeds_live.py tests/test_market_lab_evidence.py
# SEC + New York checkpoint: 49 passed in 1.93s.

PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/market_lab_feeds/test_official_feeds.py tests/test_feeds*.py tests/test_market_lab*.py
# Final: 181 passed, 3 skipped, 1 pre-existing failure in 17.11s; exit 1.
# Full output: evidence/offline-tests.txt.

PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python tests/market_lab_feeds/prove_live.py
# Exit 0: SEC 2,000 rows; New York 384 rows; cited answers and isolation passed.
# Full output: evidence/live-fetch.json. One refresh per new feed, after offline tests.

git diff --check
# Exit 0.
```

Earlier runs caught and fixed the test-only missing `at=` argument, outdated count/link expectations and missing Workspace catalogue registration. A sandboxed async test run stalled waiting for a thread-to-event-loop wakeup and was interrupted; the same offline checks passed using the environment's permitted local execution. No publisher access limit was bypassed. Recorded-response capture requests preceded offline tests; the final live proof is separate, not a fixture replay.

The remaining pytest failure is `tests/test_feeds_boundaries.py:121::test_industry_words_stay_in_the_engine`. Its repository-wide text scan flags three pre-existing Base proof files: `tests/fixtures/base-atf/ORIGIN.md`, `tests/base_proof/reference-adopt/reference-loaded.json`, and `tests/base_proof/atf-download/results.json`. No new file is an offender. Reproduced on unchanged main with:

```sh
git worktree add --detach /workspace/market-lab-main-baseline 4e74b42
# cwd: /workspace/market-lab-main-baseline
PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python -m pytest -vv tests/test_feeds_boundaries.py::test_industry_words_stay_in_the_engine
# Same failure and same three paths; evidence/main-boundary.txt.
# The same -vv test command on the branch is saved in evidence/branch-boundary.txt.
```

The three skipped checks require an explicitly configured local test Postgres database: `test_market_lab_postgres`, `test_market_lab_real_tank`, and `test_market_lab_warning_real_tank`. No Postgres/Tank/browser end-to-end success is claimed by this job's memory-ledger proof.

Workspace type check:

```sh
# cwd: /workspace/tervory-tank/workspace
/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin/node node_modules/typescript/bin/tsc --noEmit --incremental false
# Exit 2: three stale .next type references to the removed chat route, plus
# app/tiger/plugins-data.test.ts:3 importing a .ts extension without the option.
# evidence/workspace-types.txt.
```

Repeated that exact command in `/workspace/market-lab-main-baseline/workspace`, using the same installed dependencies and generated files:

```sh
ln -s /workspace/tervory-tank/workspace/node_modules /workspace/market-lab-main-baseline/workspace/node_modules
ln -s /workspace/tervory-tank/workspace/.next /workspace/market-lab-main-baseline/workspace/.next
cp /workspace/tervory-tank/workspace/next-env.d.ts /workspace/market-lab-main-baseline/workspace/next-env.d.ts
/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin/node node_modules/typescript/bin/tsc --noEmit --incremental false
# Exact same four diagnostics; evidence/main-workspace-types.txt.
```

The outputs compare byte-for-byte. This is a comparison with the same local generated build artifacts, not a clean-build or CI claim. Market Lab's TypeScript model tests pass within the pytest run, including the new card-document checks.

## Real-fetch output

The proof completed at `2026-10-28T10:27:53Z`. It used real HTTP responses and the real refresh, ingestion and deterministic answer code, with a disposable `MemoryLedger` only.

| Feed | Stored rows | Published coverage | Example returned answer |
| --- | ---: | --- | --- |
| SEC EDGAR | 2,000 events | 21 May 2012–22 Oct 2026 | `STURM RUGER & CO INC — SCHEDULE 13D/A (20 Oct 2026).` |
| New York/New Jersey port | 384 points | Jan 2000–Dec 2015 | `Loaded container imports, Port of New York and New Jersey: 251,802 20-foot container units (Dec 2015).` |

SEC source: https://www.sec.gov/Archives/edgar/data/95029/000092189526002826/0000921895-26-002826-index.html . Port source: https://data.ny.gov/Transportation/Loaded-Containers-Monthly-Imports-and-Exports-Thro/629s-5a55 . A single HEAD request to that SEC citation returned HTTP 200 (`evidence/sec-citation-link.json`); no filing content was scraped. The full JSON includes exact saved-row citation links, row fetch times, download hashes and the second-tenant denial assertions. The memory-ledger links are proof identifiers, not deployed URLs.

## Founder must decide / acceptance still pending

- **USPTO:** [official PatentsView page](https://www.uspto.gov/ip-policy/economic-research/patentsview) now points to the [ODP transition guide](https://data.uspto.gov/support/transition-guide/patentsview). The public documentation did not expose a readable contract here, and the one API access check returned 401 (`evidence/uspto-access.json`). Missing: current official API schema/rate policy and authorized access through founder-managed settings. This does not prove a paid key is required. Rule 9 in `docs/build/MILESTONES-28OCT-1NOV.md:57` says “If something blocks you … stop at that point and report exactly what is missing.” No workaround, account or key was created.
- **MarineTraffic, Freightos, LME:** excluded as requested; any licensed/paid access belongs to a separate founder decision. Long Beach and the linked page sources remain linked until a permitted official API is verified. Existing named key settings remain founder-managed.
- **SEC coverage/rate budget:** two configured companies only; any additional workers/deployments sharing an outbound address must share SEC's overall ten/second budget. The new ceiling is process-wide, not a cross-deployment claim.
- **Founder browser proof/screenshots:** not available and not claimed. After the founder deploys and refreshes the feeds, ask “Recent SEC filings from Ruger” and open the cited row/source. For the historical port dataset, ask “New York container imports in 2015”. The founder must capture the result in his own browser. Rule 11 screenshots and the job's DONE condition remain pending that acceptance.

## Git checkpoints

`4e74b42` branch creation pushed early; `40829f1` audit pushed; `2d99303` SEC implementation/tests pushed; `69f8aaa` New York implementation/tests and USPTO blocker pushed; `865f770` Workspace registration and live proof pushed. This final documentation/evidence update is pushed separately. No push to main, GitHub API call, PR creation or merge request.
