# Missing product names — local, fixture page

Branch: `codex/tiger-flag-missing-name`, based on main `2b12945`.

A check with no product name records `missing_name`, a null price, the URL and the
attempt time. It creates no alert. The last name actually read for that tenant and
URL remains the identifier; otherwise the identifier is the page link. The screen
says **Not checked — the product name wasn't found on the page**. A watch label or
HTML document title is not evidence of a product name.

The name and failure reason are stored in the existing observation evidence JSON
and exposed through Tiger's observation response. No database migration is needed.
Old observations without name evidence are flagged until a new check reads a name.
The bounded evidence allowance includes the new name fields without truncating the
saved layout. The shared prices formatter and other products are unchanged.

The optional manual name input was removed from Tiger: it no longer determines the
identifier. Names come from the extraction result or a unique product heading.

## Missing-value audit

| Missing value | Client behavior | Regression coverage |
| --- | --- | --- |
| Product name, including blank/old placeholder | Page link or last read name; exact missing-name status; no price or new alert | `test_tiger_missing_name.py`; Workspace model/render tests; real job below |
| Price or stock | Existing layout-changed status; no price shown | Workspace model tests and saved-page stock tests |
| Currency | Explicit currency-not-found status; no assumed USD, price or new alert | Saved no-currency page, Workspace model, real job |
| Attempt time | Explicit attempt-time-not-recorded status | Workspace model tests, including invalid timestamp |
| Page link or check interval | Explicit missing-field status; no made-up value | Workspace model tests |
| Observation response | Latest-check-could-not-be-loaded status, not a never-checked placeholder | Throwing and malformed-response Workspace tests |
| Alert before/after, kind, time, link, name or currency | Explicit error; no fabricated change or values | Workspace alert model tests |
| Account name | `Account name could not be loaded.` status | React server-render test |

Input hints (search text and URL format) remain input instructions. Empty lists and
watches with no attempt yet remain honest empty/pending states. The unmounted
Plugins code is not part of `/tiger`.

## Run the real job

Requirements: Python dependencies from `tank/requirements*.txt`, Node 22, Workspace
npm dependencies, Playwright, Chromium, PostgreSQL 16. Use an empty disposable local
database whose name starts with `tiger_name_proof`.

```sh
docker run --rm -d --name tiger-name-proof-db \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=tiger_name_proof \
  -p 127.0.0.1:55435:5432 postgres:16
# Wait until pg_isready succeeds before running the proof.
docker exec tiger-name-proof-db pg_isready -U postgres
PYTHONPATH=tank:tests \
  DATABASE_URL=postgresql://postgres@127.0.0.1:55435/tiger_name_proof \
  READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium \
  python tests/tiger_missing_name/evidence/real_tank_proof.py
docker stop tiger-name-proof-db
```

The script starts the actual Tank application (including startup/schema), actual
Tiger service and queue worker, and PgStore. It approves the already installed
`tiger.price_extract/1.1.0` skill only in the disposable local database. Tiger's
HTTP browser boundary renders saved fixture HTML in real Chromium. No live store,
login, captcha or model is contacted. Only that external fetch is replaced; the
worker calls the installed extraction skill through Tank's real HTTP route.

The Workspace runs against that Tank. A throwaway copy aliases Clerk to a fixture
organization using CI's dummy publishable key; repository authentication and tenant
derivation stay intact. Each fixture job is queued explicitly on Tiger's existing
job endpoint. The fixture tenants' automatic schedules are disabled to prevent an
extra minute-boundary check during assertions. No production scheduler changes.

The run checks: first nameless attempt; complete reading and confirmed change;
subsequent nameless attempt retaining the last name; another tenant on the same
URL; missing currency; recovery comparing the previous complete price. Workspace
assertions cover Overview, Watch list and History. Screenshots are visibly labelled
**local, fixture page**. Live signed-in proof belongs to Claude after deployment.

- [Output](proof/output.txt)
- [Observations returned through Tank](proof/observations.json)
- [First nameless attempt](proof/first-nameless.png)
- [Later nameless attempt retaining the name](proof/last-name-retained.png)

## Test fixture changes

Synthetic stock/preference fixtures now contain an explicit product name, so those
tests still exercise stock and preference behavior. Access tests retain their
no-model and tenant-boundary assertions; the numeric-only private portal result is
now expected to be flagged for its absent name. No `client_connection` behavior or
upstream feed parser was changed. Current numeric-only sources cannot complete a
named reading until their source supplies the actual name.

The saved Automation Exercise page uses ambiguous `Rs.` without a currency code.
Gold cases pg-076 through pg-080 now require the initial attempt to flag missing
currency and still reject the changed layouts. Control pc-016 likewise expects an
incomplete reading. No fixture HTML, score threshold or baseline was weakened.
`GOLD_REVIEW.md` records the updated expected result.

## Local validation

- Local regression suite: **251 passed, 1 skipped** (the existing 100-page gold test awaits human-labelled answers), including `test_smoke.py` with `PYTHONPATH=tank`.
- Workspace model/actions/React rendering: **19 tests passed**.
- Final Workspace production build: **passed**, using CI's dummy Clerk keys.
- Ruff E9/F checks and secret scan: **passed**.
- Real Tank/Tiger/PgStore/Chromium/Workspace job: **all seven proof checks passed**.

```sh
PYTHONPATH=tank READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium pytest -q \
  tests/test_agent_chassis.py tests/test_tiger*.py tests/test_tg2_tiger_watchlist.py \
  tests/tiger_* tests/test_access1_feeds.py tests/test_access1_review.py \
  tests/test_smoke.py tests/test_secrets.py
node tests/tiger_works/workspace.test.cjs
```

`test_agent_chassis.py` precedes the smoke import, as in full-suite collection.
The final production build used a temporary Workspace copy and `next build` with
CI's dummy Clerk keys; no repository authentication file was changed. GitHub
Actions was not manually dispatched or retried; these are local results.
