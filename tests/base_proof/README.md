# Base local fixture proof

These are **local, fixture page** screenshots, not a signed-in live service.
The founder has excluded accounts and credentials from this brief. The harness
copies Workspace to a temporary directory and substitutes Clerk, tenant identity,
middleware and the authentication shell only in that copy. Production auth is
unchanged. The actual Base page, controls, server proxy and Tank product router run.
The four-row reference and public observations are explicit fixtures, never seed data.

From a fresh clone, run `pip install -r tank/requirements.txt -r tank/requirements-dev.txt playwright`
in a Python environment, install Chromium at `/usr/bin/chromium`, and run
`npm ci --prefix workspace`. All commands run on the cloud machine.

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

Validated in the cloud on 26 October 2026: 286 Base and affected cost-reader
regression tests passed with the local database checks enabled (zero skips);
the production Workspace build passed. The browser script passed the reference
batch, per-field evidence, CSV upload/download, saved batch link and Apollo flow
at 375 and 1440 pixels. These results do not claim live account access.
