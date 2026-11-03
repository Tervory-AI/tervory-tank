# Rig cart (US) — Proposed, not approved

Page: [10 · Rig cart (US)](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=289-13919), node `289:13919`. Every frame name and visible review bar says **Proposed, not approved**. The bar marks the values as illustrative and Figma only; every added word awaits founder approval. There is no runtime implementation or new live copy.

Branch: `codex/rig-cart-figma`. Baseline source commit: `d6004c8d1f0110cc74fc7bbeaae4144277ca6758`. Only this document is committed. Claude opens the PR; the founder merges.

## Frame map — one line per frame

| Screen | Node ID | Size | Existing source component reused |
| --- | --- | --- | --- |
| S01a · Product · store stock | [291:9](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-9) | 1440 × 960 | Widget .card / .price-row / .actions; page/search.css button.card and .price; store theme variables |
| S01a · Product · store stock | [291:26](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-26) | 375 × 960 | Widget .card / .price-row / .actions; page/search.css button.card and .price; store theme variables |
| S01b · Product · longer delivery | [291:43](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-43) | 1440 × 960 | Same product card, price and action as S01a; only the delivery text changes; store theme variables |
| S01b · Product · longer delivery | [291:60](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-60) | 375 × 960 | Same product card, price and action as S01a; only the delivery text changes; store theme variables |
| S01c · Product · back order | [291:77](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-77) | 1440 × 960 | Widget .card, .actions, .btn-accent and .btn-ghost; product/back-order status text |
| S01c · Product · back order | [291:97](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-97) | 375 × 960 | Widget .card, .actions, .btn-accent and .btn-ghost; product/back-order status text |
| S02 · Item added to cart | [291:117](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-117) | 1440 × 960 | Widget .chosen, .ack, .price-row and .actions; original product card and store theme |
| S02 · Item added to cart | [291:140](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-140) | 375 × 960 | Widget .chosen, .ack, .price-row and .actions; original product card and store theme |
| S03 · Your cart | [291:163](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-163) | 1440 × 1495 | Widget .part/.chosen/.price-row; store page .product-layout/.bundle/.bundle-parts; .field and .actions |
| S03 · Your cart | [291:223](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-223) | 375 × 1718 | Widget .part/.chosen/.price-row; store page .product-layout/.bundle/.bundle-parts; .field and .actions |
| S04 · Going to store checkout | [291:283](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-283) | 1440 × 960 | Widget .panel/.status/.actions and primary/ghost buttons; store page .bundle; no checkout/payment form |
| S04 · Going to store checkout | [291:302](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-302) | 375 × 960 | Widget .panel/.status/.actions and primary/ghost buttons; store page .bundle; no checkout/payment form |
| S05a · Payment window ended · rechecking | [291:321](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-321) | 1440 × 1665 | Same cart components as S03; .status/.ack; existing disabled .btn state; checkout disabled while rechecking |
| S05a · Payment window ended · rechecking | [291:384](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-384) | 375 × 1937 | Same cart components as S03; .status/.ack; existing disabled .btn state; checkout disabled while rechecking |
| S05b · Cart rechecked · changes found | [291:447](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-447) | 1440 × 1633 | Same cart components as S03; .status/.ack; existing .part text and price rows for changes |
| S05b · Cart rechecked · changes found | [291:511](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-511) | 375 × 1970 | Same cart components as S03; .status/.ack; existing .part text and price rows for changes |
| S06a · Order complete | [291:575](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-575) | 1440 × 1198 | Widget .ack/.chosen/.price-row; store page .bundle and .bundle-parts; original product card instances |
| S06a · Order complete | [291:598](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-598) | 375 × 1162 | Widget .ack/.chosen/.price-row; store page .bundle and .bundle-parts; original product card instances |
| S06b · Checkout not completed | [291:621](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-621) | 1440 × 960 | Widget .status/.panel/.actions; primary/ghost buttons; no payment fields |
| S06b · Checkout not completed | [291:640](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-640) | 375 × 960 | Widget .status/.panel/.actions; primary/ghost buttons; no payment fields |
| A07-choose · Shop platform · not connected | [291:8053](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8053) | 1440 × 960 | RetailerAdmin .retailer-header/.retailer-card, Source select, .retailer-notice and existing buttons |
| A07-choose · Shop platform · not connected | [291:8075](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8075) | 375 × 960 | RetailerAdmin .retailer-header/.retailer-card, Source select, .retailer-notice and existing buttons |
| A07-shopify · Shopify · enter credentials | [291:8097](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8097) | 1440 × 960 | RetailerAdmin form/label/input, existing Shopify secret-key input pattern, .retailer-primary |
| A07-shopify · Shopify · enter credentials | [291:8124](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8124) | 375 × 960 | RetailerAdmin form/label/input, existing Shopify secret-key input pattern, .retailer-primary |
| A07-woo · WooCommerce · enter credentials | [291:8151](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8151) | 1440 × 960 | RetailerAdmin form/label/input and existing WooCommerce username/consumer-key + password/secret pattern |
| A07-woo · WooCommerce · enter credentials | [291:8182](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8182) | 375 × 960 | RetailerAdmin form/label/input and existing WooCommerce username/consumer-key + password/secret pattern |
| A07-big · BigCommerce · enter credentials | [291:8213](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8213) | 1440 × 960 | RetailerAdmin form/label/input pattern, with proposed BigCommerce store-hash/access-token labels |
| A07-big · BigCommerce · enter credentials | [291:8240](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8240) | 375 × 960 | RetailerAdmin form/label/input pattern, with proposed BigCommerce store-hash/access-token labels |
| A07-testing · Shop platform · testing | [291:8267](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8267) | 1440 × 960 | RetailerAdmin .retailer-card/.retailer-notice and native disabled button opacity |
| A07-testing · Shop platform · testing | [291:8288](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8288) | 375 × 960 | RetailerAdmin .retailer-card/.retailer-notice and native disabled button opacity |
| A07-connected · Shop platform · connected | [291:8309](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8309) | 1440 × 960 | RetailerAdmin .retailer-card/.retailer-notice/.retailer-actions; saved credential values omitted |
| A07-connected · Shop platform · connected | [291:8333](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8333) | 375 × 960 | RetailerAdmin .retailer-card/.retailer-notice/.retailer-actions; saved credential values omitted |
| A07-failed · Shop platform · connection failed | [291:8357](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8357) | 1440 × 960 | RetailerAdmin .retailer-notice.is-error/.retailer-actions; saved credential values omitted |
| A07-failed · Shop platform · connection failed | [291:8381](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8381) | 375 × 960 | RetailerAdmin .retailer-notice.is-error/.retailer-actions; saved credential values omitted |
| A08 · Orders | [291:8405](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8405) | 1440 × 1006 | RetailerAdmin .retailer-history article and .retailer-actions; original mobile stacked history layout |
| A09 · Store delivery time | [291:8444](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8444) | 1440 × 960 | RetailerAdmin .retailer-card, settings form/label/input, .retailer-hint and .retailer-primary |
| A08 · Orders | [291:8464](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8464) | 375 × 974 | RetailerAdmin .retailer-history article and .retailer-actions; original mobile stacked history layout |
| A09 · Store delivery time | [291:8503](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=291-8503) | 375 × 960 | RetailerAdmin .retailer-card, settings form/label/input, .retailer-hint and .retailer-primary |

