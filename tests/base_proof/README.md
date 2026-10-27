# Base local fixture proof

These are **local, fixture page** screenshots, not a signed-in live service.
The founder has excluded accounts and credentials from this brief. The harness
copies Workspace to a temporary directory and substitutes Clerk, tenant identity,
middleware and the authentication shell only in that copy. Production auth is
unchanged. The actual Base page, controls, server proxy and Tank product router run.
The four-row reference and public observations are explicit fixtures, never seed data.

From a fresh clone, run `pip install -r tank/requirements.txt -r tank/requirements-dev.txt playwright`
in a Python environment, install Chromium at `/usr/bin/chromium`, and run
`npm install --no-package-lock --prefix workspace`. All commands run on the cloud machine.

```
PYTHONPATH=tank:tests python -m pytest -q tests/test_base_product.py tests/test_base_vendor_meter.py tests/test_base_public_http.py
python tests/base_proof/serve.py
```

In another cloud terminal:

```
python tests/base_proof/workspace.py
```

Use the printed temporary Workspace directory as the working directory:

```
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy TANK_URL=http://127.0.0.1:8141 TANK_API_KEY=local-fixture npm run dev -- --port 3141
```

Then run `python tests/base_proof/browser.py` from the clone. The fixture labels
are fixed on every screenshot. Synthetic test identifiers are not credentials.

For SQL proof, start a disposable PostgreSQL container bound to loopback only:

```
docker run --rm --name base-fixture-postgres -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1:55441:5432 postgres:16-bookworm
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55441/postgres PYTHONPATH=tank:tests python -m pytest -q tests/test_base_database.py
```

The SQL fixture applies the full schema twice, runs each test in a rolled-back
transaction and rejects remote database addresses. It proves immutable seed
adoption, dated refresh, selection without an upload, private pairs through
the unchanged training writer, founder-only prices, exact credit costs and
unchanged historical receipts after a price is set.

Browser proof refreshed on 27 October 2026 (Pacific). The browser checks both widths,
reference selection, field source/date display, CSV upload and download, Apollo,
and the saved batch link. It imports the downloaded CSV to assert that
`+15125550101` is unchanged. Each verified row has two emails: plain `email` and
`other_emails`, with their own source URLs and ISO dates. The actual downloaded
text has no JSON, brackets or `_items` columns. The explicit fixture now includes a priced search,
an unpriced search, and a blocked uploaded business. It checks the exclusion
link, singular wording, human dates/reasons and the absence of raw provider codes.
The PostgreSQL tests separately exercise the real repository, SQL calculations,
founder-only unpriced drilldowns and tenant isolation. The collector lifecycle
test proves exactly one task runs and releases its connection before Tank shuts
down the shared pool; the prior event-hook implementation fails that test.
Two price-status PDF fixtures keep founder receipt identifiers searchable across
line boundaries; both fail on the prior formatter, which split them at hyphens.
This browser harness uses FixtureStore, not the Base worker; it does not claim a
live account or a real-agent run. The independent review of #339 at f7124a6 separately proved the real Tank,
Base agent and Workspace flow with external providers stubbed.

Full-suite comparison and exact commit IDs are recorded in `full-suite-results.md`.
The selector `.github/scripts/ci_scope.py` returns `tests=["."]` for this lane.
Install the Python dependencies in the same order as `.github/workflows/ci.yml`
(including Forge's hash-pinned requirements), install Workspace dependencies in
each fresh clone, and run the same command on main and the branch. Use separate
local PostgreSQL databases for each checkout:

```sh
PYTHONPATH=tank READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/pooltest \
ZENAS_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/pooltest \
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/basetest \
TRAINING_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/basetest \
python -m pytest -q -p no:cacheprovider --junitxml=/tmp/base-full.xml .
```

The current comparison uses main `2b12945`, including Tiger #335, Tank #334,
Market Lab #336 and the real Tank startup test. The rebased branch retains Tiger’s
browser byte for byte, every Docker COPY entry from both sides, and all of main’s
schema before the additive Base block. Both runs use CI’s Node 22 major version.
Actions are not rerun while billing is paused.

The CSV endpoint tests download failure counts with the stored reason-code filter,
then assert plain sentences in the file, exact ISO dates, source URLs and unchanged
phone values. The stored reasons remain unchanged for counts and training pairs.

Real Tank startup proof is in `tank-startup.txt`. Run the unmodified startup test:

```sh
PYTHONPATH=tank \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/pooltest \
python -m pytest -q tests/test_tank_boots.py
```

It runs the real `uvicorn main:app` process twice against one empty disposable
database, checks `/health` each time and reapplies the full schema on the second
start. The captured startup tail comes from that test helper’s returned output;
there is no stand-in Tank. Redis is deliberately pointed to closed loopback port 9
by the test, so its cache-off warning is expected.

CSV import contract (founder decision before merge): `email`, `other_emails`,
`phone`, `website`, `facebook`, `instagram`, `x`, `linkedin`, `youtube`. Each has
matching `_source_url`, `_checked_at` and `_reason` columns. Primary email and
social links use the first independently verified item in the stored order;
unverified items are excluded. Additional email values, sources and dates use
`; ` in the same order, including repeated source URLs/dates where appropriate.
Twitter maps to `x`, youtu.be to `youtube`; hostname suffixes are checked at domain
boundaries. Missing networks have empty value/source/date cells, with a plain
reason where available. The header is fixed across streamed pages. `_value` and
JSON `_items` columns are removed. The existing formula guard still protects all
cells and preserves plain phone numbers.

The CSV follow-up passed 32 tests:

```sh
PYTHONPATH=tank:tests \
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/basetest \
python -m pytest -q tests/test_base_product.py tests/test_base_database.py tests/test_base_workflow.py
```

This includes two- and three-email fixtures, distinct provenance per value,
unverified/duplicate rejection, all five networks, empty cells, ISO dates,
formula protection, and the PostgreSQL-backed streaming download. The local
Workspace browser proof also passed at 375 and 1440 pixels. Its latest CSV and
screenshots are committed here. No production app code changed outside the CSV
exporter; the older full-suite comparison remains pinned to its tested commit.
