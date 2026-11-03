# Rig never takes payment — 3 November 2026

Payments were removed on **3 Nov**, by the founder’s decision: the ZA quote flow ends at the store. The client accepts Rig’s held-price quote; the store issues its own invoice in its own system and receives EFT directly. Rig does not collect, capture, void or refund money, and takes no card or bank fields. This supersedes the former pay-on-Accept handoff and its TestAdapter/payment-webhook instructions.

Branch: `codex/rig-no-payments`; continuation checkout `/workspace/fresh-rig-nopay-0845` (historical checkout `/workspace/codex-rig-nopay`). Main already contains #599, #604 and #603; none was reapplied. The completed Figma branch and the other cart checkout were preserved. Claude opens the PR. The founder merges; no PR merge or deployment was performed.

## Resulting flow and API

* `POST /v1/rig/locate/accept` accepts only the existing product/hold/contact/notice/delivery fields. The provider token field is gone. Accept records `accepted`, the held selling price, each item’s delivery metadata and the private offer snapshot, then uses the existing quote email/webhook handoff with its retries and `needs_person` exhaustion. It creates neither a store order nor a supplier PO. It does not require an order-mode or outbox setting just to accept a quote.
* `POST /internal/retailer/confirm-store-payment` is a new operation in the existing authenticated retailer corridor. It uses `x-rig-retailer-key` (the existing **RIG_RETAILER_KEY** setting, by name only), the caller’s `tenant_id`, and `data: {"quote_id": "<accepted request_id>"}`. No payment amount, provider token, bank or card data is accepted by this action. The store is asserting receipt in its own system; Rig makes no financial request.
* A tenant-scoped JSON compare-and-swap records the store confirmation and claims a placement lease before fulfilment. Only then is `fulfilment.place_located_order` called. When the store’s `auto_order` switch is on, the existing supplier-order path follows. A completed second confirmation returns the same result without another state write, order or outbox message. An active lease does no work on duplicate requests; after 15 minutes a lost worker can be resumed against the same stable order/PO and exclusive outbox record.
* The existing sandbox-only order/outbox guards remain: **RIG_LOCATE_ORDER_MODE** and **RIG_LOCATE_OUTBOX_DIR** are existing setting names, not new live checkout configuration. Blind shipping, neutral slips, approved-source details, sent-PO refusal, exclusive outbox creation, unique-number collision rollback and unknown/unrecorded-send handling remain. Rig sends no live supplier email in these tests. An unreadable or ambiguously recorded send is kept for review, never treated as an unsent PO. A known unsent failed supplier order may be cancelled; the store handles any financial consequences outside Rig.
* Old provider-era rows, including historical `ordered` rows without this flow’s `accepted_at`, are refused by the new confirmation action and left unchanged. No payment state is newly written. The old payment module, token/route, adapter calls, webhook-event writes and payment-reconciliation queries are removed. Historical JSON and all existing columns/tables remain.

No admin button or widget rendering was added. Those need approved Figma frames. No US cart, five-minute checkout or platform connector was built or edited.

## Delivery response fields

Every product/setup quote acknowledgement now has `items`; each item carries `delivery`. The same metadata is in the stored quote and accepted held-price response. Link-only requests have no known items and return an empty list rather than invented product details.

| Item source | Delivery fields |
| --- | --- |
| Store stock | `min_days`, `max_days`, `back_order: false`, using the store’s own supplied range. An unconfigured range has null endpoints. |
| Locate offer | `ship_days`, `eta`, `back_order: false`, from the selected offer and snapshotted in the hold/accepted quote. |
| Out-of-stock item with no available Locate offer | `ship_days: null`, `eta: null`, `back_order: true`. |

An optional `retailers.delivery` JSON range (`min_days`/`max_days`) is saved through the existing retailer settings API only. Both values must be integers with `0 <= min_days <= max_days <= 365`; omission preserves the saved range. The default is empty, never a made-up delivery promise. The standard shopper projection still strips supplier identity, URL, cost and provenance; the new fields do not include those details.

## Files and lines

