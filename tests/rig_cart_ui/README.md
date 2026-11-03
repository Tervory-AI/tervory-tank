# Offline cart UI comparison

Each `<node>-built.png` is the actual cart renderer or actual React CommerceAdmin component at 1440 or 375 CSS pixels. Its matching `<node>-figma.png` is the Figma tool export. All 52 approved frame variants are represented. Product values and IDs are offline placeholders, not live acceptance evidence. The preview uses local copies of the existing approved fonts; no browser request reaches a store, Tank or a model.

Compare matching files side by side. Figma annotation bands (72 desktop / 89 mobile pixels) are not product UI. Admin references additionally include the future 240px sidebar and mobile navigation; those are intentionally excluded from implementation under the brief. The page content uses the existing Workspace shell. The desktop captures retain the requested 1440px viewport. Product IDs differ because these captures use explicitly named placeholder fixtures. Font rasterization and page-height whitespace can differ between Figma exports and Chromium. These captures do not claim pixel identity with Figma.

Quote-store before/after captures at both widths are pixel-identical; rendered content DOM also matches exactly. Only the new, unused cart stylesheet and cart-mode probe are added for quote stores.

`capture.cjs`, `admin-check.cjs`, and `quote-compare.cjs` record the checks, run from the repository root with the ignored `.rig-validation` Vite harness on port 5183 and rebuilt pinned widget source. The admin check verifies real React SSR never emits supplied saved credentials, blank browser password fields, keyboard selector focus and both payment-confirmation variants of Needs a person. API responses are offline fakes. The two Figma gaps and the founder's approved handling are recorded under Waiting for Figma in the handoff.
