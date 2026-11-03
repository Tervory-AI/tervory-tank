# Homepage Figma register

Source: [homepage Figma file](https://www.figma.com/design/bOSFzo7qMhHjJ6T5brXG1Y). Inventory read 3 Nov 2026. Approval/build source: [HOMEPAGE-BUILD-REVIEW.md](../HOMEPAGE-BUILD-REVIEW.md), plus the founder’s Wave 4 ruling that his own public website frames count as approved.

Scope: only the current homepage and public product pages. The founder explicitly excludes Workspace campaign screens, design standards/guides, toggle experiments and older homepage versions. Those exclusions say **not part of tervory.com**, not “not approved”. No design was edited in Figma.

## Public website pages

| Page | Desktop | Mobile | Status | Implementation |
| --- | --- | --- | --- | --- |
| Homepage v6 | 59:164 | 63:197 | already on site | `site/app/page.tsx`, `home-interactions.tsx`, `homepage.css` |
| Rig | 56:127 | 56:798 | built | `site/app/rig/page.tsx`, `rig-product-demo.tsx`, `rig.css`; `/rig` |

The complete inventory contains **30 top-level frames on 5 Figma pages** (73 top-level nodes including components/text). The homepage already contains every current section: navigation, hero, Engine, live arbitrage tracker, manifesto, Tisan, Rig, Trigger, squad, receipt, close and footer.

## Every top-level frame

Current homepage section comparison (all already on site):

| Section | Desktop source | Mobile source | Site selector |
| --- | --- | --- | --- |
| Navigation | 59:165 | 63:198 | `.home-nav` |
| Hero | 67:229 | 69:446 | `.home-hero` |
| Engine | 67:318 | 69:522 | `.engine-section` |
| Live arbitrage tracker | 111:2591 | 111:2622 | `.tracker-section` |
| Founder manifesto | 111:5053 | 111:5068 | `.manifesto-section` |
| Flagship Tisan/Rig | 67:610 | 69:602 | `.flagship-section` |
| Trigger | 112:14392 | 112:14420 | `.trigger-section` |
| Squad | 113:3541 | 113:3671 | `.squad-section` |
| Receipt | 68:514 | 69:912 | `.receipt-section` |
| Close and footer | 62:237 | 63:522 | `.home-close`, `.home-footer` |

This table includes every direct child of type FRAME on every Figma page, including guides. Component sets, components, instances and text are listed in the following inventory so their exclusion is explicit.

| Figma page | Frame ID | Frame name | Status |
| --- | --- | --- | --- |
| Buttons — standard (13:4) | 14:2 | Column labels | not part of tervory.com |
| Buttons — standard (13:4) | 14:27 | Buttons — standard · guide | not part of tervory.com |
| Buttons — standard (13:4) | 15:12 | Audit — current buttons in workspace/app | not part of tervory.com |
| Sidebar — standard (16:12) | 17:16 | Tervory mark · on navy | not part of tervory.com |
| Sidebar — standard (16:12) | 17:36 | Org switcher · on navy | not part of tervory.com |
| Sidebar — standard (16:12) | 18:29 | Sidebar — standard · guide | not part of tervory.com |
| Sidebar — standard (16:12) | 18:104 | Tiger · Overview — sidebar standard applied | not part of tervory.com |
| Campaign flow — generic (issue #437) (0:1) | 19:230 | 1 · Choose dataset (org switcher open) | not part of tervory.com |
| Campaign flow — generic (issue #437) (0:1) | 19:346 | 2 · Split by — any column (ATF sample) | not part of tervory.com |
| Campaign flow — generic (issue #437) (0:1) | 20:123 | 3 · Filters from columns + Start campaign (ATF sample) | not part of tervory.com |
| Campaign flow — generic (issue #437) (0:1) | 20:262 | 4 · Same flow, non-geographic dataset (Product catalogue sample) | not part of tervory.com |
| Campaign flow — generic (issue #437) (0:1) | 20:418 | 5 · Confirm (ATF sample) | not part of tervory.com |
| Campaign flow — generic (issue #437) (0:1) | 21:273 | 6 · Running — progress per group (Product catalogue sample) | not part of tervory.com |
| Campaign flow — generic (issue #437) (0:1) | 21:383 | 7 · Results (ATF sample — real DC run 919381d5) | not part of tervory.com |
| Campaign flow — generic (issue #437) (0:1) | 21:494 | 8 · Error — inline and actionable | not part of tervory.com |
| Campaign flow — generic (issue #437) (0:1) | 21:620 | 9 · Empty — no dataset yet | not part of tervory.com |
| Campaign flow — generic (issue #437) (0:1) | 21:703 | Notes · backend work needed for the generic split | not part of tervory.com |
| Homepage — v1 (44:12) | 52:74 | Homepage — v2 desktop | not part of tervory.com |
| Homepage — v1 (44:12) | 56:115 | Homepage — v3 desktop · title | not part of tervory.com |
| Homepage — v1 (44:12) | 56:119 | Homepage — v3 desktop | not part of tervory.com |
| Homepage — v1 (44:12) | 59:164 | Homepage — v6 desktop | already on site |
| Homepage — v1 (44:12) | 63:197 | Homepage — v6 mobile | already on site |
| Homepage — v1 (44:12) | 66:229 | Logos — product (vectorized, swap) | not part of tervory.com |
| Homepage — v1 (44:12) | 159:2357 | Toggle test | not part of tervory.com |
| Homepage — v1 (44:12) | 181:3460 | EXP A — demo clone | not part of tervory.com |
| Homepage — v1 (44:12) | 181:3907 | EXP B — stripped clone | not part of tervory.com |
| Homepage — v1 (44:12) | 181:3916 | Toggle Off | not part of tervory.com |
| Homepage — v1 (44:12) | 181:3917 | Toggle On | not part of tervory.com |
| Rig — v1 (56:12) | 56:127 | Rig — desktop | built |
| Rig — v1 (56:12) | 56:798 | Rig — mobile | built |

## Other top-level nodes

| Figma page | ID | Type | Name | Disposition |
| --- | --- | --- | --- | --- |
| Buttons — standard (13:4) | 13:173 | COMPONENT_SET | Button | not part of tervory.com (reusable source/guide, not a public page) |
| Buttons — standard (13:4) | 14:19 | TEXT | primary · sm | not part of tervory.com (reusable source/guide, not a public page) |
| Buttons — standard (13:4) | 14:20 | TEXT | primary · md | not part of tervory.com (reusable source/guide, not a public page) |
| Buttons — standard (13:4) | 14:21 | TEXT | secondary · sm | not part of tervory.com (reusable source/guide, not a public page) |
| Buttons — standard (13:4) | 14:22 | TEXT | secondary · md | not part of tervory.com (reusable source/guide, not a public page) |
| Buttons — standard (13:4) | 14:23 | TEXT | ghost · sm | not part of tervory.com (reusable source/guide, not a public page) |
| Buttons — standard (13:4) | 14:24 | TEXT | ghost · md | not part of tervory.com (reusable source/guide, not a public page) |
| Buttons — standard (13:4) | 14:25 | TEXT | danger · sm | not part of tervory.com (reusable source/guide, not a public page) |
| Buttons — standard (13:4) | 14:26 | TEXT | danger · md | not part of tervory.com (reusable source/guide, not a public page) |
| Buttons — standard (13:4) | 119:916 | COMPONENT_SET | Form/Early access — desktop | not part of tervory.com (reusable source/guide, not a public page) |
| Buttons — standard (13:4) | 119:941 | COMPONENT_SET | Form/Early access — mobile | not part of tervory.com (reusable source/guide, not a public page) |
| Sidebar — standard (16:12) | 17:14 | COMPONENT_SET | Product logo | not part of tervory.com (reusable source/guide, not a public page) |
| Sidebar — standard (16:12) | 17:30 | COMPONENT_SET | Sidebar / Tab | not part of tervory.com (reusable source/guide, not a public page) |
| Sidebar — standard (16:12) | 17:37 | COMPONENT | Sidebar | not part of tervory.com (reusable source/guide, not a public page) |
| Sidebar — standard (16:12) | 18:57 | TEXT | Applied · Base | not part of tervory.com (reusable source/guide, not a public page) |
| Sidebar — standard (16:12) | 18:58 | INSTANCE | Sidebar | not part of tervory.com (reusable source/guide, not a public page) |
| Sidebar — standard (16:12) | 18:103 | TEXT | Applied · Tiger (same component, swapped) | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 44:13 | COMPONENT | Brand/Tervory lockup — on light | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 44:29 | COMPONENT | Brand/Tervory lockup — on ink | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 44:45 | COMPONENT | Site/Nav — desktop | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 44:73 | COMPONENT | Site/Nav — mobile | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 44:92 | COMPONENT | Site/Footer — desktop | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 44:141 | COMPONENT | Site/Footer — mobile | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 59:163 | TEXT | Homepage — v4 desktop · title | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 63:196 | TEXT | Homepage — v4 mobile · title | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 77:2611 | COMPONENT_SET | Squad/Specialist — desktop | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 77:3158 | COMPONENT_SET | Squad/Specialist — mobile | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 89:7477 | COMPONENT_SET | Tank/Router — desktop | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 90:2783 | COMPONENT_SET | Tank/Router — mobile | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 111:12 | COMPONENT_SET | Tag/Status | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 114:3906 | COMPONENT_SET | Receipt/Example (desktop) | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 114:3907 | COMPONENT_SET | Receipt/Example (mobile) | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 116:2381 | COMPONENT_SET | Rig/Showcase — mobile | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 117:3547 | COMPONENT_SET | Rig/Showcase — desktop | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 125:2430 | COMPONENT_SET | Rig v6/Optional switch | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 127:2613 | COMPONENT_SET | Rig v6/Demo — desktop | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 127:2819 | COMPONENT_SET | Rig v6/Demo — mobile | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 159:2284 | COMPONENT_SET | Switch/Optional v2 | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 163:2480 | COMPONENT_SET | Switch/Optional v3 | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 181:3069 | COMPONENT_SET | EXP A/Rig demo clone | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 181:3500 | COMPONENT_SET | EXP B/Demo clone stripped to switch | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 208:3347 | COMPONENT_SET | Tank/Five points (desktop) | not part of tervory.com (reusable source/guide, not a public page) |
| Homepage — v1 (44:12) | 208:4443 | COMPONENT_SET | Tank/Five points (mobile) | not part of tervory.com (reusable source/guide, not a public page) |

## Explicitly unapproved frames

No current public homepage/product frame is marked proposed, draft or “not approved”. The older homepage v3 title frame **56:115** contains **56:118 “DRAFT COPY”**; homepage v3 **56:119** is excluded as an old version and is not built. The v6 Zenas product description uses “drafting” and “draft” as product wording; those words are not approval notices.

## Pages with no approved website frame

No standalone public website frame exists in this file for Tisan, Trigger, Tank, Skala, Base, Zenas, Zenas ZA, Tiger, Market Lab, Radix or Autumbra. Their homepage entries are sections, not separate page designs. The old generic site navigation/footer also names About, Pricing, Contact, Privacy and Terms; there are no corresponding page frames. None of these pages is invented or published. Sign in/Create account belong to the hosted Workspace, not new public pages.

## Browser verification

Rig: build/static export, public-page and isolated signup-store checks, and 3 homepage Python regressions pass. All seven stage selections are checked at 320, 375, 390, 430, 767, 768, 1000, 1199, 1200 and 1440px. The default drawn state passes every integer width from 320 through 1440 (1,121 widths). The check measures visible text ranges, panel/control bounds and page width, checks keyboard operation, and rejects illustration POSTs or JavaScript errors. [375px](../screenshots/homepage-wave4/rig-product-375.png), [1440px](../screenshots/homepage-wave4/rig-product-1440.png). Commands and scope are in the Wave 4 entry of the build review.

