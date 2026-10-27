# Reference adoption: local fixture proof

This proof uses the real Tank, real Base app/FFL route, real PostgreSQL and real
Workspace proxy/page. Every screenshot is labelled **local, fixture page**.
Only outbound external HTTP and Clerk in a temporary Workspace copy are fixtures.
No production reads, sign-in, account, paid call or source-list reload is needed.

The reference fixture is four platform-owned `base.records` rows, plus one other
tenant's row. It contains one older duplicate and both `PREMISE_*` and `prem_*`
headers (including spaced headers). The database snapshot is unchanged afterward.
The duplicate's newest `updated_at` row supplies the reference entry's pointer.

The first real Base process deliberately rejects the local fixture corridor
with HTTP 401. The real Tank background task records/logs the reason; the real
Workspace shows it while `file` is null. Restarting only Base with the matching
fixture setting lets the next normal background pass adopt **3 licences** and
count **1 duplicate row**. Tank and Workspace stay running throughout. The page
updates automatically, the reference batch button becomes enabled, and Type 03
remains excluded from default client selections. Both fixture tenants see the
same platform reference; the other tenant's source row never enters it.

From a fresh clone, use the dependencies in the parent proof README, Python 3.12,
Node 22, and `/usr/bin/chromium`. Point the following variable only at a disposable
loopback PostgreSQL server with CREATE DATABASE permission. The harness creates
and removes its own database, processes and temporary Workspace.

```sh
PYTHONPATH=.:tank:tests \
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/basetest \
BASE_PROOF_OUTPUT=/tmp/base-reference-adopt-evidence \
python tests/base_proof/reference_adopt.py
```

Results from 27 October 2026, cloud only:

| Check | Result |
| --- | --- |
| CI Ruff command | All checks passed |
| Focused pytest with real PostgreSQL | 78 passed in 27.33s; no skips |
| CI secret scan and real Tank startup twice | 3 passed in 37.93s |
| `next build` with CI's dummy Clerk settings | Exit 0; compiled; types checked; 37/37 pages |
| Actual background adoption and browser check | Exit 0; HTTP 401 visible, then 3 licences / 1 duplicate |

```sh
ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"
PYTHONPATH=tank:tests BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/basetest \
python -m pytest -q tests/test_base_reference_adopt.py tests/test_base_product.py tests/test_base_database.py tests/test_base_workflow.py tests/test_schema.py tests/test_base_gold_nightly.py
PYTHONPATH=tank:tests TANK_BOOT_DATABASE_URL=postgresql://postgres@127.0.0.1:55443/basetest \
python -m pytest -q tests/test_secrets.py tests/test_tank_boots.py
cd workspace
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy npx next build
```

The focused tests also cover duplicate identities across the 2,000-row projection
boundary; HTTP 401/403/422/500/503; unreadable and incomplete HTTP 200 responses;
connection failures; recent checks not suppressing failures; idempotent adoption
and schema; and preservation of the ATF block stop for background and direct
refresh calls. Failure tests ensure remote response content never enters the
stored message, API response or logs.

Captured output: [lint](lint.txt), [focused pytest](focused-tests.txt),
[CI tests](ci-tests.txt), [production build](next-build.txt), and
[real job and Tank startup tail](real-proof.txt).
The disconnected Redis warning is deliberate (closed loopback port 9).
The room gold/vault diagnostics reflect the empty fixture database and the Base
process deliberately being unavailable/rejecting calls at Tank startup. Tank
reaches `Application startup complete`; `/health` returns 200.

Evidence: [job result](reference-output.json), [failed API response](reference-failed.json),
[loaded API response](reference-loaded.json),
[loaded 1440px](reference-loaded-1440.png), [loaded 375px](reference-loaded-375.png),
[failure 1440px](reference-failed-1440.png), [failure 375px](reference-failed-375.png).

After deploy, check `https://base.tervory.com/base` in the founder's signed-in
browser. The page should show the licence count and duplicate count. Inspect
`/base/product/reference`: `file` is non-null, `total_all` is positive and
`duplicate_count` matches the extra source rows omitted. Check the platform row
in `tank.base_reference_files` (`row_count`, `duplicate_count`) and
`tank.base_reference_checks` (`status`, `message`, `checked_at`). If the Base
service fails, the same safe reason and HTTP status must appear on the page and
in Tank's logs. No live verification or deploy is claimed by this fixture proof.