| File | Change |
| --- | --- |
| `agents/rig/rigbox/payments.py` | Deleted provider abstraction, TestAdapter and provider webhook helpers. |
| `agents/rig/rigbox/api.py:211` | Payment-free Accept input and route; removed provider webhook route. |
| `agents/rig/rigbox/quotes/service.py:142` | Item metadata on quote responses; accepted-quote handoff and store-confirmation state machine immediately below. |
| `agents/rig/rigbox/retailer_api.py:17` and `:54` | Existing corridor operation allowlist and authenticated store-confirmation action. |
| `agents/rig/rigbox/service.py:653` | Per-item store/Locate/back-order delivery projection; removed unused provider attribute. |
| `agents/rig/rigbox/locate.py:233`, `locate_live.py:304` | Public offer/hold ship days alongside ETA, without private supplier fields. |
| `agents/rig/rigbox/retailer.py:137` | Validate and preserve the backend-only store delivery range. |
| `agents/rig/rigbox/store.py:392`, `:482`, `:581`, `:1088`, `:1272`, `:1456` | Delivery persistence, tenant-scoped quote read and existing JSON CAS; removed payment-event/list methods. |
| `agents/rig/schema.sql:172` | Additive/idempotent empty-default delivery column on the existing tenant retailer table. No table or column dropped. |
| `agents/rig/rigbox/fulfilment.py:1` | Updated obsolete payment/refund comments only. Executable AST is identical to main. |
| `agents/rig/app.py:381`, `.env.example:278` | Correct startup explanation; remove RIG_LOCATE_PAYMENTS_MODE. No Rig payment settings were present in the compose files. |
| `tests/test_rig_no_payments.py:1` | New removal guard, acceptance/handoff/retry tests, tenant/idempotency/concurrency/lease/history checks, delivery and real Postgres coverage. |
| Remaining changed/deleted test files below | Every test function removed, changed or added is listed individually. |

### RLS and deployment

Read `tank/main.py:_startup` (`:754` onward) before pushing: it uses the separate administrative pool for DDL and refuses bypass tenant roles when RLS is enforced. This change adds a column to the existing tenant-scoped retailer table, so existing table grants/policies apply. All new quote reads and CAS operations filter by tenant and quote ID. The unchanged Rig per-statement schema application/lock-timeout path was retained. The new Postgres test applies the schema twice and exercises concurrent, tenant-isolated confirmation. No production SQL was run.

Deployment impact on a future founder merge: Rig source changes redeploy the Rig room and regional copies, including ZA. There are no compose changes; only the obsolete name in `.env.example` is removed. No secret value was read, typed or created, no provider was connected, and no production data changed.

## Historical validation and exact commands

Final complete Rig suite: **735 passed, 19 skipped, 14 warnings in 554.03s (0:09:14)**, exit 0.

Focused delivery/hold/blind-ship/auto-order/no-payments suite: **76 passed in 63.15s**, with Postgres and outbound sockets blocked. Initial failed-target retry after environment setup: **22 passed in 10.66s**. CI-level lint (`E9,F`) passes for `tank tests` and the changed Rig modules. A code comparison after removing docstrings confirmed the executable `fulfilment.py` AST is unchanged from main.

The first broad attempt reported 19 failed, 700 passed, 19 skipped in 470.36s. One old public-response assertion needed the newly required `ship_days`; two Node tests lacked local installed dependencies; browser cases failed on temporary-profile disk I/O. The assertion is updated, existing installed TypeScript/React packages were copied into this checkout, and browser temp files now use this checkout’s local directory. No product/UI code was changed to resolve those environment failures. The final full result above supersedes that attempt.

