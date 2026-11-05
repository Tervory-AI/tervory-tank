# Rig founder acceptance sheet

The host split from merged PR #653 is included. Apply the register's shared-host domain cutover before founder browser testing. Use disposable acceptance tenants, synthetic
contact details and test stores only. Each row has exactly one executable test
named `test_RIG_NN` in `tests/acceptance/test_rig.py`; the final column identifies
the production browser/handler contract that test executes. An acknowledgement
is transport acceptance/storage, not proof that the store has invoiced anyone.

## Settings and fixture preparation

The setting names are from [FOUNDER-SETTINGS](../ops/FOUNDER-SETTINGS.md), including the room settings added by this change.
`none` means no **additional** entry from that register. It does not mean an
unauthenticated store or an unconfigured production deployment. Rig room setting names and their service boundaries are listed in the register. Keep `HF_JOBS_TOKEN` and `HF_JOBS_NAMESPACE` off;
no paid model, supplier, GPU, store or SMTP service is contacted by the proofs.

The following are test profiles, not values to apply to a real store. Create or
reset the relevant disposable tenant before **each** row. Do not expect fixture
amounts or counts in Custom Nation's real catalogue. Prepare the profiles through
the existing catalogue import/settings paths; do not run test seeding against a
production database. Synthetic supplier names stay private throughout.

- **Core:** `tests/fixtures/rig_quote_sample.py::seed`: Core One/Two/Three at
  ZAR 100/150/200; approved Part Alpha/Beta 20/30, adapters and support; the
  suggested Unapproved Part stays unapproved. Use the sample template labels
  and origin-bound publishable key on `/widget/test`. Browser proofs use the
  shipped UMD and these exact records, with Custom Nation styling over neutral
  data. Real go-live uses the founder's issued `RIG_WIDGET_PUBLISHABLE_KEY`.
- **Feed:** `tests/fixtures/rig_feed_formats/`; initial freight 1, duty 10%,
  gross margin 20%, direct FX USD→ZAR 18.50, EUR→ZAR 20, NZD→ZAR 11. Start
  with no imported products. Ordinary store admin and founder are different
  actors. Sample imports need no supplier credentials. Confirm mappings before
  import through the authenticated administration route.
- **US:** `tests/test_rig_cart.py::setup`: dedicated US cart tenant, Stock item
  USD 10, Located item displayed USD 30 but live-priced USD 20, Back order item
  USD 40; private source, quantity 5, stock delivery 2 days, located delivery
  9 days/ETA 2026-11-12. Use platform dev-store/test mode and sealed commerce
  credentials as in [the dev-store guide](../ops/RIG-US-CART-DEV-STORES.md).
  Webhook signing values are provisioned through the existing sealed vault path;
  the approved form still lacks those fields. Do not put secret values in this
  sheet or introduce card handling. Offline proofs use the platform API fake.
- **Locate:** `tests/test_rig_optional_auto_order.py::auto_shop` and the blind-ship
  fixtures. Enable tenant switches only on the test tenant. Use a disposable
  local sandbox outbox for optional supplier-order checks; no live sender is
  available. The test harness supplies existing signing/control prerequisites.
- **Notice/retention:** synthetic Core tenants; fixture clock/scheduler
  changes apply only to isolated test records. Retention/clock/cursor fault
  injection rows require the operator's test harness after deploy, not SQL or
  mass submissions against real shopper data.
- **Recall:** `tests/test_rig_recall.py::_service`, using its isolated lumaworks fixture tenant; never a real retailer.
- **L1:** `tests/fixtures/rig_catalogues/aurora/` plus the independent golden records
  loaded by `tests/test_rig_l1.py`. Use an isolated fixture tenant, never the
  real Custom Nation catalogue or real supplier prices.
- **3D:** `tests/fixtures/rig_three_d/sample.py`, local measured stand-in GLBs,
  approved fits and `rig_3d` only on its test tenant. No conversion/GPU runs.
  Admin/backend proof does not approve frames 06–07 or expose a shopper button.
- **Rooms:** two disposable stores A/B; the Core sample plus ROOM-A only / ROOM-B only (SKU ROOM-A / ROOM-B, USD 10), each in its own database. Use separate public/admin keys and the US fake-platform profile. The proof uses real Command turn/Confirm HTTP handlers, signed lifecycle HTTP against fake Coolify, actual PostgreSQL, cart/quote handlers and the real bucket signer against a fake bucket. It does not contact real stores or deploy applications.
- **Plugins:** a separate fixture tenant and vault. The off-state row needs no
  activation. Enabled-vault rows require an existing authorized test-vault grant;
  they do not imply that the production Rig vault is enabled.

For every Feed import row, use **Feeds → Source** (the named provider or
**Any catalogue**) → **Catalogue file** → select the named fixture →
**Suggest field mapping** → review the dropdowns → check **I checked this mapping
and the feed's currency, country and price type.** → **Publish catalogue**.
Connection rows choose the read-only feed mode and finish with **Connect feed**;
**Refresh now** is on the saved feed. A repeat import uses the same declarations
and server-confirmed mapping. Key setup uses **Quote delivery email → Save
delivery settings**, then **Website origin → Create embed key**.

