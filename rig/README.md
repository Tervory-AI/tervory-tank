# Tervory Rig — widget

The embeddable "find it and complete the setup" widget. Rig's brain lives in `Tervory-AI/tervory-tank` (`agents/rig/`). Start with `AGENTS.md`; tasks are in `docs/cursor/`.

This repo is the shopper UI only. It holds no secrets. With no `api-base`, the widget calls the live API on the page origin. Set `api-base="mock"` to use the sample catalogue in `widget/src/mock/catalogue.json`. The mock is loaded only in that case. A failed live call does not fall back to the mock.

The default theme is neutral. Set `theme="custom-nation"` for the Custom Nation skin. `fonts="off"` skips loading the theme's font stylesheet.

```html
<script src="https://example.com/tervory-rig.umd.js"></script>
<tervory-rig api-base="mock" rig-key="pk_demo" theme="custom-nation"></tervory-rig>
```

`theme` is `neutral`, `custom-nation`, or a JSON theme object. A script can also set the `themeData` property to a theme object.

## Scripts

- `npm run dev` — demo page at `/demo/index.html`
- `npm run build` — typecheck, then one ES module and one UMD bundle in `dist/` (each under 150 KB gzipped)
- `npm test` — API contract tests and a Playwright smoke test at 390 px and 1440 px
- `npm run lint`
