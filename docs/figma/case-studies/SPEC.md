# Client case studies and product dashboard template

Revision: founder decisions and review fixes, 28 October 2026, 07:40 PT.
Status: ready for founder review; accent colours and the proposed comparison label await approval.
File: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS
Page: 1 · Case studies (42:2).
SPEC frame: 63:10450. Founder decisions frame: 79:10314.
Repository destination for Claude: docs/figma/case-studies/SPEC.md.

Authority: the Founder decisions section below overrides every conflicting earlier instruction or description. It records the decisions pasted in this chat. The repo SPEC was unavailable in this checkout.

Figma-only revision. No application code, live client data, production data, model calls, secrets, sign-in, billing, pricing or payment work was performed. Billing is an existing navigation item only. Claude commits this exact document; no repository branch, commit or push was created here.

The protected page 0 · Dashboards (approve first), frame 12:2 and frame 10:115 remain unchanged. No new Figma file was created.
## Founder decisions

28 October 2026, 07:40 PT. This section overrides every conflicting earlier decision or description.

1. ONE MERGED MENU: Overview replaces Dashboard; then the client's entitled products Base, Tiger, Market Lab, Rig, Zenas, Trigger, Tisan, Radix, Autumbra; then CRM; then Case study; then Chats, Projects, Squad, Tasks, Data, Prices. Receipts, Billing, Settings stay at the bottom. Founder audience adds the client switcher at the top and Admin before the bottom section.
2. SIDE MENU ONLY, NO COUNTS: no product tab row on any page or template. No menu count badges, Badge variants, Show count or Count properties.
3. ONE ACCENT PER PRODUCT: navy remains the base. One proposed accent per product and one for CRM are variables, pass WCAG AA on white, colour that product's chart marks, and appear as a small marker on its menu item. The palette is shown on the Variables board. Accent proposals still require colour approval.
4. CASE STUDY PDF: available only to the client's signed-in users and the founder. No share link, public sharing state or anonymous PDF route.

Review fixes:
- ZERO charts have exactly one literal 0 at the baseline and no category labels.
- FILLED axes use each figure's own unit and range, with five linear ticks. Spend illustrates $0–$4,000; counts, percentages, minutes and sources per answer have their own domains.
- Stat values include their unit once. No repeated USD or % row.
- Proposed FIXED comparison label: vs previous period.

PDF implementation requirement: verify the signed-in user's membership of the selected client, or the founder role, before generating or returning that client's PDF. This design adds no sign-in screens or permission/error copy. All PDF data remains tenant-scoped.
## Screen frames

All existing screen node IDs are retained. Desktop frames are 1440 × 900; mobile frames are 375 × 812. Content scrolls vertically. The desktop menu or mobile bar stays fixed. Every configured figure remains in the content, including at zero.

| Page | Desktop ZERO | Desktop FILLED | Mobile ZERO | Mobile FILLED |
| --- | --- | --- | --- | --- |
| Overview | 48:554 | 48:889 | 54:5914 | 54:6208 |
| Case study summary | 48:1224 | 48:1561 | 54:6502 | 54:6796 |
| Base | 49:2056 | 49:2453 | 54:7090 | 54:7444 |
| Tiger | 49:2852 | 49:3211 | 54:7798 | 54:8114 |
| Market Lab | 51:2398 | 51:2766 | 54:8430 | 54:8753 |
| Rig | 51:3134 | 51:3510 | 54:9076 | 54:9409 |
| Zenas | 51:3886 | 51:4224 | 54:9742 | 54:10037 |
| Trigger | 51:4562 | 51:4900 | 54:10332 | 54:10627 |
| Tisan | 51:5238 | 51:5576 | 54:10922 | 54:11217 |
| Radix | 52:4638 | 52:4997 | 54:11512 | 54:11826 |
| Autumbra | 52:5356 | 52:5694 | 54:12140 | 54:12435 |

Supporting nodes:
- Variables board 42:52; proposed accent palette 72:9824.
- Component gallery 43:2.
- Desktop menu/template area 46:20; mobile template/menu area 53:5464.
- Mobile drawer ZERO 53:6328; FILLED 53:6373.
- SPEC 63:10450; authoritative Founder decisions 79:10314.

