# Rig Wave 4: L20, L39/L29 and founder cart setup

## L20: offline Odoo contract proof

`tests/fixtures/rig_odoo/quotation.json` is a synthetic, inspectable JSON-RPC
recording with invented identities and credentials. The independent ASGI fake
server accepts only those exact HTTP requests. The adapter proves legacy Odoo
16/17/18 version discovery, authentication, `execute_kw` dispatch, currency and
SKU mapping, relational line commands and unverified request-scoped partner
creation, ending with one draft `sale.order.create`.

The lost-response scenario commits the fake order and raises a transport timeout;
the retry finds the same tenant/request reference and makes no second create.
Unsupported versions, rejected authentication and RPC errors stop before writes.
The existing quote suite covers failed mappings, partner-create response loss,
server repricing, approved setup parts and delivery retry persistence.

Odoo stays off until an exact tenant entry in `RIG_QUOTE_FLOWS` selects the sender
and all four existing settings are filled: `RIG_ODOO_URL`, `RIG_ODOO_DATABASE`,
`RIG_ODOO_USER`, `RIG_ODOO_API_KEY`. A selected tenant can use its own
`RIG_ODOO_<RETAILER>` prefix. The tests prove each missing setting prevents every
HTTP request, configured dispatch works, and another tenant cannot inherit it.
No environment values or deployment configuration changed.

This is offline contract evidence, not live Odoo acceptance. The operator still
needs to verify the retailer's version, API plan, permissions, installed sale
modules, pricelist and SKU mapping before enabling its existing settings. Rig
creates a quotation only. The retailer owns invoice and EFT; Rig never confirms
an order, invoices, charges, stores a card or refunds through this adapter.

## L39/L29: backend ready, viewer entry waiting for Figma

The existing production 3D entry point already mounts tenant entitlements, model
checks, human approval and approved-fit assembly. Wave 4 reuses that path and
adds a real Postgres/API lifecycle proof rather than introducing a second path:

- A disabled tenant cannot submit a model or fetch an approved assembly/asset.
- Only the internal room credential grants the entitlement; public/admin embed
  keys cannot grant it. Granting one tenant leaves another disabled.
- The local forge stand-in supplies validated model bytes. A human must approve
  scale, appearance and attachment points, with reviewer and approval time stored.
- Approved fits yield a complete approved-model assembly. Revocation blocks old
  URLs immediately; restoration retains the reviewed revision and audit details.

No approval record for 3D frames 06–07 exists in `docs/figma`. Their pending
inventory is [RIG-3D-FRAMES.md](../figma/RIG-3D-FRAMES.md). The widget entry stays
hidden. GPU settings remain unchanged and off; no GPU or model call was made.
Entitlement grant is an internal authorization change, not a payment/subscription.

## Founder cart test

Use [RIG-US-CART-DEV-STORES.md](../ops/RIG-US-CART-DEV-STORES.md) for separate
Shopify and WooCommerce test stores, named configuration/credential fields,
signed webhook provisioning, product mappings and the acceptance checklist.
US stores go to their own checkout; Custom Nation remains quote → invoice → EFT.
Supplier names never belong in shopper views or store customer-facing lines.
The guide includes no credential values and does not claim a live store test.

## Validation

- Recorded Odoo contract file alone: **15 passed**, with external sockets disabled.
- Combined quotation, 3D engine/deployment/uploads/Workspace, cart/admin/Postgres
  regression: **131 tests covered**. The initial run had 130 passes and one local
  test-container authentication failure: the forced-RLS test creates a role
  without a password. After matching the disposable container's authentication
  to that fixture, the two cart Postgres tests passed, including the failed test.
  No application or test assertion was changed to bypass the failure.
- Ruff (`E9,F`) for the changed test modules and `git diff --check`: passed.
- All database work used an isolated loopback-bound disposable Postgres 16;
  deployment and model services were not contacted. The temporary container was
  removed after validation. No production database, environment or schema changed.

Reproduce with pytest and the repository's offline flags:
`--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1`.
Set `RIG_TEST_DATABASE_URL` only to an isolated disposable test database when
running the Postgres cases. The nine files are `test_rig_odoo_contract.py`,
`test_rig_quotes.py`, `test_rig_3d_engine.py`, `test_rig_3d_deployment.py`,
`test_rig_3d_uploads.py`, `test_rig_3d_workspace.py`, `test_rig_cart.py`,
`test_rig_cart_admin.py` and `test_rig_cart_postgres.py`, all under `tests/`.

Branch: `codex/rig-w4`, created from `origin/main`. The three items are pushed
separately. Claude opens the PR under the standing branch rules; this wave does
not open, label or merge one.
