# Rig cart (US) — Proposed, not approved

Page: [10 · Rig cart (US)](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=289-13919), node `289:13919`. Branch: `codex/rig-cart-figma`. Design-check revisions: rounds 1 and 2, then the 12-item sizing round, 3 November 2026. The sizing-round values below supersede earlier dimensional audit results.

All 52 frames and their review bars remain **Proposed, not approved**. Copy below is proposed for founder approval. Illustrative values exist only in Figma, not on a live screen. This branch changes only this register relative to main; no widget, admin, payment, credential or other runtime code is changed.

## Frame register

The original 38 frame IDs are retained. All 94 distinct node IDs named in the round-1 review still resolve. Original hidden layers are retained only to preserve those IDs and are listed below as not for build. Hidden stale layers in the 14 new frames have been deleted. Fourteen additional frames cover seven desktop/mobile pairs. Heights below come from the final canvas, not the original generator.

| Screen | Node ID | Size | Existing source reused |
| --- | --- | --- | --- |
| S01a · Product · store stock | [291:9](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-9) | 1440 × 900 | Widget product/chosen card, price and actions |
| S01a · Product · store stock | [291:26](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-26) | 375 × 812 | Widget product/chosen card, price and actions |
| S01b · Product · longer delivery | [291:43](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-43) | 1440 × 900 | Widget product/chosen card, price and actions |
| S01b · Product · longer delivery | [291:60](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-60) | 375 × 812 | Widget product/chosen card, price and actions |
| S01c · Product · back order | [291:77](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-77) | 1440 × 900 | Widget product/chosen card, price and actions |
| S01c · Product · back order | [291:97](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-97) | 375 × 812 | Widget product/chosen card, price and actions |
| S02 · Item added to cart | [291:117](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-117) | 1440 × 900 | Widget product/chosen card, price and actions |
| S02 · Item added to cart | [291:140](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-140) | 375 × 812 | Widget product/chosen card, price and actions |
| S03 · Your cart | [291:163](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-163) | 1440 × 1363 | Widget card, field, price, notice and actions |
| S03 · Your cart | [291:223](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-223) | 375 × 1574 | Widget card, field, price, notice and actions |
| S04 · Going to store checkout | [291:283](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-283) | 1440 × 900 | Widget status/panel, timer panel and actions |
| S04 · Going to store checkout | [291:302](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-302) | 375 × 812 | Widget status/panel, timer panel and actions |
| S05a · Payment window ended · rechecking | [291:321](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-321) | 1440 × 1471 | Widget card, field, price, notice and actions |
| S05a · Payment window ended · rechecking | [291:384](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-384) | 375 × 1739 | Widget card, field, price, notice and actions |
| S05b · Cart rechecked · changes found | [291:447](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-447) | 1440 × 1485 | Widget card, field, price, notice and actions |
| S05b · Cart rechecked · changes found | [291:511](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-511) | 375 × 1753 | Widget card, field, price, notice and actions |
| S06a · Paid order with back order | [291:575](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-575) | 1440 × 1210 | Widget paid notice and product-card instances |
| S06a · Paid order with back order | [291:598](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-598) | 375 × 1194 | Widget paid notice and product-card instances |
| S06b · Checkout not completed | [291:621](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-621) | 1440 × 900 | Widget status/panel, timer panel and actions |
| S06b · Checkout not completed | [291:640](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-640) | 375 × 812 | Widget status/panel, timer panel and actions |
| A07-choose · Shop platform · not connected | [291:8053](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8053) | 1440 × 900 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-choose · Shop platform · not connected | [291:8075](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8075) | 375 × 812 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-shopify · Shopify · enter credentials | [291:8097](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8097) | 1440 × 900 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-shopify · Shopify · enter credentials | [291:8124](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8124) | 375 × 812 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-woo · WooCommerce · enter credentials | [291:8151](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8151) | 1440 × 900 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-woo · WooCommerce · enter credentials | [291:8182](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8182) | 375 × 856 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-big · BigCommerce · enter credentials | [291:8213](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8213) | 1440 × 900 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-big · BigCommerce · enter credentials | [291:8240](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8240) | 375 × 812 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-testing · Shop platform · testing | [291:8267](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8267) | 1440 × 900 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-testing · Shop platform · testing | [291:8288](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8288) | 375 × 812 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-connected · Shop platform · connected | [291:8309](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8309) | 1440 × 900 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-connected · Shop platform · connected | [291:8333](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8333) | 375 × 812 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-failed · Shop platform · connection failed | [291:8357](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8357) | 1440 × 900 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-failed · Shop platform · connection failed | [291:8381](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8381) | 375 × 812 | RetailerAdmin card, label/input, select, notice and buttons |
| A08 · Orders | [291:8405](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8405) | 1440 × 900 | RetailerAdmin stacked history and actions |
| A09 · Store delivery time | [291:8444](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8444) | 1440 × 900 | RetailerAdmin numeric label/inputs and preview |
| A08 · Orders | [291:8464](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8464) | 375 × 935 | RetailerAdmin stacked history and actions |
| A09 · Store delivery time | [291:8503](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8503) | 375 × 812 | RetailerAdmin numeric label/inputs and preview |
| S03-empty · Empty cart | [318:60926](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-60926) | 1440 × 900 | Widget card, field, price, notice and actions |
| S03-empty · Empty cart | [318:60992](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-60992) | 375 × 812 | Widget card, field, price, notice and actions |
| S05c · Item unavailable after recheck | [318:61058](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-61058) | 1440 × 1527 | Widget card, field, price, notice and actions |
| S05c · Item unavailable after recheck | [318:61123](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-61123) | 375 × 1775 | Widget card, field, price, notice and actions |
| S05d · Cart rechecked without changes | [318:61188](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-61188) | 1440 × 1465 | Widget card, field, price, notice and actions |
| S05d · Cart rechecked without changes | [318:61252](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-61252) | 375 × 1713 | Widget card, field, price, notice and actions |
| S06c · Payment received after window | [321:6200](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6200) | 1440 × 1210 | Widget paid notice and product-card instances |
| S06c · Payment received after window | [321:6233](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6233) | 375 × 1194 | Widget paid notice and product-card instances |
| S04-error · Store checkout unavailable | [321:6266](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6266) | 1440 × 900 | Widget status/panel, timer panel and actions |
| S04-error · Store checkout unavailable | [321:6285](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6285) | 375 × 812 | Widget status/panel, timer panel and actions |
| A08-late · Order paid after window | [321:6304](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6304) | 1440 × 900 | RetailerAdmin stacked history and actions |
| A08-late · Order paid after window | [321:6343](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6343) | 375 × 952 | RetailerAdmin stacked history and actions |
| A07-choose-open · Choose a platform · open | [321:6382](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6382) | 1440 × 900 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-choose-open · Choose a platform · open | [321:6410](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6410) | 375 × 812 | RetailerAdmin card, label/input, select, notice and buttons |

