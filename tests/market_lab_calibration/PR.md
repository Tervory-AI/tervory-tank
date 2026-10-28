# Market Lab: historical prediction confidence and calibration API

New predictions now store the hit rate and count of comparable resolved predictions
from the same tenant. For example, three hits and one miss produce `confidence:
0.75` and `confidence_count: 4`. The calibration API compares the confidence stated
on each original forecast with its later recorded outcome.

Branch: `codex/market-lab-calibration`, recovered from base `678d47e` as requested.
Implementation and tests verified at `06a5f40`; subsequent change is this proof
document. Every finished file was committed and pushed separately. Claude opens
the PR. No GitHub API, deployment, production SQL, model calls or page changes.

## What changed

| File and line | Change |
| --- | --- |
| `agents/market_lab/core/calibration.py:27` | Identifies prediction kind, feed and horizon from existing forecast/series metadata. |
| `agents/market_lab/core/calibration.py:47` | Pairs each tenant's originals and measurable resolutions, deduplicates forecasts and enforces the historical cutoff. |
| `agents/market_lab/core/calibration.py:70` | Computes confidence at insertion and preserves the original confidence/count when appending its resolution. |
| `agents/market_lab/core/calibration.py:89` | Computes per-kind calibration bands, observed hit rates and supporting counts. |
| `agents/market_lab/core/ledger.py:105` | Stamps confidence in the memory ledger used by offline jobs/tests. |
| `agents/market_lab/core/ledger.py:451` | Stamps and stores confidence in the real Postgres ledger. History and series reads remain tenant-scoped. |
| `agents/market_lab/core/ledger.py:537` | Returns the persisted prediction metadata in tenant-scoped reads. |
| `agents/market_lab/schema.sql:73` | Adds nullable `kind`, `feed`, `horizon_seconds`, `confidence` and `confidence_count` columns idempotently, with numeric range checks. No historical backfill. |
| `agents/market_lab/core/http.py:39` | Adds private room prediction/calibration reads with an optional exact `kind` filter. |
| `tank/market_lab_routes.py:25` | Exposes those reads through Tank's existing authenticated Market Lab corridor; responses remain `private, no-store`. |
| `tests/market_lab_calibration/test_calibration.py:46` | Adds 14 collected tests covering known history, empty history, grouping, cutoffs, duplicate/invalid resolutions, immutable confidence, corrections, band boundaries, tenant isolation, actual Tank authentication and Postgres persistence. |

## API and calculation contract

Use the existing Workspace-to-Tank authentication. POST either:

- `/v1/market-lab/predictions`
- `/v1/market-lab/calibration`

Both accept `{"tenant_id": "<tenant UUID>", "kind": "comparison:gte"}`. Omit `kind`
to return all kinds belonging to that tenant. The authenticated server supplies
the tenant, as with the existing Market Lab operations; room credentials cannot
call these Workspace routes. A missing Workspace key returns 401, a room key
returns 403, and a missing private room key returns 401.

Predictions returns `{"predictions": [...]}` with original and appended resolution
rows. Existing `sources[].resolves` identifies a resolution's original forecast.
Each new forecast has `kind`, `feed`, `horizon_seconds`, `confidence` and
`confidence_count`. No comparable resolved history means `null` confidence and
count zero. A caller-supplied confidence is ignored at insertion.

The comparison key is the same tenant, kind, feed and whole-second duration from
`made_at` to `resolve_by`. Explicit kind/feed metadata is retained. Existing
forecasts without those fields use `warning:<comparator>` for warning-linked
predictions, `response:<comparator>` for response-series predictions, or
`comparison:<comparator>` otherwise. Feed comes from that tenant's registered
series source; an unregistered series uses its own ID so unrelated unknown feeds
cannot be pooled. These are API identifiers, not page text. Horizons are matched
exactly in seconds, without broadening them into arbitrary date bands.

Only recorded `hit`/`miss` outcomes resolved by the new forecast's `made_at` count.
The original must predate the new forecast and its resolution cannot predate its
deadline. Each original is counted once, using its earliest valid measurable
resolution. Pending, unmeasurable, orphan, cross-tenant and mismatched-claim rows
do not contribute. Resolution appends preserve the original confidence/count;
corrections are new forecasts and receive their own calculation. Existing outcome
classification rules are unchanged.

Calibration returns `{"groups": [...]}`, one group per kind, with `resolved_count`,
`scored_count`, `unscored_count`, `hits`, overall `hit_rate`, and `bands`. Each band
contains `lower`, `upper`, `upper_inclusive`, `count`, `hits`, `mean_confidence` and
actual `hit_rate`. Bands are `[0, .1)`, `[.1, .2)`, through `[.9, 1]`; every boundary
belongs to exactly one band, including zero and one. Empty bands have count zero
and null means/rates. No resolved history returns an empty groups array.

The bands use the confidence saved on the original forecast, never confidence
recomputed with later knowledge. Old forecasts and new cold-start forecasts with
no stated confidence contribute to overall observed hit rate and
`unscored_count`, but not the bands. Their resolved outcomes can inform later
forecasts without inventing past confidence.

## Offline and local database proof

Commands below ran from `/workspace/tervory-tank` unless a different working
directory is given. Only manufactured test histories and a disposable loopback
Postgres database were used. No feed fetches or model calls were required.

