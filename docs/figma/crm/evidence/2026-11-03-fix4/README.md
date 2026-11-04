> Provenance note · 4 Nov 2026: this is the preserved 3 Nov authoring record from PR #436 head `314bf273`. Its measurements and screenshots have not been re-run against the live canvas in this reconciliation. Status remains **Changed after approval, awaiting founder**. Current approval/wording precedence is documented in [the reconciliation](../../RECONCILIATION-20261104.md); do not replay these old writes or treat them as founder-browser acceptance.

# CRM corrections · 3 November 2026 · Figma 4

Status: **Changed after approval, awaiting founder**. Figma file `ZnphBOJU6657tohGLD3IzS`, page `93:2`. Branch `codex/crm-design`; existing PR #436. Includes the founder's 3 November 11:37 PT light-background ruling. No production code changed.

## Result

- Trigger wordmarks `180:8394`, `180:8551` and detached drawer-end review copies are navy `#001840`, bound to `VariableID:42:5`; Delete-red binding `VariableID:72:9815` removed from them.
- All 5738 outlined CRM fields, including master `93:6` and payment fields, use `#848da3`. WCAG relative-luminance calculation: **3.3228:1 against white** and **3.0711:1 against #f4f6fa**. New tokens: `VariableID:465:26691` primitive/input-border and `VariableID:465:26692` color/input-border.
- Payment input corners and all 203 Record cards/panels are 8px. Master Field padding is 16px; compact mobile card fields keep zero padding.
- Menu items are 44px tall with 8px padding; all 1657 reached menu-item instances pass. Master `180:8467`, desktop `180:8387`, screen instance `182:9119`, and drawers `98:9181` / `98:9227` preserve their IDs.
- No dark surface remains on the CRM page. White surfaces and navy text/outline replace dark backgrounds, including non-destructive confirmation buttons. Red text is restricted to Delete.
- All 56 invoice table-header rows reuse component `43:389`, the component used by list header `97:7423`, with 16px padding. Existing header frames, cells and text IDs remain; old text is hidden and shared instances are nested in the preserved cells. Header height is 72px on invoice tables to fit wrapped mobile labels. Lists use 56px headers; their row cells now match 16px padding.
- Six mobile Full name fields fill their primary 151.5px columns and are renamed Field / full_name: `94:694`, `94:710`, `94:726`, `97:2496`, `97:2512`, `97:2528`. Their text layers are named Full name. Hidden last-name layers are retained.
- Existing table review content offsets `310:35768`, `310:36139`, `310:36519`, `310:36824` were adjusted so both tables remain visible after corrected geometry.

## Complete node register

[changed-nodes.csv](changed-nodes.csv) lists **10981 unique directly written node IDs**, with operation groups. [created-nodes.csv](created-nodes.csv) lists **1120 new header-instance and descendant IDs** (some also appear in changed-nodes.csv). These are explicit write records; normal Figma inheritance and auto-layout additionally update dependent geometry. No existing node was removed or replaced. Operation groups: core1 = original fields/cards; core2/core3 = review fields/cards; menus1/menus2 = navigation and light surfaces; headers/headersFinish = shared invoice headers and Full name; addresses = address proposals/card gaps; geometryFix = compact geometry/navy paint; spacingFix = spacing/header fit; reviewOffsets = table review offsets; listAlignment = list cell alignment and detached wordmarks.

## New words · Changed after approval, awaiting founder

These are design proposals, not approved production copy. Bracketed value slots use the same proposed label inside brackets. Bill-to name, email and phone are unchanged.

| Previous label / context | Proposed label |
| --- | --- |
| Billing address line / invoice | Client's billing address line |
| Billing city / invoice | Client's billing city |
| Billing state or region / invoice | Client's billing state or region |
| Billing postcode / invoice | Client's billing postcode |
| Billing country / invoice | Client's billing country |
| Bill-to address line / invoice | Address on this invoice |
| Bill-to city / invoice | City on this invoice |
| Bill-to state or region / invoice | State or region on this invoice |
| Bill-to postcode / invoice | Postcode on this invoice |
| Bill-to country / invoice | Country on this invoice |
| Bill-to address line / quote | Address on this quote |
| Bill-to city / quote | City on this quote |
| Bill-to state or region / quote | State or region on this quote |
| Bill-to postcode / quote | Postcode on this quote |
| Bill-to country / quote | Country on this quote |

## Remaining spacing exceptions

No 20px, 32px or 40px padding/gap remains. **16 existing 104px paddingBottom clearances remain**, preserving space above pinned mobile confirmation footers, reported explicitly rather than silently changing footer behavior:

- `98:8607` · paddingBottom = 104px.
- `98:8639` · paddingBottom = 104px.
- `98:8671` · paddingBottom = 104px.
- `98:8703` · paddingBottom = 104px.
- `98:8735` · paddingBottom = 104px.
- `98:8767` · paddingBottom = 104px.
- `98:8802` · paddingBottom = 104px.
- `98:8858` · paddingBottom = 104px.
- `98:8911` · paddingBottom = 104px.
- `98:8946` · paddingBottom = 104px.
- `98:8990` · paddingBottom = 104px.
- `98:9052` · paddingBottom = 104px.
- `98:9111` · paddingBottom = 104px.
- `98:9158` · paddingBottom = 104px.
- `310:35545` · paddingBottom = 104px.
- `310:35726` · paddingBottom = 104px.

Exact data: [spacing-exceptions.json](spacing-exceptions.json). These are the remaining exceptions to the 0/8/16/24 spacing rule.

## Evidence and checks

[final-checks.json](final-checks.json) records zero dark surfaces, short menu targets, incorrect Record corners, incorrect outlined-field borders, non-Delete red text or clipped invoice header text. Product fonts remain Jost Light, Inter Regular and Inter Semi Bold. Desktop and mobile geometry were visually inspected. Screenshots are Figma authoring evidence; founder visual acceptance remains outstanding.

| Screenshot | Figma node | Evidence |
| --- | --- | --- |
| [Desktop menu](180-8387.png) | 180:8387 | Light menu, navy Trigger, 44px items |
| [Mobile drawer](98-9181.png) | 98:9181 | Light mobile menu and pinned footer |
| [Mobile cards](94-682.png) | 94:682 | Full names fill primary column; no clipping |
| [Desktop list](94-417.png) | 94:417 | Matching header/body padding |
| [Mobile payment](98-9050.png) | 98:9050 | Outlined 8px inputs, light fixed footer; remaining inputs continue in scroll |
| [Desktop invoice tables](310-36136.png) | 310:36136 | Shared headers and both tables |
| [Mobile invoice tables](310-36821.png) | 310:36821 | Wrapped headers, both tables and row Delete controls; horizontal scroll remains intentional |

Validation was read-only Figma structural inspection, visual inspection and contrast calculation. No application tests are needed for register/authoring artifacts. No API payment, deployment or production request was made.
