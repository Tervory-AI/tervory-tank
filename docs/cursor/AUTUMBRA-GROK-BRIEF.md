# Autumbra (Protect) — Builder brief for Grok

Product host: protect.tervory.com. Code room: `agents/ghost` (short-term). Branch: `grok/autumbra`. Draft PR: https://github.com/zenascapetown-code/tervory-tank/pull/337

**Never merge. Never deploy live Boston. Coolify by name only. Tank is the only model door. No CloudAgent. No Clerk. No demo copy.**

Later founder prompts win when they conflict with older body text. **Where this body and the Corrections section conflict, the Corrections win.**

## Body (product shape)

1. **Agnostic product.** Autumbra does **not** assume Cloudflare, Google Workspace, Shopify, or Woo. It is a **24/7 AI security guard**. Optional connects are **client choice**.
2. **One clear SMB price** for the full product. Second tier: **Enterprise FROM** after infra assessment. Goal: show receipts.
3. **Free Cloudflare is enough** for IP-block shields when they connect CF. Never require Pro. **We do not sell Cloudflare.**
4. **Without any connect:** stack + advisories + fix PRs + receipts still work. **"Block in seconds" lights up when a hand is connected.**
5. **Air gap:** Watch may read dirty text. Enforce reads **ThreatPayload only**. Keys for edge apply live only on per-client Enforce.
6. **Isolation:** Client Enforce never shares network/volume/secret with Tank, Workspace, tervory.com, or another client.
7. **Apply modes (fixes AND shields, separate):** approve-each (default) | auto-when-checks-pass | never. Tervory never changes them. **Client modes are the only clamp** — no separate Enforce "strength".
8. **Owner update email:** every act + weekly; **built by code from receipts**; exact wording below; three fix paragraphs by setting; tested with three fixture clients.
9. **Training:** receipt→rule first (Atomic Red Team / Caldera on own sites). GPU/HF fine-tune later **via Tank only**. HF = temporary dogfood/learning only — not permanent Enforce home.
10. **Red team:** standing exercises on Tervory's own sites; receipts marked `exercise`. Client only with written permission.
11. **Partners / hands:** use each provider's own APIs when connected; never disable or work around them.

### Owner update email — exact wording

Subject: `Autumbra update for {site}: {n} threats found, {c} critical`

Opening (numbers link to the receipt):

> This week we found {n} threats to {site}. {c} were critical: out-of-date {stack_list} with known holes serious enough to take down a company's whole IT system. (Each one is linked to its public advisory.)

**Fix paragraph — auto when checks pass:**

> You chose to let us fix this kind of problem automatically, so we did. {stack_list} are now on patched versions and your site passed its own checks afterwards. Here is the report; you can send it to your IT manager, who can reverse our change with one click. {Undo}

**Fix paragraph — I approve each one:**

> You chose to approve fixes yourself. We have built the fix and it is waiting for your approval here. {Approve the fix} Until you approve it, the hole is still open; we have reduced the risk at the edge as described below.

**Fix paragraph — Never:**

> You chose that we never touch your code. Here is exactly what to fix and how. {Report} We have reduced the risk at the edge as described below.

**Shield paragraph (when a shield ran):**

> We also stopped an attack in progress. It was blocking addresses known to be part of a widely reported campaign ({source}). We blocked {n} addresses that were attacking your site. Your own addresses, your payment provider and Cloudflare were never blocked. If this caused any problem, undo it here with one tap. {Undo}

Closing:

> Nothing from your logs was kept. We read them, acted, and deleted them. {Full receipt}

Critical wording only when a public advisory rates it critical / known_exploited.

### Carry-on jobs (until independent review lands)

1. Owner update email from receipts — exact wording above; three client-mode paragraphs; tests with three fixture clients.
2. Red-team exercise against our own sites as a receipt marked `exercise`.
3. Measure Enforce memory on dogfood so the container cap is a number, not a guess.
4. Isolation network test from inside a fixture client's container.

## Corrections (founder 2026-10-26 — **win on conflict**)

Zenas accepted these. They override any conflicting body text above and any older brief / PR wording.

1. **Market Lab is Autumbra's intel backend.** Do **not** build a feed list or a source registry in Autumbra. **Consume Market Lab's output** and **name the source on the receipt**. Clients never see the feed list (backend job).
2. **Launch intel: public + Market Lab only — no paid buy.** Paying is for speed; we do not buy if it is not faster. Public at launch includes abuse.ch (URLhaus / ThreatFox / Feodo when data exists), LevelBlue OTX, CISA KEV. Escalation only via Tank after a measured gap.
3. **Reddit in** for speed (best threads curated in Market Lab). **YouTube never. Instagram never** (clickbait / AI ads poison Market Lab).
4. **Main Market Lab** learns skills and spins them to product clones. **Autumbra / AmmoSync / TNGO each get their own Market Lab clone.** Reddit lists live in clone notes, not this PR.
5. **HF = temporary dogfood / learning only**, not permanent Enforce home. Permanent Enforce on our VPS/cloud.
6. **No Cloudflare secret names yet** — hold until a real CF (or other edge) client. Agnostic.
7. **Enforce: dogfood first, then open to clients** (not a fixed zone list).
8. **No separate Enforce "strength"** — only client modes: do the work / report only / send for approval.
9. **Enforce container cap: hold until measured dogfood / Boston RSS** — do not guess 6, 8, or 20.
10. Pin `EXPECTED_SEALED` after first clean dogfood.
11. Independent review of draft #337 from a fresh clone against this brief; one finding = fail. Do not wait on the comment — work the four jobs in parallel. Never ask to merge.

## Pytest focus

```bash
cd /workspace/ghost-build/tervory-tank
source /workspace/tank-venv/bin/activate
PYTHONPATH=. python3 -m pytest -q \
  tests/test_autumbra_*.py \
  tests/test_ghost_*.py \
  tests/test_tank_one_door.py
```

seal-check / live Docker: builder box has no Docker socket for this worker — re-run memory + isolation on Coolify **test** host (never live Boston).
