# Go-live functionality: what must exist before launch

> Written by Claude, Mon 26 Oct 2026, 01:05 PT, from a check of the code on main (`65067a4`).
>
> On 25 Oct the founder took everything with nothing behind it off the dashboard and the control panel. **This is the list of those things, built for real.** Each one is a back-end job first. Its part of the page returns to Figma only once the back end exists. Then it's built to the frame, and the assessor checks it live.

## Founder, 26 Oct 01:11 PT: product first
**Pricing, keys and Stripe come when there is something to pay for.** G1 (paid-step confirmation), G2 (plans or credits), G3 (spend cap) and G5 (savings total) are **parked**. They aren't built until the founder says so.

**The work now:** every product does its real job, end to end, live. G4 (health) and G6 to G10 stay on the list below, after that.

## Parked list (kept for later)
## Must exist before go-live (customers and money)
| # | What | Why it matters | What exists today | The job | Decision needed from the founder |
|---|---|---|---|---|---|
| G1 | **Paid-step confirmation**: a client says Yes or No before a paid step runs | No client is charged for a step they didn't approve | The chat front end already draws a confirm card (`awaiting_confirmation` in `workspace/app/chats/`), but **Tank never sets that status**, so it never happens | Tank pauses a task at a paid step, stores it as waiting, and resumes or skips on Yes/No. It feeds the chat card and "Waiting on you" on the dashboard | Which steps must ask first: every paid step, or only those over $X |
| G2 | **What clients pay for**: plans or credits | "Credits left" can only exist if credits exist | Billing is **Stripe plans only** (`workspace/app/billing/`). There is no credit balance anywhere | If credits: a credit ledger, Stripe top-ups and a balance. If plans only: credits are dropped for good | Plans, credits, or both |
| G3 | **Spend cap**: daily and monthly budgets that stop paid work by themselves | Stops a runaway bill overnight | Only the manual "Pause all paid work" (`tank/controls.py`) | Budgets stored in Tank; paid work refused once a budget is reached (the same refusal path as the pause), logged | The daily and monthly amounts |
| G4 | **Health**: one "all fine / N problems" status | The founder sees trouble without opening Coolify | The watchdog already checks every 10 minutes and opens a "Down: …" GitHub issue per problem (`.github/workflows/watchdog.yml`) | The watchdog reports each result to Tank as well; Tank keeps the current problems; the control panel reads them | None |

## Should exist at go-live
| # | What | What exists today | The job |
|---|---|---|---|
| G5 | **Saved this month** (all clients) | Per-client savings reports exist (`/tank/proof`); there's no platform total | Tank sums the client savings reports for the month |
| G6 | **Pause or start one squad** | One pause for all workers (`/v1/controls/workers-paused`) | A pause per squad, logged like the others |
| G7 | **Server load and storage** | Nothing | Grok exposes Boston CPU and memory and the R2 usage to Tank, read-only; the control panel reads them |

## After go-live
| # | What | Waits on |
|---|---|---|
| G8 | Case study (AmmoSync on Base) | Base running its first real job (build list step 2.4) |
| G9 | The four toggles: shadow checks, overnight batches, paid tools without asking, squad builds Tervory | The founder defining what each switch does |
| G10 | Autumbra alerts in "Needs you" | The Autumbra build |

## How each one is built
1. **Back-end PR** (Codex): Tank routes, schema additions, tests. No page changes.
2. **Live proof** (Grok): the route returns real values on Boston.
3. **Figma**: the founder approves the returning part of the frame, and Claude re-exports it.
4. **Page PR** (Codex), built to the export.
5. **The assessor** checks it in the founder's browser.

One job at a time per builder.
