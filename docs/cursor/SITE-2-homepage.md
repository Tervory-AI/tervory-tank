# SITE-2 — tervory.com homepage: new copy, logo-led products

> Written 18 Oct 2026, 18:30 PT by Claude. The live copy was rejected by the founder. This brief carries the replacement copy; use it **word for word**. The founder designed the product logos himself: they lead the products section at full size.

**Files you may change (corrected 18 Oct 18:50):** `site/app/page.tsx`, `site/app/globals.css`, `site/app/release-form.tsx` (labels only), `site/app/layout.tsx` (title and description only), `site/app/footer.tsx` (copy only), `site/lib/site.ts` (title and description: this is the single source, layout reads from it), `site/check-public.mjs` and `site/check-store.mjs` (update them to expect the new copy), new tests under `tests/` or `site/`. **Added 18 Oct 19:25:** `site/server.mjs` (text compression only: gzip/brotli with Node's built-in `zlib`, no new dependency, text types only, `Vary: Accept-Encoding`; the release form behaves exactly as before), and `docs/screenshots/site-2/` (the 375px and 1440px PNGs, shown inline in the PR description). Use only the existing logo files in `site/public/brand/` (exact files, never redrawn, recoloured or cropped). No new pages, no pricing, no sign-up, no tracking.

## Layout
- Hero, How it works, Why it gets cheaper, Products, Built on proof, Early access, footer.
- **Products:** a grid of nine cards. Each card: the product's logo at its natural proportions, **at least 56px tall on mobile and 72px on desktop**, never squeezed; the product name is in the logo, so no separate heading; one line of copy under it. 1 column on phones, 2 on tablets, 3 on desktop. Generous white space.
- Keep the fonts and colours already in the site (Jost, Inter; navy #001840, red #E80008). No reveal animation that leaves sections blank before scrolling.
- Lighthouse 90+ for performance, accessibility, SEO. Every logo has alt text with the product name.

## Copy (use exactly)

**Page title:** Tervory AI: specialist AI for the work that runs a business
**Meta description:** A squad of specialist AI agents for data, pricing, markets, legal, security and the web. Every answer shows its sources, the model that ran it, and what it cost.

**Hero**
- Eyebrow: Tervory AI · In build
- Headline: Specialist AI for the work that runs a business.
- Body: Tervory is a squad of specialist AI agents for data, pricing, markets, legal, security and the web. Ask in plain language. The right specialist does the work, shows its sources, and tells you which model ran it and what it cost.
- Form label: Get early access
- Button: Join the list
- Small print: We are opening to a small group of businesses first.

**How it works** (heading: How it works)
1. **Ask.** Describe the job the way you would brief a colleague.
2. **Routed.** Tank sends it to the specialist built for that job, on the best-value route that still gets it right.
3. **Answered.** Every answer comes with its sources, the model that produced it, and the cost.

**Why it gets cheaper** (heading: It gets cheaper the more it works)
Most AI charges the same for the hundredth question as the first. Tervory learns. When a cheaper model, or plain code, proves it gives the same answer, it takes over the task, automatically and only after it has been tested. The work stays right. The cost keeps falling.

**Products** (heading: The squad · sub: Nine specialists. Each one built for a single job.)
- Base: Turns a raw list into verified businesses: websites, contacts and licences, each with a source.
- Tiger: Watches prices and competitors, and tells you the moment a rival moves.
- Market Lab: Market research with every number sourced: demand, gaps, and shifts before they show.
- Rig: Finds the right product, and every part that fits it, in a retailer's own catalogue.
- Tisan: Builds websites and apps from a short brief, tested before they go live.
- Radix: Finds what your systems and sites expose, before someone else does.
- Zenas: Legal research and drafting for US and South African business law, reviewed by licensed lawyers.
- Skala: The skills library. Every skill is tested before a specialist may use it.
- Tank: The engine underneath. It routes every task to the best-value model and keeps the receipts.

**Built on proof** (heading: Measured, not promised)
Every skill passes a test set before it goes live. A cheaper route only takes over once it matches the results. If we cannot measure it, we do not claim it.

**Footer line**
Every answer shows its sources, the model that ran it, and what it cost.

**Early access** (heading: Be first in)
We are opening Tervory to a small group of businesses first. Leave your email and we will tell you when your seat is ready.
- Button: Join the list

- The phrase "one window" must not appear anywhere on the site (title, meta, copy, alt text). Add a test for it.

## Done when
CI green; the page shows exactly this copy; each of the nine logos renders at the sizes above on a 375px phone and a 1440px desktop (screenshots in the PR); Lighthouse 90+ on all three scores; the release form still stores emails as before. The PR includes both screenshots so the founder can approve before merge.
