# Rig 3D · L29 · frames 06–07

**Proposed. Not approved.** Figma file `ZnphBOJU6657tohGLD3IzS`, page [11 · Rig 3D · L29 · Proposed](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-3091), ID `514:3091`.

Branch `codex/figma-rig-3d` started at `origin/main` commit `8857cd3e3fcda721694792817a6295c923a2adbd`. The existing `docs/figma/RIG-3D-FRAMES.md` states that 06–07 have no approval. US cart S06/A07 approval is unrelated. No existing approved frame or shared component was changed.

The brief’s 1440/375 widths and Inter/light/navy-button requirements supersede the older 390px, 1920px, condensed-heading and dark-stage requirements. All new text, fixture names, status annotations and UI changes on this page are **Proposed**, including source wording reused from the product; nothing here grants implementation approval.

## Screen 06 · 3D product viewer

| State | Width | Figma frame | Size | Screenshot | Status |
| --- | --- | --- | --- | --- | --- |
| ready | 1440 | [514:4045](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4045) | 1440 × 908 | [PNG](screenshots/06-ready-1440.png) | Proposed |
| ready | 375 | [514:4101](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4101) | 375 × 1268 | [PNG](screenshots/06-ready-375.png) | Proposed |
| rotated | 1440 | [514:4157](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4157) | 1440 × 908 | [PNG](screenshots/06-rotated-1440.png) | Proposed |
| rotated | 375 | [514:4213](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4213) | 375 × 1268 | [PNG](screenshots/06-rotated-375.png) | Proposed |
| exploded | 1440 | [514:4269](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4269) | 1440 × 908 | [PNG](screenshots/06-exploded-1440.png) | Proposed |
| exploded | 375 | [514:4328](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4328) | 375 × 1268 | [PNG](screenshots/06-exploded-375.png) | Proposed |
| anchors | 1440 | [514:4387](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4387) | 1440 × 948 | [PNG](screenshots/06-anchors-1440.png) | Proposed |
| anchors | 375 | [514:4447](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4447) | 375 × 1308 | [PNG](screenshots/06-anchors-375.png) | Proposed |
| empty | 1440 | [514:4507](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4507) | 1440 × 824 | [PNG](screenshots/06-empty-1440.png) | Proposed |
| empty | 375 | [514:4551](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4551) | 375 × 1088 | [PNG](screenshots/06-empty-375.png) | Proposed |
| loading | 1440 | [514:4595](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4595) | 1440 × 832 | [PNG](screenshots/06-loading-1440.png) | Proposed |
| loading | 375 | [514:4640](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4640) | 375 × 1192 | [PNG](screenshots/06-loading-375.png) | Proposed |
| error | 1440 | [514:4685](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4685) | 1440 × 824 | [PNG](screenshots/06-error-1440.png) | Proposed |
| error | 375 | [514:4729](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4729) | 375 × 1112 | [PNG](screenshots/06-error-375.png) | Proposed |
| photos | 1440 | [514:4773](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4773) | 1440 × 824 | [PNG](screenshots/06-photos-1440.png) | Proposed |
| photos | 375 | [514:4816](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4816) | 375 × 1064 | [PNG](screenshots/06-photos-375.png) | Proposed |
| menu | 1440 | [514:4859](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-4859) | 1440 × 908 | [PNG](screenshots/06-menu-1440.png) | Proposed |
| menu | 375 | [514:5000](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=514-5000) | 375 × 1268 | [PNG](screenshots/06-menu-375.png) | Proposed |

The ready, rotated, exploded and anchors states illustrate a centre fixture and two parts. Fixture anchor positions come from `tests/fixtures/rig_three_d/models/centre.json` (left/right at ±80mm). The editable isometric drawings explain assembly and fit-anchor behavior; they are **design-only neutral stand-ins**, not real Custom Nation product photos, actual GLB renders, approved production models or a working 3D engine. Only server-returned approved fits may attach; an incompatible/unapproved fit must not snap. Keyboard arrows/plus/minus and reduced-motion behavior remain requirements from the product. Rotation/zoom buttons navigate review variants; the prototype is not a WebGL simulation. The current zoom review link uses a changed-view variant rather than a calibrated camera zoom.