## Design-check resolutions

| Review item | Resolution |
| --- | --- |
| 1 | S05a/S05b shopper headings are YOUR CART. State names remain only in Figma annotations and notices. |
| 2 | A07/A09 state subtitles are hidden. A08 has one Orders page heading; its duplicate subtitle and card heading are hidden. Existing IDs remain. |
| 3–4 | Shopper copy uses “this store’s”; the store-name token is consistently `{STORE NAME}`. |
| 5 | The six original cart summary headings are SUMMARY. |
| 6 | Every S03/S05a/S05b line has one outer card with consistent 16px padding (updated in the sizing round). Product and detail groups are transparent, borderless inner groups; no two-card split remains. |
| 7 | The changed-line notice sits immediately after the changed price in the same card. It uses Source Sans 3 SemiBold and the existing ink token. The delivery change is included there. |
| 8 | S06a shows quantity × unit price, “each”, and a line total on all three lines. The earlier register’s claim was ahead of the canvas; the canvas now actually contains those totals. |
| 9 | S06a says ORDER RECEIVED and explicitly names the back-ordered pouch. A08 #1001 says Paid · Includes back order and flags the pouch. Payment confirmation does not claim all fulfilment is complete. |
| 10 | A08 “03:42 left” uses Inter Regular, the admin body face. |
| 11 | #1003 says Unpaid order cancelled, shows $205.00, and explains that the next checkout re-checks price and stock. |
| 12 | The four flagged disabled buttons use ink on the existing light background, with opacity 1. Shopper label contrast is 15.31:1; admin is 16.12:1. |
| 13 | All ten flagged mobile admin buttons and their action rows are now 311px wide, following the sizing round’s 16px page and card insets. |
| 14–15 | S04 shows the five-minute duration and says the window starts at this store’s checkout, with no pre-Continue countdown. S06b uses the same panel treatment for TIME LEFT / 03:42; its page heading is STORE CHECKOUT, leaving one not-completed notice. |
| 16 | A07-choose is a closed select with chevron. A07-choose-open shows its option list. Only Shopify, WooCommerce and BigCommerce appear. The old Other text is hidden only in the original frames to retain its node IDs. It is deleted from the new open-select frames. |
| 17 | Each credential form identifies its own platform admin as the source and Rig admin as the place to type the values. All credential fields remain blank. |
| 18a | S03-empty adds empty cart at both widths. |
| 18b | S05c adds an unavailable-after-recheck line with active Back order / Remove item actions on that line; checkout remains disabled pending that choice. |
| 18c | S05d adds a recheck with no changes, retaining the original price and delivery. |
| 18d | S06c and A08-late add the shopper return and admin row for payment received after the window. The order proceeds at its original total of $205.00. |
| 18e | S04-error adds a store-checkout-unavailable hand-off state with Try again / Back to cart. It says the five-minute window has not started. |
| 18f | Existing S05a now explicitly says the unpaid store order was cancelled before rechecking. |
| 19 | Primitive section `289:13940` is resized to contain all seven source primitives, including `289:13949`, `289:13953` and `289:13957`. |
| 20 | The six FIND A PRODUCT layers and the paid-total/order-history layers named in the review now match their displayed text. |
| 21 | Rig is right-aligned in every shopper header, including the new frames. |
| 22 | A09 has separate minimum and maximum business-day number fields. The preview is “Delivery: 2–3 business days”. Longer delivery comes from Locate ship_days/eta; there is no supplier-delivery setting. |
| 23 | All illustrative values are registered below. Every added frame is linked above. |

## Proposed wording for founder approval

Paid order with an outstanding back order (S06a): **ORDER RECEIVED**. Notice: “Payment was received by {STORE NAME}. Your lens pouch is back ordered; its delivery date is not confirmed.” The item name is a product slot, not fixed product copy.

Credential instructions: “Get this store’s credentials from its Shopify admin, then enter them here in Rig admin. Saved credentials stay hidden.” The WooCommerce and BigCommerce versions name their respective platform admin. These are design proposals; no credential has been typed, read, generated, saved or tested.

Expired unpaid order (S05a): “The unpaid store order was cancelled. We’re checking current prices and stock before checkout can continue.”

Late payment (S06c): “{STORE NAME} received your payment after the 5-minute window ended. Your order is going through. Your lens pouch remains back ordered.”

Hand-off failure (S04-error): “We could not open this store’s checkout. You can try again or return to your cart.” Follow-up: “Prices and stock will be checked again before the next checkout. The 5-minute window has not started.”

Empty, unavailable-line and unchanged-recheck copy in the linked frames is also proposed, not approved. State labels in review bars and frame names are annotations, not shopper/admin headings.

## Every illustrative value is a slot

| Shown value | Slot / meaning |
| --- | --- |
| `{STORE NAME}` | The actual store display name. The one consistent store-name token. |
| COMPACT TRIPOD / “tripod” | Product title slot for the first line. |
| CAMERA STRAP / “strap” | Product title slot for the second line. |
| LENS POUCH / “lens pouch” / “pouch” | Product title slot for the back-ordered line, including notices and admin rows. |
| CT-01, CS-02, LP-03 | Those products’ SKU slots. |
| $120.00, $125.00 | Original and rechecked first-line unit-price slots. |
| $25.00, $35.00 | Second- and third-line unit-price slots. |
| $120.00, $125.00, $50.00, $35.00 | Computed line-total slots: quantity × original unit price. |
| $120.00 | Single-item cart-total slot in the added state. |
| $35.00, $205.00, $210.00 | Illustrative order-amount slots. #1004 uses $35.00; #1005 uses $205.00. Cart totals remain $205.00 original / $210.00 rechecked. |
| Quantity 1, 2, 1 | Editable quantity slots for the three cart lines; the single-item state also uses 1. |
| “3 lines · 4 items” | Computed count slots, not fixed copy for every cart. |
| 2–3 business days | Store-stock minimum/maximum delivery slots; A09’s numeric fields show 2 and 3. |
| 7–10 business days | Per-line longer-delivery slots from the Locate offer; no admin setting is proposed for this. |
| #1001, #1002, #1003, #1004, #1005 | Order-number slots, not real orders. |
| 03:42 / “03:42 left” | Remaining-time slot, shown after checkout starts. |

The five-minute payment window is a product rule, not an editable illustrative setting. Shopify, WooCommerce and BigCommerce are platform choices, not sample stores. Blank credential fields are not example values.

Original arithmetic: $120 + (2 × $25) + $35 = $205. Rechecked arithmetic: $125 + (2 × $25) + $35 = $210. S06a / #1001 uses the rechecked $210 order and still identifies the pouch as back ordered. S06c / A08-late #1002 uses the original $205 order, with $120 first-line unit/line price and 2–3-day delivery. A payment arriving late does not adopt a newer cart’s price.

## Source and style fidelity

