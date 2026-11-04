# Approved Tiger TG2 references

Source: Figma `ZnphBOJU6657tohGLD3IzS`, register on `codex/tiger-figma` at
`115cae58d4ac219a40989f69902c182d94ecf471`, Approved 3 Nov 15:20 PT.
These exports include the approved navy selected/Confirm borders and the
corrected 140% mobile Cheapest line heights.

| PNG node | View | Export size |
| --- | --- | --- |
| 256:10 | Price position | 1440 × 1449 |
| 256:170 | Price position | 375 × 2725 |
| 256:283 | Matches to review | 1440 × 1165 |
| 256:406 | Matches to review | 375 × 1955 |
| 256:471 | Competitor sites | 1440 × 1145 |
| 256:609 | Competitor sites | 375 × 2170 |
| 267:19232 | Matches empty | 1440 × 937 |
| 267:19356 | Matches empty | 375 × 708 |
| 267:19424 | Sites empty | 1440 × 937 |
| 267:19562 | Sites empty | 375 × 825 |

The top 89px is a Figma review annotation, excluded from the app comparison.
`copy.json` records approved FIXED text. Examples are DATA in `../fixture.ts`;
production does not import them. `../evidence/frame-sha256.json` identifies the
exports, and `../evidence/visual-results.json` records the actual comparisons.

The app uses the existing transparent
`workspace/public/brand/tervory-logo.png`, preserving main’s branding rule, at 208 × 38 desktop
and 186 × 34 mobile. Search (16 × 16), warning dot (6 × 6), neutral hollow dot
(6 × 6) and checked dot (6 × 6) are original downloaded SVGs under
`workspace/public/tiger/`. They are checked for load success and effective geometry.
No flattened design image is an implementation asset; no temporary Figma URL is
used at runtime.
