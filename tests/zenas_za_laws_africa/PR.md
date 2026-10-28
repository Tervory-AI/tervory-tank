# ZA Laws.Africa: full national coverage and resumable synchronization

Branch: `codex/zenas-za-laws-africa`. Claude opens the draft PR; the founder merges.
Started from main `a99f3cb`; updated from main `89a7234` in merge `e8de3ea` and pushed. `#372` was not in fetched main at this point.
Main subsequently advanced to `4bda46b`, including `#372` (`009f57b`). It was merged in `3160476` and pushed. The ZA Compose conflict retained both main's new ZA bucket settings and this branch's Laws.Africa token setting. Source links and the legal-information notice reuse the merged implementation.

## API contract and provenance

The public docs host was blocked by this cloud's proxy (CONNECT 403). The founder subsequently supplied Claude's documentation check and instructed this branch to use it. The following quotations are from that supplied contract, with the supplied documentation URLs; they are not presented as pages independently fetched by this cloud.

| Topic | Supplied contract and documentation |
| --- | --- |
| Authorization | “header `Authorization: Bearer <token>` … Our code already sends Bearer; keep it.” [Authentication](https://developers.laws.africa/get-started/authentication). The older `token` scheme is not used. |
| Base | “https://api.laws.africa/v3/” [Content API](https://developers.laws.africa/content-api/content-api.md). |
| Listing | “GET /v3/akn/za/.json … Paged: fields count, next (URL or null), previous, results. Follow next until null … No page-size parameter is documented; do not send one.” [Pagination](https://developers.laws.africa/content-api/reference/pagination.md). |
| Expressions | “GET /v3/{frbr_uri}; .json for details, .html for content (params: coverpage=0, standalone, resolver=none), /toc.json for the table of contents.” Points in time contain dates and language expressions. “`@` first expression, `@YYYY-MM-DD` the expression at that date, `:YYYY-MM-DD` the latest at or before that date, none = latest today.” [Works and expressions](https://developers.laws.africa/content-api/reference/works-and-expressions.md). |
| Changes | “no filter is documented. The nightly sync compares each work's points_in_time dates and expression URLs against what we stored, and fetches only new or changed expressions.” Founder instruction for the gap in [works/expressions documentation](https://developers.laws.africa/content-api/reference/works-and-expressions.md). No undocumented filter is sent. |
| Rate limit | “none documented. Send at most 1 request per second … On 429 or 5xx, honour Retry-After or back off, and resume where you stopped.” Founder instruction; no public rate limit is claimed. Retry-After is not shortened by the shared client's usual cap. |
| Licence/attribution | “not in the public docs; the founder receives the terms with the paid key on Friday. Until then store the Laws.Africa name and the official source link per section, as the catalogue already does, and add no new wording.” No commercial licence or permission is inferred from the public documentation. |

## What changed (in progress)

- `agents/zenas/pool/adapters/laws_africa_api.py`: ZA-only client, existing Bearer scheme, API-origin/region checks, one-second request pacing, bounded 429/all-5xx retries, and dated expression metadata. Bad credentials use the existing `FetchNotConfigured` path. Header-bearing requests do not follow redirects.
- `agents/zenas/pool/http.py`: optional single-attempt/no-redirect operation reuses the existing HTTP/gzip code; existing callers retain their defaults. Optional uncapped Retry-After preserves the provider's requested wait.
- `agents/zenas/pool/adapters/laws_africa_html.py` and `za_akn.py`: reuse the existing section parser for AKN HTML and its table of contents, keeping section anchors, language/version identity, dates, publisher and source URL.
- `tests/zenas_za_laws_africa/recordings/` and `test_api.py`: offline transport replay, auth/pacing/backoff/refusal checks, and section/date/link parsing. These are contract-shaped test recordings, not captures from a paid account; provenance is in the recordings README. Live code never loads them.
- `agents/zenas/pool/laws_africa.py`, `bulk.py`, and `nightly.py`: the full national walk follows returned next URLs, excludes municipal works, and checks the existing eleven-instrument minimum. Missing minimum entries are requested by their known work URI. Existing per-work checkpoint rows keep dates/URLs; the page queue resumes after interruptions. Current expressions load initially; subsequent new/changed expressions retain their dated history. Load now and nightly share the loader and a PostgreSQL advisory lock so requests on the same box cannot race.
- `catalogue.py`, `status.py`, and `api.py`: the real publisher name **Laws.Africa** appears as source data in the existing feed table; no page copy/layout changes. The national row counts the full feed, including the individual minimum-instrument rows. No missing-token or failed-request fixture fallback exists. SAFLII is disabled.
- `agents/zenas/docker-compose.za.yml:19`: forwards the existing setting name to the normal ZA room. Boston Compose is untouched. `tests/zenas_za_laws_africa/test_sync.py` tests the shared sync and actual load/status routes.
- `tests/zenas_za_laws_africa/test_answer.py`: ingests the Companies Act recording, searches it through the real production law-pool bridge (database transport replaced), uses a cached rule card with zero model calls, and checks the cited answer and saved memo. The criminal refusal is also exercised. Actual work titles are carried on indexed subsections so the instrument name can be found with the section text.
- Four existing Zenas test files update expectations for the requested SAFLII-off, missing-token and v3 JSON/HTML behaviour. SAFLII parser tests still run against explicitly enabled, offline-only source objects; the production catalogue stays disabled.

## Commands and results

Cloud directory: `/workspace/tervory-tank`. No GitHub API or paid API call was used.

```sh
git fetch founder main
git merge --no-edit founder/main
git push founder codex/zenas-za-laws-africa
env -u RIG_TEST_DATABASE_URL -u POOL_SCHEMA_DATABASE_URL -u ZENAS_SCHEMA_DATABASE_URL -u GITHUB_ACTIONS PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/zenas_za_laws_africa/test_api.py
```

Results: main merge `e8de3ea` pushed; **13 passed in 0.16s**. Tokens in tests are variable-name markers passed through mocked transport, never credentials. No model calls, live database access or fixture fallback were used.

API/parser implementation was committed and pushed as `c7f0b53`.

```sh
env -u RIG_TEST_DATABASE_URL -u POOL_SCHEMA_DATABASE_URL -u ZENAS_SCHEMA_DATABASE_URL -u GITHUB_ACTIONS PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/zenas_za_laws_africa/test_api.py tests/test_zenas_pool_schema.py
env -u RIG_TEST_DATABASE_URL -u POOL_SCHEMA_DATABASE_URL -u ZENAS_SCHEMA_DATABASE_URL -u GITHUB_ACTIONS PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/zenas_za_laws_africa
```

Results: **16 passed in 0.25s**; then **19 passed in 0.86s** after the sync/route tests were added. The first targeted Ruff run found four unused imports in new files; those imports were removed.

Sync/ZA wiring was committed and pushed as `1290689`. The targeted Ruff recheck passed. After merging main, the full offline Zenas baseline at `4bda46b` returned **517 passed, 4 skipped**. The initial branch run returned **8 failed, 528 passed, 4 skipped**: those eight failures were the old SAFLII-enabled, tokenless-snapshot and single-XML-request expectations, which were updated only within the affected Zenas tests.

```sh
env -u RIG_TEST_DATABASE_URL -u POOL_SCHEMA_DATABASE_URL -u ZENAS_SCHEMA_DATABASE_URL -u GITHUB_ACTIONS PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/zenas_za_laws_africa
env -u RIG_TEST_DATABASE_URL -u POOL_SCHEMA_DATABASE_URL -u ZENAS_SCHEMA_DATABASE_URL -u GITHUB_ACTIONS PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python /tmp/zenas-laws-africa-offline.py -q tests/zenas_za_laws_africa tests/test_zenas_pool_licence.py tests/test_zenas_pool_status_api.py tests/test_zenas_pool_za.py tests/test_zenas_saflii_patchright.py
```

Results: **20 passed in 1.59s**, including the cited-answer test; **49 passed in 1.66s** after updating the intentional behavior changes. The temporary offline runner installs a Python audit hook refusing IPv4/IPv6 `socket.connect` events, then calls `pytest.main(sys.argv[1:])`. It does not change test outcomes or supply credentials. One pre-existing Starlette/AnyIO deprecation warning remains in the focused run.

## Friday checklist — pending completion of this branch

1. **licence terms: confirm from the founder's Laws.Africa agreement**. Confirm any required attribution wording before introducing it; no additional legal wording has been invented.
2. On Coolify resource **`agent-zenas-za`**, on the **ZA box only**, set **`LAWS_AFRICA_API_TOKEN`** and apply it to the normal room container. Never set it on Boston or put its value in this PR, URLs, logs or screenshots.
3. Open **`/zenas/feeds`**, select **ZA**, and press the existing **“Load now”** control for the Laws.Africa source. Watch real counts fill; verify every national listing page completed and every existing minimum instrument loaded. SAFLII must remain off.
4. Verify a stored section's source link, publication/version dates and Laws.Africa attribution. Run Load now again: unchanged expressions must not download again. Verify the next nightly run sees new/changed expression dates/URLs and resumes after an interruption.
5. Open **`/zenas`** on the ZA-serving Workspace and ask **“Under the Companies Act, must the business and affairs of a company be managed by its board?”** Open every cited section and verify that the actual law supports the answer. A criminal-law question must still be refused.
6. Attach founder screenshots of the feed counts, actual civil answer and opened sources; record the saved matter ID and the nightly result. The founder's browser acceptance is outstanding until these exist. Tests alone are not completion.

## Decisions I made

- Used the founder-supplied documentation facts to resume work; kept the correct existing Bearer scheme.
- Kept the actual FRBR/date/language identities and HTML section IDs, rather than inventing publisher links or treating the first date in XML as the consolidation date.
- Added no new page text/layout or model calls. The paid agreement is a Friday checklist item, not an invented licence grant.
- Retained the existing minimum-instrument source rows and document identities. The national source includes those counts; nightly does not separately reload those eleven rows after its national walk. Additional national works are stored under the publisher source. Municipal works stay outside this national feed.

Founder screenshots and live proof: **pending**. Implementation/testing of the remaining steps is in progress; no Friday-ready or live-success claim is made yet.
