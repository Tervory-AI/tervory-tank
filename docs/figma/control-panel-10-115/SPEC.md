# Founder control panel: Figma frames 10:115 and 20:44

> Re-exported Sun 25 Oct 2026, 16:20 PT, after the founder approved all answers ("Do all").

## Where it is
- **Figma:**
  - the panel: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=10-115 (image `frame.png`, code `reference.tsx`);
  - its states: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=20-44 (image `states.png`, code `states.tsx`).
- **Size:** 1440 × 1140. Padding is 24 at the top, 32 at the sides and 32 at the bottom, with 18 between rows.
- **Built at:** `app.tervory.com/control` (`workspace/app/control/`). **Founder only.**

## Look
- **Logo:** the real file `workspace/public/brand/tervory-logo.png`, 180 × 33, at the left of the top bar. No text logo.
- **Fonts:**
  - Jost Light for "Control panel";
  - JetBrains Mono for every number;
  - Inter for everything else.

  All three are in `workspace/app/fonts`.
- **Colours:**

  | Use | Colour |
  |---|---|
  | Page | `#f4f6fa` |
  | Cards | white |
  | Card border | `#b8bfd0` |
  | Main text | `#001840` |
  | Muted text | `#3d4a66` |
  | Faint text | `#8c94a6` |
  | Green | `#1e7a46` |
  | Green pill | `#eaf6ef` |
  | Red | `#e80008` |
  | Red pill | `#fdecec` |
  | Bar background | `#d6deeb` |
  | Status dot: amber | `#B26B00` |
  | Status dot: grey | `#8C94A6` |

- **Radii:** cards 14, buttons 8, pills 999, bars 3.
- **Sizes, gaps and paddings:** exact in `reference.tsx` and `states.tsx`.

## FIXED text: build exactly, to the character
| Node | Text |
|---|---|
| 10:120 | `Control panel` |
| 10:126 | `Pause all paid work` |
| KPI labels | `Sign-ups`, `Paying clients`, `Work done today`, `Spent this month`, `Saved this month` |
| 10:164 | `vs top models` |
| 10:176, 10:217 | `Verified records by state`, `Cost per verified record` |
| 10:214 / 10:215 / 10:223 | `■ Verified` / `■ Licences` / `— Tervory, falling` |
| 10:227, 10:233, 10:236 | `Tervory found`, `Cost per record`, `States done` |
| 10:240 / 10:242 | `Run next state` / `Export case study` |
| 10:245, 10:277, 10:330, 10:370 | `Needs you`, `Squad`, `Latest sign-ups`, `Controls` |
| "Needs you" buttons | `Approve all`, `Run`, `Skip`, `Switch`, `Later`, `Start`, `Look`, `Let it fix` |
| Squad names | `Base`, `Tiger`, `Market Lab`, `Rig`, `Tisan`, `Radix`, `Zenas`, `Autumbra` |
| Squad buttons | `Pause`, or `Start` when that squad is stopped |
| Toggles | `Shadow checks on every model call`, `Overnight half-price batches`, `Paid tools without asking`, `Squad builds Tervory` |
| 10:389, 10:395, 10:398, 10:408 | `Daily budget`, `Servers`, `Boston`, `Storage` |
| 10:413 / 10:415 | `Open the window` / `Proof report` |
| Health pill, all fine (10:124) | `All systems normal · Autumbra on watch` (green) |
| Health pill, problems (20:48, 20:51) | `1 problem · Autumbra on watch`, or `N problems · Autumbra on watch` for 2 or more (red) |
| Needs you, empty (20:83) | `Nothing needs you.` |

## DATA text: a real value, in exactly this format
| Node | Frame shows | Real source | Format |
|---|---|---|---|
| 10:130 / 10:132 | `214` / `+31 this week` | Clerk: total sign-ups, and those in the last 7 days | Comma between thousands / `+N this week` |
| 10:138 / 10:140 | `9` / `+2 this week` | **Stripe: customers with a paid, active subscription** (no trials) / new ones in the last 7 days | Number / `+N this week` |
| 10:146 / 10:148 | `4,812` / `71% by code, no model` | Ledger: tasks finished today / share done with no model call | Comma between thousands / `N% by code, no model` |
| 10:154 / 10:156 | `$212.40` / `budget $600` | Ledger: spend this month / the monthly budget setting | `$` and 2 decimals / `budget $N` |
| 10:162 | `$3,691.70` | Ledger: saved this month | `$` and 2 decimals |
| Sparklines | lines | The same numbers per day, last 14 days | Same stroke and size as the asset |
| 10:171 / 10:173 | `Case study · AmmoSync on Base` / `ATF list · 74,012 licences` | The Base case-study job | `Case study · <job>` / `<source> · N licences` |
| Bars (DE to CA) | licences and verified per state | Same job, per state | Same colours, widths and gaps |
| 10:218 | line | Cost per verified record over time | Tervory's line only, stroke `#001840` |
| 10:228 / 10:234 / 10:237 | `14,000 records` / `$0.0004` / `12 of 50` | Verified records / cost ÷ verified / states finished | `N records` / `$` and 4 decimals / `N of 50` |
| 10:247 | `5` | How many items are in "Needs you" | Number. Hidden when 0, and the empty state shows instead |
| "Needs you" items | the five rows | Real pending founder decisions | One row each, with its FIXED buttons |
| 10:279 | `Boston ▾` | Region picker | `Boston` is the only region |
| Squad lines | `Texas list · 61%`, `—` and so on | Each squad's current job and progress | `<job> · N%`, or `—` when idle |
| Status dots | green, amber, grey | Each squad's state | Green running, amber queued, grey stopped |
| 10:333 | `All 214` | Total sign-ups | `All N` |
| Sign-up rows | name, `Company · Country`, plan, `2h ago` | Clerk: the 5 latest sign-ups | As the frame shows |
| Switches | on / off | The real setting | `switch-on.svg` / `switch-off.svg` |
| 10:391 / bar | `$20 · $7.10 used` | Daily budget and today's spend | `$N · $N.NN used`; the bar fill = used ÷ budget × 318 |
| 10:400 / 10:410 | `CPU 34% · memory 61%` / `R2 · 41 GB of 1 TB` | Boston server stats / storage used | As shown |

**Removed by the founder on 25 Oct. Never build these:**
- the South Africa server row;
- Apollo's count, legend and line;
- the "Sample figures for layout" footer.

**Every button does its real job, and every number opens its source.** No section may show "unavailable", "not linked" or a build code. If a source doesn't exist yet, **stop and report it.** Never fill in a sample value, and never write a line that isn't in this file.

## Open questions
None. All were answered by the founder on 25 Oct:
- Autumbra;
- the red problem pill;
- no South Africa row;
- no Apollo figures;
- no footer;
- "Nothing needs you.";
- the logo file at 180 wide.