Prototype entry flows: Desktop · ZERO 48:554; Desktop · FILLED 48:889; Mobile · ZERO 54:5914; Mobile · FILLED 54:6208. Choose a flow in Present. Menu navigation stays in that flow's width and data state.
## Components and variants

There are 16 component sets with 48 auto-layout variants. Plot primitives remain editable inside plot frames. Every screen retains its template and nested component instances.

| Component set | Set node ID | Variants and node IDs |
| --- | --- | --- |
| Stat tile | 43:14 | State=Zero: 43:4; State=Filled: 43:9 |
| Period picker | 43:23 | Period=7 days: 43:15; Period=30 days: 43:17; Period=90 days: 43:19; Period=Custom: 43:21 |
| Compare to previous | 43:30 | State=Off: 43:24; State=On: 43:27 |
| Export | 43:35 | Format=PDF: 43:31; Format=CSV: 43:33 |
| Line chart | 43:129 | Size=Desktop, State=Zero: 43:37; Size=Desktop, State=Filled: 43:60; Size=Mobile, State=Zero: 43:83; Size=Mobile, State=Filled: 43:106 |
| Bar chart | 43:218 | Size=Desktop, State=Zero, Categories=Three: 43:130; Size=Desktop, State=Filled, Categories=Three: 43:152; Size=Mobile, State=Zero, Categories=Three: 43:174; Size=Mobile, State=Filled, Categories=Three: 43:196; Size=Desktop, State=Zero, Categories=Two: 75:10972; Size=Desktop, State=Filled, Categories=Two: 75:10984; Size=Mobile, State=Zero, Categories=Two: 75:11004; Size=Mobile, State=Filled, Categories=Two: 75:11016 |
| Histogram | 43:308 | Size=Desktop, State=Zero: 43:220; Size=Desktop, State=Filled: 43:242; Size=Mobile, State=Zero: 43:264; Size=Mobile, State=Filled: 43:286 |
| Table header | 43:401 | Sort=None: 43:389; Sort=Ascending: 43:393; Sort=Descending: 43:397 |
| Table row | 43:408 | State=Zero: 43:402; State=Filled: 43:405 |
| Side menu item | 43:427 | State=Default: 43:409; State=Hover: 43:415; State=Active: 43:421 |
| Table | 44:31 | State=Zero: 44:3; State=Filled: 44:17 |
| Calibration | 50:2539 | Size=Desktop, State=Zero: 50:2399; Size=Desktop, State=Filled: 50:2434; Size=Mobile, State=Zero: 50:2469; Size=Mobile, State=Filled: 50:2504 |
| Workspace menu | 46:111 | Audience=Client: 46:21; Audience=Founder: 46:66 |
| Page template / Desktop | 46:698 | State=Zero: 46:112; State=Filled: 46:405 |
| Page template / Mobile | 53:6327 | State=Zero: 53:5465; State=Filled: 53:5896 |
| Workspace menu / Mobile | 70:10658 | Audience=Client: 70:10507; Audience=Founder: 70:10581 |

Stat tile properties: Label, Value, Change, Context, Show context and State. The old Unit property is removed. Value carries its unit once; Context is only method information such as 200-record audit.
The comparison row contains DATA Change plus the proposed FIXED label vs previous period.
Menu item properties: Label, State and Show marker. Badge, Show count and Count are removed. Only Default, Hover and Active variants remain.
Desktop and mobile Workspace menus expose Audience and nine Has product entitlement switches. The same tenant entitlement set must control navigation and routes.
Page templates expose State, Page and Client name. Product-tab rows, their visibility properties and the Product tab component set are removed.
Bar charts support Two or Three categories, each with desktop/mobile and ZERO/FILLED states. Other chart families have desktop/mobile and ZERO/FILLED states.
Chart titles and numeric/category text are editable figure overrides. Title is exposed where the component supplies a TEXT property.
No donut is retained; none of the requested figures needs a share chart.
## Foundations and proposed accents

