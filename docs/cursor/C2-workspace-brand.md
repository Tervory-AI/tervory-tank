# C2 — Brand the Workspace

**Goal:** app.tervory.com looks like Tervory: official logo in the header, navy/red palette, Jost headings, favicon.

**Files you may change:** `workspace/app/layout.tsx`, `workspace/app/globals.css`, `workspace/app/icon.png` (new), `workspace/app/apple-icon.png` (new). Nothing else.

**Do:**
- Header: replace the "Tervory" text link with `<Image src="/brand/tervory-logo.png">` (height 28 px, width auto, alt "Tervory AI"), linking to `/`. Keep the nav links and Clerk controls as they are.
- `globals.css`: replace the current colour variables with the brand tokens — `--fg: #001840`, `--accent: #001840` for primary buttons, a new `--red: #E80008` used only for the 👍 accepted state and the active nav underline, `--line: #D9DEE9`, `--muted: #5B6478`, subtle background `#F4F6FB` for the page and white for cards/rows. Keep the dark-mode block working: navy `#0B1326` background, white text, logo switches to `/brand/tervory-logo-reversed.png` via a `<picture>` with `prefers-color-scheme`.
- Headings (`h1`, `h2`, `.group-title`, tile numbers) in Jost Light via `next/font/google`; body Inter; `.meta`, cost figures and the ledger table numbers in JetBrains Mono.
- Favicon / app icon: crop the emblem only (circle, lines, red dot) from `workspace/public/brand/tervory-logo.png` to a square 512×512 PNG with transparent background. Do not redraw it.
- Check every page (Chat, Tasks, Data, Skills, Ledger, Tank) still reads: no text below 4.5:1 contrast.

**Done when:** PR with before/after screenshots of all six pages, light and dark.
