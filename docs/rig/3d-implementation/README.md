# Rig 3D frames 06–07 implementation

Approval: the founder's implementation instruction approves frames 06–07 in PR #671, source branch `codex/figma-rig-3d` at `3e6306a46c77ce608be63d7ca1f9ae86df0fba3a`. That branch's register retains the earlier design-review annotations; the implementation instruction supersedes that approval status. Frame IDs and original exports are unchanged.

## Frame set 06

The retailer widget checks `rig_3d`, offers Open 3D for its selected API setup, and loads `/3d/widget-entry.js` only on that action. That module rechecks entitlement and requests a complete approved assembly before importing the renderer. The server revalidates approval, tenant, current fits and anchor mappings; the browser checks asset URL, byte size and SHA-256. Revocation/expired leases close the model view. No generated/review shape or review-only caption is packaged into the live widget. Neutral GLBs remain isolated test fixtures.

The light Custom Nation layout implements 514:4045 (1440) and 514:4101 (375), rotate, zoom, exploded view, server-approved anchored parts, swap, loading/error/photo fallback and return to the existing setup/quote form. Header menu requests the embedding application's existing shared menu through the bubbling `rig-menu` event; the widget does not duplicate authenticated CRM routes into a retailer embed. No new menu destinations are introduced.

Source of record: `docs/rig/widget-source.patch` against pinned upstream `f382f8da90944a3176c1bd43cfc77f14e78c6a0f`. Reproduce with `agents/rig/rigbox/quotes/rebuild-widget.sh`. three.js remains a separate lazy renderer chunk. GPU/forge configuration and generation paths are unchanged.

## Frame set 07

The same selected setup opens a configured terminal with `kiosk-id`. It has full screen, a reduced-motion-aware attract loop, 60-second inactivity return, phone/email quote methods, online-only submission, a confirmed saved receipt, and Start again that clears contacts and choices. Server reset revisions use the existing tenant-scoped polling route. No contacts enter IndexedDB or an offline delivery queue. A saved request is described as pending delivery until the backend explicitly confirms delivery.

The kiosk fetches the store-owned privacy notice before enabling submission. `/3d/quote` now checks its current version and records the same notice receipt used by the existing quote flow. A changed notice fails closed. The live test-page CSP permits the pinned local WASM decoder and its blob texture/worker paths; JavaScript eval stays disabled. Other retailer hosts must allow Rig's module origin, local WASM decoding, blob image/worker URLs and authenticated API requests in their own embed CSP.

Phone frames: 516:1275 / 516:1347. Email: 516:1419 / 516:1491. Quote error: 516:2121 / 516:2194. Saved receipt: 516:1709 / 516:1770. The original 1440 phone export on the design branch was capped at 1024px; this implementation's reference was re-exported from the same frame at its natural 1440px size.

## Offline proof

Use a disposable local Postgres database, then run (with Playwright, Pillow, asyncpg and the room's Python dependencies installed):

```sh
RIG_3D_TEST_DATABASE_URL=postgresql://postgres:offline_fixture@127.0.0.1:55439/postgres \
RIG_3D_TEST_DATA_DIR=/tmp/rig3d-browser-assets \
python tests/fixtures/rig_three_d/browser_check.py --serve
```

`--serve` owns and closes its local fixture process and requires an explicitly configured loopback database. The browser executable is `/opt/google/chrome/chrome` in this cloud environment. No founder laptop installation is required.

The browser proof blocks all non-loopback requests and uses Chromium's software WebGL implementation. It exercises the packaged widget, verifies lazy loading, actual anchor/explode positions, photo fallback without renderer/model fetches, disposal, no review caption and no horizontal overflow. Browser tests use reviewed neutral fixture GLBs; production never imports the fixture server or its seed.

`reference/` contains untouched Figma exports from the approved branch. `screenshots/` contains actual browser captures. `comparison.json` records pixel differences for the header, headings and controls at both widths, with exact viewport bounds separately asserted. The 56px design annotation is cropped from comparisons. The deliberately excluded design-only illustration/caption and dynamic catalogue names/prices are not pixel-matched. Text rasterization differences are measured, with mean channel error below 10/255 required. These comparisons validate the static scaffold, not the production product's appearance.

Validation at frame 06 checkpoint: TypeScript + both Vite bundles, ESLint, 36 Vitest checks, four renderer checks, offline browser proof, and CI's exact `ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"`. Base UMD gzip: 23,455 bytes (limit 153,600). No live external model or GPU call was made.

Final frame 07 validation: 65 backend checks (real disposable Postgres, approval/revocation, tenant boundaries, quote contacts and notice receipts, uploads, module CORS), 36 Vitest checks, four renderer checks and 25 existing widget Playwright checks passed. The offline packaged-widget proof passes ten exported-frame comparisons at 1440/375, including phone, email, quote failure and saved receipt, plus full screen, inactivity contact clearing, negative entitlement, expired lease, integrity and foreign asset URL cases. The six existing hosting checks also pass with the updated CSP. Maximum measured scaffold mean channel error is 6.23/255; exact viewport geometry is also checked. This is not a pixel match of fixture models or product content.

The source patch replayed successfully from the pinned clean upstream checkout using the committed rebuild script, producing the same bundle hashes. Final base UMD: **23,493 bytes gzip**, below 153,600. three.js remains in the lazy 3D viewer chunk. CI's exact Ruff command passes. No new words were introduced beyond the approved register/source wording, API product/part names and store-owned privacy notice.
