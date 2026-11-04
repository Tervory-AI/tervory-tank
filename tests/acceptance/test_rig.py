"""Founder acceptance: one executable fixture proof for each sheet row.

Browser rows drive the shipped UMD. Other rows reuse the existing production
handler/contract proofs rather than a second implementation of Rig behavior.
A row's fixture parameters are explicit; no live credentials or providers run.
"""
from __future__ import annotations

import importlib
import inspect
import os
import re
import sys
import subprocess
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from playwright.async_api import expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / 'agents/rig'))
import test_rig_quotes_browser as _widget_proofs  # noqa: E402
widget_server = _widget_proofs.widget_server
from test_rig_3d_engine import rig  # noqa: E402,F401
from test_rig_feeds_mapping import mapping_pool  # noqa: E402,F401

REPO = ROOT.parent
WIDGET = 'https://rig.tervory.com/widget/test'
ADMIN = 'https://rig.tervory.com/rig/admin'
API = 'https://rig.tervory.com/v1/rig'
SMTP = 'SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM'
KEY = 'RIG_WIDGET_PUBLISHABLE_KEY'


@pytest.fixture(autouse=True)
def _acceptance_runtime_required():
    # Acceptance must fail, rather than silently skip database-dependent rows.
    assert os.environ.get('RIG_TEST_DATABASE_URL') or os.environ.get('POOL_SCHEMA_DATABASE_URL'), (
        'Use an explicitly disposable Postgres through RIG_TEST_DATABASE_URL before acceptance.'
    )


@asynccontextmanager
async def browser(real_chromium, widget_server):
    page = await real_chromium.new_page(viewport={'width': 1440, 'height': 1000})
    await page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(widget_server + '/') else route.abort())
    try:
        await page.goto(widget_server + '/widget/test')
        await page.locator('tervory-rig').evaluate("el => el.setAttribute('theme', 'custom-nation')")
        await expect(page.get_by_role('searchbox')).to_be_visible()
        yield page
    finally:
        await page.close()


async def search(page, query='Core'):
    await page.get_by_role('searchbox').fill(query)
    await page.get_by_role('button', name='Search', exact=True).click()


async def setups(page):
    await search(page)
    await page.locator('.card').filter(has=page.get_by_role('heading', name='Core One', exact=True)).get_by_role('button', name='Complete my setup', exact=True).click()
    await expect(page.locator('.setup')).to_have_count(3)


async def explore(page):
    await setups(page)
    await page.get_by_role('button', name='Explore', exact=True).click()
    await expect(page.locator('.graph-canvas')).to_be_visible()


async def _search_browser(real_chromium, widget_server):
    async with browser(real_chromium, widget_server) as page:
        await search(page)
        await expect(page.locator('.card')).to_have_count(3)
        for name in ('Core One', 'Core Two', 'Core Three'):
            await expect(page.get_by_role('heading', name=name, exact=True)).to_be_visible()


async def _setups_browser(real_chromium, widget_server):
    async with browser(real_chromium, widget_server) as page:
        await setups(page)
        for text in ('A simple setup', 'Everyday versatility', 'More flexibility', 'Most chosen'):
            await expect(page.get_by_text(text, exact=True)).to_be_visible()
        await expect(page.get_by_text('R 120', exact=True)).to_be_visible()
        assert 'Unapproved Part' not in await page.locator('.shell').text_content()


async def _swap_browser(real_chromium, widget_server):
    async with browser(real_chromium, widget_server) as page:
        await setups(page)
        first = page.locator('.setup').first
        await first.get_by_role('button', name='Swap ⇄', exact=True).click()
        await first.get_by_role('button', name='Part Beta', exact=True).click()
        await expect(first.get_by_text('R 130', exact=True)).to_be_visible()


async def _explore_browser(real_chromium, widget_server):
    async with browser(real_chromium, widget_server) as page:
        await explore(page)
        await expect(page.get_by_role('heading', name='Core One', exact=True)).to_be_visible()
        await expect(page.get_by_role('button', name='2 parts', exact=True)).to_be_visible()
        await expect(page.get_by_role('button', name='+ 1 more fitted adapters', exact=True)).to_be_visible()
        await page.get_by_role('button', name='+ 1 more fitted adapters', exact=True).click()
        await expect(page.locator('.g-chip')).to_have_count(7)


