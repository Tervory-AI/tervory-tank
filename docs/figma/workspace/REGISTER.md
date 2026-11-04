# Workspace design register

**Status: Approved 3 Nov 2026, 17:40 PT** (Claude, under the founder's 3 Nov 13:28 delegation to approve the basics): the 16 Results and Task board frames and their wording, at this commit. Feedback and Paid steps settings were drawn in `bd800c2d`; they remain Proposed, not approved. See the Wave 5 frame table below.

Branch: `codex/figma-workspace`, created from `origin/main` at `8857cd3e`. File: [Workspace proposals](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3092).

Scope: C4 results; C3 task board; C6 result feedback; founder paid-step settings. Completed: Results and Task board, each with desktop 1440×900 and mobile 375×900 default, empty, loading and error views. Feedback and Paid steps settings are drawn with the states and evidence listed in the Wave 5 continuation below. Long content scrolls vertically; screenshots show the initial viewport.

## Rules and reuse

White CRM menu and surfaces, light canvas, navy primary actions, Inter throughout new instances, 8px corners, 8/16/24 spacing. Existing shared menu, mobile bar, CRM fields and action instances are preserved. No pre-existing master or screen is edited; overrides affect new menu instances only. Proposed composite components reuse these instances and the existing colour/spacing/radius variables. Input border #848da3 has 3.32:1 contrast on white.

Sources: `workspace/app/control/view.tsx` (seven Squad products), `workspace/app/market-lab/warnings.tsx` (Useful / Not useful), `workspace/app/skala/gold/view.tsx` (Wrong), `workspace/app/control/widgets.tsx` (Pause all paid work / Resume paid work), `workspace/lib/admin.ts` (dynamic ladder steps), existing Figma CRM/Marketing components and client dashboard. User-requested labels remain Proposed until founder review.

## Download data and behaviour

All result data are Proposed design fixtures, not live client results. Each Download action opens its matching fixture under `fixtures/` on this branch. GitHub access may be required. Production must bind each result to its authorized artifact download URL. Eight sample products: Base, Tiger, Market Lab, Rig, Tisan, Radix, Zenas and Trigger. The list is data-driven, not a limit on future products. Empty and loading views never present fabricated downloadable results.

The register records authored prototype actions; it does not claim browser gesture or backend tests. No runtime code, paid provider, credential, ladder routing or access-control policy is changed.

## Frames and screenshots

| Screen / device / state | Status | Node ID | Screenshot |
|---|---|---|---|
| Results / Desktop / Default · Proposed | Proposed | [514:3163](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3163) | [results-desktop-default.png](evidence/results-desktop-default.png) |
| Results / Desktop / Empty · Proposed | Proposed | [514:3441](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3441) | [results-desktop-empty.png](evidence/results-desktop-empty.png) |
| Results / Desktop / Loading · Proposed | Proposed | [514:3560](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3560) | [results-desktop-loading.png](evidence/results-desktop-loading.png) |
| Results / Desktop / Error · Proposed | Proposed | [514:3681](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3681) | [results-desktop-error.png](evidence/results-desktop-error.png) |
| Results / Mobile / Default · Proposed | Proposed | [514:3802](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3802) | [results-mobile-default.png](evidence/results-mobile-default.png) |
| Results / Mobile / Empty · Proposed | Proposed | [514:3983](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3983) | [results-mobile-empty.png](evidence/results-mobile-empty.png) |
| Results / Mobile / Loading · Proposed | Proposed | [514:4001](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4001) | [results-mobile-loading.png](evidence/results-mobile-loading.png) |
| Results / Mobile / Error · Proposed | Proposed | [514:4021](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4021) | [results-mobile-error.png](evidence/results-mobile-error.png) |
| Tasks / Desktop / Default · Proposed | Proposed | [514:17565](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-17565) | [tasks-desktop-default.png](evidence/tasks-desktop-default.png) |
| Tasks / Desktop / Empty · Proposed | Proposed | [514:17723](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-17723) | [tasks-desktop-empty.png](evidence/tasks-desktop-empty.png) |
| Tasks / Desktop / Loading · Proposed | Proposed | [514:17842](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-17842) | [tasks-desktop-loading.png](evidence/tasks-desktop-loading.png) |
| Tasks / Desktop / Error · Proposed | Proposed | [514:17963](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-17963) | [tasks-desktop-error.png](evidence/tasks-desktop-error.png) |
| Tasks / Mobile / Default · Proposed | Proposed | [514:18084](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-18084) | [tasks-mobile-default.png](evidence/tasks-mobile-default.png) |
| Tasks / Mobile / Empty · Proposed | Proposed | [514:18141](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-18141) | [tasks-mobile-empty.png](evidence/tasks-mobile-empty.png) |
| Tasks / Mobile / Loading · Proposed | Proposed | [514:18159](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-18159) | [tasks-mobile-loading.png](evidence/tasks-mobile-loading.png) |
| Tasks / Mobile / Error · Proposed | Proposed | [514:18179](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-18179) | [tasks-mobile-error.png](evidence/tasks-mobile-error.png) |

## Wording inventory

Every visible string is listed below. **Proposed** is the conservative approval status even for reused product words; provenance above distinguishes reuse. Each screen carries a visible Proposed label. Data examples are also Proposed. This prevents any new string from being mistaken for approved wording.

| Wording | Status |
|---|---|
| Account settings | Proposed |
| Add a note | Proposed |
| All files | Proposed |
| All products | Proposed |
| Base | Proposed |
| Base · Table | Proposed |
| Billing | Proposed |
| Business | Proposed |
| CRM | Proposed |
| Calendar | Proposed |
| Cases | Proposed |
| Channels | Proposed |
| Chat bot | Proposed |
| Clients | Proposed |
| Competitor prices | Proposed |
| Composer | Proposed |
| Contacts | Proposed |
| Delaware dealer list | Proposed |
| Delivered | Proposed |
| Documents, tables, alerts and files | Proposed |
| Download | Proposed |
| Failed | Proposed |
| Feedback | Proposed |
| Google posts | Proposed |
| Google reviews | Proposed |
| Inbox | Proposed |
| Invoices | Proposed |
| Leads | Proposed |
| Lease review | Proposed |
| Loading… | Proposed |
| Market Lab | Proposed |
| Market Lab · Document | Proposed |
| Market research | Proposed |
| Marketing | Proposed |
| No work yet | Proposed |
| Not useful | Proposed |
| Open | Proposed |
| Opportunities | Proposed |
| Proposed | Proposed |
| Queued | Proposed |
| Queued · Running · Delivered · Unverified · Failed | Proposed |
| Quote draft | Proposed |
| Quotes | Proposed |
| Radix · Document | Proposed |
| Receipts | Proposed |
| Report | Proposed |
| Results | Proposed |
| Rig | Proposed |
| Rig · File | Proposed |
| Running | Proposed |
| Sales | Proposed |
| Settings | Proposed |
| Something went wrong | Proposed |
| Task board | Proposed |
| Tasks | Proposed |
| Tiger | Proposed |
| Tiger · Alert | Proposed |
| Tisan | Proposed |
| Tisan · File | Proposed |
| Trigger · Table | Proposed |
| Try again | Proposed |
| Unverified | Proposed |
| Useful | Proposed |
| Voice | Proposed |
| Workspace | Proposed |
| Write | Proposed |
| Writing | Proposed |
| Wrong | Proposed |
| Zenas · Document | Proposed |
| ⌄ | Proposed |
| ☰ | Proposed |

## Node ledger

All created nodes, instance descendants and subsequently changed IDs are listed in the JSON evidence. Reused source masters are references, not changed IDs. Failed rolled-back writes are excluded.

| Screen | Full node and prototype-action ledger |
|---|---|
| Results | [IDs and actions](evidence/results.json) (761 IDs) |
| Tasks | [IDs and actions](evidence/tasks.json) (533 IDs) |

## Review limitations

Results and Task board retain their recorded approval. Feedback and Paid steps remain Proposed. Prototype fixtures are review data. Founder-only settings need existing server-side founder authorization when implemented. Ask/Auto is a new founder-requested design proposal; it does not override today’s automatic runtime ladder. Each paid step returned by each task ladder gets its own control; the illustrated categories are not an asserted live provider inventory.

## Quota stop resolved

The earlier quota stop is superseded by `bd800c2d`, which created the Feedback and Paid steps frames and their desktop/mobile state evidence listed below. Results `f1e463c2` and Task board `0458cc63` retain their approval above; Feedback and Paid steps remain Proposed.

## Wave 5 continuation — Proposed, 4 Nov 2026

C6 feedback with an optional note and founder paid-step settings are now drawn. These additions remain Proposed; the existing Results/Tasks approval above does not approve them. [Figma page](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3092).

Feedback preserves the product, result title and matching fixture download in every context. Results Open/Add a note enters the matching product and width. Save feedback opens its matching acknowledgement; this is a prototype, not persisted feedback. None/Useful/Not useful/Wrong use the existing component variants. Notes are optional. All eight products have Note and Saved views at both widths, plus shared empty/loading/error states.

Paid settings show one independent Ask/Auto pair per paid step, grouped by task, and a separate global pause/resume. Free steps stay automatic. Paused styling keeps each stored mode; illustrative Task A/B and paid-step/route placeholders do not claim a live provider inventory. Production implementation must bind stable task/step identities and policy state; current admin step records and global pause alone do not provide that contract. No runtime policy changes are made.

All new wording/data, including optional-note example, acknowledgements, pause explanations and bracketed settings placeholders, are **Proposed**. The exhaustive [copy inventory](evidence/w5/copy-proposed.json) marks every visible string conservatively Proposed for these new screens. [Frame IDs, dimensions and SHA-256 hashes](evidence/w5/frames.json); creation receipts include every surviving created descendant ID; [existing prototype nodes changed](evidence/w5/prototype-links.json) and [component choice nodes changed](evidence/w5/component-links.json). No existing frame IDs were replaced.

Light surfaces, Inter and navy primary controls are reused from the existing CRM components. Every creation receipt records font/bounds checks; no text overflow or non-Inter text was found. Desktop/mobile feedback and paid default screenshots were visually inspected. The settings examples contain five pairs across two tasks at each width, rather than one pair per model/provider.

| Screen / context / state | Width | Frame ID | Screenshot |
| --- | --- | --- | --- |
| Feedback · Base · Note · Proposed | 1440 | [556:3054](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=556-3054) | [PNG](evidence/w5/feedback-base-note-1440.png) |
| Feedback · Base · Saved · Proposed | 1440 | [556:3190](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=556-3190) | [PNG](evidence/w5/feedback-base-saved-1440.png) |
| Feedback · Tiger · Note · Proposed | 1440 | [556:3319](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=556-3319) | [PNG](evidence/w5/feedback-tiger-note-1440.png) |
| Feedback · Tiger · Saved · Proposed | 1440 | [556:3455](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=556-3455) | [PNG](evidence/w5/feedback-tiger-saved-1440.png) |
| Feedback · Market Lab · Note · Proposed | 1440 | [557:5147](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-5147) | [PNG](evidence/w5/feedback-market-lab-note-1440.png) |
| Feedback · Market Lab · Saved · Proposed | 1440 | [557:5283](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-5283) | [PNG](evidence/w5/feedback-market-lab-saved-1440.png) |
| Feedback · Rig · Note · Proposed | 1440 | [557:5412](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-5412) | [PNG](evidence/w5/feedback-rig-note-1440.png) |
| Feedback · Rig · Saved · Proposed | 1440 | [557:5548](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-5548) | [PNG](evidence/w5/feedback-rig-saved-1440.png) |
| Feedback · Tisan · Note · Proposed | 1440 | [557:5679](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-5679) | [PNG](evidence/w5/feedback-tisan-note-1440.png) |
| Feedback · Tisan · Saved · Proposed | 1440 | [557:5815](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-5815) | [PNG](evidence/w5/feedback-tisan-saved-1440.png) |
| Feedback · Radix · Note · Proposed | 1440 | [557:5944](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-5944) | [PNG](evidence/w5/feedback-radix-note-1440.png) |
| Feedback · Radix · Saved · Proposed | 1440 | [557:6080](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-6080) | [PNG](evidence/w5/feedback-radix-saved-1440.png) |
| Feedback · Zenas · Note · Proposed | 1440 | [557:6417](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-6417) | [PNG](evidence/w5/feedback-zenas-note-1440.png) |
| Feedback · Zenas · Saved · Proposed | 1440 | [557:6553](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-6553) | [PNG](evidence/w5/feedback-zenas-saved-1440.png) |
| Feedback · Trigger · Note · Proposed | 1440 | [557:6682](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-6682) | [PNG](evidence/w5/feedback-trigger-note-1440.png) |
| Feedback · Trigger · Saved · Proposed | 1440 | [557:6818](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-6818) | [PNG](evidence/w5/feedback-trigger-saved-1440.png) |
| Feedback · Result · Empty · Proposed | 1440 | [557:7633](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7633) | [PNG](evidence/w5/feedback-result-empty-1440.png) |
| Feedback · Result · Loading · Proposed | 1440 | [557:7753](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7753) | [PNG](evidence/w5/feedback-result-loading-1440.png) |
| Feedback · Result · Error · Proposed | 1440 | [557:7875](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7875) | [PNG](evidence/w5/feedback-result-error-1440.png) |
| Feedback · Base · Note · Proposed | 375 | [557:4919](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-4919) | [PNG](evidence/w5/feedback-base-note-375.png) |
| Feedback · Base · Saved · Proposed | 375 | [557:4979](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-4979) | [PNG](evidence/w5/feedback-base-saved-375.png) |
| Feedback · Tiger · Note · Proposed | 375 | [557:5032](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-5032) | [PNG](evidence/w5/feedback-tiger-note-375.png) |
| Feedback · Tiger · Saved · Proposed | 375 | [557:5092](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-5092) | [PNG](evidence/w5/feedback-tiger-saved-375.png) |
| Feedback · Market Lab · Note · Proposed | 375 | [557:6949](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-6949) | [PNG](evidence/w5/feedback-market-lab-note-375.png) |
| Feedback · Market Lab · Saved · Proposed | 375 | [557:7009](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7009) | [PNG](evidence/w5/feedback-market-lab-saved-375.png) |
| Feedback · Rig · Note · Proposed | 375 | [557:7062](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7062) | [PNG](evidence/w5/feedback-rig-note-375.png) |
| Feedback · Rig · Saved · Proposed | 375 | [557:7122](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7122) | [PNG](evidence/w5/feedback-rig-saved-375.png) |
| Feedback · Tisan · Note · Proposed | 375 | [557:7177](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7177) | [PNG](evidence/w5/feedback-tisan-note-375.png) |
| Feedback · Tisan · Saved · Proposed | 375 | [557:7237](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7237) | [PNG](evidence/w5/feedback-tisan-saved-375.png) |
| Feedback · Radix · Note · Proposed | 375 | [557:7290](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7290) | [PNG](evidence/w5/feedback-radix-note-375.png) |
| Feedback · Radix · Saved · Proposed | 375 | [557:7350](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7350) | [PNG](evidence/w5/feedback-radix-saved-375.png) |
| Feedback · Zenas · Note · Proposed | 375 | [557:7405](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7405) | [PNG](evidence/w5/feedback-zenas-note-375.png) |
| Feedback · Zenas · Saved · Proposed | 375 | [557:7465](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7465) | [PNG](evidence/w5/feedback-zenas-saved-375.png) |
| Feedback · Trigger · Note · Proposed | 375 | [557:7518](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7518) | [PNG](evidence/w5/feedback-trigger-note-375.png) |
| Feedback · Trigger · Saved · Proposed | 375 | [557:7578](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7578) | [PNG](evidence/w5/feedback-trigger-saved-375.png) |
| Feedback · Result · Empty · Proposed | 375 | [557:7996](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-7996) | [PNG](evidence/w5/feedback-result-empty-375.png) |
| Feedback · Result · Loading · Proposed | 375 | [557:8040](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-8040) | [PNG](evidence/w5/feedback-result-loading-375.png) |
| Feedback · Result · Error · Proposed | 375 | [557:8086](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=557-8086) | [PNG](evidence/w5/feedback-result-error-375.png) |
| Paid steps · Default · Proposed | 1440 | [559:3085](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=559-3085) | [PNG](evidence/w5/paid-steps-default-1440.png) |
| Paid steps · Paused · Proposed | 1440 | [559:3249](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=559-3249) | [PNG](evidence/w5/paid-steps-paused-1440.png) |
| Paid steps · Saved · Proposed | 1440 | [559:3414](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=559-3414) | [PNG](evidence/w5/paid-steps-saved-1440.png) |
| Paid steps · Empty · Proposed | 1440 | [562:3565](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=562-3565) | [PNG](evidence/w5/paid-steps-empty-1440.png) |
| Paid steps · Loading · Proposed | 1440 | [562:3679](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=562-3679) | [PNG](evidence/w5/paid-steps-loading-1440.png) |
| Paid steps · Error · Proposed | 1440 | [562:3795](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=562-3795) | [PNG](evidence/w5/paid-steps-error-1440.png) |
| Paid steps · Default · Proposed | 375 | [561:3445](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=561-3445) | [PNG](evidence/w5/paid-steps-default-375.png) |
| Paid steps · Paused · Proposed | 375 | [561:3533](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=561-3533) | [PNG](evidence/w5/paid-steps-paused-375.png) |
| Paid steps · Saved · Proposed | 375 | [561:3622](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=561-3622) | [PNG](evidence/w5/paid-steps-saved-375.png) |
| Paid steps · Empty · Proposed | 375 | [562:3910](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=562-3910) | [PNG](evidence/w5/paid-steps-empty-375.png) |
| Paid steps · Loading · Proposed | 375 | [562:3948](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=562-3948) | [PNG](evidence/w5/paid-steps-loading-375.png) |
| Paid steps · Error · Proposed | 375 | [562:3988](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=562-3988) | [PNG](evidence/w5/paid-steps-error-375.png) |

### Wave 5 validation and publishing

Continued on `codex/figma-w5`, PR #685, under the founder’s 4 Nov 06:47 instruction. The preceding quota-stop section is historical. C6 and paid-step additions now comprise 50 Proposed frames: 38 per-result feedback/note/acknowledgement/state views and 12 paid-settings views. Existing Results/Tasks approvals are preserved; no new approval is inferred. [Final canvas read-back](evidence/w5/final-readback.json) confirms exact dimensions, Inter throughout, note/save controls and exactly one Ask/Auto pair for each of five example paid steps in each populated settings frame. All 50 PNG dimensions and SHA-256 values match frames.json. Examples use task/step placeholders rather than inventing configured providers. No runtime ladder, paid routing, persistence or founder authorization changed.
