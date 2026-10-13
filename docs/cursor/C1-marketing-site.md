# C1 — tervory.com marketing site

**Goal:** build the public site at tervory.com exactly from the approved Figma design, as a static Next.js app in a new `site/` folder of this repo.

**Source of truth:** Figma file https://www.figma.com/design/ksi7ctRwEnN8wbip1yfuhL — page "Landing — Desktop & Mobile", frames `Desktop — 1440` (node 2:11) and `Mobile — 390` (node 6:45). Read it with the Figma MCP (get_design_context per section). Colour/type/space tokens are Figma variables in collections "Tervory / Colour", "Tervory / Type", "Tervory / Space" — turn them into CSS variables, do not hard-code hex values in components.

**Logo:** use `workspace/public/brand/tervory-logo.png` (on light) and `tervory-logo-reversed.png` (on navy) — copy them into `site/public/brand/`. Never redraw or re-typeset the logo.

**Build:**
- `site/` = Next.js 15, App Router, `output: 'export'` (static), TypeScript strict, no client JS except the mobile nav toggle.
- Fonts via `next/font/google`: Jost (300, 400), Inter (400, 500, 600), JetBrains Mono (400).
- One page (`/`) with the nine sections in the Figma order. Section ids for nav anchors: `how`, `tank`, `squad`, `case-study`, `ledger`, `pricing`.
- "Sign in" → `https://app.tervory.com/sign-in`; "Start" and "Start with your own data" → `https://app.tervory.com/sign-up`.
- Copy exactly as in Figma. Numbers marked as placeholders in Figma (ledger tiles, hero table) stay as they are and get a small "Example" label.
- Responsive: match the 390 frame below 768 px; no horizontal scroll at 375 px.
- Meta: title "Tervory AI — Ask for the work. See exactly what it cost.", description from the hero sub-line, Open Graph image = a 1200×630 export of the hero (add as `site/public/og.png`).
- A `site/Dockerfile` that builds the static export and serves it with a tiny static server (nginx:alpine or `serve`), exposing port 3000.
- Lighthouse on the built page: performance ≥ 95, accessibility ≥ 95 (contrast must pass on navy bands).

**Do not:** touch `workspace/` or `tank/`; add analytics, cookies or trackers; add the site to `docker-compose.yml` (Claude wires the Coolify service and domain after merge).

**Done when:** PR open with desktop and mobile screenshots side by side with the Figma frames, and the Lighthouse scores in the description.
