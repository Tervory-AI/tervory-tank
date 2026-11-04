# Workspace design register

**Status: Proposed — no frame or new wording in this register is approved.**

Branch: `codex/figma-workspace`, created from `origin/main` at `8857cd3e`. File: [Workspace proposals](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3092).

Scope: C4 results; C3 task board; C6 result feedback; founder paid-step settings. Every screen has desktop 1440×900 and mobile 375×900 default, empty, loading and error views. Long content scrolls vertically; screenshots show the initial viewport.

## Rules and reuse

White CRM menu and surfaces, light canvas, navy primary actions, Inter throughout new instances, 8px corners, 8/16/24 spacing. Existing shared menu, mobile bar, CRM fields and action instances are preserved. No existing master or screen is edited. Proposed composite components reuse these instances and the existing colour/spacing/radius variables. Input border #848da3 has 3.32:1 contrast on white.

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

## Wording inventory

Every visible string is listed below. **Proposed** is the conservative approval status even for reused product words; provenance above distinguishes reuse. Each screen carries a visible Proposed label. Data examples are also Proposed. This prevents any new string from being mistaken for approved wording.

| Wording | Status |
|---|---|
| Account settings | Proposed |
| Add a note | Proposed |
| All files | Proposed |
| All products | Proposed |
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
| Feedback | Proposed |
| Google posts | Proposed |
| Google reviews | Proposed |
| Inbox | Proposed |
| Invoices | Proposed |
| Leads | Proposed |
| Lease review | Proposed |
| Loading… | Proposed |
| Market Lab · Document | Proposed |
| Market research | Proposed |
| Marketing | Proposed |
| No work yet | Proposed |
| Not useful | Proposed |
| Open | Proposed |
| Opportunities | Proposed |
| Proposed | Proposed |
| Quote draft | Proposed |
| Quotes | Proposed |
| Radix · Document | Proposed |
| Receipts | Proposed |
| Report | Proposed |
| Results | Proposed |
| Rig · File | Proposed |
| Sales | Proposed |
| Settings | Proposed |
| Something went wrong | Proposed |
| Tasks | Proposed |
| Tiger · Alert | Proposed |
| Tisan · File | Proposed |
| Trigger · Table | Proposed |
| Try again | Proposed |
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

## Review limitations

All frames remain Proposed. Prototype fixtures are review data. Founder-only settings need existing server-side founder authorization when implemented. Ask/Auto is a new founder-requested design proposal; it does not override today’s automatic runtime ladder. Each paid step returned by each task ladder gets its own control; the illustrated categories are not an asserted live provider inventory.
