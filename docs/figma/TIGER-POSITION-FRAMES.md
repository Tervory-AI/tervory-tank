# Tiger price position — proposed frames

Status: ready for founder review in Figma; every new word is proposed and awaits founder approval. No application code or live screen is changed.

Target: Figma file `ZnphBOJU6657tohGLD3IzS`, new page `9 · Tiger price position`.

Source: `workspace/app/tiger/view.tsx` (`TigerApp`, `Overview`, `Watch`, `SimpleTable`, `ProductIdentifier`, `PageLink`, `AttemptTime`, `RowStatus`, `Pill`) and its existing `tiger.css`; Tiger Plugins' existing Source links list. Baseline commit `bb3200835b519826b4664418c4ccb5ab900cff73`.

Reuse: existing Tiger desktop `49:3211` and mobile `54:8114`; existing workspace menu `46:21`, mobile bar `53:5990`, Table header `43:389` and Table row `43:405`. Keep existing Jost Light / Inter typography, navy, paper, white and line tokens. No new visual style or implementation.

All illustrative product names, prices, counts and reserved `.example` URLs exist only inside proposed Figma frames. They are not observations from stores and must never seed a live screen.

## Frame map — one line per frame

Page: [9 · Tiger price position](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-9), node `256:9`. Every frame name and visible review annotation says **Proposed, not approved**; the annotation explicitly marks all wording for approval and all illustrative values as Figma only.

| Frame | Node ID | Size | Existing component and source reused |
| --- | --- | --- | --- |
| 01 · Price position · Proposed, not approved | [256:10](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-10) | 1440 × 1592 | `TigerApp` shell and section navigation; `Overview`/`Watch` table and `SimpleTable`; existing Figma Table header `43:389`, default Side menu item `43:409`, active Side menu item `43:421`; `ProductIdentifier`/`PageLink` links, `AttemptTime` metadata, `Pill`/`RowStatus` states; original Tiger artwork `38:136` and Tervory artwork `38:130`. |
| 01 · Price position · Proposed, not approved | [256:170](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-170) | 375 × 2423 | `TigerApp` mobile bar cloned from `53:5990`; `Overview` mobile `.cards`/`.card-top`; existing Figma Table row `43:405` instances for own price, cheapest, rank and difference; `ProductIdentifier`/`PageLink`, `AttemptTime`, `Pill` and `.note-card`. |
| 02 · Matches to review · Proposed, not approved | [256:283](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-283) | 1440 × 1263 | `TigerApp` shell; `Watch`/`SimpleTable` table structure; existing Figma Table header `43:389` and Side menu item `43:409`/`43:421` instances; `ProductIdentifier`/`PageLink` evidence links; existing `button.line.small`, `button.text`, `.row-actions` and `.note-card`; original brand artwork. |
| 02 · Matches to review · Proposed, not approved | [256:406](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-406) | 375 × 1690 | Existing mobile bar `53:5990`; `Overview` mobile `.cards li` reflow; `ProductIdentifier`/`PageLink` evidence links; existing `button.line.small`, `button.text`, `.row-actions` and `.note-card`. |
| 03 · Competitor sites · Proposed, not approved | [256:471](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-471) | 1440 × 1379 | `TigerApp` shell; Tiger Plugins Source links list and `Watch`/`SimpleTable` columns; existing Figma Table header `43:389` and Side menu item `43:409`/`43:421` instances; `PageLink`, `AttemptTime`, `Pill`/`RowStatus`, `.check-status`, `.note-card`; original brand artwork. |
| 03 · Competitor sites · Proposed, not approved | [256:609](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-609) | 375 × 1965 | Existing mobile bar `53:5990`; Tiger Plugins Source links `.link-row` responsive stacking and `Overview` `.cards li`; existing Figma Table row `43:405` instances for pages checked and matches found; `PageLink`, `AttemptTime`, `Pill`/`RowStatus` and `.note-card`. |

## What is proposed

The existing Overview, Alerts, Watch list and History section labels remain visible. These are three proposed views under Watch list, styled with existing Tiger controls. No new product navigation style, chart, sign-in, financial control or live integration is implemented.

- Price position: three product rows/cards show a populated comparison, a confirmed page with no reading, and no matches. The populated product has two current readings and one reading older than its six-hour watch interval. Every competitor name is a clickable page link; each available reading includes price, stock, time and interval. Missing price, stock and check time are explicitly unavailable, not zero. The old reading remains visible and labelled.
- The calculation is an approval proposal, written on both frames: compare current readings for confirmed matches in the same currency; include the store in rank; equal prices share a rank; difference is own price minus cheapest, with percentage relative to cheapest; exclude missing and overdue readings. No position is shown without a current competitor reading. Stock is displayed separately. This is not an assertion that the engine already implements that rule.
- Illustrative arithmetic: own £120; current competitors £100 and £110; old £90 excluded; cheapest £100, rank 3 of 3, difference +£20 / +20%. No-match and no-reading examples show unavailable rank, cheapest and difference.
- Matches to review: two suggestions show the store's product, its brand and maker part number, the matching values observed on the proposed competitor page, no barcode match, a page evidence link, and Confirm / Reject actions. Proposed wording says suggestions affect no position until confirmed.
- Competitor sites: one row/card per illustrative saved Source link, with pages checked, matches found and the time of the latest check or attempt. Completed, human-check-blocked and robots-restricted states are visible. The proposed wording explicitly says Tiger never solves or bypasses human checks, and that robots-disallowed pages are skipped. Counts are described as belonging to the latest site check, including partial runs.
- The Plugins → Source links line is a navigation proposal, not a guessed working application URL. `.example` page links are illustrative reserved-domain destinations and do not assert real page evidence.

