# Base review: full-suite comparison

Fresh clones on the cloud machine, Python 3.12 and Node 22.23.4. Main includes the
founder’s Autumbra revert. No Autumbra code is changed in this branch.

- Main: `3261163b7ea1bcd931aecfd0018f3ad8c15c9466`.
- Branch code: `bdaa9ba1786814680f5fad2901536db369810922`.
- `.github/scripts/ci_scope.py`: `full=true`, `tests=["."]`.
- `python -m pytest -q -p no:cacheprovider --junitxml=/tmp/full.xml .` in each fresh clone.
- Same CI Python dependency installation order and fresh npm installs. Separate
  PostgreSQL 16 databases, bound only to loopback. Full commands are in README.md.
- Base and Market Lab run in the same pytest session. No tests were deselected.

| Fresh clone | Passed | Failed | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: |
| Main `3261163` | 3396 | 13 | 0 | 15 |
| Branch `bdaa9ba` | 3440 | 13 | 0 | 15 |

**0 new failing test identities versus main.**

```text
Main:   13 failed, 3396 passed, 15 skipped, 53 warnings, 437 subtests passed in 964.59s (0:16:04)
Branch: 13 failed, 3440 passed, 15 skipped, 54 warnings, 437 subtests passed in 912.45s (0:15:12)
```

Baseline categories: nine removed-Tisan-workflow checks, two Forge dedup checks, a Rig catalogue-date assertion, and a shell browser fixture timeout.

Failures on both snapshots:

- `tests.test_ci_minutes_workflows::test_concurrency_groups_differ_per_workflow`
- `tests.test_ci_minutes_workflows::test_docs_only_changes_skip_on_push_and_pull_request[tisan-site.yml]`
- `tests.test_ci_minutes_workflows::test_main_runs_are_never_cancelled_or_replaced[tisan-site.yml]`
- `tests.test_ci_minutes_workflows::test_no_workflow_uses_pull_request_target[tisan-site.yml]`
- `tests.test_ci_minutes_workflows::test_second_push_to_pull_request_cancels_the_first[tisan-site.yml]`
- `tests.test_ci_minutes_workflows::test_tisan_site_stays_on_github_hosted`
- `tests.test_ci_minutes_workflows::test_workflow_level_concurrency_block[tisan-site.yml]`
- `tests.test_ci_minutes_workflows::test_workflows_use_scope_and_do_not_hide_failed_detection`
- `tests.test_rig_forge_pipeline::test_neutral_samples_pass_all_real_tools[ai-sample.glb]`
- `tests.test_rig_forge_pipeline::test_neutral_samples_pass_all_real_tools[scan.obj]`
- `tests.test_rig_postgres::test_rig_startup_loads_catalogues_on_postgres`
- `tests.test_shell_nav::test_pages_do_not_scroll_sideways_and_squad_does_not_grow_the_sidebar`
- `tests.test_tisan_scaffold::test_site_gate_runs_in_github_actions`

An earlier complete branch run had one extra Rig timing failure: one of 200
requests took 733 ms (median 8 ms, p95 11 ms). The same benchmark passed in
isolated checks on main and the branch. The table above is the subsequent full
confirmation; no Rig code or test was changed or deselected.

Another full run exposed receipt identifiers split at hyphens in the founder
PDF. The price-status fields changed line lengths and revealed that wrapping
bug. A one-line correction plus two fixed regression cases (both fail on the
old formatter) resolve it. The table above includes that correction.

The Workspace production build (with the CI dummy Clerk settings), CI Ruff check,
PostgreSQL mixed-price/history/tenant fixtures and 375/1440 browser proof pass.
The screenshot harness is explicitly a local fixture page, not production or a
real Base-worker run. The independent review on #339 at f7124a6 separately proved
the real Tank, Base agent and Workspace flow.

The founder’s Autumbra revert landed during this work. An earlier comparison on
417eaad was superseded after its Watch HTTP test hung on both snapshots. The
comparison above uses the reverted main, without changing or skipping that lane.
Actions were not retried; the PR stays a draft. Later commits update proof
instructions and this report only; production code is the tested commit above.