Disposable database setup:

```sh
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock run --detach --rm --name codex-market-calibration-postgres --tmpfs /var/lib/postgresql/data:size=512m -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=market_calibration_test -p 127.0.0.1::5432 postgres:16
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock port codex-market-calibration-postgres 5432/tcp
```

Result: container started; port output `127.0.0.1:32770`. A fresh run may assign
another port; substitute that port in the following commands. The new Postgres
test applies the schema twice, exercises both tenants, and rolls back its rows.

CI lint command and additional lint for the changed room files:

```sh
/workspace/.tervory-cloud/venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
/workspace/.tervory-cloud/venv/bin/ruff check agents/market_lab/core/calibration.py agents/market_lab/core/ledger.py agents/market_lab/core/http.py --select E9,F
git diff --check 678d47e
```

Results: `All checks passed!` for both Ruff commands. Diff check exited 0 with no
output.

Focused tests and related Market Lab regression tests:

```sh
PYTHONPATH=tank DATABASE_URL=postgresql://postgres@127.0.0.1:32770/market_calibration_test PATH=/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin:$PATH /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/market_lab_calibration tests/test_market_lab.py tests/test_market_lab_postgres.py tests/test_market_lab_warning_stats.py tests/test_market_lab_evidence.py tests/test_market_lab_review.py tests/test_market_lab_source_pages.py tests/test_market_lab_public_pages.py tests/test_market_lab_before_deploy.py tests/test_market_lab_page.py
```

```text
142 passed, 11 warnings in 11.63s
```

This includes all 14 new tests, with no Postgres skip. Assertions prove:

- Three hits / four resolved comparable forecasts => `.75`, count `4`.
- Other kinds, feeds, horizons and tenants do not change those values.
- A `.75` forecast that later misses remains `.75`, count `4`, and enters the
  `[.7, .8)` calibration band with hit rate `0`.
- Confidences `.21` and `.29`, with one hit and one miss, produce band count `2`,
  mean confidence `.25` and actual hit rate `.5`.
- All eleven decile boundaries from `0` to `1` count exactly once.
- Tenant A's Tank API returns four resolved forecasts / three hits; tenant B's
  separate all-miss history returns hit rate zero. Filters cannot mix them.

The API tests import the actual Tank application and room router, using ASGI
transport to keep them offline. Their only permitted outbound requests are the
two private room reads; any attempted model/search/provider request fails the
test. The database version uses real Postgres for those same API reads.

## Broader checks and reproduced baseline failures

```sh
PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/test_secrets.py tests/test_tank_one_door.py tests/test_smoke.py
```

```text
1 failed, 29 passed, 6 warnings in 19.80s
```

Secrets and smoke pass. The only failure is
`tests/test_tank_one_door.py:265::test_no_new_tank_bypass`, which reports three
existing fingerprints in unchanged test files:

```text
tests/tank_batch_providers/verify_passthrough.py:87: assembled endpoint [2703e202bb2a19bc]
tests/tank_batch_providers/verify_passthrough.py:87: model/paid endpoint [d898b966b41955fb]
tests/test_command_streaming.py:81: model/paid endpoint [20a97d67b3598de5]
```

Verified against the untouched recovery base, not assumed:

```sh
git worktree add --detach /workspace/market-calibration-base 678d47e
# Working directory: /workspace/market-calibration-base
PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/test_tank_one_door.py
```

Result: `1 failed, 26 passed in 13.17s`, with exactly the same three paths, line
numbers and fingerprints. No calibration-file finding exists. The audited list
was not changed by this job.

Existing checks using actual local processes:

```sh
PYTHONPATH=tank DATABASE_URL=postgresql://postgres@127.0.0.1:32770/market_calibration_test PATH=/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin:$PATH /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/test_market_lab_real_tank.py tests/test_market_lab_warning_real_tank.py
```

Result: `1 failed, 1 passed in 9.11s`. The Market Lab test passes using actual Tank
startup/authentication, room processes and Postgres. The optional warning test
fails during Tiger process startup: `agents/tiger/alert_email.py:22` imports
`agents.rig.rigbox.reserve`, but its existing harness's subprocess path lacks the
repository root, yielding `ModuleNotFoundError: No module named 'agents'`.

Baseline reproduction, working directory `/workspace/market-calibration-base`:

```sh
PYTHONPATH=tank DATABASE_URL=postgresql://postgres@127.0.0.1:32770/market_calibration_test /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/test_market_lab_warning_real_tank.py
```

Result: `1 failed in 1.94s`, at the identical Tiger import and with the identical
exception. No Tiger code or warning harness was changed. These are local results;
no CI run was requested, and a green full-suite/CI result is not claimed.

## Founder verification still pending

This is API-only. No page, wording, screenshot or Figma frame was added. The
founder's browser/deployment test and its screenshots have not happened here and
are not claimed as proof. After deployment, Claude can inspect tenant-scoped
predictions and calibration through Tank using the existing server-side access.
New forecasts will gain confidence from comparable resolved history; historical
forecasts without stated confidence will remain unscored for calibration.

The two unrelated baseline test failures above remain for their owning threads.
No new setting values, services, keys or founder product decisions are needed
for this API implementation.
