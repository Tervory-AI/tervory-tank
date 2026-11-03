# Tisan sections — SECTIONS-SPEC

## Approval and scope — 3 November 2026

The founder approved the short designs on **3 Nov**. Unchanged specimens say **Approved 3 Nov**. The 3 Nov limit changes, redrawn max masters, absent-slot examples, annotation changes and unused-state labels say **Changed after approval, awaiting founder**. This revision supersedes the 1 Nov hold on max redraws; it does not extend the earlier approval to today's changes.

File: [Tisan sections](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=197-9), page **6 · Tisan sections** (`197:9`). SPEC frame: `205:5479`. Short review: `202:5473`. New optional-slot / realistic-navigation board: `276:5827`.

Work stays on `codex/tisan-sections-design`, PR #591, in `/workspace/codex-tisan-sections-design`. The shared source is `agents/tisan/templates/next-site/sections/manifest.json`; sections, builder and publish all consume that contract. Round 1 changed its specified bounds, boundary tests, CONTRACT.md and design evidence. This re-check changes Figma, this specification and design evidence only; the manifest, CONTRACT.md and content-check implementation/tests remain unchanged from round 1. Website component implementation is separate.

### Re-check after fix round 1 — 3 November

Footer max labels now contain exactly 40 non-padding characters and wrap inside their targets; at 390 and 768 their labels align left with the footer text. Desktop logo-header nav blocks align to the right edge of the 1200px content area while retaining wrapping. Every nav/footer target and slot uses its own array index. All 132 item instances in max feature, product, steps and gallery masters now reference the corresponding max item component and carry **Changed after approval, awaiting founder**.

The existing no-logo 390/768 masters now show the closed menu control with no logo space; separate open masters show left-aligned links. Desktop remains expanded nav only, left-aligned. Skip links are visually hidden at rest in every header. Dedicated keyboard-focus specimens at 390 and 1440 show the skip link and its focus outline. Existing master and review root IDs are retained. These corrections await founder approval; they do not inherit the short designs' **Approved 3 Nov** status.

Polish after the re-check: desktop footer `199:594` now uses a fixed 32px gap between the text box (bottom y=176) and links (top y=208), with link labels flush to the text edge. Its height hugs to 512px. No-logo menu-open/menu-close labels in `276:5621`, `276:5657`, `310:37135` and `310:37170` align left at the content edge, matching the open links; their 240px targets remain. All node IDs are retained and these changes still await founder approval. Visual readback checked linked review instances at both widths and the desktop footer. Updated captures: `nov3-polish-footer-1440.png`, `nov3-polish-menu-closed-390.png`, `nov3-polish-menu-closed-768.png`, `nov3-polish-menu-open-390.png`, `nov3-polish-menu-open-768.png`. They supersede the corresponding round 2 captures below.

## Frame index

All 42 original max section-master root IDs are retained: fourteen families at 390, 768 and 1440. Their 84 A/B max review instances remain linked. The twelve reusable max item masters were also brought to the same limits and type. The following existing review-instance index remains valid; each cell is **short A / short B ; max A / max B**.

