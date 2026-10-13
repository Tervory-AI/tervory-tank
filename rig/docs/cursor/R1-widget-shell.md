# R1 — Widget shell on sample data (Phase 1)

**Goal:** the five Figma frames working as one embeddable web component on sample data, themed for Custom Nation, ready to switch from the mock to Rig's live API by changing one attribute.

**Read first:** `AGENTS.md`, `docs/api.md`, and the Figma file `uRpPy3Hns0WxWZYTPwZ2ni` (frames 00–05; 00 is notes).

**Build:**
1. Repo setup: `widget/` (TypeScript, Vite, Shadow DOM web component `<tervory-rig>`), `demo/` (a plain HTML page embedding it), npm scripts `dev`, `build`, `test`, `lint`. Output: one ES module + one UMD bundle under 150 KB gzipped.
2. API client implementing `docs/api.md`, and a mock (`widget/src/mock/`) implementing every call on a sample catalogue JSON: Staccato C2 / P / XC, the red dots and holsters shown in Figma, each with attributes (optic cut, holster fit) and simple fitment so the mock returns the same three setups as the Figma frame. Every sample item is labelled SAMPLE DATA in the UI. Attribute `api-base="mock"` selects the mock.
3. Screens from the frames: Search (empty state, popular makes, three-step "how it works"), Results, Complete your setup (three setups, swap a part, one indicative total, "Request a quote for this setup", "Quote this only"), Can't find it (paste a link + note), Explore graph view (product at the centre, branches to fitted categories with counts, then products; side panel with setup, total and "why"; "Ask a question" box calling `/ask`).
4. Theme tokens with the Custom Nation theme: cream #f2efe7, ink #242722, red #ad322c, Barlow Condensed (headings) + Inter (body). A second neutral theme to prove nothing is hard-coded.
5. Tests: unit tests for the API client and mock contract (every call's shape), and a Playwright smoke test of the main path at 390 and 1440 px.

**Not in this task:** any real backend, search engine, AI, supplier feeds, or the Custom Nation site.

**Done when:** every frame is reproduced at 1440 and 390 px with no horizontal scroll, keyboard usable, only one indicative total ever shown, the neutral theme works, tests pass, and the demo page runs. PR with screenshots of each screen at both widths, then stop for Claude's review.
