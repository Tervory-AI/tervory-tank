# Market Lab briefs and calibration — H7

**Latest brief-detail addition:** [Confidence and history frame slots](#confidence-and-history-frame-slots--proposed-4-nov-2026) are **Proposed**, added 4 Nov 2026 at both widths. Current slot links and screenshots are registered below; Wave 5 images remain historical evidence.

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

## Confidence and history frame slots — Proposed, 4 Nov 2026

Added on `codex/figma-market-lab-slots`, based on `origin/main` at `31683f28`. The six existing populated brief-detail frames are extended in place in [the Market Lab Figma file](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=513-37050). Their frame IDs, original wording, saved-report/citation content, delivery summaries and prototype destinations are retained. The new sections and their copy are **Proposed**; the existing review bars remain visible. This entry does not change the recorded approval status of earlier work.

The section order is saved report → Confidence → Sources cited → History → Monthly briefs. Desktop remains 1440 wide with 1072-wide content cards; mobile remains 375 wide with 327-wide cards. The frames grow vertically. Empty/loading/error, Monthly briefs and Calibration frames are unchanged.

The field contract is [PR #701](https://github.com/Tervory-AI/tervory-tank/pull/701), branch `codex/market-lab-h7`, inspected at `1e6ef3af8334aef18ed1a7245ba1ac724a590ff5`: [CHANGES.md](https://github.com/Tervory-AI/tervory-tank/blob/1e6ef3af8334aef18ed1a7245ba1ac724a590ff5/tests/market_lab_h7/CHANGES.md), [brief detail assembly](https://github.com/Tervory-AI/tervory-tank/blob/1e6ef3af8334aef18ed1a7245ba1ac724a590ff5/agents/market_lab/core/brief_detail.py), and [Workspace types/formatters](https://github.com/Tervory-AI/tervory-tank/blob/1e6ef3af8334aef18ed1a7245ba1ac724a590ff5/workspace/app/market-lab/h7-model.ts). H7 exposes these structured fields but does not yet render the dedicated confidence/history sections. This design task adds the missing Figma slots only.

| Frame / status | Final size | Confidence slot | History slot | Screenshot |
| --- | --- | --- | --- | --- |
| [Report 1 · 1440 · Proposed](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-395) | 1440 × 2963 | [689:1597](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1597) | [689:1624](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1624) | [PNG](evidence/frame-slots/brief-detail-report-1-1440.png) |
| [Report 2 · 1440 · Proposed](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-601) | 1440 × 2127 | [689:1639](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1639) | [689:1658](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1658) | [PNG](evidence/frame-slots/brief-detail-report-2-1440.png) |
| [Report 3 · 1440 · Proposed](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-799) | 1440 × 2963 | [689:1666](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1666) | [689:1693](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1693) | [PNG](evidence/frame-slots/brief-detail-report-3-1440.png) |
| [Report 1 · 375 · Proposed](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-2140) | 375 × 3117 | [689:1708](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1708) | [689:1735](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1735) | [PNG](evidence/frame-slots/brief-detail-report-1-375.png) |
| [Report 2 · 375 · Proposed](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-2249) | 375 × 2241 | [689:1750](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1750) | [689:1769](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1769) | [PNG](evidence/frame-slots/brief-detail-report-2-375.png) |
| [Report 3 · 375 · Proposed](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=566-2350) | 375 × 3097 | [689:1777](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1777) | [689:1804](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1804) | [PNG](evidence/frame-slots/brief-detail-report-3-375.png) |

### Existing data bindings

| Slot | H7 field | Presentation / missing-data rule |
| --- | --- | --- |
| Signal heading / claim | `signals[]` index and `signals[].claim` | Repeat one card per returned signal; keep the corresponding claim. The index is presentation only. |
| Confidence | `signals[].confidence` | Use H7 `percent`: finite values in [0, 1] become one-decimal percentages. Null, unavailable or invalid values stay `—`; never substitute zero or a cohort average. |
| Warning pair / feed | `signals[].kind`, `signals[].feed` | Keep the original signal's pair/feed; missing values are `—`. Bracketed text in Figma marks field slots, not a live warning pair. |
| Frozen horizon | `signals[].horizon_seconds` | Use H7 `period` for a present horizon: whole days or seconds. A missing horizon stays `—`; do not infer it from the report date. |
| Prediction | `signals[].prediction_id` | Show the original reference when present; missing references are `—`. |
| Open stored source | `signals[].stored_href` | Link only to the verified returned stored-passage path. Every new Figma action is disabled with no destination because its source is a placeholder. Never derive a passage link from the public source URL. |
| Saved report | Report event in `history[]`, `happened_at` from `made_at` | The returned report event has no delivery channel/status. It must not imply a send. Preserve the event timestamp; the design reuses each existing illustrative report date. |
| Delivery event heading | `history[].channel`, `history[].status` | Repeat for **every** recorded event, including multiple events for one channel, in returned chronological order. Email and Webhook remain separate. Apply H7's delivery labels; retain other returned states such as `sending`. |
| Event date/time | `history[].happened_at` | Render the recorded timestamp with date, time and timezone so same-day transitions remain distinguishable. Missing time is `—`; no invented timestamp. |
| Event reason | `history[].reason` | Show the actual reason when present; omit the row when absent. Held/suppressed reasons must not become success messages. |
| No recorded delivery events. | No delivery entries in `history[]` | Preserve the saved-report event. Do not reconstruct earlier sends from current `deliveries[]` statuses. |

Report 1 shows one **illustrative** 75.0% / 30-day signal, using values already covered in H7 fixtures, plus unknown signals. Reports 2 and 3 show unknown confidence/horizon/reference values. Report 2 demonstrates a saved report with no recorded delivery events even though the original delivery summary has current states. Reports 1 and 3 show Email/Webhook event **placeholders**, not fabricated delivery receipts. The illustrative sample is not a claim that those values occurred together in a saved production report. All dates, claims, pairs and event details remain Figma-only.

### Style and editable assets

Existing Inter 20/28 semibold and 14/20 regular text, 16px spacing, white card surfaces, navy text, input-border strokes, 8px corners and 48px outline actions are reused. Surface/text/border/spacing/radius/stroke properties use the file's existing variables. No Code Connect files or matching subscribed-library Market Lab view were found, so the new cards use the existing frame styling and linked stored-source action.

- [Signal confidence component](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1585): text properties for signal, claim, metrics, pair/feed and prediction; 16 instances across the six frames.
- [Recorded history event component](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=689-1593): event/time/reason text properties and optional reason visibility; 14 instances across the six frames.

Both new local mains are on the same Proposed page to the right of existing frames. Existing shared mains are unchanged. New sections contain editable text and component instances. The only raster layers in the complete frames are the inherited logo assets.

### Copy inventory — Proposed

Every string below is Proposed for these sections, including reused product terms and illustrative data. Bracketed values are design-only field placeholders.

| Exact visible string | Status |
| --- | --- |
| Confidence | Proposed |
| Original signal confidence. Unknown values stay —. | Proposed |
| Signal 1 | Proposed |
| [Claim 1] | Proposed |
| Confidence: 75.0% · Frozen horizon: 30 days | Proposed |
| Warning pair / feed: [Warning pair] / [Feed] | Proposed |
| Prediction: [Saved prediction reference] | Proposed |
| Open stored source | Proposed |
| Signal 2 | Proposed |
| [Claim 2] | Proposed |
| Confidence: — · Frozen horizon: — | Proposed |
| Prediction: — | Proposed |
| Signal 3 | Proposed |
| [Claim 3] | Proposed |
| History | Proposed |
| Only recorded events are shown. Earlier sends are not reconstructed. | Proposed |
| Saved report | Proposed |
| Date: 1 Nov 2026 | Proposed |
| Email · [Recorded status] | Proposed |
| Date: [Recorded date and time] | Proposed |
| Reason: [Recorded reason, when present] | Proposed |
| Webhook · [Recorded status] | Proposed |
| Date: 1 Oct 2026 | Proposed |
| No recorded delivery events. | Proposed |
| Date: 1 Sep 2026 | Proposed |

### Verification and evidence

All six final full-frame PNGs were visually checked after correcting the persisted positions of existing citations and the back action. The final views have no overlapping body rows or overflowing new content. Inter is asserted on every text layer. All original nodes and text were retained, and the 18 existing brief-detail navigation destinations match the Wave 5 prototype register. The sidebar height extends with the desktop content; inherited shared-menu geometry is otherwise unchanged.

Evidence: [construction and retained-content checks](evidence/frame-slots/build.json), [layout correction](evidence/frame-slots/layout-fix.json), [persisted final read-back](evidence/frame-slots/final-readback.json), and [PNG dimensions, SHA-256 and local checks](evidence/frame-slots/verification.json). The [construction script](authoring/frame-slots.js) and [layout-persistence correction](authoring/frame-slots-layout-fix.js) record the two authoring steps; the final read-back and screenshots are authoritative.

Checks cover six expected 1440/375 frames; 12 section slots; 30 new card instances; all original text and frame IDs; native editable layers; existing navigation destinations; PNG dimensions/hashes; JSON validity; JavaScript syntax; Markdown evidence links; and `git diff --check`. No application tests or deployment were needed: changed repository files are confined to `docs/figma/market-lab/`. Implementation and approval of the Proposed additions remain subsequent work.
