# Tisan sections — SECTIONS-SPEC

Status: founder approval pending. This is a client-website design proposal, not Tervory UI and not authorization to implement unapproved frames.

[Open page 6 · Tisan sections](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=197-9). SPEC frame: `205:5479`. Short review board: `202:5473`.

Source branch: `tisan/sections-contract` at `6cf65168a6a16ddf622c3e78ff4468e209f317ae`. Sources: `agents/tisan/templates/next-site/sections/manifest.json`, `sections/CONTRACT.md`, `app/tokens.css` and the existing `app/contact/page.tsx`. The manifest remains unchanged.

## Inventory and frame index

Fourteen state/layout families cover header closed/open, footer, hero, feature-grid, product-grid, image-text left/right, steps, FAQ closed/open, CTA band, contact and gallery. Each has three widths, two lengths and two client token sets: 84 linked masters, 168 review instances, plus 24 reusable array-item masters. Main component sets sit to the right of review content.

Each cell below is `short A / short B` ; `max A / max B`. IDs identify individual review instances in the same Figma file. Short rows live in the compact review board; maximum-length rows sit in the adjacent column. Inspect frames at 100% for typography.

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

## Color and type variables

Collection: `Tisan sections / Client tokens` (`VariableCollectionId:197:11`). Modes: A · Light (`197:1`) and B · Inverse (`197:2`). All section text/fills/strokes bind to these variables, with source-palette primitives in a separate collection. No Tervory logo, Tervory colors, unrelated font or generated image is used.

| Variable / CSS name | A · Light | B · Inverse |
| --- | --- | --- |
| ink / --colour-ink | #1a1a1a | #ffffff |
| paper / --colour-paper | #ffffff | #1a1a1a |
| accent / --colour-accent | #1d4ed8 | #d4d4d8 |
| line / --colour-line | #1a1a1a | #d4d4d8 |
| heading / --font-heading | Literata Regular | Literata Regular |
| body / --font-body | Atkinson Hyperlegible Regular | Atkinson Hyperlegible Regular |

The two specimens remap only values already present in tokens.css. A maps line to source ink so border-line controls meet AA without changing the existing form. B swaps source ink/paper and maps source line to accent/line. The unmodified source default #d4d4d8 border against white is not claimed to meet 3:1; these contrast-ready specimens are deliberate client token sets, not a change to tokens.css.

Calculated sRGB contrast: ink/paper 17.40:1; A accent/paper 6.70:1; B accent/paper 11.78:1. CTA headings use paper on accent. CTA buttons use paper fill/ink text. Standard focus uses accent against paper; CTA focus uses paper against accent. These pairs exceed 4.5:1 text and 3:1 control/focus contrast. Fonts are variable-bound to the two source families.

## Breakpoints, geometry and wrapping

| Rule | 390 specimen / below 768 | 768 specimen / 768–1023 | 1440 specimen / 1024 and above |
| --- | --- | --- | --- |
| Side padding | 24px | 32px | centered 1200px content; 120px at 1440 |
| Section vertical padding | 48px | 64px | 80px |
| Main gap | 24px | 24px | 32px |
| Feature/product columns | 1 | 2 | 3 |
| Gallery/steps columns | 1 | 2 | 4 |
| Hero/image-text | image then text | two equal columns | two equal columns |
| Heading / line-height | 32px / 38.4px | 40px / 48px | 48px / 57.6px |

Item headings: 24px/31.2px. Body and controls: 16px/24px. All content starts at the leading edge. Grid rows align at the top. Cards have 16px padding and gap, 1px line borders and square corners; image annotations sit in neutral paper boxes with line borders. Image boxes use a 4:3 minimum area; logo boxes have a 64px minimum height. Logo/image source and alt annotations are review-only and never become visible page captions.

Header/footer use 24px header vertical padding and 12px nav gaps / 16px footer-link gaps. Short mobile mastheads place logo and menu target side by side; long slots stack the masthead so labels never overlap. Desktop nav wraps without truncation; it remains expanded in both desktop header specimens. The open desktop companion illustrates the focused skip-link state, not a desktop mobile-menu button.

Containers hug content height. No text clamp, ellipsis, crop or forced equal card height. Links/buttons wrap and grow; targets are at least 48px high, exceeding the 44px brief. At arbitrary widths, keep the content max-width and selected column counts, with no horizontal page overflow. On 390, both image-text side variants stack image before text. At two-column widths, left/right changes the image order only.

## Content slots and limits

Every visible content placeholder is the exact manifest slot path in braces, e.g. `{heading}`, `{items[0].title}`. Short specimens use one whole token. Maximum specimens repeat whole tokens with spaces to exactly 200 characters, or 2000 for body/answer/footer-text slots; any remaining characters are trailing spaces, never invented words. Indexes use the actual item position. URL/src limits are metadata, not visible URL strings.