Initial setup, successful (named-file `ls` also passed):

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-rig-nopay
cd /workspace/codex-rig-nopay
git fetch origin main
git checkout -B codex/rig-no-payments origin/main
git config user.name 'Codex'
git config user.email 'codex@users.noreply.github.com'
ls agents/rig/rigbox/payments.py agents/rig/rigbox/api.py agents/rig/rigbox/quotes/service.py agents/rig/rigbox/fulfilment.py agents/rig/rigbox/retailer_store.py agents/rig/schema.sql agents/rig/rigbox/retailer_api.py agents/rig/rigbox/locate.py docs/rig/optional-pay-on-accept-main-handoff.md tank/main.py .env.example docker-compose.yml docker-compose.za.yml
```

After every finished file, `.git/rig-nopay/finish-file.sh <file> <commit message>` ran exactly these commands, sequentially; all completed pushes succeeded:

```sh
git add -- "$1"
git commit -m "$2"
git fetch origin main
git merge origin/main
git push origin HEAD:codex/rig-no-payments
```

Disposable Postgres 16, trust authentication on loopback only, no password created:

```sh
docker run -d --name codex-rig-nopay-pg -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=rig_nopay_test -p 127.0.0.1::5432 postgres:16
docker port codex-rig-nopay-pg 5432
docker exec codex-rig-nopay-pg pg_isready -U postgres
```

Result: mapped `127.0.0.1:32844`; accepting connections. Each database test creates/drops a unique disposable database.

Existing dependency/runtime reuse and successful failed-target retry:

```sh
mkdir -p workspace/node_modules .git/rig-nopay/tmp
cp -a /workspace/codex-rig-cart/workspace/node_modules/typescript /workspace/codex-rig-cart/workspace/node_modules/react /workspace/codex-rig-cart/workspace/node_modules/react-dom /workspace/codex-rig-cart/workspace/node_modules/scheduler workspace/node_modules/
TMPDIR=/workspace/codex-rig-nopay/.git/rig-nopay/tmp READ1_CHROMIUM_EXECUTABLE=/opt/google/chrome/chrome RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32844/rig_nopay_test PYTHONPATH=agents/_chassis:agents/rig /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig_3d_workspace.py tests/test_rig_feeds_workspace.py tests/test_rig_supply_locate.py 'tests/test_rig_landing_overflow.py::test_decorative_overflow_preserves_viewport[landing-tervory-375]' -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Final complete command:

```sh
TMPDIR=/workspace/codex-rig-nopay/.git/rig-nopay/tmp READ1_CHROMIUM_EXECUTABLE=/opt/google/chrome/chrome RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32844/rig_nopay_test PYTHONPATH=agents/_chassis:agents/rig /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig* -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
/workspace/codex-tiger-t1/.venv/bin/python -m ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
git diff --check
```

Full-suite test output and intermediate command logs remain under `.git/rig-nopay/` as local orchestration evidence. They are not live data or a shipped fixture.

Additional exact validation commands (the first is the 76-pass focused run):

```sh
RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32844/rig_nopay_test PYTHONPATH=agents/_chassis:agents/rig /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig_no_payments.py tests/test_rig_optional_auto_order.py tests/test_rig_optional_blind_ship.py tests/test_rig_locate_checkout.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
python3 - <<'AST_CHECK'
import ast, subprocess
from pathlib import Path
old = ast.parse(subprocess.check_output(['git', 'show', 'origin/main:agents/rig/rigbox/fulfilment.py'], text=True))
new = ast.parse(Path('agents/rig/rigbox/fulfilment.py').read_text())
for tree in (old, new):
    for node in ast.walk(tree):
        if (isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body = node.body[1:]
assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)
print('PASS: executable fulfilment AST unchanged from main; #578 safety implementation retained')
AST_CHECK
```

Both commands passed. The first broad invocation, before local dependency/temp setup, used the same Postgres/PYTHONPATH prefix with `python -m pytest tests/test_rig* -q --tb=short`; its 19 failures and final replacement result are recorded above. An exploratory unrestricted Ruff check also reported 34 style findings; this is not claimed as a passing check. The repository's required `E9,F` lint selection passed.

After validation, only this job's disposable database container was removed with `docker rm -f -v codex-rig-nopay-pg`. The final Git verification uses `git diff --check origin/main...HEAD`, `git rev-parse HEAD`, `git ls-remote origin refs/heads/codex/rig-no-payments` and `git status --short --branch`; final remote head and clean-state evidence are reported in the task.

## Every removed or changed test