## Required behavior shown

- Rig never takes payment. Add to cart is a Rig cart on the store's own site. Checkout leaves for that store's own shop-platform checkout; no card, bank, billing or payment-entry form is drawn inside Rig. The handoff explicitly states who takes payment.
- Result cases use the same product, price and FIND A PRODUCT heading. Store stock has 2–3 business days; the other available case changes only the delivery time to 7–10 business days. No shopper content identifies a supplier or says which source fulfils the item. Back order shows no confirmed delivery date and offers Back order or Leave. Case names in the review bars are Figma annotations, not shopper copy.
- Added state shows the product added to this store's Rig cart, quantity and total, with View cart / Keep shopping. The larger cart illustrates subsequent selections: one tripod, two straps and one pouch. Every line has quantity, unit price, line total, and its delivery time or back-order notice.
- Original cart: $120 + (2 × $25) + $35 = $205. The checkout handoff states a five-minute payment window. The displayed 05:00 / 03:42 times are static Figma state illustrations, not claimed running timers.
- Expired window has a separate Checking frame with Checkout disabled. The following rechecked frame shows the tripod price changing $120 → $125, its delivery 2–3 → 7–10 business days, and total $205 → $210. Checkout can continue only after the depicted recheck, with a new five-minute payment window described in the draft wording.
- Paid return and admin paid order #1001 match the rechecked cart: tripod $125 × 1, strap $25 × 2, pouch $35 × 1, total $210. Back-order delivery remains unconfirmed after payment. Not-completed return says no completed payment has been confirmed, retains the cart and shows time remaining.
- Admin platform selection includes Shopify, WooCommerce, BigCommerce and Other. Separate blank credential forms cover Shopify, WooCommerce and BigCommerce, followed by testing, connected and failed examples. These are proposed connector views, not claims that checkout connectors already exist. Existing catalogue feed connections are not relabelled as working checkout integrations. Other platform support is a selection proposal; no invented connector implementation is claimed.
- Credential values are never supplied. Inputs are blank and represent the store typing them. Testing/connected/failed states omit credential values entirely and state that saved credentials are hidden. No actual credential was typed, viewed, generated, saved or tested.
- Admin orders show Paid, Waiting for payment with 03:42 left, Window expired, Back ordered and Needs a person. Review order is the manual-action proposal; no automatic payment confirmation is invented.
- Delivery setting belongs to one store and covers its own stock, with a 2–3 business-day example matching the original product case. Products needing longer retain a longer per-line delivery time. South Africa / Custom Nation quote → invoice → EFT is excluded from every frame.