async def _ask_browser(real_chromium, widget_server):
    async with browser(real_chromium, widget_server) as page:
        await explore(page)
        await page.locator('#ask-q').fill('What fits this product?')
        await page.locator('#ask-q').press('Enter')
        await expect(page.locator('.answer')).to_contain_text("I don't know")


async def _missing_browser(real_chromium, widget_server):
    async with browser(real_chromium, widget_server) as page:
        await search(page, 'zzzzzzzzzzzzzz')
        await page.locator('#link-url').fill('https://example.com/item')
        await page.locator('#link-name').fill('Sample Shopper')
        await page.get_by_role('button', name='Request a quote', exact=True).click()
        await expect(page.locator('#link-email-error')).to_have_text('Enter your email address.')
        await expect(page.locator('#link-phone-error')).to_have_text('Enter your phone number.')


async def _link_browser(real_chromium, widget_server):
    async with browser(real_chromium, widget_server) as page:
        await search(page, 'zzzzzzzzzzzzzz')
        for selector, value in [('#link-url', 'https://example.com/item'), ('#link-name', 'Sample Shopper'),
                                ('#link-email', 'sample@example.com'), ('#link-phone', '+1 202-555-0123')]:
            await page.locator(selector).fill(value)
        await page.get_by_role('button', name='Request a quote', exact=True).click()
        await expect(page.get_by_text('Request received. Reference', exact=False)).to_be_visible()
        await expect(page.get_by_role('button', name='Request a quote', exact=True)).to_be_disabled()


async def _quote_browser(real_chromium, widget_server):
    async with browser(real_chromium, widget_server) as page:
        await explore(page)
        await page.get_by_role('button', name='Request a quote for this setup →', exact=True).click()
        await page.locator('#quote-name').fill('Sample Shopper')
        await page.locator('#quote-email').fill('sample@example.com')
        await page.get_by_role('button', name='Send request', exact=True).click()
        await expect(page.get_by_text('Request received. Reference', exact=False)).to_be_visible()


@dataclass(frozen=True)
class Row:
    id: str
    where: str
    action: str
    expected: str
    settings: str
    proof: str
    parameters: dict[str, Any] = field(default_factory=dict)


ROWS: list[Row] = []


def row(where, action, expected_text, proof, settings='none', **parameters):
    ROWS.append(Row(f'RIG-{len(ROWS) + 1:02}', where, action, expected_text, settings, proof, parameters))


# Shopper: actual browser clicks against the shipped widget and fixture API.
row(WIDGET, 'Core profile: type Core; click Search.', 'Exactly three cards: Core One, Core Two, Core Three.', '_search_browser', KEY)
row(WIDGET, 'Core: search Core; on Core One click Complete my setup.', 'Three setups: A simple setup, Everyday versatility, More flexibility; Most chosen badge; first total R 120; no Unapproved Part.', '_setups_browser', KEY)
row(WIDGET, 'Core: open Core One setups; first setup → Swap ⇄ → Part Beta.', 'First setup total is R 130.', '_swap_browser', KEY)
row(WIDGET, 'Core: open Core One setups → Explore → + 1 more fitted adapters.', 'Core One heading; 2 parts; seven expanded part chips.', '_explore_browser', KEY)
row(WIDGET, 'Core: Explore Core One; enter What fits this product? in Ask; press Enter with the model path unavailable.', "Answer contains I don't know; no invented fit or price.", '_ask_browser', KEY)
row(WIDGET, 'Core: search zzzzzzzzzzzzzz; enter https://example.com/item and Sample Shopper; click Request a quote with email/phone empty.', 'Enter your email address. and Enter your phone number.', '_missing_browser', KEY)
row(WIDGET, 'Core: search zzzzzzzzzzzzzz; link https://example.com/item; Sample Shopper; sample@example.com; +1 202-555-0123; click Request a quote.', 'Request received. Reference followed by a generated reference; submit button disabled.', '_link_browser', KEY)
row(WIDGET, 'Core: Explore Core One → Request a quote for this setup →; Sample Shopper / sample@example.com → Send request.', 'Request received. Reference followed by a generated reference.', '_quote_browser', KEY)
row(WIDGET, 'Core: type successive characters before the debounce settles; wait, then inspect the administrator search count.', 'Only the settled search is counted once.', 'test_rig_quotes_browser.test_typeahead_only_counts_the_settled_search', KEY)