Collections:
- Case studies / Primitives: VariableCollectionId:42:3, Value mode.
- Case studies / Tokens: VariableCollectionId:42:4, Light mode.

There are 67 variables: 17 primitive colours, 20 semantic colours, eight spacing values, five radii, nine type sizes, two stroke widths, two font families and four font styles. Semantic colours alias primitives.

The original navy base, pale canvas, white surfaces, muted text, border/grid and active navy remain from frame 12:2. The original green token is retained; it is not an extra product accent.
Source RGB values: navy 0/0.094/0.251; canvas 0.957/0.965/0.980; white 1/1/1; muted 0.239/0.290/0.400; border 0.722/0.749/0.816; active 0.133/0.204/0.353.

One proposed accent per product and one for CRM:

| Product | Proposed accent | Contrast on white | Semantic variable ID | Primitive variable ID |
| --- | --- | --- | --- | --- |
| Base | #1D4ED8 | 6.70:1 | VariableID:72:9805 | VariableID:72:9804 |
| Tiger | #9A3412 | 7.31:1 | VariableID:72:9807 | VariableID:72:9806 |
| Market Lab | #6D28D9 | 7.10:1 | VariableID:72:9809 | VariableID:72:9808 |
| Rig | #0F766E | 5.47:1 | VariableID:72:9811 | VariableID:72:9810 |
| Zenas | #475569 | 7.58:1 | VariableID:72:9813 | VariableID:72:9812 |
| Trigger | #BE185D | 6.04:1 | VariableID:72:9815 | VariableID:72:9814 |
| Tisan | #15803D | 5.02:1 | VariableID:72:9817 | VariableID:72:9816 |
| Radix | #A16207 | 4.92:1 | VariableID:72:9819 | VariableID:72:9818 |
| Autumbra | #A21CAF | 6.32:1 | VariableID:72:9821 | VariableID:72:9820 |
| CRM | #0369A1 | 5.93:1 | VariableID:72:9823 | VariableID:72:9822 |

Semantic names are color/accent/base, tiger, market-lab, rig, zenas, trigger, tisan, radix, autumbra and crm, each under the color/accent/ prefix.
All ten pass WCAG AA on white. These are proposals, not approved new brand colours.
Product chart marks use that product's accent, including its shared Tank charts. Overview and Case study aggregate charts retain navy. Calibration uses the Market Lab accent for both series, distinguished by solid/dashed lines.
Menu markers use an 8 px accent dot inside a 16 px white carrier so the accent's white-background contrast is preserved on the navy menu. Product names also identify the destination. CRM has a marker; no CRM figures were invented.

Spacing: 0, 8, 16, 24, 32, 40, 48, 64 px. New layout gaps and padding follow the 8-point scale.
Radii: 0, 8, 10, 12, 16 px from the base. Cards use 16; navigation and controls use 8.
Type: Jost Light headings/values; Inter Regular/Medium/Semi Bold labels and controls. Sizes: 12, 13, 14, 15, 17, 18, 24, 34, 40 px. Primary product value 40; secondary values 34.
Desktop sidebar width 220, content horizontal padding 64. Mobile content padding 24; charts 327 wide. The plot value gutter is 72 px desktop and 64 px mobile.
Original logo asset is reused, not redrawn. Light only; dark remains unresolved.
Base text contrast: navy/white 17.44:1; muted/white 8.87:1; navy/canvas 16.12:1; white/active 12.30:1.
## Merged menu and template behaviour

Client menu order:
Overview; entitled Base, Tiger, Market Lab, Rig, Zenas, Trigger, Tisan, Radix, Autumbra; CRM; Case study; Chats; Projects; Squad; Tasks; Data; Prices.
Receipts, Billing, Settings are pinned at the bottom.

Founder adds the client switcher at the top and Admin after Prices, before the pinned bottom group. Client hides both. No menu counts or product tabs remain.