The source directories remain `agents/rig/rigbox/quotes/widget`, `agents/rig/rigbox/page` and `workspace/app/rig/admin`. The existing register’s source inspection covered the shipped widget UMD/manifest, store search CSS and markup, and retailer admin TSX/CSS. No matching Code Connect files were found in these directories.

This revision inspected the existing page and its source primitives, and searched the subscribed libraries for Rig cart/checkout and retailer-platform-select composites. No matches were returned. Existing on-page Rig components were reused rather than substituting unrelated kit components.

Shopper frames retain the neutral store skin: Newsreader SemiBold headings, Source Sans 3 body, existing `--rig-*` variables from collection `289:13920`, white cards, ink #1c1e21, canvas #f4f5f7, accent #1d4e89, muted #5c6370, line #d5d8de and 10px radius. The values are the source skin’s fallback; store overrides remain store-owned. No fake logo or product image was introduced.

Admin retains Jost Light / Inter, navy #001840, paper #F4F6FB, line #B8BFD0 and red #E80008 through the existing variables. The flagged timer uses body Inter. The original source primitives remain `289:13941` / `289:13943` (widget buttons), `289:13945` / `289:13947` (admin buttons), `289:13949` / `289:13953` (fields) and `289:13957` (product card).

All content remains editable Figma text, auto-layout containers and source-component instances. No screenshot was flattened into a deliverable. No supplier identity, URL or cost, payment-entry form, card wording, ZA content or EFT flow is present in shopper frames. Rig never takes payment.

## Verification and exact commands

Figma session: `fdb69eb8-048a-49b3-b7d4-148e49e783d2`. Tool calls returned created/mutated IDs. Final structural checks found 52 frames, no missing original frame IDs, all 94 reviewer-referenced IDs present, no visible “your store’s” or mixed-case store token, no horizontal text overflow, all ten flagged button widths 305px, disabled contrasts 15.31:1 / 16.12:1, and no source primitives outside their section. The shopper content check uses word boundaries, so TIME LEFT is not misclassified as EFT.

Composition screenshots were visually inspected for changed cart, paid/back-ordered return, number inputs, open select, cancelled/rechecking, timer return, admin orders, unavailable line, late paid return, checkout failure, hand-off, empty cart and unchanged recheck. Targeted post-fix screenshots confirm active Back order, readable error typography and cancelled admin wording. These are Figma review screenshots, not founder live-store acceptance screenshots.

Exact repository commands for this review:

```sh
git status --short
git branch --show-current
cat AGENTS.md
cat docs/figma/RIG-CART-FRAMES.md
git fetch origin main codex/rig-cart-figma
git merge origin/main
git config user.name 'Codex'
git config user.email 'codex@users.noreply.github.com'
git fetch origin main && git merge origin/main && git push origin codex/rig-cart-figma
git diff --check
git add docs/figma/RIG-CART-FRAMES.md
git commit -m 'docs(figma): register corrected Rig cart proposals and missing states'
git fetch origin main && git merge origin/main && git push origin codex/rig-cart-figma
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git status --short --branch
```

Main refreshes were clean; the intermediate merge push succeeded at `79317ef9`. Final command results are reported in the task. Scripts and audit JSON under `.git/rig-design/` are untracked orchestration, not repository deliverables. No runtime tests were required for this Figma/register-only revision. Claude opens the PR; founder approval and merge are still outstanding.

## Round-2 re-check — all nine items

| Item | Final change |
| --- | --- |
| 1 | The S05c tripod line has “No longer available. Back order it or remove it.” directly after its price, in the existing notice emphasis. The pouch keeps its distinct back-order status. The four specified S05c/S01c line buttons say Remove item; related instructions agree. |
| 2 | Deleted the two hidden full carts, two hidden changed-price messages, two hidden Other options, and six hidden subtitles/headings from the new frames, including their child layers. No hidden stale layers remain in the 14 new frames. Original hidden layers below are not for build. |
| 3 | Every A08/A08-late row’s third line starts with its amount. #1002 is $205.00; #1004 is $35.00; #1005 is $205.00. #1003’s bare timer is replaced with Payment window ended. These amounts are illustrative slots. |
| 4 | All twelve chosen-platform fields in credential/testing/connected/failed frames are closed selects with the same chevron and input treatment as the two original choose fields. The existing open-select option list remains. |
| 5 | S06b and S04-error use STORE CHECKOUT, because these states do not display the cart. |
| 6 | Both paid-order notices use {STORE NAME}. The late-payment notice begins “{STORE NAME} received your payment after the 5-minute window ended.” |
| 7 | The register refers to original total and original unit price. No wording implies that Rig holds a card or takes payment. |
| 8 | All ten remaining summary buttons are exactly the bordered panel’s inner content width: 278px desktop / 301px mobile. The two stale empty-cart summary buttons were deleted with the hidden carts. Left and right insets now match. |
| 9 | A09 helper copy is “Minimum and maximum business days for this store’s own stock. Items sourced from another supplier show that supplier’s longer delivery time.” The internal name is absent from the retailer-visible copy. |

### Original hidden layers — not for build

These 22 original text layers are kept solely for ID continuity. They are excluded from visible layouts and must not be implemented as UI. Deleted layers from new frames are not build references.

| Node ID | Historical layer | Build status |
| --- | --- | --- |
| [291:8061](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8061) | Shop platform · not connected | **Not for build** — hidden solely to preserve an original ID. |
| [291:8068](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8068) | Shopify · WooCommerce · BigCommerce · Other | **Not for build** — hidden solely to preserve an original ID. |
| [291:8083](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8083) | Shop platform · not connected | **Not for build** — hidden solely to preserve an original ID. |
| [291:8090](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8090) | Shopify · WooCommerce · BigCommerce · Other | **Not for build** — hidden solely to preserve an original ID. |
| [291:8105](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8105) | Shopify · enter credentials | **Not for build** — hidden solely to preserve an original ID. |
| [291:8132](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8132) | Shopify · enter credentials | **Not for build** — hidden solely to preserve an original ID. |
| [291:8159](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8159) | WooCommerce · enter credentials | **Not for build** — hidden solely to preserve an original ID. |
| [291:8190](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8190) | WooCommerce · enter credentials | **Not for build** — hidden solely to preserve an original ID. |
| [291:8221](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8221) | BigCommerce · enter credentials | **Not for build** — hidden solely to preserve an original ID. |
| [291:8248](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8248) | BigCommerce · enter credentials | **Not for build** — hidden solely to preserve an original ID. |
| [291:8275](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8275) | Shop platform · testing | **Not for build** — hidden solely to preserve an original ID. |
| [291:8296](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8296) | Shop platform · testing | **Not for build** — hidden solely to preserve an original ID. |
| [291:8317](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8317) | Shop platform · connected | **Not for build** — hidden solely to preserve an original ID. |
| [291:8341](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8341) | Shop platform · connected | **Not for build** — hidden solely to preserve an original ID. |
| [291:8365](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8365) | Shop platform · connection failed | **Not for build** — hidden solely to preserve an original ID. |
| [291:8389](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8389) | Shop platform · connection failed | **Not for build** — hidden solely to preserve an original ID. |
| [291:8413](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8413) | Orders | **Not for build** — hidden solely to preserve an original ID. |
| [291:8415](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8415) | Orders | **Not for build** — hidden solely to preserve an original ID. |
| [291:8452](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8452) | Store delivery time | **Not for build** — hidden solely to preserve an original ID. |
| [291:8472](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8472) | Orders | **Not for build** — hidden solely to preserve an original ID. |
| [291:8474](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8474) | Orders | **Not for build** — hidden solely to preserve an original ID. |
| [291:8511](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8511) | Store delivery time | **Not for build** — hidden solely to preserve an original ID. |

