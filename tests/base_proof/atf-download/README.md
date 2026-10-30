# First ATF download — local fixture proof

This runs real Tank, the real Base app and `/reference/ffl` engine, PostgreSQL,
and Workspace. Only outbound external HTTP and Clerk in a temporary Workspace
copy are fixtures. Every screenshot says **local, fixture page**. There is no
production sign-in, deploy, or live ATF request in the proof.

The first download serves the full saved **September 2025** ATF list: **77,611
licences**, 11,103,529 original bytes. It is losslessly compressed in
[`tests/fixtures/base-atf`](../../fixtures/base-atf/ORIGIN.md), with source/archive
provenance and the original SHA256. It is not a generated miniature list. The
synthetic listing advertises old, future, unofficial and state-specific files
alongside the saved complete list. Production always reads the official ATF page
and downloads its latest eligible complete file, never this fixture archive.

## Results

27 October 2026, cloud machine, Python 3.12 / Node 22, current pinned Tank and
Workspace dependencies from main `c752e59`:

| Check | Result |
| --- | --- |
| CI Ruff command | All checks passed |
| Focused pytest, PostgreSQL enabled | 91 passed in 56.12s; no skips |
| CI secret tests and real Tank startup twice | 3 passed in 41.68s |
| `next build` with CI dummy Clerk settings | Exit 0, compilation/types pass, 38/38 pages |
| Real Tank → Base → Workspace proof | All three cases pass |

| Case | ATF requests | File downloads | Result |
| --- | ---: | ---: | --- |
| Empty reference | 2 | 1 | Page shows 77,611 licences, 1 Sept 2025 and the official file link |
| Existing saved rows | 1 | 0 | 3 adopted licences / 1 duplicate; every original row unchanged |
| ATF returns 403 | 1 | 0 | Plain stop message; no more requests after restarting Tank and Base |

The empty case reads only the listing and the selected file, **3.002 seconds**
apart, using `Tervory/1.0 (+https://tervory.com)`. A subsequent background pass
does not repeat the download. The saved case performs the existing newer-month
listing check but downloads nothing and keeps its original reference. Both
tenants can read the resulting platform reference.

The 403 case retains the message below even when both services restart and the
fixture would now allow a download:

> The reference could not be loaded: The Base reference service returned HTTP 422. ATF did not allow the read (HTTP 403). Automatic checks have stopped.

The tests additionally cover a CAPTCHA, an active block in HTTP 200 content,
HTTP 429, a block on the file itself, malformed/incomplete files, no eligible
link, concurrent arrival of saved rows or a reference snapshot, and the existing
adoption, deduplication, monthly refresh and tenant-isolation regressions. Blank
tab-filled rows in the real file are skipped; incomplete licence rows still fail.
The shutdown test uses `app.router.add_event_handler`, the API available under
main's current FastAPI pin; the production lifecycle is unchanged.

Captured [lint](lint.txt), [focused pytest](focused-tests.txt), [CI tests](ci-tests.txt),
[build](next-build.txt), [real job output and Tank startup tails](real-proof.txt),
and [three case results](results.json). The startup logs retain the deliberate
closed-loopback Redis warning and the initial Base connection failure while
that process starts. Each Tank reaches `Application startup complete` and
answers `/health`; the reference then loads or records its ATF block.

Screenshots: [loaded 1440px](empty-1440.png), [loaded 375px](empty-375.png),
[saved set 1440px](saved-1440.png), [saved set 375px](saved-375.png),
[blocked 1440px](blocked-1440.png), [blocked 375px](blocked-375.png).

## Reproduce

Use a cloud machine, Python 3.12, Node 22 and Chromium at `/usr/bin/chromium`.
Install `tank/requirements.txt`, `tank/requirements-dev.txt`, and Workspace's npm
dependencies. Point the database variable at a disposable loopback PostgreSQL
server with CREATE DATABASE permission. The real-process harness creates and
removes its own three databases and temporary Workspace copies. SQL pytest
fixtures apply the schema twice and roll back test data.

```sh
ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"
PYTHONPATH=tank:tests BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/basetest \
python -m pytest -q tests/test_base_atf_download.py tests/test_base_reference_adopt.py tests/test_base_product.py tests/test_base_database.py tests/test_base_workflow.py tests/test_schema.py tests/test_base_gold_nightly.py
PYTHONPATH=tank TANK_BOOT_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/basetest \
python -m pytest -q tests/test_tank_boots.py tests/test_secrets.py
PYTHONPATH=.:tank:tests BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/basetest \
BASE_PROOF_OUTPUT=/tmp/base-atf-download-proof python tests/base_proof/atf_download.py
cd workspace
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy npx next build
```

After deploying **Tank and Base**, inspect `https://base.tervory.com/base` in the
founder's browser: date, official source link and licence count should appear.
`/base/product/reference` should have a non-null `file` and positive `total_all`.
The platform row in `tank.base_reference_files` records `published_on`,
`source_url`, `sha256`, `row_count`, and `adopted=false` for a first download.
`tank.base_reference_checks` should report success or a plain blocked reason.
If ATF blocks the request, the page must show that checks stopped and no retries
may bypass that stop. Existing saved rows and dated reference files stay intact.
