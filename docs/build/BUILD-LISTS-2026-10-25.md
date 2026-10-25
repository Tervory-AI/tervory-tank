# Build lists: every product, split between Codex and Grok

> Written by Claude, Sun 25 Oct 2026. One list per product. **Autumbra is built in its own session** (see the end). The other nine are built here.
>
> **The rule for this round:** each product ends with **one real job working for a real customer, start to finish, on its own `<product>.tervory.com`**. No sample data on a customer's screen. Customers bring their own connections (their CSV, their accounts); **nothing waits on the founder's keys**.
>
> **The split:**
> - **Codex** builds features and tests.
> - **Grok** does security on the servers, deploys, live data runs, and proves each job live.
> - Firearms-related data work goes to **Grok**.
>
> **Every PR follows the same rules:**
> - draft until CI is green;
> - stay inside the files named;
> - no secrets;
> - the founder merges;
> - the PR ends with the exact live proof.

## 0. Security first (all products, before any feature work)
After the Python, PHP and Node compromises last week, these come before anything else.

**Grok (servers):**
- [ ] **S1 · Host patching.** List the PHP, Node, Python and Docker versions on Boston (host and every container) and patch to the latest patch release of the same version. Never replace the system Python. Report before and after.
- [ ] **S2 · Coolify.** Confirm its current version, that ports 8000, 6001, 6002 and 8080 are still blocked from outside, and that access logs are on. The founder turns on 2FA.
- [ ] **S3 · Redis.** Pin a patched 7.4.x by tag and digest in both compose files, including Chatwoot's Redis.
- [ ] **S4 · Exposure check.** No service outside Traefik listens on a public address. Run `ss -tlnp` and `docker ps` port maps, and save the output in the log.

**Codex (code):**
- [ ] **S5 · Dependency alerts.** Fix the 4 open alerts on `tervory-tank` main (2 high) with pinned versions, one PR.
- [ ] **S6 · Pin everything, every project.**
  - Python: `requirements.lock` installed with `--require-hashes`.
  - Node: `npm ci` with a committed lockfile and `--ignore-scripts` where possible.
  - Docker base images: pinned by `@sha256`.
  - A CI check fails any unpinned install.
