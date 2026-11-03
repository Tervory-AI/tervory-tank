# Rig cart US — dependency stop, 3 November 2026

Incomplete; not ready for founder acceptance. Claude opens the PR. No merge or deployment was performed.

The existing cart work was preserved, main was merged, and the pending test change was committed and pushed as `d1b8bbd3`. That change uses `Service(store)` instead of a partial test double in `tests/test_rig_cart.py`.

## Exact missing dependency

The original brief requires: “Merge it cleanly when it lands, and reuse its ‘store confirms payment’ step rather than writing a second one.” The no-payments branch has not landed on main (`1ad2c794`). Its current head is `2d7de0464f13563fa41440bd4be6392830df3b8d` and defines `QuoteService.confirm_store_payment`. Neither that method nor a `store_confirms_payment` implementation exists in this branch's production service.

`agents/rig/rigbox/cart.py:179` refuses checkout without a callable `store_confirms_payment`; line 244 invokes that callback after verified platform confirmation. The tests substitute a callback. This does not prove real supplier fulfilment, so no such completion is claimed. A bridge to the shared confirmation method remains necessary after the dependency lands, with integration tests proving quantity, tenant scope, and exactly-once supplier orders. Copying a separate fulfilment implementation here would violate the reuse requirement; merging all no-payments changes here would change the ZA quote flow, which the cart brief excludes.

Remaining work includes the shared confirmation integration, complete official-source/line citations for platform fakes and credential mechanisms, evaluation of the four additional platforms, and a fresh full Rig test run with throwaway Postgres. WooCommerce real-store tax and `payment_url` amount remain founder acceptance checks. No UI was added; Figma remains Proposed.

## Commands and evidence from this resume

All commands ran in `/workspace/codex-rig-cart`.

