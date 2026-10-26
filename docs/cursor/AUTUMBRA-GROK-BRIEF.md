# Autumbra (Protect) — Grok living brief

Product host: protect.tervory.com. Code room: `agents/ghost` (short-term). Branch: `grok/autumbra`. Never merge. Never deploy live Boston. Coolify by name only. Tank is the only model door. Later founder prompts win when they conflict.

Draft PR: https://github.com/zenascapetown-code/tervory-tank/pull/337

## Agreed with founder (2026-10-26) — Zenas + Tervory

1. **Agnostic product.** Autumbra does **not** assume Cloudflare, Google Workspace, Shopify, or Woo. It is a **24/7 AI security guard**. Optional connects (CF, Shopify, Google, host firewall, etc.) are **client choice**, like linking a tool in Claude.
2. **One clear SMB price for the full product.** If a client skips connects they chose a smaller Autumbra — not false advertising. Second tier: **Enterprise FROM** price after infra assessment. Goal: show receipts. No tier fluff.
3. **Free Cloudflare is enough** for IP-block shields when they connect CF. Never require Pro / $20 to use Autumbra. **We do not sell Cloudflare.**
4. **Without any connect:** stack half + advisories + fix PRs + receipts still work. **"Block in seconds" lights up when a hand is connected.** Say that plainly in product copy.
5. **Differentiation (tip of the spear):** air gap (Watch dirty / Enforce ThreatPayload-only + keys) + receipts + zero-keep logs + one price + optional hands. **IP filing for the air gap is serious** (delay competitors, force acknowledgment → traffic).
6. **Training:** receipt→rule loop first (Atomic Red Team / Caldera on own sites). GPU / HF fine-tune later **via Tank only**. Founder-approved capacity (names only): HF monthly allowance + unused 1TB storage bucket — document as launch capacity, no secrets. **Case studies: 5 exist** — launch assets.
7. **Founder recommendations** (still pending explicit yes on each): cap 20; test host not Boston; extend seal-check; paid feeds off; secret name `AUTUMBRA_CF_API_TOKEN_<tenant_slug>`; `tervory.com` zones until dogfood passes; guardrails off except named exercise.

## Product shape (infra + behaviour)

- **Air gap:** Watch may read dirty text. Enforce reads **ThreatPayload only**. Any raw byte into Enforce = fail. Keys for edge apply live only on per-client Enforce.
- **Optional hands:** CF / Google / Shopify / host firewall / etc. — client choice. Watch stays shared and tenant-scoped. Enforce = **one container per client** when an edge hand needs it; internal network; own ThreatPayload queue; Coolify secret **name** `AUTUMBRA_CF_API_TOKEN_<tenant_slug>`; disconnect destroys container + secret binding.
- **Isolation:** Client container never shares network/volume/secret with Tank, Workspace, tervory.com, or another client.
- **Perimeter not import:** Stream events → act per settings → discard. Receipt = what Tervory did only. Stack inventory = versions / package names. Copy: we read logs, acted, deleted them — nothing kept.
- **Apply modes (fixes AND shields, separate):** approve-each (default) | auto-when-checks-pass | never. Tervory never changes them.
- **Owner email:** every act + weekly; code-built from receipts; three fix paragraphs by setting.
- **Partners / hands:** use each provider’s own APIs when connected; never disable, replace, or work around them. We do not sell Cloudflare.
- **Sources:** free registry first; cross-check; weights; no dark web / no onion crawl. Paid feeds off until founder yes.
- **Speed:** rule decision <2s; shield <10s; health <30s; auto-undo <60s e2e; model off shield critical path. “Block in seconds” requires a connected hand.
- **Red team / training:** standing exercises on Tervory’s own sites (Atomic Red Team / Caldera → receipt→rule). Client only with written permission. GPU/HF fine-tune later through Tank only.

## Inventory