- [ ] **S7 · Secret scanning in CI.** gitleaks (Radix already bakes it in) runs on every PR and blocks a merge on a hit.
- [ ] **S8 · Supply-chain watch.** A nightly job reads the open vulnerability sources (OSV, GitHub advisories, the government's list of actively exploited vulnerabilities) against every lockfile, and opens one PR per fix. This is Autumbra's first feed; share the code.

---

## 1. Tank: the cost router and receipts
**First customer job:** a client asks a question in the Workspace and gets the answer, with a receipt showing what it cost and what it would have cost.
- **Today:** chats and receipts work (proven 21 Oct), along with the proof and savings pages (`/tank/proof`) and the ledger.
- **Codex:**
  1. Match the **receipt (C3)** and **savings (C4)** screens to Figma. Real numbers only; any empty state says "No work yet".
  2. A client-facing receipt for every finished task, linked from the chat.
  3. A **"Check answers"** page: rename the founder's "gold" page (`/skala/gold`) and its menu item, keeping the same function.
- **Grok:** prove it live. A test client runs 10 real questions; screenshot the receipts and savings and post them.
- **Done when:** a signed-in test client sees real receipts and savings that match Figma C3 and C4.

## 2. Skala: the skills library and approvals (founder only)
**First job:** the founder approves new skill versions in one pass and sees what changed.
- **Today:** the library, "Approve all ready" and the checking page exist.
- **Codex:**
  1. Match **F4 (Skala)** and **F5 (checking)** to Figma.
  2. Show each skill's last test result and its cost per run in the row.
- **Grok:** live check on skala.tervory.com: founder-only, and signed-out visitors go to sign-in.
- **Done when:** the founder approves 3 real pending skills on the live page.

## 3. Base: verified business lists
**First customer job:** a client uploads a list (or names a state and category), and gets back verified contacts with sources and a receipt.
- **Today:** the Base room and brain exist, with the AmmoSync case-study data. The squad page comes back with #325.
- **Codex:**
  1. After #325, match the **Base agent page (C5)** to Figma: Ask Base, Upload list, the jobs table, and "What Base has learned".
  2. CSV in, verified CSV out, with each row's source link and a checked date.
- **Grok (firearms-adjacent data):**
  1. Run one real state end to end for a test client.
  2. Publish the counts: rows in, verified, failed and why.
  3. Respect robots.txt. No captcha solving.
- **Done when:** a test client downloads a verified list from base.tervory.com, with receipts.

## 4. Tiger: price and stock watches
**First customer job:** a client adds product links to watch, and gets an email or panel alert when a price or stock level changes.
- **Today:** the room exists, but **it has no data yet**. Its page comes back with #325.
- **Codex:**
  1. A watch list: add a URL, or upload a CSV of URLs.
  2. A check schedule per watch.
  3. A change history and alerts (email plus panel), with per-tenant limits.
  4. Tests on saved test pages.
- **Grok:**
  1. Run 20 real public product pages for a test client for 48 hours.
  2. Report checks run, changes caught and failures.
- **Done when:** a test client gets a real alert from a real page change on tiger.tervory.com.

## 5. Market Lab: market research
**First customer job:** a client asks a market question and gets a cited brief built from the feeds.
- **Today:** the room, R2 storage and documents exist. **Live feeds are not yet fetching** (open issue #29).
- **Codex:**
  1. Finish #29: real fetching for the listed public feeds, with history backfill.
  2. A brief page where every number links to its source document.
- **Grok:**
  1. Run the feeds for 24 hours.
  2. Report counts per feed and failures.
- **Done when:** a test client receives a cited brief on market-lab.tervory.com, with every link opening its source.

## 6. Rig: parts finder and quotes for stores
**First customer job:** a store uploads its own catalogue CSV, and a shopper on that store's site searches, builds a setup and sends a quote request that reaches the store.
- **Today:** phase 1 is merged and live: the widget, feeds (every format and currency), quotes, the 3D engine and the forge (TRELLIS off). It runs on test data. **The founder isn't handing over distributor keys, so the store's own CSV is how Rig goes live.**
- **Codex:**
  1. The store's onboarding page at rig.tervory.com: upload a CSV, map its columns (Rig suggests them, the store confirms), preview, publish.
  2. The embed snippet for the store's site.
  3. Quote requests delivered by email to the store, while Odoo stays off.
- **Grok:**
  1. Load one test store's real catalogue CSV (one the founder approves) and embed the widget on a test page.
  2. Run 10 shopper searches and 3 quotes, and screenshot each step.
- **Done when:** a test store receives 3 real quote emails from shoppers on its own test page.

## 7. Tisan: websites for clients
**First customer job:** a client describes a small business site, and Tisan builds it on its own preview link, checks it and hands it over.
- **Today:** the room and the Next.js site template exist, and the Playwright site gate runs in CI.
- **Codex:**
  1. Request form, brief, build, preview link, client feedback, revision, hand-over.
  2. Every site passes the template checks: speed, accessibility, links, no secrets.
- **Grok:**
  1. Host previews on a separate preview domain, with no client data on Boston's main apps.
  2. Build one real test site end to end.
- **Done when:** a test client opens a working preview site built from their request, and asks for one change that gets made.

## 8. Radix: code scanning (sealed)
**First customer job:** a client hands over a repository (as an upload or git bundle) and gets a plain-English report of what to fix.
- **Today:** the sealed room has Gitleaks, Semgrep and offline OSV data, and the scan job exists.
- **Codex:**
  1. The upload page at radix.tervory.com.
  2. The report page: findings by severity, each with file, line and fix, plus a downloadable PDF.
  3. Rebuild the OSV data nightly so it never goes stale.
- **Grok:**
  1. Scan `tervory-tank` and `tervory-rig` main as the first real job, and post the summary.
  2. Report any critical finding to the founder at once.
- **Done when:** a test client uploads a repo and downloads a correct report. Our own repos have no critical findings open.

## 9. Zenas: civil legal research and drafting
**First customer job:** a US test client asks a civil question, gets a cited answer and draft, a reviewer releases it, and the client sees the released version.
- **Today:** the room, scope gate (no criminal), US library, Z12 precedent checks, drafting, deadlines, Matters and Review pages, and the Moot text court (MOOT-1a) all exist. zenas.tervory.com opens on Moot.
- **Codex:**
  1. Point zenas.tervory.com's home at the Zenas page (`/zenas`), with Moot at `/moot`. It's one line in `workspace/lib/product-hosts.ts`.
  2. The client's view of a released answer.
  3. Match the Matters and Review pages to Figma where frames exist.
- **Grok:** run the US end-to-end test from `docs/ops/ZENAS-LIVE-SUNDAY.md` part 5, with the founder as the test reviewer. **ZA stays stopped,** by the founder's decision.
- **Done when:** a released US answer is visible to the test client on zenas.tervory.com, and a criminal question is refused.

---

## 10. Autumbra (built in the new session)
Start from the code already on main (#281–#304: the threat form between the two halves, Watch and Enforce, the Shields board and fixes as PRs, all switched off), not from Gemini's scripts. Build in this order:
1. **The never-block list and IP check.** Never block the client's own IPs, payment providers or Cloudflare. The IP must appear in the raw log. Plain rules decide first, with the AI as a second opinion. Actions per hour are capped.
2. **Reversible shields, applied immediately:** block an IP, turn on a WAF rule, rate-limit a path, revoke sessions. Each gets a health check, an automatic Undo if the site breaks, a one-tap Undo, and a receipt.
3. **Code fixes arrive as a ready PR** that the client approves with one tap. **They never auto-merge.**
4. **Signed webhooks only** (Cloudflare and Google signatures). No keys in code. The AI engine is never on a public address.
5. **Public, legitimate threat sources only.** No dark web. "Red team" tests only the client's own systems, with written permission.
6. **The small-business tier:** connect Cloudflare and Google Workspace. Logs are read and deleted, never stored, and the copy says exactly that.
7. **Dogfood on our own sites first,** with S8's supply-chain watch as its first feed.

**Done when:** on our own sites, a test attack is shielded in seconds and undone in one tap, and the receipt reaches the founder.
