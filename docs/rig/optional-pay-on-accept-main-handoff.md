Pay-on-Accept is rebuilt on `rig/optional-auto-order-main`, preserving #511, #530, #531, #533 and #534. The code retains the reviewed TestAdapter state machine, HMAC webhooks, idempotent refund/intent recovery, fair reconciliation and schema lock timeout. TestAdapter is instantiated only in tests. Startup still leaves the provider unset, so Accept is unavailable without a provider and the normal quote flow stays unchanged.

real checkout needs a provider connector; founder chooses the provider

Claude opens this PR from `rig/optional-pay-on-accept-main` against `rig/optional-auto-order-main`. The founder squash-merges auto-order first. After that squash, retarget this PR to main and refresh/review its resulting head before the founder's second squash merge. This job did not merge main, deploy, access production SQL, connect a provider, move money or send supplier mail.

## Reviewed source and changes

| Source | Retained behaviour |
| --- | --- |
| `rig/optional-auto-order` → `rig/optional-pay-on-accept-followup3` (`d0e55771`) | #511, #530, #531 and #533, including every source test. |
| `rig/optional-pay-on-accept-followup2` → `rig/optional-schema-lock-timeout` (`8f5bacc0`) | #534's per-statement transaction-local lock timeout, bounded retry/backoff, clean failure and tests. |
| Main | R2 guard/removal, cost-guard follow-ups (#559), and #560's order-race work. #528 and the old cost-guard branches were not reapplied. |

| File and line | Change |
| --- | --- |
| `agents/rig/rigbox/payments.py:85` | Reviewed PaymentAdapter intent/create/capture/cancel/find/retrieve/refund interface and TestAdapter. Every adapter call retains explicit test-mode guards and idempotency keys. No concrete provider added. |
| `agents/rig/rigbox/api.py:241` | Reviewed signed payment webhook; replay protection and bounded body validation. |
| `agents/rig/rigbox/quotes/service.py:148` | Held-price Accept state machine; preserve ambiguous payment/send states, cancellation and refund recovery rather than moving money twice. Opaque test payment tokens are not persisted as quote data. |
| `agents/rig/rigbox/quotes/service.py:404` | Reconciliation: flagged/unflagged passes, rotation by attempt time, auto-order-only drafts, recovery from cancelling/reconciling, failure reporting and clearing settled review flags. |
| `agents/rig/rigbox/quotes/service.py:766` | Verified webhook events enter tenant-scoped persisted recovery state; duplicates are ignored. |
| `agents/rig/rigbox/fulfilment.py:173` and `:229` | Refund only after a known cancelled/missing order; preserve uncertain send state and reconcile reviewed auto-order drafts. |
| `agents/rig/rigbox/store.py:103` and `:782` | #534 lock timeout: parameterized set_config(..., true) inside each statement's transaction; retry only 55P03 with backoff, then log and fail cleanly. Main's optional-DDL handling and cost-guard reporting are preserved. |
| `agents/rig/rigbox/store.py` | Tenant-scoped payment-state CAS, events, attempt ordering and recovery reads; preserve #533's exact PO unique-index conflict target and rollback behaviour. |
| `agents/rig/schema.sql:541` | Additive `locate_attempt_at` column. Other Optional schema is inherited from the first PR, default off. |
| `tests/test_rig_optional_pay_on_accept.py`, `tests/test_rig_optional_pay_followup.py`, `tests/test_rig_optional_pay_followup2.py`, `tests/test_rig_optional_pay_followup3.py` | All reviewed TestAdapter, ambiguous-response, cancellation/refund, backlog fairness, collision, reporting and isolation regressions. |
| `tests/test_rig_schema_lock_timeout.py:38`, `tests/test_rig.py` | Held-lock timeout, release/retry, failure and transaction-locality checks on throwaway Postgres; existing schema doubles gain transaction support. |
| `tests/test_rig_locate_checkout.py` | Reviewed legacy-provider compatibility for the standardized idempotent refund contract. |

The source's added blind-ship collision tests were already in main through #560; applying that hunk produced no change, so no duplicate or empty commit was made. Store-method insertion conflicts were resolved while retaining both sides' work; superseded duplicate definitions were removed. All sixteen persistence methods changed by the payment source delta match the reviewed source AST. The entire executable AST of payments.py, quotes/service.py and fulfilment.py also matches `d0e55771`.

No UI, page wording, provider credentials, pricing rules or credit controls were added. Runtime demo data was not restored. Any added auto-order fixture literals use invented store/part values and remain in tests.

## Verification and exact commands

Final full Rig result: **827 passed, 11 skipped, 15 warnings in 306.27 seconds**, exit 0. The focused state-machine/Optional/lock-timeout/R2 suite also passed **139 tests**. Raw final output, with trailing whitespace normalized, is committed in `docs/rig/optional-pay-on-accept-main-validation.txt`.

All database tests used the disposable local Postgres 16 container described in the auto-order handoff (`127.0.0.1:32790`). Each database test creates/drops its own unique database. External sockets and nonlocal DNS were blocked. Skips require opt-in Docker/Hermes images, missing Forge tools, or an uncommitted private supplier export; no real model or provider was enabled.

Exact source-application commands (run per file, with inspected conflicts resolved before committing):

```bash
git diff origin/rig/optional-auto-order origin/rig/optional-pay-on-accept-followup3 -- "$rig_file" | git apply --3way
git diff origin/rig/optional-pay-on-accept-followup2 origin/rig/optional-schema-lock-timeout -- "$rig_file" | git apply --3way
git add "$rig_file"
git commit -m "rig: retain reviewed pay-on-Accept changes in $rig_file"
git push
```

New source test files were read directly from the named reviewed ref with `git show` and committed/pushed individually. Old branches were never merged wholesale, and no old supplier/demo data was carried into runtime.

Exact focused command:

```bash
TMPDIR=/workspace/rig-optional-pay-on-accept-main/.rig-validation RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32790/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32790/postgres /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_rig_optional*.py tests/test_rig_locate_checkout.py tests/test_rig_schema_lock_timeout.py tests/test_rig_runtime_catalogues.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Result: **139 passed in 32.71 seconds**. TestAdapter proves Accept → pay → store order and supplier PO; failure/cancellation → one refund and cancelled records; replay does not move money twice. Existing no-provider and store-switch tests prove refusal/default-off isolation and unchanged quote behaviour.

Exact final full command:

```bash
TMPDIR=/workspace/rig-optional-pay-on-accept-main/.rig-validation PYTHONPATH=/workspace/rig-optional-pay-on-accept-main/.rig-validation/python-overlay RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32790/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32790/postgres READ1_CHROMIUM_EXECUTABLE=/opt/google/chrome/chrome PLAYWRIGHT_BROWSERS_PATH=/home/ammosync/.cache/ms-playwright /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_rig*.py tests/rig_tiger_prices tests/custom_nation_rig -q --tb=short --continue-on-collection-errors --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

The local ignored Python overlay reuses already-installed jsonschema dependencies from the existing Trigger test runtime; Workspace node_modules and the complete venv-ci were also reused read-only. No shared dependency environment or lockfile changed.

```bash
/home/ammosync/trigger-crm-venv312/bin/ruff check agents/rig tests/test_rig_optional_pay*.py tests/test_rig_schema_lock_timeout.py --select E9,F
git diff --check origin/rig/optional-auto-order-main...HEAD
git diff --exit-code origin/main -- agents/rig/app.py agents/rig/rigbox/service.py agents/rig/rigbox/shopper_attributes.py agents/rig/rigbox/catalogue.py
git fetch origin rig/optional-auto-order-main
git merge --no-edit origin/rig/optional-auto-order-main
git push
git merge-base --is-ancestor origin/rig/optional-auto-order-main HEAD
```

Results: lint, whitespace, unchanged-startup/R2/cost-module checks and ancestry pass. The final base refresh added only the first PR's two documentation files; executable code and test content were unchanged from the full passing run.

## Review boundary

Deploy-on-main selects Rig and its regional copies. Startup's explicit absent-provider refusal is unchanged. Claude opens both PRs and checks CI; these local test results do not claim an uncreated PR is green. This run's revised DONE condition is proof against TestAdapter in tests. No founder-session screenshots or real checkout proof are claimed.
