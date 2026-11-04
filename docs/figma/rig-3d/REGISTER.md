# Rig 3D · L29 · frames 06–07

**Approved 3 Nov 2026, 17:47 PT** (Claude, under the founder's 3 Nov 13:28 delegation): all 56 frames of 06 (viewer) and 07 (kiosk) and their wording, at this commit. The stand-in models and the "Stand-in models · design review only" line are Figma-only and never reach a live page; the widget shows only approved models.

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

Screen 06 was pushed first; screen 07 is completed in the following section. No runtime code, deployment, real contact, quote submission, secret, entitlement or paid service is changed. Runtime tests do not apply to the design-only deliverable.


## Screen 07 · Full-screen dealership terminal

**Proposed.** Desktop compositions are 1440 × 1024. Mobile companions are 375px wide with vertically scrolling content and the same touch controls; the new brief’s 375px target supersedes the older 390px requirement. The older 1920 × 1080 runtime target is not an extra frame in this brief and is not claimed verified here.

| State | Width | Figma frame | Size | Screenshot | Status |
| --- | --- | --- | --- | --- | --- |
| attract | 1440 | [516:421](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-421) | 1440 × 1024 | [PNG](screenshots/07-attract-1440.png) | Proposed |
| attract | 375 | [516:481](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-481) | 375 × 1552 | [PNG](screenshots/07-attract-375.png) | Proposed |
| attract-rotated | 1440 | [516:541](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-541) | 1440 × 1024 | [PNG](screenshots/07-attract-rotated-1440.png) | Proposed |
| attract-rotated | 375 | [516:601](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-601) | 375 × 1552 | [PNG](screenshots/07-attract-rotated-375.png) | Proposed |
| attract-still | 1440 | [516:661](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-661) | 1440 × 1024 | [PNG](screenshots/07-attract-still-1440.png) | Proposed |
| attract-still | 375 | [516:721](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-721) | 375 × 1552 | [PNG](screenshots/07-attract-still-375.png) | Proposed |
| ready | 1440 | [516:781](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-781) | 1440 × 1024 | [PNG](screenshots/07-ready-1440.png) | Proposed |
| ready | 375 | [516:841](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-841) | 375 × 1528 | [PNG](screenshots/07-ready-375.png) | Proposed |
| rotated | 1440 | [516:901](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-901) | 1440 × 1024 | [PNG](screenshots/07-rotated-1440.png) | Proposed |
| rotated | 375 | [516:961](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-961) | 375 × 1528 | [PNG](screenshots/07-rotated-375.png) | Proposed |
| exploded | 1440 | [516:1021](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1021) | 1440 × 1024 | [PNG](screenshots/07-exploded-1440.png) | Proposed |
| exploded | 375 | [516:1084](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1084) | 375 × 1528 | [PNG](screenshots/07-exploded-375.png) | Proposed |
| anchors | 1440 | [516:1147](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1147) | 1440 × 1024 | [PNG](screenshots/07-anchors-1440.png) | Proposed |
| anchors | 375 | [516:1211](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1211) | 375 × 1568 | [PNG](screenshots/07-anchors-375.png) | Proposed |
| phone | 1440 | [516:1275](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1275) | 1440 × 1024 | [PNG](screenshots/07-phone-1440.png) | Proposed |
| phone | 375 | [516:1347](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1347) | 375 × 1448 | [PNG](screenshots/07-phone-375.png) | Proposed |
| email | 1440 | [516:1419](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1419) | 1440 × 1024 | [PNG](screenshots/07-email-1440.png) | Proposed |
| email | 375 | [516:1491](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1491) | 375 × 1448 | [PNG](screenshots/07-email-375.png) | Proposed |
| sending | 1440 | [516:1563](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1563) | 1440 × 1024 | [PNG](screenshots/07-sending-1440.png) | Proposed |
| sending | 375 | [516:1636](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1636) | 375 × 1488 | [PNG](screenshots/07-sending-375.png) | Proposed |
| saved | 1440 | [516:1709](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1709) | 1440 × 1024 | [PNG](screenshots/07-saved-1440.png) | Proposed |
| saved | 375 | [516:1770](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1770) | 375 × 1144 | [PNG](screenshots/07-saved-375.png) | Proposed |
| empty | 1440 | [516:1831](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1831) | 1440 × 1024 | [PNG](screenshots/07-empty-1440.png) | Proposed |
| empty | 375 | [516:1879](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1879) | 375 × 1344 | [PNG](screenshots/07-empty-375.png) | Proposed |
| loading | 375 | [516:1976](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1976) | 375 × 1432 | [PNG](screenshots/07-loading-375.png) | Proposed |
| error | 1440 | [516:2025](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2025) | 1440 × 1024 | [PNG](screenshots/07-error-1440.png) | Proposed |
| error | 375 | [516:2073](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2073) | 375 × 1368 | [PNG](screenshots/07-error-375.png) | Proposed |
| error-quote | 1440 | [516:2121](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2121) | 1440 × 1024 | [PNG](screenshots/07-error-quote-1440.png) | Proposed |
| error-quote | 375 | [516:2194](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2194) | 375 × 1512 | [PNG](screenshots/07-error-quote-375.png) | Proposed |
| offline | 375 | [516:2328](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2328) | 375 × 1592 | [PNG](screenshots/07-offline-375.png) | Proposed |
| reset | 375 | [516:2435](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2435) | 375 × 1264 | [PNG](screenshots/07-reset-375.png) | Proposed |
| photos | 1440 | [516:2481](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2481) | 1440 × 1024 | [PNG](screenshots/07-photos-1440.png) | Proposed |
| photos | 375 | [516:2528](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2528) | 375 × 1304 | [PNG](screenshots/07-photos-375.png) | Proposed |
| menu | 1440 | [516:2575](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2575) | 1440 × 1024 | [PNG](screenshots/07-menu-1440.png) | Proposed |
| menu | 375 | [516:2720](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2720) | 375 × 1528 | [PNG](screenshots/07-menu-375.png) | Proposed |
| loading | 1440 | [516:1927](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-1927) | 1440 × 1024 | [PNG](screenshots/07-loading-1440.png) | Proposed |
| offline | 1440 | [516:2267](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2267) | 1440 × 1024 | [PNG](screenshots/07-offline-1440.png) | Proposed |
| reset | 1440 | [516:2389](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=516-2389) | 1440 × 1024 | [PNG](screenshots/07-reset-1440.png) | Proposed |

The attract and attract-rotated frames form a four-second, same-width prototype loop. Touching the product or **Explore this setup** opens the active viewer. The attract-still variants have no timer and specify the reduced-motion alternative; runtime must honor the user preference rather than infer it from the prototype. Active states expose 64px touch buttons, rotate/zoom/exploded controls and an approved-fit anchor illustration. **Full screen** represents the existing browser-fullscreen action; Figma navigation is a review simulation and does not invoke the browser Fullscreen API. **Start again** represents clearing the current build and all contact values before returning to attract.

Phone and email quote-entry states use blank name/contact instances from `289:13953`. All 16 visible contact inputs across phone, email, sending and error-quote states are blank. Switching contact methods is illustrated; a runtime submission requires a name and at least one valid contact method, and must validate before sending. Prototype taps simulate state navigation only: no form, phone number, email, request or message is submitted. The sending state disables the submit control. The saved acknowledgement uses the product’s precise pending-delivery wording; it does not claim a quote has reached a shopper, inbox or retailer.

The source viewer sends a quote request with a phone or email through its existing handoff interface, and the downstream retailer handles delivery. This design does not invent a delivered-to-phone success message or a new SMS/email service. The caller must provide the actual approved retailer privacy notice before enabling a real quote submission, as the existing widget does; this proposal neither invents consent wording nor supplies a privacy URL.

The error-quote state retains the source reconnect/try-again instruction. Offline retains a briefly usable approved view but disables quoting: the source cached snapshot expires after five minutes, quotes need a connection and contact details must never be queued/cached locally. The reset/disconnected state uses **Connect this terminal to start again.** Remote reset takes effect on the next successful five-second poll; this design does not imply a disconnected terminal receives it immediately. Empty, loading, viewer-error and photo-fallback states remain distinct. No unavailable/unapproved model is replaced by an invented production model. All example cuboids remain labelled design-review stand-ins.

### Screen 07 wording ledger · Proposed

Exact existing product strings reused: **Explore this setup**; **Touch the product to explore a setup.**; **Full screen**; **Start again**; **Your name**; **Your phone**; **Your email**; **Request a quote**; **Enter a phone number or email for your quote.**; **Loading…**; **Your quote request was saved. Delivery to the retailer is pending.**; **The quote could not be confirmed. Reconnect and try again.**; **Connection lost. This approved view is available briefly; quotes need a connection.**; **Connect this terminal to start again.** Same viewer source path listed above.

**Dealership terminal** comes from the pending RIG-5a requirement rather than an approved register, so it is explicitly **Proposed**. The **Phone** and **Email** switch labels exist in the Custom Nation theme copy; their use as a method switch is Proposed. Review captions follow **Proposed · L29 · 07 · {state} · {width}**. The new/composed fixture and anchor wording listed for screen 06 is reused as Proposed. The shared menu’s inherited product navigation strings are unchanged except for the local existing product identity **Rig**; all instance text is Inter.

## Final validation and push checkpoints

56 Proposed frames: 18 for screen 06, 38 for screen 07. Every state has both 1440 and 375 widths. All 56 snapshots are checked as nonempty PNGs with valid signatures, chunk CRCs and IEND. The export URLs initially returned empty HTTP 202 responses; those placeholders were replaced with rendered inline PNG data before the final screen push. No temporary URL or base64 data is committed. Pixel dimensions can differ from frame dimensions because exports cap their longest edge at 1024–1600px; the register records original Figma dimensions.

Targeted final Figma audit: **zero** text-bound, font, frame-status, width or prototype-target issues; all visible text is **Inter**; no dark panels/bands/themes; minimum visible text contrast **4.73:1**. Initially muted disabled-control labels were 4.28:1 on the beige disabled fill, so all 138 labels were changed to existing Custom Nation ink `#242722` and the 22 affected snapshots were refreshed. Disabled states retain their inactive fill and have no active review link. Existing shared component definitions remain unchanged.

412 same-page review links resolve. Self-navigation actions are omitted; actual rotation, snapping, model entitlement, cache expiry, browser fullscreen and quote delivery remain runtime acceptance items, not capabilities implemented by these drawings. Kiosk desktop phone, mobile email, desktop attract and refreshed mobile loading compositions were visually inspected; all other states have per-frame screenshots and structural validation. No founder acceptance is claimed.

- Screen 06 checkpoint: `dd49dcf8`, pushed before kiosk construction; this final checkpoint also corrects its initially empty PNG exports.
- Screen 07 checkpoint: committed and pushed after all 38 kiosk variants, cross-screen links, final contrast correction and PNG verification.

[Screen 07 node manifest](07-nodes.json), [final audit](validation.json), and [contrast-correction IDs](contrast-fix.json) complement the screen 06 manifest. Exact per-frame model IDs in both manifests supersede the cumulative model list returned during initial construction. Every created node belongs to new page `514:3091`; only these new nodes received local prototype/style changes.

Only `docs/figma/rig-3d/` changes in Git. No production code, catalogue, real product model, contact, message, quote, credential, live setting, deployment or main push changed. Existing `docs/figma/RIG-3D-FRAMES.md` still correctly waits for founder approval. Validation commands: PNG signature/CRC/IEND verifier; register state/width/screenshot checks; `git diff --check`; `git diff --name-only origin/main...HEAD`; branch push and remote-head verification. Runtime tests are not applicable to this design-only deliverable.

## Implementation (codex/rig-3d, PR #672)

The founder approved frames 06–07 in the implementation instruction for `codex/rig-3d`. The complete original design register, IDs and exports are preserved on [codex/figma-rig-3d at 3e6306a4](https://github.com/Tervory-AI/tervory-tank/blob/3e6306a46c77ce608be63d7ca1f9ae86df0fba3a/docs/figma/rig-3d/REGISTER.md), PR #671. Its earlier Proposed annotations record the design's status when authored; the founder's approval supersedes them. No Figma node was changed by this implementation.

| Approved state | Desktop / mobile node IDs | Offline browser evidence |
| --- | --- | --- |
| 06 ready / approved model viewer | 514:4045 / 514:4101 | [1440](../../rig/3d-implementation/screenshots/06-ready-1440.png), [375](../../rig/3d-implementation/screenshots/06-ready-375.png) |
| 07 phone | 516:1275 / 516:1347 | [1440](../../rig/3d-implementation/screenshots/07-phone-1440.png), [375](../../rig/3d-implementation/screenshots/07-phone-375.png) |
| 07 email | 516:1419 / 516:1491 | [1440](../../rig/3d-implementation/screenshots/07-email-1440.png), [375](../../rig/3d-implementation/screenshots/07-email-375.png) |
| 07 quote failure | 516:2121 / 516:2194 | [1440](../../rig/3d-implementation/screenshots/07-error-quote-1440.png), [375](../../rig/3d-implementation/screenshots/07-error-quote-375.png) |
| 07 saved receipt | 516:1709 / 516:1770 | [1440](../../rig/3d-implementation/screenshots/07-saved-1440.png), [375](../../rig/3d-implementation/screenshots/07-saved-375.png) |

[Implementation and verification](../../rig/3d-implementation/README.md), [comparison measurements](../../rig/3d-implementation/comparison.json). Export comparisons omit the design annotation, stand-in illustration/caption and dynamic catalogue values. The original review shapes and caption never ship to the live page. Models come exclusively from the authenticated approved-assembly/asset routes behind `rig_3d`.

New words: none beyond approved register/product wording and store/API supplied content. Light Custom Nation styling, navy main buttons and Inter are retained. Header navigation delegates the existing shared menu to the embed host using `rig-menu`; no CRM navigation routes are copied into a public retailer widget. GPU generation paths/configuration remain off and unchanged.