For a page row, follow the exact actions below. API rows use the indicated URL
and the authenticated request emitted by the corresponding page (Network →
select that request → replay it with the stated fixture input). Keep keys and
raw credentials out of evidence. Replace `{reference}` and `{tenant_id}` only
with the reference/tenant produced for that row, never another store's value.
For `/chats`, use the administrator account and the quoted tool confirmation;
the offline contract proves the tool/card/handler, not live-model interpretation.

The browser proofs execute real clicks. Other rows exercise the existing HTTP,
server-action or business-handler path behind the named page, with actor/transport
boundaries replaced by fixtures. The last column makes the proof inspectable;
these contracts do not claim pixel acceptance, real email receipt, a real store
payment, DNS/TLS cutover or external-service readiness.

## Founder rows

| ID | Where (exact URL) | What to do | What to see | Setting it needs | Offline proof |
| --- | --- | --- | --- | --- | --- |
| RIG-01 | https://rig.tervory.com/widget/test | Core profile: type Core; click Search. | Exactly three cards: Core One, Core Two, Core Three. | RIG_WIDGET_PUBLISHABLE_KEY | _search_browser |
| RIG-02 | https://rig.tervory.com/widget/test | Core: search Core; on Core One click Complete my setup. | Three setups: A simple setup, Everyday versatility, More flexibility; Most chosen badge; first total R 120; no Unapproved Part. | RIG_WIDGET_PUBLISHABLE_KEY | _setups_browser |
| RIG-03 | https://rig.tervory.com/widget/test | Core: open Core One setups; first setup → Swap ⇄ → Part Beta. | First setup total is R 130. | RIG_WIDGET_PUBLISHABLE_KEY | _swap_browser |
| RIG-04 | https://rig.tervory.com/widget/test | Core: open Core One setups → Explore → + 1 more fitted adapters. | Core One heading; 2 parts; seven expanded part chips. | RIG_WIDGET_PUBLISHABLE_KEY | _explore_browser |
| RIG-05 | https://rig.tervory.com/widget/test | Core: Explore Core One; enter What fits this product? in Ask; press Enter with the model path unavailable. | Answer contains I don't know; no invented fit or price. | RIG_WIDGET_PUBLISHABLE_KEY | _ask_browser |
| RIG-06 | https://rig.tervory.com/widget/test | Core: search zzzzzzzzzzzzzz; enter https://example.com/item and Sample Shopper; click Request a quote with email/phone empty. | Enter your email address. and Enter your phone number. | RIG_WIDGET_PUBLISHABLE_KEY | _missing_browser |
| RIG-07 | https://rig.tervory.com/widget/test | Core: search zzzzzzzzzzzzzz; link https://example.com/item; Sample Shopper; sample@example.com; +1 202-555-0123; click Request a quote. | Request received. Reference followed by a generated reference; submit button disabled. | RIG_WIDGET_PUBLISHABLE_KEY | _link_browser |
| RIG-08 | https://rig.tervory.com/widget/test | Core: Explore Core One → Request a quote for this setup →; Sample Shopper / sample@example.com → Send request. | Request received. Reference followed by a generated reference. | RIG_WIDGET_PUBLISHABLE_KEY | _quote_browser |
| RIG-09 | https://rig.tervory.com/widget/test | Core: type successive characters before the debounce settles; wait, then inspect the administrator search count. | Only the settled search is counted once. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_quotes_browser.test_typeahead_only_counts_the_settled_search |
| RIG-10 | https://rig.tervory.com/rig/admin | Feed profile: import shopify.json as Shopify, USD; upload the same file twice. | First receipt: added 2, updated 0, rejected 0; second: added 0, updated 2. Two receipts. | none | test_rig_feeds_retailer.test_sample_imports_receipts_and_repeatability |
| RIG-11 | https://rig.tervory.com/rig/admin | Feed: import woocommerce.json as WooCommerce, USD; upload the same file twice. | First: added 1, updated 0, rejected 0; second: added 0, updated 1. | none | test_rig_feeds_retailer.test_sample_imports_receipts_and_repeatability |
| RIG-12 | https://rig.tervory.com/rig/admin | Feed: import google.xml as Google Merchant, USD; upload twice. | First: added 1, updated 0, rejected 0; second: added 0, updated 1. | none | test_rig_feeds_retailer.test_sample_imports_receipts_and_repeatability |
| RIG-13 | https://rig.tervory.com/rig/admin | Feed: Any catalogue → us-distributor.csv; currency USD, country US, price type cost; review suggested mapping; import. Records path: automatic. | US-LAMP has indicative selling price ZAR 534.19; mapping preview contains column names, not product values. | none | test_rig_feeds_catalogues.test_every_required_sample_is_mapped_receipted_and_priced |
| RIG-14 | https://rig.tervory.com/rig/admin | Feed: Any catalogue → eu-distributor.xml; currency EUR, country DE, price type cost; review suggested mapping; import. Records path: automatic. | EU-STAND has indicative selling price ZAR 440.00; mapping preview contains column names, not product values. | none | test_rig_feeds_catalogues.test_every_required_sample_is_mapped_receipted_and_priced |
| RIG-15 | https://rig.tervory.com/rig/admin | Feed: Any catalogue → nz-distributor.json; currency NZD, country NZ, price type cost; review suggested mapping; import. Records path: catalogue.products. | NZ-SHADE has indicative selling price ZAR 196.63; mapping preview contains column names, not product values. | none | test_rig_feeds_catalogues.test_every_required_sample_is_mapped_receipted_and_priced |
| RIG-16 | https://rig.tervory.com/rig/admin | Feed: Any catalogue → distributor.xlsx; currency USD, country US, price type cost; review suggested mapping; import. Records path: automatic. | XLSX-CHAIR has indicative selling price ZAR 788.56; mapping preview contains column names, not product values. | none | test_rig_feeds_catalogues.test_every_required_sample_is_mapped_receipted_and_priced |
| RIG-17 | https://rig.tervory.com/rig/admin | Feed: Any catalogue → store-catalogue.csv; currency ZAR, country ZA, price type selling; review suggested mapping; import. Records path: automatic. | STORE-DESK has indicative selling price ZAR 799.95; mapping preview contains column names, not product values. | none | test_rig_feeds_catalogues.test_every_required_sample_is_mapped_receipted_and_priced |
| RIG-18 | https://rig.tervory.com/rig/admin | Feed: preview us-distributor.csv; review dropdowns; confirm once; import; try the same confirmation again. | One confirmation succeeds; reused/wrong/expired preview is rejected (422); import adds 1, next import updates 1. | none | test_rig_feeds_mapping.test_confirmation_is_bound_consumed_and_required_for_import |
| RIG-19 | https://rig.tervory.com/rig/admin | Feed: import a file with a valid first row and invalid later row. | Whole import rejected; no partial products; rejection receipt remains. | none | test_rig_feeds_retailer.test_late_bad_row_rolls_back_every_product_and_keeps_rejection_receipt |
| RIG-20 | https://rig.tervory.com/rig/admin | Feed: import SAMPLE-LAMP/SAMPLE-SHADE; approve their suggested fit; refresh; reject the fit; refresh again. | Approved fit remains approved after refresh; rejected fit does not reappear as a suggestion. | none | test_rig_feeds_retailer.test_supplier_evidence_is_reviewed_and_refresh_preserves_decisions |
| RIG-21 | https://rig.tervory.com/rig/admin | Feed: import SAMPLE-LAMP; search/open it and inspect administrator response bodies. | Indicative ZAR 534.19; no supplier_cost, freight, duty_percent, margin_percent, exchange_rates or private rate 18.50 in public/admin projections. | none | test_rig_feeds_retailer.test_private_inputs_never_appear_in_public_or_admin_responses |
| RIG-22 | https://rig.tervory.com/rig/admin | Feed: set freight/duty/margin to zero; as ordinary admin try USD rate 22, then save it as founder. | SAMPLE-LAMP reprices to ZAR 370; ordinary admin gets 403; founder rate reprices to ZAR 440. | none | test_rig_feeds_retailer.test_rule_reprices_and_exchange_rate_requires_founder |
| RIG-23 | https://rig.tervory.com/rig/admin | Feed: connect a paginated Shopify read-only feed; click Refresh now; inspect nightly refresh/history after advancing the test scheduler. | Confirmed mapping and encrypted credentials are reused; completed refresh has a receipt; failures do not replace the catalogue. | none | test_rig_feeds_retailer.test_access_connect_manual_refresh_nightly_and_receipts_on_postgres |
| RIG-24 | https://rig.tervory.com/rig/admin | Feed: select SAMPLE-LAMP → Delete selected → confirm Delete 1 product?; inspect the other test retailer. | deleted = 1; the other tenant retains its SAMPLE-LAMP; an ordinary member is refused (403). | none | test_rig_delete_products.test_tank_delete_route_founder_and_tenant_boundary |
| RIG-25 | https://rig.tervory.com/rig/admin | Core: save two different store names/emails; issue an embed key restricted to https://a.fixture.test. | Store B retains its own settings; issued snippet uses the hashed/integrity-protected bundle and the key is restricted to its owning store. | none | test_rig_store_job.test_store_settings_and_keys_are_bound_to_the_authenticated_tenant |
| RIG-26 | https://rig.tervory.com/rig/admin | Feed: save the lighting template with stand as its default role and create a no-result search in store A; open store B. | Store A has its lighting/stand default and missed search; store B has empty templates and missed searches. | none | test_rig_feeds_retailer.test_template_defaults_and_no_result_counts_are_tenant_scoped |
| RIG-27 | https://rig.tervory.com/v1/rig/admin/analytics | Core: search Core and a no-result term; record each settled search once; open one setup, commit one swap and send one quote. Read analytics with admin key. | counts = searches 2, setups_opened 1, swaps 1, quotes 1, no_results 1; shopper gets 403; other store counts are zero. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_quotes.test_http_flow_counts_and_admin_isolation |
| RIG-28 | https://rig.tervory.com/widget/test | Core: send a product quote with SMTP failing once; fix test SMTP and retry the saved request. | pending with email_unavailable becomes sent; exactly one saved quote, same reference and Message-ID, mail addressed to the store. | SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM | test_rig_quotes.test_store_email_delivery_keeps_pending_retry_and_reference |
| RIG-29 | https://rig.tervory.com/v1/rig/admin/quotes/{reference}/delivery | Core fault-injection profile: POST /v1/rig/admin/quotes/{reference}/retry with {} between failures; after six attempts repair SMTP, then POST /v1/rig/admin/quotes/{reference}/resume with {}. | After six attempts status needs_person; ordinary retry does not reset its budget; explicit resume permits delivery. | SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM | test_rig_quotes.test_delivery_backoff_stops_and_only_explicit_resume_reopens_budget |
| RIG-30 | https://rig.tervory.com/v1/rig/admin/quotes/attention | Core fault-injection profile: create 205 held requests; GET attention; POST /v1/rig/admin/quotes/held_000/resume; follow next_cursor until the end. | First page 100; exactly held_000 through held_204 across pages, no duplicates; other tenant sees only other_held. | none | test_rig_quotes.test_attention_pages_past_100_and_only_resumed_holds_count |
| RIG-31 | https://rig.tervory.com/widget/test | Core: exhaust one shopper browse allowance; use a second shopper; send a quote within its independent allowance. | First shopper receives 429 with Retry-After; another shopper still receives 200; browse and quote budgets stay separate. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_quotes_limits.test_http_separate_budgets_cors_and_spoofed_forwarding |
| RIG-32 | https://rig.tervory.com/rig/admin | Retention fixture: age only synthetic quote/contact rows beyond the configured retention window; run discovery; inspect a recent quote and another tenant. | Expired quote and handoff disappear together; recent data and anonymous counts remain; deletion is tenant-scoped. | none | test_rig_quotes_postgres.test_retention_purge_job_cascade_and_tenant_isolation |
| RIG-33 | https://rig.tervory.com/widget/test | Notice fixture: open quote; replace Offline policy one. with Offline policy two. before submission; acknowledge current notice and submit; repeat with Offline policy three. | Stale consent cannot submit; one stored quote records Offline policy two.; next records Offline policy three. with current version/time. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_quote_notice.test_shipped_notice_stale_recovery_and_real_receipts |
| RIG-34 | https://rig.tervory.com/v1/rig/locate | Supply profile: locate out-of-stock desk; repeat without key, then as the other store. | Own-store result status available_to_order and only status/eta/ship_days/price; unauthenticated 401; foreign store cannot see the offer. | none | test_rig_supply_locate.test_http_locate_and_admin_ingestion_boundaries |
| RIG-35 | https://rig.tervory.com/widget/test | Locate profile: accept a sourced quote before the store confirms payment; inspect quote email and order records. | Request is stored/handed off; no order, supplier PO, payment charge, card or refund is created by accepting the quote. | SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM | test_rig_no_payments.test_accept_without_order_configuration_stores_and_hands_off_only |
| RIG-36 | https://app.tervory.com/chats | Locate profile: after the store receives EFT, use the existing rig.quote.confirm_payment confirmation for the saved quote reference; repeat confirmation. Do not send bank/card fields. | Unauthenticated control call 401; extra bank_details 422; foreign quote 404; repeat confirmed request returns same result and one local order. | none | test_rig_no_payments.test_retailer_http_confirmation_requires_existing_control_auth_and_only_quote_id |
| RIG-37 | https://rig.tervory.com/widget/test | Core: open a setup with store delivery 2–3 days and one unavailable part; request its quote. | Every item has delivery metadata; stocked item min_days 2/max_days 3/back_order false; unavailable item back_order true. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_no_payments.test_every_setup_item_carries_delivery_metadata |
| RIG-38 | https://rig.tervory.com/widget/test | Recall profile: search the same term twice, then change the catalogue and search again. | Unchanged search is reused without ranking again; changed catalogue invalidates the saved result. | none | test_rig_recall.test_a_changed_catalogue_is_not_reused |
| RIG-39 | https://rig.tervory.com/v1/rig/search | L1 profile: run the independent 578-record search/detail/quote fixture suite, including category, relation, fit and stock queries. | Every independent golden result, detail and reservation result agrees; no live model or supplier call. | none | test_rig_l1.test_complete_search_detail_and_reservation_golden |
| RIG-40 | https://rig.tervory.com/widget/test | US profile: add stock, located and back-order lines, quantity 2 each; continue to WooCommerce checkout. | Store line totals 20.00, 40.00, 80.00; total USD 140.00; delivery 2 days / 9 days with ETA / back order; no supplier identity. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_cart.test_carrier_mixed_order_privacy_and_posted_prices |
| RIG-41 | https://rig.tervory.com/widget/test | US: change stock price from 10.00 to 11.00 before Continue; restore it; retry after an uncertain order-create response. | Changed price requires recheck; no stale checkout; retries keep one remote order and state create_unknown until resolved. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_cart.test_checkout_recheck_and_lost_create_never_duplicate |
| RIG-42 | https://rig.tervory.com/widget/test | US: continue a sourced cart to store checkout; leave unpaid for five minutes; then deliver a valid late paid callback twice. | At 299 seconds pending; at 300 expired; late_payment true after signed confirmation; exactly one supplier placement. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_cart.test_expiry_release_and_late_signed_payment_honoured_once |
| RIG-43 | https://rig.tervory.com/v1/rig/commerce/webhooks/{tenant_id} | US: deliver the same raw WooCommerce callback with a wrong signature, then its correct X-WC-Webhook-Signature. | Bad signature refused; correct raw-body HMAC accepted; modified body without re-signing refused. | none | test_rig_cart.test_official_raw_body_signatures_and_timestamp |
| RIG-44 | https://rig.tervory.com/widget/test | US: create a Shopify checkout with one native stock variant plus a sourced custom line. | Shopify draft checkout carries native variantId and projected custom line; no payment/card endpoint is called. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_cart.test_shopify_and_bigcommerce_create_native_and_custom_lines |
| RIG-45 | https://rig.tervory.com/widget/test | US: create a BigCommerce checkout with native and custom lines. | BigCommerce native/custom cart redirect is on the allowed store host; no payment/card endpoint is called. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_cart.test_shopify_and_bigcommerce_create_native_and_custom_lines |
| RIG-46 | https://rig.tervory.com/rig/admin?cart=connection | US: ordinary store member attempts shop connection, Orders and delivery operations. | Each unauthorized operation is refused before dispatch; administrator identity is server-owned. | none | test_rig_cart_admin.test_cart_admin_rejects_ordinary_member_before_dispatch |
| RIG-47 | https://rig.tervory.com/rig/admin?cart=orders | US: set store delivery range and open Orders as store A while submitting store B tenant IDs. | Only authenticated store A delivery and orders are returned; supplied foreign tenant never wins. | none | test_rig_cart_admin.test_delivery_and_orders_use_only_account_tenant |
| RIG-48 | https://rig.tervory.com/widget/test | US: deliver concurrent paid callbacks and poll the order while placement is underway. | Exactly one located order/PO; recorded quantity preserved; supplier identity remains private. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_cart.test_mixed_cart_concurrent_webhooks_and_readback_use_one_located_order |
| RIG-49 | https://rig.tervory.com/widget/test | US: open a cart, explicitly recheck and change quantities while concurrent updates run. | Preview does not silently commit refreshed price/stock; explicit changes are atomic and preserve one consistent cart. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_cart.test_cart_preview_recheck_and_quantity_changes_are_atomic |
| RIG-50 | https://rig.tervory.com/rig/admin/three-d | 3D profile: prepare the local stand-in model; preview as admin; omit attachment-point approval, then approve scale/appearance/attachment points. | Draft asset is 404 to shopper; incomplete review 422; full admin review 200; repeat approval 409; approved GLB begins glTF. | none | test_rig_3d_engine.test_draft_hidden_until_all_human_checks_and_idempotent_submission |
| RIG-51 | https://rig.tervory.com/v1/rig/3d/assembly | 3D: build centre from approved models/fits; change module to part-tall; revoke that fit and retry. | Three models; USD 150 indicative total; swap USD 155; revoked fit 422 and cannot be quoted. | none | test_rig_3d_engine.test_assembly_approved_mounts_swap_current_fit_and_single_total |
| RIG-52 | https://rig.tervory.com/v1/rig/3d/assembly | 3D: request an assembly with a missing approved model. | available false and no asset address; no partial misleading assembly. | none | test_rig_3d_engine.test_missing_model_falls_back_without_any_asset_address |
| RIG-53 | https://rig.tervory.com/v1/rig/3d/capabilities | 3D: internally grant rig_3d to one test store; approve models; revoke and restore that grant. | Grant is tenant-scoped; revoked old asset/assembly 403; restore retains approved revision, reviewer and timestamp; photo_sources scan only. | none | test_rig_3d_engine.test_wave4_room_entitlement_grant_review_revoke_and_restore |
| RIG-54 | https://rig.tervory.com/3d/ | 3D: open a configured kiosk; request a quote; use the administrator reset for that kiosk. | Reset increments revision to 1 for the owning store; quote is stored; shopper cannot reset (403). | none | test_rig_3d_engine.test_remote_reset_is_tenant_scoped_and_quote_is_stored |
| RIG-55 | https://rig.tervory.com/rig/admin/three-d | 3D: with few-photo preparation disabled, attempt source ai with one photo. | Capabilities list scan only; ai preparation is refused before storage or GPU work. Leave HF_JOBS_TOKEN/HF_JOBS_NAMESPACE unused. | none | test_rig_3d_engine.test_few_photo_preparation_is_hidden_and_rejected_until_enabled |
| RIG-56 | https://rig.tervory.com/widget/test | Core mobile: at 390px complete search → setup → swap → missing-product form → Explore → Ask → quote. | No horizontal overflow; three setups; swap R 130; field errors work; Ask says I don't know; quote acknowledged. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_quotes_browser.test_built_widget_live_api_journey |
| RIG-57 | https://rig.tervory.com/rig/admin?cart=connection | US: connect shopify using test credentials; reconnect after an operator has provisioned webhook_secret in the sealed vault. | Credentials stay sealed and are not forwarded/returned/logged; reconnect preserves the existing webhook secret. | none | test_rig_cart_admin.test_cart_admin_credentials_sealed_not_forwarded_returned_or_logged |
| RIG-58 | https://rig.tervory.com/rig/admin?cart=connection | US: connect woocommerce using test credentials; reconnect after an operator has provisioned webhook_secret in the sealed vault. | Credentials stay sealed and are not forwarded/returned/logged; reconnect preserves the existing webhook secret. | none | test_rig_cart_admin.test_cart_admin_credentials_sealed_not_forwarded_returned_or_logged |
| RIG-59 | https://rig.tervory.com/rig/admin?cart=connection | US: connect bigcommerce using test credentials; reconnect after an operator has provisioned webhook_secret in the sealed vault. | Credentials stay sealed and are not forwarded/returned/logged; reconnect preserves the existing webhook secret. | none | test_rig_cart_admin.test_cart_admin_credentials_sealed_not_forwarded_returned_or_logged |
| RIG-60 | https://rig.tervory.com/v1/rig/commerce/webhooks/{tenant_id} | US: send a signed shopify raw callback, then alter its body/signature (and BigCommerce timestamp). | Valid signature accepted; altered body/signature refused; BigCommerce old timestamp refused. | none | test_rig_cart.test_official_raw_body_signatures_and_timestamp |
| RIG-61 | https://rig.tervory.com/v1/rig/commerce/webhooks/{tenant_id} | US: send a signed bigcommerce raw callback, then alter its body/signature (and BigCommerce timestamp). | Valid signature accepted; altered body/signature refused; BigCommerce old timestamp refused. | none | test_rig_cart.test_official_raw_body_signatures_and_timestamp |
| RIG-62 | https://rig.tervory.com/widget/test | Locate profile: enable blind shipping only on the test store; accept a quoted item with the test shopper delivery address and a neutral-slip source. | Local order/PO retains the delivery address and neutral-slip instruction; no supplier identity reaches the shopper. | SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM | test_rig_optional_blind_ship.test_blind_accept_records_a_rig_order_and_a_neutral_slip_po_to_the_shopper |
| RIG-63 | https://rig.tervory.com/widget/test | Locate sandbox: after store payment confirmation, enable auto-order and use the local test outbox; repeat the same confirmation. | One local supplier-order email file, one order and one PO; no live supplier email, card or refund. | none | test_rig_no_payments.test_confirmation_is_concurrent_idempotent_and_tenant_scoped |
| RIG-64 | https://app.tervory.com/chats | As test-store administrator ask: Confirm the store has received payment for quote <the saved reference>. Review the rig.quote.confirm_payment card, confirm it once, then retry. | Confirmation binds the authenticated actor and saved quote; a zero-cost code receipt records the result; one local order. | none | test_rig_confirmation_command.test_confirm_card_binds_actor_quote_and_writes_zero_code_receipt |
| RIG-65 | https://rig.tervory.com/widget/test | Core: submit a setup quote with the first SMTP send failing; retry after repairing the test transport. | pending → sent; same store recipient, quote reference and Message-ID; exactly one saved quote. | SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM | test_rig_quotes.test_store_email_delivery_keeps_pending_retry_and_reference |
| RIG-66 | https://rig.tervory.com/widget/test | Core: submit a link quote with the first SMTP send failing; retry after repairing the test transport. | pending → sent; same store recipient, quote reference and Message-ID; exactly one saved quote. | SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM | test_rig_quotes.test_store_email_delivery_keeps_pending_retry_and_reference |
| RIG-67 | https://app.tervory.com/rig | Open Plugins before the Rig vault has been enabled. | This vault is off. Turn it on in Tank.; secret/file/link/connection lists are empty. | none | _workspace_contract |
| RIG-68 | https://app.tervory.com/rig | On an enabled test vault, open Plugins → API keys; save fixture-key with a synthetic value; reload. | Only fixture-key metadata and •••••••• return; raw secret never reaches the panel. | none | _workspace_contract |
| RIG-69 | https://app.tervory.com/rig | On enabled test Plugins, upload fixture.csv; add a weekly source link and an authenticated fixture connection; remove all three. | Requests remain scoped to rig.vault and the authenticated tenant; metadata lists fixture.csv; remove actions use the same owning tenant. | none | _workspace_contract |
| RIG-70 | https://rig.tervory.com/v1/rig/compare | Core: POST {"product_ids":["CORE-1","CORE-2"]} using the issued store key and allowed Origin. | Two selected lines CORE-1/CORE-2 with indicative ZAR 100/150; market is null when no observation exists. | none | _compare_http |
| RIG-71 | https://rig.tervory.com/widget/test | Recall profile: search optic for lumaworks twice against unchanged fixture data. | Same result IDs; second search reused true, cost 0; no extra ranking or model call. | none | test_rig_recall.test_the_same_search_is_reused_for_nothing |
| RIG-72 | https://rig.tervory.com/v1/rig/admin/analytics | Supply: record a synthetic USD 53.21 sale receipt; replay it; record an external adjustment -3.21 and EUR 7. Read kept revenue. | Before receipts revenue is null; after, USD 50.00 and EUR 7 remain separate; receipt_count 3; source store_reported_sale_receipts. Rig initiates no refund. | none | test_rig_supply_locate.test_revenue_requires_receipt_retries_dont_inflate_and_currencies_separate |
| RIG-73 | https://rig.tervory.com/rig/admin/three-d | 3D: stage overlapping photos whose combined streamed data exceeds the job limit; try 71 scan photos. | 1 GB job limit refuses before output upload, scratch is removed; 71 photos rejected. No GPU conversion. | none | test_rig_3d_uploads.test_whole_job_limit_is_checked_before_any_write_and_scratch_is_removed |
| RIG-74 | https://rig.tervory.com/v5 | Use a published key owned by an empty second store; open the catalogue page while another store has products. | window.RIG_KEY is empty for the empty store; no other store key, Archon or bundled demo catalogue is borrowed. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_no_live_demo.test_configured_page_requires_its_own_published_products |
| RIG-75 | https://rig.tervory.com/widget/test | US: after a signed payment callback, simulate transient order_unavailable during placement, then repair it and replay the callback. | paid_pending releases its lease; repair produces placed with one order, not a second payment. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_cart.test_placement_failure_releases_only_own_lease_and_retries |
| RIG-76 | https://rig.tervory.com/widget/test | US: after signed payment, simulate permanent order_mismatch; replay the callback. | needs_person remains; no duplicate order or second placement attempt. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_cart.test_placement_failure_releases_only_own_lease_and_retries |
| RIG-77 | https://rig.tervory.com/rig/admin/three-d | 3D: request a quote with a valid phone only; then try missing/invalid contact. | Valid phone-only quote is stored for its tenant; missing or invalid contact rejected with 422. | none | test_rig_3d_engine.test_quote_accepts_phone_only_and_rejects_missing_or_invalid_contacts |
| RIG-78 | https://rig.tervory.com/rig/admin | Feed: import the five catalogue samples; set EU rule freight 2/duty 5/margin 0, then DE freight 4/duty 0/margin 0, then supplier freight 3/duty 0/margin 0; change the default rule. | EU-STAND reprices ZAR 357 → 380 → 360 and stays 360 after the default changes; selling-price STORE-DESK stays 799.95. | none | test_rig_feeds_catalogues.test_regional_and_supplier_overrides_and_selling_price_survive_repricing |
| RIG-79 | https://rig.tervory.com/v1/rig/search | Second-store profile: search lamps, shades, parts, shade to go with the lamp, then 2 pack lamps. | Focus SECOND-LAMP-01; shade/parts IDs SECOND-SHADE-01; message We list lamps separately.; no first-store vocabulary is pasted. | none | test_rig_l1.test_second_store_owns_categories_parts_and_sentences_without_fallback |
| RIG-80 | https://rig.tervory.com/widget/test | US: leave a second tenant in default quote mode; attempt cart add there; on the cart tenant send a signed paid callback whose read-back total is 1.00 instead of the saved total. | Default quote tenant returns cart_disabled; changed paid total raises order_mismatch; no supplier placement. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_cart.test_quote_default_tenant_isolation_and_total_verification |
| RIG-81 | https://rig.tervory.com/ | Sign in; open /?q=part and /admin?cart=orders. | Workspace rewrites to /rig?q=part and /rig/admin?cart=orders; signed-out visitors return to the same Rig URL. | none | test_rig_product_host.test_workspace_middleware_preserves_rig_authentication_and_query_strings |
| RIG-82 | https://rig.tervory.com/widget/test | Load an existing issued embed and replay its API, asset and signed callback URLs through the shared host. | Every issued widget/store URL reaches agent-rig unchanged; root and admin reach Workspace. | none | test_rig_product_host.test_real_traefik_keeps_embed_store_urls_and_sends_app_paths_to_workspace |
| RIG-83 | https://app.tervory.com/chats | In disposable store A enter rig.store.onboard; review and confirm its card twice. Switch to store B and repeat; enter rig.rooms.list and confirm. | Two distinct Coolify applications on the configured server; created, cost_usd 0; repeated Confirm creates no duplicate. Store B lists only its own room. Creation stays undeployed until its named settings are filled. | RIG_COOLIFY_URL, RIG_COOLIFY_TOKEN, RIG_COOLIFY_PROJECT_UUID, RIG_COOLIFY_SERVER_UUID, RIG_COOLIFY_ENVIRONMENT, RIG_COOLIFY_GITHUB_APP_UUID, RIG_LIFECYCLE_KEY, RIG_ROOM_DB_PASSWORD | test_rig_rooms_acceptance.test_chats_two_store_rooms_keep_search_cart_quote_and_destroy_isolated |
| RIG-84 | https://rig.tervory.com/v1/rig/rooms/{tenant_id}/v1/rig/search | Rooms profile: search ROOM-A with A’s key. Try that key on B. Add ROOM-A quantity 1 to A; view B using the same cart session. Quote ROOM-A in A; request its delivery status with B’s admin key. | A returns ROOM-A only; foreign key 401; B cart lines is []; A quote delivery 200 and B delivery 404; no B platform call or quote. | RIG_WIDGET_PUBLISHABLE_KEY | test_rig_rooms_acceptance.test_chats_two_store_rooms_keep_search_cart_quote_and_destroy_isolated |
| RIG-85 | https://app.tervory.com/chats | Rooms profile: in A enter rig.store.destroy and confirm. Search A and B through their room API paths; inspect A’s private bucket manifest and its retained Coolify volumes. | A returns 503; B returns 200 with ROOM-B only. A’s database/data volumes and hashed bucket backup parts remain. Bucket failure prevents application deletion. | RIG_LIFECYCLE_KEY, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID_RIG, R2_SECRET_ACCESS_KEY_RIG | test_rig_rooms_acceptance.test_chats_two_store_rooms_keep_search_cart_quote_and_destroy_isolated |
| RIG-86 | https://app.tervory.com/chats | As ordinary member try rig.store.onboard. As a Rig administrator inspect/replay the tool validation with tenant_id naming B instead of using the current store. | Member cannot use the tool (403); extra tenant argument is rejected (422). No cross-store operation or paid adapter is available. | none | test_rig_rooms_acceptance.test_room_commands_require_admin_and_never_accept_foreign_tenant |
| RIG-87 | https://github.com/Tervory-AI/tervory-tank/blob/main/docs/ops/RIG-STORE-ROOMS.md#measure-rooms-locally | On the disposable Coolify test host run python3 tests/load/rig_rooms_load.py --rooms 2 --duration 60s after building the local image. Open its measurement.json. | rooms 2; two per_room entries; finite search_p95_ms and quote_p95_ms; sampled memory in bytes; failed_checks 0, http_failure_rate 0, capacity_claim null. All fixture containers are removed. | none | test_rig_rooms_acceptance.test_load_harness_records_p95_and_memory_and_cleans_only_its_fixtures |
| RIG-88 | https://rig.tervory.com/v1/rig/rooms/{tenant_id}/v1/rig/commerce/webhooks/{tenant_id} | Rooms protocol fixture: replay the signed WooCommerce body unchanged through A’s room prefix; try an internal/retailer path and a nested room path through that prefix. | Valid callback accepted true; body, signature and Origin are preserved; spoofed forwarding address is replaced by the resolved peer. Both forbidden paths return 404. | none | test_rig_rooms_acceptance.test_room_gateway_preserves_signed_callback_bytes_and_refuses_control_paths |

