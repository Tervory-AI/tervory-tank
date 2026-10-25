# Client dashboard: Figma frames 12:2 and 20:2

> Final export, Sun 25 Oct 2026, 17:10 PT. The founder's decision: **only what is real is on the page.** "Credits left" and "Waiting on you" were removed, because nothing behind them exists yet. Every text in `reference.tsx` and `states.tsx` was checked against Figma by script: 42 texts, 0 differences.

## Where it is
- **Figma:**
  - the dashboard: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=12-2 (`frame.png`, `reference.tsx`);
  - its states: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=20-2 (`states.png`, `states.tsx`).
- **Size:** 1440 × 900. The sidebar is 220 wide; the main area is 1220 wide, with padding 64 at the sides and 48 at the top and bottom.
- **Built at:** `app.tervory.com/`, the signed-in client home (`workspace/app/page.tsx`).

## Look
- **Logo:** `workspace/public/brand/tervory-logo-reversed.png`, 180 × 33, at the top of the sidebar with 18 below it.
- **Fonts:** Jost Light for the greeting and the two big numbers, and Inter for everything else (`workspace/app/fonts`).
- **Colours:**

  | Use | Colour |
  |---|---|
  | Page | `#f4f6fa` |
  | Sidebar | `#001840` |
  | Active nav | `#22345a` |
  | Card border | `#b8bfd0` |
  | Main text | `#001840` |
  | Muted text | `#3d4a66` |
  | Placeholder | `#8c94a6` |
  | Saved (green) | `#1e7a46` |
  | Status dot: ready | `#1E7A46` |
  | Status dot: in progress | `#001840` |
  | Status dot: queued | `#8C94A6` |
  | Status dot: failed | `#E80008` |

- **Radii:** cards 16, buttons 10, nav items 8, team tiles 12.
- **Sizes, gaps and paddings:** exact in `reference.tsx` and `states.tsx`.

## FIXED text: build exactly, to the character
| Where | Text |
|---|---|
| Nav | `Home`, `Chats`, `Files`, `Billing`, `Settings` |
| Ask box | Placeholder `What do you need today?`; buttons `Add a file` and `Go` |
| Card labels | `Jobs done this month`, `You saved` |
| Section titles | `Recent work`, `Your team` |
| Job status | Exactly one of `Queued` (grey), `In progress` (navy), `Ready` (green), `Failed` (red) |
| Team tiles | From this list only: `Base` / `Business lists`, `Tiger` / `Prices`, `Market Lab` / `Market research`, `Zenas` / `Legal` |
| Greeting | `Good morning, `, `Good afternoon, ` or `Good evening, ` + first name |
| Recent work, empty | `No work yet.` |

## DATA text: a real value, in exactly this format
| Where | Frame shows | Real source | Format |
|---|---|---|---|
| Greeting name | `Thandi` | The signed-in user's first name (Clerk) | Before 12:00 morning, 12:00 to 17:59 afternoon, from 18:00 evening, in the client's local time |
| Top right | `Northwind Law` | The client's organisation (the active tenant) | As stored |
| Jobs done this month | `67` | Finished jobs this calendar month (`/v1/dashboards/client`, `jobs_done`) | Whole number, comma between thousands |
| You saved | `$8,557` | This month's total from the client's savings report (the one `/tank/proof` shows) | `$` + whole number, comma between thousands. It opens the savings report |
| Recent work rows | job name + status | The client's latest jobs (`recent`): queued → `Queued`, running → `In progress`, done → `Ready`, failed → `Failed` | Up to 4 rows. Each opens its job |
| Team tiles | 4 tiles | The squads the founder has granted this client | Only granted squads; each opens its page |

**Removed by the founder's decision. Never build these:**
- Credits left;
- Waiting on you;
- the "Waiting on you" job status.

**Every number opens its source.** If a source doesn't exist or doesn't return the value, **stop and report it.** Never fill in a sample value, and never write a line that isn't in this file.
