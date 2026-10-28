# Client case studies and product dashboard template

Status: ready for founder review; approval is pending. **Founder decisions of 28 Oct 2026 07:40 PT are at the end of this file and override anything above them.**
Date: 28 October 2026.
File: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS
Page: 1 · Case studies (42:2).
SPEC frame: 63:10450. SPEC overview proof frame: 63:10451.
Repository destination: docs/figma/case-studies/SPEC.md (committed by Claude from the SPEC frame, word for word).

This is a Figma-only delivery. No application code, live client records, production data, model calls, secrets, billing, sign-in or pricing work was used. No repository branch, commit or push was created by the designer.

The approved page 0 · Dashboards (approve first), frame 12:2 and frame 10:115 were preserved. Frame 12:2 supplied the fonts, palette, shell and logo. No new Figma file was created.

## Screen frames

Every desktop frame is 1440 × 900; every mobile frame is 375 × 812. Content scrolls vertically. The sidebar or mobile bar stays fixed. The long content contains every configured figure, including at zero.

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

Supporting delivery nodes: Variables 42:52; Components 43:2; Menu and page template 46:20; Mobile template and drawers 53:5464; mobile drawer ZERO 53:6328; mobile drawer FILLED 53:6373; SPEC 63:10450.

Prototype entry flows: Desktop · ZERO 48:554; Desktop · FILLED 48:889; Mobile · ZERO 54:5914; Mobile · FILLED 54:6208. Choose a flow in Present. Navigation stays in that flow's width and data state.

## Components and variants

All component variants use auto layout. Chart plotting primitives sit inside an editable plot frame. Screens retain their component instances. Components are token-bound; no screen is a flattened screenshot.

| Component set | Set node ID | Variants and node IDs |
| --- | --- | --- |
| Stat tile | 43:14 | State=Zero: 43:4; State=Filled: 43:9 |
| Period picker | 43:23 | Period=7 days: 43:15; Period=30 days: 43:17; Period=90 days: 43:19; Period=Custom: 43:21 |
| Compare to previous | 43:30 | State=Off: 43:24; State=On: 43:27 |
| Export | 43:35 | Format=PDF: 43:31; Format=CSV: 43:33 |
| Line chart | 43:129 | Size=Desktop, State=Zero: 43:37; Size=Desktop, State=Filled: 43:60; Size=Mobile, State=Zero: 43:83; Size=Mobile, State=Filled: 43:106 |
| Bar chart | 43:218 | Size=Desktop, State=Zero: 43:130; Size=Desktop, State=Filled: 43:152; Size=Mobile, State=Zero: 43:174; Size=Mobile, State=Filled: 43:196 |
| Histogram | 43:308 | Size=Desktop, State=Zero: 43:220; Size=Desktop, State=Filled: 43:242; Size=Mobile, State=Zero: 43:264; Size=Mobile, State=Filled: 43:286 |
| Table header | 43:401 | Sort=None: 43:389; Sort=Ascending: 43:393; Sort=Descending: 43:397 |
| Table row | 43:408 | State=Zero: 43:402; State=Filled: 43:405 |
| Side menu item | 43:427 | State=Default, Badge=Off: 43:409; State=Default, Badge=On: 43:412; State=Hover, Badge=Off: 43:415; State=Hover, Badge=On: 43:418; State=Active, Badge=Off: 43:421; State=Active, Badge=On: 43:424 |
| Product tab | 43:432 | State=Default: 43:428; State=Active: 43:430 |
| Table | 44:31 | State=Zero: 44:3; State=Filled: 44:17 |
| Calibration | 50:2539 | Size=Desktop, State=Zero: 50:2399; Size=Desktop, State=Filled: 50:2434; Size=Mobile, State=Zero: 50:2469; Size=Mobile, State=Filled: 50:2504 |
| Workspace menu | 46:111 | Audience=Client: 46:21; Audience=Founder: 46:66 |
| Page template / Desktop | 46:698 | State=Zero: 46:112; State=Filled: 46:405 |
| Page template / Mobile | 53:6327 | State=Zero: 53:5465; State=Filled: 53:5896 |

