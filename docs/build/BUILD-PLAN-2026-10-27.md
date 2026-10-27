# Tervory build plan, 27 Oct 2026: what is done, what is broken, what is left

> Written by Claude on Tue 27 Oct 2026, 09:20 PT, at the founder's request. **This replaces every earlier build list:**
> - the two-day plan of 21 Oct (`plan/two-day-build.md` in the project);
> - the build lists of 25 Oct (`docs/build/BUILD-LISTS-2026-10-25.md`, `REAL-BUILD-LIST-2026-10-25.md`);
> - the go-live list and the break points of 26 Oct (on branch `docs/go-live-list`, never merged).
>
> **Sources:**
> - the code on `main` at `c752e59` (#352, merged 07:23 PT), plus #355 (09:15 PT);
> - the open branches on GitHub;
> - the founder's own browser, checked between 09:05 and 09:16 PT.
>
> Every line says where it comes from. **"Merged" only means the code is on main.** Nothing in this plan counts as done until the founder's live page does its job.

## The rules every builder follows (founder)
1. **Product first.** Nothing that isn't needed to make a product work live: no sign-in work, no pricing, keys, Stripe, credits or spend caps.
2. **Figma first.** Nothing goes on any site without an approved Figma frame, matched to the character. A thread that deviates, or botches a deploy, is deleted with all its work.
3. **No demo or sample data, and no made-up copy.** If a real source is missing, stop and report it.
4. **No model calls where code can do the job,** and none to check work.
5. **Savings is core.** Every finished job shows what it cost and what it would have cost.
6. **Done** means the live page matches Figma and does its real job in the founder's browser. Tests passing is not done.
7. **The founder merges.** Never type, see or create secrets. Never weaken a seal.

---

## 0. Fix first: the live Workspace is down
Between 09:05 and 09:16 PT, app.tervory.com, base.tervory.com and tiger.tervory.com all showed "Application error: a client-side exception has occurred" in the founder's browser.

- **Cause:** #341 (merged 07:05 PT) moved Clerk to `7.9.21` (`workspace/package.json:12`). The shell still used `<SignedIn>` (`workspace/app/shell.tsx:3` and `:152` at `c752e59`), which Clerk 7 removed.
- **Fix:** merged as #355 at 09:15 PT. At 09:16 app.tervory.com was still down, so the Workspace still has to be redeployed and checked.
- **Why it reached live:** #351 (05:49 PT) cut the merge check to lint, the secret scan and Tank start. The Workspace build and its tests no longer gate a merge.
- **Done when:** the Workspace is redeployed with #355 and every product host opens in the founder's browser.
- **Then:** add a Workspace production build to the merge check (one `next build`, a few minutes), so a page-breaking change can't merge again.

## 1. Why nobody could find the work
- **The 21 Oct plan lives only in the project** (`plan/two-day-build.md`), not in the repo, so builders never saw it.
- **The 26 Oct go-live list, the break points and the Base C5 Figma export** sit on branch `docs/go-live-list`, which was never merged. On main, `docs/figma/` holds only the dashboard (12:2) and the control panel (10:115).
- **The 26 Oct builder briefs:** only `ops/BUILDER-BRIEFS-2026-10-26/04-GROK-AUTUMBRA.md` is on main. Briefs 01 to 03 never reached the repo.
- **The CORE lane** ran as CORE-1, CORE-2, CORE-2b and CORE-2c (#218, #227, #234, #242). There is no CORE-3.

**From now on:** this file is the one plan. It lives on main at `docs/build/BUILD-PLAN-2026-10-27.md` and in the project at `plan/BUILD-PLAN-2026-10-27.md`. Each builder brief links to it.

---

## 2. The 21 Oct plan, lane by lane

| Lane | Merged | What landed | What is still missing |
|---|---|---|---|
| CORE-1, 2, 2b, 2c: bench, savings, proof page | #218, #227, #234, #242 (21–22 Oct) | Ledger savings, the founder's proof page `/tank/proof`, client copies and PDF exports | Chat turns never reach savings (section 3, Tank). The client dashboard shows a "View savings" link, not an amount (`workspace/app/page.tsx:37`) |
| AGENT-1: Base brain | #216 (21 Oct) | Base's Hermes brain (`agents/base/Dockerfile.brain`) | Never cloned. Only Base and Rig (#248) have a brain; Tiger, Market Lab, Tisan, Radix and Zenas have none |
| MODELS-2 and 3: every model | #154, #230 | DeepSeek, Kimi and Perplexity in the roster; open-weight models via Hugging Face | Nothing. Built |
| BUCKET-1: R2 per agent | #217 | Room-owned R2 storage | Nothing. Built |
| DASH-1: dashboards | #220 | The first dashboard and control panel | Main still shows "Credits left" and "Waiting on you" (`workspace/app/page.tsx:37`, `:39`), which the founder removed. The rebuilds to the 26 Oct frames are on branches `codex/dashboard` and `codex/control-panel`, not merged |
| GHOST-1, now Autumbra | #219, then #345 (27 Oct) | Watch, Enforce, shields with undo, the owner email | Section 3, Autumbra |
| COMMAND-1 A and B: Tank command API and the window | #224, #225 | `/chats`, with receipts on each turn | The cheap ladder doesn't reach chats (section 3, Tank) |
| COMMAND-1 C: workers take builds from the window | Partly: `worker.build` exists (`tank/command.py:503`) | Workers run on Boston (#222) | Never proven: no build has gone from the window to a merged PR |
| **MOA-1: the Gemini points** (Mixture of Agents) | #228 (21 Oct) | The bench measures each mixture shape (`tank/bench.py:293`) | **Measured only, never switched on.** `moa_enabled` defaults to false (`tank/schema.sql:1526`), and no task turns it on |
| SKALA-2: approval safety | #223 | Approve all ready, rollback and confirmation | Nothing. Built |
| MARKET-DOCS-1: feed Market Lab documents | **Never built** | Market Lab's upload saves files to the vault only (`workspace/app/market-lab/plugin-actions.ts:71`) | Read the files, learn from them, cite them, forget them |
| The nightly cycle and morning report | Partly | The bench loop (`tank/bench.py:347`) and the nightly gold intake (#179) | **The morning report was never built.** Nobody has confirmed the bench runs live |

---

## 3. Product by product

### Tank: the one door, the ladder and the receipts
- **Merged:**
  - #334 (26 Oct): closes tenant leaks and serves the code-and-cache ladder;
  - approved code skills first, then the cache (per tenant), then Luna (`tank/schema.sql:1697–1726`);
  - batch receipts (`tests/test_tank_batches.py`).
- **Broken:**
  1. **Chats get none of the ladder.** `command.turn` keeps `cache_scope 'none'` (`tank/schema.sql:1046`), and the ladder seed doesn't touch it.
  2. **Chat turns never reach savings.** A turn is routed without a job (`tank/command.py:376`), and the savings report drops any row with no job ("No linked job", `tank/proof.py:271`). Turns are also filed as "Other work", because the agent is `orchestrator`.
  3. **The Gemini mixture (MOA-1) is off everywhere** (table above).
- **Left:**
  - link each chat turn to a job, and give `command.turn` the tenant cache;
  - when the bench proves a mixture cheaper, the founder switches it on for that task.
- **Done when:** a test client asks the same question twice in `/chats`. The second answer comes from the cache at $0, and both turns appear in the client's savings.

### Skala: skills and approvals (founder only)
- **Merged:** SKALA-2 (#223), the skills library (#197), the 30-day cost per call (#201).
- **Left:** the control panel built to frame 10:115, which includes Approve all. It's on `codex/control-panel`, not merged, so it needs a review against the frame first.
- **Done when:** the founder approves real pending skills from the live control panel.

### Base: verified business lists
- **Merged:**
  - #339 (27 Oct): CSV upload and verified CSV export on `/base`. It also fixes the platform-tenant read in the context report.
  - #352 (27 Oct): duplicate reference licences, and load failures shown.
- **Open:** `codex/base-atf-download` downloads the first ATF list only when the store is empty.
- **Proof so far:** the builder's own screenshots in `tests/base_proof/`. The #339 note says "Real signed-in proof remains blocked on test access."
- **Not checked:** the `/base` page against Figma C5 (7:221). That export is on branch `docs/go-live-list` only, so the builder couldn't see it.
- **Left:**
  1. merge the C5 export to main;
  2. match `/base` to it;
  3. run one real ATF state for a test client;
  4. show the client the cost of that run against Apollo, from the founder's invoices. Nothing is built for this yet, and the control panel says "No measured Apollo comparison yet." (`workspace/app/control/view.tsx:55`)
- **Done when:** a test client uploads a list on base.tervory.com and downloads it verified, with a receipt.

### Tiger: price and stock watches
- **Merged:**
  - #335 (26 Oct) restores price reads: the browser keeps the page HTML for Tiger's price reader only (`agents/_brain/browser.py:533–537`). This fixes the 26 Oct break.
  - #348 (27 Oct) flags pages with no product name.
- **Missing:** alerts are stored and shown on the page (`agents/tiger/watch.py:89`), but **no email is sent.** There is no mail code in `agents/tiger` or `workspace/app/tiger`.
- **Not checked:** the page against any Figma frame. The PR doesn't mention one.
- **Left:** a Figma frame for the Tiger page, then the email alert.
- **Done when:** a test client watches 20 real product pages for 48 hours on tiger.tervory.com, and a real price change reaches them.

### Market Lab: market research
- **Merged:**
  - #336 (26 Oct): questions answered from stored feeds, with every fact cited. The page now reads the room's own Postgres records (`workspace/app/market-lab/load.ts:11`).
  - #349: source pages.
  - #350: cited warnings, plus learning from outcomes per tenant.
- **Missing:** documents never feed its answers (MARKET-DOCS-1, table above).
- **Not checked:** the page against any Figma frame.
- **Left:** MARKET-DOCS-1, and a Figma frame for the page.
- **Done when:** a test client gets a cited brief on market-lab.tervory.com, and every link opens its source.

### Rig: parts finder and quotes for stores
- **On main:** the widget still says "Prices shown are sample data" and "SAMPLE DATA" (`agents/rig/rigbox/quotes/widget/tervory-rig.*.umd.js`).
- **Open:** `codex/rig-works`, "Complete Rig store onboarding and email quote delivery" (43 files), not merged.
- **Left:**
  1. review and merge `codex/rig-works`;
  2. remove every sample-data line;
  3. one test store uploads its own CSV;
  4. a shopper sends a quote, and the store gets the email.
- **Done when:** a test store receives 3 real quote emails from its own test page.

### Tisan: websites for clients
- **On main:** the page's chat form does nothing (`workspace/app/tisan/tisan.tsx:508`, `onSubmit` only calls `preventDefault`). There is no brain.
- **Left:** request, brief, build, preview link, one revision, hand-over. Then Tisan learns from each approved Figma-to-page pair (the gold export, #176, already exists).
- **Done when:** a test client opens a working preview site built from their own request.

### Radix: code scanning (sealed)
- **On main:** the sealed scanner with offline OSV data. No Radix code has merged since 24 Oct.
- **Missing:** a route a client can reach. Radix still has only the Ghost corridor.
- **Left:** a client upload (repo or git bundle) and the report page.
- **Done when:** a test client uploads a repo and downloads a correct report.

### Zenas: civil legal research and drafting
- **On main:** zenas.tervory.com opens Moot (#303). The answers path and release UI landed on 24 Oct (#273, #274, #280).
- **Open:** `codex/zenas-backend` (PR #326, last changed 25 Oct), not merged. It restricts active Zenas back-end routing to Boston: `TANK_REGION` must be `us-east`, or Zenas fails at startup.
- **Left:** merge #326 once reviewed, then run the US test end to end from `docs/ops/ZENAS-LIVE-SUNDAY.md` part 5. ZA stays stopped.
- **Done when:** a released US answer shows to a test client, and a criminal question is refused.

### Autumbra: protection for client sites
- **Merged:** #345 (27 Oct): shield apply, undo and approve, never-block, and the owner email.
- **Reverted:** #337 on 26 Oct (#343), because it merged before passing review.
- **Proof so far:** fixture tests only.
- **Left:** dogfood on Tervory's own sites first.
- **Done when:** on our own site, a test attack is shielded and undone with one tap, and the receipt reaches the founder.

### Workspace: dashboard and control panel
- **Live:** down (section 0).
- **Left:** review `codex/dashboard` and `codex/control-panel` against frames 12:2 and 10:115 (`docs/figma/`), merge, then check them in the founder's browser.

---

## 4. Across all products
- **Memory and brains:** only Base and Rig have a Hermes brain. The clone to the other agents (21 Oct, day 2) was never built.
- **The ladder:** served for Base and Zenas tasks (#334). Not for chats.
- **Shadow learning:** shadow runs exist in Tank (`tank/main.py:1292`). Each agent's shadow results and the morning report are not built.
- **Figma:** 8 product PRs merged on 26–27 Oct (#335, #336, #339, #345, #348, #349, #350, #352). None of them mentions a Figma frame. Each page needs its frame approved and the page matched before it counts.
- **The merge check** (section 0): #351 removed the full suite from the merge gate. A Workspace build needs to come back.

## 5. Order of work: parallel lanes
These run at the same time, one thread each:
1. **Now (Grok):** redeploy the Workspace with #355, then confirm every host opens in the founder's browser.
2. **Tank:** chats on the ladder and in savings.
3. **Base:** the C5 export to main, `/base` matched to it, `codex/base-atf-download`, one real state.
4. **Rig:** review `codex/rig-works`, then strip the sample data.
5. **Workspace:** review `codex/dashboard` and `codex/control-panel` against Figma.
6. **Market Lab:** MARKET-DOCS-1.
7. **Tiger:** a Figma frame, then the email alert.
8. **Zenas:** review #326.

After those: the brain clones, Radix's client route, Tisan's build flow, the morning report, and switching on any mixture the bench proves.

## 6. Waiting on the founder
| Branch | What it is | State |
|---|---|---|
| `codex/base-atf-download` | Base: first ATF list only when empty | Open |
| `codex/rig-works` | Rig: store onboarding and quote email | Open, needs review |
| `codex/dashboard`, `codex/control-panel` | The 12:2 and 10:115 rebuilds | Open since 26 Oct, need a check against the frames |
| `codex/zenas-backend` (#326) | Zenas back end | Open since 25 Oct |
| `codex/sec-code` (#329) | Code security | Open; its Dockerfile install lines were still unpinned at the last review |
| `docs/go-live-list` | Figma C5 export, go-live list, break points | Superseded by this file, apart from the C5 export, which should go to main |
