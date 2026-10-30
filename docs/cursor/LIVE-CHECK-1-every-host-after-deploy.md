# LIVE-CHECK-1: open every product page after each deploy, like the founder does

> Written by Claude, 27 Oct 2026, 16:20 PT, at the founder's request. Plan: `docs/build/BUILD-PLAN-2026-10-27.md`.
>
> **Why this exists.** On 27 Oct, #341 passed every merge check, including the Workspace build. Every product page still showed "Application error" live from 07:05 to after 09:16 PT. The cause was a runtime error in the browser (Clerk 7 removed `<SignedIn>`).
> - The build can't see a runtime error.
> - The 10-minute watchdog (`.github/scripts/watchdog.py`) can't see it either: the page still returns HTTP 200.
>
> Claude found it only by opening the pages in the founder's browser. This check does that automatically, with **no model calls** (founder rule 4).

## Rules (founder)
1. **Product first.** No sign-in work, pricing, keys, Stripe, credits or spend caps.
2. **Figma first.** This check adds no page and no copy.
3. **No sample or demo data on a live screen.** This check is how that rule gets enforced.
4. **No model calls where code can do the job,** and none to check work.
5. **Use what exists and is free; never recode it.** Use Playwright (already in the repo and in CI), not a home-made browser.
6. **Never type, see or create secrets.** Secrets are added by the founder, by name only.
7. **The founder merges.** A thread that deviates from this brief is deleted with its work.

## What to build
1. **One script, `ops/live_check.mjs`, using Playwright Chromium.**
   - It opens each host signed out:
     - app.tervory.com
     - base.tervory.com
     - tiger.tervory.com
     - market-lab.tervory.com
     - tisan.tervory.com
     - radix.tervory.com
     - zenas.tervory.com
     - protect.tervory.com
     - rig.tervory.com
     - skala.tervory.com
     - tank.tervory.com
   - Take the list from `workspace/lib/product-hosts.ts` plus rig.tervory.com, so a new host is checked without editing the script.
   - Signed-out hosts redirect to sign-in. The check is that whatever page loads, loads without error.
2. **A host fails if any of these happen:**
   - The page shows "Application error" or "client-side exception", or the browser console logs an uncaught exception.
   - The response is 500 or above, or the page doesn't finish loading within 30 seconds.
   - **The visible text breaks rule 3.** It contains any of:
     - `sample data`, `SAMPLE DATA`;
     - `Fixture`, `[TEST]`;
     - `Demo price`;
     - `CVE-2024-0000`;
     - `00000000-0000-0000-0000`.

     Keep this list in one file (`ops/live_check_banned.txt`) so the founder can add to it.
3. **It saves a screenshot of every host** (at 1440 and 375 wide) as the run's artifact, so the founder can look without opening anything.
4. **When it runs:**
   - As a second job in `.github/workflows/deploy-on-merge.yml`, after the deploy job succeeds. Wait for Coolify to report the apps healthy, then check.
   - And every 30 minutes on a schedule, in its own workflow `live-check.yml`.
5. **On a failure:** the job fails, red on main, naming the host and the reason. It also opens one GitHub issue titled `Live check failed: <host>`, or updates the open one, with the screenshot linked. No email or Slack; that's a later decision.
6. **Signed-in pages (step 2, after the founder adds the secrets):**
   - The founder creates one test user in Clerk with no client data and adds two repo secrets by name: `LIVE_CHECK_EMAIL` and `LIVE_CHECK_PASSWORD`.
   - Use Clerk's documented testing support for automated sign-in. Don't solve captchas.
   - With those set, the script also opens:
     - app.tervory.com/
     - /chats
     - /base
     - /tiger
     - /market-lab
     - /rig/admin
     - /zenas
   - It applies the same failure rules.
   - Without the secrets, this step is skipped with a notice. It is not a failure.

## How to run Chromium in CI
Copy the `savings-page` job in `.github/workflows/ci.yml`:
- `ubuntu-latest`;
- Playwright `1.64.1`;
- the npm and browser caches;
- `playwright install --with-deps chromium` when no system browser exists.

Don't use an `ubuntu-26.04` runner: the removed tisan-site workflow failed there at the Chromium install on every run.

## Files you may change
- new `ops/live_check.mjs` and `ops/live_check_banned.txt`;
- new `.github/workflows/live-check.yml`;
- `.github/workflows/deploy-on-merge.yml`, to add the second job only;
- new `tests/test_live_check.py`, which runs the script against a local test server serving one good page, one "Application error" page and one page with banned text, and checks the result for each.

Nothing else.

## Done when
1. The test passes in CI.
2. On the first run against the live hosts, the founder sees the run's screenshots and the pass/fail list.
   - On 27 Oct it will fail on rig.tervory.com (the Archon catalogue), zenas.tervory.com ("Fixture … [TEST]") and protect.tervory.com ("CVE-2024-0000").
   - That is correct. Those pages break rule 3 until the cleanup lane removes the fixtures.
3. One draft PR with the proof: what changed (file and line), the exact commands run and their results, and the screenshots. Then stop. The founder merges.