Stat tile properties: Label, Value, Change and Unit.
Chart properties: Title; calibration uses editable title text, band ticks and two series.
Table row properties: Label and Value. Header variants represent sort order.
Menu item properties: State, Badge, Label, Show count and Count.
Workspace menu: Audience=Client or Founder, plus Has Base / Has Tiger / Has Market Lab / Has Rig / Has Zenas / Has Trigger / Has Tisan / Has Radix / Has Autumbra.
Page templates: State, Page, Client name, and the same nine Has product switches for tabs. Unused stat/chart slots are hidden.
The application must supply the same tenant entitlement set to menu items, tabs and routes.

No donut is used or retained: the requested figures do not require a share chart. Work by code / cache / model uses counts in a bar chart.

## Foundations

Variable collections: Case studies / Primitives (VariableCollectionId:42:3, Value mode) and Case studies / Tokens (VariableCollectionId:42:4, Light mode). There are 47 variables: seven primitive colours, ten semantic colours, eight spacing values, five radii, nine type sizes, two stroke widths, two font families and four font styles.

Palette from frame 12:2, stored at the source's precision:
- Navy: RGB 0, 0.094, 0.251.
- Canvas: RGB 0.957, 0.965, 0.980.
- White: RGB 1, 1, 1.
- Muted text: RGB 0.239, 0.290, 0.400.
- Border/grid: RGB 0.722, 0.749, 0.816.
- Active/hover navy: RGB 0.133, 0.204, 0.353.
- Existing green: RGB 0.118, 0.478, 0.275; retained as a token, unused for claims.

Semantic colour tokens: canvas, surface, text, muted, sidebar, inverse, active, border, chart and success. They alias primitives.
Spacing: 0, 8, 16, 24, 32, 40, 48, 64 px. New layout gaps and padding use the 8-point scale.
Radii from the base: 0, 8, 10, 12, 16 px. Cards use 16; navigation and controls use 8.
Type: Jost Light for headings and values; Inter Regular/Medium/Semi Bold for labels and controls. Sizes: 12, 13, 14, 15, 17, 18, 24, 34, 40 px. The primary product value is 40; other stat values are 34.
Desktop shell: 220 px sidebar; main horizontal padding 64. Mobile content padding: 24; charts are 327 px wide.
The original logo image is cloned from 12:4, with no redrawing.
Light mode only. The approved base has no dark-mode system.

All products consistently use the approved navy for plotted data. Calibration uses a muted dashed confidence reference and navy solid hit-rate series. Product names and line patterns carry meaning alongside colour. No unapproved product palette was invented.
Contrast calculations: navy/white 17.44:1; muted/white 8.87:1; navy/canvas 16.12:1; white/active 12.30:1. Data strokes and axes use navy; grid and card borders are supporting lines.
Charts have five equally spaced gridlines. FILLED reference ticks are 0/25/50/75/100; actual axes are DATA and must be generated from the approved source values. ZERO chart measurements and stat values stay zero. Long category labels fit inside mobile plots.

## Template, navigation and behaviour

One page template consists of the Workspace shell, header, controls, product tabs, stat rows, chart grid and table. Product pages configure the named stat/chart slots with the figure register below. Adding a product means adding figures and entitlement-driven navigation, not designing a new page.

Overview aggregates the client's own products. It shows T1–T6 and a product spend table.
Case study summary shows T1–T6 and one primary outcome per owned product. Its table pairs each product name with its primary metric label. It contains no narrative client claims.
Every product page contains all its own figures plus T1–T6 scoped to that product.

Primary values: Base B1; Tiger G1; Market Lab M1; Rig R1; Zenas Z1; Trigger V1; Tisan S1; Radix D1; Autumbra A1. Overview and Case study emphasise T1.

