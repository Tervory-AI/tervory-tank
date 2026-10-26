# Base page: Figma frames 7:221 (C5) and 26:31

> Final export, Mon 26 Oct 2026, 01:40 PT. The founder's approved C5 frame, cleaned to only what is real: no sample footer, no rand, no "Needs you", "Paid" or "Saved" columns, and no "What Base has learned". The sidebar's "Savings" item is gone until the client savings page exists.

## Where it is
- **Figma:** https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=7-221 (page "2 · Client screens"; `frame.png`, `reference.tsx`), plus its states https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS/?node-id=26-31 (`states.png`, `states.tsx`).
- **Size:** 1440 × 1000, with a 256 sidebar.
- **Built at:** `app.tervory.com/base` and `base.tervory.com/`. It replaces today's /base page.

## FIXED text: build exactly, to the character
| Where | Text |
|---|---|
| Sidebar | `Dashboard` (→ `/`), `Projects`, `Chats` (→ `/chats`), `Squad` (current), `Billing` (→ `/billing`), `Settings` |
| Header | `Base`, `Verified business lists.` |
| Ask box | Placeholder `Ask Base, or upload a list to verify…`; buttons `Upload list` and `Ask` |
| Jobs | Title `Jobs`; columns `Job`, `Status`, `Records`, `Verified`; link `Download` on every row |
| States (26:31) | `No lists yet.` · `Uploading…` · statuses `Running`, `Done`, `Failed` · errors `file over 80 MB; split it`, `no rows found; first line must be a header`, `max 100,000 rows per upload; split the file`, `Tank unavailable` |

## DATA text: a real value, in exactly this format
| Where | Frame shows | Real source (already in the code) | Format |
|---|---|---|---|
| Account | `Northwind Law` | The client's organisation (the active tenant) | As stored |
| Job | `Delaware licence list` | The batch name (`/v1/base/batches`, `batch`) | As stored. For an upload it is the file name without `.csv` |
| Status | `Done` / `Running` | Same row: `pending` > 0 → `Running`; else `failed` = `total` → `Failed`; else `Done` | One word |
| Records | `1,284` | `total` | Comma between thousands, JetBrains Mono |
| Verified | `1,051` | `ready` (confidence 80 or more) | Comma between thousands, JetBrains Mono |
| Download | link | `/api/base/export?batch=<batch>` (exists) | — |

## What each button does
- **Upload list:** opens a file picker for `.csv`, then posts the file to the existing `POST /api/base` with the batch name taken from the file name. The new job appears at the top of Jobs. Errors show the route's own message (26:64).
- **Ask:** the existing code-only record search behind today's "Ask Base" (`workspace/app/base/records.ts` / `search.ts`), scoped to the client's own tenant. **No model call.**

**Every read is the signed-in client's own tenant** (AGENTS.md rule 3). If anything above has no source, **stop and report it.** Never write a line that isn't in this file.