Round-2 verification: 52 frame IDs retained; all 94 round-1 review IDs still resolve; no hidden nodes remain in new frames; no horizontal text overflow; ten summary button widths equal their 278/301px content widths; fourteen closed platform selects plus the two open-select states. Screenshots of S05c mobile, Shopify credentials mobile, A08 mobile and S04-error mobile were inspected after the edits. No runtime code or founder live-store acceptance test is claimed.

Exact final commands for this re-check:

```sh
git status --short --branch
git diff --check
git add docs/figma/RIG-CART-FRAMES.md
git commit -m 'docs(figma): record round-two cart design corrections'
git fetch origin main && git merge origin/main && git push origin codex/rig-cart-figma
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git status --short --branch
git rev-parse HEAD
git rev-parse origin/codex/rig-cart-figma
```

The page remains Proposed, not approved. Founder approval and merge are outstanding.

## Sizing round — founder decision, 3 November 03:20 PT

All 12 items were changed. Existing frame, field, text and action IDs remain. New Workspace-shell children are editable layers; the logo is cloned from the existing CRM raster asset, not redrawn. Admin review bars sit immediately above their screen bounds and remain Figma-only annotations. All screens remain **Proposed, not approved**.

Source references: CRM desktop `94:1061`, mobile `94:1596`, page-title role `94:381` / `94:1204`, card-heading role `288:8508`, back-link role `288:8457`, action `93:4`, field `93:6` / `98:8828`. The font sizes below are bound to the existing `type/size/*` variables with `--cs-type-size-*` WEB syntax; 44 and 35 are line boxes, not font sizes. CRM’s 24px card-heading role and 14px back-link role use auto line height; these proposals explicitly set their requested 35px and 17px boxes.

The shell follows `workspace/app/shell.tsx` and `workspace/app/product-nav.ts` on this branch. `usesOwnShell('/rig/admin')` is false. Retailer navigation, in rendered order, is **Dashboard, Projects, Chats, Squad, Rig, Overview, Ledger, Billing, Tasks, Data, Prices, Settings, CLI sign-ins, Support**. Rig is the section heading; Overview links to `/rig`. The default retailer state has no founder/reviewer-only links. Mobile shows the existing **Menu** control. No navigation copy was invented. Geometry is the founder-requested CRM 240px sidebar, rather than the live CSS’s 256px desktop width; this is a design proposal, not a runtime shell change.

| Item | Changed nodes and new values |
| --- | --- |
| 1 · Shell | All 22 admin frames in the shell map below. Desktop sidebar x=0, width=240; existing content x=240, width=1200, padding=32, inner width=1136. Mobile top bar 375×64, content y=64, page margins=16, inner width=343. |
| 2 · Buttons / accent | `289:13945` and `289:13947`, and all 26 admin action instances listed below: height=44, radius=8. Primary fill is navy `#001840` via `color/text` (`VariableID:42:14`); secondary is white with a navy outline drawn inside its 44px box to avoid clipping. The failed notices `291:8372` / `291:8396` also use navy instead of the stray red accent. No admin paint remains bound to `VariableID:164:17`; there is no Delete action here. |
| 3 · Platform rows | `321:6406` / `321:6434` lists; rows `321:6407`, `321:6408`, `321:6409`, `321:6435`, `321:6436`, `321:6437`: each row box=44 high, 14px Inter / 24px line, vertically centred; list gap=0, padding=8. |
| 4 · Type | All visible admin content text is bound to CRM font-size/family/style variables. Page titles (including `291:8104` / `291:8131`) are Jost Light 34px / 44px line; card headings (including `291:8107`) 24px / 35px line. Back links (including `291:8102`) Inter 14px / 17px. Order heading `291:8417` is 15px / 24px; status `291:8418` 14px / 24px; metadata `291:8419` 13px / 17px. Fields use 14px / 24px; buttons 13px / 17px Semi Bold; YOUR STORE is 12px / 17px. All equivalent roles follow these values. |
| 5 · Fields / cards | Field primitive `289:13953` / label `289:13954` / value group `289:13955` / value `289:13956`, all 34 instances, and 22 record cards listed below: white surfaces, radius=8. Field labels are inside their bordered outer box, padding=16, gap=8, height=88; old inner input boxes have no separate border/padding. Record cards have no stroke. Credential values remain blank. |
| 6 · Spacing | All 22 content stacks in the shell map: gap=24. All 22 record cards: padding=24 desktop / 16 mobile; internal gap=16. Actions use gap=16; notices use padding=16/gap=8. `291:8102` → `291:8103` → `291:8104` → `291:8106` now has 24px gaps. |
| 7 · Equal widths | `291:8106` is 1136 wide with padding=24 and no stroke; `291:8107`, `291:8108`, `291:8112`, `291:8116`, `291:8120`, `291:8121` are all x=24, width=1088. The corresponding mobile card `291:8133` is 343 wide with 16px padding and 311px children. All equivalent card children fill the same available width. |
| 8 · Chevron | All 16 chevron frames listed below: 16×16, 16px inset from the select’s right edge, centred on its value line. Closed `354:18492` and open `321:6400` both x=1080/y=127 in the desktop card; closed `354:18494` and open `321:6428` both x=295/y=119 on mobile. The 8×4 glyph stays at x=4/y=6 within each frame. |
| 9 · Frame sizes | All 52 root frames in the current frame register use a 1440×900 or 375×812 minimum; only content requiring more height extends. All 11 admin desktop frames are 1440×900. Admin mobile exceptions: WooCommerce `291:8182`=375×856, Orders `291:8464`=375×935, late Orders `321:6343`=375×952. Existing shopper cart/order states retain the larger content heights listed above. |
| 10 · Shopper consistency | `289:13941` / `289:13943` and all 72 shopper action instances below: height=48. All 30 cart-line outer cards and all 18 shopper summary/status panels use padding=16, with strokes outside the content inset; examples `291:174` / `291:216`. Transparent product/detail inner groups keep padding=0. All 30 `.part details` gaps, including `291:180`, are 8. Summary buttons fill the updated content width: 288 desktop / 311 mobile; `291:220` / `291:280` match their new 16px panel insets. |
| 11 · Centre widget | All 15 desktop widget shells listed below are width=1200 at x=120 in their 1440 frames, including `291:13` / `291:167`. The 15 mobile shells remain width=375 at x=0 because they already span the viewport. |
| 12 · Field edges | New `--rig-field-border` (`VariableID:440:499`), value `#8b919a`, scope STROKE_COLOR, WEB `var(--rig-field-border)`. Bound to primitive stroke `289:13951` and all 30 widget field instance strokes listed below. Contrast is 3.17:1 against `#ffffff` (at least 3:1). Other shopper brand tokens remain `--rig-*`. |

