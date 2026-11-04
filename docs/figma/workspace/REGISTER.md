# Workspace design register

**Status: Approved 3 Nov 2026, 17:40 PT** (Claude, under the founder's 3 Nov 13:28 delegation to approve the basics): the 16 Results and Task board frames and their wording, at this commit. Feedback and Paid steps settings are not drawn yet and are not approved.

Branch: `codex/figma-workspace`, created from `origin/main` at `8857cd3e`. File: [Workspace proposals](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3092).

Scope: C4 results; C3 task board; C6 result feedback; founder paid-step settings. Completed: Results and Task board, each with desktop 1440×900 and mobile 375×900 default, empty, loading and error views. Feedback and Paid steps settings have not been created. Long content scrolls vertically; screenshots show the initial viewport.

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

All frames remain Proposed. Prototype fixtures are review data. Founder-only settings need existing server-side founder authorization when implemented. Ask/Auto is a new founder-requested design proposal; it does not override today’s automatic runtime ladder. Each paid step returned by each task ladder gets its own control; the illustrated categories are not an asserted live provider inventory.

## Incomplete work — Figma access limit

Figma rejected the first Feedback creation call: “You’ve reached the Figma MCP tool call limit for your Full seat on the Professional plan.” No Feedback or Paid steps settings frames, IDs or screenshots were created. All 16 registered screen frames belong to Results and Task board only.

Pending before this task is complete:

- Create C6 Feedback desktop/mobile and empty/loading/error states; preserve the originating result’s identity and download URL. Add optional-note entry and a submission acknowledgement.
- Create founder-only Paid steps settings with Ask/Auto on every configured paid ladder step, a global pause/resume state, and desktop/mobile empty/loading/error views. The three authoring-script categories are Proposed examples, not a verified paid-step inventory.
- Connect Workspace tabs, result Open / Add a note, feedback selection, task Open and the mobile header to the shared drawer. The present visible controls are design proposals; only Download, loading-delay and Try again actions are authored. No selected feedback, persistence, filter behaviour or drawer navigation is claimed.
- Inspect the remaining screenshots and verify all intended interactions after the allowance is restored. Save screenshots and IDs for every new frame, and push each completed screen group.

[Authoring script](authoring/build-screen.js) preserves construction helpers, component IDs are in the [session ledger](evidence/session-ledger.json). Invoke with explicit `SCREEN` and `GROUP` constants only after checking existing frame names to prevent duplicates. Remaining proposed calls: `SCREEN='Feedback', GROUP=2`; `SCREEN='Paid steps', GROUP=3`. These scripts have not been executed or visually validated for the remaining screens. Before using them, replace the single Base feedback example with per-result context and implement the pending interactions above.

Per-screen pushes: Results `f1e463c2`; Task board `0458cc63`. These commits contain Proposed design evidence only. The task remains incomplete due to the reported Figma limit.
