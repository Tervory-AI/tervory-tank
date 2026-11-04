# Tervory mobile delivery

Gate 1 reuses the Workspace unchanged: standalone manifest, iOS home-screen
metadata, and square 180/192/512 PNGs rendered from the exact existing
`workspace/public/brand/tervory-logo-reversed.png`. The logo retains its aspect
ratio and sits inside the maskable safe zone on brand navy, never a white box.
No new logo, screen or visible wording is drawn.

The worker caches only install metadata/icons and same-origin `_next/static`
JS/CSS/fonts. Navigations, APIs, JSON, documents, query-bearing requests,
non-GETs, cross-origin requests and private/no-store responses are not cached.
There is no authenticated HTML offline fallback and no offline client storage.
Install through Safari's Share → Add to Home Screen or Android browser Install.
Existing authentication and all product work still require connectivity.

Gate 3 acceptance is tracked in [`../acceptance/mobile.md`](../acceptance/mobile.md).
Run the web rows after deployment. Store rows explicitly depend on the separate
gate 2 merge and versioned installable builds; this branch creates no `mobile/`.
Gate 1 adds no environment variables or alternate identity configuration.

Gate 2 integration finding: main's Workspace authenticates with Clerk. Existing
Zitadel support is ZA-only CLI device authorization (`tank/identity_device.py`),
not a Workspace session issuer. A native wrapper must not treat a Zitadel token
as a Clerk session or invent an organization mapping. The native gate must prove
this boundary before claiming system-browser sign-in works.
