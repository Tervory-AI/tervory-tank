# Rig cart (US) — Proposed, not approved

Page: [10 · Rig cart (US)](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=289-13919), node `289:13919`. Branch: `codex/rig-cart-figma`. Design-check revision: 3 November 2026.

All 52 frames and their review bars remain **Proposed, not approved**. Copy below is proposed for founder approval. Illustrative values exist only in Figma, not on a live screen. This branch changes only this register relative to main; no widget, admin, payment, credential or other runtime code is changed.

## Frame register

The original 38 frame IDs are retained. All 94 distinct node IDs named in the review still resolve, including text removed from visible layouts by hiding it. Fourteen additional frames cover seven desktop/mobile pairs. Heights below come from the final canvas, not the original generator.

| Screen | Node ID | Size | Existing source reused |
| --- | --- | --- | --- |
| S01a · Product · store stock | [291:9](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-9) | 1440 × 960 | Widget product/chosen card, price and actions |
| S01a · Product · store stock | [291:26](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-26) | 375 × 960 | Widget product/chosen card, price and actions |
| S01b · Product · longer delivery | [291:43](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-43) | 1440 × 960 | Widget product/chosen card, price and actions |
| S01b · Product · longer delivery | [291:60](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-60) | 375 × 960 | Widget product/chosen card, price and actions |
| S01c · Product · back order | [291:77](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-77) | 1440 × 960 | Widget product/chosen card, price and actions |
| S01c · Product · back order | [291:97](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-97) | 375 × 960 | Widget product/chosen card, price and actions |
| S02 · Item added to cart | [291:117](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-117) | 1440 × 960 | Widget product/chosen card, price and actions |
| S02 · Item added to cart | [291:140](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-140) | 375 × 960 | Widget product/chosen card, price and actions |
| S03 · Your cart | [291:163](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-163) | 1440 × 1393 | Widget card, field, price, notice and actions |
| S03 · Your cart | [291:223](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-223) | 375 × 1616 | Widget card, field, price, notice and actions |
| S04 · Going to store checkout | [291:283](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-283) | 1440 × 960 | Widget status/panel, timer panel and actions |
| S04 · Going to store checkout | [291:302](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-302) | 375 × 960 | Widget status/panel, timer panel and actions |
| S05a · Payment window ended · rechecking | [291:321](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-321) | 1440 × 1501 | Widget card, field, price, notice and actions |
| S05a · Payment window ended · rechecking | [291:384](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-384) | 375 × 1781 | Widget card, field, price, notice and actions |
| S05b · Cart rechecked · changes found | [291:447](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-447) | 1440 × 1517 | Widget card, field, price, notice and actions |
| S05b · Cart rechecked · changes found | [291:511](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-511) | 375 × 1797 | Widget card, field, price, notice and actions |
| S06a · Paid order with back order | [291:575](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-575) | 1440 × 1222 | Widget paid notice and product-card instances |
| S06a · Paid order with back order | [291:598](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-598) | 375 × 1206 | Widget paid notice and product-card instances |
| S06b · Checkout not completed | [291:621](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-621) | 1440 × 960 | Widget status/panel, timer panel and actions |
| S06b · Checkout not completed | [291:640](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-640) | 375 × 960 | Widget status/panel, timer panel and actions |
| A07-choose · Shop platform · not connected | [291:8053](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8053) | 1440 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-choose · Shop platform · not connected | [291:8075](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8075) | 375 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-shopify · Shopify · enter credentials | [291:8097](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8097) | 1440 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-shopify · Shopify · enter credentials | [291:8124](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8124) | 375 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-woo · WooCommerce · enter credentials | [291:8151](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8151) | 1440 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-woo · WooCommerce · enter credentials | [291:8182](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8182) | 375 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-big · BigCommerce · enter credentials | [291:8213](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8213) | 1440 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-big · BigCommerce · enter credentials | [291:8240](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8240) | 375 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-testing · Shop platform · testing | [291:8267](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8267) | 1440 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-testing · Shop platform · testing | [291:8288](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8288) | 375 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-connected · Shop platform · connected | [291:8309](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8309) | 1440 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-connected · Shop platform · connected | [291:8333](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8333) | 375 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-failed · Shop platform · connection failed | [291:8357](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8357) | 1440 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-failed · Shop platform · connection failed | [291:8381](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8381) | 375 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A08 · Orders | [291:8405](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8405) | 1440 × 960 | RetailerAdmin stacked history and actions |
| A09 · Store delivery time | [291:8444](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8444) | 1440 × 960 | RetailerAdmin numeric label/inputs and preview |
| A08 · Orders | [291:8464](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8464) | 375 × 960 | RetailerAdmin stacked history and actions |
| A09 · Store delivery time | [291:8503](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8503) | 375 × 960 | RetailerAdmin numeric label/inputs and preview |
| S03-empty · Empty cart | [318:60926](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-60926) | 1440 × 960 | Widget card, field, price, notice and actions |
| S03-empty · Empty cart | [318:60992](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-60992) | 375 × 960 | Widget card, field, price, notice and actions |
| S05c · Item unavailable after recheck | [318:61058](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-61058) | 1440 × 1561 | Widget card, field, price, notice and actions |
| S05c · Item unavailable after recheck | [318:61123](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-61123) | 375 × 1821 | Widget card, field, price, notice and actions |
| S05d · Cart rechecked without changes | [318:61188](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-61188) | 1440 × 1497 | Widget card, field, price, notice and actions |
| S05d · Cart rechecked without changes | [318:61252](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=318-61252) | 375 × 1757 | Widget card, field, price, notice and actions |
| S06c · Payment received after window | [321:6200](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6200) | 1440 × 1222 | Widget paid notice and product-card instances |
| S06c · Payment received after window | [321:6233](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6233) | 375 × 1206 | Widget paid notice and product-card instances |
| S04-error · Store checkout unavailable | [321:6266](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6266) | 1440 × 960 | Widget status/panel, timer panel and actions |
| S04-error · Store checkout unavailable | [321:6285](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6285) | 375 × 960 | Widget status/panel, timer panel and actions |
| A08-late · Order paid after window | [321:6304](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6304) | 1440 × 960 | RetailerAdmin stacked history and actions |
| A08-late · Order paid after window | [321:6343](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6343) | 375 × 961 | RetailerAdmin stacked history and actions |
| A07-choose-open · Choose a platform · open | [321:6382](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6382) | 1440 × 960 | RetailerAdmin card, label/input, select, notice and buttons |
| A07-choose-open · Choose a platform · open | [321:6410](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=321-6410) | 375 × 960 | RetailerAdmin card, label/input, select, notice and buttons |

