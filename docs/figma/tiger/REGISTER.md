# Tiger frames — 4 Nov 2026

Every new frame, presentation label and data example is **Proposed — not approved**. Figma file: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS. Branch: `codex/figma-tiger`, own checkout `/workspace/codex-figma-tiger`, based on current main `15432cb522a7922359ad9174aed3784480b34b50`. No approved frame or shared main is edited.

## Style and reuse

Reference: [approved Tiger register](../TIGER-POSITION-FRAMES.md), approved 3 Nov 15:20 PT. Existing 1440/375 Tiger shells and responsive menu/logo/search/segments are cloned into a separate Proposed page. Light surfaces, navy text/outline actions (48px), selected tint #e9edf6, 8px corners, spacing 0/8/16/24 and larger padding on multiples of 8. Jost Light headings and Inter body/control text match the approved Tiger frames. Search remains a single line at 375 with the approved contrast edge. Original logo images are the only raster assets; composed UI is editable text, frames and component instances.

No Code Connect files were found. Local source instances and variables take precedence over unrelated subscribed community results: source frames `256:10/170`, `256:283/406`, `256:471/609`; approved note-card source `256:167`; CRM action main `93:4`; CRM field main `93:6`. Discovery and authoring are saved under `authoring/`; per-item construction and read-back ledgers enumerate node IDs.

## Source and behavior contracts

- `workspace/app/tiger/load.ts`, `model.ts`, `actions.ts`: unavailable read history stays unknown; a failed decision is shown pending, with no false success or Rejected state. Source reuse includes "Tiger is not reachable right now. No products are shown.", "the latest check couldn't be loaded", "That could not be saved. Try again.". New explanatory wording remains Proposed.
- `docs/cursor/TG2-tiger-watchlist-page.md`, `agents/tiger/app.py`, `watch.py`, `change_alert.py`: interval, enabled, threshold and five independent alert booleans. Threshold is a fraction internally: the Proposed 5% field maps to 0.05, and changes must be strictly greater than it. No runtime policy or watch is changed.
- `tank/tiger_alerts.py` and `agents/tiger/alert_email.py`: five kinds are `price`, `stock`, `new_product`, `below_cost`, `market_gap`. Display labels Price / Stock / New product / Below cost / Market gap are conservatively Proposed. Current Workspace model filters the last three and only renders Price/Stock; implementation must bind all five instead of pretending they already ship.
- GTIN and catalogue/match UI have no current approved implementation contract in this main snapshot. Identifier slots and review copy are Proposed; no barcode is fabricated or declared validated. Reserved `.example` product links and Fieldlight fixtures are copied from the approved register, never live client evidence.

## Frames and screenshots

