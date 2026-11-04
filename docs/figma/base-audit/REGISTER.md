# Base audit and client case-study template

Every frame: **Proposed — not approved**. All new wording and numeric examples are Proposed. Figma [file](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS), page `516:3152`. Branch `codex/figma-base-audit`, based on `origin/main` `8857cd3e`.

## Base case-study audit · F12

| State | Width | Frame ID | Status | Screenshot |
| --- | --- | --- | --- | --- |
| Ready | 1440 | [516:3153](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-3153) | Proposed | [PNG](screenshots/audit-ready-1440.png) |
| Ready | 375 | [516:3458](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-3458) | Proposed | [PNG](screenshots/audit-ready-375.png) |
| Empty | 1440 | [516:3791](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-3791) | Proposed | [PNG](screenshots/audit-empty-1440.png) |
| Empty | 375 | [516:4061](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-4061) | Proposed | [PNG](screenshots/audit-empty-375.png) |
| Loading | 1440 | [516:4338](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-4338) | Proposed | [PNG](screenshots/audit-loading-1440.png) |
| Loading | 375 | [516:4608](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-4608) | Proposed | [PNG](screenshots/audit-loading-375.png) |
| Error | 1440 | [516:4885](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-4885) | Proposed | [PNG](screenshots/audit-error-1440.png) |
| Error | 375 | [516:5158](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-5158) | Proposed | [PNG](screenshots/audit-error-375.png) |

The audit is founder-only, matching `tank/base_audit_commands.py`. Existing white shared-menu and CRM action instances are reused without changing their main components. Chart/stat/table/control instances reuse the case-study library from `docs/figma/case-studies/SPEC.md`. Inter throughout, light canvas/panels, navy primary buttons. All content is editable; only the original logo is raster.

### Wording and example data

[audit.json](audit.json) records content strings and node IDs. Every frame says Proposed and its header says “Proposed wording and example data”. All unsourced wording is **Proposed**, including the audit page title, Hand audit, Reviewed, 95% confidence interval, Draw 200-record sample, Download audit CSV, Upload checked CSV, View receipts, Source scores and explanatory/loading/error text. Existing labels include 200-record audit, Measured accuracy, Confidence histogram, Cost per verified record, Records verified, Recorded spend, Founder only and period/compare/export controls. Source display names are Proposed human-readable forms of existing categories.

Ready illustrates 197 correct / 3 wrong / 0 unsure out of 200 reviewed: 98.5%, 95% Wilson interval 95.68%–99.49%. Histogram counts are 10 / 20 / 50 / 120 in bands 0–39 / 40–59 / 60–79 / 80–100, totaling 200; widths reflect the confidence ranges. Ledger format example: $40 / 200 verified records = $0.20. These are Proposed examples, never client measurements. Remaining source-score zeros illustrate formatting, not empirical accuracy.

### Source contracts

- `tank/base_audit.py:21`: 200 target records; `measure` computes resolved-verdict accuracy and the Wilson interval. Unsure is not correct. CSV start/export/review uses `tank/base_audit_commands.py`.
- `tank/base_audit.py`: recorded confidence bands and campaign histogram; confidence is never inferred from a verified flag.
- `tank/base_queries.py:80`: ledger spend and verified population. Missing prices/receipts must remain unavailable, not silently zero.
- `tank/base_reliability.py:32`: explicit human field verdicts generate per-source/per-field scores, counts and Wilson lower bound. Platform aggregates remain founder-only.

### Validation

All eight audit frames passed Inter and content-bounds checks. Original component instances, editable plots and auto-layout remain. Screenshots were visually reviewed and histogram geometry adjusted. No live data, credential, application or shared-component changes. Client template progress and quota blocker are recorded below.

## Client case-study template · incomplete

The Figma account reached its MCP tool-call quota while creating the remaining states. Both `use_figma` and `get_screenshot` return: “You've reached the Figma MCP tool call limit for your Full seat on the Professional plan.” No retry, credential, alternative account or paid upgrade was used to bypass this limit.

Ready and Empty were created at both widths, but their screenshots and visual validation could not be completed. Loading and Error were **not created**. This screen is not complete or ready for approval.

| State | Width | Frame ID | Status | Screenshot |
| --- | --- | --- | --- | --- |
| Ready | 1440 | [518:6969](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=518-6969) | Proposed; unvalidated | Pending — quota |
| Ready | 375 | [518:7555](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=518-7555) | Proposed; unvalidated | Pending — quota |
| Empty | 1440 | [518:8159](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=518-8159) | Proposed; unvalidated | Pending — quota |
| Empty | 375 | [518:8746](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=518-8746) | Proposed; unvalidated | Pending — quota |
| Loading | 1440 | Not created | Proposed; pending | Pending |
| Loading | 375 | Not created | Proposed; pending | Pending |
| Error | 1440 | Not created | Proposed; pending | Pending |
| Error | 375 | Not created | Proposed; pending | Pending |

Created node IDs are in [client-template.json](client-template.json). This template contains all product configurations from the SPEC in one scrolling review document: T1–T6, B1–B6, G1–G6, M1–M4, R1–R6, Z1–Z5, V1–V4, S1–S2, D1–D2 and A1–A3. Thirteen configured charts include both confidence/price-change histograms and calibration, plus all stat measurements, period picker, compare control, PDF/CSV export and sortable product table. Ready and Empty both use zero data to demonstrate the required no-data convention. Product availability must follow tenant entitlements in implementation; this review template enumerates all configurations, not a claim that a client owns all products.

Source: `docs/figma/case-studies/SPEC.md`. No founder-owned frame or existing shared component was changed. New global heading/description/loading/error/PDF-explanation copy in `build-frames.js` is **Proposed**, even where it summarizes an existing policy. The proposed label “vs previous period” is not newly approved; comparison rows remain hidden while Compare is off. Zero charts hide footer totals and category labels and preserve one baseline 0; final visual verification remains pending because of the quota. PDF access remains signed-in client members or founder only; no public sharing design or route is added.

### Resume work after Figma access returns

1. Validate the four created client frames and capture full-content native Figma PNGs.
2. Run `build-frames.js` with mode `Client case-study template` and selected states `[2,3]` to create Loading/Error; do not rerun `[0,1]` or recreate existing frames.
3. Check all 13 figures, zero-chart marks/categories/baseline, Inter typography, light surfaces, control styles and bounds in every state. Record the remaining IDs, screenshots and wording inventory, push and report.

No complete client-template validation is claimed. The Base audit PNGs remain available above.
