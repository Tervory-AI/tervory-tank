# TG2 offline evidence

- `tiger-regression-initial.txt`: all 502 selected Tiger cases, xdist with two
  workers, Python 3.12, embedded pgserver, Chromium and task-local Redis.
  Result: 470 passed, 1 skipped, 5 failed, 26 setup errors.
- `tiger-regression-retry.txt`: the exact 31 failed/error node IDs, serially on
  isolated PostgreSQL 16.15. Result: 31 passed. The first run lacked `pg_trgm` and
  shared cluster-wide roles across workers; no source or test assertion was
  changed to fix those environment failures.
- The sole skip is `test_filled_gold_pages_match_exactly`, whose existing
  100-page human-checked manifest has not been supplied.
- `tank-flow.txt` and `site-time.txt`: focused real-card, tenant, catalogue-outage
  and immutable site-timestamp checks.
- `workspace-python.txt`: 34 existing Workspace Python tests.
- `workspace-existing.txt`: 66 existing Workspace TypeScript tests.
- `tiger-node.txt`: 19 existing Tiger Node tests.
- `workspace-unit.txt`: 10 TG2 model/loader/action/transport regressions.
- `guards.txt`: 29 one-door/secret checks, unix sockets allowed for async fixtures.
- `browser.txt`, `visual-results.json`, `screenshots/`: all ten approved frames,
  exact FIXED copy, geometry, assets and interactions; app region excludes the
  89px Figma review annotation. Channel delta >32, changed-pixel ratio <5%.
- `frame-sha256.json`: exported reference hashes; references are in `../frames/`.
- `build.txt`, `typecheck.txt`, `lint.txt`: production build using CI dummy Clerk
  settings, TypeScript and the exact CI Ruff command.
- `chats-*.txt`, `device-next-fetch.txt`, `cli-sign-ins.txt`: existing Workspace
  contract scripts from CI.

Selection for the broad run: recursively collect `tests/**/test_*.py` whose name
starts `test_tiger` or `test_tg2`, or whose parent path contains a `tiger_*` folder.
Pytest sockets were disabled except unix/loopback. The rerun used the same IDs and
socket restrictions, with no xdist, plus a task-only PostgreSQL 16.15 container
sharing only the network namespace of the network-disabled test container.
Containers used `--rm`, `tervory.test=1`, names starting `codex-tiger-w4` and
checkout-local temporary files. No existing volume was mounted.

The browser fixture uses production React components and CSS with server reads
mocked. Real Tank durable-card dispatch is covered separately by Python tests.
Hosted CI, live account prices and founder-phone acceptance are not claimed here.