### Admin shell map — item 1 and spacing scope

| Screen root | Existing content | New shell | Screen size |
| --- | --- | --- | --- |
| [291:8053](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8053) | `291:8057` | `441:499` | 1440 × 900 |
| [291:8075](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8075) | `291:8079` | `441:530` | 375 × 812 |
| [291:8097](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8097) | `291:8101` | `441:533` | 1440 × 900 |
| [291:8124](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8124) | `291:8128` | `441:564` | 375 × 812 |
| [291:8151](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8151) | `291:8155` | `441:567` | 1440 × 900 |
| [291:8182](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8182) | `291:8186` | `441:598` | 375 × 856 |
| [291:8213](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8213) | `291:8217` | `441:601` | 1440 × 900 |
| [291:8240](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8240) | `291:8244` | `441:632` | 375 × 812 |
| [291:8267](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8267) | `291:8271` | `441:635` | 1440 × 900 |
| [291:8288](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8288) | `291:8292` | `441:666` | 375 × 812 |
| [291:8309](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8309) | `291:8313` | `441:669` | 1440 × 900 |
| [291:8333](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8333) | `291:8337` | `441:700` | 375 × 812 |
| [291:8357](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8357) | `291:8361` | `441:703` | 1440 × 900 |
| [291:8381](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8381) | `291:8385` | `441:734` | 375 × 812 |
| [291:8405](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8405) | `291:8409` | `441:737` | 1440 × 900 |
| [291:8444](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8444) | `291:8448` | `441:768` | 1440 × 900 |
| [291:8464](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8464) | `291:8468` | `441:799` | 375 × 935 |
| [291:8503](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8503) | `291:8507` | `441:802` | 375 × 812 |
| [321:6304](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6304) | `321:6308` | `441:805` | 1440 × 900 |
| [321:6343](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6343) | `321:6347` | `441:836` | 375 × 952 |
| [321:6382](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6382) | `321:6386` | `441:839` | 1440 × 900 |
| [321:6410](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6410) | `321:6414` | `441:870` | 375 × 812 |

### CRM type bindings — item 4

| Role | Existing variable | WEB syntax | Size / line box |
| --- | --- | --- | --- |
| Page title | `VariableID:42:42` · type/size/34 | `--cs-type-size-34` | 34 / 44 |
| Card heading | `VariableID:42:41` · type/size/24 | `--cs-type-size-24` | 24 / 35 |
| Back link; body/field | `VariableID:42:37` · type/size/14 | `--cs-type-size-14` | 14 / 17; 14 / 24 |
| Order heading | `VariableID:42:38` · type/size/15 | `--cs-type-size-15` | 15 / 24 |
| Metadata/helper/button | `VariableID:42:36` · type/size/13 | `--cs-type-size-13` | 13 / 17 |
| Kicker | `VariableID:42:35` · type/size/12 | `--cs-type-size-12` | 12 / 17 |

Heading family/style binds `VariableID:42:46` / `42:48`; body family binds `42:47`, with regular `42:49`, medium `42:50` or semibold `42:51` as appropriate. Shopper text retains its store theme and is not converted to Jost/Inter.

### Changed node inventory by item

Lists identify the complete affected instance/container scope; their existing child text and glyph IDs are retained. Inherited primitive changes also affect their corresponding instance descendants.

**2 · Admin actions:** `291:8073`, `291:8095`, `291:8122`, `291:8149`, `291:8180`, `291:8211`, `291:8238`, `291:8265`, `291:8286`, `291:8307`, `291:8329`, `291:8331`, `291:8353`, `291:8355`, `291:8377`, `291:8379`, `291:8401`, `291:8403`, `291:8441`, `291:8462`, `291:8500`, `291:8521`, `321:6340`, `321:6379`, `321:6399`, `321:6427`.

