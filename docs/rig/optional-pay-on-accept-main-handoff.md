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

The source's added blind-ship collision tests were already in main through #560; applying that hunk produced no change, so no duplicate or empty commit was made. Store-method insertion conflicts were resolved while retaining both sides' work; superseded duplicate definitions were removed. All sixteen persistence methods changed by the payment source delta match the reviewed source AST. Before the main refresh below, the executable AST of payments.py, quotes/service.py and fulfilment.py matched `d0e55771`. The refresh deliberately retains main’s newer uncertain-send cancellation fix.

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

## Main refresh — 2026-11-03, PR #579

Merged main `9313fd6e07f7fc9722fcc31dac7894d92271b73c` in merge commit `8d1ebdf0`; PR #579 now targets main. All five conflicts resolved. No provider or startup wiring changed.

| File and line | Resolution |
| --- | --- |
| `agents/rig/rigbox/fulfilment.py:202` | Preserve main's database reconciliation exception → unknown; no cancel/refund with uncertain supplier send. Retain payment-only auto_only reconciliation and deferred refund recovery. |
| `agents/rig/rigbox/quotes/service.py:318` | Keep reviewed cancelling-before-cancel and refund-only-after-cancelled/missing payment recovery. |
| `agents/rig/rigbox/store.py:782` | Keep main's TenantPool autocommit checkout and per-statement transactions; retain #534 lock timeout/retries. Cancellation and supplier_po_sent methods in both stores match main's AST exactly; no duplicate methods. Payment persistence/fair selection remains. |
| `agents/rig/schema.sql:541` | Keep additive idempotent locate_attempt_at column. No new tables, policies or RLS migrations. |
| `tests/test_rig_optional_auto_order.py:355` | Import main's test_written_po_and_reconcile_database_outage_never_refunds unchanged. Proves an existing outbox PO plus database outage cannot trigger refund. |
| `tests/test_rig_optional_auto_order.py:380` | Import main's test_known_unsent_po_cancel_record_failure_still_reports_unrecorded unchanged. Preserves the distinct known-unsent cancellation-write failure. |

Changed tests: these two tests were added from main; the whole auto-order test file matches main byte-for-byte. No existing test assertion changed. Payment review fixes #511/#530/#531/#533 and schema lock fix #534 remain.

Checked `tank/main.py:753` `_startup` before pushing: RLS enforces a non-bypass tenant role and separate validated BYPASSRLS admin pool; Tank DDL uses the admin pool when configured. Rig retains main's scoped-pool schema checkout, optional-DDL rollback and existing-schema permission fallback. The actual restricted-role Rig schema test applies schema twice and passes. This refresh does not activate RLS or run production SQL.

Results: **829 passed, 11 skipped, 16 warnings in 327.75s**, versus previous **827 passed, 11 skipped** (+2 main regressions). Focused Optional/schema-lock run: **110 passed in 32.74s**. Restricted scoped-role schema run: **1 passed, 16 deselected in 1.84s**. The focused selection differs from the prior 139-test selection; the full selection is the same. Output is in `docs/rig/optional-pay-on-accept-main-refresh-validation.txt` (trailing whitespace normalized).

Exact setup and verification commands (all database URLs refer only to our throwaway local trust-auth Postgres):

```bash
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-rig-r1b
cd /workspace/codex-rig-r1b
git fetch origin main rig/optional-pay-on-accept-main
git checkout rig/optional-pay-on-accept-main
git config user.name 'Codex'
git config user.email 'codex@users.noreply.github.com'
ls -l agents/rig/rigbox/fulfilment.py agents/rig/rigbox/quotes/service.py agents/rig/rigbox/store.py agents/rig/schema.sql tests/test_rig_optional_auto_order.py docs/rig/optional-pay-on-accept-main-handoff.md tank/main.py
git merge origin/main
docker run --detach --name codex-rig-r1b-pg --publish 127.0.0.1::5432 --env POSTGRES_HOST_AUTH_METHOD=trust postgres:16
docker port codex-rig-r1b-pg 5432
TMPDIR=/workspace/codex-rig-r1b/.rig-validation PYTHONPATH=/workspace/codex-rig-r1b/.rig-validation/python-overlay RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32798/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32798/postgres /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_rig_optional*.py tests/test_rig_schema_lock_timeout.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
RLS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32798/postgres PYTHONPATH=/workspace/codex-rig-r1b/.rig-validation/python-overlay /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_tenant_rls.py -k 'room_schema_recovery and rig' -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
TMPDIR=/workspace/codex-rig-r1b/.rig-validation PYTHONPATH=/workspace/codex-rig-r1b/.rig-validation/python-overlay RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32798/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32798/postgres READ1_CHROMIUM_EXECUTABLE=/opt/google/chrome/chrome PLAYWRIGHT_BROWSERS_PATH=/home/ammosync/.cache/ms-playwright /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_rig*.py tests/rig_tiger_prices tests/custom_nation_rig -q --tb=short --continue-on-collection-errors --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
/home/ammosync/trigger-crm-venv312/bin/ruff check agents/rig tests/test_rig_optional*.py tests/test_rig_schema_lock_timeout.py --select E9,F
git diff --check
git push origin rig/optional-pay-on-accept-main
```

Clone, fetch, named-file checks, lint, whitespace and pushes succeeded. Merge initially reported the five expected conflicts; resolved as above. Reused installed dependencies through ignored local symlinks only. No secrets, model calls, external provider calls or founder-browser screenshots were needed or claimed. GitHub checks are checked separately on the final pushed head; local tests alone do not establish green CI.