# Retailer import and catalogue administration; fixture contracts behind these pages.
row(ADMIN, 'Feed profile: import shopify.json as Shopify, USD; upload the same file twice.', 'First receipt: added 2, updated 0, rejected 0; second: added 0, updated 2. Two receipts.', 'test_rig_feeds_retailer.test_sample_imports_receipts_and_repeatability', provider='shopify', count=2)
row(ADMIN, 'Feed: import woocommerce.json as WooCommerce, USD; upload the same file twice.', 'First: added 1, updated 0, rejected 0; second: added 0, updated 1.', 'test_rig_feeds_retailer.test_sample_imports_receipts_and_repeatability', provider='woocommerce', count=1)
row(ADMIN, 'Feed: import google.xml as Google Merchant, USD; upload twice.', 'First: added 1, updated 0, rejected 0; second: added 0, updated 1.', 'test_rig_feeds_retailer.test_sample_imports_receipts_and_repeatability', provider='google', count=1)
for case in [
    ('us-distributor.csv', 'USD', 'US', 'cost', 'US-LAMP', '534.19', ''),
    ('eu-distributor.xml', 'EUR', 'DE', 'cost', 'EU-STAND', '440.00', ''),
    ('nz-distributor.json', 'NZD', 'NZ', 'cost', 'NZ-SHADE', '196.63', 'catalogue.products'),
    ('distributor.xlsx', 'USD', 'US', 'cost', 'XLSX-CHAIR', '788.56', ''),
    ('store-catalogue.csv', 'ZAR', 'ZA', 'selling', 'STORE-DESK', '799.95', ''),
]:
    row(ADMIN, f'Feed: Any catalogue → {case[0]}; currency {case[1]}, country {case[2]}, price type {case[3]}; review suggested mapping; import. Records path: {case[-1] or "automatic"}.', f'{case[4]} has indicative selling price ZAR {case[5]}; mapping preview contains column names, not product values.', 'test_rig_feeds_catalogues.test_every_required_sample_is_mapped_receipted_and_priced', case=case)
row(ADMIN, 'Feed: preview us-distributor.csv; review dropdowns; confirm once; import; try the same confirmation again.', 'One confirmation succeeds; reused/wrong/expired preview is rejected (422); import adds 1, next import updates 1.', 'test_rig_feeds_mapping.test_confirmation_is_bound_consumed_and_required_for_import')
row(ADMIN, 'Feed: import a file with a valid first row and invalid later row.', 'Whole import rejected; no partial products; rejection receipt remains.', 'test_rig_feeds_retailer.test_late_bad_row_rolls_back_every_product_and_keeps_rejection_receipt')
row(ADMIN, 'Feed: import SAMPLE-LAMP/SAMPLE-SHADE; approve their suggested fit; refresh; reject the fit; refresh again.', 'Approved fit remains approved after refresh; rejected fit does not reappear as a suggestion.', 'test_rig_feeds_retailer.test_supplier_evidence_is_reviewed_and_refresh_preserves_decisions')
row(ADMIN, 'Feed: import SAMPLE-LAMP; search/open it and inspect administrator response bodies.', 'Indicative ZAR 534.19; no supplier_cost, freight, duty_percent, margin_percent, exchange_rates or private rate 18.50 in public/admin projections.', 'test_rig_feeds_retailer.test_private_inputs_never_appear_in_public_or_admin_responses')
row(ADMIN, 'Feed: set freight/duty/margin to zero; as ordinary admin try USD rate 22, then save it as founder.', 'SAMPLE-LAMP reprices to ZAR 370; ordinary admin gets 403; founder rate reprices to ZAR 440.', 'test_rig_feeds_retailer.test_rule_reprices_and_exchange_rate_requires_founder')
row(ADMIN, 'Feed: connect a paginated Shopify read-only feed; click Refresh now; inspect nightly refresh/history after advancing the test scheduler.', 'Confirmed mapping and encrypted credentials are reused; completed refresh has a receipt; failures do not replace the catalogue.', 'test_rig_feeds_retailer.test_access_connect_manual_refresh_nightly_and_receipts_on_postgres')
row(ADMIN, 'Feed: select SAMPLE-LAMP → Delete selected → confirm Delete 1 product?; inspect the other test retailer.', 'deleted = 1; the other tenant retains its SAMPLE-LAMP; an ordinary member is refused (403).', 'test_rig_delete_products.test_tank_delete_route_founder_and_tenant_boundary')
row(ADMIN, 'Core: save two different store names/emails; issue an embed key restricted to https://a.fixture.test.', 'Store B retains its own settings; issued snippet uses the hashed/integrity-protected bundle and the key is restricted to its owning store.', 'test_rig_store_job.test_store_settings_and_keys_are_bound_to_the_authenticated_tenant')
row(ADMIN, 'Feed: save the lighting template with stand as its default role and create a no-result search in store A; open store B.', 'Store A has its lighting/stand default and missed search; store B has empty templates and missed searches.', 'test_rig_feeds_retailer.test_template_defaults_and_no_result_counts_are_tenant_scoped')

