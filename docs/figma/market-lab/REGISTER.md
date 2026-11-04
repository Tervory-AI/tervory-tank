# Market Lab briefs and calibration — H7

**Approved 3 Nov 2026, 17:45 PT** (Claude, under the founder's 3 Nov 13:28 delegation): the eight Monthly briefs frames and their wording, at this commit. The illustrative values in the frames (titles, dates, counts) are Figma-only and never reach a live page. Brief detail and Calibration are not drawn yet and are not approved.

**Wave 5 status: new detail/calibration frames remain Proposed.** The eight Monthly briefs approvals above are preserved. Branch `codex/figma-market-lab` was created from `origin/main` at `8857cd3e`. Existing Figma pages, shared mains and production code were not modified. All new work is isolated on [11 · Market Lab · H7 · Proposed](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-37050), page ID `513:37050`.

## Delivery status

| Screen | Desktop 1440 / mobile 375 | Empty, loading, error | Evidence |
| --- | --- | --- | --- |
| Monthly briefs list | Proposed frames created at both widths | All six state frames created | All eight screenshots now captured; original list approval unchanged |
| Brief detail | 12 Proposed frames created | Empty/loading/error at both widths | Wave 5 evidence below |
| Calibration table and chart | Eight Proposed frames created | Empty/loading/error at both widths | Wave 5 evidence below |

**Historical quota stop — superseded by wave 5 below:** the final mobile-error screenshot request returned: “You’ve reached the Figma MCP tool call limit for your Full seat on the Professional plan.” Further Figma creation and validation cannot continue until tool access is restored. No quota bypass was attempted. This push preserves the reviewable first-screen work, not a claim that H7 is complete.

The requested push-after-each-screen sequence stops here at the first screen because of this external limit. Remaining work: mobile error screenshot; detail populated/empty/loading/error at both widths; calibration populated/empty/loading/error at both widths; mobile shared-menu open view; prototype links between list/detail/calibration and Menu; final audits/screenshots; push each remaining screen.

## Monthly briefs frame register

Every frame name ends in Proposed and every viewport carries a visible Proposed review bar plus “Illustrative values · Figma only.” Dates, counts and statuses are illustrative data, not observed delivery receipts.

| State | Width × height | Frame ID | Screenshot | SHA-256 |
| --- | --- | --- | --- | --- |
| Filled · Proposed | 1440 × 1037 | [514:5141](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-5141) | [PNG](screenshots/briefs-filled-1440.png) | `06edf2d0f128b4b11d32090f35715ed3ea7c2510016a86b6de06f437031ffba4` |
| Filled · Proposed | 375 × 1336 | [514:5414](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-5414) | [PNG](screenshots/briefs-filled-375.png) | `94aea962c017b0b4c96dbedd65f94b0d265e128f9bb9fe540096bf9b2fa7bb89` |
| Empty · Proposed | 1440 × 1037 | [514:5483](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-5483) | [PNG](screenshots/briefs-empty-1440.png) | `7d6375b6c043b07a3da71e381857b581e328e9c080a13e0264c5d40caf938a88` |
| Empty · Proposed | 375 × 781 | [514:5603](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-5603) | [PNG](screenshots/briefs-empty-375.png) | `5f3a8c4e6935ab3348bcfb3161fa4b465d8ad26da3aa4a90f3e1cc776398568c` |
| Loading · Proposed | 1440 × 1037 | [514:5623](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-5623) | [PNG](screenshots/briefs-loading-1440.png) | `b8c0423b098ee62a1a67e5baa877256b81a8976e10ec48676395dd493fc423d5` |
| Loading · Proposed | 375 × 781 | [514:5746](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-5746) | [PNG](screenshots/briefs-loading-375.png) | `6a1b396075c68f83a904e2905d844511e542a4bd39862a39cac7e91b3fe544ca` |
| Error · Proposed | 1440 × 1037 | [514:5769](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-5769) | [PNG](screenshots/briefs-error-1440.png) | `4568aadea1952c06301f3c7620e02834e5ff0bbd222d2fc8a2923daafcf60146` |
| Error · Proposed | 375 × 781 | [514:5891](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-5891) | [PNG](screenshots/briefs-error-375.png) | `79f7bde1fd97c09ab91936e1592c94600aa60c56bd24de5f05f3d94a4eb35ad2` |

## Component and styling reuse

- Tiger SimpleTable wrapper `256:74` is cloned and reconfigured; its existing header instance `256:76` remains linked to main `43:389`. The generic main’s unrelated sort/value example layers are hidden in the new headers, matching the actual Tiger override.
- Tiger Pill `256:654` and Action Confirm `256:380` supply status pills and navy-outline actions. Main buttons are white/light with navy borders and text, 48px high; no dark button fill is introduced. Selected tabs use `#e9edf6`.
- Desktop shared Navigation main `180:8387`, set `180:8549`, is instantiated with `Product heading#508:0 = Market Lab`, using the approved shared-menu property from `docs/figma/MCP-MENU-20261103.md`. The shared destination labels are retained, not replaced by invented Market Lab destinations. The new two-tab screen navigation is separate Proposed copy.
- Inter is used for all visible new-screen and menu text, including the per-instance product heading. This overrides typography only on new instances; it does not change shared mains.
- Mobile light bar/logo/Menu reuse `256:175`. The Menu interaction/open view is outstanding because Figma access stopped.
- Palette reuses white, canvas `#f4f6fb`, navy `#001840`, body `#3d4a66`, line `#b8bfd0`, and existing warning `#b45309`. Tables/cards have 8px corners.

The approved shared menu has no Market Lab-specific destination set. Its current CRM destination labels are retained deliberately, following the approved shared-menu register. Do not interpret the inherited CRM destinations as new Market Lab features.

## Product bindings and implementation limits

| Visible information | Existing source | Binding / limit |
| --- | --- | --- |
| Title | `agents/market_lab/core/jobs.py`, saved report `question` | Monthly job currently asks `Where is demand outrunning supply?`; this exact title is reused in the illustrative rows. |
| Date | `agents/market_lab/core/ledger.py`, report `made_at` | Render with existing `workspace/app/market-lab/format.ts` `formatDay`. **Current `tank/market_lab_ml3.py` briefs projection omits `made_at`; this saved date needs to be exposed for implementation. No API change is made by this design task.** |
| Delivery status | saved brief `deliveries[].channel/status/reason` | Email and webhook are separate; one successful channel must not imply both succeeded. Proposed title-case labels map directly to existing lowercase states. |
| Citations | saved report `citations[]` | Count the actual stored citations. Detail must preserve claim/date/source URL and page/row/prediction reference where present; no fabricated citation targets. |
| Sample values | Proposed design-only data | Dates 1 Nov / 1 Oct / 1 Sep 2026; counts 3 / 2 / 3; Sent/Pending/Suppressed/Held examples. No real saved report/delivery is claimed. |

Brief-detail continuation: bind title/question, date/made_at, answer and citation objects from the same stored report ID, with separate channel statuses. Do not substitute a feed description for the brief’s saved answer, or infer a successful delivery from a report existing. Use existing `Open stored source` wording. A held brief can still contain citations that later fail the evidence gate; hold reasons must not be silently converted to delivery success.

Calibration continuation: reuse the editable existing Calibration components `50:2434` (desktop filled), `50:2504` (mobile filled), and set `50:2539`. Proposed table columns should identify warning pair, frozen horizon, confidence, actual hit rate and sample count. `core/warnings.py` sets prediction `kind=config.id` and `feed=config.source`; `core/predictions.py` groups resolved originals by `(kind, feed, horizon_seconds)`, returns per-bin confidence/rate/count and excludes unknown or unmeasurable predictions. Do not pool different horizons or average bin means without sample weights. Unknown stays an em dash; no fabricated 0% chart in empty/error states.

The existing chart’s approved-register wording is `Prediction confidence vs actual hit rate`, `Confidence`, `Actual hit rate`, and `Confidence – –  /  Actual hit rate —` (`docs/figma/case-studies/SPEC.md`). The existing 75.0% / 71.4% figure is illustrative only. Proposed example pair labels must come from engine configuration, such as Port of Los Angeles container volume / Watched product availability; do not claim causal relationships or live forecast accuracy. No calibration screen has yet been created.

## Copy inventory — exact strings

Any wording without an existing product/register match below is explicitly **Proposed** and requires founder approval. These strings are marked Proposed through the visible frame review bar and this inventory. Reused wording does not approve the new screen or its behavior. Data examples remain Proposed even where individual digits already occur elsewhere.

| Exact visible string | Status / source |
| --- | --- |
| 1 Nov 2026 | **Proposed illustrative DATA**, not a saved observation |
| 1 Oct 2026 | Existing exact text: `workspace/app/market-lab/model.test.ts` |
| 1 Sep 2026 | **Proposed illustrative DATA**, not a saved observation |
| 2 | Existing exact text: `workspace/app/dashboard-greeting.tsx` |
| 2 · Sources cited | **Proposed illustrative DATA**, not a saved observation |
| 3 | Existing exact text: `workspace/app/layout.tsx` |
| 3 · Sources cited | **Proposed illustrative DATA**, not a saved observation |
| Account settings | Existing exact text: `workspace/app/zenas/view.tsx` |
| All products | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Billing | Existing exact text: `workspace/app/billing/page.tsx` |
| Business | Existing exact text: `workspace/app/page.tsx` |
| CRM | Existing exact text: `workspace/app/base/vault.test.ts` |
| Calendar | Existing exact text: `workspace/app/market-lab/format.ts` |
| Calibration | Existing exact text: `docs/figma/case-studies/SPEC.md` |
| Cases | Existing exact text: `workspace/app/skala/view.tsx` |
| Channels | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Chat bot | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Citations | Existing exact text: `workspace/app/zenas/feeds/board.tsx` |
| Clients | Existing exact text: `workspace/app/control/client-squads.tsx` |
| Composer | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Contacts | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Date | Existing exact text: `workspace/app/dashboard-greeting.tsx` |
| Delivery status | **Proposed presentation wording**; existing data/brief concepts where applicable; not claimed approved |
| Email | Existing exact text: `workspace/app/base/view.tsx` |
| Google posts | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Google reviews | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Held | **Proposed presentation wording**; existing data/brief concepts where applicable; not claimed approved |
| Illustrative values · Figma only. | Existing exact text: `docs/figma/TIGER-POSITION-FRAMES.md` |
| Inbox | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Invoices | Existing exact text: `workspace/app/billing/screen.tsx` |
| Leads | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Loading… | Existing exact text: `workspace/app/onboarding/page.tsx` |
| Market Lab | Existing exact text: `workspace/app/page.tsx` |
| Marketing | Existing exact text: `docs/figma/MCP-FRAMES.md` |
| Menu | Existing exact text: `workspace/app/shell.tsx` |
| Monthly briefs | **Proposed presentation wording**; existing data/brief concepts where applicable; not claimed approved |
| Monthly briefs could not be loaded. | **Proposed presentation wording**; existing data/brief concepts where applicable; not claimed approved |
| No monthly briefs yet. | **Proposed presentation wording**; existing data/brief concepts where applicable; not claimed approved |
| Opportunities | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Pending | **Proposed presentation wording**; existing data/brief concepts where applicable; not claimed approved |
| Proposed | Existing exact text: `workspace/app/admin/console.tsx` |
| Quotes | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Receipts | Existing exact text: `workspace/app/autumbra/receipts/weekly/[tenant]/page.tsx` |
| Sales | Existing exact text: `docs/figma/MCP-FRAMES.md` |
| Sent | **Proposed presentation wording**; existing data/brief concepts where applicable; not claimed approved |
| Settings | Existing exact text: `workspace/app/skala/view.tsx` |
| Sources cited | Existing exact text: `docs/figma/case-studies/SPEC.md` |
| Suppressed | **Proposed presentation wording**; existing data/brief concepts where applicable; not claimed approved |
| Tasks | Existing exact text: `workspace/app/tiger/view.tsx` |
| Title | Existing exact text: `workspace/app/prices/page.tsx` |
| Try again | Existing exact text: `workspace/app/billing/page.tsx` |
| Voice | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |
| Webhook | **Proposed presentation wording**; existing data/brief concepts where applicable; not claimed approved |
| Where is demand outrunning supply? | **Proposed wording**; no exact existing product/register match found |
| Write | Existing exact text: `workspace/app/feedback-buttons.tsx` |
| Writing | Existing exact text: `docs/figma/MCP-FRAMES.md` |
| ⌄ | Existing exact text: `docs/figma/MCP-CHANGES-20261103.md` |

## IDs and verification

New page ID `513:37050`; eight new frame IDs are above. The complete **522 new surviving frame/descendant IDs**, component-instance/main IDs, and exact text inventory are in [list-evidence.json](list-evidence.json). Original Figma nodes modified: none. No existing frame ID was replaced.

Checks in [list-checks.json](list-checks.json): all eight frames have the expected 1440/375 width and Proposed naming; no visible non-Inter text; no dark surface fills; no product-content bounds overflow. The audit reports two inherited shared-menu container edges in each desktop frame: the source’s 1px stroke inset makes their right edge exceed the parent by 1px. The source menu clips its scroll area; no text box overflow is reported. This inherited geometry is disclosed rather than claimed fixed.

Visual inspection covered filled desktop/mobile, mobile empty/loading and desktop error. All seven captured screenshots are committed for review. The eighth screenshot and mobile menu-open/prototype behavior remain unverified. Initial horizontal-container sizing and unrelated generic header sample text were corrected on the new frames before final captures.

Documentation/image checks: valid evidence JSON; exactly eight frames / four states × two widths; every frame Proposed; exactly seven nonempty PNGs; all recorded IDs unique; `git diff --check`; changed files restricted to `docs/figma/market-lab/`. No application tests apply because no runtime code changed.

## Wave 5 continuation — Proposed, 4 Nov 2026

Continued on `codex/figma-w5`, same PR #685. The earlier quota-stop and outstanding-work paragraphs describe the prior attempt; detail/calibration and the missing monthly-list error PNG are now delivered below. Existing Monthly briefs approvals are preserved. No new approval is implied.

Brief detail preserves each illustrative row’s date and distinct Email/Webhook statuses, with saved-answer, claim, source-URL/date and optional page/row/prediction slots. These are explicitly marked placeholders; Open stored source is disabled until a real saved citation URL is available. No fabricated citation link, research result or delivery receipt is claimed. List/detail/calibration/back/retry prototype links are recorded in [prototype-links.json](evidence/w5/prototype-links.json). Mobile shared-menu opening remains an inherited presentation control, not a verified navigation flow.

Calibration keeps `(kind, feed, frozen horizon)` groups separate. The desktop table and mobile stacked rows show confidence, actual hit rate and sample counts; the chart shows the first 30-day group only. Its dot is x=75%, y=5/7 (71.4%), n=7; the dashed diagonal is an ideal reference, not an empirical curve. The separate 7-day example is 2/4=50%, n=4 and is not pooled or plotted as part of the 30-day group. All values, group placeholders and wording are Proposed. Empty/error/loading states use em dashes rather than fabricated measured zeroes. [Exact plot correction and node IDs](evidence/w5/calibration-point-fix.json).

[Full editable-layer/font/wording read-back](evidence/w5/final-readback.json), [all visible wording marked Proposed](evidence/w5/copy-proposed.json), and [frame dimensions / PNG SHA-256](evidence/w5/frames.json). All 20 new frames use Inter; only original logo image assets are raster content. Charts remain linked case-study components with instance-level geometry/visibility overrides and a separate editable point; shared masters and approved list wording were not rewritten. Existing Tiger list/header/pill reuse remains intact. The authoring script is the initial construction snapshot; the final read-back and plot-correction ledger record the subsequent exact chart repair.

| Screen / state | Size | Frame | Screenshot |
| --- | --- | --- | --- |
| Brief detail / Report 1 · Proposed | 1440×1531 | [566:395](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-395) | [PNG](evidence/w5/brief-detail-report-1-1440.png) |
| Brief detail / Report 2 · Proposed | 1440×1245 | [566:601](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-601) | [PNG](evidence/w5/brief-detail-report-2-1440.png) |
| Brief detail / Report 3 · Proposed | 1440×1531 | [566:799](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-799) | [PNG](evidence/w5/brief-detail-report-3-1440.png) |
| Brief detail / Report 1 · Proposed | 375×1625 | [566:2140](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-2140) | [PNG](evidence/w5/brief-detail-report-1-375.png) |
| Brief detail / Report 2 · Proposed | 375×1319 | [566:2249](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-2249) | [PNG](evidence/w5/brief-detail-report-2-375.png) |
| Brief detail / Report 3 · Proposed | 375×1625 | [566:2350](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-2350) | [PNG](evidence/w5/brief-detail-report-3-375.png) |
| Brief detail / Empty · Proposed | 1440×1037 | [566:2459](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-2459) | [PNG](evidence/w5/brief-detail-empty-1440.png) |
| Brief detail / Loading · Proposed | 1440×1037 | [566:2634](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-2634) | [PNG](evidence/w5/brief-detail-loading-1440.png) |
| Brief detail / Error · Proposed | 1440×1037 | [566:2812](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-2812) | [PNG](evidence/w5/brief-detail-error-1440.png) |
| Brief detail / Empty · Proposed | 375×900 | [566:2989](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-2989) | [PNG](evidence/w5/brief-detail-empty-375.png) |
| Brief detail / Loading · Proposed | 375×900 | [566:3067](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-3067) | [PNG](evidence/w5/brief-detail-loading-375.png) |
| Brief detail / Error · Proposed | 375×900 | [566:3148](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-3148) | [PNG](evidence/w5/brief-detail-error-375.png) |
| Calibration / Filled · Proposed | 1440×1378 | [567:941](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=567-941) | [PNG](evidence/w5/calibration-filled-1440.png) |
| Calibration / Empty · Proposed | 1440×1037 | [567:1193](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=567-1193) | [PNG](evidence/w5/calibration-empty-1440.png) |
| Calibration / Loading · Proposed | 1440×1037 | [567:1369](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=567-1369) | [PNG](evidence/w5/calibration-loading-1440.png) |
| Calibration / Error · Proposed | 1440×1037 | [567:1548](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=567-1548) | [PNG](evidence/w5/calibration-error-1440.png) |
| Calibration / Filled · Proposed | 375×1311 | [567:1726](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=567-1726) | [PNG](evidence/w5/calibration-filled-375.png) |
| Calibration / Empty · Proposed | 375×900 | [567:1846](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=567-1846) | [PNG](evidence/w5/calibration-empty-375.png) |
| Calibration / Loading · Proposed | 375×900 | [567:1925](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=567-1925) | [PNG](evidence/w5/calibration-loading-375.png) |
| Calibration / Error · Proposed | 375×900 | [567:2007](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=567-2007) | [PNG](evidence/w5/calibration-error-375.png) |
