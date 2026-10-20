# Next site

A small site: home, about, contact, privacy, and a page for addresses that do not exist.

Colours and fonts come from `app/tokens.css`. Pages use those tokens. The contact form posts to `/api/contact`, which accepts the message and does not store it.

No analytics. No third-party scripts.

## Checks

GitHub Actions runs these on every build. All of them must pass.

- ESLint and Prettier
- TypeScript
- Unit tests
- The production build
- Deploy gate: the saved pages must include a privacy notice, and a cookie notice when a page loads a script or frame from another site
- Playwright in Chromium at 390px, 768px, and 1440px, including axe-core
- Lighthouse: performance, accessibility, best practices, and SEO, each 90 or above

## Deploy

`npm run deploy` reads the HTML from the production build. It refuses to continue when a saved page has no privacy notice, or when a saved page loads a script or frame from another site and has no cookie notice. It does not fetch a page. A web address is not a saved page. Nothing is published.