Names containing the old word “refund” are historical test identifiers; remaining supplier-safety cases now run through store confirmation without a provider or financial operation. The two renamed order-failure tests replace refund assertions with `needs_person` / supplier-failure review assertions. Existing direct fulfilment/collision/unknown-send tests remain intact, including `test_known_unsent_po_cancel_record_failure_still_reports_unrecorded`.

### Removed

| File | Test | Reason |
| --- | --- | --- |
| `tests/test_rig_locate_checkout.py` | `test_payments_refuse_without_test_mode_live_keys_and_unproven_test_charges` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_locate_checkout.py` | `test_accept_pays_in_test_mode_then_orders_and_records_each_state` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_locate_checkout.py` | `test_accept_refunds_when_sandbox_order_fails` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_locate_checkout.py` | `test_accept_refuses_before_taking_hold_or_payment` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_locate_checkout.py` | `test_accept_without_provider_refuses` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_locate_checkout.py` | `test_tenant_isolation_hold_offer_and_switch` | Replaced by confirmation tenant-isolation and held-price tests in test_rig_no_payments.py. |
| `tests/test_rig_optional_auto_order.py` | `test_supplier_order_failure_refunds` | Renamed/replaced below: order failures require store review, with no Rig refund. |
| `tests/test_rig_optional_blind_ship.py` | `test_blind_order_failure_refunds` | Renamed/replaced below: order failures require store review, with no Rig refund. |
| `tests/test_rig_optional_pay_followup.py` | `test_a_backlog_of_flagged_quotes_never_starves_a_newer_refund` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup.py` | `test_memory_store_lists_flagged_quotes_only_in_their_own_pass` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup.py` | `test_real_postgres_lists_flagged_quotes_only_in_their_own_pass` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup.py` | `test_an_unrecorded_cancel_at_accept_is_left_cancelling_and_finished_by_reconcile` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup.py` | `test_review_flags_are_cleared_when_a_flagged_quote_settles` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup.py` | `test_reconcile_error_is_cleared_when_a_retried_refund_settles` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup.py` | `test_reconcile_cancels_an_unsent_po_when_the_send_refused_before_writing` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup.py` | `test_reconcile_stays_strict_for_other_send_errors` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup.py` | `test_memory_store_refuses_an_order_number_taken_by_another_quote` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup2.py` | `test_unflagged_refunds_that_fail_every_run_rotate_behind_a_newer_refund` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup2.py` | `test_a_flagged_quote_behind_120_older_flagged_quotes_is_reached` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup2.py` | `test_memory_store_lists_least_recently_tried_first` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup2.py` | `test_manual_drafts_never_block_a_stranded_auto_order_refund` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup2.py` | `test_memory_store_auto_only_drafts_rotate_and_default_is_unchanged` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup2.py` | `test_memory_store_po_number_clash_is_order_mismatch` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup2.py` | `test_real_postgres_po_number_clash_is_order_mismatch_and_saves_nothing` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup2.py` | `test_real_postgres_lists_rotate_by_last_attempt_and_drafts_are_auto_only` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup2.py` | `test_reconcile_docstrings_describe_rotation_and_the_checked_count` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup2.py` | `test_checked_counts_each_list_so_it_can_exceed_limit` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup3.py` | `test_100_stuck_reconciling_quotes_with_sent_pos_no_longer_starve_a_newer_refund` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup3.py` | `test_a_stuck_reconciling_quote_is_settled_by_its_order` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup3.py` | `test_a_failing_attempt_write_is_reported_in_the_result_and_logged` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup3.py` | `test_draft_list_summary_and_po_conflict_target` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_followup3.py` | `test_real_postgres_po_conflict_target_is_exactly_a_unique_index` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_webhook_signature_accepts_only_a_fresh_exact_hmac` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_webhook_verification_sits_behind_the_test_mode_guard` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_test_adapter_moves_money_at_most_once_per_key` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_live_mode_is_refused_before_any_adapter_call` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_the_test_adapter_is_not_wired_into_the_app_and_there_is_no_live_mode` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_accept_pays_then_auto_orders_once` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_supplier_order_failure_refunds_the_captured_payment` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_order_failure_refunds_the_captured_payment` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_declined_or_failed_capture_places_no_order` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_lost_capture_response_is_resolved_by_the_cancel_call` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_capture_failure_with_a_lost_cancel_is_settled_by_reconcile` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_reconcile_refunds_a_paid_quote_with_no_order_once` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_reconcile_records_an_order_placed_before_the_crash_and_never_refunds_it` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_reconcile_refunds_a_pending_intent_that_was_captured_before_the_crash` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_refused_capture_is_voided` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_refusal_after_capture_is_refunded_by_reconcile` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_lost_create_intent_response_is_voided_by_reconcile` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_create_intent_that_never_reached_the_provider_settles_as_failed` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_crash_between_ordered_and_the_supplier_send_is_cancelled_and_refunded` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_stranded_po_the_supplier_has_is_not_refunded` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_an_unconfirmed_supplier_order_is_never_refunded_on_a_guess` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_refund_that_fails_at_accept_is_retried_by_reconcile` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_refund_whose_response_was_lost_is_replayed_with_one_adapter_call` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_stranded_po_whose_refund_fails_is_left_refund_due_and_retried` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_manual_order_is_never_refunded_after_the_store_turns_auto_order_on` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_crashed_auto_order_is_settled_after_the_store_turns_auto_order_off` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_failed_refund_due_write_after_accept_cancels_is_refunded_by_reconcile` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_failed_refund_due_swap_in_the_stranded_branch_is_refunded_next_run` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_a_quote_left_cancelling_is_settled_from_the_order` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_an_order_saved_before_place_raised_is_never_refunded` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_reconcile_is_test_mode_only` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_one_shot_providers_still_work` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_webhook_route_records_signed_events_once` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_real_postgres_payment_events_are_deduplicated_atomically` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |
| `tests/test_rig_optional_pay_on_accept.py` | `test_real_postgres_reconcile_claims_each_stuck_quote_once` | Retired provider/intent/webhook/refund/reconciliation contract; Rig no longer moves money. |