**4 · Admin text nodes (including new shell labels):** `291:8058`, `291:8059`, `291:8060`, `291:8063`, `I291:8064;289:13954`, `I291:8064;289:13956`, `291:8070`, `291:8071`, `I291:8073;289:13946`, `441:503`, `441:505`, `441:507`, `441:509`, `441:511`, `441:513`, `441:515`, `441:517`, `441:519`, `441:521`, `441:523`, `441:525`, `441:527`, `441:529`, `291:8080`, `291:8081`, `291:8082`, `291:8085`, `I291:8086;289:13954`, `I291:8086;289:13956`, `291:8092`, `291:8093`, `I291:8095;289:13946`, `441:532`, `291:8102`, `291:8103`, `291:8104`, `291:8107`, `I291:8108;289:13954`, `I291:8108;289:13956`, `I291:8112;289:13954`, `I291:8112;289:13956`, `I291:8116;289:13954`, `I291:8116;289:13956`, `291:8120`, `I291:8122;289:13946`, `441:537`, `441:539`, `441:541`, `441:543`, `441:545`, `441:547`, `441:549`, `441:551`, `441:553`, `441:555`, `441:557`, `441:559`, `441:561`, `441:563`, `291:8129`, `291:8130`, `291:8131`, `291:8134`, `I291:8135;289:13954`, `I291:8135;289:13956`, `I291:8139;289:13954`, `I291:8139;289:13956`, `I291:8143;289:13954`, `I291:8143;289:13956`, `291:8147`, `I291:8149;289:13946`, `441:566`, `291:8156`, `291:8157`, `291:8158`, `291:8161`, `I291:8162;289:13954`, `I291:8162;289:13956`, `I291:8166;289:13954`, `I291:8166;289:13956`, `I291:8170;289:13954`, `I291:8170;289:13956`, `I291:8174;289:13954`, `I291:8174;289:13956`, `291:8178`, `I291:8180;289:13946`, `441:571`, `441:573`, `441:575`, `441:577`, `441:579`, `441:581`, `441:583`, `441:585`, `441:587`, `441:589`, `441:591`, `441:593`, `441:595`, `441:597`, `291:8187`, `291:8188`, `291:8189`, `291:8192`, `I291:8193;289:13954`, `I291:8193;289:13956`, `I291:8197;289:13954`, `I291:8197;289:13956`, `I291:8201;289:13954`, `I291:8201;289:13956`, `I291:8205;289:13954`, `I291:8205;289:13956`, `291:8209`, `I291:8211;289:13946`, `441:600`, `291:8218`, `291:8219`, `291:8220`, `291:8223`, `I291:8224;289:13954`, `I291:8224;289:13956`, `I291:8228;289:13954`, `I291:8228;289:13956`, `I291:8232;289:13954`, `I291:8232;289:13956`, `291:8236`, `I291:8238;289:13946`, `441:605`, `441:607`, `441:609`, `441:611`, `441:613`, `441:615`, `441:617`, `441:619`, `441:621`, `441:623`, `441:625`, `441:627`, `441:629`, `441:631`, `291:8245`, `291:8246`, `291:8247`, `291:8250`, `I291:8251;289:13954`, `I291:8251;289:13956`, `I291:8255;289:13954`, `I291:8255;289:13956`, `I291:8259;289:13954`, `I291:8259;289:13956`, `291:8263`, `I291:8265;289:13946`, `441:634`, `291:8272`, `291:8273`, `291:8274`, `291:8277`, `I291:8278;289:13954`, `I291:8278;289:13956`, `291:8283`, `291:8284`, `291:8285`, `I291:8286;289:13946`, `441:639`, `441:641`, `441:643`, `441:645`, `441:647`, `441:649`, `441:651`, `441:653`, `441:655`, `441:657`, `441:659`, `441:661`, `441:663`, `441:665`, `291:8293`, `291:8294`, `291:8295`, `291:8298`, `I291:8299;289:13954`, `I291:8299;289:13956`, `291:8304`, `291:8305`, `291:8306`, `I291:8307;289:13946`, `441:668`, `291:8314`, `291:8315`, `291:8316`, `291:8319`, `I291:8320;289:13954`, `I291:8320;289:13956`, `291:8325`, `291:8326`, `291:8327`, `I291:8329;289:13946`, `I291:8331;289:13948`, `441:673`, `441:675`, `441:677`, `441:679`, `441:681`, `441:683`, `441:685`, `441:687`, `441:689`, `441:691`, `441:693`, `441:695`, `441:697`, `441:699`, `291:8338`, `291:8339`, `291:8340`, `291:8343`, `I291:8344;289:13954`, `I291:8344;289:13956`, `291:8349`, `291:8350`, `291:8351`, `I291:8353;289:13946`, `I291:8355;289:13948`, `441:702`, `291:8362`, `291:8363`, `291:8364`, `291:8367`, `I291:8368;289:13954`, `I291:8368;289:13956`, `291:8373`, `291:8374`, `291:8375`, `I291:8377;289:13946`, `I291:8379;289:13948`, `441:707`, `441:709`, `441:711`, `441:713`, `441:715`, `441:717`, `441:719`, `441:721`, `441:723`, `441:725`, `441:727`, `441:729`, `441:731`, `441:733`, `291:8386`, `291:8387`, `291:8388`, `291:8391`, `I291:8392;289:13954`, `I291:8392;289:13956`, `291:8397`, `291:8398`, `291:8399`, `I291:8401;289:13946`, `I291:8403;289:13948`, `441:736`, `291:8410`, `291:8411`, `291:8412`, `291:8417`, `291:8418`, `291:8419`, `291:8422`, `291:8423`, `291:8424`, `291:8427`, `291:8428`, `291:8429`, `291:8432`, `291:8433`, `291:8434`, `291:8437`, `291:8438`, `291:8439`, `I291:8441;289:13946`, `441:741`, `441:743`, `441:745`, `441:747`, `441:749`, `441:751`, `441:753`, `441:755`, `441:757`, `441:759`, `441:761`, `441:763`, `441:765`, `441:767`, `291:8449`, `291:8450`, `291:8451`, `291:8454`, `I291:8455;289:13954`, `I291:8455;289:13956`, `I318:48336;289:13954`, `I318:48336;289:13956`, `291:8459`, `291:8460`, `I291:8462;289:13946`, `441:772`, `441:774`, `441:776`, `441:778`, `441:780`, `441:782`, `441:784`, `441:786`, `441:788`, `441:790`, `441:792`, `441:794`, `441:796`, `441:798`, `291:8469`, `291:8470`, `291:8471`, `291:8476`, `291:8477`, `291:8478`, `291:8481`, `291:8482`, `291:8483`, `291:8486`, `291:8487`, `291:8488`, `291:8491`, `291:8492`, `291:8493`, `291:8496`, `291:8497`, `291:8498`, `I291:8500;289:13946`, `441:801`, `291:8508`, `291:8509`, `291:8510`, `291:8513`, `I291:8514;289:13954`, `I291:8514;289:13956`, `I318:48340;289:13954`, `I318:48340;289:13956`, `291:8518`, `291:8519`, `I291:8521;289:13946`, `441:804`, `321:6309`, `321:6310`, `321:6311`, `321:6316`, `321:6317`, `321:6318`, `321:6321`, `321:6322`, `321:6323`, `321:6326`, `321:6327`, `321:6328`, `321:6331`, `321:6332`, `321:6333`, `321:6336`, `321:6337`, `321:6338`, `I321:6340;289:13946`, `441:809`, `441:811`, `441:813`, `441:815`, `441:817`, `441:819`, `441:821`, `441:823`, `441:825`, `441:827`, `441:829`, `441:831`, `441:833`, `441:835`, `321:6348`, `321:6349`, `321:6350`, `321:6355`, `321:6356`, `321:6357`, `321:6360`, `321:6361`, `321:6362`, `321:6365`, `321:6366`, `321:6367`, `321:6370`, `321:6371`, `321:6372`, `321:6375`, `321:6376`, `321:6377`, `I321:6379;289:13946`, `441:838`, `321:6387`, `321:6388`, `321:6389`, `321:6392`, `I321:6393;289:13954`, `I321:6393;289:13956`, `321:6407`, `321:6408`, `321:6409`, `321:6396`, `321:6397`, `I321:6399;289:13946`, `441:843`, `441:845`, `441:847`, `441:849`, `441:851`, `441:853`, `441:855`, `441:857`, `441:859`, `441:861`, `441:863`, `441:865`, `441:867`, `441:869`, `321:6415`, `321:6416`, `321:6417`, `321:6420`, `I321:6421;289:13954`, `I321:6421;289:13956`, `321:6435`, `321:6436`, `321:6437`, `321:6424`, `321:6425`, `I321:6427;289:13946`, `441:872`.

**5 · Field instances:** `291:8064`, `291:8086`, `291:8108`, `291:8112`, `291:8116`, `291:8135`, `291:8139`, `291:8143`, `291:8162`, `291:8166`, `291:8170`, `291:8174`, `291:8193`, `291:8197`, `291:8201`, `291:8205`, `291:8224`, `291:8228`, `291:8232`, `291:8251`, `291:8255`, `291:8259`, `291:8278`, `291:8299`, `291:8320`, `291:8344`, `291:8368`, `291:8392`, `291:8455`, `318:48336`, `291:8514`, `318:48340`, `321:6393`, `321:6421`.