Desktop Client/Founder: 46:21 / 46:66, set 46:111.
Desktop scroll regions: 70:10451 / 70:10478. Footers: 70:10452 / 70:10479.
Mobile Client/Founder: 70:10507 / 70:10581, set 70:10658.
Mobile scroll regions: 70:10516 / 70:10590. Footers: 70:10517 / 70:10591.
Drawers 53:6328 and 53:6373 contain the shared mobile Client menu. Founder mobile is available as the Audience=Founder component variant.

The menu middle scrolls independently while its header and bottom group remain visible. The all-products Figma configuration has 21 client destinations and 22 founder destinations. A real client sees only entitled products.
Mobile uses this drawer, not a bottom bar. The menu button opens the matching ZERO/FILLED drawer; × closes it.
There are 264 side-menu/drawer navigation links across the 44 screens and two drawers. Current desktop destinations do not navigate to themselves.
CRM and the existing Workspace/Admin entries are included in the menu. New destination page designs and route URLs were not invented.

The shared page template contains header, period/compare/export controls, stat rows, chart grid and table. There is no product-tab row. A new product is figure configuration in this system, not a new page design.
Overview shows T1–T6 across owned products and a product spend table.
Case study summary shows T1–T6 and one primary outcome per owned product. It has no client narrative claims.
Each product page contains all of that product's figures plus T1–T6 scoped to that product.

Primary values: Base B1; Tiger G1; Market Lab M1; Rig R1; Zenas Z1; Trigger V1; Tisan S1; Radix D1; Autumbra A1. Overview and Case study emphasise T1.
Each stat value contains its unit once. Change is shown alongside vs previous period. No repeated USD or % row. The 200-record audit context identifies the intended method, not a completed-audit claim.

Every client must receive the template automatically at sign-up with their entitled products. No sign-in screen is added. Every configured chart stays present and shows the defined ZERO state until real data arrives.
The period picker cycles 7 days / 30 days / 90 days / Custom to demonstrate states. Compare toggles Off/On; header clicks cycle sort states. These prototype interactions do not query data.
No extra custom-date, empty-state, success, error or permission wording is added.
## Chart units, ranges and ZERO behaviour

ZERO: axes and five gridlines remain. There is exactly one literal 0 at the baseline. No categories, date labels, repeated zero ticks, data bars, series marks or footer totals are shown.
FILLED: five linear value ticks use the figure's own unit and range. Values below are format-only domains for Figma; production scales must be computed from actual figure data and the approved unit.

| Figure ID | Figure | Chart | FILLED value-axis domain | FILLED category/date labels |
| --- | --- | --- | --- | --- |
| T1 | Spend | Line | 0–4000 currency | 1 / 15 / 30 |
| T5 | Work by code / cache / model | Bar, 3 categories | 0–20000 count | Code / Cache / Model |
| T6 | Graduation progress | Line | 0–100 percent | 1 / 15 / 30 |
| B4 | Confidence histogram | Histogram | 0–6000 count | 0% / 50% / 100% |
| B5 | By state | Bar, 3 categories | 0–20000 count | [State] / [State] / [State] |
| B6 | vs Apollo | Bar, 2 categories | 0–100 percent | Base / Apollo |
| G5 | Price-change histogram | Histogram | 0–500 count | −20% / 0% / +20% |
| G6 | Time to detect a change | Line | 0–4 minutes | 1 / 15 / 30 |
| M3 | Prediction confidence vs actual hit rate | Calibration | 0–100 percent | 0% / 50% / 100% |
| R5 | Quotes that became estimates or invoices | Bar, 2 categories | 0–400 count | Estimates / Invoices |
| R6 | Most-searched products | Bar, 3 categories | 0–2000 count | [Product] / [Product] / [Product] |
| Z4 | Sources per answer | Line | 0–6 decimal | 1 / 15 / 30 |
| D2 | Findings by severity | Bar, 3 categories | 0–300 count | [Severity] / [Severity] / [Severity] |