### Changed

| File | Test | Reason |
| --- | --- | --- |
| `tests/test_rig_locate_checkout.py` | `test_confirm_issues_hold_from_live_price_without_supplier_fields` | The public response now includes the required safe ship_days field. |
| `tests/test_rig_optional_auto_order.py` | `test_accept_auto_orders_once_through_the_sandbox_outbox` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_auto_order.py` | `test_source_without_vendor_or_inbox_refuses_before_payment` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_auto_order.py` | `test_missing_outbox_refuses_before_hold_or_payment` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_auto_order.py` | `test_switch_off_keeps_the_draft_po_and_writes_nothing` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_auto_order.py` | `test_supplier_failure_after_the_outbox_write_keeps_the_order_and_does_not_refund` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_auto_order.py` | `test_written_po_and_reconcile_database_outage_never_refunds` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_auto_order.py` | `test_outbox_unavailable_on_cancel_never_refunds` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_auto_order.py` | `test_accept_refunds_when_the_send_itself_refused_before_writing` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_blind_ship.py` | `test_blind_accept_records_a_rig_order_and_a_neutral_slip_po_to_the_shopper` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_blind_ship.py` | `test_blind_accept_without_address_refuses_before_hold_or_payment` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_blind_ship.py` | `test_switch_off_keeps_the_existing_ship_to_store_order` | Run ordering after retailer confirmation; preserve the supplier/blind-shipping safety assertions and remove provider assertions. |
| `tests/test_rig_optional_blind_ship.py` | `test_locate_confirm_accept_responses_have_no_supplier_identity_or_cost` | Accept returns safe delivery metadata and creates no order; supplier-private data remains absent. |
| `tests/test_rig_supply_locate.py` | `test_http_locate_and_admin_ingestion_boundaries` | The public response now includes the required safe ship_days field. |

### Added

