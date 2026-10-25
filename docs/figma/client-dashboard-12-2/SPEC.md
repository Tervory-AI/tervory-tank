# Client dashboard: Figma frames 12:2 and 20:2

> Re-exported Sun 25 Oct 2026, 16:20 PT, after the founder approved all answers ("Do all").

## Where it is
- **Figma:**
  - the dashboard: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=12-2 (image `frame.png`, code `reference.tsx`);
  - its states: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=20-2 (image `states.png`, code `states.tsx`).
- **Size:** 1440 × 900. The sidebar is 220 wide; the main area is 1220 wide, with padding 64 at the sides and 48 at the top and bottom.
- **Built at:** `app.tervory.com/`, the signed-in client home (`workspace/app/page.tsx`).

## Look
- **Logo:** the real file `workspace/public/brand/tervory-logo-reversed.png`, 180 × 33, at the top of the sidebar with 18 below it. No text logo.
- **Fonts:** Jost Light for the greeting and the three big numbers, and Inter for everything else. Both are in `workspace/app/fonts`.
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
  | Status dot: waiting | `#B26B00` |
  | Status dot: ready | `#1E7A46` |
  | Status dot: in progress | `#001840` |

- **Radii:** cards 16, buttons 10, nav items 8, team tiles 12.
- **Sizes, gaps and paddings:** exact in `reference.tsx` and `states.tsx`.

## FIXED text: build exactly, to the character
| Node | Text |
|---|---|
| 12:8, 12:10, 12:12, 12:14, 12:16 | `Home`, `Chats`, `Files`, `Billing`, `Settings` |
| 12:23 | `What do you need today?` (the ask box placeholder) |
| 12:25 / 12:27 | `Add a file` / `Go` |
| 12:30, 12:33, 12:36 | `Jobs done this month`, `You saved`, `Credits left` |
| 12:40, 12:52, 12:70 | `Waiting on you`, `Recent work`, `Your team` |
| 12:44 / 12:46 / 12:50 | `Yes` / `No` / `Open` |
| Job status (12:56, 12:60, 12:68) | Exactly one of `Waiting on you`, `Ready`, `In progress`, with its dot colour |
| Team tiles | Squad name and line, from this list only: `Base` / `Business lists`, `Tiger` / `Prices`, `Market Lab` / `Market research`, `Zenas` / `Legal` |
| Greeting (20:4, 20:5, 20:6) | `Good morning, `, `Good afternoon, `, `Good evening, ` + first name |
| Empty: Waiting on you (20:20) | `Nothing is waiting on you.` |
| Empty: Recent work (20:39) | `No work yet.` |
| Empty: Credits left (20:43) | `No credits bought yet` |

## DATA text: a real value, in exactly this format
| Node | Frame shows | Real source | Format |
|---|---|---|---|
| 12:19 | `Good morning, Thandi` | The signed-in user's first name (Clerk). The greeting goes by the client's local time: before 12:00 morning, 12:00 to 17:59 afternoon, from 18:00 evening | One of the three greetings + first name |
| 12:21 | `Northwind Law` | The client's organisation name | As stored |
| 12:31 | `67` | Jobs finished this calendar month (ledger) | Whole number, comma between thousands |
| 12:34 | `$8,557` | Saved this month: what it would have cost, minus what it cost (ledger) | `$` + whole number, comma between thousands |
| 12:37 | `18,420` | Credits left (billing) | Whole number, comma between thousands |
| 12:42, 12:48 | `Search the web for 212 businesses? About $20`, `Lease review is ready to read` | Real items waiting on this client | One row each. A question gets `Yes` `No`; finished work gets `Open` |
| 12:54 to 12:66 | `Delaware dealer list` and so on | This client's latest jobs | Job name, dot, status |
| Team tiles | Base, Tiger, Market Lab, Zenas | The squads on this client's plan | Only the squads they have |

**When to use the states:**
- **Waiting on you:** nothing is waiting → show 20:8 in place of 12:39.
- **Recent work:** no jobs yet → show 20:21 in place of 12:51.
- **Credits left:** no credits ever bought → show 20:40 in place of 12:35.

**Every number opens its source.** If a source doesn't exist yet, or a client has a squad that isn't in the team list above, **stop and report it.** Never fill in a sample value, and never write a line that isn't in this file.

## Open questions
None. All were answered by the founder on 25 Oct:
- dollars;
- the greeting by time of day;
- the three empty states;
- team names without "(logo)";
- the logo file at 180 wide.
