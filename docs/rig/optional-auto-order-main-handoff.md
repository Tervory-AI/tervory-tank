Auto-order is rebuilt on current main from the reviewed #510 feature delta (`rig/optional-blind-ship` → `rig/optional-auto-order`, source head `6694ff13`). A store's `auto_order` setting is false by default. When explicitly enabled, a paid sandbox Locate order writes its supplier PO once to a local `.eml` outbox. There is no SMTP or live supplier transport.

real checkout needs a provider connector; founder chooses the provider

Claude opens this PR from `rig/optional-auto-order-main` against `main`. Founder squash-merges it before the pay-on-Accept PR. No main push, merge, deployment, production SQL, real payment or external supplier message was performed by this job.

## What changed

| File and line | Behaviour |
| --- | --- |
| `agents/rig/rigbox/supplier_orders.py:1` | Reviewed sandbox-only outbox; stable references, exclusive file creation, no network transport, source vendor/inbox validation. |
| `agents/rig/rigbox/fulfilment.py:132` | Send a draft supplier PO once; retain receipts and report uncertain writes accurately. |
| `agents/rig/rigbox/fulfilment.py:173` and `:228` | Strict cancellation and reconciliation: sent or uncheckable POs prevent an unsafe refund; unreadable and stranded POs are reported distinctly. |
| `agents/rig/rigbox/quotes/service.py:148` | Check outbox/source readiness before consuming the hold or paying; preserve all #510 review fixes around cancellation and unknown send state. |
| `agents/rig/rigbox/locate_live.py`, `agents/rig/rigbox/locate.py`, `agents/rig/rigbox/api.py` | Carry source vendor/inbox into the private held order; peek a usable hold before consuming it. No shopper supplier fields. |
| `agents/rig/rigbox/retailer.py:134`, `agents/rig/rigbox/store.py:373` and `:990` | Tenant-scoped, strictly boolean per-store switch; absent values preserve the saved setting; default is off. R2 shop settings remain preserved. |
| `agents/rig/schema.sql:168` | Additive default-off switch, source vendor/inbox columns, and supplier PO send receipt columns. |
| `tests/test_rig_optional_auto_order.py:1`, `tests/test_rig_store_job.py` | All reviewed auto-order regressions, real Postgres persistence/cancellation/reconciliation, default-off store settings. Added test literals use the invented Harbor Gear name and SRC part ID. |

The old endpoint diff also reversed unrelated newer work. Those reversions were excluded: main's R2 removal, cost guards (#559), and order-race safeguards (#560) remain intact. No demo directory is restored. Existing uploaded data and startup's absent-provider refusal are unchanged. No UI controls, copy or Figma changes.

## Verification

Final result: **758 passed, 11 skipped, 15 warnings in 291.84 seconds**, exit 0.

The full Rig suite used a new disposable Postgres 16 container bound only to `127.0.0.1:32790`. Tests create/drop uniquely named databases. No production database was used. The eleven skipped checks depend on opt-in Docker/Hermes images, Forge executables absent from this host, or the uncommitted private supplier export; none was enabled to make a model call.

Exact feature-application commands (run once per named file):

```bash
git fetch origin main
git checkout -B rig/optional-auto-order-main origin/main
git diff origin/rig/optional-blind-ship origin/rig/optional-auto-order -- "$rig_file" | git apply --3way
git add "$rig_file"
git commit -m "rig: preserve reviewed auto-order changes in $rig_file"
git push
```

For `store.py`, only the reviewed auto-order methods, read columns and timestamp bookkeeping were carried over; main's shop and cost-guard methods and number-conflict fix were retained. For `schema.sql`, the unrelated cost-guard deletion hunk was excluded. All six other changed runtime files applied cleanly. No real merchant data was introduced. Commit history records each finished file and push.

Exact database setup:

```bash
docker run --detach --name rig-optional-rebuild-pg --publish 127.0.0.1::5432 --env POSTGRES_HOST_AUTH_METHOD=trust postgres:16
docker port rig-optional-rebuild-pg 5432
```

Result: disposable PostgreSQL on `127.0.0.1:32790`.

The existing complete `venv-ci` and Workspace node_modules were reused. Current main also imports jsonschema via Trigger; its already-installed jsonschema, jsonschema_specifications, referencing and rpds packages were symlinked from `/home/ammosync/trigger-crm-venv312/lib/python3.12/site-packages` into this checkout's ignored `.rig-validation/python-overlay`. No shared environment or dependency lockfile was changed.

Exact final full-suite command:

```bash
TMPDIR=/workspace/rig-optional-auto-order-main/.rig-validation PYTHONPATH=/workspace/rig-optional-auto-order-main/.rig-validation/python-overlay RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32790/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32790/postgres READ1_CHROMIUM_EXECUTABLE=/opt/google/chrome/chrome PLAYWRIGHT_BROWSERS_PATH=/home/ammosync/.cache/ms-playwright /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_rig*.py tests/rig_tiger_prices tests/custom_nation_rig -q --tb=short --continue-on-collection-errors --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Full output, with trailing whitespace normalized, is in `docs/rig/optional-auto-order-main-validation.txt`. External sockets and nonlocal DNS were blocked. The prior missing-dependency run and corrected send-receipt/settings-assertion failures are not claimed as passing; the result above is from the final run.

```bash
/home/ammosync/trigger-crm-venv312/bin/ruff check agents/rig tests/test_rig_optional_auto_order.py --select E9,F
git diff --check origin/main...HEAD
```

Results: lint and whitespace checks pass. The R2 runtime-data guard is included in the full test run.

## Review and test boundary

This PR changes Rig runtime code and additive schema; deploy-on-main selects Rig and its regional copies. The founder merges; Claude opens the PR and checks its CI. This handoff reports local test results, not an uncreated PR's CI status. No founder-session screenshots are claimed: this run's revised DONE condition is TestAdapter/state-machine proof in tests; the TestAdapter integration lands in the second PR. Provider checkout and live store/browser proof remain outside this run.