Menu order: Overview; Base; Tiger; Market Lab; Rig; Zenas; Trigger; Tisan; Radix; Autumbra; Case study; Receipts; Settings.
Only entitled products appear for a real tenant. Figma demonstrates the all-products entitlement configuration. Founder-only Audience=Founder adds the client switcher; Client hides it.
Product badges use the corresponding primary figure count. ZERO badges are 0. Overview, Case study, Receipts and Settings have no invented count.
Receipts and Settings are existing destinations; this brief supplies no new screens for them, so no new destination screens or wording were invented.

Mobile uses a drawer rather than a bottom bar because thirteen destinations would crowd a 375 px bottom bar. The menu button opens the matching ZERO/FILLED drawer; × closes it. Product tabs scroll horizontally. Cards, charts and table rows stack vertically.
There are 624 navigation links across the screen menus, tabs, drawer buttons and drawer destinations. The active current destination does not navigate to itself.
The period picker cycles through 7 days / 30 days / 90 days / Custom to demonstrate its states. Compare toggles Off/On with a moving knob. Header clicks cycle None/Ascending/Descending to demonstrate sortable-header states. These Figma interactions do not query or change data.
No extra custom-date controls, export messages, error wording or empty-state wording were added.

Every client must receive this template automatically at sign-up, populated only with their entitled products. This requirement introduces no sign-in screen work. Builders must keep every configured chart present, with zero values until real data arrives.

PDF/CSV buttons are designed controls. No CSV file or download service was implemented in Figma.
Case study full-content PDF export targets are its Main frames, avoiding viewport cropping:
- Desktop ZERO: I48:1224;46:156.
- Desktop FILLED: I48:1561;46:449.
- Mobile ZERO: I54:6502;53:5467.
- Mobile FILLED: I54:6796;53:5898.
These Main frames have PDF export settings. Claude exports approved frames for builders.

## DATA register

Every FILLED value, chart point, bar height, category placeholder, total, badge and change is DATA used only to show formatting. These are not a real or sample client dataset, do not make client claims, and never ship. Repeated numbers do not define arithmetic relationships.
ZERO contains zero measurements, axes and baseline marks. Known reference bands remain visible. Unknown state/product/severity labels use 0 in ZERO and bracketed format placeholders in FILLED.

The IDs below are logical source figure IDs assigned to the founder's figure list. They are not claims that an API or database binding was verified. Builders must map them to tenant-scoped sources after approval.

| Source figure ID | Product | FIXED label | FILLED format-only value | ZERO value | Format / unit |
| --- | --- | --- | --- | --- | --- |
| T1 | Tank | Spend | $3,691.70 | $0.00 | USD |
| T2 | Tank | Savings vs baseline cost | $8,557.00 | $0.00 | USD |
| T3 | Tank | Cost per task | $0.20 | $0.00 | USD |
| T4 | Tank | Cache hits | 64.2% | 0% | % |
| T5 | Tank | Work by code / cache / model | 18 420 | 0 | integer counts by Code, Cache, Model |
| T6 | Tank | Graduation progress | 64.2% | 0 | percentage; progress-band bars |
| B1 | Base | Records verified | 18 420 | 0 | integer |
| B2 | Base | Cost per verified record | $0.20 | $0.00 | USD |
| B3 | Base | Measured accuracy | 98.5% ± 1.7 | 0% ± 0 | 200-record audit |
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
- F.unit is the unit in the register. Empty unit fields remain empty; no extra wording is added.
- F.value, F.change, F.series, F.axisTicks, totals and table cells must share the selected period, tenant and product scope.

Additional DATA fields:
- C1.clientName: display-name string, shown as [Client name] in Figma. The founder switcher uses the selected client's display name. No real client identity was used.
- C2.period: one of the four FIXED picker labels; default 30 days. Table period headers follow this selection.
- C3.productCount: integer with space grouping, sourced from the product's primary figure ID listed above; ZERO 0. Badge visibility follows product entitlement.
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

