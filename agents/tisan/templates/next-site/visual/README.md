# Frame comparison

`npm run test:e2e` includes the visual gate. Add `visual/frames.json` as an array
of recorded frames, one per page at **375px and 1440px**. Each record has `page`
(a local path), `frameId`, `width`, `height`, `tokens` (CSS variable name to
recorded six-digit hex colour), and `elements`. Each element maps a `nodeId` to
one unique DOM `selector`, a document-relative `box` (`x`, `y`, `width`, `height`),
optional exact `text`, and `colours` (CSS property to token name). Supported
properties: `color`, `backgroundColor`, `borderTopColor`.

Use measured frame coordinates relative to the frame origin, not Figma canvas
coordinates. Include all meaningful layout and text nodes. Coverage is exactly
the explicit mapping; unmapped nodes are not checked. Do not resize a 390px
frame and call it a 375px reference. Never generate expected measurements from
the page under test. A logo must use the original asset, never a drawn copy.

The browser waits for fonts and images, disables animation, and blocks external
requests. Package original fonts/images locally. Each page gets a 0–1 score and
layout/text/colour breakdown, with a screenshot and JSON attachment. A box may
differ by at most 2 CSS pixels. Any failed check or horizontal overflow fails
review CI, even if the aggregate score is high. Missing/duplicate/hidden elements
fail. Colours compare the recorded token against both the CSS variable and the
painted property, so changing the token cannot silently update the baseline.

No file means an explicit UNSCORED skipped test, not a passing comparison.
A present but empty, invalid, or incomplete file fails. The generic starter has
no Figma counterpart, and the repository's current Tervory recording lacks full
boxes/text and a 375px frame. Supply that evidence before claiming visual parity.
The synthetic checker tests are labelled test data and are never gold candidates.
Screenshots/reports can contain page content: keep client artifacts in their
region and do not publish them as public fixtures. Never include credentials.

Run `npm run test:visual` for an explicit review gate. This command fails with
`frame data incomplete` when the reference file is absent. Figma-linked scaffold
jobs always write a reference file from the saved reading, so missing fields
cannot silently skip their generated CI comparison. REST captures retain the
original document and map measured nodes to `data-figma-id` selectors; a builder
must carry those ids onto the matching DOM elements. Unsupported non-image paints remain
in the raw evidence and are flagged incomplete, never approximated. Fixture
captures may supply the same explicit mapping plus an original `preview_png`
for the founder review; the reader retains it without redrawing the frame.

Image fills and logo instances are atomic elements (`asset: "image"` or
`asset: "logo"`): score their position and size, without text or paint checks
inside them. Logos additionally require a local image whose SHA-256 matches an
exact PNG in `workspace/public/brand/`. Inline redraws and altered files fail.
`brand-hashes.json` records those hashes; a repository test detects drift.
Other unsupported paints still leave the frame incomplete.