Site slots: `{logo.alt}`, `{nav[i].label}`, `{footer.text}`, `{footer.links[i].label}`, `{ui.menu_open}`, `{ui.menu_close}`, `{ui.skip_link}`. Logo source box: `{logo.src}`. Nav and footer labels, logo alt and UI labels max 200; footer text max 2000.

Hero: `{heading}`, `{body}`, `{image.alt}`, `{cta.label}`; image box `{image.src}`. Feature-grid and steps: `{heading}`, `{items[i].title}`, `{items[i].body}`. Product-grid: `{heading}`, `{items[i].name}`, `{items[i].body}`, `{items[i].image.alt}`; image box `{items[i].image.src}`. Image-text: `{heading}`, `{body}`, `{image.alt}`; image box `{image.src}`. FAQ: `{heading}`, `{items[i].question}`, `{items[i].answer}`. CTA band: `{heading}`, `{cta.label}`. Contact: `{heading}`, `{body}`, followed by the existing form labels. Gallery: `{heading}`, `{images[i].alt}`; image box `{images[i].src}`.

All headings/titles/names/questions/CTA labels/alt slots max 200. Body/answer slots max 2000. Media src max 1000; link href max 500 and remain destination metadata. Page titles are document-title metadata under the contract; no new visible title section is invented. Optional fields are shown when present; no missing-content or error wording is added.

Long specimens use maximum counts: nav 8; footer links 12; features 12; products 24; steps 8; FAQ 30; gallery 24. Short specimens show one item except steps, which shows its required minimum of two. Empty/omitted optional arrays do not acquire made-up empty states.

## States and keyboard behavior

Below 1024, menu closed hides navigation; menu open displays the same nav slots inline and pushes content down. The button label switches between the existing manifest UI slots. Enter/Space toggles; Escape closes and returns focus to the opening button. Inline navigation is not a modal and does not trap focus. Skip-link is hidden until focus and moves focus to main content. Desktop navigation remains expanded.

FAQ closed hides answers; FAQ open shows answers, including all maximum-length answers in the stress specimen. Use native details/summary disclosure behavior and keyboard interaction. Open/closed frames are state references, not a wired Figma prototype.

Focus examples use the source 2px outline, 2px outside offset, square corners, and no layout shift. Outlined controls demonstrate their styles; multiple reference outlines are not simultaneous browser focus. Product cards with href use the whole card as a focusable link; do not add an uncontracted button or label. Heading/body/image-only regions are not interactive.

## Existing contact form — unchanged

Preserve source field order and words: Name, Email, Message, Send. Required name input (type text, autocomplete name), required email input (type email, autocomplete email), required five-row textarea, POST /api/contact. Keep max-width 448px, 12px form gaps, 48px minimum controls, square 1px border-line fields, source paper fills and accent submit button. Send stays left aligned with 16px horizontal padding; its visible focus outline is outside flow. The five-row textarea is 138px including source padding/border at 16px/24px body type. No placeholder, success/error copy, new input, consent field or submission behavior is proposed.

## Evidence and implementation boundary

Figma structural checks returned no issues: 14 component sets / 84 section masters / 168 linked review instances; 24 reusable array-item masters; correct source font families and font bindings; all section solid fills/strokes bound; no nonpositive text bounds or vertical text overflow; minimum target height 48px and minimum target width 151px. Maximum indexed feature/product/step/gallery overrides were read back at indexes 11/23/7/23 with exact 200/2000-character text values. Neutral image placeholders intentionally contain no raster image fills.

Designer review captures: `sections-overview.png` (5452×7462, short composition after alignment fix) and `hero-max-390.png` (390×1925, 200-character heading/CTA and 2000-character body). These are editable Figma designs exported for review, not founder browser screenshots or live website data.

Commands executed from /workspace/codex-tisan-sections-design: `git fetch origin main tisan/sections-contract`; `git checkout -B codex/tisan-sections-design origin/tisan/sections-contract`; `ls agents/tisan/templates/next-site/sections/manifest.json agents/tisan/templates/next-site/sections/CONTRACT.md agents/tisan/templates/next-site/app/tokens.css`; `git diff --check`; `git diff --exit-code origin/tisan/sections-contract -- agents/tisan/templates/next-site/sections/manifest.json agents/tisan/templates/next-site/sections/CONTRACT.md agents/tisan/templates/next-site/app/tokens.css agents/tisan/templates/next-site/app/contact/page.tsx`. Fetch, checkout and file inventory succeeded. Source-integrity and whitespace checks passed (exit 0, no output). The local specification check also passed: all nine manifest section types, all three widths and both nonempty screenshots are present. Figma create_session/use_figma/get_screenshot tools supplied frame, binding, length, geometry and screenshot evidence; no model/image-generation calls or website runtime tests were used for this design-only change.

Only this specification and its two design screenshots are added on codex/tisan-sections-design. Website/template implementation remains unchanged. Claude opens the PR; founder merges. Founder page review and explicit frame approval remain pending; the sections thread may build only after that approval.