```sh
git status --short && git log -1 --oneline
git fetch origin && git merge origin/main
git add tests/test_rig_cart.py
git commit -m 'tests(rig): use real service interface in cart tests'
git fetch origin && git merge origin/main
git push origin codex/rig-cart-us
git merge-base --is-ancestor 2d7de0464f13563fa41440bd4be6392830df3b8d origin/main
rg -n 'store_confirms_payment|confirm_store_payment' agents/rig/rigbox/quotes/service.py agents/rig/rigbox/service.py agents/rig/rigbox/cart.py
PYTHONPATH=agents/_chassis:agents/rig /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig_cart.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Main merged without conflicts (`fb80bd2b`); pending test commit pushed successfully (`d1b8bbd3`). The ancestry command returned exit 1, confirming the dependency is unmerged. The search found only the two cart callback references, at lines 179 and 244. Focused offline tests: **11 passed in 2.24s**. These are callback-contract tests, not proof of complete shared fulfilment. No fresh full-suite/Postgres result or founder screenshots are claimed in this resume.

This handoff was checked with `git diff --check`, committed, then pushed after `git fetch origin && git merge origin/main`. Final head is reported in the task.

## Wave 3 continuation — 3 November 2026

The historical callback dependency above is superseded. PR #613 merged as
`cf473a12f7ecd2c74100e4674e65bae8c37e31d4`. The single authorised main merge
is `aa930a8dd42b700be5c40c7df7a8e31a2bdbe051`; main is not merged again.

Paid carts now use `RigOrders.place_located_order` directly for Locate lines,
with `quote_id = cart:<checkout id>:<line id>` and the line quantity. Stock
requires no supplier placement; back-order status is recorded on its line.
The existing quote default remains quantity 1. A persisted whole-row CAS lease
claims `paid_pending -> placing -> placed`, expires after 15 minutes and releases
on transient errors. Only `order_mismatch` and `order_rejected` require a person.
Webhooks, shopper order read-back and the existing recovery sweep retry placement.
Stable order/PO identifiers and the shared exclusive supplier outbox prevent
additional durable orders or sends after an uncertain result or lease takeover.
The cart exposes only its existing public projections.

Tank accepts `commerce-connect`, `commerce-orders` and `store-delivery` through
its signed-in admin corridor. Ordinary members are refused before dispatch.
The account supplies the tenant. Connect strips credential data before forwarding
and seals it into `rig.vault` using its existing tenant/name associated data.
Store delivery saves integer `min_days`/`max_days`, 0–60, in commerce config.
Existing ship_days configs remain readable. Schema startup remains
`await store.apply_schema()` in `agents/rig/app.py`; the existing commerce DDL
has been moved above generated memory, without adding a column or table.

### Official sources for the platform fakes

These are protocol fakes, not evidence of founder real-store acceptance.

| Platform | Behaviour and official source | Credential used by this adapter |
| --- | --- | --- |
| Shopify | [draftOrderCreate](https://shopify.dev/docs/api/admin-graphql/latest/mutations/draftOrderCreate) accepts catalog variants and custom-priced lines; [DraftOrder.invoiceUrl](https://shopify.dev/docs/api/admin-graphql/latest/objects/draftorder#field-DraftOrder.fields.invoiceUrl) supplies the store checkout link; [draftOrderDelete](https://shopify.dev/docs/api/admin-graphql/latest/mutations/draftOrderDelete) removes the unpaid draft. | Admin API access token in `X-Shopify-Access-Token`, plus the app webhook signing secret. [Current own-organisation client credentials grant](https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/client-credentials-grant); [legacy admin-created apps](https://shopify.dev/docs/apps/build/authentication-authorization/legacy/admin-custom-apps) continue to work, but cannot be newly created. The adapter consumes a supplied token; no token provisioning or refresh is claimed. |
| WooCommerce | [REST orders and authentication](https://woocommerce.github.io/woocommerce-rest-api-docs/#orders) defines pending order creation, product/SKU line references, quantities and totals, read-back and cancellation by status; the [official controller reference](https://woocommerce.github.io/code-reference/files/woocommerce-includes-rest-api-controllers-version2-class-wc-rest-orders-v2-controller.html) defines `payment_url` and resolves SKU carrier lines; [webhook headers](https://developer.woocommerce.com/docs/apis/rest-api/v2/webhooks) define `X-WC-Webhook-Signature` as base64 HMAC-SHA256 over the payload. | Consumer key and consumer secret via HTTPS Basic authentication; a separately configured webhook secret. The hidden/private taxable carrier is reused by SKU, never exposed as a storefront sample item. |
| BigCommerce | [Create Cart Redirect URL](https://docs.bigcommerce.com/developer/api-reference/rest/admin/management/carts/redirects/create-cart-redirect-url) returns `checkout_url`; [Managing Carts](https://docs.bigcommerce.com/developer/docs/storefront/headless/cart-and-checkout/carts) covers Management API carts and custom items; [HTTPS webhooks](https://docs.bigcommerce.com/developer/docs/integrations/webhooks/https) documents Standard Webhooks signatures and timestamp verification. The callback hash alone is not authentication. | [API account access token](https://docs.bigcommerce.com/developer/docs/overview/api-fundamentals/api-accounts) in `X-Auth-Token`, with store hash; the app client secret is the webhook signing secret. Redirect hosts must be explicitly permitted for that store. |

### Additional platform assessment — no unsupported adapter enabled

| Platform | Evidence and remaining missing part of a safe equivalent flow |
| --- | --- |
| Wix | [Create Checkout](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/checkout/checkout/create-checkout) supports custom lines. [Payment requests](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/order-payment-requests/create-order-payment-request) return a payment URL but require a published Payment Request Page. [Cancel Order](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/orders/cancel-order) cancels an existing order, not a pre-order checkout. The alternative [manual Create Order](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/orders/create-order) requires line tax information and limits unpublished apps to five calls/hour/site. Missing in this integration: a verified pre-payment checkout invalidation path, or the tax inputs and published request page needed for the different manual-order flow. This is not a claim that Wix lacks those three primitives separately. No Wix adapter or fake has been added. |
| Squarespace | [Orders API](https://developers.squarespace.com/commerce-apis/orders) creates imported third-party orders and lists/retrieves/fulfils orders, with API key or OAuth bearer authentication. Missing verified public APIs for a hosted payment link to such an unpaid order and for cancelling it. No adapter added. |
| Adobe Commerce / Magento | [Cart custom prices](https://developer.adobe.com/commerce/webapi/rest/saas-integrations/cart-custom-price/) require admin/integration bearer authentication and a catalog SKU in Cloud Service. The [SaaS GraphQL schema](https://developer.adobe.com/commerce/webapi/includes/autogenerated/graphql-api-saas-mutations) includes `createPaymentLink`, and [order management](https://developer.adobe.com/commerce/webapi/rest/saas-integrations/order-management/) includes cancellation. The [PaaS order flow](https://developer.adobe.com/commerce/webapi/rest/tutorials/orders/order-create-order/) instead submits billing/payment information. Missing verification that a single supported Magento deployment exposes all three in the same flow, including hosted link invalidation before payment and custom non-catalog lines. Cloud Service capabilities are not assumed for arbitrary Magento stores. No adapter added. |
| Ecwid | [Create order](https://docs.ecwid.com/api-reference/rest-api/orders/create-order) permits item prices; [Update order](https://docs.ecwid.com/api-reference/rest-api/orders/update-order) supports `CANCELLED`. Both use an app bearer token with order scopes. [Get order](https://docs.ecwid.com/api-reference/rest-api/orders/get-order) and Create do not document a hosted pay-existing-order URL. `paymentUrl` in the [payment app guide](https://docs.ecwid.com/guides/payments/process-online-payment-requests/step-1.-decode-and-parse-payment-request-from-ecwid) is the payment provider callback endpoint, which Rig must not become. Missing verified store-owned payment link for the newly created custom-priced order. No adapter added. |

### Validation so far

All commands run in `/workspace/codex-rig-cart`, offline with fake platform APIs.
The new local disposable Postgres container uses trust authentication on loopback,
not production data or credentials.

```sh
PYTHONPATH=agents/_chassis:agents/rig /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig_cart.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
PYTHONPATH=tank:agents/_chassis:agents/rig /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig_cart_admin.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
PYTHONPATH=tank:agents/_chassis:agents/rig RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32870/postgres /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig_cart.py tests/test_rig_cart_admin.py tests/test_rig_cart_postgres.py tests/test_rig_no_payments.py tests/test_rig_optional_auto_order.py tests/test_rig_optional_blind_ship.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
TMPDIR=/workspace/codex-rig-cart PYTHONPATH=tank:agents/_chassis:agents/rig RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32870/postgres /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig_cart_postgres.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
git diff --check
```

Results respectively: 17 passed; 5 passed; 85 passed; 2 passed; whitespace clean.
The first cart run found two test-fixture mistakes (cost equal to shopper price,
and an uncreated outbox directory), fixed before the passing run. The initial
combined no-payment regression found forbidden internal-state vocabulary in the
external platform adapter; external states are now normalized and Woo additionally
requires processing/completed status. Existing quote tests were not edited.
An attempted full glob run exited 120 with no output. A separate `/tmp` write
failed with `Disk quota exceeded`; the exit-120 cause was not independently
proved. The per-file rerun uses ignored `.rig-validation/` as TMPDIR and records
each file independently. Its completed results are recorded below.

Figma access works in this continuation. Session
`8e34b1cc-82bb-45e9-849f-139d94ec5aea` read Approved frame `291:9` and its screenshot.
No UI or browser acceptance proof is claimed by these backend tests.

### Required stop at gate 2: approved credential controls and paid-order wording

Gate 2 says: “If a state needs text no frame has, stop and report it.” Welcome
rules 2 and 9 also prohibit adding missing fields or wording or working around
that absence. This stop follows those explicit instructions, not a request for
permission or for any credential value.

All 52 registered frames were read with `get_design_context`. The A08 and
A08-late frames were also read with `get_screenshot` at both widths. Figma is
accessible; access/export is not the blocker. No page, visible text or built
widget was changed. The upstream widget was cloned and checked out at the
existing pinned commit in ignored `.rig-validation/widget-source`, preserving
the reviewed patch. Gate 3 has not started because the brief requires stopping
at the missing-frame boundary.

Exact missing approved design content:

1. A07-shopify (`291:8097`, `291:8124`) contains Store address and Access token,
   but no control/label/instruction for the webhook signing credential. Shopify
   [documents](https://shopify.dev/docs/apps/build/webhooks/verify-deliveries)
   that HTTPS HMAC uses the app client secret, not the Admin API access token.
   A07-woo (`291:8151`, `291:8182`) contains Consumer key and Consumer secret,
   but no separately configured Woo webhook secret. A07-big (`291:8213`,
   `291:8240`) contains Store hash and Access token, but no app client secret
   for the documented Standard Webhooks verification. Gate 1's vault input and
   `Platform.verify` require `webhook_secret`. There is no approved field or
   existing provisioned-name-only path specified to supply it on first connect.
   No secret was generated, read, derived from an access token, or requested.
2. A08 (`291:8405`, `291:8464`) and A08-late (`321:6304`, `321:6343`) have a
   Needs a person row whose fixed third-line text is “Payment status could not
   be confirmed”. The gate-1 permanent-placement tests reach needs_person
   after a valid paid order is verified, when shared placement raises
   `order_mismatch` or `order_rejected`. Applying that fixed payment-status
   sentence to this state would be false. Missing: approved row wording for
   confirmed payment with order placement requiring a person. The register's
   data slots permit substituting order numbers/amounts, not this sentence.

These are design gaps, not evidence that verification should be weakened.
Founder browser screenshots, UI parity, widget vitest/build, Workspace build,
L1 migration/golden equivalence and gate-3 acceptance remain unperformed.
No open PR exists for `codex/rig-cart-us` according to the read-only GitHub
pulls query; Claude opens it. Final-head CI tank/workspace results are therefore
not available and no CI success is claimed.

### Changed files and entry lines relative to step-0 head

| File | Entry line | Change |
| --- | ---: | --- |
| `agents/rig/rigbox/cart.py` | 250 | Shared per-Locate placement, whole-cart lease, retries, back-order row state and quantity; callback removed; delivery-range compatibility. |
| `agents/rig/rigbox/cart_store.py` | 57 | Tenant-scoped compare-and-swap under the existing advisory/memory lock. |
| `agents/rig/rigbox/fulfilment.py` | 57, 101 | Optional keyword quantity, default 1; validated quantity used in PO. |
| `agents/rig/rigbox/cart_api.py` | 79 | Shared admin dispatch and integer store-delivery validation. |
| `agents/rig/rigbox/retailer_api.py` | 18, 46 | Three commerce operations in the private retailer corridor. |
| `agents/rig/rigbox/commerce.py` | 214, 250 | Normalize external states; require paid Woo processing/completed status. |
| `agents/rig/schema.sql` | 545 | Existing commerce DDL moved above generated memory; no new DDL. |
| `tank/access.py` | 939, 961 | Explicit admin/founder requirement; account tenant; credentials sealed in existing vault and not forwarded. |
| `workspace/app/rig/admin/api/route.ts` | 5 | Three operation names; no page edits. |
| `workspace/app/rig/admin/types.ts` | 13 | Corresponding operation types. |
| `tests/test_rig_cart.py` | 346 | Real placement tests, mixed cart, quantities, concurrent webhooks/read-back, post-insert retry, permanent errors, auto-order and lease takeover. |
| `tests/test_rig_cart_admin.py` | 20 | Ordinary-member refusal for all three operations; sealed credential/tenant/response/log and delivery-range checks. |
| `tests/test_rig_cart_postgres.py` | 72 | Real Postgres CAS/placement retry, durable quantities and quote default. |
| `docs/rig/rig-cart-us-handoff.md` | 35 | Sources, commands, proof and this explicit missing-frame stop. |

Additional final checks:

```sh
/workspace/codex-tiger-t1/.venv/bin/python -m ruff check agents/rig/rigbox/cart.py agents/rig/rigbox/cart_store.py agents/rig/rigbox/cart_api.py agents/rig/rigbox/retailer_api.py agents/rig/rigbox/fulfilment.py agents/rig/rigbox/commerce.py tank/access.py tests/test_rig_cart.py tests/test_rig_cart_admin.py tests/test_rig_cart_postgres.py --select E9,F
TMPDIR=/workspace/codex-rig-cart/.rig-validation PYTHONPATH=tank:agents/_chassis:agents/rig /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_secrets.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
git diff --check
```

Ruff: all checks passed. Secrets tests: 2 passed. Whitespace: passed.


### Completed backend regression evidence

The already-started per-file pass completed after the required UI stop was
identified. All **67** `tests/test_rig*.py` files exited 0: **766 passed,
19 skipped**, with fake platform APIs and disposable local Postgres.
`tests/rig_cart_gate1/verification.txt:1` records the exact per-file commands,
exit codes and captured pytest summaries. The skips are reported, not treated
as passed container/runtime checks. CI remains the full-suite test of record;
there is no final-head tank/workspace CI result without the PR Claude opens.

Runner command:

```sh
TMPDIR=/workspace/codex-rig-cart/.rig-validation PYTHONPATH=tank:agents/_chassis:agents/rig RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32870/postgres /workspace/codex-tiger-t1/.venv/bin/python .rig-validation/run_rig.py
```

The runner sorts `glob.glob('tests/test_rig*.py')`, runs each pytest command
shown in the committed verification file in a separate subprocess with a
300-second limit, captures its output/exit code, and writes an ignored local
results JSON. It does not change source, credentials, data or test expectations.
The tested runtime/test tree is `f08033f6`; later commits contain handoff or
verification evidence and a whitespace-only schema EOF cleanup. No SQL token or
runtime behavior changed after the regression run. Every completed source/test file was committed and
pushed individually to `codex/rig-cart-us`. No PR was opened, labelled or merged,
no main push or additional main merge occurred, and no deployment was attempted.

Additional changed evidence file: `tests/rig_cart_gate1/verification.txt:1`.
The exact missing approved controls/wording remain those listed above. Gate 2
implementation and gate 3 are unstarted; no founder-browser completion is claimed.


Final cleanup commands:

```sh
git diff --check aa930a8d HEAD
git status --short
git rev-parse HEAD
docker rm -fv codex-rig-cart-wave3-placeholder-pg
```

The first full-range whitespace check found a trailing blank line introduced by
the schema-block move; it was removed and the full-range check then passed.
The disposable test container was removed. The original checkout and ignored
validation/source evidence remain preserved. The working tree is clean after
pushing the evidence commit; the new head is reported in the chat.

## Waiting for Figma

Founder direction after the gate-2 stop authorises proceeding with these gaps:

- Shopify A07: webhook-signing app client secret field, label and instructions.
- WooCommerce A07: separately configured webhook-signing secret field, label and instructions.
- BigCommerce A07: webhook-signing app client secret field, label and instructions.
- A08/A08-late: wording for a placement failure after confirmed payment. Until approved, show the existing status pill and omit the untrue payment-status sentence for that state.

The A07 forms keep exactly the approved visible fields. The backend accepts a
future `credential.webhook_secret` through the existing sealed vault path and
preserves an already saved value when the approved form omits it. An absent
signing value fails webhook verification closed; it is never substituted with
an access token, generated, returned or logged. These gaps no longer block gates
2 or 3 under the founder's explicit instruction. Main is not merged again.
