# W-1 — Client onboarding: sign up to first results

**Goal:** a new client goes from sign-up to their first enriched records without help.

**Files you may change:** `workspace/app/onboarding/*` (new), `workspace/app/page.tsx` (redirect new orgs to onboarding only), `workspace/lib/tank.ts`, `workspace/lib/tenant.ts`, new tests. No Tank changes.

- **Steps:** (1) create or join an organisation (Clerk organisations = tenants); (2) choose the industry engine (list from `GET /v1/base/engines`); (3) upload a CSV (drag-and-drop; show the first 5 rows; map columns to name, address, city, state, zip, phone, with sensible auto-matching); (4) start the run (`POST /v1/base/run`) and show live progress per pass; (5) land on the Data page filtered to that batch.
- Show what each step costs in plain English before Start (most steps are free; paid steps use the cheapest option available). Nothing waits for approval.
- Validation in plain English (missing columns, empty rows, file too big: 10 MB limit). Nothing is uploaded until the user presses Start.
- Brand rules from AGENTS.md; works at 390 px and 1440 px.

**Done when:** CI green; a Playwright test walks a fresh organisation from sign-up to a started batch with the fixture CSV.
