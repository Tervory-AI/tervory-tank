# SENTINEL-1: a permanent onsite agent that only solves problems

> Written 21 Oct 2026. Founder: "a permanent onsite agent working the site to check for security issues and to assist at all times with any other technical issues. It does nothing else but solve issues it is directed at."
>
> Sentinel is its own squad member, with **its own box** in the AGENT-1 shape: its own Hermes Agent brain, sandbox, browser and memory, sharing nothing. It is the eighth tile on the founder control panel.

**Files you may change:**
- new `agents/sentinel/` (room, compose, gold_sources);
- `tank/` (route registration only);
- `workspace/app/admin/` (the Sentinel panel only);
- `docs/cursor/ROOMS.md`;
- tests.

1. **It watches, always:**
   - uptime and response time of app.tervory.com, za.tervory.com, tervory.com and each room's health;
   - errors in the Workspace and Tank logs (counts and patterns, never secret values);
   - certificate expiry and DNS;
   - failed deploys and red CI on `main`;
   - the security headers on the public sites;
   - Radix scan results for new findings.
2. **It solves only what it is pointed at.** An issue reaches it in one of three ways: its own alert, the founder pressing "Look" on the control panel, or a message in the window ("Sentinel, the login page is slow"). For each issue it:
   - reproduces the problem in its own browser and sandbox;
   - finds the cause from logs, recent deploys and the code;
   - writes the fix as a brief, which goes to the workers as a PR with a receipt, or does a safe action it is allowed (re-run a failed deploy, restart a crashed room);
   - reports back in plain words: what broke, why, and what it did.
3. **Limits:**
   - Read-only on production data.
   - It never changes keys, settings or the database, and never merges.
   - Anything beyond re-running a deploy or restarting a room needs the founder's OK.
   - Human checks are never solved.
4. **Learning:** every solved issue is saved to Sentinel's own memory with the cause and the fix, so a repeat is solved faster. It also becomes a gold example (`sentinel:incident:{YYYY-MM}`).
5. **Receipts:** every investigation shows its steps and cost through Tank like any agent.

## Done when
CI green. Tests:
- an injected failing health check raises an issue;
- "Look" starts an investigation;
- a fix becomes a worker brief, not a direct change;
- a production write is refused;
- a solved issue is remembered and found again on the next similar alert.
