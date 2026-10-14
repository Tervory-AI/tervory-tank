# tisan.scaffold

## 1.0.0
- First version. Turns a short brief into a Next.js project (TypeScript, Tailwind, ESLint, Prettier, Vitest, Playwright).
- Brand colours and fonts become CSS variables and Tailwind tokens. Components do not hard-code colours.
- Writes `/data/builds/<tenant>/<slug>/<n>.tar.gz` and a manifest with `files`, `token_set`, and `checks`.
- Runs `npm ci`, `npm run lint`, `npm run build`, and `npm test` before returning. The room image caches those dependencies so the run can stay offline.
