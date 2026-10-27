# Grok brief: Autumbra, built in its own box (full version, 26 Oct 2026)

Read `00-RULES-FOR-ALL-BUILDERS.md` first. Branch: **`grok/autumbra`** from `origin/main`. Everything for Autumbra goes on this one branch until it is complete in full. Nothing from it merges or deploys until the founder says the whole product is ready. Don't ask.

## Start from
The Autumbra code already on main (#281–#304: the threat form between the two halves, Watch and Enforce, the Shields board, fixes as PRs, all switched off). Not from any outside scripts. Take `agents/ghost/dogfood_hf.py` from branch `codex/tank-one-door` first: it moves the synthetic dogfood off the Hugging Face inference token and through Tank (`/v1/route`, task `reason.brief`, platform tenant). Autumbra never holds an inference key; every model call goes through Tank; the guard `tests/test_tank_one_door.py` will be in CI and fails the build on any direct provider call in `agents/ghost`.

## What Autumbra is
A perimeter guard for a business that has Cloudflare and Google Workspace and no IT department. Nothing installed on their machines. It watches what passes the perimeter, stops attacks with reversible shields, closes holes in the stack with ready-made fixes, and explains every action in plain English with an undo. Defence only. Partners with Cloudflare and Google, never fights them. Built to scale to enterprise, proven first on small business and on Tervory's own servers.

## Infrastructure and the air gap (not optional; this is the product's shape)
**The two halves.** Watch and Enforce are separate processes on separate networks, and the only thing that crosses between them is a validated `ThreatPayload` (`agents/ghost/threat_payload.py`, #281). Watch may read dirty text: event streams, webhook bodies, triage JSON. Enforce never reads raw input; it reads `ThreatPayload` only (`agents/ghost/wraith.py` + `rails/`, #284). That is the air gap (`docs/cursor/AUTUMBRA-6-dual-llm-airgap.md`). Any change that lets Enforce see a raw byte is a fail.

**Networks and boxes.**
- Watch runs in the `agent-ghost` container on the gateway network with its own browser container (`agents/ghost/docker-compose.yml`). It reaches Tank and the public sources. It holds no client credential.
- **Enforce is one container per client, not shared.** When a client connects Cloudflare, Tank asks the Autumbra room to create that client's Enforce container (Coolify API by name, or compose with a per-tenant project name) on its own internal-only network (`internal: true`), holding only that client's zone-scoped credential as a named secret, with its own `ThreatPayload` queue and its own receipts. Disconnecting the client destroys the container and its secret. Creation and destruction are receipts the founder can see. Cap containers per host; write the cap under Founder must decide.
- **Isolation is the point.** A compromised client's traffic can never reach Tervory's own services or another client. No client container shares a network, volume or secret with Tank, the Workspace, tervory.com or any other client's container. Prove it with `ops/seal-check.sh` on every box and a network test from inside a fixture client's container that fails to reach every Tervory service except its own queue and Cloudflare's API.
- The AI engine (Tank through LiteLLM) is never on a public address. Watch calls Tank; Enforce never calls a model.
- Inbound webhooks (Cloudflare, Google) enter only through Traefik, signature-checked at the edge of Watch before anything is parsed. Unsigned or badly signed requests are dropped and counted, never stored.
- The guardrail door (`agents/ghost/guardrails.py`, flag off by default) sits in front of Watch's triage; arm it only for dogfood with the flag, and say so in the PR.
- No privileged containers, no Docker socket, no host mounts. Server work happens on a separate test host or service, never the live Boston apps, until the founder says deploy. If a second host is needed, write the smallest option under Founder must decide; no spend without the founder.

**The perimeter, not an import.** Autumbra never imports, copies or stores a client's data. It reads traffic metadata and security alerts, never content: Cloudflare's event stream and Google Workspace alerts are read as they arrive, checked, acted on according to the client's settings, and discarded. Nothing is written to disk outside Watch's working memory, and nothing leaves the client's Enforce box except the receipt. The receipt holds only what Tervory did: time, action, the addresses blocked (needed for undo), the advisory matched, the client's setting that governed it. The stack inventory is version numbers and package names, never code or content. Autumbra never asks for content scopes (no mailbox read, no database). The client copy says exactly this, and a test proves that after a run no client payload exists anywhere on Tervory's side.

## Build in this order, each step proven on our own sites before the next
1. **Never-block list and IP check.** Never block the client's own IPs, payment providers or Cloudflare. The IP must appear in the raw event before anything acts on it. Plain rules decide first; the AI is a second opinion only, never in the critical path of a shield. Actions per hour are capped. False positives are the whole risk; this step is the licence to exist.
2. **Reversible shields, applied immediately:** block an IP, turn on a WAF rule, rate-limit a path, revoke sessions. Each has a health check, an automatic Undo if the site breaks, a one-tap Undo, and a receipt. Shields use Cloudflare's and Google's own controls through their own APIs; Autumbra never disables, replaces or works around a protection the client already has.
3. **Code fixes arrive as a ready PR. How it's applied is the client's choice**, set per client in their Autumbra settings, default "I approve each one":
   - "I approve each one": the PR waits for the client's one tap. Default.
   - "Apply automatically when checks pass": merges itself only if the client's own CI is green, the change is inside the files Autumbra may touch for that client, and the client turned this on in writing in the settings page. Every auto-merge gets a receipt and a pre-made revert PR as the one-tap Undo.
   - "Never": Autumbra reports and proposes only.
   The same three choices apply to shields, separately. Stored per client, shown on every receipt, changeable at any time. Tervory never changes it.
4. **Signed webhooks only** (Cloudflare and Google signatures). No keys in code.
5. **Public, legitimate sources only.** No offensive tooling. Red-team exercises only against our own systems, or a client's with written permission (item 12).
6. **The small-business tier:** connect Cloudflare and Google Workspace in five minutes, choose the three settings, done. Nothing to install.
7. **Dogfood on our own sites first.** The supply-chain watch is feed one: nightly inventory of what each host runs (PHP, Node, Python, Docker images, every lockfile) against the vulnerability lists; last week's PHP, Node and Python on Boston are the opening story. Fix as PR, the client's own checks as the gate, undo ready.
8. **The owner's update email.** Every time Autumbra acts, and once a week regardless, one email in plain English, built by code from the receipts (no model), every number linked to its receipt. Exact wording, variable parts in brackets:

   Subject: Autumbra update for [site name]: [10] threats found, [3] critical

   This week we found [10] threats to [site name]. [3] were critical: out-of-date [PHP, Python and Node] with known holes serious enough to take down a company's whole IT system. (Each linked to its public advisory.)

   Then ONE of three paragraphs, chosen by the client's code-fix setting:
   - [apply automatically] You chose to let us fix this kind of problem automatically, so we did. [PHP, Python and Node] are now on patched versions and your site passed its own checks afterwards. Here is the report; you can send it to your IT manager, who can reverse our change with one click. [Undo link]
   - [I approve each one] You chose to approve fixes yourself. We have built the fix and it is waiting for your approval here. [PR link] Until you approve it, the hole is still open; we have reduced the risk at the edge as described below.
   - [never] You chose that we never touch your code. Here is exactly what to fix and how. [Report link] We have reduced the risk at the edge as described below.

   Then, if a shield was applied: We also stopped an attack in progress. It was part of a widely reported campaign ([public source]). We blocked [214] addresses that were attacking your site. Your own addresses, your payment provider and Cloudflare were never blocked. If this caused any problem, undo it here with one tap. [Undo link]

   Closing line, always: Nothing from your logs was kept. We read them, acted, and deleted them. [Full receipt]

   Rules: "critical" means a public advisory rates it critical and the link proves it. "Blocked addresses" means the specific attacking addresses with the count, never all traffic. The client's setting picks the paragraph; Tervory never overrides it. A quiet week still sends: "Quiet week. [1,204] checks, 0 threats, 0 actions." Test: three fixture clients with the three settings each receive the right paragraph with the right links.
9. **Partners, not rivals.** Cloudflare does the edge; Google does the mailbox; Autumbra decides and explains within the client's limits. If a client has neither, the stack half still runs and the page says which half is active.
10. **Many eyes, not two.** Watch takes signals from public, legitimate sources, free first per the ladder; paid ones named under Founder must decide and off. One source alone never triggers a shield unless the client set "act on single source". Every source is named on the receipt. A source registry page lists each source, who runs it, its licence, refresh rate, last-seen time, and its track record scored on our own receipts (first / confirmed / wrong); weights are visible and no source, Cloudflare and Google included, is trusted alone. Other edges and hosts later (AWS/CloudFront, Vercel, cPanel-style hosts) are new intake adapters into the same `ThreatPayload`, never a change to Enforce.
11. **Speed, measured** on every receipt and shown on the founder's console: event seen → decision under 2 s for rule hits; decision → shield applied under 10 s; health check after a shield under 30 s; automatic undo on a failed health check under 60 s end to end. Test with a fixture attack and assert the budgets.
12. **Red team ourselves, always.** A scheduled exercise against Tervory's own sites (a client's only with written permission): credential stuffing from a fixture address list, a path scan, an out-of-date package planted in a test branch, a forged webhook. Each is a receipt marked "exercise" and feeds the learning: every miss becomes a rule or a training pair; every false positive lowers a threshold. Never against anyone else. The exercise list and last results are on the founder's console.
13. **Source registry, first entries** (public, legitimate, free; each with licence, link, owner and a credit line on every receipt it contributes to): ransomware.live, RansomLook, ransomwatch (leak-site trackers run by researchers); abuse.ch URLhaus / ThreatFox / Feodo / MalwareBazaar, Spamhaus DROP, Shadowserver daily reports (register our ranges and each client's), the Tor exit list; CISA KEV, OSV, GitHub Advisory Database, NVD, GitHub "exploit published" signals; Have I Been Pwned domain search for each client's domain; a founder-approved list of researcher accounts and newsletters read by RSS/public posts, leads only, never a trigger alone. Autumbra reads what these publish; it never operates accounts on criminal sites or crawls onion services itself. The registry page credits every source by name with a link, and the founder's console lists which accept support.
14. **Learning and the ladder.** Rules first, a model as second opinion, graduating to code as Autumbra learns each client's normal. Show the client the curve ("Decisions made by our own rules this month: 97%"). When one client's box blocks an attacker's addresses, every other client's box gets those addresses within seconds; only the attacker's fingerprints move, never client data. Every action, undo, exercise result and client reaction is stored through Tank as a training pair for that tenant.

## Box rules, in addition to the common rules
- No privileged containers, no Docker socket. Never weaken a seal.
- Coolify settings by name only. Never type, see or store a secret.
- Autumbra and Ghost are defence only.
- Every Tank read and write scoped by `tenant_id`. Platform work uses `PLATFORM_TENANT`.
- No new paid service, key or provider. If one seems needed, write it under Founder must decide and build without it.
- Plain English on every client screen and email, written for an owner who learned what Cloudflare was a month ago: no "WAF rule", no model names, no build codes, no sample data. Empty states say "No work yet".

## Tests, locally, before any PR
`PYTHONPATH=tank python3 -m pytest -q` on `tests/test_ghost_*.py`, `tests/test_autumbra_*.py` and everything you add; the one-door guard; the air-gap test (a crafted injection in an event line is quarantined into a `ThreatPayload` with the fixed burn detail, and Enforce's input is only the payload fields); the isolation network test; `ops/seal-check.sh` output pasted in the PR; and the Workspace build if you touch it: `cd workspace && npm install --no-package-lock --no-audit --no-fund && NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy npx next build`.

## Done when
On our own sites, a test attack is shielded in seconds, undone in one tap, the owner email arrives with the right paragraph, the receipt reaches the founder, and no client payload exists on Tervory's side afterwards. Then one draft PR with the full proof (the job step by step as a client experiences it; what changed, file and line; how tested, exact commands and results; screenshots; Founder must decide), and stop. An independent reviewer checks it from a fresh clone; one finding is a fail. Never ask to merge.

## Corrections from the founder, 26 Oct 10:52 PT (these override anything above that conflicts)
- **Keep the spine:** air gap (Watch dirty / Enforce ThreatPayload-only), Tank one door, per-client Enforce, receipts + undo, optional hands.
- **Agnostic product.** Don't assume Cloudflare, Shopify or Google. Cloudflare Free is used only if the client connects it; never sell Cloudflare Pro. "Block in seconds" is promised only when a hand (a connected control) exists.
- **Client modes are the only clamp:** do / report only / approve. No separate Enforce "strength" setting.
- **Price:** one SMB price for the full product; Enterprise "from" a price after an assessment.
- **Autumbra is a client of Market Lab (backend).** Market Lab does the intel job (public feeds + research) and learns the skills; it spins clones, and Autumbra, AmmoSync and TNGO each get their own Market Lab. Clients never see the feed list. The source registry in items 10 and 13 lives in Market Lab, not on an Autumbra client page.
- **Launch intel: public sources and Market Lab only. No paid feed.** Paying is only ever for speed; don't buy anything that isn't faster. Reddit: yes. YouTube and Instagram: never.
- **Hugging Face is temporary**, for dogfood and learning only; not Enforce's permanent home.
- **Enforce cap:** don't guess. Measure dogfood and Boston memory (RSS) first, then set it. Pin the seal after the first clean run.
- **Cloudflare secret names:** hold until there is a real Cloudflare client. Enforce is dogfood-first, then opened to clients.
- **Draft work lives on PR #337** (grok/…), still draft: no merge, no Boston deploy, Coolify names only, Tank for keys and spend, no Clerk, no "demo" copy.