## Source, brand and component fidelity

Required directories were all present: `agents/rig/rigbox/quotes/widget`, `agents/rig/rigbox/page`, `workspace/app/rig/admin`. Read sources include the shipped widget UMD and manifest, `quotes/rebuild-widget.sh`, `docs/rig/widget-source.patch`, store `index.html`, `search.css`, `search.js`, v5 README/CSS, and admin `retailer-admin.tsx`, `retailer-admin.css`, `products.tsx`.

Shopper frames reuse the **existing widget neutral store skin**, not the Custom Nation skin: canvas #f4f5f7; ink #1c1e21; accent #1d4e89; muted #5c6370; line #d5d8de; white card/on-accent; 10px radius. Fonts are the widget's actual Newsreader SemiBold heading and Source Sans 3 body, not a substituted Tervory font. The displayed {STORE NAME} is a configurable store-name placeholder, not an invented brand or fake logo. Product images were not fabricated; the existing text/card and chosen-product patterns are used.

The source theme already supports store overrides. Missing Figma bindings were represented in collection `289:13920` (Rig cart / Existing neutral widget store theme) with source-named `--rig-*` variables, semantic colour aliases, explicit scopes and CSS `var(--rig-...)` syntax. The neutral values are only the existing skin's review fallback; a store's theme overrides replace them. Existing client/Chatbot or Tisan tokens were not passed off as Rig store branding.

Admin keeps its actual navy #001840, paper #F4F6FB, line #B8BFD0, red #E80008, Jost Light and Inter. Mobile gutters/cards and error left border follow `retailer-admin.css`. Existing `42:*` and `164:17` variables are reused. Credential field geometry is reused; no credential values exist.