## Design-check resolutions

| Review item | Resolution |
| --- | --- |
| 1 | S05a/S05b shopper headings are YOUR CART. State names remain only in Figma annotations and notices. |
| 2 | A07/A09 state subtitles are hidden. A08 has one Orders page heading; its duplicate subtitle and card heading are hidden. Existing IDs remain. |
| 3–4 | Shopper copy uses “this store’s”; the store-name token is consistently `{STORE NAME}`. |
| 5 | The six original cart summary headings are SUMMARY. |
| 6 | Every S03/S05a/S05b line has one outer card with consistent 18px padding. Product and detail groups are transparent, borderless inner groups; no two-card split remains. |
| 7 | The changed-line notice sits immediately after the changed price in the same card. It uses Source Sans 3 SemiBold and the existing ink token. The delivery change is included there. |
| 8 | S06a shows quantity × unit price, “each”, and a line total on all three lines. The earlier register’s claim was ahead of the canvas; the canvas now actually contains those totals. |
| 9 | S06a says ORDER RECEIVED and explicitly names the back-ordered pouch. A08 #1001 says Paid · Includes back order and flags the pouch. Payment confirmation does not claim all fulfilment is complete. |
| 10 | A08 “03:42 left” uses Inter Regular, the admin body face. |
| 11 | #1003 says Unpaid order cancelled, shows $205.00, and explains that the next checkout re-checks price and stock. |
| 12 | The four flagged disabled buttons use ink on the existing light background, with opacity 1. Shopper label contrast is 15.31:1; admin is 16.12:1. |
| 13 | All ten flagged mobile admin buttons and their action rows are 305px wide. |
| 14–15 | S04 shows the five-minute duration and says the window starts at this store’s checkout, with no pre-Continue countdown. S06b uses the same panel treatment for TIME LEFT / 03:42; its page heading is YOUR CART, leaving one not-completed notice. |
| 16 | A07-choose is a closed select with chevron. A07-choose-open shows its option list. Only Shopify, WooCommerce and BigCommerce appear. The old Other text is hidden, with its node ID retained. |
| 17 | Each credential form identifies its own platform admin as the source and Rig admin as the place to type the values. All credential fields remain blank. |
| 18a | S03-empty adds empty cart at both widths. |
| 18b | S05c adds an unavailable-after-recheck line with active Back order / Leave actions on that line; checkout remains disabled pending that choice. |
| 18c | S05d adds a recheck with no changes, retaining the original price and delivery. |
| 18d | S06c and A08-late add the shopper return and admin row for payment received after the window. The order proceeds at its original held total of $205.00. |
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

Late payment (S06c): “This store received your payment after the 5-minute window ended. Your order is going through. Your lens pouch remains back ordered.”

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
| $120.00, $125.00, $50.00, $35.00 | Computed line-total slots: quantity × held unit price. |
| $120.00 | Single-item cart-total slot in the added state. |
| $205.00, $210.00 | Original/rechecked cart totals and unpaid/paid order-amount slots. |
| Quantity 1, 2, 1 | Editable quantity slots for the three cart lines; the single-item state also uses 1. |
| “3 lines · 4 items” | Computed count slots, not fixed copy for every cart. |
| 2–3 business days | Store-stock minimum/maximum delivery slots; A09’s numeric fields show 2 and 3. |
| 7–10 business days | Per-line longer-delivery slots from the Locate offer; no admin setting is proposed for this. |
| #1001, #1002, #1003, #1004, #1005 | Order-number slots, not real orders. |
| 03:42 / “03:42 left” | Remaining-time slot, shown after checkout starts. |
| 00:00 | Expired-timer slot in the cancelled admin order. |

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
