# CI failure comparison

The reviewed PR head was `596585e5e28c1f98487187c287f7d91cccd11add`.
Its [tank CI job](https://github.com/zenascapetown-code/tervory-tank/actions/runs/40338108767/job/121625135804)
**failed: 3 failed, 3,445 passed, 20 skipped, 437 subtests passed**.
The existing log was downloaded; no CI rerun was requested.

The baseline is the exact main commit
`65067a43a0d27d54b48633bf6db4f3fc211ec05f`, exported with `git archive`.
The failing tests and their implementation files are byte-identical between
that baseline and this branch. Local comparisons use Python 3.12, Node 22,
Chromium and a disposable Postgres 16 service, with `PYTHONPATH=tank`.

## Every failing CI test

1. `tests/test_core2_savings.py::test_exports_reconcile_and_keep_precise_decimals`.
   The decorator is at **line 174**, function at **175**, assertion at **184**.
   CI's exact failure was `'777' not in csv`: the valid row UUID
   `02e777e0-3dd7-4788-a60b-24402391fe39` contains that substring. Both expected
   decimal amounts were present. This is a substring assertion over a whole
   CSV, including random IDs; the cited occurrence is not a foreign price.
2. `tests/test_rig_postgres.py::test_rig_startup_loads_catalogues_on_postgres`.
   `_assert_imported` asserts at line 155 that every market date to be `2026-03-01`;
   the committed Archon catalogue includes `2026-10-18`. CI and the unmodified
   main baseline both fail with `assert '2026-10-18' == '2026-03-01'`.
3. `tests/test_shell_nav.py::test_pages_do_not_scroll_sideways_and_squad_does_not_grow_the_sidebar`.
   The subprocess assertion at line 33 fails because `tests/shell_browser.ts:263`
   throws `Page did not load http://127.0.0.1:<port>/fixtures/actual-1440.html`.
   CI and the unmodified main baseline fail at the same navigation step.

The plain three-test baseline run returned **2 failed, 1 passed in 12.02s**:
Rig and sidebar failed as above; savings passed. Ten further plain local savings
runs passed, consistent with the intermittent UUID condition. Those passes are
not presented as reproduction of the CI failure.

## Deterministic savings replay

[ci_savings_replay.py](ci_savings_replay.py) is an explicitly enabled pytest
plugin, not a collected test or runtime dependency. It fixes only the first
fixture ledger row's database-generated UUID to
`00000000-0000-4777-8000-000000000001`. The UUID stays last in the existing export
sort order. All foreign-key receipts, prices, tenants, export code and the test's
assertions remain intact. This reproduces the same valid-ID substring condition
seen in CI without waiting for random UUIDs.

On both the untouched main export and this branch:

```text
E  '777' is contained here:
E  ledger,<fixture tenant>,us-east,,00000000-0000-4777-8000-000000000001,job_id,...
tests/test_core2_savings.py:184: AssertionError
FAILED tests/test_core2_savings.py::test_exports_reconcile_and_keep_precise_decimals
1 failed
```

Main: **1 failed in 1.19s**. Branch: **1 failed in 1.16s**. No application code or
savings test file was edited for either comparison.

## Reproduce locally

Set `POOL_SCHEMA_DATABASE_URL` to a disposable Postgres 16 database with permission
to create test databases. Set `READ1_CHROMIUM_EXECUTABLE` to Chromium and use Node
22 on PATH. Install the repository's test dependencies and Workspace packages.
From either checkout, run:

```sh
PYTHONPATH=tank python -m pytest -q \
  tests/test_core2_savings.py::test_exports_reconcile_and_keep_precise_decimals \
  tests/test_rig_postgres.py::test_rig_startup_loads_catalogues_on_postgres \
  tests/test_shell_nav.py::test_pages_do_not_scroll_sideways_and_squad_does_not_grow_the_sidebar
```

For the savings replay, add this branch's **absolute evidence directory** to
PYTHONPATH while keeping `tank` relative to the checkout under test:

```sh
PYTHONPATH=tank:/path/to/tiger-branch/tests/tiger_works/evidence \
  python -m pytest -q -p ci_savings_replay \
  tests/test_core2_savings.py::test_exports_reconcile_and_keep_precise_decimals
```

The replay intentionally fails the unchanged assertion; it is evidence, not an
extra CI test. Ordinary pytest collection does not load the plugin.

## Additional local tool failures

The local environment has Blender but no `gltf-transform`, `gltfpack` or `toktx`.
That enables the forge image tests, which stop at their first missing executable:

- `tests/test_rig_forge_pipeline.py::test_neutral_samples_pass_all_real_tools[ai-sample.glb]`
- `tests/test_rig_forge_pipeline.py::test_neutral_samples_pass_all_real_tools[scan.obj]`

Both were run on unmodified main `65067a4` and failed identically:
`agents/rig/forge/pipeline.py:51: StageFailed: dedup failed; the result is not eligible for approval.`
The baseline command returned **2 failed in 5.58s**. The `dedup` stage invokes
`gltf-transform` at `agents/rig/forge/pipeline.py:82`. These are local environment
failures, not additional failures claimed for the reviewed tank CI job.

```sh
PYTHONPATH=tank python -m pytest -q \
  tests/test_rig_forge_pipeline.py::test_neutral_samples_pass_all_real_tools
```

## Smoke collection check

`test_smoke.py` passed in the full `PYTHONPATH=tank` suite. An additional isolated
`pytest tests/test_smoke.py` invocation raises `KeyError: 'tank_main'` during
collection, because its importlib harness relies on registration performed by
other collected modules. That same isolated invocation fails identically on
`65067a4` (`tank/main.py:3097`). No smoke test or unrelated Tank code was changed.
This is not counted as a failure of the full suite or of the reviewed CI job.