# Quotes, evidence, rate limits, retention and store-owned fulfilment.
row(API + '/admin/analytics', 'Core: search Core and a no-result term; record each settled search once; open one setup, commit one swap and send one quote. Read analytics with admin key.', 'counts = searches 2, setups_opened 1, swaps 1, quotes 1, no_results 1; shopper gets 403; other store counts are zero.', 'test_rig_quotes.test_http_flow_counts_and_admin_isolation', KEY)
row(WIDGET, 'Core: send a product quote with SMTP failing once; fix test SMTP and retry the saved request.', 'pending with email_unavailable becomes sent; exactly one saved quote, same reference and Message-ID, mail addressed to the store.', 'test_rig_quotes.test_store_email_delivery_keeps_pending_retry_and_reference', SMTP, kind='product')
row(API + '/admin/quotes/{reference}/delivery', 'Core fault-injection profile: POST /v1/rig/admin/quotes/{reference}/retry with {} between failures; after six attempts repair SMTP, then POST /v1/rig/admin/quotes/{reference}/resume with {}.', 'After six attempts status needs_person; ordinary retry does not reset its budget; explicit resume permits delivery.', 'test_rig_quotes.test_delivery_backoff_stops_and_only_explicit_resume_reopens_budget', SMTP)
row(API + '/admin/quotes/attention', 'Core fault-injection profile: create 205 held requests; GET attention; POST /v1/rig/admin/quotes/held_000/resume; follow next_cursor until the end.', 'First page 100; exactly held_000 through held_204 across pages, no duplicates; other tenant sees only other_held.', 'test_rig_quotes.test_attention_pages_past_100_and_only_resumed_holds_count')
row(WIDGET, 'Core: exhaust one shopper browse allowance; use a second shopper; send a quote within its independent allowance.', 'First shopper receives 429 with Retry-After; another shopper still receives 200; browse and quote budgets stay separate.', 'test_rig_quotes_limits.test_http_separate_budgets_cors_and_spoofed_forwarding', KEY)
row(ADMIN, 'Retention fixture: age only synthetic quote/contact rows beyond the configured retention window; run discovery; inspect a recent quote and another tenant.', 'Expired quote and handoff disappear together; recent data and anonymous counts remain; deletion is tenant-scoped.', 'test_rig_quotes_postgres.test_retention_purge_job_cascade_and_tenant_isolation')
row(WIDGET, 'Notice fixture: open quote; replace Offline policy one. with Offline policy two. before submission; acknowledge current notice and submit; repeat with Offline policy three.', 'Stale consent cannot submit; one stored quote records Offline policy two.; next records Offline policy three. with current version/time.', 'test_rig_quote_notice.test_shipped_notice_stale_recovery_and_real_receipts', KEY, theme='neutral', width=390)
row(API + '/locate', 'Supply profile: locate out-of-stock desk; repeat without key, then as the other store.', 'Own-store result status available_to_order and only status/eta/ship_days/price; unauthenticated 401; foreign store cannot see the offer.', 'test_rig_supply_locate.test_http_locate_and_admin_ingestion_boundaries')
row(WIDGET, 'Locate profile: accept a sourced quote before the store confirms payment; inspect quote email and order records.', 'Request is stored/handed off; no order, supplier PO, payment charge, card or refund is created by accepting the quote.', 'test_rig_no_payments.test_accept_without_order_configuration_stores_and_hands_off_only', SMTP)
row('https://app.tervory.com/chats', 'Locate profile: after the store receives EFT, use the existing rig.quote.confirm_payment confirmation for the saved quote reference; repeat confirmation. Do not send bank/card fields.', 'Unauthenticated control call 401; extra bank_details 422; foreign quote 404; repeat confirmed request returns same result and one local order.', 'test_rig_no_payments.test_retailer_http_confirmation_requires_existing_control_auth_and_only_quote_id')
row(WIDGET, 'Core: open a setup with store delivery 2–3 days and one unavailable part; request its quote.', 'Every item has delivery metadata; stocked item min_days 2/max_days 3/back_order false; unavailable item back_order true.', 'test_rig_no_payments.test_every_setup_item_carries_delivery_metadata', KEY)
row(WIDGET, 'Recall profile: search the same term twice, then change the catalogue and search again.', 'Unchanged search is reused without ranking again; changed catalogue invalidates the saved result.', 'test_rig_recall.test_a_changed_catalogue_is_not_reused')
row(API + '/search', 'L1 profile: run the independent 578-record search/detail/quote fixture suite, including category, relation, fit and stock queries.', 'Every independent golden result, detail and reservation result agrees; no live model or supplier call.', 'test_rig_l1.test_complete_search_detail_and_reservation_golden')

