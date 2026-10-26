# CI failure comparison

The third review checked PR head
`e1601bbb5b62beba46dbf83dc4f4321b10cde025`.
Its [tank CI job](https://github.com/zenascapetown-code/tervory-tank/actions/runs/40381092771/job/121777279885)
**failed: 2 failed, 3,477 passed, 20 skipped, 437 subtests passed in 867.39s**.
The completed log was downloaded. No CI retry or manual workflow run was requested.

## Every failing CI test on e1601bb

| Test | Cause | Local comparison |
| --- | --- | --- |
| `tests/test_shell_nav.py:23` — `test_pages_do_not_scroll_sideways_and_squad_does_not_grow_the_sidebar` | The assertion at line 33 sees a failed Node subprocess. `tests/shell_browser.ts:263` times out loading `/fixtures/actual-1440.html`. | The same fixture-load failure was reproduced on exact main `65067a4` during the first review fixes. |
| `tests/test_rig_postgres.py:92` — `test_rig_startup_loads_catalogues_on_postgres` | The date assertion at line 155 expects every row to be `2026-03-01`; the committed Archon catalogue includes `2026-10-18`. | The same date mismatch was reproduced on exact main `65067a4` during the first review fixes. |

The baseline is `65067a43a0d27d54b48633bf6db4f3fc211ec05f`, exported with
`git archive`. These tests and their relevant Rig/sidebar implementation files
are unchanged between that baseline and this branch. The Rig search-speed test
that failed on the prior head is not a failure of this reviewed head.

## Reproduce locally

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

## Founder must decide

- `client_connection` remains unchanged. A genuine client-network/session path
  after a block is outside this brief.
- Older user agents remain unchanged outside this lane: `tank/main.py:670` and
  `workspace/app/api/base/route.ts:129` identify as `TervoryBase/0.1`; root
  `tiger/app.py:36,81` appends `TervoryTiger/0.1` and rewrites the browser's
  HeadlessChrome identity. The shared browser and the agent under `agents/tiger`
  use `Tervory/1.0 (+https://tervory.com)`. Alignment of the older clients belongs
  to their owning threads.
- Deleting a watch removes only the watch. Existing observations and alerts are
  retained; alerts for removed URLs can remain visible under the hostname. The
  founder must decide retention and deletion behavior. This revision does not
  change stored data or deletion semantics.
