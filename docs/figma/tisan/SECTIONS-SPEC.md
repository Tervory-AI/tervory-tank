# Tisan sections — SECTIONS-SPEC

> Craft revision, founder brief 1 November 17:33. The short specimens were refined in place after studying the approved homepage desktop `59:164` and mobile `63:197` in `bOSFzo7qMhHjJ6T5brXG1Y`. The homepage supplied craft references only; client variables, brace slots, content counts and existing frame IDs remain. Maximum-length frames are untouched.

Status: founder approval pending. This is a client-website design proposal, not Tervory UI and not authorization to implement unapproved frames.

**Maximum-length frames are on hold (founder, 1 November, 17:20 PT).** Keep every existing “max” master and review frame unchanged. Claude is tightening the section limits in the shared contract; wait for the new maximums before redrawing those frames. The limits and max specimens described below record the earlier contract and are not the new maximums or approval to implement them.

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

Calculated sRGB contrast: ink/paper 17.40:1; A accent/paper 6.70:1; B accent/paper 11.78:1. CTA headings use paper on accent in A and ink on accent in B. CTA buttons use paper fill/ink text in A and ink fill/paper text in B. Standard focus uses accent against paper; CTA focus uses paper against accent. These pairs exceed 4.5:1 text and 3:1 control/focus contrast. Fonts are variable-bound to the two source families.

## Breakpoints, geometry and wrapping — revised short specimens

The reference homepage uses 100px/98% desktop hero type, 56px/106% section headings, 20px-radius quiet cards, generous split-section spacing and 50px/100% mobile hero type. Its native component transitions include 300ms ease-out Smart Animate and longer 450ms hover examples. These principles are adapted to Literata and Atkinson Hyperlegible, without importing its palette, fonts, images or words.

| Rule | 390 / below 768 | 768 / 768–1023 | 1440 / 1024 and above |
| --- | --- | --- | --- |
| Side padding | 24px | 32px | centered 1200px content; 120px at 1440 |
| Section vertical padding | 80px | 104px | 144px |
| Section gap | 32px | 32px | 48px |
| Hero/image-text column gap | 32px | 32px | 80px |
| Hero heading | 46px / 108% | 60px / 108% | 88px / 108% |
| Section heading | 36px / 114% | 44px / 114% | 56px / 114% |
| Closing CTA heading | 44px / 108% | 60px / 108% | 88px / 108% |
| Feature/product columns | 1 | 2 | 3 |
| Gallery/steps columns | 1 | 2 | 4 |
| Hero/image-text order | image then text | two columns | two columns |

Headings use Literata Regular with -2.5% tracking; card titles use Literata Medium 24px/130% with -1% tracking. Body is Atkinson Hyperlegible Regular 18px/155%; desktop hero lead is 22px/155%. FAQ questions use body Bold 18px mobile and 20px tablet/desktop, line-height 140%. Controls retain 16px/24px type. Existing font-family variable bindings remain attached, including on Medium card titles.

Cards use 24px radius and padding, 16px internal gap and a quiet ink surface at 3.5% node opacity over paper. Image crops use 20px radii: hero 4:5 at 768/1440 and 4:3 at 390; image-text 5:4; products 4:5; gallery 3:4. Images remain neutral editable crop compositions labelled with the original src/alt brace slots. The tonal field, off-center cropped circle and angled cropped plane indicate composition only; they are not client assets or runtime illustrations. Replace with founder-supplied media using cover cropping and retain the generous crop area. No raster assets from the homepage were imported.

Steps and FAQ use restrained 1px separators at 18% ink/line opacity instead of heavy boxes. These separators and tonal fills are decorative; full-contrast text, form borders and focus outlines provide the accessible information. Buttons have 8px radii, 12px vertical and 20px horizontal padding; desktop/tablet hero action width is 220px and mobile fills its text column. Closing CTA is centered with a 240px action. No resting product-card stroke is present.

Header vertical padding is 20px, with a quiet boundary rule. Desktop closed header is a single horizontal masthead/nav row; existing root ID and the 1440px width remain. Open header keeps its skip-link and expanded nav state. Footer has 64px vertical padding, a boundary rule, and desktop text/links side by side. Mobile footer stacks. Existing contact form geometry and wording remain unchanged; its surrounding heading, body and section spacing follow the revised scale.