| Family / state | 390 | 768 | 1440 |
| --- | --- | --- | --- |
| header-closed | `202:5476 / 202:5477` ; `198:137 / 198:145` | `202:5479 / 202:5480` ; `198:154 / 198:162` | `202:5482 / 202:5483` ; `198:171 / 198:201` |
| header-open | `202:5530 / 202:5531` ; `199:377 / 199:413` | `202:5533 / 202:5534` ; `199:450 / 199:486` | `202:5536 / 202:5537` ; `199:523 / 199:556` |
| footer | `202:5618 / 202:5619` ; `199:767 / 199:806` | `202:5621 / 202:5622` ; `199:846 / 199:885` | `202:5624 / 202:5625` ; `199:925 / 199:964` |
| hero | `202:5658 / 202:5659` ; `199:1142 / 199:1153` | `202:5661 / 202:5662` ; `199:1165 / 199:1176` | `202:5664 / 202:5665` ; `199:1188 / 199:1199` |
| feature-grid | `202:5728 / 202:5729` ; `199:1425 / 199:1475` | `202:5731 / 202:5732` ; `199:1526 / 199:1570` | `202:5734 / 202:5735` ; `199:1615 / 199:1657` |
| product-grid | `202:5768 / 202:5769` ; `199:2305 / 199:2475` | `202:5771 / 202:5772` ; `199:2646 / 199:2804` | `202:5774 / 202:5775` ; `199:2963 / 199:3117` |
| image-text-left | `202:5826 / 202:5827` ; `199:3374 / 199:3382` | `202:5829 / 202:5830` ; `199:3391 / 199:3399` | `202:5832 / 202:5833` ; `199:3408 / 199:3416` |
| image-text-right | `202:5878 / 202:5879` ; `199:3527 / 199:3535` | `202:5881 / 202:5882` ; `199:3544 / 199:3552` | `202:5884 / 202:5885` ; `199:3561 / 199:3569` |
| steps | `202:5930 / 202:5931` ; `200:2923 / 200:2957` | `202:5933 / 202:5934` ; `200:2992 / 200:3022` | `202:5936 / 202:5937` ; `200:3053 / 200:3081` |
| faq-closed | `202:5990 / 202:5991` ; `200:3437 / 200:3529` | `202:5993 / 202:5994` ; `200:3622 / 200:3714` | `202:5996 / 202:5997` ; `200:3807 / 200:3899` |
| faq-open | `202:6024 / 202:6025` ; `200:4418 / 200:4540` | `202:6027 / 202:6028` ; `200:4663 / 200:4785` | `202:6030 / 202:6031` ; `200:4908 / 200:5030` |
| cta-band | `202:6064 / 202:6065` ; `201:4415 / 201:4421` | `202:6067 / 202:6068` ; `201:4428 / 201:4434` | `202:6070 / 202:6071` ; `201:4441 / 201:4447` |
| contact | `202:6104 / 202:6105` ; `201:4616 / 201:4629` | `202:6107 / 202:6108` ; `201:4643 / 201:4656` | `202:6110 / 202:6111` ; `201:4670 / 201:4683` |
| gallery | `202:6192 / 202:6193` ; `201:5126 / 201:5248` | `202:6195 / 202:6196` ; `201:5371 / 201:5481` | `202:6198 / 202:6199` ; `201:5592 / 201:5696` |

The 1440 header-open masters `199:143` and `199:144` and their review instances `199:523` / `199:556` are explicitly **UNUSED — desktop navigation is always expanded**. They remain as labeled reference states and must not be implemented as desktop open-menu variants.

| Added specimen / Changed after approval, awaiting founder | 390 master | 768 master | 1440 master |
| --- | --- | --- | --- |
| Text-only hero | `276:5579` | `276:5593` | `276:5607` |
| Header without logo, closed below 1024 / expanded desktop | `276:5621` | `276:5657` | `276:5693` |
| Eight realistic navigation labels | `276:5724` | `276:5760` | `276:5796` |
| Header without logo, open | `310:37135` | `310:37170` | unused |
| Skip link focused | `310:37328` | — | `310:37340` |

These thirteen additional masters have twenty-six A/B review instances in `276:5827`. No empty image column, logo box or site-name fallback is added when the optional content is absent. The new no-logo open review row is `310:37205` (390 A/B `310:37207` / `310:37237`, 768 A/B `310:37268` / `310:37298`). The skip-link-focused row is `310:37354` (390 A/B `310:37356` / `310:37368`, 1440 A/B `310:37381` / `310:37395`). Existing no-logo review instances now show the closed state below 1024.

## Contract limits

| Slot | Maximum characters |
| --- | ---: |
| `nav[].label`, `footer.links[].label` | 40 |
| `footer.text` | 600 |
| Every section `heading`, including hero and CTA | 80 |
| Section `body` / intro | 600 |
| Item `title`, product `name` | 80 |
| Item `body` | 400 |
| FAQ `answer` | 800 |

Maximum counts: **nav 8; footer links 12; features 12; products 12; steps 8; FAQ 20; gallery 12**. All other schema rules remain: required/optional properties, enums, URL patterns, page/section identity and minimum counts. In particular, FAQ questions, CTA labels, UI labels and alt attributes remain 200; media sources remain 1000 and hrefs 500. Steps still require at least two items. No site-name slot is invented.

Max content uses repeated complete brace-slot tokens, padded only where a token will not fit the exact character count. Array indexes identify the actual item, including media-source annotations. Header navigation uses eight realistic labels of **exactly 40 characters** rather than brace tokens. Footer max masters use the same eight 40-character specimens followed by the first four again, filling all twelve link slots without padding:

- Explore our studio and creative approach
- Discover our services and design process
- Selected projects and recent client work
- Meet the people behind our design studio
- Learn how we work with your organisation
- Read client stories and project outcomes
- Browse design resources and useful tools
- Contact our team to discuss your project

