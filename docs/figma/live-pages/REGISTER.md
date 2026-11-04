# Live pages — Proposed as-built frames

Founder brief, 4 Nov 08:30 PT. **Every frame is Proposed, not approved.** [Figma file and page](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=610-675). Branch `codex/figma-w5`, PR #685.

These copy the built pages, not a redesign. Existing wording, fonts, colours, dark navigation and browser-native controls are retained under this brief. Proposed appears in frame names and this register, not as extra text inside the copied page. Billing and the listed founder tools are outside scope; a Billing link remains wherever it already exists in the shared navigation.

Source baseline: `origin/main` `c94610bd0f9f35443f9d58deb45ec44b60ecb33d`. The requested route source matches this branch. Public Autumbra and Moot returned HTTP 200 on 4 Nov. Protected pages are rendered from unchanged production components with offline identity/data boundaries, without credentials, founder sessions or production reads. They are source-faithful fixture states, not signed-in live captures or claims about live client values. Provider-hosted widgets that cannot be reproduced without an account must be listed as gaps rather than invented.

## Frames

| Page / built state | Address | Width | Frame ID | Status | Figma screenshot | Browser reference |
| --- | --- | --- | --- | --- | --- | --- |
| Data · empty batch | https://app.tervory.com/data | 1440 | [604:9](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=604-9) | Proposed | [PNG](evidence/data-figma-1440.png) | [PNG](evidence/data-browser-1440.png) |
| Data · empty batch | https://app.tervory.com/data | 375 | [606:9](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=606-9) | Proposed | [PNG](evidence/data-figma-375.png) | [PNG](evidence/data-browser-375.png) |

## Data

Unchanged `workspace/app/data/page.tsx`, `data.css`, actual `Shell`, global CSS, local fonts and original brand images. Existing default sample CSV and the built empty-batch message are retained. No batch, upload, enrichment or export is run. Client role excludes founder tools. The account-provider widget is unavailable offline; no company/avatar UI is invented.

[Source hashes](evidence/data-source.json); [source/browser metadata](evidence/data-1440.json) and [phone metadata](evidence/data-375.json); [final IDs and exact wording](evidence/data-final.json); [native conversion repairs](evidence/data-corrections.json); [PNG hashes, dimensions and copy checks](evidence/data-checks.json). Every copied product text is checked against the rendered production HTML. The browser's existing “Choose File” / “No file chosen” words are reproduced as editable text; Arimo is the metrics-compatible Figma substitute for the browser's Arial file-button font. Checkbox and input clipping retain the native control geometry. Main components are unchanged.

Both native Figma PNGs have the same dimensions as their browser references: 1440×951 and 375×1397. The table and file input retain the built horizontal clipping at phone width. No new product wording is introduced, and no site/application code is changed.

## Remaining requested pages

| Page | Route | Progress |
| --- | --- | --- |
| Ledger | `/ledger` | Pending |
| Matters | `/matters` | Pending |
| Chat cost details | `/chats/evidence/[thread]` and `/chats/evidence/[thread]/[row]` | Pending |
| Onboarding | `/onboarding` | Pending; account-provider widget requires separate evidence |
| Stored Market Lab sources | `/market-lab/sources/[id]` | Pending |
| Moot public watch | `/moot` and `/moot/[match]` on zenas.tervory.com | Pending |
| Autumbra public | `/autumbra` | Pending |
| Autumbra undo | `/autumbra/undo/[id]` | Pending; never use a real credential-bearing link |
| Autumbra weekly receipts | `/autumbra/receipts/weekly/[tenant]` | Pending; never use a real credential-bearing link |

Skipped: Billing; Access, Admin, Review, Rig 3D admin, Tank, Skala and Gold. No frames for those pages are created.
