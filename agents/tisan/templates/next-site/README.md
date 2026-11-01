# Next site

The template keeps the existing contact form, `/api/contact`, and privacy page.
With no `content/site.json`, the home route renders no content and all other
unrecognized paths return an empty 404. There are no default site labels.

## Content plumbing

`sections/manifest.json` and `sections/CONTRACT.md` are the shared contract.
`scripts/content-check.cjs` validates `content/site.json` before `next build`,
without additional packages. It reports all schema errors together, including
missing required text, image sources, and alt text. Optional slots may be omitted;
when their parent object is supplied its required children must be filled.
Existing contact/privacy routes retain precedence over content for those paths.
Unknown section types, unknown properties, invalid URLs, duplicate page names,
paths or section IDs, and paths reserved for API/framework routes
are refused. Malformed JSON fails the build. Missing content is permitted.

`app/[[...path]]/page.tsx` selects the content page by its full path and supplies
its title as document metadata. The route passes sections through
`sections/registry.tsx`. Every registered section currently returns `null`.
Header, footer, and all section visuals wait for approved Figma frames; this
plumbing does not render navigation, footer, or new section UI. Contact and
privacy retain their existing words and use their existing headings as document
titles. The contact form and API behavior are unchanged.

`lib/site.ts` retains only the locale default. The existing scaffold may replace
that file with its older generated structure; the layout uses only its locale.
Content still comes exclusively from `content/site.json`, never from that older
structure. Scaffold/builder changes belong to the separate builder branch.

## Checks

- `npm run lint`: ESLint and Prettier. The shared manifest is excluded from
  formatting so this branch preserves the contract exactly.
- `npm run typecheck`: TypeScript.
- `npm test`: validation, content routing, accessibility structure, visual-checker,
  and saved-page deploy-gate unit tests.
- `npm run build`: content validation followed by the production build.
- `npm run test:e2e`: existing Playwright checks at 390px, 768px, and 1440px,
  including axe-core for contact/privacy and screenshots attached for existing
  pages. Empty home and missing routes are checked for absence of invented UI.
- `npm run lhci`: existing Lighthouse gate; each category must score 90 or above.
- `npm run test:visual`: requires recorded approved frame measurements. No
  section visuals or Figma comparison scores are claimed by this plumbing.

`tests/fixtures/site.json` is invented test-only content covering every manifest
section type. Unit tests import it directly; normal builds and the runtime loader
never fall back to it. Tests verify that a project containing only that fixture
has no runtime content. No fixture is installed at `content/site.json`.

## Deploy

The existing deploy gate remains intact. `npm run deploy` reads saved production
HTML and refuses missing privacy notices, or missing cookie notices when pages
load external scripts or frames. With section visuals pending, the template does
not yet supply those notices on every page, so deployment is refused. Nothing in
this plumbing publishes a site. The founder's real-site browser test follows the
builder work and approved Figma implementation.
