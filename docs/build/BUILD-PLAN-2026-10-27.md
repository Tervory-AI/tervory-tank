# Tervory build plan, 27 Oct 2026: the whole project, what is done and what is left

> Written by Claude on Tue 27 Oct 2026: first at 09:20 PT, extended at 13:10 PT to cover the entire project, and the tool map (section 8) added at 13:20 PT, all at the founder's request. **This replaces every earlier build list.**
>
> **What was planned** (every point traced in the appendix):
> - **Build Pack v2** (11 Oct, artifact "Tervory AI — Build Pack v2"): read in full.
> - **Build Pack v1** (`Tervory_AI_Build_Pack.pdf`): its per-product build orders, where v2 is silent.
> - **The Gemini blueprint** (*Tervory Architecture Blueprint.pdf*, Google Drive, 20 Oct): read in full.
> - **The repo briefs** for Rig, Autumbra, Moot and in-video shopping.
> - **The founder's later decisions.**
>
> **What is there:**
> - the code on `main` at `cb5d1cf` (#353, merged 12:18 PT);
> - the open branches;
> - the founder's own browser, checked at 09:05–09:16 PT and again at about 12:18–12:25 PT.
>
> **How to read a status:**
> - **Built:** the code on main does it.
> - **Part:** some of it is there, or it is there but switched off.
> - **Replaced:** our own code does the job instead of the named tool.
> - **Not started:** no code.
> - **Dropped or stopped:** the founder ruled it out or paused it.
>
> **Built means code, not done.** Nothing counts as done until the founder's live page does its job.

## The rules every builder follows (founder)
1. **Product first.** Nothing that isn't needed to make a product work live: no sign-in work, no pricing, keys, Stripe, credits or spend caps.
2. **Figma first.** Nothing goes on any site without an approved Figma frame, matched to the character. A thread that deviates, or botches a deploy, is deleted with all its work.
3. **No demo or sample data, and no made-up copy, on any live screen.** If a real source is missing, stop and report it.
4. **No model calls where code can do the job,** and none to check work.
5. **Savings is core.** Every finished job shows what it cost and what it would have cost.
6. **Done** means the live page matches Figma and does its real job in the founder's browser. Tests passing is not done.
7. **The founder merges.** Never type, see or create secrets. Never weaken a seal.
8. **Use what already exists and is free; never recode it** (founder, 27 Oct). Where a free, open-source tool does the job, use it. Our own code only fills the gaps no tool covers.

---

## 0. Live, now
- **09:05–09:16 PT:** every Workspace host was down ("Application error"). Clerk 7 (#341) removed `<SignedIn>`, which the shell still used.
- **12:18 PT:** after the fix (#355, merged 09:15), all nine hosts loaded in the founder's browser.

What they show breaks rule 3 in four places:
- **rig.tervory.com** shows the Archon Type B test catalogue ("Closed catalogue", "Market price").
- **zenas.tervory.com** shows one moot match: "Fixture Landlord v Tenant (SCA) [TEST]".
- **protect.tervory.com** (Autumbra) shows fixture receipts, including a made-up "CVE-2024-0000", plus internal words ("ThreatPayload", "ghost.threat.v1", "burn-on-fail"). The page always renders `PUBLIC_AUTUMBRA_FIXTURE` (`workspace/app/autumbra/page.tsx:3`, `:9`).
- **market-lab.tervory.com** shows raw internal series ids in its feed review table ("00000000-0000-0000-0000-000000000001:check_counts:total:AL").

The rest of what the pages show:
- **The dashboard** (app.tervory.com) still shows "Credits left" and "Waiting on you", both removed from Figma 12:2. "You saved" is a link, not an amount.
- **Base** says "There are no saved ATF licence rows in the platform reference." Main can't download the first ATF file. The fix was on branch `codex/base-atf-download` at 09:20 PT.
- **Market Lab:** 5 feeds are on with real stored data (EIA diesel, Census population, World Bank commodities, NWS alerts, NOAA climate). 10 are off: "blocked", "needs key" or "source could not be read".
- **Tiger, Radix and Tisan** load empty, with nothing watched, scanned or built.

**Merge check:** since #351 (27 Oct), the merge check is lint, the secret scan and Tank start only. A Workspace production build has to come back into it, so a page-breaking change can't merge again.

## 1. Why nobody could find the work
- **The 21 Oct two-day plan** lives only in the project (`plan/two-day-build.md`), never in the repo.
- **The 26 Oct go-live list, the break points and the Base C5 Figma export** sit on branch `docs/go-live-list`, never merged. On main, `docs/figma/` holds only frames 12:2 and 10:115.
- **Only one of the 26 Oct builder briefs** is on main (`ops/BUILDER-BRIEFS-2026-10-26/04-GROK-AUTUMBRA.md`).
- **The CORE lane** went CORE-1, 2, 2b, 2c (#218, #227, #234, #242). There is no CORE-3.
- **Two documents disagree with the code.** README.md:17 says secrets go in Doppler, but they are in Coolify settings. AGENTS.md rule 10 says "No run waits for a person" (see section 4).

**From now on** this file is the one plan: `docs/build/BUILD-PLAN-2026-10-27.md` in the repo, `plan/BUILD-PLAN-2026-10-27.md` in the project. Each brief links to it.

---

## 2. The whole project at a glance
196 planned points, traced one by one in the appendix:

| Area | Planned points | Built | Part | Replaced by our own code | Not started | Dropped or stopped |
|---|---|---|---|---|---|---|
| Tank | 31 | 6 | 17 | 5 | 3 | 0 |
| Skala | 6 | 4 | 2 | 0 | 0 | 0 |
| Workspace | 12 | 2 | 7 | 0 | 3 | 0 |
| Memory and agent brains | 6 | 0 | 4 | 0 | 2 | 0 |
| Squad contract and event bus | 5 | 1 | 2 | 0 | 2 | 0 |
| Base | 13 | 3 | 9 | 0 | 1 | 0 |
| Tiger | 9 | 3 | 2 | 3 | 0 | 1 |
| Market Lab | 11 | 0 | 9 | 2 | 0 | 0 |
| Radix | 10 | 0 | 7 | 0 | 3 | 0 |
| Tisan | 8 | 1 | 5 | 0 | 2 | 0 |
| Zenas | 9 | 0 | 6 | 1 | 1 | 1 |
| Rig | 40 | 28 | 10 | 0 | 1 | 1 |
| Autumbra | 27 | 10 | 16 | 0 | 1 | 0 |
| Infrastructure | 7 | 0 | 5 | 1 | 0 | 1 |
| Other planned products | 2 | 0 | 0 | 0 | 1 | 1 |
| **All** | **196** | **58** | **101** | **12** | **20** | **5** |

**Where the gaps are:**
- **Rig** is the most complete: the feeds, pricing, fits, widget, forge and 3D engine are built.
- **Autumbra** is wide but acts only on fixtures.
- **Tank and Skala** have the core: one door, ledger, savings, shadow, bench, graduation and approvals. Most of the Gemini points are there but switched off, or below the bar set in the plans.
- **Thinnest:** memory, the event bus, Radix, Tisan and the alerts. Rig's quote email (#353) is the only product email in code. Autumbra's owner email goes to a fixture transport, and Tiger, Market Lab and Zenas have no email code.

## 3. The Gemini blueprint, point by point

| Gemini point | Status | Where | What is left |
|---|---|---|---|
| Tank classifies each query and sends deterministic ones to plain code | Part | Code and cache rungs skip the model (`tank/main.py:1160–1191`). The path is chosen per task type by policy (`:1103`) | There is no per-query complexity scoring. A bypass happens only where a policy already points at a skill or the cache |
| RouteLLM as the routing classifier | Not started | No RouteLLM anywhere | Add RouteLLM (rule 8, section 4b) |
| Skala shadow test: the same query run in the background on a cheap open-weights model | Built, mostly off | Async shadow (`tank/main.py:1291`, `:1507`). Open-weight models are in the roster (#230) | `shadow_rate` defaults to 0 (`tank/schema.sql:54`). Only `reason.brief` is seeded with a candidate |
| LLM-as-judge on accuracy, structure and tone (DeepEval) | Replaced | Our own judge, `tank.judge` (`tank/schema.sql:153`, `tank/main.py:1528`). Field agreement in `tank/graduate.py:201–235` | Move to DeepEval (section 4b): today it gives one 0–100 score, with no separate structure or tone score |
| Switch only after a sustained 99% equivalence over a batch | Part | `tank/graduate.py:301`. Promotion writes the policy (`tank/main.py:1670`) | The default bar is 97% over 30 samples (`tank/graduate.py:23–24`). Build Pack v2 says 1,000 calls at 97%; Gemini says 99%. The founder picks one (section 4) |
| Mixture of Agents: 4 proposers and an aggregator, with timeouts, retries and degradation (LangGraph) | Part, off | `tank/moa.py:282–336` (LangGraph StateGraph, retry and timeout policies, circuit breaker), #228 | `moa_enabled` is false and no policy turns it on (`tank/schema.sql:1526`) |
| Aggregator steps down when the proposers agree | Part, off | `tank/moa.py:317–318` | The same switch as above |
| Langfuse as the immutable receipt | Replaced | Ledger and transcripts per call (`tank/schema.sql:7`, `:93`), MoA receipts, the founder's proof page (`tank/proof.py:94–178`) | Add Langfuse beside the ledger (section 4b) |
| LiteLLM: keys, load balancing, failover | Part | Failover chains, cheapest first (`litellm/config.yaml:644–697`) | No load balancing (one deployment per model) |
| Day 1 / Day 30 / Day 60 cost per query | Part | Actual against "would have cost" per call (`tank/proof.py`). MoA receipts show saved against frontier | No staged view of the cost falling over time |
| Perplexity in the research seat (founder) | Part, off | The Perplexity presets and `/v1/research` (`tank/research.py:145–200`) are off until the founder promotes `market.research` | Perplexity is barred from MoA seats in code (`tank/moa.py:68–72`), so there is no research seat |
| Commercial: credits, bring-your-own-key with gain-share, outcome pricing | Parked | Pricing is parked by the founder's rule 1 | Recorded only |

## 4. Founder decisions: five already made, three open
I first listed eight "open decisions". Five of them you had already made, and the code or the plan has to follow you.

**Already decided by the founder:**
1. **The free tools, never our own code where a tool exists** (confirmed 27 Oct). You adopted the Gemini infrastructure, built on LiteLLM, RouteLLM, DeepEval, Langfuse and LangGraph. The builders replaced RouteLLM, DeepEval and Langfuse with our own code. That is a deviation to fix, and section 4b lists every place it happened.
2. **Zenas review stays off.** You decided lawyer approval is not a gate. `ZENAS_REVIEW` defaulting off (`agents/zenas/core/review_switch.py:16`) follows that.
3. **Memory: the wall stays.** Every squad member has its own memory and shares nothing. Learning is shared through Skala skills. Build Pack v2's de-identified platform memory is superseded.
4. **No event bus.** Each agent talks only to Tank and Skala (`plan/squad-learning-plan.md`, 20 Oct). Market Lab pulling Tiger data through Tank (`tank/market_lab_routes.py:115`) fits that. Build Pack v2's Redis Streams events are superseded.
5. **Autumbra #345 is on main by your merge** (27 Oct, 05:45 PT). It stays unless you say otherwise. Its live public page still breaks the no-sample-data rule (section 0).

**Still open:**
1. **Paid steps.** Your ladder rule (pause for admin approval before a paid step such as Brave, unless that step is set to auto) conflicts with AGENTS.md rule 10, "No run waits for a person" (set 14 Oct, #41). The code has only a global pause (`tank/controls.py:44–80`).
   - *Recommendation:* each paid step gets an "auto" or "ask first" setting, auto by default for steps you've already funded, with the global pause kept as the master switch.
2. **The graduation bar:** 30 samples at 97% (the code), 1,000 calls at 97% (Build Pack v2), or a sustained 99% (Gemini).
   - *Recommendation:* 99% agreement over at least 200 checked samples, plus your approval.
   - *Why:* 30 samples is too few to prove anything, and 1,000 calls would keep most tasks from ever switching.
3. **Mixture of Agents:** which tasks?
   - *Recommendation:* none until the bench shows a mixture shape cheaper than the single model at the same quality. Then you switch it on per task from the graduation page.

---

## 4b. Swap our own code for the free tools (founder, 27 Oct)
"It is stupidity to recode what's already done and free to use." In each place below, a builder wrote its own version of a free tool that the plans named. Each one moves to the tool, keeping today's behaviour and tests.

| Where | What we wrote ourselves | The free tool to use | Plan |
|---|---|---|---|
| Tank routing | Per-task policy only; no complexity scoring (`tank/main.py:1103`) | **RouteLLM** | Gemini |
| Skala judge | Own judge with one 0–100 score (`tank/main.py:1528`, `tank/graduate.py:201`) | **DeepEval** (faithfulness, structure, tone) | Gemini |
| Receipts and tracing | Ledger and transcripts only (`tank/schema.sql:7`, `:93`) | **Langfuse**, self-hosted, beside the ledger | Gemini |
| Cost dashboards | Own dashboards (`tank/dashboards.py`, `tank/admin.py:819`) | **Grafana + Prometheus**, fed from the ledger | Build Pack v2 |
| Semantic cache | Postgres table with a homemade bag-of-words vector (`tank/graduate.py:417–440`) | **Qdrant** (already running for memory) | Build Pack v2 |
| Batch queue | Postgres queue (`tank/schema.sql:1661`) | **Redis** (already running), plus each provider's batch API, not OpenAI only | Build Pack v2 |
| Scheduling | Chassis cron per room (`agents/market_lab/app.py:158`); nightly jobs with no trigger | **Airflow** (one instance for all agents) | Build Pack v1 and v2 |
| Base web reading | Own `scrape_site` (`tank/skills/base.scrape_site`) | **Firecrawl**, self-hosted | Build Pack v2 |
| Tiger watch-and-diff | Own diff (`agents/tiger/watch.py:337`) and httpx | **ChangeDetection.io** and **curl-cffi** | Build Pack v1 and v2 |
| Market Lab research | Perplexity presets only (`tank/research.py`) | **GPT-Researcher** over **SearXNG** (SearXNG is already deployed) | Build Pack v1 and v2 |
| Zenas drafting | Own clause library (`agents/zenas/core/drafting.py:15`) | **Docassemble** | Build Pack v2 |
| Tisan visual check | Own frame scorer (`agents/tisan/templates/next-site/e2e/visual.spec.ts`) | **pixelmatch** | Build Pack v2 |
| CI secret scan | Own regex test (`tests/test_secrets.py`) | **Gitleaks** and **Semgrep** in CI (both already in the Radix image) | Build Pack v2 |
| Uptime | GitHub watchdog (`.github/scripts/watchdog.py`) | **Uptime Kuma** | Build Pack v2 |

Already on the tools, so nothing to do: **LiteLLM** (gateway), **LangGraph** (Mixture of Agents, `tank/moa.py:300`), **Playwright**, **Semgrep**, **Gitleaks** and **OSV** (Radix scanning), and **Hermes Agent** (the Base and Rig brains).

Two tools are still to add where nothing exists yet: **Nuclei** and **OWASP ZAP** for Radix.

## 5. Product by product: what is left, in order

### Tank
1. **Link each chat turn to a job, and give `command.turn` the tenant cache.**
   - Chats get none of the ladder: `command.turn` has `cache_scope 'none'` (`tank/schema.sql:1046`).
   - Turns never reach savings: they have no job (`tank/command.py:376`), and the savings report drops rows with "No linked job" (`tank/proof.py:271`).
2. **Make `priority` real.** urgent and standard behave the same today (`tank/main.py:594`). Then add Tier 0 classify-first: `tier0.classify` exists but nothing calls it.
3. **Batch** works only for OpenAI models (`tank/main.py:2398`). Add the other providers' batch APIs. There is no off-peak scheduler.
4. **Rung 2: serve the trained models** (TRAIN-2). LoRA training exists (`jobs/train/train.py`); nothing serves the result.
5. **Re-run Skala skill evals when a model changes.** `models_validated` is never written (`tank/schema.sql:175`).
6. **The open questions in section 4:** paid steps, the graduation bar and Mixture of Agents.
- **Done when:** a test client asks the same question twice in `/chats`. The second answer comes from the cache at $0, and both turns appear in that client's savings.

### Skala
- **Built:** the states, version pinning, Approve all ready and rollback (#223).
- **Left:** the 30-day wait before an old version retires (it retires at once today, `tank/skala.py:502–519`), and the control panel to frame 10:115 (branch `codex/control-panel`).

### Workspace
- **Dashboard and control panel:** merge `codex/dashboard` and `codex/control-panel` once checked against 12:2 and 10:115.
- **Feedback:** add "wrong" and a note box, on chats and agent results as well as `/tasks` (`workspace/app/feedback-buttons.tsx:5`).
- **The task board** has no "unverified" column. Chat "streaming" sends the whole answer at once (`tank/command.py:408`).
- **Not started:** client API keys and webhooks, the tester programme (cohorts, sealed tenants, captured questions), and the CLI.

### Base
1. **The ATF reference:** merge `codex/base-atf-download` so an empty store downloads the first list.
2. **State order is alphabetical** (`tank/base_repository.py:241`). Your rule is fewest FFLs first.
3. **Figma:** merge the C5 export from `docs/go-live-list` to main, then match `/base` to it.
4. **One real state** for a test client.
5. **The case study:**
   - built: cost per verified record and the Apollo CSV comparison (`tank/base_product.py:281–315`);
   - missing: the 200-record audit tool and the confidence histogram;
   - the comparison uses no invoice costs yet.
- **Not built:**
  - Google Places is priced but never called;
  - OpenCorporates, Hunter, ZoomInfo and Clearbit, reviews and tech stack have no code;
  - there are no source-reliability scores.
- **Done when:** a test client uploads a list on base.tervory.com and downloads it verified, with a receipt.

### Tiger
- **Built:** watches, schedules, price and stock reads, scope rules, and the price-reading fix (#335).
- **Left:**
  1. a Figma frame for the page;
  2. **email alerts:** none are sent today, and no mail code exists in `agents/tiger` or `workspace/app/tiger`;
  3. new-product, below-cost and market-gap alerts;
  4. site playbooks per domain (today the layout is learned per URL, `agents/tiger/page_guard.py:30`).
- **Done when:** a test client watches 20 real pages for 48 hours on tiger.tervory.com, and a real change reaches them by email.

### Market Lab
- **Built in part:** cited answers from stored feeds (#336), source pages (#349), warnings and outcome learning (#350), predictions with a horizon and a realised outcome.
- **Left:**
  1. **Documents (MARKET-DOCS-1):** the upload calls `/v1/vaults`, which Tank doesn't have (`workspace/lib/tank.ts:502`; no route in `tank/`), so every upload fails.
  2. **The off feeds:** fix the 10 off feeds.
     - Of the sources Build Pack v2 named, only FRED and the Federal Register have fetchers.
     - UN Comtrade, MarineTraffic, Freightos, USPTO, SEC EDGAR, Reddit and LME have none.
  3. A confidence value on each prediction, plus calibration curves.
  4. Email and webhook delivery of briefs.
  5. Remove the internal ids from the feed review table.
- **Done when:** a test client gets a cited brief, and every link opens its source.

### Rig
- **Merged today:** #353 (12:18 PT) adds:
  - the store's quote email (`EmailHandoff`);
  - store settings;
  - the embed key and snippet;
  - removal of the widget's sample-data text.
- **Left:**
  1. **Remove the Archon demo** from rig.tervory.com `/` and from the Workspace `/rig` lab and search pages (`agents/rig/rigbox/page/v5/index.html:128`, `workspace/app/rig/lab.tsx:219`).
  2. **Set `SMTP_*` in Coolify** (names only, `agents/rig/docker-compose.yml:30`).
  3. **One real store:** its own CSV, the embedded widget, 10 searches and 3 quote emails.
  4. **3D for Custom Nation:**
     - frames 06–07 approved in Figma;
     - the 3D button in the widget;
     - the GPU jobs, which are off with TRELLIS disabled;
     - the `rig_3d` purchase, parked under rule 1.
  5. Tiger feeding prices for products with no feed (only the receiving end exists, `tank/access.py:976`).
- **Done when:** a test store receives 3 real quote emails from its own page.

### Tisan
- **Built:** the Next.js site scaffold, and the Figma reader, which works from a recorded fixture only.
- **The page does nothing.** "Start build" and search only call `preventDefault` (`workspace/app/tisan/tisan.tsx:508`, `:267`). Chat answers "Nothing was sent" (`:89–96`).
- **Left:**
  1. the request, brief, build, preview and revision flow;
  2. a live Figma read;
  3. Coolify staging and production;
  4. a Radix scan in QA;
  5. the ecommerce and quote-form modules;
  6. the build log to memory.
- **Done when:** a test client opens a working preview built from their own request.

### Radix
- **Built in part:** a real Semgrep, Gitleaks and offline OSV scan, open to the Ghost corridor only (`tank/ghost_routes.py:270–286`).
- **Left:**
  1. a client upload of a repo, and the report page (today the Reports tab shows a hard-coded example, `workspace/app/radix/content.ts:41`);
  2. the deploy gate actually used (`deploy_blocked` is set in `agents/radix/scanlib/orchestrate.py:78`, and nothing reads it);
  3. a weekly self-scan of Tervory;
  4. ZAP and Nuclei, uptime, the Tisan link and the Zenas link.
- **Done when:** a test client uploads a repo and downloads a correct report.

### Zenas
- **Built:**
  - the criminal refusal, which runs first (`agents/zenas/core/scope_rules.py:17`, `:121`);
  - the release flow;
  - drafting from a clause library (in place of Docassemble);
  - US loaders.
- **Left:**
  1. **#326's work is gone from GitHub.** Branch `codex/zenas-backend` was deleted and its commits are not on main (last known commit `75098a9`: Boston-only routing and source links kept in answers). Restore it or redo it.
  2. Schedule the nightly regulatory runner; nothing calls it today (`agents/zenas/pool/nightly.py`).
  3. Turn on meaning search (a no-op until embeddings, `agents/zenas/pool/embed.py`).
  4. Put the disclaimer on each answer, not only the page footer (`workspace/app/zenas/view.tsx:478`).
  5. Email and SMS alerts.
  6. Moot: replace the fixture match on the live page. AI counsel and an AI judge are not started; today counsel is stubbed and the judge is fixed text.
- **ZA stays stopped.**
- **Done when:** a released US answer shows to a test client, and a criminal question is refused.

### Autumbra
- **Built:**
  - the Watch–Enforce air gap;
  - the never-block list;
  - undo with signed tokens;
  - receipts;
  - public threat sources only;
  - "logs read and deleted".
- **Acts only on fixtures.** Enforce applies "block IP" to an in-process fixture edge only (`agents/ghost/fixture_edge.py:1–6`). The WAF, rate-limit and revoke-session shields are plans only. The health check reads a flag. The owner email goes to a fixture transport.
- **Left:**
  1. a real Cloudflare hand;
  2. a real health probe;
  3. real email;
  4. per-client containers;
  5. an AI second opinion;
  6. Cloudflare's and Google's own webhook signatures;
  7. a public page with no fixtures.
- **Done when:** on our own site, a test attack is shielded and undone with one tap, and the receipt reaches the founder.

### Memory, brains and the bus
- **Brains:** only Base and Rig have a Hermes brain, a browser and a sandbox. Tiger has a browser only. Market Lab, Radix, Tisan and Zenas have none.
- **Memory:** vectors in Qdrant per agent per tenant, with one shared key. There is no record row. There is no platform tier, and by the founder's decision none is needed (section 4).
- **The nightly cycle:** the bench runs inside Tank, and the gold retests have no trigger. **The morning report doesn't exist.**
- **The bus:** none, and by the founder's decision none is needed (section 4).

### Infrastructure
- **The backup to R2** is off unless the `r2-backup` profile is enabled (`docker-compose.yml:271`). There's no Qdrant snapshot, no second offsite copy and no restore drill.
- **No Postgres row-level security** on `tenant_id`, and Qdrant uses one shared key.
- **CI** uses a home-grown secret test, not Gitleaks, and has no Semgrep. Radix doesn't gate our own repo.
- **Uptime:** the GitHub watchdog stands in for Uptime Kuma. There is no Grafana and no egress alert.
- **FFL** is the only industry engine, with no template for the next vertical.
- **ZA** is stopped (`ZA_OFFLINE`).

### Not started
- **In-video shopping:** brief only (`docs/cursor/AGENT-in-video-shopping.md`, `VSHOP-1-phase-1.md`).
- **ZA2:** stopped.

---

## 6. Order of work: parallel lanes
These run at the same time, one thread each. Only the paid-step and graduation items wait on section 4's open questions:
1. **Rule 3 cleanup (one thread, today):** remove the fixtures and internal words from rig.tervory.com `/`, the Workspace `/rig`, zenas.tervory.com Moot, protect.tervory.com, and the Market Lab feed review.
2. **Tank:** chats on the ladder and in savings; real priority; Tier 0 classify-first.
2b. **The tool swap (section 4b):** one thread per tool, starting with RouteLLM, DeepEval and Langfuse in Tank.
3. **Base:** merge the ATF download, fewest-first order, the C5 frame, one real state, the audit tool.
4. **Rig:** set SMTP in Coolify, then one real store and 3 quote emails.
5. **Workspace:** the dashboard and control panel to Figma; feedback with "wrong" and a note.
6. **Market Lab:** the missing `/v1/vaults` route and document reading (MARKET-DOCS-1); the off feeds.
7. **Tiger:** a Figma frame, then email alerts.
8. **Zenas:** restore or redo #326; schedule the nightly runner; disclaimer per answer.

Next: the Radix client upload and deploy gate, the Tisan build flow, brains for the other agents, the morning report, backups switched on with a restore drill, row-level security, Gitleaks and Semgrep in CI, a Workspace build in the merge check, and then any Mixture of Agents shape the bench proves.

## 7. Waiting on the founder
| Branch | What it is | State |
|---|---|---|
| `codex/base-atf-download` | Base: the first ATF list when empty | Open |
| `codex/dashboard`, `codex/control-panel` | The 12:2 and 10:115 rebuilds | Open since 26 Oct; check against the frames |
| `codex/zenas-backend` (#326) | Zenas back end, Boston-only routing | **Deleted from GitHub, not merged.** Last known commit `75098a9` |
| `codex/sec-code` (#329) | Code security | Open; its Dockerfile install lines were unpinned at the last review |
| `docs/go-live-list` | Figma C5 export (still needed), go-live list, break points | The lists are superseded by this file |

## 8. Every tool: where it goes and which agents it serves
**Status:**
- **In:** in the code and on.
- **Off:** in the code, switched off.
- **Swap:** we coded our own; move to the tool (rule 8).
- **Add:** planned, no code yet.
- **Stopped** or **Dropped:** by the founder's decision.

### Core: Tank, Skala, memory (serves every agent)
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| LiteLLM | Tank gateway: every model call, keys, failover | All | In |
| RouteLLM | Tank: scores each request and picks the cheapest capable path | All | Add |
| DeepEval | Skala and Tank: the judge for shadow tests and graduation | All | Swap |
| Langfuse | Tank: trace and receipt for every call, beside the ledger | All | Add |
| LangGraph | Tank: Mixture of Agents fan-out and fan-in | All (complex tasks) | Off |
| PostgreSQL | Tank ledger and policy, each agent's own schema | All | In |
| Redis | Tank batch queue and cache | All | In (the batch queue is a swap from Postgres) |
| Qdrant | Tank semantic cache and Hermes memory | All | In for memory; Swap for the cache |
| Hermes Agent | Each agent's own brain, browser and sandbox | Base and Rig In; Tiger, Market Lab, Radix, Tisan and Zenas Add | Part |
| Airflow | One scheduler for every agent's nightly and daily jobs | All | Swap |
| Grafana and Prometheus | Founder cost dashboards from the ledger | Founder (Tank) | Swap |
| Hugging Face | LoRA training of our own small models | All (rung 2) | In (training only) |
| Together, Groq or Ollama | Serving our own trained models | All (rung 2) | Add |
| Perplexity Sonar | Tank research route (the research seat) | Market Lab first | Off |

### Workspace (app.tervory.com and the product hosts)
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| Next.js | The client app and every product page | All | In |
| Clerk | Sign-in, one organisation per tenant | All | In |
| Resend | Email for alerts and reports | Tiger, Market Lab, Zenas, Autumbra | Add (no email code in any of them) |
| Twilio | Text-message alerts | Zenas | Add |

### Base: verified business lists
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| Playwright (shared browser) | Reading sites like a person | Base (shared with Tiger) | In |
| SearXNG | Free search for business websites | Base, Market Lab | In |
| Brave Search | Paid search rung | Base | In (paid, gated) |
| RapidFuzz | Matching names and addresses | Base | In |
| Firecrawl | Reading and structuring websites | Base | Swap (from our own `scrape_site`) |
| Google Places | Entity match, reviews | Base | Add (priced, never called) |
| OpenCorporates | Company registry match | Base | Add |
| Hunter.io | Email patterns | Base | Add |
| Context.dev | Company data trial | Base | In (trial) |
| Apollo, ZoomInfo, Clearbit | Learning sprint and case-study comparison | Base | Apollo In (CSV import only); ZoomInfo and Clearbit Add |
| ATF FFL list | The FFL engine's reference list | Base, Market Lab | In (first download fix on `codex/base-atf-download`) |

### Tiger: price and stock watches
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| Playwright (shared browser) | Rendered product pages | Tiger (shared with Base) | In |
| curl-cffi | Fast reads of static pages | Tiger | Swap (from httpx) |
| ChangeDetection.io | Watch and diff | Tiger | Swap (from our own diff) |
| Steel.dev | Persistent sessions where terms allow | Tiger | Swap only if a free edition fits; our own saved sessions do the job today |
| Residential proxies, CapSolver | Blocked sites | Tiger | Dropped (no captcha solving) |

### Market Lab: market research and prediction
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| GPT-Researcher | Research runs over SearXNG, through Tank | Market Lab | Add |
| EIA, Census, World Bank, NOAA, NWS | Feeds | Market Lab | In (live, storing data) |
| FRED | Economic series | Market Lab | Off (needs its key) |
| Federal Register | Rules feed | Market Lab, Zenas | In code, "could not be read" live |
| LegiScan | State bill tracking | Market Lab | Off (needs its key) |
| Census trade, Port of LA, BTS freight | Trade and freight feeds | Market Lab | In code, off live (blocked or could not be read) |
| UN Comtrade, MarineTraffic, Freightos, USPTO, SEC EDGAR, Reddit, LME | Signal feeds | Market Lab | Add |
| Qdrant (pattern library) | Matching new signals to past ones | Market Lab | Part |

### Radix: code scanning
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| Semgrep | Unsafe-code scan | Radix (and CI for our own repo) | In for Radix; Swap into CI |
| Gitleaks | Secret scan | Radix (and CI for our own repo) | In for Radix; Swap into CI |
| OSV data | Package advisories | Radix, Autumbra | In |
| Checkov, Socket.dev | Infrastructure files and supply chain | Radix | Add |
| OWASP ZAP, Nuclei | Testing a live app | Radix | Add |
| Nmap, testssl.sh, dnsx | Weekly checks of live sites | Radix | Add |
| axe-core | Accessibility checks | Radix, Tisan | In for Tisan only; Add for Radix |
| Uptime Kuma | Uptime of client sites and ours | Radix (and Tervory) | Swap (from our own watchdog) |
| HIBP, ClamAV, VirusTotal | Breach watch, malware | Radix | Add |

### Tisan: websites for clients
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| Next.js, Tailwind, TypeScript | The site template | Tisan | In |
| Figma API / MCP | Reading the locked design | Tisan | Part (recorded fixture only; live read Add) |
| Aider (through Tank) | Writing the code component by component | Tisan | Add (used today only by Tervory's own build workers) |
| Playwright, Lighthouse CI | Tests on every build | Tisan | In |
| pixelmatch | Page against Figma frame | Tisan | Swap (from our own scorer) |
| k6 | Load test | Tisan | Add |
| Coolify API | Staging, then production | Tisan | Add |

### Zenas: civil legal research and drafting
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| CourtListener | US case law | Zenas | In |
| GovInfo (US Code), eCFR, Federal Register | US law and rules | Zenas | In (the nightly runner has no trigger) |
| Congress.gov, Justia, EUR-Lex | More law sources | Zenas | Add |
| SAFLII, gov.za, Government Gazette | South African law | Zenas | Stopped (ZA) |
| Docassemble | Contracts and letters from templates | Zenas | Swap (from our own clause library) |
| LlamaIndex with Qdrant | Meaning search over the law library | Zenas | Add (search is a no-op today) |

### Rig: parts finder, quotes, 3D
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| SMTP (store email) | Quote emails to the store | Rig | In (#353); needs the SMTP settings in Coolify |
| Odoo | Quotations in the store's Odoo | Rig | Off |
| three.js | 3D viewer in the widget and kiosk | Rig | In |
| Blender, gltf-transform, gltfpack, KTX, trimesh, manifold, glTF validator | The 3D forge | Rig | In |
| Meshroom, TRELLIS 2 (on Hugging Face Jobs) | 3D from photos | Rig | Off (TRELLIS licence switched off) |

### Autumbra: protection for client sites
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| CISA KEV, OSV, GHSA, NVD | Public threat sources | Autumbra (through Market Lab) | In |
| Vector, Fluent Bit, Steampipe, OpenCTI | Watch intake | Autumbra | Off |
| Ansible, Terraform | Enforce changes | Autumbra | Off (plans only) |
| Cloudflare API | The real shield "hand" | Autumbra | Add (fixture only today) |
| Google Workspace API | Small-business connect | Autumbra | Add |

### Infrastructure (Tervory itself)
| Tool | Goes into | For which agents | Status |
|---|---|---|---|
| Coolify | Deploys and settings (in place of Doppler, by the founder's choice) | All | In |
| Cloudflare (DNS, WAF, R2) | Edge, storage, backups | All | In; the R2 backup is off unless its profile is on |
| Backblaze B2 | Second offsite backup copy | All | Add |
| GitHub Actions | CI and the watchdog | All | In |

---

# Appendix: every planned point, traced
Code on main at `cb5d1cf` (Rig rows L18, L21, L25 and L26 updated for #353), read only. File and line are as of that commit.


### A. Tank

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| A1 | Gateway: one endpoint, LiteLLM proxy + FastAPI, holds provider keys, priority flag urgent/standard/batch (BP2) | Part | tank/main.py:2298 `/v1/route` -> run_route :1059 posts to LiteLLM :1224; keys only in litellm/config.yaml (`os.environ/...`); RouteRequest.priority main.py:594, written to ledger :1281 | The gateway is built. `priority` is only a label: urgent and standard are handled the same way. Batch is a separate endpoint (`/v1/route/batch`, :2364), not a value of the flag. |
| A2 | Ledger: one row per call with tenant, agent, skill, task type, model, tokens, cost, latency, cache hit, eval score, outcome (BP2) | Built | tank/schema.sql:7-24 (tenant, agent, skill, task_type, rung, model, tokens, cost_usd, latency_ms, cache_hit, eval_score, outcome) plus feedback :31-36; written at main.py:1274, :989 | `eval_score` is only filled on bench rows (bench.py:230). Live calls leave it null. |
| A3 | Routing policy as data in tank.policy: task type → models, priority, batch eligibility, cache scope, region; editable per tenant without deploy (BP2) | Part | tank.policy schema.sql:39-51 (model, priority, batch_eligible, cache_scope, per-tenant via tenant_id plus unique index :88); `PUT /v1/policy/{task_type}` main.py:777 | There is no region column; region is set per box (main.py:118 box_region). The fallback chain (the "models" list) lives in litellm/config.yaml:649, so changing it needs a deploy. |
| A4 | Eval harness: golden set per task type; runs any model/distilled model/code path; scores agreement (BP2) | Built | tank.evals schema.sql:104; gold sets gold.py:87/312; nightly bench replays evals on every roster model bench.py:149,199,260; code path via skill evals skala.py:311; agreement scoring graduate.py:226 compare (CORE-1 #218, TRAIN-1 #147) | Scoring is field agreement or the judge's score, not a separate agreement metric for each harness. |
| A5 | Graduation loop: surfaces task types ready to move down a rung (>=1,000 calls, >=97% agreement), human approves, Skala ships, policy re-routes; admin view (BP2) | Part | graduate.py:301 proven_reason, :443 promote_if_proven; auto_promote default false schema.sql:830 (a person approves); `/v1/graduation` main.py:1900 plus promote :2084 and rollback :2100; admin view workspace/app/tank/graduation-panel.tsx (GRAD-1 #186) | The bar is `min_shadow_samples` default 30 (schema.sql:303, graduate.py:24), not ">=1,000 calls". The 97% default matches. Skala approval and the policy promote are two separate manual steps; they are not linked. |
| A6 | Cost ladder rung 1 frontier, rung 2 owned small model, rung 3 code, rung 4 cache (BP2) | Part | Rung 4 cache main.py:1161-1164, rung 3 code :1170-1191, then escalation to a paid model labelled rung 2 :1192-1199; ledger rung comment schema.sql:15 | Rung 2 is used as the label for "paid escalation after code failed", not for an owned small model. No owned model is served (see A30). |
| A7 | Batch: queued in Redis, sent through provider batch APIs (~50% off) within 24h (BP2, BP1 "batch queue") | Replaced | Durable queue in Postgres tank.batches/batch_items schema.sql:1661-1695; provider Batch API with 50% discount and a 24h window main.py:2333-2345, :2541-2604; loop started main.py:708 (`fe1a430` #334) | Postgres replaces Redis. Only OpenAI-provider models are batched (main.py:2402), and only for policies with `batch_eligible` (seeded for 5 task types, schema.sql:1730), with >=50 non-interactive requests (TANK_BATCH_MIN). |
| A8 | Off-peak scheduler (BP1 build order) | Not started | Searched for off.peak, offpeak, schedul, cron in tank/, litellm/, jobs/ | "Off-peak" appears only in DeepSeek price comments (litellm/config.yaml:90). Nothing holds work for an off-peak window. |
| A9 | Semantic cache (Qdrant) with tenant scoping (BP2) | Replaced | Postgres tank.route_cache schema.sql:1648; tenant-scoped read/write main.py:1016-1056; local hashed bag-of-words vector graduate.py:417-440, :679 semantic_lookup (#334) | Qdrant is not used for the cache. `semantic_cache` defaults to false (schema.sql:598) and is switched on only for zenas.* (schema.sql:1716). The exact-match cache is on wherever cache_scope is not 'none'. Every scope is forced to tenant-local. |
| A10 | Tier 0: classify first; definitions/drafting/summaries/general Q&A to cheapest model or cache; capture tester questions (BP2) | Part | tier0.answer/tier0.draft policy rows on the cheapest model plus cache scope schema.sql:143-146; Workspace chat calls tier0.answer directly workspace/app/api/chat/route.ts:16; transcripts capture questions schema.sql:93 | There is no "classify first" step in the request path. tier0.classify exists, but neither chat nor tasks calls it. |
| A11 | Client ledger view in Workspace: spend this month, cost per verified outcome, rung mix (BP2) | Built | workspace/app/ledger/page.tsx:28-80 (spend, cost per delivered and per accepted answer, rung mix) from `/v1/ledger/summary` main.py:3449 | The window is the last 30 days, not the calendar month. "Verified outcome" means feedback=accepted. |
| A12 | Grafana/Prometheus cost dashboards from the ledger (BP2, BP1) | Replaced | Own dashboards: tank/dashboards.py (DASH-1 #220), econ_daily rollup admin.py:819-951 (C11 #23), founder console workspace/app/admin/console.tsx | No Grafana or Prometheus anywhere (grep of tank/, docker-compose.yml, workspace/). |
| A13 | Orchestrator route.request as a Tank task type with its own golden set; first to graduate (BP2) | Part | route.request policy schema.sql:146; skill tier0.classify 1.0.0 (task_type route.request, 5 cases) tank/skills/tier0.classify/1.0.0/skill.yaml | It is not wired into routing. The first seeded graduation candidate is reason.brief (schema.sql:159), not route.request. |
| A14 | GEM: Tank classifier with complexity scoring → path (code, fast LLM, premium LLM); deterministic prompts bypass LLM entirely | Part | Path is chosen per task type by policy (main.py:1103), code and cache rungs skip the LLM (:1160-1191); the only "complexity" signal is a MoA char threshold moa.py:48,:691 | No classifier scores the complexity of each request. Deterministic bypass works only where a policy row already points at a skill or cache. |
| A15 | GEM: RouteLLM as routing classifier (matrix factorization complexity scoring) | Not started | Searched for routellm, matrix factor, complexity in the whole repo | Routing is the per-task policy table plus bench-chosen candidates (bench.py:68). No learned router. |
| A16 | GEM: Skala shadow test — async shadow execution of the same query on a cheap open-weights model | Built | Async shadow main.py:1291-1294 -> _shadow :1507; candidate can be any roster model, including the MODELS-3 open-weight entries (litellm/config.yaml:187-489, #230); bench sets candidates bench.py:318 | `shadow_rate` defaults to 0 (schema.sql:54). Only reason.brief is seeded with a candidate at rate 1.0 (schema.sql:159). Others depend on the bench proposing one. |
| A17 | GEM: LLM-as-a-judge equivalence (semantic accuracy, structure, tone); DeepEval as the judge | Replaced | Own judge: tank.judge policy schema.sql:153-154 (re-pinned :386-393) called in main.py:1528-1536; structured field agreement graduate.py:201-235 | No DeepEval. The judge returns one 0-100 score for "conclusion and key facts". Structure and tone are not scored separately. |
| A18 | GEM: switch only after sustained 99% equivalence over a batch; Tank updates routing tables | Part | proven_reason graduate.py:301 (agreement >= eval_threshold over >= min samples); promote writes tank.policy main.py:1670-1714 | The default bar is 97% over 30 samples, not a sustained 99%. Per-row thresholds can be raised. Auto-switch is off (auto_promote false). |
| A19 | GEM: Mixture of Agents fan-out to 4 diverse proposers + aggregator; atomic timeouts and retries; graceful degradation; LangGraph orchestration | Part | LangGraph fan-out moa.py:282-336 (StateGraph :300), RetryPolicy/TimeoutPolicy :174,:201-203, circuit breaker :131-156, degradation on missing seats :316,:333; up to 8 seats :38 (MOA-1 #228) | Off by default: moa_enabled false and no policy seeded (schema.sql:1526-1527). Seats are configurable; there is no fixed set of 4 proposers. |
| A20 | GEM: dynamic aggregator step-down when proposers agree | Part | moa.py:317-318: with the 'optimised' shape, the cheap aggregator is used when agreement >= threshold | Same switch as A19, so off by default. Agreement is exact or JSON equality (moa.py:217-228). |
| A21 | GEM: Langfuse telemetry/tracing as the immutable receipt (tokens, latency, cost per query) | Replaced | Ledger plus transcripts per call (schema.sql:7,:93), MoA receipts tank.moa_runs, founder proof receipts tank/proof.py:94-178 | No Langfuse in the repo. |
| A22 | GEM: LiteLLM failover when a provider crashes, load balancing | Part | Fallback chains litellm/config.yaml:649-693; allowed_fails/cooldown :695-697 (#41) | Failover is built. There is no load balancing: one deployment per model_name and no routing_strategy. |
| A23 | GEM: Day1/Day30/Day60 cost-per-query economics shown (baseline vs substituted vs step-down) | Part | Proof shows actual against baseline and standard cost per call (proof.py:94-178, :279-330); MoA receipts show saved vs frontier and vs single (moa.py:254-277) | No Day1/Day30/Day60 projection or staged view (grep for day30, day60 found nothing). |
| A24 | GEM commercial: unified credits, BYOK + gain-share (charge % of saved dollars), outcome-based pricing (founder: pricing parked until product works — record only) | Part | Outcome price book and outcomes schema.sql:239-262; Stripe billing events main.py:3695-3760; dashboard shows "Credits left —" workspace/app/page.tsx:37 | Recorded only, as the founder asked. No BYOK, gain-share or unified credits (grep byok, gain.share, credits found nothing). |
| A25 | Founder: savings proof per client — what it cost vs what it would have cost (standard default model), shadow runs and receipts; live on the client's dashboard | Built | Baseline and standard model cost per ledger row by trigger (schema.sql:845-890, :1102-1140; savings_defaults.py:2-4); client savings API proof.py:455-512; on the client dashboard workspace/app/page.tsx:30-38 (CORE-1 #218, CORE-2 #227/#234/#242) | Shadow pairs appear in the founder proof (proof.py:134-142). Whether they reach the client copy was not checked in detail. |
| A26 | Founder: cheapest funded model first, move to next cheapest when a provider is empty | Built | Chains sorted cheapest first, provider skipped after 1 failure for 300s litellm/config.yaml:644-697; ledger books the model that answered main.py:1265 (#41) | Cheapest-first starts from the model the policy picked, not across the whole roster. Fallbacks are disabled for pinned and capped calls (main.py:1128,:1218). |
| A27 | Founder: the ladder pauses for admin approval before a paid step (e.g. Brave) unless set to auto | Part | A global founder pause on all paid work, fail-closed, controls.py:44-80 (default not paused); paid hosts such as Brave are metered and gated by the same pause controls.py:83-88, vendor_meter.py:18-23 | There is no per-step "wait for admin approval before a paid step unless auto". AGENTS.md rule 10 says "No run waits for a person", which conflicts with this item. |
| A28 | Founder/GEM: Perplexity in the research seat (MOA-1) | Part | Perplexity presets in litellm/config.yaml:100-160; separate `/v1/research` research.py:145-200, usable only once a founder promotes `market.research` (research.py:172-174; seeded on 'sol' schema.sql:337) (MODELS-2 #154) | Perplexity is explicitly forbidden in MoA seats (moa.py:68-72, :401), so there is no MoA research seat. The research route is off until promoted. |
| A29 | Distillation: open-weight teachers; record teacher per skill (BP2) | Not started | Searched for teacher, distil in tank/, jobs/, agents/, workspace/; training_pairs schema.sql:719-736 has no teacher column | No record of which model taught each skill. Training pairs come from human-checked gold and accepted outputs. |
| A30 | Rung 2: fine-tune owned small models on eval data, served via Together/Groq/Ollama or HF (BP2, TRAIN-2) | Part | Capped private HF LoRA training of Qwen3-4B jobs/train/train.py:5,:110, jobs/train/run.py, tank.training_jobs schema.sql:782; datasets export training.py:553-659 (GRAD-1 #190) | TRAIN-2 serving is not built: no jobs/serve, no `tervory-own-*` roster entry, no HF_SERVE_* code. Training is a manual submit and needs HF_TOKEN/HF_ORG. |
| A31 | Model roster as policy data; model swap re-runs every skill's evals before policy change (BP2) | Part | Roster comes from litellm/config.yaml (main.py:1342-1428 _roster_models); a change to the roster or price fingerprint re-runs the bench for every rung 1-2 policy and only proposes a candidate bench.py:60-66,:292-331 | The roster is a config file, not policy data. A roster change does not re-run Skala skill evals, and `tank.skills.models_validated` (schema.sql:175) is never written. |

### B. Skala

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| B1 | Skill = versioned package with eval sets; states candidate → staging → approved → retired | Built | Package layout and states skala.py:1-21, :81-123; tank.skills state column schema.sql:163-182; eval moves candidate->staging (and back) main.py:2919-2950; approve/retire skala.py:502-574 (SKALA-2 #223) | Approval needs >=5 distinct cases, including a refusal, and 3 consecutive clean runs for model skills (skala.py:417-462). |
| B2 | Agents request skills by id+version; Skala refuses unapproved; agents may propose but never ship | Built | Run by id plus optional version, approved only, main.py:3000-3015, :3075-3077; agent ownership check :3061-3074; agents submit candidates only, agent_skills.py:538-543, no approval endpoint there (agent_skills.py:1-4) | `preview=true` lets a caller run candidate or staging versions (labelled unverified in the ledger, main.py:3101). Submission is enabled for the Base room only. |
| B3 | Every model swap re-runs skill evals | Part | Weekly re-test of approved skills against gold gold.py:312-372, scheduled training.py:464-506; bench re-run on roster change bench.py:60-66 | Nothing re-runs skill evals when a model swaps. models_validated is unused. Skala evals (`/v1/skala/.../evals`) are started by hand. |
| B4 | Retire after newer version 30 days clean; keep old for rollback | Part | Approving a new version retires the previous approved one at once and keeps it for rollback skala.py:502-519; rollback of a retired, previously approved version :545-554 | There is no "30 days clean" wait before retirement. |
| B5 | Phase 1 ten skills: five Tier 0/orchestrator, five Base pass 1–2 | Built | Packages with evals: tier0.answer, tier0.classify, tier0.draft, tier0.summarize, reason.brief, base.resolve, base.find_site, base.scrape_site, base.extract, base.normalize (tank/skills/*; `7d95001` Skala v1 and Base passes 1-2) | Approval state lives in the DB and cannot be seen from code. Some versions have fewer than 5 cases (e.g. tier0.summarize 1.0.0 has 3), so only the newer versions can pass the approval gate. |
| B6 | Founder approval page (Approve all, rollback) | Built | workspace/app/skala/approve-all.tsx:35 "Approve all ready"; rollback button and confirm view.tsx:107-169,:350,:385-393; bulk preview/confirm skala.py:588-633 (SKALA-2 #223) | "Approve all" skips room-authored skills, which need a source review one at a time (skala.py:594-595). |

### C. Workspace

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| C1 | Clerk login; every user in one tenant with a region | Part | workspace/middleware.ts:26-51 (Clerk gate); workspace/lib/tenant.ts:3-6,41-67 (Clerk org = tenant, auto personal org) (3f82fdb); region: agent_zenas.tenants.home_region agents/zenas/schema.sql:7-14 (5a9c089) | Login and one-org-one-tenant are built. No tenant region on the platform side: tank/main.py:144-148 is a TODO("Thread C") saying the tenant home-region column does not exist yet. Only Zenas has a per-tenant region. |
| C2 | Chat: Tier 0 through Tank, streaming, file upload | Part | /chats: workspace/app/chats/window.tsx:175-224,266; proxy app/chats/api/[...path]/route.ts:55-60,97-120; Tank tank/command.py:374-378 (run_route, command.turn), 454-498 (SSE), 1153-1226 (attachments) (#225, #224). Older app/api/chat/route.ts:16 uses tier0.answer | Goes through Tank, and file upload works (5 MB). "Streaming" is SSE carrying the whole buffered answer, not token deltas (command.py:408). Binary files are stored only and the model cannot read them (command.py:887). |
| C3 | Task board: queued, running, delivered, unverified | Part | workspace/app/tasks/page.tsx:7,24-29; tank/schema.sql:122-137 (tank.tasks status queued/running/done/failed) (1ed8290, #199) | Columns are Queued/Running/Done/Failed. There is no "delivered" or "unverified" state (ledger outcome has unverified at schema.sql:24, but the board never shows it). |
| C4 | Results panel: documents, tables, alerts, files, downloadable | Part | Text result inline on task cards tasks/page.tsx:139; chat file download chats/api/[...path]/route.ts:17-22,47-55; Base CSV download app/base/download/route.ts; Files page app/data/page.tsx | There is no single Results panel for documents/tables/alerts/files. Results are scattered across task cards, chat attachments and per-agent pages. |
| C5 | Ledger view (see A11) | Built | workspace/app/ledger/page.tsx:14,28-33,41-51,58-80; lib/tank.ts:220; tank/main.py:3450-3465 (1ed8290, #339) | Shows spend, cost per accepted answer and rung mix. The window is a rolling 30 days, not the calendar month, and "verified" means thumbs-up accepted. The home sidebar does not link to it (app/page.tsx:32). |
| C6 | Feedback: useful / not useful / wrong + note on every result, writes ledger outcome | Part | workspace/app/feedback-buttons.tsx:5,36-55; app/api/feedback/route.ts:14-19; tank/main.py:650-654,3365-3392 (writes ledger.feedback and tank.evals) (1ed8290) | Only two verdicts (accepted/rejected). There is no "wrong" verdict and no note box (the API accepts a note but the UI never sends one). The buttons appear only on the /tasks board, not on /chats answers or agent results. |
| C7 | Per-agent tabs as agents arrive: Base data tab; Tiger watchlists/alerts; Market Lab briefs/signals; Radix reports/uptime; Tisan projects; Zenas documents/alerts/matters | Part | Tabs exist: app/base, app/data, app/tiger/view.tsx:122-154 (watch/alerts/history), app/market-lab/view.tsx:42-50, app/radix/view.tsx:9-10, app/tisan/tisan.tsx:98-121, app/zenas/view.tsx:15-27 + app/matters, zenas/deadlines-panel.tsx | Radix Findings/Reports show demo content only (radix/content.ts:1 "Demonstration content only", view.tsx:103,128). Market Lab has no Briefs/Signals tab (Overview/On/Linked pages/Warnings). Tisan "Projects" links to /tasks (tisan.tsx:121). Uptime is not shown. |
| C8 | API keys and webhooks (Business tier) | Not started | Searched workspace/app, workspace/lib, tank/*.py, tank/schema.sql for api_key/webhook/business tier | There is no client-issued Tervory API key and no outbound webhook. "API keys" in the code are vault-stored third-party keys (rig/tisan/market-lab plugins), and the only webhook is Stripe inbound (api/billing/webhook). The closest is the MCP connector with Clerk OAuth (mcp/README.md:1-3). |
| C9 | Entrepreneur testing programme: cohorts of 5–10, sealed tenant, free allowance; capture de-identified questions, routing labels, ratings, feature requests, tester industry/size | Not started | Searched cohort/tester/feature request/allowance/testing programme in tank, workspace, agents, jobs | No cohorts, sealed test tenant, free allowance or feature-request capture. Fragments: ratings become tank.evals source 'tester_feedback' (main.py:3386), the founder sign-up list (control/signups/page.tsx), and an onboarding industry step (onboarding/wizard.tsx:32,154) that does not appear to be saved. |
| C10 | Founder control panel (frame 10:115) and client dashboard (frame 12:2) | Part | Founder: workspace/app/control/page.tsx:14-33, control/view.tsx:41-78; client: app/page.tsx:24-43 (#227, #225, #232) | Main still has placeholders: "Credits left —" and "Waiting on you … when connected" (page.tsx:37,39), "Health unavailable · GHOST-1", and disabled "Pause / Start · AGENT-1" and Ghost buttons (view.tsx:50,63,70). The Figma-based rebuilds of 12:2 and 10:115 (#331 spec) sit unmerged on origin/codex/dashboard (5124913, 3680b92) and origin/codex/control-panel (f2a5b5f). The dashboard branch drops the Credits/Waiting cards. |
| C11 | Each product on its own .tervory.com host (founder) | Built | workspace/lib/product-hosts.ts:22-34 (protect/autumbra/zenas/base/tiger/market-lab/tisan/radix/skala/tank), used in middleware.ts:28-50 (#302, #303) | Host-to-path rewrite is in code. Rig, MCP and the site are separate Coolify services. DNS and Coolify domains cannot be checked from code. Public squad host UI (#306) was reverted (c8b3fc1), so squad hosts need sign-in. |
| C12 | CLI (founder: window + CLI) (CLI-1) | Not started | Brief only: docs/cursor/CLI-1-tervory-cli.md. Searched for a cli/ dir (absent), personal_access/access_token in tank/schema.sql and command.py, and `git log --all --grep CLI-1` | No CLI package and no personal access tokens. The window's /v1/command contract it would use does exist (tank/command.py). |

### D. Memory and agent brains

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| D1 | Three tiers: sealed client memory per agent per tenant; de-identified agent platform memory; read-only platform reference corpora | Part | Tier 1: hermes/README.md:7, hermes/store.py:16-20 (mem_<agent>, tenant filter), agents/_chassis/chassis/memory.py:1-5 (#30). Reference corpora: zenas_pool schema agents/_chassis/chassis/roles.py:17,94-98 | Only sealed per-agent/per-tenant memory exists. There is no de-identified platform memory tier in Hermes, and no platform-wide read-only reference tier (zenas_pool is the Zenas room's own schema). PLATFORM_TENANT exists for training data (tank/training.py:140-141), not memory. |
| D2 | Learning record: row first (claim, evidence, confidence, last-verified), vector second; re-embed on model change | Not started | hermes/store.py:41-49 (Memory: text, kind, sources, meta, seen); hermes/qdrant_store.py:47-76 (Qdrant only); hermes/runtime.py:26 (HERMES_EMBED_MODEL) | Memory is vector-only in Qdrant: there is no Postgres record row first. It has no claim/evidence/confidence/last-verified fields (only `sources`) and no re-embed when the model changes. |
| D3 | Publish rule: client learning → platform memory only via a de-identifying publish step, logged | Not started | Searched publish/de-identify/platform memory in hermes, tank, agents. Training only exports PLATFORM_TENANT public rows: tank/training.py:140-141,545-549 (fe1a430) | No de-identifying publish step and no publish log. Today client data can never reach the platform at all, which is a hard wall rather than the planned gated path. |
| D4 | Stores: Postgres records, Qdrant vectors per tier/agent/tenant with scoped keys, Redis session | Part | Postgres per-agent schemas: agents/_chassis/chassis/roles.py:127-145, db.py:33-55. Qdrant: hermes/qdrant_store.py:47-56, one key hermes/runtime.py:28 & docker-compose.yml:57,77. Redis: tank/main.py:696-702 | Postgres records are built. Qdrant has one collection per agent with a tenant payload filter, not one per tier/tenant, and uses a single shared QDRANT_API_KEY rather than scoped keys. Redis is used only for the rung-4 cache, with no session store. |
| D5 | Founder: every squad member has its own Hermes Agent brain, own browser, own computer, shares nothing | Part | Hermes Agent (NousResearch, pinned commit) brains: agents/base/Dockerfile.brain:7-24, agents/rig/Dockerfile.brain:7-12 (#318). Per-room services: agents/base/docker-compose.yml (brain, sandbox, browser), agents/rig (brain, sandbox, browser), agents/tiger & agents/ghost (browser only) | Only Base and Rig have a brain plus browser plus sandbox ("computer"). Tiger and Ghost have a browser but no brain. Market Lab, Radix, Tisan and Zenas are a single service with no brain, browser or sandbox. |
| D6 | Founder: agents learn in parallel as the build continues; nightly cycle (gold intake, bench, evals, morning report) | Part | Daily bench loop: tank/bench.py:1,60-65,260-300,347-357, router mounted tank/main.py:3769. Gold intake per day: tank/training.py:404-421. Retest job endpoint tank/gold.py:397 (require_job). Backup nightly jobs/train/backup.py:1-5 | The daily bench runs inside Tank (needs a LiteLLM key, capped by TANK_BENCH_MAX_USD). No trigger for the gold retest/export jobs was found (.github/workflows/retest.yml is workflow_dispatch only). There is no morning report code (searched "morning"). |

### E. Squad contract and event bus

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| E1 | Shared job contract {tenant_id, region, agent, skill, input, priority, engine} | Part | Tank RouteRequest tank/main.py:588-600 (tenant_id, region/home_region, agent, skill, priority, messages); chassis job row agents/_chassis/chassis/db.py:35-50 and JobContext jobs.py:10-20 (tenant_id, kind, input) (#17) | No single shared contract. The room job table has no region, skill, priority or engine. Tank's request has no `engine` (only Base passes engine, agents/base/app.py:244). |
| E2 | Event bus: Redis Streams, one stream per tenant per event type, consumer group per agent | Not started | Searched xadd/xreadgroup/xgroup/redis stream/pg_notify/event bus in tank, agents, hermes, workers, jobs | No event bus. Redis only serves the rung-4 cache (main.py:696-702). |
| E3 | Events: base.record.enriched, tiger.price.changed, marketlab.signal.scored, zenas.regulation.changed, radix.finding, tisan.build.ready | Not started | Searched all six event names (base.record.enriched … tisan.build.ready) repo-wide | None of the events exist. Only the `agent_radix.findings` table name matches, in tests. |
| E4 | Agents only call Tank; own Postgres schema; never another agent's storage | Built | Own role and schema with search_path, public revoked: agents/_chassis/chassis/roles.py:104-145. Agents call Tank and Hermes via chassis (chassis/tank.py, memory.py). Probe agents/check_isolation.sh:1-8 (#17) | No agent-to-agent storage access found (the only cross-URL is base-brain to its own room, agents/_brain/runner.py:108). Tank itself reads agent_* schemas (tank/base_repository.py, training.py), which the rule allows because Tank is not an agent. |
| E5 | Network isolation: Tiger and Radix in isolated networks; sealed rooms | Part | Tiger sealed browser net agents/tiger/docker-compose.yml:92-94; Radix internal proxy-link agents/radix/docker-compose.yml:98-102 and tervory-gw-radix "--internal" docker-compose.yml:437-442; live check ops/seal-check.sh:1-30 (base/radix/tiger/rig must be sealed) | Radix's internal corridor depends on a hand-made `docker network create --internal` (a comment, not code). The main-stack `tiger` browser service also sits on the default network (docker-compose.yml:174-185). Sealing is verified only by running seal-check.sh by hand, not in CI. |

### F. Base

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| F1 | Pass 1 entity resolution (Google Places, OpenCorporates, engine registry, RapidFuzz) | Part | tank/skills/base.resolve/1.0.0/run.py:1-35 (RapidFuzz token_set_ratio, same-state pool, city bonus); agents/base/pipeline.py:272-293 (pass 1b + engine registry match on ATF licence, confidence 100); tank/vendor_meter.py:20-21 | RapidFuzz and the engine registry are built. Google Places is only metered/priced (vendor_meter.py, base_product.py:31); no code calls it. OpenCorporates appears only as a skipped host (find_site 1.7.0 run.py:26); no fetcher. |
| F2 | Pass 2 web discovery (search, Firecrawl), products and contacts | Part | tank/skills/base.find_site/1.7.0/run.py:431 (SearXNG), :446 (Brave, key-gated), :100 (Tiger render); tank/skills/base.scrape_site/1.2.0/run.py:1-5, :38; agents/base/access_sources.py:29-56 (retries, then Wayback/Common Crawl archive, dated); PR #108, #49, #231 | Search + site read built. Firecrawl replaced by own scrape_site + Tiger browser (no Firecrawl code). Contacts come from pass 2b; "products" are not extracted (extract 2.0.0 gives categories/services/description/people only). |
| F3 | Pass 3 contact discovery (email pattern, decision maker, phone verification) | Part | tank/skills/base.contacts/1.1.0/run.py:70 (learn_pattern), :84 (MX over DNS-over-HTTPS), :125-132 (pattern-derived address, decision maker); base.verify/1.0.1/run.py:60-65 (input phone vs site phone) | Email pattern and decision maker built. Phone verification is only "phone matches site"; no line/carrier/reachability check. |
| F4 | Pass 4 social discovery (Facebook, Instagram, YouTube) | Part | tank/skills/base.socials/1.0.1/run.py:1-20 (canonicalise FB/IG/YouTube/X/LinkedIn/TikTok links seen on site); agents/base/access_sources.py:59-84; tank/access.py:1101-1107 | Presence only, from links on the business's own site. Meta official API path exists but is off until META_APP_REVIEW_APPROVED=true (access.py:1106). No YouTube API, no activity scoring (run.py:5-6 says "later version"). |
| F5 | Pass 5 business data (size, revenue band, reviews, industry code, tech stack) | Part | tank/skills/base.business_data/2.0.0/run.py:1-8, :296-323 (size band, revenue band from engine table, NAICS from engine table; pure code); PR #45 (C13) | Size, revenue band and industry code built (estimates, confidence capped at 60). No reviews, no tech-stack detection anywhere in Base. |
| F6 | Pass 6 industry engine (FFL: licence type, SOT, expiry, compliance flags) | Part | tank/skills/ffl.profile/1.1.0/run.py:11-21 (licence types), :42-50 (expiry decode), :91-116; agents/base/pipeline.py:443-469 | Licence type, expiry, renewal window, lapsed built. SOT and compliance flags are hard-coded null "not in the public list" (run.py:114-116). |
| F7 | Pass 7 verification, cross-source, staleness, confidence 0–100 and bands | Built | tank/skills/base.verify/1.0.1/run.py:1-8, :60-90 (cross-source checks: phone vs site, email domain vs site, MX), :110-118 (0-100 score, tiers ready/use_with_awareness/review/requeue) | Staleness is a thin heuristic only ("site_thin_or_stale", run.py:110-112); there is no crawl-date or age check. |
| F8 | Source-reliability scores in platform memory | Not started | Searched "reliab", "source_score", "source_trust", "playbook" in tank/, agents/: no hits. Base memory use is a heartbeat only (agents/base/app.py:57-62) | No per-source reliability scores stored anywhere. |
| F9 | Learning sprint vs Apollo, ZoomInfo, Hunter, Clearbit | Part | tank/base_product.py:281-315 (Apollo CSV import + side-by-side comparison); agents/base/sources/context_dev.py, trial.py:12-30 (Context.dev Brand trial, founder button); PR #183, #195 | Apollo only via an uploaded CSV; Context.dev trial exists. No ZoomInfo, Hunter or Clearbit code (only as skipped hosts in find_site). No "learning sprint" loop. |
| F10 | Client upload a list → verified CSV out with sources and receipt | Built | tank/base_product.py:168-180 (POST /uploads, grouped by state), :213-247 (records.csv); tank/base_metrics.py:179-195 (per-field source_url, checked_at, reason columns); workspace/app/base/reference-workflow.tsx:69 (CSV upload), :118-123 (cost receipts panel); PR #339 | Receipts are shown on the page from the ledger (base_product.py:249-279), not inside the CSV file. |
| F11 | Full ATF list state by state (founder: fewest FFLs first) | Part | tank/base_repository.py:17 (ATF complete-list URL), :149-166 (refresh needs an existing file); agents/base/engines/ffl/reference.py:1-4, :157-182; tank/base_product.py:151-166 (state campaign from reference); tank/base_repository.py:241 | State-by-state campaigns exist, but campaign order is `sorted(groups)` = alphabetical (base_repository.py:241), not fewest-first. Smallest-first only on the room's split_by_state path (agents/base/app.py:289, pipeline.py:181). An empty DB cannot download the first ATF file on main; that fix is on unmerged origin/codex/base-atf-download. |
| F12 | Case study audit: 200-record hand audit, confidence histogram, cost per verified record from ledger, Apollo comparison page | Part | workspace/app/base/reference-workflow.tsx:118 (cost per verified record from ledger); tank/base_product.py:281-315 + reference-workflow.tsx:60-68 (Apollo comparison) | Cost per verified record and Apollo comparison built. No 200-record hand-audit tool and no confidence histogram (grep "histogram", "audit" in Base: none). |
| F13 | Founder: Base must not need a model where code can do it; browse like a human | Built | tank/skills/base.extract/2.0.0/run.py:1-8 and base.business_data/2.0.0/run.py:1-8 (no model); agents/base/pipeline.py:94-103; agents/_brain/browser.py:1, :84-86, :389 (persistent cookies, human checks recorded not solved); tank/base_public_http.py:1-5; PR #45, #231 | Every pass has a code version. Which version is approved is DB state (not checkable here); 1.x model versions still exist, and the optional Hermes brain (BASE_BRAIN_URL, agents/base/base_brain.py) is a model path. |

### G. Tiger

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| G1 | Fetch: curl-cffi static, Playwright rendered, ChangeDetection.io watch-and-diff | Replaced | Rendered: tiger/app.py:1-12, :28 (Playwright Chromium) and room browser agents/_brain/browser.py (agents/tiger/docker-compose.yml:40-55). Static: agents/tiger/app.py:86-95 (httpx). Watch-and-diff: agents/tiger/watch.py:337-370, change_alert.py:1-5; PR #99, #335 | No curl-cffi and no ChangeDetection.io in code; plain httpx and Tiger's own watch/diff do the job. |
| G2 | Sessions (Steel.dev) where terms allow | Replaced | tiger/app.py:13-16, :186-243 (per agent/tenant browser contexts, cookies saved); agents/_brain/browser.py:389, :511, :643 (storage_state persisted) | No Steel.dev; own Playwright sessions instead. |
| G3 | Residential proxies; CapSolver (BP1/BP2) — note founder rule: no captcha solving | Dropped | tiger/app.py:10-12 (no CAPTCHA solving, no stealth); agents/_brain/browser.py:84-86 (human checks detected, recorded); tank/base_public_http.py:1 (no identity spoofing or block bypass) | CapSolver ruled out by "no captcha solving". Residential proxies: no code (BROWSER_PROXY_URL at agents/tiger/docker-compose.yml:53 is the internal egress gateway). |
| G4 | Site playbooks per domain in platform memory | Part | agents/tiger/page_guard.py:1-5, :30 (learn_layout), :72 (layout_from_evidence); agents/tiger/watch.py:1069-1071 | A price layout is learned per watched URL and kept in that URL's observation evidence. Not per domain and not in platform memory. |
| G5 | Alerts: price drop/rise, out of stock, new product, below cost, market gap; email + Workspace push | Part | agents/tiger/watch.py:337-370 (price move past threshold, stock change), :610-618 (alerts table), :1127-1129; workspace/app/tiger/view.tsx:147, :227 (alerts list) | Only price and stock alerts. No new-product, below-cost or market-gap alert. No email is sent: no Resend/SMTP/webhook code in agents/tiger, tiger/ or Tank for Tiger; alerts are only shown when the Workspace page is opened. |
| G6 | Storage tiger.price_history, tiger.watchlist per tenant | Built | agents/tiger/watch.py:576-620 (watchlist UNIQUE(tenant_id,url), observations, alerts, all tenant_id); agents/_chassis/chassis/db.py:13-16 (schema agent_tiger) | Tables are agent_tiger.watchlist and agent_tiger.observations (price history), not "tiger.price_history". |
| G7 | Schedule (check every X hours) | Built | agents/tiger/watch.py:112-113 (per-tenant dispatch schedule every minute), :213-268 (`every` like 6h, watch_is_due), :1153-1164 (dispatch_tenant) | none |
| G8 | Tiger → Market Lab events | Replaced | tank/market_lab_routes.py:115-131 (Market Lab reads Tiger watchlist + observations through Tank); agents/market_lab/engines/ffl/warnings.py:32-42 (tiger_price, tiger_stock as outcomes); PR #350 | Market Lab pulls Tiger data; Tiger does not push events. |
| G9 | Scope rule: public pages only; portals via feed/API | Built | agents/tiger/watch.py:143-175 (public http(s) hosts only, private IPs refused), :1037-1046 (official feed first), :1056-1058 (portal item only via client connection); tank/access.py:598-601 (/feeds/price) | none |

### H. Market Lab

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| H1 | Feeds: FRED, UN Comtrade, MarineTraffic, Freightos, USPTO, Federal Register, SEC EDGAR, Reddit, RSS, SearXNG, LME | Part | FRED: agents/market_lab/core/jobs.py:330-364 (live, not stored), tank/skills/market.series_fetch/1.2.0/run.py:22-35. Federal Register: agents/market_lab/feeds/fetch.py:216-231, feeds/engines/ffl/sources.py:114-121. Keys: feeds/keys.py:21-31; PR #31, #105 | Of the 11 named, only FRED (off until FRED_API_KEY) and Federal Register have fetchers. None for UN Comtrade, MarineTraffic, Freightos, USPTO, SEC EDGAR, Reddit, RSS, SearXNG, LME. Code uses others instead: Census trade (sources.py:140), Port of LA (:213), BTS freight (:232), World Bank commodities (:169), plus Census, LegiScan, eCFR, EIA, NOAA, FWS. |
| H2 | GPT-Researcher with SearXNG + Tank | Replaced | tank/research.py:1-7, :164-171 (Perplexity presets via LiteLLM, policy-gated, receipts); agents/market_lab/core/research_adapter.py:10-31; tank/skills/market.research/1.1.0 (code-first lookups, PR #180) | No GPT-Researcher or SearXNG. Paid research stays off until a policy promotes a preset (research.py:166). |
| H3 | Signal classifier (rung 2 target) | Part | agents/market_lab/core/pure.py:33 (surge_detect), :74 (shift_detect); tank/skills/market.surge_detect, market.shift_detect | Rule-based move detection only. No signal classifier (no rung-2 model or trained classifier). |
| H4 | Causal chain mapper (frontier via Tank, engine supply map) | Part | agents/market_lab/core/warnings.py:48-83 (upstream→downstream pairs); agents/market_lab/engines/ffl/warnings.py:35-60 (port/freight → watched stock, "No causal claim is inferred") | One code-only chain type with lag statistics. No frontier causal mapper and no engine supply map. |
| H5 | Pattern library (Qdrant, platform memory) | Part | agents/market_lab/schema.sql:162-166 (warning_pairs episode summaries); agents/market_lab/core/jobs.py:234, :313 (reports saved to Hermes memory; hermes/qdrant_store.py) | Episodes are stored per pair and reports are remembered, but there is no pattern library in Qdrant that is searched or reused. |
| H6 | Prediction ledger marketlab.predictions with horizon, confidence, realised outcome | Part | agents/market_lab/schema.sql:54-68 (predictions: resolve_by, outcome, resolved_at, score); agents/market_lab/core/ledger.py:1-5 (insert-only); core/pure.py:132, :285; PR #33 | Table is agent_market_lab.predictions with horizon (resolve_by) and realised outcome/score. No confidence column. |
| H7 | Accuracy loop + calibration curves in Workspace; 90 days before external brief | Part | agents/market_lab/core/jobs.py:243-279 (resolve), engines/ffl/engine.py:102 (daily resolve); core/warning_stats.py:129-134 (hits, hit_rate); workspace/app/market-lab/warning-evidence.tsx:34 | Hit rate per warning pair is shown. No calibration curves and no 90-day gate before an external brief. |
| H8 | Brief writer; alert delivery (Resend email + webhook) | Part | agents/market_lab/core/jobs.py:216-234 (monthly opportunities write-up saved as a report); core/warnings.py:348 (cited warning text) | Brief text is written in code. No alert delivery: no Resend email or webhook code in Market Lab. |
| H9 | Airflow scheduling | Replaced | agents/market_lab/engines/ffl/engine.py:97-104 (daily refresh, monthly opportunities, daily resolve); agents/market_lab/app.py:158-180 (chassis cron schedules) | No Airflow; the chassis scheduler does it. |
| H10 | Founder: feed industry and history documents (MARKET-DOCS-1) | Part | workspace/app/market-lab/view.tsx:466-484 (CSV/XLSX/PDF drop zone); plugin-actions.ts:66-71 → workspace/lib/tank.ts:542-556 (POST /v1/vaults/lab.vault/files) | Upload screen exists, but Tank on main has no /v1/vaults route (no Python match; tests/base_proof/real-job-output.txt:24 shows 404), so it is effectively off. No reading into passages, no citing file/page, no forget. Research only uses passages a caller passes in (agents/market_lab/app.py:88-109). |
| H11 | Founder: opportunity/prediction layer — thin supply, bottlenecks, ATF baseline + legislation + shipping + weather | Part | agents/market_lab/core/pure.py:42 (gap_score), :249; engines/ffl/engine.py:74-90 (supply = ATF listing counts, demand = NICS checks + uploads, products); core/jobs.py:162-240 (ranked opportunities + predictions); engines/ffl/warnings.py:8-24 | Thin supply / gap ranking and shipping → availability warnings exist. Legislation (LegiScan) and weather (NOAA) are collected only as notices and do not feed the scoring; LegiScan and NOAA climate stay off until their keys are set (feeds/keys.py:22-28). |

### I. Radix

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| I1 | Static: Semgrep, Gitleaks, Checkov, npm audit/Safety, Socket.dev | Part | Semgrep: agents/radix/scanlib/static.py:54 + scanlib/semgrep.yml. Gitleaks: scanlib/secrets.py:53. The scan runs both plus deps: scanlib/orchestrate.py:47-51 (RX1 #47). | **Replaced:** npm audit/Safety are replaced by baked OSV data (scanlib/dependencies.py:25; Dockerfile:6-13; caf35b6). **Missing:** Checkov and Socket.dev, which have no code anywhere. |
| I2 | Dynamic: OWASP ZAP, Nuclei | Not started | Searched for zaproxy/owasp zap/nuclei. The only "nuclei" hit is a blocked bot User-Agent in agents/ghost/shields.py:44. The README says "Run exploits ... never" and that target ownership proof is "a later skill". | No dynamic scanning code. |
| I3 | Infra: Nuclei, Nmap, testssl.sh, dnsx (weekly) | Part | agents/radix/live.py:257 (header check) and :316-386 (TLS version/name/dates), for `https://lokd.co.za` only, via egress proxy (#95, #107). It runs by hand (`python live.py`, live.py:439) and is not a job (app.py:60 has handlers ping/scan only). | Nmap, testssl.sh, dnsx and Nuclei: no code found. No weekly schedule. Only one allow-listed host. |
| I4 | Compliance: axe-core WCAG, cookie audit, GDPR/POPIA/CCPA, PCI checklists, engine rules | Part | `comply.gdpr` checks for GDPR/POPIA privacy and cookie notices on a saved HTML page: scanlib/comply.py:244-296 (#121). axe-core exists only in the Tisan template (agents/tisan/templates/next-site/e2e/a11y.spec.ts). Business-verification skills: verify/routes.py:78 (#144). | comply is not a service job. It checks only that a notice exists. No CCPA, PCI, cookie-behaviour audit or engine-rule compliance. |
| I5 | Monitoring: Uptime Kuma, SSL expiry, HIBP, checksum change, ClamAV | Part | Certificate-expiry warning (<14 days) in live.py:380-386, manual run only. | Uptime Kuma, HIBP, checksum-change watch and ClamAV: no code found. Nothing scheduled. |
| I6 | Deploy gate: critical findings block deploy; applied to Tervory's own repo first | Part | A scan sets `deploy_blocked: critical > 0` (orchestrate.py:78), but nothing reads it. CI's "Secret scan" is a regex test, not Radix (.github/workflows/ci.yml:142-145 → tests/test_secrets.py). deploy-on-merge.yml has no Radix step. | Not wired as a gate on Tervory's own repo. Own-repo scans were manual (runbook docs/ops/SUN-RADIX-osv-redeploy.md:169; commit 318bdc3 "clear Radix criticals"). |
| I7 | Plain-language report writer | Part | One-sentence plain-English summary: orchestrate.py:20-28. Each finding has a `fix` field (:12). The workspace Reports tab only shows a hard-coded example: workspace/app/radix/content.ts:41, view.tsx:127-129. | No report writer turns a real scan into a client report. The workspace chat (request-service.ts:97-106) gives guidance only and says it cannot run a scan. |
| I8 | Tisan integration and Zenas → Radix signal | Not started | Searched agents/tisan, agents/zenas, workspace/app/tisan and workspace/app/zenas for "radix". The only hit is UI copy: workspace/app/tisan/tisan.tsx:478 ("Coolify deploy ... Radix scan is clean", shown Off). | No Tisan→Radix call and no Zenas→Radix signal. |
| I9 | Client upload of a repo → report (25 Oct list) | Part | The full archive scan is open only to the **Ghost corridor**: tank/ghost_routes.py:270-286 (`require_ghost`, platform tenant). Client paths are limited. (a) Command tool `radix.scan` (tank/command.py:36, :772-773, :825) sends up to 20 pasted text files to the Skala `scan.static` skill only, and only for tenants whose squad the founder has enabled (command.py:93, :257-276). (b) workspace/app/radix/requests/route.ts:31-41 → request-service.ts:106 makes a `tier0.answer` chat task, not a scan. (c) Vault upload accepts only CSV/XLSX/PDF (workspace/app/radix/plugin-actions.ts:33). | No route lets a client upload a repo (tar/zip/bundle) and get the 3-tool scan plus a report. |
| I10 | Weekly self-scan of Tervory | Not started | Radix's only schedule is the 5-minute ping heartbeat (agents/radix/app.py:61-68). Searched .github/workflows/*.yml for radix/semgrep/gitleaks/scan: none apart from the ci.yml regex step. | No weekly self-scan job or workflow. |

### J. Tisan

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| J1 | Brief → Figma design gate → architecture → build (Aider via Tank) → QA + deploy | Part | Separate pieces exist. Room jobs `scaffold` and `figma`: agents/tisan/app.py:63-72, :87 (TS1 #44, TS2 #98). Command tool `tisan.scaffold`: tank/command.py:35, :824. Aider exists only in workers/ (Tervory's own build workers; workers/task/requirements.txt, tests/test_workers_1.py:270). | No pipeline links brief → Figma design gate → architecture → Aider build → QA/deploy. Aider is not used by Tisan. |
| J2 | Figma MCP reader: tokens, components, layouts; component manifest; style contract | Part | agents/tisan/figma.py:1-8, :66-70, :379-404: tokens, Tailwind config, component manifest, conflicts/gaps (#98). Visual frame data: #191, #194. | It reads only the recorded fixture fixtures/tervory-landing.json and makes no live Figma/MCP call (README "Figma reader"). Gaps: no spacing/type variables in the fixture. |
| J3 | Project scaffold (Next.js + Tailwind + TS) | Built | agents/tisan/scaffold.py:37-40 (npm ci/lint/build/test), packs to /data/builds (:3). Template agents/tisan/templates/next-site/package.json: next 15.5.28 (:19), tailwindcss 4.3.3 (:36), typescript 5.9.3 (:37) (TS1 #44, TS-3 #96). | Generates home/about/contact/privacy pages only. |
| J4 | Ecommerce module, quote-form state machine | Not started | Searched templates/next-site for cart/checkout/quote/ecommerce/state machine: no hits. The contact form posts to /api/contact and is not stored (README). | No ecommerce module and no quote-form state machine in Tisan. |
| J5 | QA: Playwright, Lighthouse CI, axe-core, k6, pixelmatch; Radix scan | Part | The generated project's CI (templates/next-site/.github/workflows/ci.yml) runs Playwright (package.json:14, :27), axe-core (e2e/a11y.spec.ts), Lighthouse CI (package.json:15, lighthouserc.cjs; 0a6157d), and a custom visual frame score (e2e/visual.spec.ts:3, :32-39; #191). | **Missing:** k6 and a Radix scan. **Replaced:** pixelmatch, by a custom scorer (visual/check). Browser checks run in the client project's GitHub Actions, not in the room. |
| J6 | Coolify staging → production via API (no docker socket) | Not started | Searched agents/tisan for coolify: none. The deploy gate never deploys (templates/next-site/scripts/deploy-gate.cjs:406-407 "Nothing was deployed"). The UI shows "Coolify deploy" as Off (tisan.tsx:478). | No staging→production via Coolify API. |
| J7 | Build log to Hermes; founder: Tisan learns to build | Part | Hermes write is only the heartbeat (agents/tisan/app.py:50-56). "Learns": founder gold approvals in workspace/app/tisan/gold-actions.ts:24-31 and gold export agents/tisan/gold_sources.py (#176). | No build log to Hermes. Training is limited to gold candidates. |
| J8 | Client request form, preview link, feedback, revision, hand-over (25 Oct list) | Part (UI shell, off) | workspace/app/tisan/tisan.tsx forms do nothing beyond preventDefault. "Start a build" `<form onSubmit={e=>e.preventDefault()}>` (:508) does nothing else. Composer `send` (:89-96) calls the local `replyTo` (copy.ts:91-105: "Nothing was sent, and no build was started."). Search form (:267) also only calls preventDefault. Only Plugins (vault) and founder gold review make real server calls. | No client request backend, preview link, feedback, revision or hand-over. The only route to a build is Command `tisan.scaffold` for enabled tenants. |

### K. Zenas

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| K1 | Regulatory monitoring: Federal Register, Congress.gov, state legislatures; ZA Gazette; EUR-Lex; daily; plain-language change alerts | Part | Ingest adapters: agents/zenas/pool/adapters/federal_register.py, ecfr.py, govinfo.py, states.py (Delaware/NY/Texas, :47, :163, :235), za_gazette.py. Nightly runner pool/nightly.py:50, :547 (`python -m agents.zenas.pool`). | **Not scheduled:** there is no cron/caller (compose has only a one-shot loader profile, docker-compose.yml:41-67). **No code:** Congress.gov, EUR-Lex, change detection, plain-language change alerts. ZA sources fall under K7 (stopped). |
| K2 | Document automation (Docassemble templates): contracts, NDAs, SLAs, distributor agreements, letters | Replaced | No Docassemble (searched). Drafts are assembled from an approved-clause library with templates nda, supply, distribution, services and others: agents/zenas/core/drafting.py:15-24. Room route `POST /drafts` (agents/zenas/app.py:874), Z5 #59. | No SLA or letter templates. There is no workspace route or Command tool for drafts (workspace/app/api/zenas has no drafts; tank/command.py:826-828). |
| K3 | Research: RAG over CourtListener, Justia, US Code, SAFLII, EUR-Lex with citations | Part | Retrieval by citation and full text from the pool: core/service.py:320-345. cite_check: core/engine.py:444. Sources: CourtListener bulk (pool/adapters/courtlistener_bulk.py, #167), US Code via govinfo/USLM (pool/uslm.py), SAFLII adapter (za_saflii.py, off). | Meaning (vector) search is a no-op until Hermes embeddings are wired (pool/embed.py:1-5; search.py:20-26). No Justia or EUR-Lex. PR #326 (7c3cc67) kept source links in answers; its branch was deleted unmerged. |
| K4 | Compliance checks (engine rules) and signal to Radix | Part | Regulatory areas export_controls, customs, sanctions and firearms_permits (core/areas.json:19) are flagged needs_lawyer: core/scope_rules.py:80-81, :125-133. | No compliance-check engine beyond scope flagging. No signal to Radix (no "radix" in agents/zenas). |
| K5 | Alerts via Resend + Twilio | Not started | Searched agents/zenas, tank and workspace/app for resend/twilio: no integration (the one "resend" hit, workspace/app/chats/window.tsx, is unrelated). Alert timings are static copy: workspace/app/zenas/frame.ts:84-88. | No email or SMS alert sending. |
| K6 | Disclaimer and citations on every output; civil only, refuse criminal (founder) | Part | **Criminal refusal is built.** REFUSED text is at core/scope_rules.py:17. Rules decide first: :78-83, :121-125. A model hint cannot override: :172-187. It is enforced before skills in core/matters.py:96-126 and service.py:123-133, and release is also gated (service.py:1069-1072). Bail/theft are refused per ede995f. **Citations:** answers without sources are hidden (workspace/app/api/zenas/rules.ts:281-282) and cite_check runs (engine.py:444). | **Disclaimer:** only a page footer (workspace/app/zenas/view.tsx:478, "legal information, not legal advice"). It is not attached to each answer, memo or draft output. |
| K7 | Founder: full SA law library (all legislation), precedent with court weight; ZA stopped for now (25 Oct) | Stopped | ZA code exists: pool/adapters/za_*.py, Z9 gov.za Acts (#171), Z12 precedent with court weight (core/precedent.py, core/precedent_rules.json, #204). docs/ops/ZENAS-LIVE-SUNDAY.md:29 says the ZA region is down and the SA library is not loaded; :18 says SAFLII is off pending permission. | Founder stopped ZA work on 25 Oct. PR #326 (c433fca) would have restricted active routing to Boston; its branch was deleted unmerged. |
| K8 | Review/release flow: answer → reviewer releases → client sees release | Part (exists but off) | The flow exists. Reviewer UI workspace/app/review/desk.tsx:24 → workspace/app/api/zenas/matters/[id]/release/route.ts:17-67 (requireReviewer, jurisdiction check, admission no.) → agents/zenas/app.py:752 → core/service.py:1042-1088 (records review, sets "released"). The client sees released docs only: service.py:1227-1235 and workspace/app/matters/page.tsx (#274, #280). | **Review switch defaults off:** core/review_switch.py:16, .env.example:79. With it off, a memo that passes cite-check is auto-released to the client with no reviewer (service.py:1798, :1651). This follows the founder's decision that lawyer approval is not a gate. |
| K9 | MOOT-1: AI moot court (text court first) | Part | MOOT-1a text court on fixtures (#267, #303). agents/zenas/core/moot/: counsel is stubbed (session.py:41-52, `_STUB_COST_PER_TURN`). Judge is deterministic: "Deterministic text ruling for fixtures" (judge.py:93-103). Made-up citation flags: judge.py:17-40. Room routes: app.py:1091, :1132 (ai-ai), :1146 (student), :1168 (publish). Watch page reads hard-coded FIXTURES (workspace/app/moot/store.ts:17-40). Zenas tab is a placeholder (workspace/app/zenas/moot-court.tsx). | No model-driven AI counsel or judge, no real decided appeal as the problem, no persistence of matches. MOOT-1b (voice) is not started. |

### L. Rig

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| L1 | Rig is industry-neutral; Custom Nation is only a skin (`theme="custom-nation"`) | Part | Widget themes `neutral` + `custom-nation` in `agents/rig/rigbox/quotes/widget/tervory-rig.3dff…umd.js:1`; root route `agents/rig/rigbox/page_route.py:80-83` serves v5 "Archon fixtures"; `agents/rig/catalogues/archon/products.csv:2` ("Archon Firearms", "Demo price"); CN-only module `agents/rig/rigbox/cn.py:1-5`; `workspace/app/rig/copy.ts:46,113,178` (Staccato demo) | The widget code is neutral. But rig.tervory.com `/` and the Workspace Rig pages show a firearms demo catalogue. |
| L2 | Rig's own box (RIG-2): own Hermes brain through Tank (`agent.rig.think`), sealed sandbox, browser behind its own gateway, raw compose, seal-check | Built | `agents/rig/docker-compose.yml:72,103,128,151`; `agents/rig/rig_brain/service.py:56-60`; `tank/schema.sql:1051`; `ops/seal-check.sh:39,49-50`; PR #248, #252, #318 | Whether the box is live on Coolify can't be checked from the repo. |
| L3 | Storage and receipts: `tervory-rig` R2 with `R2_ACCESS_KEY_ID_RIG`, per-tenant memory, a receipt for every step | Built | `agents/rig/docker-compose.yml:20,191`; `agents/rig/rig_brain/service.py:32-60` (receipt per task), `:50` memory | The credentials are names only; their values are in Coolify. I did not check the paid-work pause. |
| L4 | Public API and skills (search, setups, explain, ask, fit_suggest) via Tank; hashed publishable keys with origins and rate limit; tenant isolation | Built | `tank/schema.sql:582-586` (policy rows); `agents/rig/rigbox/logic.py:279-305` (one total); `agents/rig/rigbox/quotes/limits.py:70-72`; `tests/test_rig_isolation.py:65` | R3 and PRs #199/#202. |
| L5 | Rig takes every feed it is fed: CSV/TSV, XLSX, XML/Google Merchant, JSON/Shopify/WooCommerce, ACCESS distributor feeds, one interface | Built | `agents/rig/rigbox/feeds/mapper.py:15,35-55`; `agents/rig/rigbox/feeds/catalogue.py:73,138-151`; `tank/access.py:29,587-593` (ACCESS reuse); PR `110e84d` | Proven only on the sample feeds; no real supplier is connected (as the plan intends). |
| L6 | Delivery by upload, scheduled URL (nightly plus "Refresh now"), or API connection with credentials stored by name | Built | `tank/access.py:1005` (`rig_feed_loop`), `:684` (vault.seal), `:697` (refresh); `agents/rig/app.py:372-380` (cron `0 3 * * *`) | — |
| L7 | Per-feed field mapping: Rig suggests, a person confirms, the map is saved | Built | `tank/access.py:924-932` (`mapping` / `confirm-mapping` with preview_id); `workspace/app/rig/admin/retailer-admin.tsx:62-80`; `agents/rig/rigbox/feeds/catalogue.py:216` | — |
| L8 | Each feed declares currency, country, and cost vs selling price | Built | `tank/rig_feed_mapping.py:18`; `agents/rig/rigbox/pricing.py:35-40` (selling price, FX only) | — |
| L9 | Feed safety: size limits, no XML entities or DOCTYPE, never fetch a private address | Built | `agents/rig/rigbox/feeds/catalogue.py:37-40`; `agents/rig/rigbox/feeds/mapper.py:164`; `tank/access.py:525-527` (8 MB), `:629-631` (global addresses only) | — |
| L10 | All-or-nothing import per file, with `{added, updated, rejected}` on a receipt | Built | `agents/rig/rigbox/service.py:759-769`; `agents/rig/rigbox/retailer_store.py:88` (transaction) | — |
| L11 | Landed-cost rule kept on the server (cost, freight, duty, margin, FX), one indicative price; cost never reaches the browser | Built | `agents/rig/rigbox/pricing.py:1,53-67`; `tests/test_rig_feeds_pricing.py:14-25` | — |
| L12 | Fitment: feed fits, `rig.fit_suggest` rows as `suggested`, an approval queue; nothing reaches a shopper until approved | Built | `agents/rig/rigbox/logic.py:164` (`approved`); `agents/rig/rigbox/retailer_api.py:66-80`; `agents/rig/rigbox/page/admin.html` ("Fits to review") | — |
| L13 | Retailer admin `/rig/admin`: feeds, price rule, setup templates, fit queue, "what shoppers couldn't find" | Built | `workspace/app/rig/admin/retailer-admin.tsx:110-144` | #353 changed the "sample file" copy to "catalogue file". |
| L14 | Tiger updates price and availability (never fitment) for products with no feed | Part | Receiver `tank/access.py:976-982`; `agents/rig/rigbox/catalogue.py:97-105` (fitment dropped) | Nothing in `agents/tiger/` calls `/rig/tiger`, so only the receiving end is built. |
| L15 | Sample feeds: US CSV (USD), EU XML (EUR), NZ JSON (NZD), .xlsx, store CSV (ZAR selling) | Built | `agents/rig/catalogues/samples/` (us-distributor.csv, eu-distributor.xml, nz-distributor.json, distributor.xlsx, store-catalogue.csv, shopify.json, woocommerce.json, google.xml) | These are test fixtures only. |
| L16 | Widget to Figma frames 01–05, including Explore graph and Ask, custom-nation theme | Built | `agents/rig/rigbox/quotes/widget/manifest.json` (bundle 17,710 B gzip); the bundle has explore/ask/graph screens (`…umd.js:1`); PRs `385d86c`, `28a9262` | How closely it matches Figma can't be judged from code. |
| L17 | `SAMPLE DATA` badge shows only when `sample` is true | Built | Bundle `…umd.js:1`: `e.results.some(S)?Y(t.sampleLabel)` where `S = attributes.sample===true`; 3D viewer `agents/rig/rigbox/three_d/widget/assets/viewer-3SqG96cb.js:3698` (`n.sample`); `agents/rig/rigbox/three_d/engine.py:23-30` (sample defaults to False) | #353 removed the badge from the widget. |
| L18 | No sample or demo data on any live screen (founder) | Part | #353 (merged 12:18 PT) removed the widget's "sample data" text and badge (no match in `agents/rig/rigbox/quotes/widget/tervory-rig.500d8e8c….umd.js`). Still on main: rig.tervory.com `/` v5 page `agents/rig/rigbox/page/v5/index.html:128`, `rig.js` sample suppliers; Workspace `workspace/app/rig/lab.tsx:219-220`, `search-view.tsx:462-463` | The root page and the Workspace lab/search pages still show the Archon demo catalogue (seen live at 12:2x PT). |
| L19 | Quote and link-quote requests stored and sent to the retailer's flow per tenant, with retries | Built | `agents/rig/rigbox/quotes/service.py:48-102`; `agents/rig/rigbox/quotes/senders.py:140-174` (webhook); `agents/rig/app.py:381` (`retry_quotes` every 5 min) | See L21 for email. |
| L20 | Odoo quotation adapter behind the sender interface, stubbed in tests, `RIG_ODOO_*` empty until last | Part | `agents/rig/rigbox/quotes/senders.py:43-137` (Odoo 16–18 JSON-RPC); `agents/rig/docker-compose.yml` `RIG_ODOO_URL: ${…:-}` | Built but switched off: never run against a real or test Odoo, and the "draft quotation reaches Odoo" proof is not done. |
| L21 | Quote requests delivered to the store by email while Odoo stays off | Part | #353: `EmailHandoff` (`agents/rig/rigbox/quotes/senders.py:140`), used when the store has an email and no webhook; `SMTP_*` names in `agents/rig/docker-compose.yml:30` (empty by default) | Built in code, proven only against a local fixture mail catcher. The SMTP settings must be set in Coolify before a real email can go. |
| L22 | Live publishable key for Custom Nation, limited to customnation.co.za and its test page | Part | Key issuing `agents/rig/rigbox/quotes/api.py:89` (admin key, exact HTTPS origins); `agents/rig/rigbox/quotes/README.md:85` ("No live key is generated by this change") | The mechanism is built. No live CN key exists. |
| L23 | UMD bundle hosted on a public, cache-busted path, under 150 KB gzip | Built | `agents/rig/rigbox/quotes/hosting.py:44` (SHA-256 + 150 KB check), `:87-90` (immutable caching); manifest gzip 17,710 B | — |
| L24 | Analytics as counts only (searches, setups, swaps, quotes, no-result searches), no tracking of people | Built | `agents/rig/rigbox/quotes/api.py:22-27`; `agents/rig/rigbox/api.py:189-195,308-310` | — |
| L25 | Store onboarding: upload CSV, map columns (Rig suggests, store confirms), preview, publish | Built | `workspace/app/rig/admin/retailer-admin.tsx` (suggest mapping, confirm, "Publish catalogue", quote delivery card); `agents/rig/rigbox/retailer.py` `set_settings` (#353) | It lives in the Workspace (`/rig/admin`), not on rig.tervory.com. Not yet run by a real store. |
| L26 | Embed snippet for the store's site | Built | `agents/rig/rigbox/quotes/keys.py:29` `embed_snippet` (SRI script tag and `<tervory-rig>`), admin card "Widget for your website" (#353) | Needs a saved delivery email and a published catalogue first. |
| L27 | First customer job: a real store CSV, embedded widget, 10 searches, 3 real quote emails received (Grok) | Not started | #353 proved it only against a local fixture SMTP catcher (`tests/rig_store_job/mail.py`, `evidence/job-output.txt`) | Needs SMTP configured and a live run with a founder-approved store CSV. |
| L28 | No distributor keys until the product works; stores upload their own CSV | Built | No distributor key names in `agents/rig/docker-compose.yml` or `.env.example`; feed credentials only through the admin, sealed by name (`tank/access.py:684`) | The rule holds on main. |
| L29 | RIG-5a: 3D frames 06–07 in Figma, founder-approved before 3D code is wired into the widget | Part | `agents/rig/rigbox/three_d/README.md:121-122` ("Until frames 06–07 are approved, the existing widget does not expose a 3D button") | Figma itself can't be checked from the repo. The widget has no 3D entry point. |
| L30 | RIG-5F forge: sealed `rig-forge` (Blender, gltf-transform, gltfpack, KTX, trimesh/manifold, validator), pinned and checksummed, egress allow-list | Built | `agents/rig/forge/` (tools.lock.json, install_tools.py, LICENSES.md, pipeline.py); `agents/rig/docker-compose.yml:173-208`; `.github/workflows/rig-forge.yml`; PR `558235e`, #254 | — |
| L31 | GPU jobs: Meshroom photogrammetry and TRELLIS 2 on Hugging Face Jobs, with cost cap and receipts through Tank | Part | `agents/rig/forge/gpu/` (Dockerfile.meshroom, Dockerfile.trellis2, reconstruct.py); `tank/rig_forge_routes.py`; `agents/rig/docker-compose.yml:39` (`RIG_FORGE_TRELLIS_ENABLED:-false`), `:193` (`HF_JOBS_TOKEN:-`) | Built but switched off: tested against a stub only, TRELLIS off, no token. |
| L32 | Automatic model check (faces outward, no holes, real mm size, budget) and glTF validator; failures never reach review | Built | `agents/rig/forge/model_check.py`; `tests/test_rig_forge_geometry.py`, `tests/test_rig_forge_pipeline.py` | — |
| L33 | 3D comes from photos only, never from AutoCAD/STEP/IGES/CAD files | Built | `agents/rig/rigbox/three_d/contracts.py:57` (jpg/jpeg/png only); `tests/test_rig_3d_engine.py:344`; PRs `fd88f98` ("remove CAD support"), #279 | — |
| L34 | Every model is a draft until a person approves it (scale, look, anchors) | Built | `workspace/app/rig/admin/three-d/` (screen, preview, actions); `agents/rig/rigbox/three_d/engine.py` | — |
| L35 | Mount points as named anchors; a part snaps only to an anchor an approved fit allows | Built | `agents/rig/rigbox/three_d/forge.py:120`; `agents/rig/rigbox/three_d/README.md` (admin supplies measured anchors, human approval) | — |
| L36 | `rig_3d` entitlement per tenant; three.js viewer as a lazy chunk; base bundle stays under 150 KB | Built | `agents/rig/schema.sql:266`; `agents/rig/rigbox/three_d/engine.py:30-37`; separate `three_d/widget/assets/viewer-*.js` | — |
| L37 | Kiosk mode: full screen, attract loop, cached catalogue, remote reset, quote to phone or email | Built | `agents/rig/rigbox/three_d/api.py:99-110`; viewer bundle `viewer-3SqG96cb.js:3698` (attract, full screen, reset, `/3d/quote`) | — |
| L38 | Billing: `rig_3d` plan add-on, price set by the founder, conversion costs on receipts | Part | `workspace/app/billing/rig-three-d.tsx:6-13` (needs `RIG_3D_PRICE_ID`); `agents/rig/rigbox/three_d/README.md:120` ("Purchase/Stripe synchronization is deliberately excluded") | Only the display is built; there is no purchase flow and the price is not set. Parked under rule 1. |
| L39 | The 3D upgrade must exist for Custom Nation (founder) | Part | The engine runs on neutral stand-ins (`agents/rig/rigbox/three_d/fixtures/`, `sample.py:1`); no 3D button in the widget (README:121) | Missing for CN: the entitlement, approved models and the widget wiring. GPU paths are off (L31). |
| L40 | Custom Nation's live shopper data moves to the ZA (Hetzner) host | Stopped | `docs/build/BUILD-LISTS-2026-10-25.md:137` ("ZA stays stopped"), founder 25 Oct | Boston only for now. |

### M. Autumbra

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| M1 | Air gap: Watch and Enforce are separate processes; only a validated `ThreatPayload` crosses; Enforce never reads raw input | Built | `agents/ghost/threat_payload.py`; `agents/ghost/enforce_apply.py:27-58` (TypeError on anything not a ThreatPayload); `agents/ghost/enforce_app.py` (own entrypoint); `agents/ghost/docker-compose.enforce.yml:51` (`internal: true`) | — |
| M2 | Tank one door: Autumbra holds no inference key; CI guard against direct provider calls | Built | `agents/ghost/dogfood_hf.py:22,72` (`/v1/route`, `reason.brief`); `tests/test_tank_one_door.py`; `.github/scripts/ci_scope.py` | — |
| M3 | One Enforce container per client on an internal network, with its own secret and queue; create/destroy receipts; capped per host | Part | `agents/ghost/enforce_lifecycle.py:11-12,183` (`FixtureComposeBackend` writes local project directories), `:26-32` (cap `None`, "held until measured") | There is no Coolify or compose backend that actually creates containers, and the cap is not set. |
| M4 | Isolation proved with `ops/seal-check.sh` and a network test from inside a client container | Part | `agents/ghost/enforce_isolation_probe.py:67-69`; `ops/seal-check.sh:40-41,223` ("missing is OK until dogfood") | Autumbra rooms are not in `EXPECTED_SEALED`, and the probe has not been run on a real host. |
| M5 | Never-block list: the client's own IPs, payment providers, Cloudflare | Built | `agents/ghost/never_block.py:17-55,99-118`; enforced in Enforce at `agents/ghost/enforce_apply.py:86-93` | — |
| M6 | The IP must appear in the raw log; plain rules decide first; AI is a second opinion only | Part | `agents/ghost/never_block.py:120-133` (`may_block_ip`); used at `agents/ghost/threat_queue.py:253`, `agents/ghost/app.py:822` | No AI second-opinion step exists: grepping "second opinion" in `agents/ghost` finds nothing. The rules side is done. |
| M7 | Actions per hour are capped | Part | `agents/ghost/never_block.py:136-152` (`ActionCap`, 60/h); `agents/ghost/threat_queue.py:514` | The cap is held in memory and, by its own docstring, resets on every restart. |
| M8 | Reversible shields applied immediately: block an IP, WAF rule, rate-limit a path, revoke sessions | Part | **Shields act on fixtures only.** Enforce applies `block_ip` only, and only to `FixtureEdgeControl` (`agents/ghost/enforce_apply.py:113-124`; `agents/ghost/fixture_edge.py:1-6` "not Cloudflare, not a live edge API"). WAF, rate-limit and revoke-sessions only produce a plan (`agents/ghost/shields.py:83-119`). Watch is dry-run only with an empty token (`shields.py:52-58,300-310`) | No real edge "hand" exists; Cloudflare and Google APIs are never called. |
| M9 | Health check after each shield, with automatic Undo if the site breaks | Part | `agents/ghost/enforce_apply.py:146-158` | The health check is `FixtureEdgeControl.health_check()`, which reads a boolean flag (`fixture_edge.py:62-66`), not a real site probe. |
| M10 | One-tap Undo | Built | `workspace/app/api/autumbra/undo/route.ts:66` → `agents/ghost/app.py:938` → queue → Enforce `undo_from_payload` (`enforce_apply.py:206`); signed token `agents/ghost/undo_token.py:6,24` (fails closed) | The chain works end to end, but it undoes a fixture rule (M8). |
| M11 | A receipt for every action (time, tenant, advisory, client setting, sources, budgets) | Built | `agents/ghost/enforce_apply.py:63-84`; `workspace/app/autumbra/receipts/weekly/[tenant]/page.tsx`; `workspace/app/api/autumbra/receipts/weekly/[tenant]/route.ts:37` | — |
| M12 | Code fixes arrive as a ready PR the client approves with one tap; never auto-merged | Part | `agents/ghost/patch_pr.py:1,18-19` (flag `GHOST_PATCH_PR_ENABLED`, off by default), `:224` (`draft: True`), `:230` (no merge method); `agents/ghost/patch_connect.py` | Switched off by default (dry run), and there is no client one-tap approve. Note: `client_settings.py:17-20` offers "Apply automatically when checks pass", but it only picks the owner-email paragraph (`owner_email.py:186`); the code never merges. |
| M13 | Signed webhooks only (Cloudflare and Google signatures) | Part | `agents/ghost/webhooks.py:1-5,63-117` (own HMAC over timestamp+nonce+body, replay window); `agents/ghost/app.py:778-800` (`x-autumbra-signature` headers) | This is Autumbra's own signing scheme, not Cloudflare's or Google's native verification. The secrets are empty by default. |
| M14 | No keys in code; the AI engine is never on a public address | Built | `agents/ghost/webhooks.py:20-21` (env names only); `agents/ghost/shields.py:23-26,52-54` (Watch holds no edge credential); `agents/ghost/enforce_apply.py:1-7` (Enforce calls no model) | — |
| M15 | Public, legitimate threat sources only; no dark web; no paid feed at launch | Built | `agents/ghost/advisories.py:11,35-45` (CISA KEV, OSV, GHSA, NVD, vendor releases); `agents/ghost/market_lab_intel.py:15,28-29` (refuses paid sources and YouTube/Instagram) | — |
| M16 | Red team tests only our own systems, or a client's with written permission | Built | `agents/ghost/red_team.py:39-60` | Exercises run on fixture logs only. |
| M17 | Small-business tier: connect Cloudflare and Google Workspace in five minutes, nothing installed | Part | `agents/ghost/client_settings.py:46-49,187-218` (hands are boolean toggles); `agents/ghost/app.py:713-745` | There is no real connect flow (no OAuth or API token) and no intake of Cloudflare event streams or Workspace alerts. |
| M18 | Logs are read and deleted, never stored, and the copy says exactly that | Built | `agents/ghost/client_settings.py:222`; `agents/ghost/owner_email.py:50-54`; `agents/ghost/perimeter.py:28` (`assert_no_client_payload`); webhook returns `stored: False` (`agents/ghost/app.py:797-845`) | — |
| M19 | Client modes (do / report only / approve) are the only clamp | Built | `agents/ghost/client_settings.py:17-23`; `agents/ghost/enforce_apply.py:95-100` | — |
| M20 | Owner update email built from receipts (on every action plus weekly), three paragraphs chosen by the client's setting | Part | Built by code in `agents/ghost/owner_email.py`, `agents/ghost/owner_email_jobs.py:273-378` | Only an in-memory `FixtureEmailTransport` exists (`owner_email.py:283-300`), and the weekly loop uses it (`app.py:268-272`). No real email is sent. |
| M21 | Speed budgets measured on every receipt (<2 s decision, <10 s shield, <30 s health, <60 s auto-undo) | Part | `agents/ghost/speed_budgets.py:8-13`; stamped in `agents/ghost/enforce_apply.py:85,144,148,154` | Measured only on the in-process fixture path, so it says nothing yet about a real edge. |
| M22 | Intel comes through Market Lab (Autumbra is its client); sources named on receipts; clients never see a feed list | Part | `agents/ghost/market_lab_intel.py:1-7,97-120`; `agents/ghost/app.py:754-776` (consume route) | Only the consumer side exists. Nothing in `agents/market_lab` produces `market_lab.ioc.v1` bundles. |
| M23 | Dogfood on our own sites first; the supply-chain watch is feed one | Part | The advisory watcher is real code: `agents/ghost/advisories.py:604-712,763`; daily inventory of Tervory hosts at `agents/ghost/app.py:130-165,307`; `agents/ghost/inventory.py:30` (WATCHED_SITES) | Matches only reach dry-run proposals, and fix-as-PR is off (M12). Deploy state is not visible. |
| M24 | Done when: on our own sites a test attack is shielded in seconds, undone in one tap, and the receipt reaches the founder | Part | `tests/test_autumbra_fixture_attack.py`; `tests/test_autumbra_watch_enforce_pipe.py` | Proved only against the fixture edge, not against our own sites. |
| M25 | Plain English and no sample data on client screens; empty states say "No work yet" | Part | The public `/autumbra` page always renders `PUBLIC_AUTUMBRA_FIXTURE` (`workspace/app/autumbra/page.tsx:3,9`; `fixtures.ts:1-30`). The founder console silently falls back to fixtures (`workspace/app/admin/autumbra/page.tsx:9-38`; `shields-data.ts:29-38`) | A live screen shows fixture data. |
| M26 | Learning ladder: training pairs through Tank; blocked attacker addresses shared across clients | Not started | Searched `agents/ghost` for training/save_pair/propagation: only `gold_sources.py` | — |
| M27 | OSS lanes (Watch intake via Vector/Fluent Bit/Steampipe/OpenCTI, Enforce Ansible/Terraform, guardrails door) | Part | `agents/ghost/watch_oss/`, `agents/ghost/enforce_oss/`, `agents/ghost/guardrails.py:26,41` | All built but switched off; Enforce OSS is dry-plan only (PRs #290, #291, #286). |

### N. Infrastructure

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| N1 | Two regions (Boston us-east, ZA) — ZA stopped by founder 25 Oct; per-tenant region flag | Stopped | ZA stack docker-compose.za.yml:1-6; switch ZA_OFFLINE .github/scripts/deploy_changed.py:26-28,122-126 (#246), .github/scripts/watchdog.py:36-40,258-292 (4cdda27); region guard tank/main.py:75-79,138-159 | ZA is code-complete but off via the repo var ZA_OFFLINE. The per-tenant region flag is only in agent_zenas.tenants. Tank's tenant column is a TODO (main.py:144). |
| N2 | Secrets in Doppler (founder uses Coolify settings) — record which | Replaced | Coolify environment panel: .env.example:1, mcp/README.md:9, deploy token .github/workflows/deploy-on-merge.yml:25-26 | Coolify settings are used, not Doppler: no Doppler code or config exists. README.md:17 still says "put the values in Doppler" (stale). |
| N3 | Backups 3-2-1: daily Postgres dump, Qdrant snapshot, R2/B2 offsite; restore drill < 4h | Part | Nightly encrypted pg_dump to R2: jobs/train/backup.py:1-5,48-67,92; jobs/train/Dockerfile.backup CMD --nightly; service docker-compose.yml:270-303 | Postgres to R2 only. The service is behind `profiles: ["r2-backup"]` (docker-compose.yml:271), so it is off unless that profile is enabled. No Qdrant snapshot, no second offsite copy (B2), and no restore drill (searched snapshot/pg_restore/restore drill). |
| N4 | Hardening: UFW, SSH keys, Fail2ban, Cloudflare WAF, non-root containers, Postgres RLS on tenant_id, Qdrant keys per tenant | Part | Non-root USER in most Dockerfiles (tank/, hermes/, workspace/, agents/*, mcp/, jobs/train); cap_drop/no-new-privileges e.g. docker-compose.yml:280-283 | No Postgres RLS (no ENABLE ROW LEVEL SECURITY/CREATE POLICY anywhere). Qdrant uses one shared key, not per tenant. litellm, searxng, site and tiger Dockerfiles have no USER line. UFW, SSH, Fail2ban and the Cloudflare WAF are not in the repo (Ghost WAF files are unapplied templates, agents/ghost/configs/enforce/terraform/cloudflare_waf_rule.tf.tpl:1). |
| N5 | CI: Gitleaks + Semgrep on every commit; Playwright on Workspace; Radix deploy gate on own repo | Part | CI .github/workflows/ci.yml:5-14,138-148 (ruff + tests/test_secrets.py regex scan + Tank boots), 184-230 (Playwright on savings pages only) | A home-grown regex secret test replaces Gitleaks in CI, and there is no Semgrep in CI. Gitleaks and Semgrep exist only as Radix client scanners (agents/radix/Dockerfile:18-22). Playwright covers savings pages only. No Radix deploy gate on its own repo was found. Docs-only changes skip CI. |
| N6 | Monitoring: Uptime Kuma, Grafana alert on egress, watchdog | Part | Watchdog every 10 min: .github/workflows/watchdog.yml:15, .github/scripts/watchdog.py:1-30 (sites, Coolify app status, TLS expiry) (#42, #89) | Uptime Kuma is replaced by the GitHub Actions watchdog (OPS4 brief). No Grafana or Prometheus, and no egress alert (searched grafana/prometheus/uptime-kuma). |
| N7 | Industry engines as packages (FFL first; template for new vertical) | Part | Engine contract agents/base/pipeline.py:30-31 (<engine>.ingest/.profile); FFL skills tank/skills/ffl.ingest, ffl.profile; agents/base/engines/ffl/reference.py, atf_gold.py; engine pick agents/base/room.py:162-171, app.py:400-403 (#188, #339, #352) | FFL is the only engine, and it is Skala skills plus files inside the Base room rather than a separate package. No template or scaffold for a new vertical exists (agents/_template is a room template, not an engine). |

### O. Other planned products

| ID | Planned | Status | Evidence on main | What is missing |
|---|---|---|---|---|
| O1 | In-video shopping agent (VSHOP-1: upload, scenes, detect, match through Rig, shoppable player, Buy → AmmoSync) | Not started | Only the brief exists: `docs/cursor/AGENT-in-video-shopping.md`, `docs/cursor/VSHOP-1-phase-1.md` (commit `23ee17d`). Searched `agents/` (no `vshop`), `workspace/app` (no `vshop`), `tank/skills` (no `vshop.*`), remote branches; the only hit is a path string in `tests/test_ci_minutes_workflows.py:223` | The whole room, skills, page and tests are still to build, and the agent still needs a name. |
| O2 | ZA2: the full squad on the ZA box, in rand | Stopped | Founder stopped ZA on 25 Oct (`docs/build/BUILD-LISTS-2026-10-25.md:137`). Only `agents/zenas/docker-compose.za.yml` and `docker-compose.za.yml` exist; no `APP_URL_ZA` in `workspace/` | Only design docs (`886aa0c`, `7f274f0`, `59f8e01`). |
