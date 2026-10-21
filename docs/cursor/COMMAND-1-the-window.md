# COMMAND-1: the window. Talk to Tervory, and the squad does the work

> Written 20 Oct 2026, 18:45 PT. Founder: "Where is the window like I am discussing with you now that I asked for two weeks ago." And: "I still have a ticketing system."
>
> **Today:** `/` ("Chats") is a one-shot question box. Messages are not saved, it has no tools, and it cannot start work. Tervory's own build workers only take GitHub issues labelled `worker` that name a brief, which is a ticket system.
>
> **Goal:** a conversation window like the one the founder uses with Claude. He says what he wants. Tervory plans it, runs the squad and the workers, shows progress live, asks before anything that cannot be undone, and puts a receipt on every turn. The window is the ticket.

**Files you may change:**
- `workspace/app/page.tsx` and new `workspace/app/chats/`;
- new `tank/command.py` and `tank/main.py` (new `/v1/command/*` routes only);
- `tank/schema.sql` (additive);
- `workers/issues.py` and `workers/service.py` (also accept tasks from Tank);
- `workspace/lib/tank.ts` (command calls only);
- `.env.example` (names only);
- tests.

Do not change room code, Tank's router or the ledger rules.

## 1. Threads
- Chats are saved per tenant and per user on this box: a list of threads, new thread, rename, search.
- Messages stream in as they are written.
- Files can be attached, and are stored on this box only.

## 2. The orchestrator: every model call goes through Tank
- **Each turn is one Tank route** with task type `command.turn`, using the cheapest proven model as policy decides. It follows the ladder like any other task.
- **The tools it may call,** each through Tank routes that already exist:
  - each squad agent: Base batch and search, Tiger watch and read, Market Lab research, Rig search and ask, Tisan scaffold, Radix scan, Zenas ask, matters and review;
  - Skala: list skills, run evals, approve and retire (founder only, with a confirm);
  - the ledger and the proof page: costs, savings, receipts;
  - workers: start a build task (point 4);
  - repo read: briefs, PRs and CI status through the GitHub App, read-only.
- **The tools a user sees depend on their role.** A client sees only their own squad agents. The founder sees all of them.
- **Actions that change or cost something show an in-chat card with Confirm / Cancel first:** approving a skill, starting a paid run, starting a worker build, retiring a version. Nothing changes until Confirm is pressed.

## 3. The live work panel
- A panel beside the chat lists the steps of the current job (planned, running, done, failed), which agent or worker is doing each one, and links to anything produced (a batch, a PR, a report).
- It updates live. If the user leaves and comes back, the thread still shows where the job is.

## 4. Builds from the chat, not tickets
- When the founder asks for a change to Tervory, the orchestrator writes the brief into the thread. On Confirm it gives the task to the workers directly through Tank (`POST /v1/command/build`).
- No GitHub issue is needed. Workers still accept the `worker` label as a fallback.
- The worker's progress, its PR link, CI status and the reviewer's verdict all appear in the thread.
- The founder can reply in the thread ("fix X") and the worker continues on the same PR.

## 5. Receipts and benefits on every turn
- **Under every answer and every finished job:** each step's model or "code (no model)", tokens, cost, the baseline cost for the same tokens on the task's baseline model, and money saved.
- **The thread header shows totals:** spent and saved.
- **Every number links to its ledger rows.** No number is estimated.

## 6. Regions
- On the ZA box, threads, files and work stay on the ZA box and use tank-za. The same applies on Boston.
- Founders have full access on both.

## Done when
CI green. Tests:
- threads persist and stream;
- a tool call goes through Tank and appears on the ledger;
- an approve or paid action does nothing until Confirm;
- a client cannot see founder tools;
- a build started from the chat reaches the workers without a GitHub issue, and its PR link shows in the thread;
- every turn shows model, cost, baseline and saved, all matching ledger rows;
- the panel updates as steps change;
- 375px and 1440px screenshots are in the PR.

CI only runs on PRs: open one draft PR to run it, and mark it ready only when every check is green.
