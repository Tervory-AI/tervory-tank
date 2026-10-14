# TS-1 — Tisan: the project scaffold

**Goal:** Tisan's first skill: produce a ready-to-build website project from a short brief, so later skills (Figma reader, test runner, deploy) have a standard base.

**Files you may change:** `agents/tisan/` (app, Dockerfile, README), `agents/tisan/templates/next-site/` (new), `tank/skills/tisan.scaffold/1.0.0/` (evals + CHANGELOG), new tests. Not `docker-compose.yml`.

- **Template:** Next.js (App Router) + TypeScript strict + Tailwind, with ESLint, Prettier, Vitest, Playwright and a GitHub Actions CI file. Pages: home, about, contact (form posts to a placeholder endpoint), privacy, 404. Accessible by default: landmarks, labels, focus styles, alt text.
- **Inputs** (`tisan.scaffold`): `{name, slug, pages[], brand: {colours, fonts, logo_url}, locale}`. Brand values become design tokens (CSS variables + Tailwind theme). No hard-coded colours in components.
- **Output:** the generated project as a tarball stored in Tisan's `/data/builds/<tenant>/<slug>/<n>.tar.gz`, with a manifest (`files`, `token_set`, `checks`).
- **Checks run in the room before returning:** `npm ci`, `npm run lint`, `npm run build`, `npm test`. Dependencies are installed at **image build time** into a cache, so a run needs no internet (Tisan's room is standard, but keep runs offline where possible).
- **No secrets** in generated code. No analytics or third-party scripts unless asked.

**Done when:** CI green; the skill's evals generate two different brands and both build and pass their own tests inside the room.
