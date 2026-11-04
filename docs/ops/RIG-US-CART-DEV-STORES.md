# Founder cart test: Shopify and WooCommerce development stores

Use dedicated test stores and synthetic products/contact details. This guide
lists setting names only; keep credential values in the existing sealed vault,
never in this document, screenshots, chat, source, URLs or browser storage.
Rig never takes payment, holds a card or refunds. The store owns checkout and
payment. Custom Nation stays quote → retailer invoice → EFT; these US cart
instructions do not change its configuration.

## Shared Rig preparation

1. Use a separate US test retailer tenant. Confirm the existing room setting
   `TANK_REGION` selects the US deployment. Existing server credential names are
   `TANK_API_KEY`, `TANK_KEY`, `RIG_RETAILER_KEY` and `TANK_VAULT_KEY`; do not create
   another credential path or expose these to the browser.
2. Open Rig's approved Shop platform form as that tenant's administrator. The
   stored commerce setting names are `mode`, `region`, `platform`, `site`,
   `vault_name`, `products`, `checkout_hosts` and `delivery`. The connection action
   selects cart mode and US region. Quote mode remains the default elsewhere.
3. Map each test stock SKU through `products`, using `product_id` and, where
   applicable, `variant_id`. Configure `checkout_hosts` for the actual store
   checkout hostname (no scheme/path) and `delivery` using `min_days` / `max_days`.
   Never add supplier names, costs, card fields or raw supplier payloads to these mappings.
4. Webhook credentials use `webhook_secret` inside the same tenant-scoped sealed
   `rig.vault` commerce credential. The approved A07 forms currently omit this
   field. An authorized operator must provision it through the existing
   administrator `commerce-connect` action (`credential`, `vault_name`,
   `platform`), which seals the values server-side. The form preserves an
   existing secret on reconnect. Never disable signature checks to get the test working. See the missing per-platform
   fields in `docs/rig/rig-cart-us-handoff.md` under Waiting for Figma.

## Shopify

1. Create a Shopify dev store, install the test integration and create synthetic
   stocked variants with inventory and prices. Use an app token with the scopes
   needed by the adapter: `read_products`, `read_inventory`, `read_orders`,
   `read_draft_orders` and `write_draft_orders`. Do not grant payment/card permissions. The adapter uses
   Admin API version 2026-10 and creates a draft order with a store invoice URL.
2. In the Shopify connection form provide the `site` setting for its canonical
   myshopify origin. The sealed credential setting name is `access_token`.
   Run the connection test before adding the product mappings above.
3. Configure a Shopify Test payment gateway or the provider's test mode in the
   dev store. Enter test payment information only on Shopify's checkout.
4. Configure an order-paid webhook to the US Rig route
   `/v1/rig/commerce/webhooks/{tenant_id}`. The receiver verifies
   `X-Shopify-Hmac-Sha256` against the sealed `webhook_secret`; use the signing
   secret belonging to the app/subscription which sends the event. Preserve the
   raw JSON body. A browser return alone does not confirm payment.

References: [Shopify dev stores](https://shopify.dev/docs/apps/build/stores/development-stores),
[test orders](https://help.shopify.com/en/manual/checkout-settings/test-orders/processing-test-order),
[draft creation scope](https://shopify.dev/docs/api/admin-graphql/latest/mutations/draftordercreate),
[draft read scope](https://shopify.dev/docs/api/admin-graphql/latest/objects/draftorder).

## WooCommerce

1. Create an isolated HTTPS WordPress/WooCommerce test installation with working
   cart/checkout pages and non-plain permalinks. Add synthetic stock products and
   variations with prices, inventory and US test shipping/tax configuration.
2. Under WooCommerce → Settings → Advanced → REST API, create a dedicated
   integration user's read/write key. The sealed credential setting names are
   `consumer_key` and `consumer_secret`; `site` identifies the HTTPS store origin.
   Rig uses `/wp-json/wc/v3`. Run the approved connection test. It finds or creates
   the hidden carrier product by SKU; reconnecting must not duplicate it.
3. Enable the store payment provider's sandbox/test mode. Do not use real card
   data or a live payment account. Payment information stays on the store checkout.
4. Configure order webhooks for updates that report a paid order, targeting
   `/v1/rig/commerce/webhooks/{tenant_id}`. Set the webhook Secret and provision
   that same secret as `webhook_secret` in the sealed commerce credential.
   The receiver verifies `X-WC-Webhook-Signature` over the raw body, then checks
   the store's order state. Unpaid orders must remain unconfirmed.

References: [REST API keys](https://woocommerce.com/document/woocommerce-rest-api/),
[advanced settings](https://woocommerce.com/document/configuring-woocommerce-settings/advanced/),
[webhooks](https://woocommerce.com/document/webhooks/).

## Founder acceptance run, once per store

- Add stock and sourced test lines; change quantity, remove a line, and recheck
  after changing price/stock in the store. Confirm unit price × quantity, delivery
  and total. An unavailable item cannot silently proceed.
- Continue to the store checkout. Confirm its host, items, quantities, currency,
  shipping/tax and payable total. The five-minute window starts there. Refresh
  and return without paying: Rig must not claim payment was received.
- Complete a test order on the store. Deliver its signed webhook, then read the
  order back in Rig. Confirm the original order/total and payment status; replay
  the webhook and check that no duplicate order or supplier placement occurs.
- Test expiry, a delayed payment event, a bad signature and a temporary placement
  failure. Paid placement failures show the existing status pill without the
  unconfirmed-payment sentence. Never refund through Rig.
- Inspect shopper views, response bodies and the store's customer-facing lines:
  supplier names and private costs must be absent. Inspect private placement
  evidence separately as an authorized administrator.

Record the store/platform, tenant identifier, test time, observed order state
and pass/fail evidence without tokens, secrets, card/contact data or supplier
identities in shopper screenshots. These are manual dev-store checks still to
run; offline adapter tests do not claim live-store acceptance.
