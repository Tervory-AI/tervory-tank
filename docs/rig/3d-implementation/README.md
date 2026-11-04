# Rig 3D frames 06–07 implementation

Approval: the founder's implementation instruction approves frames 06–07 in PR #671, source branch `codex/figma-rig-3d` at `3e6306a46c77ce608be63d7ca1f9ae86df0fba3a`. That branch's register retains the earlier design-review annotations; the implementation instruction supersedes that approval status. Frame IDs and original exports are unchanged.

## Frame set 06

The retailer widget checks `rig_3d`, offers Open 3D for its selected API setup, and loads `/3d/widget-entry.js` only on that action. That module rechecks entitlement and requests a complete approved assembly before importing the renderer. The server revalidates approval, tenant, current fits and anchor mappings; the browser checks asset URL, byte size and SHA-256. Revocation/expired leases close the model view. No generated/review shape or review-only caption is packaged into the live widget. Neutral GLBs remain isolated test fixtures.

The light Custom Nation layout implements 514:4045 (1440) and 514:4101 (375), rotate, zoom, exploded view, server-approved anchored parts, swap, loading/error/photo fallback and return to the existing setup/quote form. Header menu requests the embedding application's existing shared menu through the bubbling `rig-menu` event; the widget does not duplicate authenticated CRM routes into a retailer embed. No new menu destinations are introduced.

Source of record: `docs/rig/widget-source.patch` against pinned upstream `f382f8da90944a3176c1bd43cfc77f14e78c6a0f`. Reproduce with `agents/rig/rigbox/quotes/rebuild-widget.sh`. three.js remains a separate lazy renderer chunk. GPU/forge configuration and generation paths are unchanged.

## Offline proof

Use a disposable local Postgres database, then launch:

```sh
PYTHONPATH=agents/rig:agents/_chassis:tests \
RIG_3D_TEST_DATABASE_URL=postgresql://postgres:offline_fixture@127.0.0.1:55439/postgres \
RIG_3D_TEST_DATA_DIR=/tmp/rig3d-browser-assets \
uvicorn fixtures.rig_three_d.viewer:app --host 127.0.0.1 --port 8035
python tests/fixtures/rig_three_d/browser_check.py
```

The browser proof blocks all non-loopback requests and uses Chromium's software WebGL implementation. It exercises the packaged widget, verifies lazy loading, actual anchor/explode positions, photo fallback without renderer/model fetches, disposal, no review caption and no horizontal overflow. Browser tests use reviewed neutral fixture GLBs; production never imports the fixture server or its seed.

`reference/` contains untouched Figma exports from the approved branch. `screenshots/` contains actual browser captures. `comparison.json` records pixel differences for the header, headings and controls at both widths, with exact viewport bounds separately asserted. The 56px design annotation is cropped from comparisons. The deliberately excluded design-only illustration/caption and dynamic catalogue names/prices are not pixel-matched. Text rasterization differences are measured, with mean channel error below 10/255 required. These comparisons validate the static scaffold, not the production product's appearance.

Validation at frame 06 checkpoint: TypeScript + both Vite bundles, ESLint, 36 Vitest checks, four renderer checks, offline browser proof, and CI's exact `ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"`. Base UMD gzip: 23,455 bytes (limit 153,600). No live external model or GPU call was made.