Currency ticks include $, counts use integer grouping, percentages include %, duration ticks include min, and sources per answer use decimals.
Example Spend ticks: $0, $1,000, $2,000, $3,000, $4,000. There is no blanket 0–100 scale for counts or currency.
B4 confidence and G5 price-change histograms use counts on the value axis and percentages on the category axis.
M3 has percentage axes for confidence and actual hit rate, with separate dashed/solid series.
T6 is a percentage time series. Its operational definition still needs a source contract.
All plot marks, category placeholders and scale examples are format-only DATA, never client performance claims.
## Case study PDF access and exports

Resolved policy: only the client's signed-in users and the founder may generate or receive that client's Case study PDF. Validate membership of the selected tenant or founder role before export; scope all data to that tenant.
There is no share-link control, public sharing state or anonymous PDF route. PDF permission is not an open question.
This is a design and implementation requirement, not a claim that application authentication code was changed.

PDF/CSV buttons remain designed controls. No download service or CSV implementation was built in Figma.
Case study full-content PDF exports use the Main frames, not cropped viewport roots:
- Desktop ZERO: I48:1224;46:156.
- Desktop FILLED: I48:1561;46:449.
- Mobile ZERO: I54:6502;53:5467.
- Mobile FILLED: I54:6796;53:5898.
These Main frames retain PDF export settings. Export component 43:35 records the access policy.
Claude exports approved frames for builders.
## DATA register

Every FILLED value, chart point, bar height, category placeholder, total and change is DATA used only to show formatting. These are not a real or sample client dataset, do not make client claims, and never ship. Repeated numbers do not define arithmetic relationships.
ZERO stats and measurements are zero. Each ZERO chart shows axes, gridlines and exactly one literal 0 at the baseline, with no category labels, repeated zero labels, data bars or footer total. FILLED category placeholders remain DATA.

The IDs below are logical source figure IDs assigned to the founder's figure list. They are not claims that an API or database binding was verified. Builders must map them to tenant-scoped sources after approval.

| Source figure ID | Product | FIXED label | FILLED format-only value | ZERO value | Format / unit |
| --- | --- | --- | --- | --- | --- |
| T1 | Tank | Spend | $3,691.70 | $0.00 | USD |
| T2 | Tank | Savings vs baseline cost | $8,557.00 | $0.00 | USD |
| T3 | Tank | Cost per task | $0.20 | $0.00 | USD |
| T4 | Tank | Cache hits | 64.2% | 0% | % |
| T5 | Tank | Work by code / cache / model | 18 420 | 0 | integer counts by Code, Cache, Model |
| T6 | Tank | Graduation progress | 64.2% | 0 | percentage over time |
| B1 | Base | Records verified | 18 420 | 0 | integer |
| B2 | Base | Cost per verified record | $0.20 | $0.00 | USD |
| B3 | Base | Measured accuracy | 98.5% ± 1.7 | 0% ± 0 | percentage ± range; audit context |
| B4 | Base | Confidence histogram | 18 420 | 0 | integer counts; categories/bins below |
| B5 | Base | By state | 18 420 | 0 | integer counts; categories/bins below |
| B6 | Base | vs Apollo | 98.5% | 0 | percentages by Base and Apollo |
| G1 | Tiger | Changes caught | 1 240 | 0 | integer |
| G2 | Tiger | Pages watched | 320 | 0 | integer |
| G3 | Tiger | Checks run | 18 420 | 0 | integer |
| G4 | Tiger | Alerts sent | 248 | 0 | integer |
| G5 | Tiger | Price-change histogram | 1 240 | 0 | integer counts; categories/bins below |
| G6 | Tiger | Time to detect a change | 2.4 min | 0 | decimal minutes |
| M1 | Market Lab | Questions answered | 1 240 | 0 | integer |
| M2 | Market Lab | Sources cited | 6 840 | 0 | integer |
| M4 | Market Lab | Active feeds | 24 | 0 | integer |
| M3 | Market Lab | Prediction confidence vs actual hit rate | 75.0% / 71.4% | 0% / 0% | stated confidence % / actual hit rate % |
| R1 | Rig | Searches | 18 420 | 0 | integer |
| R2 | Rig | No-result searches | 240 | 0 | integer |
| R3 | Rig | Setups built | 1 240 | 0 | integer |
| R4 | Rig | Quotes sent | 320 | 0 | integer |
| R5 | Rig | Quotes that became estimates or invoices | 248 | 0 | integer counts; categories/bins below |
| R6 | Rig | Most-searched products | 1 240 | 0 | integer counts; categories/bins below |
| Z1 | Zenas | Questions | 1 240 | 0 | integer |
| Z2 | Zenas | Cited answers | 1 180 | 0 | integer |
| Z3 | Zenas | Criminal questions refused | 24 | 0 | integer |
| Z5 | Zenas | Drafts | 320 | 0 | integer |
| Z4 | Zenas | Sources per answer | 4.2 | 0 | decimal sources per answer |
| V1 | Trigger | Drafts | 1 240 | 0 | integer |
| V2 | Trigger | Checker issues per draft | 2.4 | 0 | decimal |
| V3 | Trigger | Acceptance rate | 82.4% | 0% | % |
| V4 | Trigger | Voice-rule hits | 320 | 0 | integer |
| S1 | Tisan | Sites built | 24 | 0 | integer |
| S2 | Tisan | Visual scores | 92.4 | 0 | decimal |
| D1 | Radix | Scans | 1 240 | 0 | integer |
| D2 | Radix | Findings by severity | 248 | 0 | integer counts; categories/bins below |
| A1 | Autumbra | Checks | 18 420 | 0 | integer |
| A2 | Autumbra | Incidents | 24 | 0 | integer |
| A3 | Autumbra | Shields | 320 | 0 | integer |

