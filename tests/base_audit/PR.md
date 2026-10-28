# Base: saved 200-record human audits and confidence histogram API

Base's case-study API could show verified-record costs and Apollo comparisons,
but could not preserve a human-checkable random audit or return confidence counts.
This adds a saved sample of exactly 200 verified records, source/date CSV export,
checked CSV import with accuracy and a 95% Wilson interval, and confidence counts
for a campaign and its states.

Branch: `codex/base-audit`, from `origin/main` at `1c78aaa`.
Claude opens the draft PR. No GitHub API was used; pushes used git.

## What changed

| File and line | Behavior |
| --- | --- |
| `tank/base_product.py:55`, `:337` | Strict request bodies and five API endpoints behind the existing Workspace key, founder guard and US-region guard. Every request requires an explicit tenant and campaign. |
| `tank/base_audit.py:24`, `:115` | Campaign population, seeded sampling and saved evidence. Membership joins both task and batch under the tenant; newest result per licence is chosen within the campaign before filtering for completed verified records. |
| `tank/base_audit.py:72`, `:86`, `:154` | Reopen audits; extend the existing contact CSV export; validate and atomically save checked verdicts. |
| `tank/base_audit.py:41` | Accuracy, resolved denominator, unsure count, Wilson interval and separate unresolved sample bounds. Standard library only. |
| `tank/base_audit.py:176` | Campaign/state histogram from `agent_base.records.confidence`, using existing Base bands. Missing, invalid or stale scores are counted separately, never converted to zero. |
| `tank/schema.sql:1857` | Additive, idempotent `tank.base_audits` table with a composite tenant/campaign foreign key and unique tenant/campaign/seed. |
| `tests/test_base_audit.py:35` | PostgreSQL/API fixtures and tests for sampling, persistence, CSVs, statistics, access, isolation, histogram boundaries and concurrency. |
| `tests/base_audit/` | Commands, test output and actual fixture API results. |

No Workspace/page files, approved skills, model routes, workers, prices or settings
changed. The existing Dockerfile copies new Tank modules through `COPY *.py`.

## API contract

Prefix: `/v1/base-product/campaigns/{campaign_id}`. These Tank endpoints use the
existing server-side `X-Tank-Key` and `X-Tervory-Admin` headers. The latter must
identify an allowlisted founder. Client identities are refused even with a valid
Workspace key. No new credential is required.

| Method and suffix | Input | Result |
| --- | --- | --- |
| `POST /audits` | JSON `tenant_id`, integer `seed` (0 through 2^63−1) | Saved audit with ID, seed, population count/digest, 200 snapshots, creator/date and measurement. A seed retry reopens the same saved audit. |
| `GET /audits/{audit_id}` | Query `tenant_id` | Saved snapshots, verdicts, review metadata and measurement. |
| `GET /audits/{audit_id}/records.csv` | Query `tenant_id` | UTF-8 CSV with BOM and `private, no-store`. Includes identity, confidence, record date, existing per-contact sources/check dates, and blank or saved `verdict`. |
| `POST /audits/{audit_id}/review` | JSON `tenant_id`, `csv` containing checked CSV text | Atomic saved verdicts and measurement. Uses the existing Apollo CSV-in-JSON upload pattern. |
| `GET /confidence-histogram` | Query `tenant_id` | Campaign and per-state totals, inclusive bands 0–39, 40–59, 60–79, 80–100, and `missing_confidence`. |

Sampling uses `random.Random(seed).sample` without replacement on the UUID-sorted
eligible population. Seed, method, population size/digest and sampled evidence are
saved. Reopening after source changes returns the original snapshots. Concurrent
creates with one seed return one audit.

All campaign states must have terminal `done` or `failed` status and a finish date.
Only completed records with independently verified website, phone or email enter
the sample. Uncollected/stale results, missing/invalid scores, or fewer than 200
eligible records return 409 without saving. Unknown or mismatched tenant/campaign/
audit IDs return 404.

Retain every exported column and value except `verdict`. Fill all 200 verdicts with
exactly `correct`, `wrong` or `unsure`. Row/column order, BOM and LF/CRLF may differ.
Missing, duplicate, foreign or edited evidence rows and invalid verdicts return 422
and save nothing. The first completed review records the authenticated founder and
time; identical retries succeed. A different later review returns 409 so concurrent
uploads cannot silently replace the saved measurement.

The histogram uses the same campaign-scoped verified population and can also report
work in progress. Empty campaign states have zero counts. Bands match the existing
`tank/skills/base.verify/1.0.1/run.py:4` and `:115`; that skill is unchanged.