Source figure T6 is represented by progress-band bars and a percentage footer. Its exact operational definition remains an open question.
All time-series dates/ticks are DATA; the displayed 1 / 15 / 30 are format-only day positions. Histogram and calibration reference percentages are DATA axis fields.
Do not ship any Figma placeholder, bracketed category, chart geometry or fabricated client text.

## FIXED text register for founder approval

The following is the complete screen and component copy inventory. These labels, units and symbols require founder approval before shipping.

Navigation and identity labels:
Overview; Case study; Case study summary; Base; Tiger; Market Lab; Rig; Zenas; Trigger; Tisan; Radix; Autumbra; Receipts; Settings; Product.

Controls:
7 days; 30 days; 90 days; Custom; Compare to previous; Export PDF; Export CSV.

Shared Tank labels:
Spend; Savings vs baseline cost; Cost per task; Cache hits; Work by code / cache / model; Graduation progress; Code; Cache; Model.

Base:
Records verified; Cost per verified record; Measured accuracy; 200-record audit; Confidence histogram; By state; vs Apollo; Apollo.

Tiger:
Pages watched; Checks run; Changes caught; Alerts sent; Price-change histogram; Time to detect a change.

Market Lab:
Questions answered; Sources cited; Prediction confidence vs actual hit rate; Active feeds; Confidence; Actual hit rate.
Legend string: Confidence – –  /  Actual hit rate —.

Rig:
Searches; No-result searches; Setups built; Quotes sent; Quotes that became estimates or invoices; Estimates; Invoices; Most-searched products.

Zenas:
Questions; Cited answers; Criminal questions refused; Sources per answer; Drafts.

Trigger:
Drafts; Checker issues per draft; Acceptance rate; Voice-rule hits.

Tisan: Sites built; Visual scores.
Radix: Scans; Findings by severity.
Autumbra: Checks; Incidents; Shields.

Units and notation:
USD; %; min; ±; the signed change prefix + or −; the summary separator ·.
Control symbols: ☰ opens the menu; × closes it; ⌄ marks the founder client switcher; ↕ / ↑ / ↓ mark table sort states.
Numeric values, tick labels, badges and [Client name] / [State] / [Product] / [Severity] are DATA, not fixed copy.

Documentation-only text, never product UI:
Variables; Frame 12:2 · Light; sidebar; canvas; surface; text; muted; active; border; success.
Variable board type line: Jost Light 34 / 40 · Inter Regular 14 / 15 · Inter Semi Bold 13 / 17.
Variable board spacing line: Spacing 8 / 16 / 24 / 32 / 48 / 64 · Radius 8 / 10 / 12 / 16.
This SPEC and layer/component/property names are handoff documentation, not product copy.
No "no data" wording, invented client narrative, new empty state or error message was added.

## Proof and validation

Changed page: 1 · Case studies, 42:2. The screen and component IDs above identify the complete delivery.
44 screen instances: 22 desktop and 22 mobile, spanning Overview, Case study and nine products, each in ZERO and FILLED.
16 component sets contain 47 auto-layout component variants. There are 47 variables.
The deterministic Figma audit passed: dimensions, zero stat values, five chart gridlines, per-product chart coverage and chart widths. Screen content retains every required source figure.
A later navigation audit confirmed all 624 links after product badge binding.
Native screenshots were shown after variables, components, template, Overview, Case study, each product, mobile and SPEC. Full-content screenshots precede the final viewport crop; final screenshots show the scroll viewport, menu badges and phone-width calibration.
Colour contrast was calculated from the source palette, with text pairs at 8.87:1 or higher.
All Figma screen text, charts and data marks remain editable. The brand logo remains an image asset.
No model was called to create data or check work. No live data was read or changed.
Founder review and any separate review findings are still pending; address requested changes before approval.
No claim of production implementation, live API binding, CSV generation or user acceptance is made.

