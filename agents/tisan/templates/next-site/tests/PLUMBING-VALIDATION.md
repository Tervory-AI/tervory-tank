# Tisan plumbing validation — 1 November 2026

Scope: founder's revised plumbing brief. No section visuals were implemented.
`sections/manifest.json` and `sections/CONTRACT.md` match the fetched
`tisan/sections-contract` commit `6cf65168` exactly.

## Changes for review

Paths below are relative to `agents/tisan/templates/next-site/`.

| File and line | Behavior |
| --- | --- |
| `scripts/content-check.cjs:10` | Plain-code validation of the manifest's JSON Schema subset; aggregates errors, including missing required descendants and image alt text. |
| `scripts/content-check.cjs:108` | Document/page validation, unknown-section refusal, unique names/paths/IDs, API/framework route protection. |
| `scripts/content-check.cjs:145` | Reads only `content/site.json`; missing content is allowed, malformed/invalid content fails. |
| `package.json:7` | Runs the checker before `next build`; no package or lockfile additions. |
| `lib/content.ts:25` | Runtime uses the same checker, without a fixture fallback. |
| `app/[[...path]]/page.tsx:10` | Selects content by full path, uses its title, and renders through the registry. |
| `sections/registry.tsx:7` | Every contract section type returns nothing pending approved Figma. |
| `app/layout.tsx:8`, `lib/site.ts:3`, `app/not-found.tsx:1` | No default site name, nav, footer, welcome, or error wording. Default home/about files removed. |
| `app/contact/page.tsx:1`, `app/privacy/page.tsx:1` | Existing heading reused as document title. Page bodies and contact API unchanged. |
| `tests/content-check.test.ts:1`, `tests/content-route.test.ts:1` | Validator/route behavior, all section types, and test-fixture isolation. |
| `e2e/pages.spec.ts:6` | Browser checks and screenshot files for existing pages at all three configured widths. |
| `tests/test_tisan_scaffold.py:50` (repository root) | Replaces assertions about deleted default pages and invented logo alt text. |

Existing contact/privacy routes retain precedence when content includes those
paths. Site-level and section slots follow the manifest's required/optional
rules; absent optional slots are not invented.

## Commands and results

Template commands ran from
`/workspace/codex-tisan-sections/agents/tisan/templates/next-site`.
The temporary directory override avoids the host's exhausted `/tmp` user quota.

| Exact command | Result |
| --- | --- |
| `TMPDIR=/workspace/codex-tisan-sections/.git/tmp npm test` | 53 passed, 6 test files. |
| `npm run lint` | ESLint and Prettier passed. Shared manifest excluded from reformatting. |
| `npm run typecheck` | Passed. |
| `TMPDIR=/workspace/codex-tisan-sections/.git/tmp npm run build` | Passed; checker runs first. Routes are the content catch-all, existing contact/privacy, contact API and empty not-found. |
| `TMPDIR=/workspace/codex-tisan-sections/.git/tmp npm run test:e2e` | 31 passed, 11 skipped. Contact/privacy axe checks pass at 390/768/1440. Skips are existing single-project visual-checker deduplication and absent Figma evidence. |
| `TMPDIR=/workspace/codex-tisan-sections/.git/tmp npm run lhci` | Configured assertions passed for both existing pages, three runs each. |

Repository command, from `/workspace/codex-tisan-sections`:

```sh
TMPDIR=/workspace/codex-tisan-sections/.git/tmp .git/venv/bin/python -m pytest -q -rs tests/test_tisan_*
```

Result: **50 passed, 1 skipped**. The skipped test is
`tests/test_tisan_gold_sources.py:138`, which requires the CI Postgres database.
The local test environment uses Python 3.12, matching Tank's runtime; npm installs
use the existing lockfiles. No model calls or production data were used.

Lighthouse scores (performance/accessibility/best-practices/SEO):

| Page | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| Contact | 92/100/100/90 | 83/100/100/90 | 97/100/100/90 |
| Privacy | 97/100/100/90 | 97/100/100/90 | 96/100/100/90 |

The existing Lighthouse median assertions pass; one contact performance sample
was below 90. No assertion thresholds were changed.

Initial local runs exposed stale default-page assertions, missing test
prerequisites, missing document titles, and test-runner JSX/module setup issues.
Those were corrected before the passing runs above. Deploy-gate assertions now
verify refusal of pending designs, rather than claiming blank pages can publish.
The gate implementation itself is unchanged.

## Browser evidence and remaining boundary

Six screenshots are saved under the template's local `test-results/` directory:
`pages--contact-has-its-exi-52337--or-an-empty-pending-design-{mobile,tablet,desktop}/page.png`
and
`pages--privacy-has-its-exi-fda68--or-an-empty-pending-design-{mobile,tablet,desktop}/page.png`.
These are local test-browser evidence of the existing pages. They are not the
founder's real-site acceptance test. Figma comparison remains unscored until
approved frames exist; the founder's browser test follows the builder work.

No PR was opened or merged; Claude opens the PR from `codex/tisan-sections`.
On merge, changes under `agents/tisan/` redeploy the Tisan room and its configured
regional copies under the existing deploy-on-merge rules. This branch does not
change runtime configuration or publish a generated site.