## Measurement and proof

`accuracy = correct / (correct + wrong)`. Unsure verdicts are separate. The 95%
Wilson interval uses the resolved denominator and is conditional on resolved
verdicts; it does not establish accuracy for unsure records. No finite-population
correction is applied. Before review, or if all verdicts are unsure, accuracy and
interval are null. `sample_accuracy_bounds` separately treats unresolved sample
records as all wrong or all correct; those bounds are not a confidence interval.

The known checked CSV produced **171 correct, 19 wrong, 10 unsure**:

- Resolved denominator **190**; accuracy **0.9**.
- Wilson interval **[0.8491030549232077, 0.9350429215090166]**.
- Bounds including unsure sample records **[0.855, 0.905]**.

[api-proof.json](api-proof.json) contains the actual responses and one exported
fixture record with sources/dates. [histogram-proof.json](histogram-proof.json)
contains 32 verified records: band counts 8, 8, 8, 7 plus one deliberately missing
score; state totals remain 16 each. These are disposable offline fixtures only.

## Exact validation commands and results

Cloud workspace `/workspace/tervory-tank`, Python 3.12.14, PostgreSQL 16.15.
The reused test environment lacked the PDF test dependency. Installed the existing
repository pin; no repository dependency changed:

```sh
uv --cache-dir /tmp/base-audit-uv-cache pip install \
  --python /tmp/command-repo-venv/bin/python pypdf==6.21.2
```

Result: installed `pypdf==6.21.2`. The initial Base regression attempt had two
missing-`pypdf` errors; both subsequent runs below passed.

Disposable local database, bound to loopback, with no password or production data:

```sh
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY \
  -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock run \
  --detach --rm --name base-audit-postgres --publish 127.0.0.1:55441:5432 \
  --env POSTGRES_HOST_AUTH_METHOD=trust postgres:16.15
```

First implementation proof:

```sh
set -o pipefail
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55441/postgres \
  /tmp/command-repo-venv/bin/python -m pytest -q tests/test_base_audit.py \
  tests/test_base_product.py tests/test_base_database.py --tb=short \
  | tee tests/base_audit/step-1-tests.txt
```

Result: **53 passed in 15.34s**. [Output](step-1-tests.txt).

Final proof, including duplicate licences, concurrent reviews and empty histograms:

```sh
set -o pipefail
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55441/postgres \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55441/postgres \
BASE_AUDIT_PROOF_DIR=tests/base_audit \
  /tmp/command-repo-venv/bin/python -m pytest -q \
  tests/test_base_audit.py tests/test_base_product.py tests/test_base_database.py \
  tests/test_tank_boots.py tests/test_secrets.py tests/test_tank_one_door.py \
  --tb=short | tee tests/base_audit/pytest.txt
```

Result: **86 passed in 47.93s; no skips**. [Output](pytest.txt). This includes Base
regressions, secret checks, model-boundary checks, and real `uvicorn main:app`
startup twice on a fresh local database with `/health` checks and schema restart
idempotency. Audit tests use real PostgreSQL and actual FastAPI routes; outbound
HTTP is blocked in that fixture. No model calls were made.

```sh
/tmp/command-repo-venv/bin/ruff check tank tests --select E9,F \
  --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
git diff --check
```

Results: **All checks passed** and **no whitespace errors**. No Workspace build:
there are no Workspace changes.

After staging the final proof artifacts:

```sh
git diff --cached --check
/tmp/command-repo-venv/bin/python -m pytest -q tests/test_secrets.py --tb=short
```

Results: **no whitespace errors; 2 passed in 7.17s**.

## Acceptance handoff

Independent review and deployed acceptance remain pending. No live data was read
or changed, and no founder screenshot is claimed. This brief is API only; page
work and browser screenshots wait for an approved Figma frame.

After deployment, use the existing founder-authenticated server-side API context
with a real tenant and a finished campaign containing at least 200 verified records.
Create an audit with a chosen seed; download `records.csv`; check the sources and
dates by hand; fill the 200 verdicts and POST the CSV to that audit's `/review`.
Reopen and download the audit again: its records and evidence must match, with the
saved verdicts and measurement present. Read `/confidence-histogram` for that
campaign and compare state totals with its verified records. Repeating the seed
must reopen the same audit; substituting another tenant ID for those campaign/audit
IDs must return 404.

There is no new page to open or button to click in this API-only PR.