Containers hug content height. No text clamp, ellipsis or text cropping. Links/buttons wrap and grow; targets remain at least 48px high. At arbitrary widths preserve max-width and column counts without horizontal page overflow. Both image-text variants stack image first at 390. The original maximum-length geometry remains historical and must not inherit these revisions before new limits are approved.

## Content slots and limits

Every visible content placeholder is the exact manifest slot path in braces, e.g. `{heading}`, `{items[0].title}`. Short specimens use one whole token. Maximum specimens repeat whole tokens with spaces to exactly 200 characters, or 2000 for body/answer/footer-text slots; any remaining characters are trailing spaces, never invented words. Indexes use the actual item position. URL/src limits are metadata, not visible URL strings.

Site slots: `{logo.alt}`, `{nav[i].label}`, `{footer.text}`, `{footer.links[i].label}`, `{ui.menu_open}`, `{ui.menu_close}`, `{ui.skip_link}`. Logo source box: `{logo.src}`. Nav and footer labels, logo alt and UI labels max 200; footer text max 2000.

Hero: `{heading}`, `{body}`, `{image.alt}`, `{cta.label}`; image box `{image.src}`. Feature-grid and steps: `{heading}`, `{items[i].title}`, `{items[i].body}`. Product-grid: `{heading}`, `{items[i].name}`, `{items[i].body}`, `{items[i].image.alt}`; image box `{items[i].image.src}`. Image-text: `{heading}`, `{body}`, `{image.alt}`; image box `{image.src}`. FAQ: `{heading}`, `{items[i].question}`, `{items[i].answer}`. CTA band: `{heading}`, `{cta.label}`. Contact: `{heading}`, `{body}`, followed by the existing form labels. Gallery: `{heading}`, `{images[i].alt}`; image box `{images[i].src}`.

All headings/titles/names/questions/CTA labels/alt slots max 200. Body/answer slots max 2000. Media src max 1000; link href max 500 and remain destination metadata. Page titles are document-title metadata under the contract; no new visible title section is invented. Optional fields are shown when present; no missing-content or error wording is added.

Long specimens use maximum counts: nav 8; footer links 12; features 12; products 24; steps 8; FAQ 30; gallery 24. Short specimens show one item except steps, which shows its required minimum of two. Empty/omitted optional arrays do not acquire made-up empty states.

## States and keyboard behavior

Below 1024, menu closed hides navigation; menu open displays the same nav slots inline and pushes content down. The button label switches between the existing manifest UI slots. Enter/Space toggles; Escape closes and returns focus to the opening button. Inline navigation is not a modal and does not trap focus. Skip-link is hidden until focus and moves focus to main content. Desktop navigation remains expanded.

FAQ closed hides answers; FAQ open shows answers, including all maximum-length answers in the stress specimen. Use native details/summary disclosure behavior and keyboard interaction. Open/closed frames are state references, not a wired Figma prototype.

Resting short specimens no longer show persistent selection/focus outlines. Dedicated interaction boards show Default, Hover and Focus in A/B. Product board `219:5750` has the three card widths; product state component set `219:5746` has nine variants. Control board `222:5815` shows the existing CTA slot, nav slot and empty existing input, without added UI words. Sets: button `222:5826`, link `222:5865`, existing input `222:5901`.

Product hover deepens the tonal surface from 3.5% to 7.5% and subtly changes the crop-plane angle; it never adds a full-card accent border. Button hover uses ink fill with paper text; link hover underlines. Inputs retain the existing border and geometry on hover. Focus alone adds a 2px accent outline with 2px outside offset, matched to the control/card radius and without layout shift. On accent-backed CTA sections, use the existing contrasting paper/ink focus treatment. Links/cards use their existing href slot; no uncontracted button or label is added.

Native ON_HOVER → CHANGE_TO reactions are stored for the three product Default variants and the button/link Default variants, using SMART_ANIMATE, EASE_OUT, 0.3 seconds. Focus is an explicit visual reference, not a simulated browser keyboard test. Menu/FAQ state specimens remain static state references. Apply the same hover/focus language to nav, footer, menu, summary and CTA controls. In implementation, suppress decorative motion with prefers-reduced-motion, preserve immediate focus, and never animate layout or delay activation. Prototype reaction data and resting-state screenshots were checked; animated playback and founder browser approval are not claimed.

## Existing contact form — unchanged