Every new title, description, table label, status, calculation rule, action label and example value is covered by the visible approval annotation in its frame. Existing copied labels are likewise presented for review. No proposed text is approved for implementation by this document.

## Reuse and editability evidence

Source anchors: `workspace/app/tiger/view.tsx`: `Pill` 18; `RowStatus` 24; `ProductIdentifier` 30; `PageLink` 34; `AttemptTime` 38; `TigerApp` 42; `Overview` 171; `Watch` 307; `SimpleTable` 379. CSS anchors and exact line numbers are provided by the commands below; source line numbers should be rechecked if main changes.

The original desktop/mobile Tiger case-study frames (`49:3211`, `54:8114`) supplied the existing visual/component map. `38:127` supplied the original Tiger artwork. The desktop panel geometry and responsive content follow the existing Tiger source (240px panel, 64px desktop content gutters, 20px mobile gutters). Original pages and components were not modified.

The frames contain editable text, auto-layout containers, original discrete logo images, reusable Table header / Table row / Side menu item instances, and the source search SVG. Only logo artwork is raster; no complete UI screenshot is used as a design layer. Existing `42:*` color, spacing, radius and typography variables are bound wherever an applicable token exists. Source-specific dimensions use the existing CSS values. Jost Light headings/prices and Inter Regular / Medium / Semi Bold body/control text were verified by reading rendered text nodes.

## Validation and handoff

- Figma audit: six frames; exactly three at 1440 and three at 375; every frame labelled “Proposed, not approved”. Zero visible text bounds outside a frame or its immediate parent after the inherited table sizing was corrected.
- Editable-layer audit, per frame: `256:10` 141 descendants; `256:170` 115; `256:283` 108; `256:406` 67; `256:471` 121; `256:609` 82. Node types include FRAME, TEXT, RECTANGLE, INSTANCE, VECTOR and ELLIPSE where applicable. Discrete image nodes are the original logos only.
- Full-frame composition screenshots were viewed for all six frame IDs. The initial price screenshots exposed wrapping/clipping; the corrected full-frame screenshots are the final visual checks. These are agent checks in Figma, not founder acceptance screenshots.
- No application tests were run: no application file was changed and no authentication, scraping or matching implementation is part of this design job.
- Founder review in his own browser remains pending. No founder test or approval is claimed. Claude opens the PR from `codex/tiger-figma`; the founder merges. Nothing merged or deployed.

## Commands and results

Initial required command, exit 0:

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-tiger-figma && cd /workspace/codex-tiger-figma && git fetch origin main && git checkout -B codex/tiger-figma origin/main && ls workspace/app/tiger/view.tsx
```

Source reads used `cat AGENTS.md`, `sed -n '1,220p' workspace/app/tiger/view.tsx`, `sed -n '220,440p' workspace/app/tiger/view.tsx`, `cat workspace/app/tiger/tiger.css`, `sed -n '245,470p' workspace/app/tiger/tiger.css`, `sed -n '490,650p' workspace/app/tiger/tiger.css`, `sed -n '650,735p' workspace/app/tiger/tiger.css`, `cat workspace/app/tiger/copy.ts`, `sed -n '195,225p' workspace/app/tiger/plugins.tsx`, `sed -n '1,45p' workspace/app/tiger/model.ts`, and `cat workspace/app/squad-links.tsx`. All required source files were present. Searches for Code Connect mappings returned no matching files; existing local Figma components were used. The scoped library search for “Tiger price position workspace” returned no published composite, so the existing local Tiger assets remained authoritative.

The first commit command stopped with `Author identity unknown` (exit 128); no push ran in that chained command. Local repository identity was then set by name/email, and the commit and push succeeded:

```sh
git config user.name Codex && git config user.email codex@users.noreply.github.com && git commit -m 'docs(figma): record Tiger proposal scope and existing component sources' && git push origin codex/tiger-figma
```

Result: commit `42ebbdc8`; branch created remotely; exit 0. Design scripts were transient files under `.git/tiger-design/`; they are not tracked or part of the repository deliverable. Figma tool calls constructed and inspected page `256:9`; their returned node IDs and screenshot outputs are recorded in this task.

Final checks:

```sh
git diff --check
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git status --short --branch
```

Validation result: no diff whitespace errors; only `docs/figma/TIGER-POSITION-FRAMES.md` differs from the branch baseline; clean branch synchronized with `origin/codex/tiger-figma`. The final command output in this task records these results.


The first `git diff --check` found one extra blank line at EOF (exit 2); it was removed before committing. The source-anchor `rg` check confirmed the line numbers recorded above.
