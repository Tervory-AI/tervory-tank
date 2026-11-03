# Milestones, tests and prompts: Wed 28 Oct to Sun 1 Nov 2026

Written by Claude, Tue 27 Oct, 20:10 PT. Claude is unavailable until Sunday, so this runs without Claude.
- The plan: `plan/BUILD-PLAN-2026-10-27.md`.
- Tonight's jobs 1 to 8: `plan/TONIGHT-2026-10-27.md`.
- ZA Zenas: `plan/GROK-ZA-ZENAS-2026-10-27.md`.

**How it runs without Claude:**
1. Builders give their proof in the PR.
2. The machine checks run on every PR.
3. The live page check runs after each deploy, once job 7 is merged.
4. **The founder runs each milestone's test in his own browser.** A milestone passes only when its test passes. A failed test goes back to the same thread with the screenshot.
5. **There is no review agent.** Risky PRs (secrets, sign-in and tenant isolation, seals, money, deleting data) wait for Claude on Sunday.

---

## The milestones

| When | Milestone | Founder's test (in his own browser) | Pass when |
|---|---|---|---|
| **Tue 27, tonight** | M0: backups on (job 1) | Open Grok's report | Today's backup file is in R2; restored row counts match live; restore time noted |
| **Wed 28** | M1: Rig email (job 2) | Send a quote from the test store's widget | The email is in your inbox with the same reference |
| **Wed 28** | M1: Base reference (job 3) | Set `BASE_REFERENCE_FILE_URL` in Coolify; open base.tervory.com | Reference licences show the file's date; a new campaign lists the smallest state first |
| **Wed 28** | M1: Tank chat cache and savings (job 4) | Ask the same question twice in /chats | The second answer costs $0; both turns show in your savings; graduation shows 99% / 200 |
| **Wed 28** | M1: no sample data (jobs 5, 6) | Open rig.tervory.com, /rig, zenas.tervory.com, protect.tervory.com, Market Lab feed review | No Archon, Fixture, [TEST], CVE-2024-0000, ThreatPayload or internal ids |
| **Wed 28, first** | M1: **your own chat builds (prompt D), the founder's priority** | In /chats, ask for a small change; confirm the card | The worker's PR, its checks and its result show in the same thread. From then on, builds are asked for in your own window |
| **Wed 28** | M1: live check (job 7) | Open its first run on GitHub | Screenshots and a pass/fail list for every host; all pass once 5 and 6 are merged |
| **Thu 29** | M2: ZA Zenas (Grok prompt) | Sign in as a ZA client; ask one civil SA question on zenas.tervory.com/zenas | A cited answer from the SA library with its receipt; a criminal question is refused; the ZA backup is in the ZA bucket |
| **Thu 29** | M2: Zenas source links (prompt A) | Ask a US question | Every cited law opens its source |
| **Thu 29** | M2: Market Lab documents (prompt B) | Upload one PDF report on market-lab.tervory.com; ask a question it answers | The answer cites the file and page; deleting the file removes it from answers |
| **Fri 30** | M3: Tiger email (prompt C) | Watch 5 real product pages; wait for a change | The alert email arrives; the 48-hour, 20-page run starts |
| **Fri 30** | M3: Custom Nation on Rig (job 8) | Custom Nation's test page | The Custom Nation skin, the real catalogue, the privacy notice above the button, and the quote email in Custom Nation's inbox |
| **Fri 30** | M3: Base one real state (Grok, prompt E) | Download the state's verified CSV | Rows with sources and check dates; cost per verified record shown |
| **Sat 31 to Sun 1** | M4: founder weekend | Control panel inventory and decisions; homepage frames; box for the brains; **Rig "no published catalogue" state in Figma** for rig.tervory.com and app.tervory.com/rig (the founder writes the words) | Decisions written down for Sunday; the Rig state frame approved in Figma |
| **Sun 1** | Claude back | Claude checks every milestone against this table in your browser, then writes the next week's plan | |

**Rules of the week:**
- Nothing in M2 waits for M1, unless it says so.
- The free-tool swaps and the brain clones start only after M1 to M3 pass (recommendation 4).

---

## The rules block (inside every prompt)

```
RULES (founder, non-negotiable):
1. Product first. No sign-in work, pricing, keys, Stripe, credits or spend caps. Exception: Rig Locate checkout (test-mode payment, sandbox supplier order) is built, and runs only when a store switches it on.
2. Figma first. Nothing new goes on any page without an approved Figma frame, matched to the character. Do not add text, buttons, empty states or error wording. If you need one, stop and report it.
3. No sample, demo or fixture data on any live screen, and no made-up copy.
4. No model calls where code can do the job, and none to check work.
5. Use what already exists and is free; never recode it.
6. Never type, see or create secrets. Coolify settings are handled by name only; the founder fills in values.
7. The founder merges. Never push to main. One draft PR, then stop.
8. No SQL on production data and no permanent live-data change without the founder's OK.
Done means the founder sees it work in his own browser. Tests passing is not done.
Deviate from this brief and the thread is deleted with its work.
9. DO NOT ASK QUESTIONS. Follow these instructions exactly as written. You are pre-approved to do everything in this brief except merging. If something blocks you (a missing setting value, missing Figma text, a file you may not change), stop at that point and report exactly what is missing. Do not ask, do not guess, do not work around it.
10. A separate review thread checks your PR against this brief. Fix everything it lists, on the same PR, without arguing.
11. Your PR must show: what changed (file and line), the exact commands you ran and their results, and screenshots of the founder's test. Nothing claimed without that proof.
```

---

