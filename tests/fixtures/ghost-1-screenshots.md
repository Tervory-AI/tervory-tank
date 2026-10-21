# GHOST-1 visual evidence

`ghost-1-375.png` and `ghost-1-1440.png` render the actual
`workspace/app/admin/ghost/panel.tsx` component with an offline incident fixture.
They are not production evidence. Fonts and brand files are the repository's
original assets. No authentication bypass was added to the app.

Captured in the managed cloud workspace using Chromium and Playwright, at
375 × 1000 and 1440 × 1000 viewport sizes with full-page capture. Both checks
asserted no horizontal overflow and no browser runtime errors, clicked Look
with a mocked server action and verified the status text, then expanded the
worker brief and verified its title. `next build` separately validated the
real server page and server actions.