| Item / state | Size | Frame | Status | Screenshot |
| --- | --- | --- | --- | --- |
| T01-1440 · Loading | 1440×1189 | [622:10](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=622-10) | Proposed | [PNG](evidence/T01-1440.png) |
| T01-375 · Loading | 375×1151 | [622:216](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=622-216) | Proposed | [PNG](evidence/T01-375.png) |
| T02-1440 · Read failure | 1440×1189 | [622:309](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=622-309) | Proposed | [PNG](evidence/T02-1440.png) |
| T02-375 · Read failure | 375×935 | [622:499](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=622-499) | Proposed | [PNG](evidence/T02-375.png) |
| T03-1440 · Decision failure | 1440×1189 | [622:594](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=622-594) | Proposed | [PNG](evidence/T03-1440.png) |
| T03-375 · Decision failure | 375×1251 | [622:764](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=622-764) | Proposed | [PNG](evidence/T03-375.png) |
| T04-1440 · Unavailable site-check details | 1440×1189 | [627:158](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=627-158) | Proposed | [PNG](evidence/T04-1440.png) |
| T04-375 · Unavailable site-check details | 375×1195 | [627:317](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=627-317) | Proposed | [PNG](evidence/T04-375.png) |
| T05-1440 · Empty catalogue | 1440×1189 | [628:205](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=628-205) | Proposed | [PNG](evidence/T05-1440.png) |
| T05-375 · Empty catalogue | 375×900 | [628:376](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=628-376) | Proposed | [PNG](evidence/T05-375.png) |
| T06-1440 · GTIN review | 1440×1189 | [628:470](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=628-470) | Proposed | [PNG](evidence/T06-1440.png) |
| T06-375 · GTIN review | 375×1277 | [628:623](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=628-623) | Proposed | [PNG](evidence/T06-375.png) |
| T07-1440 · Watch card controls · On | 1440×1577 | [629:293](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=629-293) | Proposed | [PNG](evidence/T07-1440.png) |
| T07-375 · Watch card controls · On | 375×1678 | [629:510](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=629-510) | Proposed | [PNG](evidence/T07-375.png) |
| T08-1440 · Watch card controls · Off | 1440×1610 | [629:650](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=629-650) | Proposed | [PNG](evidence/T08-1440.png) |
| T08-375 · Watch card controls · Off | 375×1728 | [629:868](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=629-868) | Proposed | [PNG](evidence/T08-375.png) |
| T09-1440 · Alerts · All five kinds | 1440×1700 | [642:443](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=642-443) | Proposed | [PNG](evidence/T09-1440.png) |
| T09-375 · Alerts · All five kinds | 375×1936 | [642:662](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=642-662) | Proposed | [PNG](evidence/T09-375.png) |
| T10-1440 · Alerts · Empty | 1440×1189 | [645:496](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=645-496) | Proposed | [PNG](evidence/T10-1440.png) |
| T10-375 · Alerts · Empty | 375×900 | [645:676](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=645-676) | Proposed | [PNG](evidence/T10-375.png) |
| T11-1440 · Alerts · Loading | 1440×1189 | [645:782](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=645-782) | Proposed | [PNG](evidence/T11-1440.png) |
| T11-375 · Alerts · Loading | 375×900 | [645:962](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=645-962) | Proposed | [PNG](evidence/T11-375.png) |
| T12-1440 · Alerts · Error | 1440×1189 | [645:1068](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=645-1068) | Proposed | [PNG](evidence/T12-1440.png) |
| T12-375 · Alerts · Error | 375×900 | [645:1250](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=645-1250) | Proposed | [PNG](evidence/T12-375.png) |

## Validation and copy

[wording.json](evidence/wording.json) lists every visible string with explicit Proposed status and its frame IDs. Existing product labels and source wording are reused without claiming a new approval. Each frame carries a visible Proposed review bar.

[validation.json](evidence/validation.json) records exact native PNG dimensions and SHA-256. Per-item `*-audit.json` records editable node-type counts, all surviving IDs, actual fonts, logo image slots, text bounds and minimum control checks. Construction ledgers additionally identify removed temporary clone nodes. No source main/component was changed.

Screenshots are review evidence, not proof of backend behavior. No model call, scheduled read, match decision, catalogue mutation, GTIN validation or alert delivery is executed by this design task. Full application tests do not apply to documentation/Figma-only changes.

## Completion — 4 Nov 2026

All six requested items are delivered: 24 Proposed frames with native-width PNGs. Card controls have On and Off views; five independent alert choices keep their values when the watch is Off. Alerts includes all five labels plus empty/loading/error at both widths. Input outlines reuse the existing accessible input-border token; [paint fallback correction](evidence/color-fallback-fix.json) records exact numeric fallback/binding synchronization without geometry or wording changes. The new desktop clones use their linked Tiger navigation alone, hiding inherited duplicate legacy siblings; approved source frames remain unchanged.

Per-item pushes: loading/read/decision `97b75ee2`; site details `ca54e129`; empty catalogue `2f83679e`; GTIN `35d15ea0`; controls `10d2757e`; bound-colour correction `591dc9d9`; Alerts `ad5b34cb`. Final evidence checks: 24 unique frame IDs, exact widths and native PNG dimensions/hashes, Jost/Inter only, no recorded text overflow or control below 44px, all five kind labels in both filled Alerts frames, and 27 valid relative register references before this completion appendix. These are drawing/evidence checks, not runtime acceptance or founder approval.
