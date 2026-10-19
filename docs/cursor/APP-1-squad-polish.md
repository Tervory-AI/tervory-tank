# APP-1 — app.tervory.com: clean up the squad pages

> Written 18 Oct 2026, 18:30 PT. The squad pages are live (PR #136) but show build placeholders and controls that do nothing. Clients and lawyers will see these.

**Files you may change (corrected 18 Oct 18:45):** every file inside `workspace/app/{base,tiger,market-lab,rig,tisan,radix,zenas,skala,tank}/` (pages, view components such as `view.tsx`, `tisan.tsx`, `lab.tsx`, `plugins.tsx`, `plugins.ts`, and CSS), `workspace/app/shell.tsx`, `workspace/app/squad-links.tsx`, `workspace/app/globals.css`, and the **existing page tests** under `tests/` for those pages (`tests/test_*_page.py`, `tests/*_page.test.ts`, `tests/*_page_*.mjs`). Where an existing test pins a placeholder, a dead control or `pointer-events: none` (for example `tests/test_tisan_page.py` requiring "Chat bot, to be named"), update that test to the new behaviour; never delete a test that checks real behaviour. New tests are welcome. No backend, no schema, no new routes.

## Fix
1. **No placeholder text anywhere.** Remove or replace: "Chat bot, to be named", "Thread · __ messages", "49 · Show all", "to be named", lorem text, TODO labels, fake counts. Every number shown comes from real data; if there is none, show a short empty state ("No matters yet.").
2. **No dead controls.** Every button, tab, menu item and filter either works or is hidden. Hide Vault switches and anything marked "later".
3. **Logos.** Each page shows its agent's own official mark (`workspace/public/brand/*-on-dark.png` on the dark panel), at its natural proportions, never squeezed, at least 40px tall in the panel. Exact files only.
4. **Mobile first.** 375px wide: no horizontal scroll, no overlapping elements, tap targets 44px+, the Menu opens and closes, search and chat boxes full width.
5. **One pattern on every page:** search box, chat box ("Ask <Agent>"), Sources under answers, Plugins tab. Same spacing and type scale everywhere.
6. **Copy:** plain, confident, short. No developer words (no "route not mounted", "draft", "stub"). Error messages say what to do next.

## Done when
CI green; a test fails the build if any page contains "to be named", "__", "TODO", "lorem" or "stub"; screenshots at 375px and 1440px for all nine pages in the PR; Lighthouse accessibility 90+ on each page.