Preserve source field order and words: Name, Email, Message, Send. Required name input (type text, autocomplete name), required email input (type email, autocomplete email), required five-row textarea, POST /api/contact. Keep max-width 448px, 12px form gaps, 48px minimum controls, square 1px border-line fields, source paper fills and accent submit button. Send stays left aligned with 16px horizontal padding; its visible focus outline is outside flow. The five-row textarea is 138px including source padding/border at 16px/24px body type. No placeholder, success/error copy, new input, consent field or submission behavior is proposed.

## Evidence and implementation boundary

This pass changes the short masters, their linked A/B review instances, and SPEC in place; it adds neutral crop layers and separate interaction reference components. Existing section/review frame IDs and the original brace-slot text are retained. The 42 short masters retain widths 390, 768 and 1440 (14 of each). A descendant bounds check returned zero horizontal overflows; minimum measured interactive height is 48px. Representative heading, Medium card title and body nodes retain their font-family variable bindings.

Before and after fingerprints use deterministic FNV-1a over serialized node IDs, names, geometry, fills/strokes, text/font metrics, visibility, opacity, auto-layout properties and variable bindings. All 68 protected maximum roots (42 section masters, 14 review rows and 12 array-item masters, including resolved descendants) match `973f44b6`. Original brace-slot IDs/text match `c7827ea0`. New state-example slots are excluded from that original-slot comparison. No shared variable values or old text-style definitions were modified. The old `hero-max-390.png` remains unchanged.

Designer review captures from Figma, visually checked after the final relevant fixes:

| File | Rendered size | Frame |
| --- | --- | --- |
| `sections-overview.png` | 5452 × 9556 | `202:5473` |
| `product-interactions.png` | 2800 × 1867 | `219:5750` |
| `control-interactions.png` | 2072 × 432 | `222:5815` |

These are designer Figma screenshots, not founder browser screenshots or live website data. One intermediate individual product screenshot request timed out; the full overview and dedicated interaction captures succeeded. No runtime tests or model/image-generation calls were used. This is a design-only change; the template, manifest, contract, tokens and contact source remain unchanged.

Commands executed from `/workspace/codex-tisan-sections-design`, with results:

```sh
git status --short --branch
# clean, codex/tisan-sections-design tracks origin/codex/tisan-sections-design
git diff --check
# exit 0, no whitespace errors
git diff --exit-code origin/tisan/sections-contract -- agents/tisan/templates/next-site/sections/manifest.json agents/tisan/templates/next-site/sections/CONTRACT.md agents/tisan/templates/next-site/app/tokens.css agents/tisan/templates/next-site/app/contact/page.tsx
# exit 0, source files unchanged
cp /home/ammosync/.codex/tisan-sections-design-evidence/product-interactions.png docs/figma/tisan/product-interactions.png
git add docs/figma/tisan/product-interactions.png && git commit -m 'docs(figma): capture Tisan product hover and focus craft' && git push origin codex/tisan-sections-design
# exit 0, commit 1428f827 pushed
cp /home/ammosync/.codex/tisan-sections-design-evidence/sections-craft-final.png docs/figma/tisan/sections-overview.png && git add docs/figma/tisan/sections-overview.png && git commit -m 'docs(figma): refresh short Tisan section craft specimens' && git push origin codex/tisan-sections-design
# exit 0, commit cc87af32 pushed
cp /home/ammosync/.codex/tisan-sections-design-evidence/control-interactions.png docs/figma/tisan/control-interactions.png && git add docs/figma/tisan/control-interactions.png && git commit -m 'docs(figma): capture separate control interaction states' && git push origin codex/tisan-sections-design
# exit 0, commit 6b347e79 pushed
```

Figma create_session/use_figma/get_screenshot supplied the reference measurements, in-place mutations, IDs, binding/geometry audits, stored reactions and captures. Screenshot URLs were downloaded with `curl -f -L -o <local capture> <tool-returned URL>` and viewed locally; transient URLs are not retained in this shared spec. The local Markdown was updated with Python 3 and synchronized into the existing SPEC frame text, preserving its IDs.

Figma items pending: founder review and explicit approval of the refined short frames; tightened limits and subsequent maximum-length redesign. Website implementation and founder browser screenshots follow approved frames. Claude opens the PR; founder merges. Nothing in this document claims founder acceptance or authorizes the sections thread to implement unapproved frames.
