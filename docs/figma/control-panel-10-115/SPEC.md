# Founder control panel: Figma frames 10:115 and 20:44

> Final export, Sun 25 Oct 2026, 17:10 PT. The founder's decision: **only what is real is on the page.** Everything with nothing behind it was removed. Every text in `reference.tsx` and `states.tsx` was checked against Figma by script: 68 texts, 0 differences.

## Where it is
- **Figma:**
  - the panel: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=10-115 (`frame.png`, `reference.tsx`);
  - its states: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=20-44 (`states.png`, `states.tsx`).
- **Size:** 1440 wide, height fits the content. Padding is 24 at the top, 32 at the sides and 32 at the bottom, with 18 between rows.
- **Built at:** `app.tervory.com/control` (`workspace/app/control/`). **Founder only.**

## Look
- **Logo:** `workspace/public/brand/tervory-logo.png`, 180 × 33, at the left of the top bar.
- **Fonts:**
  - Jost Light for "Control panel";
  - JetBrains Mono for every number;
  - Inter for everything else (`workspace/app/fonts`).
- **Colours:**

  | Use | Colour |
  |---|---|
  | Page | `#f4f6fa` |
  | Cards | white |
  | Card border | `#b8bfd0` |
  | Main text | `#001840` |
  | Muted text | `#3d4a66` |
  | Green | `#1e7a46` |
  | Red | `#e80008` |
  | Status dot: amber | `#B26B00` |
  | Status dot: grey | `#8C94A6` |

- **Radii:** cards 14, buttons 8, plan pills 999.
- **Sizes, gaps and paddings:** exact in `reference.tsx` and `states.tsx`.

## FIXED text: build exactly, to the character
| Where | Text |
|---|---|
| Top bar | `Control panel`. Button `Pause all paid work`, or `Resume paid work` while it is paused (22:25) |
| KPI labels | `Sign-ups`, `Paying clients`, `Work done today`, `Spent this month` |
| Section titles | `Needs you`, `Squad`, `Latest sign-ups`, `Controls` |
| "Needs you" buttons | `Approve all`; `Switch` and `Later`; `Start` |
| "Needs you" empty | `Nothing needs you.` (20:83), with no count |
| Squad names | `Base`, `Tiger`, `Market Lab`, `Rig`, `Tisan`, `Radix`, `Zenas` |
| Controls | `Squad workers` with `Pause workers`, or `Resume workers` while paused (22:27). Buttons `Open the window` (→ `/chats`) and `Proof report` (→ `/tank/proof`) |

## DATA text: a real value, in exactly this format
| Where | Frame shows | Real source (already in the code) | Format |
|---|---|---|---|
| Sign-ups | `214` / `+31 this week` | Clerk: total users / users created in the last 7 days (`signupSource`) | Comma between thousands / `+N this week` |
| Paying clients | `9` / `+2 this week` | Stripe: customers with an active paid subscription (`payingSource`) / those that started in the last 7 days | Number / `+N this week` |
| Work done today | `4,812` / `71% by code, no model` | Ledger, today: delivered calls / share done by code (`/v1/dashboards/founder`, `daily`) | Comma between thousands / `N% by code, no model` |
| Spent this month | `$212.40` | Ledger: sum of `spent` this month | `$` and 2 decimals |
| Sparklines | lines | The same numbers per day this month | Same stroke and size as the asset; no line under 2 days of data |
| Needs you count | `5` | The number of rows below it | Number; hidden when 0 (then the empty state shows) |
| Skills row | `14 skills passed their tests` | Skills in staging (`skills`) | `N skills passed their tests`. `Approve all` approves them (the existing action) |
| Cheaper model row | `Cheaper model proven for market research · saves $410/mo` | Shadow comparisons where the candidate is proven and cheaper (`readDashboardCandidates`) | One row per task. `Switch` switches; `Later` hides it until the next visit |
| Daily check row | `Daily check: 26 examples` | Check answers summary (`/v1/gold/summary`), examples waiting | `Daily check: N examples`. `Start` opens `/skala/gold` |
| Squad count | `2 running`, `1 queued`, `—` | Tasks running and queued per squad (`squad`) | `N running`, `N queued` when none are running, `—` when idle. Dot: green running, amber queued only, grey idle |
| Latest sign-ups | name, `Company · Country`, plan, `2h ago` | Clerk: the 5 latest users (`signupSource`) | As the frame shows. `All N` opens `/control/signups` |

**Removed by the founder's decision. Never build these:**
- the health pill;
- the budget and `budget $N`;
- Saved this month;
- the whole case study card;
- the web search and Autumbra items in "Needs you";
- the region picker;
- squad job names, % progress and the per-squad buttons;
- the four toggles;
- the daily budget bar;
- the server and storage rows.

**Every button does its real job, and every number opens its source.** If a source returns nothing usable, **stop and report it.** Never fill in a sample value, and never write a line that isn't in this file.