# US cart: platform API fake, exact same public operation/backend paths.
row(WIDGET, 'US profile: add stock, located and back-order lines, quantity 2 each; continue to WooCommerce checkout.', 'Store line totals 20.00, 40.00, 80.00; total USD 140.00; delivery 2 days / 9 days with ETA / back order; no supplier identity.', 'test_rig_cart.test_carrier_mixed_order_privacy_and_posted_prices', KEY)
row(WIDGET, 'US: change stock price from 10.00 to 11.00 before Continue; restore it; retry after an uncertain order-create response.', 'Changed price requires recheck; no stale checkout; retries keep one remote order and state create_unknown until resolved.', 'test_rig_cart.test_checkout_recheck_and_lost_create_never_duplicate', KEY)
row(WIDGET, 'US: continue a sourced cart to store checkout; leave unpaid for five minutes; then deliver a valid late paid callback twice.', 'At 299 seconds pending; at 300 expired; late_payment true after signed confirmation; exactly one supplier placement.', 'test_rig_cart.test_expiry_release_and_late_signed_payment_honoured_once', KEY)
row(API + '/commerce/webhooks/{tenant_id}', 'US: deliver the same raw WooCommerce callback with a wrong signature, then its correct X-WC-Webhook-Signature.', 'Bad signature refused; correct raw-body HMAC accepted; modified body without re-signing refused.', 'test_rig_cart.test_official_raw_body_signatures_and_timestamp', platform='woocommerce')
row(WIDGET, 'US: create a Shopify checkout with one native stock variant plus a sourced custom line.', 'Shopify draft checkout carries native variantId and projected custom line; no payment/card endpoint is called.', 'test_rig_cart.test_shopify_and_bigcommerce_create_native_and_custom_lines', KEY, kind='shopify')
row(WIDGET, 'US: create a BigCommerce checkout with native and custom lines.', 'BigCommerce native/custom cart redirect is on the allowed store host; no payment/card endpoint is called.', 'test_rig_cart.test_shopify_and_bigcommerce_create_native_and_custom_lines', KEY, kind='bigcommerce')
row(ADMIN + '?cart=connection', 'US: ordinary store member attempts shop connection, Orders and delivery operations.', 'Each unauthorized operation is refused before dispatch; administrator identity is server-owned.', 'test_rig_cart_admin.test_cart_admin_rejects_ordinary_member_before_dispatch', operation='commerce-connect')
row(ADMIN + '?cart=orders', 'US: set store delivery range and open Orders as store A while submitting store B tenant IDs.', 'Only authenticated store A delivery and orders are returned; supplied foreign tenant never wins.', 'test_rig_cart_admin.test_delivery_and_orders_use_only_account_tenant')
row(WIDGET, 'US: deliver concurrent paid callbacks and poll the order while placement is underway.', 'Exactly one located order/PO; recorded quantity preserved; supplier identity remains private.', 'test_rig_cart.test_mixed_cart_concurrent_webhooks_and_readback_use_one_located_order', KEY)
row(WIDGET, 'US: open a cart, explicitly recheck and change quantities while concurrent updates run.', 'Preview does not silently commit refreshed price/stock; explicit changes are atomic and preserve one consistent cart.', 'test_rig_cart.test_cart_preview_recheck_and_quantity_changes_are_atomic', KEY)