**Row count: 88.** No row is conditionally skipped by the acceptance harness.
The real database and browser prerequisites must be present for its complete run.

## Deployment preparation

Attach rig.tervory.com to the Workspace application as well as agent-rig, following
FOUNDER-SETTINGS section C.1 and PRODUCT-HOSTS. Rows RIG-81–82 prove the merged
middleware and real Traefik split offline, including issued embed URLs.
Frames 06–07 are still pending; GPU flags remain off. Odoo is retired. Custom
Nation stays quote → the store's own invoice → EFT. US stores go to their store
checkout. Rig never takes payment, holds a card or refunds.

## Run the offline proofs

Use the repository test runtime, Chromium and an explicitly disposable Postgres
16 through `RIG_TEST_DATABASE_URL` (the existing test-only variable). Then:

```sh
RIG_TRAEFIK_TEST_BINARY=/absolute/path/to/traefik python -m pytest -q tests/acceptance/test_rig.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

The tests use the same fixture implementations cited above; no live credentials
are needed. Every row runs independently. A parity assertion in every case
refuses a sheet whose row IDs differ from the executable registry. Validation: **80 passed, zero skipped, zero failures**, in 132.95 seconds,
using Chromium, disposable Postgres 16 and socket blocking. Combined collection
with the existing Rig tests: **876 tests**, no module/fixture conflicts. The
first 69-row pass and subsequent 77-row pass also passed; the final complete
80-row run is the acceptance result. Corrections were confined to the sheet/test
harness (fixture registration, a parameter-name collision and exact UI wording);
no production behavior changed. CI's exact Ruff command passed with
**All checks passed!**. The temporary database container was removed afterwards.

## Paid ladder approval

Use a disposable test tenant and the cloud-side authenticated Tank client; do not put service keys into a browser. Configure an existing paid model on `rig.ask` for this fixture. The screen switches await the frames listed in `docs/paid-steps/FRAMES.md`; the authenticated settings API is available now.

| Row | Where | What the founder does | Expected result | Setting it needs | Offline case |
| --- | --- | --- | --- | --- | --- |
| PAID-RIG | Tank `POST /v1/route`, task_type `rig.ask`; existing `/chats` confirmation card | Send a test request in Ask mode. Confirm its pending paid-step card, then repeat the same run. Set that exact step to Auto and start a new run. Enable Pause all paid work and start another run. | Ask returns 409 with `paid_step_approval_required` before dispatch. Approval resumes with HTTP 200 and receipt `paid_step_mode=approved`; repeating the run does not dispatch again. Auto returns 200 with `paid_step_mode=automatic`. Master pause returns 503 and sends no paid call. | `paid_step_settings.mode`; `paid_paused`; existing configured model and room credentials | `tests/acceptance/test_paid_steps.py`, `rig` |

refuses a sheet whose row IDs differ from the executable registry. The original
80-row baseline passed with disposable Postgres and Chromium. Gate 1 adds two
merged-host proofs: both passed, including the real local Traefik proxy.
Full current results are recorded with the gate validation, rather than implying
that an earlier baseline run validates new rows.

Room proof boundaries: the Coolify API and bucket are fixture HTTP transports;
store databases, Command turn/Confirm state, room routing, carts and quote delivery
are real handlers. The load row executes the shipped k6 scenarios with fixture
HTTP and measured-duration inputs, then the actual harness/report path with a
recording Docker transport. Those fixture numbers are not host measurements.
Use the local-container harness on the founder’s test host to measure capacity;
60–80 clients per KVM 8 remains an estimate, not a tested result.
