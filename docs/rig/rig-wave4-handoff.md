# Rig Wave 4: store email delivery, 3D readiness and dev-store setup

## Founder direction: Trigger CRM replaces the retired ERP

The founder's 3 November 2026, 15:23 PT direction supersedes L20. Its contract test and fake
server recording are removed from this branch. The quotation adapter and its
sender dispatch are removed from `rigbox/quotes/senders.py`, along with its
credential settings in `.env.example` and the Rig Compose service. No new
Trigger CRM adapter is introduced by this removal.

Quote delivery continues through the existing store email/SMTP path, with the
same pending/sent states, retry budget, safe error codes and stable Message-ID.
Existing explicitly configured webhooks retain their behavior. Custom Nation
stays quote → the store's own invoice → EFT. Rig never invoices, takes payment,
holds a card or refunds. US stores continue to their own cart/checkout.

`fulfilment.py` and `supplier_orders.py` already use Rig-owned local order and
purchase-order rows; their retired ERP references are removed. No supplier
identity is added to shopper output. The three new email regression cases cover
product, setup and link requests, SMTP failure and successful retry to the store.

## Schema and scope

`agents/rig/schema.sql` is unchanged: no column or table is dropped, renamed or
repurposed. There is no Odoo-named column in the current Rig schema; its existing
historical comment remains. Any legacy deployed column is left in place unused.
No destructive migration is introduced. `tank/skills/base.site_signals` is
unchanged: its website platform detection is outside this removal.

The Rig runtime/Compose change will redeploy the Rig room and its configured
regional copies when reviewed and merged. This work does not deploy or change
live settings. It follows the founder's explicit request to make these removals
on `codex/rig-w4`, PR #646.

## L39/L29: backend ready, viewer entry waiting for Figma

The existing production 3D entry point mounts tenant entitlements, model checks,
human approval and approved-fit assembly. The real Postgres/API lifecycle proof
covers disabled access, room-key grants scoped to one tenant, human review of
scale/appearance/attachment points, approved assembly, immediate revocation and
restoration of the same reviewed revision and audit details.

No approval record for 3D frames 06–07 exists in `docs/figma`. Their pending
inventory is [RIG-3D-FRAMES.md](../figma/RIG-3D-FRAMES.md). The widget entry stays
hidden. GPU settings remain unchanged and off; no GPU or model call was made.
Entitlement grant is an internal authorization change, not a payment/subscription.

## Founder cart test

Use [RIG-US-CART-DEV-STORES.md](../ops/RIG-US-CART-DEV-STORES.md) for separate
Shopify and WooCommerce test stores, named configuration/credential fields,
signed webhook provisioning, product mappings and the acceptance checklist.
The guide includes no credential values and does not claim live-store acceptance.

## Validation

The complete remaining Rig suite (`tests/test_rig*.py`): **777 passed,
19 skipped, no failures**, in 401.79 seconds. The skips are the suite's existing
environment-gated checks; none was newly disabled by this change. The run used
Chromium and a fresh loopback-bound disposable Postgres 16, with external sockets
disabled. The temporary database container was removed afterwards. No live
store, GPU, model, SMTP server or production database was contacted.

The focused delivery/store-job/optional-order run also passed: **62 passed,
4 skipped** (that focused run had no database setting). The three new email
regression cases passed in both runs. Ruff (`E9,F`), `git diff --check`, and
`docker compose -f agents/rig/docker-compose.yml config --no-interpolate --quiet`
passed. The withdrawn L20 recording and its results are removed from this handoff.

Reproduce using an isolated `RIG_TEST_DATABASE_URL`, the repository's Python
paths and Chromium, then run:

```sh
python -m pytest -q tests/test_rig*.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

## Change inventory (current file and line)

| File and line | Change |
| --- | --- |
| `agents/rig/rigbox/quotes/senders.py:41` | Removes the quotation adapter and dispatch; retains store email and explicit webhook delivery. |
| `agents/rig/rigbox/quotes/service.py:48` | Removes retired ERP wiring comments; local fulfilment and delivery claim behavior unchanged. Delivery timeout comment at line 292. |
| `agents/rig/rigbox/fulfilment.py:1` | Clarifies the existing Rig-owned order/PO path; no external ERP adapter exists here. |
| `agents/rig/rigbox/supplier_orders.py:1` | Removes the retired ERP reference; sandbox supplier outbox unchanged. |
| `.env.example:263` | Removes the four retired credential settings and obsolete flow prefix instructions. |
| `agents/rig/docker-compose.yml:31` | Removes the four credential environment passthroughs; SMTP settings remain. |
| `agents/rig/BOX.md:30` | Removes the retired ERP credential reference. |
| `agents/rig/rigbox/quotes/README.md:22` | Replaces adapter instructions with existing store email setup, invoice/EFT boundary and email retry acceptance checks. |
| `agents/rig/rigbox/three_d/README.md:143` | Describes the delivery acknowledgement without the retired sender. |
| `tests/rig_store_job/README.md:46` | Keeps SMTP and explicit webhook instructions; removes the retired sender. |
| `tests/test_rig_quotes.py:1` | Removes the retired adapter stub/cases, preserves the exact-tenant/webhook test, and adds product/setup/link email recovery checks at line 257. |
| `tests/test_rig_optional_auto_order.py:1` | Removes the stale ERP reference; local PO test cases remain. |
| `tests/test_rig_optional_blind_ship.py:1` | Removes the stale ERP reference; blind shipping/privacy cases remain. |
| `docs/cursor/RIG-PHASE-1.md:17` | Removes obsolete ERP setup instructions from the phase-one brief and records the founder’s store-email/Trigger CRM direction. |
| `docs/rig/rig-wave4-handoff.md:3` | Replaces the withdrawn L20 proof with the founder's removal direction, schema note and current validation. |
| Removed: `tests/test_rig_odoo_contract.py`, `tests/fixtures/rig_odoo/README.md`, `tests/fixtures/rig_odoo/quotation.json` | Deletes this wave's entire L20 proof. No current line remains for a deleted file. |