# 3D backend/admin exists; GPU and shopper entry remain off pending frames.
row('https://rig.tervory.com/rig/admin/three-d', '3D profile: prepare the local stand-in model; preview as admin; omit attachment-point approval, then approve scale/appearance/attachment points.', 'Draft asset is 404 to shopper; incomplete review 422; full admin review 200; repeat approval 409; approved GLB begins glTF.', 'test_rig_3d_engine.test_draft_hidden_until_all_human_checks_and_idempotent_submission')
row(API + '/3d/assembly', '3D: build centre from approved models/fits; change module to part-tall; revoke that fit and retry.', 'Three models; USD 150 indicative total; swap USD 155; revoked fit 422 and cannot be quoted.', 'test_rig_3d_engine.test_assembly_approved_mounts_swap_current_fit_and_single_total')
row(API + '/3d/assembly', '3D: request an assembly with a missing approved model.', 'available false and no asset address; no partial misleading assembly.', 'test_rig_3d_engine.test_missing_model_falls_back_without_any_asset_address')
row(API + '/3d/capabilities', '3D: internally grant rig_3d to one test store; approve models; revoke and restore that grant.', 'Grant is tenant-scoped; revoked old asset/assembly 403; restore retains approved revision, reviewer and timestamp; photo_sources scan only.', 'test_rig_3d_engine.test_wave4_room_entitlement_grant_review_revoke_and_restore')
row('https://rig.tervory.com/3d/', '3D: open a configured kiosk; request a quote; use the administrator reset for that kiosk.', 'Reset increments revision to 1 for the owning store; quote is stored; shopper cannot reset (403).', 'test_rig_3d_engine.test_remote_reset_is_tenant_scoped_and_quote_is_stored')
row('https://rig.tervory.com/rig/admin/three-d', '3D: with few-photo preparation disabled, attempt source ai with one photo.', 'Capabilities list scan only; ai preparation is refused before storage or GPU work. Leave HF_JOBS_TOKEN/HF_JOBS_NAMESPACE unused.', 'test_rig_3d_engine.test_few_photo_preparation_is_hidden_and_rejected_until_enabled', 'none')



# Additional platform/privacy/settings surfaces, without enabling external services.
row(WIDGET, 'Core mobile: at 390px complete search → setup → swap → missing-product form → Explore → Ask → quote.', 'No horizontal overflow; three setups; swap R 130; field errors work; Ask says I don\'t know; quote acknowledged.', 'test_rig_quotes_browser.test_built_widget_live_api_journey', KEY, width=390)
for platform, primary in [('shopify', {'access_token': 'placeholder-access'}),
                          ('woocommerce', {'consumer_key': 'placeholder-key', 'consumer_secret': 'placeholder-secret'}),
                          ('bigcommerce', {'access_token': 'placeholder-access'})]:
    row(ADMIN + '?cart=connection', f'US: connect {platform} using test credentials; reconnect after an operator has provisioned webhook_secret in the sealed vault.', 'Credentials stay sealed and are not forwarded/returned/logged; reconnect preserves the existing webhook secret.', 'test_rig_cart_admin.test_cart_admin_credentials_sealed_not_forwarded_returned_or_logged', platform=platform, primary=primary, preserve=True)
for platform in ('shopify', 'bigcommerce'):
    row(API + '/commerce/webhooks/{tenant_id}', f'US: send a signed {platform} raw callback, then alter its body/signature (and BigCommerce timestamp).', 'Valid signature accepted; altered body/signature refused; BigCommerce old timestamp refused.', 'test_rig_cart.test_official_raw_body_signatures_and_timestamp', platform=platform)