| File | Test | Reason |
| --- | --- | --- |
| `tests/test_rig_no_payments.py` | `test_accept_without_order_configuration_stores_and_hands_off_only` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_no_payments.py` | `test_confirmation_is_concurrent_idempotent_and_tenant_scoped` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_no_payments.py` | `test_every_setup_item_carries_delivery_metadata` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_no_payments.py` | `test_failed_handoff_retries_existing_quote_without_ordering` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_no_payments.py` | `test_historical_provider_state_is_preserved_and_cannot_place_an_order` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_no_payments.py` | `test_no_provider_module_route_setting_or_call_remains` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_no_payments.py` | `test_postgres_store_confirmation_schema_twice_and_tenant_isolation` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_no_payments.py` | `test_quote_items_expose_store_time_offer_time_or_back_order_without_provenance` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_no_payments.py` | `test_retailer_http_confirmation_requires_existing_control_auth_and_only_quote_id` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_no_payments.py` | `test_stale_confirmation_lease_recovers_same_saved_order_and_outbox` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_no_payments.py` | `test_store_delivery_range_is_validated_and_preserved` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_optional_auto_order.py` | `test_supplier_order_failure_needs_store_review` | New payment-free flow regression or renamed store-review order-failure case. |
| `tests/test_rig_optional_blind_ship.py` | `test_blind_order_failure_needs_person` | New payment-free flow regression or renamed store-review order-failure case. |

## Founder acceptance — outstanding

No founder-browser test or screenshot is claimed. After the founder merges/deploys, he must accept a quote on the Custom Nation test page and see its store handoff without a payment step, then confirm through the authenticated retailer API and verify exactly one order/PO. API responses carry each item’s delivery time or back-order flag without supplier details. Widget display and a retailer confirmation button remain Figma items; this job adds no unapproved rendering or wording.

The founder’s test screenshots must be added to the PR after that acceptance. Tests passing is not the founder’s DONE WHEN. Claude opens the PR; the founder’s review and merge remain pending.


## Fresh continuation of #613

The latest public `task_complete` at 2026-11-03T16:47:59.307Z explicitly acknowledged stopping with no push in flight. Its reported uncommitted `tank/command.py` diff was copied read-only from the stopped checkout and preserved here. No old checkout was edited.

`rig.quote.confirm_payment` uses the existing /chats Confirm card, with the tool name as its label and only `quote_id` as its argument. Tenant admins receive it through the same additional tool exposure as Trigger; the founder also receives it, ordinary members do not. Confirmed dispatch binds the saved card to the signed-in tenant, user, tool and arguments. The existing Tank corridor derives tenant identity from the actor and writes a $0 `code` ledger receipt on success. This operation uses its tool permission rather than requiring a separate Rig squad grant; other retailer operations keep their existing gate.

| File and line | Continuation change |
| --- | --- |
| `tank/command.py:44`, `:118`, `:1018`, `:1262`, `:1461`, `:1655` | Tool registration, admin/founder exposure, strict arguments, adapter and confirmed dispatch; preserved stopped-owner patch. |
| `tank/access.py:938` | Existing confirmation corridor checks tool authority; other operations retain the Rig squad gate. |
| `tests/test_command.py:1408`, `:1430`, `:1469` | Ordinary-member denial/admin/founder exposure, required Confirm and $0 code receipt, other-tenant 404 through confirmed admin dispatch. |
| `tests/test_rig_no_payments.py:193`, `:204`, `:207`, `:229`, `:236`, `:247`, `:271`, `:300`, `:314` | Explicit placeholder test data. |

After merge, the founder fills these setting names only: `RIG_LOCATE_ORDER_MODE`, `RIG_RETAILER_KEY`, `RIG_LOCATE_OUTBOX_DIR` for auto-order, plus the store's delivery range through existing retailer settings.

No founder browser acceptance is claimed. Verification uses offline tests with a disposable local Postgres, never a model call. Historical results above are not claims for this continuation's final head. CI's `tank` job is the full-suite test of record; its final-head result is recorded in the PR body.

Fresh-checkout commands (the first collection attempt lacked `jsonschema`; the local overlay reuses installed packages without changing a shared environment):

```sh
git clone --single-branch --branch codex/rig-no-payments https://github.com/Tervory-AI/tervory-tank.git /workspace/fresh-rig-nopay-0845
git config user.name Codex
git config user.email codex@openai.com
git -C /workspace/codex-rig-nopay diff -- tank/command.py | git apply
docker run --detach --name fresh-rig-nopay-0845-pg --publish 127.0.0.1::5432 --env POSTGRES_HOST_AUTH_METHOD=trust postgres:16
docker port fresh-rig-nopay-0845-pg 5432
TMPDIR=/workspace/fresh-rig-nopay-0845/.rig-validation PYTHONPATH=.rig-validation/python-overlay:agents/_chassis:agents/rig POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32864/postgres RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32864/postgres /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_command.py -k rig_confirmation tests/test_rig_no_payments.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
TMPDIR=/workspace/fresh-rig-nopay-0845/.rig-validation PYTHONPATH=.rig-validation/python-overlay:agents/_chassis:agents/rig RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32864/postgres /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_rig_no_payments.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
/home/ammosync/trigger-crm-venv312/bin/ruff check tank/command.py tank/access.py tests/test_command.py tests/test_rig_no_payments.py --select E9,F
git diff --check
```

Results: the three new Command tests pass (`3 passed, 99 deselected`); the separate no-payments suite passes (`16 passed`). Lint and whitespace pass. The initial new permission test omitted its runtime fixture; that test harness issue was corrected before these passing runs.


Before the first push, re-fetch found newer remote commits `e8ad7ca1`, `401130a1`, `a651d586`. All were preserved with a branch merge; overlapping placeholder-only conflicts in `tests/test_rig_no_payments.py` use the remote version, including its transient/permanent-error/lost-lease tests. Main was merged exactly once in this fresh continuation, at the end, from fetched commit `dc270ec75be61f2cafa783937f57114614526ffb`.

```sh
git fetch origin codex/rig-no-payments main
git merge --no-edit origin/codex/rig-no-payments
# Resolve overlapping placeholder edits by preserving the newer remote test file.
git show origin/codex/rig-no-payments:tests/test_rig_no_payments.py > tests/test_rig_no_payments.py
git add tests/test_rig_no_payments.py
git commit -m "Merge newer no-payments branch work and preserve regression tests"
git merge --no-edit dc270ec75be61f2cafa783937f57114614526ffb
TMPDIR=/workspace/fresh-rig-nopay-0845/.rig-validation PYTHONPATH=.rig-validation/python-overlay:agents/_chassis:agents/rig POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32864/postgres RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32864/postgres /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_rig_confirmation_command.py tests/test_rig_no_payments.py tests/test_command.py -k 'rig_confirmation or confirmation_tool or confirm_card or test_rig_no_payments' -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
/home/ammosync/trigger-crm-venv312/bin/ruff check tank/command.py tank/access.py tests/test_command.py tests/test_rig_confirmation_command.py tests/test_rig_no_payments.py --select E9,F
git diff --check dc270ec75be61f2cafa783937f57114614526ffb...HEAD
```

Final merged-code focused result: **26 passed, 83 deselected, 3 warnings in 16.66s**. Lint and whitespace pass. Final-head CI evidence is maintained in PR #613 so recording its result does not create another untested head.

## PR #613 review fixes — 3 November 2026

This section supersedes the earlier confirmation-error behavior and validation result for the review changes. CI's **tank** job is the full-suite test of record for the final pushed head; the older 735-pass local result above applies to the original implementation, not this final revision.

| File and line | Review change |
| --- | --- |
| `agents/rig/rigbox/quotes/service.py:217` | A released confirmation lease can be retried immediately. |
| `agents/rig/rigbox/quotes/service.py:247` | Only `order_mismatch` and `order_rejected` require a person; other placement failures retain `store_confirmed` and clear the lease. Stable order numbers and supplier outbox safeguards remain. |
| `agents/rig/rigbox/retailer_api.py:55` | On a lost lease, re-read only the same tenant's quote and return its current state in the existing response shape. |
| `tank/access.py:945` | Signed-in Rig admin corridor accepts strict `quote_id`, requires the existing Confirm binding, and writes a zero-cost code ledger receipt after success. Tenant identity is supplied by the account, never the body. |
| `tank/command.py:44` | Register `rig.quote.confirm_payment` in Rig tools. |
| `tank/command.py:118` | Expose the tool to tenant admins/founder, excluding ordinary members. |
| `tank/command.py:1018` | Strict quote-ID-only argument model. |
| `tank/command.py:1262` | Existing action-card adapter; label is exactly the tool name. |
| `tank/command.py:1461` | Forward only `data: {quote_id}`; account headers supply tenant identity. |
| `tank/command.py:1655` | Use durable confirmed dispatch, as Trigger tools do. |
| `tests/test_rig_no_payments.py:34` | Placement retries before/after an insert; exactly one order/outbox message. |
| `tests/test_rig_no_payments.py:62` | Both permanent errors remain `needs_person`. |
| `tests/test_rig_no_payments.py:75` | HTTP lost-lease response and cross-tenant 404. New literal identities/contact values use `placeholder`. |
| `tests/test_rig_confirmation_command.py:20` | Ordinary-member refusal, admin/founder exposure, strict arguments. |
| `tests/test_rig_confirmation_command.py:40` | Pending card, Confirm gate, actual signed-in admin route, tenant 404, successful store confirmation and actual code-receipt SQL with zero cost. No model or external API calls. |
| `tests/test_rig_optional_blind_ship.py:186` | Renamed `test_blind_order_failure_needs_person` to `test_blind_transient_order_failure_releases_lease`: the double raises transient `order_unavailable`, so verify release then successful placement instead of person review. |

The earlier `test_blind_order_failure_refunds` → `test_blind_order_failure_needs_person` rename is historical; the final name is now `test_blind_transient_order_failure_releases_lease`. No supplier safety assertions were removed.

### Founder settings after merge — names only

* `RIG_LOCATE_ORDER_MODE`
* `RIG_RETAILER_KEY`
* `RIG_LOCATE_OUTBOX_DIR` for auto-order
* The store's `delivery.min_days` / `delivery.max_days` range through the existing retailer settings operation.

The founder supplies all setting values. This change adds no bank/card data and no new page or button. The existing `/chats` Confirm card is specifically authorized for `rig.quote.confirm_payment`. Rechecked `tank/main.py:_startup` at line 755: existing additive schema and administrative RLS rollout remain unchanged.

### Exact review validation commands and results

All commands below run from `/workspace/codex-rig-nopay`:

```sh
git status --short --branch
git diff --check
git add tank/command.py
git commit -m 'feat(rig): add admin-only quote confirmation tool with existing Confirm card'
git push origin codex/rig-no-payments
PYTHONPATH=agents/_chassis:agents/rig /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig_no_payments.py tests/test_rig_confirmation_command.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
PYTHONPATH=agents/_chassis:agents/rig /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig_no_payments.py tests/test_rig_confirmation_command.py tests/test_rig_optional_auto_order.py tests/test_rig_optional_blind_ship.py tests/test_rig_locate_checkout.py tests/test_command.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
/workspace/codex-tiger-t1/.venv/bin/python -m ruff check tests/test_rig_no_payments.py tests/test_rig_confirmation_command.py tests/test_rig_optional_blind_ship.py tank/command.py tank/access.py agents/rig/rigbox/quotes/service.py agents/rig/rigbox/retailer_api.py --select E9,F
```

The focused run passed **22 tests, 1 skipped, 3 warnings in 11.67s**. The broader run initially found the obsolete blind-shipping transient-failure expectation (**1 failed, 113 passed, 52 skipped**). After updating that expectation, the same broader command passed: **114 passed, 52 skipped, 14 warnings in 7.03s**. Skips require local Postgres fixtures; no local Postgres/full-suite result is claimed for this revision. Lint passed; `git diff --check` passed. Every completed test file was committed and pushed separately, in sequence.

Final integration commands (results and final head are recorded in the PR body):

```sh
git add docs/rig/optional-pay-on-accept-main-handoff.md
git commit -m 'docs(rig): record confirmation review proof and founder setting names'
git fetch origin && git merge origin/main
git diff --check
git push origin codex/rig-no-payments
git rev-parse HEAD
git status --short --branch
```

The GitHub PR body contains the removed/changed test inventory and final-head CI state. Founder-browser acceptance and screenshots remain outstanding; no acceptance is claimed from unit tests.
