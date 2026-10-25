# Client dashboard: Figma frame 12:2

- **Figma:** https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=12-2. The frame is named "Client dashboard · clean (Northwind Law, ZA)".
- **Size:** 1440 × 900. The sidebar is 220 wide and the main area 1220 wide (64 left and right padding, 48 top and bottom).
- **Built at:** `app.tervory.com/`, the signed-in client home (`workspace/app/page.tsx`).
- **Fonts:**
  - Jost Light for the greeting and the three big numbers;
  - Inter for everything else.

  Both are already in `workspace/app/fonts`.
- **Colours:**

  | Use | Colour |
  |---|---|
  | Page background | `#f4f6fa` |
  | Sidebar | `#001840` |
  | Active nav | `#22345a` |
  | Card border | `#b8bfd0` |
  | Main text | `#001840` |
  | Muted text | `#3d4a66` |
  | Placeholder | `#8c94a6` |
  | Saved (green) | `#1e7a46` |
  | Status: waiting | `#B26B00` |
  | Status: ready | `#1E7A46` |
  | Status: in progress | `#001840` |

- **Radii:** cards 16, buttons 10, nav items 8, team tiles 12.
- **Exact sizes, gaps and paddings:** in `reference.tsx`. The image is `frame.png`.

## FIXED text: build exactly, to the character
| Node | Text |
|---|---|
| 12:8 | `Home` |
| 12:10 | `Chats` |
| 12:12 | `Files` |
| 12:14 | `Billing` |
| 12:16 | `Settings` |
| 12:23 | `What do you need today?` (placeholder in the ask box) |
| 12:25 | `Add a file` |
| 12:27 | `Go` |
| 12:30 | `Jobs done this month` |
| 12:33 | `You saved` |
| 12:36 | `Credits left` |
| 12:40 | `Waiting on you` |
| 12:44 / 12:46 | `Yes` / `No` |
| 12:50 | `Open` |
| 12:52 | `Recent work` |
| 12:56 / 12:60 / 12:68 | Job statuses, exactly one of: `Waiting on you`, `Ready`, `In progress` |
| 12:70 | `Your team` |

## DATA text: a real value, in exactly this format
| Node | Frame shows | Real source | Format rule |
|---|---|---|---|
| 12:19 | `Good morning, Thandi` | The signed-in user's first name (Clerk) | `Good morning, ` + first name. See open question 1 |
| 12:21 | `Northwind Law` | The client's organisation name | As stored |
| 12:31 | `67` | Jobs finished this calendar month (ledger) | A whole number, with a space between thousands |
| 12:34 | `R 8 557` | Saved this month: what it would have cost minus what it cost (ledger) | Currency sign, a space, a whole number with a space between thousands. See open question 2 |
| 12:37 | `18 420` | Credits left (billing) | A whole number, with a space between thousands |
| 12:42, 12:48 | `Search the web for 212 businesses? About R 20` / `Lease review is ready to read` | Real items waiting on this client (approvals asked for, finished work not yet opened) | One row per item. The buttons are FIXED (`Yes` `No` for a question, `Open` for finished work) |
| 12:54, 12:58, 12:62, 12:66 | `Delaware dealer list`, `Lease review`, `Competitor prices`, `Q3 dealer list` | This client's latest jobs | Job name, then a status dot and a status from the FIXED list |
| 12:73–12:83 | `Base (logo)` + `Business lists`, and so on | The squads on this client's plan | See open question 4 |

Every DATA value must come from a real source and open that source when clicked (build list, step 2.1). If a source doesn't exist yet, **stop and report it.** Never put in a made-up or sample value.

## Founder's open questions: answer in Figma before the build starts
The builder must not answer these. Each one is a change to the frame, or a "build as is".

1. **The greeting:** always `Good morning, `, or morning, afternoon and evening? Only "morning" is in the frame.
2. **Currency:** the frame shows rand (`R 8 557`, `About R 20`). ZA is stopped and clients are in the US. Should it be `$` with US formatting (`$8,557`), or the client's own currency?
3. **Empty states:** what shows when there's nothing waiting, no recent work, or no credits bought yet? None of these is in the frame, so as it stands a builder can't show anything.
4. **"Your team":** the frame says `Base (logo)`. Which logo files? `workspace/public/brand` only has the "on-dark" versions, and these tiles are light. Do they show only the client's squads, or always these four?
5. **The logo size:** the frame's logo is 98 px wide, and the logo rule says at least 180 px. Which wins? The file to use on the dark sidebar is `tervory-logo-reversed.png`.