The short navigation labels shown on board `276:5827`, including its no-logo examples, are:

- Home
- About our studio
- Design services
- Selected projects
- Our process
- Client stories
- Resources
- Contact the team

Both label sets are **design specimens, not runtime copy**. Every live text slot still requires accepted Trigger copy. Supplied media remains the only source of image URLs. The existing content checker reads `manifest.json` directly, so the new limits are enforced without a second limit table in executable code. Tests accept each revised limit and reject one character or item over; existing constraints stay covered.

## Type, spacing and reflow

Max masters reuse the approved short layouts and client-token bindings. Their fixed widths are 390, 768 and 1440; heights hug the actual content. No text clamp, ellipsis, text crop, fixed card-height cap or horizontal page overflow is used. A maximum-content page can be tall and scroll normally.

| Max-master rule | 390 | 768 | 1440 |
| --- | --- | --- | --- |
| Hero heading | 46px / 108% | 60px / 108% | 88px / 108% |
| Section / CTA heading | 36px / 114% | 44px / 114% | 56px / 114% |
| Body / intro / item body / answer | 18px / 155% | 18px / 155% | 18px / 155% |
| Card title | Literata Medium 24px / 130% | same | same |
| Side padding | 24px | 32px | 120px; centered 1200px content |
| Section vertical padding | 80px | 104px | 144px |
| Main gap | 32px | 32px | 48px |
| Split-section column gap | 32px | 32px | 80px |
| Feature / product columns | 1 | 2 | 3 |
| Gallery / steps columns | 1 | 2 | 4 |

Header vertical padding remains 20px; footer vertical padding remains 64px. Controls keep 16px/24px type and at least 48px targets. The existing contact form keeps its own approved geometry and labels. Approved short exceptions, including its larger desktop hero lead and closing-CTA treatment, have not been silently rescaled.

Heading family remains Literata, with -2.5% tracking on large headings; card titles use Medium and -1% tracking. Body remains Atkinson Hyperlegible. The local **Tisan sections / Client tokens** collection (`VariableCollectionId:197:11`) retains A · Light (`197:1`) and B · Inverse (`197:2`). All cloned text retains its existing font-family/fill bindings; Medium card titles were checked with their family binding intact.

A uses ink #1a1a1a, paper #ffffff, accent #1d4ed8 and ink-colored line. B uses ink #ffffff, paper #1a1a1a, accent/line #d4d4d8. No Tervory logo, palette or new raster client asset is introduced. Cards keep their approved 24px padding/radius, 16px internal gap and quiet tonal surface. Image compositions keep their approved crops and rounded corners. Geometry inside a media crop is decorative clipping; text never clips.

## Navigation and absent slots

**One wrapping rule:** whenever navigation is visible, its container wraps links inside the available content width. Below 1024 the existing closed/open menu states remain. At 1024 and above the navigation is always expanded, within the centered 1200px content area. In the 1440 header the existing 160px logo area and 48px gap leave 992px for wrapping navigation. Both `198:14` and many-links master `276:5796` right-align their wrapped nav targets within that 992px area, reaching the right content edge. The eight maximum-length labels wrap to rows instead of extending beyond the frame. The realistic-label board demonstrates the responsive rule at all three widths.

**No logo:** remove the logo area entirely, with no reserved logo space or site-name fallback. Below 1024, the closed state shows the existing menu-open control; the open state shows the existing menu-close control and left-aligned links wrapping within 342px at 390 and 704px at 768. At 1440, show expanded nav only, aligned to the leading edge of the 1200px content area, including left-aligned labels. There is no desktop menu button.

**No hero image:** remove the complete media column. Heading and body fill the available 342, 704 or 1200px content width. The action retains its approved target geometry. No blank image container, duplicate caption or empty state remains.

## Images, states and accessibility

Alt values are accessibility metadata. Their Figma text nodes are named **ANNOTATION ONLY · alt attribute · never rendered as page text** and are hidden from the visible specimens. They are not captions. Source brace annotations inside the neutral media boxes are review metadata, not visible runtime page copy. Image arrays use their real indexes.

There are **no focus outlines at rest** on the redrawn max masters. The skip link is visually hidden until it receives keyboard focus in every header, including the open states `199:140` / `199:142`. It remains keyboard reachable; Figma visibility represents its resting appearance, not removal from the runtime accessibility tree. Separate **skip link focused** specimens at 390 and 1440 show `{ui.skip_link}` with a 2px token-bound focus outline; activation moves focus to the main content. Separate approved hover/focus/pressed control and product examples remain on the page. Keyboard focus keeps its approved contrast and outline in those dedicated states. Existing menu, FAQ disclosure and contact interactions are preserved; no extra field, error, success, loading or empty-state copy is added.

