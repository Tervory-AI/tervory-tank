# Tiger price position — design check, 3 Nov

The founder approved the baseline on 3 Nov, as reported in this task. Every modified/new frame and its review top bar now records **Approved 3 Nov** and **Changed after approval, awaiting founder**. All ten frames have changed wording; the earlier approval does not approve these changes.

Page: [9 · Tiger price position](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-9), node `256:9`. Same branch: `codex/tiger-figma`. Only this document is committed. No application or live-data changes; nothing merged or deployed. Claude opens the PR and the founder merges.

## Frame map — one line per frame

All rows below have both approval-history and awaiting-founder labels.

| Frame | Node ID | Size | Existing components reused |
| --- | --- | --- | --- |
| Price position | [256:10](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-10) | 1440 × 1292 | TigerApp panel, Side menu items 43:409/43:421, SimpleTable, Table header 43:389, PageLink, AttemptTime, Pill/RowStatus |
| Price position | [256:170](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-170) | 375 × 2336 | TigerApp mobile bar 53:5990, Overview .cards, Table row 43:405, PageLink, AttemptTime, Pill/RowStatus |
| Matches to review, pending and rejected rows | [256:283](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-283) | 1440 × 1114 | TigerApp panel, Side menu items, SimpleTable, Table header 43:389, PageLink, button.line.small, button.text |
| Matches to review, pending and rejected cards | [256:406](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-406) | 375 × 1776 | Mobile bar 53:5990, Overview .cards, PageLink, button.line.small, button.text, .row-actions |
| Competitor sites | [256:471](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-471) | 1440 × 1070 | TigerApp panel, Side menu items, Plugins Source links, SimpleTable, Table header 43:389, Pill/RowStatus |
| Competitor sites | [256:609](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=256-609) | 375 × 1878 | Mobile bar 53:5990, responsive Source links, Overview .cards, Table row 43:405, Pill/RowStatus |
| Matches to review — empty | [267:19232](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19232) | 1440 × 989 | Existing desktop Matches shell and controls; Tiger empty-text pattern |
| Matches to review — empty | [267:19356](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19356) | 375 × 713 | Existing mobile Matches shell and controls; Tiger empty-text pattern |
| Competitor sites — empty | [267:19424](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19424) | 1440 × 989 | Existing desktop sites shell and controls; Tiger empty-text pattern |
| Competitor sites — empty | [267:19562](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=267-19562) | 375 × 794 | Existing mobile sites shell and controls; Tiger empty-text pattern |

All six original frame IDs survive. Four new frames cover the two empty states at both widths. The second original Matches row/card demonstrates Rejected with Undo; the first retains Confirm and Reject.

## Changed node IDs and behavior

- Approval bars retained: `256:11`, `256:171`, `256:284`, `256:407`, `256:472`, `256:610`. Existing heading/body text IDs retained. New illustrative-data annotations: `267:19218`, `267:19219`, `267:19220`, `267:19224`, `267:19230`, `267:19231`.
- South shop becomes saved North shop at `256:377`, `256:378`, `256:448`, including evidence hyperlinks to `https://north-shop.example/products/desk-lamp`. All illustrative competitors are saved North, West or East sites. Reserved .example links remain Figma-only examples, not claimed observations.
- Duplicate section strips removed: desktop `256:59`, `256:332`, `256:520`; mobile `256:189`, `256:425`, `256:628`. Desktop section navigation remains once in the panel, as in TigerApp; mobile uses Menu.
- Repeated view-heading text removed: `256:65`, `256:195`, `256:338`, `256:431`, `256:526`, `256:634`. Each view name appears once in its segment below the Tiger heading.
- Shared Matches intro removed at `256:346`, `256:439`. Its unchanged sentence is now each row/card's reason: `267:19222`, `267:19223`, `267:19226`, `267:19228`.
- Rejected/Undo retain original text IDs: desktop `256:400`/`256:402`; mobile `256:465`/`256:467`. Rejected is plain status, not a Confirm-style button; evidence is retained.
- Explicit mobile competitor-page links added at `267:19227`, `267:19229`, with the North/East page URLs and placed before actions.
- Empty text nodes: `267:19355`, `267:19423` = No matches to review.; `267:19561`, `267:19641` = No saved sites.
- Warning text/pill pairs: stale `256:127`/`256:125`, `256:228`/`256:226`; human check `256:588`/`256:586`, `256:670`/`256:668`; robots `256:604`/`256:602`, `256:684`/`256:682`. Text, border and dot use existing light warning colour `--warn: #b45309` from `workspace/app/globals.css:60`. Checked stays neutral. No Figma warning token exists, so this source value was used directly rather than inventing a token.
- Compact desktop rows retain IDs: price `256:101`, `256:133`, `256:153`; matches `256:366`, `256:385`; sites `256:559`, `256:575`, `256:591`. Row height now fits the tallest content cell plus existing padding. Empty desktop panel height accommodates History and Support.
- Aligned missing-value glyphs: `256:149`–`256:151`, `256:164`–`256:166`, all Inter 14px / 21px. Desktop difference `256:131` matches mobile `I256:237;43:407`: +£20.00 · +20%. Desktop Difference column widened to 160px.
- Native Tiger logo rule: original Tiger artwork is 48px high at native 2607:801 aspect ratio in the desktop panel (`256:16`, `256:289`, `256:477`). Mobile bar is 67px high with actual original Tervory artwork resized to 186 × 34 (`256:177`, `256:413`, `256:616`); new empty mobile artwork `267:19364`, `267:19570` uses the same rule. No logo redrawn.
- Search text updated: `256:55`, `256:185`, `256:328`, `256:421`, `256:516`, `256:624`; copied to empty frames.
- Mobile attempt wording: `256:667`, `256:681`.
- Plugins navigation `256:535`, `256:643` is underlined as a link and copied to empty sites frames. No working application route was invented.