row(WIDGET, 'Locate profile: enable blind shipping only on the test store; accept a quoted item with the test shopper delivery address and a neutral-slip source.', 'Local order/PO retains the delivery address and neutral-slip instruction; no supplier identity reaches the shopper.', 'test_rig_optional_blind_ship.test_blind_accept_records_a_rig_order_and_a_neutral_slip_po_to_the_shopper', SMTP)
row(WIDGET, 'Locate sandbox: after store payment confirmation, enable auto-order and use the local test outbox; repeat the same confirmation.', 'One local supplier-order email file, one order and one PO; no live supplier email, card or refund.', 'test_rig_no_payments.test_confirmation_is_concurrent_idempotent_and_tenant_scoped')
row('https://app.tervory.com/chats', 'As test-store administrator ask: Confirm the store has received payment for quote <the saved reference>. Review the rig.quote.confirm_payment card, confirm it once, then retry.', 'Confirmation binds the authenticated actor and saved quote; a zero-cost code receipt records the result; one local order.', 'test_rig_confirmation_command.test_confirm_card_binds_actor_quote_and_writes_zero_code_receipt')
for kind in ('setup', 'link'):
    row(WIDGET, f'Core: submit a {kind} quote with the first SMTP send failing; retry after repairing the test transport.', 'pending → sent; same store recipient, quote reference and Message-ID; exactly one saved quote.', 'test_rig_quotes.test_store_email_delivery_keeps_pending_retry_and_reference', SMTP, kind=kind)
row('https://app.tervory.com/rig', 'Open Plugins before the Rig vault has been enabled.', 'This vault is off. Turn it on in Tank.; secret/file/link/connection lists are empty.', '_workspace_contract', case='plugins-off')
row('https://app.tervory.com/rig', 'On an enabled test vault, open Plugins → API keys; save fixture-key with a synthetic value; reload.', 'Only fixture-key metadata and •••••••• return; raw secret never reaches the panel.', '_workspace_contract', case='plugins-key')
row('https://app.tervory.com/rig', 'On enabled test Plugins, upload fixture.csv; add a weekly source link and an authenticated fixture connection; remove all three.', 'Requests remain scoped to rig.vault and the authenticated tenant; metadata lists fixture.csv; remove actions use the same owning tenant.', '_workspace_contract', case='plugins-data')