Empty/loading/error/photo-fallback states exist at both widths. Empty has no chosen model and cannot request a quote. Loading and load failure disable the model controls; error opens the photo fallback. The photo fallback contains an explicitly named photo slot because no real product photo was supplied; it does not fabricate one. Existing setup fields on these design states are placeholders, not fetched products. Total is `—`, not a fabricated price. No catalogue, product, contact or quote is read or created.

Screen 06 has 78 non-self, same-width review links between viewer variants, with zero text-bound issues after the compact shared-menu label was changed to FILL within its own instance. Cross-screen quote links are connected when screen 07 is added. All 18 screenshots are saved after the menu sizing correction. Desktop anchor and mobile ready compositions were visually inspected; remaining states have structural bounds checks and per-frame screenshots.

## Source, theme and component provenance

- Requirement/approval gate: `docs/cursor/RIG-PHASE-1.md` sections RIG-5a/RIG-5 and `docs/figma/RIG-3D-FRAMES.md`.
- Current source wording: `agents/rig/rigbox/three_d/widget/assets/viewer-rM6udzfj.js`, `agents/rig/rigbox/three_d/widget/assets/index-DiMsDMFY.js`, `agents/rig/rigbox/quotes/widget/tervory-rig.274b83f574e1ba645aa48238a154334eaf9a0f56f0cc4c9d0970f7c8e92117fa.umd.js`.
- Custom Nation light palette from that widget’s `custom-nation` theme: canvas `#f2efe7`, ink `#242722`, muted `#686b60`, line `#d5d0c3`, white cards, badge `#e8e4da`. Navy main actions `#001840` and Inter throughout override the old red actions/Barlow headings/dark graph as explicitly requested. Custom Nation is a store-name label, not a redrawn logo.
- Existing linked button components `289:13945` / `289:13947`, blank input `289:13953`, shared menu bar `180:8550`, shared menu drawer `180:8467`. Instances receive local text/Inter/size overrides only. Main components, routes and shared navigation labels remain unchanged. Drawer entries are inherited product navigation, not newly invented destinations. Store/kiosk navigation context remains Proposed for founder review.
- No matching Code Connect files were present for these roles. Search of the subscribed Simple Design System library for 3D viewer and kiosk quote form returned no matching composite; existing on-file components are used.

## Wording ledger · all Proposed

Source wording reused exactly includes **3D product view**, **Explore this setup**, **Rotate left**, **Rotate right**, **Zoom in**, **Zoom out**, **Exploded view**, **Back to setups**, **Your setup**, **Swap**, **Request a quote**, **Loading product view…**, **Photos are available for this product.**, **The 3D view could not load. Please use the product photos.**, **Product photo (from feed)**, and **One indicative total per setup. We confirm stock, permits and the final quotation in your client space.** Source paths above. These exact strings were read before design construction.

New or composed wording, explicitly **Proposed**: **Stand-in models · design review only**; **Centre product**; **Part A · left**; **Part B · right**; **Indicative total: —**; **Approved fit only: Part A → left; Part B → right.**; **Choose a product to explore in 3D.**; **Photos** as a control label; and each **Proposed · L29 · 06 · {state} · {width}** review caption. Here “Approved fit” states the required data gate; it does not approve this design or any fixture.

## Evidence and mutation manifest

[Screen 06 node manifest](06-nodes.json) includes every created frame/layer ID, local instance sizing changes, and prototype sources. All created nodes belong to the new page. Existing approved pages and shared component definitions were read-only. Text, controls and fixture geometry remain editable layers and linked instances; no flattened UI screenshot was imported.

Screen 07 is next and remains incomplete in this first screen checkpoint. No runtime code, deployment, real contact, quote submission, secret, entitlement or paid service is changed. Runtime tests do not apply to the design-only deliverable.