**5–7 · Record cards:** `291:8062`, `291:8084`, `291:8106`, `291:8133`, `291:8160`, `291:8191`, `291:8222`, `291:8249`, `291:8276`, `291:8297`, `291:8318`, `291:8342`, `291:8366`, `291:8390`, `291:8414`, `291:8453`, `291:8473`, `291:8512`, `321:6313`, `321:6352`, `321:6391`, `321:6419`.

**8 · Chevron frames:** `318:48344`, `318:48346`, `354:18492`, `354:18494`, `354:18496`, `354:18498`, `354:18500`, `354:18502`, `354:18504`, `354:18506`, `354:18508`, `354:18510`, `354:18512`, `354:18514`, `321:6400`, `321:6428`.

**10 · Shopper action instances:** `291:24`, `291:41`, `291:58`, `291:75`, `291:92`, `291:94`, `291:112`, `291:114`, `291:136`, `291:138`, `291:159`, `291:161`, `291:186`, `291:200`, `291:214`, `291:220`, `291:246`, `291:260`, `291:274`, `291:280`, `291:298`, `291:300`, `291:317`, `291:319`, `291:347`, `291:361`, `291:375`, `291:381`, `291:410`, `291:424`, `291:438`, `291:444`, `291:474`, `291:488`, `291:502`, `291:508`, `291:538`, `291:552`, `291:566`, `291:572`, `291:596`, `291:619`, `291:636`, `291:638`, `291:655`, `291:657`, `318:60990`, `318:61056`, `318:61121`, `318:61074`, `318:61080`, `318:61086`, `318:61091`, `318:61186`, `318:61139`, `318:61145`, `318:61151`, `318:61156`, `318:61208`, `318:61214`, `318:61220`, `318:61225`, `318:61272`, `318:61278`, `318:61284`, `318:61289`, `321:6219`, `321:6252`, `321:6281`, `321:6282`, `321:6300`, `321:6301`.

**10 · Shopper outer cards/panels:** `291:174`, `291:188`, `291:202`, `291:216`, `291:234`, `291:248`, `291:262`, `291:276`, `291:292`, `291:311`, `291:335`, `291:349`, `291:363`, `291:377`, `291:398`, `291:412`, `291:426`, `291:440`, `291:461`, `291:476`, `291:490`, `291:504`, `291:525`, `291:540`, `291:554`, `291:568`, `291:587`, `291:610`, `318:61069`, `318:61075`, `318:61081`, `318:61087`, `318:61134`, `318:61140`, `318:61146`, `318:61152`, `318:61202`, `318:61209`, `318:61215`, `318:61221`, `318:61266`, `318:61273`, `318:61279`, `318:61285`, `321:6212`, `321:6245`, `321:6275`, `321:6294`.

**10 · Shopper detail groups:** `291:180`, `291:194`, `291:208`, `291:240`, `291:254`, `291:268`, `291:341`, `291:355`, `291:369`, `291:404`, `291:418`, `291:432`, `291:467`, `291:482`, `291:496`, `291:531`, `291:546`, `291:560`, `318:61071`, `318:61077`, `318:61083`, `318:61136`, `318:61142`, `318:61148`, `318:61204`, `318:61211`, `318:61217`, `318:61268`, `318:61275`, `318:61281`.

**11 · Centred desktop widget shells:** `291:13`, `291:47`, `291:81`, `291:121`, `291:167`, `291:287`, `291:325`, `291:451`, `291:579`, `291:625`, `318:60930`, `318:61062`, `318:61192`, `321:6204`, `321:6270`.

**12 · Bound widget field strokes:** `I291:181;289:13951`, `I291:195;289:13951`, `I291:209;289:13951`, `I291:241;289:13951`, `I291:255;289:13951`, `I291:269;289:13951`, `I291:342;289:13951`, `I291:356;289:13951`, `I291:370;289:13951`, `I291:405;289:13951`, `I291:419;289:13951`, `I291:433;289:13951`, `I291:468;289:13951`, `I291:483;289:13951`, `I291:497;289:13951`, `I291:532;289:13951`, `I291:547;289:13951`, `I291:561;289:13951`, `I318:61072;289:13951`, `I318:61078;289:13951`, `I318:61084;289:13951`, `I318:61137;289:13951`, `I318:61143;289:13951`, `I318:61149;289:13951`, `I318:61206;289:13951`, `I318:61212;289:13951`, `I318:61218;289:13951`, `I318:61270;289:13951`, `I318:61276;289:13951`, `I318:61282;289:13951`.

### Sizing verification and commands

Canvas audit: all 52 roots retained; 22 admin shell/content pairs; 26 admin action instances at 44px/radius 8; 72 shopper action instances at 48px; 34 admin field instances; 22 borderless record cards; six 44px option rows; 16 aligned chevrons; 30 widget field strokes bound to the new token. All visible admin content text has a CRM size binding. No remaining red accent binding in any admin frame, no wrong-colour primary, and no horizontal child overflow. The desktop and mobile Shopify credential frames, mobile open select, shopper cart, mobile Orders and failed-connection screenshots were inspected. The secondary-button inside stroke was verified after correcting outline clipping. These are design checks, not founder acceptance screenshots or runtime tests.

```sh
git fetch origin && git merge origin/main
python3 .git/rig-design/document-sizing.py
git diff --check
git diff --name-only origin/main...HEAD
git add docs/figma/RIG-CART-FRAMES.md
git commit -m 'docs(figma): record all twelve Rig cart sizing corrections'
git fetch origin && git merge origin/main
git push origin codex/rig-cart-figma
git rev-parse HEAD
git ls-remote origin refs/heads/codex/rig-cart-figma
git status --short --branch
```

The first fetch/merge was already up to date. The register is the only repository deliverable; scripts/audits in `.git/rig-design` are untracked orchestration. Final push/remote-head results are reported in the task. No runtime code, credential, production data or deployment changed. Founder approval and merge remain outstanding.


## Final seven corrections — 3 November 2026

**Proposed, not approved.** This section supersedes the earlier sizing-round values for the listed roles. Existing node IDs are retained; shopper theme variables are unchanged.

### 1. Admin field edges

`cs/field-border` (`VariableID:452:499`), `#8b919a`, STROKE_COLOR, 3.17:1 on white. Separate from shopper `--rig-field-border`.

Nodes: `289:13953`, `291:8064`, `291:8086`, `291:8108`, `291:8112`, `291:8116`, `291:8135`, `291:8139`, `291:8143`, `291:8162`, `291:8166`, `291:8170`, `291:8174`, `291:8193`, `291:8197`, `291:8201`, `291:8205`, `291:8224`, `291:8228`, `291:8232`, `291:8251`, `291:8255`, `291:8259`, `291:8278`, `291:8299`, `291:8320`, `291:8344`, `291:8368`, `291:8392`, `291:8455`, `318:48336`, `291:8514`, `318:48340`, `321:6393`, `321:6421`, `321:6406`, `321:6434`.