For every figure ID F above:
- F.value is the stat, chart footer or table value in the stated format.
- F.change is the signed change versus the preceding equal-length period; FILLED format +12.4%, ZERO 0%. No increase is presented as automatically good.
- F.series[] is editable DATA: date/band/category plus numeric value. F.axisTicks[] are numeric DATA derived from the approved domain and unit.
- F.tableValue repeats F.value; table row labels use the FIXED figure label. Case study uses Product · FIXED label plus the primary figure value.
- F.unit drives the formatter inside F.value. Currency includes $, percentages include %, and duration includes min. There is no duplicated unit row in stat tiles. Context is optional method information.
- F.value, F.change, F.series, F.axisTicks, totals and table cells must share the selected period, tenant and product scope.

Additional DATA fields:
- C1.clientName: display-name string, shown as [Client name] in Figma. The founder switcher uses the selected client's display name. No real client identity was used.
- C2.period: one of the four FIXED picker labels; default 30 days. Table period headers follow this selection.
- B3.audit: measurement and ± range from a 200-record audit; FILLED 98.5% ± 1.7, ZERO 0% ± 0. The uncertainty method requires approval.
- B4.bins[]: confidence percentages, illustrated at 0% / 50% / 100%, and integer bin counts.
- B5.categories[]: state names, FILLED [State], and counts.
- B6.series[]: Base and Apollo comparison values formatted as percentages. All shown bar geometry is format-only.
- G5.bins[]: price-change percentages, illustrated at −20% / 0% / +20%, and counts.
- G6.series[]: detection duration by date; footer format 2.4 min.
- M3.bands[]: stated-confidence percentages and resolved actual-hit-rate percentages for the same cohort. Confidence is dashed; actual hit rate is solid. Table format 75.0% / 71.4%; ZERO 0% / 0%. No model calls are needed to calculate these rates.
- R5.categories[]: Estimates and Invoices, with integer counts.
- R6.categories[]: product names, FILLED [Product], and search counts.
- Z4.series[]: decimal sources per answer, footer format 4.2.
- D2.categories[]: severity labels, FILLED [Severity], and counts.

Source figure T6 uses a progress time series with a percentage footer and a 0–100% axis. Its exact operational definition remains an open question.
All time-series dates/ticks are DATA; the displayed 1 / 15 / 30 are format-only day positions. Histogram and calibration reference percentages are DATA axis fields in FILLED only; ZERO has no category labels.
Do not ship any Figma placeholder, bracketed category, chart geometry or fabricated client text.
## FIXED text register for founder approval

