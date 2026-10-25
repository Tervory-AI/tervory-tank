# The real build list: make every page work

> Written by Claude, Sun 25 Oct 2026, 14:25 PT, from a check of every page in the founder's own signed-in browser. **This replaces `BUILD-LISTS-2026-10-25.md`.**
>
> **What counts as done (no exceptions):**
> - the page is opened signed in on its own domain;
> - every button does its real job;
> - every number is real (or the page says plainly that there's nothing yet);
> - there's no demo data, no build codes (like "GHOST-1") and no model names on client screens.
>
> Claude checks it in the founder's browser, and the founder sees the screenshot, before anything is called done. **Tests passing and a deploy finishing are not "done".**

## What the founder's browser showed (25 Oct, 14:20 PT)
| Page | Today |
|---|---|
| Chats | **Works.** But it lists model names and prices to clients |
| Dashboard (home) | Loads. The savings numbers are real; credits show a dash |
| Base, Tiger, Market Lab, Tisan, Radix, Tank, Skala | **Demo data** from #306, this morning |
| Rig (admin) | Test catalogue; no real store |
| Zenas | Says "South Africa" though ZA is stopped. No matters |
| Control panel | Health, case study and Ghost "unavailable" or "not linked"; buttons carry build codes; "Paying clients 8" is wrong |

## Step 1: take the demo data off (today)
- [ ] **#325, the restore.** The founder merges it once CI is green. Claude then re-checks all seven pages in the founder's browser, and this table gets a new row per page showing what the *real* page does.

## Step 2: fix the pages, most important first
Each line is one PR (**Codex** builds; **Grok** deploys and runs any live data) followed by Claude's browser check.

1. **Chats (the one working product).**
   - Hide model names and prices from client accounts; founders still see them.
   - The "Model" picker is founder-only.
   - **Check:** as a client, no model name appears anywhere.
2. **Dashboard.** Credits left shows the real balance from billing, or "No credits bought yet". Jobs and savings link to the real work. **Check:** every number opens its source.
3. **Control panel.**
   - Wire up, or remove, every section showing "unavailable" or "not linked".
   - Remove all build codes from the screen.
   - "Paying clients" counts only real paid Stripe customers.
   - **Check:** no build code, and no number that can't be opened to its source.
4. **Zenas.**
   - Show the US region (Boston), since ZA is stopped.
   - "Ask Zenas" gives a cited answer to a real question.
   - A matter can be opened and saved.
   - **Check:** ask one US civil question live and save it as a matter.
5. **The seven squad pages, after step 1.** One line per page, each with one real job, written after Claude has seen what the real page does. (Placeholders until then, so nothing is guessed.)
6. **Rig.**
   - The store's own catalogue upload works from the admin page.
   - The test catalogue is removed from the live admin.
   - **Check:** upload one real CSV and search it.

## Step 3: security, alongside (doesn't wait for the pages)
1. **Grok:** patch PHP, Node and Python on the servers, pin Redis, and confirm nothing is exposed (before and after, in the log).
2. **Codex:**
   - fix the 4 open dependency alerts (2 high);
   - pin and hash-check every package and base image;
   - add secret scanning in CI.

## Rules for this list
- **One line at a time per builder.** The next line starts only after the last one passes the browser check.
- **No new features or pages** until steps 1 and 2 are done.
- **A line that can't be finished** says so in plain words. It is never shipped with demo data or a build code in its place.