## Added or changed words awaiting founder

| Exact text | Purpose |
| --- | --- |
| Approved 3 Nov | Baseline approval history |
| Changed after approval, awaiting founder | Current review status |
| Illustrative values · Figma only. | Review annotation |
| Search watched products, readings and alerts | Search placeholder |
| North shop ↗ | Saved-site correction |
| North shop · page evidence ↗ | Evidence-link correction |
| Rejected | Row status |
| Undo | Rejected-row action |
| No matches to review. | Empty Matches |
| No saved sites. | Empty sites |
| Blocked by a human check | Warning |
| Some pages closed to robots | Warning |
| Last attempt: 25 minutes ago | Corrected mobile metadata |
| Last attempt: 1 hour ago | Same correction on the other attempted check |
| Competitor page: north-shop.example/products/desk-lamp ↗ | Explicit mobile page link |
| Competitor page: east-shop.example/products/wall-lamp ↗ | Explicit mobile page link |
| +£20.00 · +20% | Shared difference format |

Moved, not rewritten: “Same brand and maker part number. No barcode match. Confirm the product before it affects price position.” It now belongs to each row. The previously approved price-position rule and all other unchanged wording remain intact.

## Reuse and validation

Baseline source commit `bb3200835b519826b4664418c4ccb5ab900cff73`; previous design handoff `ad4168a8`. Sources: `workspace/app/tiger/view.tsx`, `tiger.css`, Tiger Plugins Source links and existing Figma Tiger frames/components. Live logo rules are at `view.tsx:87` onward and `tiger.css:129` onward. Original pages and main components were not edited.

Ten editable frames: five at 1440 and five at 375. Final bounds audit found zero text outside its frame or immediate parent, zero old South shop / reads and alerts / Last checked: Attempted wording, and verified Jost Light plus Inter Regular/Medium/Semi Bold. Original discrete logos are the only raster images; no flattened UI image is a design layer. Existing spacing, colour and type bindings remain.

The initial audit found sidebar overflow on short empty desktop frames; minimum panel height was corrected before final verification. Full-frame screenshots were inspected for corrected desktop price, desktop/mobile Matches, desktop/mobile sites, desktop Matches empty and mobile sites empty. The mobile Matches screenshot was checked again after correcting the actual logo image size. These are agent visual checks. Baseline founder approval is recorded from the user's message; acceptance and founder screenshots for the changes remain pending.

## Commands and results

Required branch/source checks and reads:

```sh
git status --short --branch
git branch --show-current
cat docs/figma/TIGER-POSITION-FRAMES.md
sed -n '80,160p' workspace/app/tiger/view.tsx
rg -n 'warn|warning|logo|topbar|panel-top' workspace/app/tiger/tiger.css
rg -n -i 'warn(ing)?[^\n]{0,70}(#|color)|#[a-f0-9]{3,8}[^\n]{0,50}warn' workspace/app workspace/components | head -n 45
nl -ba workspace/app/globals.css | sed -n '55,63p'
```

Result: correct branch, clean starting tree and all required brief files present. The optional warning search reported that `workspace/components` does not exist; the existing warning colour was found in `workspace/app/globals.css`. No required file was missing. The first document replacement tool call failed validation before changing the document; it was corrected with a single-file write. Design orchestration scripts are transient under `.git/tiger-design/` and not tracked.

Final commands:

```sh
git diff --check
git add docs/figma/TIGER-POSITION-FRAMES.md
git commit -m 'docs(figma): record Tiger post-approval design corrections'
git push origin codex/tiger-figma
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git status --short --branch
```

The command output in this task records the results. Only this document may differ from main. No application tests are needed for this Figma-only change; no runtime feature is claimed to work. The founder must approve changed/new words before build.
