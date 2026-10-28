# Market Lab official feeds — work in progress

Branch: `codex/market-lab-official-feeds`. Base: `origin/main` at `4e74b42`.
Claude opens the PR. This task uses git only; no GitHub API or PR creation.

## Catalogue audit

At this base, `feeds/catalog.py` delegates to `feeds/engines/ffl/sources.py`. The engine contains **34 entries**, all statically enabled. Five existing structured fetchers plus seven FRED links are gated by named key settings: **12 entries are off when those settings are absent**. Production setting values were not inspected. Fourteen catalogue entries already have live ingestion handlers; the premise that only FRED/Federal Register have fetchers does not match this main revision.

The table includes every key-gated entry and every link-only entry. Eleven link entries have page-hash watchers, so they are explicitly distinguished from missing fetchers. SEC EDGAR, USPTO, MarineTraffic, Freightos and LME are absent from the current catalogue.

| Feed ID | Catalogue name | Reason/status at base |
| --- | --- | --- |
| `census_population` | Census population by state and county | Existing live fetcher; off when CENSUS_API_KEY is absent. No new fetcher is needed. Registration/settings belong to the founder. |
| `legiscan` | State bill status changes | Existing live fetcher; off when LEGISCAN_API_KEY is absent. No new fetcher is needed. Registration/settings belong to the founder. |
| `census_trade` | Census trade: imports and exports by product, country and port | Existing live fetcher; off when CENSUS_API_KEY is absent. No new fetcher is needed. Registration/settings belong to the founder. |
| `eia_diesel` | U.S. diesel prices | Existing live fetcher; off when EIA_API_KEY is absent. No new fetcher is needed. Registration/settings belong to the founder. |
| `noaa_climate` | Monthly temperature and precipitation by state | Existing live fetcher; off when NOAA_TOKEN is absent. No new fetcher is needed. Registration/settings belong to the founder. |
| `port_long_beach` | Port of Long Beach container statistics | Link-only. Existing catalogue records no verified permission to bulk-copy this dataset; no structured fetcher is enabled. |
| `port_nynj` | Port of New York and New Jersey loaded containers | Link-only. Existing catalogue records no verified permission to bulk-copy this dataset; no structured fetcher is enabled. |
| `fred_tsifrght` | Freight Transportation Services Index | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_tsifrghtc` | Freight Transportation Services Index, monthly change | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pcoppusdm` | Copper price on FRED | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pzincusdm` | Zinc price on FRED | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pleadusdm` | Lead price on FRED | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_pcottindusdm` | Cotton price on FRED | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `fred_gasdesw` | On-highway diesel on FRED | Separate live-only FRED reader exists; FRED_API_KEY gates it. Existing terms prohibit copying FRED content into this database. No ingestion adapter by design. |
| `ups_hazmat` | UPS hazardous materials | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `fedex_hazmat` | FedEx hazardous materials | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `usps_pub52` | USPS Publication 52 | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `ups_firearms` | UPS firearms shipping rules | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `ca_oag_firearms` | California Attorney General, firearms | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `atf_state_ordinances` | ATF state laws and published ordinances | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `season_ca` | California hunting seasons | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `season_tx` | Texas hunting seasons | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `season_fl` | Florida hunting seasons | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `season_pa` | Pennsylvania hunting seasons | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |
| `season_ny` | New York hunting seasons | Existing page-hash watcher only, not a structured API feed. Page text is not stored; no approved official structured API is configured. Scraping is outside this job. |

## Sources named in the job

- SEC EDGAR: official JSON APIs require no authentication or API key. SEC publishes a 10 requests/second maximum and requires a declared User-Agent. Investigation/implementation pending.
- USPTO: current API access, terms and limits are being checked. No unsupported endpoint or registration requirement is assumed.
- MarineTraffic, Freightos, LME: absent from this catalogue; paid/proprietary or scraping routes are excluded by the brief. No adapter will be built for them in this task; the founder must decide any future licensed integration.

Official documentation read: [SEC access/fair-access policy](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data), [SEC JSON APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [SEC developer FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions#developers). Documentation research is not a successful feed fetch.

## Proof status

No new adapter or live data import is claimed at this checkpoint. Tests, exact commands/results, per-feed row counts and remaining blockers will be recorded here. No production SQL or persistent live-data change; all verification databases are local and disposable. Founder-browser citation proof remains pending deployment.