Menu labels:
Overview; Base; Tiger; Market Lab; Rig; Zenas; Trigger; Tisan; Radix; Autumbra; CRM; Case study; Chats; Projects; Squad; Tasks; Data; Prices; Receipts; Billing; Settings; Admin.
Other headings: Case study summary; Product.

Controls:
7 days; 30 days; 90 days; Custom; Compare to previous; Export PDF; Export CSV.
Proposed comparison label: vs previous period.

Shared Tank:
Spend; Savings vs baseline cost; Cost per task; Cache hits; Work by code / cache / model; Graduation progress; Code; Cache; Model.

Base:
Records verified; Cost per verified record; Measured accuracy; 200-record audit; Confidence histogram; By state; vs Apollo; Apollo.

Tiger:
Pages watched; Checks run; Changes caught; Alerts sent; Price-change histogram; Time to detect a change.

Market Lab:
Questions answered; Sources cited; Prediction confidence vs actual hit rate; Active feeds; Confidence; Actual hit rate.
Legend: Confidence – –  /  Actual hit rate —.

Rig:
Searches; No-result searches; Setups built; Quotes sent; Quotes that became estimates or invoices; Estimates; Invoices; Most-searched products.

Zenas:
Questions; Cited answers; Criminal questions refused; Sources per answer; Drafts.

Trigger:
Drafts; Checker issues per draft; Acceptance rate; Voice-rule hits.

Tisan: Sites built; Visual scores.
Radix: Scans; Findings by severity.
Autumbra: Checks; Incidents; Shields.

Formatting and controls:
$; %; min; ±; signed change + or −; summary separator ·.
☰ opens the drawer; × closes it; ⌄ marks the founder switcher; ↕ / ↑ / ↓ indicate sort state.
Numeric values, ticks and [Client name] / [State] / [Product] / [Severity] are DATA. No count-badge copy remains. USD is an internal format/unit code, not a repeated stat label.

Documentation-only, never product UI:
Variables; Frame 12:2 · Light; sidebar; canvas; surface; text; muted; active; border; success.
Proposed accents · WCAG AA on white.
Jost Light 34 / 40 · Inter Regular 14 / 15 · Inter Semi Bold 13 / 17.
Spacing 8 / 16 / 24 / 32 / 48 / 64 · Radius 8 / 10 / 12 / 16.
Product hex codes and calculated contrast ratios are technical palette evidence.
This SPEC and layer/component/property names are handoff documentation, not product copy.
## Proof and validation

Changed page: 1 · Case studies, 42:2. The protected dashboard page and frames 12:2 / 10:115 were not edited.
44 screen IDs retained; four prototype entry flows retained.
16 component sets, 48 auto-layout variants, 67 variables.
Deterministic audit passed:
- 44 viewport dimensions and removal of all product-tab rows.
- Menu order, pinned bottom group, Founder-only switcher/Admin and nine entitlement bindings in each of four menu variants.
- Removal of Badge / Show count / Count and count variants.
- All 86 ZERO charts: exactly one baseline 0 and no category labels.
- All 86 FILLED charts: figure-specific value-axis ticks and mobile chart widths.
- All 288 visible stat tiles: no duplicate unit row and the proposed comparison label present.
- 364 product chart marks checked against their accent variable bindings.
- All four Case study Main frames retain PDF export settings.
A navigation write pass restored 264 links after component changes.
All ten accents pass AA on white; lowest ratio 4.92:1.

Screenshots were shown after the merged menu, tab/count removal, palette and bindings, ZERO charts, unit-specific FILLED scales, stat review fixes, PDF policy, final mobile proofs and updated SPEC.
Key proof nodes: merged mobile Founder 70:10581; palette 72:9824; mobile ZERO chart 43:83; mobile FILLED chart 43:106; stat tile 43:9; Overview 48:889; Rig 51:3510; drawer 53:6373; Founder decisions 79:10314; SPEC 63:10450.
All text and plot marks remain editable; only the original logo is an image asset.
No model was called to generate data or check work. No live data or production state was changed. No application implementation or verified API binding is claimed.
Founder approval and any further review findings remain pending.
## Open questions for the founder

