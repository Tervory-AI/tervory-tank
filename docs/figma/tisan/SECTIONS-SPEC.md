# Tisan sections

Status: design in progress; founder approval pending. No section is approved for implementation by this document alone.

Figma file: `ZnphBOJU6657tohGLD3IzS`. Target page: `6 · Tisan sections`.
Source: `agents/tisan/templates/next-site/sections/manifest.json` (`tisan.sections/1`), its `CONTRACT.md`, and `app/tokens.css`, on `tisan/sections-contract`.

## Scope

Client websites built by Tisan: header with logo/navigation and mobile closed/open states; footer; hero; feature-grid; product-grid; image-text left/right; steps; FAQ closed/open; CTA band; unchanged existing contact form; gallery. Each has 390, 768 and 1440 width specimens. Every specimen has two token sets side by side, short slots and maximum-length slots.

All content copy is a brace-delimited manifest slot path. Long specimens repeat complete slot tokens, separated by spaces, to exactly the manifest's maximum character count. No sample customer/site copy is proposed. Neutral image boxes carry their image source slot; alt slots are accessibility annotations, not extra page copy.

The contact form retains Name, Email, Message, Send, its field order, two required inputs, required five-row textarea, POST /api/contact, 48px minimum controls, 12px form gaps and 448px maximum width. No status or error message is invented.

## Foundations

Use only the four source palette values through semantic variables: ink, paper, accent, line; font variables heading and body resolve to Literata and Atkinson Hyperlegible. A second inverse specimen remaps existing palette values through the same variable names; it does not propose another client's identity. Component geometry and text hierarchy remain identical across token sets.

## Layout contract

390: 24px side padding, one column, 24px section gaps and 48px vertical padding. 768: 32px side padding, two grid columns, 24px gaps and 64px vertical padding. 1440: 1200px maximum content width, 120px outer gutters, three grid columns (four for gallery), 32px gaps and 80px vertical padding.

At widths below 1024 use the mobile menu. At 768, hero/image-text may use two columns; 390 always stacks the image before text. Image-text side changes order only in two-column layouts. Grid items and long text grow naturally, with no clamp, ellipsis or fixed section height. Button/link labels wrap; interactive targets are at least 48px, exceeding the requested 44px.

Heading sizes are 32/40/48px at the three widths, line-height 1.2. Item headings use 24px/1.3, body 16px/1.5. Keyboard focus uses the source 2px outline with 2px offset, in a token color that passes contrast against the adjacent paper. FAQ uses native disclosure semantics; closed answers are not visible. Menu and disclosure focus return behavior will be specified alongside frame references.

## Pending evidence

Figma page/frame identifiers, exact variable mappings, final state inventory, contrast results, structural validation and design screenshots will be recorded here after canvas construction. Founder browser screenshots and frame approval have not occurred. Claude opens the PR; founder merges.