### On main before this branch (switched off / dry) — KEEP
ThreatPayload, Enforce stub (`wraith.py`), rails, guardrails (OFF), Shields Up, inventory/advisories, patch-as-PR, Watch OSS, Enforce OSS, airgap dogfood, isolation corridor, seal-check (base/radix/tiger/rig).

### Landed on `grok/autumbra` (draft #337)
1. Tank one-door dogfood + `tests/test_tank_one_door.py` (Base `run_code_first` runtime skips until that lane lands).
2. Watch compose: no edge write credential. Per-client `docker-compose.enforce.yml` (`internal: true`).
3. Secret **name** pattern: `AUTUMBRA_CF_API_TOKEN_<tenant_slug>` (compose env `AUTUMBRA_CF_API_TOKEN`).
4. Never-block + IP-in-log + action cap; `block_ip` / `revoke_sessions`.
5. Client apply settings + optional hands (`cloudflare`, `google_workspace`, `shopify`, `host_firewall`) + `block_in_seconds` half.
6. Owner email builder; source registry; signed webhooks; red-team; enforce lifecycle plans; perimeter residual; speed budgets; Enforce ThreatPayload-only apply; `/ghost/autumbra/*` routes; fixture-attack test.

### Still open for Claude / founder
- Product copy: one SMB price; Enterprise FROM; plain “block in seconds when a hand is connected”; empty “No work yet”.
- IP filing for air gap (legal / ops — founder).
- Case-study packaging (5 exist) + launch assets list.
- Document Founder-approved resources by **name only**: HF monthly allowance, unused 1TB storage bucket (no secrets, no spend without yes).
- Live dogfood on own sites on **test host**; seal-check paste from host.
- Explicit yes/no on each Founder recommendation below.
- Independent reviewer from fresh clone.

## Source registry — first free entries
ransomware.live, RansomLook, ransomwatch; abuse.ch URLhaus/ThreatFox/Feodo/MalwareBazaar; Spamhaus DROP; Shadowserver; Tor exit list; CISA KEV; OSV; GitHub Advisory DB; NVD; HIBP domain search; founder-approved researcher RSS (leads only).

## Founder recommendations (pending explicit yes on each)
| # | Recommendation |
| --- | --- |
| 1 | Enforce container cap **20** (soft; refuse above) |
| 2 | Server work on **test host**, never live Boston; smallest Enforce option = separate Coolify compose resource on existing test host |
| 3 | Extend `ops/seal-check.sh` EXPECTED_SEALED for Autumbra Watch / enforce-* before live |
| 4 | Paid threat feeds **off** until named |
| 5 | Coolify secret name pattern **`AUTUMBRA_CF_API_TOKEN_<tenant_slug>`** (names only in git) |
| 6 | `ALLOWED_ZONES` stay **tervory.com** until own-site dogfood passes |
| 7 | Guardrails **off** except a named dogfood exercise |

## Founder-approved resources (names only — no secrets)
- Hugging Face monthly allowance (inference / jobs capacity for later Tank-only fine-tune — not wired; no spend without go).
- Unused **1TB** storage bucket (launch capacity — not wired).
- Case studies: **5** exist (launch assets).

## Pytest (local last run)
```
PYTHONPATH=. python3 -m pytest -q tests/test_autumbra_*.py tests/test_ghost_*.py tests/test_tank_one_door.py
# ~281 passed, skips for live dogfood + Base run_code_first
```
seal-check: exit 2 on builder box (no Docker socket). Re-run on Coolify test host.

## Claude handoff checklist
- [ ] Read this brief + PR #337 “Agreed with founder” section first
- [ ] Keep air gap + optional hands; never require CF Pro; never assume a connect
- [ ] Product copy: one SMB price; Enterprise FROM; block-in-seconds only when hand connected
- [ ] No merge / no Boston deploy / Coolify by name only / Tank only for models
- [ ] Training: receipt→rule first; GPU/HF later via Tank; document approved resources by name only
- [ ] Get explicit yes on each Founder recommendation before spending or enabling flags
- [ ] Independent review from fresh clone; one finding = fail