## Open questions for the founder (as delivered)

1. Approve or mark changes on all frames and every FIXED string above.
2. Dark mode: the approved base supplies light only. Provide an approved dark palette before dark designs are added.
3. Confirm source/API field mappings, metric definitions, units, periods and denominators for every logical figure ID. No live API contracts were available in this Figma-only task.
4. Confirm baseline cost for T2, cache-hit denominator for T4, and the meaning and denominator of graduation progress T6.
5. Confirm B3's 200-record audit protocol and uncertainty method; confirm Apollo comparison provenance and comparability for B6.
6. Confirm calibration cohort/kind selection, confidence bands and resolved-prediction eligibility for M3, with strict tenant isolation. No new filter copy was invented.
7. Confirm state names, severity taxonomy, ranked-product labels, visual-score scale and what counts as a shield. Figma uses DATA fields for these.
8. Confirm zero-denominator comparison behaviour and missing-measurement semantics. The requested ZERO design displays zeros; no unapproved explanatory/error copy was added.
9. Confirm custom-date interaction and CSV/PDF download behaviour. No extra calendar, success text or error wording was invented.
10. Confirm the founder client-switcher interaction and existing Receipts/Settings destinations. No new screens were supplied for them.
11. Approve the primary figure selected for each product and the resulting count badges; confirm all chart units/domains before real data is rendered.
12. Approve the shared navy data colour, or provide approved distinct product colours. Every product currently uses navy consistently.
13. Confirm the public/shared Case study PDF's identity and permission rules. The design uses [Client name] only and contains no client claims.

---

## Founder decisions, 28 Oct 2026 07:40 PT (override the above)

1. **One merged menu.** Overview replaces Dashboard. Then the client's products (Base, Tiger, Market Lab, Rig, Zenas, Trigger, Tisan, Radix, Autumbra, entitled only), then Case study, then the existing Workspace items (Chats, Projects, Squad, Tasks, Data, Prices), then Receipts (the Ledger), Billing and Settings at the bottom. Founder-only items (client switcher, Admin) stay founder-only.
2. **Side menu only, no counts.** Remove the product tab row from every page, and remove the count badges from the menu. On mobile the drawer is the only navigation.
3. **One accent colour per product.** Navy stays the base; each product gets its own accent for its charts and its menu marker, proposed in Figma for the founder to approve, each meeting WCAG AA on white.
4. **Case study PDF: the client and the founder only.** Downloaded by signed-in users of that client or by the founder; no public or share link. The client shares it themselves if they choose.

## Claude's review notes, 28 Oct 2026 (for the next design pass)

- ZERO charts show "0" on every gridline and "0 0 0" category labels. ZERO shows one 0 at the baseline and no category labels.
- FILLED charts use a 0–100 axis for money and counts. Axes scale to the figure's own unit and range (for example $0–$4,000).
- Stat tiles repeat the unit ("$0.00" above "USD", "64.2%" above "%"). Show the unit once.
- The change line ("+12.4%") has no label saying what it compares to. Add one short FIXED label for founder approval, for example "vs previous period".

## Answers to the open questions Claude can settle from the code

- T2 savings: the ledger's existing baseline cost per row (tank.ledger baseline_cost_usd) minus the actual cost, as Tank's proof (CORE-1) already computes.
- T4 cache hits: the share of ledger rows in the period served by a cache rung.
- T6 graduation progress: for policies with a candidate in shadow, samples checked out of 200 and agreement against the 99% bar (founder decision, #360).
- B3: as implemented in #390 (200-record seeded sample, checked by hand, with its confidence interval).
- M3: as implemented by the Market Lab calibration job (same kind, feed and horizon; resolved predictions only; per tenant).
- Q8 zero denominators: show 0, as the ZERO design does.
- Q9 custom dates and Q10 the client switcher: a date-range control and a client list need their own frames; listed for the next design pass.
- Q2 dark mode: light only for now.