## Prompt A (Codex): Zenas, keep law source links in answers

```
[paste the rules block]
JOB: #326's branch was deleted unmerged. Claude restored it on 27 Oct as branch restore/zenas-backend-326 (commit 75098a9).
- Take ONLY commit 7c3cc67, "Retain verified law source links in answers and saved memos" (agents/zenas/core/citation_sources.py and the files it touches), onto a new branch from main.
- Do NOT take c433fca, "Restrict active Zenas backend routing to Boston". ZA Zenas now runs on its own box (founder, 27 Oct).
- Also, schedule the nightly law runner (agents/zenas/pool/nightly.py; today nothing calls it) with Coolify's scheduled tasks, once a night on each region's box.
- Put the existing footer line "legal information, not legal advice" (workspace/app/zenas/view.tsx:478) on each answer, memo and draft output as well. Same words, no new text.
Tests offline. Run the Zenas tests.
DONE WHEN: the founder asks a US question on zenas.tervory.com/zenas, and every cited law opens its source; the answer carries the notice.
```

## Prompt B (Codex): Market Lab documents, and the missing vault routes

```
[paste the rules block]
JOB: every product's file, plugin and secret screen calls /v1/vaults/... (workspace/lib/tank.ts:502-613: plugins, secrets, files, links, connections). Tank has no /v1/vaults route at all, so these calls return 404 (tests/base_proof/real-job-output.txt:24). Market Lab's document upload therefore fails.
1. Build the /v1/vaults routes Tank is missing, matching exactly what workspace/lib/tank.ts sends and expects. Files go to that agent's own R2 bucket; secrets are sealed with tank/vault.py seal(); every route is tenant-scoped and squad-checked.
2. Then MARKET-DOCS-1 (docs/cursor/MARKET-DOCS-1-feed-market-lab.md):
   - an uploaded PDF, XLSX or CSV is read into passages with existing free libraries (no model);
   - Market Lab's answers cite the file and page;
   - deleting the file removes its passages.
Tests offline, including another tenant never seeing the file.
DONE WHEN: the founder uploads one real PDF report on market-lab.tervory.com, asks a question it answers, and the answer cites the file and page. After he deletes the file, the answer no longer uses it.
```

## Prompt C (Codex): Tiger email alerts

```
[paste the rules block]
JOB: Tiger stores alerts but never emails them (agents/tiger/watch.py:89; no mail code in agents/tiger or workspace/app/tiger).
- Send each confirmed price or stock alert by email to the tenant's alert address. Use the same SMTP approach Rig uses (agents/rig/rigbox/reserve.py SmtpMailer, EmailHandoff in senders.py), with Tiger's own SMTP_* setting names. Grok creates them by name; the founder fills in the values.
- The email text: use only the wording already shown for that alert on the Tiger page. If an email needs other words, stop and report.
- Respect the existing alert preferences (#335). Send one email per alert, never repeated, and retry on failure.
Tests offline with a local mail catcher.
DONE WHEN: the founder watches 5 real product pages, and when one changes, the alert email reaches his inbox.
```

## Prompt D (Codex): the window builds (workers take work from /chats)

```
[paste the rules block]
JOB: in app.tervory.com/chats, a confirmed "build" card puts a task on Tank's build queue (tank/command.py:501-682: POST /v1/command/build, GET /v1/command/builds/next, progress and follow-ups). Tervory's workers never read that queue: nothing in workers/ calls /v1/command, so they still take GitHub issues only.
- Make the workers (workers/service.py, workers/tank_status.py) poll GET /v1/command/builds/next with their existing worker key.
- Run the task exactly as they run an issue today.
- Post progress, the PR link, CI status and the result to /v1/command/builds/{id}/progress.
- Pick up follow-ups from the same thread on the same PR.
- Keep the GitHub "worker" label as a fallback.
- The workers never merge.
Tests offline against a local Tank.
DONE WHEN: the founder asks for a small change in /chats, presses Confirm, and sees the worker's PR link, its checks and its result appear in that same thread.
```

## Prompt F (Codex, Sunday, after Claude exports the frame): Rig, the "no published catalogue" state

Founder decision, 27 Oct 20:23 PT: tonight Rig shows nothing where there is no catalogue (job 5 follow-up); the proper wording comes from Figma afterwards. Claude exports the approved frame to docs/figma/ on Sunday before this runs.

```
[paste the rules block]
JOB: job 5 left Rig's pages blank where a store has no published catalogue. The founder has now approved the "no published catalogue" state in Figma, exported to docs/figma/ (see its SPEC.md).
- Build that state on rig.tervory.com (agents/rig/rigbox/page/v5/) and on app.tervory.com/rig (workspace/app/rig/), exactly as the export shows: FIXED text to the character, DATA text from the store's real catalogue only.
- Show it only when the store has no published catalogue. Change nothing else.
Tests offline: with no published catalogue, both pages show exactly the SPEC.md text and no Archon, sample or demo text.
DONE WHEN: the founder opens both pages for a store with no published catalogue and sees exactly the Figma state.
```

## Prompt E (Grok): Base, one real state

```
[paste the rules block]
JOB: after job 3 is merged and the founder has set BASE_REFERENCE_FILE_URL:
1. On base.tervory.com, as the AmmoSync tenant, start one campaign for the state with the fewest licences.
2. Let it finish. Respect each site's limits. No captcha solving.
3. Report rows in, verified, failed and why, plus cost per verified record from the page.
Do not change code.
DONE WHEN: the founder downloads that state's verified CSV with sources and check dates, and sees the cost per verified record.
```