def _workspace_contract(case):
    result = subprocess.run(['node', 'tests/acceptance/rig_workspace.cjs', case],
                            cwd=REPO, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


row(API + '/compare', 'Core: POST {"product_ids":["CORE-1","CORE-2"]} using the issued store key and allowed Origin.', 'Two selected lines CORE-1/CORE-2 with indicative ZAR 100/150; market is null when no observation exists.', '_compare_http')
row(WIDGET, 'Recall profile: search optic for lumaworks twice against unchanged fixture data.', 'Same result IDs; second search reused true, cost 0; no extra ranking or model call.', 'test_rig_recall.test_the_same_search_is_reused_for_nothing')
row(API + '/admin/analytics', 'Supply: record a synthetic USD 53.21 sale receipt; replay it; record an external adjustment -3.21 and EUR 7. Read kept revenue.', 'Before receipts revenue is null; after, USD 50.00 and EUR 7 remain separate; receipt_count 3; source store_reported_sale_receipts. Rig initiates no refund.', 'test_rig_supply_locate.test_revenue_requires_receipt_retries_dont_inflate_and_currencies_separate')
row('https://rig.tervory.com/rig/admin/three-d', '3D: stage overlapping photos whose combined streamed data exceeds the job limit; try 71 scan photos.', '1 GB job limit refuses before output upload, scratch is removed; 71 photos rejected. No GPU conversion.', 'test_rig_3d_uploads.test_whole_job_limit_is_checked_before_any_write_and_scratch_is_removed')
row('https://rig.tervory.com/v5', 'Use a published key owned by an empty second store; open the catalogue page while another store has products.', 'window.RIG_KEY is empty for the empty store; no other store key, Archon or bundled demo catalogue is borrowed.', 'test_rig_no_live_demo.test_configured_page_requires_its_own_published_products', KEY)
row(WIDGET, 'US: after a signed payment callback, simulate transient order_unavailable during placement, then repair it and replay the callback.', 'paid_pending releases its lease; repair produces placed with one order, not a second payment.', 'test_rig_cart.test_placement_failure_releases_only_own_lease_and_retries', KEY, error='order_unavailable', expected='paid_pending')
row(WIDGET, 'US: after signed payment, simulate permanent order_mismatch; replay the callback.', 'needs_person remains; no duplicate order or second placement attempt.', 'test_rig_cart.test_placement_failure_releases_only_own_lease_and_retries', KEY, error='order_mismatch', expected='needs_person')
row('https://rig.tervory.com/rig/admin/three-d', '3D: request a quote with a valid phone only; then try missing/invalid contact.', 'Valid phone-only quote is stored for its tenant; missing or invalid contact rejected with 422.', 'test_rig_3d_engine.test_quote_accepts_phone_only_and_rejects_missing_or_invalid_contacts')


async def _compare_http():
    import httpx
    from fastapi import FastAPI
    from rigbox.api import mount
    from test_rig_quotes import service
    from fixtures.rig_quote_sample import KEY as public_key
    app = FastAPI()
    app.state.rig = await service()
    mount(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://rig.tervory.com') as client:
        response = await client.post('/v1/rig/compare', headers={
            'X-Rig-Key': public_key, 'Origin': 'http://127.0.0.1:8001'},
            json={'product_ids': ['CORE-1', 'CORE-2']})
    assert response.status_code == 200
    lines = response.json()['lines']
    assert [item['id'] for item in lines] == ['CORE-1', 'CORE-2']
    assert [item['price']['amount'] for item in lines] == [100, 150]
    assert all(item['price']['currency'] == 'ZAR' and item['price']['indicative'] for item in lines)
    assert all(item['market'] is None for item in lines)

row(ADMIN, 'Feed: import the five catalogue samples; set EU rule freight 2/duty 5/margin 0, then DE freight 4/duty 0/margin 0, then supplier freight 3/duty 0/margin 0; change the default rule.', 'EU-STAND reprices ZAR 357 → 380 → 360 and stays 360 after the default changes; selling-price STORE-DESK stays 799.95.', 'test_rig_feeds_catalogues.test_regional_and_supplier_overrides_and_selling_price_survive_repricing')
row(API + '/search', 'Second-store profile: search lamps, shades, parts, shade to go with the lamp, then 2 pack lamps.', 'Focus SECOND-LAMP-01; shade/parts IDs SECOND-SHADE-01; message We list lamps separately.; no first-store vocabulary is pasted.', 'test_rig_l1.test_second_store_owns_categories_parts_and_sentences_without_fallback')
row(WIDGET, 'US: leave a second tenant in default quote mode; attempt cart add there; on the cart tenant send a signed paid callback whose read-back total is 1.00 instead of the saved total.', 'Default quote tenant returns cart_disabled; changed paid total raises order_mismatch; no supplier placement.', 'test_rig_cart.test_quote_default_tenant_isolation_and_total_verification', KEY)


def _sheet_matches_rows():
    text = (REPO / 'docs/acceptance/rig.md').read_text()
    ids = re.findall(r'^\| (RIG-\d+) \|', text, flags=re.MULTILINE)
    assert ids == [item.id for item in ROWS], 'Sheet/proof rows must stay one-to-one'


def _install(check: Row):
    if '.' in check.proof:
        module, name = check.proof.rsplit('.', 1)
        target = getattr(importlib.import_module(module), name)
    else:
        target = globals()[check.proof]
    parameters = [p for p in inspect.signature(target).parameters.values() if p.name not in check.parameters]
    if inspect.iscoroutinefunction(target):
        async def proof(**fixtures):
            _sheet_matches_rows()
            await target(**fixtures, **check.parameters)
        proof = pytest.mark.asyncio(proof)
    else:
        def proof(**fixtures):
            _sheet_matches_rows()
            target(**fixtures, **check.parameters)
    proof.__name__ = 'test_' + check.id.replace('-', '_')
    proof.__doc__ = check.where + '\n' + check.action + '\nExpected: ' + check.expected
    proof.__signature__ = inspect.Signature(parameters)
    globals()[proof.__name__] = proof


for _check in ROWS:
    _install(_check)