1. Approve or mark changes on the revised frames, the ten proposed accents and the proposed FIXED label vs previous period.
2. Dark mode remains unresolved because the protected base provides light only.
3. Confirm source/API mappings, metric definitions, units and runtime scaling contracts for every logical figure ID. Figma domains and geometry are format-only.
4. Confirm T2's baseline, T4's denominator and T6's graduation-progress definition.
5. Confirm B3's audit/uncertainty protocol and B6's Apollo provenance/comparability.
6. Confirm M3 cohort/kind selection, bands and resolved-prediction eligibility, with tenant isolation.
7. Confirm state/severity names, product-ranking labels, visual-score scale and what counts as a shield.
8. Confirm custom-date interaction, CSV payload and export generation details. Case study PDF access is already resolved by Founder decision 4.
9. Supply existing route targets for CRM, Workspace items, Receipts/Billing/Settings and Admin, plus the founder client-switcher interaction. No new destination screens or client lists were invented.
10. Confirm zero-denominator and missing-measurement semantics without introducing unapproved UI wording.

Claude commits this full updated SPEC to docs/figma/case-studies/SPEC.md and opens the PR. The founder reviews and merges. No work was pushed to main.

## Claude's review of the 28 Oct revision (09:15 PT)

The founder's four decisions are in the frames: one merged side menu, no counts, one accent per product shown as a menu marker and in the charts, and the PDF limited to the client's signed-in users and the founder. The 44 screen IDs are unchanged. To fix in the next pass:

1. **Menu text is clipped.** "Projects" reads "Proiects" in the desktop menu (46:111, both audiences) and the product screens: the descender of the j is cut off. Give the menu item text room for descenders.
2. **The compare toggle shows off on Filled screens** (for example Tiger 49:3211 and 54:8114), but every tile shows "+12.4% vs previous period". On Filled, show the toggle on, or hide the change line when it's off.
3. **The founder menu is missing Skala and Tank.** Today's founder-only items are Skala (where skill versions are approved), Tank, and the Admin links Training (/skala/gold), Law feeds (/zenas/feeds), Feeds (/admin/feeds) and Homes (/admin/homes) (workspace/app/product-nav.ts:23-24, 47-52). The founder audience needs them, under Admin or as their own section.
4. **Accents for the founder to decide:**
   - Zenas #475569 is slate grey. As a menu marker it reads as "disabled".
   - Market Lab #6D28D9, Autumbra #A21CAF and Trigger #BE185D are three close purple-pinks. As small menu dots they're hard to tell apart.

## Answers from the code to open question 9 (route targets)

These routes exist in Workspace today (workspace/app/product-nav.ts):

| Menu item | Route |
|---|---|
| Projects | /matters |
| Tasks | /tasks |
| Data | /data |
| Prices | /prices |
| Billing | /billing |
| Receipts | /ledger (labelled "Ledger" today) |
| Settings | /onboarding |
| Admin | /admin |
| Chats | / (the chat home) |
| CRM | https://crm.tervory.com (Trigger CRM, #392, founder-only until its own design) |

Squad has no single route today: SQUAD_LINKS are the product pages. Case study is the new page from this design (data from #397).

## Answers from the code to the other open questions (carried from the first review)

- **T2, savings:** the ledger's existing baseline cost per row (tank.ledger baseline_cost_usd) minus the actual cost, as Tank's proof (CORE-1) already computes.
- **T4, cache hits:** the share of ledger rows in the period served by a cache rung.
- **T6, graduation progress:** for policies with a candidate in shadow, samples checked out of 200 and agreement against the 99% bar (founder decision, #360).
- **B3:** as implemented in #390: a 200-record seeded sample, checked by hand, with its confidence interval.
- **M3:** as implemented by the Market Lab calibration job: same kind, feed and horizon; resolved predictions only; per tenant.
- **Zero denominators:** show 0, as the ZERO design does.
- **Dark mode:** light only for now.