Contact stays Name, Email, Message, Send, with required name/email/message fields, existing autocomplete, five-row textarea and POST `/api/contact`. No new submission behavior is introduced.

## Evidence and checks

Round 1 structural readback checked 42 max masters and nine additional masters, including 662 visible text nodes; `nov3-audit.json` records that check. Round 2 readback checked **42 max masters and thirteen additional masters**, including **669 visible text nodes**, and found **zero text-containment, truncation, target-index, footer-length, footer-alignment, nav-edge, item-reference or resting-skip-link errors**. All 132 max item instances reference max masters. The preceding round 1 type/count check passed heading scales, body-18 values, Medium card titles and requested item counts; round 2 preserves those styles and counts. Root master IDs and both client token modes remain. `nov3-r2-audit.json` records the re-check.

Round 1 Figma captures below record the first fix round. Header and optional-state captures are superseded by the round 2 evidence; they are retained as history. These are design evidence, not founder live-browser acceptance:

| Capture | Figma review node | File |
| --- | --- | --- |
| Header max, 1440 | `198:171` | `nov3-header-max-1440.png` |
| Hero max, 390 | `199:1142` | `nov3-hero-max-390.png` |
| Hero max, 768 | `199:1165` | `nov3-hero-max-768.png` |
| Hero max, 1440 | `199:1188` | `nov3-hero-max-1440.png` |
| CTA max, 390 | `201:4415` | `nov3-cta-max-390.png` |
| Product max, 1440 | `199:2963` | `nov3-product-max-1440.png` |
| FAQ max, 390 | `200:4418` | `nov3-faq-max-390.png` |
| Optional slots / nav, both modes | `276:5827` | `nov3-optional-and-nav.png` |

Round 2 captures:

| Capture | Figma review node | File |
| --- | --- | --- |
| Footer max, 390 | `199:767` | `nov3-r2-footer-390.png` |
| Footer max, 768 | `199:846` | `nov3-r2-footer-768.png` |
| Footer max, 1440 | `199:925` | `nov3-r2-footer-1440.png` |
| Right-aligned max nav, 1440 | `198:171` | `nov3-r2-nav-1440.png` |
| Optional slots, no-logo closed/open, many links and focused skip links, A/B | `276:5827` | `nov3-r2-optional-states.png` |
| Skip link focused, 390 | `310:37356` | `nov3-r2-skip-focus-390.png` |
| Skip link focused, 1440 | `310:37381` | `nov3-r2-skip-focus-1440.png` |
| Steps max items, 1440 | `200:3053` | `nov3-r2-steps-1440.png` |

Round 2 used structural readback and visual inspection at all three review widths, including the corrected footer wrapping, desktop nav, no-logo closed/open states and focused/hidden skip-link states. Manifest, CONTRACT.md and content-check files have no round 2 diff. No executable source changed, so the following round 1 checks were not rerun for this design-only re-check.

Executed in round 1 in `agents/tisan/templates/next-site`:

```sh
npm ci --no-audit --no-fund
TMPDIR=/workspace/codex-tisan-sections-design/.git/tisan-test-tmp npm test -- --run tests/content-check.test.ts
TMPDIR=/workspace/codex-tisan-sections-design/.git/tisan-test-tmp npm run lint
TMPDIR=/workspace/codex-tisan-sections-design/.git/tisan-test-tmp npm run build
TMPDIR=/workspace/codex-tisan-sections-design/.git/tisan-test-tmp npm test
```

Results: install exit 0 (654 packages); boundary suite **43 passed**; ESLint/Prettier passed; production content check, build and type check passed; complete suite **82 passed across six files**. Existing module-format warnings remain. An initial boundary-test attempt failed writing to `/tmp` with errno -122; the branch-local TMPDIR resolved that environment failure. CONTRACT.md was formatted after the first lint check reported it. No model/image-generation calls, paid checks, production SQL or live content mutations were used.

Figma create_session/use_figma/get_screenshot supplied measurements, editable node changes, readback and captures. `git diff --check` passed. Runtime changes under `agents/tisan/` deploy the room and regional copies on merge. The founder merges; today's changed designs still await founder approval. Unchanged 3 Nov-approved frames retain that approval.
