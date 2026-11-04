# Tervory window panel — Proposed

Figma file: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS

Branch: `codex/figma-w5`. Every frame and all new panel wording are **Proposed**, not approved. New designs only; existing approved frames are unchanged.

## Reference and implementation contract

Founder clarification, 4 Nov 2026: no Tervory desktop shell exists yet. The `window/` build on `codex/window` will follow these frames. These are design proposals, not screenshots of a shipped build.

Code-OSS baseline: **1.145.0**, the current stable release checked 4 Nov 2026 ([release](https://github.com/microsoft/vscode/releases/tag/1.145.0), release commit `a717861`). Layout/title-bar references are pinned to that tag: [layout.ts](https://github.com/microsoft/vscode/blob/1.145.0/src/vs/workbench/browser/layout.ts), [titlebarPart.ts](https://github.com/microsoft/vscode/blob/1.145.0/src/vs/workbench/browser/parts/titlebar/titlebarPart.ts). Light custom-title-bar desktop workbench: title/menu, activity bar, Explorer, tabs, breadcrumbs, editor and bottom status bar; Tervory docks on the right at 448px. Proposed geometry uses a 40px title bar and 24px status bar (an intentional Tervory adaptation of upstream, whose command-center title bar defaults to 35px); it does not claim pixel parity with an existing desktop build. Inter throughout.

Exact logo asset: `workspace/public/brand/tervory-logo-on-white.png`, unchanged bytes, FIT in title and activity bars. SHA-256: `18f375fa245b97c814811e356e9a08b9fe8419f68f8b181b3a32e409ce0dc605`. No redrawing, cropping or generated logos. Upstream [Codicons](https://github.com/microsoft/vscode-codicons/tree/main/src/icons) are imported as editable SVG vectors (files, search, source-control, debug-alt, extensions and window controls).

Local design-system discovery found no editor-chat composite or Code Connect mappings. Reuse: existing `CRM / Action` main `93:4` (navy outline/text, light fill; 48px controls), existing brand/surface/border/spacing/radius variables, and new reusable Code-OSS editor shell components `548:43` / `548:76`. Community button primitives are not used in place of the compatible local CRM action. No dark surfaces.

Wording/behavior sources: [CLI code/undo and region contract](../../../cli/README.md), [code-session transport](../../../cli/src/code-mode.mjs), [command approval](../../../cli/src/code-tools.mjs). US uses Workspace/Clerk; ZA uses ZA/Zitadel with no US fallback. Example device codes and old/new file text are the existing offline CLI fixture, never live credentials. `Receipt pending` means no cost is invented. New panel labels/prompts are listed in each item audit under `words` and remain **Proposed**, even when they reuse a source phrase. Accept / Reject and Run are explicitly requested panel labels, not claims that these controls already ship.

## Frames

| Item / state | Size | Figma frame | Status | Screenshot |
| --- | --- | --- | --- | --- |
| W01-US-1440 · Sign in | 1440×900 | [548:77](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=548-77) | Proposed | [W01-US-1440.png](evidence/W01-US-1440.png) |
| W01-US-1280 · Sign in | 1280×800 | [548:136](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=548-136) | Proposed | [W01-US-1280.png](evidence/W01-US-1280.png) |
| W01-ZA-1440 · Sign in | 1440×900 | [548:195](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=548-195) | Proposed | [W01-ZA-1440.png](evidence/W01-ZA-1440.png) |
| W01-ZA-1280 · Sign in | 1280×800 | [548:254](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=548-254) | Proposed | [W01-ZA-1280.png](evidence/W01-ZA-1280.png) |
| W02-1440 · Empty state | 1440×900 | [553:1326](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=553-1326) | Proposed | [W02-1440.png](evidence/W02-1440.png) |
| W02-1280 · Empty state | 1280×800 | [553:1421](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=553-1421) | Proposed | [W02-1280.png](evidence/W02-1280.png) |
| W03-1440 · Conversation / proposed edit | 1440×900 | [555:284](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=555-284) | Proposed | [W03-1440.png](evidence/W03-1440.png) |
| W03-1280 · Conversation / proposed edit | 1280×800 | [555:390](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=555-390) | Proposed | [W03-1280.png](evidence/W03-1280.png) |
| W04-1440 · Command waiting for Run | 1440×900 | [556:1710](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=556-1710) | Proposed | [W04-1440.png](evidence/W04-1440.png) |
| W04-1280 · Command waiting for Run | 1280×800 | [556:1815](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=556-1815) | Proposed | [W04-1280.png](evidence/W04-1280.png) |

## Evidence and validation

Each item has its own `evidence/Wxx-nodes.json` construction ledger and `evidence/Wxx-audit.json` read-back: all descendant IDs, editable node-type counts, exact frame dimensions, Inter font assertion, component main IDs, discrete logo image slots and visible words. PNGs are exports for review only; no complete-UI raster is imported into the design. `evidence/validation.json` records screenshot dimensions and SHA-256.

Screenshots visually reviewed before each item push. Design/documentation only: no model calls, commands from the depicted cards, production writes or UI implementation. Native Code-OSS chrome controls remain compact; Tervory panel actions are 48px. The logo is the only raster content.
