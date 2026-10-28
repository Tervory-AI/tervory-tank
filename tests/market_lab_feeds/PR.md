# Market Lab official feeds — work in progress

Branch: `codex/market-lab-official-feeds`. Base: `origin/main` at `4e74b42`.
Claude opens the PR. This task uses git only; no GitHub API or PR creation.

## Catalogue audit

At this base, `feeds/catalog.py` delegates to `feeds/engines/ffl/sources.py`. The engine contains **34 entries**, all statically enabled. Five existing structured fetchers plus seven FRED links are gated by named key settings: **12 entries are off when those settings are absent**. Production setting values were not inspected. Fourteen catalogue entries already have live ingestion handlers; the premise that only FRED/Federal Register have fetchers does not match this main revision.

The table includes every key-gated entry and every link-only entry. Eleven link entries have page-hash watchers, so they are explicitly distinguished from missing fetchers. SEC EDGAR, USPTO, MarineTraffic, Freightos and LME are absent from the current catalogue.

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
| `fred_tsifrghtc` | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pcoppusdm` | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pzincusdm` | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pleadusdm` | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pcottindusdm` | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_gasdesw` | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
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

## Proof status

SEC checkpoint: `PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/market_lab_feeds/test_official_feeds.py` → **13 passed**. Covers recorded responses, deduplication, citations/fetch time, denial/no retry, rate limit across clients/hosts, malformed data, answer citations, tenant isolation and fixture isolation. SEC plus New York checkpoint: `PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/market_lab_feeds/test_official_feeds.py tests/test_feeds_live.py tests/test_market_lab_evidence.py` → **49 passed in 1.93s**. These offline tests include monthly imports/exports, stable pagination, invalid counts, rollback on 429, period-aware cited answers and two-tenant isolation. Final regression: **181 passed, 3 skipped, 1 pre-existing failure**; the failure was reproduced on untouched main `4e74b42`. The final live refresh succeeded: SEC **2,000 rows**, New York **384 rows**, each producing a source-cited answer and passing tenant isolation. Full outputs are in `evidence/offline-tests.txt` and `evidence/live-fetch.json`. The initial test run caught a missing test-only `at=` argument; it was corrected before this checkpoint. No production SQL or persistent live-data change; all verification databases are local and disposable. Founder-browser citation proof remains pending deployment.

New York uses the existing publisher attribution and source-document path. Its multi-state port geography is declared by the engine and respected by the existing answer filter; no new page controls or UI wording. API requests retain the normal two-second host pacing and stop on 429. Terms: https://data.ny.gov/dataset/OPEN-NY-Terms-Of-Use/77gx-ii52 ; https://dev.socrata.com/docs/app-tokens.html .

Workspace registration uses the source name “SEC EDGAR” from the job in the existing card, with no descriptive copy. New York moves from linked to stored; its now-false “Linked, not copied” summary and the group sentence naming it were removed. No new controls, layout, empty state or error wording. Existing backfill, Postgres, real-Tank and browser-proof count expectations are updated for 16 stored feeds; the optional server tests were not run in this checkpoint.