### 2. Field geometry

Stroke INSIDE; outer height 88; radius 8; padding 16 on every side.

Nodes: `289:13953`, `291:8064`, `291:8086`, `291:8108`, `291:8112`, `291:8116`, `291:8135`, `291:8139`, `291:8143`, `291:8162`, `291:8166`, `291:8170`, `291:8174`, `291:8193`, `291:8197`, `291:8201`, `291:8205`, `291:8224`, `291:8228`, `291:8232`, `291:8251`, `291:8255`, `291:8259`, `291:8278`, `291:8299`, `291:8320`, `291:8344`, `291:8368`, `291:8392`, `291:8455`, `318:48336`, `291:8514`, `318:48340`, `321:6393`, `321:6421`.

### 3. Chevrons

No change, as directed: desktop centre y=135, mobile y=127. Representative closed/open frames retain x/y=1080/127 desktop and 295/119 mobile.

Nodes: `354:18492`, `354:18494`, `321:6400`, `321:6428`.

### 4. Order headings

Inter Semi Bold 14/24; font size bound to CRM `VariableID:42:37`.

Nodes: `291:8417`, `291:8422`, `291:8427`, `291:8432`, `291:8437`, `291:8476`, `291:8481`, `291:8486`, `291:8491`, `291:8496`, `321:6316`, `321:6321`, `321:6326`, `321:6331`, `321:6336`, `321:6355`, `321:6360`, `321:6365`, `321:6370`, `321:6375`.

### 5. Metadata and helpers

Inter Regular 14/24; size `VariableID:42:37`, secondary colour `VariableID:42:15` (`#3d4a66`).

Nodes: `291:8120`, `291:8147`, `291:8178`, `291:8209`, `291:8236`, `291:8263`, `291:8419`, `291:8424`, `291:8429`, `291:8434`, `291:8439`, `291:8478`, `291:8483`, `291:8488`, `291:8493`, `291:8498`, `321:6318`, `321:6323`, `321:6328`, `321:6333`, `321:6338`, `321:6357`, `321:6362`, `321:6367`, `321:6372`, `321:6377`.

### 6. Kickers and Rig section labels

Inter Semi Bold 12/20; size `VariableID:42:35`, style `42:51`, secondary colour `42:15` (`#3d4a66`).

Nodes: `291:8059`, `441:511`, `291:8081`, `291:8103`, `441:545`, `291:8130`, `291:8157`, `441:579`, `291:8188`, `291:8219`, `441:613`, `291:8246`, `291:8273`, `441:647`, `291:8294`, `291:8315`, `441:681`, `291:8339`, `291:8363`, `441:715`, `291:8387`, `291:8411`, `441:749`, `291:8470`, `291:8450`, `441:780`, `291:8509`, `321:6310`, `441:817`, `321:6349`, `321:6388`, `441:851`, `321:6416`.

### 7. Action labels

Inter Semi Bold 13/18; size `VariableID:42:36`, style `42:51`. Buttons remain 44 tall.

Nodes: `289:13946`, `289:13948`, `I291:8073;289:13946`, `I291:8095;289:13946`, `I291:8122;289:13946`, `I291:8149;289:13946`, `I291:8180;289:13946`, `I291:8211;289:13946`, `I291:8238;289:13946`, `I291:8265;289:13946`, `I291:8286;289:13946`, `I291:8307;289:13946`, `I291:8329;289:13946`, `I291:8331;289:13948`, `I291:8353;289:13946`, `I291:8355;289:13948`, `I291:8377;289:13946`, `I291:8379;289:13948`, `I291:8401;289:13946`, `I291:8403;289:13948`, `I291:8441;289:13946`, `I291:8500;289:13946`, `I291:8462;289:13946`, `I291:8521;289:13946`, `I321:6340;289:13946`, `I321:6379;289:13946`, `I321:6399;289:13946`, `I321:6427;289:13946`.

The larger text line boxes require height-only extensions: `291:8182` → 375 × 880; `291:8405` → 1440 × 906; `291:8464` → 375 × 1018; `321:6304` → 1440 × 906; `321:6343` → 375 × 1042. Other root dimensions stay unchanged. Desktop Shopify credentials (`291:8097`) and mobile late Orders (`321:6343`) screenshots were inspected: no cropped text or overlapping rows. These are design verification screenshots, not founder acceptance.

Commands: `git fetch origin && git merge origin/main` completed successfully with a clean merge; `git diff --check` passed. The register was committed and pushed with `git add docs/figma/RIG-CART-FRAMES.md`, `git commit -m 'docs(figma): record final seven Rig cart corrections'`, `git fetch origin && git merge origin/main`, and `git push origin codex/rig-cart-figma`. No runtime tests apply to this documentation/design-only change. Founder approval remains outstanding.

## Final geometry corrections and CRM reference stop — 3 November 2026

**Proposed, not approved.** Node IDs are preserved. This section supersedes the previous open-chevron coordinate interpretation.

| Item | Nodes | Result |
| --- | --- | --- |
| 1 | `321:6400` | Rotation remains 180°. Pivot x/y = **1096/143**; rendered 16×16 bounds start at **1080/127**, centre y = **135**. |
| 2 | `321:6428` | Rotation remains 180°. Pivot x/y = **311/135**; rendered 16×16 bounds start at **295/119**, centre y = **127**. |
| 3 | `441:737`, `441:805` | Both navy sidebars are **240×906**, matching their enclosing frames `291:8405` and `321:6304`. |
| 4 | `441:511`, `441:545`, `441:579`, `441:613`, `441:647`, `441:681`, `441:715`, `441:749`, `441:780`, `441:817`, `441:851` | **Blocked; unchanged.** The specified CRM reference does not currently supply the requested colour on navy. |

For rotated open chevrons, Figma x/y denotes the pivot position, not the rendered top-left. Desktop and mobile open-select screenshots were inspected after correcting these pivots.

Item 4 source inspection: frame `94:1061` is currently named **Leads / Detail / Desktop / Filled · Changed after approval, awaiting founder**. Its `182:9119` navigation instance has a **white** fill, bound to `VariableID:42:13`. Its CRM section label `I182:9119;180:8405` (and Writing, Sales, Marketing, Chat bot section labels) uses `VariableID:42:15`, **#3d4a66**, at opacity 1. The ancestor chain has no navy background. That reference therefore cannot supply a matching CRM section-label colour meeting 4.5:1 on #001840. Rule 9 stop: the missing input is a CRM navy-sidebar section-label colour/reference meeting the specified contrast. No replacement colour was invented. Rig section labels retain 12/20 Semi Bold; light-background kickers remain unchanged.

Verification: Figma returned all four mutated node IDs and their new geometry; desktop/mobile open-select screenshots were inspected. `git fetch origin && git merge origin/main` was run before the documentation commit/push. `git diff --check` verifies the register. No runtime code or production data changed. No founder acceptance is claimed.
