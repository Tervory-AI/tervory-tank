# CI failure comparison

The second review checked PR head
`483211e21885e90ac57d71bd0a712e238c9276fe`.
Its [tank CI job](https://github.com/zenascapetown-code/tervory-tank/actions/runs/40347190881/job/121657271661)
**failed: 3 failed, 3,476 passed, 20 skipped, 437 subtests passed in 661.82s**.
These are the three failures on that head. The completed log was downloaded;
no CI retry or manual workflow run was requested.

## Every failing CI test on 483211e

| Test | Cause | Local comparison |
| --- | --- | --- |
| `tests/test_shell_nav.py:23` — `test_pages_do_not_scroll_sideways_and_squad_does_not_grow_the_sidebar` | The assertion at line 33 sees a failed Node subprocess. `tests/shell_browser.ts:263` times out loading `/fixtures/actual-1440.html`. | The same fixture-load failure was reproduced on exact main `65067a4` during the first review fixes. |
| `tests/test_rig_postgres.py:92` — `test_rig_startup_loads_catalogues_on_postgres` | The date assertion at line 155 expects every row to be `2026-03-01`; the committed Archon catalogue includes `2026-10-18`. | The same date mismatch was reproduced on exact main `65067a4` during the first review fixes. |
| `tests/test_rig_pr90_independent.py:738` — `test_gate_5_search_speed` | The assertion at line 762 requires both p95 and maximum latency below 300 ms. CI measured 200 searches: p50 **5.992 ms**, p95 **6.973 ms**, maximum **374.590 ms**, **one** request over 300 ms. | Passes locally on both this branch and `65067a4`; this is a timing failure, not a reproducible functional search failure. No Rig code or timing threshold was changed. |

The baseline is `65067a43a0d27d54b48633bf6db4f3fc211ec05f`, exported with
`git archive`. The three test files and their relevant Rig/sidebar implementation
files are unchanged between that baseline and this branch.

## Local timing comparison

Python 3.12, existing Workspace dependencies, the unchanged test's in-memory
ranker, no network or Postgres:

```sh
PYTHONPATH=tank python -m pytest -q -s \
  tests/test_rig_pr90_independent.py::test_gate_5_search_speed
```

- Branch: **1 passed in 1.64s**; 200 searches; p50 **5.245 ms**, p95 **10.568 ms**,
  maximum **72.062 ms**, none over 300 ms.
- Main `65067a4`: **1 passed in 1.39s**; 200 searches; p50 **4.813 ms**, p95
  **7.110 ms**, maximum **73.949 ms**, none over 300 ms.

These local passes do not erase the CI failure or establish that its timing
condition cannot recur. The CI job on the reviewed head remains failed.

## Reproduce the other two failures

Use Python 3.12 and Node 22 with the repository's test dependencies and Workspace
packages. Set `POOL_SCHEMA_DATABASE_URL` to a disposable Postgres 16 database
with permission to create test databases, and install Chromium. From either
checkout:

```sh
PYTHONPATH=tank READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium python -m pytest -q \
  tests/test_rig_postgres.py::test_rig_startup_loads_catalogues_on_postgres \
  tests/test_shell_nav.py::test_pages_do_not_scroll_sideways_and_squad_does_not_grow_the_sidebar
```

The earlier main comparison failed with:

```text
tests/test_rig_postgres.py:155: AssertionError
assert '2026-10-18' == '2026-03-01'

tests/test_shell_nav.py:33: AssertionError
Error: Page did not load http://127.0.0.1:<port>/fixtures/actual-1440.html
```

## Founder must decide: Base user agents

The shared browser and Tiger identify as `Tervory/1.0 (+https://tervory.com)`.
Two Base paths still identify as `TervoryBase/0.1`: `tank/main.py:670` (the shared
HTTP client includes the website suffix) and `workspace/app/api/base/route.ts:129`.
Both are unchanged and outside the Tiger lane. The Base thread must handle any
alignment of those clients.
