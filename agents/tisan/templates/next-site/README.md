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
- Playwright in Chromium at 390px, 768px, and 1440px, including axe-core
- Lighthouse: performance, accessibility, best practices, and SEO, each 90 or above