No matching published Rig widget composite or Code Connect files were found. The existing Rig case-study frame `51:3510` was inspected, but its reporting tiles/charts are not shopper-cart components. Only missing Figma representations of existing code primitives were created, in a separate source-component section, with instances inside the review frames:

- `289:13941` / `289:13943`: widget .btn-accent / .btn-ghost.
- `289:13945` / `289:13947`: existing admin primary / secondary button styles.
- `289:13949` / `289:13953`: widget .field / admin label-input.
- `289:13957`: existing widget .card/.chosen product text/price/delivery pattern.

All text is editable. The UI is auto-layout containers, text, existing-source component instances and dividers; no flattened full-UI screenshot is embedded. Original pages/components were not modified. No unrelated library work was done.

## Validation and review status

- 38 review frames: 19 at 1440 and 19 at 375. Coverage is 20 shopper frames and 18 admin frames. All have the requested approval label.
- Final complete audit: 666 visible text nodes, zero frame/parent text overflow, correct widget versus admin font families, and no complete-UI raster. The last product-heading correction only shortened six headings to identical source wording and was visually checked on the longer-delivery mobile frame.
- Initial visual review found inherited input widths extending outside mobile cards. The shared field components were corrected, then relevant mobile compositions were checked again. Mobile admin padding and notice/error styling were also corrected to the source CSS.
- Full-view screenshots inspected: desktop cart `291:163`, mobile rechecked cart `291:511`, handoff `291:302`, connected `291:8333`, orders `291:8464`, credential form `291:8182`, failure `291:8381`, delivery setting `291:8503`, final paid return `291:598`, back order `291:97`, platform choice `291:8053`, testing `291:8288`, and final longer-delivery result `291:60`.
- These are agent visual checks of proposed Figma designs. Founder browser review/approval and screenshots of that test remain pending; none are claimed. Static design frames do not prove a working cart, timer, connector or payment callback.
- No application tests were run because no application file changed. No live data, secrets, environment values or payment settings were changed. Nothing merged or deployed.

## Commands and results

Required first command, exit 0:

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-rig-cart-figma && cd /workspace/codex-rig-cart-figma && git fetch origin main && git checkout -B codex/rig-cart-figma origin/main && git config user.name 'Codex' && git config user.email 'codex@users.noreply.github.com' && ls -ld agents/rig/rigbox/quotes/widget agents/rig/rigbox/page workspace/app/rig/admin
```

Read-only source inspection used `cat AGENTS.md`, `rg --files` on the three required directories, `sed -n '1,210p' workspace/app/rig/admin/retailer-admin.tsx`, `cat workspace/app/rig/admin/retailer-admin.css`, `sed -n '1,160p' workspace/app/rig/admin/products.tsx`, `cat agents/rig/rigbox/quotes/widget/manifest.json`, `sed -n '1,180p' agents/rig/rigbox/page/index.html`, `cat agents/rig/rigbox/page/search.css`, `cat agents/rig/rigbox/quotes/rebuild-widget.sh`, `sed -n '1,120p' agents/rig/rigbox/page/v5/README.md`, and source-token extraction with Python. Searches returning no nested AGENTS/Code Connect matches did not indicate a missing required file. All required source directories existed.

Initial document commit/push succeeded: `6402d2cc`. The branch upstream was then set by `git branch --set-upstream-to=origin/codex/rig-cart-figma codex/rig-cart-figma`. Figma operations returned their created/mutated IDs and audit results in this task. Transient scripts and manifests under `.git/rig-design/` are untracked orchestration, not repository deliverables.

Final commands:

```sh
python3 .git/rig-design/document.py
git diff --check
git add docs/figma/RIG-CART-FRAMES.md
git commit -m 'docs(figma): map all US Rig cart and store-admin proposals'
git push origin codex/rig-cart-figma
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git status --short --branch
```

The command output in this task records the exact results. Allowed changed file: `docs/figma/RIG-CART-FRAMES.md` only. Proposed words await the founder before implementation.
